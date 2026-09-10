"""Terminal panels for the analytics suite: IV surface (SURF), vol skew & moneyness (SKEW),
implied distribution (CURV), dealer gamma (GEX), historical replay (RPLY) and expiry-day
backtests (BKTS). Markup, CSS and a self-contained script that pages.py splices into the
dashboard. Charts are hand-drawn on canvas in the terminal's palette; nothing animates on
its own — replay only advances when the user presses play or drags the scrubber."""

PANELS = [("surf", "IV surface"), ("skew", "Vol skew"), ("curv", "Implied distribution"), ("gex", "Gamma exposure"), ("rply", "Replay"), ("bkts", "Backtest")]
ALIASES = {"SURF": "surf", "SURFACE": "surf", "IVS": "surf", "SKEW": "skew", "SMILE": "skew", "MONEY": "skew", "MONEYNESS": "skew",
           "CURV": "curv", "CURVE": "curv", "BELL": "curv", "DIST": "curv", "GEX": "gex", "GAMMA": "gex",
           "RPLY": "rply", "REPLAY": "rply", "BKTS": "bkts", "BACKTEST": "bkts", "BT": "bkts"}

_SEG_U = '<span class="seg an-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="FINNIFTY">FINNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span>'

MARKUP = f"""
  <section class="panel a-wide an" id="p-surf" aria-label="IV surface">
    <div class="panel-hd"><span class="k">SURF</span><span class="s">IV SURFACE · RICH/CHEAP</span><span class="r"><span class="an-state" id="surf-state">—</span></span></div>
    <div class="an-top">{_SEG_U}<span class="seg" id="surf-mode"><button type="button" data-m="iv" class="on">IV %</button><button type="button" data-m="rich">RICH / CHEAP</button></span><span class="an-note" id="surf-note">hover a cell</span></div>
    <div class="an-kpi" id="surf-kpi"></div>
    <div class="an-cvw"><canvas class="an-cv" id="surf-cv"></canvas></div>
    <div class="an-foot">Moneyness = ln(K/S). Rich/cheap = each strike's IV against its expiry's own fitted smile, in vol points: magenta is expensive, cyan is cheap. Exchange IVs and OI via Upstox; refreshes every minute.</div>
  </section>
  <section class="panel an" id="p-skew" aria-label="Vol skew and moneyness">
    <div class="panel-hd"><span class="k">SKEW</span><span class="s">VOL SKEW · MONEYNESS</span><span class="r"><span class="an-state" id="skew-state">—</span></span></div>
    <div class="an-top">{_SEG_U}<select class="an-sel an-exp" aria-label="Expiry"></select><span class="seg" id="skew-x"><button type="button" data-x="strike" class="on">STRIKE</button><button type="button" data-x="m">MONEYNESS</button><button type="button" data-x="delta">DELTA</button></span></div>
    <div class="an-kpi" id="skew-kpi"></div>
    <div class="an-cvw"><canvas class="an-cv" id="skew-cv"></canvas></div>
    <div class="an-foot" id="skew-note">CE IV cyan · PE IV magenta · fitted smile gold. 25Δ risk reversal = put IV − call IV; butterfly = wing average − ATM.</div>
  </section>
  <section class="panel an" id="p-curv" aria-label="Implied distribution">
    <div class="panel-hd"><span class="k">CURV</span><span class="s">IMPLIED DISTRIBUTION</span><span class="r"><span class="an-state" id="curv-state">—</span></span></div>
    <div class="an-top">{_SEG_U}<select class="an-sel an-exp" aria-label="Expiry"></select></div>
    <div class="an-kpi" id="curv-kpi"></div>
    <div class="an-cvw"><canvas class="an-cv" id="curv-cv"></canvas></div>
    <div class="an-foot">Risk-neutral density from the option chain (Breeden–Litzenberger on the fitted smile). Gold = what the market prices; dashed = a no-skew lognormal at ATM vol. Shaded band = 16th–84th percentile.</div>
  </section>
  <section class="panel an" id="p-gex" aria-label="Dealer gamma exposure">
    <div class="panel-hd"><span class="k">GEX</span><span class="s">DEALER GAMMA BY STRIKE</span><span class="r"><span class="an-state" id="gex-state">—</span></span></div>
    <div class="an-top">{_SEG_U}<select class="an-sel an-exp" aria-label="Expiry"></select></div>
    <div class="an-kpi" id="gex-kpi"></div>
    <div class="an-cvw"><canvas class="an-cv" id="gex-cv"></canvas></div>
    <div class="an-foot">₹ crore of dealer gamma per 1% move. Calls sold to dealers count positive (they hedge against the move), puts negative (they hedge with it). Gold line = cumulative; the flip is where it crosses zero.</div>
  </section>
  <section class="panel a-wide an" id="p-rply" aria-label="Historical replay">
    <div class="panel-hd"><span class="k">RPLY</span><span class="s">HISTORICAL REPLAY · EXPIRY DAYS</span><span class="r"><span class="an-state" id="rp-state">—</span></span></div>
    <div class="an-top">{_SEG_U}<select class="an-sel" id="rp-date" aria-label="Expiry day"></select><button type="button" class="an-btn" id="rp-load">LOAD DAY</button>
      <span class="an-play"><button type="button" class="an-btn" id="rp-play" disabled>▶ PLAY</button><select class="an-sel" id="rp-speed"><option value="4">1 min / 250 ms</option><option value="10">1 min / 100 ms</option><option value="1">1 min / 1 s</option></select></span>
      <span class="an-note" id="rp-note">pick an expiry day and load it — 1-minute candles, ATM ±5 strikes</span></div>
    <div class="an-scrub"><input type="range" id="rp-t" min="0" max="0" value="0" step="1" disabled aria-label="Time"><b id="rp-time">--:--</b></div>
    <div class="an-kpi" id="rp-kpi"></div>
    <div class="an-split"><div class="an-cvw"><canvas class="an-cv" id="rp-cv"></canvas></div>
      <div class="scroll an-tbl-wrap"><table class="an-table"><thead><tr><th>STRIKE</th><th>CE</th><th>PE</th><th>CE+PE</th></tr></thead><tbody id="rp-rows"></tbody></table></div></div>
  </section>
  <section class="panel a-wide an" id="p-bkts" aria-label="Backtesting">
    <div class="panel-hd"><span class="k">BKTS</span><span class="s">EXPIRY-DAY BACKTEST</span><span class="r"><span class="an-state" id="bt-state">—</span></span></div>
    <div class="an-top">{_SEG_U}<select class="an-sel" id="bt-strat" aria-label="Strategy"><option value="short_straddle">Short straddle</option><option value="short_strangle">Short strangle</option><option value="iron_fly">Iron fly</option><option value="iron_condor">Iron condor</option><option value="long_straddle">Long straddle</option><option value="long_strangle">Long strangle</option></select>
      <label class="an-lbl">IN <input class="an-in" id="bt-entry" value="10:00" maxlength="5" aria-label="Entry time"></label><label class="an-lbl">OUT <input class="an-in" id="bt-exit" value="15:15" maxlength="5" aria-label="Exit time"></label>
      <label class="an-lbl">WINGS <select class="an-sel" id="bt-wings"><option>1</option><option selected>2</option><option>3</option><option>4</option></select></label>
      <label class="an-lbl">EXPIRIES <select class="an-sel" id="bt-n"><option value="26">last 26</option><option value="52" selected>last 52</option><option value="104">last 104</option><option value="400">all</option></select></label>
      <button type="button" class="an-btn" id="bt-run">RUN</button><span class="an-note" id="bt-note">1-minute closes on each past expiry day since Oct 2024 · no slippage or costs</span></div>
    <div class="an-kpi" id="bt-kpi"></div>
    <div class="an-split"><div class="an-cvw"><canvas class="an-cv" id="bt-cv"></canvas></div>
      <div class="scroll an-tbl-wrap"><table class="an-table"><thead><tr><th>EXPIRY</th><th>ATM</th><th>MOVE</th><th>CREDIT</th><th>P&amp;L / LOT</th><th>MAE</th></tr></thead><tbody id="bt-rows"></tbody></table></div></div>
  </section>
"""

