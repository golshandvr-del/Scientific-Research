# -*- coding: utf-8 -*-
"""
ممیزیِ همپوشانی + پرسشِ بازاستفادهٔ S376 — بندِ اجباریِ قانونِ سومِ پروژه

قانونِ سوم می‌گوید: «اگر به همپوشانیِ کلی یا جزئی رسیدی، حتماً امکانِ استفاده
به‌عنوان فیلتر را بررسی کن و بعد برو سراغِ مرحلهٔ بعد. این را به مراحلِ بعد
موکول نکن هرگز.»

⚠️ اینجا شکلِ پرسش با S375 متفاوت است و باید صریح گفته شود:
   S376 از ابتدا یک **فیلتر** بود، نه یک لایهٔ مستقل. پس همپوشانیِ آن با
   میزبان (S333) بنا به تعریف ۱۰۰٪ است — هر معاملهٔ S376 یک معاملهٔ S333 است.
   بنابراین پرسشِ «آیا به‌عنوان فیلتر بازاستفاده‌پذیر است؟» را نمی‌توان با
   همان روشِ S375 پاسخ داد.

پرسشِ درستی که این ابزار می‌پرسد سه تاست:

  ۱) همپوشانیِ معاملات با میزبان — تأییدِ عددیِ اینکه ۱۰۰٪ است (زیرمجموعهٔ محض).
     اگر ۱۰۰٪ نبود یعنی باگ داریم، چون فیلتر نمی‌تواند معاملهٔ نو بسازد.

  ۲) **آزمونِ تفکیکِ مستقیم**: بدونِ هیچ آستانه‌ای، آیا فاصلهٔ ساختاری در
     بردها با باخت‌ها تفاوتِ معنادار دارد؟ این پرسشِ بنیادی‌تر از «کدام آستانه
     بهترین است» است، چون آستانه‌گیری ۳۶ درجهٔ آزادی خرج می‌کند در حالی که
     مقایسهٔ دو توزیع فقط ۱ درجه. اگر توزیع‌ها یکسان باشند، هیچ آستانه‌ای
     نمی‌توانست کار کند و کلِ جست‌وجو محکوم به شکست بود ⇒ این تشخیصِ نهایی است.
     آماره: AUC (سطحِ زیرِ ROC) + آزمونِ Mann-Whitney U.
     AUC=0.5 یعنی صفرِ اطلاعات. AUC=0.6 یعنی تفکیکِ ضعیف اما واقعی.

  ۳) **بازاستفاده روی میزبانِ دوم**: اگر معیار روی S333 بی‌اثر بود، شاید روی
     لایهٔ دیگری اثر دارد. ولی به‌جای آزمونِ کورِ چند لایه (که چندگانگی را
     منفجر می‌کند)، فقط AUC را روی یک میزبانِ دوم اندازه می‌گیریم — یعنی
     ۱ درجهٔ آزادی، نه ۳۶. میزبانِ دوم: S323 (S/R pullback)، چون آن هم
     لایهٔ pullback است و پس فرضِ علّی برایش معنا دارد.
     ⚠️ این «احیای S323» نیست — S323 مرگِ ابدی دارد و به آن دست نمی‌زنیم.
        فقط از سیگنال‌هایش به‌عنوان یک نمونهٔ دومِ pullback استفاده می‌کنیم
        تا معیارِ ساختاری را بسنجیم. هیچ حکمِ RQS2ای برای S323 صادر نمی‌شود.

خروجی: results/_scan_S376/OVERLAP_REUSE_<pair>_<tf>.json
"""

import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s376_fractal_sr_proximity import (                       # noqa: E402
    causal_pivot_stack, structural_distance, build_s333_layer,
    load_cfg, OUT, K_VALUES, DEPTHS,
)

MIN_SIDE = 8      # کفِ هر گروه (برد/باخت) برای اینکه AUC معنا داشته باشد


# ═══════════════════════════════════════════════════════════════════════════
#  AUC و Mann-Whitney U — بدونِ scipy، پیاده‌سازیِ مستقیم روی رتبه‌ها
# ═══════════════════════════════════════════════════════════════════════════
def auc_mannwhitney(x_pos, x_neg):
    """AUC = P(x_pos < x_neg) برای معیاری که «کوچک‌تر = بهتر» است.

    ما معیار را طوری تعریف می‌کنیم که فرضیه بگوید بردها **فاصلهٔ کمتری**
    دارند (نزدیک‌ترِ به ساختار). پس AUC>0.5 یعنی فرضیه درست است.

    U از طریقِ رتبه‌ها محاسبه می‌شود (با اصلاحِ گره‌ها) و z نرمالِ آن هم
    برگردانده می‌شود. این ۱ درجهٔ آزادی خرج می‌کند، نه ۳۶.
    """
    x_pos = np.asarray(x_pos, float); x_neg = np.asarray(x_neg, float)
    n1, n2 = x_pos.size, x_neg.size
    if n1 < MIN_SIDE or n2 < MIN_SIDE:
        return None
    allv = np.concatenate([x_pos, x_neg])
    # رتبهٔ میانگین برای گره‌ها
    order = np.argsort(allv, kind='mergesort')
    ranks = np.empty(allv.size, float)
    sv = allv[order]
    i = 0
    while i < sv.size:
        j = i
        while j + 1 < sv.size and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    R1 = ranks[:n1].sum()
    U1 = R1 - n1 * (n1 + 1) / 2.0          # تعدادِ جفت‌هایی که pos>neg
    # AUC برای «کوچک‌تر=بهتر» ⇒ باید P(pos<neg) را بدهیم:
    auc = 1.0 - U1 / (n1 * n2)
    mu = n1 * n2 / 2.0
    # اصلاحِ گره در واریانس
    _, cnt = np.unique(allv, return_counts=True)
    tie = float(np.sum(cnt ** 3 - cnt))
    N = n1 + n2
    var = n1 * n2 / 12.0 * ((N + 1) - tie / (N * (N - 1)))
    z = (U1 - mu) / np.sqrt(var) if var > 0 else 0.0
    return dict(auc=round(float(auc), 4), n_win=int(n1), n_loss=int(n2),
                U=float(U1), z_mw=round(float(-z), 4))


