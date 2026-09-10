"""Analytics maths on synthetic chains: smile fit, surface grid, implied distribution, dealer gamma;
history engine (legs, backtest arithmetic) on synthetic candles with a fake REST client."""
import sys, pathlib, tempfile, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import bs, analytics as A, history as H, upstox_rest as UR
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

SPOT, T = 24000.0, 7 / 365
def vol_of(k):                       # a put-skewed smile: higher IV below spot
    m = math.log(k / SPOT) * 100
    return 14.0 - 0.45 * m + 0.03 * m * m
def chain(oi=True):
    rows = []
    for k in range(23000, 25050, 50):
        v = vol_of(k) / 100
        row = {"strike": k}
        for right in ("CE", "PE"):
            g = bs.greeks(SPOT, k, T, v, right)
            row[right.lower()] = {"ltp": round(bs.price(SPOT, k, T, v, right), 2), "iv": round(v * 100, 2), "delta": g["delta"], "gamma": g["gamma"],
                                 "oi": (int(1e5 * math.exp(-((k - SPOT) / 400) ** 2)) + (90000 if (right == "CE" and k > SPOT) else 50000 if (right == "PE" and k < SPOT) else 0)) if oi else 0}
        rows.append(row)
    return rows

print("=== smile ===")
sm = A.smile(chain(), SPOT, T)
check("ATM IV ~14", sm["atm_iv"] is not None and abs(sm["atm_iv"] - 14.0) < 0.3, sm["atm_iv"])
check("fit recovers the skew (negative slope, positive curvature)", sm["fit"] and sm["fit"][1] < 0 and sm["fit"][2] > 0, sm["fit"])
check("risk reversal positive (puts richer than calls)", sm["rr25"] is not None and sm["rr25"] > 0, sm["rr25"])
check("moneyness sign and residuals near zero on a smooth smile", all((p["m"] < 0) == (p["strike"] < SPOT) for p in sm["points"]) and max(abs(p["rich"]) for p in sm["points"] if p["rich"] is not None) < 0.6)
lost = [dict(r, ce=None) if r["strike"] > 24600 else r for r in chain()]
check("missing sides tolerated", A.smile(lost, SPOT, T)["atm_iv"] is not None)

print("\n=== surface ===")
sf = A.surface([{"expiry": "2026-09-15", "label": "15 Sep", "rows": chain(), "spot": SPOT, "t": T}, {"expiry": "2026-09-22", "label": "22 Sep", "rows": chain(), "spot": SPOT, "t": 2 * T}])
check("two expiry rows × 13 moneyness columns", len(sf["rows"]) == 2 and all(len(r["cells"]) == 13 for r in sf["rows"]))
mid = sf["rows"][0]["cells"][6]
check("ATM column ≈ 14 IV, rich ≈ 0", mid["iv"] is not None and abs(mid["iv"] - 14) < 0.4 and abs(mid["rich"]) < 0.5, mid)
check("cells outside the strike range are blank", sf["rows"][0]["cells"][0]["iv"] is None and sf["rows"][0]["cells"][12]["iv"] is None)
check("term structure carries ATM IV per expiry and ranges", len(sf["term"]) == 2 and sf["iv_range"] and sf["rich_max"] is not None)

