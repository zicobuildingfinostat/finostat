"""Alert engine: validation, live-only, fire-once, rearm, isolation, email coalescing."""
import os, sys, tempfile, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import alerts as AL

ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}"))
    ok = ok and cond

sent = []
emails = {1: "one@x.com", 2: "two@x.com"}
eng = AL.AlertEngine(pathlib.Path(tempfile.mkdtemp()) / "a.db",
                     send_email=lambda to, subj, lines: sent.append((to, subj, list(lines))),
                     user_email=lambda uid: emails.get(uid))

def snap(spot=23650.0, straddle=70.0, live=True, bfly_atm=15.0, net_atm=0.3):
    return {"live": live, "straddle": straddle,
            "quotes": [{"symbol": "NIFTY 50", "price": spot, "change": 0.0},
                       {"symbol": "RELIANCE", "price": 2900.0, "change": 0.1}],
            "sheet": {"rows": [[23600, 80.0, 12.0, 10.0, -0.2], [23650, 46.0, 29.0, bfly_atm, net_atm]]}}

print("=== validation ===")
r, e = AL.validate({"metric": "spot:NIFTY 50", "cmp": ">=", "value": "24000"})
check("index spot rule ok", r and r["value"] == 24000.0 and r["strike"] is None and r["email"] == 1, (r, e))
r, e = AL.validate({"metric": "spot:RELIANCE", "cmp": "<=", "value": 2800}, symbols={"NIFTY 50", "RELIANCE"})
check("stock spot ok when in universe", r is not None, e)
r, e = AL.validate({"metric": "spot:RELIANCE", "cmp": "<=", "value": 2800})
check("stock spot rejected outside default universe", r is None and e == "unknown symbol", e)
r, e = AL.validate({"metric": "bfly", "strike": "23650", "cmp": ">=", "value": 14})
check("strike coerced to int", r and r["strike"] == 23650, r)
check("bfly without strike rejected", AL.validate({"metric": "bfly", "cmp": ">=", "value": 1})[1] == "strike required")
check("bad cmp rejected", AL.validate({"metric": "straddle", "cmp": "==", "value": 1})[1] is not None)
check("NaN rejected", AL.validate({"metric": "straddle", "cmp": ">=", "value": "nan"})[1] is not None)
check("email opt-out honoured", AL.validate({"metric": "straddle", "cmp": ">=", "value": 1, "email": False})[0]["email"] == 0)

print("\n=== metric values ===")
s = snap()
check("spot", AL.metric_value(s, "spot:NIFTY 50", None) == 23650.0)
check("straddle", AL.metric_value(s, "straddle", None) == 70.0)
check("bfly@strike", AL.metric_value(s, "bfly", 23650) == 15.0)
check("net@strike", AL.metric_value(s, "net", 23600) == -0.2)
check("missing strike -> None", AL.metric_value(s, "bfly", 99999) is None)

print("\n=== lifecycle ===")
a1 = eng.create(1, AL.validate({"metric": "spot:NIFTY 50", "cmp": ">=", "value": 23700})[0])
a2 = eng.create(1, AL.validate({"metric": "straddle", "cmp": "<=", "value": 65})[0])
a3 = eng.create(2, AL.validate({"metric": "bfly", "strike": 23650, "cmp": ">=", "value": 14})[0])
check("three rules created", all([a1, a2, a3]) and len(eng.list_for(1)) == 2 and len(eng.list_for(2)) == 1)
check("simulator snapshot never evaluated", eng.evaluate(snap(spot=30000, live=False)) == [] and sent == [])
f = eng.evaluate(snap(spot=23650, straddle=70, bfly_atm=15))
check("only satisfied rules fire (bfly for user 2)", [x["alert_id"] for x in f] == [a3["id"]], f)
check("fired state persisted", eng.list_for(2)[0]["state"] == "fired" and eng.list_for(2)[0]["fired_value"] == 15.0)
check("event logged with message", "BFLY 23650" in eng.events_for(2)[0]["message"], eng.events_for(2))
check("email sent to the right user", sent and sent[-1][0] == "two@x.com" and "BFLY 23650" in sent[-1][2][0], sent)
f = eng.evaluate(snap(spot=23650, straddle=70, bfly_atm=16))
check("fired rule does not fire again", f == [])
sent.clear()
f = eng.evaluate(snap(spot=23800, straddle=60))
check("two rules for one user fire together", len(f) == 2)
check("...coalesced into ONE email", len(sent) == 1 and sent[0][0] == "one@x.com" and len(sent[0][2]) == 2, sent)
check("subject names the count", "2 alerts" in sent[0][1], sent[0][1])
eng.evaluate(snap(spot=23600, straddle=70))      # last tick satisfies nothing
check("rearm works (nothing true right now)", eng.rearm(1, a1["id"]) and eng.list_for(1)[0]["state"] == "armed")
check("cannot rearm another user's rule", eng.rearm(2, a1["id"]) is False)
check("cannot delete another user's rule", eng.delete(2, a1["id"]) is False and len(eng.list_for(1)) == 2)
check("delete own rule", eng.delete(1, a1["id"]) and len(eng.list_for(1)) == 1)

print("\n=== quiet market: rules are checked at creation and re-arm ===")
eng3 = AL.AlertEngine(pathlib.Path(tempfile.mkdtemp()) / "c.db", send_email=lambda *a: None, user_email=lambda u: "q@x.com")
check("nothing to check before any live snapshot", eng3.create(1, AL.validate({"metric":"spot:NIFTY 50","cmp":">=","value":1})[0])["state"] == "armed")
eng3.on_snapshot(snap(spot=23650))            # last tick arrives...
late = eng3.create(1, AL.validate({"metric":"spot:NIFTY 50","cmp":">=","value":23000})[0])
check("...a rule armed AFTER the last tick fires immediately", late["state"] == "fired" and late["fired_value"] == 23650.0, late)
unmet = eng3.create(1, AL.validate({"metric":"spot:NIFTY 50","cmp":">=","value":99999})[0])
check("...but an unmet rule stays armed", unmet["state"] == "armed")
eng3.rearm(1, late["id"])
check("re-arming a still-true rule fires again at once", eng3.list_for(1)[1]["state"] == "fired")
eng3.on_snapshot(snap(spot=1, live=False))
check("simulator snapshot never becomes the reference", eng3._last_snap["quotes"][0]["price"] == 23650.0)

print("\n=== no-email rule ===")
sent.clear()
eng.evaluate(snap())                               # reference snapshot: spot 23650
a4 = eng.create(1, AL.validate({"metric": "spot:NIFTY 50", "cmp": ">=", "value": 1, "email": False})[0])
check("fires (at creation) but sends no email", a4["state"] == "fired" and sent == [], (a4["state"], sent))

print("\n=== per-user cap ===")
eng2 = AL.AlertEngine(pathlib.Path(tempfile.mkdtemp()) / "b.db")
rule = AL.validate({"metric": "straddle", "cmp": ">=", "value": 1})[0]
made = [eng2.create(9, rule) for _ in range(AL.MAX_PER_USER + 1)]
check(f"{AL.MAX_PER_USER} per user then refused", all(made[:-1]) and made[-1] is None)

print("\n=== stats ===")
st = eng.stats()
check("stats shape", set(st) == {"armed", "fired_total", "evaluations"} and st["fired_total"] >= 4, st)

print("\nRESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
