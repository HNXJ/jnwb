#!/usr/bin/env bash
# Save the log of each named Actions job of hnxj/jnwb and print the Python version, runner image and result line.
# usage: fetch_job_logs.sh <outdir> <jobid:label>...
export MSYS_NO_PATHCONV=1
out=${1:?outdir}; shift
mkdir -p "$out"
for pair in "$@"; do
  id=${pair%%:*}; label=${pair#*:}
  f="$out/job_${label}_$id.log"
  [ -s "$f" ] || gh api "repos/hnxj/jnwb/actions/jobs/$id/logs" > "$f" 2> "$f.err" || { echo "$label: log unreadable"; continue; }
  echo "== $label ($(wc -c < "$f") bytes)"
  grep -o -m1 -E "Successfully set up CPython \([0-9.a-z]+\)|Installed versions|Python 3\.1[0-9]\.[0-9a-z]+" "$f" | head -1
  grep -o -m2 -E "Image: .*|Version: 2[0-9]{7}[0-9.]*" "$f" | paste -sd' ' -
  grep -E "= .*[0-9]+ passed" "$f" | tail -2 | cut -c30-200
done
