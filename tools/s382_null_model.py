# -*- coding: utf-8 -*-
"""S382 — ساختِ **مدلِ صفرِ اندازه‌گیری‌شده** برای دروازه‌های H3/H4/H5.

═══════════════════════════════════════════════════════════════════════════
چرا این ابزار وجود دارد
═══════════════════════════════════════════════════════════════════════════

اجرای rqs2 روی S382 هشت دروازه از یازده را پاس کرد و سه دروازه را
`UNKNOWN` گذاشت با این یادداشتِ صریح:

    «H3 UNKNOWN: no measured null model supplied —
     absence of a control is not evidence of skill»

این یادداشت **دقیقاً همان چیزی است که معیار باید بگوید**. نبودِ گروهِ
کنترل، شاهدِ مهارت نیست. تا وقتی ندانیم «یک معامله‌گرِ بی‌مهارت با همین
هندسه چه WR می‌گیرد»، عددِ ۴۸.۹۱٪ هیچ معنایی ندارد.

═══════════════════════════════════════════════════════════════════════════
دو خطِ مبنایِ مستقل — و چرا **هر دو** لازم است
═══════════════════════════════════════════════════════════════════════════

خطِ مبنای ①: **WRِ بی‌قید** (`uncond_wr`)
    اگر در **هر کندل** وارد شویم (بدون هیچ سیگنالی) و همان بریسکتِ
    SL=122.85 / TP=184.28 را بگذاریم، چند درصد برنده می‌شویم؟

    این خطِ مبنا یک چیزِ حیاتی را می‌سنجد که سربه‌سرِ هندسی **نمی‌سنجد**:
    سربه‌سر فرض می‌کند حرکتِ قیمت متقارن است. ولی طلا در ۱۵.۵ سال روندِ
    صعودیِ عظیمی داشته. پس یک خریدارِ کاملاً کور هم ممکن است WRِ بالای
    سربه‌سر بگیرد — نه از مهارت، بلکه از سواری گرفتن روی روندِ بازار.
    این «بتا»ی بازار است، نه «آلفا»ی لایه.

    ⚠️ این خطرِ اصلیِ S382 است: لایه **لانگ-only** است روی داراییی که
    ۱۵ سال صعودی بوده. اگر `uncond_wr` هم بالای ۴۱.۰۷ باشد، آنگاه
    +۷.۸۳ واحد لبه‌ای که دیدیم ممکن است **صفر آلفا** باشد.

خطِ مبنای ②: **جای‌گشتِ زمانی** (`perm_mean`, `perm_sd`, `perm_max`)
    همان **تعدادِ** سیگنال را برمی‌داریم، ولی زمان‌بندی‌شان را تصادفی
    می‌کنیم. اگر لایه صرفاً «تعدادِ زیادی معامله در یک بازارِ صعودی»
    باشد، جای‌گشت همان WR را می‌دهد ⇒ صفر مهارت.

    این خطِ مبنا چیزی را می‌سنجد که خطِ ① نمی‌سنجد: خطِ ① همهٔ کندل‌ها
    را می‌گیرد، ولی جای‌گشت **همان تعدادِ محدود** را می‌گیرد، پس نویزِ
    نمونهٔ کوچک را هم مدل می‌کند و `perm_max` می‌گوید «شانسِ محض در
    بهترین حالت تا کجا می‌تواند برسد».

`_side_null_ref` در rqs2 از این دو، **بزرگ‌ترین** را برمی‌دارد
(نه میانگین) — یعنی سخت‌ترین رقیبِ بی‌مهارت. این محافظه‌کاریِ درست است.

═══════════════════════════════════════════════════════════════════════════
انتخاب‌های محافظه‌کارانه در این ابزار
═══════════════════════════════════════════════════════════════════════════

۱) **همان شبیه‌سازِ لایه** استفاده می‌شود (`simulate_trades` از ماژولِ
   S382)، نه یک نسخهٔ دوم. علت: پروژه قبلاً از داشتنِ دو نسخهٔ ناهمگام
   آسیب دیده (دانشِ سربه‌سر در `rqs2_site_triage` بود ولی در ابزارِ
   حسابرسی نبود). اگر مدلِ صفر با شبیه‌سازِ دیگری ساخته شود، تفاوتِ
   شبیه‌ساز با تفاوتِ مهارت اشتباه گرفته می‌شود.

۲) **قیدِ عدمِ هم‌پوشانی در مدلِ صفر هم اعمال می‌شود.** اگر مدلِ صفر
   هم‌پوشانی داشت ولی لایه نداشت، مقایسه ناعادلانه می‌شد.

۳) **بذرِ ثابت** (`SEED = 20260805`) تا نتیجه بازتولیدپذیر باشد. چهار
   ریستِ سندباکس نشان داد بازتولیدپذیری یک تجملِ نظری نیست.

۴) تعدادِ جای‌گشت `K = 2000`. علت: `perm_max` تخمینِ دمِ توزیع است و
   دم با نمونهٔ کم بی‌ثبات است. ۲۰۰۰ اجرا `perm_max` را پایدار می‌کند.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OUT = 'results/_s382'
SEED = 20260805
K = 2000


def load_layer():
    """بارگذاریِ ماژولِ S382 — تا **همان** شبیه‌ساز استفاده شود."""
    spec = importlib.util.spec_from_file_location(
        '_s382', os.path.join(ROOT, 'strategies', 's382_williamsr_momentum.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def uncond_baseline(L, df, sl_abs, ps, stride):
    """خطِ مبنای ①: ورود در **هر کندل** (بدون هیچ سیگنالی).

    `stride` برای کارآمدی: به‌جای هر کندل، هر n-اُمین کندل. چون قیدِ
    عدمِ هم‌پوشانی به‌هرحال بیشترِ سیگنال‌ها را حذف می‌کند، stride=1 و
    stride=3 نتیجهٔ تقریباً یکسان می‌دهند — ولی برای شفافیت گزارش می‌شود.
    """
    sig = pd.Series(False, index=df.index)
    sig.iloc[::stride] = True
    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
    if len(tr) == 0:
        return None, 0
    return 100.0 * float((tr['outcome'] == 'win').mean()), len(tr)


def perm_baseline(L, df, sl_abs, ps, n_sig, k=K, seed=SEED):
    """خطِ مبنای ②: جای‌گشتِ **زمان‌بندیِ** سیگنال‌ها.

    همان `n_sig` سیگنال، ولی در موقعیت‌های تصادفی. تعدادِ سیگنالِ خام
    حفظ می‌شود (نه تعدادِ معامله)، چون قیدِ عدمِ هم‌پوشانی باید **به همان
    شکلِ لایه** روی مدلِ صفر هم اثر بگذارد تا مقایسه عادلانه بماند.
    """
    rng = np.random.default_rng(seed)
    n = len(df)
    lo, hi = 200, n - 2          # حاشیه: ATR(100) و کندلِ خروج
    wrs = []
    for _ in range(k):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        sig = pd.Series(False, index=df.index)
        sig.iloc[np.sort(pos)] = True
        tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
        if len(tr) >= 30:
            wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
    a = np.asarray(wrs, float)
    return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)),
                max=float(a.max()), min=float(a.min()),
                p95=float(np.percentile(a, 95)), k=int(len(a)))


def main():
    os.makedirs(OUT, exist_ok=True)
    L = load_layer()
    df = L.load(L.CARD)
    ps = L.pip_size(L.ASSET)
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    sig = L.signals(df)
    n_sig = int(sig.fillna(False).sum())
    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_abs / ps + 3.3) / (sl_abs * L.RR / ps + sl_abs / ps)

    print(f'layer: n_sig={n_sig}  n_trades={len(tr)}  '
          f'wr={obs_wr:.2f}%  be={be:.2f}%  lift={obs_wr-be:+.2f}')
    print()

    print('=== baseline (1): unconditional entry, zero signal ===')
    rows = []
    for stride in (1, 3, 7):
        wr, n = uncond_baseline(L, df, sl_abs, ps, stride)
        rows.append((stride, wr, n))
        print(f'  stride={stride}: n={n:5d}  wr={wr:6.2f}%  '
              f'vs be={be:.2f} -> {wr-be:+6.2f}  '
              f'vs layer={obs_wr:.2f} -> {obs_wr-wr:+6.2f}')
    uncond_wr = max(r[1] for r in rows)   # سخت‌ترین مبنا
    print(f'  => hardest unconditional baseline = {uncond_wr:.2f}%')
    print()

    print(f'=== baseline (2): timing permutation, k={K} ===')
    p = perm_baseline(L, df, sl_abs, ps, n_sig)
    print(f'  mean={p["mean"]:.2f}%  sd={p["sd"]:.2f}  '
          f'min={p["min"]:.2f}  p95={p["p95"]:.2f}  max={p["max"]:.2f}  '
          f'(k={p["k"]})')
    z = (obs_wr - p['mean']) / p['sd'] if p['sd'] > 0 else float('nan')
    print(f'  observed {obs_wr:.2f}% -> z = {z:.2f}')
    print(f'  exceeds perm_max? {"YES" if obs_wr > p["max"] else "NO"}')
    print()

    null = {'long': dict(uncond_wr=uncond_wr, perm_mean=p['mean'],
                         perm_sd=p['sd'], perm_max=p['max'], perm_k=p['k']),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    payload = dict(card=L.CARD, obs_wr=obs_wr, be=be, n_trades=len(tr),
                   n_signals=n_sig, uncond=rows, perm=p, null=null,
                   seed=SEED, k=K)
    with open(f'{OUT}/null_model.json', 'w') as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f'saved -> {OUT}/null_model.json')


if __name__ == '__main__':
    main()
