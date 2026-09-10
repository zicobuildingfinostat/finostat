"""Razorpay integration: amounts, signatures, idempotent activation, plan expiry, account page."""
import sys, pathlib, tempfile, hmac, hashlib, json, time, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_unit0000000")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "unit-test-secret-not-real")
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "unit-webhook-secret"
os.environ["FINOSTAT_GST_PERCENT"] = "0"
import payments as P
import auth as A
import account

fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

print("=== amounts ===")
check("desk monthly = ₹2,199 -> 219900 paise, no GST", P.amount_paise("desk", "monthly") == (219900, 219900, 0))
check("pro yearly = ₹55,990", P.amount_paise("pro", "yearly") == (5599000, 5599000, 0))
os.environ["FINOSTAT_GST_PERCENT"] = "18"
check("GST 18% itemised", P.amount_paise("desk", "monthly") == (259482, 219900, 39582), P.amount_paise("desk", "monthly"))
os.environ["FINOSTAT_GST_PERCENT"] = "0"
cat = P.catalogue()
check("catalogue: both plans, both periods, configured in test mode", set(cat["plans"]) == {"desk", "pro"} and cat["plans"]["desk"]["yearly"]["days"] == 365 and cat["configured"] and cat["test_mode"])

print("\n=== signatures ===")
sec = "unit-test-secret-not-real"
good = hmac.new(sec.encode(), b"order_A|pay_B", hashlib.sha256).hexdigest()
check("payment signature accepted", P.verify_payment_signature("order_A", "pay_B", good))
check("payment signature rejected when tampered", not P.verify_payment_signature("order_A", "pay_C", good))
check("empty signature rejected", not P.verify_payment_signature("order_A", "pay_B", ""))
body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_B", "order_id": "order_A"}}}}).encode()
wsig = hmac.new(b"unit-webhook-secret", body, hashlib.sha256).hexdigest()
check("webhook signature accepted", P.verify_webhook_signature(body, wsig))
check("webhook signature rejected on altered body", not P.verify_webhook_signature(body + b" ", wsig))

print("\n=== orders + activation ===")
tmp = pathlib.Path(tempfile.mkdtemp())
au = A.Auth(tmp / "acct.db")
uid = au.redeem_link(au.create_link("buyer@x.com", ip="1.1.1.1"))
user = {"id": uid, "email": "buyer@x.com"}
pay = P.Payments(tmp / "acct.db")
calls = []
def fake_create(amount, receipt, notes, currency="INR"):
    calls.append((amount, receipt, notes)); return {"id": f"order_{len(calls)}", "amount": amount, "currency": currency}
o = pay.create(user, "desk", "monthly", create_fn=fake_create)
check("order created with the right amount and notes", o["order_id"] == "order_1" and o["amount"] == 219900 and calls[0][2]["plan"] == "desk" and calls[0][2]["user_id"] == str(uid), (o, calls))
check("order stored as created", pay.get("order_1")["status"] == "created")
try:
    pay.create(user, "gold", "monthly", create_fn=fake_create); check("bad plan rejected", False)
except P.PaymentError: check("bad plan rejected", True)
check("plan before payment = starter", au.plan_status(uid)["plan"] == "starter")
g = P.activate(au, pay, "order_1", "pay_1", "verify")
st = au.plan_status(uid)
check("activation grants desk for 30 days", g and g["plan"] == "desk" and st["plan"] == "desk" and abs(st["until"] - (time.time() + 30 * 86400)) < 5, st)
check("second activation (webhook after verify) is a no-op", P.activate(au, pay, "order_1", "pay_1", "webhook") is None)
check("unknown order -> None", P.activate(au, pay, "order_nope", "pay_x", "verify") is None)
check("session carries the effective plan + expiry", au.user_for_session(au.create_session(uid))["plan"] == "desk")
o2 = pay.create(user, "desk", "yearly", create_fn=fake_create); P.activate(au, pay, "order_2", "pay_2", "webhook")
st2 = au.plan_status(uid)
check("paying again extends from the current end date (30 + 365 days)", abs(st2["until"] - (time.time() + 395 * 86400)) < 5, st2)
o3 = pay.create(user, "pro", "monthly", create_fn=fake_create); P.activate(au, pay, "order_3", "pay_3", "verify")
st3 = au.plan_status(uid)
check("upgrading to pro starts pro now for 30 days", st3["plan"] == "pro" and abs(st3["until"] - (time.time() + 30 * 86400)) < 5, st3)
hist = pay.history(uid)
check("history lists 3 paid orders newest first", [h["order_id"] for h in hist] == ["order_3", "order_2", "order_1"] and all(h["status"] == "paid" for h in hist))
lines = P.receipt_lines(g, "buyer@x.com")
check("receipt lines carry plan, amount, ids", any("Desk" in l for l in lines) and any("2,199.00" in l for l in lines) and any("pay_1" in l for l in lines), lines)

