# -*- coding: utf-8 -*-
"""
S851-POOL — نجاتِ پیش‌ثبت‌شده‌ی تجمیع برای کارت‌های POWER-LIMITED
================================================================================
پیش‌ثبت: results/S851_PREREG_CUSUM_BREAKPOINT.md §6 (commit f7c1adb0 — قبل از
دیدنِ نتایجِ کارت‌ها): «اگر ≥۲ کارتِ TF حکمِ POWER-LIMITED گرفتند، معاملاتشان
با engine/rqs2_pool.py ادغام و حکمِ استخر جداگانه گزارش می‌شود. هیچ نجاتِ
دیگری مجاز نیست.»

وضعیت: H6 = POWER-LIMITED (19.3)، H12 = POWER-LIMITED (21.4) ⇒ شرط برقرار.
(H8 با حکم REJECT واجدِ شرایط نیست — طبق متنِ پیش‌ثبت فقط POWER-LIMITED.)

روش (الگوی اثبات‌شده‌ی S431):
  ۱) بازتولیدِ قطعیِ معاملاتِ هر کارت با پارامترهای judged از چک‌پوینت.
  ۲) lift هر کارت نسبت به نولِ اندازه‌گیری‌شده‌ی خودش (از چک‌پوینت).
  ۳) pool_cards: هم‌جهتی + همگنی + FIFO تقویمی.
  ۴) محورِ مصنوعیِ یکنواختِ ۱ساعته روی افقِ کاملِ استخر (درسِ BUG-SPAN/BUG-QUANT).
  ۵) closeِ محور از H1 با نگهداشتِ آخرین مقدار (بدونِ آینده‌بینی).
  ۶) تقسیمِ ارثی: صدکِ ۶۰٪ زمانِ ورود ⇒ holdout_mask (درسِ BUG-SPLITDIR).
  ۷) یک فراخوانِ compute_rqs2 — حکم عیناً.
"""
import sys
import os
import json

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from engine.rqs2_pool import pool_cards                             # noqa: E402
from strategies.s348_rr_sweep import trades_df                      # noqa: E402
from strategies.s851_cusum_breakpoint import (                      # noqa: E402
    ASSET, MAX_HOLD, N_TRIALS, SPLIT_FRAC, atr_series, zscores,
    cusum_signals, combo_trades)
from tools import s434_fast_data as fd                              # noqa: E402

SCAN = 'results/_scan_S851'
OUT = 'results/_scan_S851/POOL.json'
CARDS = ('H6', 'H12')            # فقط POWER-LIMITEDها — طبق پیش‌ثبت §6
STEP_NS = 3600 * 1_000_000_000   # محور مصنوعی ۱ساعته (ریزترین کارت = H6)


def member(tf):
    """بازتولیدِ قطعیِ معاملاتِ کارت + lift از نولِ ذخیره‌شده."""
    ck = json.load(open(os.path.join(SCAN, f'{tf}.json')))
    j = ck['judged']
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    close = df['close'].values.astype(np.float64)
    pip = se.ASSETS[ASSET]['pip']
    warmup = max(34 + 2, 100)
    atr = atr_series(df)
    z = zscores(close)
    ls, ss = cusum_signals(z, j['kd'], j['h'])
    ls[:warmup] = False
    ss[:warmup] = False
    st = combo_trades(df, ls, ss, atr, j['k'], j['rr'], warmup,
                      n - MAX_HOLD - 2, pip)
    assert st is not None and st['n'] == j['n'], \
        f"{tf}: reproduction mismatch n={None if st is None else st['n']} vs {j['n']}"
    tr = trades_df(st)
    # محورِ تقویمیِ کارت (epoch ثانیه → datetime64[ns])
    dt = (np.asarray(d['time'], dtype=np.int64) * 1_000_000_000
          ).astype('datetime64[ns]')
    # lift وزنی به سمت نسبت به نولِ اندازه‌گیری‌شده‌ی ذخیره‌شده
    null = ck['null']
    nL = j['n_long']
    nS = j['n_short']
    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
    refs, wts = [], []
    for side, cnt in (('long', nL), ('short', nS)):
        u = null[side].get('uncond_wr')
        if u is not None and cnt > 0:
            refs.append(u * cnt)
            wts.append(cnt)
    ref = (sum(refs) / sum(wts)) if wts else None
    lift = (wr - ref) if ref is not None else None
    print(f"  [{tf}] n={j['n']} wr={wr:.2f} ref={ref:.2f} lift={lift:+.2f} "
          f"sl_med={j['sl_med']} tp_med={j['tp_med']}", flush=True)
    return dict(card=tf, tr=tr, dt=dt, lift=lift, null=null,
                n=int(len(tr)), sl_pip=j['sl_med'], tp_pip=j['tp_med'])


