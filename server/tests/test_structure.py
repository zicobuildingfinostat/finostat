"""STRUCT: the engine on Indian candles via a fake candle store; alert families; shared chart module on both terminals."""
import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import structure, gold, alerts, pages, pages_global, chart_pa

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

random.seed(3)
def make(n, start=23000.0, step_min=15):
    px, out = start, []
    for i in range(n):
        drift = 0.0006 if (i // 150) % 2 == 0 else -0.0004
        px *= 1 + drift + random.gauss(0, 0.002)
        o = px * (1 + random.gauss(0, 0.0008)); h = max(o, px) * (1 + abs(random.gauss(0, 0.0008))); l = min(o, px) * (1 - abs(random.gauss(0, 0.0008)))
        ts = 1789000000 + i * step_min * 60
        out.append([f"2026-09-{1 + (i // 25) % 28:02d}T{9 + (i % 25) // 4:02d}:{(i % 4) * 15:02d}:00+05:30", o, h, l, px, 100])
    return out

class FakeCandles:
    def __init__(self): self.calls = 0
    def series(self, key, tf):
        self.calls += 1
        if key == "NSE_EQ|SHORT":
            return {"candles": make(20)}
        return {"candles": make(700 if tf != "D" else 300)}
FC = FakeCandles()
S = structure.Structure(FC, lambda label: {"NIFTY 50": "NSE_INDEX|Nifty 50", "NSE:RELIANCE": "NSE_EQ|INE002A01018", "NSE:SHORT": "NSE_EQ|SHORT"}.get(label), ttl=60)
v = S.view("NIFTY 50", "15m", 120)
check("view: engine output in the chart shape", "series" in v and "pa" in v and "summary" in v and v["tf"] == "15m" and len(v["series"]["t"]) == 120 and v["signal"] and "systems" in v)
check("view: summary fields", set(v["summary"]) >= {"structure", "structure_word", "last_event", "range", "nearest_demand", "nearest_supply", "liquidity_above", "liquidity_below"})
check("view: markers/zones indices shifted into the window", all(0 <= m["i"] < 120 for m in v["markers"]) and all(0 <= e["i"] < 120 for e in v["pa"]["events"]))
n0 = FC.calls
S.view("NIFTY 50", "15m", 80)
check("view: cached per (key, tf)", FC.calls == n0)
check("view: stock label resolves, daily tf maps", "series" in S.view("NSE:RELIANCE", "D", 100) and S.view("NSE:RELIANCE", "D", 100)["tf"] == "D")
check("view: unknown symbol / too few candles", "error" in S.view("NSE:XYZ", "15m") and "error" in S.view("NSE:SHORT", "15m"))
check("to_ms handles iso with offset", structure.to_ms([["2026-09-15T09:15:00+05:30", 1, 2, 0.5, 1.5, 3]])[0][0] == 1789443900000)
check("slice_view keeps full when bars >= n", len(gold.slice_view(gold.analyze(structure.to_ms(make(120)), "15m"), 500)["series"]["t"]) == 120)

# alerts
check("alerts: struct families parse", alerts.parse_extra("struct:NIFTY 50:15m") == ("struct", ["NIFTY 50", "15m"]) and alerts.parse_extra("structdir:NSE:RELIANCE:1h") == ("structdir", ["NSE", "RELIANCE", "1h"]) or alerts.parse_extra("structdir:BANKNIFTY:D") == ("structdir", ["BANKNIFTY", "D"]))
check("alerts: struct rejects bad tf", alerts.parse_extra("struct:NIFTY 50:2h") is None)
check("alerts: labels", "engine score" in alerts.metric_label("struct:NIFTY 50:15m", None) and "structure" in alerts.metric_label("structdir:BANKNIFTY:D", None))
ok, err = alerts.validate({"metric": "structdir:NIFTY 50:15m", "cmp": "<=", "value": -1})
check("alerts: validate structdir", ok and ok["value"] == -1, err)

# pages
doc = pages.render_dashboard({}).decode()
for m in ('id="p-struct"', "/api/struct?u=", "['struct','Market structure']", "STRUCT:'struct'", "window.finoPA=", "id:'structdir:NIFTY 50:15m'"):
    check("dashboard has " + m, m in doc)
g = pages_global.render().decode()
check("global terminal uses the shared renderer once", g.count("window.finoPA=") == 1 and "finoPA.draw(" in g and "function drawGold(){ var r=window.finoPA" in g)
check("chart_pa is self-contained", "function draw(cv,d,o)" in chart_pa.JS and "gd." not in chart_pa.JS)
# ---- VIP Indicator product
import vip_page, payments, guest
check("vip: price + label", payments.PRODUCTS["vip"] == 12999 and payments.valid_item("vip", "lifetime") and payments.PRODUCT_APP["vip"] == "/vip-indicator/app")
sales = vip_page.render_sales({"NIFTY 15m": "BUY", "NIFTY 1D": "NEUTRAL"}, True).decode()
for m in ('"@type":"Product"', '"price":"12999"', "/vip-indicator/buy", "VIP Indicator", "ENGINE NOW", "Pine Script", "Not investment advice", "STRUCT panel"):
    check("vip sales has " + m, m in sales)
check("vip sales: no old name", "Sovereign" not in sales.replace("XAU Sovereign", "").replace("xau-sovereign", ""))
buy = guest.render("vip", "lifetime").decode()
check("vip buy page", 'data-plan="vip"' in buy and "₹12,999" in buy and 'id="gc-cyc"' not in buy and "Buy VIP Indicator" in buy)
app_locked = vip_page.render_app(locked=True, signed_in=False).decode()
check("vip app locked", "FINO_LOCKED=true" in app_locked and "Buy VIP Indicator" in app_locked and 'id="p-struct"' in app_locked and 'id="p-risk"' not in app_locked and "window.finoPA=" in app_locked)
app_open = vip_page.render_app(locked=False, signed_in=True, pine=True).decode()
check("vip app open with pine", "FINO_PINE=true" in app_open and "/vip-indicator/pine" in app_open and "loadStx" in app_open and "FINO_LOCKED=true" not in app_open)
pine = vip_page.pine_for("buyer@example.com").decode()
check("vip pine", pine.startswith("//@version=5") and 'shorttitle="VIP INDICATOR"' in pine and "buyer@example.com" in pine and "XAU" not in pine and pine.count("(") == pine.count(")"))

print("fails:", fails)
sys.exit(1 if fails else 0)
