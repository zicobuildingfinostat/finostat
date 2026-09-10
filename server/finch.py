"""Finch by Finostat: a derivatives course for beginners, taught on today's market.

Chapters live in finch_part1/finch_part2 as HTML fragments. What makes this
different from a static article is the live widgets: a chapter can drop in the
current NIFTY spot, the live ATM straddle and the expected move it implies, a
chain excerpt with IV and greeks, or a strategy priced off the real chain --
all from the same APIs the terminal uses.
"""
from __future__ import annotations

import json
import re

from finch_part1 import CHAPTERS as _P1
from finch_part2 import CHAPTERS as _P2

CHAPTERS = _P1 + _P2
BY_SLUG = {c["slug"]: c for c in CHAPTERS}

_CSS = r"""
:root{--bg:#0c0626;--panel:#120a33;--panel-hd:#1c1052;--line:#2c1c66;--line-strong:#4a34a0;
  --gold:#f5c842;--gold-2:#ffe27a;--cyan:#7fe0f0;--pink:#ff6ec7;--up:#3dd68c;--down:#ff5c6c;
  --text:#f1edff;--muted:#a89ccf;--faint:#6d609e;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;--body:"IBM Plex Sans",system-ui,sans-serif;
  --display:"Barlow Condensed",Impact,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--bg);scroll-behavior:smooth}
html::after{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(ellipse 70% 40% at 50% 0%,rgba(122,60,245,.42),transparent 70%),var(--bg)}
body{color:var(--text);font-family:var(--body);font-size:16px;line-height:1.65;-webkit-font-smoothing:antialiased;min-height:100vh}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;background:repeating-linear-gradient(0deg,rgba(200,180,255,.03) 0 1px,transparent 1px 3px)}
a{color:var(--cyan);text-decoration:none}a:hover{color:var(--gold)}
.top{display:flex;align-items:center;gap:14px;min-height:48px;padding:6px 16px;background:rgba(12,6,38,.94);border-bottom:1px solid var(--line-strong);font-family:var(--mono);font-size:11px;position:sticky;top:0;z-index:5;flex-wrap:wrap}
.top .logo{font-family:var(--display);font-weight:700;font-size:17px;letter-spacing:.14em;text-transform:uppercase;background:linear-gradient(180deg,#fff 20%,var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}
.top .logo b{color:var(--gold);-webkit-text-fill-color:var(--gold)}
.top .r{margin-left:auto;display:flex;gap:14px;color:var(--faint);letter-spacing:.06em;flex-wrap:wrap}
.top .r a{color:var(--faint)}.top .r a:hover{color:var(--gold)}
.top .home-ic{flex:0 0 auto;width:34px;height:34px;border-radius:9px;overflow:hidden;margin-left:10px;box-shadow:0 0 0 1px rgba(245,200,66,.35),0 0 14px rgba(245,200,66,.22);animation:fino-glow 3.4s ease-in-out infinite}
.top .home-ic img{width:100%;height:100%;display:block}
.top .home-ic:hover{box-shadow:0 0 0 1px var(--gold),0 0 30px rgba(245,200,66,.7);animation:none}
@keyframes fino-glow{0%,100%{box-shadow:0 0 0 1px rgba(245,200,66,.35),0 0 14px rgba(245,200,66,.22)}50%{box-shadow:0 0 0 1px rgba(245,200,66,.7),0 0 26px rgba(245,200,66,.5)}}
@media (prefers-reduced-motion:reduce){.top .home-ic{animation:none}}

.live-dot{color:var(--up);display:inline-flex;align-items:center;gap:6px}
.live-dot::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--up);box-shadow:0 0 8px var(--up);animation:pulse 1.6s infinite}
.live-dot.off{color:var(--faint)}.live-dot.off::before{background:var(--faint);box-shadow:none;animation:none}
@keyframes pulse{50%{opacity:.35}}
.wrap{width:min(1040px,calc(100% - 36px));margin:0 auto;position:relative;z-index:1;padding:30px 0 70px}
.layout{display:grid;grid-template-columns:230px minmax(0,1fr);gap:34px;align-items:start}
.toc{position:sticky;top:64px;font-family:var(--mono);font-size:11.5px}
.toc h4{color:var(--gold);letter-spacing:.16em;text-transform:uppercase;font-size:10.5px;margin-bottom:10px}
.toc ol{list-style:none;counter-reset:ch}
.toc li{counter-increment:ch;margin:0 0 6px;display:flex;gap:8px;align-items:baseline}
.toc li::before{content:counter(ch,decimal-leading-zero);color:var(--faint);font-size:10px}
.toc a{color:var(--muted)}.toc a:hover,.toc li.on a{color:var(--gold)}
.crumb{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.crumb a{color:var(--faint)}
h1{font-family:var(--display);font-weight:600;font-size:clamp(36px,5vw,56px);line-height:.95;text-transform:uppercase;margin:10px 0 8px}
.lede{color:var(--muted);font-size:18px;max-width:64ch;margin-bottom:26px}
article h2{font-family:var(--display);font-weight:600;font-size:28px;letter-spacing:.02em;text-transform:uppercase;margin:38px 0 10px;color:var(--gold-2)}
article h3{font-family:var(--mono);font-size:12.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--cyan);margin:26px 0 8px}
article p{margin:0 0 14px;max-width:72ch}
article ul,article ol{margin:0 0 14px 22px;max-width:70ch}article li{margin:4px 0}
article strong{color:var(--gold-2)}article em{color:var(--cyan);font-style:normal}
article code{font-family:var(--mono);font-size:13px;color:var(--cyan);background:rgba(127,224,240,.08);padding:1px 5px}
article table{border-collapse:collapse;width:100%;max-width:720px;margin:8px 0 18px;font-family:var(--mono);font-size:12.5px}
article th{text-align:left;color:var(--cyan);font-weight:500;padding:7px 10px;border-bottom:1px solid var(--line-strong);font-size:11px;letter-spacing:.08em}
article td{padding:6px 10px;border-bottom:1px solid rgba(190,150,255,.1);vertical-align:top}
article td:first-child{color:var(--gold)}
.scrollx{overflow-x:auto;max-width:100%}
aside{border:1px solid var(--line-strong);border-left:3px solid var(--cyan);padding:12px 16px;margin:16px 0 20px;max-width:72ch;background:rgba(18,10,51,.7)}
aside.warn{border-left-color:var(--down)}aside.tip{border-left-color:var(--gold)}
aside b{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;display:block;margin-bottom:4px;color:var(--cyan)}
aside.warn b{color:var(--down)}aside.tip b{color:var(--gold)}
aside p:last-child{margin-bottom:0}
.example{border:1px solid var(--line-strong);background:var(--panel);margin:16px 0 22px;max-width:760px;box-shadow:0 14px 40px rgba(0,0,0,.35)}
.example .hd{display:flex;align-items:center;gap:12px;padding:7px 12px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);font-family:var(--mono);font-size:11px;letter-spacing:.06em}
.example .hd .k{color:var(--gold);font-weight:600}.example .hd .s{color:var(--cyan)}.example .hd .r{margin-left:auto;color:var(--faint)}
.example .bd{padding:12px 14px;font-family:var(--mono);font-size:12.5px}
.example .bd p{font-family:var(--body);font-size:14px;color:var(--muted);margin:8px 0 0}
.example table{margin:0}
.big{display:flex;gap:22px;flex-wrap:wrap}
.big div{min-width:130px}.big small{display:block;font-size:10px;letter-spacing:.12em;color:var(--faint);text-transform:uppercase}
.big b{font-family:var(--display);font-size:30px;font-weight:600;letter-spacing:.02em}
.up{color:var(--up)}.down{color:var(--down)}
.example svg{width:100%;height:140px;display:block;margin-top:8px}
.example .loading{color:var(--faint)}
.bars{display:grid;grid-template-columns:repeat(auto-fit,minmax(38px,1fr));gap:4px;align-items:end;height:110px;margin-top:8px}
.bars div{background:linear-gradient(180deg,var(--gold-2),#b8862a);position:relative;min-height:4px}
.bars div span{position:absolute;bottom:-16px;left:0;right:0;text-align:center;font-size:9px;color:var(--faint)}
.bars div i{position:absolute;top:-14px;left:0;right:0;text-align:center;font-size:9.5px;color:var(--cyan);font-style:normal}
.cta{display:inline-flex;align-items:center;gap:8px;font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;padding:9px 14px;border:1px solid var(--gold);color:#2a1a02;background:linear-gradient(180deg,var(--gold-2),#f2b830);font-weight:600;margin-top:10px}
.cta:hover{filter:brightness(1.08);color:#000}
.cta.ghost{background:none;color:var(--text);border-color:var(--line-strong)}.cta.ghost:hover{border-color:var(--gold);color:var(--gold)}
.pager{display:flex;justify-content:space-between;gap:14px;margin-top:44px;padding-top:18px;border-top:1px solid var(--line);font-family:var(--mono);font-size:12px}
.pager a{color:var(--muted);max-width:48%}.pager a:hover{color:var(--gold)}.pager small{display:block;color:var(--faint);font-size:10px;letter-spacing:.14em;text-transform:uppercase}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-top:22px}
.card{border:1px solid var(--line-strong);background:var(--panel);padding:18px 18px 16px;display:flex;flex-direction:column;box-shadow:0 14px 40px rgba(0,0,0,.3)}
.card:hover{border-color:var(--gold)}
.card .n{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;color:var(--faint)}
.card h3{font-family:var(--display);font-size:24px;font-weight:600;text-transform:uppercase;line-height:1;margin:6px 0 8px;color:var(--text)}
.card p{color:var(--muted);font-size:14px;flex:1}
.card .go{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--cyan);margin-top:12px}
.glossary dt{font-family:var(--mono);color:var(--gold);margin-top:12px}.glossary dd{color:var(--muted);margin:2px 0 0;max-width:70ch}
.disc{margin-top:40px;font-family:var(--mono);font-size:11px;color:var(--faint);line-height:1.7;max-width:90ch}
@media (max-width:860px){.layout{grid-template-columns:1fr}.toc{position:static;border:1px solid var(--line);padding:12px 14px;margin-bottom:10px}.toc ol{display:grid;grid-template-columns:1fr 1fr;gap:2px 12px}}
"""

