#!/usr/bin/env bash
# Protocol tests. No network, no credentials, no broker needed.
set -uo pipefail
cd "$(dirname "$0")"
fail=0
for t in test_wsclient.py test_kiteticker.py test_miniproto.py test_recorder.py test_strategies.py test_auth.py test_alerts.py test_universe.py test_backup.py test_indices.py test_bs.py test_builder.py test_contracts.py test_chains.py test_finch.py test_assessment.py test_founder.py test_legal.py test_brief.py test_oi.py test_payments.py test_paywall.py test_videos.py test_broker.py test_cas.py test_book.py test_events.py test_econ.py test_analytics.py; do
  echo "--- $t"
  python3 "$t" || fail=1
done
exit $fail
