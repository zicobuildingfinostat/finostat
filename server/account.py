"""/account -- plan status, upgrade with Razorpay checkout, payment history."""
from __future__ import annotations

import html
import json
import time

import payments as pm
from finch import _CSS as _BASE_CSS

_CSS = _BASE_CSS + r"""
.acct{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:32px;align-items:start;margin-top:14px}
.status{border:1px solid var(--line-strong);background:var(--panel);padding:16px 18px;margin:0 0 18px}
.status small{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.status b{font-family:var(--display);font-size:34px;font-weight:600;line-height:1;color:var(--gold);text-transform:uppercase}
.status .sub{font-family:var(--mono);font-size:11.5px;color:var(--muted);margin-top:6px}
.toggle{display:inline-flex;border:1px solid var(--line-strong);font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;margin:6px 0 14px}
.toggle button{padding:7px 14px;background:none;border:0;color:var(--muted);cursor:pointer}.toggle button.on{background:var(--gold);color:#2a1a02;font-weight:600}
.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:0 0 18px}
.plan{border:1px solid var(--line-strong);background:var(--panel);padding:16px 18px;display:flex;flex-direction:column}
.plan.best{border-color:var(--gold);box-shadow:0 0 30px rgba(245,200,66,.12)}
.plan h3{font-family:var(--display);font-size:26px;font-weight:600;text-transform:uppercase;margin:0 0 2px;line-height:1}
.plan .price{font-family:var(--display);font-size:30px;color:var(--gold);margin:8px 0 0}.plan .price i{font-style:normal;font-size:13px;color:var(--muted);font-family:var(--mono)}
.plan .gst{font-family:var(--mono);font-size:10.5px;color:var(--faint);margin:2px 0 10px}
.plan ul{list-style:none;margin:0 0 14px;padding:0;font-size:13.5px;color:var(--muted);flex:1}.plan li{padding:3px 0 3px 16px;position:relative}.plan li::before{content:"▸";position:absolute;left:0;color:var(--gold)}
.pay{display:inline-flex;justify-content:center;align-items:center;gap:8px;font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;padding:11px 16px;border:1px solid var(--gold);background:linear-gradient(180deg,var(--gold-2),#f2b830);color:#2a1a02;font-weight:600;cursor:pointer}
.pay:hover{filter:brightness(1.08)}.pay[disabled]{opacity:.5;cursor:wait}.pay.ghost{background:none;color:var(--muted);border-color:var(--line-strong)}
.msg{font-family:var(--mono);font-size:12px;padding:10px 12px;border:1px solid var(--line-strong);margin:0 0 14px}.msg.ok{border-color:var(--up);color:var(--up)}.msg.bad{border-color:var(--down);color:var(--down)}
.hist{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11.5px}.hist th{text-align:left;color:var(--cyan);font-weight:500;font-size:10px;letter-spacing:.1em;padding:6px 8px;border-bottom:1px solid var(--line-strong)}.hist td{padding:6px 8px;border-bottom:1px solid rgba(190,150,255,.1)}
.side{border:1px solid var(--line-strong);background:var(--panel);padding:14px 16px;font-size:13.5px;color:var(--muted)}.side h4{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--cyan);margin:0 0 8px}.side p{margin:0 0 10px}
.side a.cta{margin-top:0}
.phone{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 14px;font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.phone input{background:var(--bg);border:1px solid var(--line-strong);color:var(--text);padding:8px 10px;font:inherit;font-size:14px;width:180px;outline:0}.phone input:focus{border-color:var(--gold)}
.pay.alt{background:none;color:var(--text);border-color:var(--line-strong);margin-top:6px}.pay.alt:hover{border-color:var(--gold);color:var(--gold)}
.testbadge{font-family:var(--mono);font-size:10px;letter-spacing:.12em;color:#2a1a02;background:var(--gold);padding:2px 6px;margin-left:8px;vertical-align:middle}
@media(max-width:860px){.acct{grid-template-columns:1fr}}
"""

_PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your account — Finostat</title><meta name="robots" content="noindex"><meta name="theme-color" content="#0c0626"><link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>__CSS__</style></head><body>
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/dashboard">TERMINAL</a><a href="/brief">BRIEF</a><a href="/finch">FINCH</a><a href="/auth/logout" id="logout">SIGN OUT</a></div></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · ACCOUNT</nav>
<h1>Your account</h1><p class="lede">__EMAIL__</p>
<div class="acct"><div>
<div class="msg" id="msg" hidden></div>
<div class="status"><small>Current plan</small><b>__PLAN__</b><div class="sub">__PLAN_SUB__</div></div>
<h2 style="font-family:var(--display);font-size:24px;text-transform:uppercase;margin:0 0 4px">__UPGRADE_HEAD__</h2>
<div class="toggle" id="period"><button type="button" data-period="monthly" class="on">Monthly</button><button type="button" data-period="yearly">Yearly · save 17%</button></div>
<div class="phone" id="phone" hidden><label for="phone-in">Mobile (needed by Cashfree)</label><input id="phone-in" type="tel" inputmode="numeric" maxlength="14" placeholder="10-digit mobile" value="__PHONE__"></div>
<div class="plans" id="plans"></div>
<p class="disc" style="margin-top:0">__NOTE__</p>
__HISTORY__
</div>
<aside class="side">
<h4>How billing works</h4>
<p>Pay for 30 days or 365 days at a time. Nothing renews by itself — you get an email three days before the period ends and choose whether to continue. Paying again while a plan is running extends it from its current end date.</p>
<p>Payments are processed by Razorpay or Cashfree (UPI, cards, net banking, wallets). Finostat never sees your card or UPI details.</p>
<p>Starter stays free. Cancel simply by not renewing; the plan runs to the end of the paid period.</p>
<a class="cta ghost" href="/contact">Questions → contact</a>
</aside></div>
</main>
<script>window.ACCT=__DATA__;</script>

