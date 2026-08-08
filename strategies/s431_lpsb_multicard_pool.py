# -*- coding: utf-8 -*-
"""
S431 — احیای `S351`ِ POWER-LIMITED از راهِ **تجمیعِ چند-کارتی**
================================================================================
پیش‌ثبت: `results/S431_PREREG_S351_MULTICARD_POOLING.md` (با دو الحاقیه).

فرضیه
--------------------------------------------------------------------------------
عضوِ مرکزیِ LPSB (`L=8, f=0.33`) با هندسهٔ منجمدِ `S351`
(`SL=1.618·ATR21`, `RR=1.618`, `hold=12`) روی چهار کارتِ طلا
(`M5/M15/M30/H1`) **هیچ دروازه‌ای را نمی‌شکند** و هر چهار `POWER-LIMITED`اند:
تنها بیماری‌شان `n≈۵۰` است، با `lift`های هم‌جهت و هم‌مرتبه (+۱۲.۵ تا +۱۸.۸).

چون هندسه بر حسبِ **ATRِ خودِ کارت** است (نه pipِ ثابت)، قانون
تایم‌فریم-اگنوستیک است. پس تجمیعِ تقویمیِ چهار کارت باید `n` را به ~۲۳۱
برساند و `z` را از ~۲.۱ به بالای `۳.۰۹` ببرد — **بدونِ افزودنِ حتی یک
پارامترِ نو**، یعنی بدونِ هزینهٔ چندگانگیِ نو.

⛔ چرا این «نرم‌کردنِ معیار» نیست
--------------------------------------------------------------------------------
۱) هیچ پارامتری جست‌وجو نمی‌شود؛ همه از `S351` **منجمد** ارث می‌رسند.
۲) همپوشانیِ زمانی با صفِ FIFOِ تقویمیِ `engine/rqs2_pool.py` **حذف** می‌شود،
   پس `n`ِ گزارش‌شده `n_eff`ِ واقعی است، نه تورمِ ۴برابریِ چهار کارت.
۳) مدلِ صفر **اندازه‌گیری‌شده** است (جای‌گشت روی همان کارت‌ها)، نه فرضی.
۴) حکم با `compute_rqs2`ِ استاندارد (v2.6) صادر می‌شود، نه با proxy.

درسِ ثبت‌شده از تلاشِ شکست‌خوردهٔ قبلی (`s351_pool_rescue.py`)
--------------------------------------------------------------------------------
آن گام نسخهٔ **خام** را تجمیع کرد (D1 با `lift=+۱۳.۹` و `n=۷۴` در کنارِ H1 با
`lift=+۲.۳` و `n=۱۹۳۷`) ⇒ **رقیق‌سازیِ وزنی** ⇒ `z=۱.۵۷` ⇒ REJECT.
اینجا اعضا هم‌مرتبه‌اند (بیشترین سهم ۳۲٪ ⇒ قیدِ `C5` پاس).

قانونِ «اندک اندک»: هر کارت به‌محضِ محاسبه در JSONِ خودش checkpoint می‌شود؛
منتظرِ اتمامِ همه نمی‌مانیم، چون سندباکس ناپایدار است.
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from engine.rqs2_pool import pool_cards, _to_calendar              # noqa: E402
from strategies.s348_rr_sweep import (queue_rr, trades_df,         # noqa: E402
                                      cost_pip, SPLIT_FRAC)
from strategies.s351_lpsb import (atr_series, lpsb_signals, CARDS,  # noqa: E402
                                  GEO_SL_K, GEO_RR, GEO_HOLD, ATR_P)
from strategies.s351_verdict import build_null_side, CENTRAL        # noqa: E402

OUT = 'results/_scan_S431'

# ---------------------- اعضای استخر (قفل‌شده در پیش‌ثبت) ----------------------
# دقیقاً همان چهار کارتی که در الحاقیهٔ ۲ اعلام شد. قیدِ `C2`: این فهرست
# **پیش از** دیدنِ هر عددِ نو قفل شده و پس از اجرا کوتاه نمی‌شود.
POOL_MEMBERS = ['XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1']

WARMUP = max(4 * (2 * 13 + 1), 250)     # همان WARMUPِ S351 (بزرگ‌ترین L=13)
SEED = 20260805                         # بذرِ پیش‌ثبت‌شده
K_PERM = 2000                           # `K` پیش‌ثبت‌شده

# قیدِ `C5`ِ پیش‌ثبت‌شده: هیچ عضوی بیش از این سهم از نمونهٔ تجمیعی نباشد.
C5_MAX_MEMBER_SHARE = 0.50

# ---- چندگانگیِ صادقانه (قیدِ `C4`) --------------------------------------------
# `S431` هیچ پارامترِ نویی جست‌وجو نمی‌کند. تنها هزینهٔ چندگانگی، **ارثِ**
# خانوادهٔ پیش‌ثبت‌شدهٔ `S351` است: |L_LIST| × |F_LIST| = 3×3 = 9 عضو،
# ضربدر ۴ کارتِ استخر ⇒ ۳۶. عمداً بدبینانه گزارش می‌شود.
N_TRIALS_INHERITED = 9 * len(POOL_MEMBERS)


def card_population(card, n_perm=K_PERM, verbose=True):
    """
    اجرای عضوِ مرکزیِ LPSB روی یک کارت با هندسهٔ منجمدِ `S351`.

    برمی‌گرداند dict شاملِ `tr` (معاملات)، `dt` (محورِ تقویمی)، `lift`
    (نسبت به مبنای **اندازه‌گیری‌شده**) و متریک‌های خودِ کارت.

    هیچ پارامتری اینجا جست‌وجو نمی‌شود — همه ارثی و منجمدند.
    """
    asset, path = CARDS[card]
    df = se.load_data(path)
    atr = atr_series(df)
    dt = df['dt'].values if 'dt' in df.columns else np.arange(len(df))

    ls, ss, _ = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    sel = (ls | ss) & np.isfinite(atr) & (atr > 0)
    sig = np.where(sel)[0]
    if len(sig) < 5:
        return None

    is_long = ls[sig]
    st = queue_rr(df, sig, is_long, GEO_SL_K * atr[sig], asset,
                  GEO_HOLD, GEO_RR)
    if st is None or st['n'] < 5:
        return None
    tr = trades_df(st)

    # ---- مبنای **اندازه‌گیری‌شده** روی همان کارت (نه عددِ فرضی) ----
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[valid >= WARMUP]
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    rng = np.random.default_rng(SEED)
    null = build_null_side(df, asset, valid, GEO_SL_K * atr, nL, nS,
                           n_perm, rng, verbose=verbose)

    # lift وزنی به سمت، نسبت به مبنای بی‌قید
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
                exp_pip=float(np.mean(tr['pnl_pip'])),
                bars=int(len(df)))


def blend_pool_null(members_used, pool_df):
    """
    مدلِ صفرِ استخر: ترکیبِ **وزنیِ** نول‌های اندازه‌گیری‌شدهٔ اعضا، با وزنِ
    سهمِ هر کارت از معاملاتِ **باقی‌ماندهٔ پس از FIFO** (نه سهمِ اولیه‌اش).

    چرا وزن با سهمِ پس-از-FIFO؟ چون صفِ FIFO بخشی از معاملات را حذف می‌کند و
    اگر با سهمِ اولیه وزن بدهیم، مبنای کارتی که بیشتر حذف شده بیش‌ازحد
    اثر می‌گذارد ⇒ مبنایِ اشتباه ⇒ liftِ اشتباه. این جزئیاتِ ریز، تفاوتِ
    یک اندازه‌گیریِ درست و یک عددِ خوش‌ظاهر است.
    """
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
                # واریانسِ ترکیب: وزن‌ها را روی واریانس اعمال می‌کنیم، نه sd
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
    ap = argparse.ArgumentParser()
    ap.add_argument('--perm', type=int, default=K_PERM)
    ap.add_argument('--cards', type=str, default='')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    want = [c.strip() for c in a.cards.split(',') if c.strip()] or POOL_MEMBERS

    print(f'== S431 — تجمیعِ چند-کارتیِ LPSB · اعضا: {want} ==', flush=True)
    print(f'   هندسهٔ منجمد: SL={GEO_SL_K}·ATR{ATR_P} RR={GEO_RR} '
          f'hold={GEO_HOLD} · عضو={CENTRAL} · K={a.perm}', flush=True)

    members = []
    for card in want:
        cache = os.path.join(OUT, f'{card.replace("-", "_")}_member.json')
        print(f'\n-- کارتِ {card} --', flush=True)
        m = card_population(card, n_perm=a.perm)
        if m is None:
            print('   ناکافی (سیگنال/معاملهٔ کم) — رد', flush=True)
            continue
        print(f"   n={m['n']} (L={m['n_long']}/S={m['n_short']}) "
              f"WR={m['wr']:.2f} ref={m['ref_wr']} lift={m['lift']} "
              f"exp={m['exp_pip']:+.2f} pip", flush=True)
        # checkpointِ «اندک اندک» — بی‌درنگ روی دیسک
        with open(cache, 'w', encoding='utf-8') as fh:
            json.dump({k: v for k, v in m.items() if k not in ('tr', 'dt')},
                      fh, ensure_ascii=False, indent=1, default=str)
        members.append(m)

    if len(members) < 2:
        print('\n[توقف] کمتر از دو عضوِ معتبر — تجمیع بی‌معناست.', flush=True)
        return

    # ------------------------- قیدِ C1: همگنی -------------------------
    lifts = [m['lift'] for m in members if m['lift'] is not None]
    same_sign = all(x > 0 for x in lifts) or all(x < 0 for x in lifts)
    print(f'\n[C1 همگنی] liftها={["%.2f" % x for x in lifts]} '
          f'هم‌علامت={same_sign}', flush=True)
    if not same_sign:
        print('[C1 نقض] اعضا هم‌جهت نیستند ⇒ تجمیع متوقف (REJECT).',
              flush=True)
        return

    # --------------------- تجمیعِ تقویمی + حذفِ همپوشانی ---------------------
    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                           lift=m['lift']) for m in members])
    if res is None:
        print('[توقف] pool_cards هیچ عضوِ معتبری نیافت.', flush=True)
        return

    pool = res['pool']
    print(f"\n[تجمیع] n_before={res['n_before']} → n_after={res['n_after']} "
          f"(حذفِ همپوشانیِ FIFO: "
          f"{100*(1-res['n_after']/max(res['n_before'],1)):.1f}%)", flush=True)
    print(f"   used={[u['card'] for u in res['used']]}", flush=True)
    for d in res['dropped']:
        print(f"   dropped {d['card']}: {d['reason']}", flush=True)
    print(f"   selection trace={json.dumps(res['selection']['trace'], ensure_ascii=False)}",
          flush=True)

    # ------------------------- قیدِ C5: سقفِ سهم -------------------------
    share = pool['src_card'].value_counts(normalize=True)
    print(f'\n[C5 سهمِ اعضا] {share.round(3).to_dict()}', flush=True)
    if float(share.max()) > C5_MAX_MEMBER_SHARE:
        print(f'[C5 نقض] عضوِ {share.idxmax()} سهمِ {share.max():.1%} دارد '
              f'> {C5_MAX_MEMBER_SHARE:.0%} ⇒ خطرِ رقیق‌سازی ⇒ توقف (REJECT).',
              flush=True)
        with open(os.path.join(OUT, 'pool_c5_violation.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(dict(share=share.to_dict(), limit=C5_MAX_MEMBER_SHARE),
                      fh, ensure_ascii=False, indent=1)
        return

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f'\n[نولِ استخر] {json.dumps(null, ensure_ascii=False, default=str)}',
          flush=True)

    # ------------------------- داوریِ RQS2 v2.6 -------------------------
    asset = used_members[0]['asset']
    sl_med = float(np.median(pool['sl_pip'])) if 'sl_pip' in pool else None
    tp_med = (sl_med * GEO_RR) if sl_med else None
    # محورِ زمانِ تقویمی برای آزمون‌های تقویمی/رژیمی
    bar_time = pool['t_entry'].values.astype('datetime64[ns]')

    r = rqs2.compute_rqs2(pool, asset, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null,
                          n_trials=N_TRIALS_INHERITED,
                          allow_overlap=False)

    print('\n' + rqs2.format_rqs2('S431-POOL', r), flush=True)

    out = dict(members=[dict(card=m['card'], n=m['n'], lift=m['lift'],
                             wr=m['wr'], exp_pip=m['exp_pip'])
                        for m in members],
               used=[u['card'] for u in res['used']],
               dropped=res['dropped'],
               selection=res['selection'],
               n_before=res['n_before'], n_after=res['n_after'],
               member_share=share.to_dict(),
               sl_pip_med=sl_med, tp_pip_med=tp_med,
               n_trials=N_TRIALS_INHERITED,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'))
    with open(os.path.join(OUT, 'pool_verdict.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f"\n[saved] {OUT}/pool_verdict.json", flush=True)


if __name__ == '__main__':
    main()
