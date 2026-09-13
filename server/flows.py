"""FLOWS: FII/DII cash flows and participant-wise F&O positioning from NSE.

Two NSE sources, both public, both unofficial:
- /api/fiidiiTradeReact — the day's FII/FPI and DII buy/sell/net in the cash market (₹ crore). NSE
  only serves the latest session, so every fetch is banked and the history grows day by day.
- nsearchives .../fao_participant_oi_DDMMYYYY.csv — open interest by participant (Client, DII,
  FII, Pro) in index/stock futures and options, published every evening. Fetchable for past
  dates, so the store is backfilled on first run.
The scheduler polls in the evening until the day's files appear, and once in the morning to pick
up late postings. Weekends and NSE holidays are skipped.
"""
from __future__ import annotations

import csv
import http.cookiejar
import io
import json
import logging
import sqlite3
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger("finostat.flows")
IST = timezone(timedelta(hours=5, minutes=30))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
FIIDII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
FIIDII_HOME = "https://www.nseindia.com/reports/fii-dii"
PART_URL = "https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{ddmmyyyy}.csv"
CLIENTS = ("Client", "DII", "FII", "Pro")
COLS = ("fut_idx_long", "fut_idx_short", "fut_stk_long", "fut_stk_short", "opt_idx_call_long", "opt_idx_put_long", "opt_idx_call_short",
        "opt_idx_put_short", "opt_stk_call_long", "opt_stk_put_long", "opt_stk_call_short", "opt_stk_put_short", "total_long", "total_short")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fii_dii(
  date TEXT NOT NULL, category TEXT NOT NULL, buy REAL, sell REAL, net REAL, fetched REAL NOT NULL,
  PRIMARY KEY(date, category));
CREATE TABLE IF NOT EXISTS participant_oi(
  date TEXT NOT NULL, client TEXT NOT NULL,
  fut_idx_long INTEGER, fut_idx_short INTEGER, fut_stk_long INTEGER, fut_stk_short INTEGER,
  opt_idx_call_long INTEGER, opt_idx_put_long INTEGER, opt_idx_call_short INTEGER, opt_idx_put_short INTEGER,
  opt_stk_call_long INTEGER, opt_stk_put_long INTEGER, opt_stk_call_short INTEGER, opt_stk_put_short INTEGER,
  total_long INTEGER, total_short INTEGER, fetched REAL NOT NULL,
  PRIMARY KEY(date, client));
"""


def parse_fiidii(payload) -> list[dict]:
    """NSE's list of {category, date 'DD-Mon-YYYY', buyValue, sellValue, netValue} -> rows."""
    out = []
    for r in payload or []:
        try:
            d = datetime.strptime(str(r.get("date", "")).strip(), "%d-%b-%Y").date().isoformat()
            cat = "FII" if "FII" in str(r.get("category", "")).upper() else "DII"
            out.append({"date": d, "category": cat, "buy": float(str(r.get("buyValue", "0")).replace(",", "")),
                        "sell": float(str(r.get("sellValue", "0")).replace(",", "")), "net": float(str(r.get("netValue", "0")).replace(",", ""))})
        except (TypeError, ValueError):
            continue
    return out


def parse_participant(text: str) -> tuple[str | None, list[dict]]:
    """The participant-wise OI CSV -> (date ISO, rows per client)."""
    lines = [l for l in text.splitlines() if l.strip()]
    day = None
    for l in lines[:2]:
        if "as on" in l:
            try:
                day = datetime.strptime(l.split("as on", 1)[1].strip().strip('",').strip(), "%b %d, %Y").date().isoformat()
            except ValueError:
                day = None
    rows = []
    reader = csv.reader(io.StringIO("\n".join(l for l in lines if not l.startswith('"') and "as on" not in l)))
    for rec in reader:
        rec = [c.strip() for c in rec]
        if not rec or rec[0] not in CLIENTS or len(rec) < 15:
            continue
        try:
            vals = [int(float(x.replace(",", "") or 0)) for x in rec[1:15]]
        except ValueError:
            continue
        rows.append(dict({"client": rec[0]}, **dict(zip(COLS, vals))))
    return day, rows


