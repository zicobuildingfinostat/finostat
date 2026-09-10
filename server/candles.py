"""Candles for the terminal's own chart, from Upstox's historical + intraday endpoints.

TradingView's embed refuses NSE symbols ("only available on TradingView"), so the terminal
draws its own chart. Timeframes: 1m (last ~5 sessions), 5m (last month), 15m and 1h
(aggregated from the 5-minute series), D (one year). Today's session comes from the
intraday endpoint and is stitched onto the history. Results are cached briefly so a
crowd of terminals costs one request per symbol and timeframe.
"""
from __future__ import annotations

import logging
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import upstox_rest as ur

log = logging.getLogger("finostat.candles")
IST = timezone(timedelta(hours=5, minutes=30))

INDEX_KEYS = {"NIFTY 50": "NSE_INDEX|Nifty 50", "NIFTY": "NSE_INDEX|Nifty 50", "BANKNIFTY": "NSE_INDEX|Nifty Bank", "NIFTY BANK": "NSE_INDEX|Nifty Bank",
              "FINNIFTY": "NSE_INDEX|Nifty Fin Service", "SENSEX": "BSE_INDEX|SENSEX", "INDIA VIX": "NSE_INDEX|India VIX",
              "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT", "BANKEX": "BSE_INDEX|BANKEX", "NIFTY NEXT 50": "NSE_INDEX|Nifty Next 50"}
TIMEFRAMES = {"1m": ("minutes", 1, 8, 1), "5m": ("minutes", 5, 32, 5), "15m": ("minutes", 5, 32, 15), "1h": ("minutes", 5, 32, 60), "D": ("days", 1, 370, 0)}
# tf -> (unit, api interval, calendar days of history, aggregate-to minutes; 0 = as is)


def resolve_key(label: str, meta: dict | None) -> str | None:
    """Tape label / 'NSE:SYM' / raw instrument key -> Upstox instrument key."""
    s = (label or "").strip()
    if not s:
        return None
    if "|" in s and s.split("|", 1)[0] in ("NSE_INDEX", "BSE_INDEX", "NSE_EQ", "BSE_EQ", "NSE_FO", "BSE_FO", "MCX_FO"):
        return s                                                     # already a key (options can be charted too)
    up = s.upper()
    if up in INDEX_KEYS:
        return INDEX_KEYS[up]
    if meta:
        want = up if ":" in up else "NSE:" + up
        for key, m in meta.items():
            if m.get("kind") == "stock" and m.get("label") == want:
                return key
    return None


def aggregate(candles: list[list], minutes: int) -> list[list]:
    """Bucket ascending 1/5-minute candles into `minutes` bars aligned to the 09:15 session open."""
    if minutes <= 0 or not candles:
        return candles
    out: list[list] = []
    cur_key = None
    for c in candles:
        ts = datetime.fromisoformat(c[0])
        mins = (ts.hour * 60 + ts.minute) - (9 * 60 + 15)
        bucket = mins // minutes
        key = (ts.date(), bucket)
        if key != cur_key:
            start = ts.replace(hour=9, minute=15, second=0, microsecond=0) + timedelta(minutes=bucket * minutes)
            out.append([start.isoformat(), c[1], c[2], c[3], c[4], c[5] or 0, c[6] or 0])
            cur_key = key
        else:
            o = out[-1]
            o[2] = max(o[2], c[2])
            o[3] = min(o[3], c[3])
            o[4] = c[4]
            o[5] += c[5] or 0
            o[6] = c[6] or o[6]
    return out


class Candles:
    def __init__(self, client: ur.Client, ttl: float = 25.0):
        self.client, self.ttl = client, ttl
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def _hist(self, key: str, unit: str, interval: int, to: str, frm: str) -> list[list]:
        path = f"/historical-candle/{urllib.parse.quote(key, safe='')}/{unit}/{interval}/{to}/{frm}"
        data = self.client.get_v3(path)
        return sorted(data.get("candles") or [], key=lambda c: c[0])

    def _intraday(self, key: str, unit: str, interval: int) -> list[list]:
        path = f"/historical-candle/intraday/{urllib.parse.quote(key, safe='')}/{unit}/{interval}"
        data = self.client.get_v3(path)
        return sorted(data.get("candles") or [], key=lambda c: c[0])

    def series(self, key: str, tf: str) -> dict:
        tf = tf if tf in TIMEFRAMES else "5m"
        ck = (key, tf)
        now = time.time()
        with self._lock:
            hit = self._cache.get(ck)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        unit, interval, days, agg = TIMEFRAMES[tf]
        today = datetime.now(IST).date()
        to = (today - timedelta(days=1)).isoformat()
        frm = (today - timedelta(days=days)).isoformat()
        hist = self._hist(key, unit, interval, to, frm)
        live: list[list] = []
        try:
            live = self._intraday(key, "minutes", 5 if unit == "days" else interval)
        except ur.RestError as exc:
            log.info("intraday candles unavailable for %s: %s", key, exc)
        if unit == "days" and live:
            # today's bar from the intraday 5-minute candles
            o, h, l, c = live[0][1], max(x[2] for x in live), min(x[3] for x in live), live[-1][4]
            live = [[datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), o, h, l, c, sum(x[5] or 0 for x in live), live[-1][6] or 0]]
        rows = hist + [x for x in live if not hist or x[0] > hist[-1][0]]
        if agg:
            rows = aggregate(rows, agg)
        out = {"key": key, "tf": tf, "candles": [[r[0], r[1], r[2], r[3], r[4], r[5] or 0] for r in rows], "count": len(rows), "at": now}
        with self._lock:
            self._cache[ck] = (now, out)
        return out
