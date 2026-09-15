"""VIP package engines: scalper, seller, footprint/profile, engine dispatch in Structure, Pine downloads."""
import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import scalper, seller, footprint, structure, gold, alerts, vip_page, pages, pages_global

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

random.seed(11)
def make(n, step_min=5, start=23000.0, vol=True):
    px, out = start, []
    for i in range(n):
        drift = 0.0008 if (i // 120) % 2 == 0 else -0.0005
        px *= 1 + drift + random.gauss(0, 0.0015)
        o = px * (1 + random.gauss(0, 0.0006)); h = max(o, px) * (1 + abs(random.gauss(0, 0.0006))); l = min(o, px) * (1 - abs(random.gauss(0, 0.0006)))
        out.append([1789400000000 + i * step_min * 60000, o, h, l, px, (100 + random.random() * 50) if vol else 0])
    return out
c = make(700)

# scalper
a = scalper.analyze(c, "5m")
check("scalper: shape + signal words", a["engine"] == "scalp" and a["signal"] in ("LONG", "SHORT", "FLAT") and len(a["kpis"]) == 7 and a["series"]["s200"] and len(a["markers"]) > 3)
check("scalper: stop on the right side, 1.5R target", a["direction"] == 0 or ((a["stop"] < a["entry"] < a["target"]) if a["direction"] == 1 else (a["target"] < a["entry"] < a["stop"])))
check("scalper: non-repainting", scalper.analyze(c[:-30], "5m")["series"]["state"] == a["series"]["state"][:670])
vw = scalper.session_vwap([[1789400000000 + i * 60000, 100, 101, 99, 100 + i % 3, 10] for i in range(5)])
check("scalper: vwap resets per day and stays inside range", len(vw) == 5 and 99 <= vw[-1] <= 101)

# seller
b = seller.analyze(c, "15m", {"iv_percentile": 72, "realised_vs_expected_pct": 60, "em_day": 150}, step=50)
check("seller: shape + strikes on the step", b["engine"] == "seller" and b["call_strike"] % 50 == 0 and b["put_strike"] % 50 == 0 and b["put_strike"] < b["entry"] < b["call_strike"] and len(b["kpis"]) == 8)
check("seller: extras voted", any(s["key"] == "ivp" and s["vote"] == 1 for s in b["systems"]) and any(s["key"] == "rvsx" and s["vote"] == 1 for s in b["systems"]))
check("seller: signal vocabulary", b["signal"] in ("SELL STRADDLE", "SELL CALLS", "SELL PUTS", "STAND ASIDE", "NEUTRAL") and all(m["side"] in ("BUY", "SELL", "EXIT") and "label" in m for m in b["markers"]))
check("seller: levels only while selling", (b["direction"] == 1) == bool(b["levels"]))
b2 = seller.analyze(c, "15m", None, step=None)
check("seller: works without extras / step", "error" not in b2 and b2["call_strike"] > b2["put_strike"])

# footprint / profile
fp = footprint.footprint(c[-50:])
check("footprint: rows with bins, delta, cvd", fp["has_volume"] and len(fp["rows"]) == 50 and len(fp["rows"][0][2]) == 4 and len(fp["cvd"]) == 50 and abs(sum(fp["rows"][0][2]) - c[-50][5]) < 0.6)
bs_ = footprint.bar_split(100, 110, 90, 110, 1000)
check("footprint: close at high = all buying", bs_ == (1000.0, 0.0))
pr = footprint.profile(c[-100:])
check("profile: poc inside value area inside range", pr and pr["lo"] <= pr["val"] <= pr["poc"] <= pr["vah"] <= pr["hi"] and abs(sum(pr["vol"]) - pr["total"]) < 1)
check("footprint: no volume -> flagged", not footprint.footprint(make(30, vol=False))["has_volume"] and footprint.profile(make(30, vol=False)) is None)
v = footprint.attach(gold.slice_view(gold.analyze(c, "5m"), 100))
check("attach: fp rows match the sliced window", len(v["fp"]["rows"]) == 100 and v["profile"])

# dispatch
class FC:
    def series(self, key, tf): return {"candles": [[f"2026-09-{1 + (i // 75) % 28:02d}T{9 + (i % 75) // 12:02d}:{(i % 12) * 5:02d}:00+05:30", k[1], k[2], k[3], k[4], k[5]] for i, k in enumerate(c)]}
S = structure.Structure(FC(), lambda l: "NSE_INDEX|Nifty 50" if l == "NIFTY 50" else None, extras_fn=lambda u: {"iv_percentile": 65, "em_day": 120})
for e in ("struct", "scalp", "seller"):
    d = S.view("NIFTY 50", "15m", 120, e)
    check(f"dispatch {e}: engine tag, fp + profile attached, window", d.get("engine") == e and d["fp"]["has_volume"] and d["profile"] and len(d["series"]["t"]) == 120)
check("dispatch: seller got index extras", any(s["key"] == "ivp" for s in S.view("NIFTY 50", "15m", 120, "seller")["systems"]))

# alerts + pine + pages
check("alerts: scalp/seller kinds", alerts.parse_extra("scalp:NIFTY 50:5m") and alerts.parse_extra("seller:BANKNIFTY:15m") and "scalper" in alerts.metric_label("scalp:NIFTY 50:5m", None))
for w, fn in (("struct", "vip-structure.pine"), ("scalp", "vip-scalper.pine"), ("seller", "vip-seller.pine")):
    p = vip_page.pine_for("x@y.z", w).decode()
    check(f"pine {w}: v5, licensed, balanced", p.startswith("//@version=5") and "x@y.z" in p and p.count("(") == p.count(")") and vip_page.PINES[w][0] == fn and "alertcondition(" in p)
check("pine scalper/seller titles", 'shorttitle="VIP SCALPER"' in vip_page.PINE_SCALP and 'shorttitle="VIP SELLER"' in vip_page.PINE_SELLER)
doc = pages.render_dashboard({}).decode()
for m in ('id="stx-eng"', 'data-e="seller"', 'data-l="fp"', "engine='+stx.engine", "id:'seller:NIFTY 50:15m'", "id:'scalp:NIFTY 50:5m'", "volume delta · CVD"):
    check("dashboard has " + m, m in doc)
app = vip_page.render_app(locked=False, signed_in=True, pine=True).decode()
check("vip app: three pine links + engines", "which=scalp" in app and "which=seller" in app and 'data-e="scalp"' in app and "FOOTPRINT" in app)
g = pages_global.render().decode()
check("global gold panel has footprint layers", 'data-l="fp"' in g and "fp:true" in g)
print("fails:", fails)
sys.exit(1 if fails else 0)
