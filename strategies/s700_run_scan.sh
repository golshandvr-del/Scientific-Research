#!/bin/bash
# S700 — اجرای اسکنِ نیمهٔ جست‌وجو، کارت به کارت، با کامیتِ افزایشی (ضدِ ریستِ سندباکس)
cd /home/user/webapp
for tf in M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1; do
  if [ -f "results/_s700/scan_${tf}.json" ]; then
    echo "[skip] $tf already scanned"
    continue
  fi
  echo "[scan] $tf started $(date -u +%H:%M:%S)"
  python3 strategies/s700_aroon_pulse_scan.py "$tf" || { echo "[FAIL] $tf"; exit 1; }
  git add results/_s700/ strategies/s700_aroon_pulse_scan.py strategies/s700_run_scan.sh
  git commit -m "S700 scan checkpoint: ${tf} (search-half only)" -q
  git pull --rebase origin main -q 2>/dev/null
  git push origin main -q 2>/dev/null || echo "[warn] push failed for $tf (will retry next TF)"
  echo "[done] $tf $(date -u +%H:%M:%S)"
done
echo "S700 SCAN COMPLETE"
