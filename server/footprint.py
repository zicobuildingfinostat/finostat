"""Volume footprint and profile from OHLCV candles.

True footprints need bid/ask ticks. From candles we build the transparent approximation desks use
when ticks are unavailable: each bar's volume is split into buying and selling by where it closed
within its range (close at the high = all buying, at the low = all selling), and spread over price
bins across the bar's range with more weight near the close. That gives per-bar delta, cumulative
delta (CVD) and a volume profile with point of control and value area for the visible window."""
from __future__ import annotations


def bar_split(o: float, h: float, l: float, c: float, v: float) -> tuple[float, float]:
    rng = h - l
    if rng <= 0 or v <= 0:
        return v / 2, v / 2
    clv = (c - l) / rng                                            # 0 = closed at the low, 1 = at the high
    buy = v * clv
    return buy, v - buy


def footprint(c: list[list], bins: int = 4) -> dict:
    """Per-bar rows [[lo, hi, [vol per bin low->high], buy, sell, delta]] + CVD; None when there is no volume."""
    if not c or not any((k[5] or 0) > 0 for k in c):
        return {"bins": bins, "rows": [], "cvd": [], "has_volume": False}
    rows, cvd, acc = [], [], 0.0
    for k in c:
        o, h, l, cl, v = k[1], k[2], k[3], k[4], float(k[5] or 0)
        buy, sell = bar_split(o, h, l, cl, v)
        rng = h - l
        cells = []
        if rng <= 0:
            cells = [v] + [0.0] * (bins - 1)
        else:
            # weight each bin by closeness to the close: 3 at the close's bin down to 1 at the far end
            pos = min(bins - 1, int((cl - l) / rng * bins))
            w = [3.0 - 2.0 * abs(b - pos) / max(1, bins - 1) for b in range(bins)]
            tw = sum(w)
            cells = [v * x / tw for x in w]
        acc += buy - sell
        rows.append([round(l, 2), round(h, 2), [round(x, 1) for x in cells], round(buy, 1), round(sell, 1), round(buy - sell, 1)])
        cvd.append(round(acc, 1))
    return {"bins": bins, "rows": rows, "cvd": cvd, "has_volume": True}


def profile(c: list[list], buckets: int = 24) -> dict | None:
    """Volume by price bucket over the window, with POC and the 70% value area."""
    if not c or not any((k[5] or 0) > 0 for k in c):
        return None
    lo = min(k[3] for k in c)
    hi = max(k[2] for k in c)
    if hi <= lo:
        return None
    size = (hi - lo) / buckets
    vol = [0.0] * buckets
    buy = [0.0] * buckets
    for k in c:
        v = float(k[5] or 0)
        if v <= 0:
            continue
        b_lo = min(buckets - 1, max(0, int((k[3] - lo) / size)))
        b_hi = min(buckets - 1, max(0, int((k[2] - lo) / size)))
        span = b_hi - b_lo + 1
        bv, _ = bar_split(k[1], k[2], k[3], k[4], v)
        for b in range(b_lo, b_hi + 1):
            vol[b] += v / span
            buy[b] += bv / span
    total = sum(vol)
    poc = max(range(buckets), key=lambda b: vol[b])
    # value area: expand from the POC until 70% of volume is inside
    inside, lo_b, hi_b = vol[poc], poc, poc
    while inside < 0.7 * total and (lo_b > 0 or hi_b < buckets - 1):
        up = vol[hi_b + 1] if hi_b < buckets - 1 else -1
        dn = vol[lo_b - 1] if lo_b > 0 else -1
        if up >= dn:
            hi_b += 1; inside += up
        else:
            lo_b -= 1; inside += dn
    return {"lo": round(lo, 2), "hi": round(hi, 2), "size": round(size, 4), "buckets": buckets,
            "vol": [round(x, 1) for x in vol], "buy": [round(x, 1) for x in buy],
            "poc": round(lo + (poc + 0.5) * size, 2), "vah": round(lo + (hi_b + 1) * size, 2), "val": round(lo + lo_b * size, 2), "total": round(total, 1)}


def attach(view: dict) -> dict:
    """Add fp/profile for the candles in a sliced view (series in the chart shape)."""
    s = view.get("series")
    if not s:
        return view
    c = [[t, o, h, l, cl, v] for t, o, h, l, cl, v in zip(s["t"], s["o"], s["h"], s["l"], s["c"], s.get("v") or [0] * len(s["t"]))]
    view["fp"] = footprint(c)
    view["profile"] = profile(c)
    return view
