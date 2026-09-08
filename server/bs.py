"""Black-Scholes pricing, implied volatility and greeks. Standard library only.

Used to derive IV and greeks from streamed option prices, because Upstox's
greeks feed mode would shrink our LTPC budget to 2,000 instruments. Indian
index and stock options are European-style, so BS is the right model; rates
use a flat risk-free assumption and no dividends.
"""
from __future__ import annotations

import math

RISK_FREE = 0.065          # rough Indian 91-day T-bill; the builder's sensitivity to it is tiny
DAY = 86400.0


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def price(spot: float, strike: float, t: float, vol: float, right: str, r: float = RISK_FREE) -> float:
    """t in years, vol as a decimal, right 'CE' or 'PE'."""
    if t <= 0 or vol <= 0:
        return max(0.0, (spot - strike) if right == "CE" else (strike - spot))
    sd = vol * math.sqrt(t)
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t) / sd
    d2 = d1 - sd
    disc = math.exp(-r * t)
    if right == "CE":
        return spot * _ncdf(d1) - strike * disc * _ncdf(d2)
    return strike * disc * _ncdf(-d2) - spot * _ncdf(-d1)


def implied_vol(target: float, spot: float, strike: float, t: float, right: str,
                r: float = RISK_FREE) -> float | None:
    """Bisection on vol in [0.5%, 500%]; None when the price is outside no-arbitrage bounds."""
    if t <= 0 or target <= 0 or spot <= 0 or strike <= 0:
        return None
    intrinsic = max(0.0, (spot - strike * math.exp(-r * t)) if right == "CE" else (strike * math.exp(-r * t) - spot))
    if target < intrinsic - 1e-9:
        return None
    lo, hi = 0.005, 5.0
    if price(spot, strike, t, hi, right, r) < target:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if price(spot, strike, t, mid, right, r) < target:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-6:
            break
    return 0.5 * (lo + hi)


def greeks(spot: float, strike: float, t: float, vol: float, right: str, r: float = RISK_FREE) -> dict:
    """delta, gamma, theta (per calendar day), vega (per 1 vol point), rho (per 1%)."""
    if t <= 0 or vol <= 0:
        itm = (spot > strike) if right == "CE" else (spot < strike)
        return {"delta": (1.0 if right == "CE" else -1.0) if itm else 0.0, "gamma": 0.0,
                "theta": 0.0, "vega": 0.0, "rho": 0.0}
    sd = vol * math.sqrt(t)
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t) / sd
    d2 = d1 - sd
    disc = math.exp(-r * t)
    pdf = _npdf(d1)
    gamma = pdf / (spot * sd)
    vega = spot * pdf * math.sqrt(t) / 100.0
    if right == "CE":
        delta = _ncdf(d1)
        theta = (-spot * pdf * vol / (2 * math.sqrt(t)) - r * strike * disc * _ncdf(d2)) / 365.0
        rho = strike * t * disc * _ncdf(d2) / 100.0
    else:
        delta = _ncdf(d1) - 1.0
        theta = (-spot * pdf * vol / (2 * math.sqrt(t)) + r * strike * disc * _ncdf(-d2)) / 365.0
        rho = -strike * t * disc * _ncdf(-d2) / 100.0
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}


def years_to(expiry_epoch_ms: float, now_epoch: float) -> float:
    """Time to expiry in years, expiry taken at 15:30 IST on the expiry date."""
    exp = expiry_epoch_ms / 1000.0
    # Upstox stamps expiry at 23:59:59 IST on the expiry date; trading ends at
    # 15:30 IST, 8.5 hours before that stamp.
    exp_close = exp - 8.5 * 3600.0
    return max(0.0, (exp_close - now_epoch) / (365.0 * DAY))
