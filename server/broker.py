"""Members connect their own broker account for positions, funds and order
placement from the terminal. Upstox first (OAuth 2, daily tokens); the
structure is per-broker so Zerodha Kite can follow the same shape.

Safety rules baked in here:
- Only signed-in, paid members can connect or trade (checked in app.py).
- Tokens are sealed at rest with FINOSTAT_SECRET_KEY (HMAC-keystream + tag);
  the database never holds a usable token in the clear.
- Orders are only sent from /api/broker/order with confirm=true, leg by leg,
  buys before sells, and every attempt is recorded with the broker's answer.
- Nothing here ever chooses an order for the member: it transmits what the
  builder shows, and returns exactly what the broker said.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import pathlib
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import config

log = logging.getLogger("finostat.broker")

IST = timezone(timedelta(hours=5, minutes=30))
UPSTOX_AUTH = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN = "https://api.upstox.com/v2/login/authorization/token"
UPSTOX_API = "https://api.upstox.com/v2"
USER_AGENT = "Finostat/1.0 (+https://finostat.com)"
BROKERS = {"upstox": "Upstox", "zerodha": "Zerodha Kite"}
PRODUCTS = {"D": "NRML (carry)", "I": "Intraday"}
STATE_TTL = 600.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS broker_accounts(
  user_id     INTEGER NOT NULL,
  broker      TEXT NOT NULL,
  broker_uid  TEXT,
  name        TEXT,
  email       TEXT,
  token       TEXT NOT NULL,
  expires     REAL NOT NULL,
  connected   REAL NOT NULL,
  last_used   REAL,
  PRIMARY KEY(user_id, broker)
);
CREATE TABLE IF NOT EXISTS broker_states(
  state    TEXT PRIMARY KEY,
  user_id  INTEGER NOT NULL,
  broker   TEXT NOT NULL,
  ts       REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS broker_orders(
  id       INTEGER PRIMARY KEY,
  user_id  INTEGER NOT NULL,
  broker   TEXT NOT NULL,
  placed   REAL NOT NULL,
  tag      TEXT,
  legs     TEXT NOT NULL,
  results  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS broker_orders_user ON broker_orders(user_id, placed);
"""


class BrokerError(Exception):
    pass


# ---------------------------------------------------------------------------
# Configuration + sealing
# ---------------------------------------------------------------------------
def api_key() -> str:
    return os.environ.get("UPSTOX_API_KEY", "").strip() or config.UPSTOX_API_KEY


def api_secret() -> str:
    return os.environ.get("UPSTOX_API_SECRET", "").strip() or config.UPSTOX_API_SECRET


def configured(broker: str = "upstox") -> bool:
    return broker == "upstox" and bool(api_key() and api_secret())


def public_url() -> str:
    return (os.environ.get("FINOSTAT_PUBLIC_URL", "").strip() or "https://finostat.com").rstrip("/")


def redirect_uri(broker: str = "upstox") -> str:
    return f"{public_url()}/broker/{broker}/callback"


def _seal_key() -> bytes:
    k = os.environ.get("FINOSTAT_SECRET_KEY", "").strip() or config.SECRET_KEY or api_secret()
    if not k:
        raise BrokerError("no sealing key configured")
    return hashlib.sha256(("finostat-seal:" + k).encode()).digest()


def _keystream(key: bytes, nonce: bytes, n: int) -> bytes:
    out, ctr = bytearray(), 0
    while len(out) < n:
        out += hmac.new(key, nonce + ctr.to_bytes(4, "big"), hashlib.sha256).digest()
        ctr += 1
    return bytes(out[:n])


def seal(text: str) -> str:
    """base64(nonce || ciphertext || tag). Tamper-evident; key never leaves the server."""
    key, nonce = _seal_key(), secrets.token_bytes(16)
    data = text.encode("utf-8")
    ct = bytes(a ^ b for a, b in zip(data, _keystream(key, nonce, len(data))))
    tag = hmac.new(key, nonce + ct, hashlib.sha256).digest()[:16]
    return base64.b64encode(nonce + ct + tag).decode()


