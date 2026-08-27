"""Turn a raw option chain into the rows the front end renders.

A chain is a flat mapping of (strike, "CE"|"PE") -> last traded price. Whatever
produces it -- the simulator or a live broker feed -- the maths below is the
same, which is what keeps the two interchangeable.
"""
from __future__ import annotations


def atm_strike(spot: float, step: int) -> int:
    """Nearest tradable strike to spot."""
    return int(round(spot / step) * step)


def strike_ladder(spot: float, step: int, rows: int) -> list[int]:
    """`rows` strikes centred on the money."""
    atm = atm_strike(spot, step)
    half = rows // 2
    return [atm + (i - half) * step for i in range(rows)]


def _fly(chain: dict, strike: int, wing: int, right: str) -> float | None:
    """1:2:1 butterfly cost: long the wings, short two of the body.

    Returns None when any leg is missing from the chain, so a partially
    populated chain degrades to blank cells rather than to wrong numbers.
    """
    lo = chain.get((strike - wing, right))
    mid = chain.get((strike, right))
    hi = chain.get((strike + wing, right))
    if lo is None or mid is None or hi is None:
        return None
    return lo - 2.0 * mid + hi


def butterfly_rows(chain: dict, spot: float, step: int, rows: int, wing: int) -> list[list]:
    """Build the hero sheet: [strike, CE, PE, BFLY, NET] per strike.

    BFLY is the call butterfly's net debit. NET is that minus the equivalent
    put butterfly -- the CE/PE dislocation. In a frictionless market the two
    are equal and NET is zero, so a NET far from zero is the edge the scanner
    is looking for.
    """
    out: list[list] = []
    for strike in strike_ladder(spot, step, rows):
        call = chain.get((strike, "CE"))
        put = chain.get((strike, "PE"))
        if call is None or put is None:
            continue
        call_fly = _fly(chain, strike, wing, "CE")
        put_fly = _fly(chain, strike, wing, "PE")
        if call_fly is None:
            continue
        net = 0.0 if put_fly is None else call_fly - put_fly
        out.append([
            strike,
            round(call, 1),
            round(put, 1),
            round(call_fly, 1),
            round(net, 1),
        ])
    return out


def mini_rows(chain: dict, spot: float, step: int, count: int = 4) -> list[list]:
    """The small BUY/SELL panel: [strike, buy, sell] for strikes above the money.

    Sell is carried negative because the front end renders it as an outflow and
    sums the pair into the delta column.
    """
    atm = atm_strike(spot, step)
    out: list[list] = []
    for i in range(count):
        strike = atm + i * step
        put = chain.get((strike, "PE"))
        call = chain.get((strike, "CE"))
        if put is None or call is None:
            continue
        out.append([strike, round(put, 1), round(-call, 1)])
    return out


def straddle_price(chain: dict, spot: float, step: int) -> float | None:
    """ATM straddle: the call plus the put at the money."""
    atm = atm_strike(spot, step)
    call = chain.get((atm, "CE"))
    put = chain.get((atm, "PE"))
    if call is None or put is None:
        return None
    return round(call + put, 1)
