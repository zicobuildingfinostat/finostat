"""Shop: catalogue seed, products, images, cart pricing, checkout, payment confirm + stock, order updates, pages, sitemap."""
import os, sys, tempfile, pathlib, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import shop, shop_catalog

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

d = pathlib.Path(tempfile.mkdtemp())
created = []
S = shop.Shop(d / "a.db", d / "img", create_order=lambda oid, amt, cust, note, ret: created.append((oid, amt, cust, ret)) or {"payment_session_id": "sess_1"},
              fetch_order=lambda oid: {"order_status": "PAID" if oid in PAID else "ACTIVE"}, fetch_payments=lambda oid: [{"payment_status": "SUCCESS", "cf_payment_id": "cf9"}])
PAID = set()
check("seed once", shop_catalog.seed(S) == len(shop_catalog.ITEMS) and shop_catalog.seed(S) == 0)
ps = S.products()
check("catalogue: mugs, tees, mat, keyboard present with mockups", len(ps) == len(shop_catalog.ITEMS) and any("mug" in p["slug"] for p in ps) and any("keyboard" in p["slug"] for p in ps) and all(p["images"] and p["images"][0].endswith(".svg") for p in ps))
tee = next(p for p in ps if p["slug"] == "sell-premium-tee")
check("tee has sizes and compare price", tee["sizes"] == ["S", "M", "L", "XL", "XXL"] and tee["compare_price"] > tee["price"])
check("mockup svg served by image_path", S.image_path(tee["images"][0]) is not None and S.image_path("../etc/passwd") is None and S.image_path("zz.svg") is None)

# products CRUD
p = S.save_product({"name": "Test Cap", "price": "599", "stock": 3, "sizes": ["", "One"], "images": ["bad.exe"], "compare_price": "", "description": "x"})
check("save_product: slug, sizes cleaned, bad image dropped", p["slug"] == "test-cap" and p["sizes"] == ["One"] and p["images"] == [] and p["compare_price"] is None)
p2 = S.save_product({"name": "Test Cap", "price": 10, "stock": 1})
check("duplicate names get unique slugs", p2["slug"] == "test-cap-2")
try:
    S.save_product({"name": "", "price": 1, "stock": 1}); check("empty name rejected", False)
except shop.ShopError:
    check("empty name rejected", True)
S.save_product({"name": "Test Cap", "price": 650, "stock": 0, "active": False}, pid=p["id"])
check("update + hidden product not listed", S.product(p["id"])["price"] == 650 and all(x["id"] != p["id"] for x in S.products()) and any(x["id"] == p["id"] for x in S.products(active_only=False)))
check("delete", S.delete_product(p2["id"]) and S.product(p2["id"]) is None)

# images
png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 100).decode()
name = S.save_image("image/png", "data:image/png;base64," + png)
check("png upload stored", name.endswith(".png") and S.image_path(name))
for mime, data, why in (("image/gif", png, "type"), ("image/png", base64.b64encode(b"notpng").decode(), "magic"), ("image/svg+xml", png, "svg upload blocked")):
    try:
        S.save_image(mime, data); check("upload rejected: " + why, False)
    except shop.ShopError:
        check("upload rejected: " + why, True)

# cart + checkout
mug = next(p for p in ps if p["slug"] == "theta-gang-mug")
pr = S.price_cart([{"id": tee["id"], "size": "L", "qty": 2}, {"id": mug["id"], "qty": 1}])
check("price_cart: lines, subtotal, free shipping above threshold", len(pr["lines"]) == 2 and pr["subtotal"] == tee["price"] * 2 + mug["price"] and pr["shipping"] == 0)
pr2 = S.price_cart([{"id": mug["id"], "qty": 1}])
check("price_cart: shipping charged under threshold", pr2["shipping"] == 79 and pr2["total"] == mug["price"] + 79)
for items, why in (([{"id": tee["id"], "qty": 1}], "size required"), ([{"id": mug["id"], "qty": 99}], "qty cap"), ([{"id": 99999, "qty": 1}], "unknown product"), ([], "empty")):
    try:
        S.price_cart(items); check("price_cart rejects: " + why, False)
    except shop.ShopError:
        check("price_cart rejects: " + why, True)
