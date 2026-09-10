"""Economic calendar: India rules, FOMC/RBI dates, feed parsing, storage/merge, page."""
import sys, pathlib, tempfile, json, time
from datetime import date, datetime, timedelta
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import econ as E
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

print("=== india rules ===")
ev = E.india_events(date(2026, 9, 1), date(2026, 9, 30))
by = {e["title"]: e for e in ev}
cpi = datetime.fromtimestamp(by["CPI y/y (inflation)"]["ts"], E.IST)
check("CPI on 12 Sep 2026 (Saturday) rolls to Monday 14th at 16:00 IST", cpi.strftime("%Y-%m-%d %H:%M") == "2026-09-14 16:00", cpi)
wpi = datetime.fromtimestamp(by["WPI inflation y/y"]["ts"], E.IST)
check("WPI 14th at noon", wpi.strftime("%Y-%m-%d %H:%M") == "2026-09-14 12:00", wpi)
pmi = datetime.fromtimestamp(by["Manufacturing PMI"]["ts"], E.IST)
check("Manufacturing PMI first working day (Tue 1 Sep) 10:30", pmi.strftime("%Y-%m-%d %H:%M") == "2026-09-01 10:30", pmi)
spmi = datetime.fromtimestamp(by["Services PMI"]["ts"], E.IST)
check("Services PMI third working day (Thu 3 Sep)", spmi.strftime("%Y-%m-%d") == "2026-09-03", spmi)
check("no GDP in September, GDP at end of August", "GDP growth q/y" not in by and any(e["title"].startswith("GDP") for e in E.india_events(date(2026, 8, 1), date(2026, 8, 31))))
gdp = [e for e in E.india_events(date(2026, 8, 1), date(2026, 8, 31)) if e["title"].startswith("GDP")][0]
check("GDP on the last working day of August (Mon 31 Aug) 16:00", datetime.fromtimestamp(gdp["ts"], E.IST).strftime("%Y-%m-%d %H:%M") == "2026-08-31 16:00")
fx = [e for e in ev if e["title"].startswith("Forex reserves")]
check("forex reserves every Friday of the month (4 in Sep 2026)", len(fx) == 4 and all(datetime.fromtimestamp(e["ts"], E.IST).weekday() == 4 for e in fx), len(fx))
rbi = [e for e in E.india_events(date(2026, 10, 1), date(2026, 10, 31)) if "RBI" in e["title"]]
check("RBI decision 7 Oct 2026 at 10:00 IST, high impact", len(rbi) == 1 and datetime.fromtimestamp(rbi[0]["ts"], E.IST).strftime("%Y-%m-%d %H:%M") == "2026-10-07 10:00" and rbi[0]["impact"] == "High")
budget = [e for e in E.india_events(date(2027, 1, 25), date(2027, 2, 5)) if e["title"] == "Union Budget"]
check("Budget 1 Feb 2027", len(budget) == 1)
check("ids stable across calls", E.india_events(date(2026, 9, 1), date(2026, 9, 30))[0]["id"] == ev[0]["id"])

print("\n=== fomc ===")
f = E.fomc_events(date(2026, 9, 1), date(2026, 12, 31))
check("three FOMC decisions Sep-Dec 2026", [datetime.fromtimestamp(e["ts"], E.IST).strftime("%Y-%m-%d") for e in f] == ["2026-09-16", "2026-10-28", "2026-12-10"], [datetime.fromtimestamp(e["ts"], E.IST).strftime("%Y-%m-%d") for e in f])
check("Sep decision at 14:00 EDT = 23:30 IST; Dec at 14:00 EST = 00:30 IST next day", datetime.fromtimestamp(f[0]["ts"], E.IST).strftime("%H:%M") == "23:30" and datetime.fromtimestamp(f[2]["ts"], E.IST).strftime("%Y-%m-%d %H:%M") == "2026-12-10 00:30")

