#!/bin/bash
# S770 — داوری RQS2 کامل روی کارت‌های دارای سلول پایدار در اکتشاف (مسیر C)
# کارت‌های بدون best خودکار REJECT-by-rule ثبت می‌شوند.
cd /home/user/webapp
TFS="H1 H4 H6 H8 H12 D1 W1 M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H2 H3 MN1"
for tf in $TFS; do
  echo "===== S770 adjudicate $tf ====="
  python3 strategies/s770_adr_expansion.py --phase adjudicate --tf $tf \
    > results/_scan_S770/${tf}_adjudicate.log 2>&1
  git add results/_scan_S770/${tf}_verdict.json results/_scan_S770/${tf}_adjudicate.log 2>/dev/null
  git commit -m "S770 adjudicate checkpoint: $tf" --quiet 2>/dev/null
  git pull --rebase origin main --quiet 2>/dev/null
  git push origin main --quiet 2>/dev/null
done
echo "===== S770 adjudicate ALL DONE ====="