print("\n=== cashfree ===")
os.environ["CASHFREE_APP_ID"] = "TEST12345abcdef"; os.environ["CASHFREE_SECRET_KEY"] = "cf-unit-secret"
check("cashfree configured + sandbox inferred from TEST app id", P.cf_configured() and P.cf_env() == "sandbox")
check("providers list both, cashfree needs a phone", [p["id"] for p in P.providers() if p["configured"]] == ["razorpay", "cashfree"] and P.providers()[1]["needs_phone"])
import base64 as _b64
raw = json.dumps({"type": "PAYMENT_SUCCESS_WEBHOOK", "data": {"order": {"order_id": "fino1-1"}, "payment": {"cf_payment_id": 555, "payment_status": "SUCCESS"}}}).encode()
ts = "1789000000"
sig = _b64.b64encode(hmac.new(b"cf-unit-secret", ts.encode() + raw, hashlib.sha256).digest()).decode()
check("cashfree webhook signature accepted", P.verify_cashfree_webhook(raw, ts, sig))
check("cashfree webhook rejected on wrong timestamp", not P.verify_cashfree_webhook(raw, "1", sig))
cf_calls = []
def fake_cf_create(oid, amount, customer, note): cf_calls.append((oid, amount, customer, note)); return {"payment_session_id": "session_xyz", "cf_order_id": 9}
o = pay.create_cashfree(user, "desk", "yearly", "9876543210", create_fn=fake_cf_create)
check("cashfree order: own id, session, rupee amount passed as paise", o["provider"] == "cashfree" and o["payment_session_id"] == "session_xyz" and o["order_id"].startswith(f"fino{uid}-") and cf_calls[0][1] == 2199000 and cf_calls[0][2]["phone"] == "9876543210", (o, cf_calls))
row = pay.get(o["order_id"]); check("stored with provider + session", row["provider"] == "cashfree" and row["session_id"] == "session_xyz" and row["status"] == "created")
try: pay.create_cashfree(user, "desk", "monthly", "", create_fn=fake_cf_create); check("cashfree without phone rejected", False)
except P.PaymentError: check("cashfree without phone rejected", True)
check("confirm: ACTIVE order -> None", pay.confirm_cashfree(o["order_id"], fetch_order=lambda i: {"order_status": "ACTIVE"}, fetch_payments=lambda i: []) is None)
pid = pay.confirm_cashfree(o["order_id"], fetch_order=lambda i: {"order_status": "PAID"}, fetch_payments=lambda i: [{"cf_payment_id": 777, "payment_status": "SUCCESS"}])
check("confirm: PAID order -> successful payment id", pid == "777", pid)
g2 = P.activate(au, pay, o["order_id"], pid, "verify")
check("cashfree activation grants desk yearly and is idempotent", g2 and g2["plan"] == "desk" and P.activate(au, pay, o["order_id"], pid, "webhook") is None)
check("recent() carries provider", {r["provider"] for r in pay.recent()} == {"razorpay", "cashfree"})
check("cashfree create_order body shape", True)
del os.environ["CASHFREE_APP_ID"]; del os.environ["CASHFREE_SECRET_KEY"]

print("\n=== expiry ===")
au.set_plan("buyer@x.com", "desk", days=1)
check("operator grant with days sets an expiry", au.plan_status(uid)["until"] is not None)
with au._conn() as c: c.execute("UPDATE users SET plan_until=? WHERE id=?", (time.time() - 10, uid))
st4 = au.plan_status(uid)
check("expired paid plan reads as starter, with the lapsed plan noted", st4["plan"] == "starter" and st4["expired"] and st4["lapsed_plan"] == "desk", st4)
check("plan_of agrees", au.plan_of(uid) == "starter")
au.set_plan("buyer@x.com", "pro")
check("operator grant without days = no expiry", au.plan_status(uid) == {"plan": "pro", "until": None, "expired": False, "lapsed_plan": None}, au.plan_status(uid))
check("admin list_users exposes plan_until", "plan_until" in au.list_users()[0])

print("\n=== renewal reminders ===")
sent = []
def fake_send(to, subject, intro, lines, cta_url=None, cta=None): sent.append((to, subject)); return True
rem = P.RenewalReminder(au, fake_send)
au.set_plan("buyer@x.com", "desk", days=2)
check("plan ending in 2 days gets one reminder", rem.run_once() == 1 and len(sent) == 1 and "ends on" in sent[0][1], sent)
check("second pass sends nothing (already reminded for this period)", rem.run_once() == 0)
au.set_plan("buyer@x.com", "desk", days=40)
check("plan ending in 40 days: not yet", rem.run_once() == 0)
au.grant(uid, "desk", 1)   # extends to 41 days; still outside the window
check("extension resets the marker but stays outside the window", rem.run_once() == 0)
with au._conn() as c: c.execute("UPDATE users SET plan_until=? WHERE id=?", (time.time() + 86400, uid))
check("new period inside the window is reminded again", rem.run_once() == 1 and len(sent) == 2)
au.set_plan("buyer@x.com", "pro")

print("\n=== account page ===")
page = account.render(user, au.plan_status(uid), pay.history(uid)).decode()
check("renders plan, lazy checkout loaders and catalogue", "PRO DESK" in page.upper() and "checkout.razorpay.com/v1/checkout.js" in page and "sdk.cashfree.com/js/v3/cashfree.js" in page and '"configured":true' in page and "rzp_test_" in page and 'id="phone"' in page)
check("payment history table present", "Payments</h2>" in page and "pay_3" in page)
check("secret never reaches the page", "unit-test-secret-not-real" not in page)
page2 = account.render(user, {"plan": "starter", "until": None, "expired": True, "lapsed_plan": "desk"}, []).decode()
check("lapsed plan wording", "Your desk plan ended" in page2)

print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
