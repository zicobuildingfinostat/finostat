"""Operator CLI for accounts and plans. Runs against FINOSTAT_DATA_DIR.

  python3 admin.py users
  python3 admin.py set-plan zico@finostat.com pro
  python3 admin.py requests            # pending upgrade requests
  python3 admin.py handled 3           # mark request #3 done

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
    if cmd == "handled" and len(argv) == 3:
        au.mark_handled(int(argv[2])); print(f"  request #{argv[2]} marked handled"); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