class Store:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def put_fiidii(self, rows: list[dict]) -> int:
        with self._lock, self._conn() as c:
            for r in rows:
                c.execute("INSERT OR REPLACE INTO fii_dii(date,category,buy,sell,net,fetched) VALUES(?,?,?,?,?,?)",
                          (r["date"], r["category"], r["buy"], r["sell"], r["net"], time.time()))
        return len(rows)

    def put_participants(self, day: str, rows: list[dict]) -> int:
        with self._lock, self._conn() as c:
            for r in rows:
                c.execute(f"INSERT OR REPLACE INTO participant_oi(date,client,{','.join(COLS)},fetched) VALUES(?,?,{','.join('?' * len(COLS))},?)",
                          (day, r["client"], *[r.get(k) for k in COLS], time.time()))
        return len(rows)

    def has_participants(self, day: str) -> bool:
        with self._conn() as c:
            return c.execute("SELECT 1 FROM participant_oi WHERE date=? LIMIT 1", (day,)).fetchone() is not None

    def fiidii(self, days: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT date,category,buy,sell,net FROM fii_dii ORDER BY date DESC LIMIT ?", (days * 2,)).fetchall()
        by: dict[str, dict] = {}
        for r in rows:
            d = by.setdefault(r["date"], {"date": r["date"]})
            k = r["category"].lower()
            d[k + "_buy"], d[k + "_sell"], d[k + "_net"] = r["buy"], r["sell"], r["net"]
        return sorted(by.values(), key=lambda x: x["date"])

    def participants(self, days: int) -> list[dict]:
        with self._conn() as c:
            dates = [r[0] for r in c.execute("SELECT DISTINCT date FROM participant_oi ORDER BY date DESC LIMIT ?", (days,)).fetchall()]
            if not dates:
                return []
            rows = c.execute(f"SELECT * FROM participant_oi WHERE date IN ({','.join('?' * len(dates))}) ORDER BY date", dates).fetchall()
        return [dict(r) for r in rows]

    def counts(self) -> dict:
        with self._conn() as c:
            a = c.execute("SELECT COUNT(DISTINCT date), MAX(date) FROM fii_dii").fetchone()
            b = c.execute("SELECT COUNT(DISTINCT date), MAX(date) FROM participant_oi").fetchone()
        return {"fiidii_days": a[0], "fiidii_last": a[1], "participant_days": b[0], "participant_last": b[1]}


def derive(participants: list[dict], fiidii: list[dict]) -> dict:
    """What the panel shows: per date, each participant's net index futures, net index calls/puts
    (long − short), day-on-day change; plus the FII/DII cash series with cumulative sums."""
    by_date: dict[str, dict] = {}
    for r in participants:
        d = by_date.setdefault(r["date"], {"date": r["date"]})
        cl = r["client"].lower()
        d[cl] = {"fut_idx_net": (r["fut_idx_long"] or 0) - (r["fut_idx_short"] or 0), "fut_idx_long": r["fut_idx_long"], "fut_idx_short": r["fut_idx_short"],
                 "call_net": (r["opt_idx_call_long"] or 0) - (r["opt_idx_call_short"] or 0), "put_net": (r["opt_idx_put_long"] or 0) - (r["opt_idx_put_short"] or 0),
                 "fut_stk_net": (r["fut_stk_long"] or 0) - (r["fut_stk_short"] or 0)}
    series = sorted(by_date.values(), key=lambda x: x["date"])
    prev = None
    for d in series:
        for cl in ("client", "dii", "fii", "pro"):
            if cl in d and prev and cl in prev:
                d[cl]["fut_idx_net_chg"] = d[cl]["fut_idx_net"] - prev[cl]["fut_idx_net"]
                d[cl]["call_net_chg"] = d[cl]["call_net"] - prev[cl]["call_net"]
                d[cl]["put_net_chg"] = d[cl]["put_net"] - prev[cl]["put_net"]
        prev = d
    cum_f = cum_d = 0.0
    cash = []
    for r in fiidii:
        cum_f += r.get("fii_net") or 0.0
        cum_d += r.get("dii_net") or 0.0
        cash.append(dict(r, fii_cum=round(cum_f, 2), dii_cum=round(cum_d, 2)))
    latest = series[-1] if series else None
    return {"positions": series, "cash": cash, "latest": latest, "latest_cash": cash[-1] if cash else None}


class Flows:
    def __init__(self, store: Store, holidays=None, clock=None, backfill_days: int = 60):
        self.store, self.holidays, self.clock, self.backfill_days = store, holidays, clock or (lambda: datetime.now(IST)), backfill_days
        self._stop = threading.Event()
        self.fetched: float | None = None
        self.error: str | None = None

    # -- network -------------------------------------------------------------
    def _opener(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
        return op, h

    def fetch_fiidii(self) -> int:
        op, h = self._opener()
        op.open(urllib.request.Request(FIIDII_HOME, headers=h), timeout=20).read(2000)
        r = op.open(urllib.request.Request(FIIDII_URL, headers=dict(h, Accept="application/json", Referer=FIIDII_HOME)), timeout=20)
        rows = parse_fiidii(json.loads(r.read().decode("utf-8")))
        return self.store.put_fiidii(rows)

    def fetch_participants(self, day: date) -> int:
        op, h = self._opener()
        url = PART_URL.format(ddmmyyyy=day.strftime("%d%m%Y"))
        try:
            r = op.open(urllib.request.Request(url, headers=h), timeout=20)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return 0                                       # not a trading day, or not published yet
            raise
        d, rows = parse_participant(r.read().decode("utf-8", "replace"))
        return self.store.put_participants(d or day.isoformat(), rows) if rows else 0

    def _trading_day(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        try:
            return not (self.holidays and d.isoformat() in self.holidays.dates())
        except Exception:                                   # noqa: BLE001
            return True

    def refresh(self, backfill: bool = False) -> bool:
        ok = True
        try:
            self.fetch_fiidii()
        except Exception as exc:                            # noqa: BLE001
            ok = False
            self.error = f"fii/dii: {str(exc)[:120]}"
            log.info("flows: FII/DII fetch failed: %s", exc)
        today = self.clock().date()
        span = self.backfill_days if backfill else 3
        for i in range(0, span + 1):
            d = today - timedelta(days=i)
            if not self._trading_day(d) or self.store.has_participants(d.isoformat()):
                continue
            try:
                self.fetch_participants(d)
                time.sleep(0.3)
            except Exception as exc:                        # noqa: BLE001
                ok = False
                self.error = f"participant {d}: {str(exc)[:100]}"
                log.info("flows: participant OI %s failed: %s", d, exc)
        if ok:
            self.fetched, self.error = time.time(), None
        return ok

    # -- schedule ----------------------------------------------------------------
    def start(self) -> None:
        threading.Thread(target=self._run, name="flows", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        self.refresh(backfill=True)
        while not self._stop.is_set():
            now = self.clock()
            hhmm = now.hour * 60 + now.minute
            evening = self._trading_day(now.date()) and 15 * 60 + 45 <= hhmm <= 21 * 60
            wait = 20 * 60 if evening else 60 * 60
            if self._stop.wait(wait):
                return
            if evening or hhmm // 60 in (8, 9):
                self.refresh()

    def api(self, days: int = 30) -> dict:
        out = derive(self.store.participants(days), self.store.fiidii(days))
        out.update({"fetched": self.fetched, "error": self.error, "counts": self.store.counts()})
        return out
