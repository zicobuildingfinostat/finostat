"""The Global / Crypto terminal at /global: world index tape, TradingView charting, Deribit BTC/ETH
option chains with Greeks to third order, an option buying / selling strategy builder, the
analytics suite (SURF, SKEW, CURV, GEX) on crypto chains, DVOL and funding, and a CoinDCX
connection. Reuses the Indian terminal's stylesheet and paywall; nothing animates on its own."""
from __future__ import annotations

import pages
import panels_pro

_SEG = '<span class="seg an-u"><button type="button" data-u="BTC" class="on">BTC</button><button type="button" data-u="ETH">ETH</button></span>'
_INDEX_SEG = '<span class="seg an-u"><button type="button" data-u="NIFTY 50" class="on">NIFTY</button><button type="button" data-u="BANKNIFTY">BANKNIFTY</button><button type="button" data-u="FINNIFTY">FINNIFTY</button><button type="button" data-u="SENSEX">SENSEX</button></span>'


def _analytics_markup() -> str:
    """SURF/SKEW/CURV/GEX sections from the pro suite, re-pointed at BTC/ETH."""
    parts = panels_pro.MARKUP.split("  <section ")
    keep = [p for p in parts if p.startswith('class="panel a-wide an" id="p-surf"') or p.startswith('class="panel an" id="p-skew"')
            or p.startswith('class="panel an" id="p-curv"') or p.startswith('class="panel an" id="p-gex"')]
    m = "".join("  <section " + p for p in keep)
    m = m.replace(_INDEX_SEG, _SEG)
    m = m.replace("Exchange IVs and OI via Upstox; refreshes every minute.", "Mark IVs and OI from Deribit; refreshes every minute.")
    m = m.replace("₹ crore of dealer gamma per 1% move.", "$ million of dealer gamma per 1% move (OI in coins × index price).")
    return m


def _analytics_js() -> str:
    js = panels_pro.JS
    for a, b in (("'/api/surface?u='", "'/api/global/surface?u='"), ("'/api/skew?u='", "'/api/global/skew?u='"),
                 ("'/api/curve?u='", "'/api/global/curve?u='"), ("'/api/gex?u='", "'/api/global/gex?u='"),
                 ("u:'NIFTY 50'", "u:'BTC'"), ('u:"NIFTY 50"', 'u:"BTC"'), ("d.source==='upstox-rest'", "(d.source==='upstox-rest'||d.source==='deribit')"),
                 ("'₹'+nf(d.total,1)+' cr'", "'$'+nf(d.total,1)+' M'"), ("' · ₹'+nf(d.max_pos.net,1)+' cr'", "' · $'+nf(d.max_pos.net,1)+' M'"),
                 ("' · ₹'+nf(d.max_neg.net,1)+' cr'", "' · $'+nf(d.max_neg.net,1)+' M'")):
        js = js.replace(a, b)
    return js


