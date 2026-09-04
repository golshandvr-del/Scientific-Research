#!/bin/bash
# S771 adjudicate runner — waits for explore to finish, then per-TF adjudication with commits.
cd /home/user/webapp
LOG=results/_scan_S771/adjudicate.log
while ! grep -q ALL_EXPLORE_DONE results/_scan_S771/explore.log; do sleep 20; done
for tf in W1 D1 H12 H8 H6 H4 H3 H2 H1 M30 M20 M15 M12 M10 M6 M5 M4 M3 M1 MN1; do
  python3 strategies/s771_amr_monthly_expansion.py --phase adjudicate --tf $tf >> $LOG 2>&1
  echo "DONE $tf" >> $LOG
  git add results/_scan_S771/${tf}_verdict.json $LOG >/dev/null 2>&1
  git commit -q -m "S771 adjudicate checkpoint: $tf" >/dev/null 2>&1
done
echo ALL_ADJ_DONE >> $LOG
