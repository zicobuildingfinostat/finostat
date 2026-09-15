"""RISK board: the whole book (paper, algo and broker positions, already marked by book.mark) seen the way
a desk sees it — net Greeks in ₹ terms per underlying and per expiry, a spot × IV shock grid, expiry
payoff extremes, a hedge-to-flat suggestion, margin, and limits with breach flags."""
from __future__ import annotations

import time

import bs

SPOT_SHIFTS = [-3, -2, -1, -0.5, 0, 0.5, 1, 2, 3]
IV_SHIFTS = [-4, -2, 0, 2, 4]
DAYS_AHEAD = [0, 1]
DEFAULT_LIMITS = {"delta_inr_1pct": 25000, "gamma_inr_1pct": 25000, "vega": 5000, "theta": 15000, "day_loss": 50000}
LIMIT_KEYS = tuple(DEFAULT_LIMITS)


def clean_limits(raw) -> dict:
    out = dict(DEFAULT_LIMITS)
    if isinstance(raw, dict):
        for k in LIMIT_KEYS:
            try:
                v = float(raw.get(k, out[k]))
            except (TypeError, ValueError):
                continue
            if 0 < v < 1e9:
                out[k] = round(v, 0)
    return out


def _inr(g: dict, spot: float) -> dict:
    """Greeks (already scaled by quantity) -> rupee sensitivities."""
    move = spot * 0.01
    return {"delta_inr_1pct": round(g["delta"] * move, 0), "gamma_inr_1pct": round(0.5 * g["gamma"] * move * move, 0),
            "vega": round(g["vega"], 0), "theta": round(g["theta"], 0)}


