"""Evergreen schedule pages under /calendar/<slug>: the searches traders actually make
("RBI policy dates 2026", "India CPI release date", "FOMC meeting dates 2027").
Dates come from the same lists and rules as the live calendar (econ.py); never typed here."""
from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta, timezone

import econ

IST = econ.IST

# Full meeting windows (decision on the last day). RBI: FY 2026-27 calendar. FOMC: Fed's published
# calendar; * = meetings with a Summary of Economic Projections.
RBI_MEETINGS = [("2026-04-06", "2026-04-08"), ("2026-06-03", "2026-06-05"), ("2026-08-03", "2026-08-05"),
                ("2026-10-05", "2026-10-07"), ("2026-12-02", "2026-12-04"), ("2027-02-03", "2027-02-05")]
FOMC_MEETINGS = [("2026-01-27", "2026-01-28", True), ("2026-03-17", "2026-03-18", True), ("2026-04-28", "2026-04-29", False),
                 ("2026-06-16", "2026-06-17", True), ("2026-07-28", "2026-07-29", False), ("2026-09-15", "2026-09-16", True),
                 ("2026-10-27", "2026-10-28", False), ("2026-12-08", "2026-12-09", True),
                 ("2027-01-26", "2027-01-27", False), ("2027-03-16", "2027-03-17", True), ("2027-04-27", "2027-04-28", False),
                 ("2027-06-08", "2027-06-09", True), ("2027-07-27", "2027-07-28", False), ("2027-09-14", "2027-09-15", True),
                 ("2027-10-26", "2027-10-27", False), ("2027-12-07", "2027-12-08", True)]
assert [m[1] for m in RBI_MEETINGS if m[1] >= "2026-10-01"] == econ.RBI_MPC
assert [m[1] for m in FOMC_MEETINGS if m[1] >= "2026-09-01"] == econ.FOMC


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _fmt(d: date) -> str:
    return d.strftime("%a %d %b %Y")


def _range(start: str, end: str) -> str:
    a, b = _d(start), _d(end)
    if a.month == b.month:
        return f"{a.day:02d}–{b.day:02d} {b.strftime('%b %Y')}"
    return f"{a.strftime('%d %b')} – {b.strftime('%d %b %Y')}"


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _tbl(head: list[str], rows: list[list[str]], today: date, date_col: int = 0, name_col: int = -1) -> str:
    ths = "".join(f'<th style="text-align:left;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">{h}</th>' for h in head)
    trs = []
    for r in rows:
        past = r[date_col] < today.isoformat() if isinstance(r[date_col], str) and len(r[date_col]) == 10 else False
        cells = "".join(f'<td class="{"n" if i == name_col else "t"}">{_esc(c) if i != date_col else _fmt(_d(c))}</td>' for i, c in enumerate(r))
        trs.append(f'<tr class="{"past" if past else ""}">{cells}</tr>')
    return f'<div class="scrollx"><table class="cal"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'


def _next_of(dates: list[str], today: date) -> str | None:
    for s in dates:
        if _d(s) >= today:
            return s
    return None


