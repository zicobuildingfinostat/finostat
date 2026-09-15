"""Guest checkout: pay with a mobile number; the account comes with the payment.

People were dropping off at the email magic link. Now the plan buttons land here: pick a plan,
enter a mobile number (Cashfree needs it anyway), pay by UPI/card/net banking. The server
creates or finds the account for that number, activates the plan when Cashfree confirms, and —
for accounts created this way — signs the buyer in on this device immediately. Accounts that
already have a real email are activated too, and get their sign-in link by email.
"""
from __future__ import annotations

import account
import payments as pm

_CSS = r"""
.gc{max-width:560px;margin:0 auto}.gc h1{font-family:var(--display);font-size:38px;text-transform:uppercase;line-height:1;margin:0 0 6px}
.gc .lede{color:var(--muted);margin:0 0 18px}
.gc .plans{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 14px}.gc .pl{border:1px solid var(--line-strong);padding:12px 14px;cursor:pointer;background:var(--panel)}.gc .pl.on{border-color:var(--gold);box-shadow:0 0 0 1px var(--gold) inset}
.gc .pl b{font-family:var(--display);font-size:20px;text-transform:uppercase;display:block}.gc .pl .px{font-family:var(--display);font-size:26px;color:var(--gold)}.gc .pl small{display:block;color:var(--faint);font-family:var(--mono);font-size:10.5px;margin-top:2px}
.gc .cyc{display:flex;gap:6px;margin:0 0 14px;font-family:var(--mono);font-size:11px}.gc .cyc button{border:1px solid var(--line-strong);background:none;color:var(--muted);padding:6px 12px;cursor:pointer}.gc .cyc button.on{background:var(--gold);color:#2a1a02;border-color:var(--gold);font-weight:600}
.gc label{display:block;font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;color:var(--faint);margin:10px 0 4px}.gc input{width:100%;background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:16px;padding:10px 12px;box-sizing:border-box}
.gc .pay{margin-top:16px;width:100%;padding:14px;background:var(--gold);color:#2a1a02;border:0;font-family:var(--mono);font-size:13px;letter-spacing:.12em;font-weight:700;cursor:pointer}.gc .pay:disabled{opacity:.5}
.gc .msg{margin-top:12px;padding:10px 12px;border:1px solid var(--line-strong);font-size:14px}.gc .msg.bad{border-color:var(--down)}.gc .msg.ok{border-color:var(--up)}
.gc .fine{color:var(--faint);font-size:12px;margin-top:14px;line-height:1.5}.gc .fine a{color:var(--cyan)}
.gc .total{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:8px}.gc .total b{color:var(--text)}
"""

_JS = r"""
(function(){
  var plan=__PLAN__, period=__PERIOD__, NAMES={desk:'Desk',pro:'Pro desk',sovereign:'XAU Sovereign',vip:'VIP Indicator'};
  var $=function(id){ return document.getElementById(id); }; var msg=$('gc-msg');
  function show(k,t){ msg.hidden=false; msg.className='msg '+k; msg.textContent=t; }
  function total(){ var card=document.querySelector('.pl[data-plan="'+plan+'"] .px'); if(!card) return; var amt=period==='monthly'?card.getAttribute('data-m'):card.getAttribute('data-y'); $('gc-total').innerHTML='You pay <b>₹'+amt+'</b> '+(period==='lifetime'?'once for '+NAMES[plan]+' · lifetime access':'for '+NAMES[plan]+' · '+(period==='monthly'?'30 days':'365 days'));
    Array.prototype.forEach.call(document.querySelectorAll('.pl'),function(el){ var px=el.querySelector('.px'); px.textContent='₹'+(period==='monthly'?px.getAttribute('data-m'):px.getAttribute('data-y')); var sm=el.querySelector('small'); sm.textContent=sm.textContent.replace(/^per (month|year)/, period==='monthly'?'per month':'per year'); }); }
  $('gc-plans').addEventListener('click',function(e){ var el=e.target.closest('.pl'); if(!el) return; plan=el.getAttribute('data-plan'); Array.prototype.forEach.call(document.querySelectorAll('.pl'),function(x){ x.classList.toggle('on',x===el); }); total(); });
  if($('gc-cyc')) $('gc-cyc').addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; period=b.getAttribute('data-p'); Array.prototype.forEach.call(this.querySelectorAll('button'),function(x){ x.classList.toggle('on',x===b); }); total(); });
  total();
  function loadScript(src,cb){ if(window.Cashfree) return cb(); var s=document.createElement('script'); s.src=src; s.onload=cb; s.onerror=function(){ show('bad','Cashfree checkout failed to load'); $('gc-pay').disabled=false; }; document.head.appendChild(s); }
  function post(url,body,cb){ fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify(body),credentials:'same-origin'}).then(function(r){ return r.json().then(function(j){ return {s:r.status,j:j}; }); }).then(function(x){ cb(x.s,x.j); }).catch(function(){ cb(0,{error:'network'}); }); }
  function settle(orderId,tries){ tries=tries||0; post('/api/pay/guest/verify',{order_id:orderId},function(s,j){
    if(s===200&&j.ok){ if(j.signed_in){ show('ok',period==='lifetime'?'Payment received — opening '+NAMES[plan]+'…':'Payment received — opening your terminal…'); location.href=j.next||'/dashboard'; } else { show('ok',j.message||'Payment received. Check your inbox for the sign-in link.'); } return; }
    if(j.pending&&tries<6){ show('ok','Waiting for Cashfree to confirm…'); setTimeout(function(){ settle(orderId,tries+1); },3000); return; }
    show('bad',j.error||'Could not confirm the payment yet. If money left your account it activates automatically; write to hello@finostat.com with your mobile number.'); $('gc-pay').disabled=false; }); }
  $('gc-pay').addEventListener('click',function(){ var phone=$('gc-phone').value.trim(), email=$('gc-email').value.trim(); var d=phone.replace(/\D/g,''); if(d.length===12&&d.slice(0,2)==='91') d=d.slice(2); if(!(d.length===10&&/[6-9]/.test(d[0]))){ show('bad','Enter a 10-digit Indian mobile number.'); $('gc-phone').focus(); return; }
    var b=this; b.disabled=true; show('ok','Creating your order…');
    post('/api/pay/guest',{plan:plan,period:period,phone:d,email:email},function(s,o){ if(s!==200){ show('bad',o.error||('HTTP '+s)); b.disabled=false; return; }
      loadScript('https://sdk.cashfree.com/js/v3/cashfree.js',function(){ if(!window.Cashfree){ show('bad','Cashfree checkout failed to load'); b.disabled=false; return; } var cf=window.Cashfree({mode:o.env==='sandbox'?'sandbox':'production'}); cf.checkout({paymentSessionId:o.payment_session_id, redirectTarget:'_modal'}).then(function(){ settle(o.order_id); }).catch(function(){ show('bad','Cashfree checkout error'); b.disabled=false; }); }); }); });
})();
"""


