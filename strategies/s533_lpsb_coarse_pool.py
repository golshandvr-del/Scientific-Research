# -*- coding: utf-8 -*-
"""
S533 — احیای LPSB خام روی TFهای درشت با تجمیع {H6,H8,H12,D1}
================================================================================
پیش‌ثبت: `results/S533_PREREG_LPSB_CoarseTF_Pool.md` (commit 8a01754d —
**قبل** از نوشتنِ این فایل و قبل از هر محاسبه).

فرضیهٔ H_pool: لبهٔ جهتی LPSB که D1 نشان داد (S351: REJECT 29، فقط H3 قرمز،
lift=+13.9pp، n=74 — سقفِ شیشه‌ای) در همسایه‌های **بکر** H6/H8/H12 هم حاضر
است؛ تجمیعِ تقویمیِ FIFO چهار کارت n را به مرتبهٔ چند صد می‌رساند.

صفر پارامترِ آزاد:
  • سیگنال: عضوِ مرکزیِ پیش‌ثبت‌شدهٔ S351 (L=8, f=0.33)، هر دو جهت.
  • هندسه: SL=1.618·ATR21، RR=1.618، hold=12 (قانونِ قفلِ سه‌گانهٔ S351).
  • کارت‌ها: XAUUSD-{H6,H8,H12,D1} — فهرست پیش از دیدنِ هر عدد قفل است.

قواعدِ صداقت (میراثِ S431):
  • ISSUE-C2: حکمِ اصلی روی استخرِ FULL (بدونِ گزینشِ پس‌ازدیدن-داده).
  • BUG-DEFAULTARG: wrapper برای add_margin=-1.0 (پیش‌فرضِ تابع قفل است).
  • BUG-SPLITDIR: holdout = صدکِ ۶۰٪ِ **زمانِ ورودِ معاملات**، نه تقویم.
  • BUG-AXIS/QUANT/SPAN: محورِ مشترکِ مصنوعی، رزولوشن ریزتر از ریزترین کارت.
  • قانونِ اندک‌اندک: checkpoint هر کارت بی‌درنگ.
  • قانونِ توقف: <۲ عضو با lift>0 ⇒ STOPPED_DEAD بدونِ خرجِ holdout.
  • امتناع از اجرای دوم اگر verdict.json موجود باشد.

چندگانگیِ صادقانه: n_trials = 141 (135 اسکنِ S351 + 4 جمعیتِ کارت +
1 تصمیمِ تجمیع + 1 حکم). K=2000، SEED=20260817.
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                               # noqa: E402
from engine import rqs2                                             # noqa: E402
from engine.rqs2_pool import pool_cards                              # noqa: E402
from strategies.s351_lpsb import atr_series, GEO_SL_K                # noqa: E402
from strategies.s351_verdict import (member_trades, build_null_side,  # noqa: E402
                                     CENTRAL)
from strategies.s348_rr_sweep import trades_df                       # noqa: E402

OUT = 'results/_s533'

# ---------------------- اعضای استخر (قفل‌شده در پیش‌ثبت) ----------------------
POOL_MEMBERS = ['XAUUSD_H6', 'XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1']
DATA = {c: f"data/mt5_full/{c}.csv" for c in POOL_MEMBERS}

SEED = 20260817                         # بذرِ پیش‌ثبت‌شده
K_PERM = 2000                           # K پیش‌ثبت‌شده
SPLIT_FRAC = 0.60                       # تقسیمِ ارثی
N_TRIALS = 141                          # چندگانگیِ صادقانهٔ پیش‌ثبت‌شده
C5_MAX_MEMBER_SHARE = 0.50              # سقفِ سهمِ عضو
MIN_SPAN_YEARS = 14.0                   # گاردِ DATASETDRIFT (دادهٔ کامل)


def card_population(card, n_perm=K_PERM, verbose=True):
    """جمعیتِ یک کارت = LPSB خامِ عضوِ مرکزی با هندسهٔ منجمدِ S351."""
    asset = 'XAUUSD'
    path = DATA[card]
    if not os.path.exists(path):
        print(f'   [خطا] دادهٔ {path} یافت نشد', flush=True)
        return None

    df = se.load_data(path)
    n = len(df)
    dt = df['dt'].values
    span_y = (dt[-1] - dt[0]) / np.timedelta64(1, 'D') / 365.25
    if span_y < MIN_SPAN_YEARS:
        raise RuntimeError(f'DATASETDRIFT: {card} span={span_y:.1f}y < '
                           f'{MIN_SPAN_YEARS}y — دادهٔ کامل نیست')

    atr = atr_series(df)                                    # ATR21 (Wilder)
    warmup = max(4 * (2 * CENTRAL['L'] + 1), 250)           # پیش‌فرضِ ارثی

    st = member_trades(df, atr, asset, CENTRAL['L'], CENTRAL['f'], warmup)
    if st is None or st['n'] < 3:
        print(f'   [رد] {card}: معاملهٔ ناکافی', flush=True)
        return None
    tr = trades_df(st)

    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))

    # ---- مبنای اندازه‌گیری‌شده با همان هندسهٔ شناور (نه ۵۰٪ فرضی) ----
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[valid >= warmup]
    rng = np.random.default_rng(SEED)
    null = build_null_side(df, asset, valid, GEO_SL_K * atr, nL, nS,
                           n_perm, rng, verbose=verbose)

    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
    refs, wts = [], []
    for side, cnt in (('long', nL), ('short', nS)):
        u = null[side].get('uncond_wr')
        if u is not None and cnt > 0:
            refs.append(u * cnt)
            wts.append(cnt)
    ref = (sum(refs) / sum(wts)) if wts else None
    lift = (wr - ref) if ref is not None else None

    return dict(card=card, asset=asset, tr=tr, dt=dt, lift=lift,
                n=int(len(tr)), wr=wr, ref_wr=ref, null=null,
                n_long=nL, n_short=nS,
                sl_pip=sl_med, tp_pip=tp_med,
                exp_pip=float(np.mean(tr['pnl_pip'])),
                span_years=float(span_y), bars=int(n))


def blend_pool_null(members_used, pool_df):
    """نولِ استخر = ترکیبِ وزنیِ نول‌های اعضا با سهمِ پس-از-FIFO (الگوی S431)."""
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
                num_s += (d['perm_sd'] ** 2) * (w ** 2)   # واریانس با w²
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
    ap = argparse.ArgumentParser()
    ap.add_argument('--perm', type=int, default=K_PERM)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    # ---- امتناع از اجرای دوم (پروتکل §۵ بند ۴) ----
    vpath = os.path.join(OUT, 'verdict.json')
    if os.path.exists(vpath):
        print(f'[امتناع] {vpath} موجود است — حکم قبلاً صادر شده. '
              'اجرای دوم ممنوع.', flush=True)
        sys.exit(2)

    print(f'== S533 — استخرِ LPSB درشت‌دانه · اعضا: {POOL_MEMBERS} ==',
          flush=True)
    print(f'   عضو={CENTRAL} · هندسه: SL=1.618·ATR21, RR=1.618, hold=12 '
          f'· K={a.perm} · seed={SEED} · n_trials={N_TRIALS}', flush=True)

    members = []
    for card in POOL_MEMBERS:
        print(f'\n-- کارتِ {card} --', flush=True)
        m = card_population(card, n_perm=a.perm)
        if m is None:
            continue
        print(f"   n={m['n']} (L={m['n_long']}/S={m['n_short']}) "
              f"WR={m['wr']:.2f} ref={m['ref_wr']:.2f} lift={m['lift']:+.2f} "
              f"exp={m['exp_pip']:+.2f}pip SL~{m['sl_pip']:.0f}pip "
              f"span={m['span_years']:.1f}y", flush=True)
        # checkpointِ اندک‌اندک — بی‌درنگ روی دیسک
        with open(os.path.join(OUT, f'{card}_member.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump({k: v for k, v in m.items() if k not in ('tr', 'dt')},
                      fh, ensure_ascii=False, indent=1, default=str)
        members.append(m)

    # ---- قانونِ توقفِ پیش‌ثبت‌شده ----
    pos = [m for m in members if m['lift'] is not None and m['lift'] > 0]
    print(f'\n[قانونِ توقف] اعضای lift>0: '
          f'{[(m["card"], round(m["lift"], 2)) for m in pos]}', flush=True)
    virgin_pos = [m for m in pos if m['card'] != 'XAUUSD_D1']
    print(f'[P1] کارت‌های بکرِ lift>0: {[m["card"] for m in virgin_pos]} '
          f'از {["XAUUSD_H6", "XAUUSD_H8", "XAUUSD_H12"]}', flush=True)
    if len(pos) < 2:
        out = dict(status='STOPPED_DEAD',
                   reason='<2 اعضای lift>0 — استخرِ تک‌عضوی = تکرارِ S351؛ '
                          'حکمِ رسمی صادر نمی‌شود (مرگِ صادقانه)',
                   members=[dict(card=m['card'], n=m['n'], lift=m['lift'],
                                 wr=m['wr']) for m in members])
        with open(os.path.join(OUT, 'stopped_dead.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
        print('\n[STOPPED_DEAD] فرضیهٔ شیبِ فراکتالیِ کیفیت مرده — '
              'بدونِ خرجِ holdout.', flush=True)
        return

    # ---- تجمیع: SELECTED (موتوری) + FULL (حکمِ اصلی؛ ISSUE-C2) ----
    payload = [dict(card=m['card'], tr=m['tr'], dt=m['dt'], lift=m['lift'])
               for m in members]
    res_sel = pool_cards(payload)
    if res_sel is None:
        print('[توقف] pool_cards هیچ عضوِ معتبری نیافت.', flush=True)
        return

    # BUG-DEFAULTARG: پیش‌فرضِ add_margin در لحظهٔ تعریف قفل شده ⇒ wrapper
    import engine.rqs2_pool as _rp
    _orig_choose = _rp.choose_homogeneous_subset

    def _choose_all(cands, add_margin=None):
        return _orig_choose(cands, add_margin=-1.0)

    try:
        _rp.choose_homogeneous_subset = _choose_all
        res_full = pool_cards(payload)
    finally:
        _rp.choose_homogeneous_subset = _orig_choose

    if res_full is None:
        print('[توقف] استخرِ FULL ساخته نشد.', flush=True)
        return

    print(f"\n[ISSUE-C2] SELECTED={[u['card'] for u in res_sel['used']]} · "
          f"FULL={[u['card'] for u in res_full['used']]} "
          f"⇒ حکمِ اصلی روی FULL.", flush=True)

    res = res_full
    pool = res['pool']
    print(f"[تجمیع] n_before={res['n_before']} → n_after={res['n_after']} "
          f"(حذفِ FIFO: {100*(1-res['n_after']/max(res['n_before'],1)):.1f}%)",
          flush=True)
    for d in res['dropped']:
        print(f"   dropped {d['card']}: {d['reason']}", flush=True)

    # ---- قیدِ C5: سقفِ سهمِ عضو ----
    share = pool['src_card'].value_counts(normalize=True)
    print(f'[C5 سهمِ اعضا] {share.round(3).to_dict()}', flush=True)
    if float(share.max()) > C5_MAX_MEMBER_SHARE:
        print(f'[C5 نقض] {share.idxmax()} سهم {share.max():.1%} > '
              f'{C5_MAX_MEMBER_SHARE:.0%} ⇒ توقف (REJECT).', flush=True)
        with open(os.path.join(OUT, 'pool_c5_violation.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(dict(share=share.to_dict(),
                           limit=C5_MAX_MEMBER_SHARE),
                      fh, ensure_ascii=False, indent=1)
        return

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f'[نولِ استخر] {json.dumps(null, ensure_ascii=False, default=str)}',
          flush=True)

    # ---- محورِ تقویمیِ مشترک (اصلاح‌های BUG-AXIS/QUANT/SPAN) ----
    # ریزترین کارت H6 است؛ محور را ریزتر (۱ساعته) می‌سازیم تا نه گردکردن
    # رخ دهد نه کلیپ. پوشش = min(t_entry)−گام تا max(t_exit)+۲گام.
    STEP_NS = 60 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f'\n[محورِ مشترک] شبکهٔ ۱ساعته · {axis_dt[0]} → {axis_dt[-1]} · '
          f'{len(axis_t):,} سطل', flush=True)

    # close هم‌راستا (H10): از H6 که کلِ افق را دارد؛ last-value، بدونِ آینده
    ref_df = se.load_data(DATA['XAUUSD_H6'])
    ref_t = ref_df['dt'].values.astype('datetime64[ns]').astype(np.int64)
    ref_c = ref_df['close'].to_numpy(float)
    posn = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                   len(ref_c) - 1)
    axis_close = ref_c[posn]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_entry'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_exit'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # ---- هندسهٔ استخر: مدیانِ وزنی به سهمِ پس-از-FIFO ----
    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = sum(by_card[c]['sl_pip'] * w for c, w in shares.items()
                 if c in by_card)
    tp_med = sum(by_card[c]['tp_pip'] * w for c, w in shares.items()
                 if c in by_card)
    sl_med = float(sl_med) if sl_med > 0 else None
    tp_med = float(tp_med) if tp_med > 0 else None
    print(f'[هندسهٔ استخر] SL~{sl_med:.1f}pip TP~{tp_med:.1f}pip '
          f'rr_eff={tp_med/sl_med:.3f}', flush=True)

    # ---- تقسیم: صدکِ ۶۰٪ِ زمانِ ورودِ معاملات (اصلاحِ BUG-SPLITDIR) ----
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'[تقسیم {SPLIT_FRAC:.0%}] مرز={np.datetime64(split_ns, "ns")} · '
          f'اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}',
          flush=True)

    # ---- یک و فقط یک داوری RQS2 v2.6 ----
    r = rqs2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=axis_dt, null=null,
                          close=axis_close,
                          holdout_mask=holdout,
                          n_trials=N_TRIALS,
                          allow_overlap=False)

    print('\n' + rqs2.format_rqs2('S533-POOL', r), flush=True)

    out = dict(members=[dict(card=m['card'], n=m['n'], lift=m['lift'],
                             wr=m['wr'], ref_wr=m['ref_wr'],
                             exp_pip=m['exp_pip'], sl_pip=m['sl_pip'],
                             tp_pip=m['tp_pip'])
                        for m in members],
               used=[u['card'] for u in res['used']],
               used_selected=[u['card'] for u in res_sel['used']],
               dropped=res['dropped'],
               n_before=res['n_before'], n_after=res['n_after'],
               member_share=share.to_dict(),
               sl_pip_med=sl_med, tp_pip_med=tp_med,
               split_ns=split_ns,
               n_trials=N_TRIALS, seed=SEED, k_perm=a.perm,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'))
    with open(vpath, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f'\n[saved] {vpath}', flush=True)


if __name__ == '__main__':
    main()
