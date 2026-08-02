# -*- coding: utf-8 -*-
"""
S358 — نجاتِ لایهٔ `S323` از تنها دروازه‌ای که آن را زمین می‌زند: **H5**

═══════════════════════════════════════════════════════════════════════════
چرا این اسکریپت وجود دارد
═══════════════════════════════════════════════════════════════════════════
بازداوریِ `s357` روی کارتِ `XAUUSD-M30` نشان داد نسخهٔ **اصلیِ پایتونیِ** S323
ده دروازه از یازده دروازهٔ RQS2 v2.4 را پاس می‌کند و فقط روی `H5` می‌افتد:

    n=160   WR=72.50٪   ref_wr=59.84٪   lift=+12.66pp
    z_obs        = 3.266
    z_luck_bound = 3.496      ← E[max z] برای ۲۴۰۰ آزمون (قضیهٔ استراتژیِ کاذب)
    z_margin     = −0.230     ← تنها فاصلهٔ باقی‌مانده تا پذیرش

یعنی لبه **واقعی** است ولی هنوز از «بهترینِ ۲۴۰۰ تلاشِ شانسی» متمایز نشده.
حسابِ فاصله (در همین نشست انجام شد) می‌گوید برای عبور کافی است:

    · یا +۲ برد روی همان ۱۶۰ معامله  (WR: 72.50٪ → 73.39٪)
    · یا +۲۴ معامله با همان WR       (n: 160 → 184)
    · یا حذفِ **۳ باخت** بدونِ ازدست‌دادنِ هیچ برد  ⇒ z=3.590 ✅

راهِ سوم ارزان‌ترین است و دقیقاً همان چیزی است که «قانونِ بهبود» توصیف می‌کند:
یک فیلترِ ورودی که زیرمجموعه‌ای از باخت‌ها را حذف کند.

═══════════════════════════════════════════════════════════════════════════
⚠️ تلهٔ مرکزی: جست‌وجوی بیشتر، سد را بالا می‌برد
═══════════════════════════════════════════════════════════════════════════
`H5` بر پایهٔ `expected_max_z(n_trials)` است. اگر برای یافتنِ آن فیلتر، کورکورانه
هر ۴۰۱ اندیکاتورِ بانک را در چند آستانه بگردیم، `n_trials` از ۲۴۰۰ به ~۴۸۰۰
می‌رود و سد از **3.496 به ~3.68** می‌پرد. یعنی brute-force **خودش را شکست
می‌دهد**: هر فیلتری که پیدا کند، باید از سدِ بالاتری که خودش ساخته رد شود.

    expected_max_z(2400) = 3.496
    expected_max_z(2460) = 3.500      ← +۶۰ آزمون: عملاً رایگان
    expected_max_z(4800) = 3.634      ← +۲۴۰۰ آزمون: +0.14σ جریمه

پس طراحیِ این اسکریپت یک **قیدِ بودجه** است: حداکثر چند ده آزمون، انتخاب‌شده با
استدلالِ علّی دربارهٔ «چرا این لایه می‌بازد»، نه با پیمایشِ کورِ بانک. این همان
تفاوتِ «تفکرِ خطی» (بگرد تا پیدا شود) و «تفکرِ غیرخطی» (بفهم چرا می‌بازد، بعد
یک ابزارِ دقیق بردار) است که پروژه می‌خواهد.

هر آزمونی که واقعاً اجرا شود در `n_trials_used` شمرده و صادقانه به موتور داده
می‌شود؛ هیچ آزمونی از حساب پنهان نمی‌ماند. این ضدِ اشتباهِ رایج #۸ است.

═══════════════════════════════════════════════════════════════════════════
انتخابِ نامزدها — از تحلیلِ حالتِ شکست، نه از فهرستِ الفبایی
═══════════════════════════════════════════════════════════════════════════
S323 = «خرید در پولبک به حمایت، درونِ روندِ صعودی». یک چنین معامله‌ای وقتی
می‌بازد که **حمایت بشکند**. سه علتِ ریشه‌ایِ ممکن، و برای هرکدام سنجهٔ عمیقِ
متناظر از `docs/indicators/` (نه MAِ ساده — اجتنابِ صریح از اشتباهِ رایج #۳):

    ۱) «روند» در واقع رنجِ اره‌ای بوده و ADX≥22 گولمان زده
       → chop (پایین=روندی) · r2 (بالا=خطیِ تمیز) · corr_t (بالا=خلوصِ صعودی)
       → hurst (بالا=پایا) · entropy (پایین=ساختارمند)
       سند `statistical.md` صریحاً می‌گوید ترکیبِ `r2+hurst` لایهٔ S332 را از
       مرگ نجات داد؛ همان‌جا نوشته «اگر ساده‌ها جواب ندادند، اول اینجا را بگرد».

    ۲) روند خسته شده و این پولبک در واقع شروعِ برگشت است
       → fisher (اشباعِ گاوسی‌شده) · cmo (مومنتومِ خالص) · trix (شتابِ هموار)

    ۳) انفجارِ نوسان سطح را می‌درد (خبر/رویداد)
       → natr (نوسانِ نرمال‌شده) · kurt (دُمِ چاق = ریسکِ جهش) · ulcer (دردِ dd)

⇒ ۱۱ سنجه، هر کدام نمایندهٔ یک **مفهومِ متمایز** — نه ۱۱ نسخهٔ یک ایده.

آستانه‌ها: کوانتایلِ توزیعِ همان اندیکاتور **روی کندل‌های سیگنال** (نه اعدادِ
رند). این هم‌زمان اشتباهِ رایج #۷ را رفع می‌کند و آستانه را به مقیاسِ واقعیِ
هر اندیکاتور می‌چسباند بدون اینکه لازم باشد دامنه‌اش را از پیش بدانیم.

═══════════════════════════════════════════════════════════════════════════
وفاداریِ علّی (بدونِ نگاه به آینده)
═══════════════════════════════════════════════════════════════════════════
· اندیکاتور روی کلِ سری محاسبه می‌شود ولی فقط مقدارِ **کندلِ سیگنال** (بارِ i)
  خوانده می‌شود؛ ورود روی open کندلِ i+1 است ⇒ مقدار در لحظهٔ تصمیم معلوم است.
· آستانه از کوانتایلِ سیگنال‌ها می‌آید که یک ثابتِ **درون‌نمونه‌ای** است. این را
  پنهان نمی‌کنیم: به‌همین دلیل هر آستانه یک آزمونِ جدا شمرده می‌شود و `H7`
  (خارج از نمونه) هم مستقلاً باید پاس شود.
· پس از فیلتر، معاملات **بازشبیه‌سازی** می‌شوند، چون حذفِ یک ورود ممکن است
  ورودی را که قبلاً به‌خاطرِ قاعدهٔ ناهم‌پوشانی مسدود بود آزاد کند. صرفاً
  حذف‌کردنِ ردیف از جدولِ معاملات نتیجهٔ غلط می‌دهد.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import indicators as ind          # noqa: E402
from engine import rqs2 as R2                 # noqa: E402
from engine import scalp_engine as se         # noqa: E402
from engine import indicator_bank as BANK     # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s357_s323_v24_rejudge import (           # noqa: E402
    cfg_for, signals_backtested, outcome_table, wr_of, empirical_p,
)

CARD = 'XAUUSD-M30'
OUT_DIR = 'results/_s358_s323_rescue'

# بودجهٔ آزمونِ پایه که لایه با آن ساخته شده بود (از `s357`)
N_TRIALS_BASE = 2400
SEEDS = (23, 101, 777)
K_SCAN = 400        # فقط برای برآوردِ perm_mean (میانگین سریع همگرا می‌شود)
K_FULL = 2000       # برای داوریِ نهایی — سدِ H3 حداقل ۵۰۰ می‌خواهد
P_BAR = 0.001

# ───────────────────────────────────────────────────────────────────────────
# نامزدها: (نام در بانک، جهتِ نگه‌داشتن، توضیحِ علّی)
#   keep='low'  ⇒ فقط سیگنال‌هایی که مقدارشان ≤ آستانه است نگه داشته می‌شوند
#   keep='high' ⇒ فقط سیگنال‌هایی که مقدارشان ≥ آستانه است
# هر دو جهت آزموده می‌شود چون فرضِ علّیِ ما ممکن است دربارهٔ علامت اشتباه باشد؛
# ولی هزینه‌اش صادقانه در `n_trials_used` شمرده می‌شود.
# ───────────────────────────────────────────────────────────────────────────
CANDIDATES = [
    # ۱) کیفیت/واقعی‌بودنِ روند
    ('chop',    'روندی‌بودن — شاخصِ اره‌ای‌بودنِ بازار'),
    ('r2',      'خلوصِ خطیِ روند — R² رگرسیونِ قیمت بر زمان'),
    ('corr_t',  'همبستگیِ قیمت با زمان — جهت + خلوص هم‌زمان'),
    ('hurst',   'پایاییِ فراکتالی — روندی در برابر بازگشتی'),
    ('entropy', 'آنتروپیِ شانون — ساختارمندی در برابر نویز'),
    # ۲) خستگیِ روند
    ('fisher',  'تبدیلِ فیشر — اشباعِ گاوسی‌شده'),
    ('cmo',     'مومنتومِ چاند — شتابِ خالصِ بدونِ هموارسازی'),
    ('trix',    'TRIX — شتابِ سه‌بار-هموارشده'),
    # ۳) رژیمِ نوسان
    ('natr',    'ATR نرمال‌شده — نوسان نسبت به قیمت'),
    ('kurt',    'کشیدگی — ریسکِ دُمِ چاق/جهش'),
    ('ulcer',   'شاخصِ اولسر — عمق و دوامِ افت'),
]

# کوانتایل‌هایی که آستانه از آن‌ها ساخته می‌شود (غیررند، برگرفته از توزیعِ خودِ
# سیگنال‌ها). عمداً از ۰.۵ فاصله گرفته‌اند تا فیلتر واقعاً چیزی حذف کند.
QUANTILES = (0.30, 0.45, 0.60, 0.75)


# ═══════════════════════════════════════════════════════════════════════════
def binom_z(wins: int, n: int, p0: float) -> float:
    """همان آمارهٔ H5 در موتور: z دوجمله‌ای نسبت به نرخِ مرجعِ مدلِ صفر."""
    if n <= 0 or not (0.0 < p0 < 1.0):
        return float('nan')
    return (wins / n - p0) / math.sqrt(p0 * (1.0 - p0) / n)


def perm_mean_for(res, xbar, valid, k, k_perm, seed):
    """میانگینِ WR جای‌گشت‌های تصادفیِ ناهم‌پوشان با اندازهٔ k."""
    rng = np.random.default_rng(seed)
    acc, got = 0.0, 0
    for _ in range(k_perm):
        pick = np.sort(rng.choice(valid, size=min(k, valid.size), replace=False))
        w = wr_of(pick, res, xbar)
        if w is not None:
            acc += w
            got += 1
    return (acc / got) if got else None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    asset, tf = CARD.split('-')
    df = se.load_data(os.path.join('data', f'{asset}_{tf}.csv'))
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)

    cfg = cfg_for(CARD)
    atr14 = ind.atr(df, 14).values
    pip = se.ASSETS[asset]['pip']
    atr_pip_med = float(np.nanmedian(atr14[260:]) / pip)
    sl = round(cfg['slMult'] * atr_pip_med, 1)
    tp = round(cfg['tpMult'] * atr_pip_med, 1)
    mh = int(cfg['maxHold'])

    sig = signals_backtested(df, asset, cfg)
    idx = np.flatnonzero(sig)
    print(f"پایه: {CARD}  SL={sl}pip TP={tp}pip RR={tp/sl:.3f} mh={mh} "
          f"سیگنال={len(idx)}", flush=True)

    tr0 = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                             max_hold=mh, allow_overlap=False)
    n0 = len(tr0)
    w0 = int((tr0['pnl_pip'] > 0).sum())
    res, xbar = outcome_table(df, asset, sl, tp, mh)
    valid = np.arange(260, max(261, len(df) - mh - 2))
    valid = valid[res[valid] != 0]
    uncond = wr_of(valid, res, xbar)
    pm0 = perm_mean_for(res, xbar, valid, n0, K_SCAN, SEEDS[0])
    ref0 = max(uncond, pm0)
    z0 = binom_z(w0, n0, ref0 / 100.0)
    print(f"پایه: n={n0} برد={w0} WR={100*w0/n0:.2f}% ref={ref0:.2f} z={z0:.3f} "
          f"سد={R2.expected_max_z(N_TRIALS_BASE):.3f}", flush=True)

    # ── محاسبهٔ اندیکاتورهای نامزد ─────────────────────────────────────────
    print(f"\nمحاسبهٔ {len(CANDIDATES)} سنجهٔ نامزد ...", flush=True)
    series = {}
    for name, _desc in CANDIDATES:
        try:
            s = BANK.compute(name, df).values.astype(float)
            series[name] = s
        except Exception as exc:                       # noqa: BLE001
            print(f"  ✗ {name}: {exc}", flush=True)

    # ── پیمایشِ بودجه‌دار ──────────────────────────────────────────────────
    rows = []
    trials = 0
    t0 = time.time()
    for name, desc in CANDIDATES:
        if name not in series:
            continue
        s = series[name]
        vals = s[idx]
        vals = vals[np.isfinite(vals)]
        if vals.size < 30:
            print(f"  ✗ {name}: مقدارِ معتبرِ کافی روی سیگنال‌ها نیست", flush=True)
            continue
        for q in QUANTILES:
            thr = float(np.quantile(vals, q))
            for keep in ('low', 'high'):
                trials += 1
                mask = np.zeros(len(df), dtype=bool)
                sv = s[idx]
                ok = (sv <= thr) if keep == 'low' else (sv >= thr)
                ok &= np.isfinite(sv)
                mask[idx[ok]] = True
                if mask.sum() < 40:
                    continue
                tr = se.simulate_trades(df, mask, np.zeros(len(df), bool), sl, tp,
                                        asset, max_hold=mh, allow_overlap=False)
                if tr is None or len(tr) < 30:
                    continue
                n = len(tr)
                w = int((tr['pnl_pip'] > 0).sum())
                pm = perm_mean_for(res, xbar, valid, n, K_SCAN, SEEDS[0])
                ref = max(uncond, pm)
                z = binom_z(w, n, ref / 100.0)
                rows.append(dict(ind=name, desc=desc, keep=keep, q=q,
                                 thr=round(thr, 6), n=n, wins=w,
                                 wr=round(100.0 * w / n, 2), ref=round(ref, 2),
                                 lift=round(100.0 * w / n - ref, 2), z=round(z, 3),
                                 dn=n - n0, dz=round(z - z0, 3)))
    print(f"\n{trials} آزمون در {time.time()-t0:.0f}s — "
          f"سدِ جدید = expected_max_z({N_TRIALS_BASE}+{trials}) = "
          f"{R2.expected_max_z(N_TRIALS_BASE + trials):.3f}", flush=True)

    rows.sort(key=lambda r: -r['z'])
    zbar = R2.expected_max_z(N_TRIALS_BASE + trials)
    print(f"\n{'ind':9s} {'keep':5s} {'q':5s} {'n':>4s} {'WR':>6s} {'ref':>6s} "
          f"{'lift':>6s} {'z':>6s} {'Δz':>6s}")
    for r in rows[:25]:
        flag = ' ✅' if r['z'] > zbar else ''
        print(f"{r['ind']:9s} {r['keep']:5s} {r['q']:.2f}  {r['n']:4d} "
              f"{r['wr']:6.2f} {r['ref']:6.2f} {r['lift']:6.2f} {r['z']:6.3f} "
              f"{r['dz']:+6.3f}{flag}")

    out = dict(card=CARD, sl_pip=sl, tp_pip=tp, maxhold=mh,
               base=dict(n=n0, wins=w0, wr=round(100.0 * w0 / n0, 2),
                         uncond=round(uncond, 2), perm_mean=round(pm0, 2),
                         ref=round(ref0, 2), z=round(z0, 3)),
               n_trials_base=N_TRIALS_BASE, n_trials_scan=trials,
               n_trials_total=N_TRIALS_BASE + trials,
               z_bar_base=round(R2.expected_max_z(N_TRIALS_BASE), 3),
               z_bar_after=round(zbar, 3),
               quantiles=list(QUANTILES),
               candidates=[c[0] for c in CANDIDATES],
               rows=rows)
    path = os.path.join(OUT_DIR, 'scan.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"\n→ wrote {path}")


if __name__ == '__main__':
    main()
