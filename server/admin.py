"""Operator CLI for accounts and plans. Runs against FINOSTAT_DATA_DIR.

  python3 admin.py users
  python3 admin.py set-plan zico@finostat.com pro
  python3 admin.py requests            # pending upgrade requests
  python3 admin.py handled 3           # mark request #3 done
  python3 admin.py assessments [N]     # latest N trader assessments (default 50)
  python3 admin.py assessments-csv > leads.csv
  python3 admin.py assessment-delete 7   # remove one submission

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
            print(f"  #{u['id']:<4} {u['email']:<36} {u['plan']:<8} last seen {seen}")
        return 0
    if cmd == "set-plan" and len(argv) == 4:
        email, plan = argv[2].strip().lower(), argv[3].strip().lower()
        try:
            ok = au.set_plan(email, plan)
        except ValueError as exc:
            print(f"  {exc}"); return 2
        print(f"  {'updated' if ok else 'NO SUCH USER'}: {email} -> {plan}")
        return 0 if ok else 1
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
    if cmd == "assessment-delete" and len(argv) == 3:
        import assessment
        ok = assessment.Assessments(au.path).delete(int(argv[2]))
        print(f"  {'deleted' if ok else 'NO SUCH SUBMISSION'}: #{argv[2]}"); return 0 if ok else 1
    if cmd == "handled" and len(argv) == 3:
        au.mark_handled(int(argv[2])); print(f"  request #{argv[2]} marked handled"); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
