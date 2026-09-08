"""Auth: link lifecycle, sessions, prefs, rate limiting, cookie parsing."""
import os, sys, tempfile, time, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import auth as A

ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}"))
    ok = ok and cond

tmp = pathlib.Path(tempfile.mkdtemp())
au = A.Auth(tmp / "t.db")

print("=== email normalisation ===")
check("lowercases + trims", A.normalize_email("  Zico@Finostat.COM ") == "zico@finostat.com")
check("rejects garbage", A.normalize_email("not an email") is None)
check("rejects empty", A.normalize_email("") is None)
check("rejects >254", A.normalize_email("a" * 250 + "@x.com") is None)

print("\n=== magic link lifecycle ===")
tok = au.create_link("zico@finostat.com", ip="1.2.3.4")
check("token issued", tok and len(tok) > 30)
check("token not stored raw", tok not in open(tmp / "t.db", "rb").read().decode("latin1"))
uid = au.redeem_link(tok)
check("redeem creates user", isinstance(uid, int))
check("token single-use", au.redeem_link(tok) is None)
check("bogus token rejected", au.redeem_link("nope") is None)
tok2 = au.create_link("zico@finostat.com", ip="1.2.3.4")
check("same email -> same user", au.redeem_link(tok2) == uid)

# expiry
tok3 = au.create_link("late@x.com", ip="9.9.9.9")
with au._conn() as c:
    c.execute("UPDATE magic_links SET expires=? WHERE token_hash=?", (time.time() - 1, A._h(tok3)))
check("expired token rejected", au.redeem_link(tok3) is None)

print("\n=== sessions ===")
sid = au.create_session(uid)
check("session id issued", sid and len(sid) > 30)
check("session id not stored raw", sid not in open(tmp / "t.db", "rb").read().decode("latin1"))
u = au.user_for_session(sid)
check("session resolves user", u and u["email"] == "zico@finostat.com" and u["id"] == uid, u)
check("unknown session -> None", au.user_for_session("garbage") is None)
au.destroy_session(sid)
check("destroyed session gone", au.user_for_session(sid) is None)

print("\n=== prefs ===")
au.set_prefs(uid, {"watchlist": ["NIFTY 50", "INDIA VIX"], "layout": {"hide": ["wire"]}})
p = au.get_prefs(uid)
check("prefs round-trip", p.get("watchlist") == ["NIFTY 50", "INDIA VIX"] and p["layout"]["hide"] == ["wire"], p)
au.set_prefs(uid, {"watchlist": ["SENSEX"]})
check("upsert replaces one key, keeps others", au.get_prefs(uid)["watchlist"] == ["SENSEX"] and "layout" in au.get_prefs(uid))
au.set_prefs(uid, {"huge": "x" * 30000})
check("oversized value dropped", "huge" not in au.get_prefs(uid))

print("\n=== rate limiting ===")
au2 = A.Auth(tmp / "rl.db")
got = [au2.create_link("spam@x.com", ip="5.5.5.5") for _ in range(6)]
check("5 per address then blocked", all(got[:5]) and got[5] is None, [bool(g) for g in got])
got_ip = [au2.create_link(f"u{i}@x.com", ip="7.7.7.7") for i in range(21)]
check("20 per IP then blocked", all(got_ip[:20]) and got_ip[20] is None)

