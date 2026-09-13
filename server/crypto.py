"""Global & crypto data for the /global terminal, all from keyless public endpoints:
- Deribit: BTC/ETH option chains (mark price, mark IV, open interest), index prices, perpetual
  funding/OI, the DVOL volatility index, and candles. Greeks are computed here from mark IV.
- Kraken + CoinGecko: spot in USD and INR for the crypto tape.
- CNBC: the global index/commodity/rates tape (S&P, Nasdaq, Dow, DAX, Nikkei, HSI, FTSE, DXY,
  gold, crude, US 10Y).
Every call is cached for a short time so the page can poll freely without hammering anyone.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import bs
import chains as chainmod

log = logging.getLogger("finostat.crypto")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
DERIBIT = "https://www.deribit.com/api/v2/public/"
CURRENCIES = ("BTC", "ETH")
GLOBAL = [(".SPX", "S&P 500"), (".IXIC", "NASDAQ"), (".DJI", "DOW"), (".GDAXI", "DAX"), (".N225", "NIKKEI"), (".HSI", "HANG SENG"),
          (".FTSE", "FTSE 100"), (".DXY", "DXY"), ("@GC.1", "GOLD"), ("@CL.1", "CRUDE"), ("US10Y", "US 10Y")]
CNBC_URL = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=" + urllib.parse.quote("|".join(s for s, _ in GLOBAL), safe="")
            + "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
KRAKEN_URL = "https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD"
GECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd,inr&include_24hr_change=true"
WINDOW = 15


def _get(url: str, timeout: float = 20.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _num(s) -> float | None:
    try:
        return float(str(s).replace(",", "").replace("%", "").replace("+", ""))
    except (TypeError, ValueError):
        return None


class _Cache:
    def __init__(self):
        self._d: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl: float, fn):
        with self._lock:
            hit = self._d.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        try:
            val = fn()
        except Exception as exc:                                    # noqa: BLE001 - serve stale on failure
            log.info("crypto fetch %s failed: %s", key, exc)
            if hit:
                return hit[1]
            raise
        with self._lock:
            self._d[key] = (time.time(), val)
        return val


# ---------------------------------------------------------------------------
# Deribit option chains in the terminal's row shape
# ---------------------------------------------------------------------------
def parse_instrument(name: str) -> tuple[str, int, int, str] | None:
    """'BTC-27MAR26-80000-C' -> (currency, expiry_ms, strike, right)."""
    try:
        cur, d, k, r = name.split("-")
        exp = datetime.strptime(d, "%d%b%y").replace(hour=8, tzinfo=timezone.utc)      # Deribit expires 08:00 UTC
        return cur, int(exp.timestamp() * 1000), int(float(k)), "CE" if r == "C" else "PE"
    except (ValueError, AttributeError):
        return None


def build_chain(cur: str, summary: list[dict], index_price: float, expiry_ms: int | None = None, now: float | None = None, window: int = WINDOW) -> dict:
    """Deribit book summaries -> {spot, expiry, expiries, step, atm, lot, t_years, rows, oi}. Option prices in USD (mark × index)."""
    now = now or time.time()
    by_exp: dict[int, dict[int, dict]] = {}
    for s in summary:
        p = parse_instrument(s.get("instrument_name", ""))
        if not p or p[0] != cur:
            continue
        _, exp, k, right = p
        if exp / 1000 <= now:
            continue
        by_exp.setdefault(exp, {}).setdefault(k, {"strike": k})[right.lower()] = s
    exps = sorted(by_exp)
    if not exps:
        return {"error": "no live Deribit expiries"}
    exp = expiry_ms if expiry_ms in by_exp else exps[0]
    t = max(0.0, (exp / 1000 - now) / (365 * 86400))
    strikes = sorted(by_exp[exp])
    atm = min(strikes, key=lambda k: abs(k - index_price))
    i = strikes.index(atm)
    strikes = strikes[max(0, i - window): i + window + 1]
    step = min((b - a for a, b in zip(strikes, strikes[1:]) if b > a), default=0)
    rows = []
    for k in strikes:
        row = {"strike": k, "atm": k == atm}
        for side in ("ce", "pe"):
            s = by_exp[exp][k].get(side)
            if not s or s.get("mark_price") is None:
                row[side] = None
                continue
            iv = s.get("mark_iv")
            iv = float(iv) if iv else None
            right = "CE" if side == "ce" else "PE"
            g = bs.greeks(index_price, k, t, iv / 100.0, right, r=0.0) if (iv and t > 0) else None
            gx = bs.greeks_ext(index_price, k, t, iv / 100.0, right, r=0.0) if (iv and t > 0) else None
            mark_btc = float(s["mark_price"])
            row[side] = {"ltp": round(mark_btc * index_price, 2), "ltp_coin": mark_btc, "iv": round(iv, 2) if iv else None,
                         "oi": int(float(s.get("open_interest") or 0) * 100) / 100, "vol": s.get("volume"), "bid": s.get("bid_price"), "ask": s.get("ask_price"),
                         "delta": round(g["delta"], 3) if g else None, "gamma": round(g["gamma"], 6) if g else None, "theta": round(g["theta"], 2) if g else None, "vega": round(g["vega"], 2) if g else None,
                         **({k2: round(v, 8) for k2, v in gx.items()} if gx else {}), "key": s.get("instrument_name")}
        rows.append(row)
    return {"underlying": cur, "kind": "crypto", "name": cur, "exchange": "DERIBIT", "spot": round(index_price, 2), "expiry": exp, "expiries": exps[:8],
            "step": step, "atm": atm, "lot": 1, "t_years": round(t, 6), "rows": rows, "oi": chainmod.oi_summary(rows, index_price), "oi_source": "deribit",
            "warming": False, "missing": 0, "live": True, "source": "deribit"}


class Crypto:
    def __init__(self):
        self.c = _Cache()

    # -- Deribit -------------------------------------------------------------
    def summary(self, cur: str) -> list[dict]:
        return self.c.get(f"sum:{cur}", 20.0, lambda: _get(DERIBIT + f"get_book_summary_by_currency?currency={cur}&kind=option").get("result") or [])

    def index(self, cur: str) -> float:
        return self.c.get(f"idx:{cur}", 10.0, lambda: float(_get(DERIBIT + f"get_index_price?index_name={cur.lower()}_usd")["result"]["index_price"]))

    def perp(self, cur: str) -> dict:
        def fn():
            r = (_get(DERIBIT + f"get_book_summary_by_instrument?instrument_name={cur}-PERPETUAL").get("result") or [{}])[0]
            return {"mark": r.get("mark_price"), "funding": r.get("current_funding"), "funding_8h": r.get("funding_8h"), "oi_usd": r.get("open_interest"),
                    "volume_usd": r.get("volume_usd"), "high": r.get("high"), "low": r.get("low"), "change": r.get("price_change")}
        return self.c.get(f"perp:{cur}", 30.0, fn)

    def dvol(self, cur: str) -> float | None:
        def fn():
            end = int(time.time() * 1000)
            d = _get(DERIBIT + f"get_volatility_index_data?currency={cur}&start_timestamp={end - 6 * 3600 * 1000}&end_timestamp={end}&resolution=3600")
            data = (d.get("result") or {}).get("data") or []
            return float(data[-1][4]) if data else None
        return self.c.get(f"dvol:{cur}", 300.0, fn)

    def chain(self, cur: str, expiry_ms: int | None = None) -> dict:
        cur = cur.upper()
        if cur not in CURRENCIES:
            return {"error": "BTC or ETH"}
        try:
            return build_chain(cur, self.summary(cur), self.index(cur), expiry_ms)
        except Exception as exc:                                    # noqa: BLE001
            return {"error": f"Deribit unavailable: {str(exc)[:100]}"}

    def candles(self, instrument: str, resolution: str = "5", hours: int = 48) -> list[list]:
        def fn():
            end = int(time.time() * 1000)
            d = _get(DERIBIT + f"get_tradingview_chart_data?instrument_name={urllib.parse.quote(instrument)}&start_timestamp={end - hours * 3600 * 1000}&end_timestamp={end}&resolution={resolution}")
            r = d.get("result") or {}
            return [[datetime.fromtimestamp(t / 1000, timezone.utc).isoformat(), o, h, l, c, v] for t, o, h, l, c, v in zip(r.get("ticks", []), r.get("open", []), r.get("high", []), r.get("low", []), r.get("close", []), r.get("volume", []))]
        return self.c.get(f"cndl:{instrument}:{resolution}", 30.0, fn)

    # -- tapes -------------------------------------------------------------------
    def crypto_tape(self) -> list[dict]:
        def fn():
            kr = (_get(KRAKEN_URL).get("result") or {})
            out = []
            for pair, sym in (("XXBTZUSD", "BTC"), ("XETHZUSD", "ETH"), ("SOLUSD", "SOL")):
                r = kr.get(pair) or {}
                last = _num((r.get("c") or [None])[0])
                op = _num(r.get("o"))
                out.append({"symbol": sym, "price": last, "change": round((last - op) / op * 100, 2) if last and op else None, "ccy": "USD"})
            try:
                g = _get(GECKO_URL)
                inr = {"BTC": g.get("bitcoin", {}).get("inr"), "ETH": g.get("ethereum", {}).get("inr"), "SOL": g.get("solana", {}).get("inr")}
                for q in out:
                    q["inr"] = inr.get(q["symbol"])
            except Exception:                                       # noqa: BLE001
                pass
            return out
        return self.c.get("tape:crypto", 15.0, fn)

    def global_tape(self) -> list[dict]:
        def fn():
            d = _get(CNBC_URL)
            qs = ((d.get("FormattedQuoteResult") or {}).get("FormattedQuote")) or []
            by = {q.get("symbol"): q for q in qs}
            return [{"symbol": label, "code": code, "price": _num((by.get(code) or {}).get("last")), "change": _num((by.get(code) or {}).get("change_pct")),
                     "status": (by.get(code) or {}).get("curmktstatus")} for code, label in GLOBAL]
        return self.c.get("tape:global", 60.0, fn)

    def tape(self) -> dict:
        out = {"crypto": [], "global": [], "vol": {}}
        try:
            out["crypto"] = self.crypto_tape()
        except Exception as exc:                                    # noqa: BLE001
            out["crypto_error"] = str(exc)[:80]
        try:
            out["global"] = self.global_tape()
        except Exception as exc:                                    # noqa: BLE001
            out["global_error"] = str(exc)[:80]
        for cur in CURRENCIES:
            try:
                out["vol"][cur] = {"dvol": self.dvol(cur), **self.perp(cur)}
            except Exception:                                       # noqa: BLE001
                pass
        return out
