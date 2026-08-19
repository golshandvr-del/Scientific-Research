#!/bin/bash
# S892: all 19 gold TFs, M1 first (law), commit+push per TF. NO EURUSD.
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
for tf in $TFS; do
  f="results/_s892/rqs2_XAUUSD-$tf.json"
  if [ -f "$f" ]; then echo "[skip] $tf"; continue; fi
  echo "===== RUN $tf $(date -u +%H:%M:%S) ====="
  nice -n 10 python3 strategies/s892_session_drift.py "$tf" > "results/_s892/log_$tf.txt" 2>&1
  rc=$?
  tail -5 "results/_s892/log_$tf.txt"
  [ $rc -ne 0 ] && echo "[ERR] $tf rc=$rc"
  git add results/_s892/ >/dev/null 2>&1
  git commit -m "S892 progress: XAUUSD-$tf tested (prereg b0f8770a)" -q 2>/dev/null
  git push origin main -q 2>/dev/null || true
done
echo "===== S892 ALL DONE $(date -u +%H:%M:%S) ====="
