#!/bin/bash
cd /home/user/webapp
for TF in M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1; do
  echo "=== running $TF ==="
  python3 strategies/s741_failed_absorption.py "$TF" --kperm 500 >> results/_scan_S741/scan.log 2>&1
  git add results/_scan_S741/ 2>/dev/null
  git commit -q -m "S741 checkpoint $TF" 2>/dev/null
  git pull --rebase origin main -q 2>/dev/null
  git push origin main -q 2>/dev/null
done
echo "=== S741 scan finished ===" >> results/_scan_S741/scan.log