def render(plan: str, period: str, notice: str | None = None, configured: bool = True) -> bytes:
    cat = pm.catalogue()
    product = plan in pm.PRODUCTS
    plan = plan if plan in ("desk", "pro") or plan in pm.PRODUCTS else "desk"
    period = "lifetime" if product else (period if period in ("monthly", "yearly") else "monthly")
    names = {"desk": "Desk", "pro": "Pro desk", "sovereign": "XAU Sovereign", "vip": "VIP Indicator"}
    blurbs = {"sovereign": "one-time · lifetime · XAU/USD buy·sell engine: live web app + TradingView Pine Script", "vip": "one-time · lifetime · NIFTY, BANKNIFTY & F&O stocks buy·sell engine: live web app + TradingView Pine Script"}
    blurb = {"desk": "live terminal, chains, builder, alerts, analytics", "pro": "everything in Desk + stock chains, replay, backtests, algos"}
    cards = []
    for p in ("desk", "pro"):
        m, y = int(cat["plans"][p]["monthly"]["rupees"]), int(cat["plans"][p]["yearly"]["rupees"])
        cards.append(f'<div class="pl{" on" if p == plan else ""}" data-plan="{p}" role="button" tabindex="0"><b>{names[p]}</b>'
                     f'<span class="px" data-m="{m:,}" data-y="{y:,}">₹{(m if period == "monthly" else y):,}</span>'
                     f'<small>{"per month" if period == "monthly" else "per year"} · {blurb[p]}</small></div>')
    if product:
        rupees = int(cat["products"][plan]["rupees"])
        cards = [f'<div class="pl on" data-plan="{plan}" role="button" tabindex="0" style="grid-column:1/-1"><b>{names[plan]}</b><span class="px" data-m="{rupees:,}" data-y="{rupees:,}">₹{rupees:,}</span>'
                 f'<small>{blurbs[plan]}</small></div>']
    notice_html = f'<div class="msg ok">{account._esc(notice)}</div>' if notice else ""
    cyc = ("" if product else
           f'<div class="cyc" id="gc-cyc"><button type="button" data-p="monthly"{" class=on" if period == "monthly" else ""}>MONTHLY</button>'
           f'<button type="button" data-p="yearly"{" class=on" if period == "yearly" else ""}>YEARLY · 2 MONTHS FREE</button></div>')
    body = (f'<div class="gc"><h1>{"Buy" if product else "Get"} {names[plan]}</h1>'
            '<p class="lede">Pay with UPI, card or net banking through Cashfree. Your account is created from the payment — no email link to wait for.</p>'
            f'{notice_html}<div class="plans" id="gc-plans">{"".join(cards)}</div>{cyc}'
            '<label for="gc-phone">MOBILE NUMBER</label><input id="gc-phone" type="tel" inputmode="numeric" maxlength="14" placeholder="10-digit mobile" autocomplete="tel">'
            '<label for="gc-email">EMAIL (optional — receipts and sign-in on other devices)</label><input id="gc-email" type="email" placeholder="you@example.com" autocomplete="email">'
            '<div class="total" id="gc-total"></div>'
            f'<button class="pay" id="gc-pay" type="button"{"" if configured else " disabled"}>{"PAY WITH CASHFREE →" if configured else "PAYMENTS OPENING SOON"}</button>'
            '<div class="msg" id="gc-msg" hidden></div>'
            '<p class="fine">Prices in INR, exclusive of GST. Active the moment the payment clears; the terminal opens on this device straight after. '
            'Already a member with an email? <a href="/login?next=%2Faccount">Sign in with your email link</a>. <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/contact">Help</a></p></div>'
            "<script>" + _JS.replace("__PLAN__", repr(plan)).replace("__PERIOD__", repr(period)) + "</script>")
    head, _, _tail = account._PAGE.partition("<main")
    doc = (head.replace("__CSS__", account._CSS + _CSS).replace("Your account — Finostat", f"Get {names[plan]} — pay with your mobile number | Finostat")
           + '<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · ' + ('<a href="' + ('/vip-indicator' if plan == 'vip' else '/xau-sovereign') + '">' + names[plan].upper() + '</a> · BUY' if product else 'GET ' + names[plan].upper()) + "</nav>" + body + "</main></body></html>")
    return doc.encode("utf-8")
