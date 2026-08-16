#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S880 — آزمونِ نهاییِ Path C روی **نیمهٔ دوم** (hold-out) — یک بار، فقط یک بار.

پیش‌ثبت: results/S880_PREREG_EntropyCollapse_PathC.md (commit 874f0a59)

ورودی: نامزدِ منتخبِ هر TF از results/_scan_S880/XAUUSD_<TF>.json ('best').
قواعدِ منجمد:
  - چندک‌های q30/q70: از نیمهٔ اول (فایلِ اسکن) — روی نیمهٔ دوم بازمحاسبه نمی‌شود.
  - هندسه: sl/tp پیپِ منجمدِ همان نامزد.
  - null: به سبکِ s351_verdict.build_null_side — WR بی‌قید + K=500 قرعهٔ
    هم‌اندازه/هم‌هندسه per-side، فقط داخلِ نیمهٔ دوم.
  - rqs2.compute_rqs2 با هر ۵ ورودیِ اختیاریِ اجباری. n_trials=72.
  - حکم را موتور صادر می‌کند.

usage: python3 strategies/s880_verdict.py <TF> [<TF> ...]
خروجی: results/_scan_S880/VERDICT_XAUUSD_<TF>.json
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2
from strategies.s880_entropy_collapse_scan import entropy_vec, build_events, wr_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = os.path.join(ROOT, 'results', '_scan_S880')
N_TRIALS = 72
N_PERM = 500


def null_side(df, side, n_side, sl, tp, hold, rng, n_perm=N_PERM):
    """null اندازه‌گیری‌شده per-side — ساختارِ کانونی (s351_verdict)."""
    d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
             perm_max=None, perm_k=None)
    n = len(df)
    lo, hi = 200, n - hold - 2
    if hi <= lo or n_side < 1:
        return d
    pool = np.arange(lo, hi)
    z = np.zeros(n, dtype=bool)
    # WR بی‌قید: همهٔ کندل‌های معتبر با گامِ نمونه‌برداری (سقف 20k برای سرعت)
    step = max(1, len(pool) // 20000)
    sig = np.zeros(n, dtype=bool); sig[pool[::step]] = True
    tr = se.simulate_trades(df, sig if side == 'long' else z,
                            z if side == 'long' else sig,
                            sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                            max_hold=hold, allow_overlap=False)
    w, m = wr_of(tr)
    d['uncond_wr'] = w
    wrs = []
    for _ in range(n_perm):
        pick = rng.choice(pool, size=min(n_side, len(pool)), replace=False)
        s2 = np.zeros(n, dtype=bool); s2[pick] = True
        t2 = se.simulate_trades(df, s2 if side == 'long' else z,
                                z if side == 'long' else s2,
                                sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                                max_hold=hold, allow_overlap=False)
        w2, m2 = wr_of(t2)
        if w2 is not None:
            wrs.append(w2)
    if wrs:
        a = np.asarray(wrs)
        d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                 perm_max=float(a.max()), perm_k=int(len(a)))
    return d


def judge_tf(tf):
    t0 = time.time()
    fp = os.path.join(SCAN, f'XAUUSD_{tf}.json')
    with open(fp) as f:
        scan = json.load(f)
    best = scan.get('best')
    out = {'tf': tf, 'candidate': best}
    if not best:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'no eligible IS candidate — hold-out untouched, no test spent'
        return out

    p, k, hold = best['p'], best['k'], best['hold']
    sl, tp = best['sl_pip'], best['tp_pip']
    q = scan['quantiles'][f'p{p}']
    q30, q70 = q['q30'], q['q70']

    d = fd.load_fast('XAUUSD', tf)
    out['src'] = d['src']
    df_all = fd.as_dataframe(d)
    half = scan['half_idx']
    # پنجرهٔ گرم‌سازی: p+k کندل قبل از مرز تا E روی اولین کندل‌های OOS تعریف باشد
    warm = p + k + 5
    df2 = df_all.iloc[half - warm:].reset_index(drop=True)
    close = df2['close'].values

    E = entropy_vec(close, p)
    ls, ss = build_events(E, close, p, k, q30, q70)
    # سیگنال‌های داخلِ ناحیهٔ گرم‌سازی حذف (متعلق به IS اند)
    ls[:warm] = False; ss[:warm] = False
    out['n_long_sig'] = int(ls.sum()); out['n_short_sig'] = int(ss.sum())

    trades = se.simulate_trades(df2, ls, ss, sl_pip=sl, tp_pip=tp,
                                asset='XAUUSD', max_hold=hold,
                                allow_overlap=False)
    wr, n = wr_of(trades)
    out['oos_n'] = n
    out['oos_wr'] = wr
    if n == 0:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'zero OOS trades'
        return out

    nl = int((trades['direction'] == 'long').sum())
    ns = n - nl
    rng = np.random.default_rng(880)
    null = {'long': null_side(df2, 'long', max(nl, 1), sl, tp, hold, rng),
            'short': null_side(df2, 'short', max(ns, 1), sl, tp, hold, rng)}
    out['null'] = null

    split_idx = len(df2) // 2   # برای H5 داخلِ خودِ OOS
    r = rqs2.compute_rqs2(trades, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                          bar_time=df2['time'].values, null=null,
                          n_trials=N_TRIALS, split_bar=split_idx,
                          close=df2['close'].values)
    out['verdict'] = r['verdict']
    out['rqs2_score'] = r['rqs2_score']
    out['gates'] = r['gates']
    out['metrics'] = {kk: (float(vv) if isinstance(vv, (int, float, np.floating)) else vv)
                      for kk, vv in r['metrics'].items()}
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def main():
    for tf in sys.argv[1:]:
        res = judge_tf(tf)
        fo = os.path.join(SCAN, f'VERDICT_XAUUSD_{tf}.json')
        def _default(o):
            if isinstance(o, (np.integer,)): return int(o)
            if isinstance(o, (np.floating,)): return float(o)
            if isinstance(o, np.ndarray): return o.tolist()
            if isinstance(o, np.bool_): return bool(o)
            return str(o)
        with open(fo, 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=_default)
        print(tf, '→', res.get('verdict'), res.get('rqs2_score'),
              'n=', res.get('oos_n'), 'wr=', res.get('oos_wr'), flush=True)


if __name__ == '__main__':
    main()
