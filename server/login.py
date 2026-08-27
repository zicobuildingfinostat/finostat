"""Mint a Kite Connect access token.

Kite access tokens expire every morning, so this is a daily ritual:

  1. Open the login URL this script prints and sign in to Zerodha.
  2. You land on your redirect URL carrying ?request_token=XXXX
  3. Run:  python3 login.py XXXX
  4. Paste the printed KITE_ACCESS_TOKEN line into server/.env

Your api_secret is only ever used locally, to compute the SHA-256 checksum
Kite requires. It is never logged or transmitted anywhere except to Kite.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import config


def login_url() -> str:
    return f"https://kite.zerodha.com/connect/login?v=3&api_key={config.KITE_API_KEY}"


def exchange(request_token: str) -> dict:
    checksum = hashlib.sha256(
        (config.KITE_API_KEY + request_token + config.KITE_API_SECRET).encode()
    ).hexdigest()
    body = urllib.parse.urlencode({
        "api_key": config.KITE_API_KEY,
        "request_token": request_token,
        "checksum": checksum,
    }).encode()
    req = urllib.request.Request(
        config.KITE_BASE + "/session/token", data=body, method="POST",
        headers={"X-Kite-Version": "3", "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"Kite refused the exchange (HTTP {exc.code}): {detail}")
    if payload.get("status") != "success":
        raise SystemExit(f"Kite error: {payload.get('message')}")
    return payload["data"]


def main(argv: list[str]) -> int:
    if not config.KITE_API_KEY or not config.KITE_API_SECRET:
        print("Set KITE_API_KEY and KITE_API_SECRET in server/.env first.", file=sys.stderr)
        return 2
    if len(argv) < 2:
        print("Step 1 — sign in here:\n")
        print("   " + login_url())
        print("\nStep 2 — copy the request_token from the redirect URL, then run:\n")
        print("   python3 login.py <request_token>\n")
        return 0
    data = exchange(argv[1].strip())
    print(f"\nSigned in as {data.get('user_name')} ({data.get('user_id')}).")
    print("Add this line to server/.env — it is valid until tomorrow morning:\n")
    print(f"KITE_ACCESS_TOKEN={data['access_token']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
