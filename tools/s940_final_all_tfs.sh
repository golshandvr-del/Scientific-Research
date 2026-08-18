#!/bin/bash
# S940 — فاز دوم مسیر C: آزمونِ تک‌تیرِ holdout برای هر TFِ قفل‌شده.
# قفل‌ها پیش‌تر commit شده‌اند (مُهر زمانی git = پیش‌ثبت). هر TF فقط یک بار.
# فقط فایل‌های _scan_S940 لمس می‌شوند (عدم مداخله در کار دانشمندان موازی).
set -u
cd /home/user/webapp
TFS="M12 M15 M20 M30 H1 H2 H3 H6 H8"
for TF in $TFS; do
  if [ -f "results/_scan_S940/final_XAUUSD-${TF}.json" ]; then
    echo "=== $TF already final — skip (one-shot rule) ==="
    continue
  fi
  echo "=== S940 FINAL $TF === $(date -u +%H:%M:%S)"
  PYTHONPATH=. python3 -u strategies/s940_volatility_birth.py \
      --phase final --tf "$TF" \
      > "results/_scan_S940/final_${TF}.log" 2>&1
  RC=$?
  V=$(python3 -c "
import json
try:
    r = json.load(open('results/_scan_S940/final_XAUUSD-${TF}.json'))
    print(r.get('verdict'), r.get('score'))
except Exception as e:
    print('ERR', e)")
  git add "results/_scan_S940/final_XAUUSD-${TF}.json" \
          "results/_scan_S940/null_XAUUSD-${TF}.json" 2>/dev/null
  git commit -m "S940 ${TF} HOLDOUT VERDICT (one-shot, n_trials=1): ${V} (rc=${RC})" 2>&1 | tail -1
  git pull --rebase origin main 2>&1 | tail -1
  git push origin main 2>&1 | tail -1
done
echo "=== ALL FINALS DONE === $(date -u +%H:%M:%S)"
