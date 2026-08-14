# -*- coding: utf-8 -*-
"""
S500 — تجمیعِ H1+H4 مکانیزمِ Brooks Trend-Resumption (نسخهٔ علّیِ S356)
================================================================================
پیش‌ثبت: results/S500_PREREG_S354_H1H4_UNIFORM_POOLING.md (+ الحاقیهٔ ۱)
هر دو **پیش از این اسکریپت** commit شده‌اند. این اجرا هیچ پارامتری تنظیم
نمی‌کند؛ فقط قانونِ منجمد را روی دو عضوِ قفل‌شده اجرا و تجمیع را داوری می‌کند.

قانونِ منجمد (بیت‌به‌بیت از S356 ACCEPT):
    سیگنال: build_signals_causal(df, 'XAUUSD', tf, 0.13, late_hour=16, 0.8, 12.0)
    گیت:    r2_fib_55 >= 0.45  ·  جهت: فقط LONG
    هندسه:  SL = 1.3×ATR_pip(کارت) · TP = 2×SL · max_hold = 20 بار (پیش‌ثبت)
اعضای قفل‌شده (C2): XAUUSD-H1 و XAUUSD-H4 — نه حذف، نه افزودن.
بذر: 20260813 · K=2000 · n_trials = 97 (سخت‌گیرانه‌تر از 51ِ پیش‌ثبت: 96ِ
ارثیِ S356 + 1 برای تصمیمِ تجمیع؛ سفت‌کردن همیشه مجاز است، شل‌کردن هرگز).
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                               # noqa: E402
from engine import rqs2                                             # noqa: E402
from engine.rqs2 import n_required_for_h3                           # noqa: E402
from engine.rqs2_pool import pool_cards                             # noqa: E402
import engine.rqs2_pool as _rp                                      # noqa: E402
from strategies import s354_brooks_trend_resumption as base         # noqa: E402
from strategies.s354_causal_check import build_signals_causal       # noqa: E402
from strategies.s354_improve_long import build_null_canonical       # noqa: E402

OUT = 'results/_scan_S500'
ASSET = 'XAUUSD'
MEMBERS = ['H1', 'H4']              # C2: قفل‌شده در پیش‌ثبت
SEED = 20260813                     # بذرِ پیش‌ثبت‌شده
K_PERM = 2000                       # پیش‌ثبت‌شده
N_TRIALS = 97                       # 96 ارثیِ S356 + 1 تصمیمِ تجمیع (سخت‌گیرانه‌تر از پیش‌ثبت)
SPLIT_FRAC = 0.60                   # قاعدهٔ ارثیِ پروژه
SIG = dict(n_open_frac=0.13, late_hour=16, spike_k=0.8, tight_atr=12.0)
SL_K, RR, MAX_HOLD = 1.3, 2.0, 20   # منجمد از S356 / پیش‌ثبت


def _win_col(tr):
    if 'win' not in tr.columns:
        tr = tr.copy()
        tr['win'] = (tr['pnl_pip'].to_numpy() > 0).astype(int)
    return tr


def member_population(tf):
    """جمعیتِ یک عضو با قانونِ منجمد + نولِ اندازه‌گیری‌شدهٔ همان کارت."""
    df = se.load_data(os.path.join('data', f'{ASSET}_{tf}.csv'))
    atr_pip = base._atr_pip(df, ASSET, base.TF_ATR_P.get(tf, 34))
    sl = round(SL_K * atr_pip, 1)
    tp = round(RR * sl, 1)
    gate = base.regime_gate(df, ('r2_fib_55', 'ge', 0.45))
    sig = build_signals_causal(df, ASSET, tf,
                               SIG['n_open_frac'], SIG['late_hour'],
                               SIG['spike_k'], SIG['tight_atr']) & gate
    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp,
                            ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    if tr is None or len(tr) < 10:
        return None
    tr = _win_col(tr)

    # نولِ کانونیِ اندازه‌گیری‌شده (همان سازندهٔ S356)
    null = build_null_canonical(df, sig, sl, tp, MAX_HOLD,
                                n_perm=K_PERM, seed=SEED)
    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
    ref = null['long'].get('uncond_wr')
    lift = (wr - ref) if ref is not None else None
    return dict(card=f'{ASSET}_{tf}', asset=ASSET, tf=tf, tr=tr,
                dt=df['dt'].values, lift=lift, n=int(len(tr)), wr=wr,
                ref_wr=ref, null=null, sl_pip=float(sl), tp_pip=float(tp),
                max_hold=MAX_HOLD, n_signals=int(sig.sum()),
                exp_pip=float(np.mean(tr['pnl_pip'])), bars=int(len(df)))


def chi2_homogeneity(members):
    """آزمونِ χ²ِ 2×2 همگنیِ نرخِ برد (C1). p با erfc برای df=1."""
    from math import erfc, sqrt
    w = [int((m['tr']['pnl_pip'] > 0).sum()) for m in members]
    n = [m['n'] for m in members]
    l_ = [ni - wi for wi, ni in zip(w, n)]
    W, L, N = sum(w), sum(l_), sum(n)
    chi2 = 0.0
    for wi, li, ni in zip(w, l_, n):
        for obs, tot in ((wi, W), (li, L)):
            e = tot * ni / N
            if e > 0:
                chi2 += (obs - e) ** 2 / e
    p = erfc(sqrt(chi2 / 2.0))
    return chi2, p


def blend_pool_null(members_used, pool_df):
    """نولِ ترکیبی با وزنِ سهمِ پس-از-FIFO (روشِ اثبات‌شدهٔ S431)."""
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
    print(f'== S500 — تجمیعِ H1+H4 (قانونِ منجمدِ S356) · sig={SIG} '
          f'SLk={SL_K} RR={RR} mh={MAX_HOLD} · K={K_PERM} seed={SEED} ==',
          flush=True)

    # ---------- گامِ ۱: اعضا (checkpointِ اندک‌اندک) ----------
    members = []
    for tf in MEMBERS:
        print(f'\n-- عضو {ASSET}-{tf} --', flush=True)
        m = member_population(tf)
        if m is None:
            print('   معاملهٔ ناکافی — عضو ساخته نشد.', flush=True)
            continue
        print(f"   n={m['n']} WR={m['wr']:.2f} ref={m['ref_wr']:.2f} "
              f"lift={m['lift']:+.2f} exp={m['exp_pip']:+.2f}pip "
              f"SL={m['sl_pip']} TP={m['tp_pip']}", flush=True)
        with open(f'{OUT}/{ASSET}_{tf}_member.json', 'w', encoding='utf-8') as fh:
            json.dump({k: v for k, v in m.items() if k not in ('tr', 'dt')},
                      fh, ensure_ascii=False, indent=1, default=str)
        members.append(m)

    if len(members) < 2:
        print('\n[توقف] کمتر از دو عضو — تجمیع بی‌معناست ⇒ گام شکست‌خورده.',
              flush=True)
        return

    # آزمونِ ۱ (الحاقیهٔ ۱): بازتولیدِ H1 در ±۱۰٪ لنگرِ S356 (n=117, WR=51.28)
    h1 = next(m for m in members if m['tf'] == 'H1')
    rep_ok = (abs(h1['n'] - 117) <= 0.10 * 117) and (abs(h1['wr'] - 51.28) <= 0.10 * 51.28)
    print(f"\n[بازتولید H1] n={h1['n']} (لنگر 117) WR={h1['wr']:.2f} "
          f"(لنگر 51.28) ⇒ {'OK' if rep_ok else 'FAIL'}", flush=True)

    # آزمونِ مسافرِ مجانی (C5ِ بازتعریف‌شده): lift عضوِ H4 باید مثبت باشد
    h4 = next(m for m in members if m['tf'] == 'H4')
    print(f"[C5 مسافرِ مجانی] lift H4 = {h4['lift']:+.2f} ⇒ "
          f"{'OK' if h4['lift'] and h4['lift'] > 0 else 'FAIL'}", flush=True)

    # ---------- گامِ ۲: C1 همگنی ----------
    lifts = [m['lift'] for m in members]
    same_sign = all(x > 0 for x in lifts) or all(x < 0 for x in lifts)
    chi2, p_hom = chi2_homogeneity(members)
    print(f'\n[C1 همگنی] liftها={["%.2f" % x for x in lifts]} '
          f'هم‌علامت={same_sign} · χ²={chi2:.3f} p={p_hom:.4f} '
          f'(رد اگر p<0.05)', flush=True)
    c1_ok = same_sign and p_hom >= 0.05
    with open(f'{OUT}/c1_homogeneity.json', 'w', encoding='utf-8') as fh:
        json.dump(dict(lifts=lifts, same_sign=same_sign, chi2=chi2,
                       p=p_hom, ok=c1_ok), fh, ensure_ascii=False, indent=1)
    if not c1_ok:
        print('[C1 نقض] ⇒ تجمیع متوقف — REJECT.', flush=True)
        return

    # ---------- گامِ ۳: تجمیع (استخرِ FULL، بدونِ گزینشِ پس‌ازدیدن) ----------
    _orig = _rp.choose_homogeneous_subset

    def _choose_all(cands, add_margin=None):
        return _orig(cands, add_margin=-1.0)

    try:
        _rp.choose_homogeneous_subset = _choose_all
        res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                               lift=m['lift']) for m in members])
    finally:
        _rp.choose_homogeneous_subset = _orig
    if res is None:
        print('[توقف] استخر ساخته نشد.', flush=True)
        return

    pool = res['pool']
    drop_pct = 100 * (1 - res['n_after'] / max(res['n_before'], 1))
    print(f"\n[C3 تجمیع/FIFO] n_before={res['n_before']} → "
          f"n_eff={res['n_after']} (حذفِ همپوشانی {drop_pct:.1f}%)", flush=True)
    share = pool['src_card'].value_counts(normalize=True)
    print(f'[سهمِ اعضا] {share.round(3).to_dict()}', flush=True)

    # ---------- گامِ ۴: نولِ ترکیبی + سقفِ شیشه‌ای (الحاقیهٔ ۱) ----------
    used = [m for m in members if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used, pool)
    wr_pool = 100.0 * float((pool['pnl_pip'] > 0).mean())
    ref_pool = null['long']['uncond_wr']
    lift_pool = wr_pool - ref_pool
    n_req = n_required_for_h3(lift_pool, ref_pool / 100.0)
    glass_ok = res['n_after'] >= n_req
    print(f'\n[سقفِ شیشه‌ای] WR_pool={wr_pool:.2f} ref={ref_pool:.2f} '
          f'lift={lift_pool:+.2f} ⇒ n_required={n_req:.0f} در برابرِ '
          f"n_eff={res['n_after']} ⇒ {'قابلِ‌عبور' if glass_ok else 'GLASS'}",
          flush=True)

    # ---------- گامِ ۵: محورِ مشترک + هندسهٔ وزنی + تقسیمِ ارثی ----------
    shares = share.to_dict()
    by_card = {m['card']: m for m in used}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))

    STEP_NS = 5 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    bar_time = axis_t.astype('datetime64[ns]')
    ref_df = se.load_data('data/XAUUSD_H1.csv')
    ref_t = ref_df['dt'].values.astype('datetime64[ns]').astype(np.int64)
    ref_c = ref_df['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_entry'].values, 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_exit'].values, 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'[تقسیمِ ارثی {SPLIT_FRAC:.0%}] مرز={np.datetime64(split_ns, "ns")} '
          f'· اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}',
          flush=True)

    # ---------- گامِ ۶: داوریِ RQS2 v2.6 ----------
    r = rqs2.compute_rqs2(pool, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null, close=axis_close,
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S500-POOL', r), flush=True)

    out = dict(prereg='results/S500_PREREG_S354_H1H4_UNIFORM_POOLING.md',
               addendum='results/S500_PREREG_ADDENDUM_1_CAUSAL_ANCHOR.md',
               sig=SIG, sl_k=SL_K, rr=RR, max_hold=MAX_HOLD,
               seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS,
               reproduction_ok=bool(rep_ok),
               c1=dict(lifts=lifts, chi2=chi2, p=p_hom, ok=c1_ok),
               c5_h4_lift=h4['lift'],
               members=[dict(card=m['card'], n=m['n'], wr=m['wr'],
                             ref=m['ref_wr'], lift=m['lift'],
                             sl=m['sl_pip'], tp=m['tp_pip'],
                             exp_pip=m['exp_pip']) for m in members],
               n_before=res['n_before'], n_eff=res['n_after'],
               member_share=share.to_dict(),
               wr_pool=wr_pool, ref_pool=ref_pool, lift_pool=lift_pool,
               n_required=n_req, glass_ok=bool(glass_ok),
               sl_pip_med=sl_med, tp_pip_med=tp_med,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'))
    with open(f'{OUT}/pool_verdict.json', 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f'\n[saved] {OUT}/pool_verdict.json', flush=True)


if __name__ == '__main__':
    main()
