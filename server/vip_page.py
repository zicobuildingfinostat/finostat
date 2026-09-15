"""VIP INDICATOR — the Indian markets buy·sell engine (NIFTY, BANKNIFTY, FINNIFTY, SENSEX and every
F&O stock), sold as a one-time ₹12,999 product.

/vip-indicator        public sales page (Product + FAQ schema)
/vip-indicator/buy    Cashfree checkout by mobile number (guest.py with product 'vip')
/vip-indicator/app    the buyer's app: the STRUCT panel standalone + Pine instructions
/vip-indicator/pine   the TradingView Pine Script, buyers only

Same engine as the terminal's STRUCT panel (structure.py on top of gold.analyze)."""
from __future__ import annotations

import html
import json

import chart_pa
import pages
import panels_desk
import sovereign_page

NAME = "VIP Indicator"
TAGLINE = "The Indian markets buy · sell engine"
PRICE = 12999
PRODUCT = "vip"
_CSS = sovereign_page._CSS

PINE = (sovereign_page.PINE
        .replace("XAU SOVEREIGN — the XAU/USD buy·sell engine · © Finostat (finostat.com/xau-sovereign)", "VIP INDICATOR — the Indian markets buy·sell engine · © Finostat (finostat.com/vip-indicator)")
        .replace('indicator("XAU Sovereign — Gold Buy·Sell Engine", shorttitle="XAU SOVEREIGN"', 'indicator("VIP Indicator — Indian Markets Buy·Sell Engine", shorttitle="VIP INDICATOR"')
        .replace('"XAU SOVEREIGN"', '"VIP INDICATOR"').replace("XAU Sovereign", "VIP Indicator").replace("XAU SOVEREIGN", "VIP INDICATOR"))


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


