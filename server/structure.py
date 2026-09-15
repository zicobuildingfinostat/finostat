"""STRUCT: the XAU Sovereign engine (classic systems + smart-money price action) run on Indian
underlyings — NIFTY 50, BANKNIFTY, FINNIFTY, SENSEX and any F&O stock — on 5m / 15m / 1h / daily
candles from Upstox. Output is the same shape gold.analyze produces, so the shared chart renderer
draws it: market structure (BOS / CHoCH), order blocks, fair value gaps, liquidity sweeps,
premium/discount, displacement, markers, entry/stop/target and the score strip."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

import footprint
import gold
import scalper
import seller

ENGINES = ("struct", "scalp", "seller")
STEP = {"NIFTY 50": 50, "BANKNIFTY": 100, "FINNIFTY": 50, "SENSEX": 100}

log = logging.getLogger("finostat.structure")
INDICES = ("NIFTY 50", "BANKNIFTY", "FINNIFTY", "SENSEX")
TFS = ("5m", "15m", "1h", "D")
MAX_BARS = 1000


def to_ms(candles: list[list]) -> list[list]:
    """CANDLES.series rows [[iso, o, h, l, c, v], ...] -> [[ms, o, h, l, c, v], ...]."""
    out = []
    for c in candles:
        try:
            ts = int(datetime.fromisoformat(str(c[0]).replace("Z", "+00:00")).timestamp() * 1000)
            out.append([ts, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5] or 0)])
        except (ValueError, TypeError, IndexError):
            continue
    return out


def summary(d: dict) -> dict:
    """The one-screen read for the panel header and Vega."""
    pa = d.get("pa") or {}
    ev = (pa.get("events") or [None])[-1]
    n = len(d["series"]["t"]) if "series" in d else 0
    rng = pa.get("range")
    spot = d.get("entry")
    pos = None
    if rng and rng["hi"] > rng["lo"] and spot:
        pos = round(100 * (spot - rng["lo"]) / (rng["hi"] - rng["lo"]), 0)
    demand = [z for z in (pa.get("obs") or []) + (pa.get("fvgs") or []) if z["dir"] == 1 and spot and z["top"] < spot]
    supply = [z for z in (pa.get("obs") or []) + (pa.get("fvgs") or []) if z["dir"] == -1 and spot and z["bot"] > spot]
    pools = [p for p in (pa.get("pools") or []) if p.get("swept") is None]
    return {"structure": pa.get("structure"), "structure_word": {1: "bullish", -1: "bearish"}.get(pa.get("structure"), "none"),
            "last_event": ({"type": ev["type"], "dir": ev["dir"], "level": ev["level"], "bars_ago": n - 1 - ev["i"]} if ev else None),
            "range": ({"lo": rng["lo"], "hi": rng["hi"], "pos_pct": pos, "zone": ("below range" if pos < 0 else "above range" if pos > 100 else "discount" if pos < 50 else "premium") if pos is not None else None} if rng else None),
            "nearest_demand": max(demand, key=lambda z: z["top"])["top"] if demand else None,
            "nearest_supply": min(supply, key=lambda z: z["bot"])["bot"] if supply else None,
            "liquidity_above": min((p["price"] for p in pools if spot and p["price"] > spot), default=None),
            "liquidity_below": max((p["price"] for p in pools if spot and p["price"] < spot), default=None)}


class Structure:
    def __init__(self, candles, resolve_key, ttl: float = 60.0, extras_fn=None):
        self.candles, self.resolve_key, self.extras_fn = candles, resolve_key, extras_fn
        self.ttl = ttl
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def view(self, label: str, tf: str = "15m", bars: int = 220, engine: str = "struct") -> dict:
        tf = tf if tf in TFS else "15m"
        engine = engine if engine in ENGINES else "struct"
        label = (label or "").strip()
        key = self.resolve_key(label)
        if not key:
            return {"error": f"unknown symbol {label!r}"}
        ck = (key, tf, engine)
        with self._lock:
            hit = self._cache.get(ck)
        if hit and time.time() - hit[0] < self.ttl:
            d = hit[1]
        else:
            try:
                rows = self.candles.series(key, tf).get("candles") or []
            except Exception as exc:                                # noqa: BLE001
                return {"error": f"candles unavailable: {str(exc)[:80]}"}
            c = to_ms(rows)[-MAX_BARS:]
            if len(c) < 60:
                return {"error": "not enough candles yet for this timeframe"}
            if engine == "scalp":
                d = scalper.analyze(c, tf)
            elif engine == "seller":
                extras = None
                if self.extras_fn and label in INDICES:
                    try:
                        extras = self.extras_fn(label)
                    except Exception as exc:                        # noqa: BLE001
                        log.info("structure: extras unavailable for %s: %s", label, exc)
                d = seller.analyze(c, tf, extras, step=STEP.get(label))
            else:
                d = gold.analyze(c, "1d" if tf == "D" else tf)
                if "error" not in d:
                    d["engine"] = "struct"
            if "error" in d:
                return d
            d["label"], d["key"], d["tf"] = label, key, tf
            d["summary"] = summary(d) if engine != "scalp" else {"structure": 0, "structure_word": "n/a", "last_event": None, "range": None, "nearest_demand": None, "nearest_supply": None, "liquidity_above": None, "liquidity_below": None}
            with self._lock:
                self._cache[ck] = (time.time(), d)
        out = footprint.attach(gold.slice_view(d, bars))
        out["as_of"] = (hit[0] if hit and time.time() - hit[0] < self.ttl else time.time())
        return out
