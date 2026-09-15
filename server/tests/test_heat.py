"""HEAT: heatmap packing (top 20/20 default) for the Indian feed universe, CoinGecko markets and CNBC quotes; panels present."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import heat, pages, pages_global, crypto
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
t = heat.rows(U, "fo")
ups = [r for r in t["rows"] if r["change"] > 0]; downs = [r for r in t["rows"] if r["change"] < 0]
check("default = top 20 gainers + top 20 losers, sorted desc", t["mode"] == "top" and len(ups) == 20 and len(downs) == 20 and t["count"] == 40 and t["rows"][0]["change"] >= t["rows"][-1]["change"])
check("breadth counts cover the whole universe, not just the tiles", t["universe"] == 200 and t["adv"] + t["dec"] + t["unch"] == 200 and t["top"]["change"] == max(x["change"] for x in ups))
check("top 20 are the largest gainers", ups[0]["change"] == max(e["change"] for k, e in U.items() if k.startswith("NSE:") and e["fo"] and e["price"]) and downs[-1]["change"] == min(e["change"] for k, e in U.items() if k.startswith("NSE:") and e["fo"] and e["price"]))
r = heat.rows(U, "n50", "all")
check("n50 all: only NSE members with prices", r["count"] == 50 and all(x["n50"] for x in r["rows"]) and all(x["key"].startswith("NSE:") for x in r["rows"]))
a = heat.rows(U, "all", "all", limit=100)
check("all NSE: trimmed to the biggest movers on both ends", a["count"] == 100 and a["universe"] == 600 and a["rows"][0]["change"] >= 9 and a["rows"][-1]["change"] <= -9)
g = heat.rows(U, "fo", "gainers"); l = heat.rows(U, "fo", "losers")
check("gainers/losers modes", all(x["change"] > 0 for x in g["rows"]) and all(x["change"] < 0 for x in l["rows"]) and l["rows"][0]["change"] <= l["rows"][-1]["change"])
check("empty universe / bad args", heat.rows({}, "fo")["count"] == 0 and heat.rows({}, "fo")["top"] is None and heat.rows(None, "zzz", "zzz")["u"] == "fo" and heat.rows(None, "zzz", "zzz")["mode"] == "top")
# crypto
M = [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "current_price": 76405, "price_change_percentage_24h": -2.585, "market_cap": 1.5e12, "market_cap_rank": 1},
     {"id": "tether", "symbol": "usdt", "name": "Tether", "current_price": 1.0, "price_change_percentage_24h": 0.01, "market_cap": 1.6e11, "market_cap_rank": 3},
     {"id": "wrapped-bitcoin", "symbol": "wbtc", "name": "Wrapped Bitcoin", "current_price": 76400, "price_change_percentage_24h": -2.6, "market_cap": 1e10, "market_cap_rank": 12}]
for i in range(60):
    M.append({"id": f"coin{i}", "symbol": f"c{i}", "name": f"Coin {i}", "current_price": 1 + i, "price_change_percentage_24h": (i % 13) - 6 + 0.1 * i, "market_cap": 1e9 - i, "market_cap_rank": 20 + i})
M.append({"id": "nochange", "symbol": "nc", "name": "No change", "current_price": 1, "price_change_percentage_24h": None, "market_cap": 1, "market_cap_rank": 99})
c = heat.from_markets(M)
allc = heat.from_markets(M, "all")["rows"]
check("crypto: stablecoins + wrapped dropped, None change dropped, top 20/20", c["u"] == "crypto" and c["universe"] == 61 and not any(x["symbol"] in ("USDT", "WBTC", "NC") for x in c["rows"]) and c["count"] == min(20, sum(1 for x in allc if x["change"] > 0)) + min(20, sum(1 for x in allc if x["change"] < 0)) and c["rows"][0]["change"] == max(x["change"] for x in allc))
check("crypto: symbols upper-cased, key = coingecko id", all(x["symbol"] == x["symbol"].upper() for x in c["rows"]) and any(x["key"] == "bitcoin" for x in heat.from_markets(M, "all")["rows"]))
# world
Q = [{"symbol": code, "name": name + " Inc", "last": f"{100 + i:,.2f}", "change_pct": f"{'+' if i % 2 else '-'}{(i % 7) * 0.5:.2f}%", "curmktstatus": "REG_MKT" if i % 3 else "POST_MKT"} for i, (code, name) in enumerate(crypto.WORLD[:50])]
w = heat.from_cnbc(Q, crypto.WORLD)
check("world: parses CNBC strings, drops missing quotes, session flag", w["u"] == "world" and w["universe"] == 50 and w["session"] == "REG_MKT" and all(isinstance(x["price"], float) for x in w["rows"]) and w["rows"][0]["symbol"] == "BRK" or w["rows"][0]["change"] == 3.0)
wc = heat.from_cnbc([dict(q, curmktstatus="POST_MKT") for q in Q], crypto.WORLD)
check("world: closed session detected", wc["session"] == "POST_MKT" and len(crypto.WORLD) >= 100 and len({c for c, _ in crypto.WORLD}) == len(crypto.WORLD))
check("cnbc batches url", "AAPL%7CMSFT" in crypto.cnbc_url(["AAPL", "MSFT"]))
doc = pages.render_dashboard({}).decode()
for m in ('id="p-heat"', "/api/heat?u=", "['heat','Market heatmap']", "HEATMAP:'heat'", 'data-m="top" class="on"'):
    check("dashboard has " + m, m in doc)
gdoc = pages_global.render(False, True, "desk").decode()
for m in ('id="p-cheat"', 'id="p-wheat"', "/api/global/heat?m=crypto", "/api/global/heat?m=world", "function tvGo(", ".ht-map{"):
    check("global page has " + m, m in gdoc)
print("fails:", fails)
sys.exit(1 if fails else 0)
