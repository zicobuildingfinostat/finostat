"""The 'Ask Vega' chat widget: a floating button bottom-right and a chat sheet. Self-contained CSS/JS,
fixed palette so it looks the same on every page. Nothing moves on its own (no pulsing, no
auto-open); it only responds to the user's taps. `inject(doc)` appends it before </body>."""
from __future__ import annotations

SNIPPET = r"""
<style id="vega-css">
#vega-btn{position:fixed;right:16px;bottom:16px;z-index:1200;display:inline-flex;align-items:center;gap:9px;padding:10px 14px 10px 10px;background:#120a33;border:1px solid #f5c842;color:#ffe27a;font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;cursor:pointer;box-shadow:0 14px 40px rgba(0,0,0,.5),0 0 24px rgba(245,200,66,.15)}
#vega-btn:hover{background:#1c1052}#vega-btn i{width:26px;height:26px;border-radius:50%;background:linear-gradient(180deg,#ffe27a,#f2b830);color:#2a1a02;display:inline-flex;align-items:center;justify-content:center;font-style:normal;font-family:"Barlow Condensed",Impact,sans-serif;font-weight:700;font-size:16px}
#vega{position:fixed;right:16px;bottom:16px;z-index:1300;width:min(400px,calc(100vw - 32px));height:min(600px,calc(100vh - 32px));display:flex;flex-direction:column;background:#0c0626;border:1px solid #4a34a0;box-shadow:0 30px 90px rgba(0,0,0,.7),0 0 40px rgba(106,53,240,.2);font-family:"IBM Plex Sans",system-ui,sans-serif;color:#f1edff}
#vega[hidden]{display:none}
#vega .hd{display:flex;align-items:center;gap:10px;padding:9px 12px;background:#1c1052;border-bottom:1px solid #4a34a0;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase}
#vega .hd i{width:26px;height:26px;border-radius:50%;background:linear-gradient(180deg,#ffe27a,#f2b830);color:#2a1a02;display:inline-flex;align-items:center;justify-content:center;font-style:normal;font-family:"Barlow Condensed",Impact,sans-serif;font-weight:700;font-size:16px}
#vega .hd b{color:#f5c842;font-weight:600}#vega .hd span{color:#7fe0f0}#vega .hd small{margin-left:auto;color:#6d609e;font-size:9.5px;letter-spacing:.08em;text-transform:none}
#vega .hd button{background:none;border:0;color:#a89ccf;font-size:18px;cursor:pointer;padding:0 2px;line-height:1}#vega .hd button:hover{color:#f5c842}
#vega .log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;scrollbar-width:thin;scrollbar-color:#4a34a0 transparent}
#vega .m{max-width:88%;padding:9px 12px;font-size:13.5px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word}
#vega .m.u{align-self:flex-end;background:#2c1c66;border:1px solid #4a34a0;color:#f1edff}
#vega .m.v{align-self:flex-start;background:#120a33;border:1px solid #2c1c66;border-left:2px solid #f5c842}
#vega .m.v a{color:#7fe0f0;text-decoration:underline}#vega .m.wait{color:#a89ccf;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.08em}
#vega .chips{display:flex;gap:6px;flex-wrap:wrap;padding:0 12px 8px}#vega .chips button{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.04em;padding:5px 8px;border:1px solid #4a34a0;background:none;color:#a89ccf;cursor:pointer;text-align:left}#vega .chips button:hover{border-color:#f5c842;color:#f5c842}
#vega form{display:flex;gap:8px;padding:10px 12px;border-top:1px solid #2c1c66;background:#120a33}
#vega input{flex:1;min-width:0;background:#06031a;border:1px solid #4a34a0;color:#f1edff;font:inherit;font-size:14px;padding:9px 10px}#vega input:focus{outline:none;border-color:#f5c842}
#vega form button{background:linear-gradient(180deg,#ffe27a,#f2b830);color:#2a1a02;border:0;font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.1em;font-weight:700;padding:0 14px;cursor:pointer}#vega form button:disabled{opacity:.5;cursor:default}
#vega .fine{padding:4px 12px 8px;font-size:10px;color:#6d609e;font-family:"IBM Plex Mono",monospace;line-height:1.4}
@media(max-width:560px){#vega{right:0;bottom:0;width:100vw;height:min(88vh,640px);border-left:0;border-right:0;border-bottom:0}#vega-btn{right:12px;bottom:12px}}
@media print{#vega,#vega-btn{display:none}}
</style>
<button type="button" id="vega-btn" aria-controls="vega" aria-expanded="false" title="Ask Vega — Finostat's trading co-pilot"><i>V</i>Ask Vega</button>
<section id="vega" hidden role="dialog" aria-label="Vega, Finostat's trading co-pilot">
  <div class="hd"><i>V</i><b>VEGA</b><span>TRADING CO-PILOT</span><small>site guide · not advice</small><button type="button" id="vega-x" aria-label="Close">×</button></div>
  <div class="log" id="vega-log"></div>
  <div class="chips" id="vega-chips"></div>
  <form id="vega-form" autocomplete="off"><input id="vega-in" placeholder="Ask about Nifty, gold, a panel, a plan…" maxlength="2000" aria-label="Message Vega"><button type="submit" id="vega-send">SEND</button></form>
  <div class="fine">Vega points you to the right page and quotes the numbers the site already shows. Not a SEBI-registered adviser; never tells you what to buy.</div>
</section>
<script>
(function(){
  var $=function(id){ return document.getElementById(id); };
  var btn=$('vega-btn'), box=$('vega'), logEl=$('vega-log'), form=$('vega-form'), input=$('vega-in'), send=$('vega-send'), chips=$('vega-chips');
  if(!btn||!box) return;
  var hist=[]; try{ hist=JSON.parse(sessionStorage.getItem('vega_hist')||'[]'); }catch(e){ hist=[]; }
  var page=location.pathname;
  var SUGGEST=page.indexOf('/xau-sovereign')===0?['What is gold doing right now?','How does XAU Sovereign decide BUY or SELL?','What do I get for ₹8,000?','Does it repaint?']
    :page.indexOf('/global')===0?['What is the BTC option chain showing?','Explain the strategy builder','What is DVOL?','How do I connect CoinDCX?']
    :page.indexOf('/dashboard')===0?['Where is the option chain?','What does GEX mean?','How do I set an alert?','What is the ATM straddle now?']
    :['Where is the option chain?','What is gold doing?','Which plan should I pick?','What is max pain?'];
  function esc(s){ return String(s).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function linkify(s){ return esc(s).replace(/(^|[\s(])(\/[a-z0-9\-\/#?=&.]+)/gi,function(m,pre,path){ var tail=''; while(/[.,)]$/.test(path)){ tail=path.slice(-1)+tail; path=path.slice(0,-1); } return pre+'<a href="'+path+'">'+path+'</a>'+tail; }); }
  function add(role,text,cls){ var d=document.createElement('div'); d.className='m '+(role==='user'?'u':'v')+(cls?' '+cls:''); d.innerHTML=role==='user'?esc(text):linkify(text); logEl.appendChild(d); logEl.scrollTop=logEl.scrollHeight; return d; }
  function save(){ try{ sessionStorage.setItem('vega_hist',JSON.stringify(hist.slice(-12))); }catch(e){} }
  function renderChips(){ chips.innerHTML=hist.length?'':SUGGEST.map(function(s){ return '<button type="button">'+esc(s)+'</button>'; }).join(''); }
  function open(){ box.hidden=false; btn.hidden=true; btn.setAttribute('aria-expanded','true'); if(!logEl.children.length){ if(hist.length){ hist.forEach(function(m){ add(m.role,m.content); }); } else { add('assistant',"Hi, I'm Vega — Finostat's guide. Tell me what you're looking for — the terminal, the option chain, gold, FII/DII, the calendar, plans, or what a term means — and I'll take you there."); } } renderChips(); input.focus(); }
  function close(){ box.hidden=true; btn.hidden=false; btn.setAttribute('aria-expanded','false'); }
  btn.addEventListener('click',open); $('vega-x').addEventListener('click',close);
  document.addEventListener('keydown',function(e){ if(e.key==='Escape'&&!box.hidden) close(); });
  chips.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; input.value=b.textContent; form.dispatchEvent(new Event('submit',{cancelable:true})); });
  form.addEventListener('submit',function(e){ e.preventDefault(); var q=input.value.trim(); if(!q||send.disabled) return; input.value=''; add('user',q); hist.push({role:'user',content:q}); save(); renderChips(); send.disabled=true; var w=add('assistant','Vega is reading the tape…','wait');
    fetch('/api/vega',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify({messages:hist.slice(-12),page:page})}).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){ w.remove(); var t=x.j&&x.j.reply?x.j.reply:(x.j&&x.j.error?x.j.error:'Vega could not answer just now.'); add('assistant',t); if(x.j&&x.j.reply){ hist.push({role:'assistant',content:t}); save(); } }).catch(function(){ w.remove(); add('assistant','Network hiccup — try again.'); }).then(function(){ send.disabled=false; input.focus(); }); });
})();
</script>
"""


def inject(doc: bytes) -> bytes:
    """Append the widget before </body> (once)."""
    if b'id="vega-btn"' in doc or b"</body>" not in doc:
        return doc
    return doc.replace(b"</body>", SNIPPET.encode("utf-8") + b"</body>", 1)
