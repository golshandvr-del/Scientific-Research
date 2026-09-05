#!/bin/bash
# S907 batch runner — «اندک اندک»: هر TF → discover → commit → final → commit → push
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
  echo "=== S907 $TF discover ==="
  python3 -u strategies/s907_quiet_regime_exit.py --phase discover --tf "$TF" \
    >> results/_s907/run_all.log 2>&1 || { echo "[err] discover $TF"; continue; }
  git add results/_s907/ && git commit -m "S907 $TF discovery+lock checkpoint" >/dev/null 2>&1
  push_safe

  echo "=== S907 $TF final ==="
  python3 -u strategies/s907_quiet_regime_exit.py --phase final --tf "$TF" \
    >> results/_s907/run_all.log 2>&1 || { echo "[err] final $TF"; continue; }
  git add results/_s907/ && git commit -m "S907 $TF FINAL verdict checkpoint" >/dev/null 2>&1
  push_safe
done
echo "S907 ALL DONE"
