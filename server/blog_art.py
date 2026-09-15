"""Generated illustrations for blog posts: branded SVG in the site's palette, deterministic per slug,
no external images (nothing to license, nothing to load). Guides get a purpose-drawn diagram; daily
desk reads get a hero drawn from the day's real path and an OI-walls figure."""
from __future__ import annotations

import math
import random

W, H = 1200, 520
BG, GRID = "#06031a", "rgba(190,150,255,.10)"
GOLD, CYAN, PINK, UP, DOWN, FAINT, TEXT, VIOLET = "#f5c842", "#7fe0f0", "#ff6ec7", "#3dd68c", "#ff5c6c", "#6d609e", "#f1edff", "#6a35f0"
FONT = "IBM Plex Mono, ui-monospace, Menlo, monospace"


def _svg(body: str, w: int = W, h: int = H, label: str = "") -> str:
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}" preserveAspectRatio="xMidYMid meet">'
            f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#130b36"/><stop offset="1" stop-color="{BG}"/></linearGradient>'
            f'<linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GOLD}" stop-opacity=".35"/><stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="cf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity=".3"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient></defs>'
            f'<rect width="{w}" height="{h}" fill="url(#bg)"/>{_grid(w, h)}{body}</svg>')


def _grid(w: int, h: int, step: int = 60) -> str:
    out = []
    for x in range(step, w, step):
        out.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{h}" stroke="{GRID}"/>')
    for y in range(step, h, step):
        out.append(f'<line x1="0" y1="{y}" x2="{w}" y2="{y}" stroke="{GRID}"/>')
    return "".join(out)


def _t(x, y, s, color=FAINT, size=16, anchor="start", weight="500") -> str:
    return f'<text x="{x:.0f}" y="{y:.0f}" fill="{color}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{s}</text>'


def _path(points: list[tuple[float, float]], color: str, width: float = 2.5, dash: str = "") -> str:
    d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"{dash_attr}/>'


def _walk(seed: str, n: int, drift: float = 0.0, vol: float = 1.0, start: float = 100.0) -> list[float]:
    r = random.Random(seed)
    px, out = start, []
    for _ in range(n):
        px += drift + r.gauss(0, vol)
        out.append(px)
    return out


def _candles(vals: list[float], x0: float, x1: float, y0: float, y1: float, seed: str, w: float | None = None) -> tuple[str, callable, callable]:
    r = random.Random(seed + "c")
    n = len(vals)
    lo, hi = min(vals) - 3, max(vals) + 3
    sx = lambda i: x0 + (x1 - x0) * i / max(1, n - 1)
    sy = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
    bw = w or max(3.0, (x1 - x0) / n * 0.6)
    out = []
    for i, c in enumerate(vals):
        o = vals[i - 1] if i else c - 0.5
        h, l = max(o, c) + abs(r.gauss(0, .7)), min(o, c) - abs(r.gauss(0, .7))
        col = UP if c >= o else DOWN
        out.append(f'<line x1="{sx(i):.1f}" y1="{sy(h):.1f}" x2="{sx(i):.1f}" y2="{sy(l):.1f}" stroke="{col}" stroke-width="1.5"/>'
                   f'<rect x="{sx(i) - bw / 2:.1f}" y="{sy(max(o, c)):.1f}" width="{bw:.1f}" height="{max(2, sy(min(o, c)) - sy(max(o, c))):.1f}" fill="{col}" rx="1"/>')
    return "".join(out), sx, sy


