"""GOLD signal: a composite buy/sell indicator built from the published, rule-based systems that
well-known traders are associated with, each voting on the same gold candles:

  Turtle breakout      Richard Dennis & William Eckhardt  20-bar breakout, 10-bar exit
  200-day rule         Paul Tudor Jones                    only long above the 200 MA, short below
  Holy Grail           Linda Raschke                       ADX > 30 trend, buy/sell the pullback to the 20 EMA
  MACD                 Gerald Appel                        12/26/9 momentum
  RSI                  J. Welles Wilder                    14-period, 55/45 bias with 70/30 caution
  ADX / DMI            J. Welles Wilder                    trend strength regime
  Supertrend           10, 3×ATR                           trailing trend line
  Ichimoku             Goichi Hosoda                       cloud position + tenkan/kijun
  Bollinger %B         John Bollinger                      20, 2σ band position
  EMA ribbon           9 / 21 / 50 alignment, 50/200 cross

Nobody at those desks wrote these signals; the systems are public and this is a faithful,
transparent implementation of each. Candles: Binance PAXGUSDT (gold-backed token that tracks
XAU/USD), Kraken PAXGUSD as fallback; spot cross-check from gold-api.com. Pure Python, no numpy."""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request

log = logging.getLogger("finostat.gold")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
TFS = {"1h": ("1h", 60, 60.0), "4h": ("4h", 240, 300.0), "1d": ("1d", 1440, 600.0)}     # tf -> (binance interval, kraken minutes, cache ttl)
OZ_PER_10G = 10.0 / 31.1034768


def _get(url: str, timeout: float = 15.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_candles(tf: str, limit: int = 1000) -> list[list]:
    """[[ts_ms, o, h, l, c, v], ...] oldest first."""
    interval, minutes, _ = TFS[tf]
    try:
        raw = _get(f"https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval={interval}&limit={limit}")
        out = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in raw]
        if len(out) >= 60:
            return out
    except Exception as exc:                                        # noqa: BLE001
        log.info("gold: binance klines failed (%s); trying kraken", exc)
    raw = _get(f"https://api.kraken.com/0/public/OHLC?pair=PAXGUSD&interval={minutes}")
    rows = (raw.get("result") or {}).get("PAXGUSD") or []
    return [[int(r[0]) * 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6])] for r in rows]


def spot_xau() -> float | None:
    try:
        return float(_get("https://api.gold-api.com/price/XAU")["price"])
    except Exception:                                               # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# indicators (lists aligned to the candles, None until warm)
# ---------------------------------------------------------------------------
def ema(xs: list[float], n: int) -> list:
    out, k, e = [], 2.0 / (n + 1), None
    for i, x in enumerate(xs):
        if e is None:
            if i + 1 < n:
                out.append(None); continue
            e = sum(xs[: n]) / n
        else:
            e = x * k + e * (1 - k)
        out.append(e)
    return out


def sma(xs: list[float], n: int) -> list:
    out, s = [], 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        out.append(s / n if i + 1 >= n else None)
    return out


def _wilder(xs: list, n: int) -> list:
    out, a = [], None
    for i, x in enumerate(xs):
        if x is None:
            out.append(None); continue
        if a is None:
            window = [v for v in xs[max(0, i - n + 1): i + 1] if v is not None]
            if len(window) < n:
                out.append(None); continue
            a = sum(window) / n
        else:
            a = (a * (n - 1) + x) / n
        out.append(a)
    return out


