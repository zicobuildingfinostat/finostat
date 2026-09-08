"""Search and lookup over the streamed stock universe. Pure functions."""
from __future__ import annotations


def search(universe: dict, quotes: list, q: str, limit: int = 20) -> list[dict]:
    """Rank: exact symbol, symbol prefix, name/symbol substring; F&O and indices first."""
    q = (q or "").strip().upper()
    limit = max(1, min(50, limit))
    if not q:
        return []
    hits = []
    for quote in quotes or []:
        sym = quote.get("symbol", "")
        if q in sym.upper():
            hits.append((0, sym, {"key": sym, "symbol": sym, "name": sym, "exchange": "INDEX",
                                  "fo": True, "price": quote.get("price"), "change": quote.get("change")}))
    for key, e in (universe or {}).items():
        sym, name = e.get("symbol", "").upper(), e.get("name", "").upper()
        if sym == q:
            rank = 1
        elif sym.startswith(q):
            rank = 2
        elif q in sym or q in name:
            rank = 3
        else:
            continue
        if e.get("n50"):
            rank -= 0.1       # index constituents are what most searches want
        if not e.get("fo"):
            rank += 0.5
        if e.get("exchange") == "BSE":
            rank += 0.25      # the NSE listing is the liquid one; show it first
        hits.append((rank, sym, dict(e, key=key)))
    hits.sort(key=lambda h: (h[0], len(h[1]), h[1]))
    return [h[2] for h in hits[:limit]]


def group(universe: dict, flag: str = "n50") -> list[dict]:
    """Every entry carrying `flag`, symbol order."""
    out = [dict(e, key=k) for k, e in (universe or {}).items() if e.get(flag)]
    out.sort(key=lambda e: e.get("symbol", ""))
    return out


def lookup(universe: dict, quotes: list, keys) -> dict:
    """Quotes for explicit keys ('NSE:RELIANCE' or an index label)."""
    out = {}
    idx = {q.get("symbol"): q for q in quotes or []}
    for k in list(keys)[:50]:
        if k in idx:
            q = idx[k]
            out[k] = {"key": k, "symbol": k, "exchange": "INDEX", "price": q.get("price"), "change": q.get("change")}
        elif k in (universe or {}):
            out[k] = dict(universe[k], key=k)
    return out
