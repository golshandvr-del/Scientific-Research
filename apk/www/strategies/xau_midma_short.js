/* ============================================================================
 * استراتژیِ ۲ — XAUUSD SHORT بر پایهٔ قطعِ نزولیِ میانهٔ سه‌MA (s118)
 * ----------------------------------------------------------------------------
 * ماشه: قیمت میانهٔ سه‌MA (mid_ma3) را رو به پایین قطع کند.
 * مغز:  SHORT_PARAMS (sl=70pip, tp=800pip, trail=6pip) — «بگذار بردها بدوند».
 * قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر (XAUUSD+EURUSD)» است — نه WR.
 * ==========================================================================*/
(function () {
  'use strict';
  window.GoldEngine.registerStrategy({
    id: 'xau_midma_short',
    name: 'طلا — قطعِ نزولیِ میانهٔ سه‌MA (SHORT، s118)',
    asset: 'XAUUSD',
    evaluate: function (ctx) {
      if (!ctx.crossDn) return null;
      const p = ctx.price, pip = ctx.pip, prm = ctx.SHORT_PARAMS;
      const sl = p + prm.sl_pip * pip;
      const tp = p - prm.tp_pip * pip;
      return {
        state: 'ENTRY', side: 'short',
        headline: 'ورود به معاملهٔ فروش (SHORT) — کشفِ آغازِ روندِ نزولی.',
        reasons: [
          `قیمت (${p.toFixed(2)}) میانهٔ سه‌MA (${ctx.midNow.toFixed(2)}) را رو به پایین شکست.`,
          'منطقِ برندهٔ s118 «بگذار بردها بدوند» (TP=800pip، trail=6pip).',
        ],
        entry: ctx.r2(p), sl: ctx.r2(sl), tp: ctx.r2(tp),
        rr: Math.round((prm.tp_pip / prm.sl_pip) * 100) / 100,
        instruction: 'معاملهٔ فروش را در حسابِ دمو باز و ثبت کن، سپس روی «ثبت معامله» بزن.',
      };
    },
  });
})();
