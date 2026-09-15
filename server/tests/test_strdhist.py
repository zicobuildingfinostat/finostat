"""IVP: straddle / IV percentile history maths with a fake archive (no network)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date
import strdhist, bs, pages

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

check("trading days: Mon->Tue = 1, Fri->Mon = 1, same day 0", strdhist.trading_days_between(date(2026, 9, 14), date(2026, 9, 15)) == 1 and strdhist.trading_days_between(date(2026, 9, 11), date(2026, 9, 14)) == 1 and strdhist.trading_days_between(date(2026, 9, 15), date(2026, 9, 15)) == 0)
check("trading day before: 2 before Tue 15 = Fri 11", strdhist.trading_day_before(date(2026, 9, 15), 2) == date(2026, 9, 11) and strdhist.trading_day_before(date(2026, 9, 15), 0) == date(2026, 9, 15))
iv = strdhist.straddle_iv(bs.price(23400, 23400, 2 / 365, 0.14, "CE") + bs.price(23400, 23400, 2 / 365, 0.14, "PE"), 23400, 23400, 2 / 365)
check("straddle IV solves back", abs(iv - 14.0) < 0.05, iv)
check("straddle IV below intrinsic -> None", strdhist.straddle_iv(0.01, 23400, 23400, 2 / 365) is None or strdhist.straddle_iv(0.01, 23400, 23400, 2 / 365) < 1)

class FakeHist:
    """Archive with 4 weekly expiries; straddle decays through the day, cheaper in older cycles."""
    def __init__(self):
        self.exps = ["2026-08-18", "2026-08-25", "2026-09-01", "2026-09-08"]
    def days(self, u): return self.exps
    def index_day(self, u, day):
        return [[f"{day}T{h:02d}:{m:02d}:00+05:30", 23400, 23410, 23390, 23400 + (h - 9) * 5, 0] for h in range(9, 16) for m in range(0, 60) if "09:15" <= f"{h:02d}:{m:02d}" <= "15:29"]
    def contracts(self, u, expiry):
        return {"lot": 75, "step": 50, "keys": {f"{r}:{k}": f"X|{expiry}|{r}|{k}" for k in range(23000, 23801, 50) for r in ("CE", "PE")}}
    def candles(self, key, day):
        _, expiry, right, k = key.split("|")
        i = self.exps.index(expiry)
        base = 60 + 8 * i                                              # later cycles richer
        return [[f"{day}T{h:02d}:{m:02d}:00+05:30", 0, 0, 0, max(1.0, base - ((h - 9) * 60 + m) * 0.08), 0] for h in range(9, 16) for m in range(0, 60) if "09:15" <= f"{h:02d}:{m:02d}" <= "15:29"]

H = FakeHist()
s = strdhist.sample_cycle(H, "NIFTY 50", "2026-09-08", 1)
check("cycle: day = 1 trading day before expiry, atm at open, points on the 5-min grid with iv", s["day"] == "2026-09-07" and s["atm"] == 23400 and len(s["points"]) > 60 and s["points"][0][0] == "09:15" and s["points"][0][3] and s["decay_pct"] < 0)
st = strdhist.study(H, "NIFTY 50", 1, 20, date(2026, 9, 15))
check("study: 4 cycles newest first", st["n"] == 4 and st["samples"][0]["expiry"] == "2026-09-08" and st["samples"][-1]["expiry"] == "2026-08-18")
b = strdhist.bands(st["samples"])
check("bands per minute: min <= median <= max", len(b) > 60 and all(x[1] <= x[2] <= x[3] for x in b))
# today: a straddle richer than every cycle at 10:00
today_pts = [["09:15", 200.0, 0.855, 15.0], ["10:00", 190.0, 0.812, 14.5]]
now = strdhist.compare_now(today_pts, st["samples"])
check("compare: percentile 100 when above all cycles, read = rich", now["pct_percentile"] == 100 and now["cycles"] == 4 and "rich" in now["read"] and now["minute"] == "10:00")
cheap = strdhist.compare_now([["10:00", 20.0, 0.085, 3.0]], st["samples"])
check("compare: cheap read", cheap["pct_percentile"] == 0 and "cheap" in cheap["read"])
check("compare: empty today -> {}", strdhist.compare_now([], st["samples"]) == {})
v = strdhist.vix_rank([10 + (i % 7) for i in range(100)] + [17.0])
check("vix rank/percentile", v["rank"] == 100 and v["percentile"] == 100 and v["days"] == 101)
check("vix too short -> None", strdhist.vix_rank([12.0] * 5) is None)
doc = pages.render_dashboard({}).decode()
for m in ('id="p-ivp"', "/api/strdhist?u=", "['ivp','Straddle & IV percentile']", "IVP:'ivp'"):
    check("dashboard has " + m, m in doc)
print("fails:", fails)
sys.exit(1 if fails else 0)