def rsi(closes: list[float], n: int = 14) -> list:
    gains = [None] + [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses = [None] + [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    ag, al = _wilder(gains, n), _wilder(losses, n)
    return [None if g is None or l is None else (100.0 if l == 0 else 100 - 100 / (1 + g / l)) for g, l in zip(ag, al)]


def true_range(c: list[list]) -> list:
    out = [None]
    for i in range(1, len(c)):
        h, l, pc = c[i][2], c[i][3], c[i - 1][4]
        out.append(max(h - l, abs(h - pc), abs(l - pc)))
    return out


def adx(c: list[list], n: int = 14) -> tuple[list, list, list]:
    tr = true_range(c)
    pdm, ndm = [None], [None]
    for i in range(1, len(c)):
        up, dn = c[i][2] - c[i - 1][2], c[i - 1][3] - c[i][3]
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)
    atr_, p, q = _wilder(tr, n), _wilder(pdm, n), _wilder(ndm, n)
    pdi = [None if a is None or not a else 100 * x / a for x, a in zip(p, atr_)]
    ndi = [None if a is None or not a else 100 * x / a for x, a in zip(q, atr_)]
    dx = [None if a is None or b is None or (a + b) == 0 else 100 * abs(a - b) / (a + b) for a, b in zip(pdi, ndi)]
    return _wilder(dx, n), pdi, ndi


def supertrend(c: list[list], n: int = 10, mult: float = 3.0) -> tuple[list, list]:
    """(line, direction) with direction +1 up / -1 down."""
    atr_ = _wilder(true_range(c), n)
    line, dirn = [], []
    fu = fl = None
    d = 1
    for i, k in enumerate(c):
        a = atr_[i]
        if a is None:
            line.append(None); dirn.append(None); continue
        mid = (k[2] + k[3]) / 2
        bu, bl = mid + mult * a, mid - mult * a
        pc = c[i - 1][4] if i else k[4]
        fu = bu if fu is None or bu < fu or pc > fu else fu
        fl = bl if fl is None or bl > fl or pc < fl else fl
        if d == 1 and k[4] < fl:
            d = -1
        elif d == -1 and k[4] > fu:
            d = 1
        line.append(fl if d == 1 else fu)
        dirn.append(d)
    return line, dirn


def rolling(xs: list[float], n: int, fn) -> list:
    """fn over the PRIOR n bars (excludes the current bar) — breakouts compare against the past."""
    return [fn(xs[i - n: i]) if i >= n else None for i in range(len(xs))]


def bollinger(closes: list[float], n: int = 20, k: float = 2.0) -> tuple[list, list, list]:
    mid = sma(closes, n)
    up, lo = [], []
    for i, m in enumerate(mid):
        if m is None:
            up.append(None); lo.append(None); continue
        w = closes[i - n + 1: i + 1]
        sd = (sum((x - m) ** 2 for x in w) / n) ** 0.5
        up.append(m + k * sd); lo.append(m - k * sd)
    return mid, up, lo


def ichimoku(c: list[list]) -> dict:
    highs, lows = [k[2] for k in c], [k[3] for k in c]
    def mid(n):
        return [(max(highs[i - n + 1: i + 1]) + min(lows[i - n + 1: i + 1])) / 2 if i + 1 >= n else None for i in range(len(c))]
    tenkan, kijun, s52 = mid(9), mid(26), mid(52)
    span_a = [None if t is None or k is None else (t + k) / 2 for t, k in zip(tenkan, kijun)]
    # the cloud at bar i is what was projected 26 bars earlier
    cloud_a = [span_a[i - 26] if i >= 26 else None for i in range(len(c))]
    cloud_b = [s52[i - 26] if i >= 26 else None for i in range(len(c))]
    return {"tenkan": tenkan, "kijun": kijun, "cloud_a": cloud_a, "cloud_b": cloud_b}



# ---------------------------------------------------------------------------
# price action / smart-money structure (no look-ahead: swings register once confirmed)
# ---------------------------------------------------------------------------
PA_SYSTEMS = [
    ("structure", "Market structure", "BOS / CHoCH", 2.0),
    ("zone", "Order block / FVG", "demand & supply zones", 1.5),
    ("liquidity", "Liquidity sweep", "equal highs / lows", 1.5),
    ("range", "Premium / discount", "dealing range 50%", 1.0),
    ("displacement", "Displacement", "momentum candles", 1.0),
    ("candle", "Rejection / engulfing", "candle at a level", 0.5),
]
PA_WEIGHT = {k: w for k, _, _, w in PA_SYSTEMS}


def price_action(c: list[list], atr_: list, left: int = 3) -> tuple[list[dict], dict]:
    """Per-bar votes for the price-action systems plus the structures to draw."""
    n = len(c)
    o = [k[1] for k in c]; h = [k[2] for k in c]; l = [k[3] for k in c]; cl = [k[4] for k in c]
    bodies = [abs(cl[i] - o[i]) for i in range(n)]
    avg_body = sma(bodies, 20)
    swings: list[dict] = []                     # confirmed pivots in order
    sh: list[dict] = []; sl: list[dict] = []
    events: list[dict] = []                     # BOS / CHoCH
    fvgs: list[dict] = []; obs: list[dict] = []; pools: list[dict] = []
    structure = 0
    votes: list[dict] = []
    last_sweep = None
    last_disp = None
    rng = None
    for i in range(n):
        # -- confirm pivots at i (the pivot itself is `left` bars back)
        p = i - left
        if p >= left:
            if h[p] == max(h[p - left: p + left + 1]):
                tag = "HH" if sh and h[p] > sh[-1]["price"] else "LH" if sh else "H"
                sw = {"i": p, "price": h[p], "type": "high", "tag": tag, "broken": False}
                swings.append(sw); sh.append(sw)
                # equal highs -> liquidity pool
                for prev in sh[-4:-1]:
                    tol = (atr_[p] or h[p] * 0.003) * 0.25
                    if abs(prev["price"] - h[p]) <= tol and not prev.get("pooled"):
                        pools.append({"price": max(prev["price"], h[p]), "type": "EQH", "i0": prev["i"], "i1": p, "swept": None}); prev["pooled"] = True; break
            if l[p] == min(l[p - left: p + left + 1]):
                tag = "LL" if sl and l[p] < sl[-1]["price"] else "HL" if sl else "L"
                sw = {"i": p, "price": l[p], "type": "low", "tag": tag, "broken": False}
                swings.append(sw); sl.append(sw)
                for prev in sl[-4:-1]:
                    tol = (atr_[p] or l[p] * 0.003) * 0.25
                    if abs(prev["price"] - l[p]) <= tol and not prev.get("pooled"):
                        pools.append({"price": min(prev["price"], l[p]), "type": "EQL", "i0": prev["i"], "i1": p, "swept": None}); prev["pooled"] = True; break
        # -- structure breaks on close
        ev = None
        last_high = next((s for s in reversed(sh) if not s["broken"]), None)
        last_low = next((s for s in reversed(sl) if not s["broken"]), None)
        if last_high and cl[i] > last_high["price"]:
            kind = "BOS" if structure == 1 else "CHoCH"
            ev = {"i": i, "type": kind, "dir": 1, "level": last_high["price"], "from": last_high["i"]}
            for s_ in sh:                                            # every high under this close is taken out by it
                if s_["price"] < cl[i]:
                    s_["broken"] = True
            # bullish order block: last down candle between the origin low and the break
            origin = next((s for s in reversed(sl) if s["i"] < i), None)
            start = origin["i"] if origin else max(0, i - 20)
            for j in range(i - 1, start - 1, -1):
                if cl[j] < o[j]:
                    obs.append({"i": j, "top": h[j], "bot": l[j], "dir": 1, "touched": None, "dead": None}); break
            structure = 1
        elif last_low and cl[i] < last_low["price"]:
            kind = "BOS" if structure == -1 else "CHoCH"
            ev = {"i": i, "type": kind, "dir": -1, "level": last_low["price"], "from": last_low["i"]}
            for s_ in sl:
                if s_["price"] > cl[i]:
                    s_["broken"] = True
            origin = next((s for s in reversed(sh) if s["i"] < i), None)
            start = origin["i"] if origin else max(0, i - 20)
            for j in range(i - 1, start - 1, -1):
                if cl[j] > o[j]:
                    obs.append({"i": j, "top": h[j], "bot": l[j], "dir": -1, "touched": None, "dead": None}); break
            structure = -1
        if ev:
            events.append(ev)
        # -- fair value gaps (three-candle imbalance)
        if i >= 2:
            if l[i] > h[i - 2]:
                fvgs.append({"i": i, "top": l[i], "bot": h[i - 2], "dir": 1, "filled": None})
            elif h[i] < l[i - 2]:
                fvgs.append({"i": i, "top": l[i - 2], "bot": h[i], "dir": -1, "filled": None})
        for f in fvgs:
            if f["filled"] is None and f["i"] < i:
                if (f["dir"] == 1 and l[i] <= f["bot"]) or (f["dir"] == -1 and h[i] >= f["top"]):
                    f["filled"] = i
        for ob in obs:
            if ob["dead"] is None and ob["i"] < i:
                if ob["dir"] == 1 and cl[i] < ob["bot"]:
                    ob["dead"] = i
                elif ob["dir"] == -1 and cl[i] > ob["top"]:
                    ob["dead"] = i
                elif ob["touched"] is None and ((ob["dir"] == 1 and l[i] <= ob["top"]) or (ob["dir"] == -1 and h[i] >= ob["bot"])):
                    ob["touched"] = i
        # -- liquidity sweeps: wick through the pool, close back inside
        for pool in pools:
            if pool["swept"] is None and pool["i1"] < i:
                if pool["type"] == "EQH" and h[i] > pool["price"] and cl[i] < pool["price"]:
                    pool["swept"] = i; last_sweep = {"i": i, "dir": -1, "price": pool["price"], "type": "EQH"}
                elif pool["type"] == "EQL" and l[i] < pool["price"] and cl[i] > pool["price"]:
                    pool["swept"] = i; last_sweep = {"i": i, "dir": 1, "price": pool["price"], "type": "EQL"}
                elif (pool["type"] == "EQH" and cl[i] > pool["price"]) or (pool["type"] == "EQL" and cl[i] < pool["price"]):
                    pool["swept"] = -1                              # taken out by a close: it was a breakout, not a sweep
        # -- displacement and candle patterns
        if avg_body[i] and bodies[i] > 2.0 * avg_body[i] and (h[i] - l[i]) > 0 and bodies[i] / (h[i] - l[i]) > 0.6:
            last_disp = {"i": i, "dir": 1 if cl[i] > o[i] else -1}
        candle = 0; cnote = "no pattern"
        if i >= 1:
            rng_ = h[i] - l[i] or 1e-9
            lower, upper = min(o[i], cl[i]) - l[i], h[i] - max(o[i], cl[i])
            if cl[i] > o[i] and cl[i - 1] < o[i - 1] and cl[i] >= o[i - 1] and o[i] <= cl[i - 1]:
                candle, cnote = 1, "bullish engulfing"
            elif cl[i] < o[i] and cl[i - 1] > o[i - 1] and cl[i] <= o[i - 1] and o[i] >= cl[i - 1]:
                candle, cnote = -1, "bearish engulfing"
            elif lower >= 2 * bodies[i] and lower / rng_ >= 0.6:
                candle, cnote = 1, "bullish rejection wick (pin bar)"
            elif upper >= 2 * bodies[i] and upper / rng_ >= 0.6:
                candle, cnote = -1, "bearish rejection wick (pin bar)"
        # -- dealing range: origin swing to the latest structural extreme
        if structure == 1 and sh and sl:
            top = max((s for s in sh if s["i"] <= i), key=lambda s: s["i"], default=None)
            lows_before = [s for s in sl if top and s["i"] < top["i"]]
            bot = lows_before[-1] if lows_before else None
            rng = {"hi": top["price"], "lo": bot["price"], "i0": bot["i"], "i1": top["i"]} if top and bot and top["price"] > bot["price"] else rng
        elif structure == -1 and sh and sl:
            bot = max((s for s in sl if s["i"] <= i), key=lambda s: s["i"], default=None)
            highs_before = [s for s in sh if bot and s["i"] < bot["i"]]
            top = highs_before[-1] if highs_before else None
            rng = {"hi": top["price"], "lo": bot["price"], "i0": top["i"], "i1": bot["i"]} if top and bot and top["price"] > bot["price"] else rng
        # -- votes for this bar
        v: dict[str, tuple[int, str]] = {}
        if events:
            e = events[-1]
            age = i - e["i"]
            v["structure"] = (structure, f"{'bullish' if structure == 1 else 'bearish'} — {e['type']} {'up' if e['dir'] == 1 else 'down'} through {e['level']:,.0f}, {age} bar{'s' if age != 1 else ''} ago")
        elif swings:
            v["structure"] = (0, "no structure break yet")
        zone = 0; znote = "not at a zone"
        live_obs = [ob for ob in obs if ob["dead"] is None and ob["i"] < i]
        live_fvgs = [f for f in fvgs if f["filled"] is None and f["i"] < i]
        for z, kind in [(ob, "order block") for ob in live_obs[-6:]] + [(f, "fair value gap") for f in live_fvgs[-6:]]:
            inside = l[i] <= z["top"] and h[i] >= z["bot"]
            if inside and z["dir"] == 1 and structure == 1:
                zone, znote = 1, f"price at a bullish {kind} {z['bot']:,.0f}–{z['top']:,.0f} in bullish structure"; break
            if inside and z["dir"] == -1 and structure == -1:
                zone, znote = -1, f"price at a bearish {kind} {z['bot']:,.0f}–{z['top']:,.0f} in bearish structure"; break
            if inside:
                znote = f"price at a {'bullish' if z['dir'] == 1 else 'bearish'} {kind} against structure"
        if zone == 0 and znote == "not at a zone":
            below = [z for z in live_obs + live_fvgs if z["dir"] == 1 and z["top"] < cl[i]]
            above = [z for z in live_obs + live_fvgs if z["dir"] == -1 and z["bot"] > cl[i]]
            if below or above:
                znote = "nearest zones: " + " · ".join(x for x in [f"demand {max(below, key=lambda z: z['top'])['top']:,.0f}" if below else "", f"supply {min(above, key=lambda z: z['bot'])['bot']:,.0f}" if above else ""] if x)
        v["zone"] = (zone, znote)
        if last_sweep and i - last_sweep["i"] <= 3:
            v["liquidity"] = (last_sweep["dir"], f"{last_sweep['type']} at {last_sweep['price']:,.0f} swept {i - last_sweep['i']} bar{'s' if i - last_sweep['i'] != 1 else ''} ago — {'stops taken below, reversal bias up' if last_sweep['dir'] == 1 else 'stops taken above, reversal bias down'}")
        else:
            openp = [p_ for p_ in pools if p_["swept"] is None and p_["i1"] < i]
            up_ = [p_ for p_ in openp if p_["price"] > cl[i]]; dn_ = [p_ for p_ in openp if p_["price"] < cl[i]]
            parts = [f"resting above {min(up_, key=lambda p_: p_['price'])['price']:,.0f}" if up_ else "", f"below {max(dn_, key=lambda p_: p_['price'])['price']:,.0f}" if dn_ else ""]
            v["liquidity"] = (0, "no recent sweep; liquidity " + " and ".join(x for x in parts if x) if any(parts) else "no recent sweep, no equal highs/lows nearby")
        if rng and rng["hi"] > rng["lo"]:
            pos = (cl[i] - rng["lo"]) / (rng["hi"] - rng["lo"])
            if structure == 1:
                v["range"] = (1 if pos < 0.5 else 0, f"{'discount' if pos < 0.5 else 'premium'} ({pos * 100:.0f}% of {rng['lo']:,.0f}–{rng['hi']:,.0f}) — {'buys favoured' if pos < 0.5 else 'wait for a discount to buy'}")
            elif structure == -1:
                v["range"] = (-1 if pos > 0.5 else 0, f"{'premium' if pos > 0.5 else 'discount'} ({pos * 100:.0f}% of {rng['lo']:,.0f}–{rng['hi']:,.0f}) — {'sells favoured' if pos > 0.5 else 'wait for a premium to sell'}")
            else:
                v["range"] = (0, f"{pos * 100:.0f}% of the range, no structure")
        if last_disp and i - last_disp["i"] <= 3:
            v["displacement"] = (last_disp["dir"], f"{'bullish' if last_disp['dir'] == 1 else 'bearish'} displacement candle {i - last_disp['i']} bar{'s' if i - last_disp['i'] != 1 else ''} ago")
        else:
            v["displacement"] = (0, "no displacement in the last 3 bars")
        v["candle"] = (candle, cnote)
        votes.append(v)
    draw = {"swings": [{k: s[k] for k in ("i", "price", "type", "tag")} for s in swings[-60:]],
            "events": events[-30:],
            "fvgs": [f for f in fvgs if f["filled"] is None][-12:],
            "obs": [ob for ob in obs if ob["dead"] is None][-8:],
            "pools": [p_ for p_ in pools if p_["swept"] is None or p_["swept"] > 0][-12:],
            "range": rng, "structure": structure}
    return votes, draw

# ---------------------------------------------------------------------------
# the composite
# ---------------------------------------------------------------------------
SYSTEMS = [
    ("turtle", "Turtle breakout", "Dennis & Eckhardt", 1.5),
    ("ma200", "200-bar rule", "Paul Tudor Jones", 1.5),
    ("grail", "Holy Grail pullback", "Linda Raschke", 1.0),
    ("macd", "MACD 12/26/9", "Gerald Appel", 1.0),
    ("rsi", "RSI 14", "Welles Wilder", 1.0),
    ("supertrend", "Supertrend 10/3", "ATR trailing", 1.5),
    ("ichimoku", "Ichimoku cloud", "Goichi Hosoda", 1.5),
    ("bb", "Bollinger %B", "John Bollinger", 0.5),
    ("ribbon", "EMA ribbon 9/21/50", "trend structure", 1.0),
]
WEIGHT = {k: w for k, _, _, w in SYSTEMS}


def label(score: float, direction: int | None = None) -> str:
    """Signal words. With a direction (the hysteresis state) the word follows the state; the strength follows the score."""
    if direction is not None:
        if direction == 0:
            return "NEUTRAL"
        strong = abs(score) >= 0.5
        return ("STRONG BUY" if strong else "BUY") if direction == 1 else ("STRONG SELL" if strong else "SELL")
    if score >= 0.5:
        return "STRONG BUY"
    if score >= 0.25:
        return "BUY"
    if score <= -0.5:
        return "STRONG SELL"
    if score <= -0.25:
        return "SELL"
    return "NEUTRAL"


def analyze(c: list[list], tf: str = "1d") -> dict:
    n = len(c)
    if n < 60:
        return {"error": "not enough candles"}
    closes = [k[4] for k in c]
    highs, lows = [k[2] for k in c], [k[3] for k in c]
    e9, e21, e50, e20 = ema(closes, 9), ema(closes, 21), ema(closes, 50), ema(closes, 20)
    s200 = sma(closes, 200)
    e12, e26 = ema(closes, 12), ema(closes, 26)
    macd = [None if a is None or b is None else a - b for a, b in zip(e12, e26)]
    macd_vals = [m for m in macd if m is not None]
    sig_tail = ema(macd_vals, 9)
    signal = [None] * (n - len(sig_tail)) + sig_tail
    hist = [None if m is None or s is None else m - s for m, s in zip(macd, signal)]
    r = rsi(closes)
    adx_, pdi, ndi = adx(c)
    atr_ = _wilder(true_range(c), 14)
    st_line, st_dir = supertrend(c)
    hh20, ll20 = rolling(highs, 20, max), rolling(lows, 20, min)
    hh10, ll10 = rolling(highs, 10, max), rolling(lows, 10, min)
    bb_mid, bb_up, bb_lo = bollinger(closes)
    ich = ichimoku(c)

    pa_votes, pa_draw = price_action(c, atr_, left=3 if tf != "1d" else 3)
    votes_hist: list[dict] = []
    scores: list = []
    classic_scores: list = []
    pa_scores: list = []
    turtle = 0
    for i in range(n):
        v: dict[str, tuple[int, str]] = {}
        cl = closes[i]
        # turtle: enter on 20-bar breakout, exit on 10-bar reversal
        if hh20[i] is not None:
            if cl > hh20[i]:
                turtle = 1
            elif cl < ll20[i]:
                turtle = -1
            elif turtle == 1 and ll10[i] is not None and cl < ll10[i]:
                turtle = 0
            elif turtle == -1 and hh10[i] is not None and cl > hh10[i]:
                turtle = 0
            v["turtle"] = (turtle, "long since the 20-bar breakout" if turtle == 1 else "short since the 20-bar breakdown" if turtle == -1 else "flat — no breakout held")
        if s200[i] is not None:
            above = cl > s200[i]
            v["ma200"] = (1 if above else -1, f"price {'above' if above else 'below'} the 200-bar average ({s200[i]:,.0f})")
        if adx_[i] is not None and e20[i] is not None and i > 0 and e20[i - 1] is not None:
            rising = e20[i] > e20[i - 1]
            touch = lows[i] <= e20[i] * 1.003 and highs[i] >= e20[i] * 0.997
            if adx_[i] > 30 and touch:
                v["grail"] = (1 if rising else -1, f"ADX {adx_[i]:.0f} > 30 and price is at the 20 EMA — {'buy' if rising else 'sell'} the pullback")
            else:
                v["grail"] = (0, f"ADX {adx_[i]:.0f}; {'waiting for a pullback to the 20 EMA' if adx_[i] > 30 else 'no trend to trade (ADX < 30)'}")
        if macd[i] is not None and signal[i] is not None:
            up = macd[i] > signal[i]
            v["macd"] = (1 if up else -1, f"MACD {'above' if up else 'below'} signal, histogram {'widening' if hist[i] is not None and i > 0 and hist[i - 1] is not None and abs(hist[i]) > abs(hist[i - 1]) else 'narrowing'}")
        if r[i] is not None:
            vote = 1 if r[i] > 55 else -1 if r[i] < 45 else 0
            note = f"RSI {r[i]:.0f}" + (" — overbought, don't chase" if r[i] > 70 else " — oversold, don't chase" if r[i] < 30 else " — bullish bias" if vote == 1 else " — bearish bias" if vote == -1 else " — no edge")
            v["rsi"] = (vote, note)
        if st_dir[i] is not None:
            v["supertrend"] = (st_dir[i], f"Supertrend {'up' if st_dir[i] == 1 else 'down'}, line at {st_line[i]:,.0f}")
        if ich["cloud_a"][i] is not None and ich["cloud_b"][i] is not None and ich["tenkan"][i] is not None and ich["kijun"][i] is not None:
            top, bot = max(ich["cloud_a"][i], ich["cloud_b"][i]), min(ich["cloud_a"][i], ich["cloud_b"][i])
            tk = ich["tenkan"][i] > ich["kijun"][i]
            if cl > top and tk:
                v["ichimoku"] = (1, "above the cloud, tenkan over kijun")
            elif cl < bot and not tk:
                v["ichimoku"] = (-1, "below the cloud, tenkan under kijun")
            else:
                v["ichimoku"] = (0, "inside the cloud" if bot <= cl <= top else "cloud and tenkan/kijun disagree")
        if bb_up[i] is not None and bb_up[i] > bb_lo[i]:
            pb = (cl - bb_lo[i]) / (bb_up[i] - bb_lo[i])
            v["bb"] = (1 if pb > 0.8 else -1 if pb < 0.2 else 0, f"%B {pb:.2f} — {'riding the upper band' if pb > 0.8 else 'riding the lower band' if pb < 0.2 else 'mid-band'}")
        if e50[i] is not None:
            if e9[i] > e21[i] > e50[i]:
                v["ribbon"] = (1, "9 > 21 > 50 EMA — stacked bullish" + (", 50 above 200 (golden cross)" if s200[i] is not None and e50[i] > s200[i] else ""))
            elif e9[i] < e21[i] < e50[i]:
                v["ribbon"] = (-1, "9 < 21 < 50 EMA — stacked bearish" + (", 50 below 200 (death cross)" if s200[i] is not None and e50[i] < s200[i] else ""))
            else:
                v["ribbon"] = (0, "EMAs tangled — no structure")
        tw = sum(WEIGHT[k] for k in v)
        classic = sum(WEIGHT[k] * v[k][0] for k in v) / tw if tw else 0.0
        if adx_[i] is not None and adx_[i] < 20:
            classic *= 0.6                                      # rangebound: trend votes count less
        pv = pa_votes[i]
        pw = sum(PA_WEIGHT[k] for k in pv)
        pa = sum(PA_WEIGHT[k] * pv[k][0] for k in pv) / pw if pw else 0.0
        score = 0.5 * classic + 0.5 * pa if pw else classic
        votes_hist.append(v)
        classic_scores.append(round(classic, 3)); pa_scores.append(round(pa, 3))
        scores.append(round(score, 3) if len(v) >= 6 else None)

    # signal state + markers (flips only, so nothing repaints while a state persists)
    state, markers = 0, []
    states = []
    for i, s in enumerate(scores):
        if s is None:
            new = state
        elif state == 1:
            new = 1 if s > 0.1 else (-1 if s <= -0.25 else 0)
        elif state == -1:
            new = -1 if s < -0.1 else (1 if s >= 0.25 else 0)
        else:
            new = 1 if s >= 0.25 else -1 if s <= -0.25 else 0
        if new != state and s is not None:
            if new != 0:
                markers.append({"i": i, "t": c[i][0], "side": "BUY" if new == 1 else "SELL", "price": closes[i], "score": s})
            else:
                markers.append({"i": i, "t": c[i][0], "side": "EXIT", "price": closes[i], "score": s})
        state = new
        states.append(state)

    # how the flips have fared: 10-bar forward return in the signal's direction
    horizon = 10
    outcomes = [(m["side"], (closes[m["i"] + horizon] / m["price"] - 1) * (1 if m["side"] == "BUY" else -1)) for m in markers if m["side"] != "EXIT" and m["i"] + horizon < n]
    stats = None
    if outcomes:
        wins = sum(1 for _, x in outcomes if x > 0)
        stats = {"n": len(outcomes), "hit_rate": round(100 * wins / len(outcomes), 1), "avg_pct": round(100 * sum(x for _, x in outcomes) / len(outcomes), 2),
                 "best_pct": round(100 * max(x for _, x in outcomes), 2), "worst_pct": round(100 * min(x for _, x in outcomes), 2), "horizon": horizon}

    i = n - 1
    last, score = c[i], scores[i] or 0.0
    a = atr_[i] or 0.0
    direction = states[i]
    if direction == 1:
        stop = st_line[i] if st_dir[i] == 1 and st_line[i] < closes[i] else closes[i] - 2 * a
        stop = max(stop, closes[i] - 3 * a)
    elif direction == -1:
        stop = st_line[i] if st_dir[i] == -1 and st_line[i] > closes[i] else closes[i] + 2 * a
        stop = min(stop, closes[i] + 3 * a)
    else:
        stop = None
    risk = abs(closes[i] - stop) if stop else None
    target = (closes[i] + direction * 2 * risk) if risk else None
    regime = "trending" if (adx_[i] or 0) >= 25 else "rangebound" if (adx_[i] or 0) < 20 else "building"
    systems = []
    for key, name, who, w in SYSTEMS:
        vote, note = votes_hist[i].get(key, (0, "warming up"))
        systems.append({"key": key, "name": name, "who": who, "weight": w, "vote": vote, "note": note, "group": "classic"})
    for key, name, who, w in PA_SYSTEMS:
        vote, note = pa_votes[i].get(key, (0, "warming up"))
        systems.append({"key": key, "name": name, "who": who, "weight": w, "vote": vote, "note": note, "group": "price action"})
    cs, ps = classic_scores[i], pa_scores[i]
    confluence = "CONFLUENCE" if (cs >= 0.2 and ps >= 0.2) or (cs <= -0.2 and ps <= -0.2) else "CONFLICT" if (cs >= 0.2 and ps <= -0.2) or (cs <= -0.2 and ps >= 0.2) else "PARTIAL"
    since = None
    for m in reversed(markers):
        if m["side"] != "EXIT":
            since = m; break
    return {
        "tf": tf, "bars": n, "last": {"t": last[0], "o": last[1], "h": last[2], "l": last[3], "c": last[4]},
        "score": round(score, 3), "signal": label(score, direction), "direction": direction, "regime": regime,
        "classic_score": cs, "pa_score": ps, "confluence": confluence, "structure": pa_draw["structure"], "pa": pa_draw,
        "adx": round(adx_[i], 1) if adx_[i] is not None else None, "rsi": round(r[i], 1) if r[i] is not None else None, "atr": round(a, 2),
        "entry": round(closes[i], 2), "stop": round(stop, 2) if stop else None, "target": round(target, 2) if target else None,
        "risk_pct": round(100 * risk / closes[i], 2) if risk else None,
        "since": since, "systems": systems, "stats": stats,
        "markers": markers[-40:],
        "series": {"t": [k[0] for k in c], "o": [k[1] for k in c], "h": highs, "l": lows, "c": closes, "v": [k[5] for k in c],
                   "e21": e21, "e50": e50, "s200": s200, "st": st_line, "st_dir": st_dir, "bb_up": bb_up, "bb_lo": bb_lo, "score": scores, "state": states,
                   "classic": classic_scores, "pa_score": pa_scores},
    }


def slice_view(full: dict, bars: int) -> dict:
    """Trim an analyze() result to the last `bars` candles, shifting every drawing index."""
    d = dict(full)
    if "series" in d:
        n = len(d["series"]["t"])
        cut = max(0, n - bars)
        d["series"] = {k: v[cut:] for k, v in d["series"].items()}
        d["markers"] = [dict(m, i=m["i"] - cut) for m in d["markers"] if m["i"] >= cut]
        pa = d["pa"]
        d["pa"] = {"structure": pa["structure"],
                   "swings": [dict(x, i=x["i"] - cut) for x in pa["swings"] if x["i"] >= cut],
                   "events": [dict(x, i=x["i"] - cut, **{"from": max(0, x["from"] - cut)}) for x in pa["events"] if x["i"] >= cut],
                   "fvgs": [dict(x, i=max(0, x["i"] - cut)) for x in pa["fvgs"]],
                   "obs": [dict(x, i=max(0, x["i"] - cut)) for x in pa["obs"]],
                   "pools": [dict(x, i0=max(0, x["i0"] - cut), i1=max(0, x["i1"] - cut), swept=(x["swept"] - cut if x["swept"] and x["swept"] > 0 else x["swept"])) for x in pa["pools"]],
                   "range": dict(pa["range"], i0=max(0, pa["range"]["i0"] - cut), i1=max(0, pa["range"]["i1"] - cut)) if pa["range"] else None}
        d["offset"] = cut
    return d


class Gold:
    def __init__(self):
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, dict]] = {}
        self._spot: tuple[float, float | None] = (0.0, None)

    def spot(self) -> float | None:
        if time.time() - self._spot[0] > 60:
            self._spot = (time.time(), spot_xau() or self._spot[1])
        return self._spot[1]

    def view(self, tf: str = "1d", bars: int = 220, usdinr: float | None = None) -> dict:
        tf = tf if tf in TFS else "1d"
        ttl = TFS[tf][2]
        with self._lock:
            hit = self._cache.get(tf)
        if not hit or time.time() - hit[0] > ttl:
            try:
                data = analyze(fetch_candles(tf), tf)
                with self._lock:
                    self._cache[tf] = (time.time(), data)
                hit = self._cache[tf]
            except Exception as exc:                                # noqa: BLE001
                log.info("gold: refresh failed: %s", exc)
                if not hit:
                    return {"error": f"gold candles unavailable: {str(exc)[:80]}"}
        d = slice_view(hit[1], bars)
        try:
            import footprint as _fp
            _fp.attach(d)
        except Exception:                                           # noqa: BLE001
            pass
        d["spot_xau"] = self.spot()
        d["source"] = "binance PAXGUSDT"
        if usdinr and d.get("entry"):
            d["usdinr"] = round(usdinr, 2)
            d["inr_10g"] = round(d["entry"] * usdinr * OZ_PER_10G, 0)
        d["as_of"] = hit[0]
        return d
