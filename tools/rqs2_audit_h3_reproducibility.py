"""حسابرسیِ بازتولیدپذیریِ H3 — آیا حکمِ ACCEPT/REJECT به پارامترهایِ محاسباتی
(تعدادِ قرعه K و بذرِ تصادفی seed) وابسته است؟

پرسشِ علمی: یک معیارِ معتبر باید روی یک لایهٔ **ثابت** و دادهٔ **ثابت** همیشه
همان حکم را بدهد. اگر عوض‌کردنِ `n_perm` یا `seed` — که هیچ‌کدام خاصیتِ لایه
نیستند، بلکه انتخاب‌های محاسباتیِ ما هستند — حکم را برگرداند، آن‌گاه حکم
خاصیتِ لایه نیست، خاصیتِ اجرا است.

روش: لایهٔ S354 (پیکربندیِ causal، همان که در `_final_honest_verdict.json`
ثبت شده) را روی XAUUSD-H1 با شبکه‌ای از (K, seed) بازداوری می‌کنیم و برای هر
اجرا ثبت می‌کنیم:
    lift · z_skill · perm_max · شرطِ A (z>=3) · شرطِ B (wr>perm_max) · H3

خروجی به‌صورتِ تدریجی (`اندک اندک`) در JSON نوشته می‌شود تا ریستِ سندباکس
پیشرفت را نبرد.

⚠️ این ابزار **هیچ چیزی را در معیار تغییر نمی‌دهد** — فقط اندازه‌گیری می‌کند.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2 as R2                  # noqa: E402
from strategies import s354_brooks_trend_resumption as base   # noqa: E402
from strategies import s354_improve_long as imp               # noqa: E402
from strategies import s354_causal_check as cc                # noqa: E402

OUT = 'results/_audit_H3/reproducibility.json'

# شبکهٔ آزمایش: K های متعارفِ پروژه × چند بذر
K_GRID = [100, 200, 400, 1000, 2000]
SEED_GRID = [11, 23, 47, 101, 199, 307]


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df = se.load_data('data/XAUUSD_H1.csv')
    atr = base._atr_pip(df, 'XAUUSD', base.TF_ATR_P.get('H1', 34))
    mh = base.TF_MAX_HOLD.get('H1', 20)
    sl = round(1.3 * atr, 1)
    tp = round(2.0 * sl, 1)
    gate = base.regime_gate(df, ('r2_fib_55', 'ge', 0.45))
    split = int(len(df) * 0.60)

    # لایهٔ ثابت و بدونِ تغییر در تمامِ اجراها (پیکربندیِ causal)
    sig = cc.build_signals_causal(df, 'XAUUSD', 'H1', 0.13, 16, 0.8, 12.0) & gate
    no_short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, no_short, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)

    rows = []
    if os.path.exists(OUT):
        try:
            rows = json.load(open(OUT)).get('runs', [])
        except Exception:
            rows = []
    done = {(r['K'], r['seed']) for r in rows}

    for K in K_GRID:
        for sd in SEED_GRID:
            if (K, sd) in done:
                continue
            null = imp.build_null_canonical(df, sig, sl, tp, mh, n_perm=K, seed=sd)
            res = R2.compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                                  bar_time=df['time'].values, close=df['close'].values,
                                  null=null, n_trials=96, split_bar=split)
            m = res['metrics']
            wr = m['win_rate']
            pmax = m.get('perm_max')
            z = m.get('skill_z')
            lift = m.get('skill_lift_pp')
            row = dict(K=K, seed=sd, n=len(tr), wr=wr, perm_max=pmax,
                       z=z, lift=lift,
                       condA_z_ge_3=(z is not None and z >= 3.0),
                       condB_wr_gt_permmax=(pmax is not None and wr > pmax),
                       condC_lift_ge_4=(lift is not None and lift >= 4.0),
                       H3=res['gates']['H3'],
                       rqs2=res['rqs2_score'], verdict=res['verdict'])
            rows.append(row)
            # ذخیرهٔ تدریجی — قانونِ «اندک اندک»
            json.dump({'layer': 'S354 causal XAUUSD-H1 (fixed)', 'runs': rows},
                      open(OUT, 'w'), indent=1, default=float)
            print(f"K={K:5d} seed={sd:4d}  wr={wr:6.2f} pmax={pmax:6.2f} "
                  f"z={z:5.2f} lift={lift:6.2f} | A={row['condA_z_ge_3']} "
                  f"B={row['condB_wr_gt_permmax']} => H3={row['H3']}", flush=True)

    # خلاصهٔ تحلیلی
    print('\n=== SUMMARY: verdict stability ===', flush=True)
    for K in K_GRID:
        sub = [r for r in rows if r['K'] == K]
        if not sub:
            continue
        nB = sum(1 for r in sub if r['condB_wr_gt_permmax'])
        nH = sum(1 for r in sub if r['H3'])
        pm = [r['perm_max'] for r in sub]
        print(f"K={K:5d}: perm_max range [{min(pm):.2f},{max(pm):.2f}] "
              f"spread={max(pm)-min(pm):.2f}pp | condB passed {nB}/{len(sub)} "
              f"| H3 passed {nH}/{len(sub)}", flush=True)


if __name__ == '__main__':
    main()
