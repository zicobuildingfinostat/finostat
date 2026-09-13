"""XAU SOVEREIGN — the XAU/USD buy·sell engine, sold as a one-time ₹8,000 product.

/sovereign        public sales page (SEO, Product schema)
/xau-sovereign/buy    Cashfree checkout by mobile number (guest.py with the product)
/xau-sovereign/app    the indicator app for buyers (pages_global.render_sovereign)
/xau-sovereign/pine   the TradingView Pine Script, buyers only

The Pine script below is the same engine as server/gold.py: classic systems + price-action structure,
blended 50/50, hysteresis, non-repainting."""
from __future__ import annotations

import html
import json

from finch import _CSS as _BASE_CSS

NAME = "XAU Sovereign"
TAGLINE = "The XAU/USD buy · sell engine"
PRICE = 8000

_CSS = _BASE_CSS + r"""
.au-hero{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:28px;align-items:center;margin:10px 0 26px}
.au-hero h1{font-family:var(--display);font-size:clamp(44px,7vw,84px);line-height:.9;text-transform:uppercase;margin:0 0 8px;background:linear-gradient(180deg,#ffe27a,#f5c842 55%,#c99a12);-webkit-background-clip:text;background-clip:text;color:transparent}
.au-hero .tag{font-family:var(--display);font-size:clamp(20px,3vw,30px);text-transform:uppercase;color:var(--cyan);letter-spacing:.04em;margin:0 0 14px}
.au-hero p{color:var(--muted);font-size:16px;line-height:1.6;max-width:60ch}
.au-buy{border:1px solid var(--gold);background:var(--panel);padding:20px 22px;box-shadow:0 30px 80px rgba(0,0,0,.5),0 0 40px rgba(245,200,66,.1)}
.au-buy .pr{font-family:var(--display);font-size:54px;line-height:1;color:var(--gold)}.au-buy .pr i{font-style:normal;font-family:var(--mono);font-size:12px;color:var(--muted);letter-spacing:.08em;margin-left:8px}
.au-buy ul{list-style:none;padding:0;margin:12px 0 16px;font-size:14px;color:var(--text)}.au-buy li{padding:5px 0 5px 18px;position:relative;border-bottom:1px solid rgba(190,150,255,.1)}.au-buy li::before{content:"▸";position:absolute;left:0;color:var(--gold)}
.au-buy a.go{display:block;text-align:center;background:linear-gradient(180deg,#ffe27a,#f2b830);color:#2a1a02;font-family:var(--mono);font-weight:700;font-size:13px;letter-spacing:.12em;padding:15px;text-decoration:none}.au-buy a.go:hover{filter:brightness(1.06);color:#000}
.au-buy small{display:block;font-family:var(--mono);font-size:10.5px;color:var(--faint);margin-top:10px;line-height:1.5}
.au-spot{font-family:var(--mono);font-size:11px;letter-spacing:.1em;color:var(--faint);margin:0 0 10px}.au-spot b{color:var(--gold)}
.au-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:10px 0 24px}.au-card{border:1px solid var(--line-strong);background:var(--panel);padding:16px 18px}
.au-card h3{font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold-2);margin:0 0 6px}.au-card h3 small{font-family:var(--mono);font-size:10px;letter-spacing:.12em;color:var(--faint);margin-left:8px}
.au-card table{width:100%;border-collapse:collapse;font-size:13px}.au-card td{padding:5px 6px;border-bottom:1px solid rgba(190,150,255,.1);vertical-align:top}.au-card td:first-child{color:var(--text);white-space:nowrap;font-weight:500}.au-card td:last-child{color:var(--muted)}
.au-card td i{font-style:normal;font-family:var(--mono);font-size:10px;color:var(--faint);display:block}
.au-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0 24px}.au-steps div{border:1px solid var(--line-strong);padding:14px;background:var(--panel)}.au-steps b{font-family:var(--display);font-size:34px;color:var(--gold);display:block;line-height:1}.au-steps p{margin:6px 0 0;color:var(--muted);font-size:13px;line-height:1.5}
.au-shot{border:1px solid var(--line-strong);background:#06031a;margin:8px 0 24px;position:relative;overflow:hidden}.au-shot svg{display:block;width:100%;height:auto}
.au-shot .cap{position:absolute;left:12px;top:10px;font-family:var(--mono);font-size:10px;letter-spacing:.12em;color:var(--faint)}
.faq h3{font-family:var(--display);font-size:20px;text-transform:uppercase;color:var(--gold-2);margin:22px 0 4px}.faq p{color:var(--muted);max-width:76ch}
.au-disc{border-left:2px solid var(--down);padding:8px 12px;color:var(--faint);font-size:12px;line-height:1.55;margin:24px 0}
@media(max-width:860px){.au-hero,.au-grid{grid-template-columns:1fr}.au-steps{grid-template-columns:1fr 1fr}}
"""

