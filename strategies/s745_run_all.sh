#!/bin/bash
# S745 — اجرای MTF با چک‌پوینت و کامیتِ per-TF (قانونِ اندک‌اندک)
cd /home/user/webapp
TFS="M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1 M20 M15 M12 M10 M6 M5 M4 M3 M1"
for tf in $TFS; do
  echo "=== S745 $tf ===" >> results/_scan_S745/scan.log
  python3 strategies/s745_key_reversal.py "$tf" --kperm 500 >> results/_scan_S745/scan.log 2>&1
  git add results/_scan_S745/ >/dev/null 2>&1
  git commit -q -m "S745 checkpoint $tf" >/dev/null 2>&1
  for i in 1 2 3; do
    git pull --rebase -q origin main && git push -q origin main && break || sleep 3
  done
done
echo "=== S745 scan finished ===" >> results/_scan_S745/scan.log
git add results/_scan_S745/ >/dev/null 2>&1
git commit -q -m "S745 scan complete" >/dev/null 2>&1
for i in 1 2 3; do
  git pull --rebase -q origin main && git push -q origin main && break || sleep 3
done
