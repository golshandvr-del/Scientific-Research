#!/bin/bash
# S753 runner — M1 first, then all remaining gold TFs. Per-TF git checkpoint. NO EURUSD.
cd /home/user/webapp
TFS="M1 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1"
for TF in $TFS; do
  if [ -f "results/s753/$TF.json" ]; then
    echo "== $TF already done, skip =="
    continue
  fi
  echo "== running $TF =="
  python3 strategies/s753_chop_birth.py "$TF" 2>&1 | tail -8
  if [ -f "results/s753/$TF.json" ]; then
    V=$(python3 -c "import json;print(json.load(open('results/s753/$TF.json')).get('verdict'))")
    S=$(python3 -c "import json;print(json.load(open('results/s753/$TF.json')).get('rqs2_score'))")
    git add "results/s753/$TF.json"
    git commit -m "S753 checkpoint $TF: $V rqs2=$S" -q
    git push origin main -q 2>/dev/null || { git pull --rebase origin main -q; git push origin main -q 2>/dev/null; }
    echo "== $TF committed: $V ($S) =="
  fi
done
echo "== S753 ALL DONE =="
