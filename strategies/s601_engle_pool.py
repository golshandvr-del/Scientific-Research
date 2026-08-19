# -*- coding: utf-8 -*-
"""
S601 — احیای S840 (شوکِ استانداردشدهٔ انگل) با تجمیعِ چندکارتیِ {D1,H8,H12,H6}
================================================================================
پیش‌ثبت: `results/S601_PREREG_ENGLE_SHOCK_MULTICARD_POOLING.md` (commit 214309ca،
**قبل** از اجرای این فایل). خلاصهٔ عهد:

  · نامزدها: چهار برندهٔ منجمدِ IS از `results/_scan_S840/*.json` — صفر جست‌وجو.
  · انتخابِ عضو: `choose_homogeneous_subset` با حاشیهٔ **رسمی** ۰.۱۵
    (رویهٔ ACCEPTهای S431/S432) — خروجی هرچه بود همان گزارش می‌شود.
  · نول: نول‌های اندازه‌گیری‌شدهٔ **منجمد** از checkpointهای S840 (perm_k=800/سمت،
    SEED=840) — نولِ جدید ساخته نمی‌شود؛ ترکیبِ وزنی به سهمِ پس-از-FIFO.
  · بودجه: n_trials=5136 (رسمی) + 8000 (تنش). حکم فقط از compute_rqs2 v2.6.
  · EURUSD مطلقاً آزموده نمی‌شود (استثنای صریحِ کاربر).

قلمروها (قانونِ کاربر: S500–S980 هر دهه یک دانشمند): S601 در دههٔ خودِ من
(S600–S609) است؛ از قلمروِ انگل (S840–S849) فقط مصنوعاتِ *نهایی‌شده* خوانده
می‌شود — هیچ فایلی از آن قلمرو تغییر نمی‌کند. پیش‌ثبتِ اول = مالکِ مفهوم
(سابقهٔ S870).

دفترِ باگ‌های S431 (رعایت از روزِ اول):
  · BUG-AXIS/BUG-SPAN: محورِ مشترک = شبکهٔ مصنوعیِ یکنواختِ H1 پوشا بر کلِ استخر.
  · BUG-SPLITDIR: مرزِ holdout = صدکِ ۶۰٪ زمانِ ورودِ معاملات.
  · BUG-DEFAULTARG: هیچ monkey-patch؛ add_margin پیش‌فرضِ رسمیِ خودِ ماژول.

سنجهٔ سلامت (بندِ ۱ پیش‌ثبت): n/WR کاملِ هر کارت باید با checkpointِ S840
بیت‌به‌بیت بخواند؛ کارتِ ناسازگار حذف و علت گزارش می‌شود.

اجرا:
    python3 strategies/s601_engle_pool.py
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, '.')

import numpy as np
import pandas as pd

from engine import rqs2 as R2
import engine.rqs2_pool as rp
from tools import s434_fast_data as fd

# منطقِ منجمدِ سیگنال/شبیه‌سازی — وارد می‌شود، بازنویسی نمی‌شود (زنجیرهٔ s601→s840)
from strategies.s840_engle_shock import (
    atr_series, ewma_z, signals_for, queue_frozen, trades_from_st, TF_HOLD)

import warnings
warnings.filterwarnings('ignore')

# ═════════════ ثابت‌های پیش‌ثبت‌شدهٔ S601 (بندهای ۱–۳) ═════════════
ASSET = 'XAUUSD'
CANDIDATES = ['D1', 'H8', 'H12', 'H6']            # ترتیبِ قدرت — قفل در پیش‌ثبت
SEED = 20260817                                    # بذرِ داوریِ پیش‌ثبت‌شده
N_TRIALS = 5136                                    # رسمی (سازگار با S600)
N_TRIALS_STRESS = 8000                             # تنش
SPLIT_FRAC = 0.60
OUT = 'results/_s601_engle_pool'
SCAN = 'results/_scan_S840'

# سنجهٔ سلامت: بازتولیدِ بیت‌به‌بیتِ checkpointِ S840 (کلِ داده، قانونِ منجمد)
EXPECTED = {'D1': dict(n=87, wr=64.37), 'H8': dict(n=337, wr=58.75),
            'H12': dict(n=450, wr=55.11), 'H6': dict(n=470, wr=50.43)}


def member_population(tf: str) -> dict | None:
    """جمعیتِ یک کارت: سیگنالِ منجمدِ برندهٔ IS + نولِ منجمدِ checkpoint."""
    t0 = time.time()
    ck = json.load(open(os.path.join(SCAN, f'{tf}.json')))
    w = ck['is_winner']
    hold = TF_HOLD[tf]
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n_bars = len(df)
    warmup = 250 if n_bars >= 5000 else max(60, n_bars // 10)

    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr = atr_series(h, l, cl)
    z, _ = ewma_z(cl)

    sig, isl = signals_for(z, atr, w['z_thr'], w['mode'], warmup)
    st = queue_frozen(df, sig, isl, w['sl_k'] * atr[sig], hold, w['rr'])
    if st is None or st['n'] < 5:
        print(f'-- {tf}: هیچ معامله‌ای — حذف.', flush=True)
        return None
    tr = trades_from_st(st)
    n, wr = int(len(tr)), float((tr['pnl_pip'] > 0).mean() * 100.0)

    exp = EXPECTED[tf]
    ok = (n == exp['n']) and (abs(wr - exp['wr']) < 0.01)
    print(f'-- {tf} src={ck["src"]}\n   frozen: z>={w["z_thr"]} {w["mode"]} '
          f'sl_k={w["sl_k"]} rr={w["rr"]} hold={hold}\n'
          f'   n={n} WR={wr:.2f} | S840 expected n={exp["n"]} WR={exp["wr"]} '
          f'⇒ {"✅ REPRODUCED" if ok else "❌ MISMATCH"} ({time.time()-t0:.0f}s)',
          flush=True)
    if not ok:
        print(f'   [حذف] {tf}: بازتولید شکست خورد (بندِ ۱ پیش‌ثبت).', flush=True)
        return None

    # نولِ منجمدِ checkpoint — به تفکیکِ سمت؛ lift کلِ کارت = WR − نولِ وزنی‌به‌سمت
    null = ck['null']
    n_long = int((tr['direction'] == 'long').sum())
    n_short = n - n_long
    ref = ((null['long']['perm_mean'] or 0.0) * n_long +
           (null['short']['perm_mean'] or 0.0) * n_short) / n
    lift = wr - ref
    print(f'   null(frozen): long={null["long"]["perm_mean"]:.2f} '
          f'short={null["short"]["perm_mean"]:.2f} → ref={ref:.2f} '
          f'lift={lift:+.2f}pp (L={n_long} S={n_short})', flush=True)

    dt = (pd.to_datetime(df['time'].values, unit='s', utc=True)
          .tz_localize(None).values.astype('datetime64[ns]'))
    return dict(card=f'{ASSET}-{tf}', tf=tf, tr=tr, dt=dt, n=n,
                wr=round(wr, 2), ref_wr=round(ref, 4), lift=round(lift, 4),
                null=null, n_long=n_long, n_short=n_short,
                sl_pip=float(np.median(tr['sl_pip'])),
                tp_pip=float(np.median(tr['tp_pip'])),
                hold=hold, winner=w, data_src=ck['src'],
                exp_pip=float(tr['pnl_pip'].mean()), bars=n_bars)


def blend_pool_null(members_used, pool_df):
    """نولِ استخر: ترکیبِ وزنیِ نول‌های منجمدِ اعضا با سهمِ پس-از-FIFO (الگوی S431)."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0
        kmin = None
        for m in members_used:
            wgt = float(share.get(m['card'], 0.0))
            if wgt <= 0:
                continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * wgt
                den_u += wgt
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * wgt
                num_s += (d['perm_sd'] ** 2) * (wgt ** 2)
                den_p += wgt
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
    print(f'== S601 — تجمیعِ شوکِ انگل · نامزدها={CANDIDATES} · seed={SEED} '
          f'n_trials={N_TRIALS} (تنش {N_TRIALS_STRESS}) ==', flush=True)

    # ---------------- گامِ ۱: جمعیتِ اعضا + checkpoint ----------------
    members = []
    for tf in CANDIDATES:
        m = member_population(tf)
        if m is None:
            continue
        with open(os.path.join(OUT, f'{tf}_member.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump({k: v for k, v in m.items() if k not in ('tr', 'dt')},
                      fh, ensure_ascii=False, indent=1, default=str)
        members.append(m)
    if len(members) < 2:
        print('[توقف] کمتر از ۲ عضوِ بازتولیدشده — تجمیع بی‌معناست.', flush=True)
        return

    print('\n[liftها] ' +
          ' · '.join(f'{m["tf"]}={m["lift"]:+.2f}' for m in members), flush=True)

    # ------- گامِ ۲: انتخابِ همگن (حاشیهٔ رسمی ۰.۱۵) + FIFO تقویمی -------
    res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                              lift=m['lift']) for m in members])
    if res is None:
        print('[توقف] pool_cards هیچ عضوِ معتبری نیافت.', flush=True)
        return
    print(f'[انتخاب‌گر] trace='
          f'{json.dumps(res["selection"]["trace"], ensure_ascii=False)}',
          flush=True)
    print(f'[حذف‌شده‌ها] {res["dropped"]}', flush=True)

    pool = res['pool']
    fifo_cut = 100 * (1 - res['n_after'] / max(res['n_before'], 1))
    print(f'[تجمیع] n_before={res["n_before"]} → n_after={res["n_after"]} '
          f'(حذفِ FIFO: {fifo_cut:.1f}%)', flush=True)
    share = pool['src_card'].value_counts(normalize=True)
    print(f'[سهمِ اعضا] {share.round(3).to_dict()}', flush=True)

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f'[نولِ استخر] long={null["long"]} short={null["short"]}', flush=True)

    # ---- هندسهٔ استخر: مدیانِ وزنی به سهمِ پس-از-FIFO (الگوی S431) ----
    shares = share.to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))
    print(f'[هندسهٔ استخر] SL={sl_med:.1f} TP={tp_med:.1f} '
          f'RR={tp_med/max(sl_med,1e-9):.3f}', flush=True)

    # ---- محورِ مشترک: شبکهٔ H1 (BUG-AXIS/BUG-SPAN) + close از H1 برای H10 ----
    STEP_NS = 60 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f'[محورِ مشترک] H1 · {axis_dt[0]} → {axis_dt[-1]} · '
          f'{len(axis_t):,} سطل', flush=True)

    d1h = fd.load_fast(ASSET, 'H1')
    ref_t = (pd.to_datetime(d1h['time'], unit='s', utc=True)
             .tz_localize(None).values.astype('datetime64[ns]')
             .astype(np.int64))
    ref_c = d1h['close'].astype(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1,
                  0, len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_entry'].values.astype(np.int64),
                        'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_exit'].values.astype(np.int64),
                        'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # ---- holdout: صدکِ ۶۰٪ زمانِ ورود (BUG-SPLITDIR) ----
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'[تقسیمِ {SPLIT_FRAC:.0%}] مرز={np.datetime64(split_ns, "ns")} · '
          f'اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}',
          flush=True)

    # ---------------- گامِ ۳: داوریِ RQS2 v2.6 (رسمی + تنش) ----------------
    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt, null=null,
                  close=axis_close, holdout_mask=holdout, allow_overlap=False)
    r = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS, **common)
    r_st = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print('\n' + R2.format_rqs2('S601-POOL OFFICIAL', r), flush=True)
    print(R2.format_rqs2(f'S601-POOL STRESS({N_TRIALS_STRESS})', r_st),
          flush=True)

    def _slim(rr_):
        m = rr_.get('metrics', {})
        return dict(verdict=rr_.get('verdict'),
                    rqs2_score=rr_.get('rqs2_score'),
                    gates=rr_.get('gates'), notes=rr_.get('notes'),
                    metrics={k: m[k] for k in m if isinstance(
                        m[k], (int, float, str, bool, type(None)))})

    out = dict(session='S601',
               prereg='results/S601_PREREG_ENGLE_SHOCK_MULTICARD_POOLING.md',
               members=[dict(card=m['card'], n=m['n'], wr=m['wr'],
                             ref_wr=m['ref_wr'], lift=m['lift'],
                             n_long=m['n_long'], n_short=m['n_short'],
                             sl_pip=round(m['sl_pip'], 2),
                             tp_pip=round(m['tp_pip'], 2), hold=m['hold'],
                             winner=m['winner'], data_src=m['data_src'],
                             exp_pip=round(m['exp_pip'], 3))
                        for m in members],
               selection=res['selection'],
               used=[u['card'] for u in res['used']], dropped=res['dropped'],
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2),
               member_share=share.round(4).to_dict(),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, seed=SEED,
               n_trials=N_TRIALS, n_trials_stress=N_TRIALS_STRESS,
               split_frac=SPLIT_FRAC,
               split_utc=str(np.datetime64(split_ns, 'ns')),
               official=_slim(r), stress=_slim(r_st),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'))
    with open(os.path.join(OUT, 'pool_verdict.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f'\n[saved] {OUT}/pool_verdict.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
