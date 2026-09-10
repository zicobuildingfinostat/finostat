"""On-demand option chains for any index or F&O stock.

Streaming every F&O chain would need ~17,000 contracts; instead a chain is
subscribed when someone asks for it (ATM ± `half` strikes, near expiry by
default), kept warm while it is being looked at, and dropped after `ttl`
seconds idle. Forty warm chains still fit on one socket.

Implied vol and greeks are derived here from the streamed prices (bs.py), so
the broker's plain LTPC mode is all that is needed.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import bs
from contracts import INDEX_UNDERLYINGS

log = logging.getLogger("finostat.chains")
IST = timezone(timedelta(hours=5, minutes=30))


def merge_rest_oi(rows: list[dict], rest_rows: list[dict]) -> int:
    """Fill open interest, ΔOI (vs previous close), volume, bid/ask — and IV where ours is
    missing — from an Upstox REST chain. The socket's LTPC mode carries none of that on the
    Standard plan. Returns how many option sides received OI."""
    by = {r["strike"]: r for r in rest_rows}
    n = 0
    for row in rows:
        src = by.get(row["strike"])
        if not src:
            continue
        for side in ("ce", "pe"):
            dst, s = row.get(side), src.get(side)
            if not dst or not s:
                continue
            if dst.get("oi") is None and s.get("oi") is not None:
                dst["oi"], dst["oi_chg"], dst["oi_since"] = s["oi"], s.get("oi_chg"), "prev close"
                n += 1
            if dst.get("vol") is None and s.get("vol") is not None:
                dst["vol"] = s["vol"]
            if dst.get("bid") is None and s.get("bid") is not None:
                dst["bid"], dst["ask"] = s["bid"], s.get("ask")
            if dst.get("iv") is None and s.get("iv"):
                dst["iv"] = round(float(s["iv"]), 2)
    return n


def oi_summary(rows: list[dict], spot: float) -> dict | None:
    """PCR, max pain and the OI walls over the loaded strikes. None if the
    feed carries no open interest for this chain."""
    ce = [(r["strike"], r["ce"]["oi"]) for r in rows if r.get("ce") and r["ce"].get("oi") is not None]
    pe = [(r["strike"], r["pe"]["oi"]) for r in rows if r.get("pe") and r["pe"].get("oi") is not None]
    if not ce and not pe:
        return None
    tot_ce, tot_pe = sum(o for _, o in ce), sum(o for _, o in pe)
    strikes = sorted({k for k, _ in ce} | {k for k, _ in pe})
    pain = None
    if strikes and (tot_ce or tot_pe):
        pain = min(strikes, key=lambda s: sum(o * max(s - k, 0) for k, o in ce) + sum(o * max(k - s, 0) for k, o in pe))
    above = [(k, o) for k, o in ce if k >= spot]
    below = [(k, o) for k, o in pe if k <= spot]
    call_wall = max(above, key=lambda x: x[1])[0] if above else None
    put_wall = max(below, key=lambda x: x[1])[0] if below else None
    since = None
    return {"pcr": round(tot_pe / tot_ce, 2) if tot_ce else None, "max_pain": pain,
            "call_wall": call_wall, "put_wall": put_wall, "tot_ce": tot_ce, "tot_pe": tot_pe,
            "max_oi": max([o for _, o in ce + pe] or [0])}


class ChainManager:
    def __init__(self, feed, contracts, half: int = 10, ttl: float = 600.0, max_warm: int = 40):
        self.feed, self.contracts = feed, contracts
        self.half, self.ttl, self.max_warm = half, ttl, max_warm
        self.rest = None                      # upstox_rest.Client, set by the app: OI + Greeks the socket lacks
        self._rest_warned = 0.0
        self._lock = threading.Lock()
        self._warm: dict[str, dict] = {}     # ukey -> {expiry, keys, last, name}
        self._stop = threading.Event()

    # -- what can be built on ----------------------------------------------
    def resolve(self, ukey: str):
        """ukey -> (option name, exchange, spot key, kind) or None."""
        if ukey in INDEX_UNDERLYINGS:
            name, exch, spot_key = INDEX_UNDERLYINGS[ukey]
            return (name, exch, spot_key, "index") if self.contracts.has(name) else None
        if ukey.startswith("NSE:"):
            sym = ukey[4:]
            if self.contracts.has(sym):
                return (sym, "NSE", ukey, "stock")
        return None

    def underlyings(self) -> list[dict]:
        snap = self.feed.snapshot()
        uni = snap.get("universe") or {}
        out = [{"key": k, "label": k, "kind": "index", "name": k} for k in INDEX_UNDERLYINGS if self.contracts.has(INDEX_UNDERLYINGS[k][0])]
        for key, e in uni.items():
            if e.get("exchange") == "NSE" and e.get("fo") and self.contracts.has(e.get("symbol", "")):
                out.append({"key": key, "label": e["symbol"], "kind": "stock", "name": e.get("name", ""),
                            "n50": bool(e.get("n50"))})
        order = {k: i for i, k in enumerate(INDEX_UNDERLYINGS)}      # NIFTY 50 first, not alphabetical
        out.sort(key=lambda u: (u["kind"] != "index", order.get(u["key"], 99), not u.get("n50", False), u["label"]))
        return out

    # -- chain access -------------------------------------------------------
    def chain(self, ukey: str, expiry_ms: int | None = None) -> dict:
        r = self.resolve(ukey)
        if r is None:
            return {"error": "no option chain for that underlying"}
        name, exch, spot_key, kind = r
        spot = self.feed.spot_of(spot_key)
        if not spot:
            return {"error": "no spot price yet", "underlying": ukey}
        expiries = self.contracts.expiries(name)
        if not expiries:
            return {"error": "no live expiry", "underlying": ukey}
        expiry = expiry_ms if expiry_ms in expiries else expiries[0]
        ladder = self.contracts.ladder(name, expiry, spot, self.half)
        if not ladder:
            return {"error": "no strikes near spot", "underlying": ukey}
        self._ensure_warm(ukey, name, expiry, ladder)

        now = time.time()
        t = bs.years_to(expiry, now)
        rows, missing = [], 0
        for row in ladder:
            entry = {"strike": row["strike"], "atm": row["atm"]}
            for right, key in (("CE", row["ce_key"]), ("PE", row["pe_key"])):
                ltp, close = self.feed.price_of(key)
                if ltp is None:
                    missing += 1
                    entry[right.lower()] = None
                    continue
                iv = bs.implied_vol(ltp, spot, row["strike"], t, right) if t > 0 else None
                g = bs.greeks(spot, row["strike"], t, iv, right) if iv else None
                st = self._stats(key)
                entry[right.lower()] = {
                    "oi": st.get("oi"), "oi_chg": st.get("oi_chg"), "vol": st.get("vol"),
                    "bid": st.get("bid"), "ask": st.get("ask"),
                    "ltp": round(ltp, 2),
                    "change": round((ltp - close) / close * 100.0, 2) if close else None,
                    "iv": round(iv * 100.0, 2) if iv else None,
                    "delta": round(g["delta"], 3) if g else None,
                    "theta": round(g["theta"], 2) if g else None,
                    "vega": round(g["vega"], 2) if g else None,
                    "gamma": round(g["gamma"], 5) if g else None,
                }
            rows.append(entry)
        step = self.contracts.step(name, expiry)
        atm = next((r["strike"] for r in ladder if r["atm"]), None)
        oi_source = "socket"
        if self.rest is not None and kind == "index" and any(row.get(sd) and row[sd].get("oi") is None for row in rows for sd in ("ce", "pe")):
            day = datetime.fromtimestamp(expiry / 1000, IST).strftime("%Y-%m-%d")
            try:
                rc = self.rest.option_chain(ukey, day)                    # cached 30 s inside the client
                if merge_rest_oi(rows, rc.get("rows") or []):
                    oi_source = "rest"
            except Exception as exc:                                       # noqa: BLE001 - OI is a bonus, never a blocker
                if now - self._rest_warned > 300:
                    self._rest_warned = now
                    log.info("chain OI via REST unavailable for %s: %s", ukey, exc)
        oi = oi_summary(rows, spot)
        return {
            "oi": oi, "oi_source": oi_source, "oi_basis": "prev close" if oi_source == "rest" else "day open",
            "underlying": ukey, "kind": kind, "name": name, "exchange": exch,
            "spot": round(spot, 2), "expiry": expiry, "expiries": expiries[:6],
            "step": step, "atm": atm, "lot": ladder[0]["lot"], "t_years": round(t, 6),
            "rows": rows, "warming": missing > 0, "missing": missing,
            "live": bool(self.feed.snapshot().get("live")),
        }

    def _stats(self, key: str) -> dict:
        fn = getattr(self.feed, "stats_of", None)          # simulator / older feeds carry no OI
        try:
            return (fn(key) if fn else None) or {}
        except Exception:
            return {}

    def _ensure_warm(self, ukey: str, name: str, expiry: int, ladder: list[dict]) -> None:
        with self._lock:
            w = self._warm.get(ukey)
            if w and w["expiry"] == expiry:
                w["last"] = time.time()
                return
            if len(self._warm) >= self.max_warm:
                oldest = min(self._warm, key=lambda k: self._warm[k]["last"])
                self._drop(oldest)
            metas = {}
            for row in ladder:
                for right, key in (("CE", row["ce_key"]), ("PE", row["pe_key"])):
                    metas[key] = {"kind": "chain", "underlying": ukey, "name": name,
                                  "strike": row["strike"], "right": right, "expiry": expiry}
            if w:                         # expiry changed: swap the subscription
                self._drop(ukey)
            self._warm[ukey] = {"expiry": expiry, "keys": set(metas), "last": time.time(), "name": name}
        self.feed.subscribe_dynamic(metas)
        log.info("chain warm: %s %s (%d contracts)", ukey, time.strftime("%Y-%m-%d", time.localtime(expiry / 1000)), len(metas))

    def _drop(self, ukey: str) -> None:
        w = self._warm.pop(ukey, None)
        if w:
            self.feed.unsubscribe_dynamic(w["keys"])
            log.info("chain dropped: %s (idle)", ukey)

    # -- housekeeping -------------------------------------------------------
    def sweep(self) -> int:
        now = time.time()
        with self._lock:
            idle = [k for k, w in self._warm.items() if now - w["last"] > self.ttl]
            for k in idle:
                self._drop(k)
        return len(idle)

    def start(self) -> None:
        def run():
            while not self._stop.wait(30.0):
                try:
                    self.sweep()
                except Exception:
                    log.exception("chain sweep failed")
        threading.Thread(target=run, name="chains", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def stats(self) -> dict:
        with self._lock:
            return {"warm": len(self._warm), "contracts": sum(len(w["keys"]) for w in self._warm.values()),
                    "underlyings": sorted(self._warm)}
