# -*- coding: utf-8 -*-
"""
s950_overlap_audit.py — ممیزیِ همپوشانیِ S950-H8 (drift-aligned) با ۵ لایهٔ ACCEPT سایت
================================================================================
قانونِ همپوشانیِ پروژه — سه پرسش:
  ۱) با کدام لایه‌ها و چند درصد همپوشانی دارد؟ (بازهٔ نگهداری + روزِ ورود)
  ۲) بخشِ متفاوت ارزشِ افزودن دارد؟
  ۳) بخشِ همپوشان به‌عنوانِ فیلتر چه می‌کند؟ (بلافاصله آزموده می‌شود، نه بعداً)

چون کارت‌ها تایم‌فریم‌های متفاوت دارند (M5/M15/M30/H1/H4 در برابرِ H8)،
سنجش روی محورِ **زمان** است نه اندیسِ کندل:
  • concur%  = سهمِ معاملاتِ S950 که بازهٔ [ورود,خروج]شان با بازهٔ بازِ لایهٔ
               دیگر تلاقی دارد (اشغالِ هم‌زمانِ حساب — همان چیزی که بودجه را می‌خورد).
  • jac_day  = ژاکاردِ روزهای ورود (این‌همانیِ الگو).

بازتولیدِ ورودها — هر لایه از منبعِ کدِ خودش، صفر رجوع به MD:
  S355: s530_s355_fullhistory_adjudicate.s355_mask (M5 full)
  S344: trend_from_open_signals، پارامترهای بایگانی (M15 short)
  S312: sim_strategies.S312_MidMonth_Long + شبیه‌سازِ رویداد-محور (M30)
  S356: s356_v24_rejudge run_card signal path (H1)
  S382: جدولِ معاملاتِ داوریِ اصلی results/_s382/XAUUSD_H4_trades.csv (H4)
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from engine import scalp_engine as se                       # noqa: E402
from engine import rqs2                                     # noqa: E402
from tools import s434_fast_data as fd                      # noqa: E402
from strategies.s950_jump_aftermath import (features, member_signals,   # noqa: E402
                                            build_null_perm, SPLIT_FRAC,
                                            MAX_HOLD, BV_WIN)

OUT = 'results/_scan_S950'


def to_dt(time_vals):
    v = np.asarray(time_vals)
    if np.issubdtype(v.dtype, np.datetime64):
        return pd.DatetimeIndex(v)
    return pd.DatetimeIndex(pd.to_datetime(v.astype(np.int64), unit='s'))


def intervals_from_trades(tr, dt_index):
    eb = tr['entry_bar'].values.astype(int)
    xb = tr['exit_bar'].values.astype(int)
    xb = np.minimum(xb, len(dt_index) - 1)
    return list(zip(dt_index[eb].values, dt_index[xb].values)), \
        set(pd.DatetimeIndex(dt_index[eb]).normalize())


# ---------------------------- S950-H8 drift-aligned ----------------------------
def s950_trades():
    d = fd.load_fast('XAUUSD', 'H8')
    df = fd.as_dataframe(d)
    pip = se.ASSETS['XAUUSD']['pip']
    c = df['close'].values.astype(np.float64)
    r, sbv, atr_px = features(df)
    ls0, ss0 = member_signals(r, sbv, 2.6, 'continuation', warm=BV_WIN + 2)
    drift = np.zeros(len(c))
    drift[BV_WIN + 1:] = c[BV_WIN:-1] - c[:-(BV_WIN + 1)]
    ls = ls0 & (drift > 0)
    ss = ss0 & (drift < 0)
    sl_arr = np.maximum(2.058 * atr_px / pip, 1e-9)
    tr = se.simulate_trades(df, ls, ss, sl_arr, sl_arr * 1.0, 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=False)
    return tr, df, ls, ss


# ------------------------------- لایه‌های سایت -------------------------------
def s382_trades():
    tr = pd.read_csv('results/_s382/XAUUSD_H4_trades.csv')
    df = pd.read_csv('data/XAUUSD_H4.csv')
    dt = to_dt(df['time'].values)
    return tr, dt


def s344_trades():
    from strategies.s344_brooks_trend_from_open import (trend_from_open_signals,
                                                        load_tf)
    from engine import indicator_bank as ib
    df = load_tf('XAUUSD', 'M15')
    sig = trend_from_open_signals(df, 'M15', 'short', n_open=4, f_range=0.20,
                                  pull_max=0.62, min_spike_frac=0.20)
    # رژیمِ r2h — عیناً مطابقِ s344_overlap_validate.regime_mask
    a = ib.r2(df, p=34).to_numpy()
    b = ib.hurst(df, p=55).to_numpy()
    sig = sig & (a >= 0.30) & (b >= 0.52) & np.isfinite(a) & np.isfinite(b)
    tr = se.simulate_trades(df, np.zeros(len(df), bool), sig, 220, 340,
                            'XAUUSD', max_hold=32, allow_overlap=False)
    return tr, to_dt(df['time'].values)


def s356_trades():
    from strategies import s356_v24_rejudge as S356
    from strategies import s354_brooks_trend_resumption as base354
    path = 'data/XAUUSD_H1.csv'
    df = se.load_data(path)
    atr_pip = base354._atr_pip(df, 'XAUUSD', base354.TF_ATR_P.get('H1', 34))
    sl = round(S356.FROZEN['sl_k'] * atr_pip, 1)
    tp = round(S356.FROZEN['rr'] * sl, 1)
    mh = base354.TF_MAX_HOLD.get('H1', 20)
    gate = base354.regime_gate(df, S356.FROZEN['regime'])
    sig = S356.build_signals_causal(df, 'XAUUSD', 'H1',
                                    S356.FROZEN['n_open_frac'],
                                    S356.FROZEN['late_hour'],
                                    S356.FROZEN['spike_k'],
                                    S356.FROZEN['tight_atr']) & gate
    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp,
                            'XAUUSD', max_hold=mh, allow_overlap=False)
    return tr, to_dt(df['time'].values)


def s312_trades():
    from engine import trade_simulator as TS
    from strategies.sim_strategies import S312_MidMonth_Long
    df = TS.load_data('XAUUSD_M30')
    strat = S312_MidMonth_Long(sl_pip=295, tp_pip=295, max_hold=36,
                               quality_filter=True)
    tr, _ = TS.simulate(df, strat, 'XAUUSD', tf='XAUUSD_M30', warmup=240,
                        max_bars_hold=36)
    dt = pd.DatetimeIndex(df['dt'])
    return tr, dt


def s355_trades():
    from strategies import s530_s355_fullhistory_adjudicate as S530
    df = S530.load_full()
    mask = S530.s355_mask(df)
    sl, tp, mh = S530.geometry()
    tr = se.simulate_trades(df, mask, np.zeros(len(df), bool), sl, tp,
                            'XAUUSD', max_hold=mh, allow_overlap=False)
    tcol = 'time' if 'time' in df.columns else 'dt'
    return tr, to_dt(df[tcol].values)


def interval_overlap_pct(iv_a, iv_b):
    """سهمِ بازه‌های a که با دست‌کم یک بازهٔ b تلاقی دارند (خطی، مرتب)."""
    if not iv_a or not iv_b:
        return 0.0, 0
    b_sorted = sorted(iv_b)
    starts = np.array([x[0] for x in b_sorted])
    ends = np.array([x[1] for x in b_sorted])
    hit = 0
    for (a0, a1) in iv_a:
        j = np.searchsorted(starts, a1, side='right')
        if j > 0 and np.any(ends[:j] >= a0):
            hit += 1
    return 100.0 * hit / len(iv_a), hit


def main():
    print('بازتولیدِ معاملاتِ ۶ لایه (رویداد-محور/موتورِ داوریِ اصلی هر لایه)…',
          flush=True)
    tr950, df950, ls950, ss950 = s950_trades()
    dt950 = to_dt(df950['time'].values)
    iv950, days950 = intervals_from_trades(tr950, dt950)
    print(f'S950-H8 drift-aligned: n={len(tr950)}', flush=True)

    layers = {}
    for name, fn in (('S382_H4', s382_trades), ('S344_M15', s344_trades),
                     ('S356_H1', s356_trades), ('S312_M30', s312_trades),
                     ('S355_M5', s355_trades)):
        try:
            tr, dt = fn()
            iv, days = intervals_from_trades(tr, dt)
            layers[name] = dict(iv=iv, days=days, n=len(tr))
            print(f'{name}: n={len(tr)}', flush=True)
        except Exception as e:                                # noqa: BLE001
            layers[name] = dict(error=repr(e))
            print(f'{name}: ERROR {e!r}', flush=True)

    report = dict(s950=dict(n=len(tr950)), vs={})
    overlap_mask_any = np.zeros(len(tr950), bool)
    for name, L in layers.items():
        if 'error' in L:
            report['vs'][name] = dict(error=L['error'])
            continue
        pct, hits = interval_overlap_pct(iv950, L['iv'])
        jd = (100.0 * len(days950 & L['days']) /
              max(len(days950 | L['days']), 1))
        # ماسکِ معامله‌به‌معامله برای آزمونِ فیلتر
        b_sorted = sorted(L['iv'])
        starts = np.array([x[0] for x in b_sorted])
        ends = np.array([x[1] for x in b_sorted])
        for i, (a0, a1) in enumerate(iv950):
            j = np.searchsorted(starts, a1, side='right')
            if j > 0 and np.any(ends[:j] >= a0):
                overlap_mask_any[i] = True
        report['vs'][name] = dict(n_other=L['n'], concur_pct=round(pct, 2),
                                  concur_hits=hits, jac_day=round(jd, 2))
        print(f'{name}: concur={pct:.2f}% ({hits}/{len(iv950)}) '
              f'jac_day={jd:.2f}%', flush=True)

    # ---------- پرسشِ ۳ — بخشِ همپوشان به‌عنوانِ فیلتر، بلافاصله ----------
    n_ov = int(overlap_mask_any.sum())
    pnl = tr950['pnl_pip'].values
    report['overlap_as_filter'] = dict(n_overlap=n_ov,
                                       n_total=len(tr950))
    if n_ov >= 5:
        wr_ov = 100.0 * float((pnl[overlap_mask_any] > 0).mean())
        wr_no = 100.0 * float((pnl[~overlap_mask_any] > 0).mean())
        report['overlap_as_filter'].update(
            wr_overlap=round(wr_ov, 2), wr_nonoverlap=round(wr_no, 2),
            net_pip_overlap=round(float(pnl[overlap_mask_any].sum()), 1),
            net_pip_nonoverlap=round(float(pnl[~overlap_mask_any].sum()), 1))
        print(f'فیلترِ همپوشانی: WR(هم‌زمان)={wr_ov:.1f}% در برابرِ '
              f'WR(مستقل)={wr_no:.1f}% (n_ov={n_ov})', flush=True)
    else:
        report['overlap_as_filter']['note'] = (
            'کمتر از ۵ معاملهٔ همپوشان — آزمونِ فیلترِ معنادار ممکن نیست؛ '
            'خودِ این یافته پاسخِ پرسشِ ۳ است: چیزی برای فیلترشدن وجود ندارد.')
        print(f'همپوشانِ کل: {n_ov} معامله — زیر آستانهٔ آزمونِ فیلتر.', flush=True)

    json.dump(report, open(f'{OUT}/H8_overlap_audit.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print('ذخیره شد:', f'{OUT}/H8_overlap_audit.json')


if __name__ == '__main__':
    main()
