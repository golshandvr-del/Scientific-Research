#!/bin/bash
cd /home/user/webapp
for TF in M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1; do
  python3 -u strategies/s902_ponzi_acceleration.py --phase discover --tf $TF >> results/_s902/run_all.log 2>&1
  git add results/_s902/ && git commit -m "S902 $TF discovery locked (checkpoint)" -q
  python3 -u strategies/s902_ponzi_acceleration.py --phase final --tf $TF >> results/_s902/run_all.log 2>&1
  git add results/_s902/ && git commit -m "S902 $TF final verdict (checkpoint)" -q
  git pull --rebase origin main -q 2>/dev/null; git push origin main -q 2>/dev/null
done
echo "S902 ALL DONE" >> results/_s902/run_all.log
