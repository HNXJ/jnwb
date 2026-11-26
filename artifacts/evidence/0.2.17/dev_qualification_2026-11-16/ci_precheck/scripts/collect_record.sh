#!/usr/bin/env bash
# Copy the pre-check scripts, package lists and one verdict block per log into a record directory.
# usage: collect_record.sh <record dir>
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
dest=${1:?record dir}
mkdir -p "$dest/scripts/py" "$dest/packages" || exit 2
cp "$here"/ci_*.sh "$here"/fetch_job_logs.sh "$here"/collect_record.sh "$dest/scripts/" || exit 1
cp "$here"/py/*.py "$dest/scripts/py/" || exit 1
cp "$here"/resolve/*.txt "$dest/packages/" || exit 1
cp D:/repos/_work/_temp_jnwb_ci/freeze_win314_fabe.txt "$dest/packages/" || exit 1
out="$dest/results.txt"
: > "$out"
for log in wsl312_fabe_full wsl312_shfabe_subset wsl312_shtip_subset wsl31318_shfabe_full wsl3152_shfabe_full \
           wsl_floors_fabe_full win314_fabe_full win314_shfabe_subset win314_shtip_subset; do
  f="$here/$log.log"
  [ -s "$f" ] || { echo "missing $f"; exit 1; }
  {
    echo "== $log"
    tr -d '\0' < "$f" | grep -a -m1 "^HEAD "
    echo "failed or errored test lines: $(tr -d '\0' < "$f" | grep -a -c -E '^(FAILED|ERROR) ')"
    tr -d '\0' < "$f" | grep -a -E "= .*(passed|failed|error).* in [0-9.]+s" | tail -1
  } >> "$out"
done
{
  echo "== wsl_build_fabe"
  tr -d '\0' < "$here/wsl_build_fabe.log" | grep -a -E "^HEAD |^===|STEP FAILED|^PASS: [0-9]|PASS: Distribution|PASS: installed|^[0-9]+ passed|rc="
} >> "$out"
echo "wrote $out: $(wc -l < "$out") lines"
