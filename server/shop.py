"""/shop — Finostat merchandise, sold directly from the site.

Owner (OWNER_EMAIL / trade users) manages products at /shop/admin: name, description, price, compare-at
price, sizes, stock, photos (uploaded as base64 JSON from the browser, stored on the volume under
data/shop/, served at /shop/img/<id>). Visitors browse /shop and /shop/<slug>, keep a cart in the
browser, and check out at /shop/cart with name, phone, email and a shipping address; payment goes
through Cashfree (UPI / cards / net banking). Orders live in sqlite with a status the owner advances
(paid → packed → shipped → delivered) and a tracking line; customers see it at /shop/order/<id>.
Stock is reserved at checkout and decremented on payment. Prices are in rupees, inclusive of GST."""
from __future__ import annotations

import base64
import html
import json
import logging
import pathlib
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger("finostat.shop")
IST = timezone(timedelta(hours=5, minutes=30))
STATUSES = ("created", "paid", "packed", "shipped", "delivered", "cancelled")
IMG_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_IMG = 6 * 1024 * 1024
_SCHEMA = """
CREATE TABLE IF NOT EXISTS shop_products(
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  price INTEGER NOT NULL, compare_price INTEGER, stock INTEGER NOT NULL DEFAULT 0, sizes TEXT NOT NULL DEFAULT '[]',
  images TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS shop_orders(
  id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'created', name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT,
  address TEXT NOT NULL, items TEXT NOT NULL, subtotal INTEGER NOT NULL, shipping INTEGER NOT NULL, amount INTEGER NOT NULL,
  session_id TEXT, payment_id TEXT, tracking TEXT, note TEXT, user_id INTEGER, created REAL NOT NULL, paid_at REAL, updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS shop_orders_created ON shop_orders(created);
CREATE TABLE IF NOT EXISTS shop_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
DEFAULT_SETTINGS = {"shipping_flat": 79, "free_above": 999, "store_name": "Finostat Shop", "tagline": "Desk-grade merchandise for traders", "announce": ""}


def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:60] or "item"


def clean_phone(s: str) -> str | None:
    d = re.sub(r"\D", "", s or "")
    if len(d) == 12 and d.startswith("91"):
        d = d[2:]
    return d if len(d) == 10 and d[0] in "6789" else None


class ShopError(ValueError):
    pass


class Shop:
    def __init__(self, db_path, img_dir, create_order=None, fetch_order=None, fetch_payments=None, public_url: str = "https://finostat.com"):
        self.path = db_path
        self.img_dir = pathlib.Path(img_dir)
        self.img_dir.mkdir(parents=True, exist_ok=True)
        self.create_order, self.fetch_order, self.fetch_payments = create_order, fetch_order, fetch_payments
        self.public_url = public_url
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    # -- settings ----------------------------------------------------------------
    def settings(self) -> dict:
        out = dict(DEFAULT_SETTINGS)
        with self._conn() as c:
            for r in c.execute("SELECT key, value FROM shop_settings"):
                try:
                    out[r["key"]] = json.loads(r["value"])
                except ValueError:
                    pass
        return out

    def set_settings(self, updates: dict) -> dict:
        with self._lock, self._conn() as c:
            for k, v in (updates or {}).items():
                if k in DEFAULT_SETTINGS:
                    if k in ("shipping_flat", "free_above"):
                        v = max(0, int(float(v)))
                    else:
                        v = str(v)[:200]
                    c.execute("INSERT INTO shop_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, json.dumps(v)))
        return self.settings()

    # -- products ----------------------------------------------------------------
    @staticmethod
    def _row(r) -> dict:
        d = dict(r)
        d["sizes"] = json.loads(d["sizes"] or "[]")
        d["images"] = json.loads(d["images"] or "[]")
        return d

    def products(self, active_only: bool = True) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM shop_products" + (" WHERE active=1" if active_only else "") + " ORDER BY sort, created DESC").fetchall()
        return [self._row(r) for r in rows]

    def product(self, slug_or_id) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM shop_products WHERE slug=? OR id=?", (str(slug_or_id), slug_or_id if isinstance(slug_or_id, int) else -1)).fetchone()
        return self._row(r) if r else None

    def save_product(self, data: dict, pid: int | None = None) -> dict:
        name = str(data.get("name", "")).strip()[:120]
        if not name:
            raise ShopError("name required")
        try:
            price = int(round(float(data.get("price", 0))))
            stock = int(data.get("stock", 0))
        except (TypeError, ValueError):
            raise ShopError("price and stock must be numbers")
        if price <= 0 or stock < 0:
            raise ShopError("price must be positive, stock non-negative")
        cp = data.get("compare_price")
        try:
            cp = int(round(float(cp))) if cp not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            cp = None
        sizes = [str(s).strip()[:12] for s in (data.get("sizes") or []) if str(s).strip()][:12]
        images = [str(i) for i in (data.get("images") or []) if re.fullmatch(r"[0-9a-f]{16}\.(jpg|png|webp|svg)", str(i))][:8]
        desc = str(data.get("description", ""))[:4000]
        active = 1 if data.get("active", True) else 0
        sort = int(data.get("sort", 0) or 0)
        now = time.time()
        with self._lock, self._conn() as c:
            if pid is None:
                slug = slugify(name)
                base, n = slug, 2
                while c.execute("SELECT 1 FROM shop_products WHERE slug=?", (slug,)).fetchone():
                    slug = f"{base}-{n}"; n += 1
                cur = c.execute("INSERT INTO shop_products(slug,name,description,price,compare_price,stock,sizes,images,active,sort,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (slug, name, desc, price, cp, stock, json.dumps(sizes), json.dumps(images), active, sort, now, now))
                pid = cur.lastrowid
            else:
                c.execute("UPDATE shop_products SET name=?, description=?, price=?, compare_price=?, stock=?, sizes=?, images=?, active=?, sort=?, updated=? WHERE id=?",
                          (name, desc, price, cp, stock, json.dumps(sizes), json.dumps(images), active, sort, now, pid))
        return self.product(int(pid))

    def delete_product(self, pid: int) -> bool:
        with self._lock, self._conn() as c:
            return c.execute("DELETE FROM shop_products WHERE id=?", (pid,)).rowcount > 0

    # -- images ------------------------------------------------------------------
    def save_image(self, mime: str, data_b64: str) -> str:
        ext = IMG_TYPES.get(mime)
        if not ext:
            raise ShopError("only JPEG, PNG or WebP images")
        try:
            raw = base64.b64decode(data_b64.split(",", 1)[-1], validate=False)
        except Exception:
            raise ShopError("bad image data")
        if not raw or len(raw) > MAX_IMG:
            raise ShopError("image must be under 6 MB")
        magic_ok = (ext == "jpg" and raw[:3] == b"\xff\xd8\xff") or (ext == "png" and raw[:8] == b"\x89PNG\r\n\x1a\n") or (ext == "webp" and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
        if not magic_ok:
            raise ShopError("file does not look like the declared image type")
        name = f"{secrets.token_hex(8)}.{ext}"
        (self.img_dir / name).write_bytes(raw)
        return name

    def image_path(self, name: str) -> pathlib.Path | None:
        if not re.fullmatch(r"[0-9a-f]{16}\.(jpg|png|webp|svg)", name or ""):
            return None
        p = self.img_dir / name
        return p if p.is_file() else None

    # -- cart / checkout -----------------------------------------------------------
    def price_cart(self, items: list) -> dict:
        """Validate cart lines against the catalogue; returns priced lines, subtotal, shipping, total (rupees)."""
        if not isinstance(items, list) or not items or len(items) > 20:
            raise ShopError("cart is empty")
        st = self.settings()
        lines, subtotal = [], 0
        for it in items:
            try:
                pid, qty = int(it.get("id")), int(it.get("qty", 1))
            except (TypeError, ValueError, AttributeError):
                raise ShopError("bad cart line")
            size = str(it.get("size") or "")[:12]
            p = self.product(pid)
            if not p or not p["active"]:
                raise ShopError("an item in your cart is no longer available")
            if qty < 1 or qty > 10:
                raise ShopError("quantity must be 1–10")
            if p["sizes"] and size not in p["sizes"]:
                raise ShopError(f"pick a size for {p['name']}")
            if p["stock"] < qty:
                raise ShopError(f"only {p['stock']} left of {p['name']}")
            lines.append({"id": pid, "name": p["name"], "slug": p["slug"], "size": size, "qty": qty, "price": p["price"], "image": (p["images"] or [None])[0]})
            subtotal += p["price"] * qty
        shipping = 0 if subtotal >= st["free_above"] else st["shipping_flat"]
        return {"lines": lines, "subtotal": subtotal, "shipping": shipping, "total": subtotal + shipping, "free_above": st["free_above"]}

    def checkout(self, items: list, customer: dict, user_id: int | None = None) -> dict:
        priced = self.price_cart(items)
        name = str(customer.get("name", "")).strip()[:80]
        phone = clean_phone(str(customer.get("phone", "")))
        email = str(customer.get("email", "")).strip()[:120] or None
        addr = {k: str(customer.get(k, "")).strip()[:120] for k in ("line1", "line2", "city", "state", "pincode")}
        if not name or not phone:
            raise ShopError("name and a 10-digit mobile number are required")
        if not addr["line1"] or not addr["city"] or not addr["state"] or not re.fullmatch(r"\d{6}", addr["pincode"]):
            raise ShopError("a full address with a 6-digit PIN code is required")
        if email and "@" not in email:
            raise ShopError("that email doesn't look right")
        oid = f"shop{int(time.time() * 1000)}{secrets.token_hex(2)}"
        if not self.create_order:
            raise ShopError("online payment is not switched on yet")
        out = self.create_order(oid, priced["total"] * 100, {"id": f"shop-{phone}", "email": email or f"{phone}@mobile.finostat", "phone": phone, "name": name},
                                f"Finostat shop · {len(priced['lines'])} item(s)", f"{self.public_url}/shop/order/{oid}?cf_order={{order_id}}")
        now = time.time()
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO shop_orders(id,status,name,phone,email,address,items,subtotal,shipping,amount,session_id,user_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (oid, "created", name, phone, email, json.dumps(addr), json.dumps(priced["lines"]), priced["subtotal"], priced["shipping"], priced["total"], out.get("payment_session_id"), user_id, now, now))
        return {"order_id": oid, "payment_session_id": out.get("payment_session_id"), "amount": priced["total"], "lines": priced["lines"]}

    def order(self, oid: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM shop_orders WHERE id=?", (oid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["address"] = json.loads(d["address"])
        d["items"] = json.loads(d["items"])
        return d

    def orders(self, limit: int = 100) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id FROM shop_orders ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [self.order(r["id"]) for r in rows]

    def mark_paid(self, oid: str, payment_id: str) -> dict | None:
        """First caller wins; decrements stock. Returns the order when newly paid."""
        now = time.time()
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE shop_orders SET status='paid', payment_id=?, paid_at=?, updated=? WHERE id=? AND status='created'", (payment_id, now, now, oid))
            if cur.rowcount != 1:
                return None
            for line in json.loads(c.execute("SELECT items FROM shop_orders WHERE id=?", (oid,)).fetchone()["items"]):
                c.execute("UPDATE shop_products SET stock=MAX(0, stock-?) WHERE id=?", (int(line["qty"]), int(line["id"])))
        return self.order(oid)

    def confirm(self, oid: str) -> dict:
        """Ask Cashfree whether the order is paid; mark it. {'ok', 'paid', 'newly_paid', 'order'}."""
        o = self.order(oid)
        if not o:
            return {"error": "unknown order"}
        if o["status"] != "created":
            return {"ok": True, "paid": o["status"] != "cancelled", "newly_paid": False, "order": o}
        if not self.fetch_order:
            return {"ok": True, "paid": False, "pending": True, "order": o}
        try:
            data = self.fetch_order(oid)
        except Exception as exc:                                    # noqa: BLE001
            return {"ok": True, "paid": False, "pending": True, "error": str(exc)[:120], "order": o}
        if str(data.get("order_status", "")).upper() != "PAID":
            return {"ok": True, "paid": False, "pending": True, "order": o}
        pid = "cf-paid"
        try:
            for p in (self.fetch_payments(oid) if self.fetch_payments else []):
                if str(p.get("payment_status", "")).upper() == "SUCCESS":
                    pid = str(p.get("cf_payment_id") or p.get("payment_id") or pid)
        except Exception:                                           # noqa: BLE001
            pass
        newly = self.mark_paid(oid, pid)
        return {"ok": True, "paid": True, "newly_paid": newly is not None, "order": newly or self.order(oid)}

    def update_order(self, oid: str, status: str | None = None, tracking: str | None = None, note: str | None = None) -> dict | None:
        sets, vals = [], []
        if status:
            if status not in STATUSES:
                raise ShopError("bad status")
            sets.append("status=?"); vals.append(status)
        if tracking is not None:
            sets.append("tracking=?"); vals.append(str(tracking)[:200])
        if note is not None:
            sets.append("note=?"); vals.append(str(note)[:500])
        if not sets:
            return self.order(oid)
        sets.append("updated=?"); vals.append(time.time())
        vals.append(oid)
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE shop_orders SET {', '.join(sets)} WHERE id=?", vals)
        return self.order(oid)

    def stats(self) -> dict:
        with self._conn() as c:
            paid = c.execute("SELECT COUNT(*) n, COALESCE(SUM(amount),0) s FROM shop_orders WHERE status IN ('paid','packed','shipped','delivered')").fetchone()
            open_ = c.execute("SELECT COUNT(*) FROM shop_orders WHERE status IN ('paid','packed')").fetchone()[0]
            prods = c.execute("SELECT COUNT(*) FROM shop_products WHERE active=1").fetchone()[0]
        return {"orders_paid": paid["n"], "revenue": paid["s"], "to_ship": open_, "products": prods}

    def receipt_lines(self, o: dict) -> list[str]:
        a = o["address"]
        lines = [f"Order: {o['id']}", f"Status: {o['status']}"]
        lines += [f"  {l['qty']} × {l['name']}{(' · ' + l['size']) if l.get('size') else ''} — ₹{l['price'] * l['qty']:,}" for l in o["items"]]
        lines += [f"Subtotal ₹{o['subtotal']:,} · Shipping ₹{o['shipping']:,} · Paid ₹{o['amount']:,} (inclusive of GST)",
                  f"Ship to: {o['name']}, {a['line1']}{(', ' + a['line2']) if a.get('line2') else ''}, {a['city']}, {a['state']} {a['pincode']} · {o['phone']}",
                  f"Track it: {self.public_url}/shop/order/{o['id']}"]
        return lines


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
from finch import _CSS as _BASE_CSS  # noqa: E402

_CSS = _BASE_CSS + r"""
.sh-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;margin:14px 0 28px}
.sh-card{border:1px solid var(--line-strong);background:var(--panel);display:flex;flex-direction:column;text-decoration:none;color:var(--text)}.sh-card:hover{border-color:var(--gold)}
.sh-card .im{aspect-ratio:1/1;background:#06031a;overflow:hidden;display:flex;align-items:center;justify-content:center}.sh-card .im img{width:100%;height:100%;object-fit:cover;display:block}.sh-card .im span{color:var(--faint);font-family:var(--mono);font-size:11px}
.sh-card .bd{padding:12px 14px}.sh-card b{font-family:var(--display);font-size:20px;text-transform:uppercase;line-height:1.05;display:block}.sh-card .pr{font-family:var(--mono);color:var(--gold);font-size:15px;margin-top:6px}.sh-card .pr s{color:var(--faint);margin-left:8px;font-size:12px}.sh-card .oos{color:var(--down);font-family:var(--mono);font-size:10.5px;letter-spacing:.1em}
.sh-prod{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:26px;margin:12px 0 30px}.sh-gal .main{aspect-ratio:1/1;background:#06031a;border:1px solid var(--line-strong)}.sh-gal .main img{width:100%;height:100%;object-fit:cover;display:block}
.sh-gal .thumbs{display:flex;gap:8px;margin-top:8px}.sh-gal .thumbs img{width:64px;height:64px;object-fit:cover;border:1px solid var(--line-strong);cursor:pointer}.sh-gal .thumbs img.on{border-color:var(--gold)}
.sh-buy h1{font-family:var(--display);font-size:clamp(30px,5vw,46px);text-transform:uppercase;line-height:1;margin:0 0 8px}.sh-buy .pr{font-family:var(--display);font-size:34px;color:var(--gold)}.sh-buy .pr s{font-family:var(--mono);font-size:14px;color:var(--faint);margin-left:10px}.sh-buy .pr i{font-style:normal;font-family:var(--mono);font-size:11px;color:var(--faint);margin-left:8px}
.sh-buy p{color:var(--muted);line-height:1.6;white-space:pre-line}.sizes{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.sizes button{font-family:var(--mono);font-size:12px;padding:8px 14px;border:1px solid var(--line-strong);background:none;color:var(--text);cursor:pointer}.sizes button.on{border-color:var(--gold);background:var(--gold);color:#2a1a02}
.qty{display:inline-flex;border:1px solid var(--line-strong)}.qty button{width:38px;height:38px;background:none;border:0;color:var(--text);font-size:18px;cursor:pointer}.qty span{width:44px;display:inline-flex;align-items:center;justify-content:center;font-family:var(--mono)}
.btn-g{display:inline-flex;align-items:center;justify-content:center;background:linear-gradient(180deg,var(--gold-2),#f2b830);color:#2a1a02;font-family:var(--mono);font-weight:700;font-size:12.5px;letter-spacing:.12em;padding:13px 22px;border:0;cursor:pointer;text-decoration:none}.btn-g:disabled{opacity:.5;cursor:default}.btn-o{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line-strong);color:var(--text);font-family:var(--mono);font-size:12px;letter-spacing:.1em;padding:12px 18px;background:none;cursor:pointer;text-decoration:none}.btn-o:hover{border-color:var(--gold);color:var(--gold)}
.cartbar{position:fixed;right:16px;bottom:86px;z-index:1100}.cartbar a{display:inline-flex;align-items:center;gap:8px;background:#120a33;border:1px solid var(--gold);color:var(--gold-2);font-family:var(--mono);font-size:11px;letter-spacing:.12em;padding:10px 14px;text-decoration:none}.cartbar b{background:var(--gold);color:#2a1a02;border-radius:50%;width:22px;height:22px;display:inline-flex;align-items:center;justify-content:center;font-size:11px}
.ck{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:26px;margin:12px 0 30px}.ck h2{font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold-2);margin:0 0 10px}
.lines{list-style:none;padding:0;margin:0}.lines li{display:grid;grid-template-columns:56px 1fr auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(190,150,255,.12)}.lines img{width:56px;height:56px;object-fit:cover;border:1px solid var(--line-strong)}.lines b{display:block;font-family:var(--display);font-size:17px;text-transform:uppercase}.lines small{color:var(--faint);font-family:var(--mono);font-size:10.5px}.lines .rm{background:none;border:0;color:var(--down);cursor:pointer;font-family:var(--mono);font-size:10px;letter-spacing:.1em}
.tot{font-family:var(--mono);font-size:12.5px;color:var(--muted);margin-top:12px;line-height:1.8}.tot b{color:var(--text)}.tot .big{font-family:var(--display);font-size:28px;color:var(--gold)}
.frm label{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.12em;color:var(--faint);margin:10px 0 4px;text-transform:uppercase}.frm input,.frm select,.frm textarea{width:100%;background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:15px;padding:10px 12px;box-sizing:border-box}.frm .two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.msg{margin-top:12px;padding:10px 12px;border:1px solid var(--line-strong);font-size:14px}.msg.bad{border-color:var(--down);color:var(--down)}.msg.ok{border-color:var(--up)}
.ord{border:1px solid var(--line-strong);background:var(--panel);padding:18px 20px;max-width:640px}.ord .st{font-family:var(--display);font-size:32px;text-transform:uppercase;color:var(--gold)}.steps{display:flex;gap:6px;margin:12px 0;font-family:var(--mono);font-size:10px;letter-spacing:.1em}.steps span{flex:1;padding:6px 0;text-align:center;border:1px solid var(--line-strong);color:var(--faint)}.steps span.on{border-color:var(--up);color:var(--up)}
.adm table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px}.adm th{font-size:10px;letter-spacing:.1em;color:var(--faint);font-weight:500;text-align:left;padding:6px 8px;border-bottom:1px solid var(--line-strong)}.adm td{padding:6px 8px;border-bottom:1px solid rgba(190,150,255,.1);vertical-align:top}.adm td img{width:40px;height:40px;object-fit:cover;border:1px solid var(--line-strong)}
.adm .kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:10px 0 18px}.adm .kp div{background:var(--panel);padding:10px 12px}.adm .kp small{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.12em;color:var(--faint)}.adm .kp b{font-family:var(--display);font-size:24px;color:var(--gold)}
.adm .imgs{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0}.adm .imgs div{position:relative}.adm .imgs img{width:72px;height:72px;object-fit:cover;border:1px solid var(--line-strong)}.adm .imgs button{position:absolute;top:-6px;right:-6px;width:20px;height:20px;border-radius:50%;border:0;background:var(--down);color:#fff;font-size:12px;cursor:pointer}
.adm select,.adm input.sm{background:#06031a;border:1px solid var(--line-strong);color:var(--text);font:inherit;font-size:12px;padding:4px 6px}
@media(max-width:800px){.sh-prod,.ck{grid-template-columns:1fr}}
"""

_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}"><meta name="theme-color" content="#0c0626"><meta name="robots" content="{robots}">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com{path}">
<meta property="og:type" content="{ogtype}"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:image" content="{ogimg}"><meta property="og:url" content="https://finostat.com{path}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
{ld}<style>{css}</style></head><body>
<header class="top"><a class="home-ic" href="/" aria-label="Finostat home"><img src="/favicon-96.png" alt="Finostat" width="30" height="30"></a><a class="logo" href="/shop">FINO<b>·</b>SHOP</a><div class="r"><a href="/shop/cart">CART</a><a href="/blog">BLOG</a><a href="/dashboard">TERMINAL</a></div></header>
<main class="wrap">"""
_FOOT = """</main><div class="cartbar" id="cartbar" hidden><a href="/shop/cart">CART <b id="cartn">0</b></a></div>
<script>(function(){ try{ var c=JSON.parse(localStorage.getItem('fino_cart')||'[]'); var n=c.reduce(function(a,x){ return a+(x.qty||1); },0); if(n){ document.getElementById('cartn').textContent=n; document.getElementById('cartbar').hidden=false; } }catch(e){} })();</script>
</body></html>"""


def _ld(obj) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


def _img(name: str | None, alt: str = "") -> str:
    return f'<img src="/shop/img/{_esc(name)}" alt="{_esc(alt)}" loading="lazy">' if name else '<span>no photo yet</span>'


def render_index(shop: Shop) -> bytes:
    st = shop.settings()
    prods = shop.products()
    cards = "".join(f'<a class="sh-card" href="/shop/{p["slug"]}"><div class="im">{_img((p["images"] or [None])[0], p["name"])}</div><div class="bd"><b>{_esc(p["name"])}</b>'
                    f'<div class="pr">₹{p["price"]:,}{("<s>₹" + format(p["compare_price"], ",") + "</s>") if p.get("compare_price") and p["compare_price"] > p["price"] else ""}</div>'
                    + ('<div class="oos">SOLD OUT</div>' if p["stock"] <= 0 else "") + '</div></a>' for p in prods) or '<p style="color:var(--faint)">The shelves are being stocked — check back soon.</p>'
    ld = _ld({"@context": "https://schema.org", "@type": "ItemList", "name": st["store_name"], "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"https://finostat.com/shop/{p['slug']}", "name": p["name"]} for i, p in enumerate(prods)]})
    doc = (_HEAD.format(title=f"{_esc(st['store_name'])} — {_esc(st['tagline'])} | Finostat", desc=f"{_esc(st['tagline'])}. Ships across India; pay by UPI, card or net banking.", robots="index, follow", path="/shop", ogtype="website",
                        ogimg=(f"https://finostat.com/shop/img/{prods[0]['images'][0]}" if prods and prods[0]["images"] else "https://finostat.com/og.jpg"), ld=ld, css=_CSS)
           + f'<nav class="crumb"><a href="/">FINO</a> · SHOP</nav><h1>{_esc(st["store_name"])}</h1><p class="lede">{_esc(st["tagline"])}. Prices include GST; shipping ₹{st["shipping_flat"]} across India, free above ₹{st["free_above"]:,}. Pay by UPI, card or net banking through Cashfree.</p>'
           + (f'<div class="msg ok">{_esc(st["announce"])}</div>' if st.get("announce") else "") + f'<div class="sh-grid">{cards}</div>' + _FOOT)
    return doc.encode("utf-8")


def render_product(shop: Shop, slug: str) -> bytes | None:
    p = shop.product(slug)
    if not p or not p["active"]:
        return None
    st = shop.settings()
    imgs = p["images"] or []
    gal = (f'<div class="main" id="gmain">{_img(imgs[0] if imgs else None, p["name"])}</div>'
           + (('<div class="thumbs">' + "".join(f'<img src="/shop/img/{_esc(i)}" alt="" class="{"on" if n == 0 else ""}" data-i="{_esc(i)}">' for n, i in enumerate(imgs)) + '</div>') if len(imgs) > 1 else ""))
    sizes = ('<div class="sizes" id="sizes">' + "".join(f'<button type="button" data-s="{_esc(s)}">{_esc(s)}</button>' for s in p["sizes"]) + '</div>') if p["sizes"] else ""
    ld = _ld({"@context": "https://schema.org", "@type": "Product", "name": p["name"], "description": p["description"][:300], "image": [f"https://finostat.com/shop/img/{i}" for i in imgs], "brand": {"@type": "Brand", "name": "Finostat"},
              "offers": {"@type": "Offer", "price": str(p["price"]), "priceCurrency": "INR", "availability": "https://schema.org/InStock" if p["stock"] > 0 else "https://schema.org/OutOfStock", "url": f"https://finostat.com/shop/{p['slug']}"}})
    pjson = json.dumps({"id": p["id"], "name": p["name"], "price": p["price"], "slug": p["slug"], "image": imgs[0] if imgs else None, "sizes": p["sizes"], "stock": p["stock"]}).replace("</", "<\\/")
    doc = (_HEAD.format(title=f"{_esc(p['name'])} — ₹{p['price']:,} | {_esc(st['store_name'])}", desc=_esc(p["description"][:160] or st["tagline"]), robots="index, follow", path=f"/shop/{p['slug']}", ogtype="product",
                        ogimg=(f"https://finostat.com/shop/img/{imgs[0]}" if imgs else "https://finostat.com/og.jpg"), ld=ld, css=_CSS)
           + f'<nav class="crumb"><a href="/">FINO</a> · <a href="/shop">SHOP</a> · {_esc(p["name"]).upper()}</nav>'
           + f'<div class="sh-prod"><div class="sh-gal">{gal}</div><div class="sh-buy"><h1>{_esc(p["name"])}</h1>'
           + f'<div class="pr">₹{p["price"]:,}{("<s>₹" + format(p["compare_price"], ",") + "</s>") if p.get("compare_price") and p["compare_price"] > p["price"] else ""}<i>incl. GST</i></div>'
           + f'<p>{_esc(p["description"])}</p>' + sizes
           + (f'<div style="display:flex;gap:12px;align-items:center;margin:14px 0"><div class="qty"><button type="button" id="qm">−</button><span id="qv">1</span><button type="button" id="qp">+</button></div><span style="font-family:var(--mono);font-size:11px;color:var(--faint)">{p["stock"]} in stock</span></div>'
              f'<button class="btn-g" id="add" type="button">ADD TO CART</button> <a class="btn-o" href="/shop/cart">VIEW CART</a><div class="msg" id="pmsg" hidden></div>' if p["stock"] > 0 else '<div class="msg bad">Sold out — back soon.</div>')
           + f'<p style="font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:16px">Ships across India in 5–7 days · ₹{st["shipping_flat"]} shipping, free above ₹{st["free_above"]:,} · pay by UPI, card or net banking</p></div></div>'
           + f"""<script>(function(){{ var P={pjson};
  var size=null, qty=1; var $=function(id){{ return document.getElementById(id); }};
  var sz=$('sizes'); if(sz) sz.addEventListener('click',function(e){{ var b=e.target.closest('button'); if(!b) return; size=b.getAttribute('data-s'); Array.prototype.forEach.call(sz.querySelectorAll('button'),function(x){{ x.classList.toggle('on',x===b); }}); }});
  if($('qm')){{ $('qm').addEventListener('click',function(){{ qty=Math.max(1,qty-1); $('qv').textContent=qty; }}); $('qp').addEventListener('click',function(){{ qty=Math.min(Math.min(10,P.stock),qty+1); $('qv').textContent=qty; }}); }}
  document.querySelectorAll('.thumbs img').forEach(function(t){{ t.addEventListener('click',function(){{ $('gmain').innerHTML='<img src="/shop/img/'+t.getAttribute('data-i')+'" alt="">'; document.querySelectorAll('.thumbs img').forEach(function(x){{ x.classList.toggle('on',x===t); }}); }}); }});
  if($('add')) $('add').addEventListener('click',function(){{ if(P.sizes.length&&!size){{ $('pmsg').hidden=false; $('pmsg').className='msg bad'; $('pmsg').textContent='Pick a size first.'; return; }} var c=[]; try{{ c=JSON.parse(localStorage.getItem('fino_cart')||'[]'); }}catch(e){{}} var hit=c.filter(function(x){{ return x.id===P.id&&(x.size||'')===(size||''); }})[0]; if(hit) hit.qty=Math.min(10,(hit.qty||1)+qty); else c.push({{id:P.id,name:P.name,price:P.price,slug:P.slug,image:P.image,size:size||'',qty:qty}}); localStorage.setItem('fino_cart',JSON.stringify(c)); $('pmsg').hidden=false; $('pmsg').className='msg ok'; $('pmsg').innerHTML='Added. <a href="/shop/cart" style="color:var(--cyan)">Go to cart →</a>'; var n=c.reduce(function(a,x){{ return a+(x.qty||1); }},0); $('cartn').textContent=n; $('cartbar').hidden=false; }});
}})();</script>""" + _FOOT)
    return doc.encode("utf-8")


def render_cart(shop: Shop, configured: bool = True, prefill: dict | None = None) -> bytes:
    st = shop.settings()
    pf = prefill or {}
    doc = (_HEAD.format(title=f"Cart & checkout | {_esc(st['store_name'])}", desc="Review your cart and pay by UPI, card or net banking.", robots="noindex", path="/shop/cart", ogtype="website", ogimg="https://finostat.com/og.jpg", ld="", css=_CSS)
           + '<nav class="crumb"><a href="/">FINO</a> · <a href="/shop">SHOP</a> · CART</nav><h1>Cart &amp; checkout</h1>'
           + '<div class="ck"><div><h2>Your items</h2><ul class="lines" id="lines"></ul><div class="tot" id="tot"></div><p><a class="btn-o" href="/shop">← Keep shopping</a></p></div>'
           + f'<div class="frm"><h2>Ship to</h2><form id="ck" autocomplete="on"><label for="f-name">Full name</label><input id="f-name" required maxlength="80" value="{_esc(pf.get("name", ""))}">'
           f'<div class="two"><div><label for="f-phone">Mobile (10 digits)</label><input id="f-phone" type="tel" inputmode="numeric" required maxlength="14" value="{_esc(pf.get("phone", ""))}"></div><div><label for="f-email">Email (for the receipt)</label><input id="f-email" type="email" maxlength="120" value="{_esc(pf.get("email", ""))}"></div></div>'
           '<label for="f-l1">Address line 1</label><input id="f-l1" required maxlength="120"><label for="f-l2">Address line 2 (optional)</label><input id="f-l2" maxlength="120">'
           '<div class="two"><div><label for="f-city">City</label><input id="f-city" required maxlength="60"></div><div><label for="f-pin">PIN code</label><input id="f-pin" inputmode="numeric" required maxlength="6" pattern="[0-9]{6}"></div></div>'
           '<label for="f-state">State</label><input id="f-state" required maxlength="60">'
           + (f'<button class="btn-g" id="pay" type="submit" style="margin-top:16px;width:100%">PAY WITH CASHFREE →</button>' if configured else '<div class="msg bad" style="margin-top:16px">Payments are not switched on yet — write to hello@finostat.com to order.</div>')
           + '<div class="msg" id="cmsg" hidden></div><p style="font-family:var(--mono);font-size:10.5px;color:var(--faint);margin-top:12px;line-height:1.5">Prices include GST. Orders ship in 5–7 days across India. Digital receipt by email; track your order at the link on the confirmation page. <a href="/terms" style="color:var(--cyan)">Terms</a> · <a href="/privacy" style="color:var(--cyan)">Privacy</a></p></form></div></div>'
           + f"""<script>(function(){{ var $=function(id){{ return document.getElementById(id); }}; var SHIP={st["shipping_flat"]}, FREE={st["free_above"]};
  function cart(){{ try{{ return JSON.parse(localStorage.getItem('fino_cart')||'[]'); }}catch(e){{ return []; }} }} function save(c){{ localStorage.setItem('fino_cart',JSON.stringify(c)); }}
  function esc(s){{ return String(s).replace(/[&<>"]/g,function(ch){{ return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[ch]; }}); }}
  function render(){{ var c=cart(); if(!c.length){{ $('lines').innerHTML='<li><span style="color:var(--faint)">Your cart is empty.</span></li>'; $('tot').innerHTML=''; if($('pay')) $('pay').disabled=true; return; }} if($('pay')) $('pay').disabled=false;
    $('lines').innerHTML=c.map(function(x,i){{ return '<li>'+(x.image?'<img src="/shop/img/'+esc(x.image)+'" alt="">':'<span></span>')+'<div><b>'+esc(x.name)+'</b><small>'+(x.size?esc(x.size)+' · ':'')+'₹'+Number(x.price).toLocaleString('en-IN')+' × '+x.qty+'</small><br><button type="button" class="rm" data-i="'+i+'">REMOVE</button></div><div style="font-family:var(--mono)">₹'+(x.price*x.qty).toLocaleString('en-IN')+'</div></li>'; }}).join('');
    var sub=c.reduce(function(a,x){{ return a+x.price*x.qty; }},0); var ship=sub>=FREE?0:SHIP; $('tot').innerHTML='Subtotal <b>₹'+sub.toLocaleString('en-IN')+'</b><br>Shipping <b>'+(ship?'₹'+ship:'FREE')+'</b>'+(ship&&FREE>sub?' <span style="color:var(--faint)">(free above ₹'+FREE.toLocaleString('en-IN')+')</span>':'')+'<br><span class="big">₹'+(sub+ship).toLocaleString('en-IN')+'</span> <span style="color:var(--faint)">incl. GST</span>'; }}
  $('lines').addEventListener('click',function(e){{ var b=e.target.closest('button.rm'); if(!b) return; var c=cart(); c.splice(Number(b.getAttribute('data-i')),1); save(c); render(); }});
  render();
  function show(k,t){{ var m=$('cmsg'); m.hidden=false; m.className='msg '+k; m.innerHTML=t; }}
  function post(url,body,cb){{ fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json','X-Requested-With':'fetch'}},body:JSON.stringify(body),credentials:'same-origin'}}).then(function(r){{ return r.json().then(function(j){{ return {{s:r.status,j:j}}; }}); }}).then(function(x){{ cb(x.s,x.j); }}).catch(function(){{ cb(0,{{error:'network'}}); }}); }}
  function loadScript(src,cb){{ if(window.Cashfree) return cb(); var s=document.createElement('script'); s.src=src; s.onload=cb; s.onerror=function(){{ show('bad','Cashfree checkout failed to load'); }}; document.head.appendChild(s); }}
  function settle(oid,tries){{ tries=tries||0; post('/api/shop/verify',{{order_id:oid}},function(s,j){{ if(s===200&&j.paid){{ localStorage.removeItem('fino_cart'); location.href='/shop/order/'+oid+'?paid=1'; return; }} if(j.pending&&tries<6){{ show('ok','Waiting for Cashfree to confirm…'); setTimeout(function(){{ settle(oid,tries+1); }},3000); return; }} show('bad',j.error||'Could not confirm the payment yet. If money left your account the order activates automatically — check /shop/order/'+oid+' in a minute.'); if($('pay')) $('pay').disabled=false; }}); }}
  $('ck').addEventListener('submit',function(e){{ e.preventDefault(); var c=cart(); if(!c.length) return; var body={{items:c.map(function(x){{ return {{id:x.id,size:x.size||'',qty:x.qty}}; }}),customer:{{name:$('f-name').value,phone:$('f-phone').value,email:$('f-email').value,line1:$('f-l1').value,line2:$('f-l2').value,city:$('f-city').value,state:$('f-state').value,pincode:$('f-pin').value}}}};
    $('pay').disabled=true; show('ok','Creating your order…'); post('/api/shop/checkout',body,function(s,o){{ if(s!==200){{ show('bad',o.error||('HTTP '+s)); $('pay').disabled=false; return; }}
      loadScript('https://sdk.cashfree.com/js/v3/cashfree.js',function(){{ if(!window.Cashfree){{ show('bad','Cashfree checkout failed to load'); $('pay').disabled=false; return; }} var cf=window.Cashfree({{mode:o.env==='sandbox'?'sandbox':'production'}}); cf.checkout({{paymentSessionId:o.payment_session_id, redirectTarget:'_modal'}}).then(function(){{ settle(o.order_id); }}).catch(function(){{ show('bad','Cashfree checkout error'); $('pay').disabled=false; }}); }}); }}); }});
}})();</script>""" + _FOOT)
    return doc.encode("utf-8")


def render_order(shop: Shop, oid: str) -> bytes | None:
    o = shop.order(oid)
    if not o:
        return None
    st = shop.settings()
    a = o["address"]
    steps = "".join(f'<span class="{"on" if STATUSES.index(o["status"]) >= STATUSES.index(s) and o["status"] != "cancelled" else ""}">{s.upper()}</span>' for s in ("paid", "packed", "shipped", "delivered"))
    items = "".join('<li>' + ('<img src="/shop/img/' + _esc(l["image"]) + '" alt="">' if l.get("image") else "<span></span>") + f'<div><b>{_esc(l["name"])}</b><small>{(_esc(l["size"]) + " · ") if l.get("size") else ""}₹{l["price"]:,} × {l["qty"]}</small></div><div style="font-family:var(--mono)">₹{l["price"] * l["qty"]:,}</div></li>' for l in o["items"])
    head = {"created": "Payment pending", "paid": "Order confirmed", "packed": "Packed", "shipped": "Shipped", "delivered": "Delivered", "cancelled": "Cancelled"}[o["status"]]
    doc = (_HEAD.format(title=f"Order {_esc(oid)} | {_esc(st['store_name'])}", desc="Order status.", robots="noindex", path=f"/shop/order/{oid}", ogtype="website", ogimg="https://finostat.com/og.jpg", ld="", css=_CSS)
           + f'<nav class="crumb"><a href="/">FINO</a> · <a href="/shop">SHOP</a> · ORDER</nav><div class="ord"><div style="font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;color:var(--faint)">ORDER {_esc(oid)} · {datetime.fromtimestamp(o["created"], IST).strftime("%d %b %Y %H:%M")} IST</div><div class="st">{head}</div>'
           + (f'<div class="steps">{steps}</div>' if o["status"] != "cancelled" else "")
           + (f'<div class="msg ok">Tracking: {_esc(o["tracking"])}</div>' if o.get("tracking") else "")
           + (f'<div class="msg" id="pend">Waiting for Cashfree to confirm your payment… this page refreshes itself.</div>' if o["status"] == "created" else "")
           + f'<ul class="lines">{items}</ul><div class="tot">Subtotal <b>₹{o["subtotal"]:,}</b> · Shipping <b>{("₹" + format(o["shipping"], ",")) if o["shipping"] else "FREE"}</b><br><span class="big">₹{o["amount"]:,}</span> <span style="color:var(--faint)">incl. GST</span></div>'
           + f'<p style="color:var(--muted);font-size:14px;margin-top:14px"><b style="color:var(--text)">Ships to</b><br>{_esc(o["name"])}<br>{_esc(a["line1"])}{("<br>" + _esc(a["line2"])) if a.get("line2") else ""}<br>{_esc(a["city"])}, {_esc(a["state"])} {_esc(a["pincode"])}<br>{_esc(o["phone"])}</p>'
           + '<p style="font-family:var(--mono);font-size:10.5px;color:var(--faint)">Questions about this order: hello@finostat.com with the order number.</p></div>'
           + ("<script>(function(){ var t=0; function poll(){ fetch('/api/shop/verify',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify({order_id:" + json.dumps(oid) + "})}).then(function(r){ return r.json(); }).then(function(j){ if(j.paid){ location.reload(); } else if(t++<10){ setTimeout(poll,4000); } }).catch(function(){}); } setTimeout(poll,2500); })();</script>" if o["status"] == "created" else "")
           + _FOOT)
    return doc.encode("utf-8")


def render_admin(shop: Shop) -> bytes:
    st = shop.settings()
    s = shop.stats()
    prods = shop.products(active_only=False)
    orders = shop.orders(60)
    prow = "".join(f'<tr><td>{_img((p["images"] or [None])[0], "")}</td><td><b>{_esc(p["name"])}</b><br><small style="color:var(--faint)">/shop/{_esc(p["slug"])}{" · hidden" if not p["active"] else ""}</small></td><td>₹{p["price"]:,}{(" <s>₹" + format(p["compare_price"], ",") + "</s>") if p.get("compare_price") else ""}</td><td>{p["stock"]}</td><td>{_esc(", ".join(p["sizes"]))}</td>'
                   f'<td><button type="button" class="btn-o" data-edit="{p["id"]}" style="padding:4px 10px;font-size:10px">EDIT</button> <button type="button" class="btn-o" data-del="{p["id"]}" style="padding:4px 10px;font-size:10px;color:var(--down)">DELETE</button></td></tr>' for p in prods) or '<tr><td colspan="6" style="color:var(--faint)">no products yet — add the first one above</td></tr>'
    def _orow(o):
        a = o["address"]
        items = "<br>".join(f'{l["qty"]}× {_esc(l["name"])}{(" " + _esc(l["size"])) if l.get("size") else ""}' for l in o["items"])
        opts = "".join(f'<option{" selected" if o["status"] == x else ""}>{x}</option>' for x in STATUSES)
        when = datetime.fromtimestamp(o["created"], IST).strftime("%d %b %H:%M")
        email = (" · " + _esc(o["email"])) if o.get("email") else ""
        return (f'<tr><td><a href="/shop/order/{o["id"]}" style="color:var(--cyan)">{_esc(o["id"])}</a><br><small style="color:var(--faint)">{when}</small></td>'
                f'<td>{_esc(o["name"])}<br><small>{_esc(o["phone"])}{email}</small><br><small style="color:var(--faint)">{_esc(a["city"])} {_esc(a["pincode"])}</small></td>'
                f'<td>{items}</td><td>₹{o["amount"]:,}</td>'
                f'<td><select data-oid="{o["id"]}" class="ost">{opts}</select><br><input class="sm otr" data-oid="{o["id"]}" placeholder="tracking / courier" value="{_esc(o.get("tracking") or "")}" style="margin-top:4px;width:150px"><br>'
                f'<button type="button" class="btn-o osave" data-oid="{o["id"]}" style="padding:3px 8px;font-size:10px;margin-top:4px">SAVE</button></td></tr>')
    orow = "".join(_orow(o) for o in orders) or '<tr><td colspan="5" style="color:var(--faint)">no orders yet</td></tr>'
    prods_json = json.dumps({p["id"]: p for p in prods}).replace("</", "<\\/")
    doc = (_HEAD.format(title="Shop admin | Finostat", desc="", robots="noindex, nofollow", path="/shop/admin", ogtype="website", ogimg="https://finostat.com/og.jpg", ld="", css=_CSS)
           + '<nav class="crumb"><a href="/">FINO</a> · <a href="/shop">SHOP</a> · ADMIN</nav><div class="adm"><h1>Shop admin</h1>'
           + f'<div class="kp"><div><small>PAID ORDERS</small><b>{s["orders_paid"]}</b></div><div><small>REVENUE</small><b>₹{s["revenue"]:,}</b></div><div><small>TO SHIP</small><b>{s["to_ship"]}</b></div><div><small>LIVE PRODUCTS</small><b>{s["products"]}</b></div></div>'
           + f'<h2 style="font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold-2)">Settings</h2><div class="frm" style="max-width:640px"><div class="two"><div><label>Store name</label><input id="s-name" value="{_esc(st["store_name"])}"></div><div><label>Tagline</label><input id="s-tag" value="{_esc(st["tagline"])}"></div></div>'
           f'<div class="two"><div><label>Shipping flat ₹</label><input id="s-ship" type="number" value="{st["shipping_flat"]}"></div><div><label>Free shipping above ₹</label><input id="s-free" type="number" value="{st["free_above"]}"></div></div><label>Announcement (optional)</label><input id="s-ann" value="{_esc(st["announce"])}"><p><button type="button" class="btn-o" id="s-save">SAVE SETTINGS</button> <span id="s-msg" style="font-family:var(--mono);font-size:11px;color:var(--faint)"></span></p></div>'
           + '<h2 style="font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold-2);margin-top:22px" id="p-head">Add a product</h2><div class="frm" style="max-width:720px"><input type="hidden" id="p-id"><label>Name</label><input id="p-name" maxlength="120"><label>Description</label><textarea id="p-desc" rows="5" maxlength="4000"></textarea>'
           '<div class="two"><div><label>Price ₹ (incl. GST)</label><input id="p-price" type="number" min="1"></div><div><label>Compare-at price ₹ (optional, shown struck out)</label><input id="p-cmp" type="number" min="0"></div></div>'
           '<div class="two"><div><label>Stock (units)</label><input id="p-stock" type="number" min="0" value="10"></div><div><label>Sizes (comma separated, blank if none)</label><input id="p-sizes" placeholder="S, M, L, XL"></div></div>'
           '<label>Photos (JPEG / PNG / WebP, up to 6 MB each, first one is the cover)</label><input id="p-file" type="file" accept="image/jpeg,image/png,image/webp" multiple><div class="imgs" id="p-imgs"></div>'
           '<label><input type="checkbox" id="p-active" checked style="width:auto"> visible in the shop</label>'
           '<p><button type="button" class="btn-g" id="p-save">SAVE PRODUCT</button> <button type="button" class="btn-o" id="p-clear">CLEAR</button> <span id="p-msg" style="font-family:var(--mono);font-size:11px;color:var(--faint)"></span></p></div>'
           + f'<h2 style="font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold-2);margin-top:22px">Products</h2><div class="scrollx"><table><thead><tr><th></th><th>PRODUCT</th><th>PRICE</th><th>STOCK</th><th>SIZES</th><th></th></tr></thead><tbody>{prow}</tbody></table></div>'
           + f'<h2 style="font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold-2);margin-top:22px">Orders</h2><div class="scrollx"><table><thead><tr><th>ORDER</th><th>CUSTOMER</th><th>ITEMS</th><th>PAID</th><th>STATUS · TRACKING</th></tr></thead><tbody>{orow}</tbody></table></div></div>'
           + f"""<script>(function(){{ var $=function(id){{ return document.getElementById(id); }}; var PRODS={prods_json}; var images=[];
  function post(url,body,cb){{ fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json','X-Requested-With':'fetch'}},body:JSON.stringify(body),credentials:'same-origin'}}).then(function(r){{ return r.json().then(function(j){{ return {{s:r.status,j:j}}; }}); }}).then(function(x){{ cb(x.s,x.j); }}).catch(function(){{ cb(0,{{error:'network'}}); }}); }}
  function drawImgs(){{ $('p-imgs').innerHTML=images.map(function(i,n){{ return '<div><img src="/shop/img/'+i+'" alt=""><button type="button" data-n="'+n+'">×</button></div>'; }}).join(''); }}
  $('p-imgs').addEventListener('click',function(e){{ var b=e.target.closest('button'); if(!b) return; images.splice(Number(b.getAttribute('data-n')),1); drawImgs(); }});
  $('p-file').addEventListener('change',function(){{ var files=Array.prototype.slice.call(this.files); var i=0; (function next(){{ if(i>=files.length){{ $('p-file').value=''; return; }} var f=files[i++]; var rd=new FileReader(); rd.onload=function(){{ $('p-msg').textContent='uploading '+f.name+'…'; post('/api/shop/admin/image',{{mime:f.type,data:rd.result}},function(s,j){{ if(s===200&&j.image){{ images.push(j.image); drawImgs(); $('p-msg').textContent='uploaded'; }} else {{ $('p-msg').textContent=j.error||('upload failed '+s); }} next(); }}); }}; rd.readAsDataURL(f); }})(); }});
  function fill(p){{ $('p-id').value=p?p.id:''; $('p-name').value=p?p.name:''; $('p-desc').value=p?p.description:''; $('p-price').value=p?p.price:''; $('p-cmp').value=p&&p.compare_price?p.compare_price:''; $('p-stock').value=p?p.stock:10; $('p-sizes').value=p?p.sizes.join(', '):''; $('p-active').checked=p?!!p.active:true; images=p?p.images.slice():[]; drawImgs(); $('p-head').textContent=p?'Edit: '+p.name:'Add a product'; window.scrollTo({{top:$('p-head').offsetTop-80,behavior:'smooth'}}); }}
  document.addEventListener('click',function(e){{ var ed=e.target.closest('[data-edit]'); if(ed){{ fill(PRODS[ed.getAttribute('data-edit')]); return; }} var dl=e.target.closest('[data-del]'); if(dl&&confirm('Delete this product?')){{ post('/api/shop/admin/product',{{op:'delete',id:Number(dl.getAttribute('data-del'))}},function(){{ location.reload(); }}); }} }});
  $('p-clear').addEventListener('click',function(){{ fill(null); }});
  $('p-save').addEventListener('click',function(){{ var body={{op:$('p-id').value?'update':'create',id:Number($('p-id').value)||null,name:$('p-name').value,description:$('p-desc').value,price:$('p-price').value,compare_price:$('p-cmp').value,stock:$('p-stock').value,sizes:$('p-sizes').value.split(',').map(function(s){{ return s.trim(); }}).filter(Boolean),images:images,active:$('p-active').checked}}; $('p-msg').textContent='saving…'; post('/api/shop/admin/product',body,function(s,j){{ if(s===200){{ location.reload(); }} else $('p-msg').textContent=j.error||('HTTP '+s); }}); }});
  $('s-save').addEventListener('click',function(){{ post('/api/shop/admin/settings',{{store_name:$('s-name').value,tagline:$('s-tag').value,shipping_flat:$('s-ship').value,free_above:$('s-free').value,announce:$('s-ann').value}},function(s,j){{ $('s-msg').textContent=s===200?'saved':(j.error||'failed'); }}); }});
  document.querySelectorAll('.osave').forEach(function(b){{ b.addEventListener('click',function(){{ var oid=b.getAttribute('data-oid'); var st=document.querySelector('.ost[data-oid="'+oid+'"]').value, tr=document.querySelector('.otr[data-oid="'+oid+'"]').value; b.textContent='…'; post('/api/shop/admin/order',{{order_id:oid,status:st,tracking:tr}},function(s,j){{ b.textContent=s===200?'SAVED':'FAILED'; }}); }}); }});
}})();</script>""" + _FOOT)
    return doc.encode("utf-8")


def sitemap_entries(shop: Shop) -> str:
    out = ['  <url><loc>https://finostat.com/shop</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>']
    for p in shop.products():
        out.append(f'  <url><loc>https://finostat.com/shop/{_esc(p["slug"])}</loc><priority>0.6</priority></url>')
    return "\n".join(out) + "\n"
