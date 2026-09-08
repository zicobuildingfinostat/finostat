"""Expiry brief: snapshot maths on a synthetic chain, narrative, scheduler windows, storage, pages."""
import sys, pathlib, tempfile, time, json, re
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import brief as B

fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

# --- a fake feed + chain manager: NIFTY at 23,650, 50-point ladder, realistic-ish premiums
EXPIRY = int((time.time() + 5 * 86400) * 1000)
def fake_chain(u, spot, step, lot, straddle):
    atm = round(spot / step) * step
    rows = []
    for k in range(atm - 10 * step, atm + 11 * step, step):
        d = (k - spot) / step
        ce = max(0.5, straddle / 2 - d * step * 0.5 + abs(d) * 2) if d > 0 else max(0.5, spot - k + straddle / 2 * 0.6)
        pe = max(0.5, straddle / 2 + d * step * 0.5 + abs(d) * 2) if d < 0 else max(0.5, k - spot + straddle / 2 * 0.6)
        iv = 12.0 + (0.6 * abs(d) if d < 0 else 0.2 * abs(d))          # put side steeper -> positive skew
        rows.append({"strike": k, "atm": k == atm,
                     "ce": {"ltp": round(ce, 2), "iv": round(iv, 2), "delta": 0.5, "theta": -8.0, "vega": 10.0, "gamma": 0.001},
                     "pe": {"ltp": round(pe, 2), "iv": round(iv + 1.0, 2), "delta": -0.5, "theta": -7.0, "vega": 10.0, "gamma": 0.001}})
    return {"underlying": u, "name": u, "kind": "index", "spot": spot, "expiry": EXPIRY, "expiries": [EXPIRY], "step": step, "atm": atm,
            "lot": lot, "t_years": 5 / 365, "rows": rows, "warming": False, "missing": 0, "live": True}

class Feed:
    live = True
    def snapshot(self):
        return {"live": self.live, "quotes": [{"symbol": "NIFTY 50", "price": 23650.0, "change": 0.42}, {"symbol": "BANKNIFTY", "price": 51200.0, "change": -0.1},
                                             {"symbol": "SENSEX", "price": 77900.0, "change": 0.3}, {"symbol": "INDIA VIX", "price": 13.4, "change": -2.0}]}
class Chains:
    calls = 0
    def chain(self, u, expiry=None):
        self.calls += 1
        return {"NIFTY 50": fake_chain(u, 23650.0, 50, 65, 240.0), "BANKNIFTY": fake_chain(u, 51200.0, 100, 30, 700.0),
                "SENSEX": fake_chain(u, 77900.0, 100, 20, 800.0)}.get(u, {"error": "no option chain for that underlying"})

print("=== snapshot ===")
feed, chains = Feed(), Chains()
d = B.build(feed, chains, "open", datetime(2026, 9, 9, 9, 20, tzinfo=B.IST), wait=0)
n = d["u"]["NIFTY 50"]
check("three underlyings captured", set(d["u"]) == {"NIFTY 50", "BANKNIFTY", "SENSEX"}, list(d["u"]))
check("date/kind/at stamped", d["date"] == "2026-09-09" and d["kind"] == "open" and d["at"] == "09:20 IST", (d["date"], d["at"]))
check("straddle = ATM ce+pe", abs(n["straddle"] - (n["ce"] + n["pe"])) < 0.01)
check("implied move pct and range", abs(n["move_pct"] - n["straddle"] / n["spot"] * 100) < 0.01 and n["lo"] == round(n["spot"] - n["straddle"]) and n["hi"] == round(n["spot"] + n["straddle"]))
check("skew positive (puts richer)", n["skew"] is not None and n["skew"] > 0, n["skew"])
check("vix + change captured", d["vix"] == 13.4 and d["vix_change"] == -2.0)
check("four strategies priced", [s["preset"] for s in n["strategies"]] == B.PRESETS, [s["preset"] for s in n["strategies"]])
ic = next(s for s in n["strategies"] if s["preset"] == "iron-condor"); ss = next(s for s in n["strategies"] if s["preset"] == "short-strangle")
check("condor credit < strangle credit, condor loss bounded, strangle unlimited", 0 < ic["net_lot"] < ss["net_lot"] and ic["max_loss_lot"] is not None and ss["max_loss_lot"] is None, (ic, ss))
check("breakevens are two numbers each", len(ic["breakevens"]) == 2 and len(ss["breakevens"]) == 2)

