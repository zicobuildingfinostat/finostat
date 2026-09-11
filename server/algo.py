"""ALGO: rule-based strategies that the terminal runs for you.

A strategy is a template (what to sell or buy and where), an entry clock, and exits
(time, stop-loss and target as a % of the credit taken, optional trailing stop, optional
spot-move stop, optional VIX filter). The engine ticks every few seconds through the
session: it enters off the live chain, marks the position off the live chain, and exits
when a rule fires. Paper mode books the trade in the positions BOOK; live mode also
routes LIMIT orders through the connected broker (Upstox rules: no market orders) and
still mirrors the position in the BOOK so P&L and exits are managed the same way.

Nothing here re-enters after an exit on the same day; an algo set to "expiry days" or
"every day" re-arms for the next qualifying session, "once" retires after one run.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import book as bookmod
import history

log = logging.getLogger("finostat.algo")
IST = timezone(timedelta(hours=5, minutes=30))

TEMPLATES = {
    "expiry_straddle": {"label": "Expiry-day short straddle", "legs": "short_straddle", "days": "expiry",
                        "desc": "Sell the ATM CE and PE at the entry time on expiry day; run to the exit time unless the stop or target hits."},
    "expiry_strangle": {"label": "Expiry-day short strangle", "legs": "short_strangle", "days": "expiry",
                        "desc": "Sell CE and PE `wings` strikes away from ATM on expiry day."},
    "wall_strangle": {"label": "Strangle at the OI walls", "legs": "wall_strangle", "days": "expiry",
                      "desc": "Sell the CE at the call wall and the PE at the put wall (largest OI on the live chain) — the strikes the market is defending."},
    "iron_fly": {"label": "Iron fly (defined risk)", "legs": "iron_fly", "days": "expiry",
                 "desc": "Short straddle with long wings `wings` strikes out: capped loss, margin-light."},
    "iron_condor": {"label": "Iron condor (defined risk)", "legs": "iron_condor", "days": "daily",
                    "desc": "Short strangle at ±wings with long wings at ±2·wings."},
    "daily_straddle": {"label": "Daily short straddle", "legs": "short_straddle", "days": "daily",
                       "desc": "The nearest-expiry ATM straddle every trading day at the entry time; intraday only."},
}
DEFAULTS = {"u": "NIFTY 50", "entry": "09:30", "exit": "15:15", "wings": 2, "lots": 1, "sl_pct": 30.0, "target_pct": 50.0,
            "trail": False, "max_vix": None, "max_move_pct": None, "days": "expiry", "mode": "paper"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS algos(
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id  INTEGER NOT NULL,
  name     TEXT NOT NULL,
  template TEXT NOT NULL,
  params   TEXT NOT NULL,
  mode     TEXT NOT NULL DEFAULT 'paper',
  status   TEXT NOT NULL DEFAULT 'armed',
  state    TEXT NOT NULL DEFAULT '{}',
  log      TEXT NOT NULL DEFAULT '[]',
  created  REAL NOT NULL,
  updated  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS algos_user ON algos(user_id);
"""


def validate(params: dict) -> dict:
    """Clean user input into a full parameter set; raises ValueError with a readable reason."""
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (params or {}).items() if k in DEFAULTS})
    if p["u"] not in ("NIFTY 50", "BANKNIFTY", "FINNIFTY", "SENSEX"):
        raise ValueError("underlying must be NIFTY 50, BANKNIFTY, FINNIFTY or SENSEX")
    for k in ("entry", "exit"):
        v = str(p[k]).strip()
        if len(v) != 5 or v[2] != ":" or not v[:2].isdigit() or not v[3:].isdigit() or not ("09:15" <= v <= "15:29"):
            raise ValueError(f"{k} time must be HH:MM between 09:15 and 15:29")
        p[k] = v
    if p["entry"] >= p["exit"]:
        raise ValueError("entry must be before exit")
    try:
        p["wings"] = max(1, min(10, int(p["wings"])))
        p["lots"] = max(1, min(50, int(p["lots"])))
        p["sl_pct"] = max(5.0, min(500.0, float(p["sl_pct"])))
        p["target_pct"] = max(0.0, min(100.0, float(p["target_pct"] or 0)))
        p["max_vix"] = float(p["max_vix"]) if p["max_vix"] not in (None, "", 0, "0") else None
        p["max_move_pct"] = float(p["max_move_pct"]) if p["max_move_pct"] not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        raise ValueError("wings, lots, stop-loss, target, VIX and move limits must be numbers")
    p["trail"] = bool(p["trail"])
    if p["days"] not in ("expiry", "daily", "once"):
        raise ValueError("days must be expiry, daily or once")
    if p["mode"] not in ("paper", "live"):
        raise ValueError("mode must be paper or live")
    return p


