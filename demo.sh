#!/usr/bin/env bash
# End-to-end demonstration of the DBYR v0.1 toolchain.
set -e
export PYTHONPATH="$(dirname "$0")"
cd "$(dirname "$0")"

echo "== 1. Validate the reconstructed Intent =="
python -m dbyr.cli validate examples/intent-exploitgym-2026-05.json || true

echo -e "\n== 2. Backtest against the incident event stream =="
python -m dbyr.cli replay --intent examples/intent-exploitgym-2026-05.json

echo -e "\n== 3. The historical record, filed honestly =="
python -m dbyr.cli validate examples/closeout-noncompliant-2026-07.json \
  --intent examples/intent-exploitgym-2026-05.json || true

echo -e "\n== 4. Public tier of the Intent (first 40 lines) =="
python -m dbyr.cli view examples/intent-exploitgym-2026-05.json --tier public | head -40

echo -e "\n== 5. File to a hash-chained register =="
rm -f /tmp/dbyr-demo-register.jsonl
python -m dbyr.cli file examples/intent-exploitgym-2026-05.json \
  --register /tmp/dbyr-demo-register.jsonl --sign

echo -e "\n== 6. Regime coverage =="
python -m dbyr.cli interop coverage | tail -18
