# -*- coding: utf-8 -*-
"""s770_overlap_audit.py — ممیزی همپوشانی S770-POOL2 {D1,H8} با ۵ لایهٔ ACCEPT سایت.

قانون همپوشانی — سه پرسش:
  ۱) با کدام لایه‌ها و چند درصد همپوشانی دارد؟ (تلاقی بازهٔ باز + ژاکارد روز ورود)
  ۲) بخش متفاوت ارزش افزودن دارد؟
  ۳) بخش همپوشان به‌عنوان فیلتر چه می‌کند؟ (بلافاصله آزموده می‌شود، نه بعداً)

الگو: strategies/s950_overlap_audit.py (همان پروتکل، همان بازتولید per-لایه).
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

from engine import scalp_engine as se                      # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402
from strategies.s770_adr_expansion import (                # noqa: E402
    load_card, build_features, signals_for, geometry, SCAN_DIR)

OUT = SCAN_DIR


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


# ------------------------- S770-POOL2: بازتولید منجمد -------------------------
def s770_pool_trades():
    """همان اعضای POOL2 با پیکربندی منجمد؛ FIFO تقویمی مثل rqs2_pool."""
    from engine.rqs2_pool import pool_cards
    members = []
    for tf in ('D1', 'H8'):
        with open(os.path.join(SCAN_DIR, f'{tf}_verdict.json')) as f:
            v = json.load(f)
        theta, hold = v['theta'], v['hold']
        df, src = load_card(tf)
        frac = build_features(df)
        sl_pip, tp_pip, atr = geometry(df)
        valid = np.isfinite(frac) & np.isfinite(sl_pip) & (sl_pip > 0)
        ls, ss = signals_for(frac, theta)
        ls &= valid; ss &= valid
        tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset='XAUUSD',
                                max_hold=hold, allow_overlap=False)
        dt = pd.to_datetime(df['time'], unit='s').values
        members.append(dict(card=f'XAUUSD_{tf}', tr=tr, dt=dt,
                            lift=float(v['metrics']['skill_lift_pp'])))
    res = pool_cards(members)
    pool = res['pool'].sort_values('t_entry').reset_index(drop=True)
    iv = list(zip(pool['t_entry'].values.astype('datetime64[ns]'),
                  pool['t_exit'].values.astype('datetime64[ns]')))
    days = set(pd.DatetimeIndex(pool['t_entry'].values.astype('datetime64[ns]')).normalize())
    return pool, iv, days


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


def main():
    print('بازتولید S770-POOL2 و ۵ لایهٔ سایت…', flush=True)
    pool, iv770, days770 = s770_pool_trades()
    print(f'S770-POOL2: n={len(pool)}', flush=True)

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

    report = dict(s770_pool=dict(n=len(pool)), vs={})
    overlap_mask_any = np.zeros(len(pool), bool)
    for name, L in layers.items():
        if 'error' in L:
            report['vs'][name] = dict(error=L['error'])
            continue
        b_sorted = sorted(L['iv'])
        starts = np.array([x[0] for x in b_sorted])
        ends = np.array([x[1] for x in b_sorted])
        hit = 0
        for i, (a0, a1) in enumerate(iv770):
            j = np.searchsorted(starts, a1, side='right')
            if j > 0 and np.any(ends[:j] >= a0):
                hit += 1
                overlap_mask_any[i] = True
        pct = 100.0 * hit / max(len(iv770), 1)
        jd = (100.0 * len(days770 & L['days']) /
              max(len(days770 | L['days']), 1))
        report['vs'][name] = dict(n_other=L['n'], concur_pct=round(pct, 2),
                                  concur_hits=hit, jac_day=round(jd, 2))
        print(f'{name}: concur={pct:.2f}% ({hit}/{len(iv770)}) jac_day={jd:.2f}%',
              flush=True)

    # ---------- پرسش ۳ — بخش همپوشان به‌عنوان فیلتر، بلافاصله ----------
    n_ov = int(overlap_mask_any.sum())
    pnl = pool['pnl_pip'].values
    report['overlap_as_filter'] = dict(n_overlap=n_ov, n_total=len(pool))
    if n_ov >= 5:
        wr_ov = 100.0 * float((pnl[overlap_mask_any] > 0).mean())
        wr_no = 100.0 * float((pnl[~overlap_mask_any] > 0).mean())
        report['overlap_as_filter'].update(
            wr_overlap=round(wr_ov, 2), wr_nonoverlap=round(wr_no, 2),
            net_pip_overlap=round(float(pnl[overlap_mask_any].sum()), 1),
            net_pip_nonoverlap=round(float(pnl[~overlap_mask_any].sum()), 1))
        print(f'فیلتر همپوشانی: WR(هم‌زمان)={wr_ov:.1f}% در برابر '
              f'WR(مستقل)={wr_no:.1f}% (n_ov={n_ov})', flush=True)
    else:
        report['overlap_as_filter']['note'] = (
            'کمتر از ۵ معاملهٔ همپوشان — چیزی برای فیلترشدن وجود ندارد.')
        print(f'همپوشان کل: {n_ov} معامله — زیر آستانهٔ آزمون فیلتر.', flush=True)

    json.dump(report, open(f'{OUT}/POOL2_overlap_audit.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print('ذخیره شد:', f'{OUT}/POOL2_overlap_audit.json')


if __name__ == '__main__':
    main()
