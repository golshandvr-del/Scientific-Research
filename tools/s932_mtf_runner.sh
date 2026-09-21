#!/usr/bin/env bash
# S932 — کمپینِ MTF: هر TF دو بازوی داوری‌شده (gated, counter) + base برای گاردِ G0/P1
cd /home/user/webapp
OUT=results/_s932
mkdir -p $OUT
for tf in M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1; do
  for mode in gated counter base; do
    echo "=== START $tf $mode $(date -u)" >> "$OUT/runner_progress.txt"
    python tools/s932_informed_fresh_floor_runner.py $mode $tf > "$OUT/log_${tf}_${mode}.txt" 2>&1
    echo "=== DONE  $tf $mode $(date -u) exit=$?" >> "$OUT/runner_progress.txt"
  done
done
echo "ALL DONE $(date -u)" >> "$OUT/runner_progress.txt"
