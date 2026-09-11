"""ALGO panel: create rule-based strategies, watch them run, stop or square off."""

MARKUP = """
  <section class="panel a-wide an" id="p-algo" aria-label="Algo strategies">
    <div class="panel-hd"><span class="k">ALGO</span><span class="s">RULE-BASED STRATEGIES · PAPER FIRST, LIVE WHEN THE BROKER IS ON</span><span class="r"><span class="an-state" id="ag-state">—</span></span></div>
    <div class="ag-wrap">
      <form class="ag-form" id="ag-form" autocomplete="off">
        <label>NAME <input id="ag-name" maxlength="60" placeholder="e.g. Thursday straddle"></label>
        <label>TEMPLATE <select id="ag-template"></select></label>
        <div class="ag-desc" id="ag-desc"></div>
        <div class="ag-grid">
          <label>UNDERLYING <select id="ag-u"><option>NIFTY 50</option><option>BANKNIFTY</option><option>FINNIFTY</option><option>SENSEX</option></select></label>
          <label>RUNS ON <select id="ag-days"><option value="expiry">expiry days</option><option value="daily">every session</option><option value="once">once (next session)</option></select></label>
          <label>ENTRY <input id="ag-entry" value="09:30" maxlength="5"></label>
          <label>EXIT <input id="ag-exit" value="15:15" maxlength="5"></label>
          <label>LOTS <input id="ag-lots" type="number" value="1" min="1" max="50"></label>
          <label>WINGS <input id="ag-wings" type="number" value="2" min="1" max="10"></label>
          <label>STOP-LOSS % <input id="ag-sl" type="number" value="30" min="5" max="500" title="loss as % of the credit taken"></label>
          <label>TARGET % <input id="ag-target" type="number" value="50" min="0" max="100" title="profit as % of the credit taken; 0 = none"></label>
          <label>MAX VIX <input id="ag-vix" type="number" step="0.1" placeholder="any" title="skip entry when INDIA VIX is above this"></label>
          <label>MAX SPOT MOVE % <input id="ag-move" type="number" step="0.1" placeholder="none" title="exit if spot moves this far from entry"></label>
          <label class="ag-chk"><input id="ag-trail" type="checkbox"> TRAILING STOP</label>
          <label>MODE <select id="ag-mode"><option value="paper">paper (BOOK)</option><option value="live">live (broker)</option></select></label>
        </div>
        <div class="ag-actions"><button type="submit" class="an-btn" id="ag-create">CREATE &amp; ARM</button><span class="an-note" id="ag-note">stop-loss and target are % of the credit received · exits at the exit time regardless</span></div>
      </form>
      <div class="ag-list scroll" id="ag-list"><div class="ev-empty">no algos yet — create one on the left</div></div>
    </div>
  </section>
"""

CSS = r"""
.ag-wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);flex:1;min-height:0}
.ag-form{padding:10px 12px;border-right:1px solid var(--line);font-size:10.5px;display:flex;flex-direction:column;gap:8px}
.ag-form label{display:flex;flex-direction:column;gap:3px;color:var(--faint);letter-spacing:.08em;font-size:9.5px}
.ag-form input,.ag-form select{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:11.5px;padding:4px 6px;min-width:0}
.ag-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.ag-chk{flex-direction:row!important;align-items:center;gap:6px!important;align-self:end;padding-bottom:6px}
.ag-desc{color:var(--muted);font-size:11px;line-height:1.45;border-left:2px solid var(--gold);padding-left:8px}
.ag-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.ag-list{padding:8px 10px;display:flex;flex-direction:column;gap:8px}
.ag-card{border:1px solid var(--line-strong);background:var(--panel-hd);padding:8px 10px;font-size:11px}
.ag-card .hd{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.ag-card .nm{font-family:var(--display);font-size:17px;text-transform:uppercase;color:var(--text)}
.ag-pill{font-size:9px;letter-spacing:.12em;padding:1px 6px;border:1px solid var(--line-strong);color:var(--muted)}.ag-pill.running{color:var(--up);border-color:var(--up)}.ag-pill.armed{color:var(--gold);border-color:var(--gold)}.ag-pill.done{color:var(--faint)}.ag-pill.error{color:var(--down);border-color:var(--down)}.ag-pill.live{color:var(--cyan);border-color:var(--cyan)}
.ag-card .pnl{margin-left:auto;font-family:var(--display);font-size:18px}.ag-card .pnl.up{color:var(--up)}.ag-card .pnl.down{color:var(--down)}
.ag-card .meta{color:var(--muted);font-size:10.5px;margin-top:3px}
.ag-card .log{margin-top:6px;color:var(--faint);font-size:10px;line-height:1.45;max-height:64px;overflow:auto}.ag-card .log b{color:var(--muted);font-weight:500}
.ag-card .btns{display:flex;gap:6px;margin-top:6px}.ag-card .btns button{font-size:9.5px;letter-spacing:.08em;padding:3px 8px;border:1px solid var(--line-strong);color:var(--muted);background:none;cursor:pointer}.ag-card .btns button:hover{border-color:var(--gold);color:var(--gold)}.ag-card .btns button.danger:hover{border-color:var(--down);color:var(--down)}
@media(max-width:860px){.ag-wrap{grid-template-columns:1fr}.ag-form{border-right:0;border-bottom:1px solid var(--line)}.ag-grid{grid-template-columns:1fr 1fr}}
"""

