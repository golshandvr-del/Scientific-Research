#!/bin/bash
# S674 — اجرای ترتیبی همهٔ TFها (M1 اول) + چک‌پوینت git پس از هر TF
cd /home/user/webapp
# H4 در data/mt5_full نیست (تلهٔ E-16) — حذف
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
for TF in $TFS; do
  if [ -f "results/_scan_S674/$TF.json" ]; then
    echo "===== [runner] $TF قبلاً انجام شده — پرش ====="
    continue
  fi
  echo "===== [runner] شروع $TF $(date -u +%H:%M:%S) ====="
  python3 strategies/s674_hikkake_search.py "$TF" 2>&1
  if [ -f "results/_scan_S674/$TF.json" ]; then
    git add "results/_scan_S674/$TF.json"
    git commit -m "S674 scan checkpoint: $TF (search-half only)" >/dev/null 2>&1
    git pull --rebase origin main >/dev/null 2>&1
    git push origin main >/dev/null 2>&1 && echo "[runner] $TF committed+pushed"
  fi
done
echo "===== [runner] همهٔ TFها تمام شد $(date -u +%H:%M:%S) ====="
