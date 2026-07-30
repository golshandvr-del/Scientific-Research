# -*- coding: utf-8 -*-
"""
S347 — **داوریِ رسمیِ RQS2** برای گروههٔ رأی‌گیری
====================================================

این فایل تنها جایی است که **حکمِ رسمیِ پذیرش/رد** صادر می‌شود.
`s347_ensemble.py` فقط *اکتشاف* است (کدام K چه می‌دهد)؛ داوری این‌جاست.

چرا جدا؟ درسِ گران‌بهای نشستِ قبل: اگر تابعِ هدفِ اکتشاف و تابعِ هدفِ داوری
یکی باشند، اکتشاف عملاً معیار را بیشینه می‌کند و داوری بی‌معنا می‌شود.

------------------------------------------------------------------------
سه انتخابِ طراحیِ حساس که باید صریح ثبت شوند
------------------------------------------------------------------------

**۱) خطِ مبنا (`null`) چگونه ساخته می‌شود؟**
   RQS2 برای `H3/H4` ساختارِ کانونیِ دو-سویه می‌خواهد:
   `{'long': {uncond_wr, perm_mean, perm_sd, perm_max, perm_k}, 'short': {...}}`

   • `uncond_wr` = ورود روی **هر** کندلِ واجدِ warmup در آن سمت، با **همان
     هندسهٔ براکت**. این «هدیهٔ رانش» را اندازه می‌گیرد؛ همان چیزی که RQS+
     نداشت و به‌جایش عددِ نظریِ ۵۰٪ را می‌گذاشت.
     ⚠️ SL در حالتِ بی‌قید باید **میانهٔ سادهٔ سه ATR** باشد نه میانهٔ وزنی،
     چون وزن‌ها از شمارِ رأی می‌آیند و در حالتِ «بی‌سیگنال» رأیی وجود ندارد؛
     استفاده از وزنِ رأی، اطلاعاتِ سیگنال را به خطِ مبنا **تزریق** می‌کرد.

   • `perm_*` = جای‌گشتِ زمانی، **به‌تفکیکِ سمت**. برای سمتِ long همان
     `n_long` ورودی از میانِ کندل‌های واجد قرعه‌کشی می‌شود (و مشابه برای
     short)، بعد صفِ بی‌همپوشانی **از نو** ساخته می‌شود.
     ⚠️ تفکیکِ سمت اجباری است، چون هدیهٔ رانش برای دو سمت قرینه نیست
     (روی D1: لانگ ۵۲.۴٪ در برابرِ شورت ۴۶.۳٪). ادغامِ دو سمت، مبنا را
     به‌طورِ مصنوعی به ۵۰٪ نزدیک می‌کرد و آزمون را **آسان‌تر** می‌ساخت.

**۲) `n_trials` برای `H5` چند است؟ — دو سناریو، و حکم با محافظه‌کارانه**

   • **خوش‌بینانه `N = ۱۰`** = ۵ مقدارِ K × ۲ گونه. تنها فضایی که *این لایه*
     پیمود. مشروع **فقط** اگر دو فیلترِ C1 «تأییدشدهٔ بیرونی» شمرده شوند —
     که مدرکش موجود است: آزمونِ تعمیم‌پذیری (۵۳/۵۳ عضوِ خارج از نمونه،
     ۲۸.۶σ) و انتقال به ۸ کارتِ دیگر.

   • **محافظه‌کارانه `N = ۱۰ × N_eff(بانک)`** ⇒ همان دو فیلتر از جست‌وجوی
     ۴۰۱ اندیکاتوری بیرون آمدند و آن جست‌وجو **بهای چندگانگی** دارد.
     `N_eff` اندازه‌گیری‌شدهٔ بانک = ۳۰۱ بُعدِ مستقل ⇒ `N = 3010`.

   **حکمِ رسمی با محافظه‌کارانه صادر می‌شود.** خوش‌بینانه فقط به‌عنوانِ
   تحلیلِ حساسیت گزارش می‌شود. این عکسِ وسوسهٔ رایج است، و عمداً چنین است:
   اگر لایه با سختِ‌ترین حساب هم رد نشود، یافته واقعاً محکم است.

**۳) `H7` روی همین کارت **آلوده** است — و پنهان نمی‌شود**
   دو فیلترِ C1 در خطِ لولهٔ کشفِ S346 پیدا شدند و آن خطِ لوله بهبود روی
   پنجرهٔ holdout را **شرط** کرده بود؛ پس holdoutِ همان سری قیمت، خارج از
   نمونهٔ *واقعی* نیست. عدد محاسبه و گزارش می‌شود، اما در فایلِ نتیجه با
   برچسبِ «آلوده» می‌آید، و مدرکِ واقعیِ خارج‌ازنمونه **انتقالِ بین‌کارتی**
   است (۸ کارتِ دیگر، `*_oos.json`).
"""