print("\n=== distribution ===")
d = A.distribution(chain(), SPOT, T)
check("density integrates to one and is centred near spot", d and abs(sum(d["pdf"]) * (d["x"][1] - d["x"][0]) / SPOT - 1) < 0.03 and abs(d["mean"] - SPOT) < SPOT * 0.01, d and (d["mean"], sum(d["pdf"]) * (d["x"][1] - d["x"][0]) / SPOT))
check("std ≈ spot·σ·√T (within 15%)", d and abs(d["std"] - SPOT * 0.14 * math.sqrt(T)) / (SPOT * 0.14 * math.sqrt(T)) < 0.15, d and d["std"])
dx = d["x"][1] - d["x"][0]
far = SPOT - 2 * d["expected_move"]
imp_left2 = sum(p for x, p in zip(d["x"], d["pdf"]) if x < far) * dx / SPOT
ln_left2 = sum(p for x, p in zip(d["x"], d["lognormal"]) if x < far) * dx / SPOT
check("put skew: implied far-left tail (beyond 2σ) fatter than the no-skew lognormal's", d and imp_left2 > ln_left2 * 1.2, d and (imp_left2, ln_left2))
check("percentiles ordered; p_up between 0.3 and 0.7", d and d["p05"] < d["p16"] < d["p50"] < d["p84"] < d["p95"] and 0.3 < d["p_up"] < 0.7)
check("no IVs -> None", A.distribution([{"strike": 24000, "ce": {"ltp": 1}, "pe": {"ltp": 1}}], SPOT, T) is None)

print("\n=== gex ===")
g = A.gex(chain(), SPOT, 65, T)
check("calls positive, puts negative, cumulative and flip present", g and all(x["call"] >= 0 and x["put"] <= 0 for x in g["strikes"]) and "cum" in g["strikes"][0] and g["flip"] is not None)
check("largest + is above spot (call OI heavier there), largest − below", g and g["max_pos"]["strike"] >= SPOT and g["max_neg"]["strike"] <= SPOT, g and (g["max_pos"], g["max_neg"]))
check("no OI -> None", A.gex(chain(oi=False), SPOT, 65, T) is None)

print("\n=== chain OI merge (REST into socket rows) ===")
import chains as CH
sock = [{"strike": 24000, "atm": True, "ce": {"ltp": 100.0, "iv": 12.0, "oi": None, "oi_chg": None, "vol": None, "bid": None, "ask": None}, "pe": {"ltp": 98.0, "iv": None, "oi": None, "vol": None, "bid": None, "ask": None}},
        {"strike": 24050, "atm": False, "ce": None, "pe": {"ltp": 120.0, "iv": 12.5, "oi": 777, "oi_chg": 5, "vol": 9, "bid": 119, "ask": 121}}]
rest = [{"strike": 24000, "ce": {"ltp": 100.5, "iv": 12.2, "oi": 500000, "oi_chg": 12000, "vol": 3000, "bid": 100, "ask": 101}, "pe": {"ltp": 98.2, "iv": 13.1, "oi": 400000, "oi_chg": -8000, "vol": 2500, "bid": 98, "ask": 99}},
        {"strike": 24050, "ce": {"ltp": 80, "iv": 12, "oi": 1, "oi_chg": 0, "vol": 1, "bid": 1, "ask": 2}, "pe": {"ltp": 121, "iv": 12.6, "oi": 999, "oi_chg": 1, "vol": 1, "bid": 1, "ask": 2}}]
n = CH.merge_rest_oi(sock, rest)
check("two empty sides filled with OI/ΔOI/vol/bid/ask; existing socket OI untouched; missing IV taken, own IV kept",
      n == 2 and sock[0]["ce"]["oi"] == 500000 and sock[0]["ce"]["oi_chg"] == 12000 and sock[0]["ce"]["oi_since"] == "prev close" and sock[0]["ce"]["iv"] == 12.0
      and sock[0]["pe"]["iv"] == 13.1 and sock[0]["pe"]["vol"] == 2500 and sock[1]["pe"]["oi"] == 777 and sock[1]["ce"] is None, (n, sock))
summ = CH.oi_summary(sock, 24000.0)
check("oi_summary works off the merged OI (PCR, walls)", summ and summ["pcr"] is not None and summ["call_wall"] == 24000 and summ["put_wall"] == 24000, summ)

