# -*- coding: utf-8 -*-
"""S388 — **بازاسکنِ آرشیو با آلفا به‌جای lift.**

منطقِ این ابزار در `results/S388_PREREG_ALPHA_RESCAN.md` پیش‌ثبت شد.

خلاصهٔ کشفی که این کار را ارزان می‌کند
--------------------------------------
خطِ مبنایِ «خریدارِ کور» به **سیگنالِ لایه بی‌نیاز** است — در هر کندل
وارد می‌شود و فقط به **هندسه** نیاز دارد: ``(card, sl_k, rr)``.

و آرشیوِ ۲۳٬۷۵۵ آزمونی روی فقط **۴۸ هندسهٔ متمایز** ساخته شده:

    ۸ کارت × sl_k ∈ {1.5, 2.0} × rr ∈ {1.0, 1.5, 2.0} = ۴۸

بنابراین:

    alpha(row) = row.wr − unc[(row.card, row.sl_k, row.rr)]

**۴۸ محاسبه ⇒ آلفای هر ۲۳٬۷۵۵ ردیف. صفر بک‌تستِ جدید.**

چرا آلفا و نه lift
------------------
``lift = wr − be`` که ``be`` **محاسبه** می‌شود، پس با پهن‌شدنِ هندسه
خودکار بهبود می‌یابد (قانونِ S385).
``alpha = wr − unc`` که ``unc`` **اندازه‌گیری** می‌شود، پس فقط با
مهارتِ واقعی بهبود می‌یابد.

و قانونِ S387 گفت ``n ∝ 1/alpha²`` — پس آلفا کمیتِ حاکم است.

نکاتِ صحت
---------
* خطِ مبنا با **سخت‌ترین** گامِ نمونه‌برداری از میانِ ``{1,3,7}`` گرفته
  می‌شود (محافظه‌کارانه‌ترین انتخاب — رقیبِ قوی‌تر).
* هندسهٔ خطِ مبنا **عیناً** هندسهٔ ردیف است. باگِ S386 (که خطِ مبنا را
  با ``L.RR`` پیش‌فرض می‌ساخت) اینجا با جایگزینیِ صریح داخلِ
  ``try/finally`` برای **هر ۴۸ هندسه** جلوگیری می‌شود.
* ``rr=1.0`` برای کامل‌بودنِ جدول **محاسبه** می‌شود ولی در غربالِ
  نامزدی **مطلقاً حذف** است (شرطِ A2 — اشتباهِ رایجِ ۸).
"""

from __future__ import annotations
import importlib.util
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, 'results', '_step2_rawedge')
OUTDIR = os.path.join(ROOT, 'results', '_s388')
os.makedirs(OUTDIR, exist_ok=True)

# ── بارِ چندگانگیِ صادقانه (پیش‌ثبت §۳) ───────────────────────────────
N_TRIALS = 23846           # 23755 + 30 (S384) + 5 + 8 (S386) + 48 (این سند)
Z_LUCK = 4.07              # کرانِ بونفرونی روی N_TRIALS

# ── شرایطِ نامزدی — قفل‌شده در پیش‌ثبت §۴ ─────────────────────────────
A1_MIN_ALPHA = 5.0
A2_MIN_RR = 1.5            # rr=1.0 مطلقاً حذف
A3_MIN_Z = 3.0
A4_MIN_N = 300
# A5: lift > 0

