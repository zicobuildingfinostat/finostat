"""ChainManager against a fake feed and the real contract index."""
import os, sys, gzip, json, pathlib, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import chains as CH, contracts as C, bs
ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}")); ok = ok and cond
SP = pathlib.Path("/private/tmp/claude-501/-Users-gicokarmakar-Desktop-Finostat-Website/45834dbf-9aca-435f-abc7-b95d1af2a80f/scratchpad")
if not (SP / "NSE.json.gz").exists() or not (SP / "BSE.json.gz").exists():
    print("  SKIP  instrument masters not present (download NSE.json.gz/BSE.json.gz from assets.upstox.com to run)")
    print("\nRESULT: ALL PASS (skipped)"); sys.exit(0)
ci = C.ContractIndex(); ci.build({"NSE": json.load(gzip.open(SP/"NSE.json.gz")), "BSE": json.load(gzip.open(SP/"BSE.json.gz"))})

class FakeFeed:
    """Prices every subscribed contract with Black-Scholes so IV round-trips."""
    def __init__(self):
        self.subs = {}; self.unsubs = []; self.vol = 0.12
        self.spots = {"NIFTY 50": 23653.0, "NSE:RELIANCE": 1294.9, "SENSEX": 75577.0}
        self.uni = {"NSE:RELIANCE": {"symbol":"RELIANCE","exchange":"NSE","fo":True,"n50":True,"name":"RELIANCE INDUSTRIES LTD","price":1294.9},
                    "NSE:ZOMATO2": {"symbol":"ZOMATO2","exchange":"NSE","fo":False,"name":"x","price":1.0}}
    def snapshot(self): return {"live": True, "quotes": [{"symbol":"NIFTY 50","price":23653.0},{"symbol":"SENSEX","price":75577.0}], "universe": self.uni}
    def spot_of(self, key):
        for q in self.snapshot()["quotes"]:
            if q["symbol"] == key: return q["price"]
        e = self.uni.get(key); return e["price"] if e else None
    def subscribe_dynamic(self, metas): self.subs.update(metas)
    def unsubscribe_dynamic(self, keys): self.unsubs.extend(keys); [self.subs.pop(k, None) for k in keys]
    def price_of(self, key):
        m = self.subs.get(key)
        if not m: return (None, None)
        spot = self.spot_of(m["underlying"]); t = bs.years_to(m["expiry"], time.time())
        p = bs.price(spot, m["strike"], t, self.vol, m["right"]); return (round(p, 2), round(p * 0.98, 2))

feed = FakeFeed(); cm = CH.ChainManager(feed, ci, half=5, ttl=0.2, max_warm=2)
print("=== underlyings ===")
u = cm.underlyings()
check("indices first, then F&O stocks; non-F&O excluded", [x["key"] for x in u][:4] == ["NIFTY 50","BANKNIFTY","FINNIFTY","SENSEX"] and any(x["key"]=="NSE:RELIANCE" for x in u) and not any(x["key"]=="NSE:ZOMATO2" for x in u), [x["key"] for x in u][:6])
print("\n=== chain ===")
c = cm.chain("NIFTY 50")
check("chain resolves with strikes around spot", "rows" in c and len(c["rows"]) == 11 and c["atm"] == 23650, {k: c.get(k) for k in ("atm","step","lot","error")})
check("contracts subscribed on demand (22)", len(feed.subs) == 22, len(feed.subs))
atm = [r for r in c["rows"] if r["atm"]][0]
check("prices + IV + greeks populated", atm["ce"]["ltp"] > 0 and atm["ce"]["iv"] and atm["ce"]["delta"], atm["ce"])
check("IV round-trips the fake feed's 12%", abs(atm["ce"]["iv"] - 12.0) < 0.05 and abs(atm["pe"]["iv"] - 12.0) < 0.05, (atm["ce"]["iv"], atm["pe"]["iv"]))
check("not warming once priced", c["warming"] is False and c["missing"] == 0)
check("lot size and expiry list present", c["lot"] > 0 and len(c["expiries"]) >= 1 and c["expiry"] == c["expiries"][0])
c2 = cm.chain("NIFTY 50", expiry_ms=c["expiries"][1])
check("explicit later expiry swaps the subscription", c2["expiry"] == c["expiries"][1] and len(feed.subs) == 22 and len(feed.unsubs) == 22)
print("\n=== stocks + limits ===")
r = cm.chain("NSE:RELIANCE")
check("F&O stock chain", r.get("kind") == "stock" and r["lot"] > 0 and r["rows"], {k: r.get(k) for k in ("error","lot","atm","step")})
s2 = cm.chain("SENSEX")
check("max_warm evicts the oldest (NIFTY) when a 3rd chain opens", cm.stats()["warm"] == 2 and "NIFTY 50" not in cm.stats()["underlyings"], cm.stats())
check("unknown underlying -> error", "error" in cm.chain("NSE:NOPE") and "error" in cm.chain("BSE:RELIANCE"))
time.sleep(0.3); n = cm.sweep()
check("idle chains dropped by the sweeper", n == 2 and cm.stats()["warm"] == 0 and feed.subs == {}, (n, cm.stats()))
print("\nRESULT:", "ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
