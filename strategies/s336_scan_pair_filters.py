# -*- coding: utf-8 -*-
"""
s336_scan_pair_filters.py — اسکنِ *جفتِ* فیلتر روی تریگرِ شورت (فراتر از تک‌فیلتر)
=================================================================================
درسِ اسکنِ تک‌فیلتر: هیچ فیلترِ تنها edge را مثبت نکرد. درسِ جهت: spread با n بالا
همه را می‌بلعد؛ نیاز به WR بالاتر از ~۵۳٪ داریم. طبق «قانونِ همکاریِ بهبودها» و
«قانونِ بی‌نهایت»، این‌بار *جفتِ* فیلتر را می‌آزماییم: شاید دو شرطِ هم‌زمان
(مثلاً رژیمِ range + کششِ افراطی) نقطه‌ی شیرینِ n≥150 & PF>1.10 بسازند.

تریگر: crsi_cross_dn82 (SHORT، پُرسیگنال). هدفِ نهایی: SHORT پُرمعامله‌ی سودده.
"""
import numpy as np
import itertools
from engine import scalp_engine as se
from engine import indicator_bank as ib


def run(asset='XAUUSD', tf='M5', tp=50, sl=40, min_n=120):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    n = len(df)
    crsi = ib.compute('crsi', df).values
    base = np.r_[False, (crsi[:-1] >= 82) & (crsi[1:] < 82)]

    # مجموعه‌ی فیلترهای کاندیدا (هر کدام یک ماسک bool، shift(1) امن)
    def s(nm):
        return ib.compute(nm, df).shift(1).values
    feats = {
        'hurst<.45': s('hurst') < 0.45,
        'hurst<.40': s('hurst') < 0.40,
        'chop>60': s('chop') > 60,
        'chop>66': s('chop') > 66,
        'r2<.15': s('r2') < 0.15,
        'zscore>2': s('zscore_fib_21') > 2.0,
        'zscore>2.5': s('zscore_fib_21') > 2.5,
        'fisher>6': s('fisher') > 6.0,
        'kurt>3': s('kurt') > 3.0,
        'entropy<2.4': s('entropy') < 2.4,
        'natr>p70': s('natr') > np.nanquantile(s('natr'), 0.70),
        'efi<0': s('efi') < 0,   # فشارِ فروش تأییدشده
        'skew<0': s('skew') < 0,
    }
    for k in feats:
        feats[k] = np.nan_to_num(feats[k], nan=False).astype(bool)

    def evaluate(mask):
        sig = base & mask
        tr = se.simulate_trades(df, np.zeros(n, bool), sig, sl, tp, asset, 24, False)
        if len(tr) < min_n:
            return None
        wr = (tr['outcome'] == 'win').mean() * 100
        wins = tr.loc[tr.pnl_pip > 0, 'pnl_pip'].sum()
        loss = -tr.loc[tr.pnl_pip <= 0, 'pnl_pip'].sum()
        pf = wins / loss if loss > 0 else 9.99
        return len(tr), wr, pf, tr['pnl_pip'].sum()

    print(f"=== PAIR-FILTER SCAN {asset}/{tf} trigger=crsi_dn82 SHORT TP{tp}/SL{sl} min_n={min_n} ===")
    results = []
    keys = list(feats.keys())
    # تک‌فیلتر
    for k in keys:
        r = evaluate(feats[k])
        if r:
            results.append((r[2], k, r[0], r[1], r[3]))
    # جفت‌فیلتر
    for a, b in itertools.combinations(keys, 2):
        r = evaluate(feats[a] & feats[b])
        if r:
            results.append((r[2], f'{a} & {b}', r[0], r[1], r[4] if len(r) > 4 else r[3]))
    results.sort(reverse=True)
    print(f"{'filter':32s} {'n':>5s} {'WR':>5s} {'PF':>5s} {'net(pip)':>9s}")
    for r in results[:22]:
        flag = ' <==' if r[0] > 1.0 else ''
        print(f"{r[1]:32s} {r[2]:>5d} {r[3]:>5.1f} {r[0]:>5.2f} {r[4]:>9.0f}{flag}")


if __name__ == '__main__':
    run('XAUUSD', 'M5')
