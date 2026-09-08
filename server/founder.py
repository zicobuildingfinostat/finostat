"""/founders -- the founder page. Static, same theme as Finch."""
from __future__ import annotations

from finch import _CSS as _BASE_CSS

_CSS = _BASE_CSS + r"""
.hero{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:40px;align-items:start;margin-top:18px}
.hero .lede{margin-bottom:18px}
.photo{position:relative;border:1px solid var(--line-strong);background:var(--panel);box-shadow:0 24px 60px rgba(0,0,0,.5);overflow:hidden}
.photo img{display:block;width:100%;height:auto;aspect-ratio:448/537;object-fit:cover;filter:saturate(1.05)}
.photo .tag{position:absolute;left:0;right:0;bottom:0;padding:8px 12px;background:linear-gradient(180deg,transparent,rgba(12,6,38,.92) 40%);font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold)}
.photo .tag small{display:block;color:var(--muted);letter-spacing:.08em;text-transform:none;font-size:11px;margin-top:2px}
.facts{margin-top:14px;border:1px solid var(--line-strong);background:var(--panel);font-family:var(--mono);font-size:12px}
.facts .hd{display:flex;gap:12px;padding:7px 12px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);font-size:11px;letter-spacing:.06em}
.facts .hd .k{color:var(--gold);font-weight:600}.facts .hd .s{color:var(--cyan)}
.facts dl{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;padding:12px 14px}
.facts dt{color:var(--faint);letter-spacing:.12em;text-transform:uppercase;font-size:10px;padding-top:3px}
.facts dd{color:var(--text)}
.stats{display:flex;gap:26px;flex-wrap:wrap;margin:6px 0 24px}
.stats div small{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.stats div b{font-family:var(--display);font-size:38px;font-weight:600;line-height:1;color:var(--gold)}
.stats div b i{font-style:normal;font-size:20px;color:var(--gold-2)}
.principles{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:12px 0 8px;max-width:820px}
.principles div{border:1px solid var(--line);background:rgba(18,10,51,.7);padding:14px 16px}
.principles b{display:block;font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--cyan);margin-bottom:6px}
.principles p{font-size:14px;color:var(--muted);margin:0}
.contact{display:flex;gap:10px;flex-wrap:wrap;margin-top:6px}
blockquote{border-left:3px solid var(--gold);padding:6px 18px;margin:18px 0 22px;max-width:66ch;font-size:19px;line-height:1.5;color:var(--text)}
blockquote cite{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);font-style:normal;margin-top:8px}
@media (max-width:860px){.hero{grid-template-columns:1fr}.hero>aside{order:-1;max-width:360px}.stats div b{font-size:32px}}
"""

_PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Zico Karmakar, founder — Finostat</title>
<meta name="description" content="Finostat was built by Zico Karmakar: ten-plus years in Indian derivatives, three-plus on proprietary and arbitrage desks. Why the desk's tools should be in every trader's hands.">
<meta name="theme-color" content="#0c0626"><link rel="icon" href="/og.jpg"><link rel="canonical" href="https://finostat.com/founders">
<meta property="og:type" content="profile"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="Zico Karmakar, founder — Finostat"><meta property="og:description" content="Ten-plus years in derivatives, three-plus on prop and arbitrage desks. Finostat puts that desk's tooling in every trader's hands."><meta property="og:image" content="https://finostat.com/founder.jpg"><meta property="og:url" content="https://finostat.com/founders">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>__CSS__</style></head><body>
<header class="top"><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/finch">FINCH</a><a href="/dashboard">TERMINAL</a><a href="/#plans">PLANS</a><a href="/assessment">ASSESS ME</a></div></header>
<main class="wrap">
<nav class="crumb"><a href="/">FINO</a> · FOUNDER</nav>
<div class="hero">
<div>
<h1>Zico Karmakar</h1>
<p class="lede">Founder, Finostat. A derivatives trader who spent a decade on the retail side of the screen and three years on the desk side, and decided the gap between them was a tooling problem, not a talent problem.</p>
<div class="stats"><div><small>Derivatives trading</small><b>10<i>+ yrs</i></b></div><div><small>Prop &amp; arbitrage desks</small><b>3<i>+ yrs</i></b></div><div><small>Instruments on the terminal</small><b>7,000<i>+</i></b></div></div>
<article>
<h2>The short version</h2>
<p>Zico has traded Indian derivatives for more than ten years — index options through every expiry regime NSE has tried, stock futures and options, and the arbitrage that sits between them. For three of those years he traded professionally on a <strong>proprietary desk</strong> and an <strong>arbitrage desk</strong>, where the job is not to have opinions about direction but to price risk precisely, hedge it, and be paid for the part nobody else wants to carry.</p>
<p>That experience shaped one conviction: the difference between a desk trader and a retail trader is rarely intelligence or discipline. It is that the desk sees the market <em>priced</em> — live greeks, the straddle as an expected move, exact breakevens before entry, alerts that watch levels so a human doesn't have to — while retail sees a chain of numbers and a chart. Finostat exists to close that gap.</p>
<blockquote>“On a desk you never put a trade on without knowing what it costs to be wrong. Retail traders are asked to guess that number. I wanted to give them the desk's answer, on their phone, for the price of a few coffees.”<cite>Zico Karmakar</cite></blockquote>
<h2>What the desk years taught</h2>
<div class="principles">
<div><b>Price first, view second</b><p>Every structure has a fair price. If the market is charging less than the risk is worth, that is the trade — whatever the chart says.</p></div>
<div><b>Size for the gap, not the average</b><p>Arbitrage desks survive by assuming the 4% overnight gap happens this week. Most retail losses are position sizes that assumed it never would.</p></div>
<div><b>Volatility is the product</b><p>Options are volatility instruments dressed up as directional ones. Know whether you are buying or selling it, and at what percentile.</p></div>
<div><b>Automate the watching</b><p>A desk has eyes on every level all day. A person with a job does not — so the server should carry the alerts, not the trader's attention.</p></div>
</div>
<h2>What he built</h2>
<p><strong>Finostat</strong> is a live options terminal for NSE and BSE — every listed equity and F&amp;O contract streamed in real time, on-demand option chains with Black-Scholes greeks computed on the server, a strategy builder with exact breakevens and payoff, server-side alerts delivered by email, and a tick recorder building the history that backtesting needs. It is written to run lean on a single small machine, because the desk's edge was never the hardware.</p>
<p><strong>Finch</strong> is the course he wishes had existed when he started: twelve chapters on derivatives, options, the Greeks, volatility, expiry mechanics, strategies and risk — every example pulled from today's live chain rather than a textbook, and free.</p>
<h2>How he trades today</h2>
<p>Mostly index options around expiry — defined-risk structures priced against the implied move — with stock options where the volatility skew pays for the risk, and the occasional cash-and-carry or calendar arbitrage when the basis gets lazy. He journals every trade, sizes by worst plausible loss, and still reads the option chain before the news every morning.</p>
<h2>Get in touch</h2>
<p>Questions about the product, partnerships, desk-side tooling, or a trade you want a second opinion on the pricing of: write to him directly.</p>
<div class="contact"><a class="cta" href="mailto:zico@finostat.com">zico@finostat.com</a><a class="cta ghost" href="/assessment">Take the trader assessment</a><a class="cta ghost" href="/finch">Read Finch</a></div>
</article>
</div>
<aside>
<div class="photo"><img src="/founder.jpg" alt="Zico Karmakar, founder of Finostat" width="448" height="537"><div class="tag">Zico Karmakar<small>Founder · derivatives trader · ex-prop &amp; arbitrage desk</small></div></div>
<div class="facts"><div class="hd"><span class="k">PROFILE</span><span class="s">FOUNDER</span></div><dl>
<dt>Experience</dt><dd>10+ years, Indian derivatives</dd>
<dt>Desk</dt><dd>3+ years, proprietary &amp; arbitrage trading</dd>
<dt>Focus</dt><dd>Index options · expiry structures · volatility · arbitrage</dd>
<dt>Markets</dt><dd>NSE, BSE, MCX</dd>
<dt>Building</dt><dd>Finostat terminal, Finch</dd>
<dt>Base</dt><dd>India</dd>
<dt>Email</dt><dd><a href="mailto:zico@finostat.com">zico@finostat.com</a></dd>
</dl></div>
</aside>
</div>
<p class="disc">Finostat is an analytics and education product. Nothing on this site is investment advice, and its founder is not a SEBI-registered investment adviser or research analyst. Derivatives can lose more than you put in.</p>
</main></body></html>"""


def render() -> bytes:
    return _PAGE.replace("__CSS__", _CSS).encode("utf-8")
