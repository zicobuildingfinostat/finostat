"""Event calendar with the option premium attached.

Three sources, one table: contract expiries (from the instrument masters),
results dates for F&O stocks (NSE's corporate board-meetings feed, refreshed
every six hours), and a small editable list of macro dates (events.json:
RBI policy, Budget, FOMC...). For every row the calendar shows the implied
move the market is pricing across that date -- the ATM straddle of the
nearest expiry on or after the event, as a percentage of spot -- so
"TCS results Thursday" reads as "market pricing ±4.2%".
"""
from __future__ import annotations

import http.cookiejar
import json
import logging
import pathlib
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

log = logging.getLogger("finostat.events")

IST = timezone(timedelta(hours=5, minutes=30))
NSE_BM = "https://www.nseindia.com/api/corporate-board-meetings?index=equities"
NSE_HOME = "https://www.nseindia.com/companies-listing/corporate-filings-board-meetings"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
MACRO_FILE = pathlib.Path(__file__).resolve().parent / "events.json"
INDEX_LABEL = {"NIFTY": "NIFTY 50", "BANKNIFTY": "BANKNIFTY", "FINNIFTY": "FINNIFTY", "SENSEX": "SENSEX"}


def parse_bm(rows: list, fo_names: set) -> list[dict]:
    """NSE board meetings -> results events for F&O names."""
    out, seen = [], set()
    for r in rows or []:
        sym = str(r.get("bm_symbol") or "").upper()
        text = f"{r.get('bm_purpose', '')} {r.get('bm_desc', '')}".lower()
        if sym not in fo_names or "result" not in text:
            continue
        try:
            d = datetime.strptime(str(r.get("bm_date")), "%d-%b-%Y").date()
        except (TypeError, ValueError):
            continue
        key = (sym, d)
        if key in seen:
            continue
        seen.add(key)
        out.append({"date": d.isoformat(), "kind": "results", "u": f"NSE:{sym}", "title": f"{sym} results",
                    "detail": (r.get("bm_desc") or "")[:160]})
    return out


def load_macro(path: pathlib.Path = MACRO_FILE) -> list[dict]:
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    out = []
    for e in raw if isinstance(raw, list) else []:
        try:
            datetime.strptime(str(e.get("date")), "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        out.append({"date": e["date"], "kind": "macro", "u": e.get("u") or "NIFTY 50", "title": str(e.get("title", ""))[:80],
                    "detail": str(e.get("detail", ""))[:160]})
    return out


