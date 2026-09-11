#!/bin/bash
# S709 — M1 سلول‌به‌سلول در فرایندِ جدا (حافظه)؛ منطق عیناً همان اسکن
cd /home/user/webapp
for i in $(seq 1 20); do
  [ -f results/_s709/scan_M1.json ] && break
  S709_ONE_CELL=1 python3 strategies/s709_range_record_scan.py M1 || { echo "cell $i failed"; }
  git add results/_s709/ -A; git commit -q -m "S709 M1 cell checkpoint $i (search-half only)" || true
done
git pull --rebase -q origin main 2>/dev/null || true; git push -q origin main 2>/dev/null || true
echo "S709 M1 DONE"
