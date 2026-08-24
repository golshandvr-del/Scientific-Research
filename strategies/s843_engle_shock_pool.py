# -*- coding: utf-8 -*-
"""
S843 — استخر خانوادگی شوک استانداردشدهٔ انگل (Family Pool of S840)
====================================================================
پیش‌ثبت: results/S843_PREREG_engle_shock_family_pool.md (کامیت‌شده پیش از این اجرا)
مسیر تعدد: B (استخر خانواده) — الگوی اثبات‌شدهٔ S431/S432.

اعضا (منجمد از checkpointهای IS کامیت‌شدهٔ S840 — عضویت کور به OOS):
  H3 (z2.618 follow slk1.618 rr1.272 hold34)
  H6 (z2.618 follow slk1.618 rr1.272 hold34)
  H8 (z2.618 follow slk1.618 rr1.0   hold34)
  H12(z2.058 follow slk1.272 rr1.0   hold34)
  D1 (z2.618 follow slk1.272 rr1.0   hold21)

روش (S431 کلمه‌به‌کلمه):
  • بازتولید معاملات هر عضو با queue_frozen روی کل داده.
  • FIFO غیرهمپوشان روی زمان تقویمی مطلق.
  • محور مصنوعی یکنواخت ۱ساعته (ضد BUG-AXIS/BUG-QUANT/BUG-SPAN)؛
    close محور از H1 با searchsorted(right)−1 (هیچ قیمت آینده به گذشته نمی‌نشیند).
  • holdout_mask = t_entry >= MAX(زمان‌های split ۵۰٪ اعضا).
  • null = blend_pool_null از nullهای OOS اندازه‌گیری‌شدهٔ S840 (perm_k=800)،
    وزن = سهم پس-از-FIFO.
  • n_trials رسمی = 59 (ارثی صادقانه) · حساسیت n_trials=1.
  • دقیقاً یک پیکربندی استخر — نتیجه هرچه بود ثبت می‌شود.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                    # noqa: E402
from engine import rqs2                                  # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402
from strategies.s840_engle_shock import (                # noqa: E402
    ASSET, TF_HOLD, SPLIT_FRAC, atr_series, ewma_z, signals_for, queue_frozen)

OUT = 'results/_scan_S843'
N_TRIALS_OFFICIAL = 59          # 54 (شبکهٔ IS S840) + 5 (داوری per-TF S840)
STEP_NS = 3600 * 1_000_000_000  # محور ۱ساعته (نانوثانیه)

# ----------------- اعضای منجمد (عیناً PREREG §۲) -----------------
MEMBERS = [
    dict(tf='H3',  z_thr=2.618, mode='follow', sl_k=1.618, rr=1.272),
    dict(tf='H6',  z_thr=2.618, mode='follow', sl_k=1.618, rr=1.272),
    dict(tf='H8',  z_thr=2.618, mode='follow', sl_k=1.618, rr=1.0),
    dict(tf='H12', z_thr=2.058, mode='follow', sl_k=1.272, rr=1.0),
    dict(tf='D1',  z_thr=2.618, mode='follow', sl_k=1.272, rr=1.0),
]


def reproduce_member(m):
    """بازتولید معاملات کامل عضو با هندسهٔ منجمد + زمان‌های تقویمی."""
    tf = m['tf']
    hold = TF_HOLD[tf]
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    warmup = 250 if n >= 5000 else max(60, n // 10)
    split = int(n * SPLIT_FRAC)
    t = df['time'].values.astype(np.int64) * 1_000_000_000   # ثانیه→ns
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr = atr_series(h, l, cl)
    z, _ = ewma_z(cl)
    sig, isl = signals_for(z, atr, m['z_thr'], m['mode'], warmup)
    st = queue_frozen(df, sig, isl, m['sl_k'] * atr[sig], hold, m['rr'])
    if st is None:
        return None
    eb = st['entry_bar'].astype(int)
    xb = np.minimum(st['exit_bar'].astype(int), n - 1)
    tr = pd.DataFrame(dict(
        pnl_pip=st['pnl'],
        outcome=np.where(st['win'], 'win', 'loss'),
        sl_pip=st['sl_pip'], tp_pip=st['tp_pip'],
        direction=np.where(st['is_long'], 'long', 'short'),
        t_entry=t[eb], t_exit=t[xb],
        src_card=tf,
    ))
    split_t = int(t[split])
    print(f"  [{tf}] reproduced n={len(tr)} WR={st['wr']:.2f}% "
          f"exp={st['exp']:+.3f}pip sl_med={np.median(st['sl_pip']):.1f} "
          f"split_time={np.datetime64(split_t, 'ns')}", flush=True)
    return dict(tf=tf, trades=tr, split_t=split_t,
                sl_med=float(np.median(st['sl_pip'])),
                tp_med=float(np.median(st['tp_pip'])))


def fifo_calendar(all_tr):
    """FIFO غیرهمپوشان روی زمان تقویمی مطلق: یک معامله در هر لحظه.

    مرتب‌سازی پایدار بر t_entry؛ معامله فقط اگر t_entry >= t_exit معاملهٔ باز
    قبلی باشد نگه داشته می‌شود (اولین رسیده، اولویت دارد — دقیقاً FIFO)."""
    df = all_tr.sort_values(['t_entry', 't_exit'],
                            kind='mergesort').reset_index(drop=True)
    keep = np.zeros(len(df), dtype=bool)
    open_until = -1
    te = df['t_entry'].values
    tx = df['t_exit'].values
    for i in range(len(df)):
        if te[i] >= open_until:
            keep[i] = True
            open_until = tx[i]
    return df[keep].reset_index(drop=True)


def blend_pool_null(members_used, pool_df):
    """ترکیب وزنی nullهای اندازه‌گیری‌شدهٔ اعضا؛ وزن = سهم پس-از-FIFO (S431)."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u, den_u = 0.0, 0.0
        num_m, num_s, den_p, kmin = 0.0, 0.0, 0.0, None
        for m in members_used:
            w = float(share.get(m['tf'], 0.0))
            if w <= 0:
                continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * w
                den_u += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * w
                num_s += (d['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = d.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f"{'=' * 88}\n=== S843 Engle-Shock FAMILY POOL :: {ASSET} "
          f"(members={[m['tf'] for m in MEMBERS]}) ===", flush=True)

    # -------- گام ۱: بازتولید اعضا --------
    reps = []
    for m in MEMBERS:
        r = reproduce_member(m)
        if r is None:
            print(f"  [{m['tf']}] NO TRADES — dropped", flush=True)
            continue
        # null اندازه‌گیری‌شدهٔ عضو از checkpoint کامیت‌شدهٔ S840
        ck = json.load(open(f'results/_scan_S840/{m["tf"]}.json'))
        r['null'] = ck['null']
        reps.append(r)

    all_tr = pd.concat([r['trades'] for r in reps], ignore_index=True)
    n_before = len(all_tr)

    # -------- گام ۲: FIFO تقویمی --------
    pool = fifo_calendar(all_tr)
    n_after = len(pool)
    print(f"\n[FIFO] n_before={n_before} → n_after={n_after} "
          f"(حذف همپوشانی: {100 * (1 - n_after / max(n_before, 1)):.1f}%)",
          flush=True)
    share = pool['src_card'].value_counts(normalize=True)
    print(f"[سهم پس-از-FIFO] {share.round(3).to_dict()}", flush=True)

    # -------- گام ۳: null ترکیبی + هندسهٔ وزنی --------
    null = blend_pool_null(reps, pool)
    print(f"[نول استخر] {json.dumps(null, ensure_ascii=False, default=str)}",
          flush=True)
    shares = share.to_dict()
    by_tf = {r['tf']: r for r in reps}
    sl_med = float(sum(by_tf[c]['sl_med'] * w for c, w in shares.items()))
    tp_med = float(sum(by_tf[c]['tp_med'] * w for c, w in shares.items()))
    print(f"[هندسهٔ وزنی] SL={sl_med:.1f}pip TP={tp_med:.1f}pip", flush=True)

    # -------- گام ۴: محور مصنوعی ۱ساعته + close از H1 --------
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f"[محور مشترک] ۱ساعته · {axis_dt[0]} → {axis_dt[-1]} "
          f"· {len(axis_t):,} سطل", flush=True)

    d_h1 = fd.load_fast(ASSET, 'H1')
    ref_t = d_h1['time'].astype(np.int64) * 1_000_000_000
    ref_c = np.asarray(d_h1['close'], dtype=np.float64)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.searchsorted(axis_t, pool['t_entry'].values, 'left')
    pool['exit_bar'] = np.searchsorted(axis_t, pool['t_exit'].values, 'left')
    pool['entry_bar'] = np.clip(pool['entry_bar'], 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(pool['exit_bar'], 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # -------- گام ۵: holdout روی زمان مطلق (PREREG §۳.۴) --------
    boundary = max(r['split_t'] for r in reps)
    te = pool['t_entry'].values.astype(np.int64)
    holdout = te >= boundary
    print(f"[holdout] boundary=MAX(splits)={np.datetime64(boundary, 'ns')} "
          f"· discovery={int((~holdout).sum())} · holdout={int(holdout.sum())}",
          flush=True)

    # -------- گام ۶: داوری RQS2 — رسمی n_trials=59 + حساسیت n_trials=1 --------
    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt,
                  null=null, close=axis_close, holdout_mask=holdout,
                  allow_overlap=False)
    res_official = rqs2.compute_rqs2(pool, ASSET,
                                     n_trials=N_TRIALS_OFFICIAL, **common)
    res_sens = rqs2.compute_rqs2(pool, ASSET, n_trials=1, **common)
    print(rqs2.format_rqs2('POOL OFFICIAL(n_t=59) ', res_official), flush=True)
    print(rqs2.format_rqs2('POOL SENS(n_t=1)     ', res_sens), flush=True)

    # -------- گام ۷: checkpoint --------
    def _slim(r):
        keep = dict(verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
                    gates={k: v for k, v in r.get('gates', {}).items()},
                    notes=r.get('notes'))
        mm = r.get('metrics', {})
        keep['metrics'] = {k: mm[k] for k in mm if isinstance(
            mm[k], (int, float, str, bool, type(None)))}
        return keep

    out = dict(
        asset=ASSET, members=[m for m in MEMBERS],
        n_before=n_before, n_after=n_after,
        share=share.round(4).to_dict(),
        sl_med=round(sl_med, 2), tp_med=round(tp_med, 2),
        null=null, boundary=str(np.datetime64(boundary, 'ns')),
        n_discovery=int((~holdout).sum()), n_holdout=int(holdout.sum()),
        pool_wr=round(float((pool['pnl_pip'] > 0).mean() * 100), 2),
        pool_exp=round(float(pool['pnl_pip'].mean()), 4),
        n_trials_official=N_TRIALS_OFFICIAL,
        rqs2_official=_slim(res_official),
        rqs2_sensitivity_nt1=_slim(res_sens),
    )
    with open(os.path.join(OUT, 'pool.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\ncheckpoint saved → {OUT}/pool.json", flush=True)
    print(f"\nVERDICT: {res_official.get('verdict')} "
          f"score={res_official.get('rqs2_score')}", flush=True)


if __name__ == '__main__':
    main()