def build_legs(template: str, chain: dict, wings: int) -> list[dict]:
    """[{right, strike, qty}] for a template off a live chain (qty −1 short, +1 long, per lot)."""
    t = TEMPLATES[template]
    step, atm = int(chain.get("step") or 50), int(chain.get("atm") or 0)
    if not atm:
        raise ValueError("chain has no ATM yet")
    if t["legs"] == "wall_strangle":
        oi = chain.get("oi") or {}
        cw, pw = oi.get("call_wall"), oi.get("put_wall")
        if cw and pw and cw > pw:
            return [{"right": "CE", "strike": int(cw), "qty": -1}, {"right": "PE", "strike": int(pw), "qty": -1}]
        legs = history.legs_for("short_strangle", atm, step, wings)         # no walls yet: fall back to ±wings
    else:
        legs = history.legs_for(t["legs"], atm, step, wings)
    return [{"right": r, "strike": k, "qty": side} for r, k, side in legs]


class Store:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _row(r) -> dict:
        d = dict(r)
        d["params"], d["state"], d["log"] = json.loads(d["params"]), json.loads(d["state"]), json.loads(d["log"])
        return d

    def create(self, user_id: int, name: str, template: str, params: dict) -> int:
        if template not in TEMPLATES:
            raise ValueError("unknown template")
        p = validate(params)
        with self._lock, self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM algos WHERE user_id=?", (user_id,)).fetchone()[0]
            if n >= 20:
                raise ValueError("20 algos is the limit — delete some first")
            now = time.time()
            cur = c.execute("INSERT INTO algos(user_id,name,template,params,mode,status,state,log,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (user_id, (name or TEMPLATES[template]["label"])[:60], template, json.dumps(p), p["mode"], "armed", "{}",
                             json.dumps([{"t": now, "m": "created · armed"}]), now, now))
            return cur.lastrowid

    def list(self, user_id: int) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("SELECT * FROM algos WHERE user_id=? ORDER BY created DESC", (user_id,)).fetchall()]

    def get(self, aid: int, user_id: int | None = None) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM algos WHERE id=?" + (" AND user_id=?" if user_id is not None else ""), (aid,) if user_id is None else (aid, user_id)).fetchone()
        return self._row(r) if r else None

    def active(self) -> list[dict]:
        with self._conn() as c:
            return [self._row(r) for r in c.execute("SELECT * FROM algos WHERE status IN ('armed','running') ORDER BY id").fetchall()]

    def save(self, a: dict, msg: str | None = None) -> None:
        if msg:
            a["log"] = (a["log"] + [{"t": time.time(), "m": msg[:200]}])[-80:]
        with self._lock, self._conn() as c:
            c.execute("UPDATE algos SET status=?, state=?, log=?, params=?, mode=?, updated=? WHERE id=?",
                      (a["status"], json.dumps(a["state"]), json.dumps(a["log"]), json.dumps(a["params"]), a["params"].get("mode", a["mode"]), time.time(), a["id"]))

    def delete(self, aid: int, user_id: int) -> bool:
        with self._lock, self._conn() as c:
            return c.execute("DELETE FROM algos WHERE id=? AND user_id=?", (aid, user_id)).rowcount == 1


