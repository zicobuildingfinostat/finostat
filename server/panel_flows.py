"""FLOWS panel: FII/DII cash flows and participant-wise index positioning."""

MARKUP = """
  <section class="panel a-wide an" id="p-flows" aria-label="FII DII flows">
    <div class="panel-hd"><span class="k">FLOW</span><span class="s">FII / DII FLOWS · PARTICIPANT POSITIONING (NSE)</span><span class="r"><span class="an-state" id="fl-state">—</span></span></div>
    <div class="an-top"><span class="seg" id="fl-days"><button type="button" data-d="20" class="on">20 SESSIONS</button><button type="button" data-d="40">40</button><button type="button" data-d="60">60</button></span><span class="an-note" id="fl-note">cash flows in ₹ crore · positions in contracts, net = long − short</span></div>
    <div class="an-kpi" id="fl-kpi"></div>
    <div class="an-split"><div class="an-cvw"><canvas class="an-cv" id="fl-cv1"></canvas></div><div class="an-cvw"><canvas class="an-cv" id="fl-cv2"></canvas></div></div>
    <div class="scroll an-tbl-wrap" style="border-left:0;border-top:1px solid var(--line);max-height:220px"><table class="an-table"><thead><tr><th>DATE</th><th>FII CASH</th><th>DII CASH</th><th>FII IDX FUT NET</th><th>Δ</th><th>FII CALLS NET</th><th>FII PUTS NET</th><th>PRO IDX FUT</th><th>CLIENT IDX FUT</th><th>DII IDX FUT</th></tr></thead><tbody id="fl-rows"></tbody></table></div>
    <div class="an-foot">FII/DII cash from NSE's daily report (₹ crore, net buy positive). Positions from NSE's participant-wise open interest file: contracts held by FII, DII, proprietary desks and clients in index futures and options. Updated each evening after NSE publishes; history accumulates from the day the panel went live.</div>
  </section>
"""

