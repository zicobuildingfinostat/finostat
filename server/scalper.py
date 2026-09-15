"""VIP SCALPER — a fast trend engine for 1-minute to 15-minute charts.

Votes on every closed candle: EMA 9 over 21 (trend), price against the session VWAP (who is in
control), Supertrend 7/2 (trailing trend + the stop), ADX 14 (only trade when there is a trend),
RSI 7 (momentum). Score in −1…+1; LONG from +0.5, SHORT from −0.5, exit when the score decays
through ±0.25 or the Supertrend flips. Stop = the Supertrend line (capped at 1.5 ATR), target = 1.5R.
Output has the same shape as gold.analyze so the shared chart renderer draws it."""
from __future__ import annotations

import gold

SYSTEMS = [("ema", "EMA 9 / 21", "trend", 1.5), ("vwap", "Session VWAP", "control", 1.5), ("st", "Supertrend 7 / 2", "trailing", 1.5),
           ("rsi", "RSI 7", "momentum", 1.0), ("adx", "ADX 14", "regime filter", 0.0)]


def session_vwap(c: list[list]) -> list:
    """VWAP anchored to each calendar day (IST) of the candle timestamps; falls back to a 20-bar VWAP when volume is missing."""
    out, day, pv, vol = [], None, 0.0, 0.0
    have_vol = any((k[5] or 0) > 0 for k in c[-50:])
    for i, k in enumerate(c):
        d = int((k[0] / 1000 + 19800) // 86400)                     # IST calendar day
        if d != day:
            day, pv, vol = d, 0.0, 0.0
        tp = (k[2] + k[3] + k[4]) / 3
        v = (k[5] or 0.0) if have_vol else 1.0
        pv += tp * v
        vol += v
        out.append(pv / vol if vol else tp)
    return out


def analyze(c: list[list], tf: str = "5m") -> dict:
    n = len(c)
    if n < 60:
        return {"error": "not enough candles"}
    closes = [k[4] for k in c]
    e9, e21, e50 = gold.ema(closes, 9), gold.ema(closes, 21), gold.ema(closes, 50)
    vwap = session_vwap(c)
    st_line, st_dir = gold.supertrend(c, 7, 2.0)
    adx_, _, _ = gold.adx(c)
    r7 = gold.rsi(closes, 7)
    atr_ = gold._wilder(gold.true_range(c), 14)
    bb_mid, bb_up, bb_lo = gold.bollinger(closes)
    scores, states, markers, votes_hist = [], [], [], []
    state = 0
    for i in range(n):
        v = {}
        if e21[i] is not None:
            v["ema"] = (1 if e9[i] > e21[i] else -1, f"EMA9 {'above' if e9[i] > e21[i] else 'below'} EMA21")
        v["vwap"] = (1 if closes[i] > vwap[i] else -1, f"price {'above' if closes[i] > vwap[i] else 'below'} VWAP {vwap[i]:,.1f}")
        if st_dir[i] is not None:
            v["st"] = (st_dir[i], f"Supertrend {'up' if st_dir[i] == 1 else 'down'} at {st_line[i]:,.1f}")
        if r7[i] is not None:
            v["rsi"] = (1 if r7[i] > 55 else -1 if r7[i] < 45 else 0, f"RSI7 {r7[i]:.0f}")
        if adx_[i] is not None:
            v["adx"] = (0, f"ADX {adx_[i]:.0f} — {'trending' if adx_[i] >= 18 else 'no trend, signals damped'}")
        tw = sum(w for k, _, _, w in SYSTEMS if k in v and w)
        score = sum(w * v[k][0] for k, _, _, w in SYSTEMS if k in v and w) / tw if tw else 0.0
        if adx_[i] is not None and adx_[i] < 18:
            score *= 0.5
        votes_hist.append(v)
        scores.append(round(score, 3) if len(v) >= 4 else None)
        s = scores[-1]
        if s is None:
            new = state
        elif state == 1:
            new = 1 if (s > 0.25 and st_dir[i] == 1) else (-1 if s <= -0.5 else 0)
        elif state == -1:
            new = -1 if (s < -0.25 and st_dir[i] == -1) else (1 if s >= 0.5 else 0)
        else:
            new = 1 if s >= 0.5 else -1 if s <= -0.5 else 0
        if new != state and s is not None:
            markers.append({"i": i, "t": c[i][0], "side": "BUY" if new == 1 else "SELL" if new == -1 else "EXIT", "price": closes[i], "score": s})
        state = new
        states.append(state)
    horizon = 8
    outcomes = [(closes[m["i"] + horizon] / m["price"] - 1) * (1 if m["side"] == "BUY" else -1) for m in markers if m["side"] != "EXIT" and m["i"] + horizon < n]
    stats = ({"n": len(outcomes), "hit_rate": round(100 * sum(1 for x in outcomes if x > 0) / len(outcomes), 1), "avg_pct": round(100 * sum(outcomes) / len(outcomes), 3), "horizon": horizon}
             if outcomes else None)
    i = n - 1
    score, direction, a = scores[i] or 0.0, states[i], atr_[i] or 0.0
    if direction == 1:
        stop = st_line[i] if st_dir[i] == 1 and st_line[i] < closes[i] else closes[i] - 1.5 * a
        stop = max(stop, closes[i] - 1.5 * a)
    elif direction == -1:
        stop = st_line[i] if st_dir[i] == -1 and st_line[i] > closes[i] else closes[i] + 1.5 * a
        stop = min(stop, closes[i] + 1.5 * a)
    else:
        stop = None
    risk = abs(closes[i] - stop) if stop else None
    target = closes[i] + direction * 1.5 * risk if risk else None
    label = {1: "LONG", -1: "SHORT", 0: "FLAT"}[direction]
    systems = [{"key": k, "name": nm, "who": who, "weight": w, "vote": votes_hist[i].get(k, (0, "warming up"))[0], "note": votes_hist[i].get(k, (0, "warming up"))[1], "group": "scalper"} for k, nm, who, w in SYSTEMS]
    since = next((m for m in reversed(markers) if m["side"] != "EXIT"), None)
    kpis = [["signal", label, "up" if direction == 1 else "down" if direction == -1 else "m"], ["score", f"{score:+.2f}", "c"],
            ["VWAP", f"{vwap[i]:,.1f} · {'above' if closes[i] > vwap[i] else 'below'}", "up" if closes[i] > vwap[i] else "down"],
            ["EMA 9 / 21", f"{e9[i]:,.1f} / {e21[i]:,.1f}", "m"], ["ADX · RSI7", f"{(adx_[i] or 0):.0f} · {(r7[i] or 0):.0f}", "m"],
            ["stop / target", f"{stop:,.1f} / {target:,.1f}" if stop else "—", "m"], ["past signals hit", f"{stats['hit_rate']:.0f}% of {stats['n']}" if stats else "—", "up" if stats and stats["hit_rate"] >= 50 else "m"]]
    return {"engine": "scalp", "tf": tf, "bars": n, "last": {"t": c[i][0], "o": c[i][1], "h": c[i][2], "l": c[i][3], "c": c[i][4]},
            "score": round(score, 3), "signal": label, "direction": direction, "regime": "trending" if (adx_[i] or 0) >= 18 else "no trend",
            "classic_score": round(score, 3), "pa_score": 0.0, "confluence": "—", "adx": round(adx_[i], 1) if adx_[i] is not None else None, "rsi": round(r7[i], 1) if r7[i] is not None else None, "atr": round(a, 2),
            "entry": round(closes[i], 2), "stop": round(stop, 2) if stop else None, "target": round(target, 2) if target else None, "risk_pct": round(100 * risk / closes[i], 2) if risk else None,
            "since": since, "systems": systems, "stats": stats, "kpis": kpis, "markers": markers[-40:],
            "pa": {"structure": 0, "swings": [], "events": [], "fvgs": [], "obs": [], "pools": [], "range": None},
            "series": {"t": [k[0] for k in c], "o": [k[1] for k in c], "h": [k[2] for k in c], "l": [k[3] for k in c], "c": closes, "v": [k[5] for k in c],
                       "e21": e9, "e50": e21, "s200": vwap, "st": st_line, "st_dir": st_dir, "bb_up": bb_up, "bb_lo": bb_lo, "score": scores, "state": states,
                       "classic": scores, "pa_score": [0.0] * n},
            "legend": {"e21": "EMA 9", "e50": "EMA 21", "s200": "VWAP"}}
