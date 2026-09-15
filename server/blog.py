"""The content engine behind /blog.

Three kinds of posts:
- guides: evergreen explainers from blog_content.py (written once, listed forever)
- daily: "Options desk read" after the close on every trading day (18:30 IST, once FII/DII is out) —
  built from live data the site already has: index closes, the public chain (PCR, max pain, walls),
  OI build-up, expected vs realised move, straddle percentile, the gold engine, FII/DII, tomorrow's events
- weekly: "Week ahead" on Sundays (events, expiries, last week's flows) and "Weekly wrap" on Fridays

Everything is deterministic and sourced from data — no external model. Each post carries the
VIP Indicator / XAU Sovereign cards. Posts are stored in sqlite and served with Article schema + RSS."""
from __future__ import annotations

import html
import json
import logging
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta, timezone

import blog_content

log = logging.getLogger("finostat.blog")
IST = timezone(timedelta(hours=5, minutes=30))
_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts(
  slug     TEXT PRIMARY KEY,
  kind     TEXT NOT NULL,
  title    TEXT NOT NULL,
  summary  TEXT NOT NULL,
  tags     TEXT NOT NULL,
  body     TEXT NOT NULL,
  day      TEXT NOT NULL,
  created  REAL NOT NULL,
  updated  REAL NOT NULL
);
"""
DAILY_AT, WRAP_AT, AHEAD_AT = "18:30", "17:30", "18:00"


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _n(v, d=0) -> str:
    try:
        return f"{float(v):,.{d}f}"
    except (TypeError, ValueError):
        return "—"


def _sg(v, d=2) -> str:
    try:
        v = float(v)
        return ("+" if v > 0 else "") + f"{v:,.{d}f}"
    except (TypeError, ValueError):
        return "—"


CTA = ('<aside class="cta-grid">'
       '<a class="cta-card" href="/vip-indicator"><small>VIP INDICATOR · ₹12,999 ONCE</small><b>Three engines for Indian markets</b><span>Structure, Scalper and Seller on NIFTY, BANKNIFTY and every F&amp;O stock, with buy/sell markers, volume footprint and three Pine Scripts.</span></a>'
       '<a class="cta-card" href="/xau-sovereign"><small>XAU SOVEREIGN · ₹8,000 ONCE</small><b>The gold buy·sell engine</b><span>Nine published systems and smart-money price action on XAU/USD, 1H/4H/1D, with entry, stop and target.</span></a>'
       '<a class="cta-card" href="/dashboard"><small>DESK · ₹2,199 / 30 DAYS</small><b>The live terminal</b><span>Chains, Greeks, OISCAN, RISK board, MOVE, IVP and both engines, streaming.</span></a>'
       '</aside>')


# ---------------------------------------------------------------------------
# generators (pure: sources is a dict of callables, all optional)
# ---------------------------------------------------------------------------
def _src(sources: dict, name: str, *args):
    fn = sources.get(name)
    if not fn:
        return None
    try:
        return fn(*args)
    except Exception as exc:                                        # noqa: BLE001 - a missing source just drops its paragraph
        log.info("blog source %s failed: %s", name, exc)
        return None


def daily_read(sources: dict, day: date) -> dict | None:
    quotes = {q.get("symbol"): q for q in (_src(sources, "quotes") or [])}
    nifty, bank = quotes.get("NIFTY 50"), quotes.get("BANKNIFTY")
    if not nifty or not nifty.get("price"):
        return None
    pretty = day.strftime("%d %b %Y")
    parts = [f"<p class=\"lede\">The desk read for {pretty}: where NIFTY and BANKNIFTY closed, what the option chain, open interest and expected move said about it, "
             f"how gold's engine is leaning, and what tomorrow carries.</p>"]
    # closes
    rows = "".join(f"<tr><td>{_esc(s)}</td><td>{_n(q.get('price'), 1)}</td><td class=\"{'up' if (q.get('change') or 0) >= 0 else 'down'}\">{_sg(q.get('change'))}%</td></tr>"
                   for s, q in quotes.items() if s in ("NIFTY 50", "BANKNIFTY", "FINNIFTY", "SENSEX", "INDIA VIX") and q.get("price"))
    parts.append(f"<h2>The close</h2><table><thead><tr><th>Index</th><th>Close</th><th>Day</th></tr></thead><tbody>{rows}</tbody></table>")
    vix = quotes.get("INDIA VIX")
    tone = "a down day" if (nifty.get("change") or 0) < -0.5 else "an up day" if (nifty.get("change") or 0) > 0.5 else "a flat day"
    parts.append(f"<p>NIFTY finished at {_n(nifty['price'], 1)} ({_sg(nifty.get('change'))}%), {tone}"
                 + (f", with India VIX at {_n(vix['price'], 2)} ({_sg(vix.get('change'))}%)" if vix and vix.get("price") else "") + ".</p>")
    # chains
    for slug, label in (("nifty", "NIFTY"), ("banknifty", "BANKNIFTY")):
        ch = _src(sources, "chain", slug) or {}
        st = ch.get("stats") or {}
        if not st:
            continue
        parts.append(f"<h2>{label} option chain</h2><p>For the {_esc(ch.get('expiry') or 'nearest')} expiry the put–call ratio is <b>{_n(st.get('pcr'), 2)}</b>, max pain sits at <b>{_n(st.get('max_pain'))}</b>, "
                     f"the call wall is at <b>{_n(st.get('call_wall'))}</b> and the put wall at <b>{_n(st.get('put_wall'))}</b>"
                     + (f", ATM {_n(st.get('atm'))}" if st.get("atm") else "") + ". "
                     + ("Puts outnumber calls by open interest, a market that has bought protection." if (st.get("pcr") or 0) >= 1.2 else "Calls outnumber puts by open interest, a market leaning long." if (st.get("pcr") or 1) <= 0.7 else "Open interest is balanced between the two sides.")
                     + f" The live chain is free at <a href=\"/option-chain/{slug}\">/option-chain/{slug}</a>.</p>")
        oi = _src(sources, "oiscan", "NIFTY 50" if slug == "nifty" else "BANKNIFTY") or {}
        if oi.get("read") and oi["read"].get("text"):
            parts.append(f"<p><b>OI build-up on the day:</b> {_esc(oi['read']['text'])}. Call OI changed by {_sg(oi.get('ce_d'), 0)} contracts and put OI by {_sg(oi.get('pe_d'), 0)}; PCR moved from {_n(oi.get('pcr_then'), 2)} to {_n(oi.get('pcr'), 2)}.</p>")
        mv = _src(sources, "move", "NIFTY 50" if slug == "nifty" else "BANKNIFTY") or {}
        e, r, c = mv.get("expected") or {}, mv.get("realised") or {}, mv.get("compare") or {}
        if e.get("em_day") and r.get("range") is not None:
            parts.append(f"<p><b>Expected versus realised:</b> the ATM straddle implied a day move of about ±{_n(e['em_day'])} points; the realised range was {_n(r['range'])} points, "
                         f"{_n(c.get('range_vs_expected_pct'))}% of the expected range — {_esc(c.get('verdict') or '')}. The straddle to expiry was ₹{_n(e.get('em_expiry_straddle'), 1)} with ATM IV at {_n(e.get('iv'), 1)}%.</p>")
        ivp = _src(sources, "ivp", "NIFTY 50" if slug == "nifty" else "BANKNIFTY") or {}
        if ivp.get("pct_percentile") is not None:
            parts.append(f"<p><b>Premium:</b> the straddle sat at the {_n(ivp['pct_percentile'])}th percentile of the last {ivp.get('cycles', 20)} cycles at this time — {_esc(ivp.get('read') or '')}.</p>")
    # gold
    g = _src(sources, "gold") or {}
    if g:
        words = " · ".join(f"{tf.upper()} {v}" for tf, v in g.get("signals", {}).items() if v)
        parts.append(f"<h2>Gold</h2><p>XAU/USD at ${_n(g.get('spot'), 2)}" + (f" (≈ ₹{_n(g.get('inr_10g'))} per 10 g)" if g.get("inr_10g") else "") + ". "
                     + (f"<a href=\"/xau-sovereign\">XAU Sovereign</a> reads {words}." if words else "") + " Levels and the reasons behind each vote are inside the engine.</p>")
    # flows
    f = _src(sources, "flows") or {}
    if f.get("cash_date"):
        parts.append(f"<h2>FII / DII</h2><p>On {_esc(f['cash_date'])} FIIs were net ₹{_sg(f.get('fii_net'), 0)} crore and DIIs net ₹{_sg(f.get('dii_net'), 0)} crore in the cash market"
                     + (f"; FII index futures net {_sg(f.get('fii_fut'), 0)} contracts" if f.get("fii_fut") is not None else "") + ". History and participant positioning at <a href=\"/fii-dii\">/fii-dii</a>.</p>")
    # tomorrow
    ev = _src(sources, "events", 2) or []
    if ev:
        items = "".join(f"<li>{_esc(e.get('title'))} ({_esc(e.get('country'))}) — {_esc(e.get('date'))}{(' ' + _esc(e.get('when'))) if e.get('when') else ''}</li>" for e in ev[:6])
        parts.append(f"<h2>What tomorrow carries</h2><ul>{items}</ul><p>Full week in IST at <a href=\"/calendar\">/calendar</a>.</p>")
    parts.append("<p>Reads like this take a minute when the panels do the counting. The terminal's OISCAN, MOVE, IVP and RISK panels ran every number above live through the session, and the VIP Indicator's three engines mark the trades on the chart.</p>")
    tags = ["daily read", "nifty", "banknifty", "option chain"]
    title = f"Options desk read, {pretty}: NIFTY {_n(nifty['price'])} ({_sg(nifty.get('change'))}%), chain, OI and expected move"
    summary = f"NIFTY closed at {_n(nifty['price'], 1)} ({_sg(nifty.get('change'))}%). The option chain, OI build-up, expected versus realised move, premium percentile, gold engine and FII/DII for {pretty}."
    return {"slug": f"desk-read-{day.isoformat()}", "kind": "daily", "title": title, "summary": summary, "tags": tags, "body": "\n".join(parts), "day": day.isoformat()}


def week_ahead(sources: dict, day: date) -> dict | None:
    """Sunday post: the coming week's events, expiries and what last week's flows said."""
    ev = _src(sources, "events", 8) or []
    exps = _src(sources, "expiries") or []
    f = _src(sources, "flows_week") or {}
    mon = day + timedelta(days=(7 - day.weekday()) % 7 or 7) if day.weekday() != 0 else day
    pretty = mon.strftime("%d %b %Y")
    parts = [f"<p class=\"lede\">What the week of {pretty} carries: the events that move NIFTY, BANKNIFTY and gold, the expiries on the calendar, and how institutions were positioned going in.</p>"]
    if ev:
        items = "".join(f"<li><b>{_esc(e.get('date'))}{(' ' + _esc(e.get('when'))) if e.get('when') else ''}</b> — {_esc(e.get('title'))} ({_esc(e.get('country'))})</li>" for e in ev[:10])
        parts.append(f"<h2>Events</h2><ul>{items}</ul>")
    if exps:
        items = "".join(f"<li><b>{_esc(x.get('date'))}</b> — {_esc(x.get('label'))} {_esc(x.get('kind'))}{(' · ' + _esc(x.get('note'))) if x.get('note') else ''}</li>" for x in exps[:8])
        parts.append(f"<h2>Expiries</h2><ul>{items}</ul><p>Expiry-day plans start with the expected move and the straddle percentile; both are on the <a href=\"/brief\">morning brief</a> at 09:20.</p>")
    if f.get("fii_net") is not None:
        parts.append(f"<h2>Flows last week</h2><p>FIIs were net ₹{_sg(f['fii_net'], 0)} crore and DIIs net ₹{_sg(f.get('dii_net'), 0)} crore across the week. "
                     + ("Foreign selling absorbed by domestic buying is the classic tug-of-war; watch whether FII index futures shorts get covered on strength." if f["fii_net"] < 0 else "Foreign buying with domestic support is the setup for trend days; watch put writing follow price up.") + "</p>")
    parts.append("<h2>How to trade the week</h2><p>Sell premium only on days the regime checklist passes (no trend, calm width, mid-range, rich straddle, quiet tape); on event days stand aside until the number is out. The VIP Indicator's SELLER engine runs that checklist on every candle, and its STRUCTURE engine marks the levels that matter before the week starts.</p>")
    return {"slug": f"week-ahead-{mon.isoformat()}", "kind": "weekly", "title": f"Week ahead, {pretty}: events, expiries and flows for NIFTY, BANKNIFTY and gold", "summary": f"The events, expiries and institutional positioning that frame the week of {pretty}.",
            "tags": ["week ahead", "events", "expiry"], "body": "\n".join(parts), "day": day.isoformat()}


def weekly_wrap(sources: dict, day: date) -> dict | None:
    quotes = {q.get("symbol"): q for q in (_src(sources, "quotes") or [])}
    wk = _src(sources, "week_change") or {}
    if not wk and not quotes:
        return None
    pretty = day.strftime("%d %b %Y")
    parts = [f"<p class=\"lede\">The week to {pretty} in numbers: how the indices moved, what open interest did, where premium ended, and what the engines are saying into the weekend.</p>"]
    rows = "".join(f"<tr><td>{_esc(s)}</td><td>{_n(v.get('close'), 1)}</td><td class=\"{'up' if (v.get('pct') or 0) >= 0 else 'down'}\">{_sg(v.get('pct'))}%</td><td>{_n(v.get('high'))}–{_n(v.get('low'))}</td></tr>" for s, v in wk.items() if v.get("close"))
    if rows:
        parts.append(f"<h2>The week</h2><table><thead><tr><th>Index</th><th>Close</th><th>Week</th><th>Range</th></tr></thead><tbody>{rows}</tbody></table>")
    for slug, label, u in (("nifty", "NIFTY", "NIFTY 50"), ("banknifty", "BANKNIFTY", "BANKNIFTY")):
        st = (_src(sources, "chain", slug) or {}).get("stats") or {}
        if st:
            parts.append(f"<p><b>{label} into the weekend:</b> PCR {_n(st.get('pcr'), 2)}, max pain {_n(st.get('max_pain'))}, call wall {_n(st.get('call_wall'))}, put wall {_n(st.get('put_wall'))}.</p>")
    g = _src(sources, "gold") or {}
    if g:
        words = " · ".join(f"{tf.upper()} {v}" for tf, v in g.get("signals", {}).items() if v)
        parts.append(f"<h2>Gold</h2><p>XAU/USD ${_n(g.get('spot'), 2)}. {('XAU Sovereign reads ' + words + '.') if words else ''}</p>")
    f = _src(sources, "flows_week") or {}
    if f.get("fii_net") is not None:
        parts.append(f"<h2>Flows</h2><p>FIIs net ₹{_sg(f['fii_net'], 0)} crore and DIIs net ₹{_sg(f.get('dii_net'), 0)} crore for the week. Detail at <a href=\"/fii-dii\">/fii-dii</a>.</p>")
    parts.append("<p>Next week's events and expiries land in the Sunday <em>week ahead</em> post. Until then, the engines keep scoring every candle: the VIP Indicator on the indices and stocks, XAU Sovereign on gold.</p>")
    return {"slug": f"weekly-wrap-{day.isoformat()}", "kind": "weekly", "title": f"Weekly wrap, {pretty}: NIFTY, BANKNIFTY, gold and flows", "summary": f"How the indices, open interest, premium and flows finished the week to {pretty}.",
            "tags": ["weekly wrap", "nifty", "banknifty"], "body": "\n".join(parts), "day": day.isoformat()}


# ---------------------------------------------------------------------------
# store + scheduler
# ---------------------------------------------------------------------------
class Blog:
    def __init__(self, db_path, sources: dict | None = None, holidays=None, clock=None):
        self.path = db_path
        self.sources = sources or {}
        self.holidays = holidays
        self.clock = clock or (lambda: datetime.now(IST))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.last_run: dict = {}
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    # -- posts ------------------------------------------------------------------
    def put(self, post: dict) -> None:
        now = time.time()
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO posts(slug,kind,title,summary,tags,body,day,created,updated) VALUES(?,?,?,?,?,?,?,?,?) "
                      "ON CONFLICT(slug) DO UPDATE SET title=excluded.title, summary=excluded.summary, tags=excluded.tags, body=excluded.body, updated=excluded.updated",
                      (post["slug"], post["kind"], post["title"], post["summary"], json.dumps(post["tags"]), post["body"], post["day"], now, now))

    def get(self, slug: str) -> dict | None:
        g = next((x for x in blog_content.GUIDES if x["slug"] == slug), None)
        if g:
            return {**g, "kind": "guide", "day": "2026-09-15", "created": 0, "updated": 0}
        with self._conn() as c:
            r = c.execute("SELECT * FROM posts WHERE slug=?", (slug,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["tags"] = json.loads(d["tags"])
        return d

    def has(self, slug: str) -> bool:
        with self._conn() as c:
            return c.execute("SELECT 1 FROM posts WHERE slug=?", (slug,)).fetchone() is not None

    def recent(self, limit: int = 40, kind: str | None = None) -> list[dict]:
        with self._conn() as c:
            if kind:
                rows = c.execute("SELECT slug,kind,title,summary,tags,day,created FROM posts WHERE kind=? ORDER BY day DESC, created DESC LIMIT ?", (kind, limit)).fetchall()
            else:
                rows = c.execute("SELECT slug,kind,title,summary,tags,day,created FROM posts ORDER BY day DESC, created DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r); d["tags"] = json.loads(d["tags"]); out.append(d)
        return out

    def all_slugs(self) -> list[tuple[str, str]]:
        with self._conn() as c:
            rows = c.execute("SELECT slug, day FROM posts ORDER BY day DESC").fetchall()
        return [(g["slug"], "2026-09-15") for g in blog_content.GUIDES] + [(r["slug"], r["day"]) for r in rows]

    # -- generation ------------------------------------------------------------------
    def _trading_day(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        try:
            return not (self.holidays and d.isoformat() in self.holidays.dates())
        except Exception:                                           # noqa: BLE001
            return True

    def due(self, now: datetime | None = None) -> list[str]:
        """Which posts should exist by now and don't."""
        now = now or self.clock()
        d = now.date()
        hm = now.strftime("%H:%M")
        out = []
        if self._trading_day(d) and hm >= DAILY_AT and not self.has(f"desk-read-{d.isoformat()}"):
            out.append("daily")
        if d.weekday() == 4 and hm >= WRAP_AT and not self.has(f"weekly-wrap-{d.isoformat()}"):
            out.append("wrap")
        if d.weekday() == 6 and hm >= AHEAD_AT and not self.has(f"week-ahead-{(d + timedelta(days=1)).isoformat()}"):
            out.append("ahead")
        return out

    def run(self, kind: str, day: date | None = None) -> dict | None:
        day = day or self.clock().date()
        post = daily_read(self.sources, day) if kind == "daily" else weekly_wrap(self.sources, day) if kind == "wrap" else week_ahead(self.sources, day) if kind == "ahead" else None
        if post:
            self.put(post)
            self.last_run[kind] = (time.time(), post["slug"])
            log.info("blog: published %s", post["slug"])
        return post

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                for kind in self.due():
                    self.run(kind)
            except Exception as exc:                                # noqa: BLE001
                log.warning("blog loop: %s", exc)
            self._stop.wait(60)

    def start(self) -> None:
        threading.Thread(target=self._loop, name="blog", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
from finch import _CSS as _BASE_CSS  # noqa: E402

_CSS = _BASE_CSS + r"""
.bl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin:12px 0 24px}
.bl-card{border:1px solid var(--line-strong);background:var(--panel);padding:16px 18px;display:flex;flex-direction:column;gap:6px}.bl-card:hover{border-color:var(--gold)}
.bl-card small{font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;color:var(--faint);text-transform:uppercase}.bl-card b{font-family:var(--display);font-size:21px;line-height:1.05;text-transform:uppercase;color:var(--text)}.bl-card span{color:var(--muted);font-size:13px;line-height:1.5}
.bl-list{list-style:none;padding:0;margin:8px 0 24px}.bl-list li{padding:10px 0;border-bottom:1px solid rgba(190,150,255,.12)}.bl-list li a{font-family:var(--display);font-size:20px;text-transform:uppercase;color:var(--text)}.bl-list li a:hover{color:var(--gold)}.bl-list li small{display:block;font-family:var(--mono);font-size:10px;color:var(--faint);letter-spacing:.1em;margin-bottom:2px}.bl-list li span{display:block;color:var(--muted);font-size:13px;margin-top:3px}
article.post{max-width:78ch}article.post h1{font-family:var(--display);font-size:clamp(30px,5vw,48px);line-height:1;text-transform:uppercase;margin:6px 0 10px}
article.post h2{font-family:var(--display);font-size:24px;text-transform:uppercase;color:var(--gold-2);margin:26px 0 6px}article.post p{color:var(--muted);line-height:1.65;font-size:15.5px;margin:0 0 12px}article.post p b{color:var(--text)}article.post .lede{color:var(--text);font-size:17px}
article.post table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px;margin:8px 0 16px}article.post th{font-size:10px;letter-spacing:.1em;color:var(--faint);font-weight:500;padding:6px 8px;text-align:left;border-bottom:1px solid var(--line-strong)}article.post td{padding:6px 8px;border-bottom:1px solid rgba(190,150,255,.1)}
article.post ul{color:var(--muted);line-height:1.6;padding-left:20px;margin:0 0 12px}article.post a{color:var(--cyan)}article.post a:hover{color:var(--gold)}.up{color:var(--up)}.down{color:var(--down)}
.meta{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}.tags a{font-family:var(--mono);font-size:10px;letter-spacing:.08em;border:1px solid var(--line-strong);padding:2px 7px;margin-right:6px;color:var(--muted)}
.cta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:22px 0}.cta-card{border:1px solid var(--gold);background:var(--panel);padding:14px 16px;display:flex;flex-direction:column;gap:4px;color:var(--text);text-decoration:none;box-shadow:0 0 24px rgba(245,200,66,.08)}.cta-card:hover{background:var(--panel-hd)}
.cta-card small{font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;color:var(--gold)}.cta-card b{font-family:var(--display);font-size:20px;text-transform:uppercase;line-height:1.05}.cta-card span{color:var(--muted);font-size:12.5px;line-height:1.45}
.disc{border-left:2px solid var(--down);padding:8px 12px;color:var(--faint);font-size:12px;line-height:1.55;margin:24px 0}
"""

_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow, max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com{path}">
<link rel="alternate" type="application/rss+xml" title="Finostat blog" href="https://finostat.com/blog/feed.xml">
<meta property="og:type" content="{ogtype}"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com{path}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
{ld}
<style>{css}</style></head><body>
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a><a class="logo" href="/blog">FINO<b>·</b>BLOG</a><div class="r"><a href="/vip-indicator">VIP INDICATOR</a><a href="/xau-sovereign">GOLD</a><a href="/finch">FINCH</a><a href="/dashboard">TERMINAL</a></div></header>
<main class="wrap">"""
_FOOT = """<div class="disc">Finostat publishes market data and technical reads for education and research. Nothing here is investment advice or a recommendation to buy or sell any security; Finostat is not a SEBI-registered investment adviser. Trade at your own risk.</div></main></body></html>"""


def _ld(obj) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def render_index(blog: Blog) -> bytes:
    guides = "".join(f'<a class="bl-card" href="/blog/{g["slug"]}"><small>guide · {_esc(" · ".join(g["tags"][:2]))}</small><b>{_esc(g["title"])}</b><span>{_esc(g["summary"])}</span></a>' for g in blog_content.GUIDES)
    posts = blog.recent(40)
    items = "".join(f'<li><small>{_esc(p["kind"])} · {_esc(datetime.strptime(p["day"], "%Y-%m-%d").strftime("%d %b %Y"))}</small><a href="/blog/{p["slug"]}">{_esc(p["title"])}</a><span>{_esc(p["summary"])}</span></li>' for p in posts) or '<li><span>The first desk read publishes after the next close at 18:30 IST.</span></li>'
    ld = _ld({"@context": "https://schema.org", "@type": "Blog", "name": "Finostat blog", "url": "https://finostat.com/blog", "description": "Options trading guides and a daily desk read on NIFTY, BANKNIFTY and gold from Finostat.",
              "publisher": {"@type": "Organization", "name": "Finostat", "url": "https://finostat.com"}})
    doc = (_HEAD.format(title="Finostat blog — options trading guides and the daily desk read on NIFTY, BANKNIFTY and gold", desc="Evergreen guides on option chains, expected move, IV percentile, OI build-up, market structure and option selling, plus a daily desk read after every close and a week-ahead every Sunday.",
                        path="/blog", ogtype="website", ld=ld, css=_CSS)
           + '<nav class="crumb"><a href="/">FINO</a> · BLOG</nav><h1>Options, read like a desk</h1><p class="lede">Guides that explain one thing properly, and a daily read after the close built from the live chain, open interest, expected move, premium percentile, the gold engine and FII/DII. New every trading day at 18:30 IST; week ahead every Sunday.</p>'
           + CTA + '<h2 style="font-family:var(--display);font-size:24px;text-transform:uppercase;color:var(--gold-2);margin:20px 0 6px">Guides</h2><div class="bl-grid">' + guides + '</div>'
           + '<h2 style="font-family:var(--display);font-size:24px;text-transform:uppercase;color:var(--gold-2);margin:20px 0 6px">Desk reads &amp; weeklies</h2><ul class="bl-list">' + items + '</ul>'
           + '<p><a href="/blog/feed.xml" style="color:var(--cyan)">RSS feed</a></p>' + _FOOT)
    return doc.encode("utf-8")


def render_post(blog: Blog, slug: str) -> bytes | None:
    p = blog.get(slug)
    if not p:
        return None
    day = datetime.strptime(p["day"], "%Y-%m-%d")
    body = p["body"]
    # CTA in the middle (after the second h2) and at the end
    parts = body.split("<h2>")
    if len(parts) > 3:
        body = "<h2>".join(parts[:3]) + CTA + "<h2>" + "<h2>".join(parts[3:])
    ld = _ld({"@context": "https://schema.org", "@type": "Article", "headline": p["title"], "description": p["summary"], "datePublished": day.strftime("%Y-%m-%dT18:30:00+05:30"),
              "dateModified": datetime.fromtimestamp(p["updated"], IST).strftime("%Y-%m-%dT%H:%M:%S+05:30") if p.get("updated") else day.strftime("%Y-%m-%dT18:30:00+05:30"),
              "author": {"@type": "Organization", "name": "Finostat"}, "publisher": {"@type": "Organization", "name": "Finostat", "url": "https://finostat.com", "logo": {"@type": "ImageObject", "url": "https://finostat.com/logo.png"}},
              "mainEntityOfPage": f"https://finostat.com/blog/{slug}", "keywords": ", ".join(p["tags"]), "image": "https://finostat.com/og.jpg"})
    crumbs = _ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Blog", "item": "https://finostat.com/blog"}, {"@type": "ListItem", "position": 2, "name": p["title"], "item": f"https://finostat.com/blog/{slug}"}]})
    related = [g for g in blog_content.GUIDES if g["slug"] != slug][:4]
    rel = "".join(f'<li><a href="/blog/{g["slug"]}">{_esc(g["title"])}</a></li>' for g in related)
    doc = (_HEAD.format(title=_esc(p["title"]) + " | Finostat", desc=_esc(p["summary"]), path=f"/blog/{slug}", ogtype="article", ld=ld + crumbs, css=_CSS)
           + f'<nav class="crumb"><a href="/">FINO</a> · <a href="/blog">BLOG</a> · {_esc(p["kind"]).upper()}</nav><article class="post"><div class="meta">{_esc(p["kind"])} · {day.strftime("%d %b %Y")} · Finostat desk</div><h1>{_esc(p["title"])}</h1>'
           + body + CTA + '<div class="tags">' + "".join('<a href="/blog">' + _esc(t) + '</a>' for t in p["tags"]) + '</div>'
           + f'<h2>Keep reading</h2><ul>{rel}</ul></article>' + _FOOT)
    return doc.encode("utf-8")


def render_feed(blog: Blog) -> bytes:
    items = []
    for p in blog.recent(30):
        items.append(f"<item><title>{_esc(p['title'])}</title><link>https://finostat.com/blog/{p['slug']}</link><guid>https://finostat.com/blog/{p['slug']}</guid>"
                     f"<pubDate>{datetime.strptime(p['day'], '%Y-%m-%d').replace(hour=18, minute=30, tzinfo=IST).strftime('%a, %d %b %Y %H:%M:%S +0530')}</pubDate><description>{_esc(p['summary'])}</description></item>")
    for g in blog_content.GUIDES:
        items.append(f"<item><title>{_esc(g['title'])}</title><link>https://finostat.com/blog/{g['slug']}</link><guid>https://finostat.com/blog/{g['slug']}</guid><description>{_esc(g['summary'])}</description></item>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Finostat blog</title><link>https://finostat.com/blog</link>'
           '<description>Options trading guides and the daily desk read on NIFTY, BANKNIFTY and gold.</description>' + "".join(items) + "</channel></rss>")
    return xml.encode("utf-8")


def sitemap_entries(blog: Blog) -> str:
    out = ['  <url><loc>https://finostat.com/blog</loc><changefreq>daily</changefreq><priority>0.8</priority></url>']
    for slug, day in blog.all_slugs():
        out.append(f'  <url><loc>https://finostat.com/blog/{_esc(slug)}</loc><lastmod>{_esc(day)}</lastmod><priority>0.6</priority></url>')
    return "\n".join(out) + "\n"
