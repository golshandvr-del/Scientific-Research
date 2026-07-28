# -*- coding: utf-8 -*-
"""
s338b_interaction.py — کشفِ رژیمِ نادر از راهِ interactionِ دو-شرطی (قانونِ همکاریِ بهبود)

مسیرِ باقی‌ماندهٔ #۱ از S338: شاید هیچ اندیکاتورِ تک lift ندهد، ولی ترکیبِ ۲ شرطِ هم‌زمان
یک رژیمِ نادرِ واقعی بسازد. با همان گاردِ سختِ OOS می‌آزماییم.

روش:
  1) baseline مثل S338 (هر کندل، جهتِ ثابت، TP=SL).
  2) یک لیستِ منتخب از اندیکاتورهای «معنادار در IS» (از خروجیِ S338) به‌عنوان پایه.
     برای هرکدام، بهترین آستانه و side را از IS نگه می‌داریم → یک ماسکِ بولین می‌سازیم.
  3) همهٔ جفت‌های این ماسک‌ها را AND می‌کنیم و conditional-WR را در IS و OOS می‌سنجیم.
  4) فقط جفت‌هایی که در OOS هم WR>baseline+3 با n>=100 و p<0.05 → ROBUST.

نکته: چون از ماسک‌های ازپیش‌lift‌دار در IS استفاده می‌کنیم، این آزمونِ سخت‌گیرانه‌ای است؛
اگر ترکیبی در OOS دوام بیاورد، احتمالِ واقعی‌بودنش بالاست (interactionِ غیرِتصادفی).
"""
import sys
import numpy as np
from scipy import stats

from engine import scalp_engine as se
from engine import indicator_bank as ib

TF_BARS_PER_DAY = {'M1': 1440, 'M5': 288, 'M15': 96, 'M30': 48,
                   'H1': 24, 'H4': 6, 'D1': 1}


