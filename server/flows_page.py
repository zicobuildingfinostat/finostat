"""Public page: /fii-dii — FII/DII activity and participant-wise positioning, updated every evening.

Server-rendered so the numbers are in the HTML for search engines; the charts are drawn by a small
script from the public JSON. Same data as the terminal's FLOWS panel."""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone

from finch import _CSS as _BASE_CSS

IST = timezone(timedelta(hours=5, minutes=30))

_CSS = _BASE_CSS + r"""
.kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:14px 0 18px}
.kp div{background:var(--panel);padding:10px 12px}.kp small{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}.kp b{font-family:var(--display);font-size:24px;font-weight:600}.kp b.up{color:var(--up)}.kp b.down{color:var(--down)}.kp b.m{color:var(--text)}
.cvw{position:relative;height:240px;border:1px solid var(--line-strong);background:var(--panel);margin:10px 0}.cvw canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:760px){.two{grid-template-columns:1fr}}
table.fl{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px;margin:8px 0 18px}table.fl th{font-size:10px;letter-spacing:.1em;color:var(--faint);font-weight:500;padding:6px 8px;text-align:right;border-bottom:1px solid var(--line-strong)}table.fl th:first-child,table.fl td:first-child{text-align:left}
table.fl td{padding:6px 8px;text-align:right;border-bottom:1px solid rgba(190,150,255,.1);font-variant-numeric:tabular-nums}.up{color:var(--up)}.down{color:var(--down)}
.faq h3{font-family:var(--display);font-size:20px;text-transform:uppercase;color:var(--gold-2);margin:22px 0 4px}.faq p{color:var(--muted);max-width:76ch}
.stamp{font-family:var(--mono);font-size:11px;color:var(--faint);letter-spacing:.08em}
"""


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _n(v, d=0) -> str:
    if v is None:
        return "—"
    return f"{v:,.{d}f}"


def _sg(v, d=0) -> str:
    if v is None:
        return "—"
    return ("+" if v > 0 else "") + _n(v, d)


def _cls(v) -> str:
    return "up" if (v or 0) >= 0 else "down"