# ---------------------------------------------------------------------------
# guide figures
# ---------------------------------------------------------------------------
def fig_option_chain() -> str:
    r = random.Random("chain")
    strikes = list(range(22800, 24050, 50))
    spot = 23420
    body = []
    x0, x1, mid = 90, 1130, 300
    sx = lambda k: x0 + (x1 - x0) * (k - strikes[0]) / (strikes[-1] - strikes[0])
    for k in strikes:
        d = abs(k - spot) / 50
        ce = max(5, 160 * math.exp(-((k - 23600) / 220) ** 2) + r.random() * 30) if k >= spot - 100 else 15 + r.random() * 10
        pe = max(5, 160 * math.exp(-((k - 23200) / 220) ** 2) + r.random() * 30) if k <= spot + 100 else 15 + r.random() * 10
        body.append(f'<rect x="{sx(k) - 9:.0f}" y="{mid - ce:.0f}" width="18" height="{ce:.0f}" fill="{CYAN}" opacity=".8" rx="2"/>')
        body.append(f'<rect x="{sx(k) - 9:.0f}" y="{mid + 4:.0f}" width="18" height="{pe:.0f}" fill="{PINK}" opacity=".8" rx="2"/>')
    body.append(f'<line x1="{x0}" y1="{mid}" x2="{x1}" y2="{mid}" stroke="{FAINT}"/>')
    body.append(f'<line x1="{sx(spot):.0f}" y1="60" x2="{sx(spot):.0f}" y2="470" stroke="{GOLD}" stroke-dasharray="6 5"/>' + _t(sx(spot) + 8, 80, "SPOT 23,420", GOLD))
    body.append(f'<rect x="{sx(23600) - 22:.0f}" y="118" width="44" height="186" fill="none" stroke="{CYAN}" stroke-dasharray="4 3"/>' + _t(sx(23600), 108, "CALL WALL", CYAN, 15, "middle"))
    body.append(f'<rect x="{sx(23200) - 22:.0f}" y="300" width="44" height="190" fill="none" stroke="{PINK}" stroke-dasharray="4 3"/>' + _t(sx(23200), 505, "PUT WALL", PINK, 15, "middle"))
    body.append(_t(sx(23400), 505, "MAX PAIN 23,400", GOLD, 15, "middle"))
    body.append(_t(x0, 40, "CALL OI ▲", CYAN, 15) + _t(x0 + 130, 40, "PUT OI ▼", PINK, 15) + _t(x1, 40, "PCR 1.06", TEXT, 15, "end"))
    return _svg("".join(body), label="Open interest by strike with call wall, put wall and max pain")


def fig_expected_move() -> str:
    body = []
    x0, x1, base = 100, 1100, 430
    mu, sig = 600, 150
    pts = []
    for i in range(201):
        x = x0 + (x1 - x0) * i / 200
        y = base - 330 * math.exp(-((x - mu) / sig) ** 2 / 2)
        pts.append((x, y))
    area = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts if mu - sig <= x <= mu + sig) + f" L{mu + sig},{base} L{mu - sig},{base} Z"
    body.append(f'<path d="{area}" fill="url(#gf)"/>')
    body.append(_path(pts, GOLD, 3))
    for k, lab in ((-2, "−2σ"), (-1, "−1σ"), (0, "SPOT"), (1, "+1σ"), (2, "+2σ")):
        x = mu + k * sig
        body.append(f'<line x1="{x}" y1="{base}" x2="{x}" y2="{base + 14}" stroke="{FAINT}"/>' + _t(x, base + 36, lab, GOLD if k == 0 else FAINT, 15, "middle"))
    body.append(f'<line x1="{mu - sig}" y1="90" x2="{mu + sig}" y2="90" stroke="{CYAN}" stroke-width="3"/>' + _t(mu, 76, "EXPECTED DAY MOVE = SPOT × IV × √(1/252)", CYAN, 16, "middle"))
    body.append(f'<line x1="{mu - 0.8 * sig}" y1="130" x2="{mu + 0.8 * sig}" y2="130" stroke="{PINK}" stroke-width="3"/>' + _t(mu, 158, "ATM STRADDLE ≈ 0.8σ", PINK, 15, "middle"))
    body.append(_t(x0, 480, "68% of days close inside ±1σ · sellers earn here", TEXT, 15) + _t(x1, 480, "buyers need the tails", TEXT, 15, "end"))
    return _svg("".join(body), label="Expected move bell curve with one-sigma band and straddle")