CSS = r"""
.a-wide{grid-column:span 2;min-height:380px}
.an .an-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:7px 10px;border-bottom:1px solid var(--line);font-size:10.5px}
.an .seg button{font-size:10px;letter-spacing:.08em;padding:4px 9px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.an .seg button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.an-sel,.an-in{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:11px;padding:3px 6px}.an-in{width:58px;text-transform:uppercase}
.an-lbl{display:inline-flex;align-items:center;gap:5px;color:var(--faint);letter-spacing:.08em;font-size:9.5px}
.an-btn{font-size:10px;letter-spacing:.1em;padding:5px 11px;border:1px solid var(--gold);color:var(--gold);background:none;cursor:pointer}.an-btn:hover{background:var(--gold);color:#2a1a02}.an-btn:disabled{opacity:.4;cursor:default}
.an-note{color:var(--faint);font-size:10.5px;margin-left:auto}.an-state{color:var(--faint)}.an-state.ok{color:var(--up)}.an-state.err{color:var(--down)}
.an-kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:1px;background:var(--line);border-bottom:1px solid var(--line)}
.an-kpi div{background:var(--panel);padding:5px 10px}.an-kpi small{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}.an-kpi b{font-family:var(--display);font-size:19px;font-weight:600;color:var(--gold)}.an-kpi b.c{color:var(--cyan)}.an-kpi b.up{color:var(--up)}.an-kpi b.down{color:var(--down)}.an-kpi b.m{color:var(--text)}
.an-cvw{position:relative;height:230px;flex:0 0 auto;min-width:0}.a-wide .an-cvw{height:270px}.an-split .an-cvw{height:300px}.an-cv{position:absolute;inset:0;width:100%;height:100%;display:block}
.an-foot{padding:6px 10px;border-top:1px solid var(--line);font-size:10px;color:var(--faint);line-height:1.45}
.an-split{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);flex:1;min-height:0}.an-tbl-wrap{border-left:1px solid var(--line);max-height:320px}
.an-table{width:100%;border-collapse:collapse;font-size:11px}.an-table th{position:sticky;top:0;background:var(--panel-hd);color:var(--faint);font-weight:500;font-size:9.5px;letter-spacing:.1em;padding:4px 8px;text-align:right}.an-table th:first-child{text-align:left}
.an-table td{padding:3px 8px;text-align:right;border-bottom:1px solid rgba(190,150,255,.08);font-variant-numeric:tabular-nums}.an-table td:first-child{text-align:left;color:var(--cyan)}.an-table tr.atm td{background:rgba(245,200,66,.1)}.an-table tr.atm td:first-child{color:var(--gold)}
.an-scrub{display:flex;align-items:center;gap:10px;padding:6px 10px;border-bottom:1px solid var(--line)}.an-scrub input{flex:1;accent-color:var(--gold)}.an-scrub b{font-family:var(--display);font-size:18px;color:var(--gold);min-width:56px;text-align:right}
.an-play{display:inline-flex;gap:6px;align-items:center}
@media(max-width:860px){.a-wide{grid-column:span 1}.an-split{grid-template-columns:1fr}.an-tbl-wrap{border-left:0;border-top:1px solid var(--line);max-height:220px}}
"""