def rbi(today: date) -> dict:
    rows = [[end, _range(start, end), "10:00 IST", "Repo rate, stance; Governor's statement and press conference"] for start, end in RBI_MEETINGS]
    nxt = _next_of([m[1] for m in RBI_MEETINGS], today)
    return {
        "title": "RBI Monetary Policy Dates 2026-27 — MPC meeting schedule, announcement time | Finostat",
        "desc": "All RBI MPC meeting dates for FY 2026-27 with the decision date and 10:00 IST announcement time. What the repo rate decision does to BANKNIFTY and how options price it.",
        "h1": "RBI monetary policy dates 2026-27",
        "lede": "The Reserve Bank's Monetary Policy Committee meets six times a year. The decision is announced at 10:00 IST on the last day of each meeting, followed by the Governor's press conference — the most important scheduled event for BANKNIFTY.",
        "next": f"Next RBI decision: {_fmt(_d(nxt))} at 10:00 IST" if nxt else "FY 2027-28 dates will be added when the RBI publishes them.",
        "body": _tbl(["DECISION", "MEETING", "TIME", "WHAT IS ANNOUNCED"], rows, today, name_col=3) + """
<section class="faq"><h3>What time is the RBI policy announced?</h3><p>10:00 IST on the last day of the meeting. The market is open, so the first move is immediate: BANKNIFTY and the rate-sensitive stocks (banks, NBFCs, auto, realty) reprice in the first five minutes, and again during the press conference around 10:45 when the stance and guidance come through.</p>
<h3>How do options price the RBI decision?</h3><p>Weekly BANKNIFTY and NIFTY options carry a premium into the meeting. The ATM straddle of the expiry that spans the decision is the implied move; it typically collapses (vol crush) within an hour of the announcement. The Finostat terminal shows this straddle next to the date in its EVENTS panel, and the <a href="/finch/implied-volatility">Finch chapter on implied volatility</a> explains the mechanics.</p>
<h3>How many MPC meetings are there in a year?</h3><p>Six bi-monthly meetings — normally April, June, August, October, December and February — each three days long. The minutes are published on the 14th day after the meeting.</p></section>""",
        "faq": [("What time is the RBI policy announced?", "At 10:00 IST on the last day of the MPC meeting, followed by the Governor's press conference."),
                ("When is the next RBI policy meeting?", f"The next decision is on {_fmt(_d(nxt))} at 10:00 IST." if nxt else "The FY 2027-28 schedule is awaited from the RBI."),
                ("How many MPC meetings are there in a year?", "Six bi-monthly meetings of three days each: April, June, August, October, December and February.")],
        "source": "Source: RBI's MPC meeting schedule for FY 2026-27 (press release, March 2026).",
    }


def _monthly(today: date, title_key: str, months: int = 14, hol: set = frozenset()) -> list[dict]:
    start = date(today.year, today.month, 1)
    y, m = start.year, start.month + months
    while m > 12:
        m -= 12; y += 1
    end = date(y, m, 1) - timedelta(days=1)
    return [e for e in econ.india_events(start, end, hol) if e["title"] == title_key]


def cpi(today: date, hol: set = frozenset()) -> dict:
    events = _monthly(today, "CPI y/y (inflation)", hol=hol)
    rows = []
    for e in events:
        d = datetime.fromtimestamp(e["ts"], IST).date()
        ref = (d.replace(day=1) - timedelta(days=1))
        why = ""
        if d.day != 12:
            twelfth = d.replace(day=12)
            blocked = [twelfth + timedelta(days=i) for i in range((d - twelfth).days)]
            why = " · rolled from the 12th (" + ("holiday" if any(x.isoformat() in hol for x in blocked) else "weekend") + ")"
        rows.append([d.isoformat(), f"CPI for {ref.strftime('%B %Y')}", "16:00 IST", "with IIP" + why])
    nxt = _next_of([r[0] for r in rows], today)
    return {
        "title": "India CPI Release Dates 2026-27 — inflation data schedule, time, IIP and WPI | Finostat",
        "desc": "When India's CPI inflation data is released each month: the 12th at 16:00 IST (next working day if a holiday), with IIP; WPI on the 14th at noon. Full date list for the coming year.",
        "h1": "India CPI release dates",
        "lede": "The Ministry of Statistics (MOSPI) releases the Consumer Price Index at 16:00 IST on the 12th of every month, together with the Index of Industrial Production. When the 12th falls on a weekend or holiday the release moves to the next working day. The cash market has closed by 16:00, so the reaction lands at the next morning's open — and in the evening's SGX/GIFT Nifty.",
        "next": f"Next CPI release: {_fmt(_d(nxt))} at 16:00 IST" if nxt else "",
        "body": _tbl(["DATE", "RELEASE", "TIME", "NOTE"], rows, today, name_col=3) + """
<section class="faq"><h3>What time is India's CPI released?</h3><p>16:00 IST, after the equity market closes. Bond and currency traders react the same evening; the equity reaction is at 09:15 the next day.</p>
<h3>What about WPI?</h3><p>Wholesale price inflation is published by DPIIT on the 14th of each month at 12:00 IST, while the market is open. It matters less for rates than CPI but moves commodity-linked names.</p>
<h3>Why does CPI matter for NIFTY?</h3><p>CPI is the number the RBI targets (4%, ±2%). A print above expectations pushes bond yields up and makes a rate cut less likely, which hits banks, NBFCs and rate-sensitive stocks; a soft print does the opposite. Watch the core (ex food and fuel) reading as much as the headline.</p></section>""",
        "faq": [("What time is India's CPI released?", "At 16:00 IST on the 12th of each month (next working day if a holiday), by MOSPI, together with IIP."),
                ("When is the next India CPI release?", f"{_fmt(_d(nxt))} at 16:00 IST." if nxt else ""),
                ("When is WPI released?", "On the 14th of each month at 12:00 IST by DPIIT.")],
        "source": "Dates follow MOSPI's advance release calendar rule (12th, 16:00 IST, next working day if a holiday); exact dates can shift on public holidays.",
    }