cust = {"name": "Zico K", "phone": "+91 98765 43210", "email": "z@x.y", "line1": "12 MG Road", "line2": "", "city": "Kolkata", "state": "WB", "pincode": "700001"}
o = S.checkout([{"id": tee["id"], "size": "L", "qty": 2}], cust)
check("checkout: order id, amount, cashfree call with return url", o["order_id"].startswith("shop") and o["amount"] == tee["price"] * 2 and created[-1][1] == tee["price"] * 2 * 100 and created[-1][2]["phone"] == "9876543210" and "/shop/order/" in created[-1][3])
try:
    S.checkout([{"id": mug["id"], "qty": 1}], dict(cust, pincode="12")); check("checkout rejects bad pin", False)
except shop.ShopError:
    check("checkout rejects bad pin", True)
r = S.confirm(o["order_id"])
check("confirm: pending while unpaid", r["ok"] and not r["paid"] and r.get("pending"))
PAID.add(o["order_id"])
r = S.confirm(o["order_id"])
check("confirm: paid once, stock decremented", r["paid"] and r["newly_paid"] and r["order"]["status"] == "paid" and r["order"]["payment_id"] == "cf9" and S.product(tee["id"])["stock"] == 23)
r2 = S.confirm(o["order_id"])
check("confirm idempotent", r2["paid"] and not r2["newly_paid"] and S.product(tee["id"])["stock"] == 23)
u = S.update_order(o["order_id"], status="shipped", tracking="Delhivery 123")
check("update order", u["status"] == "shipped" and u["tracking"] == "Delhivery 123")
try:
    S.update_order(o["order_id"], status="lost"); check("bad status rejected", False)
except shop.ShopError:
    check("bad status rejected", True)
st = S.stats()
check("stats", st["orders_paid"] == 1 and st["revenue"] == tee["price"] * 2 and st["products"] == len(shop_catalog.ITEMS))
check("receipt lines", any("Delhivery" not in l for l in S.receipt_lines(u)) and any("Ship to" in l for l in S.receipt_lines(u)))
check("settings roundtrip", S.set_settings({"shipping_flat": "99", "free_above": 1500, "announce": "Diwali sale"})["shipping_flat"] == 99 and S.settings()["announce"] == "Diwali sale")

# pages
idx = shop.render_index(S).decode()
check("index: cards, schema, announce", idx.count('class="sh-card"') == len(shop_catalog.ITEMS) and '"@type":"ItemList"' in idx and "Diwali sale" in idx and "/shop/img/" in idx)
pp = shop.render_product(S, "sell-premium-tee").decode()
check("product page: sizes, add to cart, Product schema", 'data-s="XL"' in pp and 'id="add"' in pp and '"@type":"Product"' in pp and "incl. GST" in pp)
check("hidden/unknown product -> None", shop.render_product(S, "test-cap") is None and shop.render_product(S, "nope") is None)
cart = shop.render_cart(S, True, {"phone": "9876543210"}).then if False else shop.render_cart(S, True, {"phone": "9876543210"}).decode()
check("cart page: form + cashfree + prefill", 'id="f-pin"' in cart and "cashfree.js" in cart and 'value="9876543210"' in cart and "SHIP=99" in cart)
op = shop.render_order(S, o["order_id"]).decode()
check("order page: status steps + tracking", "Shipped" in op and "Delhivery 123" in op and 'class="on">SHIPPED' in op and "MG Road" in op)
adm = shop.render_admin(S).decode()
check("admin: products, orders, settings", "Test Cap" in adm and o["order_id"] in adm and 'id="s-ship"' in adm and "SAVE PRODUCT" in adm)
sm = shop.sitemap_entries(S)
check("sitemap", "/shop</loc>" in sm and sm.count("<loc>") == 1 + len(S.products()))
print("fails:", fails)
sys.exit(1 if fails else 0)
