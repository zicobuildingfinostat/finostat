"""MOVE: expected move versus realised move for an index.

Expected (IV): 1σ = spot × IV × √(days/252) for the day and the week.
Expected (market): the ATM straddle is what the market charges for the move to expiry; 1σ to expiry
≈ straddle / 0.8 (a straddle prices ~0.8σ). Realised: today's high–low range and the move from the
previous close, each as a share of the expected figure."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def expected(spot: float, iv_pct: float | None, straddle: float | None, t_years: float | None) -> dict:
    out = {"spot": spot, "iv": iv_pct, "straddle": straddle, "t_days": round(t_years * 365, 2) if t_years is not None else None}
    if iv_pct:
        sig = iv_pct / 100.0
        out["em_day"] = round(spot * sig * math.sqrt(1 / 252), 1)
        out["em_week"] = round(spot * sig * math.sqrt(5 / 252), 1)
        out["em_expiry_iv"] = round(spot * sig * math.sqrt(max(t_years or 0.0, 1 / 365) if t_years is not None else 1 / 252), 1)
    else:
        out["em_day"] = out["em_week"] = out["em_expiry_iv"] = None
    if straddle:
        out["em_expiry_straddle"] = round(straddle, 1)
        out["sigma_expiry_straddle"] = round(straddle / 0.8, 1)
    else:
        out["em_expiry_straddle"] = out["sigma_expiry_straddle"] = None
    return out


def realised(candles: list[list], prev_close: float | None) -> dict:
    """Today's 5-minute candles [[iso, o, h, l, c, v], ...] -> open/high/low/last/range/move."""
    if not candles:
        return {"bars": 0}
    o = candles[0][1]
    h = max(c[2] for c in candles)
    l = min(c[3] for c in candles)
    last = candles[-1][4]
    out = {"bars": len(candles), "open": o, "high": h, "low": l, "last": last, "range": round(h - l, 1),
           "path": [[c[0][11:16], c[4]] for c in candles]}
    if prev_close:
        out["prev_close"] = prev_close
        out["move"] = round(last - prev_close, 1)
        out["move_pct"] = round((last / prev_close - 1) * 100, 2)
        out["gap"] = round(o - prev_close, 1)
        out["max_up"] = round(h - prev_close, 1)
        out["max_down"] = round(l - prev_close, 1)
    return out


def compare(exp: dict, real: dict) -> dict:
    out = {}
    em = exp.get("em_day")
    if em and real.get("range") is not None:
        out["range_vs_expected_pct"] = round(100 * real["range"] / (2 * em), 0)          # expected day range ≈ ±1σ = 2σ wide
    if em and real.get("move") is not None:
        out["move_sigmas"] = round(abs(real["move"]) / em, 2)
        out["move_vs_expected_pct"] = round(100 * abs(real["move"]) / em, 0)
    if em and real.get("max_up") is not None:
        out["touched_upper"] = real["max_up"] >= em
        out["touched_lower"] = real["max_down"] <= -em
    r = out.get("range_vs_expected_pct")
    out["verdict"] = (None if r is None else "quiet — realised well inside expected" if r < 60 else "in line with expected" if r <= 110 else
                      "expanding — realised beyond expected, straddles paying" if r <= 160 else "blow-out day — realised far beyond expected")
    return out


def today_only(candles: list[list], now: datetime | None = None) -> list[list]:
    day = (now or datetime.now(IST)).strftime("%Y-%m-%d")
    return [c for c in candles if str(c[0])[:10] == day]


def build(u: str, spot: float, iv_pct: float | None, straddle: float | None, t_years: float | None, prev_close: float | None,
          candles: list[list], expiry: str | None = None, now: datetime | None = None) -> dict:
    exp = expected(spot, iv_pct, straddle, t_years)
    real = realised(today_only(candles, now), prev_close)
    return {"u": u, "expiry": expiry, "expected": exp, "realised": real, "compare": compare(exp, real)}
