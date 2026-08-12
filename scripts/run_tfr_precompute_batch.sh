#!/bin/bash
# Parameterized driver for scripts/precompute_tfr_arrays_v2.py -- takes an explicit list of
# session stems (matching D:/analysis/metadata/<stem>/ and D:/nwb/omission/<stem>.nwb) as
# positional args, instead of globbing all of D:/analysis/metadata/*/ like
# run_tfr_precompute_all_sessions.sh. Lets multiple instances run concurrently against
# disjoint session lists (one process per instance, GPU-shared) without re-doing work or
# racing on the same session.
set -uo pipefail
cd "C:/workspace/omission"
CONDS="AAAX,AAXB,AXAB,BBBX,BBXA,BXBA,RRRX,RRXR,RXRR,RRRR"
LOG_DIR="/tmp/tfr_precompute_logs"
mkdir -p "$LOG_DIR"
NWB_DIR="D:/nwb/omission"

for stem in "$@"; do
  nwb="$NWB_DIR/${stem}.nwb"
  if [ ! -f "$nwb" ]; then
    echo "SKIP $stem: $nwb not found"
    continue
  fi
  echo "=== $stem ==="
  "C:/Python314/python.exe" scripts/precompute_tfr_arrays_v2.py \
    --nwb "$nwb" \
    --conditions "$CONDS" \
    > "$LOG_DIR/${stem}.log" 2>&1
  status=$?
  echo "$stem exit=$status"
done
echo "BATCH DONE"
