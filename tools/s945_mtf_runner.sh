#!/bin/bash
# S945 MTF campaign runner — sequential per-TF, incremental logs (M1 already done)
cd /home/user/webapp
OUT=results/_s945
mkdir -p "$OUT"
TFS="M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1"
for tf in $TFS; do
  echo "=== START $tf $(date -u)" >> "$OUT/runner_progress.txt"
  python strategies/s945_amihud_thin_move_fade.py "$tf" > "$OUT/log_${tf}.txt" 2>&1
  echo "=== DONE  $tf $(date -u) exit=$?" >> "$OUT/runner_progress.txt"
done
echo "ALL DONE $(date -u)" >> "$OUT/runner_progress.txt"