def unseal(blob: str) -> str | None:
    try:
        raw = base64.b64decode(blob)
        key = _seal_key()
        nonce, ct, tag = raw[:16], raw[16:-16], raw[-16:]
        if not hmac.compare_digest(hmac.new(key, nonce + ct, hashlib.sha256).digest()[:16], tag):
            return None
        return bytes(a ^ b for a, b in zip(ct, _keystream(key, nonce, len(ct)))).decode("utf-8")
    except Exception:
        return None


def token_expiry(now: float | None = None) -> float:
    """Upstox access tokens die at 03:30 IST every day."""
    t = datetime.fromtimestamp(now or time.time(), IST)
    cut = t.replace(hour=3, minute=30, second=0, microsecond=0)
    if t >= cut:
        cut += timedelta(days=1)
    return cut.timestamp()


# ---------------------------------------------------------------------------
# Upstox OAuth + REST
# ---------------------------------------------------------------------------
def authorize_url(state: str) -> str:
    q = urllib.parse.urlencode({"response_type": "code", "client_id": api_key(), "redirect_uri": redirect_uri(), "state": state})
    return f"{UPSTOX_AUTH}?{q}"


def _request(url: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> dict:
    h = {"Accept": "application/json", "User-Agent": USER_AGENT}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:600]
        try:
            j = json.loads(body)
            msg = "; ".join(e.get("message", "") for e in j.get("errors", [])) or j.get("message") or body
        except ValueError:
            msg = body
        if exc.code == 401:
            raise BrokerError("Upstox session expired — reconnect your account") from exc
        raise BrokerError(f"Upstox: {msg or exc.code}") from exc
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise BrokerError(f"Upstox unreachable: {exc}") from exc


def exchange_code(code: str) -> dict:
    body = urllib.parse.urlencode({"code": code, "client_id": api_key(), "client_secret": api_secret(),
                                   "redirect_uri": redirect_uri(), "grant_type": "authorization_code"}).encode()
    out = _request(UPSTOX_TOKEN, "POST", body, {"Content-Type": "application/x-www-form-urlencoded"})
    if not out.get("access_token"):
        raise BrokerError("Upstox returned no access token")
    return {"token": out["access_token"], "uid": out.get("user_id", ""), "name": out.get("user_name", ""), "email": out.get("email", "")}


class Upstox:
    """Thin REST client bound to one member's token."""

    def __init__(self, token: str):
        self.token = token

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path: str, params: dict | None = None) -> dict:
        url = UPSTOX_API + path + (("?" + urllib.parse.urlencode(params)) if params else "")
        return _request(url, headers=self._h())

    def post(self, path: str, body: dict) -> dict:
        return _request(UPSTOX_API + path, "POST", json.dumps(body).encode(), {**self._h(), "Content-Type": "application/json"})

    def delete(self, path: str, params: dict) -> dict:
        return _request(UPSTOX_API + path + "?" + urllib.parse.urlencode(params), "DELETE", headers=self._h())

    def profile(self) -> dict:
        return self.get("/user/profile").get("data") or {}

    def funds(self) -> dict:
        d = self.get("/user/get-funds-and-margin", {"segment": "SEC"}).get("data") or {}
        eq = d.get("equity") or {}
        return {"available": eq.get("available_margin"), "used": eq.get("used_margin")}

    def positions(self) -> list[dict]:
        return summarize_positions(self.get("/portfolio/short-term-positions").get("data") or [])

    def orders(self) -> list[dict]:
        return summarize_orders(self.get("/order/retrieve-all").get("data") or [])

    def place(self, payload: dict) -> dict:
        out = self.post("/order/place", payload)
        if out.get("status") != "success":
            raise BrokerError("Upstox rejected the order: " + json.dumps(out)[:200])
        return out.get("data") or {}

    def cancel(self, order_id: str) -> dict:
        return self.delete("/order/cancel", {"order_id": order_id}).get("data") or {}