PINE_SCALP = r"""//@version=5
// VIP SCALPER — fast trend engine for 1m–15m · part of the VIP Indicator package · © Finostat (finostat.com/vip-indicator)
// Licensed to the buyer for personal use. Same rules as the Finostat web app.
indicator("VIP Scalper — Fast Trend Engine", shorttitle="VIP SCALPER", overlay=true)

showMA   = input.bool(true,  "EMA 9 / 21 and VWAP")
showST   = input.bool(true,  "Supertrend 7 / 2")
showLvls = input.bool(true,  "Entry / stop / target")
adxMin   = input.int(18, "Minimum ADX", minval=5, maxval=40)
rr       = input.float(1.5, "Target (R multiple)", step=0.25, minval=0.5, maxval=5)

cUp   = #3dd68c
cDown = #ff5c6c
cGold = #f5c842
cCyan = #7fe0f0

e9   = ta.ema(close, 9)
e21  = ta.ema(close, 21)
vwap = ta.vwap(hlc3)
[stLine, stDir] = ta.supertrend(2.0, 7)           // stDir < 0 = uptrend
[pdi, ndi, adx] = ta.dmi(14, 14)
rsi7 = ta.rsi(close, 7)
atr  = ta.atr(14)

vEma  = e9 > e21 ? 1 : -1
vVwap = close > vwap ? 1 : -1
vSt   = stDir < 0 ? 1 : -1
vRsi  = rsi7 > 55 ? 1 : rsi7 < 45 ? -1 : 0
score = (1.5 * vEma + 1.5 * vVwap + 1.5 * vSt + 1.0 * vRsi) / 5.5
score := adx < adxMin ? score * 0.5 : score

var int state = 0
prev = state
if state == 1
    state := (score > 0.25 and stDir < 0) ? 1 : score <= -0.5 ? -1 : 0
else if state == -1
    state := (score < -0.25 and stDir > 0) ? -1 : score >= 0.5 ? 1 : 0
else
    state := score >= 0.5 ? 1 : score <= -0.5 ? -1 : 0
buyFlip  = state == 1 and prev != 1
sellFlip = state == -1 and prev != -1
exitFlip = state == 0 and prev != 0

var float entryP = na
var float stopP = na
var float targetP = na
if buyFlip
    entryP := close
    stopP := math.max(stDir < 0 and stLine < close ? stLine : close - 1.5 * atr, close - 1.5 * atr)
    targetP := close + rr * (close - stopP)
if sellFlip
    entryP := close
    stopP := math.min(stDir > 0 and stLine > close ? stLine : close + 1.5 * atr, close + 1.5 * atr)
    targetP := close - rr * (stopP - close)
if exitFlip
    entryP := na
    stopP := na
    targetP := na

plot(showMA ? e9 : na,   "EMA 9",  color=color.new(cCyan, 0))
plot(showMA ? e21 : na,  "EMA 21", color=color.new(cGold, 0))
plot(showMA ? vwap : na, "VWAP",   color=color.new(#ffb347, 0), linewidth=2)
plot(showST ? stLine : na, "Supertrend", color=stDir < 0 ? color.new(cUp, 10) : color.new(cDown, 10), linewidth=2, style=plot.style_linebr)
plot(showLvls ? entryP : na,  "Entry",  color=color.new(cCyan, 0), style=plot.style_linebr)
plot(showLvls ? stopP : na,   "Stop",   color=color.new(cDown, 0), style=plot.style_linebr, linewidth=2)
plot(showLvls ? targetP : na, "Target", color=color.new(cUp, 0),   style=plot.style_linebr, linewidth=2)
plotshape(buyFlip,  "BUY",  shape.triangleup,   location.belowbar, color=cUp,   text="BUY",  textcolor=cUp,   size=size.small)
plotshape(sellFlip, "SELL", shape.triangledown, location.abovebar, color=cDown, text="SELL", textcolor=cDown, size=size.small)
plotshape(exitFlip, "EXIT", shape.xcross, location.abovebar, color=color.new(#a89ccf, 20), size=size.tiny)
bgcolor(adx < adxMin ? color.new(#a89ccf, 94) : state == 1 ? color.new(cUp, 94) : state == -1 ? color.new(cDown, 94) : na)

var table tbl = table.new(position.top_right, 2, 5, bgcolor=color.new(#120a33, 10), border_color=color.new(#4a34a0, 0), border_width=1)
if barstate.islast
    sig = state == 1 ? "LONG" : state == -1 ? "SHORT" : "FLAT"
    table.cell(tbl, 0, 0, "VIP SCALPER", text_color=cGold, text_size=size.small, text_halign=text.align_left)
    table.cell(tbl, 1, 0, sig, text_color=state == 1 ? cUp : state == -1 ? cDown : #a89ccf, text_size=size.normal)
    table.cell(tbl, 0, 1, "score", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 1, (score >= 0 ? "+" : "") + str.tostring(score, "0.00"), text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 2, "VWAP", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 2, close > vwap ? "above" : "below", text_color=close > vwap ? cUp : cDown, text_size=size.small)
    table.cell(tbl, 0, 3, "ADX / RSI7", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 3, str.tostring(math.round(adx)) + " / " + str.tostring(math.round(rsi7)), text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 4, "stop / target", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 4, na(stopP) ? "—" : str.tostring(math.round(stopP)) + " / " + str.tostring(math.round(targetP)), text_color=#f1edff, text_size=size.small)

alertcondition(buyFlip,  "VIP Scalper LONG",  "VIP Scalper: LONG {{ticker}} {{interval}} at {{close}}")
alertcondition(sellFlip, "VIP Scalper SHORT", "VIP Scalper: SHORT {{ticker}} {{interval}} at {{close}}")
alertcondition(exitFlip, "VIP Scalper EXIT",  "VIP Scalper: exit on {{ticker}} {{interval}} at {{close}}")
"""