CLASSIC = [("Turtle breakout", "Richard Dennis & William Eckhardt", "20-bar breakout entry, 10-bar exit — the original trend-following rules."),
           ("200-bar rule", "Paul Tudor Jones", "Only long above the 200 average, only short below it."),
           ("Holy Grail pullback", "Linda Raschke", "ADX above 30, then buy or sell the pullback to the 20 EMA."),
           ("MACD 12 / 26 / 9", "Gerald Appel", "Momentum: line against signal, histogram widening or narrowing."),
           ("RSI 14 & ADX 14", "J. Welles Wilder", "55/45 bias with 70/30 caution; ADX sets the trend regime."),
           ("Supertrend 10 / 3", "ATR trailing", "Trailing trend line that also seeds the stop."),
           ("Ichimoku", "Goichi Hosoda", "Price against the cloud, tenkan over kijun."),
           ("Bollinger %B · EMA ribbon", "John Bollinger", "Band position; 9/21/50 stack with the 50/200 golden cross.")]
PA = [("Market structure", "BOS / CHoCH", "Swing highs and lows from confirmed pivots; break of structure continues, change of character flips it."),
      ("Order blocks", "demand & supply", "The last opposite candle before the move that broke structure; drawn until price closes through it."),
      ("Fair value gaps", "imbalance", "Three-candle gaps that price tends to return to; kept until filled."),
      ("Liquidity sweeps", "equal highs / lows", "Stops resting at equal highs or lows; a wick through and close back inside is the sweep."),
      ("Premium / discount", "dealing range", "Where price sits in the current swing range — buy the discount, sell the premium."),
      ("Displacement & rejection", "candles", "Momentum candles and engulfing / pin-bar rejections at a level.")]


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _shot_svg() -> str:
    """A static, hand-drawn illustration of the chart (no live data on the public page)."""
    pts = [120, 128, 124, 134, 140, 136, 150, 158, 152, 146, 138, 132, 126, 118, 110, 116, 108, 100, 94, 102, 112, 120, 126, 122, 130, 140, 148, 156, 150, 160, 168, 164, 172, 180, 176, 170]
    w, h = 900, 300
    n = len(pts)
    xs = [40 + i * (w - 120) / (n - 1) for i in range(n)]
    ys = [h - 40 - (p - 90) * 2.3 for p in pts]
    candles = []
    for i in range(n):
        o = ys[i - 1] if i else ys[i] + 6
        c = ys[i]
        up = c <= o
        top, bot = min(o, c), max(o, c)
        candles.append(f'<line x1="{xs[i]:.0f}" y1="{top - 9:.0f}" x2="{xs[i]:.0f}" y2="{bot + 9:.0f}" stroke="{"#3dd68c" if up else "#ff5c6c"}" stroke-width="1.2"/>'
                       f'<rect x="{xs[i] - 6:.0f}" y="{top:.0f}" width="12" height="{max(2, bot - top):.0f}" fill="{"#3dd68c" if up else "#ff5c6c"}"/>')
    ema = " ".join(f"{xs[i]:.0f},{(sum(ys[max(0, i - 4):i + 1]) / len(ys[max(0, i - 4):i + 1])):.0f}" for i in range(n))
    return f'''<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Illustration of the XAU Sovereign chart">
<rect width="{w}" height="{h}" fill="#06031a"/>
<rect x="{xs[7] - 8:.0f}" y="{ys[8] - 4:.0f}" width="{w - 60 - xs[7]:.0f}" height="22" fill="rgba(255,92,108,.12)"/><text x="{xs[7]:.0f}" y="{ys[8] - 8:.0f}" fill="#ff8a96" font-family="IBM Plex Mono,monospace" font-size="10">OB supply</text>
<rect x="{xs[18] - 8:.0f}" y="{ys[18] - 6:.0f}" width="{w - 60 - xs[18]:.0f}" height="20" fill="rgba(106,53,240,.3)"/><text x="{xs[18]:.0f}" y="{ys[18] - 10:.0f}" fill="#b9a6ff" font-family="IBM Plex Mono,monospace" font-size="10">OB demand</text>
<rect x="{xs[24] - 8:.0f}" y="{ys[25] - 2:.0f}" width="{w - 60 - xs[24]:.0f}" height="14" fill="rgba(61,214,140,.14)"/>
<line x1="{xs[3]:.0f}" y1="{ys[7] - 14:.0f}" x2="{xs[12]:.0f}" y2="{ys[7] - 14:.0f}" stroke="#ff5c6c" stroke-dasharray="4 3" opacity=".8"/><text x="{xs[3]:.0f}" y="{ys[7] - 18:.0f}" fill="#ff5c6c" font-family="IBM Plex Mono,monospace" font-size="10">EQH swept ×</text>
<polyline points="{ema}" fill="none" stroke="#7fe0f0" stroke-width="1.4" opacity=".9"/>
{"".join(candles)}
<text x="{xs[9]:.0f}" y="{ys[9] - 20:.0f}" fill="#f5c842" font-family="IBM Plex Mono,monospace" font-size="10" text-anchor="middle">CHoCH</text>
<text x="{xs[19]:.0f}" y="{ys[19] + 30:.0f}" fill="#3dd68c" font-family="IBM Plex Mono,monospace" font-size="16" font-weight="700" text-anchor="middle">▲</text><text x="{xs[19]:.0f}" y="{ys[19] + 44:.0f}" fill="#3dd68c" font-family="IBM Plex Mono,monospace" font-size="10" text-anchor="middle">BUY</text>
<text x="{xs[28]:.0f}" y="{ys[28] - 22:.0f}" fill="#3dd68c" font-family="IBM Plex Mono,monospace" font-size="10" text-anchor="middle">BOS</text>
<text x="{xs[8]:.0f}" y="{ys[8] - 24:.0f}" fill="#ff5c6c" font-family="IBM Plex Mono,monospace" font-size="16" font-weight="700" text-anchor="middle">▼</text><text x="{xs[8]:.0f}" y="{ys[8] - 38:.0f}" fill="#ff5c6c" font-family="IBM Plex Mono,monospace" font-size="10" text-anchor="middle">SELL</text>
<line x1="40" y1="{ys[-1]:.0f}" x2="{w - 60:.0f}" y2="{ys[-1]:.0f}" stroke="#7fe0f0" stroke-dasharray="1 3"/><rect x="{w - 58:.0f}" y="{ys[-1] - 8:.0f}" width="52" height="16" fill="#7fe0f0"/><text x="{w - 32:.0f}" y="{ys[-1] + 4:.0f}" fill="#0c0626" font-family="IBM Plex Mono,monospace" font-size="10" text-anchor="middle">entry</text>
<rect x="{w - 58:.0f}" y="{ys[-1] + 26:.0f}" width="52" height="16" fill="#ff5c6c"/><text x="{w - 32:.0f}" y="{ys[-1] + 38:.0f}" fill="#0c0626" font-family="IBM Plex Mono,monospace" font-size="10" text-anchor="middle">SL</text>
<rect x="{w - 58:.0f}" y="{ys[-1] - 62:.0f}" width="52" height="16" fill="#3dd68c"/><text x="{w - 32:.0f}" y="{ys[-1] - 50:.0f}" fill="#0c0626" font-family="IBM Plex Mono,monospace" font-size="10" text-anchor="middle">target</text>
</svg>'''


