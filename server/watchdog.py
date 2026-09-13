"""Feed watchdog: tells the owner when the market feed is not what it should be.

Every minute during the session it looks at three things: is the websocket up, are ticks
still arriving, and has the terminal been running on the REST fallback. After five minutes of
trouble it emails the owner once, repeats hourly while the trouble lasts, and sends an all-clear
when the feed recovers. The state is also exposed on /api/status and the owner's account page.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger("finostat.watchdog")
IST = timezone(timedelta(hours=5, minutes=30))

GRACE = 5 * 60          # seconds of continuous trouble before the first note
REPEAT = 60 * 60        # seconds between reminder notes while it lasts
STALE = 3 * 60          # seconds without a tick that count as trouble


class Watchdog:
    def __init__(self, feed, holidays=None, notify=None, clock=None):
        self.feed, self.holidays, self.notify, self.clock = feed, holidays, notify, clock or (lambda: datetime.now(IST))
        self._stop = threading.Event()
        self.trouble_since: float | None = None
        self.last_alert: float | None = None
        self.last_reason: str | None = None
        self.last_tick_count: int | None = None
        self.last_tick_change: float = time.time()
        self.notes_sent = 0

    # -- lifecycle -------------------------------------------------------------
    def start(self) -> None:
        threading.Thread(target=self._run, name="watchdog", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(60.0):
            try:
                self.check()
            except Exception:                                   # noqa: BLE001
                log.exception("watchdog check failed")

    # -- the check ---------------------------------------------------------------
    def in_session(self, now: datetime | None = None) -> bool:
        now = now or self.clock()
        if now.weekday() >= 5:
            return False
        if self.holidays is not None:
            try:
                if now.strftime("%Y-%m-%d") in self.holidays.dates():
                    return False
            except Exception:                                   # noqa: BLE001
                pass
        hhmm = now.hour * 60 + now.minute
        return 9 * 60 + 16 <= hhmm <= 15 * 60 + 30

    def diagnose(self) -> str | None:
        """None when healthy, else a short reason."""
        snap = self.feed.snapshot() if hasattr(self.feed, "snapshot") else {}
        ticks = getattr(self.feed, "_ticks", None)
        now = time.time()
        if ticks is not None:
            if self.last_tick_count is None or ticks != self.last_tick_count:
                self.last_tick_count, self.last_tick_change = ticks, now
        if not snap.get("live"):
            return f"feed not live: {snap.get('error') or 'no error text'}"
        if ticks is not None and now - self.last_tick_change > STALE:
            return f"no ticks for {int(now - self.last_tick_change)}s"
        if hasattr(self.feed, "_ws") and getattr(self.feed, "_ws", None) is None and getattr(self.feed, "name", "") == "upstox":
            return "websocket refused — running on REST polling"
        return None

    def check(self, now: datetime | None = None) -> dict:
        now = now or self.clock()
        if not self.in_session(now):
            if self.trouble_since:                               # session ended while in trouble: reset quietly
                self.trouble_since = self.last_reason = None
            return self.status()
        reason = self.diagnose()
        t = time.time()
        if reason:
            if self.trouble_since is None:
                self.trouble_since = t
            self.last_reason = reason
            elapsed = t - self.trouble_since
            due = elapsed >= GRACE and (self.last_alert is None or t - self.last_alert >= REPEAT)
            if due and self.notify:
                self.notify("Finostat feed: " + reason, [f"Since {datetime.fromtimestamp(self.trouble_since, IST).strftime('%H:%M IST')} ({int(elapsed // 60)} min)",
                                                         "The terminal keeps serving prices over REST if the socket is refused; streaming resumes on its own when Upstox accepts the connection.",
                                                         "Check: https://finostat.com/api/status and the Fly logs."])
                self.last_alert = t
                self.notes_sent += 1
        elif self.trouble_since is not None:
            if self.last_alert and self.notify:
                self.notify("Finostat feed: recovered", [f"Trouble lasted {int((t - self.trouble_since) // 60)} min ({self.last_reason}).", "Streaming is back to normal."])
                self.notes_sent += 1
            self.trouble_since = self.last_reason = self.last_alert = None
        return self.status()

    def status(self) -> dict:
        return {"in_session": self.in_session(), "trouble_since": self.trouble_since, "reason": self.last_reason,
                "alerted": self.last_alert, "notes_sent": self.notes_sent}
