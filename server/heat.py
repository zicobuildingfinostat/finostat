"""HEAT: the market heatmap — every NSE stock the feed quotes, tiled by the day's move.
Pure functions over the feed's universe snapshot ({label: {symbol, exchange, name, fo, n50, price, change}})."""
from __future__ import annotations

UNIVERSES = ("n50", "fo", "all")


def rows(universe: dict, u: str = "fo", mode: str = "all", limit: int = 400) -> dict:
    u = u if u in UNIVERSES else "fo"
    out = []
    for key, e in (universe or {}).items():
        if e.get("exchange") != "NSE" or e.get("price") is None:
            continue
        if u == "n50" and not e.get("n50"):
            continue
        if u == "fo" and not e.get("fo"):
            continue
        ch = e.get("change")
        if ch is None:
            continue
        out.append({"key": key, "symbol": e.get("symbol"), "name": e.get("name"), "price": e.get("price"), "change": round(float(ch), 2), "fo": bool(e.get("fo")), "n50": bool(e.get("n50"))})
    adv = sum(1 for r in out if r["change"] > 0)
    dec = sum(1 for r in out if r["change"] < 0)
    unch = len(out) - adv - dec
    avg = round(sum(r["change"] for r in out) / len(out), 2) if out else None
    if mode == "gainers":
        out = [r for r in out if r["change"] > 0]
        out.sort(key=lambda r: -r["change"])
    elif mode == "losers":
        out = [r for r in out if r["change"] < 0]
        out.sort(key=lambda r: r["change"])
    else:
        out.sort(key=lambda r: -r["change"])
    if u == "all" and len(out) > limit:
        # keep the biggest movers on both ends so the map stays readable
        half = limit // 2
        out = out[:half] + out[-half:]
    top = max(out, key=lambda r: r["change"]) if out else None
    bottom = min(out, key=lambda r: r["change"]) if out else None
    return {"u": u, "mode": mode, "count": len(out), "adv": adv, "dec": dec, "unch": unch, "avg": avg,
            "top": top, "bottom": bottom, "rows": out}
