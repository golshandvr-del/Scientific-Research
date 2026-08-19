#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S701 — استخرِ کارت‌های کندِ Aroon: نجاتِ رسمیِ لبهٔ کم‌توانِ S700
================================================================================
پیش‌ثبت: results/S701_PREREG_AROON_SLOWPOOL.md (commit 1045bccb — پیش از هر آزمون)

قفل‌شده‌ها (از پیش‌ثبت — هیچ انتخابِ تازه‌ای در این فایل نیست):
  سیگنال: aroon(55).shift(1) <= 78.6 < aroon(55) — فقط لانگ
  کاندیدِ اعضا: H1,H3,H6,H8,H12 (k_sl=2.0؛ H2 با α<0 حذفِ پیش‌ثبتی)
  انتخابِ اعضا: choose_homogeneous_subset روی آمارِ **نیمهٔ اول** (اسکنِ S700)
  SL(pip): H1:62.97 H3:110.11 H6:163.98 H8:197.94 H12:244.72 · TP=1.5×SL
  max_hold: H1/H3:64 · H6/H8/H12:32
  نول: اندازه‌گیری‌شده per-card روی کلِ داده، K=1000, SEED=701
  داوری: یک فراخوانیِ compute_rqs2 با holdout_mask و n_trials=600

درس‌های وام‌گرفته از S431:
  BUG-DEFAULTARG: مقدارِ پیش‌فرضِ add_margin در لحظهٔ تعریف قفل می‌شود ⇒
    برای خاموش‌کردنِ گزینشِ درون-pool_cards باید wrapper با آرگومانِ صریح داد.
  BUG-AXIS/BUG-QUANT/BUG-SPAN: محورِ تقویمیِ مشترک باید شبکهٔ مصنوعیِ
    یکنواختِ ابرمجموعهٔ افقِ استخر باشد، نه فایلِ هیچ کارتی.
  BUG-SPLITDIR: مرزِ hold-out روی زمانِ معاملات، نه نقطهٔ تقویمیِ خام —
    اینجا از پیش‌ثبت: بیشینهٔ زمانِ کندلِ n//2 اعضای **استفاده‌شده**.