_JS = r"""
(function(){
"use strict";
var fmt=function(n,d){ return Number(n).toLocaleString('en-IN',{minimumFractionDigits:d==null?2:d,maximumFractionDigits:d==null?2:d}); };
function esc(s){ return String(s).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
var W=document.querySelectorAll('[data-live]'); if(!W.length) return;
var dot=document.getElementById('live-dot');
var cache={quotes:null,chain:null,strategies:{}};
function setLive(ok){ if(!dot) return; dot.textContent=ok?'LIVE MARKET DATA':'DELAYED'; dot.classList.toggle('off',!ok); }
function q(sym){ return (cache.quotes||[]).filter(function(x){ return x.symbol===sym; })[0]; }
function expiryStr(ms){ return new Date(ms).toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}); }
function render(){
  var c=cache.chain, atm=c&&c.rows?c.rows.filter(function(r){ return r.atm; })[0]:null;
  Array.prototype.forEach.call(W,function(el){
    var t=el.getAttribute('data-live');
    if(t==='spot'){
      var syms=['NIFTY 50','BANKNIFTY','SENSEX','INDIA VIX'];
      el.innerHTML='<div class="big">'+syms.map(function(s){ var x=q(s); return '<div><small>'+s+'</small><b>'+(x?fmt(x.price):'—')+'</b>'+(x?'<span class="'+(x.change>=0?'up':'down')+'"> '+(x.change>=0?'▲':'▼')+' '+Math.abs(x.change).toFixed(2)+'%</span>':'')+'</div>'; }).join('')+'</div>';
    } else if(t==='lot'){
      if(!c||!c.rows){ el.innerHTML='<span class="loading">loading the live NIFTY chain…</span>'; return; }
      el.innerHTML='<div class="big"><div><small>Lot size</small><b>'+c.lot+'</b></div><div><small>Nearest expiry</small><b style="font-size:20px">'+expiryStr(c.expiry)+'</b></div><div><small>Strike step</small><b>'+c.step+'</b></div><div><small>At-the-money strike</small><b>'+c.atm+'</b></div></div><p>Spot '+fmt(c.spot)+'. One lot of NIFTY controls '+c.lot+' × '+fmt(c.spot,0)+' ≈ ₹'+fmt(c.lot*c.spot,0)+' of index exposure.</p>';
    } else if(t==='chain'){
      if(!c||!c.rows){ el.innerHTML='<span class="loading">loading the live NIFTY chain…</span>'; return; }
      var i=c.rows.findIndex(function(r){ return r.atm; }); var rows=c.rows.slice(Math.max(0,i-3),i+4), hasOi=!!c.oi;
      var k=function(n){ if(n==null) return '—'; return n>=1e5?(n/1e5).toFixed(1)+'L':n>=1000?(n/1000).toFixed(0)+'k':String(n); };
      el.innerHTML='<div class="scrollx"><table><thead><tr>'+(hasOi?'<th>CE OI</th>':'')+'<th>CE LTP</th><th>CE IV</th><th>CE Δ</th><th>STRIKE</th><th>PE Δ</th><th>PE IV</th><th>PE LTP</th>'+(hasOi?'<th>PE OI</th>':'')+'</tr></thead><tbody>'+rows.map(function(r){
        var ce=r.ce||{},pe=r.pe||{}; return '<tr'+(r.atm?' style="background:rgba(106,53,240,.25)"':'')+'>'+(hasOi?'<td>'+k(ce.oi)+'</td>':'')+'<td style="color:var(--text)">'+(ce.ltp!=null?fmt(ce.ltp):'—')+'</td><td>'+(ce.iv!=null?ce.iv.toFixed(1)+'%':'—')+'</td><td>'+(ce.delta!=null?ce.delta.toFixed(2):'—')+'</td><td style="color:var(--gold)">'+r.strike+(r.atm?' <small style="color:var(--faint)">ATM</small>':'')+'</td><td>'+(pe.delta!=null?pe.delta.toFixed(2):'—')+'</td><td>'+(pe.iv!=null?pe.iv.toFixed(1)+'%':'—')+'</td><td style="color:var(--text)">'+(pe.ltp!=null?fmt(pe.ltp):'—')+'</td>'+(hasOi?'<td>'+k(pe.oi)+'</td>':'')+'</tr>'; }).join('')+'</tbody></table></div><p>NIFTY spot '+fmt(c.spot)+' · expiry '+expiryStr(c.expiry)+' · '+(c.live?'live':'last traded')+'. Calls get cheaper as strikes rise; puts get dearer. The ATM row is where time value peaks.'+(hasOi?' Open interest right now: PCR '+(c.oi.pcr!=null?c.oi.pcr.toFixed(2):'—')+', max pain '+(c.oi.max_pain!=null?fmt(c.oi.max_pain,0):'—')+(c.oi.call_wall?', biggest call OI above spot at '+fmt(c.oi.call_wall,0):'')+(c.oi.put_wall?', biggest put OI below at '+fmt(c.oi.put_wall,0):'')+'.':'')+'</p>';
    } else if(t==='straddle'){
      if(!atm||!atm.ce||!atm.pe){ el.innerHTML='<span class="loading">loading the live ATM straddle…</span>'; return; }
      var st=atm.ce.ltp+atm.pe.ltp, pct=st/c.spot*100, days=Math.max(0,c.t_years*365);
      el.innerHTML='<div class="big"><div><small>ATM straddle ('+c.atm+')</small><b>₹'+fmt(st)+'</b></div><div><small>Implied move to expiry</small><b>± '+pct.toFixed(2)+'%</b></div><div><small>In index points</small><b>± '+fmt(st,0)+'</b></div><div><small>Days to expiry</small><b>'+days.toFixed(1)+'</b></div></div><p>Buyers of this straddle need NIFTY to close beyond '+fmt(c.spot-st,0)+' or '+fmt(c.spot+st,0)+' on '+expiryStr(c.expiry)+' just to break even. Sellers keep the premium if it stays inside.</p>';
    } else if(t==='greeks'){
      if(!atm||!atm.ce||!atm.pe){ el.innerHTML='<span class="loading">loading live greeks…</span>'; return; }
      var g=function(o){ return '<td>'+(o.delta!=null?o.delta.toFixed(3):'—')+'</td><td>'+(o.gamma!=null?o.gamma.toFixed(5):'—')+'</td><td>'+(o.theta!=null?o.theta.toFixed(2):'—')+'</td><td>'+(o.vega!=null?o.vega.toFixed(2):'—')+'</td>'; };
      el.innerHTML='<div class="scrollx"><table><thead><tr><th>'+c.atm+' (ATM)</th><th>DELTA</th><th>GAMMA</th><th>THETA /day</th><th>VEGA /1%</th></tr></thead><tbody><tr><td>CE @ '+fmt(atm.ce.ltp)+'</td>'+g(atm.ce)+'</tr><tr><td>PE @ '+fmt(atm.pe.ltp)+'</td>'+g(atm.pe)+'</tr></tbody></table></div><p>Per share. Multiply by the lot ('+c.lot+') for one contract: a long ATM call loses about ₹'+fmt(Math.abs(atm.ce.theta||0)*c.lot,0)+' a day to time decay right now, and gains about ₹'+fmt((atm.ce.delta||0)*c.lot,0)+' if NIFTY rises one point.</p>';
    } else if(t==='smile'){
      if(!c||!c.rows){ el.innerHTML='<span class="loading">loading the live IV smile…</span>'; return; }
      var rs=c.rows.filter(function(r){ return r.ce&&r.pe&&r.ce.iv!=null&&r.pe.iv!=null; });
      var vals=rs.map(function(r){ return r.strike<c.atm?r.pe.iv:r.strike>c.atm?r.ce.iv:(r.ce.iv+r.pe.iv)/2; }); var mx=Math.max.apply(null,vals)||1;
      el.innerHTML='<div class="bars">'+rs.map(function(r,i){ return '<div style="height:'+Math.max(4,vals[i]/mx*100)+'%"'+(r.atm?' title="ATM"':'')+'><i>'+vals[i].toFixed(1)+'</i><span>'+r.strike+'</span></div>'; }).join('')+'</div><p style="margin-top:24px">Implied volatility (%) by strike, using puts below the money and calls above. When the wings sit higher than the middle, the market is paying up for protection — that shape is the “smile”, and its tilt is the “skew”.</p>';
    } else if(t==='strategy'){
      var p=el.getAttribute('data-preset'), d=cache.strategies[p];
      if(!d||!d.legs){ el.innerHTML='<span class="loading">pricing '+p.replace(/-/g,' ')+' off the live chain…</span>'; return; }
      var m=d.metrics, money=function(v){ return v==null?'UNLIMITED':'₹'+fmt(v,0); };
      var pts=m.payoff||[], xs=pts.map(function(x){ return x[0]; }), ys=pts.map(function(x){ return x[1]; });
      var x0=xs[0],x1=xs[xs.length-1],ymax=Math.max.apply(null,ys.concat([0])),ymin=Math.min.apply(null,ys.concat([0])),sp=(ymax-ymin)||1;
      var X=function(x){ return (x-x0)/(x1-x0)*320; }, Y=function(y){ return 6+(ymax-y)/sp*128; }, zero=Y(0).toFixed(1);
      var path=pts.map(function(x,i){ return (i?'L':'M')+X(x[0]).toFixed(1)+' '+Y(x[1]).toFixed(1); }).join(' ');
      var pos='M'+X(x0).toFixed(1)+' '+zero+' '+pts.map(function(x){ return 'L'+X(x[0]).toFixed(1)+' '+Y(Math.max(0,x[1])).toFixed(1); }).join(' ')+' L'+X(x1).toFixed(1)+' '+zero+' Z';
      var neg='M'+X(x0).toFixed(1)+' '+zero+' '+pts.map(function(x){ return 'L'+X(x[0]).toFixed(1)+' '+Y(Math.min(0,x[1])).toFixed(1); }).join(' ')+' L'+X(x1).toFixed(1)+' '+zero+' Z';
      el.innerHTML='<div class="scrollx"><table><thead><tr><th>SIDE</th><th>QTY</th><th>TYPE</th><th>STRIKE</th><th>LTP</th><th>IV</th></tr></thead><tbody>'+d.legs.map(function(l){ return '<tr><td style="color:'+(l.qty>0?'var(--up)':'var(--down)')+'">'+(l.qty>0?'BUY':'SELL')+'</td><td>'+Math.abs(l.qty)+' lot</td><td>'+l.right+'</td><td>'+l.strike+'</td><td style="color:var(--text)">'+fmt(l.price)+'</td><td>'+(l.iv!=null?l.iv.toFixed(1)+'%':'—')+'</td></tr>'; }).join('')+'</tbody></table></div>'
        +'<div class="big" style="margin-top:12px"><div><small>net '+(m.net_premium>=0?'credit':'debit')+' / lot</small><b>₹'+fmt(Math.abs(m.net_premium_lot),0)+'</b></div><div><small>max profit</small><b class="up">'+money(m.max_profit_lot)+'</b></div><div><small>max loss</small><b class="down">'+money(m.max_loss_lot)+'</b></div><div><small>breakevens</small><b style="font-size:20px">'+(m.breakevens||[]).map(function(b){ return fmt(b,0); }).join(' / ')+'</b></div></div>'
        +'<svg viewBox="0 0 320 140" preserveAspectRatio="none"><path d="'+pos+'" fill="rgba(61,214,140,.18)"/><path d="'+neg+'" fill="rgba(255,92,108,.18)"/><line x1="0" y1="'+zero+'" x2="320" y2="'+zero+'" stroke="#4a34a0" stroke-dasharray="3 3"/><line x1="'+X(d.spot).toFixed(1)+'" y1="4" x2="'+X(d.spot).toFixed(1)+'" y2="136" stroke="#7fe0f0" stroke-dasharray="2 3"/><path d="'+path+'" fill="none" stroke="#f5c842" stroke-width="1.8"/></svg>'
        +'<p>NIFTY '+fmt(d.spot)+' · expiry '+expiryStr(d.expiry)+' · lot '+d.lot+'. Payoff at expiry per lot; the dotted line is spot. <a class="cta ghost" href="/dashboard#p-builder">Open this in the builder →</a></p>';
    }
  });
}
function load(){
  fetch('/api/quotes').then(function(r){ return r.json(); }).then(function(qs){ cache.quotes=qs; setLive(true); render(); }).catch(function(){ setLive(false); });
  var needChain=Array.prototype.some.call(W,function(el){ return ['chain','straddle','greeks','smile','lot'].indexOf(el.getAttribute('data-live'))>=0; });
  if(needChain) fetch('/api/chain?u=NIFTY%2050').then(function(r){ return r.json(); }).then(function(c){ if(c&&c.rows) cache.chain=c; render(); }).catch(function(){});
  var presets={}; Array.prototype.forEach.call(W,function(el){ if(el.getAttribute('data-live')==='strategy') presets[el.getAttribute('data-preset')]=1; });
  Object.keys(presets).forEach(function(p){
    fetch('/api/strategy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:'NIFTY 50',preset:p})}).then(function(r){ return r.json(); }).then(function(d){ if(d&&d.legs) cache.strategies[p]=d; render(); }).catch(function(){});
  });
}
render(); load(); setInterval(load, 10000);
})();
"""

