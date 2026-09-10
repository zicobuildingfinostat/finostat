"""The book: every open position marked live, with net Greeks, P&L attribution
and what-if scenarios. Positions come from two places -- paper positions the
member saved from the builder (a journal that costs nothing), and, when a
broker is connected, the real option positions at the broker mapped back onto
our chains. Both are priced the same way, off the same live chain rows.
"""
from __future__ import annotations

import json
import logging
import pathlib
import sqlite3
import threading
import time

import bs
import contracts as contractsmod

log = logging.getLogger("finostat.book")

SPOT_SHIFTS = [-3, -2, -1, 0, 1, 2, 3]      # percent
IV_SHIFTS = [-3, 0, 3]                       # IV points
DAYS_AHEAD = [0, 1]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions(
  id       INTEGER PRIMARY KEY,
  user_id  INTEGER NOT NULL,
  u        TEXT NOT NULL,
  expiry   INTEGER NOT NULL,
  legs     TEXT NOT NULL,          -- [{right, strike, qty}]
  lots     INTEGER NOT NULL,
  entries  TEXT NOT NULL,          -- entry price per leg
  lot      INTEGER NOT NULL,
  note     TEXT,
  opened   REAL NOT NULL,
  closed   REAL,
  exits    TEXT
);
CREATE INDEX IF NOT EXISTS positions_user ON positions(user_id, closed);
"""


class Store:
    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self._lock = threading.Lock()
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def open(self, user_id: int, u: str, expiry: int, legs: list, lots: int, entries: list, lot: int, note: str = "") -> int:
        with self._lock, self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM positions WHERE user_id=? AND closed IS NULL", (user_id,)).fetchone()[0]
            if n >= 40:
                raise ValueError("40 open paper positions is the limit — close some first")
            cur = c.execute("INSERT INTO positions(user_id,u,expiry,legs,lots,entries,lot,note,opened) VALUES(?,?,?,?,?,?,?,?,?)",
                            (user_id, u, int(expiry), json.dumps(legs, separators=(",", ":")), int(lots), json.dumps(entries), int(lot), (note or "")[:200], time.time()))
        return cur.lastrowid

    def close(self, user_id: int, pid: int, exits: list) -> bool:
        with self._lock, self._conn() as c:
            return c.execute("UPDATE positions SET closed=?, exits=? WHERE id=? AND user_id=? AND closed IS NULL",
                             (time.time(), json.dumps(exits), pid, user_id)).rowcount == 1

    def delete(self, user_id: int, pid: int) -> bool:
        with self._lock, self._conn() as c:
            return c.execute("DELETE FROM positions WHERE id=? AND user_id=?", (pid, user_id)).rowcount == 1

    def _rows(self, rows) -> list[dict]:
        out = []
        for r in rows:
            d = dict(r)
            d["legs"], d["entries"] = json.loads(d["legs"]), json.loads(d["entries"])
            d["exits"] = json.loads(d["exits"]) if d.get("exits") else None
            out.append(d)
        return out

    def open_positions(self, user_id: int) -> list[dict]:
        with self._conn() as c:
            return self._rows(c.execute("SELECT * FROM positions WHERE user_id=? AND closed IS NULL ORDER BY opened", (user_id,)).fetchall())

    def closed_positions(self, user_id: int, limit: int = 30) -> list[dict]:
        with self._conn() as c:
            return self._rows(c.execute("SELECT * FROM positions WHERE user_id=? AND closed IS NOT NULL ORDER BY closed DESC LIMIT ?", (user_id, limit)).fetchall())


# ---------------------------------------------------------------------------
# Marking
# ---------------------------------------------------------------------------
def _side(chain: dict, strike: int, right: str) -> dict | None:
    for r in chain.get("rows") or []:
        if r["strike"] == strike:
            return r.get(right.lower())
    return None


def mark(position: dict, chain: dict) -> dict:
    """Price one position off a live chain. Never raises: unpriceable legs are flagged."""
    lots, lot = int(position["lots"]), int(position.get("lot") or chain.get("lot") or 1)
    spot, t = chain.get("spot"), chain.get("t_years") or 0.0
    legs_out, pnl, day_pnl, g = [], 0.0, 0.0, {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    priced = True
    for i, l in enumerate(position["legs"]):
        entry = float(position["entries"][i]) if i < len(position["entries"]) and position["entries"][i] is not None else None
        mult = int(l["qty"]) * lots * lot
        side = _side(chain, int(l["strike"]), l["right"]) if chain.get("rows") else None
        leg = {"right": l["right"], "strike": int(l["strike"]), "qty": int(l["qty"]), "entry": entry, "mark": None, "iv": None, "pnl": None, "mult": mult}
        if side and side.get("ltp") is not None:
            m = float(side["ltp"])
            leg["mark"], leg["iv"] = m, side.get("iv")
            if entry is not None:
                leg["pnl"] = round((m - entry) * mult, 2)
                pnl += (m - entry) * mult
            if side.get("change") is not None:                     # % vs previous close
                close = m / (1 + side["change"] / 100.0) if side["change"] > -100 else m
                day_pnl += (m - close) * mult
            for k in g:
                if side.get(k) is not None:
                    g[k] += float(side[k]) * mult
        else:
            priced = False
        legs_out.append(leg)
    return {"id": position.get("id"), "source": position.get("source", "paper"), "u": position["u"], "expiry": position["expiry"],
            "lots": lots, "lot": lot, "note": position.get("note") or "", "opened": position.get("opened"),
            "legs": legs_out, "pnl": round(pnl, 2), "day_pnl": round(day_pnl, 2), "priced": priced, "spot": spot, "t_years": t,
            "greeks": {k: round(v, 3) for k, v in g.items()},
            "label": " · ".join(f"{'+' if l['qty'] > 0 else '−'}{abs(l['qty'])} {l['strike']} {l['right']}" for l in position["legs"])}


def scenarios(marked: list[dict]) -> dict:
    """Book P&L versus now for spot × IV shifts, today and tomorrow. Each position
    re-priced with Black-Scholes off its legs' own implied vols."""
    grid = {d: [[0.0 for _ in SPOT_SHIFTS] for _ in IV_SHIFTS] for d in DAYS_AHEAD}
    for p in marked:
        if not p["priced"] or not p["spot"]:
            continue
        for leg in p["legs"]:
            if leg["mark"] is None or not leg["iv"]:
                continue
            iv0 = leg["iv"] / 100.0
            for di, dv in enumerate(IV_SHIFTS):
                for si, ds in enumerate(SPOT_SHIFTS):
                    for d in DAYS_AHEAD:
                        t = max(p["t_years"] - d / 365.0, 0.0)
                        px = bs.price(p["spot"] * (1 + ds / 100.0), leg["strike"], t, max(iv0 + dv / 100.0, 0.01), leg["right"])
                        grid[d][di][si] += (px - leg["mark"]) * leg["mult"]
    return {"spot_shifts": SPOT_SHIFTS, "iv_shifts": IV_SHIFTS, "days": DAYS_AHEAD,
            "grid": {str(d): [[round(v, 0) for v in row] for row in grid[d]] for d in DAYS_AHEAD}}


