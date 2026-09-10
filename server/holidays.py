"""NSE trading holidays, fetched from the exchange's own holiday-master API (F&O and cash
segments), stored in the accounts DB and refreshed daily. Feeds the /calendar/nse-holidays
page, the holiday rows on the live calendar, and the working-day rules for India's releases."""
from __future__ import annotations

import http.cookiejar
import json
import logging
import pathlib
import sqlite3
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger("finostat.holidays")
IST = timezone(timedelta(hours=5, minutes=30))
NSE_API = "https://www.nseindia.com/api/holiday-master?type=trading"
NSE_HOME = "https://www.nseindia.com/resources/exchange-communication-holidays"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nse_holidays(
  date     TEXT PRIMARY KEY,
  name     TEXT NOT NULL,
  fo       INTEGER NOT NULL DEFAULT 0,
  cm       INTEGER NOT NULL DEFAULT 0,
  muhurat  INTEGER NOT NULL DEFAULT 0,
  updated  REAL NOT NULL
);
"""


def parse(payload: dict) -> list[dict]:
    """{'FO': [...], 'CM': [...]} -> rows {date, name, fo, cm, muhurat}."""
    rows: dict[str, dict] = {}
    for seg in ("FO", "CM"):
        for r in payload.get(seg) or []:
            try:
                d = datetime.strptime(str(r.get("tradingDate", "")).strip(), "%d-%b-%Y").date()
            except ValueError:
                continue
            name = str(r.get("description", "")).strip()
            muhurat = name.endswith("*") or "muhurat" in name.lower()
            name = name.rstrip("*").strip()
            row = rows.setdefault(d.isoformat(), {"date": d.isoformat(), "name": name, "fo": 0, "cm": 0, "muhurat": 0})
            row[seg.lower()] = 1
            row["muhurat"] = int(row["muhurat"] or muhurat)
    return sorted(rows.values(), key=lambda r: r["date"])


class Holidays:
    def __init__(self, path: pathlib.Path, interval: float = 24 * 3600):
        self.path, self.interval = pathlib.Path(path), interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.fetched: float | None = None
        self.error: str | None = None
        self._cache: tuple[float, list[dict]] | None = None
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def start(self) -> None:
        threading.Thread(target=self._run, name="holidays", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        delay = 30.0
        while not self._stop.is_set():
            ok = self.refresh()
            wait = self.interval if ok else min(delay, 3600.0)
            if not ok:
                delay *= 2
            if self._stop.wait(wait):
                return

    def refresh(self) -> bool:
        try:
            cj = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
            op.open(urllib.request.Request(NSE_HOME, headers=h), timeout=20).read(2000)      # cookies
            r = op.open(urllib.request.Request(NSE_API, headers=dict(h, Accept="application/json", Referer="https://www.nseindia.com/")), timeout=20)
            rows = parse(json.loads(r.read().decode("utf-8")))
        except Exception as exc:
            self.error = str(exc)[:160]
            log.warning("holidays: NSE: %s", exc)
            return False
        if not rows:
            self.error = "empty holiday list"
            return False
        self.store(rows)
        self.fetched, self.error = time.time(), None
        log.info("holidays: %d NSE holidays on file", len(rows))
        return True

    def store(self, rows: list[dict]) -> None:
        with self._lock, self._conn() as c:
            for r in rows:
                c.execute("INSERT INTO nse_holidays(date,name,fo,cm,muhurat,updated) VALUES(?,?,?,?,?,?) ON CONFLICT(date) DO UPDATE SET "
                          "name=excluded.name, fo=excluded.fo, cm=excluded.cm, muhurat=excluded.muhurat, updated=excluded.updated",
                          (r["date"], r["name"], int(r["fo"]), int(r["cm"]), int(r["muhurat"]), time.time()))
            self._cache = None

    def all(self) -> list[dict]:
        with self._lock:
            if self._cache and time.time() - self._cache[0] < 60:
                return list(self._cache[1])
            with self._conn() as c:
                rows = [dict(r) for r in c.execute("SELECT date,name,fo,cm,muhurat FROM nse_holidays ORDER BY date").fetchall()]
            self._cache = (time.time(), rows)
            return list(rows)

    def dates(self, segment: str = "fo") -> set[str]:
        """ISO dates on which the segment is closed (weekend listings included; harmless)."""
        return {r["date"] for r in self.all() if r.get(segment, 0)}

    def is_closed(self, d: date, segment: str = "fo") -> bool:
        return d.weekday() >= 5 or d.isoformat() in self.dates(segment)

    def next_open(self, d: date, segment: str = "fo") -> date:
        while self.is_closed(d, segment):
            d += timedelta(days=1)
        return d
