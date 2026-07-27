// ============================================================================
// منطقِ خالصِ «قفلِ سیگنال + صفِ تثبیت» (Signal Latch v2) — منبعِ واحدِ حقیقت
// ----------------------------------------------------------------------------
// این ماژول عمداً «خالص/بدونِ وابستگی» است تا هم در مرورگر (app.js) و هم در
// ابزارِ تستِ کیفیت (Node) «دقیقاً یک منطق» اجرا شود. آنچه تست می‌شود همان چیزی
// است که کاربر در سایت می‌بیند.
//
// ============================================================================
// 🐛 باگ‌هایی که این نسخه (v2) رفع می‌کند (User Note — سیگنالِ متناقضِ M15):
// ----------------------------------------------------------------------------
//  B1) «چند ثانیه خرید، بعد از رفرش فروش»:
//      نسخهٔ قبلی به‌محضِ ENTRYِ خام، *فوراً* آن را قفل و نمایش می‌داد و با هر
//      تغییرِ جهت هم فوراً flip می‌کرد. راه‌حل: «صفِ تثبیت» (CONFIRMING) — یک
//      سیگنالِ ورودِ تازه تا وقتی برای CONFIRM_MS میلی‌ثانیه *و* حداقل
//      CONFIRM_SAMPLES نمونه در «همان جهت» پایدار نماند، به کاربر ENTRY نشان
//      داده نمی‌شود. این دقیقاً ایدهٔ «سیگنالِ تثبیت‌شده»ی کاربر است.
//
//  B2) «برای شورت ننوشت مربوط به کدام استراتژی است / ظاهرش شبیهِ سیگنال‌های جدید نبود»:
//      نسخهٔ قبلی sourceLayer را در latch ذخیره نمی‌کرد؛ وقتی سرور NEUTRAL می‌داد،
//      latchِ قدیمی را بدونِ نامِ استراتژی به‌عنوان «ENTRYِ پایدار» نشان می‌داد.
//      راه‌حل: (۱) latch اکنون sourceLayer/confirmations/indicators را حمل می‌کند؛
//      (۲) نسخهٔ اسکیمای latch بالا رفت ⇒ هر latchِ قدیمیِ ذخیره‌شده در localStorage
//      خودکار باطل می‌شود (بقایای استراتژی‌های حذف‌شده پاک می‌شوند).
//
//  B3) «ابطالِ نمونه‌محور به‌جای زمان‌محور»:
//      NEUTRAL_TOLERANCE تعدادِ poll را می‌شمرد؛ با رفرشِ دستیِ کاربر بی‌معنا می‌شد.
//      راه‌حل: ابطال بر پایهٔ زمانِ واقعی (STALE_MS) + ابطالِ فوری اگر سرور صریحاً
//      جهتِ مخالف را ENTRY کند.
// ============================================================================

// نسخهٔ اسکیمای latch — با تغییرِ آن، همهٔ latchهای ذخیره‌شدهٔ قدیمی باطل می‌شوند.
const LATCH_SCHEMA = 2

// صفِ تثبیت: یک ENTRYِ تازه باید حداقل این‌قدر «زمان» و «نمونه» در همان جهت
// پایدار بماند تا به کاربر ENTRY نشان داده شود. قبل از آن APPROACHING (در حالِ تثبیت).
const CONFIRM_MS = 6000        // حداقل ۶ ثانیه پایداریِ جهت
const CONFIRM_SAMPLES = 2      // حداقل ۲ نمونهٔ متوالیِ هم‌جهت

// پایداریِ offerِ قفل‌شده در برابر نوسانِ گذرا (ضدِ flicker) — زمان‌محور.
const STALE_MS = 90000         // اگر بیش از ۹۰ ثانیه سیگنالِ هم‌جهت نیامد، قفل باطل

// سازگاریِ عقب‌رو: بعضی مصرف‌کننده‌ها هنوز NEUTRAL_TOLERANCE را می‌خوانند.
const NEUTRAL_TOLERANCE = 3