def fomc(today: date) -> dict:
    rows = []
    for start, end, sep in FOMC_MEETINGS:
        e = econ.fomc_events(_d(end), _d(end))
        ist = datetime.fromtimestamp(e[0]["ts"], IST) if e else None
        rows.append([end, _range(start, end) + (" *" if sep else ""), "14:00 ET", ist.strftime("%a %d %b · %H:%M IST") if ist else "—"])
    nxt = _next_of([m[1] for m in FOMC_MEETINGS], today)
    nxt_ist = datetime.fromtimestamp(econ.fomc_events(_d(nxt), _d(nxt))[0]["ts"], IST) if nxt and econ.fomc_events(_d(nxt), _d(nxt)) else None
    return {
        "title": "FOMC Meeting Dates 2026 & 2027 in IST — Fed interest rate decision schedule | Finostat",
        "desc": "Every FOMC meeting in 2026 and 2027 with the decision time converted to IST (23:30 or 00:30 next day). Which meetings carry projections and why the Fed decision moves NIFTY the next morning.",
        "h1": "FOMC meeting dates 2026 and 2027, in IST",
        "lede": "The US Federal Reserve's Open Market Committee meets eight times a year. The statement is released at 14:00 Eastern on the second day — 23:30 IST during US daylight time and 00:30 IST the following morning in winter — with the Chair's press conference half an hour later. Meetings marked * publish the Summary of Economic Projections and the dot plot.",
        "next": f"Next Fed decision: {nxt_ist.strftime('%a %d %b %Y · %H:%M IST')}" if nxt_ist else "",
        "body": _tbl(["DECISION", "MEETING", "TIME (US)", "TIME (IST)"], rows, today) + """
<section class="faq"><h3>Why does an Indian trader care about the Fed?</h3><p>The Fed sets the price of the dollar. A hawkish surprise lifts US yields and the dollar, pulls foreign money out of emerging markets and shows up as a gap-down in NIFTY and a weaker rupee at 09:15 the next morning. Dovish surprises do the reverse. IT stocks trade the dollar; banks trade the yield.</p>
<h3>Which meetings matter most?</h3><p>The four with projections (March, June, September, December) — the dot plot resets rate expectations for the year, so those meetings carry the largest overnight moves.</p>
<h3>How do I trade it?</h3><p>Usually by not carrying naked short options overnight into it. The next-day implied move is visible in the NIFTY straddle on the Finostat terminal's EVENTS panel; the <a href="/brief">daily brief</a> prints it the morning after.</p></section>""",
        "faq": [("What time is the FOMC decision in India?", "23:30 IST when the US is on daylight time (mid-March to early November), 00:30 IST the next morning otherwise."),
                ("When is the next FOMC meeting?", f"{nxt_ist.strftime('%d %B %Y')}, decision at {nxt_ist.strftime('%H:%M IST')}." if nxt_ist else ""),
                ("How many FOMC meetings are there a year?", "Eight scheduled meetings; four of them include the Summary of Economic Projections.")],
        "source": "Source: Federal Reserve Board's published FOMC meeting calendars for 2026 and 2027.",
    }