_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title><meta name="description" content="__DESC__"><meta name="theme-color" content="#0c0626">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com__PATH__">
<meta property="og:type" content="article"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="__TITLE__"><meta property="og:description" content="__DESC__"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com__PATH__">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
__LD__<style>__CSS__</style></head><body>
<header class="top"><a class="logo" href="/finch">FINCH<b>·</b>BY FINOSTAT</a><div class="r"><span class="live-dot off" id="live-dot">MARKET DATA</span><a href="/dashboard">TERMINAL</a><a href="/">SITE</a></div><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="34" height="34"></a></header>
<main class="wrap">"""

_FOOT = """<p class="disc">Finch is education, not advice. Every number marked live is today's real market, which is exactly why the examples will not match what you read yesterday. Derivatives can lose more than you put in; nothing here is a recommendation to trade. Finostat is not affiliated with NSE, BSE, MCX or SEBI.</p>
</main><script>__JS__</script></body></html>"""


_AUTHOR = {"@type": "Person", "@id": "https://finostat.com/founders#person", "name": "Zico Karmakar", "url": "https://finostat.com/founders"}
_PUB = {"@type": "Organization", "@id": "https://finostat.com/#org", "name": "Finostat", "url": "https://finostat.com/", "logo": {"@type": "ImageObject", "url": "https://finostat.com/og.jpg"}}


def _ld(obj) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def _ld_course() -> str:
    return _ld({"@context": "https://schema.org", "@type": "Course", "@id": "https://finostat.com/finch", "url": "https://finostat.com/finch",
                "name": "Finch by Finostat — F&O and options trading for beginners",
                "description": "A free twelve-chapter derivatives course taught on the live Indian market: futures, options, the Greeks, implied volatility, expiry, strategies and risk.",
                "provider": _PUB, "author": _AUTHOR, "isAccessibleForFree": True, "inLanguage": "en-IN",
                "hasCourseInstance": {"@type": "CourseInstance", "courseMode": "online", "courseWorkload": "PT4H"},
                "hasPart": [{"@type": "Article", "name": c["title"], "url": f"https://finostat.com/finch/{c['slug']}"} for c in CHAPTERS]})


def _ld_article(c: dict, n: int) -> str:
    return _ld({"@context": "https://schema.org", "@type": "Article", "@id": f"https://finostat.com/finch/{c['slug']}",
                "mainEntityOfPage": f"https://finostat.com/finch/{c['slug']}", "headline": c["title"], "description": c["summary"],
                "author": _AUTHOR, "publisher": _PUB, "isPartOf": {"@id": "https://finostat.com/finch"}, "position": n,
                "datePublished": "2026-09-08", "dateModified": "2026-09-08", "inLanguage": "en-IN", "isAccessibleForFree": True,
                "image": "https://finostat.com/og.jpg"})


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def _toc(current: str | None) -> str:
    parts = []
    for c in CHAPTERS:
        cls = ' class="on"' if c["slug"] == current else ""
        parts.append(f'<li{cls}><a href="/finch/{c["slug"]}">{_esc(c["title"])}</a></li>')
    items = "".join(parts)
    return f'<nav class="toc"><h4>Finch · chapters</h4><ol>{items}</ol></nav>'


def render_index() -> bytes:
    cards = "".join(
        f'<a class="card" href="/finch/{c["slug"]}"><span class="n">CHAPTER {i:02d} · {_esc(c["level"])}</span>'
        f'<h3>{_esc(c["title"])}</h3><p>{_esc(c["summary"])}</p><span class="go">Read →</span></a>'
        for i, c in enumerate(CHAPTERS, 1))
    body = f"""<nav class="crumb"><a href="/">FINO</a> · FINCH</nav>