STRIDES = (1, 3, 7)


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def est_z(wr, unc, n):
    """تخمینِ z برای غربالِ اولیه.

    ``z = alpha / SE`` که ``SE = 100·√(p(1−p)/n)``.
    این تخمینِ تحلیلی است؛ نامزدهای بازمانده با جایگشتِ واقعی
    (۲۰۰۰ تکرار) بازسنجی می‌شوند.
    """
    if n <= 0:
        return None
    p = wr / 100.0
    se = 100.0 * math.sqrt(max(p * (1 - p), 1e-12) / n)
    return (wr - unc) / se if se > 0 else None


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')

    cards = sorted(f[:-5] for f in os.listdir(ARCHIVE) if f.endswith('.json'))
    print(f'S388 alpha rescan | n_trials={N_TRIALS} z_luck={Z_LUCK}')
    print(f'archive cards: {len(cards)}')
    print()

    # ── مرحلهٔ ۱: ۴۸ خطِ مبنایِ خریدارِ کور ────────────────────────────
    base_path = os.path.join(OUTDIR, 'baselines.json')
    if os.path.exists(base_path):
        baselines = json.load(open(base_path))
        print(f'baselines loaded from disk: {len(baselines)} geometries')
    else:
        baselines = {}

    print('%-12s %5s %5s %9s %9s'
          % ('card', 'sl_k', 'rr', 'unc_wr', 'cost/SL%'))
    print('-' * 46)

    for card in cards:
        arc = json.load(open(os.path.join(ARCHIVE, card + '.json')))
        sl_ks = sorted({r['sl_k'] for r in arc['rows']})
        rrs = sorted({r['rr'] for r in arc['rows']})

        df = None
        for sl_k in sl_ks:
            for rr in rrs:
                key = f'{card}|{sl_k}|{rr}'
                if key in baselines:
                    b = baselines[key]
                    print('%-12s %5.1f %5.1f %9.2f %9.2f  (cached)'
                          % (card, sl_k, rr, b['unc_wr'], b['cost_share_pct']))
                    continue

                if df is None:
                    df = L.load(card)
                    atr = L.atr(df, L.ATR_LEN)
                    ps = L.pip_size(card)

                sl_abs = (atr * sl_k).to_numpy()
                # سهمِ هزینه از حدِ‌ضرر (برایِ زمینه — قانونِ S383)
                import numpy as np
                sl_pip = float(np.nanmean(sl_abs)) / ps
                cost_pip = L.SPREAD_ABS.get(card.split('_')[0], 0.0) / ps \
                    if hasattr(L, 'SPREAD_ABS') else None
                cost_share = (cost_pip / sl_pip * 100.0) \
                    if cost_pip else float('nan')

                # ⚠️ هندسهٔ خطِ مبنا باید عیناً هندسهٔ ردیف باشد (باگِ S386)
                _bk = L.RR
                try:
                    L.RR = rr
                    unc = max(
                        NM.uncond_baseline(L, df, sl_abs, ps, s)[0] or -1e9
                        for s in STRIDES)
                finally:
                    L.RR = _bk

                baselines[key] = dict(
                    card=card, sl_k=sl_k, rr=rr, unc_wr=round(unc, 4),
                    sl_pip=round(sl_pip, 2),
                    cost_share_pct=round(cost_share, 3))
                json.dump(baselines, open(base_path, 'w'), indent=1)
                print('%-12s %5.1f %5.1f %9.2f %9.2f'
                      % (card, sl_k, rr, unc, cost_share))

    print()
    print(f'baselines complete: {len(baselines)} geometries -> {base_path}')
    print()

    # ── مرحلهٔ ۲: الحاقِ ستونِ آلفا به هر ردیف + غربال ────────────────
    allrows = []
    for card in cards:
        arc = json.load(open(os.path.join(ARCHIVE, card + '.json')))
        for r in arc['rows']:
            key = f'{card}|{r["sl_k"]}|{r["rr"]}'
            b = baselines.get(key)
            if not b:
                continue
            r = dict(r)
            r['card'] = card
            r['span_years'] = arc['span_years']
            r['unc_wr'] = b['unc_wr']
            r['alpha'] = round(r['wr'] - b['unc_wr'], 4)
            r['z_est'] = est_z(r['wr'], b['unc_wr'], r['n'])
            allrows.append(r)

    print(f'rows with alpha: {len(allrows)}')

    # همبستگی lift↔alpha (پیش‌بینیِ ۳)
    import statistics as st

    def corr(x, y):
        mx, my = st.mean(x), st.mean(y)
        num = sum((a - mx) * (b - my) for a, b in zip(x, y))
        den = (sum((a - mx) ** 2 for a in x)
               * sum((b - my) ** 2 for b in y)) ** 0.5
        return num / den if den else float('nan')

    lifts = [r['lift'] for r in allrows]
    alphas = [r['alpha'] for r in allrows]
    c_all = corr(lifts, alphas)
    print(f'corr(lift, alpha) OVERALL = {c_all:+.4f}')

    within = []
    for key in baselines:
        sub = [r for r in allrows
               if f'{r["card"]}|{r["sl_k"]}|{r["rr"]}' == key]
        if len(sub) > 30:
            within.append(corr([r['lift'] for r in sub],
                               [r['alpha'] for r in sub]))
    print(f'corr(lift, alpha) WITHIN-geometry: mean={st.mean(within):+.4f} '
          f'min={min(within):+.4f} max={max(within):+.4f} '
          f'(n_geom={len(within)})')

    # غربالِ A1..A5
    cand = [r for r in allrows
            if r['alpha'] >= A1_MIN_ALPHA
            and r['rr'] >= A2_MIN_RR
            and (r['z_est'] or 0) >= A3_MIN_Z
            and r['n'] >= A4_MIN_N
            and r['lift'] > 0]
    cand.sort(key=lambda r: -(r['z_est'] or 0))

    print()
    print(f'=== candidates passing A1..A5: {len(cand)} of {len(allrows)} '
          f'({100.0*len(cand)/len(allrows):.3f}%) ===')
    print('%-12s %-24s %5s %4s %4s %6s %7s %7s %7s %7s %6s %6s'
          % ('card', 'rule', 'side', 'sl_k', 'rr', 'n', 'wr', 'unc',
             'alpha', 'lift', 'z_est', '/yr'))
    for r in cand[:40]:
        print('%-12s %-24s %5s %4.1f %4.1f %6d %7.2f %7.2f %+7.2f %+7.2f '
              '%6.2f %6.1f'
              % (r['card'], r['rule'], r['side'], r['sl_k'], r['rr'], r['n'],
                 r['wr'], r['unc_wr'], r['alpha'], r['lift'],
                 r['z_est'] or 0, r['per_year']))

    out = dict(n_trials=N_TRIALS, z_luck=Z_LUCK,
               conditions=dict(A1_min_alpha=A1_MIN_ALPHA, A2_min_rr=A2_MIN_RR,
                               A3_min_z=A3_MIN_Z, A4_min_n=A4_MIN_N,
                               A5='lift>0'),
               n_rows=len(allrows), n_candidates=len(cand),
               corr_lift_alpha_overall=round(c_all, 4),
               corr_within_mean=round(st.mean(within), 4),
               corr_within_min=round(min(within), 4),
               corr_within_max=round(max(within), 4),
               candidates=cand[:200])
    p = os.path.join(OUTDIR, 'alpha_rescan.json')
    json.dump(out, open(p, 'w'), indent=1)
    print()
    print(f'saved -> {p}')


if __name__ == '__main__':
    main()