CSS = r"""
.g-tape em.dim{color:var(--faint)}.g-tape .sec{color:var(--gold);font-weight:600;letter-spacing:.12em;font-size:10px}
.tv-wrap{position:relative;flex:1;min-height:420px}.tv-wrap>div{position:absolute;inset:0}
.tv-top{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding:7px 10px;border-bottom:1px solid var(--line);font-size:10.5px}
.tv-top button{font-size:10px;letter-spacing:.08em;padding:4px 9px;border:1px solid var(--line-strong);color:var(--muted);cursor:pointer}.tv-top button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.g-kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1px;background:var(--line)}
.g-kpi div{background:var(--panel);padding:7px 10px}.g-kpi small{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase}.g-kpi b{font-family:var(--display);font-size:21px;font-weight:600;color:var(--gold)}.g-kpi b.c{color:var(--cyan)}.g-kpi b.up{color:var(--up)}.g-kpi b.down{color:var(--down)}.g-kpi b.m{color:var(--text)}.g-kpi i{font-style:normal;color:var(--muted);font-size:10.5px;margin-left:4px}
.oc-top{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:7px 10px;border-bottom:1px solid var(--line);font-size:10.5px}
.oc-top .seg button,.bl-side button{font-size:10px;letter-spacing:.08em;padding:4px 9px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.oc-top .seg button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.bl-side button.on.buy{background:var(--up);color:#032;border-color:var(--up);font-weight:600}.bl-side button.on.sell{background:var(--down);color:#300;border-color:var(--down);font-weight:600}
.oc-tbl td.k{color:var(--gold);font-weight:600;text-align:center;background:rgba(245,200,66,.05)}.oc-tbl tr.atm td{background:rgba(127,224,240,.07)}.oc-tbl td.itm{background:rgba(106,53,240,.12)}
.oc-tbl td.px{color:var(--text);cursor:pointer}.oc-tbl td.px:hover{background:rgba(245,200,66,.18);color:var(--gold)}.oc-tbl .oib{display:inline-block;height:6px;background:var(--cyan);opacity:.55;vertical-align:middle;margin-right:4px}.oc-tbl .oib.pe{background:var(--pink)}
.oc-tbl th.ce,.oc-tbl th.pe{color:var(--muted)}
.bl-wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);flex:1;min-height:0}.bl-left{border-right:1px solid var(--line);display:flex;flex-direction:column;min-width:0}
.bl-presets{padding:8px 10px;border-bottom:1px solid var(--line);display:grid;grid-template-columns:1fr 1fr;gap:8px}.bl-presets h5{font-size:9.5px;letter-spacing:.12em;color:var(--faint);margin:0 0 5px;text-transform:uppercase}.bl-presets h5.buy{color:var(--up)}.bl-presets h5.sell{color:var(--down)}
.bl-presets button{display:block;width:100%;text-align:left;font-size:10.5px;padding:4px 7px;margin:2px 0;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.bl-presets button:hover{border-color:var(--gold);color:var(--gold)}
.bl-legs td,.bl-legs th{padding:4px 8px}.bl-legs input,.bl-legs select{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:11px;padding:2px 4px;width:78px}.bl-legs select{width:auto}.bl-legs .x{color:var(--down);cursor:pointer;background:none;border:0}
.bl-legs td.buy{color:var(--up)}.bl-legs td.sell{color:var(--down)}
.bl-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:7px 10px;border-top:1px solid var(--line);font-size:10.5px}.bl-tools button{font-size:10px;letter-spacing:.1em;padding:5px 11px;border:1px solid var(--gold);color:var(--gold);background:none;cursor:pointer}.bl-tools button:hover{background:var(--gold);color:#2a1a02}.bl-tools .msg{color:var(--faint);margin-left:auto}.bl-tools .msg.bad{color:var(--down)}
.bl-right{display:flex;flex-direction:column;min-width:0}.bl-right .an-cvw{flex:1;height:auto;min-height:220px}
.dcx-wrap{padding:10px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:12px;flex:1}.dcx-form label{display:block;font-size:9.5px;letter-spacing:.1em;color:var(--faint);text-transform:uppercase;margin:6px 0 3px}.dcx-form input{width:100%;background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:11.5px;padding:5px 7px}
.dcx-form p{font-size:10.5px;color:var(--muted);line-height:1.5;margin:6px 0}.dcx-form .row{display:flex;gap:8px;align-items:center;margin-top:8px}.dcx-form button{font-size:10px;letter-spacing:.1em;padding:6px 12px;border:1px solid var(--gold);color:var(--gold);background:none;cursor:pointer}.dcx-form button:hover{background:var(--gold);color:#2a1a02}.dcx-form button.danger{border-color:var(--down);color:var(--down)}.dcx-form button.danger:hover{background:var(--down);color:#fff}
.dcx-msg{font-size:10.5px;color:var(--muted)}.dcx-msg.bad{color:var(--down)}.dcx-msg.ok{color:var(--up)}
.dcx-state{display:flex;gap:8px;align-items:center;font-size:11px;padding:4px 0 8px;border-bottom:1px solid var(--line);margin-bottom:6px}.dcx-state .pill{font-size:9px;letter-spacing:.12em;padding:1px 6px;border:1px solid var(--line-strong);color:var(--muted)}.dcx-state .pill.on{color:var(--up);border-color:var(--up)}
.g-foot{padding:6px 10px;border-top:1px solid var(--line);font-size:10px;color:var(--faint);line-height:1.45}
.g-fkeys{display:flex;gap:6px;flex-wrap:wrap;padding:6px 10px;border-top:1px solid var(--line);background:#06031a;font-size:10px;letter-spacing:.08em}.g-fkeys a{padding:3px 9px;border:1px solid var(--line-strong);color:var(--muted)}.g-fkeys a:hover{border-color:var(--gold);color:var(--gold)}
@media(max-width:980px){.bl-wrap,.dcx-wrap{grid-template-columns:1fr}.bl-left{border-right:0;border-bottom:1px solid var(--line)}.a-wide{grid-column:auto}}
"""

_TV_SYMBOLS = [("BTC", "BINANCE:BTCUSDT"), ("ETH", "BINANCE:ETHUSDT"), ("SOL", "BINANCE:SOLUSDT"), ("SPX", "SP:SPX"), ("NDX", "NASDAQ:NDX"), ("DOW", "DJ:DJI"),
               ("DAX", "XETR:DAX"), ("NIKKEI", "TVC:NI225"), ("DXY", "TVC:DXY"), ("GOLD", "TVC:GOLD"), ("CRUDE", "TVC:USOIL"), ("US10Y", "TVC:US10Y")]

