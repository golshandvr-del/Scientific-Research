#!/bin/bash
# =============================================================================
#  درایورِ MTF برای لایهٔ S347 (گروههٔ رأی‌گیری) — مقاومِ ریست
# =============================================================================
#  ترتیبِ کارت‌ها **پیش‌ثبت‌شده** در results/S347_PREREGISTRATION_ENSEMBLE.md
#  و عوض نمی‌شود. هیچ کارتی حذف نمی‌شود (قانونِ MTF).
#  پس از هر کارت: commit + push فوری ⇒ ریست حداکثر یک کارت را می‌سوزاند.
#  کارتی که فایلِ نتیجه‌اش موجود است رد می‌شود ⇒ ادامهٔ خودکار.
# =============================================================================
set -u
cd /home/user/webapp || exit 1

CARDS="XAUUSD-W1 XAUUSD-H4 XAUUSD-H1 XAUUSD-M30 XAUUSD-M15 XAUUSD-M5 EURUSD-M30 EURUSD-M15 EURUSD-M5 EURUSD-M1"
NPERM="${1:-300}"
LOGDIR="results/_scan_S346"
mkdir -p "$LOGDIR"

for CARD in $CARDS; do
  OUTJSON="$LOGDIR/${CARD}_ens.json"
  if [ -f "$OUTJSON" ]; then
    echo "##### SKIP $CARD (already present) #####"; continue
  fi
  echo "##### START $CARD nperm=$NPERM $(date -u +%H:%M:%S) #####"
  python -u -m strategies.s347_ensemble "$CARD" "$NPERM" \
        > "$LOGDIR/ens_${CARD}.log" 2>&1
  echo "##### DONE  $CARD rc=$? $(date -u +%H:%M:%S) #####"
  grep -E "^  \[|luck bound|votes:|filter gate" "$LOGDIR/ens_${CARD}.log" | tail -14

  git add -f "$OUTJSON" "$LOGDIR/ens_${CARD}.log" 2>/dev/null
  git commit -q -m "S347 ensemble: ${CARD} MTF result (per-card checkpoint, nperm=${NPERM})" 2>/dev/null \
    && git push -q origin main 2>/dev/null \
    && echo "##### PUSHED $CARD #####" || echo "##### PUSH-SKIPPED $CARD #####"
done
echo "ENSEMBLE_MTF_COMPLETE $(date -u +%H:%M:%S)"
