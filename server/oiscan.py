"""OISCAN: open-interest build-up screener.

Indices (NIFTY 50, BANKNIFTY, FINNIFTY, SENSEX): the nearest-expiry chain is sampled every 3 minutes
during the session from Upstox REST (OI, LTP per strike and side) and kept for the day (memory +
sqlite, so a restart does not lose the morning). Every strike/side is tagged over a 5, 15 or 60 minute
window or since the open:

    price up,   OI up   -> long build-up      (fresh buying)
    price down, OI up   -> short build-up     (fresh writing)
    price up,   OI down -> short covering     (writers squeezed)
    price down, OI down -> long unwinding     (buyers giving up)

For options the read is by side: call writing above spot is supply, put writing below spot is support,
call covering is bullish, put covering is bearish. F&O stocks are screened on a day basis every 15 min
from their nearest-expiry chain: total option OI change vs the spot move.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

log = logging.getLogger("finostat.oiscan")
IST = timezone(timedelta(hours=5, minutes=30))
INDICES = ("NIFTY 50", "BANKNIFTY", "FINNIFTY", "SENSEX")
WINDOWS = {"5": 5, "15": 15, "60": 60, "day": None}
TAGS = {(1, 1): "long build-up", (-1, 1): "short build-up", (1, -1): "short covering", (-1, -1): "long unwinding"}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS oi_samples(id INTEGER PRIMARY KEY, day TEXT NOT NULL, u TEXT NOT NULL, ts REAL NOT NULL, expiry TEXT, spot REAL, blob TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS oi_samples_day ON oi_samples(day, u, ts);
"""


def classify(d_px: float, d_oi: float, oi_now: float, min_oi_pct: float = 0.5) -> str | None:
    """Tag from price and OI change; tiny OI changes (< 0.5% of current OI, or < 1 lot) are 'flat'."""
    if oi_now <= 0 or abs(d_oi) < max(1.0, oi_now * min_oi_pct / 100.0):
        return "flat" if abs(d_oi) < 1 else None
    if abs(d_px) < 1e-9:
        return None
    return TAGS[(1 if d_px > 0 else -1, 1 if d_oi > 0 else -1)]


def sample_from_chain(chain: dict) -> dict:
    """Upstox REST chain -> {strike: [ce_oi, ce_ltp, pe_oi, pe_ltp, ce_prev, pe_prev]}."""
    out = {}
    for r in chain.get("rows") or []:
        ce, pe = r.get("ce") or {}, r.get("pe") or {}
        out[int(r["strike"])] = [ce.get("oi") or 0, ce.get("ltp"), pe.get("oi") or 0, pe.get("ltp"), ce.get("prev_oi") or 0, pe.get("prev_oi") or 0]
    return out


def diff(latest: dict, then: dict, window: str, step: int, span: int = 12) -> dict:
    """Per-strike/side tags between two samples (or vs previous close for 'day'), near the money."""
    spot = latest["spot"]
    atm = round(spot / step) * step if step else spot
    rows = []
    ce_d = pe_d = ce_tot = pe_tot = ce_then = pe_then = 0.0
    for k, v in sorted(latest["data"].items()):
        if step and abs(k - atm) > span * step:
            continue
        t = then["data"].get(k) if then else None
        for side, oi_i, px_i, prev_i in (("CE", 0, 1, 4), ("PE", 2, 3, 5)):
            oi_now, px_now = v[oi_i], v[px_i]
            if window == "day":
                oi_then = v[prev_i]
                px_then = t[px_i] if t else None
            else:
                oi_then = t[oi_i] if t else None
                px_then = t[px_i] if t else None
            if oi_then is None:
                continue
            d_oi = oi_now - oi_then
            d_px = (px_now - px_then) if (px_now is not None and px_then is not None) else 0.0
            d_px_pct = (d_px / px_then * 100) if px_then else None
            tag = classify(d_px, d_oi, oi_now)
            rows.append({"strike": k, "side": side, "oi": oi_now, "d_oi": d_oi, "ltp": px_now, "d_px_pct": round(d_px_pct, 1) if d_px_pct is not None else None,
                         "tag": tag, "itm": (side == "CE" and k < spot) or (side == "PE" and k > spot)})
            if side == "CE":
                ce_d += d_oi; ce_tot += oi_now; ce_then += oi_then
            else:
                pe_d += d_oi; pe_tot += oi_now; pe_then += oi_then
    top = sorted((r for r in rows if r["tag"] and r["tag"] != "flat"), key=lambda r: -abs(r["d_oi"]))[:14]
    read = _read(rows, spot, step)
    walls = {"call": max((r for r in rows if r["side"] == "CE" and r["strike"] >= spot), key=lambda r: r["oi"], default=None),
             "put": max((r for r in rows if r["side"] == "PE" and r["strike"] <= spot), key=lambda r: r["oi"], default=None)}
    return {"spot": spot, "spot_then": then["spot"] if then else None, "atm": atm, "step": step, "window": window,
            "ts": latest["ts"], "ts_then": then["ts"] if then else None,
            "ce_oi": ce_tot, "pe_oi": pe_tot, "ce_d": ce_d, "pe_d": pe_d,
            "pcr": round(pe_tot / ce_tot, 2) if ce_tot else None, "pcr_then": round(pe_then / ce_then, 2) if ce_then else None,
            "rows": rows, "top": top, "read": read,
            "walls": {k: ({"strike": w["strike"], "oi": w["oi"]} if w else None) for k, w in walls.items()}}