def load(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


def atr_pips(df, asset):
    atr = ib.compute('atr_fib_13', df)
    pip = se.ASSETS[asset]['pip']
    return (atr / pip).values


def build_baseline(df, asset, direction, k_atr=1.5, max_hold=24):
    n = len(df)
    atrp = atr_pips(df, asset)
    sl = float(np.nanmedian(atrp)) * k_atr
    long_sig = np.zeros(n, dtype=bool); short_sig = np.zeros(n, dtype=bool)
    if direction == 'long':
        long_sig[:] = True
    else:
        short_sig[:] = True
    tr = se.simulate_trades(df, long_sig, short_sig, sl, sl, asset,
                            max_hold=max_hold, allow_overlap=True)
    entry_idx = tr['entry_bar'].values
    win = (tr['pnl_pip'].values > 0)
    return entry_idx, win, sl


def binom_p(wins, n, p0=0.5):
    if n == 0:
        return 1.0
    phat = wins / n
    se_ = np.sqrt(p0 * (1 - p0) / n)
    if se_ == 0:
        return 1.0
    z = (phat - p0) / se_
    return 2.0 * (1.0 - stats.norm.cdf(abs(z)))


# منتخبِ اندیکاتورهای «lift‌دار در IS» از خروجیِ S338 (پایه‌های امیدوارکننده)
# side و منطق را از IS خودمان دوباره کشف می‌کنیم (تا generic بماند).
BASE_POOL = [
    'stc', 'chop', 'chop_fib_13', 'chop_fib_21', 'cmo_fib_21', 'cmo_fib_34',
    'roc_fib_21', 'dpo', 'dpo_fib_21', 'cr', 'ad', 'fdi', 'hurst', 'corr_t',
    'r2_fib_89', 'er_lucas_29', 'psy_fib_89', 'ar', 'zscore_fib_233',
    'natr', 'std_fib_13', 'waddah', 'roof', 'cg', 'mom_fib_8', 'ac',
]


def best_mask_for(name, vals_is, w_is, entry_vals, base_wr, min_frac=0.05):
    """بهترین (th, side) را در IS بیاب و ماسکِ کاملِ بولین (روی همهٔ entryها) برگردان."""
    v_is = vals_is
    ok = np.isfinite(v_is)
    if ok.sum() < 200:
        return None
    min_n = max(50, int(len(v_is) * min_frac))
    qs = np.percentile(v_is[ok], np.arange(5, 96, 5))
    best = None
    for th in qs:
        for side in ('gt', 'lt'):
            m = (v_is > th) if side == 'gt' else (v_is < th)
            nn = int(m.sum())
            if nn < min_n:
                continue
            wr = w_is[m].mean() * 100
            if wr <= base_wr + 2:
                continue
            if best is None or wr > best[0]:
                best = (wr, th, side)
    if best is None:
        return None
    _, th, side = best
    full = (entry_vals > th) if side == 'gt' else (entry_vals < th)
    return dict(name=name, th=float(th), side=side, mask=np.nan_to_num(full, nan=0).astype(bool))


def run(asset='XAUUSD', tf='M5', direction='long'):
    import time
    t0 = time.time()
    print(f"\n=== S338b INTERACTION {asset}/{tf} dir={direction} ===", flush=True)
    df = load(asset, tf)
    entry_idx, win, sl = build_baseline(df, asset, direction)
    base_wr = win.mean() * 100
    m = len(win); split = m // 2
    print(f"baseline WR={base_wr:.2f}% n={m} sl={sl:.1f}  هدف OOS>{base_wr+3:.0f}%\n", flush=True)

    # ماسکِ پایه برای هر اندیکاتورِ pool
    masks = []
    for name in BASE_POOL:
        try:
            vfull = ib.compute(name, df).shift(1).values
        except Exception:
            continue
        ev = vfull[entry_idx]
        vals_is = ev[:split]
        w_is = win[:split]
        # هم‌ترازسازیِ NaN در IS
        r = best_mask_for(name, vals_is, w_is, ev, base_wr)
        if r is not None:
            masks.append(r)
    print(f"ماسکِ پایهٔ معتبر: {len(masks)} ({time.time()-t0:.0f}s)\n", flush=True)

    w = win.astype(np.float64)
    results = []
    for i in range(len(masks)):
        for j in range(i + 1, len(masks)):
            a = masks[i]; b = masks[j]
            comb = a['mask'] & b['mask']
            comb_is = comb[:split]; comb_oos = comb[split:]
            n_is = int(comb_is.sum()); n_oos = int(comb_oos.sum())
            if n_is < 100 or n_oos < 100:
                continue
            wr_is = w[:split][comb_is].mean() * 100
            wins_oos = float(w[split:][comb_oos].sum())
            wr_oos = wins_oos / n_oos * 100
            p_oos = binom_p(wins_oos, n_oos)
            results.append(dict(a=a['name'], b=b['name'], n_is=n_is, wr_is=wr_is,
                                n_oos=n_oos, wr_oos=wr_oos, p_oos=p_oos,
                                score=min(wr_is, wr_oos)))
    results.sort(key=lambda r: (-r['score'], r['p_oos']))
    print(f"جفت‌های آزموده: {len(results)} ({time.time()-t0:.0f}s)\n", flush=True)
    print(f"{'A':>16} {'B':>16} {'WR_is':>6} {'n_is':>6} {'WR_oos':>6} {'n_oos':>6} {'p_oos':>8}")
    print("-" * 74)
    n_robust = 0
    for r in results[:30]:
        robust = (r['wr_oos'] > base_wr + 3) and (r['p_oos'] < 0.05) and (r['n_oos'] >= 100)
        flag = ' <== ROBUST' if robust else ''
        if robust:
            n_robust += 1
        print(f"{r['a']:>16} {r['b']:>16} {r['wr_is']:>6.1f} {r['n_is']:>6} "
              f"{r['wr_oos']:>6.1f} {r['n_oos']:>6} {r['p_oos']:>8.4f}{flag}")
    n_robust = sum(1 for r in results if (r['wr_oos'] > base_wr + 3) and (r['p_oos'] < 0.05) and (r['n_oos'] >= 100))
    print(f"\nROBUST (OOS lift, p<0.05, n>=100): {n_robust} از {len(results)} جفت")
    return results, base_wr


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    direction = sys.argv[3] if len(sys.argv) > 3 else 'long'
    run(asset, tf, direction)
