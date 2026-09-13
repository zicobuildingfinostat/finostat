"""Global/Crypto terminal: Deribit chain normalisation, CoinDCX signing, the /global page and its paywall."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import crypto, coindcx, pages_global, builder, analytics

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

# -- instrument parsing --------------------------------------------------------
p = crypto.parse_instrument("BTC-27MAR26-80000-C")
check("parse instrument", p and p[0] == "BTC" and p[2] == 80000 and p[3] == "CE")
check("parse put", crypto.parse_instrument("ETH-3OCT26-4000-P")[3] == "PE")
check("parse junk", crypto.parse_instrument("BTC-PERPETUAL") is None)

# -- chain from a synthetic Deribit summary ------------------------------------
now = time.time()
exp = crypto.parse_instrument("BTC-27MAR27-80000-C")[1]
exp2 = crypto.parse_instrument("BTC-25JUN27-80000-C")[1]
def summ(strike, right, exp_name, mark, iv, oi):
    return {"instrument_name": f"BTC-{exp_name}-{strike}-{right}", "mark_price": mark, "mark_iv": iv, "open_interest": oi, "volume": 1.0, "bid_price": mark * 0.98, "ask_price": mark * 1.02}
rows = []
for k in range(60000, 101000, 2000):
    rows.append(summ(k, "C", "27MAR27", max(0.001, (80000 - k) / 80000 + 0.05), 55 + abs(k - 80000) / 4000, 100 + (k % 7)))
    rows.append(summ(k, "P", "27MAR27", max(0.001, (k - 80000) / 80000 + 0.05), 55 + abs(k - 80000) / 4000, 90 + (k % 5)))
    rows.append(summ(k, "C", "25JUN27", 0.06, 60, 10))
    rows.append(summ(k, "P", "25JUN27", 0.06, 60, 10))
rows.append(summ(80000, "C", "1JAN20", 0.01, 50, 5))   # expired: must be dropped
ch = crypto.build_chain("BTC", rows, 80100.0, now=now)
check("chain expiries sorted, expired dropped", ch["expiries"] == [exp, exp2], ch.get("expiries"))
check("chain atm 80000", ch["atm"] == 80000 and ch["step"] == 2000)
check("chain window ±15", 1 < len(ch["rows"]) <= 31)
atm = [r for r in ch["rows"] if r["atm"]][0]
check("price in USD = mark × index", abs(atm["ce"]["ltp"] - 0.05 * 80100) < 1)
check("greeks present incl. third order", atm["ce"]["delta"] and atm["ce"]["gamma"] and "vanna" in atm["ce"] and "ultima" in atm["ce"])
check("oi summary", ch["oi"] and ch["oi"]["pcr"] and ch["oi"]["max_pain"])
check("explicit expiry", crypto.build_chain("BTC", rows, 80100.0, exp2, now=now)["expiry"] == exp2)
check("no live expiry -> error", "error" in crypto.build_chain("ETH", rows, 3000.0, now=now))

# analytics run on crypto rows
sm = analytics.smile(ch["rows"], ch["spot"], ch["t_years"])
check("smile on crypto chain", sm and sm.get("points"))
gx = analytics.gex(ch["rows"], ch["spot"], 1, ch["t_years"], divisor=1e6)
check("gex $M divisor", gx and gx["strikes"] and abs(gx["total"]) > 0)
metrics = builder.evaluate(ch["spot"], [{"right": "CE", "strike": 80000, "qty": -1, "price": atm["ce"]["ltp"]}, {"right": "PE", "strike": 80000, "qty": -1, "price": atm["pe"]["ltp"]}],
                           0.5, ch["t_years"], {("CE", 80000): 0.55, ("PE", 80000): 0.55}, r=0.0)
check("short straddle credit, half size", metrics["net_premium_lot"] > 0 and abs(metrics["net_premium_lot"] - metrics["net_premium"] * 0.5) < 0.01 and metrics["max_loss"] is None)

# -- CoinDCX signing ----------------------------------------------------------
raw, sig = coindcx.sign("s3cr3t", {"timestamp": 1700000000000})
check("hmac sha256 hex", len(sig) == 64 and raw == b'{"timestamp":1700000000000}')
check("valid pair", coindcx.valid_pair("a" * 40, "b" * 40) and not coindcx.valid_pair("short", "b" * 40) and not coindcx.valid_pair("a b" * 20, "b" * 40))

# -- page ----------------------------------------------------------------------
doc = pages_global.render().decode()
for marker in ("s3.tradingview.com/tv.js", "/api/global/chain", "/api/global/strategy", "/api/global/surface?u=", "/api/coindcx/connect", 'data-p="short-straddle"', 'data-p="long-straddle"',
               'id="p-surf"', 'id="p-gex"', 'id="p-coindcx"', 'data-u="BTC"', "$ million of dealer gamma", "href=\"/dashboard\"", 'class="home-ic" href="/"'):
    check("page has " + marker, marker in doc)
check("no NIFTY seg left in analytics", 'data-u="NIFTY 50"' not in doc)
check("no replay/backtest panels", 'id="p-rply"' not in doc and 'id="p-bkts"' not in doc)
check("unlocked has no paywall", "paywall" not in doc and "FINO_LOCKED=true" not in doc)
locked = pages_global.render(locked=True, signed_in=False).decode()
check("locked has paywall + guard", "FINO_LOCKED=true" in locked and 'class="paywall"' in locked and "GLOBAL · CRYPTO TERMINAL" in locked and "/account?plan=desk" in locked)
lapsed = pages_global.render(locked=True, signed_in=True, plan="starter").decode()
check("starter copy", "Your account is on Starter" in lapsed)

# -- GOLD signal ----------------------------------------------------------------
import gold, random
random.seed(7)
px, cs = 2000.0, []
t0 = 1700000000000
for i in range(600):
    drift = 0.004 if (i // 120) % 2 == 0 else -0.003
    px *= 1 + drift + random.gauss(0, 0.01)
    o = px * (1 + random.gauss(0, 0.003)); h = max(o, px) * (1 + abs(random.gauss(0, 0.004))); l = min(o, px) * (1 - abs(random.gauss(0, 0.004)))
    cs.append([t0 + i * 86400000, o, h, l, px, 100 + random.random() * 50])
gd = gold.analyze(cs, "1d")
check("gold analyze keys", all(k in gd for k in ("signal", "score", "classic_score", "pa_score", "confluence", "systems", "markers", "series", "pa", "stats")))
check("gold 15 systems in two groups", len(gd["systems"]) == 15 and {x["group"] for x in gd["systems"]} == {"classic", "price action"})
check("gold signal word matches state", (gd["direction"] == 0) == (gd["signal"] == "NEUTRAL"))
check("gold levels when directional", gd["direction"] == 0 or (gd["stop"] and gd["target"] and (gd["target"] - gd["entry"]) * gd["direction"] > 0 and (gd["entry"] - gd["stop"]) * gd["direction"] > 0))
check("gold markers alternate sensibly", all(m["side"] in ("BUY", "SELL", "EXIT") for m in gd["markers"]) and len(gd["markers"]) > 3)
check("gold structure events + zones found", gd["pa"]["events"] and (gd["pa"]["fvgs"] or gd["pa"]["obs"]))
gd2 = gold.analyze(cs[:-20], "1d")
check("gold does not repaint", gd["series"]["state"][:580] == gd2["series"]["state"] and gd["series"]["score"][:580] == gd2["series"]["score"])
check("gold ema/rsi sanity", abs(gold.ema([1.0] * 30, 10)[-1] - 1.0) < 1e-9 and gold.rsi([float(i) for i in range(40)])[-1] == 100.0)
st_line, st_dir = gold.supertrend(cs)
check("gold supertrend line on the right side", all((d == 1 and ln < c[4]) or (d == -1 and ln > c[4]) or d is None for ln, d, c in zip(st_line[-50:], st_dir[-50:], cs[-50:])))
check("gold label thresholds", gold.label(0.6) == "STRONG BUY" and gold.label(0.3) == "BUY" and gold.label(0.0) == "NEUTRAL" and gold.label(-0.3) == "SELL" and gold.label(-0.7, -1) == "STRONG SELL" and gold.label(0.4, 0) == "NEUTRAL")
gdoc = pages_global.render().decode()
for marker in ('id="p-gold"', "/api/global/gold?tf=", 'data-l="zones"', 'data-tf="4h"', "composite score", "Raschke"):
    check("gold page has " + marker, marker in gdoc)

print("fails:", fails)
sys.exit(1 if fails else 0)
