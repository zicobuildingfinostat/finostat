"""FLOWS: NSE FII/DII JSON and participant-wise OI CSV parsing, storage, derived series."""
import sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import flows as F
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

print("=== parsing ===")
rows = F.parse_fiidii([{"buyValue": "15109.58", "category": "DII", "date": "11-Sep-2026", "netValue": "1968.17", "sellValue": "13141.41"},
                       {"buyValue": "12,616.89", "category": "FII/FPI", "date": "11-Sep-2026", "netValue": "-930.9", "sellValue": "13547.79"}, {"date": "bad"}])
check("fii/dii rows: ISO date, category normalised, commas stripped, bad row dropped", len(rows) == 2 and rows[0]["date"] == "2026-09-11" and rows[1]["category"] == "FII" and rows[1]["buy"] == 12616.89 and rows[1]["net"] == -930.9, rows)
csv_text = '''""Participant wise Open Interest (no. of contracts) in Equity Derivatives as on Sep 11, 2026"",,,,,,,,,,,,,,
Client Type,Future Index Long,Future Index Short,Future Stock Long,Future Stock Short       ,Option Index Call Long,Option Index Put Long,Option Index Call Short,Option Index Put Short,Option Stock Call Long,Option Stock Put Long,Option Stock Call Short,Option Stock Put Short,Total Long Contracts      ,Total Short Contracts
Client,286353,54865,3478897,213571,3847943,3126037,3618281,3879158,2716400,819413,1427016,1225584,14275043,10418475
DII,43743,29395,352254,4643802,5401,56824,3350,0,4876,44620,384382,22696,507718,5083625
FII,41252,326134,3454581,2934979,675792,1331606,962890,660000,10,20,30,40,7000000,4300000
Pro,100,200,300,400,500,600,700,800,900,1000,1100,1200,1300,1400
TOTAL,1,2,3,4,5,6,7,8,9,10,11,12,13,14
'''
day, prows = F.parse_participant(csv_text)
check("participant csv: date parsed, 4 clients, TOTAL skipped, numbers as ints", day == "2026-09-11" and [r["client"] for r in prows] == ["Client", "DII", "FII", "Pro"] and prows[2]["fut_idx_short"] == 326134 and prows[3]["total_short"] == 1400, (day, [r["client"] for r in prows]))

print("\n=== store + derive ===")
tmp = pathlib.Path(tempfile.mkdtemp()); st = F.Store(tmp / "acct.db")
st.put_fiidii(rows); st.put_participants(day, prows)
st.put_fiidii([{"date": "2026-09-10", "category": "FII", "buy": 1, "sell": 2, "net": -1000.0}, {"date": "2026-09-10", "category": "DII", "buy": 1, "sell": 2, "net": 500.0}])
p10 = [dict(r, fut_idx_long=r["fut_idx_long"] - 1000) if r["client"] == "FII" else r for r in prows]
st.put_participants("2026-09-10", p10)
check("has_participants / counts", st.has_participants("2026-09-11") and not st.has_participants("2026-09-09") and st.counts()["participant_days"] == 2 and st.counts()["fiidii_last"] == "2026-09-11")
cash = st.fiidii(30)
check("fiidii series merged per date, ascending", [c["date"] for c in cash] == ["2026-09-10", "2026-09-11"] and cash[1]["fii_net"] == -930.9 and cash[1]["dii_net"] == 1968.17)
d = F.derive(st.participants(30), cash)
fii = d["latest"]["fii"]
check("derived: FII index futures net = long − short, day-on-day change = +1000, calls/puts net", fii["fut_idx_net"] == 41252 - 326134 and fii["fut_idx_net_chg"] == 1000 and fii["call_net"] == 675792 - 962890 and fii["put_net"] == 1331606 - 660000, fii)
check("cash cumulative sums", d["cash"][-1]["fii_cum"] == round(-1000 + -930.9, 2) and d["cash"][-1]["dii_cum"] == round(500 + 1968.17, 2), d["cash"][-1])
check("api payload shape", set(("positions", "cash", "latest", "latest_cash")) <= set(d))
class Hol:
    def dates(self): return {"2026-09-14"}
fl = F.Flows(st, Hol())
import datetime as _dt
check("trading-day filter: weekend + holiday out", not fl._trading_day(_dt.date(2026, 9, 13)) and not fl._trading_day(_dt.date(2026, 9, 14)) and fl._trading_day(_dt.date(2026, 9, 15)))
print("\n=== public page ===")
import flows_page
page = flows_page.render(fl).decode()
check("public page: title with date and numbers, KPIs, table rows, Dataset + FAQ schema, canonical", "FII DII Data Today (11 Sep 2026)" in page and "−931" not in page and "-931" in page and 'class="kp"' in page and "11 Sep 2026" in page and '"Dataset"' in page and "FAQPage" in page and 'href="https://finostat.com/fii-dii"' in page and "/api/flows?days=60" in page)
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
