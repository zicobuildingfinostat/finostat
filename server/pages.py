"""Server-rendered product pages: the /dashboard terminal (and friends).

Each page is a self-contained HTML document in the same visual language as
index.html (indigo desk, gold/cyan accents, IBM Plex Mono). The server injects
a snapshot seed so the first paint shows data instantly; after that the page
rides the same SSE streams the homepage uses.
"""
from __future__ import annotations

import json


def _seed(snapshot: dict) -> str:
    payload = {
        "rows": snapshot.get("sheet", {}).get("rows", []),
        "quotes": snapshot.get("quotes", []),
        "mini": snapshot.get("mini", []),
        "atm": snapshot.get("atm"),
        "straddle": snapshot.get("straddle"),
        "symbol": snapshot.get("symbol", "NIFTY"),
        "live": bool(snapshot.get("live")),
    }
    return json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Finostat Terminal</title>
<meta name="robots" content="noindex">
<meta name="theme-color" content="#0c0626">
<link rel="icon" href="/og.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0c0626;--panel:#120a33;--panel-hd:#1c1052;--violet:#6a35f0;
  --line:#2c1c66;--line-strong:#4a34a0;--gold:#f5c842;--gold-2:#ffe27a;
  --cyan:#7fe0f0;--pink:#ff6ec7;--up:#3dd68c;--down:#ff5c6c;
  --text:#f1edff;--muted:#a89ccf;--faint:#6d609e;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
  --body:"IBM Plex Sans",system-ui,sans-serif;
  --display:"Barlow Condensed",Impact,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
html{background:var(--bg)}
body{color:var(--text);font-family:var(--mono);font-size:12.5px;line-height:1.45;
  display:flex;flex-direction:column;min-height:100vh;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:repeating-linear-gradient(0deg,rgba(200,180,255,.03) 0 1px,transparent 1px 3px)}
a{color:inherit;text-decoration:none}
button,input,select{font:inherit;color:inherit}
button{cursor:pointer;background:none;border:0}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px}

/* top bar */
.top{display:flex;align-items:center;gap:14px;height:44px;padding:0 14px;
  background:rgba(12,6,38,.95);border-bottom:1px solid var(--line-strong);position:relative;z-index:2}
.top .logo{font-family:var(--display);font-weight:700;font-size:17px;letter-spacing:.14em;text-transform:uppercase;
  background:linear-gradient(180deg,#fff 20%,var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}
.top .logo b{color:var(--gold);-webkit-text-fill-color:var(--gold)}
.top .sym{color:var(--cyan);font-size:11.5px;letter-spacing:.08em}
.top .r{margin-left:auto;display:flex;gap:16px;align-items:center;font-size:11px;color:var(--faint);letter-spacing:.06em}
.top .r a:hover{color:var(--gold)}
.live{color:var(--up);display:inline-flex;align-items:center;gap:6px}
.live::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--up);box-shadow:0 0 8px var(--up);animation:pulse 1.6s infinite}
.live.off{color:var(--down)}.live.off::before{background:var(--down);box-shadow:none;animation:none}
@keyframes pulse{50%{opacity:.35}}
.mkt{color:var(--up)}.mkt.closed{color:var(--down)}

/* tape */
.tape{background:#06031a;border-bottom:1px solid var(--line);overflow:hidden;font-size:11.5px;position:relative;z-index:1;white-space:nowrap}
.tape-inner{display:inline-flex;width:max-content;animation:tape 60s linear infinite}
.tape:hover .tape-inner{animation-play-state:paused}
.tape span{padding:6px 18px;border-right:1px solid var(--line);display:inline-flex;gap:9px}
.tape b{color:var(--cyan);font-weight:500}
.tape em{font-style:normal}
@keyframes tape{to{transform:translateX(-50%)}}
.up{color:var(--up)}.down{color:var(--down)}

/* grid */
.desk{flex:1;display:grid;gap:10px;padding:10px;position:relative;z-index:1;
  grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);
  grid-template-rows:minmax(300px,1.25fr) minmax(220px,1fr);
  grid-template-areas:"sheet side" "wire side2";
  max-width:1500px;margin:0 auto;width:100%}
