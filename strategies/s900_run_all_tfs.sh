#!/bin/bash
# S900 — اجرای اندک‌اندکِ ۱۸ TF باقیمانده (M1 انجام شد). هر TF: discover → commit → final → commit
cd /home/user/webapp
for TF in M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1; do
  echo "===== $TF discover ====="
  python3 -u strategies/s900_minsky_moment.py --phase discover --tf $TF >> results/_s900/run_all.log 2>&1
  git add results/_s900/ && git commit -m "S900 $TF discovery locked (checkpoint)" -q
  echo "===== $TF final ====="
  python3 -u strategies/s900_minsky_moment.py --phase final --tf $TF >> results/_s900/run_all.log 2>&1
  git add results/_s900/ && git commit -m "S900 $TF final verdict (checkpoint)" -q
  git pull --rebase origin main -q 2>/dev/null; git push origin main -q 2>/dev/null
done
echo "ALL DONE" >> results/_s900/run_all.log
