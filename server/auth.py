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
  last_seen REAL,
  plan      TEXT NOT NULL DEFAULT 'starter'
);
CREATE TABLE IF NOT EXISTS upgrade_requests(
  id      INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  plan    TEXT NOT NULL,
  note    TEXT,
  ts      REAL NOT NULL,
  handled INTEGER NOT NULL DEFAULT 0
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


# Plan tiers and what they unlock. Rank order matters: a higher plan has every
# lower plan's entitlements. Payment collection is not wired yet -- plans are
# granted with admin.py after payment is received out of band.
PLANS = ("starter", "desk", "pro")
ENTITLEMENTS = {
    "terminal":       "desk",      # the live terminal itself (/dashboard and its data APIs)
    "builder_index":  "starter",   # strategy builder on the four indices (Finch's live examples)
    "builder_stocks": "desk",      # ...and every F&O stock
    "history":        "pro",       # historical replay / backtesting (future)
}


def plan_rank(plan: str) -> int:
    return PLANS.index(plan) if plan in PLANS else 0


def entitled(plan: str, feature: str) -> bool:
    need = ENTITLEMENTS.get(feature)
    return need is not None and plan_rank(plan) >= plan_rank(need)


def entitlements(plan: str) -> dict:
    return {f: entitled(plan, f) for f in ENTITLEMENTS}


def _migrate(path: pathlib.Path) -> None:
    """Add columns introduced after a database was first created."""
    c = sqlite3.connect(path, timeout=10)
    try:
        cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
        if cols and "plan" not in cols:            # no users table (another schema shares the helper) -> nothing to do
            c.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'starter'")
            c.commit()
        if cols and "plan_until" not in cols:      # NULL = no expiry (manual grants); paid plans carry one
            c.execute("ALTER TABLE users ADD COLUMN plan_until REAL")
            c.commit()
    finally:
        c.close()


def _newest_backup(path: pathlib.Path) -> pathlib.Path | None:
    bdir = path.parent / "backups"
    try:
        cands = sorted(bdir.glob(f"{path.stem}-*{path.suffix}"))
    except OSError:
        return None
    for cand in reversed(cands):                       # newest first; skip any that are themselves bad
        try:
            c = sqlite3.connect(f"file:{cand}?immutable=1", uri=True)   # WAL-flagged copies need no -shm this way
            ok = c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            c.close()
            if ok:
                return cand
        except sqlite3.Error:
            continue
    return None


def open_or_quarantine(path: pathlib.Path, schema: str) -> None:
    """Apply the schema; if the file is unreadable, set it aside, restore the
    newest good backup if there is one, else start clean.

    A corrupt database must never take the site down, and with backups on the
    volume it must not cost accounts either. The bad file is renamed, not
    deleted, so the cause can be inspected afterwards.
    """
    def apply():
        c = sqlite3.connect(path, timeout=10)
        try:
            c.executescript(schema)
            c.execute("PRAGMA journal_mode=WAL")
            c.commit()
            res = c.execute("PRAGMA integrity_check").fetchone()[0]
            if res != "ok":
                raise sqlite3.DatabaseError(f"integrity_check: {res}")
        finally:
            c.close()
    try:
        apply()
        _migrate(path)
    except sqlite3.DatabaseError as exc:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for suffix in ("", "-wal", "-shm", "-journal"):
            src = pathlib.Path(str(path) + suffix)
            if src.exists():
                src.rename(f"{path}.corrupt-{stamp}{suffix}")
        backup = _newest_backup(path)
        if backup is not None:
            import shutil
            shutil.copy2(backup, path)
            log.error("%s was unreadable (%s); quarantined as %s.corrupt-%s and RESTORED from %s",
                      path.name, exc, path.name, stamp, backup.name)
        else:
            log.error("%s was unreadable (%s); quarantined as %s.corrupt-%s and recreated (no backup found)",
                      path.name, exc, path.name, stamp)
        apply()
        _migrate(path)


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
                "SELECT u.id,u.email,u.plan,u.plan_until,s.expires FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.sid_hash=?", (_h(sid),)).fetchone()
        if row is None or row["expires"] < time.time():
            return None
        return {"id": row["id"], "email": row["email"], "plan": self.effective_plan(row["plan"], row["plan_until"]),
                "plan_until": row["plan_until"]}

    def destroy_session(self, sid: str | None) -> None:
        if not sid:
            return
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM sessions WHERE sid_hash=?", (_h(sid),))

    def checkpoint(self) -> None:
        """Fold the WAL into the main file. Called on shutdown so a machine
        stop lands on a quiescent database rather than mid-checkpoint."""
        try:
            with self._conn() as c:
                c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error as exc:
            log.warning("checkpoint failed: %s", exc)

    # -- plans --------------------------------------------------------------
    def set_plan(self, email: str, plan: str, days: int | None = None) -> bool:
        """Operator grant. days=None means no expiry."""
        if plan not in PLANS:
            raise ValueError(f"plan must be one of {PLANS}")
        until = time.time() + days * 86400 if days else None
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE users SET plan=?, plan_until=? WHERE email=?", (plan, until, email))
        return cur.rowcount > 0

    def grant(self, user_id: int, plan: str, days: int) -> float:
        """A paid period. Extends the same plan if it is still running, otherwise
        starts the new plan now. Returns the expiry timestamp."""
        if plan not in PLANS:
            raise ValueError(f"plan must be one of {PLANS}")
        now = time.time()
        with self._lock, self._conn() as c:
            row = c.execute("SELECT plan, plan_until FROM users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise ValueError("no such user")
            active = row["plan"] == plan and row["plan_until"] and row["plan_until"] > now
            until = (row["plan_until"] if active else now) + days * 86400
            c.execute("UPDATE users SET plan=?, plan_until=? WHERE id=?", (plan, until, user_id))
        return until

    @staticmethod
    def effective_plan(plan: str | None, until) -> str:
        """A paid plan past its expiry is Starter again."""
        if not plan or plan == "starter":
            return "starter"
        if until is not None and until < time.time():
            return "starter"
        return plan

    def plan_of(self, user_id: int) -> str:
        with self._conn() as c:
            row = c.execute("SELECT plan, plan_until FROM users WHERE id=?", (user_id,)).fetchone()
        return self.effective_plan(row["plan"], row["plan_until"]) if row else "starter"

    def expiring(self, within: float) -> list[dict]:
        """Paid plans ending within `within` seconds that have not been reminded for this period."""
        now = time.time()
        with self._conn() as c:
            rows = c.execute(
                "SELECT u.id,u.email,u.plan,u.plan_until,(SELECT value FROM prefs p WHERE p.user_id=u.id AND p.key='renew_notice') AS noticed "
                "FROM users u WHERE u.plan!='starter' AND u.plan_until IS NOT NULL AND u.plan_until>? AND u.plan_until<=?",
                (now, now + within)).fetchall()
        out = []
        for r in rows:
            if r["noticed"] and r["noticed"] == json.dumps(r["plan_until"]):
                continue
            out.append({"id": r["id"], "email": r["email"], "plan": r["plan"], "until": r["plan_until"]})
        return out

    def mark_reminded(self, user_id: int, until: float) -> None:
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO prefs(user_id,key,value,updated) VALUES(?,?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
                      (user_id, "renew_notice", json.dumps(until), time.time()))

    def plan_status(self, user_id: int) -> dict:
        with self._conn() as c:
            row = c.execute("SELECT plan, plan_until FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            return {"plan": "starter", "until": None, "expired": False}
        eff = self.effective_plan(row["plan"], row["plan_until"])
        return {"plan": eff, "until": row["plan_until"] if eff != "starter" else None,
                "expired": bool(row["plan"] != "starter" and eff == "starter" and row["plan_until"]),
                "lapsed_plan": row["plan"] if eff == "starter" and row["plan"] != "starter" else None}

    def request_upgrade(self, user_id: int, plan: str, note: str = "") -> int | None:
        if plan not in PLANS:
            return None
        with self._lock, self._conn() as c:
            recent = c.execute("SELECT COUNT(*) FROM upgrade_requests WHERE user_id=? AND ts>?",
                               (user_id, time.time() - 3600)).fetchone()[0]
            if recent >= 3:
                return None
            cur = c.execute("INSERT INTO upgrade_requests(user_id,plan,note,ts) VALUES(?,?,?,?)",
                            (user_id, plan, (note or "")[:500], time.time()))
        return cur.lastrowid

    def list_users(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id,email,plan,plan_until,created,last_seen FROM users ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def pending_requests(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT r.id,u.email,r.plan,r.note,r.ts FROM upgrade_requests r JOIN users u ON u.id=r.user_id "
                             "WHERE r.handled=0 ORDER BY r.id").fetchall()
        return [dict(r) for r in rows]

    def mark_handled(self, request_id: int) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE upgrade_requests SET handled=1 WHERE id=?", (request_id,))

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
