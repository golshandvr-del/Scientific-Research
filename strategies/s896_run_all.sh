#!/bin/bash
# S896 sequential runner — per-TF commit+push (sandbox instability rule)
cd /home/user/webapp
mkdir -p results/_s896
for TF in H12 H8 H6 H3 H2 H1 M30 M20 M15 M12 M10 M6 M5 M4 M3 M1 D1 W1 MN1; do
  if [ -f "results/_s896/rqs2_XAUUSD-${TF}.json" ]; then
    echo "skip ${TF} (exists)"; continue
  fi
  echo "=== ${TF} ==="
  nice -n 10 python3 strategies/s896_record_drought.py ${TF} \
    > results/_s896/log_${TF}.txt 2>&1
  RC=$?
  echo "rc=${RC}"
  git add results/_s896/ && \
  git commit -qm "S896 checkpoint: XAUUSD-${TF} card (RecordAfterDrought, prereg d7338160)" && \
  git pull --rebase origin main -q && git push origin main -q || echo "PUSH FAILED ${TF}"
done
echo "ALL DONE"