PINE_SELLER = r"""//@version=5
// VIP SELLER — option-selling engine · part of the VIP Indicator package · © Finostat (finostat.com/vip-indicator)
// Licensed to the buyer for personal use. Price-based version of the Finostat web app's engine.
indicator("VIP Seller — Option Selling Engine", shorttitle="VIP SELLER", overlay=true, max_lines_count=50, max_labels_count=100)

pivL     = input.int(3,  "Swing length", minval=2, maxval=10)
adxRange = input.int(20, "ADX below = rangebound", minval=10, maxval=30)
adxTrend = input.int(28, "ADX above = stand aside", minval=20, maxval=45)
stepIn   = input.int(0,  "Strike step (0 = auto)", minval=0)
emPct    = input.float(0.7, "Expected day move % (for strikes)", step=0.1, minval=0.1, maxval=5)

cUp   = #3dd68c
cDown = #ff5c6c
cGold = #f5c842

[pdi, ndi, adx] = ta.dmi(14, 14)
basis = ta.sma(close, 20)
dev   = 2.0 * ta.stdev(close, 20)
bbU   = basis + dev
bbL   = basis - dev
bbw   = basis > 0 ? (bbU - bbL) / basis : 0
bbwPct = ta.percentrank(bbw, 100)
rsi14 = ta.rsi(close, 14)

// structure from confirmed swings
ph = ta.pivothigh(high, pivL, pivL)
pl = ta.pivotlow(low, pivL, pivL)
var float lastSH = na
var float lastSL = na
var bool shBroken = false
var bool slBroken = false
var int structure = 0
if not na(ph)
    lastSH := ph
    shBroken := false
if not na(pl)
    lastSL := pl
    slBroken := false
if not na(lastSH) and not shBroken and close > lastSH
    shBroken := true
    structure := 1
if not na(lastSL) and not slBroken and close < lastSL
    slBroken := true
    structure := -1
posPct = not na(lastSH) and not na(lastSL) and lastSH > lastSL ? (close - lastSL) / (lastSH - lastSL) * 100 : 50.0

vAdx = adx < adxRange ? 1 : adx < adxTrend ? 0 : -1
vBbw = bbwPct >= 15 and bbwPct <= 60 ? 1 : bbwPct < 15 ? -1 : 0
vRng = posPct >= 30 and posPct <= 70 ? 1 : 0
vRsi = rsi14 >= 35 and rsi14 <= 65 ? 1 : -1
score = (2.0 * vAdx + 1.0 * vBbw + 1.5 * vRng + 0.5 * vRsi) / 5.0

string side = "SELL STRADDLE"
if structure == 1 and posPct < 50
    side := "SELL PUTS"
else if structure == -1 and posPct > 50
    side := "SELL CALLS"
else if structure == 1 and posPct >= 70
    side := "SELL CALLS"
else if structure == -1 and posPct <= 30
    side := "SELL PUTS"

var int state = 0
prev = state
if state == 1
    state := (score > 0.15 and adx < adxTrend) ? 1 : adx >= adxTrend ? -1 : 0
else
    state := score >= 0.4 ? 1 : score <= -0.4 ? -1 : 0
sellOn  = state == 1 and prev != 1
aside   = state == -1 and prev != -1
exitOn  = state == 0 and prev != 0

stp = stepIn > 0 ? stepIn : close < 500 ? 5 : close < 1500 ? 10 : close < 3000 ? 20 : close < 10000 ? 50 : 100
em = close * emPct / 100
callK = math.ceil(math.max(nz(lastSH, close), close + em) / stp) * stp
putK  = math.floor(math.min(nz(lastSL, close), close - em) / stp) * stp

var float ceLvl = na
var float peLvl = na
if sellOn
    ceLvl := side == "SELL PUTS" ? na : callK
    peLvl := side == "SELL CALLS" ? na : putK
    label.new(bar_index, low, side, style=label.style_label_up, color=color.new(cGold, 10), textcolor=#2a1a02, size=size.small)
if aside or exitOn
    ceLvl := na
    peLvl := na

plot(basis, "BB mid", color=color.new(#a89ccf, 40))
plot(bbU, "BB upper", color=color.new(#a89ccf, 70))
plot(bbL, "BB lower", color=color.new(#a89ccf, 70))
plot(ceLvl, "Short call strike", color=color.new(cDown, 0), style=plot.style_linebr, linewidth=2)
plot(peLvl, "Short put strike",  color=color.new(cUp, 0),   style=plot.style_linebr, linewidth=2)
plotshape(aside,  "STAND ASIDE", shape.xcross, location.abovebar, color=cDown, text="ASIDE", textcolor=cDown, size=size.small)
plotshape(exitOn, "EXIT", shape.xcross, location.abovebar, color=color.new(#a89ccf, 20), size=size.tiny)
bgcolor(state == 1 ? color.new(cUp, 94) : state == -1 ? color.new(cDown, 94) : na)

var table tbl = table.new(position.top_right, 2, 5, bgcolor=color.new(#120a33, 10), border_color=color.new(#4a34a0, 0), border_width=1)
if barstate.islast
    sig = state == 1 ? side : state == -1 ? "STAND ASIDE" : "NEUTRAL"
    table.cell(tbl, 0, 0, "VIP SELLER", text_color=cGold, text_size=size.small, text_halign=text.align_left)
    table.cell(tbl, 1, 0, sig, text_color=state == 1 ? cUp : state == -1 ? cDown : #a89ccf, text_size=size.normal)
    table.cell(tbl, 0, 1, "sell score", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 1, (score >= 0 ? "+" : "") + str.tostring(score, "0.00"), text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 2, "ADX / BB width pct", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 2, str.tostring(math.round(adx)) + " / " + str.tostring(math.round(bbwPct)), text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 3, "range position", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 3, str.tostring(math.round(posPct)) + "%", text_color=#f1edff, text_size=size.small)
    table.cell(tbl, 0, 4, "strikes CE / PE", text_color=#a89ccf, text_size=size.tiny, text_halign=text.align_left)
    table.cell(tbl, 1, 4, str.tostring(callK) + " / " + str.tostring(putK), text_color=#f1edff, text_size=size.small)

alertcondition(sellOn, "VIP Seller SELL PREMIUM", "VIP Seller: sell premium on {{ticker}} {{interval}} at {{close}}")
alertcondition(aside,  "VIP Seller STAND ASIDE",  "VIP Seller: stand aside on {{ticker}} {{interval}} at {{close}}")
alertcondition(exitOn, "VIP Seller EXIT",         "VIP Seller: exit on {{ticker}} {{interval}} at {{close}}")
"""