function freshPending(raw, now) {
  return {
    schema: LATCH_SCHEMA,
    phase: 'confirming',          // 'confirming' → 'locked'
    direction: raw.direction,
    entry: raw.entry, tp: raw.tp, sl: raw.sl, rr: raw.rr,
    probability: raw.probability,
    sizing: raw.sizing, tpPlan: raw.tpPlan, slPlan: raw.slPlan,
    sourceLayer: raw.sourceLayer,           // 🔑 نامِ استراتژی حفظ می‌شود (رفعِ B2)
    confirmations: raw.confirmations,
    firstSeen: now, lastSeen: now, samples: 1,
  }
}

/**
 * تبدیلِ خالص: (latchِ فعلی, decisionِ خامِ سرور, آیا معامله باز است؟, now)
 *   → {decision: تصمیمِ نهاییِ نمایش, latch: latchِ جدید}
 *
 * @param {object|null} latch
 * @param {object} raw
 * @param {boolean} hasTrade
 * @param {number} now
 */
function computeLatched(latch, raw, hasTrade, now) {
  now = now || Date.now()

  // معاملهٔ ثبت‌شده → قفل بی‌معناست؛ MANAGE فرمان است، خام را بده.
  if (hasTrade) return { decision: raw, latch: null }

  // 🧹 رفعِ B2: latchِ با اسکیمای قدیمی (بازماندهٔ استراتژی‌های حذف‌شده) را دور بریز.
  if (latch && latch.schema !== LATCH_SCHEMA) latch = null

  const serverEntry = raw && raw.state === 'ENTRY' && (raw.direction === 'LONG' || raw.direction === 'SHORT')

  // ---------------------------------------------------------------------------
  // حالت A: سرور ENTRY می‌دهد
  // ---------------------------------------------------------------------------
  if (serverEntry) {
    // A1) قفل/صفی داریم و هم‌جهت است → پیشرفتِ تثبیت یا حفظِ قفل.
    if (latch && latch.direction === raw.direction) {
      const nl = { ...latch, lastSeen: now, samples: (latch.samples || 1) + 1, probability: raw.probability }
      const enoughTime = (now - latch.firstSeen) >= CONFIRM_MS
      const enoughSamples = nl.samples >= CONFIRM_SAMPLES
      if (latch.phase === 'locked' || (enoughTime && enoughSamples)) {
        // تثبیت شد (یا از قبل قفل بود) → ENTRYِ پایدار با offerِ *قفل‌شدهٔ اولیه*.
        nl.phase = 'locked'
        return {
          latch: nl,
          decision: {
            ...raw,
            entry: latch.entry, tp: latch.tp, sl: latch.sl, direction: latch.direction,
            sizing: latch.sizing || raw.sizing, tpPlan: latch.tpPlan || raw.tpPlan,
            slPlan: latch.slPlan || raw.slPlan, rr: latch.rr || raw.rr,
            sourceLayer: latch.sourceLayer || raw.sourceLayer,   // 🔑 نامِ استراتژی
            _latched: true, _latchedAt: latch.firstSeen,
          },
        }
      }
      // هنوز در حالِ تثبیت → به کاربر «در حالِ تثبیتِ سیگنال» نشان بده (نه ENTRYِ قطعی).
      return { latch: nl, decision: pendingView(nl, raw, now) }
    }

    // A2) قفلی نداریم، یا جهت عوض شد → صفِ تثبیتِ *تازه* (فوراً flip نمی‌کنیم — رفعِ B1).
    const pend = freshPending(raw, now)
    return { latch: pend, decision: pendingView(pend, raw, now) }
  }

  // ---------------------------------------------------------------------------
  // حالت B: سرور ENTRY نمی‌دهد (NEUTRAL/APPROACHING) ولی latch داریم
  // ---------------------------------------------------------------------------
  if (latch) {
    // اگر سرور صریحاً جهتِ *مخالفِ* قفل را (حتی به‌صورتِ APPROACHING) نشان دهد،
    // نگه‌داشتنِ قفلِ قبلی خطرناک است → فوراً باطل کن (ضدِ گمراهیِ کاربر).
    const serverOppApproach = raw && raw.direction && raw.direction !== '—' &&
      raw.direction !== latch.direction
    if (serverOppApproach) return { decision: raw, latch: null }

    // ابطالِ زمان‌محور (رفعِ B3): اگر خیلی وقت است سیگنالِ هم‌جهت نیامده، قفل باطل.
    if ((now - latch.lastSeen) > STALE_MS) return { decision: raw, latch: null }

    // اگر هنوز در حالِ تثبیت بود و ENTRYِ سرور قطع شد → صف را نگه نمی‌داریم
    // (سیگنالِ ناپایدار نباید به ENTRY برسد). خام را نشان بده، صف را دور بریز.
    if (latch.phase !== 'locked') return { decision: raw, latch: null }

    // قفلِ *تثبیت‌شده* در برابرِ نوسانِ گذرا پایدار می‌ماند (تا STALE_MS) — ضدِ flicker.
    return {
      latch,
      decision: {
        state: 'ENTRY', regime: raw.regime,
        headline: `ورود ${latch.direction === 'LONG' ? 'خرید (LONG)' : 'فروش (SHORT)'} — سیگنالِ پایدار`,
        reason: `این سیگنالِ ورود «قفل» شده تا با نوسانِ کوچکِ قیمت جابه‌جا نشود. ` +
          `شاخص‌ها لحظه‌ای کمی زیرِ آستانه‌اند اما پیشنهادِ اولیه (از ${latch.sourceLayer?.code || 'همان لایه'}) پابرجاست.`,
        direction: latch.direction, entry: latch.entry, tp: latch.tp, sl: latch.sl,
        rr: latch.rr, probability: latch.probability,
        sizing: latch.sizing, tpPlan: latch.tpPlan, slPlan: latch.slPlan,
        sourceLayer: latch.sourceLayer,        // 🔑 نامِ استراتژی حفظ می‌شود (رفعِ B2)
        confirmations: latch.confirmations,
        indicators: raw.indicators, _latched: true, _latchedAt: latch.firstSeen, _fading: true,
      },
    }
  }

  // نه قفل، نه سیگنال
  return { decision: raw, latch: null }
}

