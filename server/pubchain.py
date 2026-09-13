"""Public option chain pages (/option-chain/nifty, /banknifty, /finnifty) from NSE's own public
chain endpoint, refreshed every few minutes. Open interest, change in OI, volume, IV and last
price per strike, plus PCR, max pain and the OI walls. This is NSE's delayed public data, so it
can be shown to anyone; the paid terminal keeps Upstox's licensed live feed and the Greeks.
"""
from __future__ import annotations

import html
import http.cookiejar
import json
import logging
import pathlib
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

log = logging.getLogger("finostat.pubchain")
IST = timezone(timedelta(hours=5, minutes=30))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
HOME = "https://www.nseindia.com/option-chain"
INFO_URL = "https://www.nseindia.com/api/option-chain-contract-info?symbol={sym}"
CHAIN_URL = "https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={sym}&expiry={exp}"
SYMBOLS = {"nifty": ("NIFTY", "NIFTY 50", 50), "banknifty": ("BANKNIFTY", "BANKNIFTY", 100), "finnifty": ("FINNIFTY", "FINNIFTY", 50)}
WINDOW = 15            # strikes either side of ATM on the page


def _side(o: dict | None) -> dict | None:
    if not o:
        return None
    ltp = o.get("lastPrice")
    return {"oi": int(o.get("openInterest") or 0), "oi_chg": int(o.get("changeinOpenInterest") or 0), "vol": int(o.get("totalTradedVolume") or 0),
            "iv": float(o.get("impliedVolatility") or 0) or None, "ltp": float(ltp) if ltp not in (None, "") else None,
            "chg": float(o.get("change") or 0), "pchg": float(o.get("pChange") or 0), "bid": o.get("buyPrice1"), "ask": o.get("sellPrice1")}


def normalize(payload: dict) -> dict:
    """NSE option-chain-v3 -> {spot, ts, expiry, rows:[{strike, ce, pe}]}."""
    rec = payload.get("records") or {}
    rows = []
    for r in rec.get("data") or []:
        try:
            k = int(round(float(r.get("strikePrice", 0))))
        except (TypeError, ValueError):
            continue
        rows.append({"strike": k, "ce": _side(r.get("CE")), "pe": _side(r.get("PE"))})
    rows.sort(key=lambda x: x["strike"])
    spot = rec.get("underlyingValue")
    if not spot:
        # no spot in the payload: the strike where call and put prices cross is the money
        cands = [(abs((r["ce"] or {}).get("ltp") or 0 - ((r["pe"] or {}).get("ltp") or 0)), r["strike"]) for r in rows
                 if r["ce"] and r["pe"] and r["ce"].get("ltp") and r["pe"].get("ltp")]
        spot = min(cands)[1] if cands else None
    return {"spot": float(spot) if spot else None, "ts": rec.get("timestamp"), "expiry": (rec.get("data") or [{}])[0].get("expiryDates") if rec.get("data") else None, "rows": rows}


def stats(rows: list[dict], spot: float | None) -> dict:
    ce = [(r["strike"], r["ce"]["oi"]) for r in rows if r["ce"]]
    pe = [(r["strike"], r["pe"]["oi"]) for r in rows if r["pe"]]
    tot_ce, tot_pe = sum(o for _, o in ce), sum(o for _, o in pe)
    strikes = sorted({k for k, _ in ce} | {k for k, _ in pe})
    pain = min(strikes, key=lambda s: sum(o * max(s - k, 0) for k, o in ce) + sum(o * max(k - s, 0) for k, o in pe)) if strikes and (tot_ce or tot_pe) else None
    above = [(k, o) for k, o in ce if spot and k >= spot]
    below = [(k, o) for k, o in pe if spot and k <= spot]
    atm = min(strikes, key=lambda k: abs(k - spot)) if strikes and spot else None
    chg_ce = sum(r["ce"]["oi_chg"] for r in rows if r["ce"])
    chg_pe = sum(r["pe"]["oi_chg"] for r in rows if r["pe"])
    return {"pcr": round(tot_pe / tot_ce, 2) if tot_ce else None, "max_pain": pain, "atm": atm,
            "call_wall": max(above, key=lambda x: x[1])[0] if above else None, "put_wall": max(below, key=lambda x: x[1])[0] if below else None,
            "tot_ce": tot_ce, "tot_pe": tot_pe, "chg_ce": chg_ce, "chg_pe": chg_pe, "max_oi": max([o for _, o in ce + pe] or [0]),
            "iv_atm": next((r["ce"]["iv"] for r in rows if r["strike"] == atm and r["ce"] and r["ce"].get("iv")), None)}


