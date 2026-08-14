#!/bin/bash
# S890: run all 19 gold TFs sequentially, commit+push after each TF.
# Law: start from M1. NO EURUSD (explicit user order).
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
for tf in $TFS; do
  f="results/_s890/rqs2_XAUUSD-$tf.json"
  if [ -f "$f" ]; then echo "[skip] $tf already done"; continue; fi
  echo "===== RUN $tf $(date -u +%H:%M:%S) ====="
  python3 strategies/s890_reflexive_breakout.py "$tf" > "results/_s890/log_$tf.txt" 2>&1
  rc=$?
  tail -6 "results/_s890/log_$tf.txt"
  if [ $rc -ne 0 ]; then echo "[ERR] $tf rc=$rc"; fi
  git add results/_s890/ >/dev/null 2>&1
  git commit -m "S890 progress: XAUUSD-$tf tested (prereg 42ee0496)" >/dev/null 2>&1
  git push origin main >/dev/null 2>&1 || true
done
echo "===== ALL DONE $(date -u +%H:%M:%S) ====="
