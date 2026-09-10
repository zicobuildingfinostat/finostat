"""Chain analytics for the terminal: vol smile and moneyness, the IV surface with a
rich/cheap map, the option-implied distribution (Breeden–Litzenberger on a smoothed
smile) and dealer gamma exposure. Pure functions over normalised chain rows
({strike, ce:{ltp,iv,oi,gamma,delta}, pe:{...}}), so they are unit-tested without a feed.
"""
from __future__ import annotations

import math

import bs

MONEYNESS_COLS = [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6]        # % ln(K/S) buckets for the surface


def _iv(o) -> float | None:
    if not o:
        return None
    iv = o.get("iv")
    return float(iv) if iv not in (None, 0) and 0.5 < float(iv) < 300 else None


def _fit_quadratic(xs: list[float], ys: list[float], ws: list[float] | None = None) -> tuple[float, float, float] | None:
    """Weighted least squares y = a + b x + c x^2 (normal equations; tiny systems only)."""
    n = len(xs)
    if n < 3:
        return None
    ws = ws or [1.0] * n
    s = [0.0] * 5
    t = [0.0] * 3
    for x, y, w in zip(xs, ys, ws):
        p = [1.0, x, x * x, x ** 3, x ** 4]
        for i in range(5):
            s[i] += w * p[i]
        for i in range(3):
            t[i] += w * p[i] * y
    m = [[s[0], s[1], s[2]], [s[1], s[2], s[3]], [s[2], s[3], s[4]]]
    # solve 3x3 by Gaussian elimination
    a = [row[:] + [t[i]] for i, row in enumerate(m)]
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(a[r][i]))
        a[i], a[piv] = a[piv], a[i]
        if abs(a[i][i]) < 1e-12:
            return None
        for r in range(3):
            if r != i:
                f = a[r][i] / a[i][i]
                for c in range(i, 4):
                    a[r][c] -= f * a[i][c]
    return tuple(a[i][3] / a[i][i] for i in range(3))  # type: ignore[return-value]


def smile(rows: list[dict], spot: float, t: float) -> dict:
    """IV by strike with moneyness (ln K/S in %) and delta; OTM side chosen per strike; quadratic fit in moneyness."""
    pts = []
    for r in rows:
        k = r["strike"]
        if not k or not spot:
            continue
        m = math.log(k / spot) * 100.0
        ce, pe = _iv(r.get("ce")), _iv(r.get("pe"))
        # OTM side carries the information; blend across the money so stale or parity-off
        # quotes on the two sides do not leave a step in the smile right at spot
        if ce is not None and pe is not None:
            w = 1.0 / (1.0 + math.exp(m / 0.35))          # ~1 for puts below, ~0 for calls above
            iv = w * pe + (1.0 - w) * ce
        else:
            iv = ce if ce is not None else pe
        dce = (r.get("ce") or {}).get("delta")
        dpe = (r.get("pe") or {}).get("delta")
        if dce is None and iv and t > 0:
            dce = bs.greeks(spot, k, t, iv / 100.0, "CE")["delta"]
        if dpe is None and iv and t > 0:
            dpe = bs.greeks(spot, k, t, iv / 100.0, "PE")["delta"]
        pts.append({"strike": k, "m": round(m, 3), "iv": iv, "ce_iv": ce, "pe_iv": pe, "ce_delta": dce, "pe_delta": dpe})
    have = [p for p in pts if p["iv"] is not None]
    fit = None
    if len(have) >= 4:
        ws = [1.0 / (1.0 + (p["m"] / 3.0) ** 2) for p in have]                   # trust the strikes near the money more
        fit = _fit_quadratic([p["m"] for p in have], [p["iv"] for p in have], ws)
    for p in pts:
        p["fit"] = round(fit[0] + fit[1] * p["m"] + fit[2] * p["m"] ** 2, 3) if fit else None
        p["rich"] = round(p["iv"] - p["fit"], 3) if (fit and p["iv"] is not None) else None
    atm = min(have, key=lambda p: abs(p["m"]))["iv"] if have else None
    # 25-delta risk reversal and butterfly from the fitted/observed curve
    def _iv_at_delta(target: float, side: str) -> float | None:
        cands = [(abs((p["ce_delta"] if side == "CE" else -p["pe_delta"]) - target), p["iv"]) for p in have
                 if (p["ce_delta"] if side == "CE" else p["pe_delta"]) is not None]
        return min(cands)[1] if cands else None
    c25, p25 = _iv_at_delta(0.25, "CE"), _iv_at_delta(0.25, "PE")
    return {"points": pts, "atm_iv": atm, "fit": fit, "rr25": round(p25 - c25, 2) if (c25 and p25) else None,
            "bf25": round((p25 + c25) / 2 - atm, 2) if (c25 and p25 and atm) else None,
            "skew_slope": round(fit[1], 4) if fit else None}