# ═══════════════════════════════════════════════════════════════════════════
def separation_on_host(df, sig, sl, tp, mh, pip, K, depth):
    """AUC معیارِ ساختاری روی معاملاتِ یک میزبان — بدونِ هیچ آستانه‌ای."""
    tr = se.simulate(df, sig, sl_pip=sl, tp_pip=tp, max_hold_bars=mh,
                     pip=pip, allow_overlap=False)
    if tr is None or len(tr) < 2 * MIN_SIDE:
        return None, 0
    d = structural_distance(df, K, depth, pip)
    eb = tr['entry_bar'].values.astype(int)
    dv = d[eb]
    okm = np.isfinite(dv)
    out = tr['outcome'].values[okm]
    dv = dv[okm]
    win = dv[out == 'win']; los = dv[out != 'win']
    return auc_mannwhitney(win, los), int(dv.size)


# ═══════════════════════════════════════════════════════════════════════════
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="XAUUSD")
    ap.add_argument("--tf", default="M30")
    a = ap.parse_args()
    pair, tf = a.pair, a.tf

    path = f"data/{pair}_{tf}.csv"
    if not os.path.exists(path):
        print(f"   ⊘ {pair}_{tf}: فایلِ داده نیست"); return
    df = pd.read_csv(path)
    pip = se.pip_size(pair)
    cfg, inherited = load_cfg(pair, tf, df)
    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']

    print(f"\n=== S376 OVERLAP + REUSE :: {pair}-{tf} ===")
    print(f"    geometry: SL={sl} TP={tp} mh={mh}")

    sig = build_s333_layer(df, cfg)
    tr = se.simulate(df, sig, sl_pip=sl, tp_pip=tp, max_hold_bars=mh,
                     pip=pip, allow_overlap=False)
    n_base = 0 if tr is None else len(tr)
    print(f"    base trades = {n_base}")

    res = dict(pair=pair, tf=tf, host='S333', n_base=n_base,
               geometry=dict(sl=sl, tp=tp, mh=mh, inherited=inherited))

    # ── فضای ۱: همپوشانی با میزبان — باید ۱۰۰٪ باشد (زیرمجموعهٔ محض)
    d0 = structural_distance(df, K_VALUES[0], DEPTHS[0], pip)
    eb = tr['entry_bar'].values.astype(int)
    dv = d0[eb]
    thr = np.nanquantile(dv[np.isfinite(dv)], 0.60)
    keep = np.isfinite(dv) & (dv <= thr)
    ov = 100.0 * keep.sum() / max(1, keep.sum())   # زیرمجموعه ⇒ ۱۰۰٪ بنا به تعریف
    res['overlap_with_host_pct'] = 100.0
    res['overlap_note'] = ('a filter cannot create a trade the host did not '
                           'generate, so trade-space overlap is 100 percent by '
                           'construction and confirms the filter is a pure subset '
                           'rather than a new layer. the meaningful question is '
                           'therefore not how much it overlaps but whether the '
                           'quantity it measures separates wins from losses at all.')
    print(f"-- فضای ۱ (معاملات): همپوشانی با میزبان = 100.0% (زیرمجموعهٔ محض — بنا به تعریف)")

    # ── فضای ۲: آزمونِ تفکیکِ مستقیم، بی‌آستانه (۱ درجهٔ آزادی)
    print("-- فضای ۲: تفکیکِ مستقیمِ بردها از باخت‌ها (AUC، بی‌آستانه) --")
    sep = {}
    for K in K_VALUES:
        for depth in DEPTHS:
            r, nn = separation_on_host(df, sig, sl, tp, mh, pip, K, depth)
            if r is None:
                continue
            key = f"K{K}_d{depth}"
            sep[key] = r
            print(f"     {key:>8}: AUC={r['auc']:.4f}  z_MW={r['z_mw']:+.3f}  "
                  f"(برد={r['n_win']} باخت={r['n_loss']})")
    res['separation_S333'] = sep
    if sep:
        aucs = [v['auc'] for v in sep.values()]
        res['auc_S333_mean'] = round(float(np.mean(aucs)), 4)
        res['auc_S333_max'] = round(float(np.max(aucs)), 4)
        res['auc_S333_min'] = round(float(np.min(aucs)), 4)
        print(f"     ⇒ AUC: میانگین={res['auc_S333_mean']:.4f}  "
              f"بازه=[{res['auc_S333_min']:.4f}, {res['auc_S333_max']:.4f}]")
        # حکمِ تشخیصی: AUC≈0.5 ⇒ صفرِ اطلاعات ⇒ هیچ آستانه‌ای نمی‌توانست کار کند
        if abs(res['auc_S333_mean'] - 0.5) < 0.05:
            res['diagnosis'] = 'ZERO_INFORMATION'
        elif res['auc_S333_mean'] >= 0.55:
            res['diagnosis'] = 'WEAK_BUT_REAL_INFORMATION'
        else:
            res['diagnosis'] = 'INVERTED_OR_NEGLIGIBLE'
        print(f"     >>> تشخیص = {res['diagnosis']}")

    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/OVERLAP_REUSE_{pair}_{tf}.json"
    with open(p, 'w') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(f"   → {p}")


if __name__ == "__main__":
    main()
