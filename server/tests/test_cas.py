"""Closing auction recorder: window, fixed ATM at 15:15, synthetic, persistence, API payload."""
import sys, pathlib, tempfile, time, os
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import cas as C
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1
T = lambda h, m, s=0, day=10: datetime(2026, 9, day, h, m, s, tzinfo=C.IST)      # 2026-09-10 is a Thursday
print("=== window ===")
check("15:14-15:40 on a weekday", C.in_window(T(15, 14)) and C.in_window(T(15, 30)) and C.in_window(T(15, 40)) and not C.in_window(T(15, 41)) and not C.in_window(T(15, 13)))
check("weekend excluded", not C.in_window(T(15, 30, day=12)))
check("past_ref from 15:15", not C.past_ref(T(15, 14, 59)) and C.past_ref(T(15, 15)))
check("synthetic = atm + ce - pe", C.synthetic(74600, 420.5, 90.0) == 74930.5 and C.synthetic(74600, None, 1) is None)

print("\n=== recorder ===")
class Feed:
    def __init__(self): self.level = {"NIFTY 50": 24500.0, "SENSEX": 74629.5}; self.iep = {}; self.live = True
    def snapshot(self): return {"live": self.live}
    def spot_of(self, u): return self.level.get(u)
    def iep_of(self, u): return self.iep.get(u)
class Chains:
    def __init__(self): self.ce = 420.0; self.pe = 90.0
    def chain(self, u):
        step = 100 if u == "SENSEX" else 50; atm = 74600 if u == "SENSEX" else 24500
        rows = [{"strike": k, "atm": k == atm, "ce": {"ltp": self.ce + (atm - k) * 0.5}, "pe": {"ltp": self.pe + (k - atm) * 0.5}} for k in range(atm - 300, atm + 301, step)]
        return {"rows": rows, "step": step, "expiry": 1789000000000, "lot": 20 if u == "SENSEX" else 65, "atm": atm}
tmp = pathlib.Path(tempfile.mkdtemp())
feed, chains, store = Feed(), Chains(), C.Store(tmp / "acct.db")
rec = C.Recorder(feed, chains, store, underlyings=["NIFTY 50", "SENSEX"])
rec.sample(T(15, 14, 30))
s = rec.today["SENSEX"]
check("before 15:15: sampled but ATM not fixed, no synthetic", s.atm is None and len(s.points) == 1 and s.points[0][2] is None and s.points[0][1] == 74629.5)
rec.sample(T(15, 15, 0))
check("at 15:15: reference + fixed ATM (nearest 100) + expiry + lot", s.ref == 74629.5 and s.atm == 74600 and s.expiry == 1789000000000 and s.lot == 20, (s.ref, s.atm))
check("synthetic from the fixed strike", s.points[-1][2] == C.synthetic(74600, 420.0, 90.0))
feed.level["SENSEX"] = 75800.0; feed.iep["SENSEX"] = 75790.0; chains.ce = 430.0
rec.sample(T(15, 22, 0))
check("IEP preferred over level when the feed has one, flagged", s.points[-1][1] == 75790.0 and s.points[-1][3] == 1 and s.points[-1][2] == C.synthetic(74600, 430.0, 90.0))
check("ATM stays fixed while the index moves", s.atm == 74600)
feed.level["NIFTY 50"] = None; feed.iep.clear(); rec.sample(T(15, 23, 0))
n = rec.today["NIFTY 50"]
check("missing index level still records the synthetic", n.points[-1][1] is None and n.points[-1][2] is not None)
rec.flush()
loaded = store.load("SENSEX", "2026-09-10")
check("persisted and reloaded with points + fixings", loaded and loaded.atm == 74600 and len(loaded.points) == len(s.points) and store.dates() == ["2026-09-10"])
d = rec.get("SENSEX", "2026-09-10")
check("api payload: stats, window, dates, basis", d["stats"]["index"] == 75800.0 and d["stats"]["basis"] == round(75800.0 - d["stats"]["synth"], 2) and d["window"]["ref"] == "15:15" and d["dates"] == ["2026-09-10"] and d["stats"]["iep_ticks"] == 1, d["stats"])
check("unknown date -> empty session, not an error", rec.get("SENSEX", "2026-01-01")["n"] == 0)
d2 = rec.to_dict() if hasattr(rec, "to_dict") else s.to_dict()
check("session dict carries hi/lo", d2["stats"]["index_hi"] == 75800.0 and d2["stats"]["index_lo"] == 74629.5)
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