def _interp(xs: list[float], ys: list[float], x: float) -> float | None:
    """Linear interpolation, flat beyond the ends; xs ascending."""
    if not xs:
        return None
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else y0
    return ys[-1]


def _kernel_iv(xs: list[float], ys: list[float], x: float, bw: float = 0.6) -> float | None:
    """Gaussian-kernel smoothed IV at moneyness x (bandwidth in % moneyness). A smooth curve is what
    the density needs: piecewise-linear IV has kinks at every strike, and d²C/dK² turns each kink
    into a spike."""
    if not xs:
        return None
    if x < xs[0] - 2 * bw:
        x = xs[0] - 2 * bw                         # flat tails beyond the quoted range
    if x > xs[-1] + 2 * bw:
        x = xs[-1] + 2 * bw
    num = den = 0.0
    for xi, yi in zip(xs, ys):
        w = math.exp(-0.5 * ((x - xi) / bw) ** 2)
        num += w * yi
        den += w
    return num / den if den > 1e-9 else _interp(xs, ys, x)


def surface(chains: list[dict]) -> dict:
    """chains: [{expiry, label, rows, spot, t}] -> IV grid (expiries × moneyness) with rich/cheap residuals."""
    grid, term = [], []
    for ch in chains:
        sm = smile(ch["rows"], ch["spot"], ch["t"])
        have = [p for p in sm["points"] if p["iv"] is not None]
        have.sort(key=lambda p: p["m"])
        xs, ys = [p["m"] for p in have], [p["iv"] for p in have]
        cells = []
        for col in MONEYNESS_COLS:
            iv = _interp(xs, ys, float(col)) if have else None
            fit = sm["fit"]
            f = (fit[0] + fit[1] * col + fit[2] * col ** 2) if fit else None
            inside = bool(have) and xs[0] - 0.5 <= col <= xs[-1] + 0.5
            cells.append({"iv": round(iv, 2) if (iv is not None and inside) else None,
                          "rich": round(iv - f, 2) if (iv is not None and f is not None and inside) else None})
        grid.append({"expiry": ch["expiry"], "label": ch.get("label", ch["expiry"]), "t_days": round(ch["t"] * 365, 1), "cells": cells,
                     "atm_iv": sm["atm_iv"], "rr25": sm["rr25"], "bf25": sm["bf25"]})
        term.append({"expiry": ch["expiry"], "label": ch.get("label", ch["expiry"]), "atm_iv": sm["atm_iv"], "t_days": round(ch["t"] * 365, 1)})
    ivs = [c["iv"] for g in grid for c in g["cells"] if c["iv"] is not None]
    rich = [abs(c["rich"]) for g in grid for c in g["cells"] if c["rich"] is not None]
    return {"cols": MONEYNESS_COLS, "rows": grid, "term": term,
            "iv_range": [round(min(ivs), 2), round(max(ivs), 2)] if ivs else None,
            "rich_max": round(max(rich), 2) if rich else None}