BODY = r"""
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a>
  <a class="logo" href="/global">FINO<b>·</b>GLOBAL</a>
  <span class="sym" id="t-sym">BTC · ETH OPTIONS ON DERIBIT · WORLD INDICES</span>
  <div class="r">
    <span class="live off" id="conn">CONNECTING</span>
    <span id="clock">--:--:-- IST</span>
    <span id="who"><a href="/login">SIGN IN</a></span>
    <a href="/dashboard">← INDIA TERMINAL</a>
    <a href="/">← SITE</a>
  </div>
</header>

<div class="tape g-tape" aria-label="Global ticker"><div class="tape-inner" id="tape"><span><em class="dim">loading world tape…</em></span></div></div>

<main class="desk">
  <section class="panel a-wide" id="p-tv" aria-label="TradingView chart" style="min-height:520px">
    <div class="panel-hd"><span class="k">CHART</span><span class="s" id="tv-sym">BINANCE:BTCUSDT</span><span class="r"><span id="tv-state">TradingView</span></span></div>
    <div class="tv-top" id="tv-top">__TV_BUTTONS__<span class="an-note">change symbol, interval and studies inside the chart too</span></div>
    <div class="tv-wrap"><div id="tv"></div></div>
  </section>

  <section class="panel" id="p-vol" aria-label="Crypto volatility and funding">
    <div class="panel-hd"><span class="k">VOL</span><span class="s">DVOL · FUNDING · PERP OI</span><span class="r"><span id="vol-state">—</span></span></div>
    <div class="g-kpi" id="vol-kpi"></div>
    <div class="g-foot">DVOL is Deribit's 30-day implied volatility index (like VIX for BTC/ETH). Funding is the perpetual's current 8-hour rate: positive means longs pay shorts. Spot in ₹ via CoinGecko.</div>
  </section>

  <section class="panel a-wide" id="p-chain" aria-label="Crypto option chain">
    <div class="panel-hd"><span class="k">CHAIN</span><span class="s" id="oc-title">BTC OPTIONS · DERIBIT</span><span class="r"><span id="oc-kpis"></span><span id="oc-state">—</span></span></div>
    <div class="oc-top">__SEG__<select class="an-sel" id="oc-exp" aria-label="Expiry"></select>
      <span class="seg" id="oc-view"><button type="button" data-v="oi" class="on">OI</button><button type="button" data-v="greeks">GREEKS</button><button type="button" data-v="second">2ND ORDER</button><button type="button" data-v="third">3RD ORDER</button></span>
      <span class="bl-side" id="oc-side"><button type="button" data-s="1" class="on buy">CLICK = BUY</button><button type="button" data-s="-1" class="sell">CLICK = SELL</button></span>
      <span class="an-note" id="oc-note">click a CE or PE price to add it as a leg</span></div>
    <div class="scroll"><table class="oc-tbl"><thead id="oc-head"></thead><tbody id="oc-rows"></tbody></table></div>
    <div class="g-foot">Prices are Deribit mark prices converted to USD at the index (one contract = 1 BTC or 1 ETH). OI in coins. Greeks from mark IV with zero rate; theta and the time Greeks are per calendar day. Refreshes every 20 s.</div>
  </section>

  <section class="panel a-wide" id="p-build" aria-label="Crypto strategy builder">
    <div class="panel-hd"><span class="k">BUILD</span><span class="s" id="bl-title">OPTION BUYING &amp; SELLING · BTC</span><span class="r"><span id="bl-state">—</span></span></div>
    <div class="bl-wrap">
      <div class="bl-left">
        <div class="bl-presets">
          <div><h5 class="buy">Option buying</h5>__BUY_PRESETS__</div>
          <div><h5 class="sell">Option selling</h5>__SELL_PRESETS__</div>
        </div>
        <div class="scroll"><table class="bl-legs"><thead><tr><th>SIDE</th><th>RIGHT</th><th>STRIKE</th><th>QTY</th><th>PRICE $</th><th>IV</th><th>Δ</th><th></th></tr></thead><tbody id="bl-rows"><tr><td colspan="8" style="text-align:left;color:var(--faint)">pick a preset, or click prices in the chain</td></tr></tbody></table></div>
        <div class="bl-tools"><button type="button" id="bl-add">+ LEG</button><button type="button" id="bl-eval">EVALUATE</button><button type="button" id="bl-clear">CLEAR</button><label class="an-lbl">SIZE <input class="an-in" id="bl-size" value="1" style="width:46px;text-transform:none" aria-label="Contracts"> × coin</label><span class="msg" id="bl-msg"></span></div>
      </div>
      <div class="bl-right">
        <div class="an-kpi" id="bl-kpi"></div>
        <div class="an-cvw"><canvas class="an-cv" id="bl-cv"></canvas></div>
        <div class="g-foot" id="bl-foot">Payoff at expiry in USD for the size above. Net premium: positive = credit received (selling), negative = debit paid (buying). Greeks are the position's, per contract size.</div>
      </div>
    </div>
  </section>

__ANALYTICS__

  <section class="panel a-wide" id="p-coindcx" aria-label="CoinDCX account">
    <div class="panel-hd"><span class="k">DCX</span><span class="s">COINDCX · ACCOUNT</span><span class="r"><span id="dcx-state">—</span></span></div>
    <div class="dcx-wrap">
      <div class="dcx-form" id="dcx-form">
        <div class="dcx-state"><span class="pill" id="dcx-pill">NOT CONNECTED</span><span id="dcx-who"></span></div>
        <div id="dcx-connect">
          <p>Log in to CoinDCX → Profile → <b>API Keys</b> → create a key with <b>read</b> permission (no withdrawals). Paste both here. Finostat seals the pair on its server and never shows it again.</p>
          <label for="dcx-key">API key</label><input id="dcx-key" autocomplete="off" spellcheck="false">
          <label for="dcx-secret">API secret</label><input id="dcx-secret" type="password" autocomplete="off">
          <div class="row"><button type="button" id="dcx-go">CONNECT COINDCX</button><span class="dcx-msg" id="dcx-msg"></span></div>
        </div>
        <div id="dcx-connected" hidden>
          <p>Balances and open orders load from your CoinDCX account every 30 seconds while this panel is visible. Order placement from Finostat is not switched on yet.</p>
          <div class="row"><button type="button" id="dcx-refresh">REFRESH</button><button type="button" class="danger" id="dcx-off">DISCONNECT</button><span class="dcx-msg" id="dcx-msg2"></span></div>
        </div>
      </div>
      <div>
        <div class="scroll" style="max-height:220px"><table><thead><tr><th style="text-align:left">ASSET</th><th>BALANCE</th><th>LOCKED</th></tr></thead><tbody id="dcx-bal"><tr><td colspan="3" style="text-align:left;color:var(--faint)">connect to see balances</td></tr></tbody></table></div>
        <div class="scroll" style="max-height:180px;margin-top:8px"><table><thead><tr><th style="text-align:left">OPEN ORDER</th><th>SIDE</th><th>QTY</th><th>PRICE</th></tr></thead><tbody id="dcx-ord"></tbody></table></div>
      </div>
    </div>
  </section>
</main>
<div class="g-fkeys"><a href="#p-tv">CHART</a><a href="#p-chain">CHAIN</a><a href="#p-build">BUILD</a><a href="#p-surf">SURF</a><a href="#p-skew">SKEW</a><a href="#p-curv">CURV</a><a href="#p-gex">GEX</a><a href="#p-coindcx">COINDCX</a><a href="/dashboard">INDIA TERMINAL</a></div>
"""

