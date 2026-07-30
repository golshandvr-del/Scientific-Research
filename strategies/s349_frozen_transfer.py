# -*- coding: utf-8 -*-
"""
S349 — انتقالِ **صفر-پارامتریِ** هندسهٔ برندهٔ XAUUSD-D1 به کارت‌های
        هرگز-آزموده‌نشدهٔ EURUSD (D1 / H4 / H1 / W1)
================================================================================
سندِ پشتیبان : `results/S348_RRGeometrySweep_...rqs28_REJECTED.md` بندهای ۵ و ۶
معیارِ داوری : `engine/rqs2.py` v2.4 (پذیرش = هر ۱۱ دروازه؛ بدونِ کفِ نمره‌ای)

--------------------------------------------------------------------------------
پرسشِ علمیِ این ماژول — تنها یک پرسش
--------------------------------------------------------------------------------
    «لایهٔ XAUUSD-D1 در S348 نُه دروازه از یازده را پاس کرد و *تنها* روی
      H3/H5 شکست، و تشخیص این بود که شکست **اقتصادی نیست، آماری است**
      (`n = 121` برای تولیدِ zِ لازم کافی نبود).
      آیا همان هندسه، بی‌هیچ تغییری، روی داراییِ دیگری هم کار می‌کند؟»

اگر پاسخ «آری» باشد دو چیز هم‌زمان به دست می‌آید:
  ۱) نمونهٔ بیشتر ⇒ zِ بالاتر، **بدونِ افزودنِ حتی یک پارامتر**.
  ۲) قوی‌ترین شکلِ شهادت بر واقعی‌بودنِ لبه: بقا روی *داراییِ نو*.

--------------------------------------------------------------------------------
⛔ چرا این کار «نرم‌کردنِ معیار» نیست — و مرزِ دقیقش
--------------------------------------------------------------------------------
راهِ *ممنوع* برای عبور از H5 گسترشِ گرید یا افزودنِ فیلتر است: هر دو
`n_trials` را بالا می‌برند و کرانِ شانس را **دورتر** می‌کنند. این ماژول
جهتِ مخالف را می‌رود:

    هیچ چیزی روی این چهار کارت جست‌وجو نمی‌شود. حتی یک عدد.

`K = 13`، `SL_K = 1.618`، `RR = 3.236`، `hold = 8` — همه از قبل تعیین شده و
در `results/_scan_S348/XAUUSD-D1.json` ثبت‌اند. اگر لایه روی EURUSD کار کند،
به این دلیل نیست که چیزی برای EURUSD تنظیم شد.

**نکتهٔ کلیدیِ انتقال‌پذیری**: هندسه *نسبت به ATR* تعریف شده، نه بر حسبِ pipِ
مطلق. پس `SL = 1.618 × ATR21ِ همان کارت` خودش را با نوسانِ داراییِ مقصد
تنظیم می‌کند. همین‌طور دروازهٔ C1 با **چارک‌همتا** ساخته می‌شود
(`build_filter_gate`): آستانه روی توزیعِ *خودِ کارتِ هدف* در همان صدکِ
کارتِ مرجع نشانده می‌شود. پس صفرِ پارامترِ نو، به معنای واقعیِ کلمه.

--------------------------------------------------------------------------------
شمارشِ چندگانگی — **پیش‌ثبت‌شده**، و عمداً بدبینانه
--------------------------------------------------------------------------------
حکمِ رسمی با بدبینانه‌ترین شمارشِ قابلِ دفاع صادر می‌شود:

    N_TRIALS_OFFICIAL = 4 (کارتِ خانوادهٔ آزمون) × 301 (بُعدِ اندازه‌گیری‌شدهٔ
                       بانکِ اندیکاتور) = 1,204        ⇒ کران ≈ E[max z](1204)

منطقِ این انتخاب: خودِ *هندسه* روی گلد پیدا شده و بهایش آنجا پرداخت شده،
پس تکرارِ ۴۵٬۱۵۰ نادرست و بیش‌شمارش است. اما رویداد و فیلترهای C1 از
جست‌وجوی ۴۰۱ اندیکاتوری بیرون آمده‌اند و آن بها **روی داراییِ نو هم** باید
پرداخت شود؛ ضربِ ۳۰۱ همان است. و ۴ چون هم‌زمان چهار کارت آزموده می‌شود.

دو شمارشِ دیگر فقط **تحلیلِ حساسیت**‌اند و حکم نیستند:
    N_FAMILY = 4      (تصحیحِ بونفرونیِ خالص روی خانوادهٔ همین آزمون)
    N_SINGLE = 1      (یک فرضیهٔ کاملاً پیش‌تعیین‌شده)
⚠️ اگر لایه فقط در `N_SINGLE` پاس کند و در حکمِ رسمی نه، **رد است** و در
گزارش صریحاً نوشته می‌شود که با کدام شمارش پاس شد. جابه‌جا کردنِ شمارش
*بعد از* دیدنِ نتیجه، تقلب است و همین‌جا ممنوع شده.

--------------------------------------------------------------------------------
مبنای اندازه‌گیری‌شده باید **همان هندسه** را داشته باشد
--------------------------------------------------------------------------------
`s347_verdict.side_null` از `_queue`ای استفاده می‌کند که `RR = 1` منجمد دارد.
مقایسهٔ لبه با مبنایی که هندسهٔ دیگری دارد بی‌معناست، پس مبنا با همان
`queue_rr(rr=3.236)` بازساخته می‌شود — عیناً همان تصمیمی که S348 گرفت.

--------------------------------------------------------------------------------
شکافِ پوششی که این ماژول می‌بندد (قانونِ MTF)
--------------------------------------------------------------------------------
فهرستِ `CARDS` پروژه، EURUSD را فقط روی `M1/M5/M15/M30` داشت. اما بندِ ۳
سندِ S348 اندازه‌گیری کرد که سربه‌سرِ مقاومِ همان چهار کارت زیرِ `RR = 1`
به **۱۸۲٪ و ۱۱۱٪** می‌رسید ⇒ آن‌ها *حسابی* ناممکن بودند. یعنی نتیجه‌گیریِ
«EURUSD لبه ندارد» بر پایهٔ چهار کارتی بود که هیچ‌کدام قابلِ پیروزی نبودند،
در حالی که `data/EURUSD_D1.csv`, `H4`, `H1`, `W1` موجود بوده و **هرگز
آزموده نشده‌اند**. این ماژول همان چهار کارت را می‌آزماید.

--------------------------------------------------------------------------------
قانونِ «اندک اندک»
--------------------------------------------------------------------------------
هر کارت که تمام شود فوراً JSONِ خودش نوشته می‌شود
(`results/_scan_S349/<card>.json`) تا ریستِ سندباکس کلِ پروسه را نبرد.
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies.s347_ensemble import (                              # noqa: E402
    SEED, P_LIST, ENS_HOLD, WARMUP_REF, build_votes, entries_for_K,
)
from strategies.s347_verdict import build_filter_gate, BANK_NEFF     # noqa: E402
from strategies.s348_rr_sweep import (                              # noqa: E402
    queue_rr, trades_df, cost_pip, SPLIT_FRAC,
)

OUT = 'results/_scan_S349'

# ============================ هندسهٔ منجمد ============================
# ⛔ این چهار عدد از `results/_scan_S348/XAUUSD-D1.json` می‌آیند و روی
#    کارت‌های مقصد **جست‌وجو نمی‌شوند**. تغییرشان بر اساسِ نتیجهٔ EURUSD،
#    نقضِ همان چیزی است که این ماژول برای اثباتش ساخته شده.
FROZEN = dict(K=13, sl_k=1.618, rr=3.236, hold=ENS_HOLD)
FROZEN_SOURCE = 'results/_scan_S348/XAUUSD-D1.json'

# ==================== کارت‌های هرگز-آزموده‌نشده ====================
TRANSFER_CARDS = {
    'EURUSD-D1': ('EURUSD', 'data/EURUSD_D1.csv'),
    'EURUSD-H4': ('EURUSD', 'data/EURUSD_H4.csv'),
    'EURUSD-H1': ('EURUSD', 'data/EURUSD_H1.csv'),
    'EURUSD-W1': ('EURUSD', 'data/EURUSD_W1.csv'),
}

# ==================== شمارشِ چندگانگیِ پیش‌ثبت‌شده ====================
N_TRIALS_OFFICIAL = len(TRANSFER_CARDS) * BANK_NEFF     # = 1,204  ← حکم
N_FAMILY = len(TRANSFER_CARDS)                          # = 4      ← حساسیت
N_SINGLE = 1                                            #          ← حساسیت


def build_null(df, asset, valid, atr_plain, n_long, n_short, rr, hold,
               n_perm, verbose=True):
    """مبنای اندازه‌گیری‌شده، به تفکیکِ سمت، با **همان** هندسهٔ منجمد."""
    rng = np.random.default_rng(SEED)
    null = {}
    for side, is_long_flag, n_side in (('long', True, n_long),
                                       ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) >= 2:
            slv = atr_plain[valid]
            ok = np.isfinite(slv) & (slv > 0)
            vi, slv = valid[ok], slv[ok]
            if len(vi) >= 2:
                s_all = queue_rr(df, vi, np.full(len(vi), is_long_flag), slv,
                                 asset, hold, rr)
                if s_all:
                    d['uncond_wr'] = s_all['wr']
                if len(vi) > n_side:
                    wrs = []
                    for _ in range(n_perm):
                        pick = np.sort(rng.choice(len(vi), size=n_side,
                                                  replace=False))
                        s_p = queue_rr(df, vi[pick],
                                       np.full(n_side, is_long_flag),
                                       slv[pick], asset, hold, rr)
                        if s_p:
                            wrs.append(s_p['wr'])
                    if wrs:
                        a = np.asarray(wrs, dtype='float64')
                        d.update(perm_mean=float(a.mean()),
                                 perm_sd=float(a.std(ddof=1)),
                                 perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        if verbose:
            print(f"      {side:<5} uncond={d['uncond_wr']} "
                  f"perm_mean={d['perm_mean']} sd={d['perm_sd']}", flush=True)
    return null


def run_card(card, n_perm=200, verbose=True):
    asset, path = TRANSFER_CARDS[card]
    df = se.load_data(path)
    close = df['close'].values.astype('float64')
    bar_time = df['dt'].values if 'dt' in df.columns else None
    warmup = max(5 * max(P_LIST), WARMUP_REF)
    split = int(len(df) * SPLIT_FRAC)
    c = cost_pip(asset)
    K, sk, rr, hold = FROZEN['K'], FROZEN['sl_k'], FROZEN['rr'], FROZEN['hold']

    print(f"\n{'='*88}\n=== S349 FROZEN TRANSFER :: {card} "
          f"(bars={len(df):,}) ===", flush=True)
    print(f"    FROZEN from {FROZEN_SOURCE}: K={K} sl_k={sk} rr={rr} "
          f"hold={hold}  [nothing is searched here]", flush=True)
    print(f"    cost={c:.2f}pip · n_trials_official={N_TRIALS_OFFICIAL:,} "
          f"(={len(TRANSFER_CARDS)}×{BANK_NEFF})", flush=True)

    if len(df) < warmup + 50:
        print(f"    !! too few bars ({len(df)}) for warmup={warmup}",
              flush=True)
        out = dict(card=card, asset=asset, bars=len(df), verdict='TOO_SHORT')
        _save(card, out)
        return out

    votes = build_votes(df, warmup)
    gate, thr = build_filter_gate(df, warmup)
    print(f"    C1 gate keeps {gate.mean()*100:.2f}% of bars", flush=True)

    vl, vs, wl, ws, atr = votes
    sig, isl, sl = entries_for_K(vl, vs, wl, ws, atr, K)
    if len(sig) == 0:
        out = dict(card=card, asset=asset, bars=len(df), verdict='NO_SIGNAL')
        _save(card, out)
        return out
    keep = gate[sig]
    sig, isl, sl = sig[keep], isl[keep], sl[keep] * sk

    st = queue_rr(df, sig, isl, sl, asset, hold, rr)
    if st is None or st['n'] < 5:
        out = dict(card=card, asset=asset, bars=len(df), verdict='NO_TRADES')
        _save(card, out)
        return out

    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(len(tr) - n_long)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    rbe = rqs2.breakeven_wr_cost(sl_med, tp_med, 2.0 * c)
    print(f"    trades n={st['n']} (L={n_long} S={n_short}) WR={st['wr']:.2f}% "
          f"exp={st['exp']:+.3f}pip PF={st['pf']:.3f}", flush=True)
    print(f"    realised bracket SL={sl_med:.1f}pip TP={tp_med:.1f}pip "
          f"rr_eff={tp_med/sl_med:.3f} · robust BE={rbe:.1f}%", flush=True)

    atr_plain = np.nanmedian(atr, axis=0) * sk
    valid = np.where(np.isfinite(atr_plain) & (atr_plain > 0))[0]
    valid = valid[(valid >= warmup) & gate[valid]]
    print(f"    null pool = {len(valid):,} bars · {n_perm} perms/side "
          f"(same frozen geometry rr={rr})", flush=True)
    null = build_null(df, asset, valid, atr_plain, n_long, n_short, rr, hold,
                      n_perm, verbose)

    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                  null=null, split_bar=split, close=close)
    res = {}
    for tag, nt in (('official', N_TRIALS_OFFICIAL), ('family', N_FAMILY),
                    ('single', N_SINGLE)):
        r = rqs2.compute_rqs2(tr, asset, n_trials=nt, **common)
        res[tag] = r
        print(rqs2.format_rqs2(f'{card} {tag:<8}', r), flush=True)

    out = dict(card=card, asset=asset, bars=len(df), cost_pip=c,
               split_bar=split, frozen=dict(FROZEN), frozen_source=FROZEN_SOURCE,
               n_trials_official=N_TRIALS_OFFICIAL, n_family=N_FAMILY,
               realised=dict(n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'],
                             sl_pip=sl_med, tp_pip=tp_med,
                             rr_eff=tp_med / sl_med, robust_be=float(rbe),
                             n_long=n_long, n_short=n_short),
               verdict=res['official']['verdict'])
    for tag in ('official', 'family', 'single'):
        r = res[tag]
        out[f'rqs2_{tag}'] = {k: r[k] for k in
                              ('verdict', 'rqs2_score', 'gates', 'metrics',
                               'notes') if k in r}
    _save(card, out)
    return out


def _save(card, out):
    os.makedirs(OUT, exist_ok=True)
    p = f'{OUT}/{card}.json'
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(f"    [checkpoint] {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cards', nargs='*', default=None)
    ap.add_argument('--n-perm', type=int, default=200)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    order = a.cards if a.cards else list(TRANSFER_CARDS.keys())
    for card in order:
        if card not in TRANSFER_CARDS:
            print(f"!! unknown card {card}", flush=True)
            continue
        try:
            run_card(card, n_perm=a.n_perm, verbose=not a.quiet)
        except Exception as e:                                   # noqa: BLE001
            import traceback
            print(f"!! {card} FAILED: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()


if __name__ == '__main__':
    main()
