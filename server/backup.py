"""Daily on-volume backups of the accounts database.

The volume has Fly's own snapshots, but a torn header on 2026-09-08 showed how
cheap it is to lose the accounts file at a bad moment. `sqlite3`'s online
backup API copies a consistent snapshot while the server keeps running.
"""
from __future__ import annotations

import logging
import pathlib
import sqlite3
import threading
import time

log = logging.getLogger("finostat.backup")


def backup_once(src: pathlib.Path, dest_dir: pathlib.Path, keep: int = 7) -> pathlib.Path | None:
    if not src.exists():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"{src.stem}-{stamp}{src.suffix}"
    s = sqlite3.connect(src, timeout=10)
    try:
        d = sqlite3.connect(dest)
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()
    # prune, oldest first
    olds = sorted(dest_dir.glob(f"{src.stem}-*{src.suffix}"))
    for old in olds[:-keep] if keep > 0 else []:
        try:
            old.unlink()
        except OSError:
            pass
    return dest


class DailyBackup:
    def __init__(self, src: pathlib.Path, dest_dir: pathlib.Path, interval: float = 86400.0,
                 first_delay: float = 90.0, keep: int = 7):
        self.src, self.dest_dir, self.interval, self.first_delay, self.keep = src, dest_dir, interval, first_delay, keep
        self._stop = threading.Event()
        self.last: float | None = None
        self.last_path: str | None = None
        self.error: str | None = None

    def start(self) -> None:
        threading.Thread(target=self._run, name="backup", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def run_now(self) -> None:
        try:
            p = backup_once(self.src, self.dest_dir, self.keep)
            if p:
                self.last, self.last_path, self.error = time.time(), p.name, None
                log.info("backed up %s -> %s", self.src.name, p.name)
        except (sqlite3.Error, OSError) as exc:
            self.error = str(exc)
            log.error("backup of %s failed: %s", self.src.name, exc)

    def _run(self) -> None:
        if self._stop.wait(self.first_delay):
            return
        while not self._stop.is_set():
            self.run_now()
            if self._stop.wait(self.interval):
                return

    def stats(self) -> dict:
        try:
            count = len(list(self.dest_dir.glob(f"{self.src.stem}-*{self.src.suffix}")))
        except OSError:
            count = 0
        return {"last": self.last, "last_file": self.last_path, "count": count, "error": self.error}
