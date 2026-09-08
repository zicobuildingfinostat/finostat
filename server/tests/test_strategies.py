"""Strategy metrics against a Black-Scholes chain with hand-checkable answers."""
import math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import strategies as st

ok = True
def check(name, cond, extra=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {extra}"))
    ok = ok and cond

# Build the same 9-row sheet shape the feed publishes, from a convex BS chain.
def bs(S, K, t, v, cp):
    d1 = (math.log(S / K) + 0.5 * v * v * t) / (v * math.sqrt(t)); d2 = d1 - v * math.sqrt(t)
    N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    c = S * N(d1) - K * N(d2)
    return c if cp == "CE" else c - S + K

S, STEP, ATM = 23653.0, 50, 23650
chain = {}
for k in range(ATM - 5 * STEP, ATM + 6 * STEP, STEP):
    for cp in ("CE", "PE"):
        chain[(k, cp)] = round(max(0.05, bs(S, k, 2/365, 0.11, cp)), 1)
rows = []
for k in range(ATM - 4 * STEP, ATM + 5 * STEP, STEP):
    ce, pe = chain[(k, "CE")], chain[(k, "PE")]
    rows.append([k, ce, pe, 0.0, 0.0])

print("=== catalogue ===")
check("six strategies", len(st.CATALOG) == 6)
check("step inferred", st.infer_step(rows) == 50, st.infer_step(rows))
check("unknown slug -> None", st.compute("nope", rows, ATM) is None)

print("\n=== short straddle ===")
d = st.compute("short-straddle", rows, ATM)
cr = chain[(ATM, "CE")] + chain[(ATM, "PE")]
check("two sell legs at ATM", [l["action"] for l in d["legs"]] == ["SELL", "SELL"])
check("credit = CE+PE", f"₹{cr:.1f}" in d["metrics"][0][1], d["metrics"][0])
check("breakevens atm±credit", f"{ATM-cr:.0f} / {ATM+cr:.0f}" == d["metrics"][2][1], d["metrics"][2])

print("\n=== iron condor ===")
d = st.compute("iron-condor", rows, ATM)
cr = chain[(ATM-100,"PE")] + chain[(ATM+100,"CE")] - chain[(ATM-200,"PE")] - chain[(ATM+200,"CE")]
check("four legs", len(d["legs"]) == 4)
check("credit correct", f"₹{cr:.1f}" == d["metrics"][0][1], (cr, d["metrics"][0]))
check("max loss = width - credit", f"₹{100-cr:.1f}" == d["metrics"][2][1], d["metrics"][2])

print("\n=== butterfly ===")
d = st.compute("butterfly-spread", rows, ATM)
db = chain[(ATM-100,"CE")] - 2*chain[(ATM,"CE")] + chain[(ATM+100,"CE")]
check("1:2:1 legs", [l["count"] for l in d["legs"]] == [1, 2, 1])
check("debit correct", f"₹{db:.1f}" == d["metrics"][0][1], (db, d["metrics"][0]))
check("debit positive on convex chain", db > 0, db)
check("max profit = wing - debit", f"₹{100-db:.1f}" in d["metrics"][1][1], d["metrics"][1])

print("\n=== ratio spread ===")
d = st.compute("ratio-spread", rows, ATM)
net = 2*chain[(ATM+100,"CE")] - chain[(ATM,"CE")]
word = "credit" if net >= 0 else "debit"
check("1x2 legs", [l["count"] for l in d["legs"]] == [1, 2])
check("net sign worded", d["metrics"][0][0] == "Net "+word, d["metrics"][0])
check("upper breakeven", f"{ATM+200+net:.0f}" == d["metrics"][2][1], d["metrics"][2])

print("\n=== calendar ===")
d = st.compute("calendar-spread", rows, ATM, straddle=70.5)
check("honest about missing far chain", d["note"] is not None and "far expiry" in d["note"])
check("near leg priced", "₹" in d["metrics"][0][1])

print("\n=== cross butterfly ===")
d = st.compute("cross-butterfly", rows, ATM)
cf = chain[(ATM-100,"CE")] - 2*chain[(ATM,"CE")] + chain[(ATM+100,"CE")]
pf = chain[(ATM-100,"PE")] - 2*chain[(ATM,"PE")] + chain[(ATM+100,"PE")]
check("six legs", len(d["legs"]) == 6)
check("dislocation = call fly - put fly", f"₹{cf-pf:+.1f}" == d["metrics"][2][1], (cf-pf, d["metrics"][2]))
check("parity: dislocation ~ 0 on clean chain", abs(cf - pf) < 0.6, cf-pf)

print("\n=== degradation ===")
d = st.compute("iron-condor", rows[3:6], ATM)   # wings missing
check("missing strikes -> note, no metrics", d["metrics"] == [] and d["note"], d["note"])
d = st.compute("short-straddle", [], None)
check("empty chain -> waiting note", d["note"] == "Waiting for the live chain.")
allc = st.compute_all(rows, ATM, 70.0)
check("compute_all returns six", len(allc) == 6 and all(x for x in allc))

print("\nRESULT:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
