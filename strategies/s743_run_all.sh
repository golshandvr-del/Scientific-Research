#!/bin/bash
cd /home/user/webapp
for TF in M1 M3 M4 M5 M6 M10 M12 M15 M20 H1 H2 H3 H6 H8 H12 D1 W1 MN1; do
  echo "=== running $TF ==="
  python3 strategies/s743_round_level.py "$TF" --kperm 500 >> results/_scan_S743/scan.log 2>&1
  git add results/_scan_S743/ 2>/dev/null
  git commit -q -m "S743 checkpoint $TF" 2>/dev/null
  for i in 1 2 3; do git pull --rebase origin main -q 2>/dev/null && git push origin main -q 2>/dev/null && break || sleep 5; done
done
echo "=== S743 scan finished ===" >> results/_scan_S743/scan.log