print("\n=== feed parsing + storage ===")
rows = E.parse_ff([{"title": "Core CPI m/m", "country": "USD", "date": "2026-09-10T08:30:00-04:00", "impact": "High", "forecast": "0.3%", "previous": "0.2%"},
                   {"title": "Federal Funds Rate", "country": "USD", "date": "2026-09-16T14:00:00-04:00", "impact": "High", "forecast": "4.00%", "previous": "4.25%"},
                   {"title": "", "country": "EUR", "date": "2026-09-10T08:30:00-04:00"}, {"title": "x", "country": "EUR", "date": "bad"}])
check("valid rows parsed, IST conversion right (08:30 EDT = 18:00 IST)", len(rows) == 2 and datetime.fromtimestamp(rows[0]["ts"], E.IST).strftime("%H:%M") == "18:00")
tmp = pathlib.Path(tempfile.mkdtemp()); ec = E.Econ(tmp / "acct.db")
ec.store(rows)
ec.store([dict(rows[0], forecast="0.4%", actual="0.5%")])
got = ec.events(date(2026, 9, 7), date(2026, 9, 20))
cpi_row = next(e for e in got if e["title"] == "Core CPI m/m")
check("upsert keeps one row, updates forecast, keeps actual once set", cpi_row["forecast"] == "0.4%" and cpi_row["actual"] == "0.5%" and sum(1 for e in got if e["title"] == "Core CPI m/m") == 1)
check("feed's Fed row replaces the generated FOMC row on 16 Sep", sum(1 for e in got if "FOMC" in e["title"] or "Federal Funds" in e["title"]) == 1 and any(e["title"] == "Federal Funds Rate" for e in got))
check("indian rules merged in, sorted by time, flags/when/date attached", any(e["country"] == "INR" for e in got) and all(got[i]["ts"] <= got[i + 1]["ts"] for i in range(len(got) - 1)) and got[0]["flag"] and got[0]["when"] and got[0]["date"])
hi = ec.high_impact(40)
check("high_impact: only High, INR/USD", all(e["impact"] == "High" and e["country"] in ("INR", "USD") for e in hi))

print("\n=== page ===")
page = E.render(ec, date(2026, 9, 10)).decode()
check("week header, filters, faq, both schema blocks", "07 Sep – 13 Sep 2026" in page and 'id="filters"' in page and "FAQPage" in page and '"@type":"ItemList"' in page)
check("cpi row rendered with forecast and actual", "Core CPI m/m" in page and "0.4%" in page and "0.5%" in page)
check("india cpi (rolled to Mon 14th) in the week", "CPI y/y (inflation)" in page)
check("prev/next week links", "/calendar?d=2026-08-31" in page and "/calendar?d=2026-09-14" in page)
check("title targets the searches", "Economic Calendar" in page and "RBI" in page and "Fed" in page)
print("\n=== holidays ===")
import holidays as H
payload = {"FO": [{"tradingDate": "14-Sep-2026", "weekDay": "Monday", "description": "Ganesh Chaturthi"}, {"tradingDate": "08-Nov-2026", "weekDay": "Sunday", "description": "Diwali Laxmi Pujan*"},
                  {"tradingDate": "02-Oct-2026", "weekDay": "Friday", "description": "Mahatma Gandhi Jayanti"}, {"tradingDate": "bad", "description": "x"}],
           "CM": [{"tradingDate": "14-Sep-2026", "weekDay": "Monday", "description": "Ganesh Chaturthi"}, {"tradingDate": "02-Oct-2026", "weekDay": "Friday", "description": "Mahatma Gandhi Jayanti"}]}