JS = r"""
(function(){
  function $(id){ return document.getElementById(id); }
  function nf(x,d){ if(x==null||isNaN(x)) return '—'; d=d==null?1:d; return Number(x).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}); }
  function usd(x,d){ if(x==null) return '—'; return (x<0?'−':'')+'$'+nf(Math.abs(x),d==null?0:d); }
  function getJSON(url,ok,fail){ fetch(url,{credentials:'same-origin'}).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){ if(x.s>=400){ fail(x.j&&x.j.error?x.j.error:(x.s===402?'Desk plan required':'HTTP '+x.s)); } else ok(x.j); }).catch(function(){ fail('network'); }); }
  function postJSON(url,body,ok,fail){ fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify(body)}).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){ if(x.s>=400){ fail(x.j&&x.j.error?x.j.error:'HTTP '+x.s, x.j); } else ok(x.j); }).catch(function(){ fail('network'); }); }
  function visible(id){ var el=$(id); return el&&!el.hidden&&!document.hidden; }
  function segInit(el,attr,onChange){ if(!el) return; el.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; Array.prototype.forEach.call(el.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); onChange(b.getAttribute(attr)); }); }
  var MON=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  function expLabel(ms){ var d=new Date(ms); return d.getUTCDate()+' '+MON[d.getUTCMonth()]+' '+String(d.getUTCFullYear()).slice(2); }
  function css(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#fff'; }
  var C={gold:css('--gold'),cyan:css('--cyan'),pink:css('--pink'),up:css('--up'),down:css('--down'),faint:css('--faint'),text:css('--text')};
  function ctx2d(cv){ var r=cv.getBoundingClientRect(), dpr=window.devicePixelRatio||1; var w=Math.max(200,Math.floor(r.width)), h=Math.max(120,Math.floor(r.height)); if(cv.width!==Math.floor(w*dpr)||cv.height!==Math.floor(h*dpr)){ cv.width=Math.floor(w*dpr); cv.height=Math.floor(h*dpr); } var c=cv.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,w,h); c.font='10px IBM Plex Mono,monospace'; return {c:c,w:w,h:h}; }
  var locked=!!window.FINO_LOCKED;

  /* clock + who */
  function tick(){ var d=new Date(); var ist=d.toLocaleTimeString('en-GB',{timeZone:'Asia/Kolkata',hour12:false}); var utc=d.toLocaleTimeString('en-GB',{timeZone:'UTC',hour12:false,hour:'2-digit',minute:'2-digit'}); $('clock').textContent=ist+' IST · '+utc+' UTC'; }
  tick(); setInterval(tick,1000);
  if(!locked){ getJSON('/api/me',function(m){ $('who').innerHTML='<a href="/account">'+(m.email||'ACCOUNT').replace('@mobile.finostat','').toUpperCase()+'</a>'; },function(){}); }

  /* tape + vol */
  var inr=null;
  function loadTape(){ if(locked) return; getJSON('/api/global/tape',function(d){
      var b='<span><em class="sec">CRYPTO</em></span>'+(d.crypto||[]).map(function(q){ var up=q.change==null?'':(q.change>=0?'up':'down'); return '<span><b>'+q.symbol+'</b><em>'+usd(q.price,q.price<10?3:0)+'</em><em class="'+up+'">'+(q.change==null?'':(q.change>=0?'+':'')+nf(q.change,2)+'%')+'</em>'+(q.inr?'<em class="dim">₹'+nf(q.inr,0)+'</em>':'')+'</span>'; }).join('')
        +'<span><em class="sec">WORLD</em></span>'+(d.global||[]).map(function(q){ var up=q.change==null?'':(q.change>=0?'up':'down'); return '<span><b>'+q.symbol+'</b><em>'+nf(q.price,q.price<100?2:0)+'</em><em class="'+up+'">'+(q.change==null?'':(q.change>=0?'+':'')+nf(q.change,2)+'%')+'</em>'+(q.status&&q.status!=='REG_MKT'?'<em class="dim">'+(q.status==='PRE_MKT'?'pre':q.status==='POST_MKT'?'post':'closed')+'</em>':'')+'</span>'; }).join('');
      $('tape').innerHTML=b+b; var ok=(d.crypto||[]).length>0; var c=$('conn'); c.textContent=ok?'LIVE':'STALE'; c.className='live'+(ok?'':' off');
      var btc=(d.crypto||[]).filter(function(q){ return q.symbol==='BTC'; })[0]; if(btc&&btc.inr&&btc.price) inr=btc.inr/btc.price;
      var v=d.vol||{}, items=[]; ['BTC','ETH'].forEach(function(cur){ var x=v[cur]||{}; items.push([cur+' DVOL',x.dvol!=null?nf(x.dvol,1)+'<i>%</i>':'—','c']); items.push([cur+' funding 8h',x.funding_8h!=null?(x.funding_8h*100>=0?'+':'')+nf(x.funding_8h*100,4)+'<i>%</i>':'—',x.funding_8h>=0?'up':'down']); items.push([cur+' perp OI',x.oi_usd!=null?usd(x.oi_usd/1e6,1)+'<i>M</i>':'—','m']); items.push([cur+' 24h range',x.low!=null?nf(x.low,0)+'–'+nf(x.high,0):'—','m']); });
      if(btc&&btc.inr) items.push(['USD/INR (via BTC)',nf(inr,2),'m']);
      $('vol-kpi').innerHTML=items.map(function(k){ return '<div><small>'+k[0]+'</small><b class="'+(k[2]||'')+'">'+k[1]+'</b></div>'; }).join(''); $('vol-state').textContent='DERIBIT · '+new Date().toLocaleTimeString('en-GB',{hour12:false,hour:'2-digit',minute:'2-digit'});
    },function(e){ $('vol-state').textContent=e; }); }
  loadTape(); setInterval(loadTape,20000);

  /* TradingView */
  var TV=__TV_MAP__, tvSym='BINANCE:BTCUSDT', tvWidget=null;
  function mountTV(){ if(locked||!window.TradingView){ return; } $('tv').innerHTML=''; try{ tvWidget=new TradingView.widget({container_id:'tv',autosize:true,symbol:tvSym,interval:'15',timezone:'Asia/Kolkata',theme:'dark',style:'1',locale:'en',toolbar_bg:'#0c0626',enable_publishing:false,hide_side_toolbar:false,allow_symbol_change:true,withdateranges:true,details:false,studies:['Volume@tv-basicstudies'],overrides:{'paneProperties.background':'#0c0626','paneProperties.backgroundType':'solid'}}); $('tv-state').textContent='TradingView'; }catch(e){ $('tv-state').textContent='chart blocked'; } }
  if(!locked){ var s=document.createElement('script'); s.src='https://s3.tradingview.com/tv.js'; s.async=true; s.onload=mountTV; s.onerror=function(){ $('tv-state').textContent='TradingView unreachable'; $('tv').innerHTML='<div style="padding:20px;color:var(--faint)">TradingView could not load (ad-blocker or network). The chain, builder and analytics below do not depend on it.</div>'; }; document.head.appendChild(s); }
  $('tv-top').addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; Array.prototype.forEach.call($('tv-top').querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); tvSym=TV[b.getAttribute('data-tv')]||tvSym; $('tv-sym').textContent=tvSym; mountTV(); });

  /* chain */
  var oc={cur:'BTC',exp:null,view:'oi',side:1,data:null,timer:null};
  var VIEWS={oi:[['oi','OI'],['vol','VOL'],['iv','IV'],['ltp','PRICE']],greeks:[['delta','Δ'],['gamma','Γ'],['theta','Θ'],['vega','V'],['ltp','PRICE']],second:[['vanna','VANNA'],['charm','CHARM'],['vomma','VOMMA'],['veta','VETA'],['ltp','PRICE']],third:[['speed','SPEED'],['zomma','ZOMMA'],['color','COLOR'],['ultima','ULTIMA'],['ltp','PRICE']]};
  function fmtCell(k,v){ if(v==null) return '—'; if(k==='oi') return nf(v,1); if(k==='vol') return nf(v,1); if(k==='iv') return nf(v,1); if(k==='ltp') return nf(v,v<10?2:0); if(k==='delta') return nf(v,3); if(k==='gamma') return v.toExponential(2); if(k==='theta'||k==='vega') return nf(v,1); return Math.abs(v)>=100?nf(v,1):Math.abs(v)>=1?nf(v,3):v.toExponential(2); }
  segInit(document.querySelector('#p-chain .an-u'),'data-u',function(u){ oc.cur=u; oc.exp=null; bl.cur=u; bl.legs=[]; bl.exp=null; renderLegs(); loadChain(); });
  segInit($('oc-view'),'data-v',function(v){ oc.view=v; renderChain(); });
  segInit($('oc-side'),'data-s',function(s){ oc.side=Number(s); $('oc-note').textContent=oc.side>0?'click a CE or PE price to BUY it':'click a CE or PE price to SELL it'; });
  $('oc-exp').addEventListener('change',function(e){ oc.exp=Number(e.target.value); bl.exp=oc.exp; loadChain(); });
  function loadChain(){ if(locked) return; $('oc-state').textContent='loading…'; getJSON('/api/global/chain?cur='+oc.cur+(oc.exp?'&expiry='+oc.exp:''),function(d){ oc.data=d; oc.exp=d.expiry; bl.exp=d.expiry; bl.chain=d; var sel=$('oc-exp'); var have=Array.prototype.map.call(sel.options,function(o){ return o.value; }).join(); if(have!==d.expiries.join()){ sel.innerHTML=d.expiries.map(function(e){ return '<option value="'+e+'">'+expLabel(e)+'</option>'; }).join(''); } sel.value=String(d.expiry);
      $('oc-title').textContent=oc.cur+' OPTIONS · DERIBIT · '+expLabel(d.expiry)+' · '+nf(d.t_years*365,1)+'d'; var o=d.oi||{}; $('oc-kpis').innerHTML='SPOT <b style="color:var(--cyan)">'+usd(d.spot,0)+'</b> · PCR <b>'+(o.pcr!=null?nf(o.pcr,2):'—')+'</b> · MAX PAIN <b>'+(o.max_pain!=null?nf(o.max_pain,0):'—')+'</b> · CALL WALL '+(o.call_wall!=null?nf(o.call_wall,0):'—')+' · PUT WALL '+(o.put_wall!=null?nf(o.put_wall,0):'—'); $('oc-state').textContent='LIVE · '+new Date().toLocaleTimeString('en-GB',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'}); $('bl-title').textContent='OPTION BUYING & SELLING · '+oc.cur+' · '+expLabel(d.expiry); renderChain(); },function(e){ $('oc-state').textContent=e; }); }
  function renderChain(){ var d=oc.data; if(!d) return; var cols=VIEWS[oc.view]; var head='<tr>'+cols.map(function(c){ return '<th class="ce">'+c[1]+'</th>'; }).join('')+'<th>STRIKE</th>'+cols.slice().reverse().map(function(c){ return '<th class="pe">'+c[1]+'</th>'; }).join('')+'</tr>'; $('oc-head').innerHTML=head; var maxoi=(d.oi&&d.oi.max_oi)||1;
    $('oc-rows').innerHTML=d.rows.map(function(r){ var ce=r.ce||{}, pe=r.pe||{}; function cell(side,o,k){ var v=o[k]; var cls=(k==='ltp'?'px':'')+((side==='ce'&&r.strike<d.spot)||(side==='pe'&&r.strike>d.spot)?' itm':''); var bar=(k==='oi'&&v)?'<i class="oib '+side+'" style="width:'+Math.round(v/maxoi*40)+'px"></i>':''; return '<td class="'+cls+'"'+(k==='ltp'?' data-k="'+r.strike+'" data-r="'+side.toUpperCase()+'" title="'+(oc.side>0?'buy':'sell')+' '+r.strike+' '+side.toUpperCase()+'"':'')+'>'+bar+fmtCell(k,v)+'</td>'; }
      return '<tr'+(r.atm?' class="atm"':'')+'>'+cols.map(function(c){ return cell('ce',ce,c[0]); }).join('')+'<td class="k">'+nf(r.strike,0)+'</td>'+cols.slice().reverse().map(function(c){ return cell('pe',pe,c[0]); }).join('')+'</tr>'; }).join(''); }
  $('oc-rows').addEventListener('click',function(e){ var td=e.target.closest('td.px'); if(!td) return; var k=Number(td.getAttribute('data-k')), r=td.getAttribute('data-r'); addLeg(r,k,oc.side); });
  if(!locked){ loadChain(); setInterval(function(){ if(visible('p-chain')) loadChain(); },20000); }

  /* builder */
  var bl={cur:'BTC',exp:null,legs:[],chain:null,metrics:null};
  function addLeg(right,strike,qty){ var same=bl.legs.filter(function(l){ return l.right===right&&l.strike===strike; })[0]; if(same){ same.qty+=qty; if(same.qty===0) bl.legs=bl.legs.filter(function(l){ return l!==same; }); } else bl.legs.push({right:right,strike:strike,qty:qty}); renderLegs(); evaluate(); }
  function strikes(){ return bl.chain?bl.chain.rows.map(function(r){ return r.strike; }):[]; }
  function renderLegs(){ var tb=$('bl-rows'); if(!bl.legs.length){ tb.innerHTML='<tr><td colspan="8" style="text-align:left;color:var(--faint)">pick a preset, or click prices in the chain</td></tr>'; return; } var ks=strikes();
    tb.innerHTML=bl.legs.map(function(l,i){ var side=l.qty>0?'buy':'sell'; return '<tr><td class="'+side+'">'+(l.qty>0?'BUY':'SELL')+'</td><td><select data-i="'+i+'" data-f="right"><option'+(l.right==='CE'?' selected':'')+'>CE</option><option'+(l.right==='PE'?' selected':'')+'>PE</option></select></td><td><select data-i="'+i+'" data-f="strike">'+ks.map(function(k){ return '<option value="'+k+'"'+(k===l.strike?' selected':'')+'>'+nf(k,0)+'</option>'; }).join('')+'</select></td><td><input type="number" data-i="'+i+'" data-f="qty" value="'+l.qty+'" min="-10" max="10" step="1"></td><td>'+(l.price!=null?nf(l.price,l.price<10?2:0):'—')+'</td><td>'+(l.iv!=null?nf(l.iv,1):'—')+'</td><td>'+(l.delta!=null?nf(l.delta,2):'—')+'</td><td><button type="button" class="x" data-x="'+i+'" aria-label="Remove leg">×</button></td></tr>'; }).join(''); }
  $('bl-rows').addEventListener('change',function(e){ var el=e.target; var i=Number(el.getAttribute('data-i')), f=el.getAttribute('data-f'); if(!(i>=0)||!f) return; var l=bl.legs[i]; if(f==='qty'){ var q=parseInt(el.value,10)||0; if(q===0){ bl.legs.splice(i,1); } else l.qty=Math.max(-10,Math.min(10,q)); } else if(f==='strike') l.strike=Number(el.value); else l.right=el.value; renderLegs(); evaluate(); });
  $('bl-rows').addEventListener('click',function(e){ var b=e.target.closest('button.x'); if(!b) return; bl.legs.splice(Number(b.getAttribute('data-x')),1); renderLegs(); evaluate(); });
  $('bl-add').addEventListener('click',function(){ if(!bl.chain) return; addLeg('CE',bl.chain.atm,oc.side); });
  $('bl-clear').addEventListener('click',function(){ bl.legs=[]; bl.metrics=null; renderLegs(); $('bl-kpi').innerHTML=''; drawPayoff(); $('bl-state').textContent='—'; });
  $('bl-eval').addEventListener('click',evaluate); $('bl-size').addEventListener('change',evaluate);
  document.querySelector('.bl-presets').addEventListener('click',function(e){ var b=e.target.closest('button[data-p]'); if(!b) return; runPreset(b.getAttribute('data-p')); });
  function size(){ var s=parseFloat($('bl-size').value); return (s>0&&s<=1000)?s:1; }
  function runPreset(p){ if(locked) return; $('bl-state').textContent='pricing…'; postJSON('/api/global/strategy',{cur:bl.cur,expiry:bl.exp,preset:p,size:size()},onEval,function(e){ $('bl-msg').textContent=e; $('bl-msg').className='msg bad'; $('bl-state').textContent='—'; }); }
  function evaluate(){ if(locked||!bl.legs.length){ return; } $('bl-state').textContent='pricing…'; postJSON('/api/global/strategy',{cur:bl.cur,expiry:bl.exp,legs:bl.legs.map(function(l){ return {right:l.right,strike:l.strike,qty:l.qty}; }),size:size()},onEval,function(e){ $('bl-msg').textContent=e; $('bl-msg').className='msg bad'; $('bl-state').textContent='—'; }); }
  function onEval(d){ bl.legs=d.legs; bl.metrics=d.metrics; bl.exp=d.expiry; renderLegs(); $('bl-msg').textContent=d.name||''; $('bl-msg').className='msg'; var m=d.metrics, g=m.greeks||{}; var mult=d.size||1;
    var items=[['net premium',usd(m.net_premium_lot,0),m.net_premium_lot>=0?'up':'down'],['max profit',m.max_profit_lot==null?'UNLIMITED':usd(m.max_profit_lot,0),'up'],['max loss',m.max_loss_lot==null?'UNLIMITED':usd(m.max_loss_lot,0),'down'],['breakevens',(m.breakevens||[]).map(function(b){ return nf(b,0); }).join(' · ')||'—','m'],['delta',g.delta!=null?nf(g.delta,3):'—','c'],['theta / day',g.theta!=null?usd(g.theta,0):'—',g.theta>=0?'up':'down'],['vega / vol pt',g.vega!=null?usd(g.vega,0):'—','c'],['in ₹',inr&&m.net_premium_lot!=null?'₹'+nf(m.net_premium_lot*inr,0):'—','m']];
    $('bl-kpi').innerHTML=items.map(function(k){ return '<div><small>'+k[0]+'</small><b class="'+(k[2]||'')+'">'+k[1]+'</b></div>'; }).join(''); $('bl-state').textContent=(m.net_premium>=0?'CREDIT':'DEBIT')+' · '+bl.legs.length+' LEG'+(bl.legs.length>1?'S':'')+' · SIZE '+mult; drawPayoff(); }
  function drawPayoff(){ var cv=$('bl-cv'); if(!cv) return; var g=ctx2d(cv), c=g.c, m=bl.metrics; if(!m||!m.payoff){ c.fillStyle=C.faint; c.fillText('payoff appears here',12,24); return; } var pts=m.payoff, pad={l:64,r:12,t:12,b:22}; var xs=pts.map(function(p){ return p[0]; }), ys=pts.map(function(p){ return p[1]; }); var x0=xs[0], x1=xs[xs.length-1]; var lo=Math.min(0,Math.min.apply(null,ys)), hi=Math.max(0,Math.max.apply(null,ys)); var mg=(hi-lo)*.1||1; lo-=mg; hi+=mg;
    function sx(x){ return pad.l+(x-x0)/((x1-x0)||1)*(g.w-pad.l-pad.r); } function sy(y){ return pad.t+(hi-y)/((hi-lo)||1)*(g.h-pad.t-pad.b); }
    c.strokeStyle='rgba(190,150,255,.14)'; c.beginPath(); c.moveTo(pad.l,pad.t); c.lineTo(pad.l,g.h-pad.b); c.lineTo(g.w-pad.r,g.h-pad.b); c.stroke(); c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){ var v=lo+(hi-lo)*i/4; c.fillText(usd(v,0),pad.l-4,sy(v)+3); } c.textAlign='center'; for(var j=0;j<=5;j++){ var xv=x0+(x1-x0)*j/5; c.fillText(nf(xv,0),sx(xv),g.h-6); }
    c.strokeStyle='rgba(255,255,255,.25)'; c.setLineDash([3,3]); c.beginPath(); c.moveTo(pad.l,sy(0)); c.lineTo(g.w-pad.r,sy(0)); c.stroke(); c.setLineDash([]);
    /* fill above/below zero */
    for(var k=1;k<pts.length;k++){ var a=pts[k-1], b=pts[k]; var col=(a[1]+b[1])/2>=0?'rgba(61,214,140,.18)':'rgba(255,92,108,.18)'; c.fillStyle=col; c.beginPath(); c.moveTo(sx(a[0]),sy(0)); c.lineTo(sx(a[0]),sy(a[1])); c.lineTo(sx(b[0]),sy(b[1])); c.lineTo(sx(b[0]),sy(0)); c.closePath(); c.fill(); }
    c.strokeStyle=C.gold; c.lineWidth=1.8; c.beginPath(); pts.forEach(function(p,i){ if(i===0) c.moveTo(sx(p[0]),sy(p[1])); else c.lineTo(sx(p[0]),sy(p[1])); }); c.stroke(); c.lineWidth=1;
    if(bl.chain&&bl.chain.spot){ var sp=bl.chain.spot; c.strokeStyle=C.cyan; c.setLineDash([4,3]); c.beginPath(); c.moveTo(sx(sp),pad.t); c.lineTo(sx(sp),g.h-pad.b); c.stroke(); c.setLineDash([]); c.fillStyle=C.cyan; c.textAlign='center'; c.fillText('spot '+nf(sp,0),sx(sp),pad.t-2); }
    (m.breakevens||[]).forEach(function(b){ c.fillStyle=C.gold; c.textAlign='center'; c.fillText('BE '+nf(b,0),sx(b),sy(0)-4); }); }
  window.addEventListener('resize',function(){ drawPayoff(); });

  /* CoinDCX */
  var dcx={timer:null};
  function dcxRender(d){ var on=!!d.connected; $('dcx-pill').textContent=on?'CONNECTED':'NOT CONNECTED'; $('dcx-pill').className='pill'+(on?' on':''); $('dcx-who').textContent=on?(d.user||'')+(d.email?' · '+d.email:''):''; $('dcx-connect').hidden=on; $('dcx-connected').hidden=!on; $('dcx-state').textContent=on?'CONNECTED':'—';
    if(on){ var b=d.balances||[]; $('dcx-bal').innerHTML=b.length?b.map(function(x){ return '<tr><td style="text-align:left">'+x.currency+'</td><td>'+nf(x.balance,x.balance<1?6:2)+'</td><td>'+nf(x.locked,x.locked<1?6:2)+'</td></tr>'; }).join(''):'<tr><td colspan="3" style="text-align:left;color:var(--faint)">'+(d.balances_error||'no balances')+'</td></tr>'; var o=d.orders||[]; $('dcx-ord').innerHTML=o.length?o.map(function(x){ return '<tr><td style="text-align:left">'+(x.market||x.symbol||'')+'</td><td>'+(x.side||'').toUpperCase()+'</td><td>'+nf(x.total_quantity||x.quantity,4)+'</td><td>'+nf(x.price_per_unit||x.price,2)+'</td></tr>'; }).join(''):'<tr><td colspan="4" style="text-align:left;color:var(--faint)">'+(d.orders_error||'no open orders')+'</td></tr>'; } }
  function dcxLoad(){ if(locked) return; getJSON('/api/coindcx',dcxRender,function(e){ $('dcx-state').textContent=e; }); }
  $('dcx-go').addEventListener('click',function(){ var key=$('dcx-key').value.trim(), sec=$('dcx-secret').value.trim(); if(!key||!sec){ $('dcx-msg').textContent='paste both the key and the secret'; $('dcx-msg').className='dcx-msg bad'; return; } $('dcx-msg').textContent='checking with CoinDCX…'; $('dcx-msg').className='dcx-msg'; $('dcx-go').disabled=true; postJSON('/api/coindcx/connect',{key:key,secret:sec},function(d){ $('dcx-go').disabled=false; $('dcx-key').value=''; $('dcx-secret').value=''; $('dcx-msg').textContent='connected'; $('dcx-msg').className='dcx-msg ok'; dcxRender(d); },function(e){ $('dcx-go').disabled=false; $('dcx-msg').textContent=e; $('dcx-msg').className='dcx-msg bad'; }); });
  $('dcx-off').addEventListener('click',function(){ postJSON('/api/coindcx/disconnect',{},function(){ $('dcx-bal').innerHTML='<tr><td colspan="3" style="text-align:left;color:var(--faint)">connect to see balances</td></tr>'; $('dcx-ord').innerHTML=''; dcxRender({connected:false}); },function(e){ $('dcx-msg2').textContent=e; $('dcx-msg2').className='dcx-msg bad'; }); });
  $('dcx-refresh').addEventListener('click',dcxLoad);
  if(!locked){ dcxLoad(); setInterval(function(){ if(visible('p-coindcx')&&!$('dcx-connected').hidden) dcxLoad(); },30000); }
})();
"""

