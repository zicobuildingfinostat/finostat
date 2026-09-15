"""RISK board maths and the OISCAN screener (classification, windows, persistence, read) — no network."""
import os, sys, tempfile, pathlib, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import risk, oiscan, book, bs, pages

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

# ---- a marked book: short straddle on NIFTY (2 lots × 75) and a long call on BANKNIFTY
now = time.time()
exp1 = int((now + 2 * 86400) * 1000)
exp2 = int((now + 9 * 86400) * 1000)
t1, t2 = 2 / 365, 9 / 365
S1, S2 = 23400.0, 51000.0
def leg(right, k, qty, spot, t, iv, lots, lot):
    g = bs.greeks(spot, k, t, iv, right)
    mult = qty * lots * lot
    return {"right": right, "strike": k, "qty": qty, "entry": None, "mark": bs.price(spot, k, t, iv, right), "iv": iv * 100, "pnl": 0.0, "mult": mult, "g": {k2: g[k2] * mult for k2 in ("delta", "gamma", "theta", "vega")}}
def pos(u, exp, spot, t, legs, lots, lot, src="paper"):
    gg = {k: sum(l["g"][k] for l in legs) for k in ("delta", "gamma", "theta", "vega")}
    return {"id": 1, "source": src, "u": u, "expiry": exp, "lots": lots, "lot": lot, "legs": legs, "pnl": 150.0, "day_pnl": -400.0, "priced": True, "spot": spot, "t_years": t, "greeks": gg}
p1 = pos("NIFTY 50", exp1, S1, t1, [leg("CE", 23400, -1, S1, t1, 0.14, 2, 75), leg("PE", 23400, -1, S1, t1, 0.15, 2, 75)], 2, 75)
p2 = pos("BANKNIFTY", exp2, S2, t2, [leg("CE", 51500, 1, S2, t2, 0.18, 1, 30)], 1, 30, "upstox")
quotes = [{"symbol": "NIFTY 50", "price": S1, "change": -0.8}, {"symbol": "BANKNIFTY", "price": S2, "change": 0.4}]
b = risk.board([p1, p2], quotes, funds={"available": 250000, "used": 150000}, limits={"delta_inr_1pct": 1000, "vega": 200})
check("board: totals, ₹ terms, margin", b["positions"] == 2 and b["inr"]["theta"] != 0 and b["margin"]["used_pct"] == 37.5 and b["day_pnl"] == -800)
check("board: short straddle theta positive, vega negative", [u for u in b["underlyings"] if u["u"] == "NIFTY 50"][0]["theta"] > 0 and [u for u in b["underlyings"] if u["u"] == "NIFTY 50"][0]["vega"] < 0)
check("board: breaches for tiny limits", {x["key"] for x in b["breaches"]} >= {"delta_inr_1pct", "vega"})
check("board: no breach with default limits", not risk.board([p1, p2], quotes)["breaches"], risk.board([p1, p2], quotes)["breaches"])
bn = [u for u in b["underlyings"] if u["u"] == "BANKNIFTY"][0]
check("board: hedge for a long call = SELL futures", bn["hedge"] and bn["hedge"]["futures_side"] == "SELL" and bn["hedge"]["atm_option"] == "BUY PE", bn["hedge"])
e1 = [e for e in b["expiries"] if e["u"] == "NIFTY 50"][0]
check("board: expiry payoff of a short straddle capped profit, two breakevens", e1["payoff"]["max_profit"] > 0 and e1["payoff"]["max_loss"] < 0 and len(e1["payoff"]["breakevens"]) == 2 and abs(e1["dte"] - 2) < 0.1)
sh = b["shocks"]
check("board: shock grid shape + worst <= 0", len(sh["grid"]["0"]) == len(risk.IV_SHIFTS) and len(sh["grid"]["0"][0]) == len(risk.SPOT_SHIFTS) and sh["worst"] <= 0 and sh["grid"]["0"][2][4] == 0)
check("limits: cleaning keeps defaults for junk", risk.clean_limits({"vega": "x", "theta": -5, "day_loss": 70000})["vega"] == risk.DEFAULT_LIMITS["vega"] and risk.clean_limits({"day_loss": 70000})["day_loss"] == 70000)
check("board: empty book is fine", risk.board([], quotes)["positions"] == 0 and risk.board([], quotes)["shocks"]["worst"] == 0)