JS = r"""
(function(){
  var panel=document.getElementById('p-algo'); if(!panel) return;
  var $=function(id){ return document.getElementById(id); };
  var TPL={}; var listEl=$('ag-list'), stateEl=$('ag-state'), noteEl=$('ag-note');
  function inr(x){ if(x==null) return '—'; var a=Math.abs(x); return (x<0?'−':'')+'₹'+(a>=1e5?(a/1e5).toFixed(2)+' L':Math.round(a).toLocaleString('en-IN')); }
  function api(body,cb){ var o=body?{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify(body),credentials:'same-origin'}:{credentials:'same-origin'}; fetch('/api/algo',o).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){ cb(x.s,x.j); }).catch(function(){ cb(0,{error:'network'}); }); }
  function fillTemplates(t){ TPL=t; var sel=$('ag-template'); if(sel.options.length) return; sel.innerHTML=Object.keys(t).map(function(k){ return '<option value="'+k+'">'+t[k].label+'</option>'; }).join(''); descFor(); }
  function descFor(){ var k=$('ag-template').value; var t=TPL[k]; if(!t) return; $('ag-desc').textContent=t.desc; $('ag-days').value=t.days||'expiry'; }
  $('ag-template').addEventListener('change',descFor);
  function load(){ api(null,function(s,j){ if(s!==200){ stateEl.textContent=j&&j.error?j.error:'HTTP '+s; stateEl.className='an-state err'; return; } fillTemplates(j.templates); stateEl.textContent=(j.engine&&j.engine.in_session?'ENGINE LIVE':'ENGINE IDLE · runs 09:15–15:30')+(j.broker?' · BROKER ON':''); stateEl.className='an-state ok'; render(j.algos||[]); }); }
  function render(list){ if(!list.length){ listEl.innerHTML='<div class="ev-empty">no algos yet — create one on the left. Paper mode books trades in your BOOK; live mode needs the broker connected.</div>'; return; }
    listEl.innerHTML=list.map(function(a){ var p=a.params, st=a.state||{}; var pnl=a.live_pnl; var pill='<span class="ag-pill '+a.status+'">'+a.status.toUpperCase()+'</span>'+(p.mode==='live'?'<span class="ag-pill live">LIVE</span>':'<span class="ag-pill">PAPER</span>');
      var meta=p.u+' · '+a.label+' · in '+p.entry+' out '+p.exit+' · '+p.lots+' lot'+(p.lots>1?'s':'')+' · SL '+p.sl_pct+'%'+(p.target_pct?' · target '+p.target_pct+'%':'')+(p.trail?' · trailing':'')+' · '+({expiry:'expiry days',daily:'every session',once:'once'})[p.days]+(p.max_vix?' · VIX ≤ '+p.max_vix:'')+(p.max_move_pct?' · move ≤ '+p.max_move_pct+'%':'');
      var run= a.status==='running'?'<div class="meta">credit '+(st.credit!=null?st.credit.toFixed(2):'—')+'/unit · entry spot '+(st.entry_spot||'—')+' · max P&L '+inr(st.max_pnl)+'</div>':'';
      var real=a.runs?'<div class="meta">'+a.runs+' run'+(a.runs>1?'s':'')+' · realised '+inr(a.realized_total)+'</div>':'';
      var log=(a.log||[]).slice(-5).reverse().map(function(l){ var d=new Date(l.t*1000); return '<div><b>'+d.toLocaleDateString('en-IN',{day:'2-digit',month:'short'})+' '+d.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false})+'</b> '+l.m+'</div>'; }).join('');
      var btns='<div class="btns">'+(a.status==='running'?'<button data-op="square_off" data-id="'+a.id+'">SQUARE OFF NOW</button>':'')+(a.status==='armed'||a.status==='running'?'<button data-op="stop" data-id="'+a.id+'">'+(a.status==='running'?'STOP AFTER EXIT':'DISARM')+'</button>':'<button data-op="arm" data-id="'+a.id+'">ARM</button>')+'<button data-op="delete" data-id="'+a.id+'" class="danger">DELETE</button></div>';
      return '<div class="ag-card"><div class="hd"><span class="nm">'+a.name+'</span>'+pill+(pnl!=null?'<span class="pnl '+(pnl>=0?'up':'down')+'">'+inr(pnl)+'</span>':'')+'</div><div class="meta">'+meta+'</div>'+run+real+'<div class="log">'+log+'</div>'+btns+'</div>'; }).join(''); }
  listEl.addEventListener('click',function(e){ var b=e.target.closest('button[data-op]'); if(!b) return; var op=b.getAttribute('data-op'), id=Number(b.getAttribute('data-id')); if(op==='delete'&&!confirm('Delete this algo? A running position stays in the BOOK.')) return; if(op==='square_off'&&!confirm('Close the running position now at market marks?')) return; b.disabled=true; api({op:op,id:id},function(s,j){ if(s>=400){ noteEl.textContent=j.error||('HTTP '+s); } load(); }); });
  $('ag-form').addEventListener('submit',function(e){ e.preventDefault(); var body={op:'create',name:$('ag-name').value.trim(),template:$('ag-template').value,params:{u:$('ag-u').value,days:$('ag-days').value,entry:$('ag-entry').value.trim(),exit:$('ag-exit').value.trim(),lots:$('ag-lots').value,wings:$('ag-wings').value,sl_pct:$('ag-sl').value,target_pct:$('ag-target').value,max_vix:$('ag-vix').value||null,max_move_pct:$('ag-move').value||null,trail:$('ag-trail').checked,mode:$('ag-mode').value}};
    $('ag-create').disabled=true; api(body,function(s,j){ $('ag-create').disabled=false; if(s>=400){ noteEl.textContent=j.error||('HTTP '+s); noteEl.style.color='var(--down)'; return; } noteEl.style.color=''; noteEl.textContent='armed · it enters at '+body.params.entry+' on the next qualifying session'; $('ag-name').value=''; load(); }); });
  load(); setInterval(function(){ if(!document.hidden&&!panel.hidden) load(); },5000);
})();
"""
