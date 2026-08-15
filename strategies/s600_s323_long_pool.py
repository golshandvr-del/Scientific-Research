# -*- coding: utf-8 -*-
"""
S600 — احیای S323-LONG از راهِ تجمیعِ چند-کارتیِ M30+H1 (مسیرِ C)
================================================================================
پیش‌ثبت: `results/S600_PREREG_S323_LONG_MULTICARD_POOLING.md` (commit 0c14b291،
**قبل** از اجرای این فایل). خلاصهٔ عهد:

  · اعضای استخر قفل: `XAUUSD-M30 LONG` و `XAUUSD-H1 LONG` — واریانتِ
    `backtested`، پیکربندیِ منجمدِ s357، دادهٔ کاملِ mt5_full.
  · هیچ جست‌وجویی نیست. `n_trials = 2568×2 = 5136` (بودجهٔ s362 × تصمیمِ تجمیع).
  · حکم فقط با `engine/rqs2.py::compute_rqs2` v2.6 — هر ۱۱ دروازه.
  · EURUSD مطلقاً آزموده نمی‌شود (استثنای صریحِ کاربر).

چرا import و نه بازنویسی: درسِ BUG-GEOMDRIFT (S437) و قاعدهٔ S570 — هر
بازنویسیِ منطقِ سیگنال/نول یک درجهٔ آزادیِ پنهان است. سیگنال، هندسه و نول
عیناً از `s570_s323_fulldata_retest` (که خودش از `s357` وارد می‌کند) می‌آیند؛
تنها متغیرِ مستقلِ این نشست «تجمیعِ دو کارت» است — همان چیزی که فرضیهٔ
H-600 درباره‌اش است.

سنجهٔ سلامتِ پیش‌ثبت (بندِ ۶.۱): n/WR هر عضو باید با checkpointِ S570
بیت‌به‌بیت بخواند (M30: n=159, WR=72.33 · H1: n=37, WR=70.27). اگر نخواند
⇒ توقف و ریشه‌یابی، نه ادامه.

میراثِ باگ‌های S431 که اینجا از روزِ اول رعایت می‌شوند:
  · BUG-AXIS/BUG-SPAN: محورِ تقویمیِ مشترک = شبکهٔ مصنوعیِ یکنواخت روی
    افقِ کاملِ استخر (نه فایلِ هیچ کارتی). رزولوشن ۳۰ دقیقه (ریزترین TFِ عضو).
  · BUG-SPLITDIR: مرزِ holdout = صدکِ ۶۰٪ِ زمانِ ورودِ معاملات، نه ۶۰٪ تقویم.
  · BUG-DEFAULTARG: هیچ monkey-patch روی آرگومانِ پیش‌فرض؛ استخرِ FULL
    (بدونِ گزینشِ پس‌ازدیدن) حکمِ اصلی است — اینجا اصلاً موضوعیت ندارد چون
    اعضا از پیش‌ثبت ۲تا هستند و `add_margin=-1` صریحاً پاس می‌شود.

اجرا:
    python3 strategies/s600_s323_long_pool.py            # اعضا + استخر + حکم
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, '.')

import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs2 as R2
import engine.rqs2_pool as rp

# منطقِ منجمد — وارد می‌شود، بازنویسی نمی‌شود (زنجیرهٔ s600→s570→s357)
from strategies.s570_s323_fulldata_retest import cfg_for, load_full
from strategies.s357_s323_v24_rejudge import signals_backtested, build_null

import warnings
warnings.filterwarnings('ignore')

# ═════════════════ ثابت‌های پیش‌ثبت‌شدهٔ S600 (بندهای ۳ و ۴) ═════════════════
POOL_MEMBERS = ['XAUUSD-M30', 'XAUUSD-H1']       # قفل‌شده در پیش‌ثبت
PERM_K = 2000
SEED = 20260813                                   # بذرِ پیش‌ثبت‌شده
N_TRIALS = 5136                                   # 2568 (s362) × 2 (تصمیمِ تجمیع)
SPLIT_FRAC = 0.60                                 # قاعدهٔ ارثیِ پروژه
OUT = 'results/_s600_s323_pool'

# سنجهٔ سلامت: بازتولیدِ بیت‌به‌بیتِ checkpointِ S570 (بندِ ۶.۱ پیش‌ثبت)
EXPECTED = {'XAUUSD-M30': dict(n=159, wr=72.33),
            'XAUUSD-H1': dict(n=37, wr=70.27)}


def member_population(card: str, k_perm: int) -> dict | None:
    """جمعیتِ یک عضو: سیگنالِ منجمدِ backtested + براکتِ ارثی + نولِ اندازه‌گیری‌شده."""
    asset, tf = card.split('-')
    t0 = time.time()
    df, src = load_full(asset, tf)
    cfg = cfg_for(card)

    atr14 = ind.atr(df, 14).values
    pip = se.ASSETS[asset]['pip']
    atr_pip_med = float(np.nanmedian(atr14[260:]) / pip)
    sl = round(cfg['slMult'] * atr_pip_med, 1)
    tp = round(cfg['tpMult'] * atr_pip_med, 1)
    mh = int(cfg['maxHold'])

    sig = signals_backtested(df, asset, dict(
        nearMax=cfg['nearMax'], roomMin=cfg['roomMin'], rsiMax=cfg['rsiMax'],
        slopeMin=cfg['slopeMin'], adxMin=cfg['adxMin'], golden=cfg['golden'],
        hLo=cfg['hLo'], hHi=cfg['hHi'],
    ))
    n_sig = int(sig.sum())
    print(f'\n-- {card} src={src}\n   bars={len(df)} '
          f'span={df["dt"].iloc[0].date()}→{df["dt"].iloc[-1].date()} '
          f'SL={sl} TP={tp} RR={tp/sl:.3f} mh={mh} signals={n_sig} '
          f'({time.time()-t0:.0f}s)', flush=True)
    if n_sig < 5:
        return None

    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 5:
        return None
    n = len(tr)
    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())

    # ── سنجهٔ سلامت (بندِ ۶.۱): بازتولیدِ بیت‌به‌بیتِ S570 ──
    exp = EXPECTED[card]
    ok = (n == exp['n']) and (abs(wr - exp['wr']) < 0.01)
    print(f'   n={n} WR={wr:.2f} | S570 expected n={exp["n"]} WR={exp["wr"]} '
          f'⇒ {"✅ REPRODUCED" if ok else "❌ MISMATCH"}', flush=True)
    if not ok:
        raise RuntimeError(f'{card}: بازتولیدِ S570 شکست خورد — توقف (بندِ ۶.۱)')

    # ── نولِ اندازه‌گیری‌شده (همان پروتکلِ s357/s570، بذرِ پیش‌ثبت‌شدهٔ S600) ──
    null, draws = build_null(df, asset, sig, sl, tp, mh, k_perm, SEED)
    ref = null['long']['perm_mean']
    lift = wr - ref
    print(f'   null(perm_mean)={ref:.2f} lift={lift:+.2f}pp perm_k={k_perm}',
          flush=True)

    return dict(card=card, asset=asset, tf=tf, tr=tr, dt=df['dt'].values,
                df_time=df['time'].values, n=n, wr=round(wr, 2),
                ref_wr=round(ref, 4), lift=round(lift, 4), null=null,
                sl_pip=sl, tp_pip=tp, max_hold=mh, data_src=src,
                exp_pip=float(np.mean(tr['pnl_pip'])), bars=len(df))


def blend_pool_null(members_used, pool_df):
    """نولِ استخر: ترکیبِ وزنیِ نول‌های اعضا با وزنِ سهمِ پس-از-FIFO (الگوی S431)."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0
        kmin = None
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
            perm_max=None, perm_k=kmin)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'== S600 — تجمیعِ S323-LONG · اعضا(قفل)={POOL_MEMBERS} · '
          f'K={PERM_K} seed={SEED} n_trials={N_TRIALS} ==', flush=True)

    # ---------------- گامِ ۱: جمعیتِ اعضا + checkpoint ----------------
    members = []
    for card in POOL_MEMBERS:
        m = member_population(card, PERM_K)
        if m is None:
            print(f'[توقف] {card} جمعیتِ معتبر نداد.', flush=True)
            return
        with open(os.path.join(OUT, f'{card.replace("-", "_")}_member.json'),
                  'w', encoding='utf-8') as fh:
            json.dump({k: v for k, v in m.items()
                       if k not in ('tr', 'dt', 'df_time', 'null')}
                      | dict(null_long=m['null']['long']),
                      fh, ensure_ascii=False, indent=1, default=str)
        members.append(m)

    # ---------------- قیدِ C1 (هم‌جهتی — پیش‌ثبت بندِ ۳) ----------------
    lifts = [m['lift'] for m in members]
    if not all(x > 0 for x in lifts):
        print(f'[C1 نقض] liftها={lifts} هم‌جهتِ مثبت نیستند ⇒ توقف (حکم: '
              f'REJECT تجمیع).', flush=True)
        return

    # -------- گامِ ۲: تجمیعِ تقویمی FIFO — استخرِ FULL بدونِ گزینش --------
    # add_margin=-1 صریحاً پاس می‌شود (درسِ BUG-DEFAULTARG): چون فهرستِ اعضا
    # در پیش‌ثبت قفل است، هیچ حذفِ پس‌ازدیدنِ dilution مجاز نیست.
    orig_choose = rp.choose_homogeneous_subset
    rp.choose_homogeneous_subset = (
        lambda cands, add_margin=None: orig_choose(cands, add_margin=-1.0))
    try:
        res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                                  lift=m['lift']) for m in members])
    finally:
        rp.choose_homogeneous_subset = orig_choose
    if res is None:
        print('[توقف] pool_cards هیچ عضوِ معتبری نیافت.', flush=True)
        return

    pool = res['pool']
    fifo_cut = 100 * (1 - res['n_after'] / max(res['n_before'], 1))
    print(f'\n[تجمیع] n_before={res["n_before"]} → n_after={res["n_after"]} '
          f'(حذفِ FIFO: {fifo_cut:.1f}%)', flush=True)
    share = pool['src_card'].value_counts(normalize=True)
    print(f'[سهمِ اعضا] {share.round(3).to_dict()}', flush=True)

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f'[نولِ استخر] long={null["long"]}', flush=True)

    # ---- هندسهٔ استخر: مدیانِ وزنی به سهمِ پس-از-FIFO (الگوی S431) ----
    shares = share.to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))
    print(f'[هندسهٔ استخر] SL={sl_med:.1f} TP={tp_med:.1f} '
          f'RR={tp_med/sl_med:.3f}', flush=True)

    # ---- محورِ مشترک: شبکهٔ ۳۰دقیقه‌ای (BUG-AXIS/BUG-SPAN اصلاح‌شده) ----
    STEP_NS = 30 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f'[محورِ مشترک] ۳۰دقیقه‌ای · {axis_dt[0]} → {axis_dt[-1]} · '
          f'{len(axis_t):,} سطل', flush=True)

    # close هم‌راستا برای H10 — از M30ِ کامل (کلِ افق را دارد)، بدونِ نگاهِ آینده
    m30 = by_card['XAUUSD-M30']
    ref_t = (pd.to_datetime(m30['df_time'], unit='s', utc=True)
             .values.astype('datetime64[ns]').astype(np.int64))
    from tools import s434_fast_data as fd
    d30 = fd.load_fast('XAUUSD', 'M30')
    ref_c = d30['close'].astype(float)
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

    # ---- holdout: صدکِ ۶۰٪ زمانِ ورود (BUG-SPLITDIR اصلاح‌شده) ----
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'[تقسیمِ {SPLIT_FRAC:.0%}] مرز={np.datetime64(split_ns, "ns")} · '
          f'اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}',
          flush=True)

    # ---------------- گامِ ۳: داوریِ RQS2 v2.6 ----------------
    r = R2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                        bar_time=axis_dt, null=null, close=axis_close,
                        holdout_mask=holdout, n_trials=N_TRIALS,
                        allow_overlap=False)
    print('\n' + R2.format_rqs2('S600-POOL', r), flush=True)

    out = dict(session='S600',
               prereg='results/S600_PREREG_S323_LONG_MULTICARD_POOLING.md',
               members=[dict(card=m['card'], n=m['n'], wr=m['wr'],
                             ref_wr=m['ref_wr'], lift=m['lift'],
                             sl_pip=m['sl_pip'], tp_pip=m['tp_pip'],
                             max_hold=m['max_hold'], data_src=m['data_src'],
                             exp_pip=round(m['exp_pip'], 3))
                        for m in members],
               used=[u['card'] for u in res['used']], dropped=res['dropped'],
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2),
               member_share=share.round(4).to_dict(),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, seed=SEED, perm_k=PERM_K, n_trials=N_TRIALS,
               split_frac=SPLIT_FRAC, split_utc=str(np.datetime64(split_ns, 'ns')),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    with open(os.path.join(OUT, 'pool_verdict.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f'\n[saved] {OUT}/pool_verdict.json', flush=True)


if __name__ == '__main__':
    main()
