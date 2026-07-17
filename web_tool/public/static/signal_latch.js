// ============================================================================
// منطقِ خالصِ «قفلِ سیگنال» (Signal Latch) — منبعِ واحدِ حقیقت
// ----------------------------------------------------------------------------
// این ماژول عمداً «خالص/بدونِ وابستگی» است تا هم در مرورگر (app.js) و هم در
// ابزارِ تستِ کیفیت (Node — live_quality_harness.mjs) «دقیقاً یک منطق» اجرا شود.
// بنابراین آنچه harness تست می‌کند، همان چیزی است که کاربر در سایت می‌بیند.
//
// وضعیتِ قفل (latch) یک شیءِ ساده است که مصرف‌کننده خودش ذخیره/بازیابی می‌کند
// (مرورگر: localStorage ؛ Node: یک Map در حافظه). این تابع فقط «تبدیلِ خالص»
// انجام می‌دهد: (latchِ فعلی, decisionِ خام, آیا معامله باز است؟) → {تصمیمِ پایدار, latchِ جدید}.
//
// رفعِ باگِ User Note:
//   ۱) ثباتِ offer: تا وقتی سیگنالِ هم‌جهت برقرار است، entry/TP/SL «قفل» می‌ماند.
//   ۲) ضدِ flicker: نوسانِ گذرا زیرِ آستانه (تا NEUTRAL_TOLERANCE نمونه) سیگنال را نمی‌پراند.
// ============================================================================

const NEUTRAL_TOLERANCE = 3   // چند نمونهٔ متوالیِ non-ENTRY تا ابطالِ قفل

/**
 * @param {object|null} latch  وضعیتِ قفلِ فعلی (یا null)
 * @param {object} raw         RouterDecisionِ خامِ سرور
 * @param {boolean} hasTrade   آیا کاربر معاملهٔ ثبت‌شده دارد؟
 * @param {number} now         Date.now() (تزریق‌پذیر برای تست)
 * @returns {{decision: object, latch: object|null}}
 */
function computeLatched(latch, raw, hasTrade, now) {
  now = now || Date.now()

  // معاملهٔ ثبت‌شده → قفل بی‌معناست (MANAGE فرمان است)
  if (hasTrade) return { decision: raw, latch: null }

  // --- سرور ENTRY می‌دهد ---
  if (raw.state === 'ENTRY') {
    if (latch && latch.direction === raw.direction) {
      // همان جهت → offerِ قفل‌شده را حفظ کن؛ فقط متادیتای زنده به‌روز شود.
      const nl = { ...latch, neutralCount: 0, lastSeen: now, probability: raw.probability }
      return {
        latch: nl,
        decision: { ...raw, entry: latch.entry, tp: latch.tp, sl: latch.sl,
          direction: latch.direction, sizing: latch.sizing || raw.sizing,
          tpPlan: latch.tpPlan || raw.tpPlan, slPlan: latch.slPlan || raw.slPlan,
          rr: latch.rr || raw.rr, _latched: true, _latchedAt: latch.createdAt },
      }
    }
    // قفل تازه (نداشتیم یا جهت عوض شد)
    const fresh = {
      direction: raw.direction, entry: raw.entry, tp: raw.tp, sl: raw.sl,
      rr: raw.rr, probability: raw.probability,
      sizing: raw.sizing, tpPlan: raw.tpPlan, slPlan: raw.slPlan,
      createdAt: now, lastSeen: now, neutralCount: 0,
    }
    return { latch: fresh, decision: { ...raw, _latched: true, _latchedAt: fresh.createdAt } }
  }

  // --- سرور ENTRY نمی‌دهد ولی قفل داریم ---
  if (latch) {
    const nc = (latch.neutralCount || 0) + 1
    if (nc < NEUTRAL_TOLERANCE) {
      const nl = { ...latch, neutralCount: nc }
      return {
        latch: nl,
        decision: {
          state: 'ENTRY', regime: raw.regime,
          headline: `ورود ${latch.direction === 'LONG' ? 'خرید (LONG)' : 'فروش (SHORT)'} — سیگنالِ پایدار`,
          reason: `این سیگنالِ ورود «قفل» شده تا با نوسانِ کوچکِ قیمت جابه‌جا نشود. ` +
            `شاخص‌ها لحظه‌ای کمی زیرِ آستانه‌اند (${nc}/${NEUTRAL_TOLERANCE})، اما پیشنهادِ اولیه پابرجاست.`,
          direction: latch.direction, entry: latch.entry, tp: latch.tp, sl: latch.sl,
          rr: latch.rr, probability: latch.probability,
          sizing: latch.sizing, tpPlan: latch.tpPlan, slPlan: latch.slPlan,
          indicators: raw.indicators, _latched: true, _latchedAt: latch.createdAt, _fading: true,
        },
      }
    }
    // آستانه رد شد → قفل باطل
    return { decision: raw, latch: null }
  }

  // نه قفل، نه سیگنال
  return { decision: raw, latch: null }
}

// پشتیبانی از هر دو محیط: ماژولِ ES (Node/harness) و اسکریپتِ سراسری (مرورگر)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { computeLatched, NEUTRAL_TOLERANCE }
}
if (typeof window !== 'undefined') {
  window.SignalLatch = { computeLatched, NEUTRAL_TOLERANCE }
}