hrows = H.parse(payload)
check("parse: 3 rows sorted, bad date dropped, muhurat flag from the asterisk, segments merged", [r["date"] for r in hrows] == ["2026-09-14", "2026-10-02", "2026-11-08"] and hrows[2]["muhurat"] == 1 and hrows[2]["name"] == "Diwali Laxmi Pujan" and hrows[0]["fo"] == 1 and hrows[0]["cm"] == 1 and hrows[2]["cm"] == 0)
hs = H.Holidays(tmp / "acct.db"); hs.store(hrows)
check("store/all/dates/is_closed/next_open", len(hs.all()) == 3 and "2026-09-14" in hs.dates() and hs.is_closed(date(2026, 9, 14)) and hs.next_open(date(2026, 9, 12)) == date(2026, 9, 15))
ev2 = E.india_events(date(2026, 9, 1), date(2026, 9, 30), hs.dates())
cpi2 = datetime.fromtimestamp(next(e for e in ev2 if e["title"].startswith("CPI"))["ts"], E.IST)
check("CPI Sep 2026 rolls past Ganesh Chaturthi to Tue 15 Sep", cpi2.strftime("%Y-%m-%d") == "2026-09-15", cpi2)
pmi2 = [e for e in E.india_events(date(2026, 10, 1), date(2026, 10, 31), hs.dates()) if e["title"] == "Services PMI"][0]
check("Services PMI Oct 2026: 3rd working day skips the 2 Oct holiday -> Tue 6 Oct", datetime.fromtimestamp(pmi2["ts"], E.IST).strftime("%Y-%m-%d") == "2026-10-06")
ec2 = E.Econ(tmp / "acct.db", holidays=hs)
got2 = ec2.events(date(2026, 9, 14), date(2026, 9, 20))
check("calendar shows the weekday holiday row, not the Sunday one; CPI on the 15th", any(e["impact"] == "Holiday" and "Ganesh" in e["title"] for e in got2) and not any("Diwali" in e["title"] for e in ec2.events(date(2026, 11, 2), date(2026, 11, 8))) and any(e["title"].startswith("CPI") and e["date"] == "2026-09-15" for e in got2))
hp = P_render = None
import econ_pages as P
hp = P.render("nse-holidays", date(2026, 9, 10), holidays=hs).decode()
check("holidays page: title with year, next holiday, weekend + muhurat notes, segments", "NSE trading holidays 2026" in hp and "Next market holiday: Mon 14 Sep 2026" in hp and "falls on a weekend" in hp and "Muhurat trading session" in hp and "F&amp;O only" in hp and "F&amp;O + Equity" in hp)
cpi_pg = P.render("india-cpi-dates", date(2026, 9, 10), holidays=hs).decode()
check("cpi page uses holidays: Tue 15 Sep 2026, reason 'holiday'", "Tue 15 Sep 2026" in cpi_pg and "rolled from the 12th (holiday)" in cpi_pg)
check("holidays page renders empty-safe without a store", "not loaded yet" in P.render("nse-holidays", date(2026, 9, 10)).decode())

print("\n=== expiry dates ===")
import contracts as C
def _ms(y, m, d): return int(datetime(y, m, d, 23, 59, 59, tzinfo=E.IST).timestamp() * 1000)
rows_fo = []
for i, (y, m, d) in enumerate([(2026, 9, 15), (2026, 9, 22), (2026, 9, 29), (2026, 10, 1), (2026, 10, 6), (2026, 10, 27)]):   # Tuesdays; 1 Oct = Thu shifted (2 Oct holiday)
    rows_fo.append({"segment": "NSE_FO", "instrument_type": "CE", "underlying_symbol": "NIFTY", "expiry": _ms(y, m, d), "strike_price": 25000, "instrument_key": f"NSE_FO|N{i}", "lot_size": 65})
