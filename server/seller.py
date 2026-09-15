"""VIP SELLER — when to sell premium, which side, and where.

Reads the chart for the conditions option sellers want: no trend (ADX), a calm Bollinger width that is
not a coiled squeeze, price mid-range, and a structure bias from the smart-money engine to pick the
side. On indices the web app also feeds it the straddle percentile (is premium rich?) and today's
realised range against the expected move. Signals: SELL STRADDLE (neutral range), SELL CALLS (bearish
bias / premium zone), SELL PUTS (bullish bias / discount zone), EXIT / STAND ASIDE (trend, expansion,
range break). Suggested short strikes come from the range edges, the nearest supply/demand and the
expected move, rounded to the strike step. Same output shape as gold.analyze for the shared chart."""
from __future__ import annotations

import gold

SYSTEMS = [("adx", "ADX 14 regime", "no trend = sell", 2.0), ("bbw", "Bollinger width", "calm, not coiled", 1.0), ("range", "Dealing range", "mid-range = sell", 1.5),
           ("bias", "Structure bias", "picks the side", 1.0), ("rsi", "RSI 14", "not at an extreme", 0.5),
           ("ivp", "Straddle percentile", "premium rich?", 1.5), ("rvsx", "Realised vs expected", "quiet tape", 1.0)]
WEIGHT = {k: w for k, _, _, w in SYSTEMS}


def _step_for(price: float, step: int | None) -> int:
    if step:
        return step
    return 5 if price < 500 else 10 if price < 1500 else 20 if price < 3000 else 50 if price < 10000 else 100


def _round(x: float, step: int, up: bool) -> int:
    import math
    return int((math.ceil if up else math.floor)(x / step) * step)