def blend_null(members_used, pool_df):
    """نولِ استخر = ترکیبِ وزنیِ نول‌های اعضا با وزنِ سهمِ پس-از-FIFO (الگوی S431)."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0
        kmin = None
        for m in members_used:
            w = float(share.get(m['card'], 0.0))
            if w <= 0:
                continue
            dd = m['null'][side]
            if dd.get('uncond_wr') is not None:
                num_u += dd['uncond_wr'] * w
                den_u += w
            if dd.get('perm_mean') is not None and dd.get('perm_sd') is not None:
                num_m += dd['perm_mean'] * w
                num_s += (dd['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = dd.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def main():
    print('=== S851-POOL: pre-registered pooling rescue (H6 + H12) ===',
          flush=True)
    members = [member(tf) for tf in CARDS]

    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                           lift=m['lift']) for m in members])
    if res is None:
        print('[STOP] pool_cards returned None', flush=True)
        return
    pool = res['pool']
    print(f"\n[pool] n_before={res['n_before']} → n_after={res['n_after']} "
          f"used={[u['card'] for u in res['used']]} "
          f"dropped={[(d['card'], d['reason']) for d in res['dropped']]}",
          flush=True)
    print(f"[selection] {json.dumps(res['selection']['trace'])}", flush=True)

    used = [m for m in members
            if m['card'] in {u['card'] for u in res['used']}]
    null = blend_null(used, pool)
    print(f'[pool null] {json.dumps(null)}', flush=True)

    # هندسه‌ی استخر: مدیانِ وزنی به سهمِ پس-از-FIFO
    share = pool['src_card'].value_counts(normalize=True).to_dict()
    by = {m['card']: m for m in used}
    sl_med = sum(by[c]['sl_pip'] * w for c, w in share.items() if c in by)
    tp_med = sum(by[c]['tp_pip'] * w for c, w in share.items() if c in by)

    # محورِ مصنوعیِ یکنواخت + close هم‌راستا (درس‌های BUG-AXIS/SPAN/QUANT)
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    dh = fd.load_fast(ASSET, 'H1')
    ref_t = (np.asarray(dh['time'], dtype=np.int64) * 1_000_000_000)
    ref_c = np.asarray(dh['close'], dtype=np.float64)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]
    print(f'[axis] 1h grid {axis_dt[0]} → {axis_dt[-1]} ({len(axis_t):,} bins)',
          flush=True)

    pool = pool.copy()
    pool['entry_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_entry'].values.astype(np.int64),
                        'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_exit'].values.astype(np.int64),
                        'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # تقسیمِ ارثی ۶۰/۴۰ روی صدکِ زمانِ ورود (درسِ BUG-SPLITDIR)
    te = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te, SPLIT_FRAC))
    holdout = te >= split_ns
    print(f'[split 60%] boundary={np.datetime64(split_ns, "ns")} '
          f'explore={int((~holdout).sum())} holdout={int(holdout.sum())}',
          flush=True)

    r = rqs2.compute_rqs2(pool, ASSET, sl_pip=float(sl_med),
                          tp_pip=float(tp_med), bar_time=axis_dt,
                          null=null, close=axis_close,
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S851-POOL', r), flush=True)
    print(f"gates: {r['gates']}", flush=True)

    out = dict(cards=list(CARDS),
               members=[dict(card=m['card'], n=m['n'], lift=m['lift'])
                        for m in members],
               used=[u['card'] for u in res['used']],
               dropped=res['dropped'], selection=res['selection'],
               n_before=res['n_before'], n_after=res['n_after'],
               member_share=share, sl_pip_med=float(sl_med),
               tp_pip_med=float(tp_med), n_trials=N_TRIALS,
               split_ns=split_ns,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))

    def clean(x):
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating,)):
            return None if not np.isfinite(x) else float(x)
        if isinstance(x, np.bool_):
            return bool(x)
        if isinstance(x, np.ndarray):
            return None
        return x

    with open(OUT, 'w') as f:
        json.dump(clean(out), f, indent=1, ensure_ascii=False)
    print(f'✓ saved {OUT}', flush=True)


if __name__ == '__main__':
    main()
