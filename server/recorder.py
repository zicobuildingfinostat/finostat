"""Tick recorder: banks every live snapshot to SQLite.

The homepage promises "4 yrs expiry history", historical replay and
backtesting. None of that can be backfilled -- data not recorded today is gone
forever -- so this exists before any replay UI does.

Design notes:
  * Snapshots arrive via Feed.add_listener on the feed's thread. The listener
    only enqueues; a dedicated writer thread owns the SQLite connection, which
    keeps sqlite3's thread rules honest and never blocks the market feed.
  * Only LIVE snapshots are recorded. Simulator output would poison the
    history with invented prices, which is worse than a gap.
  * Throttled to one row per second. At market cadence that is ~22.5k rows a
    trading day, roughly 10 MB/day of JSON -- a 1 GB volume holds months.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import queue
import sqlite3
import threading
import time

log = logging.getLogger("finostat.recorder")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots(
  ts       REAL NOT NULL,
  symbol   TEXT NOT NULL,
  atm      INTEGER,
  straddle REAL,
  quotes   TEXT NOT NULL,
  rows     TEXT NOT NULL,
  mini     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
"""


def _data_dir() -> pathlib.Path:
    configured = os.environ.get("FINOSTAT_DATA_DIR", "").strip()
    if configured:
        return pathlib.Path(configured)
    return pathlib.Path(__file__).resolve().parent / "data"


class Recorder:
    MIN_INTERVAL = 1.0          # seconds between recorded rows
    BATCH_COMMIT = 2.0          # seconds between commits

    def __init__(self) -> None:
        self.enabled = os.environ.get("FINOSTAT_RECORD", "1").strip() != "0"
        self.path = _data_dir() / "ticks.db"
        self._queue: queue.Queue = queue.Queue(maxsize=600)
        self._stop = threading.Event()
        self._last_enqueued = 0.0
        self._lock = threading.Lock()
        self._written = 0
        self._dropped = 0
        self._error: str | None = None

    # -- listener (feed thread; must never block) ---------------------------
    def on_snapshot(self, snap: dict) -> None:
        if not self.enabled or not snap.get("live"):
            return
        now = time.time()
        if now - self._last_enqueued < self.MIN_INTERVAL:
            return
        self._last_enqueued = now
        row = (
            now,
            snap.get("symbol") or "",
            snap.get("atm"),
            snap.get("straddle"),
            json.dumps(snap.get("quotes") or [], separators=(",", ":")),
            json.dumps((snap.get("sheet") or {}).get("rows") or [], separators=(",", ":")),
            json.dumps(snap.get("mini") or [], separators=(",", ":")),
        )
        try:
            self._queue.put_nowait(row)
        except queue.Full:
            with self._lock:
                self._dropped += 1

    # -- writer thread ------------------------------------------------------
    def start(self) -> None:
        if not self.enabled:
            log.info("recorder disabled (FINOSTAT_RECORD=0)")
            return
        threading.Thread(target=self._run, name="recorder", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path)
            conn.executescript(_SCHEMA)
            # WAL keeps readers (the /api/history endpoint) from blocking writes.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.commit()
        except (OSError, sqlite3.Error) as exc:
            with self._lock:
                self._error = f"recorder disabled: {exc}"
            log.error("cannot open %s: %s", self.path, exc)
            return
        log.info("recording live snapshots to %s", self.path)

        pending = []
        last_commit = time.time()
        while not self._stop.is_set():
            try:
                pending.append(self._queue.get(timeout=1.0))
            except queue.Empty:
                pass
            if pending and (time.time() - last_commit >= self.BATCH_COMMIT):
                try:
                    conn.executemany(
                        "INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)", pending)
                    conn.commit()
                    with self._lock:
                        self._written += len(pending)
                    pending.clear()
                    last_commit = time.time()
                except sqlite3.Error as exc:
                    with self._lock:
                        self._error = str(exc)
                    log.error("write failed: %s", exc)
                    pending.clear()
        if pending:
            try:
                conn.executemany("INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)", pending)
                conn.commit()
            except sqlite3.Error:
                pass
        conn.close()

    # -- read side ----------------------------------------------------------
    def stats(self) -> dict:
        with self._lock:
            out = {"enabled": self.enabled, "written": self._written,
                   "dropped": self._dropped, "error": self._error}
        try:
            out["db_bytes"] = self.path.stat().st_size
        except OSError:
            out["db_bytes"] = 0
        return out

    def history(self, since: float | None = None, limit: int = 300) -> list[dict]:
        """Recent recorded snapshots, oldest first. Read-only connection."""
        limit = max(1, min(2000, limit))
        try:
            conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        except sqlite3.Error:
            return []
        try:
            if since is not None:
                cur = conn.execute(
                    "SELECT ts,symbol,atm,straddle,quotes,rows,mini FROM snapshots "
                    "WHERE ts>? ORDER BY ts LIMIT ?", (since, limit))
            else:
                cur = conn.execute(
                    "SELECT * FROM (SELECT ts,symbol,atm,straddle,quotes,rows,mini "
                    "FROM snapshots ORDER BY ts DESC LIMIT ?) ORDER BY ts", (limit,))
            out = []
            for ts, symbol, atm, straddle, quotes, rows, mini in cur.fetchall():
                out.append({"ts": ts, "symbol": symbol, "atm": atm, "straddle": straddle,
                            "quotes": json.loads(quotes), "rows": json.loads(rows),
                            "mini": json.loads(mini)})
            return out
        except sqlite3.Error:
            return []
        finally:
            conn.close()