def fig_iv_percentile() -> str:
    body = []
    x0, x1, y0, y1 = 90, 1130, 70, 440
    minutes = 75
    sx = lambda i: x0 + (x1 - x0) * i / (minutes - 1)
    sy = lambda v: y1 - (v - 0.3) / (1.1 - 0.3) * (y1 - y0)
    for c in range(14):
        r = random.Random(f"ivp{c}")
        start = 0.55 + r.random() * 0.4
        pts = [(sx(i), sy(start * (1 - 0.55 * i / minutes) + r.gauss(0, .01))) for i in range(minutes)]
        body.append(_path(pts, "rgba(170,140,255,.35)", 1.5))
    med = [(sx(i), sy(0.75 * (1 - 0.55 * i / minutes))) for i in range(minutes)]
    body.append(_path(med, GOLD, 2.5, "8 6"))
    today = [(sx(i), sy(0.92 * (1 - 0.5 * i / minutes))) for i in range(48)]
    body.append(_path(today, CYAN, 4))
    body.append(f'<circle cx="{today[-1][0]:.0f}" cy="{today[-1][1]:.0f}" r="7" fill="{CYAN}"/>' + _t(today[-1][0] + 14, today[-1][1] + 6, "TODAY · 84th PERCENTILE", CYAN, 16))
    body.append(_t(x0, 46, "ATM STRADDLE % OF SPOT · SAME DTE, LAST 20 CYCLES", FAINT, 15) + _t(x1, 46, "gold = median", GOLD, 15, "end"))
    for lab, i in (("09:15", 0), ("11:45", 30), ("13:45", 54), ("15:30", 74)):
        body.append(_t(sx(i), 475, lab, FAINT, 14, "middle"))
    return _svg("".join(body), label="Today's straddle decay against past expiry cycles")


