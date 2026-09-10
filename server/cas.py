"""Closing Auction Session (CAS) monitor: index IEP vs the synthetic future.

Every trading day between 15:15 and 15:40 IST the recorder samples, once a
second, each index's exchange value (the auction-driven indicative level
during CAS -- Upstox marks it `iep` when the exchange flags it) and the
synthetic future built from the option chain at an ATM strike frozen at
15:15: synthetic = ATM + call - put. Where the two diverge is where the
auction is pushing the cash index away from what the derivatives market is
paying. Sessions are stored by date for replay.
"""
from __future__ import annotations

import json
import logging
import pathlib
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger("finostat.cas")

IST = timezone(timedelta(hours=5, minutes=30))
UNDERLYINGS = ["NIFTY 50", "BANKNIFTY", "SENSEX"]
REF_AT = (15, 15)            # reference level and fixed ATM are taken here
WINDOW = ((15, 14), (15, 41))  # record between these (IST), inclusive start / exclusive end
KEEP_DAYS = 60

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cas_sessions(
  date     TEXT NOT NULL,
  u        TEXT NOT NULL,
  ref      REAL,
  atm      INTEGER,
  expiry   INTEGER,
  lot      INTEGER,
  points   TEXT NOT NULL,
  updated  REAL NOT NULL,
  PRIMARY KEY(date, u)
);
"""


def in_window(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    hm = (now.hour, now.minute)
    return WINDOW[0] <= hm < WINDOW[1]


def past_ref(now: datetime) -> bool:
    return (now.hour, now.minute) >= REF_AT


def synthetic(atm: int, ce: float | None, pe: float | None) -> float | None:
    if atm is None or ce is None or pe is None:
        return None
    return round(atm + ce - pe, 2)


class Session:
    """One index, one day."""

    def __init__(self, u: str, date: str):
        self.u, self.date = u, date
        self.ref: float | None = None
        self.atm: int | None = None
        self.expiry: int | None = None
        self.lot: int | None = None
        self.points: list = []            # [ts, index, synth, is_iep]

    def fix(self, ref: float, atm: int, expiry: int, lot: int) -> None:
        self.ref, self.atm, self.expiry, self.lot = ref, atm, expiry, lot

    def add(self, ts: float, index: float | None, synth: float | None, is_iep: bool) -> None:
        if index is None and synth is None:
            return
        self.points.append([round(ts, 1), index, synth, 1 if is_iep else 0])

    def to_dict(self) -> dict:
        idx = [p[1] for p in self.points if p[1] is not None]
        syn = [p[2] for p in self.points if p[2] is not None]
        last_i = idx[-1] if idx else None
        last_s = syn[-1] if syn else None
        return {"u": self.u, "date": self.date, "ref": self.ref, "atm": self.atm, "expiry": self.expiry, "lot": self.lot,
                "points": self.points, "n": len(self.points),
                "stats": {"index": last_i, "synth": last_s, "basis": round(last_i - last_s, 2) if last_i is not None and last_s is not None else None,
                          "index_hi": max(idx) if idx else None, "index_lo": min(idx) if idx else None,
                          "synth_hi": max(syn) if syn else None, "synth_lo": min(syn) if syn else None,
                          "iep_ticks": sum(p[3] for p in self.points)}}


class Store:
    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self._lock = threading.Lock()
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def save(self, s: Session) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO cas_sessions(date,u,ref,atm,expiry,lot,points,updated) VALUES(?,?,?,?,?,?,?,?) "
                      "ON CONFLICT(date,u) DO UPDATE SET ref=excluded.ref,atm=excluded.atm,expiry=excluded.expiry,lot=excluded.lot,points=excluded.points,updated=excluded.updated",
                      (s.date, s.u, s.ref, s.atm, s.expiry, s.lot, json.dumps(s.points, separators=(",", ":")), time.time()))
            c.execute("DELETE FROM cas_sessions WHERE date < (SELECT date FROM cas_sessions GROUP BY date ORDER BY date DESC LIMIT 1 OFFSET ?)", (KEEP_DAYS,))

    def load(self, u: str, date: str) -> Session | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM cas_sessions WHERE date=? AND u=?", (date, u)).fetchone()
        if r is None:
            return None
        s = Session(u, date)
        s.fix(r["ref"], r["atm"], r["expiry"], r["lot"])
        s.points = json.loads(r["points"])
        return s

    def dates(self, u: str | None = None, limit: int = 60) -> list[str]:
        with self._conn() as c:
            if u:
                rows = c.execute("SELECT DISTINCT date FROM cas_sessions WHERE u=? ORDER BY date DESC LIMIT ?", (u, limit)).fetchall()
            else:
                rows = c.execute("SELECT DISTINCT date FROM cas_sessions ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
        return [r[0] for r in rows]


class Recorder:
    """Samples the live feed during the window; keeps today's sessions in memory."""

    def __init__(self, feed, chains, store: Store, interval: float = 1.0, underlyings=None):
        self.feed, self.chains, self.store, self.interval = feed, chains, store, interval
        self.underlyings = list(underlyings or UNDERLYINGS)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.today: dict[str, Session] = {}
        self.date: str | None = None
        self.last_save = 0.0

    def start(self) -> None:
        threading.Thread(target=self._run, name="cas", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _index_level(self, u: str):
        """(level, is_iep). Prefer the exchange's IEP tick when the feed has one."""
        iep = getattr(self.feed, "iep_of", None)
        if iep:
            v = iep(u)
            if v:
                return v, True
        return self.feed.spot_of(u), False

    def sample(self, now: datetime | None = None) -> None:
        now = now or datetime.now(IST)
        date = now.strftime("%Y-%m-%d")
        with self._lock:
            if self.date != date:
                self.date, self.today = date, {}
            for u in self.underlyings:
                s = self.today.get(u)
                if s is None:
                    s = self.today[u] = Session(u, date)
                try:
                    chain = self.chains.chain(u)
                except Exception:
                    chain = {}
                level, is_iep = self._index_level(u)
                if s.atm is None and past_ref(now) and level and chain.get("rows"):
                    step = chain.get("step") or 50
                    s.fix(float(level), int(round(level / step) * step), chain.get("expiry"), chain.get("lot"))
                    log.info("cas %s: 15:15 ref %.2f, fixed ATM %d, expiry %s", u, s.ref, s.atm, chain.get("expiry"))
                synth = None
                if s.atm is not None and chain.get("rows"):
                    row = next((r for r in chain["rows"] if r["strike"] == s.atm), None)
                    if row and row.get("ce") and row.get("pe"):
                        synth = synthetic(s.atm, row["ce"].get("ltp"), row["pe"].get("ltp"))
                s.add(now.timestamp(), float(level) if level else None, synth, is_iep)
        if time.time() - self.last_save > 15:
            self.flush()

    def flush(self) -> None:
        with self._lock:
            sessions = [s for s in self.today.values() if s.points]
        for s in sessions:
            try:
                self.store.save(s)
            except Exception:
                log.exception("cas save failed")
        self.last_save = time.time()

    def get(self, u: str, date: str | None = None) -> dict:
        now = datetime.now(IST)
        today = now.strftime("%Y-%m-%d")
        date = date or today
        with self._lock:
            s = self.today.get(u) if date == today else None
        if s is None or not s.points:
            s = self.store.load(u, date) or s or Session(u, date)
        d = s.to_dict()
        d["live"] = date == today and in_window(now)
        d["window"] = {"start": f"{WINDOW[0][0]:02d}:{WINDOW[0][1]:02d}", "end": f"{WINDOW[1][0]:02d}:{WINDOW[1][1]:02d}", "ref": f"{REF_AT[0]:02d}:{REF_AT[1]:02d}"}
        d["dates"] = self.store.dates(u)
        return d

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                now = datetime.now(IST)
                if in_window(now) and self.feed.snapshot().get("live"):
                    self.sample(now)
                elif self.today and self.last_save and time.time() - self.last_save > 5:
                    self.flush()
                    self.last_save = 0.0       # one final flush after the window, then rest
            except Exception:
                log.exception("cas recorder")
