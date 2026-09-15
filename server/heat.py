"""HEAT: market heatmaps — stocks or coins tiled by the day's move.
Pure functions: `rows` over the Indian feed's universe snapshot, `from_markets` over CoinGecko
markets, `from_cnbc` over CNBC quotes. All share `pack`, whose default mode is the 20 top
gainers plus the 20 top losers."""
from __future__ import annotations

UNIVERSES = ("n50", "fo", "all")
MODES = ("top", "all", "gainers", "losers")
TOP_N = 20

STABLECOINS = {"usdt", "usdc", "dai", "usds", "usde", "fdusd", "tusd", "usd1", "pyusd", "usdd", "frax", "busd", "usdp", "gusd", "lusd", "eurc", "eurs",
               "wbtc", "wsteth", "weth", "steth", "cbbtc", "weeth", "reth", "wbeth", "rseth", "ezeth", "cbeth", "wbnb", "leo", "usdtb", "usd0", "rlusd", "susds", "susde", "tbtc"}


def pack(items: list[dict], mode: str = "top", limit: int = 400, n: int = TOP_N) -> dict:
    """items: [{key, symbol, name, price, change, ...}] with a numeric change. Returns the map payload."""
    mode = mode if mode in MODES else "top"
    out = [dict(r, change=round(float(r["change"]), 2)) for r in items if r.get("change") is not None and r.get("price") is not None]
    adv = sum(1 for r in out if r["change"] > 0)
    dec = sum(1 for r in out if r["change"] < 0)
    unch = len(out) - adv - dec
    avg = round(sum(r["change"] for r in out) / len(out), 2) if out else None
    top = max(out, key=lambda r: r["change"]) if out else None
    bottom = min(out, key=lambda r: r["change"]) if out else None
    out.sort(key=lambda r: -r["change"])
    if mode == "top":
        ups = [r for r in out if r["change"] > 0][:n]
        downs = [r for r in out if r["change"] < 0][-n:]
        out = ups + downs
    elif mode == "gainers":
        out = [r for r in out if r["change"] > 0]
    elif mode == "losers":
        out = [r for r in out if r["change"] < 0]
        out.reverse()
    if len(out) > limit:                                    # keep the biggest movers on both ends
        half = limit // 2
        out = out[:half] + out[-half:]
    return {"mode": mode, "n": n, "count": len(out), "universe": adv + dec + unch, "adv": adv, "dec": dec, "unch": unch, "avg": avg,
            "top": top, "bottom": bottom, "rows": out}


def rows(universe: dict, u: str = "fo", mode: str = "top", limit: int = 400) -> dict:
    """Indian heatmap from the feed universe ({label: {symbol, exchange, name, fo, n50, price, change}})."""
    u = u if u in UNIVERSES else "fo"
    items = []
    for key, e in (universe or {}).items():
        if e.get("exchange") != "NSE":
            continue
        if u == "n50" and not e.get("n50"):
            continue
        if u == "fo" and not e.get("fo"):
            continue
        items.append({"key": key, "symbol": e.get("symbol"), "name": e.get("name"), "price": e.get("price"), "change": e.get("change"),
                      "fo": bool(e.get("fo")), "n50": bool(e.get("n50"))})
    out = pack(items, mode, limit)
    out["u"] = u
    return out


def from_markets(markets: list[dict], mode: str = "top", limit: int = 400) -> dict:
    """Crypto heatmap from CoinGecko /coins/markets rows (stablecoins and wrapped assets dropped)."""
    items = []
    for m in markets or []:
        sym = str(m.get("symbol") or "").lower()
        if not sym or sym in STABLECOINS:
            continue
        items.append({"key": m.get("id"), "symbol": sym.upper(), "name": m.get("name"), "price": m.get("current_price"),
                      "change": m.get("price_change_percentage_24h"), "mcap": m.get("market_cap"), "rank": m.get("market_cap_rank")})
    out = pack(items, mode, limit)
    out["u"] = "crypto"
    return out


def from_cnbc(quotes: list[dict], universe: list[tuple[str, str]], mode: str = "top", limit: int = 400) -> dict:
    """World-stock heatmap from CNBC FormattedQuote rows for the given (code, name) universe."""
    by = {q.get("symbol"): q for q in quotes or []}
    items = []
    for code, name in universe:
        q = by.get(code)
        if not q:
            continue
        items.append({"key": code, "symbol": code.split(".")[0].split("-")[0], "name": q.get("name") or name, "price": _num(q.get("last")),
                      "change": _num(q.get("change_pct")), "status": q.get("curmktstatus")})
    out = pack(items, mode, limit)
    out["u"] = "world"
    statuses = {r.get("status") for r in items}
    out["session"] = "REG_MKT" if "REG_MKT" in statuses else "PRE_MKT" if "PRE_MKT" in statuses else "POST_MKT" if "POST_MKT" in statuses else "CLOSED"
    return out


def _num(s):
    try:
        return float(str(s).replace(",", "").replace("%", "").replace("+", ""))
    except (TypeError, ValueError):
        return None