def fig_oi_buildup() -> str:
    body = []
    cells = [("PRICE ▲  OI ▲", "LONG BUILD-UP", "fresh buying", UP), ("PRICE ▼  OI ▲", "SHORT BUILD-UP", "fresh writing", DOWN),
             ("PRICE ▲  OI ▼", "SHORT COVERING", "writers squeezed", CYAN), ("PRICE ▼  OI ▼", "LONG UNWINDING", "buyers give up", PINK)]
    for i, (a, b, c, col) in enumerate(cells):
        x = 120 + (i % 2) * 500
        y = 70 + (i // 2) * 210
        body.append(f'<rect x="{x}" y="{y}" width="460" height="180" rx="6" fill="rgba(18,10,51,.9)" stroke="{col}" stroke-width="2"/>')
        body.append(_t(x + 24, y + 44, a, FAINT, 16) + _t(x + 24, y + 96, b, col, 34, "start", "700") + _t(x + 24, y + 140, c, TEXT, 18))
    return _svg("".join(body), label="The four OI build-up cases")


def fig_structure() -> str:
    body = []
    pts_v = [(60, 400), (170, 300), (260, 350), (380, 220), (470, 280), (600, 150), (690, 230), (780, 120), (880, 260), (960, 200), (1080, 380)]
    body.append(_path(pts_v, "rgba(127,224,240,.9)", 3))
    labels = [(170, 300, "HL", UP, -14), (260, 350, "HL", UP, 26), (380, 220, "HH", DOWN, -14), (470, 280, "HL", UP, 26), (600, 150, "HH", DOWN, -14), (690, 230, "HL", UP, 26), (780, 120, "HH", DOWN, -14), (880, 260, "LL", UP, 26), (960, 200, "LH", DOWN, -14)]
    for x, y, s, col, dy in labels:
        body.append(_t(x, y + dy, s, col, 16, "middle", "700"))
    body.append(f'<line x1="380" y1="220" x2="560" y2="220" stroke="{UP}" stroke-dasharray="5 4"/>' + _t(470, 208, "BOS ↑", UP, 15, "middle"))
    body.append(f'<line x1="600" y1="150" x2="760" y2="150" stroke="{UP}" stroke-dasharray="5 4"/>' + _t(680, 138, "BOS ↑", UP, 15, "middle"))
    body.append(f'<line x1="690" y1="230" x2="900" y2="230" stroke="{GOLD}" stroke-dasharray="5 4" stroke-width="2"/>' + _t(800, 250, "CHoCH ↓ — trend flips", GOLD, 17, "middle", "700"))
    body.append(_t(60, 470, "UPTREND: HIGHER HIGHS, HIGHER LOWS", FAINT, 15) + _t(1080, 470, "REVERSAL", DOWN, 15, "end"))
    return _svg("".join(body), label="Swing structure with break of structure and change of character")


def fig_order_blocks() -> str:
    vals = _walk("ob", 40, 0.9, 1.4)
    for i in range(12, 16):
        vals[i] = vals[11] - (i - 11) * 0.8
    for i in range(16, 24):
        vals[i] = vals[15] + (i - 15) * 2.4
    cands, sx, sy = _candles(vals, 80, 1120, 70, 440, "ob")
    body = [cands]
    body.append(f'<rect x="{sx(13) - 20:.0f}" y="{sy(vals[15] + 1.2):.0f}" width="{1120 - sx(13):.0f}" height="{sy(vals[15] - 2) - sy(vals[15] + 1.2):.0f}" fill="rgba(106,53,240,.35)" stroke="{VIOLET}"/>')
    body.append(_t(sx(13) - 16, sy(vals[15] + 1.2) - 10, "ORDER BLOCK — last red candle before the break", "#b9a6ff", 15))
    body.append(f'<rect x="{sx(18) - 12:.0f}" y="{sy(vals[19] + 0.5):.0f}" width="{1120 - sx(18):.0f}" height="{sy(vals[17] + 0.5) - sy(vals[19] + 0.5):.0f}" fill="rgba(61,214,140,.16)" stroke="{UP}" stroke-dasharray="4 3"/>')
    body.append(_t(sx(18) - 8, sy(vals[19] + 0.5) - 8, "FAIR VALUE GAP — three-candle imbalance", UP, 15))
    body.append(f'<line x1="{sx(4):.0f}" y1="{sy(max(vals[:12])):.0f}" x2="{sx(20):.0f}" y2="{sy(max(vals[:12])):.0f}" stroke="{UP}" stroke-dasharray="5 4"/>' + _t(sx(20) + 6, sy(max(vals[:12])) + 5, "BOS", UP, 15))
    return _svg("".join(body), label="Order block and fair value gap after a break of structure")


def fig_liquidity() -> str:
    vals = _walk("liq", 44, 0.0, 1.2, 100)
    for i in (10, 22):
        vals[i] = 106.0
    vals[30] = 106.2
    for i in range(31, 44):
        vals[i] = 104 - (i - 30) * 0.9
    cands, sx, sy = _candles(vals, 80, 1120, 70, 440, "liq")
    body = [cands]
    body.append(f'<line x1="{sx(8):.0f}" y1="{sy(106):.0f}" x2="{sx(31):.0f}" y2="{sy(106):.0f}" stroke="{DOWN}" stroke-dasharray="6 4" stroke-width="2"/>' + _t(sx(8), sy(106) - 12, "EQUAL HIGHS = RESTING BUY STOPS", DOWN, 15))
    body.append(f'<line x1="{sx(30):.0f}" y1="{sy(106.2):.0f}" x2="{sx(30):.0f}" y2="{sy(108.3):.0f}" stroke="{GOLD}" stroke-width="3"/>' + _t(sx(30), sy(108.3) - 10, "SWEEP ×", GOLD, 18, "middle", "700") + _t(sx(30), sy(108.3) - 32, "wick through, close back below", GOLD, 14, "middle"))
    body.append(_t(sx(40), sy(vals[40]) + 34, "TRAPPED BREAKOUT LONGS FUEL THE DROP", DOWN, 15, "end"))
    return _svg("".join(body), label="Liquidity sweep of equal highs")


def fig_greeks() -> str:
    body = []
    x0, x1, y0, y1 = 100, 560, 80, 430
    pts = [(x0 + (x1 - x0) * i / 100, y1 - (y1 - y0) * (1 - math.sqrt(i / 100))) for i in range(101)]
    body.append(_path(pts, GOLD, 3) + _t(x0, 56, "OPTION VALUE vs DAYS TO EXPIRY (THETA)", GOLD, 15) + _t(x0, 470, "30 days", FAINT, 14) + _t(x1, 470, "expiry", FAINT, 14, "end"))
    body.append(f'<rect x="{x1 - 60}" y="{y0}" width="60" height="{y1 - y0}" fill="rgba(245,200,66,.12)"/>' + _t(x1 - 30, y0 - 8, "last 2 days", GOLD, 13, "middle"))
    x0, x1 = 660, 1120
    gam = [(x0 + (x1 - x0) * i / 100, y1 - (y1 - y0) * math.exp(-((i - 50) / 9) ** 2)) for i in range(101)]
    gam2 = [(x0 + (x1 - x0) * i / 100, y1 - (y1 - y0) * 0.35 * math.exp(-((i - 50) / 25) ** 2)) for i in range(101)]
    body.append(_path(gam2, "rgba(127,224,240,.5)", 2, "6 5") + _path(gam, CYAN, 3) + _t(x0, 56, "GAMMA BY STRIKE: 30 DAYS OUT (dashed) vs EXPIRY DAY", CYAN, 15))
    body.append(_t((x0 + x1) / 2, 470, "ATM", FAINT, 14, "middle") + _t(x0, 470, "OTM", FAINT, 14) + _t(x1, 470, "ITM", FAINT, 14, "end"))
    body.append(_t(600, 250, "theta earned = gamma owed", TEXT, 16, "middle", "700"))
    return _svg("".join(body), label="Theta decay and expiry-day gamma")


def fig_regime() -> str:
    body = []
    checks = [("ADX < 20", "no trend", True), ("BB WIDTH 15–60th pct", "calm, not coiled", True), ("PRICE MID-RANGE", "30–70% of range", True), ("STRADDLE > 60th pct", "premium rich", True), ("REALISED < 80% EXPECTED", "quiet tape", False)]
    for i, (a, b, ok) in enumerate(checks):
        y = 70 + i * 82
        col = UP if ok else DOWN
        body.append(f'<rect x="120" y="{y}" width="960" height="64" rx="6" fill="rgba(18,10,51,.9)" stroke="{col}"/>')
        body.append(f'<circle cx="160" cy="{y + 32}" r="14" fill="{col}"/>' + _t(160, y + 38, "✓" if ok else "✕", "#0c0626", 18, "middle", "700"))
        body.append(_t(200, y + 40, a, TEXT, 20, "start", "700") + _t(1060, y + 40, b, col, 16, "end"))
    body.append(_t(600, 500, "4 of 5 → SELL PREMIUM, SIZE DOWN · 5 of 5 → FULL SIZE · TREND → STAND ASIDE", GOLD, 16, "middle"))
    return _svg("".join(body), label="Option-selling regime checklist")


def fig_gold() -> str:
    vals = _walk("gold", 120, 0.35, 1.6, 100)
    pts_c = [(80 + 1040 * i / 119, 440 - (v - min(vals)) / (max(vals) - min(vals)) * 340) for i, v in enumerate(vals)]
    body = [f'<path d="M{pts_c[0][0]:.1f},440 ' + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts_c) + f' L{pts_c[-1][0]:.1f},440 Z" fill="url(#gf)"/>', _path(pts_c, GOLD, 3)]
    for i, side in ((18, "BUY"), (52, "SELL"), (74, "BUY"), (104, "SELL")):
        x, y = pts_c[i]
        col = UP if side == "BUY" else DOWN
        body.append(_t(x, y + (34 if side == "BUY" else -22), ("▲ " if side == "BUY" else "▼ ") + side, col, 17, "middle", "700"))
    body.append(_t(80, 50, "XAU/USD · 1D · NINE SYSTEMS + SMART-MONEY STRUCTURE → ONE CALL", GOLD, 15) + _t(1120, 50, "non-repainting", FAINT, 14, "end"))
    return _svg("".join(body), label="Gold chart with engine signals")


