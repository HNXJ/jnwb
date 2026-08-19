#!/bin/bash
# Drives scripts/precompute_tfr_arrays_v2.py across all 21 catalogued sessions (those with a
# metadata sidecar under D:/analysis/metadata), for the 10 conditions Fig05's census and
# Fig06's RXRR-vs-RRRR contrast both need (9 omission conditions + RRRR). Logs per session.
set -uo pipefail
cd "C:/workspace/omission"
CONDS="AAAX,AAXB,AXAB,BBBX,BBXA,BXBA,RRRX,RRXR,RXRR,RRRR"
LOG_DIR="/tmp/tfr_precompute_logs"
mkdir -p "$LOG_DIR"
NWB_DIR="D:/nwb/omission"

for meta_dir in D:/analysis/metadata/*/; do
  stem=$(basename "$meta_dir")
  [ "$stem" = "sidecar_index.json" ] && continue
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
echo "ALL SESSIONS DONE"
