# -*- coding: utf-8 -*-
"""S527 — استخرِ دو لبهٔ H8 دهکِ گاوس: S523 (WPR درفت-گیت) + S526 (سقف تازه).

پیش‌ثبت: `results/S527_PREREG_TwinH8EdgePool_Xauusd_H8.md` (کامیت 189dcaf4 —
قبل از این اجرا). مسیر B، صفر پارامتر آزاد.

هر دو عضو روی **یک کارت** (XAUUSD_H8، data/full) با **یک هندسه** (SL=1.5×ATR100،
RR=1.5) — پس ادغام تقویمی ساده است: dedupe همان-کندل (به نفع عضو ۱)، سپس FIFO
بدون هم‌زمانی روی محور کندل‌های H8 خود کارت (محور مشترک طبیعی است چون TF یکی است —
BUG-AXIS منتفی). نول: blend شرطی‌شدهٔ اعضا با وزن سهم پس-از-FIFO (دستورکار S431/S520).
n_trials=23789 (وراثت کامل WPR). F1: co-event >40% گزارش/داوری طبق پیش‌ثبت.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2  # noqa: E402

OUT = 'results/_s527'
CARD = 'XAUUSD_H8'
N_TRIALS = 23789
LB = 90
SPLIT_FRAC = 0.60
C5_MAX = 0.50


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')

    df = pd.read_csv(f'data/full/{CARD}.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    c = df['close']
    drift = ((c.shift(1) - c.shift(LB)) > 0).fillna(False)

    # عضو ۱: S523 — WPR گذر & drift>0
    w = L.willr(df)
    sig1 = ((w.shift(1) <= L.WILLR_THR) & (w > L.WILLR_THR) & drift).fillna(False)
    # عضو ۲: S526 — لبهٔ تازهٔ سقف ۹۰
    pm = c.rolling(LB).max().shift(1)
    nh = (c > pm).fillna(False)
    sig2 = (nh & ~nh.shift(1).fillna(False)).astype(bool)

    both = int((sig1 & sig2).sum())
    print(f'[سیگنال] s523={int(sig1.sum())} s526={int(sig2.sum())} '
          f'same-bar={both} (dedupe به نفع عضو ۱)', flush=True)

    ps = L.pip_size('XAUUSD')
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * L.RR

    # معاملات هر عضو جدا (برای سهم/نول)، سپس ادغام سیگنالی و FIFO با شبیه‌ساز واحد
    sig2_dedup = sig2 & ~sig1
    tr1 = L.simulate_trades(df, sig1, sl_abs, L.RR, True, ps)
    tr2 = L.simulate_trades(df, sig2_dedup, sl_abs, L.RR, True, ps)
    print(f'[اعضا] s523: n={len(tr1)} | s526(dedup): n={len(tr2)}', flush=True)

    # سلامت: بازتولید اعداد چک‌پوینت‌شده
    r523 = json.load(open('results/_s523/XAUUSD_H8.json'))
    r526 = json.load(open('results/_s526/XAUUSD_H8.json'))
    assert len(tr1) == r523['n_trades'], f"s523 mismatch {len(tr1)} vs {r523['n_trades']}"

    # F1: هم‌رویدادی — ورودی‌های عضو ۲ درون پنجره‌های باز عضو ۱ و برعکس
    def co_event_pct(tr_a, tr_b):
        e_a = tr_a['entry_bar'].to_numpy()
        x_a = tr_a['exit_bar'].to_numpy()
        e_b = tr_b['entry_bar'].to_numpy()
        cnt = 0
        for t in e_b:
            if np.any((e_a <= t) & (t < x_a)):
                cnt += 1
        return 100.0 * cnt / max(1, len(e_b))

    f1_2in1 = co_event_pct(tr1, tr2)
    f1_1in2 = co_event_pct(tr2, tr1)
    print(f'[F1] s526-entries inside s523-windows: {f1_2in1:.1f}% | '
          f'reverse: {f1_1in2:.1f}%', flush=True)

    # استخر: سیگنال ادغامی، شبیه‌ساز واحد allow_overlap=False = FIFO concurrency=1
    sig_pool = (sig1 | sig2).astype(bool)
    tr_pool = L.simulate_trades(df, sig_pool, sl_abs, L.RR, True, ps)
    n_before = len(tr1) + len(tr2)
    print(f'[FIFO] n_before(members)={n_before} n_pool={len(tr_pool)}', flush=True)

    # برچسب منبع هر معاملهٔ استخر (entry_bar عضوِ سازنده)
    e1 = set(tr1['entry_bar'].tolist())
    src = ['s523' if b in e1 else 's526' for b in tr_pool['entry_bar']]
    tr_pool = tr_pool.copy()
    tr_pool['src_card'] = src
    share = pd.Series(src).value_counts(normalize=True).to_dict()
    print(f'[C5 سهم] {share}', flush=True)
    if max(share.values()) > C5_MAX:
        print(f'[C5 نقض] بیشینه سهم {max(share.values()):.1%} > 50% — طبق S431 '
              f'ثبت می‌شود؛ داوری ادامه دارد و در MD لحاظ می‌شود.', flush=True)

    # نول blend: وزن به سهم پس-از-FIFO — نول‌های شرطی‌شدهٔ ذخیره‌شدهٔ اعضا
    w1 = share.get('s523', 0.0)
    w2 = share.get('s526', 0.0)
    unc = r523['uncond_wr'] * w1 + r526['uncond_wr'] * w2
    pmean = r523['perm_mean'] * w1 + r526['perm_mean'] * w2
    psd = float(np.sqrt((r523['perm_sd'] ** 2) * w1 ** 2 +
                        (r526['perm_sd'] ** 2) * w2 ** 2))
    null = {'long': dict(uncond_wr=unc, perm_mean=pmean, perm_sd=psd,
                         perm_max=None, perm_k=2000),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    print(f'[نول blend] unc={unc:.2f} perm_mean={pmean:.2f} perm_sd={psd:.3f}',
          flush=True)

    # تقسیم ۶۰/۴۰ بر صدک زمان ورود
    dtv = df['dt'].values.astype('datetime64[ns]').astype(np.int64)
    te = dtv[tr_pool['entry_bar'].values]
    split_ns = int(np.quantile(te, SPLIT_FRAC))
    holdout = te >= split_ns
    print(f'[تقسیم] مرز={np.datetime64(split_ns, "ns")} · '
          f'اکتشاف={int((~holdout).sum())} · OOS={int(holdout.sum())}', flush=True)

    r = rqs2.compute_rqs2(tr_pool, 'XAUUSD', sl_pip=sl_pip, tp_pip=tp_pip,
                          bar_time=df['dt'].values, null=null,
                          close=df['close'].to_numpy(float),
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S527-POOL', r), flush=True)

    out = dict(card=CARD, n_trials=N_TRIALS,
               members=dict(s523=dict(n=len(tr1), lift=r523['lift']),
                            s526=dict(n=len(tr2), lift=r526['lift'])),
               same_bar_signals=both, f1_s526_in_s523=round(f1_2in1, 1),
               f1_s523_in_s526=round(f1_1in2, 1),
               n_before=n_before, n_pool=len(tr_pool), member_share=share,
               sl_pip=sl_pip, tp_pip=tp_pip,
               null_blend=null['long'], split_frac=SPLIT_FRAC,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=[str(x) for x in (r.get('notes') or [])])
    with open(f'{OUT}/POOL_verdict.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, default=str)
    print(f'saved -> {OUT}/POOL_verdict.json', flush=True)


if __name__ == '__main__':
    main()
