#!/bin/bash
# S949 discovery — 19 TFs, checkpoint each TF to GitHub immediately
set -u
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
echo "TFS = $TFS"
for tf in $TFS; do
  echo "===== S949 discover $tf ====="
  python3 strategies/s949_wilder_trend_birth.py --phase discover --tf "$tf" \
    > "results/_scan_S949/log_${tf}.txt" 2>&1
  rc=$?
  echo "exit=$rc"
  git add results/_scan_S949/ >/dev/null 2>&1
  git commit -m "S949 discovery checkpoint: $tf (exit=$rc)" >/dev/null 2>&1
  git pull --rebase origin main >/dev/null 2>&1
  git push origin main >/dev/null 2>&1 || echo "push failed for $tf (will retry later)"
done
echo "ALL DONE"
