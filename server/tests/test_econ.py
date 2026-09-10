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