.a-sheet{grid-area:sheet}.a-side{grid-area:side;display:flex;flex-direction:column;gap:10px;min-height:0}
.a-wire{grid-area:wire}.a-side2{grid-area:side2}
.panel{background:var(--panel);border:1px solid var(--line-strong);display:flex;flex-direction:column;min-width:0;min-height:0;box-shadow:0 14px 40px rgba(0,0,0,.35)}
.panel-hd{display:flex;align-items:center;gap:12px;padding:6px 11px;background:var(--panel-hd);border-bottom:1px solid var(--line-strong);font-size:11px;letter-spacing:.06em;flex-shrink:0}
.panel-hd .k{color:var(--gold);font-weight:600}
.panel-hd .s{color:var(--cyan)}
.panel-hd .r{margin-left:auto;color:var(--faint);display:flex;gap:10px;align-items:center}
.scroll{overflow-y:auto;flex:1;min-height:0;scrollbar-width:thin;scrollbar-color:var(--line-strong) transparent}

/* tables */
table{width:100%;border-collapse:collapse}
th{font-weight:500;color:var(--cyan);text-align:right;padding:6px 11px;border-bottom:1px solid var(--line);font-size:10.5px;letter-spacing:.08em;position:sticky;top:0;background:var(--panel);z-index:1}
th:first-child,td:first-child{text-align:left}
td{padding:5px 11px;text-align:right;border-bottom:1px solid rgba(190,150,255,.08);font-variant-numeric:tabular-nums;transition:background .4s,color .4s}
td:first-child{color:var(--gold)}
tr.atm td{background:rgba(106,53,240,.25)}
tr.atm td:first-child::after{content:" ATM";color:var(--faint);font-size:9.5px}
td.flash-up{background:rgba(61,214,140,.2);color:var(--up)}
td.flash-down{background:rgba(255,92,108,.2);color:var(--down)}

/* straddle chart */
.chart{padding:8px 10px 4px;flex:1;display:flex;flex-direction:column;min-height:96px}
.chart svg{width:100%;flex:1;min-height:0}
.chart .legend{display:flex;justify-content:space-between;font-size:10px;color:var(--faint);letter-spacing:.06em;margin-top:2px}
.chart .legend b{color:var(--gold);font-weight:500}

