#!/bin/bash
cd /home/user/webapp
for tf in M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1; do
  echo "=== starting $tf $(date -u +%H:%M:%S) ===" >> results/_s941/runner.log
  python3 -u strategies/s941_ehlers_extremum_turn.py "$tf" > "results/_s941/log_${tf}.txt" 2>&1
  echo "=== done $tf rc=$? $(date -u +%H:%M:%S) ===" >> results/_s941/runner.log
done
echo "ALL DONE $(date -u)" >> results/_s941/runner.log
