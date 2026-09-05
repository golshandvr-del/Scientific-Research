#!/bin/bash
# S1940 discovery — 19 TFs, checkpoint each TF to GitHub immediately
set -u
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
echo "TFS = $TFS"
for tf in $TFS; do
  echo "===== S1940 discover $tf ====="
  python3 strategies/s1940_round_level_fresh_cross.py --phase discover --tf "$tf" \
    > "results/_scan_S1940/log_${tf}.txt" 2>&1
  rc=$?
  echo "exit=$rc"
  git add results/_scan_S1940/ >/dev/null 2>&1
  git commit -m "S1940 discovery checkpoint: $tf (exit=$rc)" >/dev/null 2>&1
  git -c credential.helper= pull -q --rebase "$GH_PUSH_URL" main >/dev/null 2>&1
  git -c credential.helper= push -q "$GH_PUSH_URL" HEAD:main >/dev/null 2>&1 || echo "push failed for $tf (will retry later)"
done
echo "ALL DONE"
