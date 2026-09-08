"""Option contract index: which contracts exist for any underlying.

Built once from the instrument masters (then the masters are freed), compact
enough to keep resident: one tuple per option contract for every NSE and BSE
underlying, ~40k rows. Answers "give me the near-expiry strikes around spot for
RELIANCE / NIFTY / SENSEX" without touching the network.
"""
from __future__ import annotations

import time

# Underlying label (as the UI/quotes know it) -> (option name in the master, exchange, spot key)
INDEX_UNDERLYINGS = {
    "NIFTY 50":  ("NIFTY", "NSE", "NIFTY 50"),
    "BANKNIFTY": ("BANKNIFTY", "NSE", "BANKNIFTY"),
    "FINNIFTY":  ("FINNIFTY", "NSE", "FINNIFTY"),
    "SENSEX":    ("SENSEX", "BSE", "SENSEX"),
}


class ContractIndex:
    def __init__(self) -> None:
        # name -> {expiry_ms: {(strike, right): (instrument_key, lot_size)}}
        self._by_name: dict[str, dict[int, dict[tuple, tuple]]] = {}
        self.built_at: float | None = None

    def build(self, rows_by_exchange: dict[str, list[dict]]) -> int:
        idx: dict[str, dict[int, dict]] = {}
        n = 0
        for exch, rows in rows_by_exchange.items():
            seg = "NSE_FO" if exch == "NSE" else "BSE_FO"
            for r in rows:
                if r.get("segment") != seg or r.get("instrument_type") not in ("CE", "PE"):
                    continue
                # Stock options carry the company name in `name` and the ticker in
                # `underlying_symbol`; index options have the same value in both.
                name = r.get("underlying_symbol") or r.get("asset_symbol") or r.get("name")
                exp, strike, key = r.get("expiry"), r.get("strike_price"), r.get("instrument_key")
                if not (name and exp and strike and key):
                    continue
                try:
                    strike_i = int(round(float(strike)))
                except (TypeError, ValueError):
                    continue
                idx.setdefault(name, {}).setdefault(int(exp), {})[(strike_i, r["instrument_type"])] = (key, int(r.get("lot_size") or 0))
                n += 1
        self._by_name = idx
        self.built_at = time.time()
        return n

    # -- queries ------------------------------------------------------------
    def has(self, name: str) -> bool:
        return name in self._by_name

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def expiries(self, name: str, now_ms: float | None = None) -> list[int]:
        now_ms = now_ms if now_ms is not None else time.time() * 1000
        # The master stamps expiry at 23:59:59 IST on the expiry date; the
        # contract actually stops trading at 15:30 IST, 8.5 hours earlier.
        # Getting this wrong served a settled chain (every leg at 0.05) as live.
        close_offset = 8.5 * 3600 * 1000
        return sorted(e for e in self._by_name.get(name, {}) if e - close_offset > now_ms)

    def strikes(self, name: str, expiry_ms: int) -> list[int]:
        return sorted({k[0] for k in self._by_name.get(name, {}).get(expiry_ms, {})})

    def step(self, name: str, expiry_ms: int) -> int | None:
        s = self.strikes(name, expiry_ms)
        diffs = sorted({b - a for a, b in zip(s, s[1:]) if b > a})
        return diffs[0] if diffs else None

    def ladder(self, name: str, expiry_ms: int, spot: float, half: int = 10) -> list[dict]:
        """`2*half+1` strikes centred on spot with both rights' keys and the lot size."""
        chain = self._by_name.get(name, {}).get(expiry_ms, {})
        strikes = self.strikes(name, expiry_ms)
        if not strikes:
            return []
        atm = min(strikes, key=lambda k: abs(k - spot))
        i = strikes.index(atm)
        window = strikes[max(0, i - half): i + half + 1]
        out = []
        for k in window:
            ce, pe = chain.get((k, "CE")), chain.get((k, "PE"))
            if not ce or not pe:
                continue
            out.append({"strike": k, "ce_key": ce[0], "pe_key": pe[0], "lot": ce[1] or pe[1], "atm": k == atm})
        return out
