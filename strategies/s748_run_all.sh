#!/bin/bash
# S748 — اسکن ۲۰ تایم‌فریم با چک‌پوینت و commit+push هر TF (قانون اندک‌اندک)
cd /home/user/webapp
LOG=results/_scan_S748/scan.log
mkdir -p results/_scan_S748
echo "=== S748 scan started $(date -u) ===" >> "$LOG"
for TF in MN1 W1 D1 H12 H8 H6 H4 H3 H2 H1 M30 M20 M15 M12 M10 M6 M5 M4 M3 M1; do
  echo "--- $TF $(date -u) ---" >> "$LOG"
  python3 strategies/s748_dual_drift.py "$TF" >> "$LOG" 2>&1
  git add results/_scan_S748/ >/dev/null 2>&1
  git commit -q -m "S748 checkpoint $TF" >/dev/null 2>&1
  for i in 1 2 3; do
    git pull --rebase -q origin main >/dev/null 2>&1 && \
    git push -q origin main >/dev/null 2>&1 && break || sleep 3
  done
done
echo "=== S748 scan finished $(date -u) ===" >> "$LOG"
git add results/_scan_S748/ >/dev/null 2>&1
git commit -q -m "S748 scan complete" >/dev/null 2>&1
for i in 1 2 3; do
  git pull --rebase -q origin main >/dev/null 2>&1 && \
  git push -q origin main >/dev/null 2>&1 && break || sleep 3
done