PINES = {"struct": ("vip-structure.pine", "PINE"), "scalp": ("vip-scalper.pine", "PINE_SCALP"), "seller": ("vip-seller.pine", "PINE_SELLER")}


def pine_for(email: str, which: str = "struct") -> bytes:
    stamp = f"// Licensed copy for {email} — do not redistribute.\n"
    src = {"struct": PINE, "scalp": PINE_SCALP, "seller": PINE_SELLER}.get(which, PINE)
    return src.replace("// Licensed to the buyer", stamp + "// Licensed to the buyer", 1).encode("utf-8")


def render_sales(teaser: dict | None = None, configured: bool = True) -> bytes:
    title = f"{NAME} — NIFTY & BANKNIFTY buy sell signal indicator with market structure, order blocks, FVG (web app + TradingView Pine Script) | Finostat"
    desc = (f"{NAME}: a buy·sell engine for NIFTY, BANKNIFTY, FINNIFTY, SENSEX and every F&O stock that blends nine published trading systems with smart-money price action — "
            f"market structure (BOS/CHoCH), order blocks, fair value gaps, liquidity sweeps, premium/discount. Non-repainting, 5m/15m/1h/1D, live web app plus the Pine Script for TradingView. One-time ₹{PRICE:,}.")
    ld = {"@context": "https://schema.org", "@type": "Product", "name": NAME, "description": desc, "brand": {"@type": "Brand", "name": "Finostat"},
          "url": "https://finostat.com/vip-indicator", "image": "https://finostat.com/og.jpg", "category": "Trading indicator",
          "offers": {"@type": "Offer", "price": str(PRICE), "priceCurrency": "INR", "availability": "https://schema.org/InStock", "url": "https://finostat.com/vip-indicator/buy",
                     "seller": {"@type": "Organization", "name": "Finostat", "url": "https://finostat.com"}}}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "What is VIP Indicator?", "acceptedAnswer": {"@type": "Answer", "text": "A buy/sell signal engine for Indian markets — NIFTY, BANKNIFTY, FINNIFTY, SENSEX and every F&O stock. It scores each chart from −1 to +1 by blending nine published, rule-based trading systems with smart-money price action, and prints BUY, SELL and exit markers with an entry, stop and 2R target, on 5-minute to daily candles."}},
        {"@type": "Question", "name": "Does it repaint?", "acceptedAnswer": {"@type": "Answer", "text": "No. Swings register only once confirmed, every vote uses closed candles, and a printed signal stays. The same history reproduces the same signals bar for bar."}},
        {"@type": "Question", "name": "What do I get for ₹12,999?", "acceptedAnswer": {"@type": "Answer", "text": "Lifetime access to the live VIP Indicator web app on finostat.com (any index or F&O stock, 5m/15m/1h/1D, with every vote explained) and the Pine Script source of the same indicator for your own TradingView chart, with BUY/SELL/EXIT alerts. One-time payment, nothing recurring."}},
        {"@type": "Question", "name": "Is this investment advice?", "acceptedAnswer": {"@type": "Answer", "text": "No. It is a technical tool for education and research. Past signals do not guarantee future results; the app shows the hit rate of its own past flips so you can judge it yourself."}}]}
    ld_json = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    faq_json = json.dumps(faq, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    classic = "".join(f"<tr><td>{_esc(n)}<i>{_esc(w)}</i></td><td>{_esc(d)}</td></tr>" for n, w, d in sovereign_page.CLASSIC)
    pa = "".join(f"<tr><td>{_esc(n)}<i>{_esc(w)}</i></td><td>{_esc(d)}</td></tr>" for n, w, d in sovereign_page.PA)
    live = "NIFTY · BANKNIFTY · F&amp;O STOCKS"
    if teaser:
        col = {"BUY": "var(--up)", "SELL": "var(--down)"}
        words = " · ".join(f'{_esc(k)} <b style="color:{col.get(str(sig).split()[-1], "var(--muted)")}">{_esc(sig)}</b>' for k, sig in teaser.items() if sig)
        if words:
            live += f'<br>ENGINE NOW · {words} <i style="font-style:normal;color:var(--faint)">· levels and reasons inside</i>'
    buy = ('<a class="go" href="/vip-indicator/buy">BUY NOW — ₹12,999 ONE-TIME →</a>' if configured else '<a class="go" href="/contact">PAYMENTS OPENING SOON — WRITE TO US</a>')
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow, max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com/vip-indicator">
<meta property="og:type" content="product"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{_esc(NAME)} — {_esc(TAGLINE)}"><meta property="og:description" content="{_esc(desc)}"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com/vip-indicator">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{ld_json}</script>
<script type="application/ld+json">{faq_json}</script>
<style>{_CSS}</style></head><body>
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/xau-sovereign">GOLD VIP</a><a href="/dashboard">TERMINAL</a><a href="/calendar">CALENDAR</a><a href="/finch">FINCH</a></div></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · VIP INDICATOR</nav>
<section class="au-hero"><div>
<p class="au-spot">{live}</p>
<h1>{_esc(NAME)}</h1>
<p class="tag">{_esc(TAGLINE)}</p>
<p>Three engines in one package, each printing clean <b style="color:var(--up)">BUY</b> / <b style="color:var(--down)">SELL</b> calls on the chart: <b style="color:var(--text)">STRUCTURE</b> (smart-money market structure, order blocks, fair value gaps, liquidity sweeps blended with nine published systems), <b style="color:var(--text)">SCALPER</b> (a fast trend engine for 1–15 minute charts on EMA, session VWAP and Supertrend) and <b style="color:var(--text)">SELLER</b> (when to sell premium, which side, and the strikes). Volume footprint, delta, CVD and profile on every chart. Entry, stop and target on every signal. Non-repainting. NIFTY, BANKNIFTY, FINNIFTY, SENSEX and every F&amp;O stock. Built in-house by Finostat.</p>
</div>
<div class="au-buy"><div class="pr">₹12,999<i>ONE-TIME · LIFETIME</i></div>
<ul><li>Three engines — STRUCTURE, SCALPER, SELLER — in the live web app on NIFTY, BANKNIFTY, FINNIFTY, SENSEX and any F&amp;O stock, 5m / 15m / 1h / 1D</li><li>Three Pine Scripts for your own TradingView chart, each with BUY / SELL / EXIT alerts</li><li>Volume footprint, bar delta, cumulative delta and volume profile with point of control on every chart</li><li>BOS / CHoCH, order blocks, FVGs, liquidity sweeps, premium / discount — drawn, not described</li><li>Every vote explained in plain English, every bar</li><li>Entry, stop-loss and 2R target on each signal</li><li>Pay once by UPI, card or net banking through Cashfree</li></ul>
{buy}
<small>Account is created from your mobile number at checkout. Lifetime means for as long as Finostat runs the service. Not investment advice. Desk members already have this engine in the terminal's STRUCT panel.</small></div></section>

<div class="au-shot"><span class="cap">WHAT THE ENGINE DRAWS · ILLUSTRATION</span>{sovereign_page._shot_svg()}</div>

<div class="au-grid">
<div class="au-card"><h3>Price action<small>50% of the score</small></h3><table>{pa}</table></div>
<div class="au-card"><h3>Classic systems<small>50% of the score</small></h3><table>{classic}</table></div>
</div>

<h2 style="font-family:var(--display);font-size:26px;text-transform:uppercase;color:var(--gold-2);margin:10px 0 8px">How a signal is made</h2>
<div class="au-steps">
<div><b>1</b><p>Every system votes +1, −1 or 0 on the closed candle, with a written reason.</p></div>
<div><b>2</b><p>Votes are weighted and blended 50/50 between price action and the classic systems into one score from −1 to +1. A rangebound ADX damps it.</p></div>
<div><b>3</b><p>BUY from +0.25, SELL from −0.25. A state holds until the score decays through ±0.10, so it does not flip every bar.</p></div>
<div><b>4</b><p>On a flip the chart prints the marker, the entry, a stop from the Supertrend line or 2×ATR, and a 2R target.</p></div>
</div>

<section class="faq"><h3>Which symbols and timeframes?</h3><p>NIFTY 50, BANKNIFTY, FINNIFTY and SENSEX plus every NSE F&amp;O stock, on 5-minute, 15-minute, hourly and daily candles from Upstox. In TradingView the Pine Script runs on whatever NSE chart you open — index, futures or stock.</p>
<h3>Does it repaint?</h3><p>No. Swings register only once confirmed, every vote uses closed candles, and a printed signal stays. Reloading the same history reproduces the same signals bar for bar.</p>
<h3>How is this different from XAU Sovereign?</h3><p>Same engine, different market. XAU Sovereign runs it on gold; VIP Indicator runs it on Indian indices and stocks, with Indian data and timeframes traders here use. Desk members get both engines inside the terminals; this is the standalone lifetime version for people who want just the indicator.</p>
<h3>What are the three engines?</h3><p>STRUCTURE reads the market the way smart-money traders do — break of structure, change of character, order blocks, fair value gaps, liquidity sweeps, premium and discount — and blends it with nine published systems. SCALPER is a fast trend engine for 1 to 15 minute charts: EMA 9/21, session VWAP, Supertrend 7/2, RSI momentum, filtered by ADX, with a Supertrend stop and a 1.5R target. SELLER is for option writers: it flags rangebound, calm conditions, picks the side from structure and position in the range, checks whether premium is rich and whether today is quieter than expected, and suggests the call and put strikes. Every chart also carries a volume footprint (buying versus selling per price bin, derived from each candle), bar delta, cumulative delta and a volume profile with the point of control.</p>
<h3>What about the Pine Scripts?</h3><p>After purchase, the app has three download buttons. Open TradingView → Pine Editor → paste → Add to chart. The script draws the same zones, structure, markers and levels, keeps a live score table, and has BUY / SELL / EXIT alert conditions you can route to your phone.</p>
<h3>Refunds?</h3><p>It is a digital product delivered instantly, so there are no refunds once the app or script has been opened. Write to hello@finostat.com before buying if you have questions.</p></section>
<p><a class="cta" href="/vip-indicator/buy">Buy VIP Indicator — ₹12,999 one-time →</a> <a class="cta ghost" href="/xau-sovereign">The gold engine</a></p>
<div class="au-disc">VIP Indicator is a technical analysis tool for education and research. It is not investment advice and does not guarantee returns; markets can move against any signal. Trade at your own risk and size positions responsibly. Finostat is not a SEBI-registered investment adviser.</div>
</main></body></html>"""
    return doc.encode("utf-8")


APP_BODY = r"""
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a>
  <a class="logo" href="/vip-indicator/app">VIP<b>·</b>INDICATOR</a>
  <span class="sym" id="t-sym">INDIAN MARKETS BUY · SELL ENGINE · BY FINOSTAT</span>
  <div class="r">
    <span class="live off" id="conn">—</span>
    <span id="clock">--:--:-- IST</span>
    <span id="who"><a href="/login?next=%2Fvip-indicator%2Fapp">SIGN IN</a></span>
    <a href="/dashboard">TERMINAL</a>
    <a href="/">← SITE</a>
  </div>
</header>
<main class="desk" style="grid-template-columns:minmax(0,1fr)">
__STRUCT__
  <section class="panel" id="p-pine" aria-label="TradingView Pine Script">
    <div class="panel-hd"><span class="k">PINE</span><span class="s">THREE SCRIPTS FOR YOUR TRADINGVIEW CHART</span><span class="r" id="vip-pines" hidden><a href="/vip-indicator/pine?which=struct" style="color:var(--gold);border:1px solid var(--gold);padding:1px 7px;font-size:9.5px;letter-spacing:.1em">STRUCTURE ↓</a><a href="/vip-indicator/pine?which=scalp" style="color:var(--gold);border:1px solid var(--gold);padding:1px 7px;font-size:9.5px;letter-spacing:.1em">SCALPER ↓</a><a href="/vip-indicator/pine?which=seller" style="color:var(--gold);border:1px solid var(--gold);padding:1px 7px;font-size:9.5px;letter-spacing:.1em">SELLER ↓</a></span></div>
    <div style="padding:12px 14px;font-size:12.5px;line-height:1.6;color:var(--muted)">
      <p><b style="color:var(--text)">1.</b> Download the three licensed scripts above: <code>vip-structure.pine</code> (market structure + classic systems), <code>vip-scalper.pine</code> (fast trend for 1–15 min) and <code>vip-seller.pine</code> (option selling: regime, side, strikes). Add any or all to a chart.</p>
      <p><b style="color:var(--text)">2.</b> In TradingView open <b style="color:var(--text)">Pine Editor</b> → <b style="color:var(--text)">Open → New indicator</b>, select all, paste the file's contents over it, press <b style="color:var(--text)">Add to chart</b>. Save it as private.</p>
      <p><b style="color:var(--text)">3.</b> Open NIFTY, BANKNIFTY, NIFTY1! or any NSE stock on 5m, 15m, 1h or 1D. Layers, swing length and the enter/exit thresholds are in the indicator's settings.</p>
      <p><b style="color:var(--text)">4.</b> Alerts: <b style="color:var(--text)">Alerts → Condition → VIP Indicator → BUY / SELL / EXIT</b>, then route them to the TradingView app on your phone.</p>
      <p style="color:var(--faint);font-size:11px">Licensed to your account for personal use — please don't publish or share it. Small differences between the app and TradingView come from the two data feeds, not the engine.</p>
    </div>
  </section>
</main>
<div class="g-fkeys"><a href="#p-struct">ENGINE</a><a href="#p-pine">PINE SCRIPT</a><a href="/vip-indicator">ABOUT VIP INDICATOR</a><a href="/xau-sovereign/app">GOLD ENGINE</a><a href="/account">ACCOUNT</a></div>
<script>(function(){ function tick(){ var d=new Date(); var el=document.getElementById('clock'); if(el) el.textContent=d.toLocaleTimeString('en-GB',{timeZone:'Asia/Kolkata',hour12:false})+' IST'; } tick(); setInterval(tick,1000);
  if(!window.FINO_LOCKED){ fetch('/api/me',{credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(m){ if(m&&m.email){ document.getElementById('who').innerHTML='<a href="/account">'+m.email.replace('@mobile.finostat','').toUpperCase()+'</a>'; } }).catch(function(){}); }
  if(window.FINO_PINE){ var p=document.getElementById('vip-pines'); if(p) p.hidden=false; var q=document.getElementById('stx-pine'); if(q) q.hidden=true; }
  var c=document.getElementById('conn'); if(c&&!window.FINO_LOCKED){ c.textContent='LIVE'; c.className='live'; } })();</script>
"""

_APP_DOC = None


def _struct_panel() -> str:
    m = panels_desk.MARKUP
    start = m.index('  <section class="panel a-wide an vipx" id="p-struct"')
    end = m.index("  <section ", start + 10)
    return m[start:end]


def render_app(locked: bool = False, signed_in: bool = False, pine: bool = False) -> bytes:
    global _APP_DOC
    if _APP_DOC is None:
        css = pages.DASHBOARD.split("<style>", 1)[1].split("</style>", 1)[0]
        body = APP_BODY.replace("__STRUCT__", _struct_panel())
        _APP_DOC = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VIP Indicator · Indian markets engine</title>
<meta name="robots" content="noindex">
<meta name="theme-color" content="#0c0626">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{css}{panels_desk.CSS}</style>
</head>
<body>
__GUARD__{body}
<script>{chart_pa.JS}</script>
<script>{panels_desk.JS}</script>
__PAYWALL__
</body>
</html>"""
    doc = _APP_DOC
    pine_tag = "<script>window.FINO_PINE=true;</script>" if pine else ""
    if locked:
        guard = ('<script>window.FINO_LOCKED=true;window.fetch=function(){return Promise.reject(new Error("locked"));};'
                 'document.addEventListener("DOMContentLoaded",function(){document.body.classList.add("locked");});</script>')
        primary = '<a class="b primary" href="/vip-indicator/buy">Buy VIP Indicator — ₹12,999 one-time →</a>'
        secondary = '<a class="b" href="/vip-indicator">What is VIP Indicator?</a>' if signed_in else '<a class="b" href="/login?next=%2Fvip-indicator%2Fapp">Already bought? Sign in</a>'
        wall = f"""<div class="paywall" role="dialog" aria-label="VIP Indicator purchase required"><div class="card">
<div class="hd"><span class="k">VIP INDICATOR</span><span class="s">INDIAN MARKETS BUY · SELL ENGINE</span><span class="r">₹12,999 · ONE-TIME</span></div>
<div class="bd"><h2>{"This account has not bought VIP Indicator" if signed_in else "VIP Indicator is a one-time purchase"}</h2>
<p>Nine published trading systems and a full smart-money price-action read on NIFTY, BANKNIFTY and every F&amp;O stock, blended into one non-repainting BUY / SELL call with entry, stop and target. Lifetime access to this app plus the Pine Script for your own TradingView chart.</p>
<ul><li>Indices and every F&amp;O stock</li><li>5m · 15m · 1h · 1D</li><li>Order blocks, FVGs, liquidity, BOS/CHoCH</li><li>Entry, stop, 2R target</li><li>TradingView Pine Script with alerts</li><li>Nothing recurring</li></ul>
<div class="price">₹12,999 <i>once · lifetime · exclusive of GST</i></div>
<div class="row">{primary}{secondary}</div>
<small>Desk members already have this engine as the STRUCT panel in the <a href="/dashboard" style="color:var(--cyan)">terminal</a>.</small>
</div></div></div>"""
        doc = doc.replace("__GUARD__", pages._PAYWALL_CSS + guard + pine_tag, 1).replace("__PAYWALL__", wall, 1)
    else:
        doc = doc.replace("__GUARD__", pine_tag, 1).replace("__PAYWALL__", "", 1)
    return doc.encode("utf-8")
