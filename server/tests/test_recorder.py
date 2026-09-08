"""Recorder: live-only filter, throttling, batch writes, read-back."""
import os, sys, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}"))
    ok = ok and cond

tmp = tempfile.mkdtemp()
os.environ["FINOSTAT_DATA_DIR"] = tmp
import recorder as R

rec = R.Recorder()
rec.MIN_INTERVAL = 0.0        # no throttle for the write test
rec.BATCH_COMMIT = 0.1
rec.start()

live = {"live": True, "symbol": "NIFTY", "atm": 23650, "straddle": 75.4,
        "quotes": [{"symbol": "NIFTY 50", "price": 23653.6, "change": -0.2}],
        "sheet": {"rows": [[23650, 46.4, 29.0, 43.6, 0.6]]}, "mini": [[57500, 300.0, -280.0]]}
sim = dict(live, live=False)

rec.on_snapshot(sim)                    # must be ignored
for _ in range(5):
    rec.on_snapshot(live)
    time.sleep(0.01)
time.sleep(1.8)                          # writer blocks up to 1s in get() before committing

st = rec.stats()
check("simulator snapshots never recorded", st["written"] == 5, st)
check("db file exists", os.path.exists(os.path.join(tmp, "ticks.db")))
check("no write errors", st["error"] is None, st)

hist = rec.history(limit=10)
check("read-back returns rows", len(hist) == 5, len(hist))
check("row content intact", hist[0]["atm"] == 23650 and hist[0]["rows"][0][0] == 23650, hist[:1])
check("quotes decoded", hist[0]["quotes"][0]["symbol"] == "NIFTY 50")

since = hist[2]["ts"]
newer = rec.history(since=since, limit=10)
check("since filter", len(newer) == 2, len(newer))

rec2 = R.Recorder()                      # fresh instance, default throttle
t0 = time.time()
n0 = rec2._queue.qsize()
for _ in range(50):
    rec2.on_snapshot(live)
check("1/sec throttle holds", rec2._queue.qsize() <= 1, rec2._queue.qsize())

rec.stop()
print("\nRESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