def analyze(c: list[list], tf: str = "15m", extras: dict | None = None, step: int | None = None) -> dict:
    n = len(c)
    if n < 80:
        return {"error": "not enough candles"}
    ex = extras or {}
    closes = [k[4] for k in c]
    highs, lows = [k[2] for k in c], [k[3] for k in c]
    adx_, _, _ = gold.adx(c)
    atr_ = gold._wilder(gold.true_range(c), 14)
    bb_mid, bb_up, bb_lo = gold.bollinger(closes)
    width = [((u - l) / m) if (u is not None and m) else None for u, l, m in zip(bb_up, bb_lo, bb_mid)]
    r14 = gold.rsi(closes, 14)
    e21, e50, s200 = gold.ema(closes, 21), gold.ema(closes, 50), gold.sma(closes, 200)
    st_line, st_dir = gold.supertrend(c)
    pa_votes, pa_draw = gold.price_action(c, atr_, left=3)
    # rebuild structure/range per bar from the PA pass (price_action keeps only the final draw; re-derive per-bar votes)
    scores, states, markers, votes_hist, sides = [], [], [], [], []
    state, side_state = 0, "SELL STRADDLE"
    for i in range(n):
        v = {}
        if adx_[i] is not None:
            a = adx_[i]
            v["adx"] = (1 if a < 20 else 0 if a < 28 else -1, f"ADX {a:.0f} — {'rangebound, sellers favoured' if a < 20 else 'building trend, careful' if a < 28 else 'trending, stand aside'}")
        if width[i] is not None and i >= 100:
            hist = [w for w in width[i - 100:i] if w is not None]
            pct = 100 * sum(1 for w in hist if w < width[i]) / len(hist) if hist else 50
            v["bbw"] = (1 if 15 <= pct <= 60 else -1 if pct < 15 else 0, f"BB width at the {pct:.0f}th percentile — {'calm' if 15 <= pct <= 60 else 'coiled squeeze: expansion risk' if pct < 15 else 'already wide'}")
        pv = pa_votes[i]
        rng_vote = pv.get("range")
        structure = pv.get("structure", (0, ""))[0]
        if rng_vote is not None:
            note = rng_vote[1]
            pos = None
            try:
                pos = float(note.split("(")[1].split("%")[0])
            except (IndexError, ValueError):
                pass
            v["range"] = (1 if pos is not None and 30 <= pos <= 70 else 0 if pos is not None else 0, f"{pos:.0f}% of the dealing range" if pos is not None else "no range yet")
            side = "SELL STRADDLE"
            if structure == 1 and pos is not None and pos < 50:
                side = "SELL PUTS"
            elif structure == -1 and pos is not None and pos > 50:
                side = "SELL CALLS"
            elif structure == 1 and pos is not None and pos >= 70:
                side = "SELL CALLS"                                   # bullish but stretched: fade the top with calls
            elif structure == -1 and pos is not None and pos <= 30:
                side = "SELL PUTS"
            side_state = side
        v["bias"] = (0, f"structure {'bullish' if structure == 1 else 'bearish' if structure == -1 else 'neutral'} → {side_state.lower()}")
        if r14[i] is not None:
            v["rsi"] = (1 if 35 <= r14[i] <= 65 else -1, f"RSI {r14[i]:.0f}" + (" — mid, no directional pressure" if 35 <= r14[i] <= 65 else " — at an extreme, wait"))
        if i == n - 1 and ex.get("iv_percentile") is not None:
            p = ex["iv_percentile"]
            v["ivp"] = (1 if p >= 60 else -1 if p <= 30 else 0, f"straddle at the {p:.0f}th percentile of past cycles — {'rich, worth selling' if p >= 60 else 'cheap, little to sell' if p <= 30 else 'fair'}")
        if i == n - 1 and ex.get("realised_vs_expected_pct") is not None:
            q = ex["realised_vs_expected_pct"]
            v["rvsx"] = (1 if q < 80 else -1 if q > 120 else 0, f"realised range {q:.0f}% of expected — {'quiet, theta wins' if q < 80 else 'expanding, sellers bleed' if q > 120 else 'in line'}")
        tw = sum(WEIGHT[k] for k in v if WEIGHT[k])
        score = sum(WEIGHT[k] * v[k][0] for k in v) / tw if tw else 0.0
        votes_hist.append(v)
        scores.append(round(score, 3) if len(v) >= 4 else None)
        s = scores[-1]
        broke = False
        if pa_draw.get("range") and i == n - 1:
            pass
        if s is None:
            new = state
        elif state == 1:
            new = 1 if s > 0.15 and (adx_[i] or 0) < 28 else -1 if (adx_[i] or 0) >= 28 else 0
        else:
            new = 1 if s >= 0.4 else -1 if s <= -0.4 else 0
        if new != state and s is not None:
            markers.append({"i": i, "t": c[i][0], "side": "BUY" if new == 1 else "SELL" if new == -1 else "EXIT", "label": side_state if new == 1 else "STAND ASIDE" if new == -1 else "EXIT",
                            "price": closes[i], "score": s})
        state = new
        states.append(state)
        sides.append(side_state if state == 1 else None)
    i = n - 1
    score, direction = scores[i] or 0.0, states[i]
    px = closes[i]
    stp = _step_for(px, step)
    rng = pa_draw.get("range")
    em = ex.get("em_day")
    sup = min((z["bot"] for z in (pa_draw.get("obs") or []) + (pa_draw.get("fvgs") or []) if z["dir"] == -1 and z["bot"] > px), default=None)
    dem = max((z["top"] for z in (pa_draw.get("obs") or []) + (pa_draw.get("fvgs") or []) if z["dir"] == 1 and z["top"] < px), default=None)
    call_k = _round(max(x for x in [rng["hi"] if rng else None, sup, px + em if em else None, px * 1.01] if x is not None), stp, True)
    put_k = _round(min(x for x in [rng["lo"] if rng else None, dem, px - em if em else None, px * 0.99] if x is not None), stp, False)
    side = side_state if direction == 1 else None
    levels = []
    if direction == 1:
        if side in ("SELL CALLS", "SELL STRADDLE"):
            levels.append({"price": call_k, "label": f"SELL CE {call_k:,}", "color": "down"})
        if side in ("SELL PUTS", "SELL STRADDLE"):
            levels.append({"price": put_k, "label": f"SELL PE {put_k:,}", "color": "up"})
    signal = side if direction == 1 else "STAND ASIDE" if direction == -1 else "NEUTRAL"
    systems = [{"key": k, "name": nm, "who": who, "weight": w, "vote": votes_hist[i].get(k, (0, "n/a"))[0], "note": votes_hist[i].get(k, (0, "n/a"))[1], "group": "seller"} for k, nm, who, w in SYSTEMS]
    horizon = 20
    outcomes = []
    for m in markers:
        if m["side"] != "BUY" or m["i"] + horizon >= n:
            continue
        seg = closes[m["i"]: m["i"] + horizon + 1]
        band = (em or (atr_[i] or px * 0.005) * 2)
        outcomes.append(1 if max(abs(x - m["price"]) for x in seg) <= band else 0)         # premium sold inside the band: a win
    stats = {"n": len(outcomes), "hit_rate": round(100 * sum(outcomes) / len(outcomes), 1), "horizon": horizon} if outcomes else None
    since = next((m for m in reversed(markers) if m["side"] != "EXIT"), None)
    kpis = [["signal", signal, "up" if direction == 1 else "down" if direction == -1 else "m"], ["sell score", f"{score:+.2f}", "c"],
            ["regime", f"ADX {(adx_[i] or 0):.0f} · {'range' if (adx_[i] or 0) < 20 else 'building' if (adx_[i] or 0) < 28 else 'trend'}", "up" if (adx_[i] or 0) < 20 else "down" if (adx_[i] or 0) >= 28 else "m"],
            ["short call strike", f"{call_k:,}" if direction == 1 and side != "SELL PUTS" else "—", "down"], ["short put strike", f"{put_k:,}" if direction == 1 and side != "SELL CALLS" else "—", "up"],
            ["premium", f"{ex['iv_percentile']:.0f}th pct" if ex.get("iv_percentile") is not None else "n/a on this symbol", "m"],
            ["realised vs expected", f"{ex['realised_vs_expected_pct']:.0f}%" if ex.get("realised_vs_expected_pct") is not None else "n/a", "m"],
            ["past sells inside band", f"{stats['hit_rate']:.0f}% of {stats['n']}" if stats else "—", "up" if stats and stats["hit_rate"] >= 60 else "m"]]
    return {"engine": "seller", "tf": tf, "bars": n, "last": {"t": c[i][0], "o": c[i][1], "h": c[i][2], "l": c[i][3], "c": c[i][4]},
            "score": round(score, 3), "signal": signal, "direction": direction, "regime": "rangebound" if (adx_[i] or 0) < 20 else "trending" if (adx_[i] or 0) >= 28 else "building",
            "classic_score": round(score, 3), "pa_score": round(gold.PA_WEIGHT and sum(gold.PA_WEIGHT[k] * pa_votes[i][k][0] for k in pa_votes[i]) / sum(gold.PA_WEIGHT[k] for k in pa_votes[i]) if pa_votes[i] else 0.0, 3),
            "confluence": "—", "adx": round(adx_[i], 1) if adx_[i] is not None else None, "rsi": round(r14[i], 1) if r14[i] is not None else None, "atr": round(atr_[i] or 0, 2),
            "entry": round(px, 2), "stop": None, "target": None, "risk_pct": None, "levels": levels, "side": side, "call_strike": call_k, "put_strike": put_k,
            "since": since, "systems": systems, "stats": stats, "kpis": kpis, "markers": markers[-40:], "pa": pa_draw,
            "series": {"t": [k[0] for k in c], "o": [k[1] for k in c], "h": highs, "l": lows, "c": closes, "v": [k[5] for k in c],
                       "e21": e21, "e50": e50, "s200": s200, "st": st_line, "st_dir": st_dir, "bb_up": bb_up, "bb_lo": bb_lo, "score": scores, "state": states,
                       "classic": scores, "pa_score": [0.0] * n}}
