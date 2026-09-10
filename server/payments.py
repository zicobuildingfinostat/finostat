"""Razorpay Standard Checkout for the Desk and Pro plans. Standard library only.

Flow: the account page asks the server for an order (POST /api/pay/order);
Razorpay's hosted checkout collects the payment; the browser posts the
order/payment ids and signature to /api/pay/verify, which checks the HMAC and
activates the plan for the period bought. Razorpay's webhook (payment.captured
/ order.paid) does the same activation independently, so a closed tab never
loses a paid order. Activation is idempotent on order_id.

No card data ever touches this server. Keys come from the environment:
RAZORPAY_KEY_ID (public, goes to the browser), RAZORPAY_KEY_SECRET,
RAZORPAY_WEBHOOK_SECRET. Prices are rupees per period; FINOSTAT_GST_PERCENT
(default 0) is added on top and itemised.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import pathlib
import sqlite3
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("finostat.payments")

API = "https://api.razorpay.com/v1"
PRICES = {"desk": {"monthly": 1499, "yearly": 14990}, "pro": {"monthly": 3499, "yearly": 34990}}   # rupees
DAYS = {"monthly": 30, "yearly": 365}
LABEL = {"desk": "Desk", "pro": "Pro desk"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS payments(
  id          INTEGER PRIMARY KEY,
  user_id     INTEGER NOT NULL,
  plan        TEXT NOT NULL,
  period      TEXT NOT NULL,
  amount      INTEGER NOT NULL,          -- paise, GST included
  base        INTEGER NOT NULL,          -- paise before GST
  gst         INTEGER NOT NULL,
  currency    TEXT NOT NULL DEFAULT 'INR',
  order_id    TEXT NOT NULL UNIQUE,
  payment_id  TEXT,
  status      TEXT NOT NULL DEFAULT 'created',   -- created | paid
  source      TEXT,                              -- verify | webhook
  receipt     TEXT,
  created     REAL NOT NULL,
  paid_at     REAL
);
CREATE INDEX IF NOT EXISTS payments_user ON payments(user_id, created);
"""


def key_id() -> str:
    return os.environ.get("RAZORPAY_KEY_ID", "").strip()


def key_secret() -> str:
    return os.environ.get("RAZORPAY_KEY_SECRET", "").strip()


def webhook_secret() -> str:
    return os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()


def configured() -> bool:
    return bool(key_id() and key_secret())


def test_mode() -> bool:
    return key_id().startswith("rzp_test_")


def gst_percent() -> float:
    try:
        return max(0.0, float(os.environ.get("FINOSTAT_GST_PERCENT", "0") or 0))
    except ValueError:
        return 0.0


def amount_paise(plan: str, period: str) -> tuple[int, int, int]:
    """(total, base, gst) in paise."""
    base = PRICES[plan][period] * 100
    gst = int(round(base * gst_percent() / 100.0))
    return base + gst, base, gst


def catalogue() -> dict:
    """What the account page shows: every plan/period with itemised amounts."""
    out = {}
    for plan, periods in PRICES.items():
        out[plan] = {}
        for period in periods:
            total, base, gst = amount_paise(plan, period)
            out[plan][period] = {"rupees": PRICES[plan][period], "total_paise": total, "base_paise": base,
                                 "gst_paise": gst, "days": DAYS[period]}
    return {"plans": out, "gst_percent": gst_percent(), "configured": configured(), "test_mode": test_mode(),
            "key_id": key_id() if configured() else ""}


# ---------------------------------------------------------------------------
# Razorpay REST + signatures
# ---------------------------------------------------------------------------
def _auth_header() -> str:
    return "Basic " + base64.b64encode(f"{key_id()}:{key_secret()}".encode()).decode()


def razorpay_create_order(amount: int, receipt: str, notes: dict, currency: str = "INR") -> dict:
    """POST /v1/orders. Raises PaymentError on any failure."""
    body = json.dumps({"amount": amount, "currency": currency, "receipt": receipt[:40], "notes": notes}).encode()
    req = urllib.request.Request(f"{API}/orders", data=body, method="POST", headers={
        "Authorization": _auth_header(), "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "finostat/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        log.error("razorpay order failed: HTTP %s %s", exc.code, detail)
        raise PaymentError("Razorpay refused the order" + (" (keys rejected)" if exc.code == 401 else "")) from exc
    except (urllib.error.URLError, ValueError, OSError) as exc:
        log.error("razorpay unreachable: %s", exc)
        raise PaymentError("Razorpay is unreachable right now; try again in a minute") from exc


def verify_payment_signature(order_id: str, payment_id: str, signature: str, secret: str | None = None) -> bool:
    """Razorpay signs 'order_id|payment_id' with the key secret (HMAC-SHA256, hex)."""
    secret = key_secret() if secret is None else secret
    if not (secret and order_id and payment_id and signature):
        return False
    expect = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expect, str(signature).strip().lower())


def verify_webhook_signature(body: bytes, signature: str, secret: str | None = None) -> bool:
    """Webhooks are signed over the raw request body with the webhook secret."""
    secret = webhook_secret() if secret is None else secret
    if not (secret and signature):
        return False
    expect = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expect, str(signature).strip().lower())


