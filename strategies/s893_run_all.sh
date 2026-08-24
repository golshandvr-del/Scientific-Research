#!/bin/bash
# S893 — اجرای ترتیبی هر ۱۶ کارت + commit تدریجی (بی‌ثباتی سندباکس)
cd /home/user/webapp
set -u
TFS="H2 H3 H1 H12 H6 H8 M30 M20 M15 M12 M10 M5 M6 M4 M3 M1 D1 W1 MN1"
for tf in $TFS; do
  out="results/_s893/rqs2_XAUUSD-${tf}.json"
  if [ -f "$out" ]; then echo "skip $tf (exists)"; continue; fi
  echo "===== S893 $tf ====="
  nice -n 10 python3 strategies/s893_canonical_null.py "$tf" \
    > "results/_s893/log_${tf}.txt" 2>&1 || { echo "FAIL $tf"; tail -5 "results/_s893/log_${tf}.txt"; }
  git add results/_s893/ 2>/dev/null
  git commit -qm "S893 card ${tf}: canonical geo-matched null re-audit" 2>/dev/null
  git pull --rebase origin main -q 2>/dev/null
  git push origin main -q 2>/dev/null || true
done
echo "ALL DONE"
