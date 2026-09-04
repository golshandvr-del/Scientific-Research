#!/bin/bash
# S771: finish explore M1 (with swap), then adjudicate all 20 cards sequentially (single process at a time).
cd /home/user/webapp
LOG=results/_scan_S771/explore.log
python3 strategies/s771_amr_monthly_expansion.py --phase explore --tf M1 >> $LOG 2>&1
echo "DONE M1" >> $LOG; echo ALL_EXPLORE_DONE >> $LOG
git add results/_scan_S771/M1_explore.json $LOG >/dev/null 2>&1; git commit -q -m "S771 explore checkpoint: M1 (after sandbox reset + swap)" >/dev/null 2>&1
ALOG=results/_scan_S771/adjudicate.log
for tf in W1 D1 H12 H8 H6 H4 H3 H2 H1 M30 M20 M15 M12 M10 M6 M5 M4 M3 MN1 M1; do
  python3 strategies/s771_amr_monthly_expansion.py --phase adjudicate --tf $tf >> $ALOG 2>&1
  echo "DONE $tf" >> $ALOG
  git add results/_scan_S771/${tf}_verdict.json $ALOG >/dev/null 2>&1
  git commit -q -m "S771 adjudicate checkpoint: $tf" >/dev/null 2>&1
done
echo ALL_ADJ_DONE >> $ALOG
