"""Public economic calendar (/calendar): the releases that move Indian markets.

Sources, merged and de-duplicated:
- Forex Factory's public weekly feed (USD, EUR, GBP, JPY, CNY, AUD, CAD, CHF,
  NZD): CPI, PPI, NFP, central-bank decisions, GDP... with impact, forecast
  and previous. Fetched hourly for the current week and kept, so the site
  builds its own archive week by week.
- India's scheduled releases, generated from the published rules: CPI and IIP
  (12th, 16:00 IST), WPI (14th, 12:00), PMI (first / third working day,
  10:30), GDP (last working day of Feb/May/Aug/Nov, 16:00), GST collections,
  auto sales, forex reserves (Friday 17:00).
- Scheduled decisions with known dates: RBI MPC (FY27 calendar) and FOMC
  (Fed's published 2026-27 calendar), plus the Union Budget.
Everything is shown in IST. Public, no login: it is the kind of page people
search for, and it links the rest of Finostat.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import pathlib
import sqlite3
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger("finostat.econ")

IST = timezone(timedelta(hours=5, minutes=30))
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FLAGS = {"INR": "🇮🇳", "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "CNY": "🇨🇳", "AUD": "🇦🇺", "CAD": "🇨🇦", "CHF": "🇨🇭", "NZD": "🇳🇿", "All": "🌐"}
REGION = {"INR": "India", "USD": "United States", "EUR": "Euro area", "GBP": "United Kingdom", "JPY": "Japan", "CNY": "China",
          "AUD": "Australia", "CAD": "Canada", "CHF": "Switzerland", "NZD": "New Zealand", "All": "Global"}

# Decision dates with published calendars. Decision is announced on the last day.
RBI_MPC = ["2026-10-07", "2026-12-04", "2027-02-05"]                     # FY27 schedule (RBI, 23 Mar 2026)
FOMC = ["2026-09-16", "2026-10-28", "2026-12-09", "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28",
        "2027-09-15", "2027-10-27", "2027-12-08"]                          # federalreserve.gov calendar, 2nd day
BUDGET = ["2027-02-01"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS econ_events(
  id        TEXT PRIMARY KEY,
  ts        REAL NOT NULL,
  country   TEXT NOT NULL,
  title     TEXT NOT NULL,
  impact    TEXT NOT NULL,
  forecast  TEXT,
  previous  TEXT,
  actual    TEXT,
  source    TEXT NOT NULL,
  updated   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS econ_ts ON econ_events(ts);
"""


def _eid(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:16]


def _ist(y: int, m: int, d: int, hh: int, mm: int) -> float:
    return datetime(y, m, d, hh, mm, tzinfo=IST).timestamp()