def fig_scalp() -> str:
    vals = _walk("scalp", 90, 0.25, 1.0, 100)
    cands, sx, sy = _candles(vals, 80, 1120, 70, 440, "scalp")
    body = [cands]
    ema9 = [(sx(i), sy(sum(vals[max(0, i - 8):i + 1]) / len(vals[max(0, i - 8):i + 1]))) for i in range(90)]
    ema21 = [(sx(i), sy(sum(vals[max(0, i - 20):i + 1]) / len(vals[max(0, i - 20):i + 1]))) for i in range(90)]
    vwap = [(sx(i), sy(sum(vals[:i + 1]) / (i + 1))) for i in range(90)]
    body.append(_path(ema9, CYAN, 2) + _path(ema21, GOLD, 2) + _path(vwap, "#ffb347", 3, "8 5"))
    body.append(_t(80, 50, "EMA 9", CYAN, 15) + _t(160, 50, "EMA 21", GOLD, 15) + _t(250, 50, "SESSION VWAP", "#ffb347", 15) + _t(1120, 50, "LONG only above VWAP · SHORT only below", TEXT, 14, "end"))
    for i, side in ((24, "LONG"), (58, "EXIT"), (70, "LONG")):
        x, y = sx(i), sy(vals[i])
        body.append(_t(x, y + 34 if side != "EXIT" else y - 20, ("▲ " if side == "LONG" else "× ") + side, UP if side == "LONG" else FAINT, 16, "middle", "700"))
    return _svg("".join(body), label="Scalping chart with EMA, VWAP and Supertrend signals")


