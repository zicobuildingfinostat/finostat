import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import builder as B
ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}")); ok = ok and cond
atm, step = 23650, 50
strikes = list(range(23450, 23851, 50))
prices = {("CE", k): max(0.5, 46.4 - (k - atm) * 0.6 + (k - atm) ** 2 * 0.0002) for k in strikes}
prices.update({("PE", k): max(0.5, 29.0 + (k - atm) * 0.55 + (k - atm) ** 2 * 0.0002) for k in strikes})
def priced(legs):
    return [dict(l, price=round(prices[(l["right"], l["strike"])], 1)) for l in legs]
print("=== presets ===")
check("all presets instantiate on the ladder", all(B.preset_legs(n, atm, step, strikes) for n in B.PRESETS), [n for n in B.PRESETS if not B.preset_legs(n, atm, step, strikes)])
check("missing strike -> None", B.preset_legs("iron-condor", atm, step, [atm]) is None)
check("unknown preset -> None", B.preset_legs("nope", atm, step, strikes) is None)
print("\n=== bull call spread (defined) ===")
legs = priced(B.preset_legs("bull-call-spread", atm, step, strikes)); r = B.evaluate(23650.0, legs, lot=65)
debit = legs[0]["price"] - legs[1]["price"]
check("net premium is a debit", abs(r["net_premium"] + debit) < 1e-6, (r["net_premium"], debit))
check("max loss = debit", abs(r["max_loss"] + debit) < 0.05, (r["max_loss"], debit))
check("max profit = width - debit", abs(r["max_profit"] - (100 - debit)) < 0.05, (r["max_profit"], 100 - debit))
check("one breakeven exactly at long strike + debit", len(r["breakevens"]) == 1 and abs(r["breakevens"][0] - (atm + debit)) < 0.15, (r["breakevens"], atm + debit))
check("per-lot scales by 65", abs(r["max_loss_lot"] - r["max_loss"] * 65) < 0.01)
print("\n=== short straddle (unbounded loss) ===")
legs = priced(B.preset_legs("short-straddle", atm, step, strikes)); r = B.evaluate(23650.0, legs)
cr = legs[0]["price"] + legs[1]["price"]
check("credit received", abs(r["net_premium"] - cr) < 1e-6, r["net_premium"])
check("max profit = credit, exactly at the strike", abs(r["max_profit"] - cr) < 1e-6, (r["max_profit"], cr))
check("max loss unbounded", r["max_loss"] is None)
check("two breakevens exactly at atm ± credit", len(r["breakevens"]) == 2 and abs(r["breakevens"][0] - (atm - cr)) < 0.15 and abs(r["breakevens"][1] - (atm + cr)) < 0.15, r["breakevens"])
print("\n=== iron condor (defined both sides) ===")
legs = priced(B.preset_legs("iron-condor", atm, step, strikes)); r = B.evaluate(23650.0, legs)
check("bounded profit and loss", r["max_profit"] is not None and r["max_loss"] is not None)
check("max loss = width - credit, exactly", abs(r["max_loss"] + (100 - r["net_premium"])) < 1e-6, (r["max_loss"], r["net_premium"]))
print("\n=== ratio 1x2 (naked upside) ===")
legs = priced(B.preset_legs("ratio-spread", atm, step, strikes)); r = B.evaluate(23650.0, legs)
check("unbounded loss above", r["max_loss"] is None and r["max_profit"] is not None)
print("\n=== long straddle (unbounded profit) ===")
r = B.evaluate(23650.0, priced(B.preset_legs("long-straddle", atm, step, strikes)))
check("unbounded profit, bounded loss", r["max_profit"] is None and r["max_loss"] is not None)
print("\n=== greeks + curve ===")
ivs = {(rt, k): 0.12 for k in strikes for rt in ("CE", "PE")}
r = B.evaluate(23650.0, priced(B.preset_legs("short-straddle", atm, step, strikes)), lot=65, t_years=5/365, ivs=ivs)
check("greeks aggregated per lot", "greeks" in r and r["greeks"]["theta"] > 0 and r["greeks"]["gamma"] < 0, r.get("greeks"))
check("payoff curve has points spanning the range", len(r["payoff"]) == 81 and r["payoff"][0][0] < atm < r["payoff"][-1][0])
check("no legs -> error", B.evaluate(1.0, []) == {"error": "no legs"})
print("\nRESULT:", "ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
