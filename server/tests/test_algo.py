"""Algo engine on fakes: validation, leg building (incl. OI walls), entry at the clock, stop-loss,
target, trailing, exit time, retire vs re-arm, square-off, and the paper book round-trip."""
import sys, pathlib, tempfile, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import algo as AL, book as BK
IST = timezone(timedelta(hours=5, minutes=30))
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

print("=== validate ===")
p = AL.validate({"u": "NIFTY 50", "entry": "09:30", "exit": "15:15", "lots": "2", "sl_pct": "25", "target_pct": "40", "max_vix": "", "trail": 1})
check("defaults merged, numbers coerced, blanks -> None, trail bool", p["lots"] == 2 and p["sl_pct"] == 25.0 and p["max_vix"] is None and p["trail"] is True and p["days"] == "expiry")
for bad in ({"entry": "16:00"}, {"entry": "15:00", "exit": "10:00"}, {"u": "RELIANCE"}, {"lots": "x"}, {"mode": "yolo"}):
    try:
        AL.validate(bad); check(f"rejects {bad}", False)
    except ValueError:
        check(f"rejects {bad}", True)

print("\n=== fakes ===")
EXP = int(datetime(2026, 9, 15, 23, 59, 59, tzinfo=IST).timestamp() * 1000)
class FakeChains:
    def __init__(self): self.px = {}; self.spot = 24000.0; self.walls = (24200, 23800)
    def chain(self, u, expiry=None):
        rows = []
        for k in range(23500, 24550, 50):
            rows.append({"strike": k, "atm": k == 24000, "ce": {"ltp": self.px.get(("CE", k), max(1.0, 120 - abs(k - 24000) * 0.4)), "iv": 12, "change": 0},
                         "pe": {"ltp": self.px.get(("PE", k), max(1.0, 120 - abs(k - 24000) * 0.4)), "iv": 12, "change": 0}})
        return {"underlying": u, "rows": rows, "spot": self.spot, "expiry": EXP, "step": 50, "atm": 24000, "lot": 65, "t_years": 0.01,
                "oi": {"call_wall": self.walls[0], "put_wall": self.walls[1], "pcr": 1.0, "max_pain": 24000}}
class FakeFeed:
    vix = 12.0
    def spot_of(self, k): return self.vix if k == "INDIA VIX" else None
class FakeCI:
    def expiries(self, name): return [EXP]
chains = FakeChains(); feed = FakeFeed()
tmp = pathlib.Path(tempfile.mkdtemp()); store = AL.Store(tmp / "acct.db"); book = BK.Store(tmp / "acct.db")
clock = {"now": datetime(2026, 9, 15, 9, 20, tzinfo=IST)}
routed = []
def router(a, legs, lots, closing): routed.append((closing, [(l["right"], l["strike"], l["qty"]) for l in legs])); return [{"leg": "x", "ok": True}]
eng = AL.Engine(store, chains, book, feed, lambda: FakeCI(), live_router=router, clock=lambda: clock["now"])

print("\n=== legs ===")
ch = chains.chain("NIFTY 50")
check("expiry straddle legs at ATM", AL.build_legs("expiry_straddle", ch, 2) == [{"right": "CE", "strike": 24000, "qty": -1}, {"right": "PE", "strike": 24000, "qty": -1}])
check("wall strangle uses the OI walls", AL.build_legs("wall_strangle", ch, 2) == [{"right": "CE", "strike": 24200, "qty": -1}, {"right": "PE", "strike": 23800, "qty": -1}])
check("iron condor = 4 legs", len(AL.build_legs("iron_condor", ch, 2)) == 4)

print("\n=== entry + stop-loss ===")
aid = store.create(7, "SL test", "expiry_straddle", {"entry": "09:30", "exit": "15:15", "sl_pct": 30, "target_pct": 0, "lots": 1})
check("created armed", store.get(aid)["status"] == "armed")
eng.tick(); a = store.get(aid)
check("before entry time: nothing happens", a["status"] == "armed" and not a["state"].get("entered"))
clock["now"] = datetime(2026, 9, 15, 9, 31, tzinfo=IST); eng.tick(); a = store.get(aid)
pos = book.open_positions(7)
check("entered at 09:31: running, position in the BOOK, credit = CE+PE = 240", a["status"] == "running" and len(pos) == 1 and abs(a["state"]["credit"] - 240.0) < 1e-6 and pos[0]["note"] == "ALGO SL test", (a["status"], a["state"].get("credit"), len(pos)))
chains.px[("CE", 24000)] = 160.0; chains.px[("PE", 24000)] = 160.0          # straddle 240 -> 320: loss 80/unit = 33% of credit > 30%
clock["now"] = datetime(2026, 9, 15, 10, 0, tzinfo=IST); eng.tick(); a = store.get(aid)
check("stop-loss fired at 33% loss: position closed, P&L = -80*65, re-armed (expiry days)", a["status"] == "armed" and not book.open_positions(7) and a["state"]["realized"][0]["reason"] == "stop-loss" and abs(a["state"]["realized"][0]["pnl"] + 80 * 65) < 1e-6, a["state"].get("realized"))
eng.tick(); a = store.get(aid)
check("no re-entry the same day after an exit", a["status"] == "armed" and not book.open_positions(7))