"""
import sys, os, json, time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                # noqa: E402
from engine import rqs2                                              # noqa: E402
import engine.rqs2_pool as rp                                        # noqa: E402
from tools import s434_fast_data as fd                               # noqa: E402
import bottleneck as bn                                              # noqa: E402

SEED = 701
K_PERM = 1000
N_TRIALS = 600                       # 456 (شبکهٔ S700) + 144 (بازبینیِ تجمیعی)
PERIOD = 55
THR = 78.6
RR = 1.5
WARMUP = 200                         # همان حاشیهٔ اسکنِ S700

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s701')
os.makedirs(OUT, exist_ok=True)

# ---- مشخصاتِ منجمدِ اعضا (از اسکن‌های کامیت‌شدهٔ نیمهٔ اولِ S700) ----
MEMBERS = {
    'H1':  dict(sl_pip=62.97,  max_hold=64, n_search=355, alpha_search=0.972),
    'H3':  dict(sl_pip=110.11, max_hold=64, n_search=125, alpha_search=9.535),
    'H6':  dict(sl_pip=163.98, max_hold=32, n_search=69,  alpha_search=13.172),
    'H8':  dict(sl_pip=197.94, max_hold=32, n_search=49,  alpha_search=9.130),
    'H12': dict(sl_pip=244.72, max_hold=32, n_search=33,  alpha_search=5.615),
}


def aroon_fast(df, period):
    """همان تابعِ اثبات‌شدهٔ S700 (ممیزیِ هم‌ارزی: 0 عدمِ تطابق)."""
    h = df['high'].values.astype('float64')
    l = df['low'].values.astype('float64')
    n = len(h)
    bias = (np.arange(n, dtype='float64')[::-1]) * (0.004 / max(n, 1))
    h = h + bias
    l = l - bias
    w = period + 1
    since_max = bn.move_argmax(h, w)
    since_min = bn.move_argmin(l, w)
    up = 100.0 * (period - since_max) / period
    dn = 100.0 * (period - since_min) / period
    return pd.Series(up - dn, index=df.index)


def build_member(tf, spec, rng):
    """
    بازسازیِ معاملاتِ عضو روی **کلِ** داده با هندسهٔ منجمد + نولِ
    اندازه‌گیری‌شده (K=1000). checkpoint در results/_s701/.
    """
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    n = len(df)
    half = n // 2
    dt = df['time'].values.astype('datetime64[ns]')

    sl_pip, tp_pip = spec['sl_pip'], RR * spec['sl_pip']
    mh = spec['max_hold']

    a = aroon_fast(df, PERIOD)
    a_prev = a.shift(1)
    long_sig = ((a_prev <= THR) & (a > THR)).fillna(False)
    no_sig = pd.Series(False, index=df.index)

    tr = se.simulate_trades(df, long_sig, no_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset='XAUUSD', max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 3:
        return None
    if 'win' not in tr.columns:
        tr = tr.copy()
        tr['win'] = (tr['pnl_pip'].to_numpy() > 0).astype(int)

    # ---------- نولِ اندازه‌گیری‌شده: ورود در هر کندلِ معتبر ----------
    null_path = os.path.join(OUT, f'null_{tf}.json')
    if os.path.exists(null_path):
        with open(null_path) as fh:
            null = json.load(fh)
    else:
        lo, hi = WARMUP, n - mh - 2
        idx = np.arange(lo, hi)
        sig = np.zeros(n, dtype=bool)
        sig[idx] = True
        u_tr = se.simulate_trades(df, pd.Series(sig, index=df.index), no_sig,
                                  sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                  max_hold=mh, allow_overlap=True)
        wins = (u_tr['pnl_pip'].to_numpy() > 0).astype(np.float64)
        uncond_wr = float(wins.mean() * 100.0)
        # جای‌گشت: نمونه‌گیریِ n_long بدونِ جای‌گذاری از همان آرایهٔ برد/باخت
        n_long = int(len(tr))
        perms = np.empty(K_PERM)
        for k in range(K_PERM):
            take = rng.choice(len(wins), size=min(n_long, len(wins)),
                              replace=False)
            perms[k] = wins[take].mean() * 100.0
        null = {'long': dict(uncond_wr=uncond_wr,
                             perm_mean=float(perms.mean()),
                             perm_sd=float(perms.std(ddof=1)),
                             perm_max=float(perms.max()),
                             perm_k=int(K_PERM),
                             n_uncond=int(len(wins))),
                'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)}
        with open(null_path, 'w') as fh:
            json.dump(null, fh, ensure_ascii=False, indent=1)

    wr = float((tr['pnl_pip'] > 0).mean() * 100.0)
    lift_full = wr - null['long']['uncond_wr']

    m = dict(card=f'XAUUSD_{tf}', tf=tf, asset='XAUUSD', tr=tr, dt=dt,
             # ⚠️ lift برای گزینش/هم‌جهتی = αِ **نیمهٔ اول** (پیش‌ثبتی)؛
             # liftِ کل-داده فقط گزارش می‌شود، در هیچ گزینشی دخیل نیست.
             lift=float(spec['alpha_search']),
             lift_full_info=float(lift_full),
             null=null, n=int(len(tr)), wr=wr,
             sl_pip=float(sl_pip), tp_pip=float(tp_pip), max_hold=int(mh),
             exp_pip=float(tr['pnl_pip'].mean()),
             bars=int(n), half_bar=int(half),
             half_time_ns=int(dt[half].astype('datetime64[ns]').astype(np.int64)))
    with open(os.path.join(OUT, f'member_{tf}.json'), 'w') as fh:
        json.dump({k: v for k, v in m.items() if k not in ('tr', 'dt')},
                  fh, ensure_ascii=False, indent=1, default=str)
    return m


def blend_pool_null(members_used, pool_df):
    """همان الگوی S431: وزن = سهمِ پس-از-FIFO؛ واریانس روی وزن‌های مجذور."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u, den_u = 0.0, 0.0
        num_m, num_s, den_p, kmin = 0.0, 0.0, 0.0, None
        for m in members_used:
            w = float(share.get(m['card'], 0.0))
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
            perm_max=None,
            perm_k=kmin)
    return out


