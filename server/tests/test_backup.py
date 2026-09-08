import os, sys, tempfile, pathlib, sqlite3, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import backup as B
ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}")); ok = ok and cond
tmp = pathlib.Path(tempfile.mkdtemp()); src = tmp / "finostat.db"
c = sqlite3.connect(src); c.execute("PRAGMA journal_mode=WAL"); c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT)")
c.executemany("INSERT INTO users(email) VALUES(?)", [("a@x",), ("b@x",)]); c.commit()
dest = tmp / "backups"
p = B.backup_once(src, dest, keep=3)
check("backup file created", p and p.exists() and p.parent == dest, p)
rows = sqlite3.connect(p).execute("SELECT COUNT(*) FROM users").fetchone()[0]
check("backup is a consistent copy", rows == 2, rows)
c.execute("INSERT INTO users(email) VALUES('c@x')"); c.commit()       # source keeps working after backup
check("source unaffected", sqlite3.connect(src).execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3)
for _ in range(4):
    time.sleep(1.05); B.backup_once(src, dest, keep=3)
check("retention keeps the newest 3", len(list(dest.glob("finostat-*.db"))) == 3, sorted(x.name for x in dest.glob("finostat-*.db")))
check("missing source -> None, no crash", B.backup_once(tmp / "nope.db", dest) is None)
d = B.DailyBackup(src, dest, first_delay=0.05, interval=3600, keep=3); d.run_now()
st = d.stats()
check("stats after run_now", st["last"] and st["count"] == 3 and st["error"] is None, st)
print("\nRESULT:", "ALL PASS" if ok else "FAILURES"); sys.exit(0 if ok else 1)