// نمایشِ حالتِ «در حالِ تثبیت» — به‌شکلِ APPROACHING تا کاربر بداند هنوز قطعی نیست.
function pendingView(pend, raw, now) {
  const remainMs = Math.max(0, CONFIRM_MS - (now - pend.firstSeen))
  const remainSec = Math.ceil(remainMs / 1000)
  const dirFa = pend.direction === 'LONG' ? 'خرید (LONG)' : 'فروش (SHORT)'
  return {
    state: 'APPROACHING', regime: raw.regime,
    headline: `در حالِ تثبیتِ سیگنالِ ${dirFa} — ${raw.sourceLayer?.code || ''}`.trim(),
    reason: `یک سیگنالِ ورودِ ${dirFa} شکل گرفت، اما پیش از نمایش به‌عنوانِ «ورود»، باید ` +
      `چند ثانیه پایدار بماند تا نوسانِ لحظه‌ایِ قیمت شما را گمراه نکند. ` +
      (remainSec > 0 ? `تثبیت تا حدودِ ${remainSec} ثانیهٔ دیگر…` : `در حالِ تثبیتِ نهایی…`),
    approachReason: 'پایداریِ جهتِ سیگنال (ضدِ سیگنالِ متناقضِ زودگذر)',
    direction: pend.direction,
    sourceLayer: raw.sourceLayer,              // 🔑 نامِ استراتژی حتی در مرحلهٔ تثبیت
    confirmations: raw.confirmations,
    indicators: raw.indicators,
    _confirming: true, _confirmRemainSec: remainSec,
  }
}

// پشتیبانی از هر دو محیط (مرورگر: window ؛ Node/harness: export).
if (typeof window !== 'undefined') {
  window.SignalLatch = { computeLatched, NEUTRAL_TOLERANCE, LATCH_SCHEMA, CONFIRM_MS, CONFIRM_SAMPLES, STALE_MS }
}

export { computeLatched, NEUTRAL_TOLERANCE, LATCH_SCHEMA, CONFIRM_MS, CONFIRM_SAMPLES, STALE_MS }
