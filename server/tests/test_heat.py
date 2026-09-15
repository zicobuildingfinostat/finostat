"""HEAT: heatmap rows from the feed universe; panel present."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import heat, pages
fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1
U = {}
for i in range(600):
    sym = f"S{i:03d}"
    U[f"NSE:{sym}"] = {"symbol": sym, "exchange": "NSE", "name": "Stock " + sym, "fo": i < 200, "n50": i < 50, "price": 100 + i, "change": round((i % 21) - 10 + (0.37 if i % 2 else -0.11), 2)}
U["BSE:S001"] = {"symbol": "S001", "exchange": "BSE", "name": "dup", "fo": True, "n50": True, "price": 1, "change": 9.9}
U["NSE:NOPX"] = {"symbol": "NOPX", "exchange": "NSE", "name": "no price", "fo": True, "n50": True, "price": None, "change": 1}
r = heat.rows(U, "n50")
check("n50: only NSE members with prices, sorted desc", r["count"] == 50 and all(x["n50"] for x in r["rows"]) and r["rows"][0]["change"] >= r["rows"][-1]["change"] and all(x["key"].startswith("NSE:") for x in r["rows"]))
check("counts + breadth", r["adv"] + r["dec"] + r["unch"] == 50 and r["avg"] is not None and r["top"]["change"] == max(x["change"] for x in r["rows"]) and r["bottom"]["change"] == min(x["change"] for x in r["rows"]))
f = heat.rows(U, "fo")
check("fo universe", f["count"] == 200 and all(x["fo"] for x in f["rows"]))
a = heat.rows(U, "all", limit=100)
check("all: trimmed to the biggest movers on both ends", a["count"] == 100 and a["adv"] + a["dec"] + a["unch"] == 600 and a["rows"][0]["change"] >= 9 and a["rows"][-1]["change"] <= -9)
g = heat.rows(U, "fo", "gainers"); l = heat.rows(U, "fo", "losers")
check("gainers/losers modes", all(x["change"] > 0 for x in g["rows"]) and all(x["change"] < 0 for x in l["rows"]) and l["rows"][0]["change"] <= l["rows"][-1]["change"])
check("empty universe", heat.rows({}, "fo")["count"] == 0 and heat.rows({}, "fo")["top"] is None and heat.rows(None, "zzz")["u"] == "fo")
doc = pages.render_dashboard({}).decode()
for m in ('id="p-heat"', "/api/heat?u=", "['heat','Market heatmap']", "HEATMAP:'heat'", "heatColor("):
    check("dashboard has " + m, m in doc)
print("fails:", fails)
sys.exit(1 if fails else 0)