def india_data(today: date, hol: set = frozenset()) -> dict:
    start = date(today.year, today.month, 1)
    end = date(start.year + 1, start.month, 1) - timedelta(days=1)
    wanted = ("GDP growth q/y", "Manufacturing PMI", "Services PMI", "WPI inflation y/y", "Industrial Production (IIP) y/y")
    rows = []
    for e in econ.india_events(start, end, hol):
        if e["title"] in wanted:
            d = datetime.fromtimestamp(e["ts"], IST)
            rows.append([d.strftime("%Y-%m-%d"), e["title"], d.strftime("%H:%M IST"), e.get("detail", "")])
    rows.sort()
    return {
        "title": "India Economic Data Release Schedule — GDP, PMI, IIP, WPI dates and times | Finostat",
        "desc": "The schedule of India's market-moving data for the next twelve months: quarterly GDP, manufacturing and services PMI, IIP and WPI, with release times in IST and who publishes each.",
        "h1": "India economic data release schedule",
        "lede": "Beyond CPI and the RBI, a handful of releases move Indian markets on a fixed rhythm: quarterly GDP at the end of February, May, August and November; the HSBC/S&P Global PMIs on the first and third working days of the month; IIP with CPI on the 12th; WPI on the 14th. All times IST.",
        "next": "",
        "body": _tbl(["DATE", "RELEASE", "TIME", "PUBLISHER"], rows, today, name_col=3) + """
<section class="faq"><h3>When is India's GDP released?</h3><p>At 16:00 IST on the last working day of February (Q3), May (Q4 and the full year), August (Q1) and November (Q2), by MOSPI.</p>
<h3>When is the PMI released?</h3><p>Manufacturing PMI on the first working day of the month and services PMI on the third, both at 10:30 IST while the market is open. The flash readings, where published, come about a week earlier.</p>
<h3>Which of these move the market?</h3><p>GDP and the PMIs move the index on surprises; IIP and WPI mostly move sectors (capital goods, commodities). The RBI reads all of them before its policy meeting, so a run of weak prints ahead of a decision changes the rate expectation more than any single number.</p></section>""",
        "faq": [("When is India's GDP released?", "At 16:00 IST on the last working day of February, May, August and November."),
                ("When is India's PMI released?", "Manufacturing PMI on the first working day of the month, services PMI on the third, at 10:30 IST."),
                ("When is IIP released?", "With CPI, on the 12th of each month at 16:00 IST.")],
        "source": "Dates follow the publishers' standing schedules (MOSPI, DPIIT, S&P Global); exact dates can shift on public holidays.",
    }


