/* ============================================================================
 * استراتژیِ ۱ — XAUUSD LONG بر پایهٔ قطعِ صعودیِ میانهٔ سه‌MA (S67/S14)
 * ----------------------------------------------------------------------------
 * ماشه: قیمت میانهٔ سه‌MA (mid_ma3) را رو به بالا قطع کند.
 * مغز:  LONG_PARAMS (sl=60pip, tp=400pip) — «بگذار بردها بدوند».
 * این فایل، ماژولِ مستقل و افزونه‌ای است؛ افزودنِ استراتژیِ مشابه = کپی و تغییرِ
 * evaluate. هیچ نیازی به دستکاریِ engine.js نیست.
 * قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر (XAUUSD+EURUSD)» است — نه WR.
 * ==========================================================================*/
(function () {
  'use strict';
  window.GoldEngine.registerStrategy({
    id: 'xau_midma_long',
    name: 'طلا — قطعِ صعودیِ میانهٔ سه‌MA (LONG، S67/S14)',
    asset: 'XAUUSD',
    evaluate: function (ctx) {
      if (!ctx.crossUp) return null;
      const p = ctx.price, pip = ctx.pip, prm = ctx.LONG_PARAMS;
      const sl = p - prm.sl_pip * pip;
      const tp = p + prm.tp_pip * pip;
      return {
        state: 'ENTRY', side: 'long',
        headline: 'ورود به معاملهٔ خرید (LONG) — کشفِ آغازِ روندِ صعودی.',
        reasons: [
          `قیمت (${p.toFixed(2)}) میانهٔ سه‌MA (${ctx.midNow.toFixed(2)}) را رو به بالا شکست.`,
          `EMA50=${ctx.e50.toFixed(2)}، SMA200=${ctx.e200.toFixed(2)} — چیدمانِ صعودی.`,
          'منطقِ برندهٔ S67/S14 «بگذار بردها بدوند».',
        ],
        entry: ctx.r2(p), sl: ctx.r2(sl), tp: ctx.r2(tp),
        rr: Math.round((prm.tp_pip / prm.sl_pip) * 100) / 100,
        instruction: 'معاملهٔ خرید را در حسابِ دمو باز و ثبت کن، سپس روی «ثبت معامله» بزن تا واردِ مدیریت شویم.',
      };
    },
  });
})();