print("\n=== narrative ===")
paras = B.narrative(d)
check("narrative has 4-5 paragraphs", 4 <= len(paras) <= 5, len(paras))
check("leads with spot, straddle and range", all(x in paras[0] for x in ("23,650", f"{n['straddle']:,.2f}", f"{n['lo']:,.0f}")), paras[0][:160])
check("reads VIX as ordinary range", "ordinary range" in paras[1], paras[1][:80])
check("compares condor with strangle", "iron condor" in paras[2] and "no ceiling" in paras[2])
check("mentions BANKNIFTY and SENSEX", "BANKNIFTY" in paras[-1] and "SENSEX" in paras[-1])
c = B.build(feed, chains, "close", datetime(2026, 9, 9, 15, 35, tzinfo=B.IST), wait=0)
c["u"]["NIFTY 50"]["spot"] = 23700.0
cp = B.close_narrative(d, c)
check("close narrative: move vs implied", "+50 points" in cp[0] and "stayed inside" in cp[0], cp[0][:160])
c["u"]["NIFTY 50"]["spot"] = 24000.0
check("close narrative: breakout wording", "broke out of" in B.close_narrative(d, c)[0])

print("\n=== scheduler windows (IST) ===")
T = lambda h, m, wd=1: datetime(2026, 9, 7 + wd, h, m, tzinfo=B.IST)   # 2026-09-07 is a Monday
check("09:20 weekday, live, nothing yet -> open", B.due(T(9, 20), False, False, True) == "open")
check("09:20 but feed not live -> nothing", B.due(T(9, 20), False, False, False) is None)
check("09:20 already have open -> nothing", B.due(T(9, 20), True, False, True) is None)
check("09:45 is outside the open window", B.due(T(9, 45), False, False, True) is None)
check("15:35 with open, no close -> close (even if feed is not live)", B.due(T(15, 35), True, False, False) == "close")
check("15:35 without open -> nothing", B.due(T(15, 35), False, False, True) is None)
check("saturday -> nothing", B.due(T(9, 20, wd=5), False, False, True) is None)

print("\n=== storage + pages ===")
tmp = pathlib.Path(tempfile.mkdtemp())
st = B.Briefs(tmp / "acct.db")
st.put("2026-09-09", "open", d); st.put("2026-09-09", "close", c); st.put("2026-09-08", "close", c)
rec = st.get("2026-09-09")
check("open and close stored on one row", rec["open"]["kind"] == "open" and rec["close"]["kind"] == "close")
check("dates newest first", st.dates() == ["2026-09-09", "2026-09-08"])
page = B.render_day(st, "2026-09-09").decode()
check("day page renders both sections + comparison", "At the open" in page and "At the close" in page and "What happened against what was priced" in page)
check("title carries the implied move", re.search(r"<title>NIFTY expected move today ±\d+\.\d+% — expiry brief, Wednesday, 09 September 2026", page) is not None, re.search(r"<title>[^<]*", page).group(0)[:120])
check("Article JSON-LD with the founder as author", '"@type":"Article"' in page and '"name":"Zico Karmakar"' in page)
check("pager links to the earlier brief", 'href="/brief/2026-09-08"' in page)
check("missing date -> None", B.render_day(st, "2026-01-01") is None)
idx = B.render_index(st).decode()
check("index shows latest + archive", "Latest · Wednesday, 09 September 2026" in idx and idx.count('href="/brief/2026-09-0') >= 3)
sm = B.sitemap_entries(st)
check("sitemap entries for /brief and each day", "/brief</loc>" in sm and "/brief/2026-09-09</loc>" in sm and "/brief/2026-09-08</loc>" in sm)
empty = B.Briefs(tmp / "empty.db")
check("empty index renders", "first brief is written on the next trading day" in B.render_index(empty).decode())

print("\n=== scheduler run_now + trigger ===")
sch = B.Scheduler(feed, chains, empty, tmp / "brief.trigger")
out = sch.run_now("open", "2026-09-10")
check("run_now stores under the given date", empty.get("2026-09-10")["open"]["date"] == "2026-09-10" and sch.last["ok"])
feed_dead = Feed(); chains_dead = type("C", (), {"chain": lambda self, u, e=None: {"error": "no option chain for that underlying"}})()
sch2 = B.Scheduler(feed_dead, chains_dead, empty, tmp / "t2")
sch2.run_now("open", "2026-09-11")
check("no chains -> not stored", empty.get("2026-09-11") is None and sch2.last["ok"] is False)

print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
