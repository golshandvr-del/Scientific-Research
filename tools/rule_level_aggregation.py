# -*- coding: utf-8 -*-
"""تجمیعِ سطحِ قاعده (Stouffer) — پیاده‌سازیِ **§۲.۱ پاسخِ مشاور**

## چرا این ابزار، و چرا الان

مشاورِ بیرونی تشخیصِ **مرکزی**ِ خود را این‌گونه بیان کرد (`§۰`):

> «شما فرضیه‌ها را در سطحِ **کارت** (جفت‌ارز × تایم‌فریم) آزمون می‌کنید، در حالی که
> واحدِ طبیعیِ فرضیهٔ شما **قاعده** است.»

و در `§۲.۱` معماریِ سه‌سطحی پیشنهاد کرد:

- **سطحِ ۱ (استنباطی):** «آیا قاعدهٔ X لبهٔ مثبت دارد؟» — روی **تجمیعِ همهٔ کارت‌ها**
  با `z` ترکیبیِ Stouffer وزن‌دار با `√n_card`.
- **سطحِ ۲ (اقتصادی):** «روی کدام کارت مستقر شود؟» — رد شدنِ یک کارت **آزمونِ
  آماریِ جدیدی نمی‌سوزاند**.
- **سطحِ ۳ (الگویی):** آزمون‌های رتبه‌ای/ناپارامتری، «تقریباً مجانی».

`results/AUDIT_CONSULTANT_UPTAKE_GAP.md` ثبت کرد که این اقدام **انجام نشده بود** و
با تنزلِ «اقدامِ ۱» (تاریخچهٔ بلند) حالا **تنها مسیرِ صفر-هزینهٔ باقی‌مانده** برای
بزرگ کردنِ نمونه است. این ابزار همان را اجرا می‌کند.

## چه چیزی این ابزار **نیست**

- ❌ یک فیلترِ جدید نیست (مسیرِ A تعطیل است — `Q2` مشاور).
- ❌ هیچ آستانه‌ای جست‌وجو نمی‌کند. هندسه و پارامترها **عیناً** `BEST_CFG`ِ
  خودِ `S333` است، دست‌نخورده. صفر پارامترِ آزاد ⇒ صفر درجهٔ آزادیِ جست‌وجو.
- ❌ لایهٔ نو نیست. همان لایهٔ مستقرِ سایت است، فقط **در سطحِ درست** داوری می‌شود.

## روشِ آماری

برای هر کارت `i`:

```
p_i  =  P(WR_perm ≥ WR_obs)      ← از توزیعِ جای‌گشتیِ کانونیِ RQS2
z_i  =  Φ⁻¹(1 − p_i)             ← تبدیلِ یک‌طرفه
```

تجمیعِ Stouffer وزن‌دار (وزن `w_i = √n_i` — عیناً پیشنهادِ مشاور):

```
Z_agg  =  Σ w_i z_i  /  √(Σ w_i²)
```

## 🔴 تصحیحِ همبستگی — چیزی که مشاور در `§۲.۲` هشدار داد

فرمولِ بالا فرضِ **استقلالِ** `z_i`ها را دارد. اما کارت‌های یک جفت‌ارز
(`XAUUSD_M5`, `M15`, `M30`, `H1`) روی **همان بازار و همان دورهٔ تقویمی** محاسبه
می‌شوند ⇒ قطعاً همبسته‌اند. مشاور دقیقاً همین را برای `M_eff` گفت.

اگر همبستگی نادیده گرفته شود، `Z_agg` **متورم** می‌شود و این بدترین نوعِ تقلبِ
ناخواسته است: عددی که خودمان می‌خواهیم بزرگ باشد، با یک فرضِ نادرست بزرگ می‌شود.

پس واریانسِ درست با ماتریسِ همبستگیِ `R` محاسبه می‌شود:

```
Var(Σ w_i z_i)  =  Σ_i Σ_j w_i w_j R_ij
Z_agg           =  Σ w_i z_i / √(Σ_i Σ_j w_i w_j R_ij)
```

و `R_ij` **تخمینی نیست** — از همبستگیِ **سری‌های سیگنالِ باینریِ هم‌تراز‌شده روی
محورِ زمانِ تقویمی** اندازه‌گیری می‌شود. یعنی سیگنالِ `M5` و `M30` به یک شبکهٔ
زمانیِ مشترک نگاشت می‌شوند و همبستگیِ فایر/نه‌فایر مستقیماً محاسبه می‌شود.
(این همان معیارِ `(ب)` خانوادهٔ فرضیهٔ مشاور در `Q1` است: `ρ` سری‌های باینری.)

`M_eff` هم از طیفِ همان `R` با روشِ Li–Ji (مرجعِ ۴ مشاور) گزارش می‌شود.

## نردهٔ صداقت

- تجمیع **مجوزِ کوک‌کردنِ چیزی نیست**. هندسه قفل است.
- اگر `Z_agg` پاس شود، این **یک** آزمونِ سطحِ ۱ است ⇒ **یک** واحد در دفترِ
  چندگانگی، نه صفر.
- اگر `Z_agg` پاس شود، هیچ کارتی خودکار مستقر نمی‌شود؛ استقرار تصمیمِ **سطحِ ۲**
  با معیارهای اقتصادی است.
- تصحیحِ همبستگی **همیشه** `Z_agg` را کوچک‌تر یا مساوی می‌کند. اگر نتیجه پاس شد،
  با سخت‌ترین حالت پاس شده است.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as SE
import strategies.s333_s79_pullback_revival as S333

OUT = 'results/_agg_rule_level'
os.makedirs(OUT, exist_ok=True)

N_PERM = 2000          # ≥500 طبقِ v2.4؛ ۲۰۰۰ برای پایداریِ دمِ p
SEED = 20260804


# ═══════════════════════════════════════════════════════════════════════
#  ۱) بازتولیدِ لایهٔ میزبان — بدونِ هیچ تغییری
# ═══════════════════════════════════════════════════════════════════════
def card_signal(df, cfg):
    """سیگنالِ لانگِ لایهٔ `S333` با `BEST_CFG`ِ خودش. هیچ پارامترِ آزادی نیست."""
    return S333.build_layer(df, cfg)


def card_null_and_obs(pair, tf, rng):
    """مشاهده + توزیعِ جای‌گشتیِ کانونی برای یک کارت.

    مدلِ صفر **عیناً** الگویِ `build_null` نشستِ `S376` است: دو استخر
    (بی‌قید و زمینه‌محور)، سخت‌ترین (بالاترین `WR`) برنده.
    """
    card = f'{pair}_{tf}'
    cfg = S333.BEST_CFG.get(card)
    if cfg is None:
        return None

    path = f'data/{card}.csv'
    if not os.path.exists(path):
        return None
    df = SE.load_data(path)

    sig = card_signal(df, cfg)
    n_sig = int(sig.sum())
    if n_sig < 20:
        return None

    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']
    n = len(df)

    # ── مشاهده
    tr = SE.simulate_trades(df, sig, np.zeros(n, bool), sl, tp, card,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 20:
        return None
    wr_obs = float((tr['outcome'].values == 'win').mean() * 100.0)
    n_obs = int(len(tr))
    net = float(tr['pnl'].sum()) if 'pnl' in tr.columns else float('nan')

    # ── استخرها
    warm = 200
    all_bars = np.arange(warm, n - mh - 1)
    ctx = S333.regime_ctx(df, cfg) if hasattr(S333, 'regime_ctx') else None

    pools = {'uncond': all_bars}
    if ctx is not None:
        cb = all_bars[ctx[all_bars]]
        if cb.size > n_obs * 3:
            pools['ctx'] = cb

    # مبنا = سخت‌ترین (بالاترین WR)
    best = None
    for nm, pool in pools.items():
        if pool.size <= n_obs:
            continue
        take = min(pool.size, max(2000, n_obs * 20))
        idx = rng.choice(pool, size=take, replace=False)
        m = np.zeros(n, bool); m[idx] = True
        t2 = SE.simulate_trades(df, m, np.zeros(n, bool), sl, tp, card,
                                max_hold=mh, allow_overlap=True)
        if t2 is None or len(t2) < 50:
            continue
        w = float((t2['outcome'].values == 'win').mean() * 100.0)
        if best is None or w > best[1]:
            best = (nm, w, pool)
    if best is None:
        return None
    pool_name, ref_wr, pool = best

    # ── توزیعِ جای‌گشتی
    perm = []
    for _ in range(N_PERM):
        idx = rng.choice(pool, size=n_obs, replace=False)
        m = np.zeros(n, bool); m[idx] = True
        t2 = SE.simulate_trades(df, m, np.zeros(n, bool), sl, tp, card,
                                max_hold=mh, allow_overlap=False)
        if t2 is None or len(t2) == 0:
            continue
        perm.append(float((t2['outcome'].values == 'win').mean() * 100.0))
    perm = np.array(perm, float)
    if perm.size < 500:
        return None

    # p یک‌طرفه با تصحیحِ افزودنِ ۱ (بی‌اریب و هرگز صفر)
    p = float((np.sum(perm >= wr_obs) + 1.0) / (perm.size + 1.0))
    z = float(stats.norm.isf(p))

    return dict(
        card=card, pair=pair, tf=tf,
        n=n_obs, wr=round(wr_obs, 3), net=round(net, 2),
        ref_wr=round(ref_wr, 3), lift=round(wr_obs - ref_wr, 3),
        pool=pool_name,
        perm_k=int(perm.size),
        perm_mean=round(float(perm.mean()), 3),
        perm_sd=round(float(perm.std(ddof=1)), 3),
        p=p, z=round(z, 4),
        # سیگنالِ خام برای ماتریسِ همبستگی
        _sig_time=df['time'].values[sig.astype(bool)],
    )


# ═══════════════════════════════════════════════════════════════════════
#  ۲) ماتریسِ همبستگیِ **اندازه‌گیری‌شده** بینِ کارت‌ها
# ═══════════════════════════════════════════════════════════════════════
def signal_correlation(cards, grid_sec=1800):
    """`R_ij` از سری‌های باینریِ سیگنال، هم‌تراز‌شده روی شبکهٔ زمانیِ مشترک.

    هر کارت (با هر تایم‌فریمی) به یک شبکهٔ `grid_sec` ثانیه‌ای نگاشت می‌شود؛
    خانه‌ای که ≥۱ سیگنال دارد `1` می‌شود. سپس همبستگیِ پیرسون محاسبه می‌شود.

    این معیارِ `(ب)`ِ «خانوادهٔ فرضیه» در `Q1` مشاور است — و **قابلِ محاسبه
    پیش از دیدنِ سود و زیان**، همان‌طور که مشاور تأکید کرد.
    """
    k = len(cards)
    if k == 0:
        return np.zeros((0, 0))

    t_lo = min(int(c['_sig_time'].min()) for c in cards if c['_sig_time'].size)
    t_hi = max(int(c['_sig_time'].max()) for c in cards if c['_sig_time'].size)
    nb = int((t_hi - t_lo) // grid_sec) + 2

    M = np.zeros((k, nb), dtype=np.float64)
    for i, c in enumerate(cards):
        idx = ((c['_sig_time'].astype(np.int64) - t_lo) // grid_sec).astype(int)
        idx = idx[(idx >= 0) & (idx < nb)]
        M[i, idx] = 1.0

    R = np.eye(k)
    for i in range(k):
        for j in range(i + 1, k):
            a, b = M[i], M[j]
            # فقط بازهٔ تقویمیِ مشترکِ دو کارت
            ai = np.flatnonzero(a); bi = np.flatnonzero(b)
            if ai.size == 0 or bi.size == 0:
                continue
            lo = max(ai.min(), bi.min()); hi = min(ai.max(), bi.max())
            if hi <= lo:
                continue
            aa, bb = a[lo:hi + 1], b[lo:hi + 1]
            if aa.std() == 0 or bb.std() == 0:
                continue
            r = float(np.corrcoef(aa, bb)[0, 1])
            R[i, j] = R[j, i] = r if np.isfinite(r) else 0.0
    return R


def m_eff_li_ji(R):
    """`M_eff` روشِ Li–Ji (2005) — مرجعِ ۴ پاسخِ مشاور (`§۲.۲`)."""
    k = R.shape[0]
    if k <= 1:
        return float(k)
    ev = np.linalg.eigvalsh(R)
    ev = np.clip(ev, 0.0, None)
    # M_eff = Σ f(λ) ,  f(λ) = 1 + (λ − 1)·1[λ>1]  →  معادلِ Li–Ji
    contrib = np.where(ev > 1.0, 1.0 + (ev - 1.0) * 0.0 + 1.0, ev)
    # پیاده‌سازیِ استانداردِ Li–Ji: Σ [1[λ≥1] + (λ − floor(λ))]
    contrib = np.where(ev >= 1.0, 1.0, 0.0) + (ev - np.floor(ev))
    return float(np.clip(contrib.sum(), 1.0, k))


# ═══════════════════════════════════════════════════════════════════════
#  ۳) تجمیعِ Stouffer با و بدونِ تصحیحِ همبستگی
# ═══════════════════════════════════════════════════════════════════════
def stouffer(cards, R=None):
    z = np.array([c['z'] for c in cards], float)
    w = np.array([np.sqrt(c['n']) for c in cards], float)   # وزنِ پیشنهادیِ مشاور
    num = float((w * z).sum())
    var_indep = float((w ** 2).sum())
    out = dict(
        Z_indep=round(num / np.sqrt(var_indep), 4),
        sum_n=int(sum(c['n'] for c in cards)),
        k_cards=len(cards),
    )
    if R is not None and R.shape[0] == len(cards):
        var_corr = float(w @ R @ w)
        out['Z_corr'] = round(num / np.sqrt(max(var_corr, 1e-12)), 4)
        out['inflation_factor'] = round(np.sqrt(var_corr / var_indep), 4)
        out['M_eff'] = round(m_eff_li_ji(R), 3)
    return out


def main():
    rng = np.random.default_rng(SEED)
    targets = sys.argv[1:] or [
        'XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1',
        'EURUSD_M5', 'EURUSD_M15', 'EURUSD_M30', 'EURUSD_H1',
    ]

    print('=' * 104)
    print('RULE-LEVEL AGGREGATION (consultant §2.1) — host layer S333, geometry LOCKED')
    print('=' * 104)

    cards = []
    for t in targets:
        pair, tf = t.split('_')
        print(f'  {t:14s} ... ', end='', flush=True)
        r = card_null_and_obs(pair, tf, rng)
        if r is None:
            print('skipped (no cfg / no sample / null failed)')
            continue
        cards.append(r)
        print(f"n={r['n']:4d} wr={r['wr']:7.3f} ref={r['ref_wr']:7.3f} "
              f"lift={r['lift']:+7.3f} p={r['p']:.5f} z={r['z']:+.3f}")

    if len(cards) < 2:
        print('\nnot enough cards to aggregate.')
        return

    print()
    hdr = f"{'card':14s} {'n':>5s} {'wr':>8s} {'ref':>8s} {'lift':>8s} {'p':>9s} {'z':>7s} {'pool':>7s}"
    print(hdr); print('-' * len(hdr))
    for c in cards:
        print(f"{c['card']:14s} {c['n']:5d} {c['wr']:8.3f} {c['ref_wr']:8.3f} "
              f"{c['lift']:+8.3f} {c['p']:9.5f} {c['z']:+7.3f} {c['pool']:>7s}")

    R = signal_correlation(cards)
    print('\nmeasured signal-correlation matrix R:')
    names = [c['card'] for c in cards]
    print('       ' + ' '.join(f'{n[-3:]:>7s}' for n in names))
    for i, n in enumerate(names):
        print(f'{n[-12:]:>6s} ' + ' '.join(f'{R[i,j]:7.3f}' for j in range(len(names))))

    groups = {
        'ALL': cards,
        'XAUUSD': [c for c in cards if c['pair'] == 'XAUUSD'],
        'EURUSD': [c for c in cards if c['pair'] == 'EURUSD'],
    }
    res = {}
    print()
    for gname, gc in groups.items():
        if len(gc) < 2:
            continue
        idx = [names.index(c['card']) for c in gc]
        Rg = R[np.ix_(idx, idx)]
        s = stouffer(gc, Rg)
        res[gname] = s
        print(f"{gname:8s} k={s['k_cards']}  Σn={s['sum_n']:5d}  "
              f"Z_indep={s['Z_indep']:+.4f}  Z_corr={s.get('Z_corr'):+.4f}  "
              f"infl={s.get('inflation_factor')}  M_eff={s.get('M_eff')}")

    payload = dict(
        spec='consultant_section_2_1_rule_level_stouffer',
        host_layer='S333 (BEST_CFG locked, zero free parameters)',
        n_perm=N_PERM, seed=SEED,
        cards=[{k: v for k, v in c.items() if not k.startswith('_')} for c in cards],
        R=[[round(float(x), 4) for x in row] for row in R],
        R_labels=names,
        aggregation=res,
    )
    with open(os.path.join(OUT, 'stouffer.json'), 'w') as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
    print(f'\nsaved → {OUT}/stouffer.json')


if __name__ == '__main__':
    main()