<script>__JS__</script></body></html>"""

_JS = r"""
(function(){
"use strict";
var A=window.ACCT, plansEl=document.getElementById('plans'), msg=document.getElementById('msg'), period='monthly';
var FEATURES={desk:['All sheets live, under 250 ms','Strategy builder on every F&O stock','Option chain with open interest, PCR, max pain','Server-side alerts, 25 rules, emailed','IV percentile, bell curves, volatility surface'],
              pro:['Everything in Desk','Recorded tick history and replay','Backtesting across past expiries','Unlimited alert rules','Data export and API access','One live session with the desk each quarter']};
var LABEL={desk:'Desk',pro:'Pro desk'};
function rs(p){ return '₹'+(p/100).toLocaleString('en-IN',{minimumFractionDigits:0,maximumFractionDigits:2}); }
function show(kind,text){ msg.className='msg '+kind; msg.textContent=text; msg.hidden=false; msg.scrollIntoView({block:'nearest'}); }
function render(){
  plansEl.innerHTML=['desk','pro'].map(function(plan){
    var p=A.catalogue.plans[plan][period], cur=A.status.plan===plan;
    var provs=A.catalogue.providers||[], btn;
    if(provs.length){ btn=provs.map(function(pv,i){ return '<button type="button" class="pay'+(i?' alt':'')+'" data-plan="'+plan+'" data-provider="'+pv.id+'">'+(cur?'Extend '+LABEL[plan]:'Pay '+rs(p.total_paise)+' · '+LABEL[plan])+(provs.length>1?' via '+pv.name:'')+' →</button>'; }).join(''); }
    else btn='<button type="button" class="pay ghost" data-request="'+plan+'">Request '+LABEL[plan]+' (activated by hand)</button>';
    return '<div class="plan'+(plan==='desk'?' best':'')+'"><h3>'+LABEL[plan]+(cur?' <span class="testbadge">CURRENT</span>':'')+'</h3><div class="price">'+rs(p.base_paise)+'<i> / '+(period==='monthly'?'30 days':'365 days')+'</i></div>'
      +'<div class="gst">'+(p.gst_paise?'+ GST '+A.catalogue.gst_percent+'% = '+rs(p.total_paise):'Exclusive of GST · none charged today · you pay '+rs(p.total_paise))+'</div><ul>'+FEATURES[plan].map(function(f){ return '<li>'+f+'</li>'; }).join('')+'</ul>'+btn+'</div>';
  }).join('');
}
document.getElementById('period').addEventListener('click',function(e){ var b=e.target.closest('button[data-period]'); if(!b) return; period=b.getAttribute('data-period'); Array.prototype.forEach.call(this.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); render(); });
plansEl.addEventListener('click',function(e){
  var b=e.target.closest('button[data-plan]'); var r=e.target.closest('button[data-request]');
  if(r){ r.disabled=true; fetch('/auth/upgrade',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify({plan:r.getAttribute('data-request')})}).then(function(x){ return x.json(); }).then(function(d){ show(d.ok?'ok':'bad', d.ok?'Request sent — you will get an email when it is active.':(d.error||'Could not send')); }).catch(function(){ show('bad','Network error'); }); return; }
  if(!b) return; var plan=b.getAttribute('data-plan'), provider=b.getAttribute('data-provider')||'razorpay'; msg.hidden=true;
  var phoneEl=document.getElementById('phone-in'), phone=phoneEl?phoneEl.value.trim():'';
  if(provider==='cashfree'){ var d=phone.replace(/\D/g,''); if(d.length===12&&d.slice(0,2)==='91') d=d.slice(2); if(!(d.length===10&&/[6-9]/.test(d[0]))){ document.getElementById('phone').hidden=false; phoneEl.focus(); show('bad','Cashfree needs a 10-digit mobile number first.'); return; } }
  b.disabled=true;
  fetch('/api/pay/order',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify({plan:plan,period:period,provider:provider,phone:phone})})
  .then(function(x){ return x.json().then(function(d){ d._ok=x.ok; return d; }); }).then(function(o){
    if(!o._ok){ b.disabled=false; if(o.need_phone){ document.getElementById('phone').hidden=false; phoneEl.focus(); } show('bad',o.error||'Could not create the order'); return; }
    if(o.provider==='cashfree'){ loadScript('https://sdk.cashfree.com/js/v3/cashfree.js',function(){
        if(!window.Cashfree){ b.disabled=false; show('bad','Cashfree checkout failed to load'); return; }
        var cf=window.Cashfree({mode:o.env==='sandbox'?'sandbox':'production'});
        cf.checkout({paymentSessionId:o.payment_session_id, redirectTarget:'_modal'}).then(function(res){
          if(res&&res.error){ b.disabled=false; show('bad','Payment not completed: '+(res.error.message||'cancelled')+'. Nothing was charged.'); return; }
          verifyCF(o.order_id, b);
        }).catch(function(){ b.disabled=false; show('bad','Cashfree checkout error'); });
      }); return; }
    loadScript('https://checkout.razorpay.com/v1/checkout.js',function(){ if(!window.Razorpay){ b.disabled=false; show('bad','Razorpay checkout failed to load'); return; }
    var rz=new Razorpay({key:o.key_id, amount:o.amount, currency:o.currency, name:'Finostat', description:o.label+' · '+o.days+' days', order_id:o.order_id,
      prefill:{email:o.email}, notes:{plan:o.plan,period:o.period}, theme:{color:'#6a35f0'},
      modal:{ondismiss:function(){ b.disabled=false; show('bad','Payment cancelled — nothing was charged.'); }},
      handler:function(res){
        fetch('/api/pay/verify',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify({order_id:res.razorpay_order_id,payment_id:res.razorpay_payment_id,signature:res.razorpay_signature})})
        .then(function(x){ return x.json().then(function(d){ d._ok=x.ok; return d; }); }).then(function(d){
          if(d._ok){ location.href='/account?paid=1'; } else { b.disabled=false; show('bad',d.error||'We could not verify the payment. If money was debited, email zico@finostat.com with the payment id '+res.razorpay_payment_id+'.'); }
        }).catch(function(){ show('bad','Network error after payment — if money was debited, it will still be activated by our webhook within a minute. Refresh.'); });
      }});
    rz.on('payment.failed',function(r){ b.disabled=false; show('bad','Payment failed: '+((r.error&&r.error.description)||'declined')+'. Nothing was charged.'); });
    rz.open(); });
  }).catch(function(){ b.disabled=false; show('bad','Network error'); });
});
function loadScript(src,cb){ var s=document.querySelector('script[src="'+src+'"]'); if(s&&s.getAttribute('data-ok')){ cb(); return; } s=document.createElement('script'); s.src=src; s.async=true; s.onload=function(){ s.setAttribute('data-ok','1'); cb(); }; s.onerror=function(){ cb(); }; document.head.appendChild(s); }
function verifyCF(orderId, b, tries){
  tries=tries||0;
  fetch('/api/pay/verify',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify({order_id:orderId})})
  .then(function(x){ return x.json().then(function(d){ d._ok=x.ok; d._st=x.status; return d; }); }).then(function(d){
    if(d._ok){ location.href='/account?paid=1'; return; }
    if(d.pending&&tries<5){ show('ok','Waiting for Cashfree to confirm…'); setTimeout(function(){ verifyCF(orderId,b,tries+1); },3000); return; }
    if(b) b.disabled=false; show('bad',d.error||'Could not verify the payment');
  }).catch(function(){ if(b) b.disabled=false; show('bad','Network error while verifying — refresh in a minute; a paid order activates automatically.'); });
}
var cfo=(location.search.match(/[?&]cf_order=([A-Za-z0-9_-]+)/)||[])[1]; if(cfo) verifyCF(cfo,null);
if((A.catalogue.providers||[]).some(function(p){ return p.needs_phone; })) document.getElementById('phone').hidden=false;
render();
if(location.search.indexOf('paid=1')>=0) show('ok','Payment received — your plan is active. Thank you.');
var want=(location.search.match(/[?&]plan=(desk|pro)/)||[])[1]; if(want){ var el=plansEl.querySelector('[data-plan="'+want+'"],[data-request="'+want+'"]'); if(el) el.scrollIntoView({block:'center'}); }
})();
"""


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def render(user: dict, status: dict, history: list[dict], phone: str = "") -> bytes:
    cat = pm.catalogue()
    plan = status["plan"]
    label = {"starter": "Starter", "desk": "Desk", "pro": "Pro desk"}[plan]
    if plan == "starter":
        sub = "Free forever. " + (f"Your {status['lapsed_plan']} plan ended; renew below to pick up where you left off." if status.get("lapsed_plan") else "Upgrade for the live feed, every F&O stock in the builder, and server-side alerts.")
        head = "Upgrade"
    else:
        sub = ("Active until " + time.strftime("%d %b %Y", time.gmtime(status["until"] + 19800)) + " · nothing renews automatically") if status.get("until") else "Active · no expiry"
        head = "Extend or change plan"
    rows = "".join(
        f"<tr><td>{time.strftime('%d %b %Y', time.gmtime(r['created'] + 19800))}</td><td>{_esc(pm.LABEL.get(r['plan'], r['plan']))} · {r['period']}</td>"
        f"<td>₹{r['amount'] / 100:,.2f}</td><td>{'paid' if r['status'] == 'paid' else 'not completed'}</td><td>{_esc(r.get('provider', 'razorpay'))} · {_esc(r['payment_id'] or '—')}</td></tr>"
        for r in history)
    hist = (f'<h2 style="font-family:var(--display);font-size:22px;text-transform:uppercase;margin:18px 0 6px">Payments</h2><div class="scrollx"><table class="hist"><thead><tr><th>Date</th><th>Plan</th><th>Amount</th><th>Status</th><th>Payment id</th></tr></thead><tbody>{rows}</tbody></table></div>'
            if history else "")
    note = ("Prices in INR, exclusive of GST" + (f" — {cat['gst_percent']:g}% GST added at checkout" if cat["gst_percent"] else " (none charged today)") +
            ". Secure checkout by " + " or ".join(p["name"] for p in cat["providers"]) + ". " + ("<b style='color:var(--gold)'>TEST MODE — no real money moves.</b> " if cat["test_mode"] else "") +
            "By paying you accept the <a href='/terms'>terms</a>." if cat["configured"] else
            "Online payment is not switched on yet. Requesting a plan sends us an email and we activate it by hand, usually the same day.")
    data = json.dumps({"catalogue": cat, "status": {"plan": plan, "until": status.get("until")}}, separators=(",", ":")).replace("</", "<\\/")
    doc = (_PAGE.replace("__CSS__", _CSS).replace("__EMAIL__", _esc(user["email"])).replace("__PLAN__", label).replace("__PLAN_SUB__", _esc(sub))
           .replace("__UPGRADE_HEAD__", head).replace("__NOTE__", note).replace("__HISTORY__", hist).replace("__DATA__", data).replace("__PHONE__", _esc(phone)).replace("__JS__", _JS))
    return doc.encode("utf-8")
