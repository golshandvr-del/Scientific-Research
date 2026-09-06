#!/bin/bash
# S772 sequential runner: explore 20 TFs (coarse→fine, M1 last), then adjudicate 20. Per-TF commits (incremental law).
cd /home/user/webapp
S=strategies/s772_awr_weekly_expansion.py; LOG=results/_scan_S772/explore.log; ALOG=results/_scan_S772/adjudicate.log
for tf in MN1 W1 D1 H12 H8 H6 H4 H3 H2 H1 M30 M20 M15 M12 M10 M6 M5 M4 M3 M1; do
  python3 $S --phase explore --tf $tf >> $LOG 2>&1; echo "DONE $tf" >> $LOG
  git add results/_scan_S772/${tf}_explore.json $LOG >/dev/null 2>&1; git commit -q -m "S772 explore checkpoint: $tf" >/dev/null 2>&1
done
echo ALL_EXPLORE_DONE >> $LOG
for tf in W1 D1 H12 H8 H6 H4 H3 H2 H1 M30 M20 M15 M12 M10 M6 M5 M4 M3 MN1 M1; do
  python3 $S --phase adjudicate --tf $tf >> $ALOG 2>&1; echo "DONE $tf" >> $ALOG
  git add results/_scan_S772/${tf}_verdict.json $ALOG >/dev/null 2>&1; git commit -q -m "S772 adjudicate checkpoint: $tf" >/dev/null 2>&1
done
echo ALL_ADJ_DONE >> $ALOG
