"""The daily expiry brief: /brief and /brief/YYYY-MM-DD.

Every trading day two snapshots of the index option chains are taken --
"open" at 09:20 IST and "close" at 15:35 IST -- and written up as a page:
spot, VIX, the ATM straddle as the market's implied move, skew, and four
strategies priced off the live chain. The close snapshot adds what actually
happened against what was priced. Everything is computed from data the
terminal already has; the prose is templated, deterministic and honest about
being so. Pages carry Article structured data (author: the founder).
"""
from __future__ import annotations

import html
import json
import logging
import pathlib
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import builder

log = logging.getLogger("finostat.brief")

IST = timezone(timedelta(hours=5, minutes=30))
UNDERLYINGS = ["NIFTY 50", "BANKNIFTY", "SENSEX"]      # first one is the headline
PRESETS = ["iron-condor", "short-strangle", "long-straddle", "bull-call-spread"]
OPEN_WINDOW = ((9, 20), (9, 45))                       # IST, inclusive start / exclusive end
CLOSE_WINDOW = ((15, 35), (16, 0))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs(
  date     TEXT PRIMARY KEY,
  open     TEXT,
  close    TEXT,
  updated  REAL NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Building a snapshot
# ---------------------------------------------------------------------------
def _quote(feed, symbol: str) -> dict | None:
    for q in feed.snapshot().get("quotes", []) or []:
        if q.get("symbol") == symbol:
            return q
    return None


def _warm_chain(chains, ukey: str, wait: float) -> dict | None:
    """First touch subscribes the strikes; poll until the prices have arrived."""
    deadline = time.monotonic() + wait
    chain = chains.chain(ukey)
    while "rows" in chain and chain.get("warming") and time.monotonic() < deadline:
        time.sleep(2.0)
        chain = chains.chain(ukey)
    return chain if "rows" in chain else None


def snapshot_underlying(feed, chains, ukey: str, wait: float = 40.0) -> dict | None:
    chain = _warm_chain(chains, ukey, wait)
    if chain is None:
        return None
    rows = chain["rows"]
    atm_row = next((r for r in rows if r.get("atm")), None)
    if not atm_row or not atm_row.get("ce") or not atm_row.get("pe"):
        return None
    spot, step, atm = chain["spot"], chain["step"], chain["atm"]
    ce, pe = atm_row["ce"], atm_row["pe"]
    straddle = round(ce["ltp"] + pe["ltp"], 2)
    by = {r["strike"]: r for r in rows}
    up2, dn2 = by.get(atm + 2 * step), by.get(atm - 2 * step)
    skew = None
    if up2 and dn2 and up2.get("ce") and dn2.get("pe") and up2["ce"].get("iv") and dn2["pe"].get("iv"):
        skew = round(dn2["pe"]["iv"] - up2["ce"]["iv"], 2)
    atm_iv = round(((ce.get("iv") or 0) + (pe.get("iv") or 0)) / 2, 2) if ce.get("iv") and pe.get("iv") else None
    q = _quote(feed, ukey) or {}
    strikes = [r["strike"] for r in rows]
    strategies = []
    for preset in PRESETS:
        legs = builder.preset_legs(preset, atm, step, strikes)
        if not legs:
            continue
        ivs, ok = {}, True
        for l in legs:
            side = by[l["strike"]].get(l["right"].lower())
            if not side:
                ok = False
                break
            l["price"] = side["ltp"]
            if side.get("iv"):
                ivs[(l["right"], l["strike"])] = side["iv"] / 100.0
        if not ok:
            continue
        m = builder.evaluate(spot, legs, chain["lot"], chain["t_years"], ivs)
        strategies.append({"preset": preset, "name": builder.PRESETS[preset][0],
                           "legs": [{k: l[k] for k in ("right", "strike", "qty", "price")} for l in legs],
                           "net_lot": round(m.get("net_premium_lot", 0), 0),
                           "max_profit_lot": m.get("max_profit_lot"), "max_loss_lot": m.get("max_loss_lot"),
                           "breakevens": [round(b, 0) for b in (m.get("breakevens") or [])],
                           "theta_lot": round(m["greeks"]["theta"] * chain["lot"], 0) if m.get("greeks") and m["greeks"].get("theta") is not None else None})
    days = max(0.0, chain["t_years"] * 365.0)
    return {
        "u": ukey, "spot": spot, "change": q.get("change"), "expiry": chain["expiry"], "days": round(days, 1),
        "lot": chain["lot"], "step": step, "atm": atm, "ce": ce["ltp"], "pe": pe["ltp"],
        "straddle": straddle, "move_pct": round(straddle / spot * 100.0, 2),
        "lo": round(spot - straddle, 0), "hi": round(spot + straddle, 0),
        "atm_iv": atm_iv, "skew": skew, "ce_delta": ce.get("delta"), "pe_delta": pe.get("delta"),
        "theta_lot": round(((ce.get("theta") or 0) + (pe.get("theta") or 0)) * chain["lot"], 0),
        "strategies": strategies, "live": bool(chain.get("live")),
        "oi": chain.get("oi"),
    }


def build(feed, chains, kind: str, when: datetime | None = None, wait: float = 40.0) -> dict:
    now = when or datetime.now(IST)
    for u in UNDERLYINGS:                              # subscribe all three, then let them warm together
        try:
            chains.chain(u)
        except Exception:
            pass
    out = {"date": now.strftime("%Y-%m-%d"), "kind": kind, "ts": time.time(), "at": now.strftime("%H:%M IST"),
           "live": bool(feed.snapshot().get("live")), "vix": (_quote(feed, "INDIA VIX") or {}).get("price"),
           "vix_change": (_quote(feed, "INDIA VIX") or {}).get("change"), "u": {}}
    for u in UNDERLYINGS:
        try:
            s = snapshot_underlying(feed, chains, u, wait)
        except Exception:
            log.exception("brief: %s failed", u)
            s = None
        if s:
            out["u"][u] = s
    return out


# ---------------------------------------------------------------------------
# Prose. Templated on purpose: the numbers are the content.
# ---------------------------------------------------------------------------
def _n(x, d=0) -> str:
    if x is None:
        return "—"
    return f"{x:,.{d}f}"


def _vix_read(v) -> str:
    if v is None:
        return ""
    if v < 11:
        return f"India VIX at {v:.2f} is low by any recent standard: premium is cheap, which favours buyers of options and punishes anyone selling them for 'income' at these levels."
    if v < 16:
        return f"India VIX at {v:.2f} is in its ordinary range: premium is fairly priced, and the edge comes from structure and sizing rather than from volatility being mispriced."
    if v < 22:
        return f"India VIX at {v:.2f} is elevated: the market is paying up for protection, which is the environment in which defined-risk premium selling is best paid — and in which naked selling gets hurt."
    return f"India VIX at {v:.2f} is high: options are expensive, moves are large, and the honest choice for most traders is smaller size or no position at all."


def _skew_read(s) -> str:
    if s is None:
        return ""
    if s > 2.5:
        return f"Skew is steep ({s:+.1f} IV points, puts over calls two strikes out): the crowd is paying for downside, so put spreads are richer to sell than call spreads."
    if s < -0.5:
        return f"Skew is inverted ({s:+.1f} IV points): calls are trading richer than puts, which usually means a chase for upside; call spreads carry the premium today."
    return f"Skew is mild ({s:+.1f} IV points): neither side of the chain is paying up, so structures can be built symmetric around spot."


def narrative(d: dict) -> list[str]:
    n = d["u"].get(UNDERLYINGS[0])
    if not n:
        return ["The NIFTY chain was not available when this brief was taken."]
    paras = []
    exp = datetime.fromtimestamp(n["expiry"] / 1000, IST).strftime("%d %b")
    chg = f", {n['change']:+.2f}% on the day" if n.get("change") is not None else ""
    paras.append(
        f"NIFTY is at {_n(n['spot'], 2)}{chg}. The {n['atm']} straddle for the {exp} expiry costs ₹{_n(n['straddle'], 2)} "
        f"({n['ce']:.2f} call + {n['pe']:.2f} put), which is the market pricing a one-standard-deviation move of about "
        f"±{_n(n['straddle'])} points, ±{n['move_pct']:.2f}%, over the {n['days']:.1f} days to expiry. Read that as the expected range: "
        f"{_n(n['lo'])} to {_n(n['hi'])}. Roughly two expiries in three should finish inside it; the third is where the money is made and lost.")
    v = _vix_read(d.get("vix"))
    s = _skew_read(n.get("skew"))
    if v or s:
        paras.append(" ".join(x for x in (v, s) if x))
    ic = next((x for x in n["strategies"] if x["preset"] == "iron-condor"), None)
    ss = next((x for x in n["strategies"] if x["preset"] == "short-strangle"), None)
    ls = next((x for x in n["strategies"] if x["preset"] == "long-straddle"), None)
    if ic and ss:
        paras.append(
            f"Priced off this chain, an iron condor collects ₹{_n(abs(ic['net_lot']))} a lot with a maximum loss of ₹{_n(abs(ic['max_loss_lot'] or 0))} "
            f"and breakevens at {' / '.join(_n(b) for b in ic['breakevens'])}. The short strangle underneath it collects ₹{_n(abs(ss['net_lot']))} — "
            f"₹{_n(abs(ss['net_lot']) - abs(ic['net_lot']))} more — for a loss that has no ceiling. That difference is the price of sleeping through a gap; "
            f"decide whether it is worth paying before the market decides for you.")
    if ls:
        paras.append(
            f"On the other side, the long straddle costs ₹{_n(abs(ls['net_lot']))} a lot and needs NIFTY beyond {' or '.join(_n(b) for b in ls['breakevens'])} at expiry to pay. "
            f"It bleeds about ₹{_n(abs(n['theta_lot']))} a day in time value right now. Buy it only if you expect the market to move more than it is charging for — "
            f"and know why.")
    oi = n.get("oi")
    if oi and oi.get("tot_ce"):
        walls = []
        if oi.get("call_wall"):
            walls.append(f"the largest call open interest above spot sits at {_n(oi['call_wall'])} — the strike writers are defending as resistance")
        if oi.get("put_wall"):
            walls.append(f"the largest put open interest below sits at {_n(oi['put_wall'])}, the floor")
        pcr = oi.get("pcr")
        pcr_read = ("a hedged, put-heavy book" if pcr and pcr > 1.2 else "a complacent, call-heavy book" if pcr and pcr < 0.7 else "a balanced book") if pcr is not None else ""
        paras.append(
            f"Open interest across the loaded strikes: {'; '.join(walls)}. " if walls else ""
            + (f"Put–call ratio {pcr:.2f} ({pcr_read}). " if pcr is not None else "")
            + (f"Max pain — the expiry price that leaves the most option value worthless — is {_n(oi['max_pain'])}." if oi.get("max_pain") else ""))
    others = [d["u"][u] for u in UNDERLYINGS[1:] if u in d["u"]]
    if others:
        bits = [f"{o['u']} {_n(o['spot'])} with a straddle of ₹{_n(o['straddle'])} (±{o['move_pct']:.2f}%, expiry {datetime.fromtimestamp(o['expiry'] / 1000, IST).strftime('%d %b')})" for o in others]
        paras.append("Elsewhere: " + "; ".join(bits) + ".")
    return paras


def close_narrative(o: dict, c: dict) -> list[str]:
    """What happened against what was priced at the open."""
    on, cn = o["u"].get(UNDERLYINGS[0]), c["u"].get(UNDERLYINGS[0])
    if not on or not cn:
        return []
    move = cn["spot"] - on["spot"]
    pct = move / on["spot"] * 100.0
    inside = abs(move) <= on["straddle"]
    paras = [
        f"NIFTY closed at {_n(cn['spot'], 2)}, {move:+,.0f} points ({pct:+.2f}%) from the {_n(on['spot'], 2)} it opened this brief at. "
        f"The open straddle priced ±{_n(on['straddle'])}; the day {'stayed inside' if inside else 'broke out of'} that range. "
        f"The {on['atm']} straddle itself went from ₹{_n(on['straddle'], 2)} to ₹{_n(cn['straddle'], 2)} — "
        f"{'time decay winning over movement' if cn['straddle'] < on['straddle'] else 'movement or volatility outrunning time decay'}."]
    if on.get("atm_iv") and cn.get("atm_iv"):
        paras.append(f"ATM implied volatility moved from {on['atm_iv']:.1f}% to {cn['atm_iv']:.1f}%" + (f"; India VIX from {o['vix']:.2f} to {c['vix']:.2f}." if o.get("vix") and c.get("vix") else "."))
    ss_o = next((x for x in on["strategies"] if x["preset"] == "short-strangle"), None)
    if ss_o and ss_o["breakevens"]:
        lo, hi = min(ss_o["breakevens"]), max(ss_o["breakevens"])
        paras.append(f"A short strangle put on at the open had breakevens of {_n(lo)} and {_n(hi)}; spot finished {'between them' if lo < cn['spot'] < hi else 'outside them'}. "
                     f"One day is not a track record — but this is exactly the comparison to keep a journal of.")
    return paras


# ---------------------------------------------------------------------------
# Storage and scheduling
# ---------------------------------------------------------------------------
class Briefs:
    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self._lock = threading.Lock()
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def put(self, date: str, kind: str, data: dict) -> None:
        col = "open" if kind == "open" else "close"
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO briefs(date,updated) VALUES(?,?) ON CONFLICT(date) DO NOTHING", (date, time.time()))
            c.execute(f"UPDATE briefs SET {col}=?, updated=? WHERE date=?", (json.dumps(data, separators=(",", ":")), time.time(), date))

    def get(self, date: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM briefs WHERE date=?", (date,)).fetchone()
        if r is None:
            return None
        return {"date": r["date"], "open": json.loads(r["open"]) if r["open"] else None,
                "close": json.loads(r["close"]) if r["close"] else None, "updated": r["updated"]}

    def dates(self, limit: int = 400) -> list[str]:
        with self._conn() as c:
            return [r[0] for r in c.execute("SELECT date FROM briefs ORDER BY date DESC LIMIT ?", (limit,))]

    def latest(self) -> dict | None:
        ds = self.dates(1)
        return self.get(ds[0]) if ds else None


def due(now: datetime, have_open: bool, have_close: bool, live: bool) -> str | None:
    """Which snapshot the scheduler should take at `now` (IST), if any."""
    if now.weekday() >= 5:
        return None
    hm = (now.hour, now.minute)
    if OPEN_WINDOW[0] <= hm < OPEN_WINDOW[1] and not have_open and live:
        return "open"
    if CLOSE_WINDOW[0] <= hm < CLOSE_WINDOW[1] and have_open and not have_close:
        return "close"
    return None


class Scheduler:
    """Takes the two daily snapshots; also honours a trigger file the operator
    can drop with admin.py (the feed lives only in the server process)."""

    def __init__(self, feed, chains, store: Briefs, trigger: pathlib.Path):
        self.feed, self.chains, self.store, self.trigger = feed, chains, store, pathlib.Path(trigger)
        self._stop = threading.Event()
        self.last: dict = {}

    def start(self) -> None:
        threading.Thread(target=self._run, name="brief", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def run_now(self, kind: str, date: str | None = None) -> dict:
        now = datetime.now(IST)
        data = build(self.feed, self.chains, kind, now)
        if date:
            data["date"] = date
        if data["u"]:
            self.store.put(data["date"], kind, data)
            log.info("brief: %s snapshot for %s (%d underlyings, live=%s)", kind, data["date"], len(data["u"]), data["live"])
        else:
            log.warning("brief: %s snapshot for %s produced no chains; not stored", kind, data["date"])
        self.last = {"kind": kind, "date": data["date"], "ts": time.time(), "ok": bool(data["u"])}
        return data

    def _run(self) -> None:
        while not self._stop.wait(30.0):
            try:
                if self.trigger.exists():
                    words = self.trigger.read_text().split()          # "open" | "close" [YYYY-MM-DD]
                    self.trigger.unlink()
                    kind = words[0] if words and words[0] in ("open", "close") else "open"
                    date = words[1] if len(words) > 1 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", words[1]) else None
                    self.run_now(kind, date)
                    continue
                now = datetime.now(IST)
                today = self.store.get(now.strftime("%Y-%m-%d"))
                kind = due(now, bool(today and today["open"]), bool(today and today["close"]),
                           bool(self.feed.snapshot().get("live")))
                if kind:
                    self.run_now(kind)
            except Exception:
                log.exception("brief scheduler")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
from finch import _CSS as _BASE_CSS  # noqa: E402

_CSS = _BASE_CSS + r"""
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0 22px}
.kpis div{border:1px solid var(--line-strong);background:var(--panel);padding:12px 14px}
.kpis small{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.kpis b{font-family:var(--display);font-size:28px;font-weight:600;line-height:1.1;color:var(--gold)}.kpis b i{font-style:normal;font-size:15px;color:var(--muted)}
.kpis .sub{font-family:var(--mono);font-size:11px;color:var(--muted);margin-top:2px}
.stamp{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin:0 0 6px}
.stamp b{color:var(--up)}.stamp b.off{color:var(--faint)}
.strat{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px;margin:8px 0 18px}
.strat th{text-align:left;color:var(--cyan);font-weight:500;font-size:10.5px;letter-spacing:.1em;padding:7px 8px;border-bottom:1px solid var(--line-strong)}
.strat td{padding:7px 8px;border-bottom:1px solid rgba(190,150,255,.1);vertical-align:top}
.strat td:first-child{color:var(--gold)}.strat .legs{color:var(--muted);font-size:11px}
.archive{columns:2;column-gap:24px;font-family:var(--mono);font-size:12.5px;max-width:520px}.archive li{margin:0 0 6px;list-style:none}
.archive a{color:var(--muted)}.archive a:hover{color:var(--gold)}.archive small{color:var(--faint)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0 18px}
@media(max-width:700px){.two{grid-template-columns:1fr}.archive{columns:1}}
"""

_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title><meta name="description" content="__DESC__"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow, max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com__PATH__">
<meta property="og:type" content="article"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="__TITLE__"><meta property="og:description" content="__DESC__"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com__PATH__">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
__LD__<style>__CSS__</style></head><body>
<header class="top"><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/brief">BRIEF</a><a href="/finch">FINCH</a><a href="/dashboard">TERMINAL</a><a href="/founders">FOUNDER</a></div><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="34" height="34"></a></header>
<main class="wrap">"""

_FOOT = """<p class="disc">The expiry brief is generated by Finostat's server from its live option chains at fixed times and written up from templates; it is education and market description, not a recommendation. Prices are indicative and can be stale. Derivatives can lose more than you put in. Finostat is not a SEBI-registered adviser.</p>
</main></body></html>"""

_AUTHOR = {"@type": "Person", "@id": "https://finostat.com/founders#person", "name": "Zico Karmakar", "url": "https://finostat.com/founders"}
_PUB = {"@type": "Organization", "@id": "https://finostat.com/#org", "name": "Finostat", "url": "https://finostat.com/", "logo": {"@type": "ImageObject", "url": "https://finostat.com/og.jpg"}}


def _ld(obj) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _pretty(date: str) -> str:
    return datetime.strptime(date, "%Y-%m-%d").strftime("%A, %d %B %Y")


def _money(v) -> str:
    return "unlimited" if v is None else f"₹{abs(v):,.0f}"


def _kpis(n: dict, vix) -> str:
    exp = datetime.fromtimestamp(n["expiry"] / 1000, IST).strftime("%d %b")
    chg = f'<div class="sub {"up" if (n.get("change") or 0) >= 0 else "down"}">{n["change"]:+.2f}% today</div>' if n.get("change") is not None else ""
    return (f'<div class="kpis"><div><small>NIFTY spot</small><b>{_n(n["spot"], 2)}</b>{chg}</div>'
            f'<div><small>{n["atm"]} straddle · {exp}</small><b>₹{_n(n["straddle"], 2)}</b><div class="sub">{n["ce"]:.2f} CE + {n["pe"]:.2f} PE</div></div>'
            f'<div><small>Implied move</small><b>±{n["move_pct"]:.2f}<i>%</i></b><div class="sub">±{_n(n["straddle"])} pts · {n["days"]:.1f} days</div></div>'
            f'<div><small>Expected range</small><b style="font-size:20px">{_n(n["lo"])} – {_n(n["hi"])}</b><div class="sub">spot ± straddle</div></div>'
            f'<div><small>ATM IV</small><b>{_n(n["atm_iv"], 1)}<i>%</i></b><div class="sub">skew {n["skew"]:+.1f} pts</div></div>'
            f'<div><small>India VIX</small><b>{_n(vix, 2)}</b></div>'
            + (f'<div><small>PCR · max pain</small><b>{_n(n["oi"]["pcr"], 2)}<i> · {_n(n["oi"]["max_pain"])}</i></b></div>'
               f'<div><small>OI walls</small><b style="font-size:20px">{_n(n["oi"]["put_wall"])} / {_n(n["oi"]["call_wall"])}</b><div class="sub">put floor / call ceiling</div></div>'
               if n.get("oi") and n["oi"].get("tot_ce") else "")
            + '</div>')


def _strats(n: dict) -> str:
    def leg(l):
        return f'{"+" if l["qty"] > 0 else "−"}{abs(l["qty"])} {l["strike"]} {l["right"]} @ {l["price"]:.2f}'
    rows = "".join(
        f'<tr><td>{_esc(s["name"])}<div class="legs">{" · ".join(leg(l) for l in s["legs"])}</div></td>'
        f'<td>{"credit" if s["net_lot"] >= 0 else "debit"} ₹{abs(s["net_lot"]):,.0f}</td><td class="up">{_money(s["max_profit_lot"])}</td><td class="down">{_money(s["max_loss_lot"])}</td>'
        f'<td>{" / ".join(_n(b) for b in s["breakevens"])}</td></tr>'
        for s in n["strategies"])
    return (f'<div class="scrollx"><table class="strat"><thead><tr><th>Structure · legs (per share)</th><th>Net / lot</th><th>Max profit</th><th>Max loss</th><th>Breakevens</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p><a class="cta ghost" href="/dashboard#p-builder">Re-price any of these live in the builder →</a></p>')


def _section(d: dict, label: str) -> str:
    n = d["u"].get(UNDERLYINGS[0])
    if not n:
        return f'<h2>{label}</h2><p>The NIFTY chain was not available for this snapshot.</p>'
    live = '<b>LIVE</b>' if d.get("live") else '<b class="off">LAST TRADED</b>'
    paras = "".join(f"<p>{_esc(p)}</p>" for p in narrative(d))
    return (f'<h2>{label}</h2><p class="stamp">Taken {d["at"]} · {live}</p>{_kpis(n, d.get("vix"))}{paras}'
            f'<h3>Strategies priced off this chain · NIFTY · lot {n["lot"]}</h3>{_strats(n)}')


def _others(d: dict) -> str:
    cells = []
    for u in UNDERLYINGS[1:]:
        o = d["u"].get(u)
        if not o:
            continue
        exp = datetime.fromtimestamp(o["expiry"] / 1000, IST).strftime("%d %b")
        cells.append(f'<div class="kpis" style="margin:0"><div><small>{_esc(u)}</small><b>{_n(o["spot"], 2)}</b></div><div><small>{o["atm"]} straddle · {exp}</small><b>₹{_n(o["straddle"], 2)}</b><div class="sub">±{o["move_pct"]:.2f}% · {o["days"]:.1f} days</div></div><div><small>ATM IV</small><b>{_n(o["atm_iv"], 1)}<i>%</i></b></div></div>')
    return f'<h3>BANKNIFTY and SENSEX</h3><div class="two">{"".join(cells)}</div>' if cells else ""


def title_for(rec: dict) -> tuple[str, str]:
    d = rec.get("open") or rec.get("close")
    n = d["u"].get(UNDERLYINGS[0]) if d else None
    date = _pretty(rec["date"])
    if not n:
        return f"NIFTY expiry brief — {date} | Finostat", f"Finostat's daily expiry brief for {date}."
    return (f"NIFTY expected move today ±{n['move_pct']:.2f}% — expiry brief, {date} | Finostat",
            f"NIFTY {_n(n['spot'])}: the {n['atm']} straddle at ₹{_n(n['straddle'])} prices a ±{_n(n['straddle'])}-point move ({_n(n['lo'])}–{_n(n['hi'])}). "
            f"India VIX {_n(d.get('vix'), 2)}, ATM IV {_n(n['atm_iv'], 1)}%, four strategies priced off the live chain.")


def render_day(store: Briefs, date: str, extra: str = "", extra_css: str = "") -> bytes | None:
    rec = store.get(date)
    if rec is None or not (rec["open"] or rec["close"]):
        return None
    title, desc = title_for(rec)
    ld = _ld({"@context": "https://schema.org", "@type": "Article", "@id": f"https://finostat.com/brief/{date}", "mainEntityOfPage": f"https://finostat.com/brief/{date}",
              "headline": title.split(" | ")[0], "description": desc, "author": _AUTHOR, "publisher": _PUB,
              "datePublished": date, "dateModified": datetime.fromtimestamp(rec["updated"], IST).strftime("%Y-%m-%dT%H:%M:%S+05:30"),
              "inLanguage": "en-IN", "isAccessibleForFree": True, "image": "https://finostat.com/og.jpg", "isPartOf": {"@id": "https://finostat.com/brief"}})
    body = [f'<nav class="crumb"><a href="/">FINO</a> · <a href="/brief">BRIEF</a> · {date}</nav><h1>Expiry brief · {_esc(_pretty(date))}</h1>',
            '<p class="lede">What the NIFTY option chain is pricing today, in numbers a trader can act on: the straddle as the expected move, volatility, skew, and four structures priced live. Written by the server at fixed times, every trading day.</p>']
    if extra:
        body.append(extra)
    if rec["open"]:
        body.append(_section(rec["open"], "At the open · 09:20 IST"))
        body.append(_others(rec["open"]))
    if rec["close"]:
        body.append(_section(rec["close"], "At the close · 15:35 IST"))
        if rec["open"]:
            body.append("<h3>What happened against what was priced</h3>" + "".join(f"<p>{_esc(p)}</p>" for p in close_narrative(rec["open"], rec["close"])))
        body.append(_others(rec["close"]))
    dates = store.dates(60)
    i = dates.index(date) if date in dates else -1
    prev_ = dates[i + 1] if 0 <= i < len(dates) - 1 else None
    next_ = dates[i - 1] if i > 0 else None
    pager = '<div class="pager">' + (f'<a href="/brief/{prev_}"><small>← Earlier</small>{_pretty(prev_)}</a>' if prev_ else '<span></span>') \
            + (f'<a href="/brief/{next_}" style="text-align:right"><small>Later →</small>{_pretty(next_)}</a>' if next_ else '<a href="/brief" style="text-align:right"><small>Archive →</small>All briefs</a>') + '</div>'
    body.append(pager + '<p style="margin-top:22px"><a class="cta" href="/finch/option-pricing">Why the straddle is the expected move — Finch, chapter 6 →</a></p>')
    doc = (_HEAD.replace("__TITLE__", _esc(title)).replace("__DESC__", _esc(desc)).replace("__PATH__", f"/brief/{date}").replace("__LD__", ld).replace("__CSS__", _CSS + extra_css))
    return (doc + "".join(body) + _FOOT).encode("utf-8")


def render_index(store: Briefs) -> bytes:
    dates = store.dates(400)
    latest = store.get(dates[0]) if dates else None
    body = ['<nav class="crumb"><a href="/">FINO</a> · BRIEF</nav><h1>The expiry brief</h1>',
            '<p class="lede">Every trading day at 09:20 and 15:35 IST, Finostat reads its own option chains and writes down what the market is pricing: NIFTY\'s expected move from the ATM straddle, India VIX, skew, and four strategies with exact breakevens and max loss. No opinions — the numbers, and what they mean.</p>']
    if latest:
        d = latest["close"] or latest["open"]
        n = d["u"].get(UNDERLYINGS[0])
        if n:
            body.append(f'<h2>Latest · {_esc(_pretty(latest["date"]))}</h2><p class="stamp">{"close" if latest["close"] else "open"} snapshot · {d["at"]}</p>{_kpis(n, d.get("vix"))}'
                        f'<p>{_esc(narrative(d)[0])}</p><p><a class="cta" href="/brief/{latest["date"]}">Read the full brief →</a></p>')
    if dates:
        items = "".join(f'<li><a href="/brief/{x}">{_esc(_pretty(x))}</a></li>' for x in dates)
        body.append(f'<h2>Archive</h2><ul class="archive">{items}</ul>')
    else:
        body.append('<h2>Archive</h2><p>The first brief is written on the next trading day at 09:20 IST.</p>')
    body.append('<h3>How to use it</h3><p>Compare the implied move with what you expect. If the straddle is pricing ±0.8% and you think a result or an RBI decision makes ±1.5% plausible, the long side is cheap; if the range looks generous for a dull week, defined-risk selling is being paid. Then open the <a href="/dashboard#p-builder">builder</a>, size for the worst plausible loss, and journal the comparison — <a href="/finch/option-pricing">Finch chapter 6</a> explains the straddle rule, <a href="/finch/risk-and-position-sizing">chapter 11</a> the sizing.</p>')
    ld = _ld({"@context": "https://schema.org", "@type": "CollectionPage", "@id": "https://finostat.com/brief", "url": "https://finostat.com/brief",
              "name": "Finostat expiry brief — NIFTY expected move, daily", "author": _AUTHOR, "publisher": _PUB, "inLanguage": "en-IN",
              "hasPart": [{"@type": "Article", "url": f"https://finostat.com/brief/{x}"} for x in dates[:50]]})
    doc = (_HEAD.replace("__TITLE__", "NIFTY expiry brief — expected move, VIX, skew and live-priced strategies, every trading day | Finostat")
           .replace("__DESC__", "Finostat's daily expiry brief: NIFTY's expected move from the ATM straddle, India VIX, skew and four strategies priced off the live option chain, at 09:20 and 15:35 IST.")
           .replace("__PATH__", "/brief").replace("__LD__", ld).replace("__CSS__", _CSS))
    return (doc + "".join(body) + _FOOT).encode("utf-8")


def sitemap_entries(store: Briefs) -> str:
    out = ['  <url><loc>https://finostat.com/brief</loc><changefreq>daily</changefreq><priority>0.9</priority></url>']
    for x in store.dates(400):
        out.append(f'  <url><loc>https://finostat.com/brief/{x}</loc><lastmod>{x}</lastmod><priority>0.8</priority></url>')
    return "\n".join(out) + "\n"
