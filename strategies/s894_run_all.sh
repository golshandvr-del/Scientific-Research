#!/bin/bash
cd /home/user/webapp
set -u
TFS="H2 H1 H3 M30 M20 M15 M12 M10 H6 H8 H12 M5 M6 M4 M3 M1 D1 W1 MN1"
for tf in $TFS; do
  out="results/_s894/rqs2_XAUUSD-${tf}.json"
  if [ -f "$out" ]; then echo "skip $tf"; continue; fi
  echo "===== S894 $tf ====="
  nice -n 10 python3 strategies/s894_hour_harvest.py "$tf" \
    > "results/_s894/log_${tf}.txt" 2>&1 || { echo "FAIL $tf"; tail -5 "results/_s894/log_${tf}.txt"; }
  git add results/_s894/ 2>/dev/null
  git commit -qm "S894 card ${tf}" 2>/dev/null
  git pull --rebase origin main -q 2>/dev/null
  git push origin main -q 2>/dev/null || true
done
echo "ALL DONE"
