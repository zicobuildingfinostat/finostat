"""Public option chain: NSE v3 payload normalisation, PCR/max pain/walls, page render."""
import sys, pathlib, tempfile, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pubchain as PC
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

def side(oi, chg, vol, iv, ltp): return {"openInterest": oi, "changeinOpenInterest": chg, "totalTradedVolume": vol, "impliedVolatility": iv, "lastPrice": ltp, "change": 1.5, "pChange": 2.0, "buyPrice1": ltp - 0.5, "sellPrice1": ltp + 0.5}
data = []
for k in range(23000, 24050, 50):
    data.append({"strikePrice": k, "expiryDates": "15-Sep-2026", "CE": side(100000 + (300000 if k == 23600 else 0), 5000, 1000, 12.5, max(0.5, 23477 - k + 60)), "PE": side(90000 + (250000 if k == 23300 else 0), -2000, 900, 13.0, max(0.5, k - 23477 + 55))})
payload = {"records": {"data": data, "underlyingValue": 23477.8, "timestamp": "11-Sep-2026 15:30:00"}}
print("=== normalize + stats ===")
n = PC.normalize(payload)
check("rows sorted, spot and timestamp taken, sides typed", len(n["rows"]) == 21 and n["spot"] == 23477.8 and n["ts"].startswith("11-Sep") and n["rows"][0]["ce"]["oi"] == 100000 and n["rows"][0]["pe"]["iv"] == 13.0)
st = PC.stats(n["rows"], n["spot"])
check("ATM 23500, call wall 23600, put wall 23300, PCR from totals, OI change sums", st["atm"] == 23500 and st["call_wall"] == 23600 and st["put_wall"] == 23300 and st["pcr"] == round((90000 * 21 + 250000) / (100000 * 21 + 300000), 2) and st["chg_ce"] == 5000 * 21 and st["chg_pe"] == -2000 * 21, st)
check("max pain lands between the walls", st["max_pain"] and 23300 <= st["max_pain"] <= 23600, st["max_pain"])
n2 = PC.normalize({"records": {"data": data}})
check("no underlyingValue -> spot inferred where CE and PE prices cross", n2["spot"] and abs(n2["spot"] - 23500) <= 50, n2["spot"])

print("\n=== page ===")
tmp = pathlib.Path(tempfile.mkdtemp())
pc = PC.PublicChains(tmp)
pc.data["nifty"] = {"slug": "nifty", "symbol": "NIFTY", "label": "NIFTY 50", "step": 50, "expiry": "15-Sep-2026", "expiries": ["15-Sep-2026"], "spot": n["spot"], "nse_ts": n["ts"], "fetched": time.time(), "rows": n["rows"], "stats": st}
page = PC.render(pc, "nifty").decode()
check("page: title with PCR and max pain, KPIs, ATM row, walls, schema, canonical, symbol switcher", "NIFTY 50 Option Chain" in page and "max pain" in page and 'class="kp"' in page and "class=atm" in page and 'oi wall' in page and '"Dataset"' in page and "FAQPage" in page and 'href="https://finostat.com/option-chain/nifty"' in page and '/option-chain/banknifty' in page)
check("empty symbol renders a placeholder, unknown slug -> None", "not loaded yet" in PC.render(pc, "banknifty").decode() and PC.render(pc, "nope") is None)
check("cache file written by fetch path is optional; status lists symbols", "nifty" in pc.status())
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
