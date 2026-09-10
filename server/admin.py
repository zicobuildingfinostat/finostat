"""Operator CLI for accounts and plans. Runs against FINOSTAT_DATA_DIR.

  python3 admin.py users
  python3 admin.py set-plan zico@finostat.com pro [DAYS]   # DAYS omitted = no expiry
  python3 admin.py payments [N]        # latest N Razorpay orders/payments
  python3 admin.py requests            # pending upgrade requests
  python3 admin.py handled 3           # mark request #3 done
  python3 admin.py assessments [N]     # latest N trader assessments (default 50)
  python3 admin.py assessments-csv > leads.csv
  python3 admin.py assessment-delete 7   # remove one submission
  python3 admin.py quotes                # lines visitors wrote; ★ = may be published
  python3 admin.py brief-now open|close [YYYY-MM-DD]   # ask the server to take a brief snapshot now
  python3 admin.py briefs                # stored briefs

On Fly:  fly ssh console --app finostat -C "python3 /app/server/admin.py users"
"""
from __future__ import annotations

import sys
import time

import auth as authmod


def main(argv: list[str]) -> int:
    au = authmod.Auth()
    cmd = argv[1] if len(argv) > 1 else "users"
    if cmd == "users":
        for u in au.list_users():
            seen = time.strftime("%Y-%m-%d %H:%M", time.localtime(u["last_seen"] or u["created"]))
            until = (" until " + time.strftime("%Y-%m-%d", time.localtime(u["plan_until"]))) if u.get("plan_until") else ""
            print(f"  #{u['id']:<4} {u['email']:<36} {u['plan']:<8}{until:<18} last seen {seen}")
        return 0
    if cmd == "set-plan" and len(argv) in (4, 5):
        email, plan = argv[2].strip().lower(), argv[3].strip().lower()
        days = int(argv[4]) if len(argv) == 5 else None
        try:
            ok = au.set_plan(email, plan, days)
        except ValueError as exc:
            print(f"  {exc}"); return 2
        print(f"  {'updated' if ok else 'NO SUCH USER'}: {email} -> {plan}" + (f" for {days} days" if days else " (no expiry)"))
        return 0 if ok else 1
    if cmd == "payments":
        import payments as pm
        rows = pm.Payments(au.path).recent(int(argv[2]) if len(argv) > 2 else 50)
        if not rows:
            print("  no orders yet")
        for r in rows:
            print(f"  #{r['id']:<4} {time.strftime('%Y-%m-%d %H:%M', time.localtime(r['created']))}  {r['email']:<32} {r['plan']:<5} {r['period']:<8} ₹{r['amount'] / 100:>10,.2f}  {r['status']:<8} {r['payment_id'] or '-'}")
        return 0
    if cmd == "requests":
        rows = au.pending_requests()
        if not rows:
            print("  no pending upgrade requests")
        for r in rows:
            print(f"  #{r['id']:<4} {r['email']:<36} wants {r['plan']:<6} {time.strftime('%Y-%m-%d %H:%M', time.localtime(r['ts']))}  {r['note'] or ''}")
        return 0
    if cmd in ("assessments", "assessments-csv"):
        import assessment
        store = assessment.Assessments(au.path)
        if cmd == "assessments-csv":
            sys.stdout.write(store.export_csv()); return 0
        rows = store.recent(int(argv[2]) if len(argv) > 2 else 50)
        print(f"  {store.count()} assessments total")
        for r in rows:
            a = __import__("json").loads(r["answers"])
            print(f"  #{r['id']:<4} {time.strftime('%Y-%m-%d %H:%M', time.localtime(r['ts']))}  {r['name'][:22]:<22} {r['email']:<32} {r['phone']}  {r['profile']:<12} {r['score']}/7  "
                  f"{assessment.describe('years', a.get('years'))} · {assessment.describe('goal', a.get('goal'))}")
        return 0
    if cmd == "brief-now" and len(argv) >= 3:
        import pathlib
        (au.path.parent / "brief.trigger").write_text(" ".join(argv[2:4]))
        print(f"  trigger written; the server takes the {argv[2]} snapshot within 30s (watch /api/status.brief)"); return 0
    if cmd == "briefs":
        import brief as briefmod
        st = briefmod.Briefs(au.path)
        for d in st.dates(30):
            r = st.get(d); print(f"  {d}  open={'yes' if r['open'] else 'no ':<3} close={'yes' if r['close'] else 'no'}")
        return 0
    if cmd == "quotes":
        import assessment, json as _json
        rows = assessment.Assessments(au.path).quotes()
        if not rows:
            print("  no quotes yet")
        for r in rows:
            a = _json.loads(r["answers"])
            who = f"{r['name'].split()[0]}, {a.get('city') or 'India'}"
            print(f"  #{r['id']:<4} {'★' if r['quote_ok'] else ' '} {who:<24} <{r['email']}>\n        “{r['quote']}”")
        return 0
    if cmd == "assessment-delete" and len(argv) == 3:
        import assessment
        ok = assessment.Assessments(au.path).delete(int(argv[2]))
        print(f"  {'deleted' if ok else 'NO SUCH SUBMISSION'}: #{argv[2]}"); return 0 if ok else 1
    if cmd == "handled" and len(argv) == 3:
        au.mark_handled(int(argv[2])); print(f"  request #{argv[2]} marked handled"); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