def distribution(rows: list[dict], spot: float, t: float, r: float = bs.RISK_FREE, n: int = 241) -> dict | None:
    """Risk-neutral density via Breeden–Litzenberger: price a dense strip of calls off the
    smoothed smile (linear in moneyness, flat tails), then take d²C/dK². Also the lognormal
    (flat ATM vol) reference and the summary numbers a trader reads off the curve."""
    if not spot or t <= 0:
        return None
    sm = smile(rows, spot, t)
    have = sorted([p for p in sm["points"] if p["iv"] is not None], key=lambda p: p["m"])
    if len(have) < 4 or not sm["atm_iv"]:
        return None
    xs, ys = [p["m"] for p in have], [p["iv"] for p in have]
    sig = sm["atm_iv"] / 100.0
    width = 4.5 * sig * math.sqrt(t)
    lo, hi = spot * math.exp(-width), spot * math.exp(width)
    ks = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    dk = ks[1] - ks[0]

    def vol_at(k: float) -> float:
        v = _kernel_iv(xs, ys, math.log(k / spot) * 100.0)
        return max(1.0, v) / 100.0

    calls = [bs.price(spot, k, t, vol_at(k), "CE", r) for k in ks]
    pdf = [0.0] * n
    for i in range(1, n - 1):
        pdf[i] = max(0.0, math.exp(r * t) * (calls[i + 1] - 2 * calls[i] + calls[i - 1]) / (dk * dk))
    # light smoothing (5-point binomial) to take the finite-difference noise out of the picture
    w5 = [1, 4, 6, 4, 1]
    pdf = [pdf[i] if i < 2 or i > n - 3 else sum(w * pdf[i + j - 2] for j, w in enumerate(w5)) / 16 for i in range(n)]
    mass = sum(pdf) * dk
    if mass <= 0:
        return None
    pdf = [p / mass for p in pdf]
    cdf, acc = [], 0.0
    for p in pdf:
        acc += p * dk
        cdf.append(min(1.0, acc))
    mean = sum(k * p for k, p in zip(ks, pdf)) * dk
    var = sum((k - mean) ** 2 * p for k, p in zip(ks, pdf)) * dk
    mode = ks[max(range(n), key=lambda i: pdf[i])]

    def q(level: float) -> float:
        for k, c in zip(ks, cdf):
            if c >= level:
                return k
        return ks[-1]

    # lognormal reference with the ATM vol (what a no-skew world would price)
    mu = math.log(spot) + (r - 0.5 * sig * sig) * t
    sd = sig * math.sqrt(t)
    ln = [math.exp(-((math.log(k) - mu) ** 2) / (2 * sd * sd)) / (k * sd * math.sqrt(2 * math.pi)) for k in ks]
    i_spot = min(range(n), key=lambda i: abs(ks[i] - spot))
    p_up = 1.0 - cdf[i_spot]
    em = spot * sig * math.sqrt(t)
    left = sum(p for k, p in zip(ks, pdf) if k < spot - em) * dk
    right = sum(p for k, p in zip(ks, pdf) if k > spot + em) * dk
    return {"x": [round(k, 1) for k in ks], "pdf": [round(p * spot, 6) for p in pdf], "lognormal": [round(p * spot, 6) for p in ln],
            "spot": spot, "mean": round(mean, 1), "mode": round(mode, 1), "std": round(math.sqrt(var), 1),
            "p16": round(q(0.16), 1), "p50": round(q(0.5), 1), "p84": round(q(0.84), 1), "p05": round(q(0.05), 1), "p95": round(q(0.95), 1),
            "p_up": round(p_up, 4), "expected_move": round(em, 1), "expected_move_pct": round(em / spot * 100, 2),
            "tail_left": round(left, 4), "tail_right": round(right, 4), "atm_iv": sm["atm_iv"], "t_days": round(t * 365, 2)}


def gex(rows: list[dict], spot: float, lot: int, t: float | None = None) -> dict | None:
    """Dealer gamma exposure per strike, ₹ crore per 1% move (OI in shares, as NSE reports it). Convention: dealers are long the
    calls customers sold (+) and short the puts customers bought (−); net > 0 pins, net < 0 chases."""
    out, have_oi = [], False
    for r in rows:
        k = r["strike"]
        ce, pe = r.get("ce") or {}, r.get("pe") or {}
        g_ce, g_pe = ce.get("gamma"), pe.get("gamma")
        if (g_ce is None or g_pe is None) and t and t > 0:
            ivc, ivp = _iv(ce), _iv(pe)
            g_ce = g_ce if g_ce is not None else (bs.greeks(spot, k, t, ivc / 100.0, "CE")["gamma"] if ivc else None)
            g_pe = g_pe if g_pe is not None else (bs.greeks(spot, k, t, ivp / 100.0, "PE")["gamma"] if ivp else None)
        oi_c, oi_p = int(ce.get("oi") or 0), int(pe.get("oi") or 0)
        have_oi = have_oi or oi_c > 0 or oi_p > 0
        scale = spot * spot * 0.01 / 1e7                 # OI is already in shares (contracts × lot), so no lot factor
        call = (g_ce or 0.0) * oi_c * scale
        put = -(g_pe or 0.0) * oi_p * scale
        out.append({"strike": k, "call": round(call, 3), "put": round(put, 3), "net": round(call + put, 3), "oi_ce": oi_c, "oi_pe": oi_p})
    if not have_oi:
        return None
    total = sum(x["net"] for x in out)
    cum, acc = [], 0.0
    for x in out:
        acc += x["net"]
        x["cum"] = round(acc, 3)
    # gamma flip: where cumulative net crosses zero, nearest to spot
    flip = None
    for a, b in zip(out, out[1:]):
        if (a["cum"] <= 0 < b["cum"]) or (a["cum"] >= 0 > b["cum"]):
            k = a["strike"] + (b["strike"] - a["strike"]) * (0 - a["cum"]) / ((b["cum"] - a["cum"]) or 1)
            if flip is None or abs(k - spot) < abs(flip - spot):
                flip = round(k, 0)
    pos = max(out, key=lambda x: x["net"])
    neg = min(out, key=lambda x: x["net"])
    return {"strikes": out, "total": round(total, 2), "flip": flip, "spot": spot, "lot": lot,
            "max_pos": {"strike": pos["strike"], "net": pos["net"]}, "max_neg": {"strike": neg["strike"], "net": neg["net"]},
            "regime": "positive gamma — dealers dampen moves" if total > 0 else "negative gamma — dealers chase moves"}