_BUY = [("long-straddle", "Long straddle"), ("long-strangle", "Long strangle"), ("bull-call-spread", "Bull call spread"), ("bear-put-spread", "Bear put spread"), ("butterfly", "Call butterfly")]
_SELL = [("short-straddle", "Short straddle"), ("short-strangle", "Short strangle"), ("iron-condor", "Iron condor"), ("iron-fly", "Iron fly"), ("ratio-spread", "Call ratio 1×2")]


def _doc() -> str:
    css = pages.DASHBOARD.split("<style>", 1)[1].split("</style>", 1)[0]
    tv_buttons = "".join(f'<button type="button" data-tv="{k}"{" class=on" if k == "BTC" else ""}>{k}</button>' for k, _ in _TV_SYMBOLS)
    tv_map = "{" + ",".join(f"{k}:'{v}'" for k, v in _TV_SYMBOLS) + "}"
    body = (BODY.replace("__TV_BUTTONS__", tv_buttons).replace("__SEG__", _SEG).replace("__ANALYTICS__", _analytics_markup())
            .replace("__BUY_PRESETS__", "".join(f'<button type="button" data-p="{k}">{v}</button>' for k, v in _BUY))
            .replace("__SELL_PRESETS__", "".join(f'<button type="button" data-p="{k}">{v}</button>' for k, v in _SELL)))
    js = JS.replace("__TV_MAP__", tv_map)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Finostat Global · Crypto Terminal</title>
