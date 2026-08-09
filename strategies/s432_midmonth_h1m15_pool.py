# -*- coding: utf-8 -*-
"""
S432 — احیای `S312 MidMonthDrift` روی کارت‌های `H1`+`M15` از راهِ **تجمیعِ تقویمی**
================================================================================
پیش‌ثبت: `results/S432_PREREG_S312_H1M15_POOLING.md` (پیش از هر عدد commit شد)
نامزد از: `results/_s432_priority/priority_rank.json` (رتبهٔ ۱، پس از دو اصلاحِ
          خود-گرفتهٔ `BUG-SCALEBIAS` و `BUG-SCALEBIAS-2`)

تشخیص (چرا این نامزد):
  همین سازوکار روی کارتِ `M30` حکمِ `ACCEPT` با `z=3.66` گرفته و **در سایت
  وصل است** ⇒ لبه **اثبات‌شده** است. کارتِ `H1` تنها در `H3` افتاده
  (`z=2.72` در برابرِ سدِ `3.09` ⇒ فقط ۰.۳۷σ کم) و `n=260` زیرِ سقفِ
  شیشه‌ایِ `n_required_for_h3 = 336.5` است ⇒ کمبودِ **توان**، نه نبودِ لبه.
  `M15` هم همان سازوکار با `n=129` و `z=1.71` است.
  تجمیع ⇒ `n = 260 + 129 = 389 > 336.5` ⇒ سقف ریاضیاً شکسته می‌شود.

⚠️ آنچه این اسکریپت **نمی‌کند** (و دلیلش):
  • هیچ جست‌وجوی `TP/SL` — چون `H9` از قبل پاس است (۸۵٪ امید پس از ۲× هزینه
    می‌ماند). درسِ `S430`: هندسه را وقتی عوض کن که `H9` مانع باشد، نه `H3`.
  • هیچ فیلترِ نو — چون فیلتر `n` را **کوچک** می‌کند و `z` را **پایین**
    می‌آورد ⇒ از سد دورتر می‌شویم نه نزدیک‌تر. این محاسبه است، نه سلیقه.
  ⇒ صفر پارامترِ جست‌وجو‌شده ⇒ هیچ چندگانگیِ نو.

هندسهٔ ارثی (از `s312_oos_check.py`، دست‌نخورده):
  `M15`: sl=tp=295 · max_hold=48        `H1`: sl=tp=395 · max_hold=24
  فیلترِ کیفیت: `close > EMA200` (روشن، همان حکم)
  قانونِ پایه: `day_of_month ∈ {10,13,20}` و `hour ∈ 1..12` ⇒ `LONG`
"""

from __future__ import annotations

import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from engine import indicators as ind                               # noqa: E402
from engine.rqs2_pool import pool_cards                            # noqa: E402
from strategies import s333_s79_pullback_revival as s333           # noqa: E402  (ثبتِ ASSETSِ per-TF)
from strategies.s351_verdict import build_null_side                # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_scan_S432')

# ---- قیدهای **پیش‌ثبت‌شده** (از سندِ PREREG؛ اینجا فقط بازتاب می‌شوند) ----
POOL_MEMBERS = ['XAUUSD_H1', 'XAUUSD_M15']   # `C2`: قفل — `M30` عمداً بیرون
SEED = 20260805
K_PERM = 2000                                # `C8`: حکمِ قبلی K=600 داشت
SPLIT_FRAC = 0.60
C5_MAX_MEMBER_SHARE = 0.75                   # دو عضو ⇒ سقفِ ۵۰٪ ناممکن است

# هندسهٔ ارثی — **جست‌وجو نشده**، از `s312_oos_check.py` عیناً
GEOM = {
    'XAUUSD_M15': dict(sl=295, tp=295, mh=48),
    'XAUUSD_M30': dict(sl=295, tp=295, mh=36),
    'XAUUSD_H1':  dict(sl=395, tp=395, mh=24),
}

# قانونِ پایهٔ S312 — صفر پارامترِ آزاد
DOM_SET = frozenset((10, 13, 20))
HOURS = frozenset(range(1, 13))
EMA_P = 200
WARMUP = 300

# ---- چندگانگیِ صادقانه ------------------------------------------------------
# `S312` در ممیزیِ اصلی `n_trials=149` داشت. آن هزینه **ارثی** است و باید
# پرداخت شود (نمی‌توان با عوض کردنِ اسکریپت از آن فرار کرد). خودِ تصمیمِ
# «تجمیعِ H1+M15» را هم یک درجهٔ آزادی می‌شماریم ⇒ ۱۴۹ × ۲ = ۲۹۸.
N_TRIALS_INHERITED = 298