<h1>Finch</h1>
<p class="lede">A derivatives course for people who have never traded an option, taught on <em>today's</em> market. Every chapter pulls the live NIFTY chain, straddle and greeks from the same feed the Finostat terminal runs on — so the examples are real, and they change while you read.</p>
<div class="example"><div class="hd"><span class="k">LIVE</span><span class="s">RIGHT NOW</span><span class="r">refreshes every 10s</span></div><div class="bd"><div data-live="spot"></div></div></div>
<div class="grid">{cards}</div>"""
    doc = (_HEAD.replace("__TITLE__", "Finch by Finostat — learn F&O and options trading on the live market")
           .replace("__DESC__", "A free, deep derivatives course for beginners: futures, options, the Greeks, implied volatility, expiry mechanics, strategies and risk — with live NIFTY examples.")
           .replace("__PATH__", "/finch").replace("__LD__", _ld_course()).replace("__CSS__", _CSS))
    return (doc + body + _FOOT.replace("__JS__", _JS)).encode("utf-8")


def render_chapter(slug: str) -> bytes | None:
    c = BY_SLUG.get(slug)
    if c is None:
        return None
    i = CHAPTERS.index(c)
    prev_ = CHAPTERS[i - 1] if i > 0 else None
    next_ = CHAPTERS[i + 1] if i + 1 < len(CHAPTERS) else None
    pager = '<div class="pager">'
    pager += (f'<a href="/finch/{prev_["slug"]}"><small>← Previous</small>{_esc(prev_["title"])}</a>' if prev_ else '<a href="/finch"><small>← Back</small>All chapters</a>')
    pager += (f'<a href="/finch/{next_["slug"]}" style="text-align:right"><small>Next →</small>{_esc(next_["title"])}</a>' if next_ else '<a href="/dashboard" style="text-align:right"><small>Next →</small>Open the terminal</a>')
    pager += '</div>'
    body = f"""<nav class="crumb"><a href="/">FINO</a> · <a href="/finch">FINCH</a> · CHAPTER {i + 1:02d}</nav>
<div class="layout">{_toc(slug)}<div>
<h1>{_esc(c["title"])}</h1>
<p class="lede">{_esc(c["summary"])}</p>
<article>{c["body"]}</article>
{pager}</div></div>"""
    doc = (_HEAD.replace("__TITLE__", _esc(c["title"]) + " — Finch by Finostat")
           .replace("__DESC__", _esc(c["summary"])).replace("__PATH__", f"/finch/{slug}").replace("__LD__", _ld_article(c, i + 1)).replace("__CSS__", _CSS))
    return (doc + body + _FOOT.replace("__JS__", _JS)).encode("utf-8")


def internal_links() -> list[str]:
    """Every /finch/... link used inside chapter bodies (for the tests)."""
    out = []
    for c in CHAPTERS:
        out += re.findall(r'href="(/finch/[a-z0-9-]+)"', c["body"])
    return out