def main():
    print('== S701 — استخرِ کندِ Aroon · اعضا از پیش‌ثبت ==', flush=True)
    rng = np.random.default_rng(SEED)

    # ---- گامِ ۱: گزینشِ پیش‌ثبتی روی آمارِ نیمهٔ اول (نه کل-داده) ----
    cand = [dict(card=f'XAUUSD_{tf}', lift=s['alpha_search'], n=s['n_search'])
            for tf, s in MEMBERS.items()]
    sel = rp.choose_homogeneous_subset(cand)          # قاعدهٔ رسمیِ ماژول
    chosen_tfs = [c['card'].split('_')[1] for c in sel['chosen']]
    print(f"[گزینشِ نیمهٔ اول] chosen={chosen_tfs} · "
          f"z_chosen={sel['z_chosen']} z_full={sel['z_full']}", flush=True)
    print(f"   trace={json.dumps(sel['trace'], ensure_ascii=False)}", flush=True)
    with open(os.path.join(OUT, 'selection.json'), 'w') as fh:
        json.dump(sel, fh, ensure_ascii=False, indent=1, default=str)

    # ---- گامِ ۲: بازسازیِ اعضای برگزیده روی کلِ داده + نولِ K=1000 ----
    members = []
    for tf in chosen_tfs:
        t0 = time.time()
        m = build_member(tf, MEMBERS[tf], rng)
        if m is None:
            print(f'   {tf}: ناکافی — رد', flush=True)
            continue
        print(f"   {tf}: n_full={m['n']} WR={m['wr']:.2f} "
              f"uncond={m['null']['long']['uncond_wr']:.2f} "
              f"lift_full={m['lift_full_info']:+.2f}pp "
              f"exp={m['exp_pip']:+.1f}pip ({time.time()-t0:.0f}s)", flush=True)
        members.append(m)

    if len(members) < 2:
        print('[توقف] کمتر از دو عضو — تجمیع بی‌معناست ⇒ UNPROVEN.', flush=True)
        return

    # ---- گامِ ۳: تجمیع — گزینشِ درونی خاموش (BUG-DEFAULTARG-safe) ----
    # اعضا از پیش با آمارِ نیمهٔ اول گزینش شده‌اند؛ اجازهٔ گزینشِ دوباره با
    # آمارِ کل-داده = درجهٔ آزادیِ پس‌ازدیدن-داده ⇒ ممنوع.
    _orig = rp.choose_homogeneous_subset

    def _accept_all(cands, add_margin=None):
        return _orig(cands, add_margin=-1.0)

    try:
        rp.choose_homogeneous_subset = _accept_all
        res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                                  lift=m['lift']) for m in members])
    finally:
        rp.choose_homogeneous_subset = _orig
    if res is None:
        print('[توقف] pool_cards عضوی نیافت.', flush=True)
        return

    pool = res['pool']
    print(f"\n[تجمیع] n_before={res['n_before']} → n_after={res['n_after']} "
          f"(FIFO حذف: {100*(1-res['n_after']/max(res['n_before'],1)):.1f}%)",
          flush=True)
    share = pool['src_card'].value_counts(normalize=True)
    print(f"[سهمِ اعضا] {share.round(3).to_dict()}", flush=True)

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]

    # ---- گامِ ۴: نولِ ترکیبی + هندسهٔ وزنی ----
    null = blend_pool_null(used_members, pool)
    print(f"[نولِ استخر] {json.dumps(null, ensure_ascii=False, default=str)}",
          flush=True)
    shares = share.to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))

    # ---- گامِ ۵: محورِ مشترکِ مصنوعی (BUG-AXIS/QUANT/SPAN-safe) ----
    # ریزترین عضوِ ممکن H1 است ⇒ شبکهٔ ۱ساعته ابرمجموعهٔ کلِ افق.
    STEP_NS = 3600 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f"[محور] ۱ساعته · {axis_dt[0]} → {axis_dt[-1]} · {len(axis_t):,} سطل",
          flush=True)

    ref = fd.as_dataframe(fd.load_fast('XAUUSD', 'H1'))
    ref_t = ref['time'].values.astype('datetime64[ns]').astype(np.int64)
    ref_c = ref['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(axis_t, pool['t_entry'].values,
                                                'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(axis_t, pool['t_exit'].values,
                                               'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # ---- گامِ ۶: مرزِ hold-out پیش‌ثبتی (بیشینهٔ زمانِ کندلِ n//2 اعضا) ----
    split_ns = max(m['half_time_ns'] for m in used_members)
    te = pool['t_entry'].values.astype(np.int64)
    holdout = te >= split_ns
    print(f"[تقسیم] مرز={np.datetime64(split_ns, 'ns')} · "
          f"اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}",
          flush=True)

    # ---- گامِ ۷: داوری — یک فراخوانی، ورودیِ کامل ----
    r = rqs2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=axis_dt, null=null, close=axis_close,
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S701-POOL', r), flush=True)

    out = dict(selection=sel,
               members=[dict(card=m['card'], n=m['n'], wr=m['wr'],
                             lift_search=m['lift'],
                             lift_full=m['lift_full_info'],
                             exp_pip=m['exp_pip'], sl_pip=m['sl_pip'],
                             tp_pip=m['tp_pip'], max_hold=m['max_hold'])
                        for m in members],
               used=[u['card'] for u in res['used']],
               n_before=res['n_before'], n_after=res['n_after'],
               member_share={k: float(v) for k, v in shares.items()},
               sl_pip_w=sl_med, tp_pip_w=tp_med,
               null=null, split_ns=int(split_ns),
               n_explore=int((~holdout).sum()), n_holdout=int(holdout.sum()),
               n_trials=N_TRIALS, seed=SEED, k_perm=K_PERM,
               rqs2=r)
    with open(os.path.join(OUT, 'verdict.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print('\n[ذخیره] results/_s701/verdict.json', flush=True)


if __name__ == '__main__':
    main()
