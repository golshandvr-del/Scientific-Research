#!/bin/bash
# S750 runner — M1 first (mission order), then all remaining gold TFs.
# Per-TF git checkpoint (اندک اندک rule). NO EURUSD.
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 W1 MN1"
for TF in $TFS; do
  if [ -f "results/s750/$TF.json" ]; then
    echo "== $TF already done, skip =="
    continue
  fi
  echo "== running $TF =="
  python3 strategies/s750_laguerre_dwell.py "$TF" 2>&1 | tail -12
  if [ -f "results/s750/$TF.json" ]; then
    V=$(python3 -c "import json;print(json.load(open('results/s750/$TF.json')).get('verdict'))")
    S=$(python3 -c "import json;d=json.load(open('results/s750/$TF.json'));print(d.get('rqs2_score'))")
    git add "results/s750/$TF.json"
    git commit -m "S750 checkpoint $TF: $V rqs2=$S" -q
    git push origin main -q 2>/dev/null || { git pull --rebase origin main -q; git push origin main -q; }
    echo "== $TF committed: $V ($S) =="
  fi
done
echo "== S750 ALL DONE =="
