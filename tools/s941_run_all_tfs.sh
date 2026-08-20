#!/bin/bash
# S941 — راه‌اندازِ زنجیره‌ای کشفِ مسیر C روی همهٔ TFها (به‌جز M1 که تمام شد)
# قانونِ «ذره‌ذره»: پس از هر TF، چک‌پوینت فوراً commit+push می‌شود.
set -u
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H6 H8 H12 D1 W1 MN1"
for TF in $TFS; do
  echo "=== S941 discover $TF === $(date -u +%H:%M:%S)"
  PYTHONPATH=. python3 -u strategies/s941_saturation_persistence.py \
      --phase discover --tf "$TF" \
      > "results/_scan_S941/discover_${TF}.log" 2>&1
  RC=$?
  BEST=$(python3 -c "
import json
try:
    l = json.load(open('results/_scan_S941/lock_XAUUSD-${TF}.json'))
    print(l.get('best_key'), l.get('score'))
except Exception as e:
    print('ERR', e)")
  git add "results/_scan_S941/discover_${TF}.json" \
          "results/_scan_S941/lock_XAUUSD-${TF}.json" 2>/dev/null
  git commit -m "S941 ${TF} checkpoint: discovery done (rc=${RC}) — locked: ${BEST}" 2>&1 | tail -1
  git pull --rebase origin main 2>&1 | tail -1
  git push origin main 2>&1 | tail -1
done
echo "=== ALL TFS DONE === $(date -u +%H:%M:%S)"