def summarize_positions(rows: list) -> list[dict]:
    out = []
    for p in rows:
        qty = int(p.get("quantity") or 0)
        if qty == 0 and not (p.get("realised") or 0):
            continue
        out.append({"symbol": p.get("trading_symbol") or p.get("tradingsymbol") or "", "exchange": p.get("exchange", ""),
                    "product": p.get("product", ""), "qty": qty, "avg": p.get("average_price"), "ltp": p.get("last_price"),
                    "pnl": p.get("pnl"), "unrealised": p.get("unrealised"), "realised": p.get("realised"),
                    "key": p.get("instrument_token", "")})
    return out


def summarize_orders(rows: list) -> list[dict]:
    out = []
    for o in rows:
        out.append({"order_id": o.get("order_id"), "status": o.get("status"), "symbol": o.get("trading_symbol") or o.get("tradingsymbol") or "",
                    "side": o.get("transaction_type"), "qty": o.get("quantity"), "filled": o.get("filled_quantity"),
                    "avg": o.get("average_price"), "type": o.get("order_type"), "product": o.get("product"),
                    "price": o.get("price"), "message": o.get("status_message") or "", "tag": o.get("tag") or "",
                    "time": o.get("order_timestamp") or o.get("exchange_timestamp") or ""})
    out.sort(key=lambda x: x.get("time") or "", reverse=True)
    return out


def order_payload(instrument_key: str, side: str, quantity: int, product: str = "D", order_type: str = "MARKET",
                  price: float = 0.0, tag: str = "finostat") -> dict:
    if side not in ("BUY", "SELL") or quantity <= 0:
        raise BrokerError("bad order")
    if product not in PRODUCTS or order_type not in ("MARKET", "LIMIT"):
        raise BrokerError("bad product or order type")
    return {"quantity": int(quantity), "product": product, "validity": "DAY",
            "price": float(price) if order_type == "LIMIT" else 0.0, "tag": tag[:20], "instrument_token": instrument_key,
            "order_type": order_type, "transaction_type": side, "disclosed_quantity": 0, "trigger_price": 0.0, "is_amo": False}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
