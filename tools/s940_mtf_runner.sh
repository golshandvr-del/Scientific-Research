#!/bin/bash
# S940 MTF runner — sequential, per-TF log, per prereg order (M1 already done)
cd /home/user/webapp
for tf in M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1; do
  echo "=== starting $tf $(date -u +%H:%M:%S) ===" >> results/_s940/runner.log
  python3 -u strategies/s940_ehlers_cycle_turn.py "$tf" > "results/_s940/log_${tf}.txt" 2>&1
  echo "=== done $tf rc=$? $(date -u +%H:%M:%S) ===" >> results/_s940/runner.log
done
echo "ALL DONE $(date -u)" >> results/_s940/runner.log