rows_fo.append({"segment": "NSE_FO", "instrument_type": "PE", "underlying_symbol": "RELIANCE", "expiry": _ms(2026, 9, 29), "strike_price": 1400, "instrument_key": "NSE_FO|R1", "lot_size": 250})
rows_fo.append({"segment": "BSE_FO", "instrument_type": "CE", "underlying_symbol": "SENSEX", "expiry": _ms(2026, 9, 17), "strike_price": 80000, "instrument_key": "BSE_FO|S1", "lot_size": 20})
ci = C.ContractIndex(); ci.build({"NSE": rows_fo, "BSE": [r for r in rows_fo if r["segment"] == "BSE_FO"]})
er = P.expiry_rows(ci, date(2026, 9, 10), {"2026-10-02"})
nifty = [r for r in er if r["label"] == "NIFTY 50"]
check("six NIFTY expiries, weekly/monthly classified (29 Sep + 27 Oct monthly)", len(nifty) == 6 and [r["kind"] for r in nifty] == ["weekly", "weekly", "monthly", "weekly", "weekly", "monthly"], [r["kind"] for r in nifty])
check("off-day expiry notes the usual day it moved from", nifty[3]["note"] == "moved from Tue 06 Oct", nifty[3]["note"])
check("SENSEX + stock monthly series present, sorted by date, days-to-go right", any(r["label"] == "SENSEX" for r in er) and any(r["label"].startswith("Stock options") for r in er) and er == sorted(er, key=lambda r: (r["date"], r["label"])) and nifty[0]["days"] == 5)
xp = P.render("expiry-dates", date(2026, 9, 10), holidays=hs, contracts=ci).decode()
check("expiry page: next expiry banner, per-series sections, schedule sentence, FAQ", "Next index expiry: NIFTY 50 on Tue 15 Sep 2026" in xp and "usually Tuesdays" in xp and "NIFTY 50 on Tuesdays" in xp and "FAQPage" in xp and "Stock options (monthly)" in xp)
check("expiry page renders without a contract index", "loads once the market data feed connects" in P.render("expiry-dates", date(2026, 9, 10)).decode())

print("\n=== embeds ===")
home = E.home_section(ec2, date(2026, 9, 10))
check("home section: section id, day cards, holiday card on Mon 14, links to calendar pages", 'id="events"' in home and "ev-day" in home and "Ganesh" in home and '/calendar/expiry-dates' in home and 'href="/calendar" class=main' in home)
check("home section: upcoming feed row shown (Fed decision 16 Sep)", "Federal Funds Rate" in home)
blk = E.brief_block(ec2, date(2026, 9, 10))
check("brief block: scheduled today with the CPI row (18:00 IST) and calendar link", "Scheduled today" in blk and "Core CPI m/m" in blk and "18:00" in blk and "/calendar?d=2026-09-10" in blk)
check("brief block empty on a day with nothing notable", E.brief_block(ec2, date(2026, 9, 6)) == "")
import brief as B
bs = B.Briefs(tmp / "acct.db"); bs.put("2026-09-10", "open", {"at": "09:20", "live": True, "u": {}, "vix": None})
page_b = B.render_day(bs, "2026-09-10", extra=blk, extra_css=E._BRIEF_CSS).decode()
check("brief page carries the block and its css", "Scheduled today" in page_b and "table.cal{" in page_b)

print("\n=== schedule pages ===")
import econ_pages as P
t = date(2026, 9, 10)
for slug in P.PAGES:
    body = P.render(slug, t).decode()
    check(f"{slug}: renders with canonical, FAQ+Article schema, schedules nav", f'href="https://finostat.com/calendar/{slug}"' in body and "FAQPage" in body and '"Article"' in body and "SCHEDULES" in body)
rbi = P.render("rbi-policy-dates", t).decode()
check("rbi: next decision is 7 Oct 2026, past meetings dimmed", "Next RBI decision: Wed 07 Oct 2026" in rbi and rbi.count('class="past"') == 3)
cpi = P.render("india-cpi-dates", t).decode()
check("cpi: Sep 2026 release rolled to Mon 14th, labelled as August data", "Mon 14 Sep 2026" in cpi and "CPI for August 2026" in cpi and "rolled from the 12th" in cpi)
fomc = P.render("fomc-meeting-dates", t).decode()
check("fomc: next decision 16 Sep at 23:30 IST, Dec shown as 00:30 IST next day", "Wed 16 Sep 2026 · 23:30 IST" in fomc and "Thu 10 Dec · 00:30 IST" in fomc)
data = P.render("india-data-release-dates", t).decode()
check("data schedule: GDP at end of Nov, PMIs, WPI present", "GDP growth q/y" in data and "Manufacturing PMI" in data and "WPI inflation" in data)
check("unknown slug -> None", P.render("nope", t) is None)
check("live calendar links the schedule pages", "/calendar/rbi-policy-dates" in E.render(ec, date(2026, 9, 10)).decode())
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
