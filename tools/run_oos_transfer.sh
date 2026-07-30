#!/bin/bash
# =============================================================================
#  درایورِ آزمونِ انتقالِ خارج‌ازنمونه S346  —  چند-کارتی، مقاومِ ریست
# =============================================================================
#  چرا این فایل در مخزن است و نه در /tmp:
#  نسخهٔ قبلیِ این درایور در /tmp نوشته شد و ریستِ سندباکس آن را از بین برد،
#  درحالی‌که کارِ نیمه‌تمامش هم از دست رفت. اینجا:
#    ۱) خودِ درایور نسخه‌بندی می‌شود
#    ۲) پس از هر کارت، نتیجه **بلافاصله** commit و push می‌شود (قانونِ «اندک اندک»)
#       ⇒ ریست حداکثر **یک کارت** را می‌سوزاند، نه کلِ اجرا را
#    ۳) کارتی که فایلِ نتیجه‌اش موجود است **رد می‌شود** ⇒ ادامهٔ خودکار
#
#  ترتیبِ کارت‌ها **پیش‌ثبت‌شده** است (results/S346_PREREGISTRATION_OOS.md)
#  و عوض نمی‌شود، تا «اول کارت‌های موفق» گزارش نشوند.
#
#  اجرای متوالی و نه موازی: فقط ۶۱۰MB رم آزاد و ۲ هسته داریم.
# =============================================================================
set -u
cd /home/user/webapp || exit 1

CARDS="XAUUSD-H1 XAUUSD-W1 XAUUSD-M30 EURUSD-M30 XAUUSD-M15 EURUSD-M15 XAUUSD-M5 EURUSD-M5 EURUSD-M1"
NPERM="${1:-200}"
LOGDIR="results/_scan_S346"
mkdir -p "$LOGDIR"

for CARD in $CARDS; do
  OUTJSON="$LOGDIR/${CARD}_oos.json"
  if [ -f "$OUTJSON" ]; then
    echo "##### SKIP $CARD (result already present) #####"
    continue
  fi

  echo "##### START $CARD nperm=$NPERM $(date -u +%H:%M:%S) #####"
  python -u -m strategies.s346_oos_transfer "$CARD" "$NPERM" \
        > "$LOGDIR/oos_${CARD}.log" 2>&1
  RC=$?
  echo "##### DONE  $CARD rc=$RC $(date -u +%H:%M:%S) #####"
  grep -E "verdict|VERDICT|TRANSFER|INSUFFICIENT|OBSERVED|lift=" "$LOGDIR/oos_${CARD}.log" | tail -8

  # ---- چک‌پوینتِ فوری: نتیجهٔ همین کارت، پیش از رفتن به کارتِ بعد ----
  git add -f "$OUTJSON" "$LOGDIR/oos_${CARD}.log" 2>/dev/null
  git commit -q -m "S346 OOS transfer: ${CARD} result (per-card checkpoint, nperm=${NPERM})" 2>/dev/null \
    && git push -q origin main 2>/dev/null \
    && echo "##### PUSHED $CARD #####" \
    || echo "##### PUSH-SKIPPED/FAILED $CARD #####"
done

echo "ALL_CARDS_COMPLETE $(date -u +%H:%M:%S)"