def nse_holidays(today: date, hol_rows: list[dict] | None = None) -> dict:
    rows_in = hol_rows or []
    years = sorted({r["date"][:4] for r in rows_in}) or [str(today.year)]
    ylabel = " & ".join(years)
    rows, upcoming = [], []
    for h in rows_in:
        d = _d(h["date"])
        seg = "F&O + Equity" if h["fo"] and h["cm"] else ("F&O only" if h["fo"] else "Equity only")
        note = "falls on a weekend" if d.weekday() >= 5 else ""
        if h.get("muhurat"):
            note = (note + " · " if note else "") + "Muhurat trading session in the evening"
        rows.append([h["date"], h["name"], seg, note])
        if d >= today and d.weekday() < 5:
            upcoming.append(h)
    nxt = upcoming[0] if upcoming else None
    weekday_count = sum(1 for h in rows_in if _d(h["date"]).weekday() < 5)
    return {
        "title": f"NSE Holidays {ylabel} — stock market trading holiday list (F&O and equity) | Finostat",
        "desc": f"Official NSE trading holidays for {ylabel} with the weekday, segment (F&O, equity) and Muhurat trading note. {weekday_count} weekday closures. Straight from the exchange's holiday master, refreshed daily.",
        "h1": f"NSE trading holidays {ylabel}",
        "lede": f"The days the National Stock Exchange is closed for trading in {ylabel}, as published in the exchange's holiday master and refreshed here every day. Weekend dates are listed because NSE lists them; they don't cost a trading session. Expiries that land on a holiday move to the previous trading day, and Finostat's calendar rolls India's data releases past these dates automatically.",
        "next": f"Next market holiday: {_fmt(_d(nxt['date']))} — {nxt['name']}" if nxt else "",
        "body": (_tbl(["DATE", "HOLIDAY", "SEGMENTS", "NOTE"], rows, today, name_col=1) if rows else '<div class="empty">holiday list not loaded yet — try again in a minute</div>') + """
<section class="faq"><h3>Is the stock market open on Saturdays?</h3><p>No. NSE and BSE trade Monday to Friday, 09:15 to 15:30 IST, with a pre-open session from 09:00. The exchange occasionally holds a special Saturday session to test disaster-recovery systems; those are announced separately and are not on this list.</p>
<h3>What is Muhurat trading?</h3><p>A one-hour symbolic session on the evening of Diwali (Laxmi Pujan). The market is closed during the day and opens for the special session in the evening; timings are announced by the exchange a few weeks before.</p>
<h3>What happens to a weekly expiry on a holiday?</h3><p>It moves to the previous trading day. If Thursday is a holiday, the Thursday expiry settles on Wednesday — a shorter week, so the same premium decays faster. The <a href="/brief">daily brief</a> shows the actual expiry the contracts carry.</p>
<h3>Do these holidays apply to commodity and currency segments?</h3><p>Not always — MCX and the currency derivatives segment keep their own lists, and several of these days have an evening commodity session. This page covers the equity cash and F&amp;O segments.</p></section>""",
        "faq": [("Is the stock market open on Saturdays?", "No. NSE and BSE trade Monday to Friday, 09:15 to 15:30 IST, apart from occasional special test sessions announced by the exchange."),
                ("When is the next NSE holiday?", f"{_fmt(_d(nxt['date']))}, {nxt['name']}." if nxt else ""),
                ("What is Muhurat trading?", "A one-hour symbolic trading session held on the evening of Diwali (Laxmi Pujan), when the market is otherwise closed.")],
        "source": "Source: NSE holiday master (equity and F&O segments), refreshed daily. Special sessions announced by the exchange are not included.",
    }


INDICES = [("NIFTY", "NIFTY 50", "NSE"), ("BANKNIFTY", "BANKNIFTY", "NSE"), ("FINNIFTY", "FINNIFTY", "NSE"), ("MIDCPNIFTY", "MIDCPNIFTY", "NSE"),
           ("SENSEX", "SENSEX", "BSE"), ("BANKEX", "BANKEX", "BSE")]


def expiry_rows(contracts, today: date, hol: set = frozenset()) -> list[dict]:
    """Every listed expiry per index (and the stock-option monthly series), with weekly/monthly
    classification and a holiday-shift note. Dates come from the exchange instrument masters."""
    out = []
    if contracts is None:
        return out
    # real "now" when rendering for today, so a series that closed at 15:30 drops off; midnight for fixed dates (tests)
    now_ms = (datetime.now(IST) if today == datetime.now(IST).date() else datetime(today.year, today.month, today.day, tzinfo=IST)).timestamp() * 1000
    series = [(n, label, exch) for n, label, exch in INDICES if contracts.has(n)]
    stock = next((n for n in contracts.names() if n not in {i[0] for i in INDICES} and contracts.expiries(n, now_ms)), None)
    if stock:
        series.append((stock, "Stock options (monthly)", "NSE"))
    for name, label, exch in series:
        exps = contracts.expiries(name, now_ms)
        dates = [datetime.fromtimestamp(e / 1000, IST).date() for e in exps]
        if not dates:
            continue
        weekdays = [d.weekday() for d in dates]
        usual = max(set(weekdays), key=weekdays.count)
        last_in_month = {}
        for d in dates:
            last_in_month[(d.year, d.month)] = d
        monthly_dates = set(last_in_month.values())
        for d in dates:
            kind = "monthly" if d in monthly_dates else "weekly"
            note = ""
            if d.weekday() != usual:
                # shifted off the usual weekday: the day it would have expired on, and whether that is a holiday
                u = d + timedelta(days=(usual - d.weekday()) % 7)
                note = f"moved from {u.strftime('%a %d %b')}" + (" (holiday)" if u.isoformat() in hol else "")
            out.append({"name": name, "label": label, "exchange": exch, "date": d.isoformat(), "kind": kind, "days": (d - today).days, "note": note,
                        "weekday": d.strftime("%A")})
    out.sort(key=lambda r: (r["date"], r["label"]))
    return out