print("\n=== plans ===")
check("new users start on starter", au.user_for_session(au.create_session(uid))["plan"] == "starter")
check("entitlements ladder", A.entitled("starter","builder_index") and not A.entitled("starter","builder_stocks") and A.entitled("desk","builder_stocks") and not A.entitled("desk","history") and A.entitled("pro","history"))
check("set_plan by email", au.set_plan("zico@finostat.com", "desk") and au.plan_of(uid) == "desk")
check("session reflects the new plan", au.user_for_session(au.create_session(uid))["plan"] == "desk")
check("unknown user -> False", au.set_plan("nobody@x.com", "pro") is False)
try: au.set_plan("zico@finostat.com", "platinum"); bad = False
except ValueError: bad = True
check("invalid plan rejected", bad)
rid = au.request_upgrade(uid, "pro", "please")
check("upgrade request recorded", rid and au.pending_requests()[0]["plan"] == "pro" and au.pending_requests()[0]["email"] == "zico@finostat.com")
check("request rate limited (3/hour)", au.request_upgrade(uid, "pro") and au.request_upgrade(uid, "pro") and au.request_upgrade(uid, "pro") is None)
au.mark_handled(rid); check("handled requests drop off the list", all(r["id"] != rid for r in au.pending_requests()))
# migration: a pre-plan database gains the column
old_db = tmp / "old.db"; import sqlite3
c = sqlite3.connect(old_db); c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, created REAL NOT NULL, last_seen REAL)"); c.execute("INSERT INTO users(email,created) VALUES('old@x.com',1)"); c.commit(); c.close()
au_old = A.Auth(old_db)
check("pre-plan database migrated, existing user is starter", au_old.list_users()[0]["plan"] == "starter", au_old.list_users())

print("\n=== corrupt database self-heals ===")
bad = tmp / "corrupt.db"
bad.write_bytes(b"this is not a sqlite file at all, just garbage bytes\n" * 20)
(tmp / "corrupt.db-wal").write_bytes(b"x")
au3 = A.Auth(bad)
q = list(tmp.glob("corrupt.db.corrupt-*"))
check("unreadable db quarantined (renamed, not deleted)", any(p.name.endswith(tuple("0123456789")) for p in q) and len(q) >= 1, [p.name for p in q])
check("stray -wal quarantined too", any(p.name.endswith("-wal") for p in q), [p.name for p in q])
tok = au3.create_link("heal@x.com", ip="1.1.1.1")
check("fresh db works", au3.redeem_link(tok) is not None)
check("garbage preserved for inspection", any(p.read_bytes().startswith(b"this is not") for p in q if p.name.endswith(tuple("0123456789"))))

print("\n=== corrupt database restores from the newest good backup ===")
import shutil, sqlite3 as _sq
src = tmp / "acct.db"
au4 = A.Auth(src); tok4 = au4.create_link("kept@x.com", ip="2.2.2.2"); au4.redeem_link(tok4)
(tmp / "backups").mkdir(exist_ok=True)
good = tmp / "backups" / "acct-20260101-000000.db"
s_ = _sq.connect(src); d_ = _sq.connect(good); s_.backup(d_); d_.close(); s_.close()
(tmp / "backups" / "acct-20260102-000000.db").write_bytes(b"garbage newer backup that must be skipped")
src.write_bytes(b"SQLit" + b"\x17\x03\x03" * 20)                # torn header, like production
au5 = A.Auth(src)
check("restored from newest GOOD backup (skipping a bad newer one)", [u["email"] for u in au5.list_users()] == ["kept@x.com"], au5.list_users())
check("torn file preserved for inspection", list(tmp.glob("acct.db.corrupt-*")))
check("integrity_check passes after restore", _sq.connect(src).execute("PRAGMA integrity_check").fetchone()[0] == "ok")

print("\n=== cookies ===")
h = A.Auth.cookie_header("abc", secure=True)
check("cookie has HttpOnly/Secure/SameSite", all(x in h for x in ("HttpOnly", "Secure", "SameSite=Lax", "Max-Age")), h)
check("no Secure on plain http (local dev)", "Secure" not in A.Auth.cookie_header("abc", secure=False))
check("clear header expires", "Max-Age=0" in A.Auth.clear_cookie_header(True))
check("parse sid from header", A.Auth.sid_from_cookie_header("a=1; fino_session=XYZ; b=2") == "XYZ")
check("missing cookie -> None", A.Auth.sid_from_cookie_header("a=1") is None)

print("\nRESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
