#!/bin/bash
# S906 batch runner — «اندک اندک»: هر TF → discover → commit → final → commit → push
set -u
cd /home/user/webapp

TFS="M2 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1"

push_safe() {
  for i in 1 2 3 4 5; do
    git pull --rebase origin main >/dev/null 2>&1 && \
    git push origin main >/dev/null 2>&1 && return 0
    sleep 4
  done
  echo "[warn] push failed after retries (auth may have expired)"
  return 1
}

for TF in $TFS; do
  echo "=== S906 $TF discover ==="
  python3 -u strategies/s906_tranquility_break.py --phase discover --tf "$TF" \
    >> results/_s906/run_all.log 2>&1 || { echo "[err] discover $TF"; continue; }
  git add results/_s906/ && git commit -m "S906 $TF discovery+lock checkpoint" >/dev/null 2>&1
  push_safe

  echo "=== S906 $TF final ==="
  python3 -u strategies/s906_tranquility_break.py --phase final --tf "$TF" \
    >> results/_s906/run_all.log 2>&1 || { echo "[err] final $TF"; continue; }
  git add results/_s906/ && git commit -m "S906 $TF FINAL verdict checkpoint" >/dev/null 2>&1
  push_safe
done
echo "S906 ALL DONE"
