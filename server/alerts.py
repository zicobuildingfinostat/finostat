"""Server-side alerts: rules saved to the account, evaluated against the live feed.

The browser keeps its own alert engine for signed-out users. Signed-in users get
this one instead, which keeps running with every tab closed: the feed thread
hands each snapshot to `on_snapshot`, a worker evaluates at most once a second,
and a firing is written to the database, emailed, and surfaced to the terminal
on its next poll.

Two rules that matter more than the code:
  * Only LIVE snapshots are evaluated. Firing on simulator prices would email
    people about moves that never happened.
  * A rule fires once, then sits in `fired` until re-armed. No repeats, no
    hysteresis games, no inbox floods.
"""
from __future__ import annotations

import logging
import math
import queue
import sqlite3
import threading
import time

log = logging.getLogger("finostat.alerts")

# Non-spot metrics are fixed; spot metrics are "spot:<SYMBOL>" for any symbol the
# feed currently quotes, so widening the universe (F&O stocks, all of NSE) needs
# no change here.
FIXED_METRICS = {"straddle", "bfly", "net"}
DEFAULT_SYMBOLS = {"NIFTY 50", "BANKNIFTY", "SENSEX", "FINNIFTY", "INDIA VIX"}
STRIKE_METRICS = {"bfly", "net"}
CMPS = {">=", "<="}
MAX_PER_USER = 50

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts(
  id          INTEGER PRIMARY KEY,
  user_id     INTEGER NOT NULL,
  metric      TEXT NOT NULL,
  strike      INTEGER,
  cmp         TEXT NOT NULL,
  value       REAL NOT NULL,
  email       INTEGER NOT NULL DEFAULT 1,
  state       TEXT NOT NULL DEFAULT 'armed',
  created     REAL NOT NULL,
  fired_at    REAL,
  fired_value REAL
);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id);
CREATE TABLE IF NOT EXISTS alert_events(
  id       INTEGER PRIMARY KEY,
  user_id  INTEGER NOT NULL,
  alert_id INTEGER NOT NULL,
  ts       REAL NOT NULL,
  message  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_user ON alert_events(user_id, id);
"""


def metric_label(metric: str, strike) -> str:
    if metric.startswith("spot:"):
        return metric[5:] + " spot"
    if metric == "straddle":
        return "ATM straddle"
    return f"{metric.upper()} {strike}"


def metric_value(snapshot: dict, metric: str, strike) -> float | None:
    """Same semantics the terminal uses client-side, so both engines agree."""
    if metric.startswith("spot:"):
        sym = metric[5:]
        for q in snapshot.get("quotes") or []:
            if q.get("symbol") == sym:
                return q.get("price")
        return None
    if metric == "straddle":
        return snapshot.get("straddle")
    for row in (snapshot.get("sheet") or {}).get("rows") or []:
        if row[0] == strike:
            return row[3] if metric == "bfly" else row[4] if metric == "net" else None
    return None


def validate(payload: dict, symbols=None) -> tuple[dict | None, str | None]:
    """Turn a client payload into a clean rule, or explain why not.

    `symbols` is the set of spot symbols the feed can quote right now."""
    metric = payload.get("metric")
    if not isinstance(metric, str) or len(metric) > 80:
        return None, "unknown metric"
    if metric.startswith("spot:"):
        if metric[5:] not in (symbols if symbols is not None else DEFAULT_SYMBOLS):
            return None, "unknown symbol"
    elif metric not in FIXED_METRICS:
        return None, "unknown metric"
    strike = payload.get("strike")
    if metric in STRIKE_METRICS:
        try:
            strike = int(strike)
        except (TypeError, ValueError):
            return None, "strike required"
    else:
        strike = None
    cmp = payload.get("cmp")
    if cmp not in CMPS:
        return None, "cmp must be >= or <="
    try:
        value = float(payload.get("value"))
    except (TypeError, ValueError):
        return None, "value must be a number"
    if not math.isfinite(value):
        return None, "value must be finite"
    email = 1 if payload.get("email", True) else 0
    return {"metric": metric, "strike": strike, "cmp": cmp, "value": value, "email": email}, None


class AlertEngine:
    EVAL_INTERVAL = 1.0

    def __init__(self, db_path, send_email=None, user_email=None):
        """`send_email(to, subject, lines)` and `user_email(user_id) -> str` are
        injected so the engine can be tested without a mailer or the auth db."""
        self.path = db_path
        self._send_email = send_email
        self._user_email = user_email
        self._lock = threading.Lock()
        self._latest: queue.Queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._fired_total = 0
        self._evaluations = 0
        # The most recent live snapshot. A rule armed while the market is quiet
        # (after hours, a slow instrument) is checked against this at once, so a
        # condition that is already true fires immediately instead of waiting
        # for the next tick.
        self._last_snap: dict | None = None
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    # -- rule CRUD ----------------------------------------------------------
    def list_for(self, user_id: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY id", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def events_for(self, user_id: int, limit: int = 40) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id,alert_id,ts,message FROM alert_events WHERE user_id=? "
                             "ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def create(self, user_id: int, rule: dict) -> dict | None:
        with self._lock, self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM alerts WHERE user_id=?", (user_id,)).fetchone()[0]
            if n >= MAX_PER_USER:
                return None
            cur = c.execute(
                "INSERT INTO alerts(user_id,metric,strike,cmp,value,email,state,created) "
                "VALUES(?,?,?,?,?,?,'armed',?)",
                (user_id, rule["metric"], rule["strike"], rule["cmp"], rule["value"], rule["email"], time.time()))
            new_id = cur.lastrowid
        self._check_now(new_id)
        with self._conn() as c:
            row = c.execute("SELECT * FROM alerts WHERE id=?", (new_id,)).fetchone()
        return dict(row)

    def rearm(self, user_id: int, alert_id: int) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE alerts SET state='armed', fired_at=NULL, fired_value=NULL "
                            "WHERE id=? AND user_id=?", (alert_id, user_id))
        if cur.rowcount > 0:
            self._check_now(alert_id)
        return cur.rowcount > 0

    def delete(self, user_id: int, alert_id: int) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM alerts WHERE id=? AND user_id=?", (alert_id, user_id))
        return cur.rowcount > 0

    # -- evaluation ---------------------------------------------------------
    def on_snapshot(self, snap: dict) -> None:
        """Feed thread: keep only the newest snapshot, never block."""
        if not snap.get("live"):
            return
        self._last_snap = snap
        try:
            self._latest.get_nowait()
        except queue.Empty:
            pass
        try:
            self._latest.put_nowait(snap)
        except queue.Full:
            pass

    def _check_now(self, alert_id: int) -> None:
        snap = self._last_snap
        if snap is not None:
            self.evaluate(snap, only_id=alert_id)

    def evaluate(self, snap: dict, only_id: int | None = None) -> list[dict]:
        """Fire every armed rule the snapshot satisfies. Returns the firings."""
        if not snap.get("live"):
            return []
        self._last_snap = snap
        self._evaluations += 1
        now = time.time()
        fired = []
        with self._lock, self._conn() as c:
            if only_id is None:
                armed = c.execute("SELECT * FROM alerts WHERE state='armed'").fetchall()
            else:
                armed = c.execute("SELECT * FROM alerts WHERE state='armed' AND id=?", (only_id,)).fetchall()
            for a in armed:
                cur = metric_value(snap, a["metric"], a["strike"])
                if cur is None:
                    continue
                hit = cur >= a["value"] if a["cmp"] == ">=" else cur <= a["value"]
                if not hit:
                    continue
                label = metric_label(a["metric"], a["strike"])
                arrow = "≥" if a["cmp"] == ">=" else "≤"
                msg = f"{label} crossed {arrow} {a['value']:g} (now {cur:.2f})"
                c.execute("UPDATE alerts SET state='fired', fired_at=?, fired_value=? WHERE id=?",
                          (now, cur, a["id"]))
                c.execute("INSERT INTO alert_events(user_id,alert_id,ts,message) VALUES(?,?,?,?)",
                          (a["user_id"], a["id"], now, msg))
                fired.append({"user_id": a["user_id"], "alert_id": a["id"], "message": msg,
                              "email": bool(a["email"])})
        self._fired_total += len(fired)
        if fired:
            self._notify(fired)
        return fired

    def _notify(self, fired: list[dict]) -> None:
        """One email per user per evaluation, however many rules tripped at once."""
        if not self._send_email or not self._user_email:
            return
        by_user: dict[int, list[str]] = {}
        for f in fired:
            log.info("alert fired for user %s: %s", f["user_id"], f["message"])
            if f["email"]:
                by_user.setdefault(f["user_id"], []).append(f["message"])
        for uid, lines in by_user.items():
            to = self._user_email(uid)
            if not to:
                continue
            subject = "Finostat alert: " + (lines[0] if len(lines) == 1 else f"{len(lines)} alerts fired")
            try:
                self._send_email(to, subject, lines)
            except Exception:
                log.exception("alert email to %s failed", to)

    # -- worker -------------------------------------------------------------
    def start(self) -> None:
        threading.Thread(target=self._run, name="alerts", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        log.info("alert engine running (live snapshots only)")
        while not self._stop.is_set():
            try:
                snap = self._latest.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                self.evaluate(snap)
            except Exception:
                log.exception("alert evaluation failed")
            self._stop.wait(self.EVAL_INTERVAL)

    def stats(self) -> dict:
        with self._conn() as c:
            armed = c.execute("SELECT COUNT(*) FROM alerts WHERE state='armed'").fetchone()[0]
        return {"armed": armed, "fired_total": self._fired_total, "evaluations": self._evaluations}