def _roll_forward(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _nth_working_day(y: int, m: int, n: int) -> date:
    d, seen = date(y, m, 1), 0
    while True:
        if d.weekday() < 5:
            seen += 1
            if seen == n:
                return d
        d += timedelta(days=1)


def _last_working_day(y: int, m: int) -> date:
    d = (date(y + (m // 12), m % 12 + 1, 1) - timedelta(days=1))
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def india_events(start: date, end: date) -> list[dict]:
    """Rule-generated Indian releases between two dates (inclusive)."""
    out = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        rows = [
            (_roll_forward(date(y, m, 12)), 16, 0, "CPI y/y (inflation)", "High", "MOSPI, 12th at 16:00 IST; next working day if a holiday"),
            (_roll_forward(date(y, m, 12)), 16, 0, "Industrial Production (IIP) y/y", "Medium", "MOSPI, with CPI"),
            (_roll_forward(date(y, m, 14)), 12, 0, "WPI inflation y/y", "Medium", "DPIIT, 14th at noon"),
            (_nth_working_day(y, m, 1), 10, 30, "Manufacturing PMI", "Medium", "S&P Global / HSBC"),
            (_nth_working_day(y, m, 3), 10, 30, "Services PMI", "Medium", "S&P Global / HSBC"),
            (date(y, m, 1), 12, 0, "GST collections", "Low", "Ministry of Finance"),
            (date(y, m, 1), 12, 0, "Auto sales (monthly)", "Low", "Manufacturer despatches"),
        ]
        if m in (2, 5, 8, 11):
            rows.append((_last_working_day(y, m), 16, 0, "GDP growth q/y", "High", "MOSPI quarterly estimate"))
        for d, hh, mm, title, impact, detail in rows:
            if start <= d <= end:
                out.append({"id": _eid("in", title, d), "ts": _ist(d.year, d.month, d.day, hh, mm), "country": "INR", "title": title,
                            "impact": impact, "forecast": "", "previous": "", "actual": "", "source": "rule", "detail": detail})
        # forex reserves every Friday
        d = start if start.month == m and start.year == y else date(y, m, 1)
        while d.month == m and d <= end:
            if d.weekday() == 4:
                out.append({"id": _eid("in-fx", d), "ts": _ist(d.year, d.month, d.day, 17, 0), "country": "INR", "title": "Forex reserves (weekly)",
                            "impact": "Low", "forecast": "", "previous": "", "actual": "", "source": "rule", "detail": "RBI weekly statistical supplement"})
            d += timedelta(days=1)
        m += 1
        if m == 13:
            m, y = 1, y + 1
    for s in RBI_MPC:
        d = date.fromisoformat(s)
        if start <= d <= end:
            out.append({"id": _eid("rbi", s), "ts": _ist(d.year, d.month, d.day, 10, 0), "country": "INR", "title": "RBI Monetary Policy decision (repo rate)",
                        "impact": "High", "forecast": "", "previous": "", "actual": "", "source": "rule", "detail": "MPC statement 10:00 IST, Governor's press conference after"})
    for s in BUDGET:
        d = date.fromisoformat(s)
        if start <= d <= end:
            out.append({"id": _eid("budget", s), "ts": _ist(d.year, d.month, d.day, 11, 0), "country": "INR", "title": "Union Budget",
                        "impact": "High", "forecast": "", "previous": "", "actual": "", "source": "rule", "detail": "Finance Minister's budget speech, 11:00 IST"})
    return out


def fomc_events(start: date, end: date) -> list[dict]:
    out = []
    for s in FOMC:
        d = date.fromisoformat(s)
        if start <= d <= end:
            # 14:00 Eastern: EDT (UTC-4) mid-March..early-Nov, else EST (UTC-5)
            edt = date(d.year, 3, 8) <= d < date(d.year, 11, 1)
            ts = datetime(d.year, d.month, d.day, 14, 0, tzinfo=timezone(timedelta(hours=-4 if edt else -5))).timestamp()
            out.append({"id": _eid("fomc", s), "ts": ts, "country": "USD", "title": "FOMC interest rate decision", "impact": "High",
                        "forecast": "", "previous": "", "actual": "", "source": "rule", "detail": "Statement 14:00 ET; press conference 14:30 ET"})
    return out


def parse_ff(rows: list) -> list[dict]:
    out = []
    for r in rows or []:
        try:
            ts = datetime.fromisoformat(str(r.get("date")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            continue
        title, country = str(r.get("title", "")).strip(), str(r.get("country", "All")).strip() or "All"
        if not title:
            continue
        out.append({"id": _eid("ff", title, country, int(ts)), "ts": ts, "country": country, "title": title,
                    "impact": str(r.get("impact", "Low")).title(), "forecast": str(r.get("forecast") or ""), "previous": str(r.get("previous") or ""),
                    "actual": str(r.get("actual") or ""), "source": "ff", "detail": ""})
    return out


class Econ:
    def __init__(self, path: pathlib.Path, interval: float = 3600.0):
        self.path, self.interval = pathlib.Path(path), interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.fetched: float | None = None
        self.error: str | None = None
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def start(self) -> None:
        threading.Thread(target=self._run, name="econ", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def refresh(self) -> bool:
        try:
            req = urllib.request.Request(FF_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; Finostat/1.0; +https://finostat.com)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                rows = parse_ff(json.loads(r.read().decode("utf-8")))
        except Exception as exc:
            self.error = str(exc)[:160]
            log.warning("econ: feed: %s", exc)
            return False
        self.store(rows)
        self.fetched, self.error = time.time(), None
        log.info("econ: %d global events this week", len(rows))
        return True

    def store(self, rows: list[dict]) -> None:
        with self._lock, self._conn() as c:
            for e in rows:
                c.execute("INSERT INTO econ_events(id,ts,country,title,impact,forecast,previous,actual,source,updated) VALUES(?,?,?,?,?,?,?,?,?,?) "
                          "ON CONFLICT(id) DO UPDATE SET forecast=excluded.forecast, previous=excluded.previous, "
                          "actual=CASE WHEN excluded.actual!='' THEN excluded.actual ELSE econ_events.actual END, impact=excluded.impact, updated=excluded.updated",
                          (e["id"], e["ts"], e["country"], e["title"], e["impact"], e["forecast"], e["previous"], e["actual"], e["source"], time.time()))

    def _run(self) -> None:
        self.refresh()
        while not self._stop.wait(self.interval):
            self.refresh()

    def events(self, start: date, end: date) -> list[dict]:
        """Everything between two IST dates (inclusive), merged and time-ordered."""
        t0 = datetime(start.year, start.month, start.day, tzinfo=IST).timestamp()
        t1 = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=IST).timestamp()
        with self._conn() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM econ_events WHERE ts>=? AND ts<=? ORDER BY ts", (t0, t1)).fetchall()]
        for r in rows:
            r["detail"] = ""
        gen = india_events(start, end) + fomc_events(start, end)
        # the feed already carries the Fed decision in its week: keep the feed's row, drop the generated one
        ff_fomc_days = {datetime.fromtimestamp(r["ts"], IST).date() for r in rows if r["country"] == "USD" and "federal funds" in r["title"].lower()}
        gen = [g for g in gen if not (g["title"].startswith("FOMC") and datetime.fromtimestamp(g["ts"], IST).date() in ff_fomc_days)]
        out = rows + gen
        out.sort(key=lambda e: (e["ts"], {"High": 0, "Medium": 1, "Low": 2, "Holiday": 3}.get(e["impact"], 4)))
        for e in out:
            e["flag"] = FLAGS.get(e["country"], "🌐")
            e["region"] = REGION.get(e["country"], e["country"])
            e["when"] = datetime.fromtimestamp(e["ts"], IST).strftime("%H:%M")
            e["date"] = datetime.fromtimestamp(e["ts"], IST).strftime("%Y-%m-%d")
        return out

    def high_impact(self, days: int) -> list[dict]:
        today = datetime.now(IST).date()
        return [e for e in self.events(today, today + timedelta(days=days)) if e["impact"] == "High" and e["country"] in ("INR", "USD")]


# ---------------------------------------------------------------------------
# The public page
# ---------------------------------------------------------------------------
from finch import _CSS as _BASE_CSS  # noqa: E402

_CSS = _BASE_CSS + r"""
.cal-top{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0 14px;font-family:var(--mono);font-size:11.5px}
.cal-top a.nav{border:1px solid var(--line-strong);padding:6px 12px;color:var(--muted)}.cal-top a.nav:hover{border-color:var(--gold);color:var(--gold)}
.cal-top .wk{font-family:var(--display);font-size:24px;text-transform:uppercase;letter-spacing:.02em;margin:0 6px}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px;font-family:var(--mono);font-size:10.5px}
.filters button{border:1px solid var(--line-strong);background:none;color:var(--muted);padding:5px 10px;cursor:pointer;letter-spacing:.06em}.filters button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.filters .sep{width:1px;background:var(--line-strong);margin:0 4px}
.day{margin:18px 0 6px;font-family:var(--display);font-size:20px;text-transform:uppercase;color:var(--gold-2);letter-spacing:.02em}.day small{font-family:var(--mono);font-size:11px;color:var(--faint);text-transform:none;letter-spacing:.06em;margin-left:10px}
.day.today{color:var(--gold)}.day.today::after{content:"TODAY";font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;background:var(--gold);color:#2a1a02;padding:1px 6px;margin-left:10px;vertical-align:middle}
table.cal{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px;margin:0}
table.cal td{padding:7px 8px;border-bottom:1px solid rgba(190,150,255,.1);vertical-align:top}
table.cal td.t{white-space:nowrap;color:var(--muted);width:64px}table.cal td.c{white-space:nowrap;width:48px}table.cal td.i{width:16px}
table.cal td.n{color:var(--text);font-family:var(--body);font-size:14px}table.cal td.n small{display:block;color:var(--faint);font-family:var(--mono);font-size:10.5px;margin-top:2px}
table.cal td.v{text-align:right;white-space:nowrap;width:74px;color:var(--muted)}table.cal td.v b{color:var(--text)}table.cal td.v.a b{color:var(--cyan)}
.imp{display:inline-block;width:10px;height:10px;border-radius:2px}.imp.High{background:var(--down)}.imp.Medium{background:var(--gold)}.imp.Low{background:var(--faint)}.imp.Holiday{background:transparent;border:1px solid var(--faint)}
tr.past td{opacity:.55}
.legend{display:flex;gap:16px;font-family:var(--mono);font-size:10.5px;color:var(--faint);margin:14px 0 0;flex-wrap:wrap}.legend .imp{vertical-align:middle;margin-right:5px}
.next{border:1px solid var(--gold);background:rgba(245,200,66,.06);padding:12px 16px;margin:0 0 18px;font-family:var(--mono);font-size:12px}.next b{font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold);display:block}
.faq h3{font-family:var(--display);font-size:20px;text-transform:uppercase;color:var(--gold-2);margin:22px 0 4px}.faq p{color:var(--muted);max-width:76ch}
.empty{color:var(--faint);font-family:var(--mono);font-size:12px;padding:10px 0}
@media (max-width:640px){table.cal td{padding:6px 4px}table.cal td.v{width:auto;font-size:11px}table.cal td.t{width:44px;font-size:11px}table.cal td.c{width:26px;font-size:0}table.cal td.c::first-letter{font-size:14px}table.cal td.n{font-size:12.5px}.cal-top .wk{font-size:19px}}
"""

_FAQ = """<section class="faq">
<h3>Why does an Indian trader watch US CPI or the Fed?</h3><p>Because NIFTY and BANKNIFTY open the next morning on whatever the US did overnight. A hot US CPI print or a hawkish Fed moves the dollar, US yields and FII flows, and the first fifteen minutes of the Indian session price all of that in. The high-impact rows here are the ones that show up as gap-ups and gap-downs.</p>
<h3>When is India's CPI released?</h3><p>The Ministry of Statistics releases CPI (and IIP) on the 12th of every month at 16:00 IST — after the cash market closes, so the reaction lands at the next open. WPI follows on the 14th at noon. GDP comes at the end of February, May, August and November. RBI's Monetary Policy Committee announces its decision at 10:00 IST on the last day of each bi-monthly meeting; FY 2026-27's remaining decisions are 7 October, 4 December and 5 February.</p>
<h3>What do the colours mean?</h3><p>Red is high impact — expect the market to move; amber medium; grey low. Forecast is the consensus estimate before the release, previous the last reading; when the feed reports the actual number it appears in cyan. All times are IST.</p>
<h3>How do options price these events?</h3><p>The option chain does it for you: the ATM straddle of the expiry that spans an event is the market's implied move across it. Finostat's <a href="/finch/implied-volatility">Finch course</a> explains vol crush and event pricing, the <a href="/brief">daily brief</a> prints the implied move every morning, and the terminal's EVENTS panel puts the straddle next to each date.</p>
<h3>Where does the data come from?</h3><p>Global releases and central-bank decisions come from Forex Factory's public calendar feed; Indian releases follow the published schedules of MOSPI, DPIIT, S&amp;P Global and the RBI's FY27 MPC calendar; the FOMC dates are the Federal Reserve's published calendar. Dates for rule-based Indian releases can shift around holidays — treat them as the normal schedule, not a guarantee.</p>
</section>"""


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def render(econ: Econ, anchor: date | None = None) -> bytes:
    today = datetime.now(IST).date()
    anchor = anchor or today
    monday = anchor - timedelta(days=anchor.weekday())
    sunday = monday + timedelta(days=6)
    events = econ.events(monday, sunday)
    upcoming = [e for e in econ.high_impact(30) if e["ts"] > time.time()]
    nxt = upcoming[0] if upcoming else None
    by_day: dict[str, list] = {}
    for e in events:
        by_day.setdefault(e["date"], []).append(e)
    now_ts = time.time()
    days_html = []
    for i in range(7):
        d = monday + timedelta(days=i)
        key = d.isoformat()
        rows = by_day.get(key, [])
        head = f'<div class="day{" today" if d == today else ""}">{d.strftime("%A")}<small>{d.strftime("%d %b %Y")}</small></div>'
        if not rows:
            days_html.append(head + '<div class="empty">no scheduled releases</div>')
            continue
        trs = "".join(
            f'<tr class="{"past" if e["ts"] < now_ts else ""}" data-impact="{_esc(e["impact"])}" data-country="{_esc(e["country"])}">'
            f'<td class="t">{e["when"]}</td><td class="c" title="{_esc(e["region"])}">{e["flag"]} {_esc(e["country"] if e["country"] != "All" else "")}</td>'
            f'<td class="i"><span class="imp {_esc(e["impact"])}" title="{_esc(e["impact"])} impact"></span></td>'
            f'<td class="n">{_esc(e["title"])}{("<small>" + _esc(e["detail"]) + "</small>") if e.get("detail") else ""}</td>'
            f'<td class="v{" a" if e["actual"] else ""}">{("<b>" + _esc(e["actual"]) + "</b>") if e["actual"] else ""}</td>'
            f'<td class="v">{("<b>" + _esc(e["forecast"]) + "</b>") if e["forecast"] else ""}</td><td class="v">{_esc(e["previous"])}</td></tr>'
            for e in rows)
        days_html.append(head + f'<div class="scrollx"><table class="cal"><thead><tr><th style="text-align:left;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">IST</th><th></th><th></th><th style="text-align:left;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">RELEASE</th><th style="text-align:right;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">ACTUAL</th><th style="text-align:right;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">FORECAST</th><th style="text-align:right;color:var(--faint);font-weight:500;font-size:10px;padding:4px 8px">PREVIOUS</th></tr></thead><tbody>{trs}</tbody></table></div>')
    prev_w, next_w = (monday - timedelta(days=7)).isoformat(), (monday + timedelta(days=7)).isoformat()
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Economic calendar — Finostat", "url": "https://finostat.com/calendar",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": {"@type": "Event", "name": f"{e['region']}: {e['title']}", "startDate": datetime.fromtimestamp(e["ts"], IST).isoformat(),
                               "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode", "eventStatus": "https://schema.org/EventScheduled",
                               "location": {"@type": "VirtualLocation", "url": "https://finostat.com/calendar"}, "organizer": {"@type": "Organization", "name": e["region"]}}}
                              for i, e in enumerate([x for x in events if x["impact"] == "High"][:40])]}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "When is India's CPI released?", "acceptedAnswer": {"@type": "Answer", "text": "MOSPI releases CPI and IIP on the 12th of every month at 16:00 IST (next working day if a holiday); WPI on the 14th at noon; GDP at the end of February, May, August and November."}},
        {"@type": "Question", "name": "When does the RBI announce its policy decision?", "acceptedAnswer": {"@type": "Answer", "text": "At 10:00 IST on the last day of each bi-monthly MPC meeting. Remaining FY 2026-27 decisions: 7 October 2026, 4 December 2026 and 5 February 2027."}},
        {"@type": "Question", "name": "Why does the Fed decision matter for NIFTY?", "acceptedAnswer": {"@type": "Answer", "text": "US rate decisions move the dollar, US yields and foreign flows overnight; NIFTY and BANKNIFTY open the next morning with that priced in."}}]}
    title = f"Economic Calendar — India & global: CPI, RBI policy, Fed decisions, PPI, GDP (week of {monday.strftime('%d %b %Y')}) | Finostat"
    desc = ("Free economic calendar for Indian traders in IST: India CPI, WPI, IIP, PMI, GDP and RBI monetary policy dates, plus US CPI, PPI, NFP, "
            "FOMC decisions, ECB, BoE, BoJ and China releases with forecast and previous.")
    nxt_html = (f'<div class="next"><small style="font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--faint)">NEXT HIGH-IMPACT RELEASE</small>'
                f'<b>{nxt["flag"]} {_esc(nxt["title"])}</b>{datetime.fromtimestamp(nxt["ts"], IST).strftime("%A %d %b · %H:%M IST")} · <span id="cd" data-ts="{nxt["ts"]}"></span></div>') if nxt else ""
    ld_json = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    faq_json = json.dumps(faq_ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    this_week = "" if monday <= today <= sunday else '<a class="nav" href="/calendar">this week</a>'
    updated = datetime.fromtimestamp(econ.fetched, IST).strftime("%d %b %H:%M") if econ.fetched else "—"
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow, max-image-preview:large">
<link rel="icon" href="/og.jpg"><link rel="canonical" href="https://finostat.com/calendar">
<meta property="og:type" content="website"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{_esc(title)}"><meta property="og:description" content="{_esc(desc)}"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com/calendar">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{ld_json}</script>
<script type="application/ld+json">{faq_json}</script>
<style>{_CSS}</style></head><body>
<header class="top"><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/brief">BRIEF</a><a href="/finch">FINCH</a><a href="/dashboard">TERMINAL</a><a href="/account?plan=desk">GET DESK</a></div></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · CALENDAR</nav>
<h1>Economic calendar</h1>
<p class="lede">Every release that moves Indian markets, in IST: India's CPI, WPI, IIP, PMI, GDP and RBI decisions alongside US CPI, PPI, jobs and the Fed, the ECB, BoE, BoJ and China. Free, updated hourly.</p>
{nxt_html}
<div class="cal-top"><a class="nav" href="/calendar?d={prev_w}">← previous week</a><span class="wk">{monday.strftime("%d %b")} – {sunday.strftime("%d %b %Y")}</span><a class="nav" href="/calendar?d={next_w}">next week →</a>{this_week}</div>
<div class="filters" id="filters"><button data-f="impact:High" class="on">HIGH</button><button data-f="impact:Medium" class="on">MEDIUM</button><button data-f="impact:Low">LOW</button><span class="sep"></span><button data-f="country:INR" class="on">🇮🇳 INDIA</button><button data-f="country:USD" class="on">🇺🇸 US</button><button data-f="country:EUR" class="on">🇪🇺 EURO</button><button data-f="country:GBP" class="on">🇬🇧 UK</button><button data-f="country:JPY" class="on">🇯🇵 JAPAN</button><button data-f="country:CNY" class="on">🇨🇳 CHINA</button><button data-f="country:other" class="on">OTHERS</button></div>
{"".join(days_html)}
<div class="legend"><span><i class="imp High"></i>high impact</span><span><i class="imp Medium"></i>medium</span><span><i class="imp Low"></i>low</span><span>times in IST · updated {updated}</span></div>
<p style="margin-top:22px"><a class="cta" href="/dashboard">See the implied move for each event on the terminal →</a> <a class="cta ghost" href="/brief">Today's expiry brief</a></p>
{_FAQ}
<p class="disc">Global releases via Forex Factory's public calendar feed. Indian release dates follow MOSPI, DPIIT, S&amp;P Global and RBI published schedules and may shift around holidays. Nothing here is investment advice.</p>
</main>
<script>
(function(){{
  var f=document.getElementById('filters'), state={{}}; try{{ state=JSON.parse(localStorage.getItem('fino_cal_f')||'{{}}'); }}catch(e){{}}
  var btns=f.querySelectorAll('button[data-f]'); Array.prototype.forEach.call(btns,function(b){{ var k=b.getAttribute('data-f'); if(k in state) b.classList.toggle('on',!!state[k]); }});
  function apply(){{ var on={{}}; Array.prototype.forEach.call(btns,function(b){{ on[b.getAttribute('data-f')]=b.classList.contains('on'); }});
    var known=['INR','USD','EUR','GBP','JPY','CNY'];
    Array.prototype.forEach.call(document.querySelectorAll('tr[data-impact]'),function(tr){{ var imp=tr.getAttribute('data-impact'), c=tr.getAttribute('data-country'); var okI=imp==='Holiday'?true:on['impact:'+imp]!==false; var ck=known.indexOf(c)>=0?'country:'+c:'country:other'; tr.hidden=!(okI&&on[ck]!==false); }});
    try{{ localStorage.setItem('fino_cal_f',JSON.stringify(on)); }}catch(e){{}} }}
  f.addEventListener('click',function(e){{ var b=e.target.closest('button[data-f]'); if(!b) return; b.classList.toggle('on'); apply(); }}); apply();
  var cd=document.getElementById('cd'); if(cd){{ var ts=Number(cd.getAttribute('data-ts')); function tick(){{ var s=Math.max(0,Math.floor(ts-Date.now()/1000)); var d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60); cd.textContent='in '+(d?d+'d ':'')+h+'h '+m+'m'; }} tick(); setInterval(tick,30000); }}
  setTimeout(function(){{ location.reload(); }}, 5*60*1000);
}})();
</script></body></html>"""
    return doc.encode("utf-8")