print("\n=== target + once ===")
chains.px.clear()
aid2 = store.create(7, "target once", "expiry_strangle", {"entry": "09:30", "exit": "15:15", "sl_pct": 30, "target_pct": 50, "days": "once", "wings": 2})
eng.tick(); a2 = store.get(aid2)
check("strangle entered at ATM±100 (2 wings × 50)", a2["status"] == "running" and sorted(l["strike"] for l in book.open_positions(7)[0]["legs"]) == [23900, 24100], a2["status"])
credit = a2["state"]["credit"]
for k in (23900, 24100):
    chains.px[("CE", k)] = chains.px[("PE", k)] = credit / 2 * 0.45                # decay to 45%: profit 55% > 50% target
clock["now"] = datetime(2026, 9, 15, 11, 0, tzinfo=IST); eng.tick(); a2 = store.get(aid2)
check("target hit: closed with a profit and retired (once)", a2["status"] == "done" and a2["state"]["realized"][-1]["reason"] == "target" and a2["state"]["realized"][-1]["pnl"] > 0, (a2["status"], a2["state"].get("realized")))

print("\n=== exit time + trailing + square-off + live routing ===")
chains.px.clear()
aid3 = store.create(7, "time exit", "iron_fly", {"entry": "09:30", "exit": "13:00", "sl_pct": 30, "target_pct": 0, "days": "daily"})
eng.tick(); a3 = store.get(aid3)
check("iron fly entered (4 legs)", a3["status"] == "running" and len(book.open_positions(7)[0]["legs"]) == 4)
clock["now"] = datetime(2026, 9, 15, 13, 0, tzinfo=IST); eng.tick(); a3 = store.get(aid3)
check("exit time: closed and re-armed (daily)", a3["status"] == "armed" and a3["state"]["realized"][-1]["reason"] == "exit time" and not book.open_positions(7))
aid4 = store.create(7, "trail", "daily_straddle", {"entry": "09:30", "exit": "15:15", "sl_pct": 20, "target_pct": 0, "trail": True, "days": "daily", "mode": "paper"})
clock["now"] = datetime(2026, 9, 16, 9, 35, tzinfo=IST); eng.tick(); a4 = store.get(aid4)
c4 = a4["state"]["credit"]
chains.px[("CE", 24000)] = chains.px[("PE", 24000)] = c4 / 2 * 0.6      # profit 40% of credit -> max_pnl set
clock["now"] = datetime(2026, 9, 16, 10, 0, tzinfo=IST); eng.tick()
chains.px[("CE", 24000)] = chains.px[("PE", 24000)] = c4 / 2 * 0.85     # gives back 25% (> 20% trail distance) while still in profit
clock["now"] = datetime(2026, 9, 16, 10, 5, tzinfo=IST); eng.tick(); a4 = store.get(aid4)
check("trailing stop: exited in profit after giving back more than the stop distance", a4["state"]["realized"][-1]["reason"] == "trailing stop" and a4["state"]["realized"][-1]["pnl"] > 0, a4["state"].get("realized"))
chains.px.clear()
aid5 = store.create(7, "manual", "daily_straddle", {"entry": "09:30", "exit": "15:15", "days": "daily", "mode": "live"})
clock["now"] = datetime(2026, 9, 17, 9, 40, tzinfo=IST); eng.tick(); a5 = store.get(aid5)
check("live mode: entry orders routed (buys none, 2 sells)", a5["status"] == "running" and routed and routed[-1][0] is False and all(q == -1 for _, _, q in routed[-1][1]), routed)
r = eng.square_off(a5); a5 = store.get(aid5)
check("square-off closes that position, routes reversing orders (+1), re-arms", r["ok"] and a5["status"] == "armed" and routed[-1][0] is True and all(q == 1 for _, _, q in routed[-1][1]) and all(x["note"] != "ALGO manual" for x in book.open_positions(7)))
v = eng.view(a5)
check("view payload has label, runs, realised total, trimmed log", v["label"] == "Daily short straddle" and v["runs"] == 1 and "realized_total" in v and len(v["log"]) <= 12)
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
