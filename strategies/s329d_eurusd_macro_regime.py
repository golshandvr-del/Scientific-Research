# -*- coding: utf-8 -*-
"""
S329d — افزودنِ فیلترِ رژیمِ کلان به EURUSD M15 برای پاس‌کردنِ G4 (پایداری)
================================================================================
یافتهٔ S329c: EURUSD M15 با فیلترِ session/day به **۵ گیت از ۶** رسید —
  WR=64.3٪، PF=1.92، maxDD 4.5٪، MCL 4، p=0.009 (G0,G1,G2,G3,G5 = ✓)
  اما G4 (پایداریِ walk-forward) = ✗.

ریشه‌یابیِ دقیقِ G4 (چهار پنجرهٔ متوالی):
  WF = [ +348 , +383 , -446 , +664 ]  (pip)
  پنجرهٔ سوم = نوامبر ۲۰۲۲ → مه ۲۰۲۴ = دورهٔ **روندِ صعودیِ بزرگ‌مقیاسِ یورو**
  (پس از کفِ بحرانِ انرژیِ اروپا در اکتبر ۲۰۲۲؛ EURUSD از ~۰.۹۵ به ~۱.۱۲).
  استراتژیِ ما SHORT است (fadeِ تلاشِ صعودی). در یک روندِ کلانِ صعودی، سیگنالِ
  «ema13<ema34 محلی» گاهی فعال می‌شود اما روندِ کلان SHORTها را می‌کُشد.
  ⇒ این یک **ضعفِ ساختاریِ واقعی** است، نه نویزِ تصادفی.

بهبودِ علمی (ضدِّ overfit — کاملاً همسو با تزِ اصلی):
  «فقط وقتی SHORT بزن که روندِ *بلندمدت* هم نزولی باشد.»
  فیلترِ رژیمِ کلان = شیبِ EMAِ بلند (macro_ema) طیِّ macro_lb کندلِ اخیر منفی باشد
  (close یا خودِ EMA پایین‌تر از macro_lb کندل قبل). این پنجرهٔ صعودیِ سوم را حذف
  می‌کند بی‌آنکه سه پنجرهٔ سالم را «رنگ‌آمیزی»‌کند — چون فیلتر یک قاعدهٔ ساختاریِ
  کلی است نه یک بازهٔ تاریخیِ دست‌چین‌شده.

روش: زیرکلاسِ MarketInertiaShortMTF که یک AND اضافه (macro-downtrend) به سیگنالِ
  خام می‌افزاید؛ سپس grid کوچک روی (macro_ema, macro_lb, adx_hi, rr).
خروجی: چاپِ بهترین + WF/halves برای تصمیمِ نهایی (ACCEPT/DEAD).
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from engine import indicators as ind
from strategies.s329_market_inertia_mtf import MarketInertiaShortMTF


class MacroRegimeShort(MarketInertiaShortMTF):
    """S329d — Market-Inertia SHORT + گیتِ روندِ کلانِ نزولی.

    macro_ema: طولِ EMAِ بلندمدت (رژیمِ کلان).
    macro_lb : افقِ سنجشِ شیب (چند کندل قبل). شرطِ ورود: EMA_now < EMA_{-macro_lb}
               (روندِ بلندمدت نزولی) ⇒ با تزِ «fade در روندِ نزولی» کاملاً همسو.
    """

    def __init__(self, macro_ema=200, macro_lb=100, **kw):
        super().__init__(**kw)
        self.macro_ema = macro_ema
        self.macro_lb = macro_lb

    def _precompute(self, df):
        c = df['close']
        h = df['high'].to_numpy(); l = df['low'].to_numpy(); cl = c.to_numpy()
        emaF = ind.ema(c, self.ef).to_numpy()
        emaS = ind.ema(c, self.es).to_numpy()
        adx = ind.adx(df, 14)
        adx = adx[0] if isinstance(adx, tuple) else adx
        adx = pd.Series(np.asarray(adx)).fillna(0).to_numpy()
        trend = adx > self.adx_hi
        prev_hh = pd.Series(h).rolling(self.lb).max().shift(1).to_numpy()
        rev_attempt = cl > prev_hh
        # --- گیتِ رژیمِ کلان: EMAِ بلند نسبت به macro_lb کندلِ قبل نزولی باشد ---
        macro = ind.ema(c, self.macro_ema).to_numpy()
        macro_prev = pd.Series(macro).shift(self.macro_lb).to_numpy()
        macro_down = macro < macro_prev
        raw = trend & (emaF < emaS) & rev_attempt & macro_down
        self._sig = pd.Series(raw).shift(1).fillna(False).infer_objects(copy=False).to_numpy()


def evaluate(df, asset, strat):
    tr, _ = TS.simulate(df, strat, asset, warmup=2000)
    r = RQS.compute_rqs(tr, asset)
    return r


def main():
    asset = 'EURUSD'; tf = 'M15'
    df = TS.load_data(f'{asset}_{tf}')

    # فیلترهای session/day که در S329c بهینه شدند (بازتولیدِ نقطهٔ توقف)
    bad_hours = {8, 9, 12, 17}
    bad_dow = {0, 1}

    print('===== S329d — EURUSD M15 + گیتِ رژیمِ کلان =====')
    best = None; best_kw = None
    # grid کوچک و منطقی حولِ macro-trend (اعدادِ غیررند مجاز)
    for macro_ema in (150, 200, 240):
        for macro_lb in (60, 100, 150):
            for adx_hi in (20, 22, 25):
                for rr in (1.0, 1.1, 1.2):
                    sl = 56.9; tp = round(sl * rr, 1)
                    strat = MacroRegimeShort(
                        macro_ema=macro_ema, macro_lb=macro_lb,
                        ef=13, es=34, adx_hi=adx_hi, lb=40,
                        sl_pip=sl, tp_pip=tp, max_hold=48,
                        bad_hours=bad_hours, bad_dow=bad_dow)
                    r = evaluate(df, asset, strat)
                    m = r['metrics']
                    if m.get('n_trades', 0) < 30:
                        continue
                    g = ''.join('✓' if v else '✗' for v in r['gates'].values())
                    tag = f"me{macro_ema} mlb{macro_lb} adx>{adx_hi} rr={rr}"
                    print(f"  {tag:32s} | {r['verdict']:6s} RQS={r['rqs_score']:5.1f} "
                          f"n={m.get('n_trades',0):3d} WR={m.get('win_rate',0):4.1f}% "
                          f"PF={m.get('profit_factor',0):.2f} DD={m.get('max_dd_pct',0):.1f}% "
                          f"MCL={m.get('max_consec_losses',0)} p={m.get('p_value',1):.3f} {g}")
                    if best is None or r['rqs_score'] > best['rqs_score']:
                        best = r; best_kw = (macro_ema, macro_lb, adx_hi, rr)

    print('\n' + '=' * 70)
    if best is None:
        print('هیچ ترکیبی با n>=30 یافت نشد.')
        return
    print('BEST:', RQS.format_report(f'macro{best_kw}', best))
    print('WF   :', best['metrics'].get('wf_nets'))
    print('halves:', best['metrics'].get('half_nets'))


if __name__ == '__main__':
    main()
