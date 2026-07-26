# -*- coding: utf-8 -*-
"""
S329e — فیلترِ رژیمِ مولتی‌تایم‌فریم (H1) روی EURUSD M15 — آخرین تلاش برای G4
================================================================================
یافتهٔ S329d: گیتِ روندِ کلان روی *خودِ M15* (EMA150/200) پنجرهٔ سومِ زیانده را
  فقط تا حدی بهبود داد (WF3: -446 → -301/-174) اما G4 هنوز رد ماند. ریشه:
  EMAِ روی M15 در اصلاحاتِ موقتِ درونِ روندِ صعودیِ کلان «گول می‌خورد» و لحظه‌ای
  نزولی می‌شود ⇒ SHORTِ خطا در دلِ روندِ صعودیِ بزرگِ ۲۰۲۲–۲۰۲۴.

بهبودِ نهایی (قانونِ «همه چیز شناور است» + قانونِ بی‌نهایتِ بهبود):
  رژیم را از یک تایم‌فریمِ *بالاتر* (H1) بخوان — یعنی روندِ واقعاً کلان. هر کندلِ M15
  فقط از آخرین کندلِ H1 که **قطعاً بسته شده** استفاده می‌کند (بدون look-ahead:
  H1_slope با شرطِ ts_H1_close <= ts_M15_open، سپس یک‌قدم shift).
  شرطِ ورودِ SHORT: EMA(H1, htf_ema) نسبت به htf_lb کندلِ H1 قبل نزولی باشد.

اگر پس از این هم G4 پاس نشود، تمامِ مسیرهای بهبودِ منطقی (session/day, macro-M15,
  macro-HTF) آزموده شده‌اند ⇒ EURUSD M15 برای این لایه طبقِ «قانونِ مرگِ ابدی» DEAD،
  در حالی که XAUUSD M15 (S303) همچنان تنها زیستگاهِ زندهٔ لایه است.
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


def htf_downtrend_on_m15(df_m15, htf_ema=50, htf_lb=24):
    """آرایهٔ بولیِ هم‌طولِ df_m15: آیا روندِ H1 نزولی است؟ (بدون look-ahead)

    روش: EMA(close_H1, htf_ema) را می‌سازیم، شیبِ آن نسبت به htf_lb کندلِ H1 قبل
    (نزولی؟) را حساب می‌کنیم، سپس با merge_asof (backward) به هر کندلِ M15 آخرین
    مقدارِ H1 که زمانِ بازشدنش <= زمانِ کندلِ M15 است را می‌چسبانیم و یک قدم عقب
    (shift) می‌بریم تا فقط از کندلِ H1 قطعاً‌بسته استفاده شود.
    """
    df_h1 = TS.load_data('EURUSD_H1')
    ch = df_h1['close']
    ema_h1 = ind.ema(ch, htf_ema).to_numpy()
    ema_prev = pd.Series(ema_h1).shift(htf_lb).to_numpy()
    down = ema_h1 < ema_prev
    h1 = pd.DataFrame({'dt': pd.to_datetime(df_h1['dt'].values), 'down': down})
    # یک قدم shift: کندلِ H1[k] در پایانش (≈dt+1h) قطعی می‌شود؛ محافظه‌کارانه یک ردیف عقب‌تر.
    h1['down'] = h1['down'].shift(1).fillna(False)
    h1 = h1.sort_values('dt')
    m = pd.DataFrame({'dt': pd.to_datetime(df_m15['dt'].values)})
    m = m.sort_values('dt')
    merged = pd.merge_asof(m, h1, on='dt', direction='backward')
    merged['down'] = merged['down'].fillna(False)
    # بازگردانی به ترتیبِ اصلیِ df_m15
    merged = merged.set_index(m.index).sort_index()
    return merged['down'].to_numpy().astype(bool)


class HTFRegimeShort(MarketInertiaShortMTF):
    def __init__(self, htf_ema=50, htf_lb=24, **kw):
        super().__init__(**kw)
        self.htf_ema = htf_ema
        self.htf_lb = htf_lb
        self._htf_down = None

    def _precompute(self, df):
        c = df['close']
        h = df['high'].to_numpy(); cl = c.to_numpy()
        emaF = ind.ema(c, self.ef).to_numpy()
        emaS = ind.ema(c, self.es).to_numpy()
        adx = ind.adx(df, 14)
        adx = adx[0] if isinstance(adx, tuple) else adx
        adx = pd.Series(np.asarray(adx)).fillna(0).to_numpy()
        trend = adx > self.adx_hi
        prev_hh = pd.Series(h).rolling(self.lb).max().shift(1).to_numpy()
        rev_attempt = cl > prev_hh
        htf_down = htf_downtrend_on_m15(df, self.htf_ema, self.htf_lb)
        raw = trend & (emaF < emaS) & rev_attempt & htf_down
        self._sig = pd.Series(raw).shift(1).fillna(False).infer_objects(copy=False).to_numpy()


def main():
    asset = 'EURUSD'; tf = 'M15'
    df = TS.load_data(f'{asset}_{tf}')
    bad_hours = {8, 9, 12, 17}; bad_dow = {0, 1}

    print('===== S329e — EURUSD M15 + گیتِ رژیمِ H1 (HTF) =====')
    best = None; best_kw = None
    for htf_ema in (30, 50, 80):
        for htf_lb in (12, 24, 48):
            for adx_hi in (20, 22, 25):
                for rr in (1.0, 1.1, 1.2):
                    sl = 56.9; tp = round(sl * rr, 1)
                    strat = HTFRegimeShort(
                        htf_ema=htf_ema, htf_lb=htf_lb,
                        ef=13, es=34, adx_hi=adx_hi, lb=40,
                        sl_pip=sl, tp_pip=tp, max_hold=48,
                        bad_hours=bad_hours, bad_dow=bad_dow)
                    tr, _ = TS.simulate(df, strat, asset, warmup=2000)
                    r = RQS.compute_rqs(tr, asset); m = r['metrics']
                    if m.get('n_trades', 0) < 30:
                        continue
                    g = ''.join('✓' if v else '✗' for v in r['gates'].values())
                    tag = f"he{htf_ema} hlb{htf_lb} adx>{adx_hi} rr={rr}"
                    passed = all(r['gates'].values())
                    mark = '  <== ALL PASS' if passed else ''
                    print(f"  {tag:30s} | {r['verdict']:6s} RQS={r['rqs_score']:5.1f} "
                          f"n={m.get('n_trades',0):3d} WR={m.get('win_rate',0):4.1f}% "
                          f"PF={m.get('profit_factor',0):.2f} DD={m.get('max_dd_pct',0):.1f}% "
                          f"MCL={m.get('max_consec_losses',0)} p={m.get('p_value',1):.3f} {g}{mark}")
                    if best is None or r['rqs_score'] > best['rqs_score']:
                        best = r; best_kw = (htf_ema, htf_lb, adx_hi, rr)

    print('\n' + '=' * 70)
    if best is None:
        print('هیچ ترکیبی با n>=30 یافت نشد.'); return
    print('BEST:', RQS.format_report(f'htf{best_kw}', best))
    print('WF   :', best['metrics'].get('wf_nets'))
    print('halves:', best['metrics'].get('half_nets'))


if __name__ == '__main__':
    main()
