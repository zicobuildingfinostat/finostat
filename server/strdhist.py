"""IVP: straddle and IV percentile history.

Today's ATM straddle, minute by minute, against the same clock time on the last N expiry cycles at the
same distance to expiry (DTE): if today is 2 trading days before expiry, each comparison day is the day
2 trading days before that past expiry, with the ATM fixed at that day's open. Everything is expressed
as a percentage of spot so cycles are comparable. From the straddle price an ATM implied vol is solved
at each minute, giving an IV percentile too. India VIX rank / percentile over a year is shown alongside
as the market-wide reference. Past cycles come from Upstox's expired-instruments archive (cached for
good in the history store); today's series from the live 1-minute candles."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import bs

log = logging.getLogger("finostat.strdhist")
IST = timezone(timedelta(hours=5, minutes=30))
MINUTES = [f"{h:02d}:{m:02d}" for h in range(9, 16) for m in range(0, 60, 5) if "09:15" <= f"{h:02d}:{m:02d}" <= "15:30"]


def trading_days_between(a: date, b: date) -> int:
    """Weekdays from a (exclusive) to b (inclusive); 0 when a == b."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def trading_day_before(expiry: date, dte: int) -> date:
    d = expiry
    while dte > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            dte -= 1
    return d


def straddle_iv(straddle: float, spot: float, strike: float, t: float) -> float | None:
    """Vol such that CE + PE at the strike prices to the straddle (bisection)."""
    if straddle <= 0 or spot <= 0 or t <= 0:
        return None
    lo, hi = 0.005, 5.0
    if bs.price(spot, strike, t, lo, "CE") + bs.price(spot, strike, t, lo, "PE") > straddle:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        px = bs.price(spot, strike, t, mid, "CE") + bs.price(spot, strike, t, mid, "PE")
        if px > straddle:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2 * 100, 2)


def _minute(ts: str) -> str:
    return str(ts)[11:16]


def _by_minute(candles: list[list]) -> dict[str, float]:
    return {_minute(c[0]): float(c[4]) for c in candles if c and c[0]}


def _at(series: dict[str, float], minute: str) -> float | None:
    if minute in series:
        return series[minute]
    prev = [m for m in series if m <= minute]
    return series[max(prev)] if prev else None


def build_points(spot_by_min: dict[str, float], ce: dict[str, float], pe: dict[str, float], expiry_ts: float, day: date, atm: int) -> list[list]:
    """[[HH:MM, straddle, pct_of_spot, iv], ...] on the 5-minute grid."""
    out = []
    for m in MINUTES:
        s, c, p = _at(spot_by_min, m), _at(ce, m), _at(pe, m)
        if s is None or c is None or p is None:
            continue
        st = c + p
        t_min = datetime(day.year, day.month, day.day, int(m[:2]), int(m[3:]), tzinfo=IST).timestamp()
        t = max((expiry_ts - t_min) / (365 * 86400), 1 / (365 * 24 * 60))
        out.append([m, round(st, 2), round(100 * st / s, 3), straddle_iv(st, s, atm, t)])
    return out


def sample_cycle(hist, u: str, expiry: str, dte: int) -> dict | None:
    """One past cycle: the day `dte` trading days before `expiry`, ATM fixed at that day's open."""
    exp_d = datetime.strptime(expiry, "%Y-%m-%d").date()
    day = trading_day_before(exp_d, dte)
    idx = hist.index_day(u, day.isoformat())
    if not idx:
        return None
    ctr = hist.contracts(u, expiry)
    step = ctr["step"]
    open_px = float(idx[0][1])
    atm = int(round(open_px / step) * step)
    kc, kp = ctr["keys"].get(f"CE:{atm}"), ctr["keys"].get(f"PE:{atm}")
    if not kc or not kp:
        return None
    ce, pe = _by_minute(hist.candles(kc, day.isoformat())), _by_minute(hist.candles(kp, day.isoformat()))
    if not ce or not pe:
        return None
    exp_ts = datetime(exp_d.year, exp_d.month, exp_d.day, 15, 30, tzinfo=IST).timestamp()
    pts = build_points(_by_minute(idx), ce, pe, exp_ts, day, atm)
    if len(pts) < 10:
        return None
    return {"expiry": expiry, "day": day.isoformat(), "atm": atm, "spot_open": open_px, "points": pts,
            "open_pct": pts[0][2], "close_pct": pts[-1][2], "decay_pct": round(100 * (pts[-1][1] / pts[0][1] - 1), 1) if pts[0][1] else None}


def study(hist, u: str, dte: int, n: int, today: date, job=None) -> dict:
    """The last n expired cycles at this DTE (skips cycles the archive cannot serve)."""
    days = [d for d in hist.days(u) if d < today.isoformat()]
    days = sorted(days)[-n:]
    samples = []
    for i, e in enumerate(reversed(days)):
        try:
            s = sample_cycle(hist, u, e, dte)
            if s:
                samples.append(s)
        except Exception as exc:                                    # noqa: BLE001 - one bad cycle must not kill the study
            log.info("strdhist: cycle %s skipped: %s", e, exc)
        if job is not None:
            job.progress = (i + 1) / (len(days) + 1)
    return {"u": u, "dte": dte, "n": len(samples), "samples": samples}


def bands(samples: list[dict]) -> list[list]:
    """Per minute: [minute, min, median, max] of pct-of-spot across cycles."""
    out = []
    for m in MINUTES:
        vals = sorted(p[2] for s in samples for p in s["points"] if p[0] == m)
        if not vals:
            continue
        mid = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        out.append([m, vals[0], round(mid, 3), vals[-1]])
    return out


def percentile(value: float, pool: list[float]) -> float | None:
    if not pool or value is None:
        return None
    below = sum(1 for v in pool if v < value)
    eq = sum(1 for v in pool if v == value)
    return round(100 * (below + 0.5 * eq) / len(pool), 0)


def compare_now(today_points: list[list], samples: list[dict]) -> dict:
    """Where today's latest straddle and IV sit against the cycles at the same minute."""
    if not today_points:
        return {}
    m, st, pct, iv = today_points[-1]
    pool_pct = [_at({p[0]: p[2] for p in s["points"]}, m) for s in samples]
    pool_iv = [_at({p[0]: p[3] for p in s["points"] if p[3]}, m) for s in samples]
    pool_pct = [v for v in pool_pct if v is not None]
    pool_iv = [v for v in pool_iv if v is not None]
    med = sorted(pool_pct)[len(pool_pct) // 2] if pool_pct else None
    return {"minute": m, "straddle": st, "pct": pct, "iv": iv,
            "pct_percentile": percentile(pct, pool_pct), "pct_median": med, "pct_min": min(pool_pct) if pool_pct else None, "pct_max": max(pool_pct) if pool_pct else None,
            "iv_percentile": percentile(iv, pool_iv) if iv else None, "iv_median": sorted(pool_iv)[len(pool_iv) // 2] if pool_iv else None,
            "cycles": len(pool_pct),
            "read": (None if not pool_pct else "rich — straddle above most cycles at this time" if percentile(pct, pool_pct) >= 75 else
                     "cheap — straddle below most cycles at this time" if percentile(pct, pool_pct) <= 25 else "fair — mid-pack against past cycles")}


def vix_rank(closes: list[float]) -> dict | None:
    if len(closes) < 20:
        return None
    last, lo, hi = closes[-1], min(closes), max(closes)
    return {"last": round(last, 2), "low": round(lo, 2), "high": round(hi, 2), "days": len(closes),
            "rank": round(100 * (last - lo) / (hi - lo), 0) if hi > lo else None, "percentile": percentile(last, closes[:-1])}