def expiry_dates(today: date, contracts=None, hol: set = frozenset()) -> dict:
    rows = expiry_rows(contracts, today, hol)
    by_series: dict[str, list[dict]] = {}
    for r in rows:
        by_series.setdefault(r["label"], []).append(r)
    usual_day = {label: max(set(x["weekday"] for x in rs), key=[x["weekday"] for x in rs].count) for label, rs in by_series.items()}
    parts = []
    for label, rs in by_series.items():
        wk = usual_day[label]
        head = f'<div class="day">{_esc(label)}<small>{_esc(rs[0]["exchange"])} · usually {wk}s · {len(rs)} listed</small></div>'
        trs = "".join(
            f'<tr class="{"past" if r["days"] < 0 else ""}"><td class="t">{_fmt(_d(r["date"]))}</td><td class="t">{"in " + str(r["days"]) + "d" if r["days"] > 0 else ("today" if r["days"] == 0 else "")}</td>'
            f'<td class="t"><span class="imp {"High" if r["kind"] == "monthly" else "Medium"}" style="margin-right:6px"></span>{r["kind"]}</td><td class="n">{_esc(r["note"])}</td></tr>' for r in rs)
        parts.append(head + f'<div class="scrollx"><table class="cal"><thead><tr><th style="text-align:left;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">EXPIRY</th><th style="text-align:left;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">IN</th><th style="text-align:left;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">SERIES</th><th style="text-align:left;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">NOTE</th></tr></thead><tbody>{trs}</tbody></table></div>')
    upcoming = [r for r in rows if r["days"] >= 0 and r["label"] != "Stock options (monthly)"]
    nxt = upcoming[0] if upcoming else None
    schedule = " · ".join(f"{label} on {day}s" for label, day in usual_day.items() if label != "Stock options (monthly)")
    return {
        "title": "F&O Expiry Dates — NIFTY, BANKNIFTY, FINNIFTY, SENSEX weekly and monthly expiry calendar | Finostat",
        "desc": "Every upcoming NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX and BANKEX expiry, weekly and monthly, plus the stock-options monthly series, taken from the exchange contract masters with holiday shifts marked.",
        "h1": "F&O expiry dates",
        "lede": "Every option expiry currently listed on NSE and BSE, straight from the exchange contract masters that the Finostat terminal trades from, so a holiday-shifted expiry shows the real date. Weekly expiries settle at 15:30 IST on the expiry day; the monthly series is the last expiry of each month." + (f" Current schedule: {schedule}." if schedule else ""),
        "next": f"Next index expiry: {nxt['label']} on {_fmt(_d(nxt['date']))}" + (" (today)" if nxt["days"] == 0 else f" · in {nxt['days']} day{'s' if nxt['days'] != 1 else ''}") if nxt else "",
        "body": ("".join(parts) if parts else '<div class="empty">expiry list loads once the market data feed connects — try again in a minute</div>') + """
<section class="faq"><h3>When do NIFTY and BANKNIFTY options expire?</h3><p>On the weekday the exchange has set for each index — the table above shows the current day for every series — at 15:30 IST. Only the dates the exchange has actually listed appear here, so the list grows as new weeklies are added.</p>
<h3>What happens when the expiry day is a holiday?</h3><p>The contract expires on the previous trading day. That is why a row can show a Wednesday for a Thursday series: the exchange master already carries the shifted date, and the note column names the reason when it matches the <a href="/calendar/nse-holidays">NSE holiday list</a>.</p>
<h3>Weekly or monthly — which matters?</h3><p>Monthly expiries carry the most open interest and see the largest rollover flows in the final two sessions; weeklies are where the gamma is. Stock options only have a monthly series. The <a href="/brief">daily expiry brief</a> covers the day's expiry every morning with the implied move and max pain.</p>
<h3>Is expiry day different for stocks?</h3><p>Yes: all stock options and futures share one monthly expiry, shown as the last series in the table. There are no weekly stock options.</p></section>""",
        "faq": [("When do NIFTY options expire?", f"On {usual_day.get('NIFTY 50', 'the exchange-set weekday')}s at 15:30 IST; the monthly series is the last expiry of the month." if usual_day else "At 15:30 IST on the exchange-set weekday."),
                ("What happens if expiry falls on a holiday?", "The contract expires on the previous trading day; the exchange contract master carries the shifted date."),
                ("When is the next NIFTY expiry?", next((f"{_fmt(_d(r['date']))}." for r in upcoming if r["label"] == "NIFTY 50"), ""))],
        "source": "Source: NSE and BSE contract masters (via the Upstox instrument files), refreshed with the market data feed; NSE holiday master for the shift reasons.",
    }


