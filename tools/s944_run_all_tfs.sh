#!/bin/bash
# S944 discovery — chained over all 19 gold TFs, checkpoint commit+push per TF
set -u
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
for TF in $TFS; do
  echo "=== S944 DISCOVER $TF ==="
  python3 strategies/s944_turn_of_month.py --phase discover --tf "$TF" \
    > "results/_scan_S944/log_discover_${TF}.txt" 2>&1
  RC=$?
  git add results/_scan_S944/ 2>/dev/null
  git commit -m "S944 ${TF} discovery checkpoint (rc=${RC})" -q 2>/dev/null
  git pull --rebase origin main -q 2>/dev/null
  git push origin main -q 2>/dev/null
  echo "=== $TF done rc=$RC ==="
done
echo "ALL S944 DISCOVERY DONE"