<meta name="robots" content="noindex">
<meta name="theme-color" content="#0c0626">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>{css}{CSS}</style>
</head>
<body>
__GUARD__{body}
<script>{js}</script>
<script>{_analytics_js()}</script>
__PAYWALL__
</body>
</html>"""


_DOC = None


def render(locked: bool = False, signed_in: bool = False, plan: str = "starter") -> bytes:
    global _DOC
    if _DOC is None:
        _DOC = _doc()
    doc = _DOC
    if locked:
        guard = ('<script>window.FINO_LOCKED=true;window.fetch=function(){return Promise.reject(new Error("locked"));};'
                 'document.addEventListener("DOMContentLoaded",function(){document.body.classList.add("locked");});</script>')
        doc = doc.replace("__GUARD__", pages._PAYWALL_CSS + guard, 1)
        wall = pages._paywall(signed_in, plan).replace("LIVE TERMINAL", "GLOBAL · CRYPTO TERMINAL").replace("The live terminal is part of Desk", "The Global/Crypto terminal is part of Desk").replace("The terminal is for Desk members", "The Global/Crypto terminal is for Desk members")
        doc = doc.replace("__PAYWALL__", wall, 1)
    else:
        doc = doc.replace("__GUARD__", "", 1).replace("__PAYWALL__", "", 1)
    return doc.encode("utf-8")
