"""Upstox REST v2, the read-only parts the analytics panels need.

The websocket carries prices; this carries what the socket does not: the full option
chain with open interest and exchange Greeks, and the expired-contract archive (about
two years of 1-minute candles for every past expiry) that drives replay and backtests.

Cloudflare in front of api.upstox.com rejects Python's default User-Agent (error 1010),
so every call goes out with a browser UA. Calls are throttled to stay far below the
published rate limit and cached: live chains for 30 s, contract lists for hours,
expired candles forever (they never change).
"""
from __future__ import annotations

import json
import logging
import pathlib
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import config

log = logging.getLogger("finostat.upstox_rest")

BASE = "https://api.upstox.com/v2"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
INSTRUMENT = {"NIFTY 50": "NSE_INDEX|Nifty 50", "BANKNIFTY": "NSE_INDEX|Nifty Bank", "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
              "SENSEX": "BSE_INDEX|SENSEX", "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT"}
STEP = {"NIFTY 50": 50, "BANKNIFTY": 100, "FINNIFTY": 50, "SENSEX": 100, "MIDCPNIFTY": 25}


class RestError(RuntimeError):
    pass


class Client:
    def __init__(self, token: str | None = None, min_gap: float = 0.08):
        self._token = token
        self._gap = min_gap
        self._last = 0.0
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, object]] = {}

    @property
    def token(self) -> str:
        return (self._token if self._token is not None else getattr(config, "UPSTOX_ACCESS_TOKEN", "")) or ""

    def get(self, path: str, params: dict | None = None, ttl: float = 0.0, timeout: float = 25.0, base: str = BASE):
        url = base + path + (("?" + urllib.parse.urlencode(params)) if params else "")
        if ttl:
            hit = self._cache.get(url)
            if hit and time.time() - hit[0] < ttl:
                return hit[1]
        if not self.token:
            raise RestError("no Upstox access token")
        with self._lock:                                   # one request at a time, gently spaced
            wait = self._gap - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json", "User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raise RestError(f"HTTP {exc.code} for {path}") from exc
            except Exception as exc:
                raise RestError(f"{type(exc).__name__}: {exc}") from exc
            finally:
                self._last = time.time()
        if body.get("status") != "success":
            raise RestError(f"upstox: {str(body)[:120]}")
        data = body.get("data")
        if ttl:
            self._cache[url] = (time.time(), data)
        return data

    def get_v3(self, path: str, ttl: float = 0.0):
        """Same call against the v3 API (candles with arbitrary minute intervals)."""
        return self.get(path, ttl=ttl, base=BASE.replace("/v2", "/v3"))

    # -- live chain --------------------------------------------------------
    def option_chain(self, u: str, expiry: str) -> dict:
        """Full chain for one expiry (YYYY-MM-DD), normalised to Finostat's row shape."""
        ik = INSTRUMENT.get(u, u)
        data = self.get("/option/chain", {"instrument_key": ik, "expiry_date": expiry}, ttl=30.0) or []
        return normalize_chain(u, expiry, data)

    def expiries(self, u: str) -> list[str]:
        """Live expiries (YYYY-MM-DD, ascending) from the contract master."""
        ik = INSTRUMENT.get(u, u)
        data = self.get("/option/contract", {"instrument_key": ik}, ttl=6 * 3600) or []
        return sorted({c.get("expiry") for c in data if c.get("expiry")})

    # -- expired archive ---------------------------------------------------
    def expired_expiries(self, u: str) -> list[str]:
        ik = INSTRUMENT.get(u, u)
        return sorted(self.get("/expired-instruments/expiries", {"instrument_key": ik}, ttl=12 * 3600) or [])

    def expired_contracts(self, u: str, expiry: str) -> list[dict]:
        ik = INSTRUMENT.get(u, u)
        return self.get("/expired-instruments/option/contract", {"instrument_key": ik, "expiry_date": expiry}, ttl=24 * 3600) or []

    def expired_candles(self, expired_key: str, day: str, interval: str = "1minute") -> list[list]:
        """[[ts_iso, o, h, l, c, vol, oi], ...] oldest first for one expired contract on one day."""
        data = self.get(f"/expired-instruments/historical-candle/{urllib.parse.quote(expired_key, safe='')}/{interval}/{day}/{day}") or {}
        return sorted(data.get("candles") or [], key=lambda c: c[0])

    def index_candles(self, u: str, day: str, interval: str = "1minute") -> list[list]:
        ik = INSTRUMENT.get(u, u)
        data = self.get(f"/historical-candle/{urllib.parse.quote(ik, safe='')}/{interval}/{day}/{day}", ttl=24 * 3600) or {}
        return sorted(data.get("candles") or [], key=lambda c: c[0])


def normalize_chain(u: str, expiry: str, data: list) -> dict:
        """Upstox /option/chain rows -> {spot, rows:[{strike, ce:{...}, pe:{...}}], pcr}."""
        rows, spot = [], None
        for r in data:
            spot = spot or r.get("underlying_spot_price")
            row = {"strike": int(round(float(r.get("strike_price", 0))))}
            for side, key in (("ce", "call_options"), ("pe", "put_options")):
                o = r.get(key) or {}
                md, gk = o.get("market_data") or {}, o.get("option_greeks") or {}
                ltp = md.get("ltp")
                if ltp is None:
                    row[side] = None
                    continue
                iv = gk.get("iv")
                row[side] = {"ltp": float(ltp), "iv": float(iv) if iv not in (None, 0) else None, "oi": int(md.get("oi") or 0),
                             "prev_oi": int(md.get("prev_oi") or 0), "oi_chg": int((md.get("oi") or 0) - (md.get("prev_oi") or 0)),
                             "vol": int(md.get("volume") or 0), "bid": md.get("bid_price"), "ask": md.get("ask_price"),
                             "delta": gk.get("delta"), "gamma": gk.get("gamma"), "theta": gk.get("theta"), "vega": gk.get("vega"),
                             "key": o.get("instrument_key")}
            rows.append(row)
        rows.sort(key=lambda x: x["strike"])
        pcr = data[0].get("pcr") if data else None
        return {"underlying": u, "expiry": expiry, "spot": spot, "rows": rows, "pcr": pcr, "source": "upstox-rest"}


class CandleStore:
    """Expired candles never change, so they are kept for good in SQLite (one row per contract-day)."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript("CREATE TABLE IF NOT EXISTS candles(k TEXT NOT NULL, day TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(k, day));"
                            "CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, body TEXT NOT NULL, at REAL NOT NULL);")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10, check_same_thread=False)

    def get(self, k: str, day: str):
        with self._lock, self._conn() as c:
            r = c.execute("SELECT body FROM candles WHERE k=? AND day=?", (k, day)).fetchone()
        return json.loads(r[0]) if r else None

    def put(self, k: str, day: str, candles: list) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO candles(k,day,body) VALUES(?,?,?)", (k, day, json.dumps(candles, separators=(",", ":"))))

    def meta_get(self, k: str, max_age: float):
        with self._lock, self._conn() as c:
            r = c.execute("SELECT body, at FROM meta WHERE k=?", (k,)).fetchone()
        if r and time.time() - r[1] < max_age:
            return json.loads(r[0])
        return None

    def meta_put(self, k: str, body) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO meta(k,body,at) VALUES(?,?,?)", (k, json.dumps(body, separators=(",", ":")), time.time()))

    def count(self) -> int:
        with self._lock, self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