def expiry_payoff(positions: list[dict], spot: float, span: float = 0.06, points: int = 61) -> dict | None:
    """Aggregate P&L at expiry (vs current marks) across spot × (1 ± span) for one (underlying, expiry)."""
    legs = [(l["right"], l["strike"], l["mult"], l["mark"]) for p in positions for l in p["legs"] if l["mark"] is not None]
    if not legs or not spot:
        return None
    xs = [spot * (1 - span + 2 * span * i / (points - 1)) for i in range(points)]
    ys = []
    for x in xs:
        v = 0.0
        for right, k, mult, mark in legs:
            intrinsic = max(x - k, 0.0) if right == "CE" else max(k - x, 0.0)
            v += (intrinsic - mark) * mult
        ys.append(v)
    bes = []
    for a, b, ya, yb in zip(xs, xs[1:], ys, ys[1:]):
        if (ya < 0 <= yb) or (ya >= 0 > yb):
            bes.append(round(a + (b - a) * (-ya) / ((yb - ya) or 1), 0))
    return {"max_profit": round(max(ys), 0), "max_loss": round(min(ys), 0), "breakevens": bes[:4],
            "at_spot": round(ys[points // 2], 0), "curve": [[round(x, 0), round(y, 0)] for x, y in zip(xs, ys)][::3]}


def hedge_for(delta: float, spot: float, lot: int) -> dict | None:
    """What flattens delta: futures lots (rounded) and the ATM-option alternative (~0.5 delta)."""
    if not lot or abs(delta) < lot * 0.1:
        return None
    fut = -delta / lot
    opt = -delta / (0.5 * lot)
    ro = round(opt)
    return {"futures_lots": round(fut), "futures_side": "BUY" if fut > 0 else "SELL",
            "atm_option_lots": ro, "atm_option": ("BUY CE" if ro > 0 else "BUY PE") if ro != 0 else None,
            "residual_inr_1pct": round((delta + round(fut) * lot) * spot * 0.01, 0)}


def shocks(marked: list[dict], spot_shifts=None, iv_shifts=None, days=None) -> dict:
    spot_shifts, iv_shifts, days = spot_shifts or SPOT_SHIFTS, iv_shifts or IV_SHIFTS, days or DAYS_AHEAD
    grid = {d: [[0.0 for _ in spot_shifts] for _ in iv_shifts] for d in days}
    for p in marked:
        if not p.get("priced") or not p.get("spot"):
            continue
        for leg in p["legs"]:
            if leg["mark"] is None or not leg.get("iv"):
                continue
            iv0 = leg["iv"] / 100.0
            for di, dv in enumerate(iv_shifts):
                for si, ds in enumerate(spot_shifts):
                    for d in days:
                        t = max(p["t_years"] - d / 365.0, 0.0)
                        px = bs.price(p["spot"] * (1 + ds / 100.0), leg["strike"], t, max(iv0 + dv / 100.0, 0.01), leg["right"])
                        grid[d][di][si] += (px - leg["mark"]) * leg["mult"]
    worst = min((v for d in days for row in grid[d] for v in row), default=0.0)
    return {"spot_shifts": spot_shifts, "iv_shifts": iv_shifts, "days": days,
            "grid": {str(d): [[round(v, 0) for v in row] for row in grid[d]] for d in days}, "worst": round(worst, 0)}


def board(marked: list[dict], quotes: list[dict], funds: dict | None = None, limits: dict | None = None, now: float | None = None) -> dict:
    now = now or time.time()
    limits = clean_limits(limits)
    prev_spot = {}
    for q in quotes or []:
        if q.get("price") and q.get("change") is not None and q["change"] > -100:
            prev_spot[q["symbol"]] = q["price"] / (1 + q["change"] / 100.0)
    tot = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    by_u: dict[str, dict] = {}
    by_exp: dict[tuple, dict] = {}
    pnl = day = 0.0
    for p in marked:
        pnl += p.get("pnl") or 0.0
        day += p.get("day_pnl") or 0.0
        u = p["u"]
        gu = by_u.setdefault(u, {"u": u, "spot": p.get("spot"), "lot": p.get("lot") or 1, "positions": 0, "lots": 0, "unpriced": 0,
                                 "greeks": {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}, "sources": set()})
        ge = by_exp.setdefault((u, p["expiry"]), {"u": u, "expiry": p["expiry"], "spot": p.get("spot"), "positions": [], "lots": 0,
                                                  "greeks": {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}, "t_years": p.get("t_years") or 0.0})
        gu["positions"] += 1
        gu["lots"] += int(p.get("lots") or 0)
        gu["sources"].add(p.get("source", "paper"))
        if not p.get("priced"):
            gu["unpriced"] += 1
        ge["positions"].append(p)
        ge["lots"] += int(p.get("lots") or 0)
        for k in tot:
            v = float((p.get("greeks") or {}).get(k) or 0.0)
            tot[k] += v
            gu["greeks"][k] += v
            ge["greeks"][k] += v
    underlyings = []
    for u, g in by_u.items():
        spot = g["spot"] or 0.0
        inr = _inr(g["greeks"], spot) if spot else {k: 0 for k in ("delta_inr_1pct", "gamma_inr_1pct", "vega", "theta")}
        underlyings.append({"u": u, "spot": spot, "lot": g["lot"], "positions": g["positions"], "lots": g["lots"], "unpriced": g["unpriced"],
                            "sources": sorted(g["sources"]), "greeks": {k: round(v, 2) for k, v in g["greeks"].items()}, **inr,
                            "hedge": hedge_for(g["greeks"]["delta"], spot, g["lot"]) if spot else None,
                            "day_move_pct": round((spot / prev_spot[u] - 1) * 100, 2) if spot and u in prev_spot else None})
    underlyings.sort(key=lambda x: -abs(x["delta_inr_1pct"]))
    expiries = []
    for (u, exp), g in by_exp.items():
        spot = g["spot"] or 0.0
        inr = _inr(g["greeks"], spot) if spot else {k: 0 for k in ("delta_inr_1pct", "gamma_inr_1pct", "vega", "theta")}
        expiries.append({"u": u, "expiry": exp, "dte": round(max(0.0, (exp / 1000 - now) / 86400), 1) if exp else None, "positions": len(g["positions"]), "lots": g["lots"],
                         "greeks": {k: round(v, 2) for k, v in g["greeks"].items()}, **inr, "payoff": expiry_payoff(g["positions"], spot) if spot else None})
    expiries.sort(key=lambda x: (x["u"], x["expiry"] or 0))
    # book-level ₹ terms: sum of per-underlying rupee terms (spots differ, so not one spot)
    book_inr = {k: round(sum(x[k] for x in underlyings), 0) for k in ("delta_inr_1pct", "gamma_inr_1pct", "vega", "theta")}
    breaches = []
    if abs(book_inr["delta_inr_1pct"]) > limits["delta_inr_1pct"]:
        breaches.append({"key": "delta_inr_1pct", "value": book_inr["delta_inr_1pct"], "limit": limits["delta_inr_1pct"], "note": "net delta beyond limit — hedge with futures or an ATM option"})
    if abs(book_inr["gamma_inr_1pct"]) > limits["gamma_inr_1pct"]:
        breaches.append({"key": "gamma_inr_1pct", "value": book_inr["gamma_inr_1pct"], "limit": limits["gamma_inr_1pct"], "note": "gamma too large for a 1% move — reduce near-expiry ATM exposure"})
    if abs(book_inr["vega"]) > limits["vega"]:
        breaches.append({"key": "vega", "value": book_inr["vega"], "limit": limits["vega"], "note": "vega beyond limit — a 1-pt IV move costs more than you set"})
    if abs(book_inr["theta"]) > limits["theta"]:
        breaches.append({"key": "theta", "value": book_inr["theta"], "limit": limits["theta"], "note": "daily theta beyond limit"})
    if day < -limits["day_loss"]:
        breaches.append({"key": "day_loss", "value": round(day, 0), "limit": limits["day_loss"], "note": "day loss past the stop — square off or hedge"})
    sh = shocks(marked)
    margin = None
    if funds and (funds.get("available") is not None or funds.get("used") is not None):
        try:
            avail, used = float(funds.get("available") or 0), float(funds.get("used") or 0)
            margin = {"available": round(avail, 0), "used": round(used, 0), "used_pct": round(100 * used / (avail + used), 1) if (avail + used) > 0 else None}
        except (TypeError, ValueError):
            margin = None
    return {"asof": now, "positions": len(marked), "unpriced": sum(1 for p in marked if not p.get("priced")),
            "pnl": round(pnl, 0), "day_pnl": round(day, 0), "greeks": {k: round(v, 2) for k, v in tot.items()}, "inr": book_inr,
            "limits": limits, "breaches": breaches, "underlyings": underlyings, "expiries": expiries, "shocks": sh, "margin": margin}