def render(flows) -> bytes:
    d = flows.api(60)
    lp, lc = d.get("latest") or {}, d.get("latest_cash") or {}
    fii, pro, cli, dii = lp.get("fii") or {}, lp.get("pro") or {}, lp.get("client") or {}, lp.get("dii") or {}
    pos_date = lp.get("date") or "—"
    cash_date = lc.get("date") or "—"
    pretty = lambda s: datetime.strptime(s, "%Y-%m-%d").strftime("%d %b %Y") if s and s != "—" else "—"
    title = f"FII DII Data Today ({pretty(cash_date)}) — FII/DII activity, index futures & options positions | Finostat"
    desc = (f"FII net {_sg(lc.get('fii_net'))} crore, DII net {_sg(lc.get('dii_net'))} crore on {pretty(cash_date)}. "
            f"FII index futures net {_sg(fii.get('fut_idx_net'))} contracts. Daily FII/DII cash flows and participant-wise NSE positioning, updated every evening, free.")
    kp = [("FII cash (₹ cr)", _sg(lc.get("fii_net")), _cls(lc.get("fii_net"))), ("DII cash (₹ cr)", _sg(lc.get("dii_net")), _cls(lc.get("dii_net"))),
          ("FII index futures net", _sg(fii.get("fut_idx_net")), _cls(fii.get("fut_idx_net"))), ("change on the day", _sg(fii.get("fut_idx_net_chg")), _cls(fii.get("fut_idx_net_chg"))),
          ("FII index calls net", _sg(fii.get("call_net")), "m"), ("FII index puts net", _sg(fii.get("put_net")), "m"),
          ("Pro desks index futures", _sg(pro.get("fut_idx_net")), _cls(pro.get("fut_idx_net"))), ("Clients index futures", _sg(cli.get("fut_idx_net")), _cls(cli.get("fut_idx_net"))),
          ("DII index futures", _sg(dii.get("fut_idx_net")), "m")]
    kp_html = "".join(f'<div><small>{_esc(k)}</small><b class="{c}">{_esc(v)}</b></div>' for k, v, c in kp)
    cash_by = {r["date"]: r for r in d.get("cash") or []}
    rows = []
    for r in reversed(d.get("positions") or []):
        c = cash_by.get(r["date"], {})
        f, p, cl, di = r.get("fii") or {}, r.get("pro") or {}, r.get("client") or {}, r.get("dii") or {}
        rows.append(f'<tr><td>{pretty(r["date"])}</td><td class="{_cls(c.get("fii_net"))}">{_sg(c.get("fii_net"))}</td><td class="{_cls(c.get("dii_net"))}">{_sg(c.get("dii_net"))}</td>'
                    f'<td class="{_cls(f.get("fut_idx_net"))}">{_sg(f.get("fut_idx_net"))}</td><td>{_sg(f.get("fut_idx_net_chg"))}</td><td>{_sg(f.get("call_net"))}</td><td>{_sg(f.get("put_net"))}</td>'
                    f'<td>{_sg(p.get("fut_idx_net"))}</td><td>{_sg(cl.get("fut_idx_net"))}</td><td>{_sg(di.get("fut_idx_net"))}</td></tr>')
    table = ('<div class="scrollx"><table class="fl"><thead><tr><th>SESSION</th><th>FII CASH ₹CR</th><th>DII CASH ₹CR</th><th>FII IDX FUT NET</th><th>Δ DAY</th><th>FII CALLS NET</th><th>FII PUTS NET</th><th>PRO IDX FUT</th><th>CLIENT IDX FUT</th><th>DII IDX FUT</th></tr></thead>'
             f'<tbody>{"".join(rows) or "<tr><td colspan=10>NSE has not published today’s files yet — check back after 6 pm IST.</td></tr>"}</tbody></table></div>')
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": "FII DII activity and participant-wise F&O positioning (NSE)", "url": "https://finostat.com/fii-dii",
          "description": "Daily FII/FPI and DII cash-market buy, sell and net figures with participant-wise open interest in index futures and options on NSE, updated each evening.",
          "creator": {"@type": "Organization", "name": "Finostat", "url": "https://finostat.com"}, "isAccessibleForFree": True, "license": "https://finostat.com/terms",
          "temporalCoverage": f"{(d.get('positions') or [{'date': pos_date}])[0].get('date')}/{pos_date}", "dateModified": pos_date,
          "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": "https://finostat.com/api/flows?days=60"}}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "What is FII DII data?", "acceptedAnswer": {"@type": "Answer", "text": "Foreign institutional investors (FII/FPI) and domestic institutional investors (DII) report their daily buying and selling in the cash market to the exchanges. Net buying supports the market; sustained FII selling with DII buying is the classic tug-of-war in Indian equities."}},
        {"@type": "Question", "name": "What time is FII DII data released?", "acceptedAnswer": {"@type": "Answer", "text": "NSE publishes the provisional cash-market figures around 6 pm IST after each trading session, and the participant-wise open interest file for derivatives in the evening as well. This page updates automatically when they appear."}},
        {"@type": "Question", "name": "What does FII index futures net mean?", "acceptedAnswer": {"@type": "Answer", "text": "Long contracts minus short contracts held by FIIs in NIFTY, BANKNIFTY and other index futures at the close, from NSE's participant-wise open interest report. A large net short with rising puts is a hedged or bearish book; the day-on-day change shows whether it is being added to or unwound."}}]}
    ld_json = json.dumps(ld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    faq_json = json.dumps(faq, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title><meta name="description" content="{_esc(desc)}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="index, follow, max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com/fii-dii">
<meta property="og:type" content="website"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{_esc(title)}"><meta property="og:description" content="{_esc(desc)}"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com/fii-dii">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{ld_json}</script>
<script type="application/ld+json">{faq_json}</script>
<style>{_CSS}</style></head><body>
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/calendar">CALENDAR</a><a href="/brief">BRIEF</a><a href="/finch">FINCH</a><a href="/dashboard">TERMINAL</a></div></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · FII / DII</nav>
<h1>FII &amp; DII activity today</h1>
<p class="lede">What foreign and domestic institutions did in the cash market, and how FIIs, proprietary desks, clients and DIIs are positioned in NSE index futures and options at the close. Updated every evening from NSE's own reports. Free.</p>
<p class="stamp">CASH · {_esc(pretty(cash_date))} &nbsp;·&nbsp; POSITIONS · {_esc(pretty(pos_date))} &nbsp;·&nbsp; ₹ crore · contracts, net = long − short</p>
<div class="kp">{kp_html}</div>
<div class="two"><div class="cvw"><canvas id="fl-cv1"></canvas></div><div class="cvw"><canvas id="fl-cv2"></canvas></div></div>
<h2 style="font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold-2);margin:16px 0 4px">Last sessions</h2>
{table}
<p><a class="cta" href="/dashboard">Trade it with live chains, Greeks and the implied move on the terminal →</a> <a class="cta ghost" href="/calendar">Economic calendar</a></p>
<section class="faq"><h3>How to read this page</h3><p>FII and DII cash numbers are what the two groups bought and sold in stocks that day, in crore, net buy positive. The positioning figures come from NSE's participant-wise open interest file: contracts outstanding at the close in index futures and index options, by who holds them. FIIs are structurally net short index futures against long cash books, so watch the <em>change</em> more than the level; a fast unwind of shorts often precedes a squeeze, while rising net puts with rising net shorts is protection being bought.</p>
<h3>When does it update?</h3><p>NSE publishes the provisional cash figures around 6 pm IST and the participant file in the evening. The page refreshes itself as soon as they appear, and keeps every session from the day it went live so the history builds into a series you can read across expiries.</p>
<h3>Where does the data come from?</h3><p>NSE's FII/DII trade report and NSE Clearing's participant-wise open interest report, fetched directly from nseindia.com. Finostat reformats, does not alter. Not investment advice.</p></section>
</main>
<script>
(function(){{
  function css(n){{ return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#fff'; }}
  var C={{gold:css('--gold'),cyan:css('--cyan'),faint:css('--faint'),text:css('--text'),mag:'#ff5fd2'}};
  function nf(x){{ return Number(x).toLocaleString('en-IN',{{maximumFractionDigits:0}}); }}
  function ctx2d(cv){{ var r=cv.getBoundingClientRect(), dpr=window.devicePixelRatio||1; var w=Math.max(200,Math.floor(r.width)), h=Math.max(120,Math.floor(r.height)); if(cv.width!==Math.floor(w*dpr)||cv.height!==Math.floor(h*dpr)){{ cv.width=Math.floor(w*dpr); cv.height=Math.floor(h*dpr); }} var c=cv.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,w,h); c.font='10px IBM Plex Mono, monospace'; return {{c:c,w:w,h:h}}; }}
  var data=null;
  function bars(cv,rows){{ var g=ctx2d(cv), c=g.c, pad={{l:56,r:10,t:18,b:20}}; if(!rows.length){{ c.fillStyle=C.faint; c.fillText('cash history builds from today',pad.l,30); return; }}
    var vals=[]; rows.forEach(function(r){{ vals.push(r.fii_net||0); vals.push(r.dii_net||0); }}); var m=Math.max.apply(null,vals.map(Math.abs))||1; var n=rows.length, bw=Math.min(44,(g.w-pad.l-pad.r)/n); var mid=pad.t+(g.h-pad.t-pad.b)/2, half=(g.h-pad.t-pad.b)/2;
    var X=function(i){{ return pad.l+bw*(i+.5); }}, Y=function(v){{ return mid-v/m*half*.9; }};
    c.strokeStyle='rgba(190,150,255,.14)'; c.beginPath(); c.moveTo(pad.l,mid); c.lineTo(g.w-pad.r,mid); c.stroke();
    rows.forEach(function(r,i){{ var a=r.fii_net||0, b=r.dii_net||0; c.fillStyle=a>=0?'rgba(72,232,150,.85)':'rgba(255,92,120,.85)'; c.fillRect(X(i)-bw*.42,Math.min(Y(a),mid),bw*.4,Math.abs(mid-Y(a))); c.fillStyle=b>=0?'rgba(70,225,255,.75)':'rgba(255,95,210,.75)'; c.fillRect(X(i)+bw*.02,Math.min(Y(b),mid),bw*.4,Math.abs(mid-Y(b))); }});
    c.fillStyle=C.faint; c.textAlign='right'; c.fillText('+'+nf(m),pad.l-4,pad.t+8); c.fillText('−'+nf(m),pad.l-4,g.h-pad.b-2); c.textAlign='center'; var every=Math.max(1,Math.round(n/6)); rows.forEach(function(r,i){{ if(i%every===0) c.fillText(r.date.slice(5),X(i),g.h-6); }});
    c.textAlign='left'; c.fillStyle='rgba(72,232,150,.9)'; c.fillText('FII cash ₹cr',pad.l+6,pad.t-5); c.fillStyle='rgba(70,225,255,.9)'; c.fillText('DII cash ₹cr',pad.l+100,pad.t-5); }}
  function lines(cv,rows){{ var g=ctx2d(cv), c=g.c, pad={{l:60,r:10,t:18,b:20}}; if(!rows.length){{ c.fillStyle=C.faint; c.fillText('no positions yet',pad.l,30); return; }}
    var ser=[['fii',C.gold,'FII'],['pro',C.cyan,'PRO'],['client',C.mag,'CLIENT'],['dii','rgba(200,180,255,.8)','DII']]; var vals=[]; rows.forEach(function(r){{ ser.forEach(function(s){{ if(r[s[0]]) vals.push(r[s[0]].fut_idx_net); }}); }}); var lo=Math.min.apply(null,vals), hi=Math.max.apply(null,vals); var m=(hi-lo)*.08||1; lo-=m; hi+=m;
    var n=rows.length; var X=function(i){{ return pad.l+(n>1?i/(n-1):0)*(g.w-pad.l-pad.r); }}, Y=function(v){{ return g.h-pad.b-(v-lo)/(hi-lo)*(g.h-pad.t-pad.b); }};
    c.strokeStyle='rgba(190,150,255,.14)'; c.beginPath(); c.moveTo(pad.l,pad.t); c.lineTo(pad.l,g.h-pad.b); c.lineTo(g.w-pad.r,g.h-pad.b); c.stroke(); if(lo<0&&hi>0){{ c.strokeStyle='rgba(255,255,255,.18)'; c.beginPath(); c.moveTo(pad.l,Y(0)); c.lineTo(g.w-pad.r,Y(0)); c.stroke(); }}
    c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){{ var v=lo+(hi-lo)*i/4; c.fillText(nf(v),pad.l-4,Y(v)+3); }}
    ser.forEach(function(s,si){{ c.strokeStyle=s[1]; c.lineWidth=s[0]==='fii'?2:1.3; c.beginPath(); var st=false; rows.forEach(function(r,i){{ if(!r[s[0]]) return; var y=Y(r[s[0]].fut_idx_net); st?c.lineTo(X(i),y):c.moveTo(X(i),y); st=true; }}); c.stroke(); c.fillStyle=s[1]; c.textAlign='left'; c.fillText(s[2],pad.l+6+si*60,pad.t-5); }});
    c.textAlign='center'; c.fillStyle=C.faint; var every=Math.max(1,Math.round(n/6)); rows.forEach(function(r,i){{ if(i%every===0) c.fillText(r.date.slice(5),X(i),g.h-6); }}); c.textAlign='right'; c.fillStyle=C.text; c.fillText('index futures net (contracts)',g.w-pad.r,pad.t-5); }}
  function draw(){{ if(!data) return; bars(document.getElementById('fl-cv1'),data.cash||[]); lines(document.getElementById('fl-cv2'),data.positions||[]); }}
  fetch('/api/flows?days=60').then(function(r){{ return r.json(); }}).then(function(j){{ data=j; draw(); }}).catch(function(){{}});
  window.addEventListener('resize',draw);
}})();
</script></body></html>"""
    return doc.encode("utf-8")
