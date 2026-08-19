#!/bin/bash
cd /home/user/webapp
for tf in M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1; do
  echo "=== starting $tf $(date -u +%H:%M:%S) ===" >> results/_s942/runner_progress.txt
  python3 -u strategies/s942_volume_surge_continuation.py "$tf" > "results/_s942/log_${tf}.txt" 2>&1
  echo "=== done $tf rc=$? $(date -u +%H:%M:%S) ===" >> results/_s942/runner_progress.txt
done
echo "ALL DONE $(date -u)" >> results/_s942/runner_progress.txt
