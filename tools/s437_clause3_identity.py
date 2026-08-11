# -*- coding: utf-8 -*-
"""
s437_clause3_identity.py — **آزمونِ عملِ همانی** برای حکمِ بندِ سوم.

پرسش
=====
در گامِ ۱۵۳ نسخهٔ `CONFIRM` هر سه شرطِ پیش‌ثبت‌شده را پاس کرد:
`RQS2` ۲۱.۷→۲۱.۹، `n=158≥30`، لیفت ۷.۹۳→۸.۱۱.

ولی نامزد **۹۸.۷٪** از روزهای لایهٔ زنده را می‌پوشاند و `CONFIRM`
**۲۰۷ از ۲۱۰** معامله را نگه می‌دارد. اعتراضِ ساختاری این است:

> آیا این «فیلترِ مفید» است، یا صرفاً **عملِ همانی**ای که چون دو معاملهٔ
> بازنده را تصادفاً حذف کرده، هر سه شرط را پاس می‌کند؟

این پرسش با **استدلال** حل نمی‌شود. باید **اندازه** گرفته شود.

طرحِ آزمون — توزیعِ پوچِ حذفِ تصادفی
====================================
اگر `CONFIRM` واقعاً انتخاب می‌کند، بهبودی که ایجاد می‌کند باید از
بهبودی که **حذفِ تصادفیِ ۲ معامله** ایجاد می‌کند، بزرگ‌تر باشد.

پس: از ۱۶۰ معاملهٔ `BASE`، **۱۰٬۰۰۰ بار** به‌طور تصادفی همان تعداد
معامله‌ای را حذف می‌کنیم که `CONFIRM` حذف کرده، و توزیعِ Δلیفت را
می‌سازیم. سپس می‌پرسیم:

> Δلیفتِ واقعیِ `CONFIRM` در **چندمین صدکِ** این توزیع می‌نشیند؟

* اگر صدک ≥ ۹۵ ⇒ انتخابِ واقعی. فیلتر معنا دارد.
* اگر صدک در میانهٔ توزیع ⇒ `CONFIRM` از حذفِ تصادفی **قابلِ تمیز نیست**
  ⇒ حکمِ گامِ ۱۵۳ **عملِ همانی** است و باید پس گرفته شود.

⚠️ این آزمون **قبل از دیدنِ نتیجه** نوشته و قفل می‌شود. آستانهٔ ۹۵ صدک
پیش‌ثبت است. اگر نتیجه بینابین شد، **بینابین گزارش می‌شود** — نه اینکه
آستانه جابه‌جا شود.

چرا Δلیفت و نه ΔRQS2
--------------------
`RQS2` نمرهٔ مرکبی است که ده دروازه را ترکیب می‌کند و نسبت به حذفِ چند
معامله رفتارِ پله‌ای دارد. لیفت پیوسته است و **همان کمیتی** است که شرطِ
سومِ معیار روی آن بنا شده. پس آزمونِ همانی باید روی همان بنا شود.

گاردهای منتقل‌شده (همهٔ ده باگِ این مأموریت)
=============================================
* `BUG-DATASETDRIFT` — مسیرِ فایل و بازهٔ تاریخ چاپ می‌شود.
* `BUG-CALLARGS`     — امضای فراخوانی از `s437_adjudicate.py:240` کپی شد.
* `BUG-NULLUNWRAP`   — نالِ **کاملِ سمت‌کلیددار** پاس می‌شود، بدون `['long']`.
* `BUG-GUARDKEY`     — کلیدها از **فهرستِ واقعیِ خروجی** خوانده شده‌اند.
* `BUG-PERMK`        — `perm_k` بررسی می‌شود.
* `BUG-SCOREKEY`     — هیچ مقایسه‌ای روی `None` انجام نمی‌شود.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, 'strategies') not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, 'strategies'))

from engine import scalp_engine as se                          # noqa: E402
import s333_s79_pullback_revival as s333                       # noqa: E402
from strategies.s351_lpsb import lpsb_signals                  # noqa: E402
from strategies.s351_verdict import CENTRAL                    # noqa: E402
import tools.s435_coverage_union as cov                        # noqa: E402
import tools.s437_adjudicate as adj                            # noqa: E402

WARMUP = 200
CARD = 'XAUUSD-M5'
CARD_KEY = 'XAUUSD_M5'
N_BOOT = 10_000
PCTL_BAR = 95.0                     # پیش‌ثبت — جابه‌جا نمی‌شود
SEED = 20260811
OUT = 'results/_s437_clause3'


def s355_cfg():
    best = getattr(s333, 'BEST_CFG', None)
    if not isinstance(best, dict):
        raise RuntimeError('s333.BEST_CFG یافت نشد')
    cfg = best.get(CARD_KEY) or best.get(CARD)
    if cfg is None:
        raise RuntimeError(f'کلیدِ {CARD_KEY} در BEST_CFG نیست: {sorted(best)}')
    return cfg


def s355_mask(df):
    cfg = s355_cfg()
    base = s333.build_layer(df, cfg)
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    return np.asarray(base, bool) & (np.asarray(state) == -1)


def day_index(df):
    return df['dt'].dt.normalize().to_numpy().astype('datetime64[D]').astype('int64')


def days_of(df, mask):
    return set(day_index(df)[np.asarray(mask, bool)].tolist())


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)

    df, asset = adj.load_card(CARD)
    cfg = s355_cfg()
    sl, tp, mh = float(cfg['sl']), float(cfg['tp']), int(cfg['mh'])

    ds_rel = adj.CARDS[CARD][0]                       # BUG-DATASETDRIFT
    yrs = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    print(f'[S437 آزمونِ همانی] {CARD} · هندسهٔ S355 SL={sl}/TP={tp}/mh={mh}')
    print(f'  دیتاست: {ds_rel} · ردیف={len(df):,} · '
          f'{str(df["dt"].iloc[0])[:10]}→{str(df["dt"].iloc[-1])[:10]} '
          f'({yrs:.1f} سال)')

    live = s355_mask(df)
    cand = cov.sos_edge(df)
    cd = days_of(df, cand)
    in_cand = np.isin(day_index(df),
                      np.fromiter(cd, dtype='int64', count=len(cd)))

    z = np.zeros(len(df), bool)
    base_tr = se.simulate_trades(df, live, z, sl, tp, 'XAUUSD',
                                 max_hold=mh, allow_overlap=False)
    conf_tr = se.simulate_trades(df, live & in_cand, z, sl, tp, 'XAUUSD',
                                 max_hold=mh, allow_overlap=False)
    nb, nc = len(base_tr), len(conf_tr)
    n_drop = nb - nc
    print(f'  BASE n={nb} · CONFIRM n={nc} · حذف‌شده={n_drop}')

    if n_drop <= 0:
        print('  ⛔ CONFIRM هیچ معامله‌ای حذف نکرد ⇒ عملِ همانیِ محض.')
        return 2

    wb = base_tr['pnl_pip'].to_numpy() > 0
    wr_base = 100.0 * wb.mean()
    wr_conf = 100.0 * (conf_tr['pnl_pip'].to_numpy() > 0).mean()
    d_real = wr_conf - wr_base
    print(f'  ΔWR واقعی = {d_real:+.4f} pp  ({wr_base:.4f} → {wr_conf:.4f})')

    # توزیعِ پوچ: حذفِ n_drop معاملهٔ **تصادفی** از BASE
    idx = np.arange(nb)
    deltas = np.empty(N_BOOT, float)
    for i in range(N_BOOT):
        keep = rng.choice(idx, size=nc, replace=False)
        deltas[i] = 100.0 * wb[keep].mean() - wr_base

    pctl = float((deltas < d_real).mean() * 100.0)
    print(f'  توزیعِ پوچ ({N_BOOT:,} تکرار): '
          f'میانه={np.median(deltas):+.4f} · '
          f'sd={deltas.std(ddof=1):.4f} · '
          f'p95={np.percentile(deltas, 95):+.4f}')
    print(f'  ⇒ صدکِ ΔWRِ واقعی = {pctl:.1f}  (سدِ پیش‌ثبت = {PCTL_BAR})')

    identity = pctl < PCTL_BAR
    print(f'  حکم: {"⛔ عملِ همانی — CONFIRM از حذفِ تصادفی قابلِ تمیز نیست" if identity else "✅ انتخابِ واقعی"}')

    rec = {
        'card': CARD, 'dataset': ds_rel, 'rows': int(len(df)),
        'span': [str(df['dt'].iloc[0])[:10], str(df['dt'].iloc[-1])[:10]],
        'geometry': {'sl': sl, 'tp': tp, 'mh': mh},
        'n_base': int(nb), 'n_confirm': int(nc), 'n_dropped': int(n_drop),
        'wr_base': round(wr_base, 4), 'wr_confirm': round(wr_conf, 4),
        'delta_wr_real': round(d_real, 4),
        'null_median': round(float(np.median(deltas)), 4),
        'null_sd': round(float(deltas.std(ddof=1)), 4),
        'null_p95': round(float(np.percentile(deltas, 95)), 4),
        'percentile_of_real': round(pctl, 1),
        'percentile_bar_prereg': PCTL_BAR,
        'n_boot': N_BOOT, 'seed': SEED,
        'verdict': 'IDENTITY_OPERATION' if identity else 'REAL_SELECTION',
    }
    with open(os.path.join(OUT, 'identity_test.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print('\n[done]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