def build_s312_layer(df):
    """
    ماسکِ ورودِ `S312` — بازتولیدِ **وفادارِ** `sim_strategies.S312_MidMonth_Long`
    با `quality_filter=True`.

    ⚠️ درسِ `S430` (باگِ بازتولید): آنجا فیلترِ `dip` را «۴ کندلِ نزولیِ پیاپی»
    فهمیدم در حالی که قانونِ واقعی جابه‌جاییِ خالص بود ⇒ نسخهٔ من ۱۰ برابر
    سخت‌گیرتر شد و نزدیک بود لایهٔ سالمی را «مرده» اعلام کنم. پس اینجا هر
    شرط را سطر-به-سطر از کلاسِ اصلی برداشتم:
        `dom ∈ {10,13,20}` و `hour ∈ 1..12` و `close > EMA200`
    فیلترِ `ATR` در پیکربندیِ حکم **بی‌اثر** است (`atr_lo=0`, `atr_hi=1e9`)
    پس عمداً پیاده نمی‌شود — افزودنش یک شرطِ همیشه-درست است و صرفاً
    توهمِ وفاداریِ بیشتر می‌دهد.
    """
    dt = df['dt']
    dom = dt.dt.day.to_numpy()
    hour = dt.dt.hour.to_numpy()
    ema = ind.ema(df['close'], EMA_P).to_numpy()
    close = df['close'].to_numpy(float)

    m_time = np.isin(dom, list(DOM_SET)) & np.isin(hour, list(HOURS))
    m_qual = close > ema
    sig = m_time & m_qual
    sig[:WARMUP] = False
    return sig


def _win_col(tr):
    if 'win' not in tr.columns:
        tr = tr.copy()
        tr['win'] = (tr['pnl_pip'].to_numpy() > 0).astype(int)
    return tr


def card_population(card, n_perm=K_PERM, verbose=True):
    """جمعیتِ یک عضوِ استخر = ماسکِ `S312` + هندسهٔ ارثیِ همان کارت."""
    g = GEOM[card]
    asset = 'XAUUSD'
    path = se.ASSETS[card]['file']
    if not os.path.exists(path):
        print(f'   [غایب] {path}', flush=True)
        return None

    df = se.load_data(path)
    n = len(df)
    close = df['close'].to_numpy(float)
    dt = df['dt'].values if 'dt' in df.columns else np.arange(n)

    sig = build_s312_layer(df)
    sl, tp, mh = g['sl'], g['tp'], g['mh']
    tr, _ = s333.evaluate(df, sig, card, sl, tp, mh)
    if tr is None or len(tr) < 3:
        return None
    tr = _win_col(tr)

    # ---- مبنای **اندازه‌گیری‌شده** روی همان کارت (نه عددِ فرضی) ----
    valid = np.where(np.isfinite(close))[0]
    valid = valid[valid >= WARMUP]
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    rng = np.random.default_rng(SEED)
    sl_price = sl * se.ASSETS[asset]['pip']
    null = build_null_side(df, asset, valid, np.full(n, sl_price),
                           nL, nS, n_perm, rng, verbose=verbose)

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
                n_long=nL, n_short=nS, n_base=int(sig.sum()),
                sl_pip=float(sl), tp_pip=float(tp), max_hold=int(mh),
                exp_pip=float(np.mean(tr['pnl_pip'])),
                bars=int(n))