def fig_gex() -> str:
    body = []
    strikes = list(range(22800, 24050, 100))
    x0, x1, mid = 100, 1100, 280
    sx = lambda k: x0 + (x1 - x0) * (k - strikes[0]) / (strikes[-1] - strikes[0])
    cum = []
    acc = 0
    for k in strikes:
        v = (k - 23400) / 60 + (10 if k in (23500, 23600) else 0) - (12 if k in (23100, 23200) else 0)
        v = max(-150, min(150, v * 6))
        col = UP if v >= 0 else DOWN
        body.append(f'<rect x="{sx(k) - 18:.0f}" y="{min(mid, mid - v):.0f}" width="36" height="{abs(v) or 2:.0f}" fill="{col}" opacity=".85" rx="2"/>')
        acc += v
        cum.append((sx(k), mid - acc / 4))
    body.append(f'<line x1="{x0}" y1="{mid}" x2="{x1}" y2="{mid}" stroke="{FAINT}"/>' + _path(cum, GOLD, 3))
    flip = sx(23350)
    body.append(f'<line x1="{flip:.0f}" y1="60" x2="{flip:.0f}" y2="470" stroke="{GOLD}" stroke-dasharray="6 5" stroke-width="2"/>' + _t(flip, 48, "GAMMA FLIP", GOLD, 16, "middle", "700"))
    body.append(_t(x0, 500, "◀ NEGATIVE GAMMA · dealers chase moves", DOWN, 15) + _t(x1, 500, "POSITIVE GAMMA · dealers pin ▶", UP, 15, "end"))
    return _svg("".join(body), label="Dealer gamma exposure by strike with the flip level")


GUIDE_FIGS = {
    "how-to-read-an-option-chain": fig_option_chain, "expected-move-atm-straddle": fig_expected_move, "iv-percentile-is-premium-rich": fig_iv_percentile,
    "oi-build-up-explained": fig_oi_buildup, "market-structure-bos-choch": fig_structure, "order-blocks-and-fair-value-gaps": fig_order_blocks,
    "liquidity-sweeps-stop-hunts": fig_liquidity, "greeks-a-seller-watches": fig_greeks, "when-to-sell-premium-regime-checklist": fig_regime,
    "gold-trading-for-indian-traders": fig_gold, "scalping-index-options-vwap-supertrend": fig_scalp, "dealer-gamma-gex-explained": fig_gex,
}


def guide_hero(slug: str) -> str:
    fn = GUIDE_FIGS.get(slug)
    return fn() if fn else fig_structure()


