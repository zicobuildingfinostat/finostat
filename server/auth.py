"""Passwordless accounts: magic links, sessions, and per-user preferences.

Threat model in one paragraph: nothing secret is stored in a recoverable form.
Magic-link tokens and session ids are random 256-bit values; only their SHA-256
lands in the database, so a leaked database cannot be replayed into a login.
Links expire in fifteen minutes and burn on first use. Requests are rate
limited per address and per client IP so the form cannot be used to spam an
inbox. The flow never reveals whether an address is already registered.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import pathlib
import re
import secrets
import sqlite3
import threading
import time

log = logging.getLogger("finostat.auth")

LINK_TTL = 15 * 60                  # seconds a magic link stays valid
SESSION_TTL = 30 * 24 * 3600        # seconds a session cookie stays valid
COOKIE = "fino_session"
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id        INTEGER PRIMARY KEY,
  email     TEXT NOT NULL UNIQUE,
  created   REAL NOT NULL,
  last_seen REAL
);
CREATE TABLE IF NOT EXISTS magic_links(
  token_hash TEXT PRIMARY KEY,
  email      TEXT NOT NULL,
  expires    REAL NOT NULL,
  used       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions(
  sid_hash TEXT PRIMARY KEY,
  user_id  INTEGER NOT NULL,
  created  REAL NOT NULL,
  expires  REAL NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS prefs(
  user_id INTEGER NOT NULL,
  key     TEXT NOT NULL,
  value   TEXT NOT NULL,
  updated REAL NOT NULL,
  PRIMARY KEY(user_id, key)
);
"""


def _data_dir() -> pathlib.Path:
    configured = os.environ.get("FINOSTAT_DATA_DIR", "").strip()
    return pathlib.Path(configured) if configured else pathlib.Path(__file__).resolve().parent / "data"


def _h(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def open_or_quarantine(path: pathlib.Path, schema: str) -> None:
    """Apply the schema; if the file is unreadable, set it aside and start clean.

    A corrupt database must never take the site down. The bad file is renamed,
    not deleted, so the cause can be inspected afterwards.
    """
    def apply():
        c = sqlite3.connect(path, timeout=10)
        try:
            c.executescript(schema)
            c.execute("PRAGMA journal_mode=WAL")
            c.commit()
        finally:
            c.close()
    try:
        apply()
    except sqlite3.DatabaseError as exc:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for suffix in ("", "-wal", "-shm", "-journal"):
            src = pathlib.Path(str(path) + suffix)
            if src.exists():
                src.rename(f"{path}.corrupt-{stamp}{suffix}")
        log.error("%s was unreadable (%s); quarantined as %s.corrupt-%s and recreated",
                  path.name, exc, path.name, stamp)
        apply()


def normalize_email(raw: str) -> str | None:
    email = (raw or "").strip().lower()
    if len(email) > 254 or not _EMAIL.match(email):
        return None
    return email


class RateLimiter:
    """Sliding-window counter, in memory. Good enough for one process."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            # keep the map from growing without bound
            if len(self._hits) > 5000:
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                    self._hits.pop(k, None)
            return True


class Auth:
    def __init__(self, path: pathlib.Path | None = None):
        self.path = path or (_data_dir() / "finostat.db")
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        open_or_quarantine(self.path, _SCHEMA)
        self.link_limit_email = RateLimiter(limit=5, window=15 * 60)
        self.link_limit_ip = RateLimiter(limit=20, window=15 * 60)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    # -- magic links --------------------------------------------------------
    def create_link(self, email: str, ip: str = "") -> str | None:
        """Return a fresh single-use token, or None if rate limited."""
        if not self.link_limit_email.allow("e:" + email) or not self.link_limit_ip.allow("ip:" + ip):
            log.warning("magic link rate limited for %s / %s", email, ip)
            return None
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM magic_links WHERE expires < ? OR used = 1", (now - 3600,))
            c.execute("INSERT INTO magic_links(token_hash,email,expires,used) VALUES(?,?,?,0)",
                      (_h(token), email, now + LINK_TTL))
        return token

    def redeem_link(self, token: str) -> int | None:
        """Burn a token and return the user id (creating the user if new)."""
        if not token or len(token) > 128:
            return None
        th = _h(token)
        now = time.time()
        with self._lock, self._conn() as c:
            row = c.execute("SELECT email,expires,used FROM magic_links WHERE token_hash=?", (th,)).fetchone()
            if row is None or row["used"] or row["expires"] < now:
                return None
            c.execute("UPDATE magic_links SET used=1 WHERE token_hash=?", (th,))
            email = row["email"]
            user = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if user is None:
                cur = c.execute("INSERT INTO users(email,created,last_seen) VALUES(?,?,?)", (email, now, now))
                uid = cur.lastrowid
                log.info("new account: %s", email)
            else:
                uid = user["id"]
                c.execute("UPDATE users SET last_seen=? WHERE id=?", (now, uid))
            return uid

    # -- sessions -----------------------------------------------------------
    def create_session(self, user_id: int) -> str:
        sid = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            c.execute("INSERT INTO sessions(sid_hash,user_id,created,expires) VALUES(?,?,?,?)",
                      (_h(sid), user_id, now, now + SESSION_TTL))
        return sid

    def user_for_session(self, sid: str | None) -> dict | None:
        if not sid or len(sid) > 128:
            return None
        with self._conn() as c:
            row = c.execute(
                "SELECT u.id,u.email,s.expires FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.sid_hash=?", (_h(sid),)).fetchone()
        if row is None or row["expires"] < time.time():
            return None
        return {"id": row["id"], "email": row["email"]}

    def destroy_session(self, sid: str | None) -> None:
        if not sid:
            return
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM sessions WHERE sid_hash=?", (_h(sid),))

    def email_for(self, user_id: int) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
        return row["email"] if row else None

    # -- prefs --------------------------------------------------------------
    def get_prefs(self, user_id: int) -> dict:
        with self._conn() as c:
            rows = c.execute("SELECT key,value FROM prefs WHERE user_id=?", (user_id,)).fetchall()
        out = {}
        for r in rows:
            try:
                out[r["key"]] = json.loads(r["value"])
            except ValueError:
                pass
        return out

    def set_prefs(self, user_id: int, updates: dict) -> None:
        now = time.time()
        with self._lock, self._conn() as c:
            for key, value in updates.items():
                if not isinstance(key, str) or len(key) > 64:
                    continue
                blob = json.dumps(value, separators=(",", ":"))
                if len(blob) > 20_000:
                    continue
                c.execute("INSERT INTO prefs(user_id,key,value,updated) VALUES(?,?,?,?) "
                          "ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
                          (user_id, key, blob, now))

    # -- cookies ------------------------------------------------------------
    @staticmethod
    def cookie_header(sid: str, secure: bool) -> str:
        parts = [f"{COOKIE}={sid}", "Path=/", "HttpOnly", "SameSite=Lax", f"Max-Age={SESSION_TTL}"]
        if secure:
            parts.append("Secure")
        return "; ".join(parts)

    @staticmethod
    def clear_cookie_header(secure: bool) -> str:
        parts = [f"{COOKIE}=", "Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=0"]
        if secure:
            parts.append("Secure")
        return "; ".join(parts)

    @staticmethod
    def sid_from_cookie_header(header: str | None) -> str | None:
        if not header:
            return None
        for part in header.split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE and value:
                return value
        return None