PAGES = {
    "expiry-dates": ("Expiry dates", expiry_dates),
    "nse-holidays": ("NSE holidays", nse_holidays),
    "rbi-policy-dates": ("RBI policy dates", rbi),
    "india-cpi-dates": ("India CPI dates", cpi),
    "fomc-meeting-dates": ("FOMC dates in IST", fomc),
    "india-data-release-dates": ("India data schedule", india_data),
}


def links_html(current: str | None = None) -> str:
    items = "".join(f'<a class="nav{" on" if slug == current else ""}" href="/calendar/{slug}">{label}</a>' for slug, (label, _) in PAGES.items())
    return f'<div class="cal-top" style="margin-top:18px"><span style="color:var(--faint);letter-spacing:.14em">SCHEDULES</span>{items}</div>'


def render(slug: str, today: date | None = None, holidays=None, contracts=None) -> bytes | None:
    if slug not in PAGES:
        return None
    today = today or datetime.now(IST).date()
    hol_rows = []
    try:
        hol_rows = holidays.all() if holidays is not None else []
    except Exception:
        hol_rows = []
    hol = {h["date"] for h in hol_rows if h.get("fo")}
    fn = PAGES[slug][1]
    if slug == "nse-holidays":
        p = fn(today, hol_rows)
    elif slug == "expiry-dates":
        p = fn(today, contracts, hol)
    elif slug in ("india-cpi-dates", "india-data-release-dates"):
        p = fn(today, hol)
    else:
        p = fn(today)
    url = f"https://finostat.com/calendar/{slug}"
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
              "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in p["faq"] if a]}
    art_ld = {"@context": "https://schema.org", "@type": "Article", "headline": p["h1"], "description": p["desc"], "url": url,
              "dateModified": today.isoformat(), "author": {"@type": "Person", "name": "Zico Karmakar", "url": "https://finostat.com/founders"},
              "publisher": {"@type": "Organization", "name": "Finostat", "url": "https://finostat.com"}, "isPartOf": {"@type": "WebPage", "url": "https://finostat.com/calendar"}}
    ld1 = json.dumps(faq_ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    ld2 = json.dumps(art_ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    nxt = f'<div class="next"><b>{_esc(p["next"])}</b></div>' if p["next"] else ""
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(p["title"])}</title><meta name="description" content="{_esc(p["desc"])}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow, max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{_esc(p["title"])}"><meta property="og:description" content="{_esc(p["desc"])}"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="{url}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{ld1}</script>
<script type="application/ld+json">{ld2}</script>
<style>{econ._CSS}.cal-top a.nav.on{{border-color:var(--gold);color:var(--gold)}}table.cal td.t{{white-space:nowrap;width:auto}}</style></head><body>
<header class="top"><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/calendar">CALENDAR</a><a href="/brief">BRIEF</a><a href="/finch">FINCH</a><a href="/dashboard">TERMINAL</a></div><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="34" height="34"></a></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · <a href="/calendar">CALENDAR</a> · {_esc(PAGES[slug][0]).upper()}</nav>
<h1>{_esc(p["h1"])}</h1>
<p class="lede">{p["lede"]}</p>
{nxt}
{p["body"]}
<p class="disc">{_esc(p["source"])} Nothing here is investment advice.</p>
<p style="margin-top:22px"><a class="cta" href="/calendar">This week's full economic calendar →</a> <a class="cta ghost" href="/dashboard">See the implied move on the terminal</a></p>
{links_html(slug)}
</main></body></html>"""
    return doc.encode("utf-8")
