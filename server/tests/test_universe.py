import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import universe as U
ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}")); ok = ok and cond
uni = {"NSE:RELIANCE": {"symbol":"RELIANCE","name":"RELIANCE INDUSTRIES LTD","exchange":"NSE","fo":True,"price":2905.4,"change":0.3},
       "NSE:RELINFRA": {"symbol":"RELINFRA","name":"RELIANCE INFRASTRUCTU LTD","exchange":"NSE","fo":False,"price":280.1,"change":-1.2},
       "NSE:TCS": {"symbol":"TCS","name":"TATA CONSULTANCY SERV LT","exchange":"NSE","fo":True,"price":3512.7,"change":0.1},
       "NSE:TATASTEEL": {"symbol":"TATASTEEL","name":"TATA STEEL LIMITED","exchange":"NSE","fo":True,"price":152.0,"change":0.0},
       "NSE:TATAINVEST": {"symbol":"TATAINVEST","name":"TATA INVESTMENT CORP LTD","exchange":"NSE","fo":False,"price":6000.0,"change":0.0}}
uni["BSE:RELIANCE"] = {"symbol":"RELIANCE","name":"RELIANCE INDUSTRIES LTD","exchange":"BSE","fo":True,"price":2905.9,"change":0.3}
quotes = [{"symbol":"NIFTY 50","price":23650.0,"change":-0.1},{"symbol":"BANKNIFTY","price":51000.0,"change":0.2}]
r = U.search(uni, quotes, "rel")
check("prefix hits: NSE listing, then its BSE twin, then non-F&O", [x["key"] for x in r][:3] == ["NSE:RELIANCE","BSE:RELIANCE","NSE:RELINFRA"], [x["key"] for x in r])
r = U.search(uni, quotes, "tata")
# symbol-prefix matches outrank name-substring matches; within a tier F&O comes first
check("prefix beats name-substring; F&O first within a tier", [x["key"] for x in r] == ["NSE:TATASTEEL","NSE:TATAINVEST","NSE:TCS"], [x["key"] for x in r])
check("exact symbol outranks prefix", U.search(uni, quotes, "TCS")[0]["key"] == "NSE:TCS")
check("exact BSE symbol still beats an NSE prefix match", U.search(uni, quotes, "RELIANCE")[:2] and [x["key"] for x in U.search(uni, quotes, "RELIANCE")][:2] == ["NSE:RELIANCE","BSE:RELIANCE"])
check("indices searchable, first", U.search(uni, quotes, "nifty")[0]["key"] == "NIFTY 50")
check("empty query -> nothing", U.search(uni, quotes, "  ") == [])
check("limit honoured", len(U.search(uni, quotes, "t", limit=2)) == 2)
check("no match -> empty", U.search(uni, quotes, "zzz") == [])
l = U.lookup(uni, quotes, ["NSE:TCS","NIFTY 50","NSE:NOPE"])
check("lookup stocks + indices, ignores unknown", set(l) == {"NSE:TCS","NIFTY 50"} and l["NSE:TCS"]["price"] == 3512.7, l)
check("lookup caps at 50", len(U.lookup(uni, quotes, ["NSE:TCS"]*60)) == 1)
uni["NSE:TCS"]["n50"] = True; uni["NSE:RELIANCE"]["n50"] = True
g = U.group(uni, "n50")
check("group returns only flagged, symbol order", [x["key"] for x in g] == ["NSE:RELIANCE","NSE:TCS"], [x["key"] for x in g])
uni["NSE:TATACONSUM"] = {"symbol":"TATACONSUM","name":"TATA CONSUMER PRODUCT LTD","exchange":"NSE","fo":True,"n50":True,"price":1100.0,"change":0.2}
uni["NSE:TATASTEEL"]["n50"] = False
r = [x["key"] for x in U.search(uni, quotes, "tata")]
check("n50 nudges ranking within a tier (TATACONSUM over TATASTEEL, both F&O prefix hits)", r[:2] == ["NSE:TATACONSUM","NSE:TATASTEEL"], r)
print("\nRESULT:", "ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
