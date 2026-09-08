"""Strategy builder maths: presets, payoff at expiry, breakevens, max P&L, greeks.

Legs are dicts {right: CE|PE, strike, qty, price} where qty is in lots, positive
for long and negative for short, and price is the option's last price per
share. Everything is per share until the caller multiplies by the lot size.
"""
from __future__ import annotations

import bs

PRESETS = {
    "short-straddle":   ("Short straddle",   [("CE", 0, -1), ("PE", 0, -1)]),
    "long-straddle":    ("Long straddle",    [("CE", 0, 1), ("PE", 0, 1)]),
    "short-strangle":   ("Short strangle",   [("CE", 2, -1), ("PE", -2, -1)]),
    "long-strangle":    ("Long strangle",    [("CE", 2, 1), ("PE", -2, 1)]),
    "iron-condor":      ("Iron condor",      [("PE", -2, -1), ("PE", -4, 1), ("CE", 2, -1), ("CE", 4, 1)]),
    "iron-fly":         ("Iron fly",         [("CE", 0, -1), ("PE", 0, -1), ("CE", 2, 1), ("PE", -2, 1)]),
    "bull-call-spread": ("Bull call spread", [("CE", 0, 1), ("CE", 2, -1)]),
    "bear-put-spread":  ("Bear put spread",  [("PE", 0, 1), ("PE", -2, -1)]),
    "butterfly":        ("Call butterfly",   [("CE", -2, 1), ("CE", 0, -2), ("CE", 2, 1)]),
    "ratio-spread":     ("Call ratio 1x2",   [("CE", 0, 1), ("CE", 2, -2)]),
}


def preset_legs(name: str, atm: int, step: int, strikes: list[int]) -> list[dict] | None:
    """Instantiate a preset on a real strike ladder; None if any strike is missing."""
    spec = PRESETS.get(name)
    if spec is None:
        return None
    legs = []
    for right, offset, qty in spec[1]:
        k = atm + offset * step
        if k not in strikes:
            return None
        legs.append({"right": right, "strike": k, "qty": qty})
    return legs


def _intrinsic(right: str, strike: float, s: float) -> float:
    return max(0.0, s - strike) if right == "CE" else max(0.0, strike - s)


def payoff_at(legs: list[dict], s: float) -> float:
    """Per-share P&L at expiry for underlying price s (premiums included)."""
    pnl = 0.0
    for l in legs:
        q = l["qty"]
        pnl += q * (_intrinsic(l["right"], l["strike"], s) - l["price"])
    return pnl


def evaluate(spot: float, legs: list[dict], lot: int = 1, t_years: float | None = None,
             ivs: dict | None = None, points: int = 81) -> dict:
    """Net premium, max profit/loss (or unbounded), breakevens, payoff curve, greeks.

    `ivs` maps (right, strike) -> implied vol, used only for greeks.
    """
    if not legs:
        return {"error": "no legs"}
    strikes = [l["strike"] for l in legs]
    lo = min(min(strikes), spot) * 0.85
    hi = max(max(strikes), spot) * 1.15
    xs = [lo + (hi - lo) * i / (points - 1) for i in range(points)]
    ys = [payoff_at(legs, x) for x in xs]          # for drawing only

    # Payoff at expiry is piecewise-linear with kinks at the strikes, so the
    # extrema and breakevens are exact on the kink points -- no grid error.
    kinks = sorted({lo, hi, *strikes})
    kys = [payoff_at(legs, k) for k in kinks]
    up_slope = sum(l["qty"] for l in legs if l["right"] == "CE")
    down_slope = -sum(l["qty"] for l in legs if l["right"] == "PE")
    max_profit = max(kys); max_loss = min(kys)
    unlimited_profit = up_slope > 0 or down_slope < 0
    unlimited_loss = up_slope < 0 or down_slope > 0

    bes = []
    for i in range(1, len(kinks)):
        y0, y1 = kys[i - 1], kys[i]
        if abs(y0) < 1e-9:
            bes.append(kinks[i - 1])
        elif (y0 < 0 < y1) or (y0 > 0 > y1):
            bes.append(kinks[i - 1] + (kinks[i] - kinks[i - 1]) * (-y0) / (y1 - y0))
    if abs(kys[-1]) < 1e-9:
        bes.append(kinks[-1])
    bes = sorted({round(b, 1) for b in bes})

    net = -sum(l["qty"] * l["price"] for l in legs)   # >0 credit received, <0 debit paid
    out = {
        "net_premium": round(net, 2),
        "net_premium_lot": round(net * lot, 2),
        "max_profit": None if unlimited_profit else round(max_profit, 2),
        "max_loss": None if unlimited_loss else round(max_loss, 2),
        "max_profit_lot": None if unlimited_profit else round(max_profit * lot, 2),
        "max_loss_lot": None if unlimited_loss else round(max_loss * lot, 2),
        "breakevens": bes,
        "payoff": [[round(x, 1), round(y * lot, 2)] for x, y in zip(xs, ys)],
        "lot": lot,
    }
    if t_years is not None and ivs:
        tot = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        for l in legs:
            iv = ivs.get((l["right"], l["strike"]))
            if iv is None:
                continue
            g = bs.greeks(spot, l["strike"], t_years, iv, l["right"])
            for k in tot:
                tot[k] += l["qty"] * g[k]
        out["greeks"] = {k: round(v * lot, 3) for k, v in tot.items()}
    return out