JS = r"""
(function(){
  var panel=document.getElementById('p-flows'); if(!panel) return;
  var $=function(id){ return document.getElementById(id); };
  function css(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#fff'; }
  var C={gold:css('--gold'),cyan:css('--cyan'),up:css('--up'),down:css('--down'),faint:css('--faint'),text:css('--text'),mag:'#ff5fd2'};
  function nf(x,d){ if(x==null||isNaN(x)) return '—'; return Number(x).toLocaleString('en-IN',{minimumFractionDigits:d||0,maximumFractionDigits:d||0}); }
  function sgn(x,d){ if(x==null) return '—'; return (x>0?'+':'')+nf(x,d); }
  function ctx2d(cv){ var r=cv.getBoundingClientRect(), dpr=window.devicePixelRatio||1; var w=Math.max(200,Math.floor(r.width)), h=Math.max(120,Math.floor(r.height)); if(cv.width!==Math.floor(w*dpr)||cv.height!==Math.floor(h*dpr)){ cv.width=Math.floor(w*dpr); cv.height=Math.floor(h*dpr); } var c=cv.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0); c.clearRect(0,0,w,h); c.font='10px IBM Plex Mono, monospace'; return {c:c,w:w,h:h}; }
  var st={days:20,data:null};
  panel.querySelector('#fl-days').addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; Array.prototype.forEach.call(this.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); st.days=Number(b.getAttribute('data-d')); load(); });
  function load(){ if(panel.hidden||document.hidden) return; fetch('/api/flows?days='+st.days,{credentials:'same-origin'}).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){ var s=$('fl-state'); if(x.s>=400){ s.textContent=(x.j&&x.j.error)||('HTTP '+x.s); s.className='an-state err'; return; } st.data=x.j; var d=x.j; var lp=d.latest, lc=d.latest_cash;
      s.textContent=(lp?'POSITIONS '+lp.date:'no positions yet')+(lc?' · CASH '+lc.date:''); s.className='an-state ok';
      var fii=lp&&lp.fii||{}, pro=lp&&lp.pro||{}, cli=lp&&lp.client||{}, dii=lp&&lp.dii||{};
      var k=[['FII cash (₹ cr)',lc?sgn(lc.fii_net,0):'—',lc&&lc.fii_net>=0?'up':'down'],['DII cash (₹ cr)',lc?sgn(lc.dii_net,0):'—',lc&&lc.dii_net>=0?'up':'down'],
             ['FII index futures net',sgn(fii.fut_idx_net),fii.fut_idx_net>=0?'up':'down'],['Δ vs prev day',sgn(fii.fut_idx_net_chg),fii.fut_idx_net_chg>=0?'up':'down'],
             ['FII index calls net',sgn(fii.call_net),'m'],['FII index puts net',sgn(fii.put_net),'m'],['Pro index futures net',sgn(pro.fut_idx_net),pro.fut_idx_net>=0?'up':'down'],['Client index futures net',sgn(cli.fut_idx_net),cli.fut_idx_net>=0?'up':'down'],['DII index futures net',sgn(dii.fut_idx_net),'m']];
      $('fl-kpi').innerHTML=k.map(function(x){ return '<div><small>'+x[0]+'</small><b class="'+x[2]+'">'+x[1]+'</b></div>'; }).join('');
      var pos=d.positions||[]; var byd={}; (d.cash||[]).forEach(function(r){ byd[r.date]=r; });
      $('fl-rows').innerHTML=pos.slice().reverse().slice(0,20).map(function(r){ var c=byd[r.date]||{}; var f=r.fii||{}, p=r.pro||{}, cl=r.client||{}, di=r.dii||{}; return '<tr><td>'+r.date+'</td><td class="'+(c.fii_net>=0?'up':'down')+'">'+(c.fii_net!=null?sgn(c.fii_net,0):'—')+'</td><td class="'+(c.dii_net>=0?'up':'down')+'">'+(c.dii_net!=null?sgn(c.dii_net,0):'—')+'</td><td class="'+(f.fut_idx_net>=0?'up':'down')+'">'+sgn(f.fut_idx_net)+'</td><td>'+sgn(f.fut_idx_net_chg)+'</td><td>'+sgn(f.call_net)+'</td><td>'+sgn(f.put_net)+'</td><td>'+sgn(p.fut_idx_net)+'</td><td>'+sgn(cl.fut_idx_net)+'</td><td>'+sgn(di.fut_idx_net)+'</td></tr>'; }).join('');
      draw(); }).catch(function(){ var s=$('fl-state'); s.textContent='network'; s.className='an-state err'; }); }
  function bars(cv,rows,keyA,keyB,labelA,labelB,cumKey){ var g=ctx2d(cv), c=g.c, pad={l:56,r:10,t:16,b:20}; if(!rows.length){ c.fillStyle=C.faint; c.fillText('no data yet',pad.l,30); return; }
    var vals=[]; rows.forEach(function(r){ vals.push(r[keyA]||0); vals.push(r[keyB]||0); }); var m=Math.max.apply(null,vals.map(Math.abs))||1; var n=rows.length, bw=Math.min(44,(g.w-pad.l-pad.r)/n); var mid=pad.t+(g.h-pad.t-pad.b)/2, half=(g.h-pad.t-pad.b)/2;
    var X=function(i){ return pad.l+bw*(i+.5); }, Y=function(v){ return mid-v/m*half*.9; };
    c.strokeStyle='rgba(190,150,255,.14)'; c.beginPath(); c.moveTo(pad.l,mid); c.lineTo(g.w-pad.r,mid); c.stroke();
    rows.forEach(function(r,i){ var a=r[keyA]||0, b=r[keyB]||0; c.fillStyle=a>=0?'rgba(72,232,150,.85)':'rgba(255,92,120,.85)'; c.fillRect(X(i)-bw*.42,Math.min(Y(a),mid),bw*.4,Math.abs(mid-Y(a))); c.fillStyle=b>=0?'rgba(70,225,255,.75)':'rgba(255,95,210,.75)'; c.fillRect(X(i)+bw*.02,Math.min(Y(b),mid),bw*.4,Math.abs(mid-Y(b))); });
    if(cumKey){ var cv2=rows.map(function(r){ return r[cumKey]||0; }); var cm=Math.max.apply(null,cv2.map(Math.abs))||1; c.strokeStyle=C.gold; c.lineWidth=1.6; c.beginPath(); cv2.forEach(function(v,i){ var y=mid-v/cm*half*.9; i?c.lineTo(X(i),y):c.moveTo(X(i),y); }); c.stroke(); c.fillStyle=C.gold; c.textAlign='left'; c.fillText('cumulative FII',pad.l+6,pad.t-4); }
    c.fillStyle=C.faint; c.textAlign='right'; c.fillText('+'+nf(m),pad.l-4,pad.t+8); c.fillText('−'+nf(m),pad.l-4,g.h-pad.b-2); c.textAlign='center'; var every=Math.max(1,Math.round(n/6)); rows.forEach(function(r,i){ if(i%every===0) c.fillText(r.date.slice(5),X(i),g.h-6); });
    c.textAlign='left'; c.fillStyle='rgba(72,232,150,.9)'; c.fillText(labelA,pad.l+120,pad.t-4); c.fillStyle='rgba(70,225,255,.9)'; c.fillText(labelB,pad.l+200,pad.t-4); }
  function lines(cv,rows){ var g=ctx2d(cv), c=g.c, pad={l:56,r:10,t:16,b:20}; if(!rows.length){ c.fillStyle=C.faint; c.fillText('no positions yet',pad.l,30); return; }
    var ser=[['fii',C.gold,'FII'],['pro',C.cyan,'PRO'],['client',C.mag,'CLIENT'],['dii','rgba(200,180,255,.8)','DII']]; var vals=[]; rows.forEach(function(r){ ser.forEach(function(s){ if(r[s[0]]) vals.push(r[s[0]].fut_idx_net); }); }); var lo=Math.min.apply(null,vals), hi=Math.max.apply(null,vals); var m=(hi-lo)*.08||1; lo-=m; hi+=m;
    var n=rows.length; var X=function(i){ return pad.l+(n>1?i/(n-1):0)*(g.w-pad.l-pad.r); }, Y=function(v){ return g.h-pad.b-(v-lo)/(hi-lo)*(g.h-pad.t-pad.b); };
    c.strokeStyle='rgba(190,150,255,.14)'; c.beginPath(); c.moveTo(pad.l,pad.t); c.lineTo(pad.l,g.h-pad.b); c.lineTo(g.w-pad.r,g.h-pad.b); c.stroke(); if(lo<0&&hi>0){ c.strokeStyle='rgba(255,255,255,.18)'; c.beginPath(); c.moveTo(pad.l,Y(0)); c.lineTo(g.w-pad.r,Y(0)); c.stroke(); }
    c.fillStyle=C.faint; c.textAlign='right'; for(var i=0;i<=4;i++){ var v=lo+(hi-lo)*i/4; c.fillText(nf(v),pad.l-4,Y(v)+3); }
    ser.forEach(function(s,si){ c.strokeStyle=s[1]; c.lineWidth=s[0]==='fii'?2:1.3; c.beginPath(); var started=false; rows.forEach(function(r,i){ if(!r[s[0]]) return; var y=Y(r[s[0]].fut_idx_net); started?c.lineTo(X(i),y):c.moveTo(X(i),y); started=true; }); c.stroke(); c.fillStyle=s[1]; c.textAlign='left'; c.fillText(s[2],pad.l+6+si*60,pad.t-4); });
    c.textAlign='center'; c.fillStyle=C.faint; var every=Math.max(1,Math.round(n/6)); rows.forEach(function(r,i){ if(i%every===0) c.fillText(r.date.slice(5),X(i),g.h-6); }); c.textAlign='left'; c.fillStyle=C.text; c.fillText('index futures net (contracts)',g.w-pad.r-170,pad.t-4); }
  function draw(){ var d=st.data; if(!d) return; bars($('fl-cv1'),d.cash||[],'fii_net','dii_net','FII cash','DII cash','fii_cum'); lines($('fl-cv2'),d.positions||[]); }
  load(); setInterval(load,10*60*1000); window.addEventListener('resize',draw); document.addEventListener('visibilitychange',function(){ if(!document.hidden) load(); });
})();
"""