class Calendar:
    def __init__(self, contracts_of, chains, cache: pathlib.Path | None = None, interval: float = 6 * 3600):
        self.contracts_of, self.chains, self.cache, self.interval = contracts_of, chains, cache, interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.results: list[dict] = []
        self.fetched: float | None = None
        self.error: str | None = None
        self._moves: dict = {}          # (u, expiry) -> (ts, move dict)
        if cache and cache.exists():
            try:
                d = json.loads(cache.read_text())
                self.results, self.fetched = d.get("results", []), d.get("fetched")
            except (ValueError, OSError):
                pass

    def start(self) -> None:
        threading.Thread(target=self._run, name="events", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    # -- results dates ------------------------------------------------------
    def refresh(self) -> bool:
        contracts = self.contracts_of()
        names = set(contracts.names()) if contracts else set()
        if not names:
            return False
        try:
            cj = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
            op.open(urllib.request.Request(NSE_HOME, headers=h), timeout=20).read(2000)      # cookies
            r = op.open(urllib.request.Request(NSE_BM, headers=dict(h, Accept="application/json", Referer="https://www.nseindia.com/")), timeout=20)
            rows = json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            self.error = str(exc)[:160]
            log.warning("events: NSE board meetings: %s", exc)
            return False
        parsed = parse_bm(rows, names)
        with self._lock:
            known = {(e["u"], e["date"]): e for e in self.results}
            for e in parsed:
                known[(e["u"], e["date"])] = e
            today = datetime.now(IST).date().isoformat()
            self.results = sorted([e for e in known.values() if e["date"] >= today], key=lambda e: e["date"])
            self.fetched, self.error = time.time(), None
        if self.cache:
            try:
                self.cache.write_text(json.dumps({"results": self.results, "fetched": self.fetched}))
            except OSError:
                pass
        log.info("events: %d upcoming results dates for F&O names", len(self.results))
        return True

    def _run(self) -> None:
        # The contract index is built when the feed resolves, a few seconds after
        # start: retry with backoff until a refresh succeeds, then settle down.
        delay = 15.0
        while not self._stop.is_set():
            ok = self.refresh()
            wait = self.interval if ok else min(delay, 600.0)
            if not ok:
                delay *= 2
            if self._stop.wait(wait):
                break

    # -- assembling the calendar --------------------------------------------
    def expiries(self, days: int) -> list[dict]:
        contracts = self.contracts_of()
        if not contracts:
            return []
        now = datetime.now(IST)
        horizon = now + timedelta(days=days)
        out = []
        for name, label in INDEX_LABEL.items():
            for e in contracts.expiries(name):
                d = datetime.fromtimestamp(e / 1000, IST)
                if d <= horizon:
                    out.append({"date": d.date().isoformat(), "kind": "expiry", "u": label, "title": f"{label} expiry", "detail": "", "expiry": e})
        # stock options expire monthly: take the first F&O stock's list as the segment calendar
        for name in contracts.names():
            if name in INDEX_LABEL:
                continue
            exps = contracts.expiries(name)
            if exps:
                for e in exps:
                    d = datetime.fromtimestamp(e / 1000, IST)
                    if d <= horizon:
                        out.append({"date": d.date().isoformat(), "kind": "expiry", "u": "NSE:" + name, "title": "Stock options expiry (monthly)", "detail": "", "expiry": e, "segment": True})
                break
        return out

    def implied_move(self, u: str, date: str) -> dict | None:
        """ATM straddle % of the nearest expiry on/after the event date. Cached a minute."""
        contracts = self.contracts_of()
        name = next((n for n, l in INDEX_LABEL.items() if l == u), u[4:] if u.startswith("NSE:") else None)
        if not contracts or not name or not contracts.has(name):
            return None
        target = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST, hour=15, minute=30).timestamp() * 1000
        exps = [e for e in contracts.expiries(name) if e >= target]
        if not exps:
            return None
        expiry = exps[0]
        k = (u, expiry)
        hit = self._moves.get(k)
        if hit and time.time() - hit[0] < 60:
            return hit[1]
        try:
            chain = self.chains.chain(u, expiry)
        except Exception:
            return None
        atm = next((r for r in chain.get("rows") or [] if r.get("atm")), None)
        if not atm or not atm.get("ce") or not atm.get("pe") or not chain.get("spot"):
            mv = {"expiry": expiry, "warming": True}
        else:
            st = atm["ce"]["ltp"] + atm["pe"]["ltp"]
            mv = {"expiry": expiry, "straddle": round(st, 2), "pct": round(st / chain["spot"] * 100, 2), "spot": chain["spot"], "atm": chain.get("atm"),
                  "days": round(max(0.0, chain.get("t_years", 0) * 365), 1)}
        self._moves[k] = (time.time(), mv)
        return mv

    def calendar(self, days: int = 21, price: int = 12) -> dict:
        today = datetime.now(IST).date().isoformat()
        horizon = (datetime.now(IST) + timedelta(days=days)).date().isoformat()
        with self._lock:
            results = [e for e in self.results if today <= e["date"] <= horizon]
        rows = self.expiries(days) + results + [e for e in load_macro() if today <= e["date"] <= horizon]
        rows.sort(key=lambda e: (e["date"], {"macro": 0, "expiry": 1, "results": 2}[e["kind"]], e["u"]))
        priced = 0
        for e in rows:
            if priced >= price:
                break
            if e["kind"] == "expiry" and e.get("segment"):
                continue
            mv = self.implied_move(e["u"], e["date"])
            if mv:
                e["move"] = mv
                priced += 1
        return {"today": today, "days": days, "events": rows, "results_fetched": self.fetched, "results_error": self.error,
                "counts": {"expiry": sum(1 for e in rows if e["kind"] == "expiry"), "results": len(results), "macro": sum(1 for e in rows if e["kind"] == "macro")}}