def totals(marked: list[dict], feed_quotes: list[dict]) -> dict:
    g = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    pnl = day = delta_pnl = 0.0
    prev_spot = {}
    for q in feed_quotes or []:
        if q.get("price") and q.get("change") is not None and q["change"] > -100:
            prev_spot[q["symbol"]] = q["price"] / (1 + q["change"] / 100.0)
    for p in marked:
        pnl += p["pnl"]
        day += p["day_pnl"]
        for k in g:
            g[k] += p["greeks"][k]
        if p["spot"] and p["u"] in prev_spot:
            delta_pnl += p["greeks"]["delta"] * (p["spot"] - prev_spot[p["u"]])
    theta_pnl = g["theta"]
    return {"pnl": round(pnl, 0), "day_pnl": round(day, 0), "greeks": {k: round(v, 2) for k, v in g.items()},
            "attribution": {"delta": round(delta_pnl, 0), "theta": round(theta_pnl, 0), "other": round(day - delta_pnl - theta_pnl, 0)},
            "open": len(marked), "unpriced": sum(1 for p in marked if not p["priced"])}


def broker_positions(rows: list[dict], contracts) -> list[dict]:
    """Upstox option positions -> position dicts on our chains (grouped by underlying+expiry)."""
    groups: dict[tuple, dict] = {}
    for r in rows:
        info = contracts.lookup(r.get("key", "")) if r.get("key") else None
        if not info or not r.get("qty"):
            continue
        name, expiry, strike, right, lot = info
        ukey = next((k for k, v in contractsmod.INDEX_UNDERLYINGS.items() if v[0] == name), f"NSE:{name}")
        qty_lots = int(r["qty"]) // lot if lot else int(r["qty"])
        if qty_lots == 0:
            continue
        gkey = (ukey, expiry)
        g = groups.setdefault(gkey, {"id": f"upstox:{ukey}:{expiry}", "source": "upstox", "u": ukey, "expiry": expiry, "lots": 1, "lot": lot,
                                     "legs": [], "entries": [], "note": "at Upstox", "opened": None})
        g["legs"].append({"right": right, "strike": strike, "qty": qty_lots})
        g["entries"].append(r.get("avg"))
    return list(groups.values())