# ---- OISCAN classification
check("classify tags", oiscan.classify(1, 1000, 50000) == "long build-up" and oiscan.classify(-1, 1000, 50000) == "short build-up" and oiscan.classify(1, -1000, 50000) == "short covering" and oiscan.classify(-1, -1000, 50000) == "long unwinding")
check("classify flat / tiny", oiscan.classify(1, 0, 50000) == "flat" and oiscan.classify(1, 100, 50000) is None)

# ---- sampler with a fake REST client
class FakeRest:
    def __init__(self):
        self.spot = 23400.0; self.tick = 0
    def expiries(self, u):
        return ["2020-01-01", "2099-12-31"]
    def option_chain(self, u, expiry):
        rows = []
        for k in range(22800, 24050, 50):
            ce_oi = 100000 + (self.tick * 3000 if k == 23500 else 0) - (self.tick * 2500 if k == 23300 else 0)
            pe_oi = 90000 + (self.tick * 4000 if k == 23300 else 0)
            drift = {23500: -4, 23300: 6}.get(k, 0)                      # 23500 CE written (price down, OI up); 23300 CE covered (price up, OI down)
            ce_px = max(1.0, (self.spot - k) + 300 + self.tick * drift)
            pe_px = max(1.0, (k - self.spot) + 300 - self.tick * 6)         # 23300 PE written: price down, OI up
            rows.append({"strike": k, "ce": {"oi": ce_oi, "prev_oi": 100000, "ltp": ce_px}, "pe": {"oi": pe_oi, "prev_oi": 90000, "ltp": pe_px}})
        return {"spot": self.spot, "rows": rows}
db = pathlib.Path(tempfile.mkdtemp()) / "auth.db"
fr = FakeRest()
S = oiscan.Sampler(fr, db, lambda: True, stock_keys_fn=lambda: [("RELIANCE", "NSE_EQ|X")], step_fn=lambda u: 50)
t0 = now - 20 * 60
for i in range(7):
    fr.tick = i; fr.spot = 23400 - i * 5
    S.sample_index("NIFTY 50", now=t0 + i * 180)
v = S.view("NIFTY 50", "15")
check("view: samples, window ~15 min, spot then", v["samples"] == 7 and 13 <= v["window_actual_min"] <= 16 and v["spot_then"] > v["spot"])
top = {(r["strike"], r["side"]): r["tag"] for r in v["top"]}
check("view: call writing at 23500 (short build-up), put writing at 23300, call covering at 23300", top.get((23500, "CE")) == "short build-up" and top.get((23300, "PE")) == "short build-up" and top.get((23300, "CE")) == "short covering", top)
check("view: read mentions writing", "call writing at 23,500" in v["read"]["text"] and "put writing at 23,300" in v["read"]["text"], v["read"])
check("view: walls + pcr", v["walls"]["call"]["strike"] == 23500 and v["walls"]["put"]["strike"] == 23300 and v["pcr"] and v["pcr_then"])
vd = S.view("NIFTY 50", "day")
check("view day: vs previous close", vd["window"] == "day" and any(r["strike"] == 23500 and r["side"] == "CE" and r["d_oi"] == 18000 for r in vd["rows"]))
S2 = oiscan.Sampler(fr, db, lambda: True, step_fn=lambda u: 50)
check("persistence: today's samples reload after restart", S2.view("NIFTY 50", "60")["samples"] == 7)
check("view: unknown / empty", "error" in S.view("XYZ") and "error" in S.view("SENSEX"))
n = S.sample_stocks(now=now)
sv = S.stocks_view()
check("stocks: sampled with day-basis fields", n == 1 and sv["rows"][0]["sym"] == "RELIANCE" and sv["rows"][0]["pcr"] and "d_oi_pct" in sv["rows"][0])

# ---- dashboard carries the panels
doc = pages.render_dashboard({}).decode()
for m in ('id="p-risk"', 'id="p-oiscan"', "/api/risk", "/api/oiscan?u=", "['risk','Risk board']", "OISCAN:'oiscan'", "rk-limits", "SAVE LIMITS"):
    check("dashboard has " + m, m in doc)
print("fails:", fails)
sys.exit(1 if fails else 0)
