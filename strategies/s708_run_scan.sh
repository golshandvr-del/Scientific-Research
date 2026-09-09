#!/bin/bash
# S708 — اجراگرِ اسکن با کامیتِ افزایشیِ per-TF (سندباکس ناپایدار است)
# فقط تایم‌فریم‌های درون‌روزی: D1/W1/MN1 رویدادِ درون‌روزی ندارند
cd /home/user/webapp
TFS="M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
for tf in $TFS; do
  if [ -f "results/_s708/scan_${tf}.json" ]; then
    echo "$tf: exists, skip"
    continue
  fi
  python3 strategies/s708_shock_echo_scan.py "$tf" || exit 1
  git add results/_s708/ -A
  git commit -q -m "S708 scan checkpoint: ${tf} (search-half only)" || true
  git pull --rebase -q origin main 2>/dev/null || true
  git push -q origin main 2>/dev/null || true
done
echo "S708 SCAN COMPLETE"
