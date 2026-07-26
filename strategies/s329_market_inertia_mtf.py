# -*- coding: utf-8 -*-
"""
S329 — گسترشِ مولتی‌تایم‌فریمِ لایهٔ Market-Inertia SHORT (منشأ S173 → احیای M15 = S303)
================================================================================
انگیزه (قانونِ اولِ پروژه — مولتی‌تایم‌فریمِ اجباری + اشتباهِ رایجِ ۵):
  لایهٔ Market-Inertia SHORT فقط روی XAUUSD **M15** احیا شده بود (S303, RQS 87.6).
  طبقِ قانونِ اول باید روی **همهٔ تایم‌فریم‌ها** (M5/M30/H1/H4) و **هر دو ارز**
  (XAUUSD + EURUSD) مستقل آزموده شود؛ اگر در چند TF زنده شد، منطقِ همهٔ TFهای
  تأییدشده باید در سایت اعمال گردد.

اصلِ علمیِ کلیدی (اشتباهِ رایجِ ۶ و ۷ — و قانونِ «همه چیز شناور است»):
  SL/TP نباید ثابت و رند برای همهٔ TFها باشد. یک کندلِ H4 حرکتی ~۳.۶× بزرگ‌تر از
  M5 دارد (medianATR: M5=21.8pip … H4=78.8pip). پس SL/TP را **به‌صورتِ مضربی از
  ATRِ همان TF** تعریف می‌کنیم (volatility-scaled)، نه عددِ ثابت. در S303/M15
  نسبتِ برندهٔ SL=250pip ≈ 9.5×medianATR بود؛ حولِ این نسبت grid می‌زنیم.

  RR در S303 متقارن (۱:۱) بود چون TP نزدیک ⇒ توهمِ WR (G1 رد). این را حفظ می‌کنیم
  اما اجازه می‌دهیم grid کمی حولِ ۱:۱ (۰.۹ تا ۱.۲) بگردد تا هر TF بهینهٔ خود را
  بیابد — نه عددِ رندِ تحمیلی.

روش: برای هر (asset, TF) یک grid روی (sl_mult × ATR, rr) + فیلترهای S303 (ساعت بد،
  سه‌شنبه، ADX) می‌زنیم و RQS+ را با موتورِ رویداد-محور می‌سنجیم. بهترین ترکیب که
  هر ۶ گیت را پاس کند گزارش می‌شود.

خروجی: results/_s329_mtf_grid.json  (برای بازتولید و سند)
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from engine import indicators as ind


class MarketInertiaShortMTF:
    """نسخهٔ عمومیِ Market-Inertia SHORT با SL/TP بر حسبِ *پیپِ مطلق* (از grid) +
    فیلترهای سشن/روز/ADX. منطقِ سیگنال دقیقاً همان S173/S303 است.
    """
    BAD_HOURS = frozenset({3, 5, 12, 15, 16, 17, 18})
    BAD_DOW = frozenset({1})   # سه‌شنبه

    def __init__(self, ef=20, es=50, adx_hi=28, lb=20,
                 sl_pip=250.0, tp_pip=250.0, max_hold=48,
                 bad_hours=None, bad_dow=None):
        self.ef = ef; self.es = es; self.adx_hi = adx_hi; self.lb = lb
        self.sl_pip = sl_pip; self.tp_pip = tp_pip; self.max_hold = max_hold
        self.bad_hours = self.BAD_HOURS if bad_hours is None else frozenset(bad_hours)
        self.bad_dow = self.BAD_DOW if bad_dow is None else frozenset(bad_dow)
        self._sig = None

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
        raw = trend & (emaF < emaS) & rev_attempt
        self._sig = pd.Series(raw).shift(1).fillna(False).infer_objects(copy=False).to_numpy()

    def advise(self, ctx):
        if self._sig is None:
            self._precompute(ctx.df)
        i = ctx.i
        if ctx.in_position():
            pos = ctx.position
            if (i + 1) - pos['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None
        if self._sig[i]:
            nb = i + 1
            if nb < len(ctx.df) and 'dt' in ctx.df.columns:
                ts = pd.Timestamp(ctx.df['dt'].values[nb])
                if ts.hour in self.bad_hours:
                    return None
                if ts.dayofweek in self.bad_dow:
                    return None
            price = ctx.price(); pip = ctx.spec['pip']
            sl = price + self.sl_pip * pip
            tp = price - self.tp_pip * pip
            return {'action': 'SHORT', 'sl': sl, 'tp': tp}
        return None


def median_atr_pip(df, asset, warmup=2000):
    pip = 0.10 if asset == 'XAUUSD' else 0.0001
    a = ind.atr(df, 14).to_numpy()
    return float(np.nanmedian(a[warmup:]) / pip)


def run_one(asset, tf, sl_pip, tp_pip, max_hold, warmup=2000):
    df = TS.load_data(f'{asset}_{tf}')
    strat = MarketInertiaShortMTF(sl_pip=sl_pip, tp_pip=tp_pip, max_hold=max_hold)
    tr, eq = TS.simulate(df, strat, asset, warmup=warmup)
    r = RQS.compute_rqs(tr, asset)
    return r, len(tr) if tr is not None else 0


def grid_search(asset, tf, warmup=2000):
    """grid حولِ نسبتِ ATR. sl_mult ∈ {7,8,9.5,11}× medianATR، rr ∈ {0.9,1.0,1.1,1.2}."""
    df = TS.load_data(f'{asset}_{tf}')
    matr = median_atr_pip(df, asset, warmup)
    # max_hold متناسب با TF: در S303/M15 = 48 کندل ≈ ۱۲ ساعت. برای هر TF ~۱۲ ساعت نگه‌داری.
    tf_minutes = {'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240}[tf]
    max_hold = max(12, int(round(12 * 60 / tf_minutes)))
    results = []
    for sl_mult in [7.0, 8.0, 9.5, 11.0]:
        sl_pip = round(sl_mult * matr, 1)
        for rr in [0.9, 1.0, 1.1, 1.2]:
            tp_pip = round(sl_pip * rr, 1)
            strat = MarketInertiaShortMTF(sl_pip=sl_pip, tp_pip=tp_pip, max_hold=max_hold)
            tr, eq = TS.simulate(df, strat, asset, warmup=warmup)
            r = RQS.compute_rqs(tr, asset)
            m = r['metrics']
            results.append(dict(
                asset=asset, tf=tf, matr_pip=round(matr, 1), sl_mult=sl_mult,
                sl_pip=sl_pip, tp_pip=tp_pip, rr=rr, max_hold=max_hold,
                rqs=r['rqs_score'], verdict=r['verdict'], passed=r['passed'],
                n=m.get('n_trades', 0), wr=m.get('win_rate', 0),
                pf=m.get('profit_factor', 0), dd=m.get('max_dd_pct', 0),
                mcl=m.get('max_consec_losses', 0), p=m.get('p_value', 1),
                gates=r['gates'],
            ))
    return results, matr, max_hold


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tfs = sys.argv[2].split(',') if len(sys.argv) > 2 else ['M5', 'M30', 'H1', 'H4']
    all_res = []
    for tf in tfs:
        print(f'\n===== {asset} {tf} =====')
        res, matr, mh = grid_search(asset, tf)
        res.sort(key=lambda x: x['rqs'], reverse=True)
        print(f'medianATR={matr:.1f}pip  max_hold={mh}')
        for r in res[:6]:
            g = ''.join('✓' if v else '✗' for v in r['gates'].values())
            print(f"  SL={r['sl_pip']:6.1f} TP={r['tp_pip']:6.1f} rr={r['rr']} | "
                  f"{r['verdict']:6s} RQS={r['rqs']:5.1f} n={r['n']:4d} WR={r['wr']:4.1f}% "
                  f"PF={r['pf']:.2f} DD={r['dd']:.1f}% MCL={r['mcl']} p={r['p']:.3f} {g}")
        all_res.extend(res)
    out = os.path.join(ROOT, 'results', '_s329_mtf_grid.json')
    with open(out, 'w') as f:
        json.dump(all_res, f, indent=2, default=str)
    print(f'\nsaved: {out}')
