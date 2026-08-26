#!/bin/bash
# S704 — اجراگرِ اسکن با کامیتِ افزایشیِ per-TF (سندباکس ناپایدار است)
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
for tf in $TFS; do
  if [ -f "results/_s704/scan_${tf}.json" ]; then
    echo "$tf: exists, skip"
    continue
  fi
  python3 strategies/s704_vol_termstructure_scan.py "$tf" || exit 1
  git add results/_s704/ -A
  git commit -q -m "S704 scan checkpoint: ${tf} (search-half only)" || true
  git pull --rebase -q origin main 2>/dev/null || true
  git push -q origin main 2>/dev/null || true
done
echo "S704 SCAN COMPLETE"
