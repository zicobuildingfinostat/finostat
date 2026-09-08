#!/usr/bin/env bash
# Protocol tests. No network, no credentials, no broker needed.
set -uo pipefail
cd "$(dirname "$0")"
fail=0
for t in test_wsclient.py test_kiteticker.py test_miniproto.py test_recorder.py test_strategies.py test_auth.py test_alerts.py test_universe.py test_backup.py test_indices.py test_bs.py test_builder.py test_contracts.py test_chains.py; do
  echo "--- $t"
  python3 "$t" || fail=1
done
exit $fail