class Brokers:
    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self._lock = threading.Lock()
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    # OAuth state: one-time, ten minutes, bound to the signed-in user
    def new_state(self, user_id: int, broker: str = "upstox") -> str:
        st = secrets.token_urlsafe(24)
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM broker_states WHERE ts<?", (time.time() - STATE_TTL,))
            c.execute("INSERT INTO broker_states(state,user_id,broker,ts) VALUES(?,?,?,?)", (st, user_id, broker, time.time()))
        return st

    def pop_state(self, state: str) -> tuple[int, str] | None:
        if not state or len(state) > 64:
            return None
        with self._lock, self._conn() as c:
            r = c.execute("SELECT user_id,broker,ts FROM broker_states WHERE state=?", (state,)).fetchone()
            c.execute("DELETE FROM broker_states WHERE state=?", (state,))
        if r is None or r["ts"] < time.time() - STATE_TTL:
            return None
        return int(r["user_id"]), r["broker"]

    def connect(self, user_id: int, broker: str, info: dict, expires: float) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO broker_accounts(user_id,broker,broker_uid,name,email,token,expires,connected) VALUES(?,?,?,?,?,?,?,?) "
                      "ON CONFLICT(user_id,broker) DO UPDATE SET broker_uid=excluded.broker_uid,name=excluded.name,email=excluded.email,"
                      "token=excluded.token,expires=excluded.expires,connected=excluded.connected",
                      (user_id, broker, info.get("uid"), info.get("name"), info.get("email"), seal(info["token"]), expires, time.time()))

    def get(self, user_id: int, broker: str = "upstox") -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM broker_accounts WHERE user_id=? AND broker=?", (user_id, broker)).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["expired"] = d["expires"] < time.time()
        d["token"] = unseal(d["token"]) if not d["expired"] else None
        return d

    def touch(self, user_id: int, broker: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE broker_accounts SET last_used=? WHERE user_id=? AND broker=?", (time.time(), user_id, broker))

    def disconnect(self, user_id: int, broker: str) -> bool:
        with self._lock, self._conn() as c:
            return c.execute("DELETE FROM broker_accounts WHERE user_id=? AND broker=?", (user_id, broker)).rowcount > 0

    def record_order(self, user_id: int, broker: str, legs: list, results: list, tag: str) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute("INSERT INTO broker_orders(user_id,broker,placed,tag,legs,results) VALUES(?,?,?,?,?,?)",
                            (user_id, broker, time.time(), tag, json.dumps(legs, separators=(",", ":")), json.dumps(results, separators=(",", ":"))))
        return cur.lastrowid

    def recent_orders(self, user_id: int, limit: int = 20) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM broker_orders WHERE user_id=? ORDER BY placed DESC LIMIT ?", (user_id, limit)).fetchall()
        return [{**dict(r), "legs": json.loads(r["legs"]), "results": json.loads(r["results"])} for r in rows]

    def status(self, user_id: int) -> dict:
        out = {"configured": configured(), "brokers": []}
        for bid, name in BROKERS.items():
            acc = self.get(user_id, bid) if bid == "upstox" else None
            out["brokers"].append({"id": bid, "name": name, "available": configured(bid), "connected": bool(acc),
                                   "expired": bool(acc and acc["expired"]), "user": (acc or {}).get("name") or (acc or {}).get("broker_uid"),
                                   "expires": (acc or {}).get("expires"), "connected_at": (acc or {}).get("connected")})
        return out


# ---------------------------------------------------------------------------
# Placing a builder strategy
# ---------------------------------------------------------------------------
def plan_orders(legs: list[dict], resolve_key, lots: int, product: str, order_type: str, tag: str) -> list[dict]:
    """Turn builder legs into Upstox order payloads. Buys first so spreads
    are margined as spreads. resolve_key(right, strike) -> (instrument_key, lot_size)."""
    if not 1 <= int(lots) <= 50:
        raise BrokerError("lots must be 1-50")
    if not legs or len(legs) > 8:
        raise BrokerError("1-8 legs")
    plan = []
    for l in legs:
        right, strike, qty = str(l.get("right", "")).upper(), int(l.get("strike", 0)), int(l.get("qty", 0))
        if right not in ("CE", "PE") or qty == 0:
            raise BrokerError(f"bad leg {l}")
        km = resolve_key(right, strike)
        if not km:
            raise BrokerError(f"{strike} {right} is not listed at the broker")
        key, lot = km
        price = float(l.get("price") or 0) if order_type == "LIMIT" else 0.0
        plan.append({"leg": f"{'BUY' if qty > 0 else 'SELL'} {abs(qty)}x {strike} {right}", "side": "BUY" if qty > 0 else "SELL",
                     "payload": order_payload(key, "BUY" if qty > 0 else "SELL", abs(qty) * int(lots) * int(lot), product, order_type, price, tag)})
    plan.sort(key=lambda p: 0 if p["side"] == "BUY" else 1)
    return plan


def execute(client: Upstox, plan: list[dict]) -> list[dict]:
    """Send leg by leg; stop at the first rejection so a half-built position
    never grows further. Returns one result per attempted leg."""
    results = []
    for p in plan:
        try:
            d = client.place(p["payload"])
            results.append({"leg": p["leg"], "ok": True, "order_id": d.get("order_id")})
        except BrokerError as exc:
            results.append({"leg": p["leg"], "ok": False, "error": str(exc)})
            break
    return results