JS = r"""
(function(){
  var U=['NIFTY 50','BANKNIFTY','FINNIFTY','SENSEX'];
  function $(id){ return document.getElementById(id); }
  function css(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#fff'; }
  var C={gold:css('--gold'),cyan:css('--cyan'),up:css('--up'),down:css('--down'),faint:css('--faint'),muted:css('--muted'),text:css('--text'),line:css('--line-strong'),mag:'#ff5fd2'};
  function nf(x,d){ if(x==null||isNaN(x)) return '—'; d=d==null?1:d; return Number(x).toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d}); }
  function inr(x){ if(x==null) return '—'; var a=Math.abs(x); var s=a>=1e7?(a/1e7).toFixed(2)+' cr':a>=1e5?(a/1e5).toFixed(2)+' L':nf(a,0); return (x<0?'−':'')+'₹'+s; }
  function ctx2d(cv){ var r=cv.getBoundingClientRect(), dpr=window.devicePixelRatio||1; var w=Math.max(200,Math.floor(r.width)), h=Math.max(120,Math.floor(r.height)); if(cv.width!==Math.floor(w*dpr)||cv.height!==Math.floor(h*dpr)){ cv.width=Math.floor(w*dpr); cv.height=Math.floor(h*dpr); } var c=cv.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,w,h); c.font='10px IBM Plex Mono, monospace'; return {c:c,w:w,h:h}; }
  function kpi(el,items){ el.innerHTML=items.map(function(k){ return '<div><small>'+k[0]+'</small><b'+(k[2]?' class="'+k[2]+'"':'')+'>'+k[1]+'</b></div>'; }).join(''); }
  function state(id,txt,cls){ var e=$(id); if(!e) return; e.textContent=txt; e.className='an-state'+(cls?' '+cls:''); }
  function getJSON(url,ok,fail){ fetch(url,{credentials:'same-origin'}).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){ if(x.s>=400){ fail(x.j&&x.j.error?x.j.error:(x.s===402?'Desk plan required':'HTTP '+x.s)); } else ok(x.j); }).catch(function(){ fail('network'); }); }
  function segInit(panel,cls,attr,cur,onChange){ var seg=panel.querySelector(cls); if(!seg) return; seg.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; Array.prototype.forEach.call(seg.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); onChange(b.getAttribute(attr)); }); }
  function fillExp(sel,exps,cur){ if(!sel) return; var have=Array.prototype.map.call(sel.options,function(o){ return o.value; }); if(have.join()===exps.join()){ sel.value=cur; return; } sel.innerHTML=exps.map(function(e){ var d=new Date(e+'T15:30:00+05:30'); return '<option value="'+e+'">'+d.toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+'</option>'; }).join(''); sel.value=cur; }
  function axes(c,w,h,pad){ c.strokeStyle='rgba(190,150,255,.14)'; c.lineWidth=1; c.beginPath(); c.moveTo(pad.l,pad.t); c.lineTo(pad.l,h-pad.b); c.lineTo(w-pad.r,h-pad.b); c.stroke(); }
  function visible(id){ var el=$(id); return el&&!el.hidden&&!document.hidden; }
  function heat(t){ /* 0..1 -> cyan..violet..magenta */ t=Math.max(0,Math.min(1,t)); var a=[70,225,255], b=[120,60,255], d=[255,95,210]; var x=t<.5?[a,b,t*2]:[b,d,(t-.5)*2]; var r=Math.round(x[0][0]+(x[1][0]-x[0][0])*x[2]), g=Math.round(x[0][1]+(x[1][1]-x[0][1])*x[2]), bl=Math.round(x[0][2]+(x[1][2]-x[0][2])*x[2]); return 'rgb('+r+','+g+','+bl+')'; }
  function diverge(t){ /* -1..1 -> cyan..dark..magenta */ t=Math.max(-1,Math.min(1,t)); var k=Math.abs(t); var base=[24,14,60]; var to=t<0?[70,225,255]:[255,95,210]; return 'rgb('+Math.round(base[0]+(to[0]-base[0])*k)+','+Math.round(base[1]+(to[1]-base[1])*k)+','+Math.round(base[2]+(to[2]-base[2])*k)+')'; }

  /* ---------------- SURF ---------------- */
  var surf={u:'NIFTY 50',mode:'iv',data:null,hover:null};
  var surfPanel=$('p-surf');
  if(surfPanel){
    segInit(surfPanel,'.an-u','data-u',surf.u,function(u){ surf.u=u; loadSurf(); });
    segInit(surfPanel,'#surf-mode','data-m',surf.mode,function(m){ surf.mode=m; drawSurf(); });
    var scv=$('surf-cv');
    scv.addEventListener('mousemove',function(e){ if(!surf.data||!surf.geo) return; var r=scv.getBoundingClientRect(); var x=e.clientX-r.left,y=e.clientY-r.top; var g=surf.geo; var ci=Math.floor((x-g.x0)/g.cw), ri=Math.floor((y-g.y0)/g.rh); if(ci<0||ri<0||ci>=g.nc||ri>=g.nr){ surf.hover=null; } else surf.hover=[ri,ci]; drawSurf(); });
    scv.addEventListener('mouseleave',function(){ surf.hover=null; drawSurf(); });
  }
  function loadSurf(){ if(!surfPanel) return; state('surf-state','loading…'); getJSON('/api/surface?u='+encodeURIComponent(surf.u),function(d){ surf.data=d; state('surf-state',(d.live?'LIVE':'LAST')+' · '+(d.source==='upstox-rest'?'EXCHANGE IV':'MODEL IV'),'ok'); var front=d.rows[0]||{}; kpi($('surf-kpi'),[['spot',nf(d.spot,1),'c']].concat(d.term.map(function(t){ return [t.label+' · '+Math.round(t.t_days)+'d',t.atm_iv!=null?nf(t.atm_iv,1)+'%':'—']; })).concat([['25Δ RR (front)',front.rr25!=null?(front.rr25>0?'+':'')+nf(front.rr25,2):'—',front.rr25>0?'down':'up'],['25Δ BF (front)',front.bf25!=null?nf(front.bf25,2):'—','m']])); drawSurf(); },function(err){ state('surf-state',err,'err'); }); }
  function drawSurf(){ var d=surf.data; if(!d||!scv) return; var g=ctx2d(scv), c=g.c; var padL=64, padT=22, padB=6, padR=8; var nc=d.cols.length, nr=d.rows.length; if(!nr){ c.fillStyle=C.faint; c.fillText('no expiries with a fitted smile yet',padL,padT+20); return; }
    var cw=(g.w-padL-padR)/nc, rh=(g.h-padT-padB)/nr; surf.geo={x0:padL,y0:padT,cw:cw,rh:rh,nc:nc,nr:nr};
    var lo=d.iv_range?d.iv_range[0]:0, hi=d.iv_range?d.iv_range[1]:1, rm=d.rich_max||1;
    c.textAlign='center'; c.fillStyle=C.faint; d.cols.forEach(function(m,i){ c.fillText((m>0?'+':'')+m+'%',padL+cw*(i+.5),14); });
    d.rows.forEach(function(row,ri){ row.cells.forEach(function(cell,ci){ var x=padL+cw*ci, y=padT+rh*ri; var v=surf.mode==='iv'?cell.iv:cell.rich; c.fillStyle= v==null?'rgba(255,255,255,.03)':(surf.mode==='iv'?heat(hi>lo?(v-lo)/(hi-lo):.5):diverge(rm?v/rm:0)); c.fillRect(x+1,y+1,cw-2,rh-2); if(surf.hover&&surf.hover[0]===ri&&surf.hover[1]===ci){ c.strokeStyle=C.gold; c.lineWidth=2; c.strokeRect(x+1.5,y+1.5,cw-3,rh-3); } if(v!=null&&cw>34){ c.fillStyle= surf.mode==='iv'?'rgba(0,0,0,.75)':'#fff'; c.font=(rh>26?'11px':'10px')+' IBM Plex Mono, monospace'; c.fillText(surf.mode==='iv'?v.toFixed(1):((v>0?'+':'')+v.toFixed(1)),x+cw/2,y+rh/2+4); } });
      c.textAlign='right'; c.fillStyle=C.text; c.font='10.5px IBM Plex Mono, monospace'; c.fillText(row.label,padL-8,padT+rh*ri+rh/2+1); c.fillStyle=C.faint; c.font='9px IBM Plex Mono, monospace'; c.fillText(Math.round(row.t_days)+'d',padL-8,padT+rh*ri+rh/2+12); c.textAlign='center'; });
    var note=$('surf-note'); if(surf.hover){ var row=d.rows[surf.hover[0]], cell=row.cells[surf.hover[1]], m=d.cols[surf.hover[1]]; note.textContent=row.label+' · '+(m>0?'+':'')+m+'% moneyness ≈ '+nf(d.spot*Math.exp(m/100),0)+' · IV '+(cell.iv!=null?cell.iv.toFixed(2)+'%':'—')+' · '+(cell.rich!=null?(cell.rich>0?'rich +':'cheap ')+cell.rich.toFixed(2)+' vol':'no fit'); } else note.textContent=surf.mode==='iv'?'IV range '+nf(lo,1)+'–'+nf(hi,1)+'% · hover a cell':'scale ±'+nf(rm,1)+' vol · hover a cell'; }

  /* ---------------- SKEW ---------------- */
  var skew={u:'NIFTY 50',exp:'',x:'strike',data:null};
  var skewPanel=$('p-skew');
  if(skewPanel){ segInit(skewPanel,'.an-u','data-u',skew.u,function(u){ skew.u=u; skew.exp=''; loadSkew(); }); segInit(skewPanel,'#skew-x','data-x',skew.x,function(x){ skew.x=x; drawSkew(); }); skewPanel.querySelector('.an-exp').addEventListener('change',function(e){ skew.exp=e.target.value; loadSkew(); }); }
  function loadSkew(){ if(!skewPanel) return; state('skew-state','loading…'); getJSON('/api/skew?u='+encodeURIComponent(skew.u)+(skew.exp?'&expiry='+skew.exp:''),function(d){ skew.data=d; skew.exp=d.expiry; fillExp(skewPanel.querySelector('.an-exp'),d.expiries,d.expiry); state('skew-state',(d.live?'LIVE':'LAST')+' · '+Math.round(d.t_days)+'d','ok');
      kpi($('skew-kpi'),[['spot',nf(d.spot,1),'c'],['ATM IV',d.atm_iv!=null?nf(d.atm_iv,2)+'%':'—'],['25Δ risk reversal',d.rr25!=null?(d.rr25>0?'+':'')+nf(d.rr25,2):'—',d.rr25>0?'down':'up'],['25Δ butterfly',d.bf25!=null?nf(d.bf25,2):'—','m'],['skew slope',d.skew_slope!=null?nf(d.skew_slope,3)+' /1%':'—','m']]); drawSkew(); },function(err){ state('skew-state',err,'err'); }); }
  function drawSkew(){ var d=skew.data, cv=$('skew-cv'); if(!d||!cv) return; var g=ctx2d(cv), c=g.c, pad={l:44,r:10,t:10,b:22}; var pts=d.points.filter(function(p){ return p.iv!=null; }); if(pts.length<3){ c.fillStyle=C.faint; c.fillText('not enough implied vols',pad.l,30); return; }
    function X(p){ return skew.x==='strike'?p.strike:skew.x==='m'?p.m:(p.ce_delta!=null?p.ce_delta:(p.pe_delta!=null?1+p.pe_delta:null)); }
    var xs=pts.map(X).filter(function(v){ return v!=null; }); var xmin=Math.min.apply(null,xs), xmax=Math.max.apply(null,xs); if(skew.x==='delta'){ xmin=0; xmax=1; }
    var ys=[]; pts.forEach(function(p){ [p.ce_iv,p.pe_iv,p.fit].forEach(function(v){ if(v!=null) ys.push(v); }); }); var ymin=Math.min.apply(null,ys), ymax=Math.max.apply(null,ys); var m=(ymax-ymin)*.12||1; ymin-=m; ymax+=m;
    var sx=function(v){ return pad.l+(v-xmin)/((xmax-xmin)||1)*(g.w-pad.l-pad.r); }, sy=function(v){ return g.h-pad.b-(v-ymin)/((ymax-ymin)||1)*(g.h-pad.t-pad.b); };
    axes(c,g.w,g.h,pad); c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){ var v=ymin+(ymax-ymin)*i/4; c.fillText(v.toFixed(1),pad.l-4,sy(v)+3); c.strokeStyle='rgba(190,150,255,.08)'; c.beginPath(); c.moveTo(pad.l,sy(v)); c.lineTo(g.w-pad.r,sy(v)); c.stroke(); }
    c.textAlign='center'; for(var j=0;j<=6;j++){ var xv=xmin+(xmax-xmin)*j/6; c.fillText(skew.x==='strike'?nf(xv,0):skew.x==='m'?(xv>0?'+':'')+xv.toFixed(1)+'%':xv.toFixed(2)+'Δ',sx(xv),g.h-8); }
    var atmX=skew.x==='strike'?d.spot:skew.x==='m'?0:0.5; c.strokeStyle='rgba(70,225,255,.5)'; c.setLineDash([3,3]); c.beginPath(); c.moveTo(sx(atmX),pad.t); c.lineTo(sx(atmX),g.h-pad.b); c.stroke(); c.setLineDash([]);
    function line(key,color,dash){ var ok=false; c.strokeStyle=color; c.lineWidth=key==='fit'?1.4:1.8; if(dash) c.setLineDash([5,4]); c.beginPath(); pts.forEach(function(p){ var xv=X(p), yv=p[key]; if(xv==null||yv==null) return; if(!ok){ c.moveTo(sx(xv),sy(yv)); ok=true; } else c.lineTo(sx(xv),sy(yv)); }); c.stroke(); c.setLineDash([]); if(key!=='fit'){ c.fillStyle=color; pts.forEach(function(p){ var xv=X(p), yv=p[key]; if(xv==null||yv==null) return; c.beginPath(); c.arc(sx(xv),sy(yv),2.2,0,Math.PI*2); c.fill(); }); } }
    line('fit',C.gold,true); line('ce_iv',C.cyan,false); line('pe_iv',C.mag,false);
    c.font='9.5px IBM Plex Mono, monospace'; c.textAlign='left'; c.fillStyle=C.cyan; c.fillText('CE IV',pad.l+6,pad.t+10); c.fillStyle=C.mag; c.fillText('PE IV',pad.l+46,pad.t+10); c.fillStyle=C.gold; c.fillText('FIT',pad.l+86,pad.t+10); }

  /* ---------------- CURV ---------------- */
  var curv={u:'NIFTY 50',exp:'',data:null};
  var curvPanel=$('p-curv');
  if(curvPanel){ segInit(curvPanel,'.an-u','data-u',curv.u,function(u){ curv.u=u; curv.exp=''; loadCurv(); }); curvPanel.querySelector('.an-exp').addEventListener('change',function(e){ curv.exp=e.target.value; loadCurv(); }); }
  function loadCurv(){ if(!curvPanel) return; state('curv-state','loading…'); getJSON('/api/curve?u='+encodeURIComponent(curv.u)+(curv.exp?'&expiry='+curv.exp:''),function(d){ curv.data=d; curv.exp=d.expiry; fillExp(curvPanel.querySelector('.an-exp'),d.expiries,d.expiry); state('curv-state',(d.live?'LIVE':'LAST')+' · '+nf(d.t_days,1)+'d','ok');
      kpi($('curv-kpi'),[['spot',nf(d.spot,1),'c'],['expected move (1σ)','±'+nf(d.expected_move,0)+' · '+nf(d.expected_move_pct,2)+'%'],['16–84% range',nf(d.p16,0)+' – '+nf(d.p84,0),'m'],['5–95% range',nf(d.p05,0)+' – '+nf(d.p95,0),'m'],['P(close above spot)',nf(d.p_up*100,1)+'%',d.p_up>=.5?'up':'down'],['mode / mean',nf(d.mode,0)+' / '+nf(d.mean,0),'m'],['tails beyond 1σ',nf(d.tail_left*100,1)+'% ↓ · '+nf(d.tail_right*100,1)+'% ↑','m']]); drawCurv(); },function(err){ state('curv-state',err,'err'); }); }
  function drawCurv(){ var d=curv.data, cv=$('curv-cv'); if(!d||!cv||!d.x) return; var g=ctx2d(cv), c=g.c, pad={l:10,r:10,t:12,b:22}; var xmin=d.x[0], xmax=d.x[d.x.length-1]; var ymax=Math.max(Math.max.apply(null,d.pdf),Math.max.apply(null,d.lognormal))*1.08||1;
    var sx=function(v){ return pad.l+(v-xmin)/(xmax-xmin)*(g.w-pad.l-pad.r); }, sy=function(v){ return g.h-pad.b-v/ymax*(g.h-pad.t-pad.b); };
    c.fillStyle='rgba(245,200,66,.10)'; c.beginPath(); c.moveTo(sx(d.p16),g.h-pad.b); d.x.forEach(function(x,i){ if(x>=d.p16&&x<=d.p84) c.lineTo(sx(x),sy(d.pdf[i])); }); c.lineTo(sx(d.p84),g.h-pad.b); c.closePath(); c.fill();
    c.strokeStyle='rgba(200,180,255,.45)'; c.setLineDash([4,4]); c.lineWidth=1.2; c.beginPath(); d.x.forEach(function(x,i){ i?c.lineTo(sx(x),sy(d.lognormal[i])):c.moveTo(sx(x),sy(d.lognormal[i])); }); c.stroke(); c.setLineDash([]);
    var grad=c.createLinearGradient(0,pad.t,0,g.h-pad.b); grad.addColorStop(0,'rgba(245,200,66,.35)'); grad.addColorStop(1,'rgba(245,200,66,.02)'); c.fillStyle=grad; c.beginPath(); c.moveTo(sx(xmin),g.h-pad.b); d.x.forEach(function(x,i){ c.lineTo(sx(x),sy(d.pdf[i])); }); c.lineTo(sx(xmax),g.h-pad.b); c.closePath(); c.fill();
    c.strokeStyle=C.gold; c.lineWidth=2; c.beginPath(); d.x.forEach(function(x,i){ i?c.lineTo(sx(x),sy(d.pdf[i])):c.moveTo(sx(x),sy(d.pdf[i])); }); c.stroke();
    function vline(x,color,label,dash){ c.strokeStyle=color; c.lineWidth=1; if(dash) c.setLineDash([3,3]); c.beginPath(); c.moveTo(sx(x),pad.t); c.lineTo(sx(x),g.h-pad.b); c.stroke(); c.setLineDash([]); c.fillStyle=color; c.textAlign='center'; c.fillText(label,sx(x),pad.t-2); }
    vline(d.spot,C.cyan,'spot '+nf(d.spot,0),false); vline(d.p16,C.faint,nf(d.p16,0),true); vline(d.p84,C.faint,nf(d.p84,0),true);
    c.fillStyle=C.faint; c.textAlign='center'; for(var i=0;i<=6;i++){ var v=xmin+(xmax-xmin)*i/6; c.fillText(nf(v,0),sx(v),g.h-8); } c.textAlign='left'; c.fillStyle=C.gold; c.fillText('implied',pad.l+6,pad.t+10); c.fillStyle='rgba(200,180,255,.7)'; c.fillText('lognormal (no skew)',pad.l+58,pad.t+10); }

  /* ---------------- GEX ---------------- */
  var gex={u:'NIFTY 50',exp:'',data:null};
  var gexPanel=$('p-gex');
  if(gexPanel){ segInit(gexPanel,'.an-u','data-u',gex.u,function(u){ gex.u=u; gex.exp=''; loadGex(); }); gexPanel.querySelector('.an-exp').addEventListener('change',function(e){ gex.exp=e.target.value; loadGex(); }); }
  function loadGex(){ if(!gexPanel) return; state('gex-state','loading…'); getJSON('/api/gex?u='+encodeURIComponent(gex.u)+(gex.exp?'&expiry='+gex.exp:''),function(d){ gex.data=d; gex.exp=d.expiry; fillExp(gexPanel.querySelector('.an-exp'),d.expiries,d.expiry); state('gex-state',(d.live?'LIVE':'LAST')+' · LOT '+d.lot,'ok');
      kpi($('gex-kpi'),[['spot',nf(d.spot,1),'c'],['net GEX / 1%','₹'+nf(d.total,1)+' cr',d.total>=0?'up':'down'],['regime',d.total>=0?'PINNING':'CHASING',d.total>=0?'up':'down'],['gamma flip',d.flip!=null?nf(d.flip,0):'—','m'],['largest +',nf(d.max_pos.strike,0)+' · ₹'+nf(d.max_pos.net,1)+' cr','up'],['largest −',nf(d.max_neg.strike,0)+' · ₹'+nf(d.max_neg.net,1)+' cr','down']]); $('gex-state').title=d.regime; drawGex(); },function(err){ state('gex-state',err,'err'); }); }
  function drawGex(){ var d=gex.data, cv=$('gex-cv'); if(!d||!cv||!d.strikes) return; var g=ctx2d(cv), c=g.c, pad={l:46,r:46,t:12,b:22}; var rows=d.strikes; var n=rows.length; var vmax=Math.max.apply(null,rows.map(function(r){ return Math.max(Math.abs(r.call),Math.abs(r.put)); }))||1; var cmax=Math.max.apply(null,rows.map(function(r){ return Math.abs(r.cum); }))||1;
    var bw=(g.w-pad.l-pad.r)/n; var mid=pad.t+(g.h-pad.t-pad.b)/2; var half=(g.h-pad.t-pad.b)/2;
    var sx=function(i){ return pad.l+bw*(i+.5); }, syv=function(v){ return mid-v/vmax*half*.92; }, syc=function(v){ return mid-v/cmax*half*.92; };
    c.strokeStyle='rgba(190,150,255,.14)'; c.beginPath(); c.moveTo(pad.l,mid); c.lineTo(g.w-pad.r,mid); c.stroke();
    rows.forEach(function(r,i){ var x=sx(i)-bw*.36; c.fillStyle='rgba(72,232,150,.85)'; var yc=syv(r.call); c.fillRect(x,Math.min(yc,mid),bw*.72,Math.abs(mid-yc)); c.fillStyle='rgba(255,92,120,.85)'; var yp=syv(r.put); c.fillRect(x,Math.min(yp,mid),bw*.72,Math.abs(mid-yp)); });
    c.strokeStyle=C.gold; c.lineWidth=1.8; c.beginPath(); rows.forEach(function(r,i){ i?c.lineTo(sx(i),syc(r.cum)):c.moveTo(sx(i),syc(r.cum)); }); c.stroke();
    var ks=rows.map(function(r){ return r.strike; }); var k0=ks[0], k1=ks[n-1]; function sk(k){ return pad.l+(k-k0)/((k1-k0)||1)*(g.w-pad.l-pad.r-bw)+bw/2; }
    c.strokeStyle=C.cyan; c.setLineDash([3,3]); c.beginPath(); c.moveTo(sk(d.spot),pad.t); c.lineTo(sk(d.spot),g.h-pad.b); c.stroke(); if(d.flip!=null){ c.strokeStyle=C.gold; c.beginPath(); c.moveTo(sk(d.flip),pad.t); c.lineTo(sk(d.flip),g.h-pad.b); c.stroke(); } c.setLineDash([]);
    c.fillStyle=C.faint; c.textAlign='center'; var every=Math.max(1,Math.round(n/8)); rows.forEach(function(r,i){ if(i%every===0) c.fillText(nf(r.strike,0),sx(i),g.h-8); }); c.textAlign='right'; c.fillText('+'+nf(vmax,1),pad.l-4,pad.t+10); c.fillText('−'+nf(vmax,1),pad.l-4,g.h-pad.b-2); c.textAlign='left'; c.fillStyle=C.gold; c.fillText('cum ±'+nf(cmax,1),g.w-pad.r+4,pad.t+10); c.fillStyle=C.cyan; c.fillText('spot',sk(d.spot)+3,pad.t+10); if(d.flip!=null){ c.fillStyle=C.gold; c.fillText('flip',sk(d.flip)+3,pad.t+22); } }

  /* ---------------- RPLY ---------------- */
  var rp={u:'NIFTY 50',day:'',data:null,i:0,timer:null,poll:null};
  var rpPanel=$('p-rply');
  if(rpPanel){ segInit(rpPanel,'.an-u','data-u',rp.u,function(u){ rp.u=u; loadDays(); }); $('rp-load').addEventListener('click',function(){ rp.day=$('rp-date').value; if(rp.day) loadDay(); }); $('rp-t').addEventListener('input',function(e){ rp.i=Number(e.target.value); drawRp(); }); $('rp-play').addEventListener('click',function(){ if(rp.timer){ stopRp(); return; } var ms=Math.round(1000/Number($('rp-speed').value||4)); $('rp-play').textContent='❚❚ PAUSE'; rp.timer=setInterval(function(){ if(!rp.data) return stopRp(); if(rp.i>=rp.data.frames.length-1) return stopRp(); rp.i++; $('rp-t').value=rp.i; drawRp(); },ms); }); }
  function stopRp(){ if(rp.timer){ clearInterval(rp.timer); rp.timer=null; } var b=$('rp-play'); if(b) b.textContent='▶ PLAY'; }
  function loadDays(){ if(!rpPanel) return; state('rp-state','loading days…'); getJSON('/api/replay/days?u='+encodeURIComponent(rp.u),function(d){ var sel=$('rp-date'); sel.innerHTML=d.days.slice(0,120).map(function(x){ return '<option value="'+x+'">'+new Date(x+'T15:30:00+05:30').toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'2-digit'})+'</option>'; }).join(''); state('rp-state',d.days.length+' EXPIRY DAYS','ok'); $('rp-note').textContent='archive: '+d.days[d.days.length-1]+' → '+d.days[0]+' · pick a day and load it'; },function(err){ state('rp-state',err,'err'); }); }
  function loadDay(){ stopRp(); state('rp-state','fetching candles…'); $('rp-load').disabled=true; if(rp.poll) clearTimeout(rp.poll);
    (function tick(){ getJSON('/api/replay/day?u='+encodeURIComponent(rp.u)+'&date='+rp.day,function(j){ if(j.status==='running'){ state('rp-state','fetching '+Math.round(j.progress*100)+'%'); $('rp-note').textContent='first load of a day pulls one candle file per strike; later loads are instant'; rp.poll=setTimeout(tick,1200); return; } if(j.status==='error'){ state('rp-state',j.error||'failed','err'); $('rp-load').disabled=false; return; } rp.data=j.result; rp.i=0; $('rp-load').disabled=false; $('rp-play').disabled=false; var t=$('rp-t'); t.disabled=false; t.max=rp.data.frames.length-1; t.value=0; state('rp-state',rp.u+' · '+rp.day+' · LOT '+rp.data.lot,'ok'); $('rp-note').textContent='drag the scrubber or press play · open '+nf(rp.data.open,1)+' · high '+nf(rp.data.high,1)+' · low '+nf(rp.data.low,1)+' · close '+nf(rp.data.close,1); drawRp(); },function(err){ state('rp-state',err,'err'); $('rp-load').disabled=false; }); })(); }
  function drawRp(){ var d=rp.data, cv=$('rp-cv'); if(!d||!cv) return; var f=d.frames[rp.i]; $('rp-time').textContent=f.t;
    kpi($('rp-kpi'),[['spot @ '+f.t,nf(f.spot,1),'c'],['ATM',nf(f.atm,0),'m'],['ATM straddle',f.straddle!=null?'₹'+nf(f.straddle,1):'—'],['from open',(f.spot-d.open>=0?'+':'')+nf(f.spot-d.open,1)+' · '+nf((f.spot-d.open)/d.open*100,2)+'%',f.spot>=d.open?'up':'down'],['day range',nf(d.low,0)+' – '+nf(d.high,0),'m']]);
    var g=ctx2d(cv), c=g.c, pad={l:50,r:50,t:12,b:22}; var n=d.frames.length; var sp=d.frames.map(function(x){ return x.spot; }); var st=d.frames.map(function(x){ return x.straddle; }).filter(function(v){ return v!=null; }); var smin=Math.min.apply(null,sp), smax=Math.max.apply(null,sp); var tmin=st.length?Math.min.apply(null,st):0, tmax=st.length?Math.max.apply(null,st):1; var m=(smax-smin)*.08||1; smin-=m; smax+=m;
    var sx=function(i){ return pad.l+i/(n-1)*(g.w-pad.l-pad.r); }, sy=function(v){ return g.h-pad.b-(v-smin)/((smax-smin)||1)*(g.h-pad.t-pad.b); }, sy2=function(v){ return g.h-pad.b-(v-tmin)/((tmax-tmin)||1)*(g.h-pad.t-pad.b); };
    axes(c,g.w,g.h,pad); c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){ var v=smin+(smax-smin)*i/4; c.fillText(nf(v,0),pad.l-4,sy(v)+3); } c.textAlign='left'; for(var j=0;j<=4;j++){ var w=tmin+(tmax-tmin)*j/4; c.fillText('₹'+nf(w,0),g.w-pad.r+4,sy2(w)+3); } c.textAlign='center'; [0,Math.floor(n/4),Math.floor(n/2),Math.floor(3*n/4),n-1].forEach(function(i){ c.fillText(d.frames[i].t,sx(i),g.h-8); });
    c.strokeStyle='rgba(70,225,255,.22)'; c.lineWidth=1; c.beginPath(); sp.forEach(function(v,i){ i?c.lineTo(sx(i),sy(v)):c.moveTo(sx(i),sy(v)); }); c.stroke();
    c.strokeStyle='rgba(245,200,66,.22)'; c.beginPath(); var started=false; d.frames.forEach(function(x,i){ if(x.straddle==null) return; started?c.lineTo(sx(i),sy2(x.straddle)):c.moveTo(sx(i),sy2(x.straddle)); started=true; }); c.stroke();
    c.strokeStyle=C.cyan; c.lineWidth=2; c.beginPath(); for(var k=0;k<=rp.i;k++){ k?c.lineTo(sx(k),sy(sp[k])):c.moveTo(sx(k),sy(sp[k])); } c.stroke();
    c.strokeStyle=C.gold; c.lineWidth=1.8; c.beginPath(); started=false; for(var q=0;q<=rp.i;q++){ var x=d.frames[q]; if(x.straddle==null) continue; started?c.lineTo(sx(q),sy2(x.straddle)):c.moveTo(sx(q),sy2(x.straddle)); started=true; } c.stroke();
    c.strokeStyle='rgba(255,255,255,.35)'; c.setLineDash([3,3]); c.beginPath(); c.moveTo(sx(rp.i),pad.t); c.lineTo(sx(rp.i),g.h-pad.b); c.stroke(); c.setLineDash([]); c.fillStyle=C.cyan; c.textAlign='left'; c.fillText('spot',pad.l+6,pad.t+10); c.fillStyle=C.gold; c.fillText('ATM straddle',pad.l+40,pad.t+10);
    $('rp-rows').innerHTML=f.rows.map(function(r){ var sum=(r[1]!=null&&r[2]!=null)?r[1]+r[2]:null; return '<tr'+(r[0]===f.atm?' class="atm"':'')+'><td>'+nf(r[0],0)+'</td><td>'+(r[1]!=null?nf(r[1],2):'—')+'</td><td>'+(r[2]!=null?nf(r[2],2):'—')+'</td><td>'+(sum!=null?nf(sum,2):'—')+'</td></tr>'; }).join(''); }

  /* ---------------- BKTS ---------------- */
  var bt={u:'NIFTY 50',poll:null,data:null};
  var btPanel=$('p-bkts');
  if(btPanel){ segInit(btPanel,'.an-u','data-u',bt.u,function(u){ bt.u=u; }); $('bt-run').addEventListener('click',runBt); }
  function runBt(){ if(bt.poll) clearTimeout(bt.poll); var q='/api/backtest?u='+encodeURIComponent(bt.u)+'&strategy='+$('bt-strat').value+'&entry='+encodeURIComponent($('bt-entry').value.trim())+'&exit='+encodeURIComponent($('bt-exit').value.trim())+'&n='+$('bt-n').value+'&wings='+$('bt-wings').value; $('bt-run').disabled=true; state('bt-state','running…');
    (function tick(){ getJSON(q,function(j){ if(j.status==='running'){ state('bt-state','fetching '+Math.round(j.progress*100)+'%'); $('bt-note').textContent='first run pulls one candle file per leg per expiry; results are kept, so re-runs are instant'; bt.poll=setTimeout(tick,1500); return; } $('bt-run').disabled=false; if(j.status==='error'){ state('bt-state',j.error||'failed','err'); return; } bt.data=j.result; var s=bt.data.stats; state('bt-state',s.n+' EXPIRIES · '+s.first+' → '+s.last,'ok'); $('bt-note').textContent=bt.data.label+' · in '+bt.data.entry+' out '+bt.data.exit+' · lot '+s.lot+' · 1-minute closes, no slippage or costs';
      kpi($('bt-kpi'),[['win rate',nf(s.win_rate,1)+'%',s.win_rate>=50?'up':'down'],['avg P&L / lot',inr(s.avg),s.avg>=0?'up':'down'],['total / lot',inr(s.total),s.total>=0?'up':'down'],['median',inr(s.median),'m'],['best / worst',inr(s.best)+' / '+inr(s.worst),'m'],['profit factor',s.profit_factor!=null?nf(s.profit_factor,2):'∞','m'],['max drawdown',inr(s.max_drawdown),'down'],['avg MAE (pts)',nf(s.avg_mae_pts,1),'m']]); drawBt(); },function(err){ state('bt-state',err,'err'); $('bt-run').disabled=false; }); })(); }
  function drawBt(){ var d=bt.data, cv=$('bt-cv'); if(!d||!cv) return; var g=ctx2d(cv), c=g.c, pad={l:64,r:10,t:12,b:22}; var eq=d.equity, n=eq.length; var lo=Math.min(0,Math.min.apply(null,eq)), hi=Math.max(0,Math.max.apply(null,eq)); var m=(hi-lo)*.08||1; lo-=m; hi+=m;
    var sx=function(i){ return pad.l+(n>1?i/(n-1):0)*(g.w-pad.l-pad.r); }, sy=function(v){ return g.h-pad.b-(v-lo)/((hi-lo)||1)*(g.h-pad.t-pad.b); };
    axes(c,g.w,g.h,pad); c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){ var v=lo+(hi-lo)*i/4; c.fillText(inr(v),pad.l-4,sy(v)+3); } c.strokeStyle='rgba(255,255,255,.18)'; c.beginPath(); c.moveTo(pad.l,sy(0)); c.lineTo(g.w-pad.r,sy(0)); c.stroke();
    var last=eq[n-1]; var grad=c.createLinearGradient(0,pad.t,0,g.h-pad.b); grad.addColorStop(0,last>=0?'rgba(72,232,150,.30)':'rgba(255,92,120,.30)'); grad.addColorStop(1,'rgba(0,0,0,0)'); c.fillStyle=grad; c.beginPath(); c.moveTo(sx(0),sy(0)); eq.forEach(function(v,i){ c.lineTo(sx(i),sy(v)); }); c.lineTo(sx(n-1),sy(0)); c.closePath(); c.fill();
    c.strokeStyle=last>=0?C.up:C.down; c.lineWidth=2; c.beginPath(); eq.forEach(function(v,i){ i?c.lineTo(sx(i),sy(v)):c.moveTo(sx(i),sy(v)); }); c.stroke();
    c.textAlign='center'; c.fillStyle=C.faint; [0,Math.floor(n/2),n-1].forEach(function(i){ if(d.rows[i]) c.fillText(d.rows[i].day,sx(i),g.h-8); }); c.textAlign='left'; c.fillStyle=C.text; c.fillText('cumulative P&L per lot · '+d.label,pad.l+6,pad.t+10);
    $('bt-rows').innerHTML=d.rows.slice().reverse().map(function(r){ return '<tr><td>'+r.day+'</td><td>'+nf(r.atm,0)+'</td><td class="'+(r.move_pct>=0?'up':'down')+'">'+(r.move_pct>=0?'+':'')+nf(r.move_pct,2)+'%</td><td>'+nf(r.credit,1)+'</td><td class="'+(r.pnl>=0?'up':'down')+'">'+inr(r.pnl)+'</td><td>'+nf(r.mae,1)+'</td></tr>'; }).join(''); }

  /* ---------------- lifecycle ---------------- */
  function refreshLive(){ if(visible('p-surf')) loadSurf(); if(visible('p-skew')) loadSkew(); if(visible('p-curv')) loadCurv(); if(visible('p-gex')) loadGex(); }
  refreshLive(); if(rpPanel) loadDays();
  setInterval(refreshLive,60000);
  window.addEventListener('resize',function(){ drawSurf(); drawSkew(); drawCurv(); drawGex(); drawRp(); drawBt(); });
  document.addEventListener('visibilitychange',function(){ if(!document.hidden) refreshLive(); });
  window.finoAnalyticsRefresh=refreshLive;
})();
"""
