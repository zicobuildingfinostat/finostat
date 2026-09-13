"""Watchdog: session gating, diagnosis, grace, hourly repeats, recovery; email attach flow."""
import sys, pathlib, tempfile, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import watchdog as W, auth as A
IST = timezone(timedelta(hours=5, minutes=30))
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

class FakeFeed:
    name = "upstox"
    def __init__(self): self.live = True; self._ticks = 0; self._ws = object(); self.error = None
    def snapshot(self): return {"live": self.live, "error": self.error}
class Hol:
    def dates(self): return {"2026-09-14"}
notes = []
feed = FakeFeed(); clock = {"now": datetime(2026, 9, 15, 10, 0, tzinfo=IST)}
wd = W.Watchdog(feed, Hol(), notify=lambda s, l: notes.append(s), clock=lambda: clock["now"])
print("=== session gating ===")
check("weekday in hours -> in session", wd.in_session(datetime(2026, 9, 15, 10, 0, tzinfo=IST)))
check("holiday, weekend, before open, after close -> not", not wd.in_session(datetime(2026, 9, 14, 10, 0, tzinfo=IST)) and not wd.in_session(datetime(2026, 9, 13, 10, 0, tzinfo=IST)) and not wd.in_session(datetime(2026, 9, 15, 9, 0, tzinfo=IST)) and not wd.in_session(datetime(2026, 9, 15, 15, 45, tzinfo=IST)))
print("\n=== diagnose + alerts ===")
feed._ticks = 10; wd.check()
check("healthy: no trouble", wd.trouble_since is None and wd.diagnose() is None)
feed._ws = None; wd.check()
check("socket refused -> trouble noted, no note before the grace period", wd.trouble_since is not None and "REST" in wd.last_reason and not notes)
wd.trouble_since -= 6 * 60; wd.check()
check("after 5 min: one note sent", len(notes) == 1 and "REST" in notes[0], notes)
wd.check()
check("no repeat within the hour", len(notes) == 1)
wd.last_alert -= 61 * 60; wd.check()
check("hourly reminder", len(notes) == 2)
feed._ws = object(); wd.check()
check("recovery note and state cleared", len(notes) == 3 and "recovered" in notes[2] and wd.trouble_since is None)
feed.live = False; feed.error = "handshake rejected: HTTP 403"; wd.check()
check("not live -> reason carries the feed error", "403" in (wd.last_reason or ""))
feed.live = True; feed._ticks = 10; wd.check(); wd.last_tick_change -= 400; wd.check()
check("stale ticks detected", wd.last_reason and "no ticks" in wd.last_reason, wd.last_reason)
clock["now"] = datetime(2026, 9, 13, 10, 0, tzinfo=IST); wd.check()
check("outside the session: trouble state reset, nothing sent", wd.trouble_since is None and len(notes) == 3)
print("\n=== email attach ===")
tmp = pathlib.Path(tempfile.mkdtemp()); import os; os.environ["FINOSTAT_DATA_DIR"] = str(tmp)
au = A.Auth(tmp / "acct.db") if "path" in A.Auth.__init__.__code__.co_varnames else A.Auth()
u = au.find_or_create_by_phone("9000000001")
tok = au.start_email_attach(u["id"], "Owner@Example.com")
check("token issued for a fresh email; placeholder/duplicate refused", tok and au.start_email_attach(u["id"], "x@mobile.finostat") is None)
with au._conn() as c:
    c.execute("INSERT INTO users(email,created,last_seen) VALUES('taken@example.com',1,1)")
check("email already on another account refused", au.start_email_attach(u["id"], "taken@example.com") is None)
u2 = au.finish_email_attach(tok)
check("redeem attaches the verified email and keeps the phone", u2 and u2["email"] == "owner@example.com" and u2["phone"] == "9000000001" and not A.is_phone_only(u2["email"]), u2)
check("token is single-use", au.finish_email_attach(tok) is None and au.finish_email_attach("bogus") is None)
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