print("\n=== history engine ===")
check("legs: iron condor = 4 legs, short at ±w, long at ±2w", H.legs_for("iron_condor", 24000, 50, 2) == [("CE", 24100, -1), ("PE", 23900, -1), ("CE", 24200, 1), ("PE", 23800, 1)])
class FakeClient:
    """Synthetic day: index drifts +0.5% over the session; option premiums decay linearly to intrinsic."""
    def __init__(self): self.calls = 0
    def expired_expiries(self, u): return ["2026-08-04", "2026-08-11", "2026-08-18"]
    def expired_contracts(self, u, day):
        return [{"strike_price": k, "instrument_type": r, "instrument_key": f"X|{r}{k}|{day}", "lot_size": 65} for k in range(23500, 24600, 50) for r in ("CE", "PE")]
    def _minutes(self):
        out = []
        for h in range(9, 16):
            for m in range(60):
                t = f"{h:02d}:{m:02d}"
                if "09:15" <= t <= "15:29": out.append(t)
        return out
    def index_candles(self, u, day):
        ms = self._minutes(); n = len(ms)
        return [[f"{day}T{t}:00+05:30", 24000 + 120 * i / n, 0, 0, 24000 + 120 * i / n, 0, 0] for i, t in enumerate(ms)]
    def expired_candles(self, key, day):
        self.calls += 1
        _, sym, _ = key.split("|"); right, strike = sym[:2], int(sym[2:])
        ms = self._minutes(); n = len(ms); out = []
        for i, t in enumerate(ms):
            spot = 24000 + 120 * i / n
            intrinsic = max(0.0, spot - strike) if right == "CE" else max(0.0, strike - spot)
            tv = 80.0 * (1 - i / n) * math.exp(-abs(strike - spot) / 150)
            px = round(intrinsic + tv, 2)
            out.append([f"{day}T{t}:00+05:30", px, px, px, px, 100, 1000])
        return out
tmp = pathlib.Path(tempfile.mkdtemp())
fc = FakeClient(); hist = H.History(fc, UR.CandleStore(tmp / "history.db"))
import time as _t
r = hist.backtest("NIFTY 50", "short_straddle", "10:00", "15:15", n=3, wings=2)
for _ in range(50):
    if r["status"] != "running": break
    _t.sleep(0.1); r = hist.backtest("NIFTY 50", "short_straddle", "10:00", "15:15", n=3, wings=2)
res = r.get("result") or {}
check("backtest completes over the 3 synthetic expiries", r["status"] == "done" and res.get("stats", {}).get("n") == 3, r.get("error") or r["status"])
row = (res.get("rows") or [{}])[0]
check("short straddle on a decaying, drifting day: positive credit, P&L = (credit − exit) × lot, MAE ≤ P&L", row and row["credit"] > 0 and row["pnl"] == round(row["pnl_pts"] * 65, 0) and row["mae"] <= row["pnl_pts"], row)
check("equity curve length = n, win rate computed", len(res.get("equity", [])) == 3 and res["stats"]["win_rate"] in (0.0, 33.3, 66.7, 100.0))
calls_before = fc.calls
r2 = hist.backtest("NIFTY 50", "short_straddle", "10:00", "15:15", n=3, wings=2)
check("second run is served from cache with no candle fetches", r2["status"] == "done" and r2.get("cached") and fc.calls == calls_before)
rp = hist.replay("NIFTY 50", "2026-08-11", half=3)
for _ in range(50):
    if rp["status"] != "running": break
    _t.sleep(0.1); rp = hist.replay("NIFTY 50", "2026-08-11", half=3)
fr = (rp.get("result") or {}).get("frames") or []
check("replay: 375 frames, 7 strikes, straddle at the live ATM", rp["status"] == "done" and len(fr) == 375 and len(fr[0]["rows"]) == 7 and fr[0]["straddle"] is not None, rp.get("error") or len(fr))
try:
    hist.backtest("NIFTY 50", "nope", "10:00", "15:15"); check("unknown strategy raises", False)
except ValueError:
    check("unknown strategy raises", True)
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
