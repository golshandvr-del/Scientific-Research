#!/bin/bash
# S620 — اجرای ترتیبی همهٔ TFها (M1 اول، طبق فرمان کاربر) + چک‌پوینت git پس از هر TF
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 W1 MN1"
# D1 قبلاً انجام و commit شده است
for TF in $TFS; do
  echo "===== [runner] شروع $TF $(date -u +%H:%M:%S) ====="
  python3 strategies/s620_laguerre_exit_search.py "$TF" 2>&1
  if [ -f "results/_scan_S620/$TF.json" ]; then
    git add "results/_scan_S620/$TF.json"
    git commit -m "S620 scan checkpoint: $TF (search-half only)" >/dev/null 2>&1
    git pull --rebase origin main >/dev/null 2>&1
    git push origin main >/dev/null 2>&1 && echo "[runner] $TF committed+pushed"
  fi
done
echo "===== [runner] همهٔ TFها تمام شد $(date -u +%H:%M:%S) ====="