/* alerts */
.al-form{display:grid;grid-template-columns:1.2fr .9fr .55fr .8fr auto;gap:6px;padding:9px 10px;border-bottom:1px solid var(--line)}
.al-form select,.al-form input{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font-size:11px;padding:5px 6px;min-width:0}
.al-form button{background:var(--gold);color:#2a1a02;font-weight:600;font-size:10.5px;letter-spacing:.08em;padding:5px 10px}
.al-form button:hover{filter:brightness(1.1)}
.al-list li{display:grid;grid-template-columns:1fr auto auto;gap:8px;padding:7px 10px;border-bottom:1px solid rgba(190,150,255,.08);align-items:center;font-size:11.5px}
.al-list b{color:var(--text);font-weight:500}
.al-list small{color:var(--faint);display:block;font-size:10px;margin-top:1px}
.al-list .tag{font-size:9.5px;letter-spacing:.08em;padding:2px 6px;border:1px solid var(--line-strong);color:var(--muted);white-space:nowrap}
.al-list .tag.hot{color:var(--up);border-color:var(--up)}
.al-list .tag.fired{color:var(--gold);border-color:var(--gold);animation:pulse 1.2s infinite}
.al-list button{color:var(--faint);font-size:10px;letter-spacing:.06em}
.al-list button:hover{color:var(--down)}
.al-list button.rearm:hover{color:var(--gold)}
.al-log{border-top:1px solid var(--line)}
.al-log li{padding:5px 10px;border-bottom:1px solid rgba(190,150,255,.06);font-size:10.5px;color:var(--muted);display:flex;gap:8px}
.al-log time{color:var(--faint)}
.al-empty{padding:12px 10px;color:var(--faint);font-size:11px}
.al-tools{display:flex;gap:8px;padding:6px 10px;border-top:1px solid var(--line)}
.al-tools button{font-size:10px;letter-spacing:.08em;color:var(--muted);border:1px solid var(--line-strong);padding:3px 8px}
.al-tools button:hover{color:var(--gold);border-color:var(--gold)}
.al-tools button.on{color:var(--up);border-color:var(--up)}

/* wire */
.wire-list li{display:grid;grid-template-columns:42px 1fr;gap:9px;padding:7px 11px;border-bottom:1px solid rgba(190,150,255,.08);align-items:baseline}
.wire-list li:hover{background:rgba(106,53,240,.15)}
.wire-list li.new{animation:wire-in .9s ease-out}
@keyframes wire-in{from{background:rgba(245,200,66,.25)}}
.wire-list time{color:var(--faint);font-variant-numeric:tabular-nums;font-size:10.5px}
.wire-list a{font-family:var(--body);font-size:12.5px;color:var(--text);line-height:1.35;display:block}
.wire-list a:hover{color:var(--gold)}
.wire-list .meta{display:flex;gap:8px;margin-top:2px;font-size:9.5px;letter-spacing:.08em;color:var(--faint)}
.wire-list .meta .tag{color:var(--cyan)}
.wire-list .meta .tag.fin{color:var(--gold)}
.wire-list li.hot .meta::before{content:"BREAKING";color:var(--pink);font-weight:600}

@media (max-width:560px){
  .top{flex-wrap:wrap;height:auto;min-height:44px;padding:6px 10px;row-gap:2px;gap:10px}
  .top .sym{display:none}
  .top .r{gap:10px;flex-wrap:wrap}
}
@media (max-width:980px){
  .desk{grid-template-columns:1fr;grid-template-rows:auto;grid-template-areas:"sheet" "side" "side2" "wire"}
  .a-sheet{min-height:340px}
  .al-form{grid-template-columns:1fr 1fr;grid-auto-rows:auto}
  .al-form button{grid-column:1/-1}
}
@media (prefers-reduced-motion:reduce){.tape-inner{animation:none}.live::before{animation:none}}
</style>
</head>
<body>

<header class="top">
  <a class="logo" href="/">FINO<b>·</b>TERMINAL</a>
  <span class="sym" id="t-sym">NIFTY · NEAREST EXPIRY</span>
  <div class="r">
    <span class="live off" id="conn">CONNECTING</span>
    <span id="clock">--:--:-- IST</span>
    <span class="mkt" id="mkt">NSE —</span>
    <a href="/">← SITE</a>
  </div>
</header>

<div class="tape" aria-label="Market ticker"><div class="tape-inner" id="tape"></div></div>

<main class="desk">

  <section class="panel a-sheet" aria-label="Butterfly sheet">
    <div class="panel-hd"><span class="k">BFLY</span><span class="s" id="sheet-sym">NIFTY</span><span>1:2:1</span>
      <span class="r"><span id="sheet-note">seeded</span></span></div>
    <div class="scroll"><table>
      <thead><tr><th>STRIKE</th><th>CE</th><th>PE</th><th>BFLY</th><th>NET</th></tr></thead>
      <tbody id="rows"></tbody>
    </table></div>
  </section>

  <div class="a-side">
    <section class="panel" style="flex:1" aria-label="ATM straddle">
      <div class="panel-hd"><span class="k">STRD</span><span class="s">ATM STRADDLE</span>
        <span class="r"><b id="strd-last" style="color:var(--gold)">—</b></span></div>
      <div class="chart">
        <svg viewBox="0 0 300 110" preserveAspectRatio="none" aria-hidden="true">
          <path id="strd-area" fill="rgba(245,200,66,.12)"></path>
          <path id="strd-line" fill="none" stroke="var(--gold)" stroke-width="1.6"></path>
        </svg>
        <div class="legend"><span id="strd-min">—</span><span>session</span><span id="strd-max">—</span></div>
      </div>
    </section>

    <section class="panel" style="flex:1.25" aria-label="Alerts">
      <div class="panel-hd"><span class="k">ALRT</span><span class="s">MY ALERTS</span>
        <span class="r"><span id="al-count">0 ARMED</span></span></div>
      <form class="al-form" id="al-form">
        <select id="al-metric"></select>
        <select id="al-strike" disabled><option value="">strike…</option></select>
        <select id="al-cmp"><option value=">=">≥</option><option value="<=">≤</option></select>
        <input id="al-value" type="number" step="any" placeholder="value" required>
        <button type="submit">ARM</button>
      </form>
      <ul class="al-list scroll" id="al-list" style="flex:1.2"></ul>
      <ul class="al-log scroll" id="al-log" style="flex:1;max-height:110px"></ul>
      <div class="al-tools">
        <button type="button" id="al-notif">ENABLE DESKTOP ALERTS</button>
        <button type="button" id="al-sound">SOUND: ON</button>
      </div>
    </section>
  </div>

  <section class="panel a-wire" aria-label="News wire">
    <div class="panel-hd"><span class="k">WIRE</span><span class="s">FIN · GEO</span>
      <span class="r"><span class="live off" id="wire-live">RSS</span></span></div>
    <ul class="wire-list scroll" id="wire-list"></ul>
  </section>

  <section class="panel a-side2" aria-label="Mini sheet">
    <div class="panel-hd"><span class="k">MINI</span><span class="s" id="mini-sym">BANKNIFTY · BUY/SELL</span></div>
    <div class="scroll"><table>
      <thead><tr><th>STRIKE</th><th>BUY</th><th>SELL</th><th>Δ</th></tr></thead>
      <tbody id="mini-rows"></tbody>
    </table></div>
  </section>

</main>

<script>window.SEED=__SEED__;</script>
<script>
(function(){
"use strict";
var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
var fmt = function(n,d){ return n.toLocaleString('en-IN',{minimumFractionDigits:d==null?2:d,maximumFractionDigits:d==null?2:d}); };

/* ---------- state ---------- */
var state = { rows:[], quotes:[], mini:[], atm:null, straddle:null, symbol:'NIFTY', live:false, lastEvent:0 };

/* ---------- tape ---------- */
var tapeEl = document.getElementById('tape');
function renderTape(qs){
  if(!qs || !qs.length) return;
  var b = qs.map(function(x){
    return '<span><b>'+x.symbol+'</b>'+fmt(x.price)+'<em class="'+(x.change>=0?'up':'down')+'">'+(x.change>=0?'▲':'▼')+' '+Math.abs(x.change).toFixed(2)+'%</em></span>';
  }).join('');
  tapeEl.innerHTML = b + b;
}

/* ---------- sheet ---------- */
var rowsEl = document.getElementById('rows');
var cellIndex = {};
function renderSheet(rows, atm){
  rowsEl.innerHTML = rows.map(function(r){
    var atmCls = (r[0]===atm) ? ' class="atm"' : '';
    var net = r[4];
    return '<tr'+atmCls+' data-k="'+r[0]+'"><td>'+r[0]+'</td>'
      + [1,2,3].map(function(j){ return '<td data-c="'+j+'">'+r[j].toFixed(1)+'</td>'; }).join('')
      + '<td data-c="4" class="'+(net>0?'up':net<0?'down':'')+'">'+net.toFixed(1)+'</td></tr>';
  }).join('');
  cellIndex = {};
  Array.prototype.forEach.call(rowsEl.querySelectorAll('tr'), function(tr){
    var k = tr.getAttribute('data-k');
    Array.prototype.forEach.call(tr.querySelectorAll('td[data-c]'), function(td){
      cellIndex[k+':'+td.getAttribute('data-c')] = td;
    });
  });
}
function applySheet(rows, atm){
  var sameShape = state.rows.length===rows.length && state.rows.every(function(r,i){ return r[0]===rows[i][0]; });
  if(!sameShape || state.atm!==atm){ renderSheet(rows, atm); state.rows=rows; state.atm=atm; return; }
  rows.forEach(function(r,i){
    for(var j=1;j<=4;j++){
      var nv=r[j], ov=state.rows[i][j];
      if(nv===ov) continue;
      var cell=cellIndex[r[0]+':'+j];
      if(!cell) continue;
      cell.textContent=nv.toFixed(1);
      if(j===4){ cell.classList.toggle('up',nv>0); cell.classList.toggle('down',nv<0); }
      if(!reduce){
        cell.classList.remove('flash-up','flash-down'); void cell.offsetWidth;
        cell.classList.add(nv>=ov?'flash-up':'flash-down');
        (function(c){ setTimeout(function(){ c.classList.remove('flash-up','flash-down'); },500); })(cell);
      }
    }
  });
  state.rows=rows;
}

/* ---------- mini ---------- */
var miniEl = document.getElementById('mini-rows');
function renderMini(mini){
  if(!mini || !mini.length){ miniEl.innerHTML='<tr><td colspan="4" style="color:var(--faint)">waiting for feed…</td></tr>'; return; }
  miniEl.innerHTML = mini.map(function(r){
    var d = r[1]+r[2];
    return '<tr><td>'+r[0]+'</td><td>'+r[1].toFixed(1)+'</td><td class="down">'+r[2].toFixed(1)+'</td><td class="'+(d>=0?'up':'down')+'">'+d.toFixed(1)+'</td></tr>';
  }).join('');
}

/* ---------- straddle chart ---------- */
var pts=[], lineEl=document.getElementById('strd-line'), areaEl=document.getElementById('strd-area');
var lastEl=document.getElementById('strd-last'), minEl=document.getElementById('strd-min'), maxEl=document.getElementById('strd-max');
function pushStraddle(v){
  if(v==null) return;
  if(pts.length && Math.abs(pts[pts.length-1]-v)<1e-9) return;
  pts.push(v); if(pts.length>300) pts.shift();
  drawStraddle();
}
function drawStraddle(){
  if(pts.length<2){ if(pts.length===1) lastEl.textContent='₹'+pts[0].toFixed(1); return; }
  var min=Math.min.apply(null,pts), max=Math.max.apply(null,pts), span=(max-min)||1;
  var X=function(i){ return (i/(pts.length-1))*300; }, Y=function(p){ return 104-((p-min)/span)*94; };
  var d=pts.map(function(p,i){ return (i?'L':'M')+X(i).toFixed(1)+' '+Y(p).toFixed(1); }).join(' ');
  lineEl.setAttribute('d',d);
  areaEl.setAttribute('d',d+' L300 108 L0 108 Z');
  lastEl.textContent='₹'+pts[pts.length-1].toFixed(1);
  minEl.textContent='low ₹'+min.toFixed(1); maxEl.textContent='high ₹'+max.toFixed(1);
}

/* ---------- alerts ---------- */
var LS_KEY='fino_alerts_v1';
var alerts=[]; try{ alerts=JSON.parse(localStorage.getItem(LS_KEY)||'[]')||[]; }catch(e){}
var soundOn=true; try{ soundOn=localStorage.getItem('fino_alert_sound')!=='off'; }catch(e){}
var alForm=document.getElementById('al-form'), alMetric=document.getElementById('al-metric'),
    alStrike=document.getElementById('al-strike'), alCmp=document.getElementById('al-cmp'),
    alValue=document.getElementById('al-value'), alList=document.getElementById('al-list'),
    alLog=document.getElementById('al-log'), alCount=document.getElementById('al-count'),
    alNotif=document.getElementById('al-notif'), alSound=document.getElementById('al-sound');

var METRICS=[
  {id:'spot:NIFTY 50', label:'NIFTY spot', strike:false},
  {id:'spot:BANKNIFTY', label:'BANKNIFTY spot', strike:false},
  {id:'spot:SENSEX', label:'SENSEX spot', strike:false},
  {id:'spot:INDIA VIX', label:'INDIA VIX', strike:false},
  {id:'straddle', label:'ATM straddle', strike:false},
  {id:'bfly', label:'BFLY @ strike', strike:true},
  {id:'net', label:'NET @ strike', strike:true}
];
alMetric.innerHTML=METRICS.map(function(m){ return '<option value="'+m.id+'">'+m.label+'</option>'; }).join('');
alMetric.addEventListener('change',function(){
  var m=METRICS.filter(function(x){ return x.id===alMetric.value; })[0];
  alStrike.disabled=!m.strike;
});
function refreshStrikes(){
  var cur=alStrike.value;
  alStrike.innerHTML='<option value="">strike…</option>'+state.rows.map(function(r){
    return '<option value="'+r[0]+'"'+(String(r[0])===cur?' selected':'')+'>'+r[0]+'</option>';
  }).join('');
}
function metricValue(id, strike){
  if(id.indexOf('spot:')===0){
    var sym=id.slice(5);
    var q=(state.quotes||[]).filter(function(x){ return x.symbol===sym; })[0];
    return q?q.price:null;
  }
  if(id==='straddle') return state.straddle;
  var row=(state.rows||[]).filter(function(r){ return r[0]===Number(strike); })[0];
  if(!row) return null;
  return id==='bfly'?row[3]:id==='net'?row[4]:null;
}
function metricLabel(a){
  var m=METRICS.filter(function(x){ return x.id===a.metric; })[0];
  return (m?m.label.replace(' @ strike',''):a.metric)+(a.strike?' '+a.strike:'');
}
function saveAlerts(){ try{ localStorage.setItem(LS_KEY,JSON.stringify(alerts)); }catch(e){} }
function renderAlerts(){
  var armed=alerts.filter(function(a){ return a.state==='armed'; }).length;
  alCount.textContent=armed+' ARMED';
  if(!alerts.length){ alList.innerHTML='<li class="al-empty">No alerts. Arm one above — it fires the moment the live feed crosses your level.</li>'; return; }
  alList.innerHTML=alerts.map(function(a,i){
    var cur=metricValue(a.metric,a.strike);
    var tag=a.state==='fired'?'<span class="tag fired">FIRED</span>':'<span class="tag hot">ARMED</span>';
    var act=a.state==='fired'?'<button class="rearm" data-i="'+i+'" data-act="rearm">RE-ARM</button>':'';
    return '<li><div><b>'+metricLabel(a)+' '+(a.cmp==='>='?'≥':'≤')+' '+a.value+'</b>'
      +'<small>now '+(cur==null?'—':cur.toFixed(2))+'</small></div>'+tag
      +'<span>'+act+' <button data-i="'+i+'" data-act="del">✕</button></span></li>';
  }).join('');
}
alList.addEventListener('click',function(e){
  var b=e.target.closest('button'); if(!b) return;
  var i=Number(b.getAttribute('data-i'));
  if(b.getAttribute('data-act')==='del') alerts.splice(i,1);
  else if(b.getAttribute('data-act')==='rearm') alerts[i].state='armed';
  saveAlerts(); renderAlerts();
});
alForm.addEventListener('submit',function(e){
  e.preventDefault();
  var m=METRICS.filter(function(x){ return x.id===alMetric.value; })[0];
  if(m.strike && !alStrike.value){ alStrike.focus(); return; }
  var v=parseFloat(alValue.value); if(isNaN(v)) return;
  alerts.push({metric:alMetric.value,strike:m.strike?Number(alStrike.value):null,cmp:alCmp.value,value:v,state:'armed',created:Date.now()});
  alValue.value=''; saveAlerts(); renderAlerts();
});
function beep(){
  if(!soundOn) return;
  try{
    var ctx=beep.ctx||(beep.ctx=new (window.AudioContext||window.webkitAudioContext)());
    var o=ctx.createOscillator(), g=ctx.createGain();
    o.frequency.value=880; o.type='sine'; g.gain.value=0.06;
    o.connect(g); g.connect(ctx.destination); o.start();
    g.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+0.35);
    o.stop(ctx.currentTime+0.4);
  }catch(e){}
}
function logAlert(msg){
  var li=document.createElement('li');
  var t=new Date().toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour12:false});
  li.innerHTML='<time>'+t+'</time><span>'+msg+'</span>';
  alLog.prepend(li);
  while(alLog.children.length>40) alLog.lastElementChild.remove();
}
function evalAlerts(){
  var fired=false;
  alerts.forEach(function(a){
    if(a.state!=='armed') return;
    var cur=metricValue(a.metric,a.strike);
    if(cur==null) return;
    var hit=a.cmp==='>=' ? cur>=a.value : cur<=a.value;
    if(!hit) return;
    a.state='fired'; fired=true;
    var msg=metricLabel(a)+' crossed '+a.value+' (now '+cur.toFixed(2)+')';
    logAlert(msg); beep();
    if('Notification' in window && Notification.permission==='granted'){
      try{ new Notification('Finostat alert',{body:msg,icon:'/og.jpg'}); }catch(e){}
    }
  });
  if(fired){ saveAlerts(); renderAlerts(); }
}
alNotif.addEventListener('click',function(){
  if(!('Notification' in window)){ alNotif.textContent='NOT SUPPORTED'; return; }
  Notification.requestPermission().then(function(p){
    alNotif.textContent = p==='granted' ? 'DESKTOP ALERTS ON' : 'DESKTOP ALERTS BLOCKED';
    alNotif.classList.toggle('on', p==='granted');
  });
});
if('Notification' in window && Notification.permission==='granted'){
  alNotif.textContent='DESKTOP ALERTS ON'; alNotif.classList.add('on');
}
alSound.addEventListener('click',function(){
  soundOn=!soundOn;
  alSound.textContent='SOUND: '+(soundOn?'ON':'OFF');
  try{ localStorage.setItem('fino_alert_sound',soundOn?'on':'off'); }catch(e){}
});
alSound.textContent='SOUND: '+(soundOn?'ON':'OFF');

