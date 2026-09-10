"""Event calendar: results parsing, macro file, expiries, implied move, assembly."""
import sys, pathlib, tempfile, json, time
from datetime import datetime, timedelta
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import events as E, contracts as C
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1
now = datetime.now(E.IST)
def ms(days, hour=23, minute=59): return int((now + timedelta(days=days)).replace(hour=hour, minute=minute, second=59, microsecond=0).timestamp() * 1000)
d = lambda days: (now + timedelta(days=days)).date()

print("=== results parsing ===")
rows = [{"bm_symbol": "TCS", "bm_date": d(3).strftime("%d-%b-%Y"), "bm_purpose": "Financial Results", "bm_desc": "to consider and approve the financial results"},
        {"bm_symbol": "TCS", "bm_date": d(3).strftime("%d-%b-%Y"), "bm_purpose": "Financial Results", "bm_desc": "dup"},
        {"bm_symbol": "VENUSPIPES", "bm_date": d(4).strftime("%d-%b-%Y"), "bm_purpose": "Fund raising", "bm_desc": "fund raising"},
        {"bm_symbol": "INFY", "bm_date": "bad date", "bm_purpose": "Results", "bm_desc": ""},
        {"bm_symbol": "RELIANCE", "bm_date": d(9).strftime("%d-%b-%Y"), "bm_purpose": "Board Meeting Intimation", "bm_desc": "to consider dividend"}]
r = E.parse_bm(rows, {"TCS", "RELIANCE", "INFY"})
check("only F&O names with 'result' purposes, de-duplicated, date parsed", len(r) == 1 and r[0]["u"] == "NSE:TCS" and r[0]["date"] == d(3).isoformat() and r[0]["kind"] == "results", r)

print("\n=== macro file ===")
tmp = pathlib.Path(tempfile.mkdtemp()); mf = tmp / "events.json"
mf.write_text(json.dumps([{"date": d(5).isoformat(), "title": "RBI policy", "u": "BANKNIFTY"}, {"date": "nope", "title": "bad"}]))
m = E.load_macro(mf)
check("macro rows validated", len(m) == 1 and m[0]["kind"] == "macro" and m[0]["u"] == "BANKNIFTY")
check("shipped events.json parses", isinstance(E.load_macro(), list))

print("\n=== calendar assembly + implied move ===")
ci = C.ContractIndex()
ci.build({"NSE": [
    {"segment": "NSE_FO", "instrument_type": t, "underlying_symbol": "NIFTY", "expiry": e, "strike_price": 24500, "instrument_key": f"NSE_FO|n{e}{t}", "lot_size": 65}
    for e in (ms(2), ms(9)) for t in ("CE", "PE")] + [
    {"segment": "NSE_FO", "instrument_type": t, "underlying_symbol": "TCS", "name": "TATA CONSULTANCY", "expiry": ms(20), "strike_price": 3000, "instrument_key": f"NSE_FO|t{t}", "lot_size": 175}
    for t in ("CE", "PE")]})
class Chains:
    calls = []
    def chain(self, u, expiry=None):
        self.calls.append((u, expiry)); spot = 24500.0 if u == "NIFTY 50" else 3000.0
        return {"rows": [{"strike": int(spot), "atm": True, "ce": {"ltp": spot * 0.006}, "pe": {"ltp": spot * 0.005}}], "spot": spot, "atm": int(spot), "t_years": 5 / 365}
ch = Chains()
cal = E.Calendar(lambda: ci, ch, cache=None)
cal.results = E.parse_bm(rows, {"TCS", "RELIANCE"})
out = cal.calendar(days=21)
kinds = [(e["kind"], e["u"], e["date"]) for e in out["events"]]
check("expiries for NIFTY within 21 days, TCS results, stock monthly expiry", ("expiry", "NIFTY 50", d(2).isoformat()) in kinds and ("expiry", "NIFTY 50", d(9).isoformat()) in kinds and ("results", "NSE:TCS", d(3).isoformat()) in kinds and any(k[0] == "expiry" and k[1] == "NSE:TCS" for k in kinds), kinds)
check("sorted by date", [e["date"] for e in out["events"]] == sorted(e["date"] for e in out["events"]))
tcs = next(e for e in out["events"] if e["kind"] == "results")
check("results row priced with the expiry spanning it: straddle 1.1% of spot", tcs.get("move") and tcs["move"]["pct"] == 1.1 and tcs["move"]["expiry"] == ms(20), tcs.get("move"))
n2 = next(e for e in out["events"] if e["kind"] == "expiry" and e["u"] == "NIFTY 50")
check("expiry row priced off its own expiry", n2.get("move") and n2["move"]["expiry"] == ms(2), n2.get("move"))
calls_before = len(ch.calls); cal.calendar(days=21)
check("implied moves cached for a minute (no new chain calls)", len(ch.calls) == calls_before)
check("counts", out["counts"]["results"] == 1 and out["counts"]["expiry"] >= 3)
check("event beyond the horizon excluded", all(e["date"] <= (now + timedelta(days=21)).date().isoformat() for e in out["events"]))
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