class PaymentError(Exception):
    pass


# ---------------------------------------------------------------------------
# Storage + activation
# ---------------------------------------------------------------------------
class Payments:
    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self._lock = threading.Lock()
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def create(self, user: dict, plan: str, period: str, create_fn=razorpay_create_order) -> dict:
        """Create the Razorpay order and remember it. Returns what the browser needs."""
        if plan not in PRICES or period not in DAYS:
            raise PaymentError("unknown plan or period")
        total, base, gst = amount_paise(plan, period)
        receipt = f"fino-{user['id']}-{int(time.time())}"
        order = create_fn(total, receipt, {"user_id": str(user["id"]), "email": user["email"], "plan": plan, "period": period})
        oid = order.get("id")
        if not oid:
            raise PaymentError("Razorpay returned no order id")
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO payments(user_id,plan,period,amount,base,gst,currency,order_id,receipt,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (user["id"], plan, period, total, base, gst, "INR", oid, receipt, time.time()))
        return {"order_id": oid, "amount": total, "currency": "INR", "plan": plan, "period": period,
                "label": LABEL[plan], "days": DAYS[period], "key_id": key_id(), "email": user["email"]}

    def get(self, order_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM payments WHERE order_id=?", (order_id,)).fetchone()
        return dict(r) if r else None

    def mark_paid(self, order_id: str, payment_id: str, source: str) -> dict | None:
        """First caller wins; later calls (webhook after verify, or a retry) get None."""
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE payments SET status='paid', payment_id=?, source=?, paid_at=? WHERE order_id=? AND status!='paid'",
                            (payment_id, source, time.time(), order_id))
            if cur.rowcount != 1:
                return None
            r = c.execute("SELECT * FROM payments WHERE order_id=?", (order_id,)).fetchone()
        return dict(r)

    def history(self, user_id: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM payments WHERE user_id=? ORDER BY created DESC LIMIT 50", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def recent(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT p.*, u.email FROM payments p JOIN users u ON u.id=p.user_id ORDER BY p.created DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def activate(auth, payments: Payments, order_id: str, payment_id: str, source: str) -> dict | None:
    """Mark the order paid and grant the plan. Returns the grant, or None if it
    was already activated (idempotent) or the order is unknown."""
    row = payments.mark_paid(order_id, payment_id, source)
    if row is None:
        return None
    until = auth.grant(row["user_id"], row["plan"], DAYS[row["period"]])
    log.info("payment %s activated %s/%s for user %s until %s (via %s)", payment_id, row["plan"], row["period"], row["user_id"],
             time.strftime("%Y-%m-%d", time.gmtime(until)), source)
    return {"user_id": row["user_id"], "plan": row["plan"], "period": row["period"], "amount": row["amount"],
            "base": row["base"], "gst": row["gst"], "until": until, "payment_id": payment_id, "order_id": order_id,
            "receipt": row["receipt"]}


class RenewalReminder:
    """Once an hour: email anyone whose paid plan ends within three days. Each
    period is reminded once (marker in prefs), so an extension resets it."""

    def __init__(self, auth, send, days: float = 3.0, interval: float = 3600.0):
        self.auth, self.send, self.days, self.interval = auth, send, days, interval
        self._stop = threading.Event()
        self.sent = 0

    def start(self) -> None:
        threading.Thread(target=self._run, name="renewals", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def run_once(self) -> int:
        n = 0
        for u in self.auth.expiring(self.days * 86400):
            when = time.strftime("%d %b %Y", time.gmtime(u["until"] + 19800))
            lines = [f"Plan: {LABEL.get(u['plan'], u['plan'])}", f"Ends: {when} (IST)",
                     "Nothing renews by itself. Pay for another 30 or 365 days from your account page and the plan continues from that date.",
                     "If you let it lapse, your account simply returns to Starter — your watchlist, alerts and settings stay."]
            try:
                ok = self.send(u["email"], f"Your Finostat {LABEL.get(u['plan'], u['plan'])} plan ends on {when}",
                               f"A heads-up, three days early: your {LABEL.get(u['plan'], u['plan'])} plan ends on {when}.", lines,
                               "https://finostat.com/account", "Renew from your account →")
            except Exception:
                log.exception("renewal reminder failed for %s", u["email"])
                ok = False
            if ok:
                self.auth.mark_reminded(u["id"], u["until"])
                n += 1
        self.sent += n
        return n

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.run_once()
            except Exception:
                log.exception("renewal reminder pass failed")


def receipt_lines(grant: dict, email: str) -> list[str]:
    rs = lambda p: f"₹{p / 100:,.2f}"
    lines = [f"Plan: {LABEL[grant['plan']]} · {grant['period']} ({DAYS[grant['period']]} days)",
             f"Active until: {time.strftime('%d %b %Y', time.gmtime(grant['until'] + 19800))} (IST)",
             f"Amount: {rs(grant['base'])}" + (f" + GST {rs(grant['gst'])} = {rs(grant['amount'])}" if grant["gst"] else ""),
             f"Payment id: {grant['payment_id']}", f"Order id: {grant['order_id']}", f"Receipt: {grant['receipt']}",
             f"Account: {email}"]
    return lines