# ---------------------------------------------------------------------------
# daily figures from real data
# ---------------------------------------------------------------------------
def daily_hero(label: str, path: list[list], prev_close: float | None, em: float | None, close: float | None, change: float | None) -> str:
    """Today's path with the expected-move band; falls back to a stylised walk if no path."""
    body = []
    x0, x1, y0, y1 = 90, 1130, 80, 440
    vals = [p[1] for p in path] if path else _walk(label, 75, 0.0, 1.0, close or 100)
    pc = prev_close or vals[0]
    lo, hi = min(vals + [pc - (em or 0)]), max(vals + [pc + (em or 0)])
    m = (hi - lo) * 0.1 or 1
    lo, hi = lo - m, hi + m
    n = max(75, len(vals))
    sx = lambda i: x0 + (x1 - x0) * i / (n - 1)
    sy = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)
    if em:
        body.append(f'<rect x="{x0}" y="{sy(pc + em):.0f}" width="{x1 - x0}" height="{sy(pc) - sy(pc + em):.0f}" fill="rgba(61,214,140,.10)"/>')
        body.append(f'<rect x="{x0}" y="{sy(pc):.0f}" width="{x1 - x0}" height="{sy(pc - em) - sy(pc):.0f}" fill="rgba(255,92,108,.10)"/>')
        for v, lab in ((pc + em, f"+1σ {pc + em:,.0f}"), (pc - em, f"−1σ {pc - em:,.0f}")):
            body.append(f'<line x1="{x0}" y1="{sy(v):.0f}" x2="{x1}" y2="{sy(v):.0f}" stroke="{GOLD}" stroke-dasharray="6 5"/>' + _t(x0 + 6, sy(v) - 6, lab, GOLD, 14))
    body.append(f'<line x1="{x0}" y1="{sy(pc):.0f}" x2="{x1}" y2="{sy(pc):.0f}" stroke="rgba(255,255,255,.3)" stroke-dasharray="2 4"/>' + _t(x1, sy(pc) - 6, f"prev {pc:,.0f}", FAINT, 14, "end"))
    pts = [(sx(i), sy(v)) for i, v in enumerate(vals)]
    body.append(f'<path d="M{pts[0][0]:.1f},{y1} ' + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) + f' L{pts[-1][0]:.1f},{y1} Z" fill="url(#cf)"/>')
    body.append(_path(pts, CYAN, 3))
    body.append(f'<circle cx="{pts[-1][0]:.0f}" cy="{pts[-1][1]:.0f}" r="7" fill="{CYAN}"/>')
    col = UP if (change or 0) >= 0 else DOWN
    body.append(_t(x0, 50, f"{label} · TODAY'S PATH vs EXPECTED MOVE", FAINT, 15) + _t(x1, 50, f"{(close or vals[-1]):,.1f}  {('+' if (change or 0) >= 0 else '')}{(change or 0):.2f}%", col, 22, "end", "700"))
    for lab, i in (("09:15", 0), ("11:00", int(n * 0.28)), ("13:00", int(n * 0.6)), ("15:30", n - 1)):
        body.append(_t(sx(i), 475, lab, FAINT, 14, "middle"))
    return _svg("".join(body), label=f"{label} intraday path against the expected move band")


def daily_walls(label: str, spot: float, call_wall, put_wall, max_pain, pcr) -> str:
    body = []
    x0, x1, y = 120, 1080, 260
    levels = [v for v in (spot, call_wall, put_wall, max_pain) if v]
    lo, hi = min(levels), max(levels)
    span = (hi - lo) or 1
    sx = lambda v: x0 + (x1 - x0) * (v - lo) / span
    body.append(f'<line x1="{x0 - 40}" y1="{y}" x2="{x1 + 40}" y2="{y}" stroke="{FAINT}" stroke-width="2"/>')
    for v, lab, col, dy in ((put_wall, "PUT WALL", PINK, 70), (max_pain, "MAX PAIN", GOLD, -60), (call_wall, "CALL WALL", CYAN, 70)):
        if not v:
            continue
        body.append(f'<line x1="{sx(v):.0f}" y1="{y - 40}" x2="{sx(v):.0f}" y2="{y + 40}" stroke="{col}" stroke-width="4"/>' + _t(sx(v), y + dy, lab, col, 16, "middle", "700") + _t(sx(v), y + dy + 24, f"{v:,.0f}", col, 18, "middle"))
    if spot:
        body.append(f'<circle cx="{sx(spot):.0f}" cy="{y}" r="12" fill="{TEXT}"/>' + _t(sx(spot), y - 26, "CLOSE", TEXT, 14, "middle") + _t(sx(spot), y - 44, f"{spot:,.1f}", TEXT, 18, "middle", "700"))
    body.append(_t(600, 60, f"{label} OPEN INTEREST MAP · NEAREST EXPIRY", FAINT, 15, "middle") + _t(600, 480, f"PCR {pcr:.2f}" if pcr else "", GOLD, 18, "middle", "700"))
    return _svg("".join(body), w=W, h=520, label=f"{label} call wall, put wall and max pain around the close")
