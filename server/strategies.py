"""Live strategy metrics, derived from the current option chain.

Everything works off the same 9-strike sheet the feed already publishes
([strike, CE, PE, BFLY, NET] rows around the money), so no extra broker
subscriptions are needed. Missing strikes degrade to absent metrics, never to
wrong numbers -- the same rule sheets.py follows.
"""
from __future__ import annotations

CATALOG = [
    {"slug": "short-straddle", "code": "STRD", "name": "Short straddle",
     "tag": "NEUTRAL", "bias": "Neutral", "vol": "Falling IV", "risk": "Undefined",
     "payoff": "M8 70 L100 22 L192 70",
     "blurb": "Sell the ATM call and put together. You collect both premiums and keep "
              "them if the index sits still into expiry.",
     "detail": "The purest short-volatility trade there is. Maximum profit is the whole "
               "credit, earned only at the exact strike; losses grow point-for-point "
               "beyond either breakeven, without limit. Most desks run it with hard "
               "stops or convert it into an iron condor when the credit is rich."},
    {"slug": "iron-condor", "code": "COND", "name": "Iron condor",
     "tag": "RANGE", "bias": "Neutral", "vol": "Falling IV", "risk": "Defined",
     "payoff": "M8 66 L52 66 L84 26 L116 26 L148 66 L192 66",
     "blurb": "A capped straddle. Buy wings outside your short strikes so the worst "
              "case is known before you enter.",
     "detail": "You give up part of the straddle's credit to buy the wings, and in "
               "exchange the margin is small and the max loss is fixed at the wing "
               "width minus the credit. The trade is a bet that the index expires "
               "between the short strikes."},
    {"slug": "butterfly-spread", "code": "BFLY", "name": "Butterfly spread",
     "tag": "1:2:1", "bias": "Pin to strike", "vol": "Falling IV", "risk": "Defined",
     "payoff": "M8 62 L64 62 L100 20 L136 62 L192 62",
     "blurb": "Buy the wings, sell two of the body. Cheap, defined, and pinned to one "
              "strike -- the structure the Finostat sheet was built around.",
     "detail": "The debit is small because the two short middle options finance the "
               "wings. Maximum profit lands exactly at the middle strike at expiry: "
               "wing width minus the debit. The BFLY column on the sheet is this "
               "number, live, for every strike at once."},
    {"slug": "ratio-spread", "code": "RATO", "name": "Ratio spread",
     "tag": "1:2", "bias": "Slow drift", "vol": "Skew rich", "risk": "Undefined",
     "payoff": "M8 52 L70 52 L104 24 L192 72",
     "blurb": "Buy one option, sell two further out. Often a net credit, with a drift "
              "target and a naked tail you must respect.",
     "detail": "Profits if the index drifts slowly toward the short strike, where the "
               "long leg's gain is largest and the shorts expire worthless. Beyond the "
               "shorts one option is naked, so risk grows without limit -- position "
               "size accordingly."},
    {"slug": "calendar-spread", "code": "CALN", "name": "Calendar spread",
     "tag": "TIME", "bias": "Neutral", "vol": "Term steep", "risk": "Defined",
     "payoff": "M8 64 Q100 8 192 64",
     "blurb": "Sell the near expiry, buy the far one at the same strike. A trade on "
              "the term structure rather than on direction.",
     "detail": "The near option decays faster than the far one, so time passing with "
               "the index pinned is the profit engine. Pricing it needs the far "
               "expiry's chain, which this sheet does not carry yet -- the live "
               "numbers below cover the near leg only."},
    {"slug": "cross-butterfly", "code": "XBFY", "name": "Cross butterfly",
     "tag": "CE/PE", "bias": "Arbitrage", "vol": "Skew gap", "risk": "Defined",
     "payoff": "M8 64 L44 64 L72 28 L100 50 L128 28 L156 64 L192 64",
     "blurb": "The same butterfly, priced in calls and in puts. Parity says they must "
              "match; the NET column is the live gap between them.",
     "detail": "A call butterfly and a put butterfly on identical strikes have the "
               "same payoff, so any price difference is a dislocation. Buy the cheap "
               "side, sell the rich side, and the payoff nets out to the difference "
               "collected up front. NET far from zero is the whole trade."},
]

BY_SLUG = {c["slug"]: c for c in CATALOG}


def _chain(rows):
    return {r[0]: (r[1], r[2]) for r in rows}


def infer_step(rows) -> int | None:
    strikes = sorted(r[0] for r in rows)
    diffs = [b - a for a, b in zip(strikes, strikes[1:]) if b > a]
    return min(diffs) if diffs else None


def _ce(c, k):
    v = c.get(k)
    return v[0] if v else None


def _pe(c, k):
    v = c.get(k)
    return v[1] if v else None


def _round(x):
    return None if x is None else round(x, 1)