def render_sales(spot: float | None, configured: bool = True, teaser: dict | None = None) -> bytes:
    title = f"{NAME} — XAU/USD gold buy sell signal indicator (web app + TradingView Pine Script) | Finostat"
    desc = (f"{NAME}: a gold (XAU/USD) buy·sell engine that blends nine published trading systems with smart-money price action — "
            f"market structure, order blocks, fair value gaps, liquidity sweeps. Non-repainting, 1H/4H/1D, live web app plus the Pine Script for TradingView. One-time ₹{PRICE:,}.")
    ld = {"@context": "https://schema.org", "@type": "Product", "name": NAME, "description": desc, "brand": {"@type": "Brand", "name": "Finostat"},
          "url": "https://finostat.com/xau-sovereign", "image": "https://finostat.com/og.jpg", "category": "Trading indicator",
          "offers": {"@type": "Offer", "price": str(PRICE), "priceCurrency": "INR", "availability": "https://schema.org/InStock", "url": "https://finostat.com/xau-sovereign/buy",
                     "seller": {"@type": "Organization", "name": "Finostat", "url": "https://finostat.com"}}}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "What is XAU Sovereign?", "acceptedAnswer": {"@type": "Answer", "text": "A buy/sell signal engine for gold (XAU/USD). It scores the market from −1 to +1 by blending nine published, rule-based trading systems with smart-money price action, and prints BUY, SELL and exit markers on the chart with an entry, stop and 2R target."}},
        {"@type": "Question", "name": "Does the indicator repaint?", "acceptedAnswer": {"@type": "Answer", "text": "No. Swings register only once confirmed, every vote uses closed candles, and a signal stays on the chart once printed. The same bar history gives the same signals every time."}},
        {"@type": "Question", "name": "What do I get for ₹8,000?", "acceptedAnswer": {"@type": "Answer", "text": "Lifetime access to the live XAU Sovereign web app on finostat.com (1H, 4H and daily gold charts with the engine drawn on them) and the Pine Script source of the same indicator to add to your own TradingView chart, with alerts. One-time payment, nothing recurring."}},
        {"@type": "Question", "name": "Is this investment advice?", "acceptedAnswer": {"@type": "Answer", "text": "No. It is a technical tool. Past signals do not guarantee future results; the app shows the honest hit rate of its own past flips so you can judge it yourself."}}]}
    ld_json = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    faq_json = json.dumps(faq, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    classic = "".join(f"<tr><td>{_esc(n)}<i>{_esc(w)}</i></td><td>{_esc(d)}</td></tr>" for n, w, d in CLASSIC)
    pa = "".join(f"<tr><td>{_esc(n)}<i>{_esc(w)}</i></td><td>{_esc(d)}</td></tr>" for n, w, d in PA)
    spot_html = f'GOLD NOW · <b>${spot:,.2f}</b> / oz' if spot else "GOLD · XAU/USD"
    if teaser:
        col = {"BUY": "var(--up)", "SELL": "var(--down)"}
        words = " · ".join(f'{tf.upper()} <b style="color:{col.get(sig.split()[-1], "var(--muted)")}">{_esc(sig)}</b>' for tf, sig in teaser.items() if sig)
        if words:
            spot_html += f'<br>ENGINE NOW · {words} <i style="font-style:normal;color:var(--faint)">· levels and reasons inside</i>'
    buy = ('<a class="go" href="/xau-sovereign/buy">BUY NOW — ₹8,000 ONE-TIME →</a>' if configured else '<a class="go" href="/contact">PAYMENTS OPENING SOON — WRITE TO US</a>')
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow, max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com/xau-sovereign">
<meta property="og:type" content="product"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{_esc(NAME)} — {_esc(TAGLINE)}"><meta property="og:description" content="{_esc(desc)}"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com/xau-sovereign">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{ld_json}</script>
<script type="application/ld+json">{faq_json}</script>
<style>{_CSS}</style></head><body>
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/global">GLOBAL</a><a href="/calendar">CALENDAR</a><a href="/finch">FINCH</a><a href="/dashboard">TERMINAL</a></div></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · XAU SOVEREIGN</nav>
<section class="au-hero"><div>
<p class="au-spot">{spot_html}</p>
<h1>{_esc(NAME)}</h1>
<p class="tag">{_esc(TAGLINE)}</p>
<p>Nine published trading systems and a full smart-money price-action read, voting on the same gold candles and printing one clean call: <b style="color:var(--up)">BUY</b>, <b style="color:var(--down)">SELL</b>, or stand aside. Entry, stop and target on the chart. Non-repainting. Built in-house by Finostat, runs on 1H, 4H and daily.</p>
</div>
<div class="au-buy"><div class="pr">₹8,000<i>ONE-TIME · LIFETIME</i></div>
<ul><li>Live XAU Sovereign web app — gold 1H / 4H / 1D with the engine drawn on the chart</li><li>The Pine Script source: add the same indicator to your TradingView chart, with alerts</li><li>Every vote explained in plain English, every bar</li><li>Entry, stop-loss and 2R target on each signal</li><li>Honest hit-rate of its own past flips, always visible</li><li>Pay once by UPI, card or net banking through Cashfree</li></ul>
{buy}
<small>Account is created from your mobile number at checkout. Lifetime means for as long as Finostat runs the service. Not investment advice.</small></div></section>

<div class="au-shot"><span class="cap">WHAT THE ENGINE DRAWS · ILLUSTRATION</span>{_shot_svg()}</div>

<div class="au-grid">
<div class="au-card"><h3>Classic systems<small>50% of the score</small></h3><table>{classic}</table></div>
<div class="au-card"><h3>Price action<small>50% of the score</small></h3><table>{pa}</table></div>
</div>

<h2 style="font-family:var(--display);font-size:26px;text-transform:uppercase;color:var(--gold-2);margin:10px 0 8px">How a signal is made</h2>
<div class="au-steps">
<div><b>1</b><p>Every system votes +1, −1 or 0 on the closed candle, with a written reason.</p></div>
<div><b>2</b><p>Votes are weighted and blended 50/50 between the classic systems and the price-action read into one score from −1 to +1. A rangebound ADX damps it.</p></div>
<div><b>3</b><p>BUY from +0.25, SELL from −0.25. A state holds until the score decays through ±0.10, so it does not flip every bar.</p></div>
<div><b>4</b><p>On a flip the chart prints the marker, the entry, a stop from the Supertrend line or 2×ATR, and a 2R target.</p></div>
</div>

<section class="faq"><h3>Why these systems?</h3><p>They are the public, rule-based methods that well-known traders are on record using — the Turtle rules, Paul Tudor Jones's 200-day discipline, Linda Raschke's Holy Grail, Wilder's RSI and ADX, Appel's MACD, Hosoda's Ichimoku, Bollinger's bands — implemented faithfully, plus the market-structure, order-block, fair-value-gap and liquidity concepts that modern price-action trading is built on. XAU Sovereign is Finostat's own blend of them; none of those traders is affiliated with it.</p>
<h3>Does it repaint?</h3><p>No. Swings register only once confirmed, every vote uses closed candles, and a printed signal stays. Reloading the same history reproduces the same signals bar for bar.</p>
<h3>What does the web app use for gold prices?</h3><p>Gold-backed PAXG against USDT (it tracks XAU/USD within a few dollars) for 1,000 bars of 1H, 4H and daily candles, cross-checked against the live XAU spot. In TradingView, the Pine Script runs on whichever gold symbol you open — XAUUSD, GC futures, or gold in ₹.</p>
<h3>What about the Pine Script?</h3><p>After purchase, the app has a "Pine Script" button. Open TradingView → Pine Editor → paste → Add to chart. The script draws the same zones, structure, markers and levels, keeps a live score table, and has BUY / SELL alert conditions you can route to your phone.</p>
<h3>Refunds?</h3><p>It is a digital product delivered instantly, so there are no refunds once the app or script has been opened. Write to hello@finostat.com before buying if you have questions.</p></section>
<p><a class="cta" href="/xau-sovereign/buy">Buy XAU Sovereign — ₹8,000 one-time →</a> <a class="cta ghost" href="/global">See the Global terminal</a></p>
<div class="au-disc">XAU Sovereign is a technical analysis tool for education and research. It is not investment advice and does not guarantee returns; gold can move against any signal. Trade at your own risk and size positions responsibly. Finostat is not a SEBI-registered investment adviser.</div>
</main></body></html>"""
    return doc.encode("utf-8")


PINE = r'''//@version=5
// XAU SOVEREIGN — the XAU/USD buy·sell engine · © Finostat (finostat.com/xau-sovereign)
// Licensed to the buyer for personal use. Same engine as the Finostat web app:
// nine classic systems + smart-money price action, blended 50/50, hysteresis, non-repainting.
indicator("XAU Sovereign — Gold Buy·Sell Engine", shorttitle="XAU SOVEREIGN", overlay=true, max_boxes_count=60, max_lines_count=120, max_labels_count=200)

// ───────── inputs
showZones  = input.bool(true,  "Order blocks & fair value gaps", group="Layers")
showLiq    = input.bool(true,  "Liquidity: equal highs / lows",  group="Layers")
showStruct = input.bool(true,  "Structure: swings, BOS, CHoCH",  group="Layers")
showMA     = input.bool(true,  "EMA 21 / 50 and SMA 200",        group="Layers")
showST     = input.bool(true,  "Supertrend",                     group="Layers")
showLevels = input.bool(true,  "Entry / stop / target",          group="Layers")
showTable  = input.bool(true,  "Score table",                    group="Layers")
pivL       = input.int(3,      "Swing length",   minval=2, maxval=10, group="Engine")
enterLvl   = input.float(0.25, "Enter at score", step=0.05, minval=0.1, maxval=0.9, group="Engine")
exitLvl    = input.float(0.10, "Exit below score", step=0.05, minval=0.0, maxval=0.5, group="Engine")

cUp   = #3dd68c
cDown = #ff5c6c
cGold = #f5c842
cCyan = #7fe0f0
cViol = #6a35f0
cPink = #ff6ec7

// ───────── classic systems
e9   = ta.ema(close, 9)
e20  = ta.ema(close, 20)
e21  = ta.ema(close, 21)
e50  = ta.ema(close, 50)
s200 = ta.sma(close, 200)
[macdL, sigL, histL] = ta.macd(close, 12, 26, 9)
rsi  = ta.rsi(close, 14)
[pdi, ndi, adx] = ta.dmi(14, 14)
atr  = ta.atr(14)
[stLine, stDir] = ta.supertrend(3.0, 10)          // stDir < 0 = uptrend
hh20 = ta.highest(high, 20)[1]
ll20 = ta.lowest(low, 20)[1]
hh10 = ta.highest(high, 10)[1]
ll10 = ta.lowest(low, 10)[1]
basis = ta.sma(close, 20)
dev   = 2.0 * ta.stdev(close, 20)
bbU   = basis + dev
bbL   = basis - dev
tenkan = math.avg(ta.highest(high, 9),  ta.lowest(low, 9))
kijun  = math.avg(ta.highest(high, 26), ta.lowest(low, 26))
spanA  = math.avg(tenkan, kijun)[26]
spanB  = math.avg(ta.highest(high, 52), ta.lowest(low, 52))[26]

var int turtle = 0
if close > hh20
    turtle := 1
else if close < ll20
    turtle := -1
else if turtle == 1 and close < ll10
    turtle := 0
else if turtle == -1 and close > hh10
    turtle := 0

vTurtle = turtle
vMa200  = close > s200 ? 1 : -1
touch20 = low <= e20 * 1.003 and high >= e20 * 0.997
vGrail  = adx > 30 and touch20 ? (e20 > e20[1] ? 1 : -1) : 0
vMacd   = macdL > sigL ? 1 : -1
vRsi    = rsi > 55 ? 1 : rsi < 45 ? -1 : 0
vSt     = stDir < 0 ? 1 : -1
cloudTop = math.max(spanA, spanB)
cloudBot = math.min(spanA, spanB)
vIchi   = close > cloudTop and tenkan > kijun ? 1 : close < cloudBot and tenkan < kijun ? -1 : 0
pctB    = bbU > bbL ? (close - bbL) / (bbU - bbL) : 0.5
vBB     = pctB > 0.8 ? 1 : pctB < 0.2 ? -1 : 0
vRib    = e9 > e21 and e21 > e50 ? 1 : e9 < e21 and e21 < e50 ? -1 : 0
classic = (1.5 * vTurtle + 1.5 * vMa200 + 1.0 * vGrail + 1.0 * vMacd + 1.0 * vRsi + 1.5 * vSt + 1.5 * vIchi + 0.5 * vBB + 1.0 * vRib) / 10.5
classic := adx < 20 ? classic * 0.6 : classic

// ───────── price action: swings, structure, zones, liquidity
ph = ta.pivothigh(high, pivL, pivL)
pl = ta.pivotlow(low, pivL, pivL)

var float lastSH = na
var int   lastSHbar = na
var bool  shBroken = false
var float lastSL = na
var int   lastSLbar = na
var bool  slBroken = false
var int   structure = 0
var int   lastEvBar = na
var string lastEvType = ""
var int   lastEvDir = 0
var float lastEvLevel = na

var fvgBoxes = array.new_box()
var fvgDir   = array.new_int()
var obBoxes  = array.new_box()
var obDir    = array.new_int()
var liqLines = array.new_line()
var liqType  = array.new_int()      // 1 = EQH, -1 = EQL
var liqLevel = array.new_float()
var int   sweepBar = na
var int   sweepDir = 0
var float sweepLvl = na
var int   dispBar = na
var int   dispDir = 0

if not na(ph)
    tol = atr * 0.25
    if showLiq and not na(lastSH) and math.abs(lastSH - ph) <= tol
        lvl = math.max(lastSH, ph)
        ln = line.new(lastSHbar, lvl, bar_index - pivL, lvl, extend=extend.right, color=color.new(cDown, 25), style=line.style_dashed)
        array.push(liqLines, ln)
        array.push(liqType, 1)
        array.push(liqLevel, lvl)
        label.new(bar_index - pivL, lvl, "EQH", style=label.style_label_down, color=color.new(color.black, 100), textcolor=cDown, size=size.tiny)
    if showStruct
        tag = na(lastSH) ? "H" : ph > lastSH ? "HH" : "LH"
        label.new(bar_index - pivL, ph, tag, style=label.style_label_down, color=color.new(color.black, 100), textcolor=color.new(cDown, 10), size=size.tiny)
    lastSH := ph
    lastSHbar := bar_index - pivL
    shBroken := false

if not na(pl)
    tol = atr * 0.25
    if showLiq and not na(lastSL) and math.abs(lastSL - pl) <= tol
        lvl = math.min(lastSL, pl)
        ln = line.new(lastSLbar, lvl, bar_index - pivL, lvl, extend=extend.right, color=color.new(cUp, 25), style=line.style_dashed)
        array.push(liqLines, ln)
        array.push(liqType, -1)
        array.push(liqLevel, lvl)
        label.new(bar_index - pivL, lvl, "EQL", style=label.style_label_up, color=color.new(color.black, 100), textcolor=cUp, size=size.tiny)
    if showStruct
        tag = na(lastSL) ? "L" : pl < lastSL ? "LL" : "HL"
        label.new(bar_index - pivL, pl, tag, style=label.style_label_up, color=color.new(color.black, 100), textcolor=color.new(cUp, 10), size=size.tiny)
    lastSL := pl
    lastSLbar := bar_index - pivL
    slBroken := false

// structure breaks on close
if not na(lastSH) and not shBroken and close > lastSH
    lastEvType := structure == 1 ? "BOS" : "CHoCH"
    lastEvDir := 1
    lastEvLevel := lastSH
    lastEvBar := bar_index
    shBroken := true
    structure := 1
    if showStruct
        line.new(lastSHbar, lastSH, bar_index, lastSH, color=lastEvType == "CHoCH" ? cGold : cUp, style=line.style_dotted)
        label.new(bar_index, lastSH, lastEvType, style=label.style_label_down, color=color.new(color.black, 100), textcolor=lastEvType == "CHoCH" ? cGold : cUp, size=size.small)
    if showZones
        for i = 1 to 20
            if close[i] < open[i]
                bx = box.new(bar_index - i, high[i], bar_index, low[i], border_color=color.new(cViol, 35), bgcolor=color.new(cViol, 70), extend=extend.right, text="OB demand", text_size=size.tiny, text_color=color.new(cViol, 0), text_halign=text.align_left)
                array.push(obBoxes, bx)
                array.push(obDir, 1)
                break

if not na(lastSL) and not slBroken and close < lastSL
    lastEvType := structure == -1 ? "BOS" : "CHoCH"
    lastEvDir := -1
    lastEvLevel := lastSL
    lastEvBar := bar_index
    slBroken := true
    structure := -1
    if showStruct
        line.new(lastSLbar, lastSL, bar_index, lastSL, color=lastEvType == "CHoCH" ? cGold : cDown, style=line.style_dotted)
        label.new(bar_index, lastSL, lastEvType, style=label.style_label_up, color=color.new(color.black, 100), textcolor=lastEvType == "CHoCH" ? cGold : cDown, size=size.small)
    if showZones
        for i = 1 to 20
            if close[i] > open[i]
                bx = box.new(bar_index - i, high[i], bar_index, low[i], border_color=color.new(cPink, 35), bgcolor=color.new(cPink, 75), extend=extend.right, text="OB supply", text_size=size.tiny, text_color=color.new(cPink, 0), text_halign=text.align_left)
                array.push(obBoxes, bx)
                array.push(obDir, -1)
                break

// fair value gaps
if showZones and low > high[2]
    bx = box.new(bar_index - 2, low, bar_index, high[2], border_color=color.new(cUp, 70), bgcolor=color.new(cUp, 86), extend=extend.right)
    array.push(fvgBoxes, bx)
    array.push(fvgDir, 1)
if showZones and high < low[2]
    bx = box.new(bar_index - 2, low[2], bar_index, high, border_color=color.new(cDown, 70), bgcolor=color.new(cDown, 86), extend=extend.right)
    array.push(fvgBoxes, bx)
    array.push(fvgDir, -1)

// retire filled gaps, dead order blocks, and cap the counts
if array.size(fvgBoxes) > 0
    for i = array.size(fvgBoxes) - 1 to 0
        bx = array.get(fvgBoxes, i)
        d = array.get(fvgDir, i)
        filled = (d == 1 and low <= box.get_bottom(bx)) or (d == -1 and high >= box.get_top(bx))
        if filled or array.size(fvgBoxes) - i > 12
            box.delete(bx)
            array.remove(fvgBoxes, i)
            array.remove(fvgDir, i)
if array.size(obBoxes) > 0
    for i = array.size(obBoxes) - 1 to 0
        bx = array.get(obBoxes, i)
        d = array.get(obDir, i)
        dead = (d == 1 and close < box.get_bottom(bx)) or (d == -1 and close > box.get_top(bx))
        if dead or array.size(obBoxes) - i > 8
            box.delete(bx)
            array.remove(obBoxes, i)
            array.remove(obDir, i)

// liquidity: sweep = wick through the pool and close back inside; a close through it is a breakout
if array.size(liqLines) > 0
    for i = array.size(liqLines) - 1 to 0
        ln = array.get(liqLines, i)
        t = array.get(liqType, i)
        lvl = array.get(liqLevel, i)
        swept = (t == 1 and high > lvl and close < lvl) or (t == -1 and low < lvl and close > lvl)
        broke = (t == 1 and close > lvl) or (t == -1 and close < lvl)
        if swept
            sweepBar := bar_index
            sweepDir := t == 1 ? -1 : 1
            sweepLvl := lvl
            line.set_x2(ln, bar_index)
            line.set_extend(ln, extend.none)
            label.new(bar_index, lvl, "× swept", style=t == 1 ? label.style_label_down : label.style_label_up, color=color.new(color.black, 100), textcolor=t == 1 ? cDown : cUp, size=size.tiny)
            array.remove(liqLines, i)
            array.remove(liqType, i)
            array.remove(liqLevel, i)
        else if broke or array.size(liqLines) - i > 12
            line.delete(ln)
            array.remove(liqLines, i)
            array.remove(liqType, i)
            array.remove(liqLevel, i)

// displacement and rejection candles
body = math.abs(close - open)
avgBody = ta.sma(body, 20)
rng = high - low
if avgBody > 0 and body > 2.0 * avgBody and rng > 0 and body / rng > 0.6
    dispBar := bar_index
    dispDir := close > open ? 1 : -1
lowerW = math.min(open, close) - low
upperW = high - math.max(open, close)
bullEng = close > open and close[1] < open[1] and close >= open[1] and open <= close[1]
bearEng = close < open and close[1] > open[1] and close <= open[1] and open >= close[1]
bullPin = lowerW >= 2 * body and rng > 0 and lowerW / rng >= 0.6
bearPin = upperW >= 2 * body and rng > 0 and upperW / rng >= 0.6
vCandle = bullEng ? 1 : bearEng ? -1 : bullPin ? 1 : bearPin ? -1 : 0

// price-action votes
vStruct = structure
vZone = 0
if array.size(obBoxes) > 0
    for i = 0 to array.size(obBoxes) - 1
        bx = array.get(obBoxes, i)
        d = array.get(obDir, i)
        inside = low <= box.get_top(bx) and high >= box.get_bottom(bx)
        if inside and d == structure
            vZone := d
if vZone == 0 and array.size(fvgBoxes) > 0
    for i = 0 to array.size(fvgBoxes) - 1
        bx = array.get(fvgBoxes, i)
        d = array.get(fvgDir, i)
        inside = low <= box.get_top(bx) and high >= box.get_bottom(bx)
        if inside and d == structure
            vZone := d
vLiq  = not na(sweepBar) and bar_index - sweepBar <= 3 ? sweepDir : 0
vRange = 0
posPct = 0.5
if not na(lastSH) and not na(lastSL) and lastSH > lastSL
    posPct := (close - lastSL) / (lastSH - lastSL)
    vRange := structure == 1 and posPct < 0.5 ? 1 : structure == -1 and posPct > 0.5 ? -1 : 0
vDisp = not na(dispBar) and bar_index - dispBar <= 3 ? dispDir : 0
pa = (2.0 * vStruct + 1.5 * vZone + 1.5 * vLiq + 1.0 * vRange + 1.0 * vDisp + 0.5 * vCandle) / 7.5

// ───────── composite, hysteresis, signals
score = 0.5 * classic + 0.5 * pa
var int state = 0
prevState = state
if state == 1
    state := score > exitLvl ? 1 : score <= -enterLvl ? -1 : 0
else if state == -1
    state := score < -exitLvl ? -1 : score >= enterLvl ? 1 : 0
else
    state := score >= enterLvl ? 1 : score <= -enterLvl ? -1 : 0
buyFlip  = state == 1 and prevState != 1
sellFlip = state == -1 and prevState != -1
exitFlip = state == 0 and prevState != 0

var float entryP = na
var float stopP = na
var float targetP = na
if buyFlip
    entryP := close
    stopP := stDir < 0 and stLine < close ? stLine : close - 2 * atr
    stopP := math.max(stopP, close - 3 * atr)
    targetP := close + 2 * (close - stopP)
if sellFlip
    entryP := close
    stopP := stDir > 0 and stLine > close ? stLine : close + 2 * atr
    stopP := math.min(stopP, close + 3 * atr)
    targetP := close - 2 * (stopP - close)
if exitFlip
    entryP := na
    stopP := na
    targetP := na

// ───────── drawing
plot(showMA ? e21 : na,  "EMA 21",  color=color.new(cCyan, 0), linewidth=1)
plot(showMA ? e50 : na,  "EMA 50",  color=color.new(cGold, 0), linewidth=1)
plot(showMA ? s200 : na, "SMA 200", color=color.new(#a89ccf, 20), linewidth=2, style=plot.style_line)
plot(showST ? stLine : na, "Supertrend", color=stDir < 0 ? color.new(cUp, 10) : color.new(cDown, 10), linewidth=2, style=plot.style_linebr)
plot(showLevels ? entryP : na,  "Entry",  color=color.new(cCyan, 0), style=plot.style_linebr)
plot(showLevels ? stopP : na,   "Stop",   color=color.new(cDown, 0), style=plot.style_linebr, linewidth=2)
plot(showLevels ? targetP : na, "Target", color=color.new(cUp, 0),   style=plot.style_linebr, linewidth=2)
plotshape(buyFlip,  "BUY",  shape.triangleup,   location.belowbar, color=cUp,   text="BUY",  textcolor=cUp,   size=size.small)
plotshape(sellFlip, "SELL", shape.triangledown, location.abovebar, color=cDown, text="SELL", textcolor=cDown, size=size.small)
plotshape(exitFlip, "EXIT", shape.xcross, location.abovebar, color=color.new(#a89ccf, 20), size=size.tiny)
bgcolor(state == 1 ? color.new(cUp, 94) : state == -1 ? color.new(cDown, 94) : na)

// ───────── score table
var table tbl = table.new(position.top_right, 2, 8, bgcolor=color.new(#120a33, 10), border_color=color.new(#4a34a0, 0), border_width=1)
if showTable and barstate.islast
    sig = state == 1 ? (score >= 0.5 ? "STRONG BUY" : "BUY") : state == -1 ? (score <= -0.5 ? "STRONG SELL" : "SELL") : "NEUTRAL"
    sigCol = state == 1 ? cUp : state == -1 ? cDown : #a89ccf
    agree = (classic >= 0.2 and pa >= 0.2) or (classic <= -0.2 and pa <= -0.2) ? "CONFLUENCE" : (classic >= 0.2 and pa <= -0.2) or (classic <= -0.2 and pa >= 0.2) ? "CONFLICT" : "PARTIAL"
    table.cell(tbl, 0, 0, "XAU SOVEREIGN", text_color=cGold, text_size=size.small, text_halign=text.align_left)
    table.cell(tbl, 1, 0, sig, text_color=sigCol, text_size=size.normal)
    table.cell(tbl, 0, 1, "score", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 1, str.tostring(score, "+0.00;-0.00"), text_color=sigCol, text_size=size.small)
    table.cell(tbl, 0, 2, "classic", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 2, str.tostring(classic, "+0.00;-0.00"), text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 3, "price action", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 3, str.tostring(pa, "+0.00;-0.00"), text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 4, "structure", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 4, structure == 1 ? "bullish " + lastEvType : structure == -1 ? "bearish " + lastEvType : "none", text_color=structure == 1 ? cUp : structure == -1 ? cDown : #a89ccf, text_size=size.small)
    table.cell(tbl, 0, 5, "range", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 5, (posPct < 0.5 ? "discount " : "premium ") + str.tostring(posPct * 100, "0") + "%", text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 6, "ADX / RSI", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 6, str.tostring(adx, "0") + " / " + str.tostring(rsi, "0") + (adx < 20 ? "  range" : adx >= 25 ? "  trend" : ""), text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 7, "agreement", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 7, agree, text_color=agree == "CONFLUENCE" ? cUp : agree == "CONFLICT" ? cDown : cGold, text_size=size.small)

// ───────── alerts (Alerts → condition → XAU Sovereign)
alertcondition(buyFlip,  "XAU Sovereign BUY",  "XAU Sovereign: BUY {{ticker}} {{interval}} at {{close}}")
alertcondition(sellFlip, "XAU Sovereign SELL", "XAU Sovereign: SELL {{ticker}} {{interval}} at {{close}}")
alertcondition(exitFlip, "XAU Sovereign EXIT", "XAU Sovereign: signal exited on {{ticker}} {{interval}} at {{close}}")
'''


def pine_for(email: str) -> bytes:
    stamp = f"// Licensed copy for {email} — do not redistribute.\n"
    return (PINE.replace("// Licensed to the buyer", stamp + "// Licensed to the buyer", 1)).encode("utf-8")