def blend_pool_null(members_used, pool_df):
    """
    مدلِ صفرِ استخر: ترکیبِ **وزنیِ** نول‌های اندازه‌گیری‌شدهٔ اعضا، با وزنِ
    سهمِ هر کارت از معاملاتِ **باقی‌ماندهٔ پس از FIFO** (نه سهمِ اولیه‌اش).
    عیناً همان تابعِ `S431` — چون قاعده‌اش عمومی است و بازنویسی‌اش فقط
    فرصتِ نو برای باگ می‌سازد.
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

    print(f'== S432 — تجمیعِ تقویمیِ S312 · اعضا: {want} ==', flush=True)
    print(f'   جمعیت: dom∈{{10,13,20}} · hour∈1..12 · close>EMA200 · '
          f'هندسه: ارثیِ per-card · K={a.perm}', flush=True)
    print(f'   ⚠️ کارتِ M30 عمداً بیرون است (قیدِ C3): از قبل ACCEPT دارد و '
          f'واردکردنش n را با لبهٔ اثبات‌شده باد می‌کند.', flush=True)

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
        print('[C1 نقض] اعضا هم‌جهت نیستند ⇒ تجمیع متوقف (REJECT).', flush=True)
        return

    # --------------------- تجمیعِ تقویمی + حذفِ همپوشانی ---------------------
    # ⚠️ درسِ `ISSUE-C2` + `BUG-DEFAULTARG` از `S431`، عیناً اعمال‌شده:
    # `pool_cards` درونش `choose_homogeneous_subset` را صدا می‌زند که عضوی را
    # که `z_proxy` را ≥۱۵٪ بالا نبرد **حذف** می‌کند — و آن حذف **پس از دیدنِ
    # نتیجه** است ⇒ نقضِ قیدِ `C2`. در `S431` تلاشِ اولِ من برای رفعش
    # (`POOL_ADD_MARGIN = -1.0`) در **سکوت** بی‌اثر بود، چون مقدارِ پیش‌فرضِ
    # آرگومان در لحظهٔ **تعریفِ تابع** قفل می‌شود. راهِ درست: خودِ تابع را
    # با wrapper جایگزین کن تا آرگومان **صریحاً** پاس شود.
    # با دو عضو، ۳ زیرمجموعه در دسترس است؛ برداشتنِ «بهترین» همان `H5`ِ پنهان.
    import engine.rqs2_pool as _rp
    _orig_choose = _rp.choose_homogeneous_subset

    def _choose_all(cands, add_margin=None):
        return _orig_choose(cands, add_margin=-1.0)

    try:
        _rp.choose_homogeneous_subset = _choose_all
        res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                               lift=m['lift']) for m in members])
    finally:
        _rp.choose_homogeneous_subset = _orig_choose

    if res is None:
        print('[توقف] استخرِ FULL ساخته نشد.', flush=True)
        return

    pool = res['pool']
    print(f"\n[تجمیع] n_before={res['n_before']} → n_after={res['n_after']} "
          f"(حذفِ همپوشانیِ FIFO: "
          f"{100*(1-res['n_after']/max(res['n_before'],1)):.1f}%)", flush=True)
    print(f"   used={[u['card'] for u in res['used']]}", flush=True)
    for d in res['dropped']:
        print(f"   dropped {d['card']}: {d['reason']}", flush=True)

    # ------------------------- قیدِ C5: سقفِ سهم -------------------------
    share = pool['src_card'].value_counts(normalize=True)
    print(f'\n[C5 سهمِ اعضا] {share.round(3).to_dict()}', flush=True)
    if float(share.max()) > C5_MAX_MEMBER_SHARE:
        print(f'[C5 نقض] عضوِ {share.idxmax()} سهمِ {share.max():.1%} دارد '
              f'> {C5_MAX_MEMBER_SHARE:.0%} ⇒ توقف (REJECT).', flush=True)
        return

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f'\n[نولِ استخر] {json.dumps(null, ensure_ascii=False, default=str)}',
          flush=True)

    # ------------------------- داوریِ RQS2 v2.6 -------------------------
    asset = used_members[0]['asset']
    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = sum(by_card[c]['sl_pip'] * w for c, w in shares.items()
                 if c in by_card)
    tp_med = sum(by_card[c]['tp_pip'] * w for c, w in shares.items()
                 if c in by_card)
    sl_med = float(sl_med) if sl_med > 0 else None
    tp_med = float(tp_med) if tp_med > 0 else None

    # ---- محورِ تقویمیِ مشترک (وارثِ اصلاحاتِ BUG-AXIS/QUANT/SPAN از S431) ----
    # موتور محور را با `exit_bar` ایندکس می‌کند و `entry_bar`ِ هر عضو در
    # ایندکس‌گذاریِ کارتِ خودش معنا دارد (کندلِ ۵۰۰۰ در M15 ≠ در H1). پس یک
    # شبکهٔ **مصنوعیِ** یکنواخت روی کلِ افقِ استخر می‌سازیم و اندیس‌ها را
    # بازنویسی می‌کنیم. رزولوشن = ریزترین فاصلهٔ واقعیِ این استخر = ۱۵ دقیقه
    # (عضوِ M15). پوشش = ابرمجموعهٔ افقِ هر دو عضو ⇒ نه گردکردن، نه کلیپ.
    STEP_NS = 15 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS, dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f'\n[محورِ مشترک] شبکهٔ ۱۵دقیقه‌ای · {axis_dt[0]} → {axis_dt[-1]} '
          f'· {len(axis_t):,} سطل', flush=True)

    ref_df = se.load_data(se.ASSETS['XAUUSD_H1']['file'])
    ref_t = ref_df['dt'].values.astype('datetime64[ns]').astype(np.int64)
    ref_c = ref_df['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.searchsorted(axis_t, pool['t_entry'].values, 'left')
    pool['exit_bar'] = np.searchsorted(axis_t, pool['t_exit'].values, 'left')
    pool['entry_bar'] = np.clip(pool['entry_bar'], 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(pool['exit_bar'], 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    bar_time = axis_dt

    # ---- تقسیمِ اکتشاف/خارج‌نمونه (وارثِ اصلاحِ BUG-OOS + BUG-SPLITDIR) ----
    # صدکِ ۶۰٪ِ **زمانِ ورودِ معاملات** — نه ۶۰٪ِ طولِ تقویم. چون معاملات
    # در سال‌ها یکنواخت پخش نیستند و ۶۰٪ِ *زمان* ≠ ۶۰٪ِ *نمونه*.
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'\n[تقسیمِ ارثی {SPLIT_FRAC:.0%}] مرز={np.datetime64(split_ns, "ns")} '
          f'· اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}',
          flush=True)

    r = rqs2.compute_rqs2(pool, asset, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null,
                          close=axis_close,
                          holdout_mask=holdout,
                          n_trials=N_TRIALS_INHERITED,
                          allow_overlap=False)

    print('\n' + rqs2.format_rqs2('S432-POOL', r), flush=True)

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
