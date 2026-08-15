#!/bin/bash
# S670 — داوری نهایی ترتیبی + چک‌پوینت git پس از هر TF (قانون اندک‌اندک)
cd /home/user/webapp
TFS="M12 M15 M20 M30 H1 H2 H6 H8"
for TF in $TFS; do
  if [ -f "results/_final_S670/$TF.json" ]; then
    echo "===== [final-runner] $TF قبلاً انجام شده — پرش ====="
    continue
  fi
  echo "===== [final-runner] شروع $TF $(date -u +%H:%M:%S) ====="
  python3 strategies/s670_final_adjudication.py "$TF" 2>&1
  if [ -f "results/_final_S670/$TF.json" ]; then
    git add "results/_final_S670/$TF.json" "results/_final_S670/${TF}_trades.csv"
    git commit -m "S670 final adjudication checkpoint: $TF" >/dev/null 2>&1
    git pull --rebase origin main >/dev/null 2>&1
    git push origin main >/dev/null 2>&1 && echo "[final-runner] $TF committed+pushed"
  fi
done
echo "===== [final-runner] تمام شد $(date -u +%H:%M:%S) ====="
