import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bs
ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}")); ok = ok and cond
S, K, t, v = 23650.0, 23650.0, 7/365, 0.12
c = bs.price(S, K, t, v, "CE"); p = bs.price(S, K, t, v, "PE")
check("put-call parity", abs((c - p) - (S - K * math.exp(-bs.RISK_FREE * t))) < 1e-6, (c, p))
c0 = bs.price(S, K, t, v, "CE", r=0.0)   # the 0.4*S*vol*sqrt(t) rule of thumb assumes zero rates
check("ATM call ~ 0.4*S*vol*sqrt(t) at r=0", abs(c0 - 0.4 * S * v * math.sqrt(t)) / c0 < 0.02, c0)
check("positive rate lifts the call above the r=0 price", c > c0)
iv = bs.implied_vol(c, S, K, t, "CE")
check("implied vol recovers input", iv and abs(iv - v) < 1e-4, iv)
iv2 = bs.implied_vol(bs.price(S, 24000, t, 0.18, "PE"), S, 24000, t, "PE")
check("IV recovers for OTM-ish put", iv2 and abs(iv2 - 0.18) < 1e-4, iv2)
check("price below intrinsic -> None", bs.implied_vol(10.0, S, 23000, t, "CE") is None)
check("zero price -> None", bs.implied_vol(0.0, S, K, t, "CE") is None)
g = bs.greeks(S, K, t, v, "CE"); gp = bs.greeks(S, K, t, v, "PE")
check("ATM call delta ~0.5", 0.45 < g["delta"] < 0.6, g["delta"])
check("call delta - put delta = 1", abs(g["delta"] - gp["delta"] - 1.0) < 1e-9)
check("gamma equal for call and put, positive", abs(g["gamma"] - gp["gamma"]) < 1e-12 and g["gamma"] > 0)
check("theta negative for long options", g["theta"] < 0 and gp["theta"] < 0, (g["theta"], gp["theta"]))
check("vega positive and equal", g["vega"] > 0 and abs(g["vega"] - gp["vega"]) < 1e-9)
# finite-difference delta check
h = 1.0
fd = (bs.price(S + h, K, t, v, "CE") - bs.price(S - h, K, t, v, "CE")) / (2 * h)
check("delta matches finite difference", abs(fd - g["delta"]) < 1e-4, (fd, g["delta"]))
check("expired: intrinsic only", bs.price(S, 23000, 0, v, "CE") == 650.0 and bs.greeks(S, 23000, 0, v, "CE")["delta"] == 1.0)
stamp = 1788892199000                                    # 2026-09-08 23:59:59 IST
at_1530 = stamp/1000 - 8.5*3600                          # 15:30 IST that day
check("years_to is zero at 15:30 IST on expiry day", bs.years_to(stamp, at_1530) == 0.0)
check("one day before the close = 1/365", abs(bs.years_to(stamp, at_1530 - 86400) * 365 - 1.0) < 1e-9)
check("after the close stays zero, never negative", bs.years_to(stamp, at_1530 + 3600) == 0.0)
print("\nRESULT:", "ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