STOCK_TTL = 300        # seconds a stock chain is served from cache before NSE is asked again
CHAIN_URL_EQ = "https://www.nseindia.com/api/option-chain-v3?type=Equity&symbol={sym}&expiry={exp}"


class PublicChains:
    def __init__(self, cache_dir: pathlib.Path, holidays=None, clock=None, contracts_of=None):
        self.cache_dir, self.holidays, self.clock = pathlib.Path(cache_dir), holidays, clock or (lambda: datetime.now(IST))
        self.contracts_of = contracts_of or (lambda: None)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._fetch_gate = threading.Semaphore(2)               # crawlers hitting 180 stock pages must not become 180 NSE calls at once
        self.data: dict[str, dict] = {}
        self.stocks: dict[str, dict] = {}
        self.error: str | None = None
        self._expiries: dict[str, tuple[float, list[str]]] = {}
        for slug in SYMBOLS:
            f = self.cache_dir / f"pubchain_{slug}.json"
            try:
                if f.exists():
                    self.data[slug] = json.loads(f.read_text())
            except (OSError, ValueError):
                pass

    def _opener(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
        op.open(urllib.request.Request(HOME, headers=h), timeout=20).read(2000)
        return op, dict(h, Accept="application/json", Referer=HOME)

    def _get(self, op, h, url):
        r = op.open(urllib.request.Request(url, headers=h), timeout=25)
        return json.loads(r.read().decode("utf-8"))

    def expiries(self, op, h, sym: str) -> list[str]:
        hit = self._expiries.get(sym)
        if hit and time.time() - hit[0] < 6 * 3600:
            return hit[1]
        info = self._get(op, h, INFO_URL.format(sym=sym))
        exps = info.get("expiryDates") or (info.get("data") or {}).get("expiryDates") or []
        self._expiries[sym] = (time.time(), exps)
        return exps

    def fetch(self, slug: str, op=None, h=None) -> dict:
        sym, label, step = SYMBOLS[slug]
        if op is None:
            op, h = self._opener()
        exps = self.expiries(op, h, sym)
        today = self.clock().date()
        live = [e for e in exps if datetime.strptime(e, "%d-%b-%Y").date() >= today] or exps
        exp = live[0]
        payload = self._get(op, h, CHAIN_URL.format(sym=sym, exp=urllib.parse.quote(exp)))
        n = normalize(payload)
        st = stats(n["rows"], n["spot"])
        out = {"slug": slug, "symbol": sym, "label": label, "step": step, "expiry": exp, "expiries": live[:6], "spot": n["spot"], "nse_ts": n["ts"],
               "fetched": time.time(), "rows": n["rows"], "stats": st}
        with self._lock:
            self.data[slug] = out
        try:
            (self.cache_dir / f"pubchain_{slug}.json").write_text(json.dumps(out, separators=(",", ":")))
        except OSError:
            pass
        return out

    # -- stocks: fetched when a page asks, cached a few minutes ----------------
    def fo_stocks(self) -> list[str]:
        ci = self.contracts_of()
        try:
            return ci.stock_names() if ci else []
        except Exception:                                           # noqa: BLE001
            return []

    def lots(self) -> dict[str, int]:
        ci = self.contracts_of()
        try:
            return ci.lots() if ci else {}
        except Exception:                                           # noqa: BLE001
            return {}

    def is_stock(self, sym: str) -> bool:
        return sym.upper() in set(self.fo_stocks())

    def stock(self, sym: str) -> dict | None:
        """Chain for an F&O stock; NSE is asked at most once per STOCK_TTL, stale data served on failure."""
        sym = sym.upper()
        with self._lock:
            hit = self.stocks.get(sym)
        if hit and time.time() - hit["fetched"] < STOCK_TTL:
            return hit
        if not self.is_stock(sym):
            return hit
        with self._fetch_gate:
            with self._lock:                                        # another request may have filled it while we waited
                hit = self.stocks.get(sym)
            if hit and time.time() - hit["fetched"] < STOCK_TTL:
                return hit
            try:
                op, h = self._opener()
                exps = self.expiries(op, h, sym)
                today = self.clock().date()
                live = [e for e in exps if datetime.strptime(e, "%d-%b-%Y").date() >= today] or exps
                if not live:
                    return hit
                payload = self._get(op, h, CHAIN_URL_EQ.format(sym=sym, exp=urllib.parse.quote(live[0])))
                n = normalize(payload)
                ks = sorted({r["strike"] for r in n["rows"]})
                step = min((b - a for a, b in zip(ks, ks[1:]) if b > a), default=0)
                out = {"slug": sym.lower(), "symbol": sym, "label": sym, "step": step, "expiry": live[0], "expiries": live[:4], "spot": n["spot"], "nse_ts": n["ts"],
                       "fetched": time.time(), "rows": n["rows"], "stats": stats(n["rows"], n["spot"]), "lot": self.lots().get(sym)}
                with self._lock:
                    self.stocks[sym] = out
                return out
            except Exception as exc:                                # noqa: BLE001
                log.info("stock chain %s failed: %s", sym, exc)
                return hit

    def refresh(self) -> bool:
        ok = True
        try:
            op, h = self._opener()
        except Exception as exc:                                    # noqa: BLE001
            self.error = f"nse: {str(exc)[:120]}"
            return False
        for slug in SYMBOLS:
            try:
                self.fetch(slug, op, h)
                time.sleep(0.5)
            except Exception as exc:                                # noqa: BLE001
                ok = False
                self.error = f"{slug}: {str(exc)[:120]}"
                log.info("public chain %s failed: %s", slug, exc)
        if ok:
            self.error = None
        return ok

    def _in_session(self) -> bool:
        now = self.clock()
        if now.weekday() >= 5:
            return False
        try:
            if self.holidays and now.strftime("%Y-%m-%d") in self.holidays.dates():
                return False
        except Exception:                                           # noqa: BLE001
            pass
        hhmm = now.hour * 60 + now.minute
        return 9 * 60 + 14 <= hhmm <= 15 * 60 + 40

    def start(self) -> None:
        threading.Thread(target=self._run, name="pubchain", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        self.refresh()
        while not self._stop.wait(180 if self._in_session() else 1800):
            self.refresh()

    def get(self, slug: str) -> dict | None:
        with self._lock:
            return self.data.get(slug)

    def status(self) -> dict:
        return {slug: {"fetched": d.get("fetched"), "expiry": d.get("expiry"), "spot": d.get("spot")} for slug, d in self.data.items()} | {"error": self.error}


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------
from finch import _CSS as _BASE_CSS  # noqa: E402

_CSS = _BASE_CSS + r"""
.kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:14px 0 16px}
.kp div{background:var(--panel);padding:10px 12px}.kp small{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}.kp b{font-family:var(--display);font-size:24px;font-weight:600;color:var(--gold)}.kp b.c{color:var(--cyan)}.kp b.m{color:var(--text)}.kp b.up{color:var(--up)}.kp b.down{color:var(--down)}
.syms{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0;font-family:var(--mono);font-size:11px}.syms a{border:1px solid var(--line-strong);padding:6px 12px;color:var(--muted)}.syms a.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
table.oc{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11.5px;margin:6px 0 14px}table.oc th{font-size:9.5px;letter-spacing:.1em;color:var(--faint);font-weight:500;padding:6px 6px;text-align:right;border-bottom:1px solid var(--line-strong)}
table.oc td{padding:5px 6px;text-align:right;border-bottom:1px solid rgba(190,150,255,.1);font-variant-numeric:tabular-nums;position:relative;white-space:nowrap}
table.oc td.k{text-align:center;color:var(--gold);font-weight:600;background:rgba(106,53,240,.12)}table.oc tr.atm td{background:rgba(106,53,240,.28)}
table.oc td.oi i{position:absolute;top:2px;bottom:2px;z-index:0;opacity:.28}table.oc td.ce.oi i{right:0;background:var(--down)}table.oc td.pe.oi i{left:0;background:var(--up)}table.oc td.oi span{position:relative;z-index:1}
table.oc td.wall{box-shadow:inset 0 0 0 1px var(--gold)}.up{color:var(--up)}.down{color:var(--down)}table.oc td.dim{color:var(--muted)}
.faq h3{font-family:var(--display);font-size:20px;text-transform:uppercase;color:var(--gold-2);margin:22px 0 4px}.faq p{color:var(--muted);max-width:76ch}
.stamp{font-family:var(--mono);font-size:11px;color:var(--faint);letter-spacing:.08em}
"""


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _n(v, d=0) -> str:
    return "—" if v is None else f"{v:,.{d}f}"


def _k(v) -> str:
    if v is None:
        return "—"
    a = abs(v)
    s = f"{a / 1e7:.2f}cr" if a >= 1e7 else f"{a / 1e5:.1f}L" if a >= 1e5 else f"{a / 1000:.1f}k" if a >= 1000 else str(int(a))
    return ("-" if v < 0 else "") + s


def render(pc: PublicChains, slug: str) -> bytes | None:
    if slug in SYMBOLS:
        d = pc.get(slug)
        sym, label, step = SYMBOLS[slug]
    elif pc.is_stock(slug):
        d = pc.stock(slug)
        sym = label = slug.upper()
        step = (d or {}).get("step") or 0
    else:
        return None
    st = (d or {}).get("stats") or {}
    rows = (d or {}).get("rows") or []
    spot = (d or {}).get("spot")
    atm = st.get("atm")
    if atm and rows:
        idx = next((i for i, r in enumerate(rows) if r["strike"] == atm), len(rows) // 2)
        window = rows[max(0, idx - WINDOW): idx + WINDOW + 1]
    else:
        window = rows[:2 * WINDOW + 1]
    mx = st.get("max_oi") or 1
    fetched = datetime.fromtimestamp(d["fetched"], IST).strftime("%d %b %Y, %H:%M IST") if d else "—"
    title = f"{label} Option Chain — live OI, PCR {_n(st.get('pcr'), 2)}, max pain {_n(st.get('max_pain'))} ({(d or {}).get('expiry') or 'nearest expiry'}) | Finostat"
    desc = (f"{label} option chain with open interest, change in OI, volume, IV and last price for every strike; PCR {_n(st.get('pcr'), 2)}, max pain {_n(st.get('max_pain'))}, "
            f"call wall {_n(st.get('call_wall'))}, put wall {_n(st.get('put_wall'))}. Free, refreshed every few minutes from NSE.")
    kp = [("spot", _n(spot, 2), "c"), ("expiry", (d or {}).get("expiry") or "—", "m"), ("PCR (OI)", _n(st.get("pcr"), 2), "up" if (st.get("pcr") or 0) >= 1 else "down"),
          ("max pain", _n(st.get("max_pain")), ""), ("call wall", _n(st.get("call_wall")), "down"), ("put wall", _n(st.get("put_wall")), "up"),
          ("call OI · Δ today", f"{_k(st.get('tot_ce'))} · {('+' if (st.get('chg_ce') or 0) > 0 else '')}{_k(st.get('chg_ce'))}", "m"),
          ("put OI · Δ today", f"{_k(st.get('tot_pe'))} · {('+' if (st.get('chg_pe') or 0) > 0 else '')}{_k(st.get('chg_pe'))}", "m"), ("ATM IV", _n(st.get("iv_atm"), 1) + ("%" if st.get("iv_atm") else ""), "m")]
    kp_html = "".join(f'<div><small>{_esc(k)}</small><b class="{c}">{_esc(v)}</b></div>' for k, v, c in kp)
    trs = []
    for r in window:
        ce, pe = r["ce"] or {}, r["pe"] or {}
        def oi_td(side, s, wall):
            w = int(s.get("oi", 0) / mx * 100) if s else 0
            return f'<td class="{side} oi{" wall" if wall else ""}"><i style="width:{w}%"></i><span>{_k(s.get("oi")) if s else "—"}</span></td>'
        def chg(v):
            return "—" if v is None else f'<span class="{"up" if v > 0 else "down" if v < 0 else ""}">{("+" if v > 0 else "")}{_k(v)}</span>'
        trs.append(f'<tr{" class=atm" if r["strike"] == atm else ""}>{oi_td("ce", ce, r["strike"] == st.get("call_wall"))}<td class="dim">{chg(ce.get("oi_chg")) if ce else "—"}</td><td class="dim">{_k(ce.get("vol")) if ce else "—"}</td><td class="dim">{_n(ce.get("iv"), 1) if ce and ce.get("iv") else "—"}</td><td>{_n(ce.get("ltp"), 2) if ce else "—"}</td>'
                   f'<td class="k">{r["strike"]}</td><td>{_n(pe.get("ltp"), 2) if pe else "—"}</td><td class="dim">{_n(pe.get("iv"), 1) if pe and pe.get("iv") else "—"}</td><td class="dim">{_k(pe.get("vol")) if pe else "—"}</td><td class="dim">{chg(pe.get("oi_chg")) if pe else "—"}</td>{oi_td("pe", pe, r["strike"] == st.get("put_wall"))}</tr>')
    table = ('<div class="scrollx"><table class="oc"><thead><tr><th>CALL OI</th><th>ΔOI</th><th>VOL</th><th>IV</th><th>CE LTP</th><th>STRIKE</th><th>PE LTP</th><th>IV</th><th>VOL</th><th>ΔOI</th><th>PUT OI</th></tr></thead>'
             f'<tbody>{"".join(trs) or "<tr><td colspan=11>Chain not loaded yet — NSE publishes during market hours; try again in a minute.</td></tr>"}</tbody></table></div>')
    syms = "".join(f'<a href="/option-chain/{s}"{" class=on" if s == slug else ""}>{SYMBOLS[s][1]}</a>' for s in SYMBOLS) + '<a href="/option-chain">ALL F&amp;O STOCKS · LOT SIZES</a>'
    lot = (d or {}).get("lot")
    if lot:
        kp_html += f'<div><small>lot size</small><b class="m">{lot}</b></div>'
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{label} option chain (NSE)", "url": f"https://finostat.com/option-chain/{slug}",
          "description": f"Open interest, change in OI, volume, implied volatility and last price for every {label} strike, with PCR, max pain and OI walls. Refreshed every few minutes from NSE during market hours.",
          "creator": {"@type": "Organization", "name": "Finostat", "url": "https://finostat.com"}, "isAccessibleForFree": True, "dateModified": datetime.fromtimestamp(d["fetched"], IST).isoformat() if d else None,
          "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"https://finostat.com/api/option-chain/{slug}"}}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f"What is the {label} option chain?", "acceptedAnswer": {"@type": "Answer", "text": f"Every listed {label} call and put for an expiry, strike by strike, with open interest (contracts outstanding), the day's change in OI, volume, implied volatility and last price. Calls on the left, puts on the right, the at-the-money strike highlighted."}},
        {"@type": "Question", "name": "What does PCR mean in an option chain?", "acceptedAnswer": {"@type": "Answer", "text": "The put-call ratio of open interest: total put OI divided by total call OI. Above 1 means more puts outstanding, usually read as hedged or bearish positioning that can turn into support; well below 1 means call-heavy positioning."}},
        {"@type": "Question", "name": "What is max pain?", "acceptedAnswer": {"@type": "Answer", "text": "The strike at which the total value of all outstanding options would be lowest at expiry, i.e. where option buyers as a group lose the most. Markets often drift toward it on expiry day, though it is a tendency, not a rule."}},
        {"@type": "Question", "name": "What are the call wall and put wall?", "acceptedAnswer": {"@type": "Answer", "text": "The strike above spot with the largest call OI (resistance where writers defend) and the strike below spot with the largest put OI (support). When they move, the expected range moves with them."}}]}
    ld_json = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    faq_json = json.dumps(faq, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow, max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com/option-chain/{slug}">
<meta property="og:type" content="website"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{_esc(title)}"><meta property="og:description" content="{_esc(desc)}"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com/option-chain/{slug}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{ld_json}</script>
<script type="application/ld+json">{faq_json}</script>
<style>{_CSS}</style></head><body>
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/fii-dii">FII/DII</a><a href="/calendar">CALENDAR</a><a href="/brief">BRIEF</a><a href="/dashboard">TERMINAL</a></div></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · OPTION CHAIN · {_esc(label)}</nav>
<h1>{_esc(label)} option chain</h1>
<p class="lede">Open interest, change in OI, volume, implied volatility and last price for every strike of the nearest expiry, with the put-call ratio, max pain and the OI walls. Free, from NSE's public data, refreshed every few minutes during market hours.</p>
<div class="syms">{syms}</div>
<p class="stamp">UPDATED {_esc(fetched)} · NSE TIMESTAMP {_esc((d or {}).get('nse_ts') or '—')} · OI IN CONTRACTS</p>
<div class="kp">{kp_html}</div>
{table}
<p><a class="cta" href="/dashboard">Greeks, 2nd &amp; 3rd order, implied distribution and the implied move on the terminal →</a> <a class="cta ghost" href="/fii-dii">FII/DII today</a> <a class="cta ghost" href="/calendar/expiry-dates">Expiry dates</a></p>
<section class="faq"><h3>How to read it</h3><p>Calls on the left, puts on the right, strikes down the middle with the at-the-money row highlighted. Bars behind the OI columns scale to the largest position on the chain; the gold-outlined cells are the walls. ΔOI is the change since the previous close: rising call OI above spot is writing (resistance), rising put OI below spot is support, and OI falling on both sides into expiry is unwinding.</p>
<h3>PCR, max pain and the walls</h3><p>PCR above 1 says more puts than calls are outstanding, usually hedges, which can act as support; far below 1 says call-heavy. Max pain is where option sellers as a group collect the most, and expiry-day drifts toward it are common but not guaranteed. The walls are the largest OI strikes above and below spot; the space between them is the range the market is being defended in.</p>
<h3>Live Greeks and the implied move</h3><p>This page is NSE's delayed public data. The Finostat terminal prices the same chain live off the exchange feed with delta, gamma, theta, vega, vanna, charm, vomma, speed, zomma and more on every strike, plus the implied distribution and the straddle-implied move.</p></section>
<p class="disc">Source: NSE option chain (public, delayed). Finostat reformats and computes PCR, max pain and walls; it does not alter the figures. Not investment advice.</p>
</main></body></html>"""
    return doc.encode("utf-8")



def render_index(pc: PublicChains) -> bytes:
    """/option-chain — the indices plus every F&O stock with its lot size, each linking to its chain."""
    lots = pc.lots()
    stocks = pc.fo_stocks()
    idx_lots = {SYMBOLS[s][0]: lots.get(SYMBOLS[s][0]) for s in SYMBOLS}
    cards = "".join(f'<a class="card" href="/option-chain/{s}"><b>{SYMBOLS[s][1]}</b><small>lot {idx_lots.get(SYMBOLS[s][0]) or "—"} · {(pc.get(s) or {}).get("expiry") or "nearest expiry"}</small>'
                    f'<span>PCR {((pc.get(s) or {}).get("stats") or {}).get("pcr") or "—"} · max pain {((pc.get(s) or {}).get("stats") or {}).get("max_pain") or "—"}</span></a>' for s in SYMBOLS)
    rows = "".join(f'<tr><td><a href="/option-chain/{n.lower()}">{_esc(n)}</a></td><td>{lots.get(n) or "—"}</td><td><a href="/option-chain/{n.lower()}">chain →</a></td></tr>' for n in stocks)
    title = f"F&O Stock List with Lot Sizes — {len(stocks)} NSE stocks, NIFTY & BANKNIFTY option chains | Finostat"
    desc = f"Every stock in NSE's F&O segment with its current lot size, plus live option chains with OI, PCR and max pain for NIFTY, BANKNIFTY, FINNIFTY and all {len(stocks)} stocks. Free."
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": "NSE F&O stock list with lot sizes", "url": "https://finostat.com/option-chain",
          "description": desc, "creator": {"@type": "Organization", "name": "Finostat", "url": "https://finostat.com"}, "isAccessibleForFree": True,
          "dateModified": datetime.now(IST).strftime("%Y-%m-%d")}
    ld_json = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com/option-chain">
<meta property="og:type" content="website"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{_esc(title)}"><meta property="og:description" content="{_esc(desc)}"><meta property="og:image" content="https://finostat.com/og.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{ld_json}</script>
<style>{_CSS}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:14px 0}}.card{{display:block;border:1px solid var(--line-strong);background:var(--panel);padding:12px 14px}}.card:hover{{border-color:var(--gold)}}.card b{{font-family:var(--display);font-size:20px;text-transform:uppercase;display:block;color:var(--text)}}.card small{{display:block;font-family:var(--mono);font-size:10.5px;color:var(--faint);margin:2px 0 6px}}.card span{{font-family:var(--mono);font-size:11px;color:var(--gold)}}
table.fo{{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px}}table.fo th{{font-size:10px;letter-spacing:.1em;color:var(--faint);font-weight:500;padding:6px 8px;text-align:left;border-bottom:1px solid var(--line-strong)}}table.fo td{{padding:6px 8px;border-bottom:1px solid rgba(190,150,255,.1)}}table.fo td a{{color:var(--cyan)}}
.filt{{width:100%;max-width:360px;background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:15px;padding:9px 12px;margin:8px 0 10px}}</style></head><body>
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/fii-dii">FII/DII</a><a href="/calendar">CALENDAR</a><a href="/brief">BRIEF</a><a href="/dashboard">TERMINAL</a></div></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · OPTION CHAINS</nav>
<h1>Option chains &amp; F&amp;O lot sizes</h1>
<p class="lede">Free option chains for NIFTY, BANKNIFTY, FINNIFTY and every stock in NSE's F&amp;O segment, with open interest, PCR, max pain and the OI walls, plus the current lot size for each name. Index chains refresh every few minutes in market hours; stock chains load when you open them.</p>
<div class="cards">{cards}</div>
<h2 style="font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold-2);margin:18px 0 4px">All F&amp;O stocks · {len(stocks)} names</h2>
<input class="filt" id="q" placeholder="filter: RELIANCE, HDFC, TATA…" aria-label="Filter stocks">
<div class="scrollx"><table class="fo" id="fo"><thead><tr><th>SYMBOL</th><th>LOT SIZE</th><th></th></tr></thead><tbody>{rows or "<tr><td colspan=3>loading the contract master…</td></tr>"}</tbody></table></div>
<section class="faq"><h3>What is a lot size?</h3><p>The number of shares in one futures or options contract. NSE revises lot sizes every few months so that a contract's value stays in its target band; the figures here come from the live contract master, so they update when NSE does.</p>
<h3>Which stocks are in F&amp;O?</h3><p>NSE adds and removes stocks from the derivatives segment based on liquidity criteria. This list is read from the exchange's own contract file, so it is the current segment, not a stale copy.</p></section>
<p class="disc">Chains are NSE public data (delayed). Lot sizes from the exchange contract master. Not investment advice.</p>
</main>
<script>(function(){{ var q=document.getElementById('q'), rows=document.querySelectorAll('#fo tbody tr'); q.addEventListener('input',function(){{ var v=q.value.trim().toUpperCase(); Array.prototype.forEach.call(rows,function(tr){{ tr.hidden=v&&tr.textContent.toUpperCase().indexOf(v)<0; }}); }}); }})();</script>
</body></html>"""
    return doc.encode("utf-8")


def sitemap_entries(pc: PublicChains) -> str:
    out = ['  <url><loc>https://finostat.com/option-chain</loc><changefreq>daily</changefreq><priority>0.8</priority></url>']
    for n in pc.fo_stocks():
        out.append(f'  <url><loc>https://finostat.com/option-chain/{n.lower()}</loc><changefreq>hourly</changefreq><priority>0.6</priority></url>')
    return "\n".join(out) + "\n"