def _read(rows: list[dict], spot: float, step: int) -> dict:
    """One-line desk read from the tagged strikes near the money."""
    near = [r for r in rows if r["tag"] and r["tag"] != "flat" and step and abs(r["strike"] - spot) <= 6 * step]
    bull = bear = 0.0
    notes = []
    def top_of(side, tag, above=None):
        c = [r for r in near if r["side"] == side and r["tag"] == tag and (above is None or (r["strike"] >= spot) == above)]
        return sorted(c, key=lambda r: -abs(r["d_oi"]))[:2]
    for r in near:
        w = abs(r["d_oi"])
        if r["side"] == "CE":
            if r["tag"] == "short build-up":
                bear += w
            elif r["tag"] == "short covering":
                bull += w
            elif r["tag"] == "long build-up":
                bull += w * 0.5
            elif r["tag"] == "long unwinding":
                bear += w * 0.5
        else:
            if r["tag"] == "short build-up":
                bull += w
            elif r["tag"] == "short covering":
                bear += w
            elif r["tag"] == "long build-up":
                bear += w * 0.5
            elif r["tag"] == "long unwinding":
                bull += w * 0.5
    cw = top_of("CE", "short build-up", True)
    pw = top_of("PE", "short build-up", False)
    cc = top_of("CE", "short covering")
    pc = top_of("PE", "short covering")
    if cw:
        notes.append("call writing at " + " / ".join(f"{r['strike']:,}" for r in cw) + " (supply)")
    if pw:
        notes.append("put writing at " + " / ".join(f"{r['strike']:,}" for r in pw) + " (support)")
    if cc:
        notes.append("call writers covering at " + " / ".join(f"{r['strike']:,}" for r in cc))
    if pc:
        notes.append("put writers covering at " + " / ".join(f"{r['strike']:,}" for r in pc))
    total = bull + bear
    lean = "bullish" if total and bull / total > 0.62 else "bearish" if total and bear / total > 0.62 else "balanced"
    if not near:
        return {"lean": "quiet", "score": 0, "text": "no meaningful OI change near the money in this window"}
    text = f"{lean} lean" + (" — " + "; ".join(notes) if notes else "")
    if cw and pw:
        text += f"; OI range {pw[0]['strike']:,}–{cw[0]['strike']:,}"
    return {"lean": lean, "score": round((bull - bear) / total, 2) if total else 0, "text": text}


