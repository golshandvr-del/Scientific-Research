/* ============================================================================
 * استراتژیِ ۳ — EURUSD Session-Open Drift (S73)
 * ----------------------------------------------------------------------------
 * ماشه: کندلِ ساعتِ ۰ UTC (بازشدنِ سشن) → drift صعودیِ آماری.
 * مغز:  SL=25pip، TP=45pip (پارامترهای رسمیِ S73).
 * قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر (XAUUSD+EURUSD)» است — نه WR.
 * ==========================================================================*/
(function () {
  'use strict';
  window.GoldEngine.registerStrategy({
    id: 'eurusd_session_drift',
    name: 'یورو — drift صعودیِ بازشدنِ سشن (S73، ۰ UTC)',
    asset: 'EURUSD',
    evaluate: function (ctx) {
      const last = ctx.candles[ctx.n - 1];
      const dt = new Date(last.time * 1000);
      if (dt.getUTCHours() !== ctx.EURUSD_ENTRY_HOUR) return null;
      const p = ctx.price, pip = ctx.pip;
      const sl = p - ctx.EURUSD_SL_PIP * pip;
      const tp = p + ctx.EURUSD_TP_PIP * pip;
      return {
        state: 'ENTRY', side: 'long',
        headline: 'ورود به خریدِ EURUSD — drift صعودیِ ساعتِ ۰ UTC (S73).',
        reasons: ['کشفِ آماریِ S73: بازدهِ مثبتِ پایدار در باز شدنِ سشن (۰ UTC).'],
        entry: ctx.r5(p), sl: ctx.r5(sl), tp: ctx.r5(tp),
        instruction: 'خریدِ EURUSD را ثبت کن، سپس «ثبت معامله» را بزن.',
      };
    },
  });
})();
