import os, sys, tempfile, pathlib, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import indices as I
ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}")); ok = ok and cond
sample = "Company Name,Industry,Symbol,Series,ISIN Code\n" + "\n".join(f"Co {i},Ind,SYM{i},EQ,INE{i:09d}" for i in range(50))
check("parses Symbol column", I.parse_csv(sample) == [f"SYM{i}" for i in range(50)])
check("BOM tolerated", I.parse_csv("﻿" + sample)[0] == "SYM0")
try: I.parse_csv("a,b\n1,2\n"); bad = False
except ValueError: bad = True
check("non-constituents file rejected", bad)
try: I.parse_csv("Company Name,Symbol\nX,ONLYONE\n"); bad = False
except ValueError: bad = True
check("too-short list rejected", bad)
tmp = pathlib.Path(tempfile.mkdtemp())
c = I.Constituents("NIFTY50", cache_dir=tmp)
check("fallback in effect with no cache", c.source == "fallback" and 45 <= len(c.members()) <= 55, c.stats())
check("fallback has the obvious names", {"RELIANCE","TCS","HDFCBANK","INFY"} <= c.members())
(tmp / "nifty50.json").write_text(json.dumps({"symbols": [f"C{i}" for i in range(50)], "fetched": 1.0}))
c2 = I.Constituents("NIFTY50", cache_dir=tmp)
check("cache preferred over fallback", c2.source == "cache" and "C0" in c2.members(), c2.stats())
(tmp / "nifty50.json").write_text("{bad json")
c3 = I.Constituents("NIFTY50", cache_dir=tmp)
check("corrupt cache ignored -> fallback", c3.source == "fallback")
print("\nRESULT:", "ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
