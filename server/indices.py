"""Index constituents (Nifty 50 for now): fetched from NSE, cached on disk, with
a built-in fallback so the feature never depends on NSE's archive server
answering. Membership changes twice a year; the fallback is a snapshot and
says so.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import pathlib
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("finostat.indices")

SOURCES = {
    "NIFTY50": [
        "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv",
        "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    ],
}

# Snapshot fallback (NSE list as of 2026-09-08). Used only when neither NSE nor the on-disk cache
# is available; the status endpoint reports which source is in effect.
FALLBACK = {
    "NIFTY50": [
        "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO",
        "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL", "CIPLA", "COALINDIA", "DRREDDY",
        "EICHERMOT", "ETERNAL", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HINDALCO",
        "HINDUNILVR", "ICICIBANK", "ITC", "INFY", "INDIGO", "JSWSTEEL", "JIOFIN",
        "KOTAKBANK", "LT", "M&M", "MARUTI", "MAXHEALTH", "NTPC", "NESTLEIND", "ONGC",
        "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS",
        "TATACONSUM", "TMPV", "TATASTEEL", "TECHM", "TITAN", "TRENT", "ULTRACEMCO",
        "WIPRO",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/csv,text/plain,*/*",
    "Referer": "https://www.nseindia.com/",
}


def parse_csv(text: str) -> list[str]:
    """Symbols from NSE's constituents CSV (column 'Symbol'), in file order."""
    rows = list(csv.DictReader(io.StringIO(text)))
    col = None
    for name in (rows[0].keys() if rows else []):
        if name and name.strip().lower() == "symbol":
            col = name
            break
    if col is None:
        raise ValueError("no Symbol column")
    out = []
    for r in rows:
        sym = (r.get(col) or "").strip().upper()
        if sym and sym not in out:
            out.append(sym)
    if len(out) < 30:
        raise ValueError(f"only {len(out)} symbols; not a constituents file")
    return out


def _data_dir() -> pathlib.Path:
    configured = os.environ.get("FINOSTAT_DATA_DIR", "").strip()
    return pathlib.Path(configured) if configured else pathlib.Path(__file__).resolve().parent / "data"


class Constituents:
    REFRESH = 24 * 3600

    def __init__(self, index: str = "NIFTY50", cache_dir: pathlib.Path | None = None):
        self.index = index
        self.cache = (cache_dir or _data_dir()) / f"{index.lower()}.json"
        self._lock = threading.Lock()
        self.symbols: list[str] = list(FALLBACK.get(index, []))
        self.source = "fallback"
        self.fetched: float | None = None
        self._load_cache()

    # -- sources ------------------------------------------------------------
    def _load_cache(self) -> None:
        try:
            data = json.loads(self.cache.read_text(encoding="utf-8"))
            syms = [s for s in data.get("symbols", []) if isinstance(s, str)]
            if len(syms) >= 30:
                with self._lock:
                    self.symbols, self.source, self.fetched = syms, "cache", data.get("fetched")
        except (OSError, ValueError):
            pass

    def fetch(self) -> bool:
        """Try NSE; on success update memory and the cache. Never raises."""
        for url in SOURCES.get(self.index, []):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    text = resp.read().decode("utf-8-sig", "replace")
                syms = parse_csv(text)
            except (urllib.error.URLError, OSError, ValueError) as exc:
                log.warning("%s: %s -> %s", self.index, url, exc)
                continue
            with self._lock:
                self.symbols, self.source, self.fetched = syms, "nse", time.time()
            try:
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                self.cache.write_text(json.dumps({"symbols": syms, "fetched": self.fetched}), encoding="utf-8")
            except OSError as exc:
                log.warning("could not cache %s: %s", self.index, exc)
            log.info("%s: %d constituents from NSE", self.index, len(syms))
            return True
        return False

    def start(self, first_delay: float = 20.0) -> None:
        def run():
            if self._stop.wait(first_delay):
                return
            while not self._stop.is_set():
                self.fetch()
                if self._stop.wait(self.REFRESH):
                    return
        self._stop = threading.Event()
        threading.Thread(target=run, name=f"idx-{self.index}", daemon=True).start()

    def stop(self) -> None:
        if hasattr(self, "_stop"):
            self._stop.set()

    # -- read side ----------------------------------------------------------
    def members(self) -> set[str]:
        with self._lock:
            return set(self.symbols)

    def stats(self) -> dict:
        with self._lock:
            return {"index": self.index, "count": len(self.symbols), "source": self.source,
                    "fetched": self.fetched}
