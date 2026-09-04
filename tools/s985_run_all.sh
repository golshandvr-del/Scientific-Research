#!/bin/bash
# S985 — اجرای ۱۹ کارت با checkpoint (کامیت+پوش) بعد از هر کارت — قانونِ ذره-ذره
cd /home/user/webapp
mkdir -p results/_s985
for TF in MN1 W1 D1 H12 H8 H6 H4 H3 H2 M30 M20 M15 M12 M10 M6 M5 M4 M3 M1; do
  [ -f results/_s985/scan_$TF.json ] && { echo "=== [$TF] already done ==="; continue; }
  echo "=== [$TF] start $(date -u +%H:%M:%S) ==="
  python3 strategies/s985_bvc_toxicity_scan.py --tf $TF 2>&1 | tee results/_s985/log_$TF.txt | tail -14
  git pull --rebase origin main >/dev/null 2>&1 || git rebase --abort >/dev/null 2>&1
  git add results/_s985/ tools/s985_run_all.sh
  BEST=$(python3 -c "
import json
try:
    d=json.load(open('results/_s985/scan_$TF.json'))
    r=d['results']
    if r: print(f\"best z={r[0]['z']:+.2f} lift={r[0]['lift']:+.2f}pp n={r[0]['n']} L={r[0]['L']} k={r[0]['kappa']} {r[0]['mode']}\")
    else: print('no arm with n>=30')
except Exception as e: print('?', e)")
  git commit -q -m "S985 checkpoint $TF: $BEST" 2>/dev/null
  for i in 1 2 3; do
    git push origin main >/dev/null 2>&1 && break
    git pull --rebase origin main >/dev/null 2>&1
    sleep 3
  done
  echo "=== [$TF] pushed: $BEST ==="
done
echo "ALL DONE $(date -u)"
