import os, sys, gzip, json, pathlib, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import contracts as C
ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}")); ok = ok and cond
SP = pathlib.Path("/private/tmp/claude-501/-Users-gicokarmakar-Desktop-Finostat-Website/45834dbf-9aca-435f-abc7-b95d1af2a80f/scratchpad")
if not (SP / "NSE.json.gz").exists() or not (SP / "BSE.json.gz").exists():
    print("  SKIP  instrument masters not present (download NSE.json.gz/BSE.json.gz from assets.upstox.com to run)")
    print("\nRESULT: ALL PASS (skipped)"); sys.exit(0)
nse = json.load(gzip.open(SP / "NSE.json.gz")); bse = json.load(gzip.open(SP / "BSE.json.gz"))
ci = C.ContractIndex(); n = ci.build({"NSE": nse, "BSE": bse})
check("index built from real masters", n > 30000, n)
check("NIFTY, RELIANCE and SENSEX present", all(ci.has(x) for x in ("NIFTY", "RELIANCE", "SENSEX")), [x for x in ("NIFTY","RELIANCE","SENSEX") if not ci.has(x)])
check("~200+ F&O stock underlyings", len(ci.names()) > 180, len(ci.names()))
ex = ci.expiries("NIFTY")
check("live NIFTY expiries only (close at stamp-8.5h still ahead), ascending", ex and ex == sorted(ex) and all(e - 8.5*3600*1000 > time.time()*1000 for e in ex), ex[:2])
check("a chain that settled at 15:30 today is NOT offered", ci.expiries("NIFTY", now_ms=(ex[0] - 8.5*3600*1000) + 60_000)[0] != ex[0])
step = ci.step("NIFTY", ex[0]); check("NIFTY step 50", step == 50, step)
lad = ci.ladder("NIFTY", ex[0], 23653.0, half=10)
check("21-strike ladder around spot", 15 <= len(lad) <= 21 and any(r["atm"] for r in lad), len(lad))
atm = [r for r in lad if r["atm"]][0]
check("ATM is the nearest strike (23650)", atm["strike"] == 23650, atm["strike"])
check("keys are NSE_FO instruments with a lot size", atm["ce_key"].startswith("NSE_FO|") and atm["lot"] > 0, atm)
rex = ci.expiries("RELIANCE"); rl = ci.ladder("RELIANCE", rex[0], 1294.9, half=5)
check("RELIANCE monthly chain resolves", rl and rl[0]["lot"] > 0, rl[:1])
check("RELIANCE step sensible", ci.step("RELIANCE", rex[0]) in (5, 10, 20, 25, 50), ci.step("RELIANCE", rex[0]))
sx = ci.expiries("SENSEX"); sl = ci.ladder("SENSEX", sx[0], 75577.0, half=3)
check("SENSEX chain from BSE_FO", sl and sl[0]["ce_key"].startswith("BSE_FO|"), sl[:1])
check("unknown underlying -> empty", ci.ladder("NOPE", 0, 1.0) == [] and ci.expiries("NOPE") == [])
check("expired contracts excluded", all(e - 8.5*3600*1000 > time.time()*1000 for e in ci.expiries("BANKNIFTY")))
print("\nRESULT:", "ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