import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                          # noqa: E402
from engine import rqs2                                        # noqa: E402
from strategies.s346_geom import CARDS                          # noqa: E402
from strategies.s347_ensemble import (                          # noqa: E402
    OUT, SEED, P_LIST, ENS_HOLD, RR, SL_K, K_GRID, WARMUP_REF,
    C1_FILTERS, REF_CARD, N_TRIALS,
    _ind, _ref_quantiles, _queue, build_votes, entries_for_K,
)

# N_eff اندازه‌گیری‌شدهٔ بانکِ ۴۰۱ ‌اندیکاتوری (از `strategies/s346_neff.py`)
BANK_NEFF = 301
SPLIT_FRAC = 0.60          # عیناً `s346_geom.split_idx`


def build_filter_gate(df, warmup):
    """دروازهٔ دو-فیلترهٔ منجمدِ C1 روی این کارت (چارک‌همتا)."""
    qref = _ref_quantiles()
    gate = np.ones(len(df), dtype=bool)
    gate[:warmup] = False
    thr_used = {}
    for f in C1_FILTERS:
        v = _ind(df, f['col'], f['kind'])
        ok = np.isfinite(v)
        ok[:warmup] = False
        thr = float(np.nanquantile(v[ok], qref[f['col']]))
        thr_used[f['col']] = thr
        gate &= ok & ((v >= thr) if f['dir'] == 'ge' else (v <= thr))
    return gate, thr_used


def side_null(df, asset, valid_idx, atr_plain, n_side, is_long_flag,
              hold, n_perm, rng):
    """خطِ مبنای یک سمت: بی‌قید + جای‌گشتِ زمانی."""
    out = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
               perm_max=None, perm_k=None)
    if n_side < 1 or len(valid_idx) < 2:
        return out

    # --- بی‌قید: هر کندلِ واجد، همان سمت، همان هندسه ---
    sl_all = atr_plain[valid_idx] * SL_K
    good = np.isfinite(sl_all) & (sl_all > 0)
    vi = valid_idx[good]
    sl_v = sl_all[good]
    if len(vi) >= 2:
        st = _queue(df, vi, np.full(len(vi), is_long_flag), sl_v, asset, hold)
        if st:
            out['uncond_wr'] = st['wr']

    # --- جای‌گشتِ زمانی: همان n، زمان‌های قرعه‌ای، صف از نو ---
    if len(vi) > n_side:
        wr = []
        for _ in range(n_perm):
            pick = np.sort(rng.choice(len(vi), size=n_side, replace=False))
            st = _queue(df, vi[pick], np.full(n_side, is_long_flag),
                        sl_v[pick], asset, hold)
            if st:
                wr.append(st['wr'])
        if wr:
            a = np.asarray(wr, dtype='float64')
            out.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                       perm_max=float(a.max()), perm_k=int(len(a)))
    return out


