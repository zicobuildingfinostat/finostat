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

print("\n=== cookies ===")
h = A.Auth.cookie_header("abc", secure=True)
check("cookie has HttpOnly/Secure/SameSite", all(x in h for x in ("HttpOnly", "Secure", "SameSite=Lax", "Max-Age")), h)
check("no Secure on plain http (local dev)", "Secure" not in A.Auth.cookie_header("abc", secure=False))
check("clear header expires", "Max-Age=0" in A.Auth.clear_cookie_header(True))
check("parse sid from header", A.Auth.sid_from_cookie_header("a=1; fino_session=XYZ; b=2") == "XYZ")
check("missing cookie -> None", A.Auth.sid_from_cookie_header("a=1") is None)

print("\nRESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
