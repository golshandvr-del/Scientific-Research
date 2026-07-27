# -*- coding: utf-8 -*-
"""
S331 — اسکنِ بهبودِ squeeze روی XAUUSD M15 برای عبور از هر ۶ گیتِ RQS+
================================================================================
فرضیهٔ مرکزی (تفکرِ غیرخطی): تضادِ ساختاریِ «سودِ بالا (TP بزرگ ⇒ WR پایین) ↔ WR≥۶۰
(TP کوچک ⇒ سودِ کم)» را با **مدیریتِ معاملهٔ هیبریدی** حل می‌کنیم:
  • TP نسبتاً بزرگ برای گرفتنِ انفجارِ صعودی (حفظِ سود، طبق User Note)،
  • break-even زودهنگام + trailing-stop برای تبدیلِ باخت‌ها به BE/win
    ⇒ WR↑ (G0)، maxDD↓ و MCL↓ (G3)، PF↑ (G2) — بدون کشتنِ سود.
  • + استخرِ فیلترهای «قانونِ شاید هیچ‌چیز ثابت نیست»: ADX, RSI, ATR-regime, EMA-slope.

خروجی: جدولِ کامل + بهترین پیکربندیِ گیت-پاس (بیشترین net).
"""
import os
import sys
import itertools
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs
import strategies.s332_squeeze_rqs_revival as S


def build_filters(df):
    """استخرِ فیلترهای کاندید (بردارهای بولینِ هم‌طولِ df)."""
    c = df['close'].values.astype(np.float64)
    adx_, pdi, mdi = S.adx(df, 14)
    rsi_ = S.rsi(c, 14)
    atr_ = S.atr(df, 14)
    e50 = S.ema(c, 50)
    e100 = S.ema(c, 100)
    # میانهٔ غلتانِ ATR برای رژیمِ نوسان (بدونِ look-ahead: تا کندلِ i)
    atr_med = pd.Series(atr_).rolling(200, min_periods=50).median().values
    pool = {
        'none':      np.ones(len(df), dtype=bool),
        'adx>20':    (adx_ > 20),
        'adx>25':    (adx_ > 25),
        'rsi>50':    (rsi_ > 50),
        'rsi45_75':  (rsi_ > 45) & (rsi_ < 75),
        'pdi>mdi':   (pdi > mdi),
        'ema50>100': (e50 > e100),
        'atr<1.5med':(atr_ < 1.5 * atr_med),
        'atr>0.7med':(atr_ > 0.7 * atr_med),
    }
    # جایگزینیِ NaN با False (محافظه‌کارانه: فیلترِ نامشخص = عدمِ ورود)
    for k in pool:
        pool[k] = np.where(np.isnan(pool[k].astype(float)), False, pool[k]).astype(bool) \
                  if pool[k].dtype != bool else np.nan_to_num(pool[k].astype(float), nan=0.0).astype(bool)
    return pool


def scan(sym='XAUUSD', tf='M15', sqz_pct=0.25, brk=6, max_hold=96,
         report_top=25):
    df = S.load_tf(sym, tf)
    sig = S.build_squeeze_signal(df, sqz_pct=sqz_pct, breakout_lookback=brk)
    pool = build_filters(df)
    print(f"== {sym} {tf} | squeeze signals={int(sig.sum())} | sqz_pct={sqz_pct} brk={brk} mh={max_hold} ==")

    results = []
    # شبکهٔ TP/SL نامتقارن + trailing/BE
    tp_grid = [180, 220, 260, 300]
    sl_grid = [70, 90, 110, 130]
    trail_grid = [None, 60, 90, 120]
    be_grid = [None, 50, 80]
    # فیلترهای منفرد + جفت‌ها (تا ۲ فیلترِ همزمان برای شروع)
    filt_names = ['none', 'adx>20', 'adx>25', 'rsi>50', 'rsi45_75', 'pdi>mdi',
                  'ema50>100', 'atr<1.5med', 'atr>0.7med']
    filt_combos = [('none',)]
    for a in filt_names[1:]:
        filt_combos.append((a,))
    # جفت‌های منتخب (مومنتوم × رژیم)
    for a in ['adx>20', 'adx>25', 'pdi>mdi']:
        for b in ['rsi>50', 'ema50>100', 'atr<1.5med']:
            filt_combos.append((a, b))

    for combo in filt_combos:
        fmask = np.ones(len(df), dtype=bool)
        for name in combo:
            fmask = fmask & pool[name]
        for tp in tp_grid:
            for sl in sl_grid:
                for trail in trail_grid:
                    for be in be_grid:
                        r, tr = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp,
                                           max_hold=max_hold, be_trigger_pip=be,
                                           trail_pip=trail, filt=fmask)
                        m = r['metrics']
                        if m.get('n_trades', 0) < 30:
                            continue
                        results.append(dict(
                            combo='+'.join(combo), tp=tp, sl=sl, trail=trail, be=be,
                            passed=r['passed'], rqs=r['rqs_score'],
                            n=m['n_trades'], wr=m['win_rate'], net=m['net_profit'],
                            pf=m['profit_factor'], dd=m['max_dd_pct'],
                            mcl=m['max_consec_losses'], p=m['p_value'],
                            gates=''.join('1' if r['gates'][g] else '0'
                                          for g in ['G0','G1','G2','G3','G4','G5'])))

    res = pd.DataFrame(results)
    if len(res) == 0:
        print("no configs with n>=30")
        return res
    passed = res[res['passed']].sort_values('net', ascending=False)
    print(f"\nTOTAL configs tested: {len(res)} | PASSED all 6 gates: {len(passed)}")
    if len(passed):
        print("\n=== TOP gate-passing configs (by net profit) ===")
        cols = ['combo','tp','sl','trail','be','rqs','n','wr','net','pf','dd','mcl','gates']
        print(passed[cols].head(report_top).to_string(index=False))
    else:
        # نزدیک‌ترین‌ها: بیشترین تعداد گیتِ پاس، سپس net
        res['ngate'] = res['gates'].apply(lambda s: s.count('1'))
        near = res.sort_values(['ngate','net'], ascending=[False, False])
        print("\n=== No full pass. Closest configs (most gates + net) ===")
        cols = ['combo','tp','sl','trail','be','rqs','n','wr','net','pf','dd','mcl','gates']
        print(near[cols].head(report_top).to_string(index=False))
    return res


if __name__ == '__main__':
    scan('XAUUSD', 'M15')