class Sampler:
    def __init__(self, rest, db_path, in_session_fn, stock_keys_fn=None, every: float = 180.0, stock_every: float = 900.0, step_fn=None):
        self.rest, self.path = rest, db_path
        self.in_session, self.stock_keys_fn, self.step_fn = in_session_fn, stock_keys_fn, step_fn
        self.every, self.stock_every = every, stock_every
        self.samples: dict[str, deque] = {u: deque(maxlen=160) for u in INDICES}
        self.stocks: dict[str, dict] = {}
        self.stocks_ts = 0.0
        self.last_error: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        with self._conn() as c:
            c.executescript(_SCHEMA)
        self._load_today()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10, check_same_thread=False)

    @staticmethod
    def _day(ts: float | None = None) -> str:
        return datetime.fromtimestamp(ts or time.time(), IST).strftime("%Y-%m-%d")

    def _load_today(self) -> None:
        day = self._day()
        try:
            with self._conn() as c:
                for u, ts, exp, spot, blob in c.execute("SELECT u, ts, expiry, spot, blob FROM oi_samples WHERE day=? ORDER BY ts", (day,)):
                    if u in self.samples:
                        self.samples[u].append({"ts": ts, "expiry": exp, "spot": spot, "data": {int(k): v for k, v in json.loads(blob).items()}})
                c.execute("DELETE FROM oi_samples WHERE day<?", ((datetime.now(IST) - timedelta(days=3)).strftime("%Y-%m-%d"),))
        except sqlite3.Error as exc:
            log.info("oiscan: load failed: %s", exc)

    # -- sampling -------------------------------------------------------------
    def _nearest_expiry(self, u: str) -> str | None:
        today = self._day()
        exps = [e for e in self.rest.expiries(u) if e >= today]
        return exps[0] if exps else None

    def sample_index(self, u: str, now: float | None = None) -> dict | None:
        now = now or time.time()
        exp = self._nearest_expiry(u)
        if not exp:
            return None
        ch = self.rest.option_chain(u, exp)
        if not ch.get("rows") or not ch.get("spot"):
            return None
        s = {"ts": now, "expiry": exp, "spot": float(ch["spot"]), "data": sample_from_chain(ch)}
        with self._lock:
            self.samples[u].append(s)
        try:
            with self._conn() as c:
                c.execute("INSERT INTO oi_samples(day,u,ts,expiry,spot,blob) VALUES(?,?,?,?,?,?)",
                          (self._day(now), u, now, exp, s["spot"], json.dumps(s["data"], separators=(",", ":"))))
        except sqlite3.Error as exc:
            log.info("oiscan: persist failed: %s", exc)
        return s

    def sample_stocks(self, now: float | None = None) -> int:
        if not self.stock_keys_fn:
            return 0
        now = now or time.time()
        n = 0
        for sym, key in self.stock_keys_fn():
            try:
                exps = [e for e in self.rest.expiries(key) if e >= self._day(now)]
                if not exps:
                    continue
                ch = self.rest.option_chain(key, exps[0])
                if not ch.get("rows") or not ch.get("spot"):
                    continue
                ce = pe = ce_prev = pe_prev = 0
                for r in ch["rows"]:
                    for side, acc in (("ce", 0), ("pe", 1)):
                        o = r.get(side) or {}
                        if acc == 0:
                            ce += o.get("oi") or 0; ce_prev += o.get("prev_oi") or 0
                        else:
                            pe += o.get("oi") or 0; pe_prev += o.get("prev_oi") or 0
                spot = float(ch["spot"])
                prev = self.stocks.get(sym, {}).get("open_spot") or spot
                d_oi = (ce + pe) - (ce_prev + pe_prev)
                d_px = spot - prev
                tag = classify(d_px, d_oi, ce + pe) if prev != spot else None
                self.stocks[sym] = {"sym": sym, "expiry": exps[0], "spot": spot, "open_spot": prev, "spot_chg_pct": round((spot / prev - 1) * 100, 2) if prev else None,
                                    "ce_oi": ce, "pe_oi": pe, "ce_d": ce - ce_prev, "pe_d": pe - pe_prev, "d_oi_pct": round(100 * d_oi / (ce_prev + pe_prev), 1) if (ce_prev + pe_prev) else None,
                                    "pcr": round(pe / ce, 2) if ce else None, "tag": tag, "ts": now}
                n += 1
            except Exception as exc:                                # noqa: BLE001
                log.debug("oiscan: stock %s skipped: %s", sym, exc)
        self.stocks_ts = now
        return n

    def _loop(self) -> None:
        last_stocks = 0.0
        while not self._stop.is_set():
            try:
                if self.in_session():
                    for u in INDICES:
                        try:
                            self.sample_index(u)
                        except Exception as exc:                    # noqa: BLE001
                            self.last_error = f"{u}: {str(exc)[:80]}"
                            log.info("oiscan: %s sample failed: %s", u, exc)
                    if time.time() - last_stocks > self.stock_every:
                        last_stocks = time.time()
                        try:
                            self.sample_stocks()
                        except Exception as exc:                    # noqa: BLE001
                            log.info("oiscan: stocks failed: %s", exc)
            except Exception as exc:                                # noqa: BLE001
                log.warning("oiscan loop: %s", exc)
            self._stop.wait(self.every)

    def start(self) -> None:
        threading.Thread(target=self._loop, name="oiscan", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    # -- views ---------------------------------------------------------------------
    def view(self, u: str, window: str = "15") -> dict:
        if u not in self.samples:
            return {"error": "OISCAN covers NIFTY 50, BANKNIFTY, FINNIFTY and SENSEX"}
        window = window if window in WINDOWS else "15"
        with self._lock:
            hist = list(self.samples[u])
        if not hist:
            return {"error": "no samples yet — the screener fills in during the session (first sample ~09:18 IST)", "u": u, "samples": 0}
        latest = hist[-1]
        mins = WINDOWS[window]
        if mins is None:
            then = hist[0]
        else:
            target = latest["ts"] - mins * 60
            then = min(hist, key=lambda s: abs(s["ts"] - target))
            if then is latest and len(hist) > 1:
                then = hist[-2]
        step = (self.step_fn(u) if self.step_fn else None) or _guess_step(latest["data"])
        out = diff(latest, then if then is not latest else None, window, step)
        out.update({"u": u, "expiry": latest["expiry"], "samples": len(hist), "first_ts": hist[0]["ts"],
                    "window_actual_min": round((latest["ts"] - (then["ts"] if then is not latest else latest["ts"])) / 60, 1),
                    "series": [{"ts": s["ts"], "spot": s["spot"], "ce": sum(v[0] for v in s["data"].values()), "pe": sum(v[2] for v in s["data"].values())} for s in hist]})
        return out

    def stocks_view(self) -> dict:
        rows = sorted(self.stocks.values(), key=lambda r: -abs((r["ce_d"] or 0) + (r["pe_d"] or 0)))
        return {"rows": rows, "ts": self.stocks_ts, "count": len(rows)}


def _guess_step(data: dict) -> int:
    ks = sorted(data)
    gaps = [b - a for a, b in zip(ks, ks[1:]) if b > a]
    return min(gaps) if gaps else 50