def run(card='XAUUSD-D1', K=13, variant='B', n_perm=300, save=True):
    rng = np.random.default_rng(SEED)
    asset, path = CARDS[card]
    df = se.load_data(path)
    close = df['close'].values.astype('float64')
    bar_time = df['dt'].values if 'dt' in df.columns else None
    warmup = max(5 * max(P_LIST), WARMUP_REF)

    print(f"=== S347 VERDICT :: {card} K={K} variant={variant} "
          f"(bars={len(df):,}) ===", flush=True)

    vl, vs, wl, ws, atr = build_votes(df, warmup)
    atr_plain = np.nanmedian(atr, axis=0)          # میانهٔ سادهٔ سه ATR
    sig, is_long, sl = entries_for_K(vl, vs, wl, ws, atr, K)

    gate, thr_used = build_filter_gate(df, warmup)
    if variant == 'B':
        keep = gate[sig]
        sig, is_long, sl = sig[keep], is_long[keep], sl[keep]
        print(f"    filter gate keeps {gate.mean()*100:.2f}% of bars  "
              f"thr={ {k: round(v, 6) for k, v in thr_used.items()} }", flush=True)

    st = _queue(df, sig, is_long, sl, asset, ENS_HOLD)
    if st is None or st['n'] < 5:
        print("!!! no viable trades"); return None

    # ---------------- DataFrameِ معاملات به فرمتِ RQS2 ----------------
    tr = pd.DataFrame(dict(
        pnl_pip=st['pnl'],
        outcome=np.where(st['win'], 'win', 'loss'),
        sl_pip=st['sl_pip'],
        tp_pip=st['tp_pip'],
        entry_bar=st['entry_bar'].astype(int),
        exit_bar=st['exit_bar'].astype(int),
        direction=np.where(st['is_long'], 'long', 'short'),
    ))
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(len(tr) - n_long)
    print(f"    trades n={st['n']} (long={n_long} short={n_short}) "
          f"WR={st['wr']:.2f}% exp={st['exp']:+.2f}pip PF={st['pf']:.3f}",
          flush=True)

    # ---------------- خطِ مبنا، به‌تفکیکِ سمت ----------------
    valid = np.where(np.isfinite(atr_plain) & (atr_plain > 0))[0]
    valid = valid[valid >= warmup]
    if variant == 'B':
        valid = valid[gate[valid]]
    print(f"    null pool = {len(valid):,} bars · {n_perm} permutations/side",
          flush=True)
    null = {
        'long':  side_null(df, asset, valid, atr_plain, n_long, True,
                           ENS_HOLD, n_perm, rng),
        'short': side_null(df, asset, valid, atr_plain, n_short, False,
                           ENS_HOLD, n_perm, rng),
    }
    for s in ('long', 'short'):
        d = null[s]
        print(f"      {s:<5} uncond={d['uncond_wr']} perm_mean={d['perm_mean']} "
              f"sd={d['perm_sd']} max={d['perm_max']}", flush=True)

    # ---------------- دو سناریوی n_trials ----------------
    n_cons = N_TRIALS * BANK_NEFF
    split_bar = int(len(df) * SPLIT_FRAC)

    common = dict(sl_pip=float(np.median(st['sl_pip'])),
                  tp_pip=float(np.median(st['tp_pip'])),
                  bar_time=bar_time, null=null, split_bar=split_bar,
                  close=close)

    res_cons = rqs2.compute_rqs2(tr, asset, n_trials=n_cons, **common)
    res_opt = rqs2.compute_rqs2(tr, asset, n_trials=N_TRIALS, **common)

    print()
    print(rqs2.format_rqs2(f"S347 {card} K={K}{variant} [CONSERVATIVE "
                           f"N={n_cons}]", res_cons))
    print()
    print(rqs2.format_rqs2(f"S347 {card} K={K}{variant} [optimistic "
                           f"N={N_TRIALS}]", res_opt))

    if save:
        os.makedirs(OUT, exist_ok=True)
        p = f"{OUT}/{card}_K{K}{variant}_verdict2.json"
        json.dump(dict(card=card, K=K, variant=variant, n_perm=n_perm,
                       ens_hold=ENS_HOLD, rr=RR, sl_k=SL_K,
                       filter_thr=thr_used, split_bar=split_bar,
                       n_trials_conservative=n_cons,
                       n_trials_optimistic=N_TRIALS,
                       bank_neff=BANK_NEFF,
                       h7_contaminated=True,
                       h7_contamination_note=(
                           "The two C1 filters were selected by the S346 "
                           "discovery pipeline, which required improvement on "
                           "the holdout window; therefore the holdout of THIS "
                           "price series is not a genuine out-of-sample test. "
                           "The genuine OOS evidence is the cross-card "
                           "transfer in *_oos.json."),
                       null=null,
                       trades=dict(n=st['n'], wr=st['wr'], exp=st['exp'],
                                   pf=st['pf'], n_long=n_long,
                                   n_short=n_short),
                       verdict_conservative=res_cons,
                       verdict_optimistic=res_opt),
                  open(p, 'w'), default=float, ensure_ascii=False, indent=1)
        print(f"  saved -> {p}", flush=True)
    return res_cons


if __name__ == '__main__':
    c = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-D1'
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 13
    v = sys.argv[3] if len(sys.argv) > 3 else 'B'
    nb = int(sys.argv[4]) if len(sys.argv) > 4 else 300
    run(c, k, v, nb)
