# -*- coding: utf-8 -*-
"""
s338c_kfold_verify.py — اعتبارسنجیِ سختِ k-fold برای جفت‌های کاندیدای S338b

هشدارِ آماریِ حیاتی: در S338b، ۱۹۰ جفت آزموده شد. با آستانهٔ p<0.05، به‌طور *تصادفی*
انتظار می‌رود ~۹.۵ جفت p<0.05 بدهند حتی اگر هیچ edgeِ واقعی نباشد (multiple-testing).
ما فقط ۴ جفت گرفتیم — که *کمتر* از انتظارِ تصادفی است! پس باید با گاردِ بسیار سخت‌تر
بررسی کنیم که آیا این جفت‌ها edgeِ واقعی‌اند یا نویز.

روش: به‌جای یک split، داده را به k=۵ foldِ زمانیِ متوالی می‌شکنیم. یک جفت فقط وقتی
«واقعی» است که در *اکثریتِ* foldها (>=4 از 5) WR>baseline+3 بدهد. edgeِ نویزی در
foldهای مختلف ناپایدار است؛ edgeِ واقعی پایدار.
"""
import sys
import numpy as np
from scipy import stats
from engine import scalp_engine as se
from engine import indicator_bank as ib


def load(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


def atr_pips(df, asset):
    return (ib.compute('atr_fib_13', df) / se.ASSETS[asset]['pip']).values


def build_baseline(df, asset, direction, k_atr=1.5, max_hold=24):
    n = len(df)
    sl = float(np.nanmedian(atr_pips(df, asset))) * k_atr
    ls = np.zeros(n, dtype=bool); ss = np.zeros(n, dtype=bool)
    if direction == 'long':
        ls[:] = True
    else:
        ss[:] = True
    tr = se.simulate_trades(df, ls, ss, sl, sl, asset, max_hold=max_hold, allow_overlap=True)
    return tr['entry_bar'].values, (tr['pnl_pip'].values > 0), sl


def best_th_side(v, w, base_wr, min_frac=0.05):
    ok = np.isfinite(v)
    if ok.sum() < 200:
        return None
    min_n = max(50, int(len(v) * min_frac))
    qs = np.percentile(v[ok], np.arange(5, 96, 5))
    best = None
    for th in qs:
        for side in ('gt', 'lt'):
            m = (v > th) if side == 'gt' else (v < th)
            if int(m.sum()) < min_n:
                continue
            wr = w[m].mean() * 100
            if best is None or wr > best[0]:
                best = (wr, float(th), side)
    return best  # (wr, th, side)


def mask_of(vfull, entry_idx, th, side):
    ev = vfull[entry_idx]
    m = (ev > th) if side == 'gt' else (ev < th)
    return np.nan_to_num(m, nan=0).astype(bool)


def kfold_pair(df, asset, direction, name_a, name_b, k=5):
    entry_idx, win, sl = build_baseline(df, asset, direction)
    base_wr = win.mean() * 100
    va = ib.compute(name_a, df).shift(1).values
    vb = ib.compute(name_b, df).shift(1).values
    m = len(win)
    folds = np.array_split(np.arange(m), k)

    print(f"\n--- {name_a} × {name_b} ({direction}) base_wr={base_wr:.1f}% ---")
    print(f"{'fold':>5} {'th_a/side':>18} {'th_b/side':>18} {'n':>6} {'WR%':>6} {'lift':>6}")
    lifts = []
    # آستانه‌ها را در هر fold *به‌طور مستقل* از بقیهٔ داده (train=همه جز این fold) کشف می‌کنیم
    for fi in range(k):
        test_idx = folds[fi]
        train_mask = np.ones(m, dtype=bool); train_mask[test_idx] = False
        # کشفِ آستانه روی train
        ta = best_th_side(va[entry_idx][train_mask], win[train_mask], base_wr)
        tb = best_th_side(vb[entry_idx][train_mask], win[train_mask], base_wr)
        if ta is None or tb is None:
            print(f"{fi:>5}  (threshold discovery failed)"); lifts.append(None); continue
        _, th_a, side_a = ta
        _, th_b, side_b = tb
        ma = mask_of(va, entry_idx, th_a, side_a)
        mb = mask_of(vb, entry_idx, th_b, side_b)
        comb = ma & mb
        test_sel = np.zeros(m, dtype=bool); test_sel[test_idx] = True
        sel = comb & test_sel
        n = int(sel.sum())
        if n < 30:
            print(f"{fi:>5} {th_a:>10.3f}/{side_a:>3} {th_b:>10.3f}/{side_b:>3} {n:>6}  (n<30)")
            lifts.append(None); continue
        wr = win[sel].mean() * 100
        lift = wr - base_wr
        lifts.append(lift)
        print(f"{fi:>5} {th_a:>10.3f}/{side_a:>3} {th_b:>10.3f}/{side_b:>3} {n:>6} {wr:>6.1f} {lift:>+6.1f}")

    valid = [l for l in lifts if l is not None]
    pos = sum(1 for l in valid if l > 3)
    verdict = "REAL" if (len(valid) >= 4 and pos >= 4) else ("WEAK" if pos >= 3 else "NOISE")
    print(f"  => foldهای معتبر={len(valid)}/{k}  با lift>3%: {pos}  ==> {verdict}")
    return verdict, lifts


PAIRS = [
    ('chop', 'ar'),
    ('chop_fib_13', 'ar'),
    ('r2_fib_89', 'zscore_fib_233'),
    ('chop_fib_21', 'psy_fib_89'),
]


def run(asset='XAUUSD', tf='M5', direction='long'):
    print(f"=== S338c K-FOLD VERIFY {asset}/{tf} {direction} (k=5, walk-forward آستانه) ===")
    df = load(asset, tf)
    summary = []
    for a, b in PAIRS:
        try:
            v, _ = kfold_pair(df, asset, direction, a, b)
            summary.append((a, b, v))
        except Exception as e:
            print(f"ERR {a}×{b}: {e}")
            summary.append((a, b, 'ERR'))
    print("\n=== خلاصه ===")
    for a, b, v in summary:
        print(f"  {a:>16} × {b:<16} : {v}")


if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD',
        sys.argv[2] if len(sys.argv) > 2 else 'M5',
        sys.argv[3] if len(sys.argv) > 3 else 'long')
