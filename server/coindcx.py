"""CoinDCX connection: members paste an API key + secret from their CoinDCX account; the pair is
sealed in the broker store (broker id 'coindcx') and used server-side to sign requests.
Read-only for now: balances and open orders. Signing per CoinDCX docs: HMAC-SHA256 of the JSON
body (which carries a millisecond timestamp) with the secret, sent as X-AUTH-SIGNATURE."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.request

BASE = "https://api.coindcx.com"
UA = "Finostat/1.0 (+https://finostat.com)"


class CoinDCXError(RuntimeError):
    pass


def sign(secret: str, body: dict) -> tuple[bytes, str]:
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    return raw, hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def _post(key: str, secret: str, path: str, body: dict | None = None, timeout: float = 20.0):
    body = dict(body or {}, timestamp=int(time.time() * 1000))
    raw, sig = sign(secret, body)
    req = urllib.request.Request(BASE + path, data=raw, method="POST",
                                 headers={"Content-Type": "application/json", "X-AUTH-APIKEY": key, "X-AUTH-SIGNATURE": sig, "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        text = exc.read()[:200].decode("utf-8", "replace")
        if exc.code in (401, 403):
            raise CoinDCXError("CoinDCX rejected the key/secret (check the key has read permission)") from exc
        raise CoinDCXError(f"CoinDCX HTTP {exc.code}: {text}") from exc
    except Exception as exc:
        raise CoinDCXError(f"CoinDCX unreachable: {exc}") from exc


def balances(key: str, secret: str) -> list[dict]:
    rows = _post(key, secret, "/exchange/v1/users/balances")
    out = []
    for r in rows if isinstance(rows, list) else []:
        bal, locked = float(r.get("balance") or 0), float(r.get("locked_balance") or 0)
        if bal or locked:
            out.append({"currency": r.get("currency"), "balance": bal, "locked": locked})
    out.sort(key=lambda x: -(x["balance"] + x["locked"]))
    return out


def user_info(key: str, secret: str) -> dict:
    d = _post(key, secret, "/exchange/v1/users/info")
    return {"name": d.get("first_name") or d.get("name"), "email": d.get("email"), "uid": d.get("coindcx_id") or d.get("id")} if isinstance(d, dict) else {}


def open_orders(key: str, secret: str) -> list[dict]:
    rows = _post(key, secret, "/exchange/v1/orders/active_orders", {})
    return rows if isinstance(rows, list) else (rows.get("orders") if isinstance(rows, dict) else []) or []


def valid_pair(key: str, secret: str) -> bool:
    return bool(key) and bool(secret) and 16 <= len(key) <= 128 and 16 <= len(secret) <= 128 and all(c.isalnum() for c in key) and all(c.isalnum() for c in secret)
