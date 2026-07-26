# -*- coding: utf-8 -*-
"""
S329c — تلاشِ نهاییِ احیای Market-Inertia SHORT روی EURUSD M15 (WR 56% → ≥60%)
================================================================================
یافتهٔ S329b: بهترین ترکیبِ EURUSD M15 = (lb=40, adx>22, ema13/34, SL≈57pip, rr≈1.0-1.1)
  به WR=56.2٪، PF=1.58، maxDD 2.8٪، MCL 3، G4(پایداری)=✓ رسید — یعنی یک لبهٔ ساختاریِ
  واقعی *وجود دارد* اما G0 (WR≥60) و G1 (معناداری) را رد می‌کند. n=48 (کم).

طبقِ قانونِ بی‌نهایتِ بهبود + قانونِ مرگِ ابدی (فقط وقتی مرده اعلام کن که هیچ ترکیبی
نجاتش ندهد)، این اسکریپت فیلترهای *افزایشیِ WR* را می‌آزماید — همان تاکتیکی که S303 را
روی طلا نجات داد:
  ۱) تحلیلِ WR به تفکیکِ ساعتِ UTC و روزِ هفته روی ترکیبِ پایه (کدام bucketها زیانده‌اند؟)
  ۲) حذفِ خودکارِ bucketهای زیانده (WR<50٪ با n≥5) و سنجشِ مجددِ RQS+.
  ۳) گرید کوچک روی adx_hi برایِ افزایشِ کیفیتِ سیگنال.
اگر پس از همهٔ این‌ها WR<60 یا هر گیتِ دیگر رد بماند ⇒ EURUSD M15 برای این لایه DEAD.
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
from strategies.s329_market_inertia_mtf import MarketInertiaShortMTF


def base_strategy(bad_hours=None, bad_dow=None, adx_hi=22, lb=40, ef=13, es=34,
                  sl_pip=56.9, tp_pip=62.6, max_hold=48):
    return MarketInertiaShortMTF(ef=ef, es=es, adx_hi=adx_hi, lb=lb,
                                 sl_pip=sl_pip, tp_pip=tp_pip, max_hold=max_hold,
                                 bad_hours=bad_hours or set(), bad_dow=bad_dow or set())


def analyze_buckets(tr, df):
    """WR به تفکیکِ ساعت و روز از روی exit/entry bar."""
    if tr is None or len(tr) == 0:
        return {}, {}
    tr = tr.copy()
    ts = pd.to_datetime(df['dt'].values[tr['entry_bar'].clip(0, len(df) - 1).values])
    tr['hour'] = pd.DatetimeIndex(ts).hour
    tr['dow'] = pd.DatetimeIndex(ts).dayofweek
    tr['win'] = (tr['pnl_pip'] > 0).astype(int)
    hstat = tr.groupby('hour')['win'].agg(['mean', 'count'])
    dstat = tr.groupby('dow')['win'].agg(['mean', 'count'])
    return hstat, dstat


def main():
    asset = 'EURUSD'; tf = 'M15'
    df = TS.load_data(f'{asset}_{tf}')

    # ۱) ترکیبِ پایه (بهترین از S329b) — SL=57, rr=1.1
    print('===== EURUSD M15 — تحلیلِ bucketها روی ترکیبِ پایه =====')
    tr, _ = TS.simulate(df, base_strategy(sl_pip=56.9, tp_pip=62.6), asset, warmup=2000)
    r0 = RQS.compute_rqs(tr, asset)
    print(RQS.format_report('base', r0))

    hstat, dstat = analyze_buckets(tr, df)
    print('\n-- WR به تفکیکِ ساعتِ UTC (mean=WR, count=n) --')
    print(hstat.round(3).to_string())
    print('\n-- WR به تفکیکِ روزِ هفته (0=دوشنبه) --')
    print(dstat.round(3).to_string())

    # ۲) حذفِ خودکارِ bucketهای زیانده (WR<0.50 با n>=5)
    bad_hours = set(int(h) for h, row in hstat.iterrows() if row['mean'] < 0.50 and row['count'] >= 5)
    bad_dow = set(int(d) for d, row in dstat.iterrows() if row['mean'] < 0.50 and row['count'] >= 5)
    print(f'\nbad_hours (auto) = {sorted(bad_hours)}')
    print(f'bad_dow   (auto) = {sorted(bad_dow)}')

    print('\n===== پس از حذفِ bucketهای زیانده =====')
    best = None
    for adx_hi in (20, 22, 25, 28):
        for rr in (0.9, 1.0, 1.1, 1.2):
            sl = 56.9; tp = round(sl * rr, 1)
            strat = base_strategy(bad_hours=bad_hours, bad_dow=bad_dow,
                                  adx_hi=adx_hi, sl_pip=sl, tp_pip=tp)
            tr2, _ = TS.simulate(df, strat, asset, warmup=2000)
            r = RQS.compute_rqs(tr2, asset)
            m = r['metrics']
            g = ''.join('✓' if v else '✗' for v in r['gates'].values())
            print(f"  adx>{adx_hi} rr={rr} | {r['verdict']:6s} RQS={r['rqs_score']:5.1f} "
                  f"n={m.get('n_trades',0):3d} WR={m.get('win_rate',0):4.1f}% "
                  f"PF={m.get('profit_factor',0):.2f} DD={m.get('max_dd_pct',0):.1f}% "
                  f"MCL={m.get('max_consec_losses',0)} p={m.get('p_value',1):.3f} {g}")
            if best is None or r['rqs_score'] > best['rqs_score']:
                best = r
    print('\nBEST:', RQS.format_report('best_filtered', best))
    return best


if __name__ == '__main__':
    main()
