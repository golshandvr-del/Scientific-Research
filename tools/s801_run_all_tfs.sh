#!/usr/bin/env bash
# S801 MTF runner — explore ⇒ (اگر power_ok) judge ⇒ commit افزایشی پس از هر TF.
# ترتیب: بلندها اول (ارزان)، دقیقه‌ها بعد، M1 آخر (نیازمند .npy های S800).
set -u
cd /home/user/webapp
TFS="${1:-MN1 W1 D1 H12 H8 H6 H3 H2 H1 M30 M20 M15 M12 M10 M6 M5 M4 M3 M2 M1}"
LOG=results/_scan_S801/run_all.log
mkdir -p results/_scan_S801
for tf in $TFS; do
  echo "===== $tf  $(date -u +%FT%TZ) =====" | tee -a "$LOG"
  python3 strategies/s801_expansion_pullback.py --tf "$tf" --phase explore 2>&1 | tail -4 | tee -a "$LOG"
  if python3 -c "import json,sys; d=json.load(open('results/_scan_S801/${tf}_locked.json')); sys.exit(0 if d.get('power_ok') else 1)" 2>/dev/null; then
    python3 strategies/s801_expansion_pullback.py --tf "$tf" --phase judge 2>&1 | tail -3 | tee -a "$LOG"
  fi
  V=$(python3 -c "
import json,os
p='results/_scan_S801/${tf}_judge.json'
if os.path.exists(p):
    d=json.load(open(p)); print(f\"{d['verdict']} rqs2={d['score']:.1f}\")
else:
    l=json.load(open('results/_scan_S801/${tf}_locked.json'))
    print('POWER-LIMITED' if l.get('cfg') else 'UNPROVEN', 'power=%.1f'%l.get('power',0))
" 2>/dev/null)
  git add results/_scan_S801/${tf}_*.json 2>/dev/null
  git commit -qm "S801 checkpoint ${tf}: ${V}" 2>/dev/null && echo "committed: ${tf}: ${V}" | tee -a "$LOG"
done
echo "===== DONE $(date -u +%FT%TZ) =====" | tee -a "$LOG"