/* ---------- wire ---------- */
var wireList=document.getElementById('wire-list'), wireLive=document.getElementById('wire-live');
function hhmm(ts){ return new Date(ts*1000).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:false}); }
function esc(s){ return String(s).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function ingestNews(items){
  items.sort(function(a,b){ return a.ts-b.ts; }).forEach(function(n){
    if(wireList.querySelector('a[href="'+CSS.escape(n.url)+'"]')) return;
    var li=document.createElement('li');
    li.className=(n.hot?'hot ':'')+'new';
    li.innerHTML='<time>'+hhmm(n.ts)+'</time><div><a href="'+esc(n.url)+'" target="_blank" rel="noopener">'+esc(n.text)+'</a>'
      +'<div class="meta"><span class="tag '+esc(n.category.toLowerCase())+'">'+esc(n.category)+'</span><span>'+esc(n.handle)+'</span></div></div>';
    wireList.prepend(li);
  });
  while(wireList.children.length>80) wireList.lastElementChild.remove();
}

/* ---------- ingest a sheet payload ---------- */
function ingest(d){
  state.lastEvent=Date.now();
  if(d.quotes && d.quotes.length){ state.quotes=d.quotes; renderTape(d.quotes); }
  if(d.rows && d.rows.length){ applySheet(d.rows, d.atm!=null?d.atm:state.atm); refreshStrikes(); }
  if(d.mini && d.mini.length){ state.mini=d.mini; renderMini(d.mini); }
  if(d.straddle!=null){ state.straddle=d.straddle; pushStraddle(d.straddle); }
  if(typeof d.live==='boolean') state.live=d.live;
  evalAlerts(); renderAlerts();
  document.getElementById('sheet-note').textContent = state.live?'live':'delayed';
}

/* ---------- connection ---------- */
var conn=document.getElementById('conn');
function setConn(){
  var fresh = Date.now()-state.lastEvent < 6000;
  if(fresh && state.live){ conn.textContent='LIVE'; conn.classList.remove('off'); }
  else if(fresh){ conn.textContent='DELAYED'; conn.classList.remove('off'); }
  else { conn.textContent='RECONNECTING'; conn.classList.add('off'); }
}
setInterval(setConn,2000);

var pollTimer=null;
function startPolling(){ if(!pollTimer) pollTimer=setInterval(function(){
  fetch('/api/sheet').then(function(r){ return r.json(); }).then(function(d){
    ingest({rows:d.rows,atm:d.atm,straddle:d.straddle,live:d.live});
  }).catch(function(){});
  fetch('/api/quotes').then(function(r){ return r.json(); }).then(function(q){ ingest({quotes:q}); }).catch(function(){});
},2000); }
function stopPolling(){ if(pollTimer){ clearInterval(pollTimer); pollTimer=null; } }

if('EventSource' in window){
  var ss=new EventSource('/api/sheet/stream');
  ss.addEventListener('sheet',function(e){
    stopPolling();
    var d; try{ d=JSON.parse(e.data); }catch(err){ return; }
    ingest(d);
  });
  ss.onerror=function(){ startPolling(); };
  var ns=new EventSource('/api/news/stream');
  ns.addEventListener('news',function(e){
    wireLive.textContent='LIVE'; wireLive.classList.remove('off');
    try{ ingestNews(JSON.parse(e.data)); }catch(err){}
  });
  ns.onerror=function(){ wireLive.textContent='RSS'; wireLive.classList.add('off'); };
  setTimeout(function(){ if(!state.lastEvent) startPolling(); },3000);
}else{ startPolling(); }

/* ---------- clock ---------- */
var clk=document.getElementById('clock'), mkt=document.getElementById('mkt');
function tick(){
  clk.textContent=new Date().toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour12:false})+' IST';
  var n=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'}));
  var m=n.getHours()*60+n.getMinutes();
  var open=n.getDay()>0&&n.getDay()<6&&m>=555&&m<=930;
  mkt.textContent='NSE '+(open?'OPEN':'CLOSED'); mkt.classList.toggle('closed',!open);
}
tick(); setInterval(tick,1000);

/* ---------- seed ---------- */
var seed=window.SEED||{};
document.getElementById('sheet-sym').textContent=seed.symbol||'NIFTY';
document.getElementById('t-sym').textContent=(seed.symbol||'NIFTY')+' · NEAREST EXPIRY';
renderMini(seed.mini);
if(seed.rows&&seed.rows.length){ ingest(seed); } else { renderSheet([],null); }
renderAlerts();
})();
</script>
</body>
</html>
"""


def render_dashboard(snapshot: dict) -> bytes:
    return DASHBOARD.replace("__SEED__", _seed(snapshot)).encode("utf-8")
