#!/bin/bash
# S770 — اسکن اکتشاف روی همهٔ تایم‌فریم‌ها (قانون اندک‌اندک: کامیت per کارت)
# قلمرو شماره: S770-S779 (بلوک این دانشمند). به فایل‌های بلوک‌های دیگر دست نمی‌زنیم.
cd /home/user/webapp
mkdir -p results/_scan_S770
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1"
for tf in $TFS; do
  echo "===== S770 explore $tf ====="
  python3 strategies/s770_adr_expansion.py --phase explore --tf $tf \
    > results/_scan_S770/${tf}_explore.log 2>&1
  git add results/_scan_S770/${tf}_explore.json results/_scan_S770/${tf}_explore.log 2>/dev/null
  git commit -m "S770 explore checkpoint: $tf" --quiet 2>/dev/null
  git pull --rebase origin main --quiet 2>/dev/null
  git push origin main --quiet 2>/dev/null
done
echo "===== S770 explore ALL DONE ====="