def compute(slug: str, rows, atm, straddle=None) -> dict | None:
    """Legs and metrics for one strategy from the live sheet. None = unknown slug."""
    meta = BY_SLUG.get(slug)
    if meta is None:
        return None
    out = {k: meta[k] for k in ("slug", "code", "name", "tag", "bias", "vol", "risk",
                                "payoff", "blurb", "detail")}
    out["legs"], out["metrics"], out["note"] = [], [], None
    c = _chain(rows or [])
    s = infer_step(rows or [])
    a = atm
    if not c or s is None or a is None:
        out["note"] = "Waiting for the live chain."
        return out

    def leg(action, count, right, strike):
        price = _ce(c, strike) if right == "CE" else _pe(c, strike)
        return {"action": action, "count": count, "right": right,
                "strike": strike, "price": _round(price)}

    if slug == "short-straddle":
        ce, pe = _ce(c, a), _pe(c, a)
        out["legs"] = [leg("SELL", 1, "CE", a), leg("SELL", 1, "PE", a)]
        if ce is not None and pe is not None:
            cr = ce + pe
            out["metrics"] = [["Net credit", f"₹{cr:.1f}"],
                              ["Max profit", f"₹{cr:.1f} at {a}"],
                              ["Breakevens", f"{a - cr:.0f} / {a + cr:.0f}"],
                              ["Max loss", "Unlimited beyond breakevens"]]

    elif slug == "iron-condor":
        sp, sc, lp, lc = a - 2 * s, a + 2 * s, a - 4 * s, a + 4 * s
        out["legs"] = [leg("SELL", 1, "PE", sp), leg("SELL", 1, "CE", sc),
                       leg("BUY", 1, "PE", lp), leg("BUY", 1, "CE", lc)]
        vals = [_pe(c, sp), _ce(c, sc), _pe(c, lp), _ce(c, lc)]
        if all(v is not None for v in vals):
            cr = vals[0] + vals[1] - vals[2] - vals[3]
            out["metrics"] = [["Net credit", f"₹{cr:.1f}"],
                              ["Max profit", f"₹{cr:.1f} between {sp} and {sc}"],
                              ["Max loss", f"₹{2 * s - cr:.1f}"],
                              ["Breakevens", f"{sp - cr:.0f} / {sc + cr:.0f}"]]

    elif slug == "butterfly-spread":
        w = 2 * s
        out["legs"] = [leg("BUY", 1, "CE", a - w), leg("SELL", 2, "CE", a),
                       leg("BUY", 1, "CE", a + w)]
        vals = [_ce(c, a - w), _ce(c, a), _ce(c, a + w)]
        if all(v is not None for v in vals):
            db = vals[0] - 2 * vals[1] + vals[2]
            out["metrics"] = [["Net debit", f"₹{db:.1f}"],
                              ["Max profit", f"₹{w - db:.1f} pinned at {a}"],
                              ["Max loss", f"₹{db:.1f}"],
                              ["Breakevens", f"{a - w + db:.0f} / {a + w - db:.0f}"]]

    elif slug == "ratio-spread":
        k2 = a + 2 * s
        out["legs"] = [leg("BUY", 1, "CE", a), leg("SELL", 2, "CE", k2)]
        b, sll = _ce(c, a), _ce(c, k2)
        if b is not None and sll is not None:
            net = 2 * sll - b
            word = "credit" if net >= 0 else "debit"
            mp = 2 * s + net
            out["metrics"] = [["Net " + word, f"₹{abs(net):.1f}"],
                              ["Max profit", f"₹{mp:.1f} at {k2}"],
                              ["Upper breakeven", f"{a + 4 * s + net:.0f}"],
                              ["Max loss", "Unlimited above breakeven"]]

    elif slug == "calendar-spread":
        out["legs"] = [leg("SELL", 1, "CE", a),
                       {"action": "BUY", "count": 1, "right": "CE", "strike": a,
                        "price": None, "note": "far expiry"}]
        ce = _ce(c, a)
        if ce is not None:
            out["metrics"] = [["Near leg (sell)", f"₹{ce:.1f}"],
                              ["Far leg (buy)", "needs far-expiry chain"],
                              ["ATM straddle ref", f"₹{straddle:.1f}" if straddle else "—"]]
        out["note"] = ("Live pricing needs the far expiry, which the feed does not "
                       "subscribe yet. Structure shown against the near chain.")

    elif slug == "cross-butterfly":
        w = 2 * s
        out["legs"] = [leg("BUY", 1, "CE", a - w), leg("SELL", 2, "CE", a),
                       leg("BUY", 1, "CE", a + w),
                       leg("SELL", 1, "PE", a - w), leg("BUY", 2, "PE", a),
                       leg("SELL", 1, "PE", a + w)]
        cv = [_ce(c, a - w), _ce(c, a), _ce(c, a + w)]
        pv = [_pe(c, a - w), _pe(c, a), _pe(c, a + w)]
        if all(v is not None for v in cv + pv):
            cf = cv[0] - 2 * cv[1] + cv[2]
            pf = pv[0] - 2 * pv[1] + pv[2]
            out["metrics"] = [["Call fly", f"₹{cf:.1f}"],
                              ["Put fly", f"₹{pf:.1f}"],
                              ["Dislocation (NET)", f"₹{cf - pf:+.1f}"],
                              ["Trade", "Buy the cheap fly, sell the rich one"]]

    if not out["metrics"] and out["note"] is None:
        out["note"] = "Some strikes for this structure sit outside the live sheet."
    return out


def compute_all(rows, atm, straddle=None) -> list[dict]:
    return [compute(c["slug"], rows, atm, straddle) for c in CATALOG]
