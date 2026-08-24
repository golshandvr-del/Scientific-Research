#!/bin/bash
# S972 — اجرای زنجیره‌ای همهٔ TFها (قانون MTF) با commit پس از هر TF (قانون اندک‌اندک)
cd /home/user/webapp
TFS="M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1"
for TF in $TFS; do
  echo "=== $(date -u +%H:%M:%S) launching $TF ===" >> results/_scan_S972/runner.log
  python3 strategies/s972_cs_spread_shock_fade.py "$TF" > "results/_scan_S972/${TF}.log" 2>&1
  V=$(python3 -c "import json;print(json.load(open('results/_scan_S972/${TF}.json')).get('verdict','?'))" 2>/dev/null || echo ERR)
  git add "results/_scan_S972/${TF}.json" 2>/dev/null
  git commit -q -m "S972 checkpoint ${TF}: ${V}" 2>/dev/null
  git pull --rebase -q origin main 2>/dev/null
  git push -q origin main 2>/dev/null
  echo "=== $(date -u +%H:%M:%S) $TF done: $V ===" >> results/_scan_S972/runner.log
done
echo "ALL DONE $(date -u)" >> results/_scan_S972/runner.log
