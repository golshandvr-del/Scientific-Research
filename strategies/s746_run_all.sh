#!/bin/bash
# S746 — اجرای MTF با چک‌پوینت و کامیتِ per-TF (قانونِ اندک‌اندک)
cd /home/user/webapp
TFS="M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1 M20 M15 M12 M10 M6 M5 M4 M3 M1"
for tf in $TFS; do
  echo "=== S746 $tf ===" >> results/_scan_S746/scan.log
  python3 strategies/s746_strong_close.py "$tf" --kperm 500 >> results/_scan_S746/scan.log 2>&1
  git add results/_scan_S746/ >/dev/null 2>&1
  git commit -q -m "S746 checkpoint $tf" >/dev/null 2>&1
  for i in 1 2 3; do
    git pull --rebase -q origin main && git push -q origin main && break || sleep 3
  done
done
echo "=== S746 scan finished ===" >> results/_scan_S746/scan.log
git add results/_scan_S746/ >/dev/null 2>&1
git commit -q -m "S746 scan complete" >/dev/null 2>&1
for i in 1 2 3; do
  git pull --rebase -q origin main && git push -q origin main && break || sleep 3
done
