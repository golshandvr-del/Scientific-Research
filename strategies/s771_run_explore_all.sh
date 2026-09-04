#!/bin/bash
# S771 explore runner — per-TF, commit after each card (incremental law). Coarse→fine so evidence lands early.
cd /home/user/webapp
LOG=results/_scan_S771/explore.log
for tf in MN1 W1 D1 H12 H8 H6 H4 H3 H2 H1 M30 M20 M15 M12 M10 M6 M5 M4 M3 M1; do
  python3 strategies/s771_amr_monthly_expansion.py --phase explore --tf $tf >> $LOG 2>&1
  echo "DONE $tf" >> $LOG
  git add results/_scan_S771/${tf}_explore.json $LOG >/dev/null 2>&1
  git commit -q -m "S771 explore checkpoint: $tf" >/dev/null 2>&1
done
echo ALL_EXPLORE_DONE >> $LOG
