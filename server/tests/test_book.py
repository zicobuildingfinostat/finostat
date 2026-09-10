"""The book: storage, marking, Greeks, attribution, scenarios, broker mapping."""
import sys, pathlib, tempfile, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import book as B, contracts as C, bs
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

def chain(spot=23650.0, t=7/365, shift=0.0):
    rows = []
    for k in range(23400, 23901, 50):
        r = {"strike": k, "atm": k == 23650}
        for right in ("CE", "PE"):
            iv = 0.12
            px = bs.price(spot, k, t, iv, right); g = bs.greeks(spot, k, t, iv, right)
            r[right.lower()] = {"ltp": round(px, 2), "iv": 12.0, "change": shift, "delta": round(g["delta"], 4), "gamma": round(g["gamma"], 6), "theta": round(g["theta"], 3), "vega": round(g["vega"], 3)}
        rows.append(r)
    return {"rows": rows, "spot": spot, "t_years": t, "lot": 65, "expiry": 1789000000000, "step": 50, "atm": 23650}

print("=== store ===")
tmp = pathlib.Path(tempfile.mkdtemp()); st = B.Store(tmp / "acct.db")
pid = st.open(1, "NIFTY 50", 1789000000000, [{"right": "CE", "strike": 23650, "qty": -1}, {"right": "PE", "strike": 23650, "qty": -1}], 2, [150.0, 110.0], 65, "short straddle")
check("opened", pid == 1 and st.open_positions(1)[0]["legs"][0]["qty"] == -1 and st.open_positions(1)[0]["lots"] == 2)
check("other user sees nothing", st.open_positions(2) == [])
check("close records exits and moves to history", st.close(1, pid, [120.0, 130.0]) and st.open_positions(1) == [] and st.closed_positions(1)[0]["exits"] == [120.0, 130.0])
check("close twice -> False", not st.close(1, pid, [1, 1]))
pid2 = st.open(1, "NIFTY 50", 1789000000000, [{"right": "CE", "strike": 23700, "qty": 1}], 1, [80.0], 65)
check("delete", st.delete(1, pid2) and not st.delete(1, pid2))

print("\n=== marking ===")
c0 = chain()
ce0, pe0 = B._side(c0, 23650, "CE")["ltp"], B._side(c0, 23650, "PE")["ltp"]
pos = {"id": 9, "u": "NIFTY 50", "expiry": 1789000000000, "legs": [{"right": "CE", "strike": 23650, "qty": -1}, {"right": "PE", "strike": 23650, "qty": -1}], "lots": 2, "entries": [ce0 + 10, pe0 + 10], "lot": 65}
m = B.mark(pos, c0)
check("short straddle marked: pnl = +10 x 2 legs x 2 lots x 65", abs(m["pnl"] - 10 * 2 * 2 * 65) < 0.01 and m["priced"], m["pnl"])
check("net delta ~0 for an ATM straddle, theta positive for the seller", abs(m["greeks"]["delta"]) < 15 and m["greeks"]["theta"] > 0, m["greeks"])
check("label", m["label"] == "−1 23650 CE · −1 23650 PE")
m2 = B.mark(pos, {})
check("no chain -> unpriced, no crash", not m2["priced"] and m2["pnl"] == 0.0)
c1 = chain(spot=23850.0)
m3 = B.mark(pos, c1)
check("rally hurts the short straddle", m3["pnl"] < m["pnl"])

print("\n=== totals + attribution ===")
mk = [B.mark(pos, chain(spot=23700.0, shift=2.0))]     # options up 2% on the day
t = B.totals(mk, [{"symbol": "NIFTY 50", "price": 23700.0, "change": 0.21}])
check("totals carry pnl, day pnl, greeks, attribution that sums", t["open"] == 1 and abs(t["attribution"]["delta"] + t["attribution"]["theta"] + t["attribution"]["other"] - t["day_pnl"]) < 1.5, t)
check("unpriced counted", B.totals([B.mark(pos, {})], [])["unpriced"] == 1)

print("\n=== scenarios ===")
sc = B.scenarios([B.mark(pos, c0)])
check("grid shape 3 iv x 7 spot for today and tomorrow", set(sc["grid"]) == {"0", "1"} and len(sc["grid"]["0"]) == 3 and len(sc["grid"]["0"][0]) == 7)
zero = sc["grid"]["0"][1][3]
check("no shift today ~ 0", abs(zero) < 1, zero)
check("short straddle loses on big moves either way", sc["grid"]["0"][1][0] < 0 and sc["grid"]["0"][1][6] < 0)
check("tomorrow with no move gains theta", sc["grid"]["1"][1][3] > 0)
check("higher IV hurts the seller", sc["grid"]["0"][2][3] < sc["grid"]["0"][0][3])
check("empty book -> zero grid", B.scenarios([])["grid"]["0"][1][3] == 0)

print("\n=== broker positions ===")
ci = C.ContractIndex()
ci.build({"NSE": [{"segment": "NSE_FO", "instrument_type": "CE", "underlying_symbol": "NIFTY", "expiry": 1789000000000, "strike_price": 23650, "instrument_key": "NSE_FO|1", "lot_size": 65},
                  {"segment": "NSE_FO", "instrument_type": "PE", "underlying_symbol": "NIFTY", "expiry": 1789000000000, "strike_price": 23650, "instrument_key": "NSE_FO|2", "lot_size": 65},
                  {"segment": "NSE_FO", "instrument_type": "CE", "underlying_symbol": "RELIANCE", "name": "RELIANCE INDUSTRIES", "expiry": 1789000000000, "strike_price": 1300, "instrument_key": "NSE_FO|3", "lot_size": 500}]})
check("lookup by key", ci.lookup("NSE_FO|1") == ("NIFTY", 1789000000000, 23650, "CE", 65) and ci.lookup("nope") is None)
bp = B.broker_positions([{"key": "NSE_FO|1", "qty": -130, "avg": 150.0}, {"key": "NSE_FO|2", "qty": -130, "avg": 110.0}, {"key": "NSE_FO|3", "qty": 500, "avg": 20.0}, {"key": "NSE_FO|zzz", "qty": 1}], ci)
check("grouped per underlying+expiry, qty in lots, index name mapped", len(bp) == 2 and bp[0]["u"] == "NIFTY 50" and [l["qty"] for l in bp[0]["legs"]] == [-2, -2] and bp[1]["u"] == "NSE:RELIANCE" and bp[1]["legs"][0]["qty"] == 1 and bp[0]["source"] == "upstox")
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