class Engine:
    TICK = 5.0

    def __init__(self, store: Store, chains, book_store, feed, contracts_of, live_router=None, clock=None):
        """live_router(algo, legs_with_prices, lots, closing: bool) -> list of order results (or raises)."""
        self.store, self.chains, self.book, self.feed, self.contracts_of = store, chains, book_store, feed, contracts_of
        self.live_router, self.clock = live_router, clock or (lambda: datetime.now(IST))
        self._stop = threading.Event()
        self.last_tick = 0.0

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        threading.Thread(target=self._run, name="algo", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            now = self.clock()
            in_session = now.weekday() < 5 and "09:14" <= now.strftime("%H:%M") <= "15:32"
            if in_session:
                try:
                    self.tick(now)
                except Exception:                                   # noqa: BLE001
                    log.exception("algo tick failed")
            if self._stop.wait(self.TICK if in_session else 30.0):
                return

    # -- one pass ---------------------------------------------------------------
    def tick(self, now: datetime | None = None) -> int:
        now = now or self.clock()
        self.last_tick = time.time()
        n = 0
        for a in self.store.active():
            try:
                if self._step(a, now):
                    n += 1
            except Exception as exc:                                # noqa: BLE001 - one bad algo must not stop the rest
                log.exception("algo %s failed", a["id"])
                a["status"] = "error"
                self.store.save(a, f"error: {str(exc)[:120]}")
        return n

    def _expiry_today(self, u: str, today: str) -> bool:
        ci = self.contracts_of()
        from contracts import INDEX_UNDERLYINGS
        name = INDEX_UNDERLYINGS.get(u, (None,))[0]
        if not ci or not name:
            return False
        exps = ci.expiries(name)
        return bool(exps) and datetime.fromtimestamp(exps[0] / 1000, IST).strftime("%Y-%m-%d") == today

    def _day_ok(self, a: dict, today: str) -> bool:
        d = a["params"]["days"]
        if d == "expiry":
            return self._expiry_today(a["params"]["u"], today)
        return True

    def _step(self, a: dict, now: datetime) -> bool:
        p, st = a["params"], a["state"]
        today, hhmm = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
        if st.get("day") != today:
            st.update({"day": today, "entered": False, "waited": False})
            if a["status"] == "running" and st.get("position_id"):
                # a position left open overnight (server restart at the close): keep managing it today
                pass
            self.store.save(a)
        if a["status"] == "armed":
            if st.get("entered") or not self._day_ok(a, today) or hhmm < p["entry"] or hhmm >= p["exit"]:
                return False
            return self._enter(a, now)
        if a["status"] == "running":
            return self._manage(a, now)
        return False

    def _enter(self, a: dict, now: datetime) -> bool:
        p, st = a["params"], a["state"]
        if p.get("max_vix"):
            vix = self.feed.spot_of("INDIA VIX") if hasattr(self.feed, "spot_of") else None
            if vix and vix > p["max_vix"]:
                if not st.get("waited"):
                    st["waited"] = True
                    self.store.save(a, f"skipped: VIX {vix:.2f} above {p['max_vix']}")
                return False
        chain = self.chains.chain(p["u"])
        if "rows" not in chain:
            return False
        legs = build_legs(a["template"], chain, p["wings"])
        entries = []
        for l in legs:
            side = bookmod._side(chain, l["strike"], l["right"])
            if not side or side.get("ltp") is None:
                if not st.get("waited"):
                    st["waited"] = True
                    self.store.save(a, f"waiting for prices on {l['strike']} {l['right']}")
                return False
            entries.append(float(side["ltp"]))
        credit = -sum(l["qty"] * px for l, px in zip(legs, entries))
        unit = p["lots"] * int(chain.get("lot") or 1)
        pid = self.book.open(a["user_id"], p["u"], chain["expiry"], legs, p["lots"], entries, chain.get("lot") or 1, note=f"ALGO {a['name']}")
        st.update({"entered": True, "position_id": pid, "credit": round(credit, 2), "unit": unit, "entry_spot": chain.get("spot"),
                   "entered_at": time.time(), "max_pnl": 0.0, "last_pnl": 0.0, "orders": None})
        a["status"] = "running"
        label = " · ".join(f"{'+' if l['qty'] > 0 else '−'}{abs(l['qty'])} {l['strike']} {l['right']} @ {px}" for l, px in zip(legs, entries))
        self.store.save(a, f"entered {label} · credit {credit:.2f}/unit · spot {chain.get('spot')}")
        if p["mode"] == "live" and self.live_router:
            try:
                res = self.live_router(a, [dict(l, price=px) for l, px in zip(legs, entries)], p["lots"], False)
                st["orders"] = res
                self.store.save(a, "live orders: " + "; ".join(f"{r.get('leg')} {'ok' if r.get('ok') else 'REJECTED ' + str(r.get('error'))}" for r in res))
            except Exception as exc:                                # noqa: BLE001
                self.store.save(a, f"live routing failed: {str(exc)[:120]} — position kept as paper")
        return True

    def _manage(self, a: dict, now: datetime) -> bool:
        p, st = a["params"], a["state"]
        pid = st.get("position_id")
        pos = next((x for x in self.book.open_positions(a["user_id"]) if x["id"] == pid), None) if pid else None
        if pos is None:                                             # closed by hand in the BOOK
            a["status"] = "done" if p["days"] == "once" else "armed"
            self.store.save(a, "position closed outside the algo — " + ("retired" if a["status"] == "done" else "re-armed"))
            return True
        chain = self.chains.chain(pos["u"], int(pos["expiry"]))
        if "rows" not in chain:
            return False
        m = bookmod.mark(pos, chain)
        if not m["priced"]:
            return False
        pnl = m["pnl"]
        credit_rs = float(st.get("credit") or 0.0) * float(st.get("unit") or 1)
        st["max_pnl"] = max(float(st.get("max_pnl") or 0.0), pnl)
        st["last_pnl"] = pnl
        reason = None
        sl_rs = credit_rs * p["sl_pct"] / 100.0 if credit_rs > 0 else abs(credit_rs) * p["sl_pct"] / 100.0
        if sl_rs and pnl <= -sl_rs:
            reason = "stop-loss"
        elif p["target_pct"] and credit_rs > 0 and pnl >= credit_rs * p["target_pct"] / 100.0:
            reason = "target"
        elif p["trail"] and sl_rs and st["max_pnl"] > 0 and pnl <= st["max_pnl"] - sl_rs:
            reason = "trailing stop"
        elif p.get("max_move_pct") and st.get("entry_spot") and chain.get("spot") and abs(chain["spot"] - st["entry_spot"]) / st["entry_spot"] * 100 >= p["max_move_pct"]:
            reason = "spot moved"
        elif now.strftime("%H:%M") >= p["exit"]:
            reason = "exit time"
        if not reason:
            self.store.save(a)                                     # persist the running P&L for the panel
            return False
        exits = [l["mark"] for l in m["legs"]]
        self.book.close(a["user_id"], pid, exits)
        st.setdefault("realized", []).append({"day": st.get("day"), "pnl": round(pnl, 2), "reason": reason})
        st["realized"] = st["realized"][-60:]
        st["position_id"] = None
        a["status"] = "done" if p["days"] == "once" else "armed"
        self.store.save(a, f"exited on {reason} · P&L ₹{pnl:,.0f}" + (" · retired" if a["status"] == "done" else " · re-armed for the next session"))
        if p["mode"] == "live" and self.live_router:
            try:
                res = self.live_router(a, [{"right": l["right"], "strike": l["strike"], "qty": -l["qty"], "price": l["mark"]} for l in m["legs"]], p["lots"], True)
                self.store.save(a, "live exit orders: " + "; ".join(f"{r.get('leg')} {'ok' if r.get('ok') else 'REJECTED ' + str(r.get('error'))}" for r in res))
            except Exception as exc:                                # noqa: BLE001
                self.store.save(a, f"live exit routing failed: {str(exc)[:120]} — square off at the broker")
        return True

    # -- manual controls ---------------------------------------------------------
    def square_off(self, a: dict) -> dict:
        """Close the running position now (user pressed the button)."""
        p, st = a["params"], a["state"]
        pid = st.get("position_id")
        pos = next((x for x in self.book.open_positions(a["user_id"]) if x["id"] == pid), None) if pid else None
        if pos is None:
            return {"ok": False, "error": "nothing open"}
        chain = self.chains.chain(pos["u"], int(pos["expiry"]))
        m = bookmod.mark(pos, chain if "rows" in chain else {})
        exits = [l["mark"] for l in m["legs"]]
        self.book.close(a["user_id"], pid, exits)
        st.setdefault("realized", []).append({"day": st.get("day"), "pnl": round(m["pnl"], 2) if m["priced"] else None, "reason": "manual"})
        st["position_id"] = None
        a["status"] = "done" if p["days"] == "once" else "armed"
        self.store.save(a, f"squared off by hand · P&L ₹{m['pnl']:,.0f}" if m["priced"] else "squared off by hand")
        if p["mode"] == "live" and self.live_router:
            try:
                self.live_router(a, [{"right": l["right"], "strike": l["strike"], "qty": -l["qty"], "price": l["mark"]} for l in m["legs"]], p["lots"], True)
            except Exception as exc:                                # noqa: BLE001
                self.store.save(a, f"live exit routing failed: {str(exc)[:120]}")
        return {"ok": True, "pnl": m["pnl"] if m["priced"] else None}

    def view(self, a: dict) -> dict:
        """Panel payload: params, state and live P&L when running."""
        out = {k: a[k] for k in ("id", "name", "template", "params", "mode", "status", "state", "created", "updated")}
        out["label"] = TEMPLATES.get(a["template"], {}).get("label", a["template"])
        out["log"] = a["log"][-12:]
        out["live_pnl"] = a["state"].get("last_pnl") if a["status"] == "running" else None
        r = a["state"].get("realized") or []
        out["realized_total"] = round(sum(x["pnl"] or 0 for x in r), 2) if r else 0.0
        out["runs"] = len(r)
        return out
