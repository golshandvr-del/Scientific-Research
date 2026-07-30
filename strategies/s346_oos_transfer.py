# -*- coding: utf-8 -*-
"""
S346 — آزمونِ **انتقالِ خارج‌ازنمونه** به سریِ قیمتِ دیگر

پیش‌ثبت: `results/S346_PREREGISTRATION_OOS.md` (کامیت‌شده پیش از اجرا)

پرسشِ دقیق
-----------
لبهٔ ۱۳.۰۶σ و تعمیمِ فیلترِ ۲۸.۶۳σ هر دو روی ۵۴ عضوی به‌دست آمدند که **همان یک
سریِ قیمتِ `XAUUSD-D1`** را می‌بینند. پس:

    اثبات‌شده  : فیلتر به نویزِ **یک عضو** برازش نشده
    اثبات‌نشده : فیلتر به نویزِ **سریِ D1** برازش نشده     ← این آزمون

تنها راهِ قاطع: همان خانواده + همان فیلترها، **بدونِ هیچ بازبرازشی**، روی سریِ
قیمتِ دیگر.

⚠️ تنها تبدیلِ مجاز: انتقالِ **چارک‌همتا**
--------------------------------------------
آستانه‌های خامِ D1 مقیاس‌وابسته‌اند (`std_fib_55` انحرافِ معیارِ قیمت است: روی طلا
ده‌ها دلار، روی EURUSD هزارمِ واحد). انتقالِ عددِ خام یعنی آزمونِ **مقیاس**، نه
آزمونِ **انتقال**. پس آنچه منتقل می‌شود «میزانِ انتخاب‌گری» است:

    q = چارکِ آستانهٔ D1 در توزیعِ همان اندیکاتور روی D1
    آستانهٔ هدف = همان چارکِ q روی کارتِ هدف

جمعیتِ مرجع (**پیش‌ثبت‌شده**): همهٔ کندل‌های warmup‌گذرانده با مقدارِ متناهی —
چون فیلتر روی **کندل** عمل می‌کند نه معامله.

دو مدلِ صفر — هر دو لازم
-------------------------
۱) **جای‌گشتِ زمانی** روی خانوادهٔ فیلترشده: آیا لایه روی کارتِ هدف مهارت دارد؟
   (همان تعدادِ ورود، همان نسبتِ long/short، زمانِ تصادفیِ واجدِ warmup)
۲) **زیرمجموعهٔ تصادفیِ هم‌انتخاب‌گر**: آیا فیلتر فراتر از «کوچک‌شدنِ n» چیزی
   افزود؟ (هر فیلتری با کم‌کردنِ n واریانسِ WR را بالا می‌برد و به‌شانس ΔWR مثبت
   می‌دهد؛ این مدلِ صفر همان کوچک‌شدن را با **صفر اطلاع** بازتولید می‌کند)

نکتهٔ ظریفِ اجرایی: زیرمجموعه روی **رویدادها** اعمال می‌شود و صفِ بی‌همپوشانی از
نو ساخته می‌شود، چون حذفِ یک رویداد جای صف را برای رویدادِ بعدی باز می‌کند.
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import indicator_bank as ib                            # noqa: E402
from strategies.s346_adaptive_channel import adaptive_channel      # noqa: E402
from strategies.s346_geom import CARDS, event_mask                 # noqa: E402
from strategies.s346_family import members, _queue_stats           # noqa: E402

OUT = 'results/_scan_S346'
REF_CARD = 'XAUUSD-D1'

# فیلترهای **پیش‌ثبت‌شدهٔ** C1 — عیناً، آستانه‌ها بر حسبِ **فضای بانکِ** D1
#
# ⚠️ درسِ گران‌بها (باگی که اولین اجرا لو داد): ستونِ `B:std_fib_55` در بانک
# **اندیکاتورِ خام نیست**. `_drift_fix` هر ستونی را که با زمان همبستگیِ >۰.۲۵
# داشته باشد به **زد-امتیازِ غلتانِ ۲۳۳ کندلی** تبدیل می‌کند تا مقیاس‌آزاد شود.
# `std_fib_55` انحرافِ معیارِ قیمت است و طبعاً با زمان دریفت دارد ⇒ `z233`.
# پس آستانهٔ ۰.۸۸۸ در **واحدِ زد** است، نه دلار. محاسبهٔ خامِ آن، چارک را
# ۰.۰۰۰۰ می‌داد و دروازه **۱ کندل از ۲۳٬۷۵۵** را نگه می‌داشت.
#
# ⚠️ نکتهٔ ظریفِ دوم: `_drift_fix` نوعِ تبدیل را **بر اساسِ همان کارت** تصمیم
# می‌گیرد. پس ممکن بود همان اندیکاتور روی H4 `raw` طبقه‌بندی شود و فیلتر در
# فضای دیگری تفسیر شود. برای انتقالِ منصفانه، **نوعِ تبدیلِ کارتِ مرجع تحمیل
# می‌شود** — چون معنای فیلتر در همان فضا تعریف شده است.
C1_FILTERS = [
    dict(col='cg_fib_13',  dir='ge', thr=-0.05637353658676148, kind='raw'),
    dict(col='std_fib_55', dir='le', thr=0.8881055116653442,  kind='z233'),
]
WARMUP_REF = 250          # همان کفِ warmupِ خانواده
ZWIN = 233                # عیناً `s346_bank401.ZWIN` (فیبوناچی، نه رند)


def _ind(df, name, kind='raw'):
    """یک ستونِ اندیکاتور **در همان فضای بانک** — بی‌نیاز از ساختِ کلِ بانکِ ۴۰۱.

    `kind='z233'` تبدیلِ `_drift_fix` را عیناً بازتولید می‌کند (زد-امتیازِ
    غلتان با `min_periods=55`).
    """
    v = ib.compute(name, df).values.astype('float64')
    if kind != 'z233':
        return v
    import pandas as pd
    s = pd.Series(v)
    mu = s.rolling(ZWIN, min_periods=55).mean()
    sd = s.rolling(ZWIN, min_periods=55).std()
    return ((s - mu) / sd.where(sd > 0)).values


def ref_quantiles(save=True):
    """چارکِ هر آستانه در توزیعِ همان اندیکاتور روی کارتِ مرجع (D1)."""
    path = f"{OUT}/oos_ref_quantiles.json"
    if os.path.exists(path):
        rec = json.load(open(path))
        if rec.get('ref_card') == REF_CARD:
            print(f"  ref quantiles: cache hit -> {rec['q']}", flush=True)
            return rec['q']
    _, p = CARDS[REF_CARD]
    df = se.load_data(p)
    q = {}
    for f in C1_FILTERS:
        v = _ind(df, f['col'])
        v = v[WARMUP_REF:]
        v = v[np.isfinite(v)]
        # چارکِ آستانه = سهمِ کندل‌هایی که مقدارشان از آستانه کم‌تر است
        q[f['col']] = float((v < f['thr']).mean())
        print(f"  ref {f['col']:<14} thr={f['thr']:+.6g}  ⇒  q={q[f['col']]:.4f}"
              f"   (keeps {'above' if f['dir']=='ge' else 'below'} ⇒ "
              f"{(1-q[f['col']] if f['dir']=='ge' else q[f['col']])*100:.1f}% of bars)",
              flush=True)
    if save:
        os.makedirs(OUT, exist_ok=True)
        json.dump(dict(ref_card=REF_CARD, q=q, filters=C1_FILTERS),
                  open(path, 'w'))
    return q


def transferred_gate(df, q):
    """دروازهٔ چارک‌همتا روی کارتِ هدف + آستانه‌های مطلقِ حاصل."""
    n = len(df)
    gate = np.ones(n, bool)
    thrs = {}
    for f in C1_FILTERS:
        v = _ind(df, f['col'])
        ok = np.isfinite(v)
        pool = v[WARMUP_REF:]
        pool = pool[np.isfinite(pool)]
        t = float(np.quantile(pool, q[f['col']]))
        thrs[f['col']] = t
        m = (v >= t) if f['dir'] == 'ge' else (v <= t)
        gate &= (m & ok)
        print(f"    {f['col']:<14} q={q[f['col']]:.4f} ⇒ thr={t:+.6g}",
              flush=True)
    return gate, thrs


def run(card, n_perm=200, seed=23, save=True):
    if card == REF_CARD:
        print("!!! refusing to 'transfer' onto the reference card", flush=True)
        return None
    asset, path = CARDS[card]
    df = se.load_data(path)
    n = len(df)
    rng = np.random.default_rng(seed)

    print(f"=== S346 OOS TRANSFER :: {card} (bars={n:,}) ===", flush=True)
    print("    family + filters are FROZEN from XAUUSD-D1; only the filter",
          flush=True)
    print("    thresholds are re-expressed at the SAME quantile.", flush=True)
    q = ref_quantiles()
    print("  transferred thresholds on target card:", flush=True)
    gate, thrs = transferred_gate(df, q)
    print(f"    gate keeps {gate.sum():,}/{n:,} bars "
          f"({gate.mean()*100:.2f}%)", flush=True)

    mem = members()
    rows, prep = [], []
    ch_cache = {}
    for gi, g in enumerate(mem):
        k = (g['p'], g['mult'])
        if k not in ch_cache:
            ch_cache[k] = adaptive_channel(df, p=g['p'], mult=g['mult'])
        ch = ch_cache[k]
        warmup = max(5 * g['p'], WARMUP_REF)
        ls, ss = event_mask(df, ch, g['mode'], g['mult'], g['er_thr'], warmup)
        ev = ls | ss
        sig_all = np.where(ev)[0]
        if len(sig_all) < 20:
            continue
        sig_f = np.where(ev & gate)[0]
        atr = ch['atr_a']
        st0 = _queue_stats(df, sig_all, ls[sig_all], atr[sig_all], g, asset)
        if len(sig_f) < 10:
            rows.append(dict(geom=g, n_bare=st0['n'], wr_bare=round(st0['wr'], 3),
                             exp_bare=round(st0['exp'], 3), n_flt=len(sig_f),
                             skipped='too few filtered events'))
            continue
        st1 = _queue_stats(df, sig_f, ls[sig_f], atr[sig_f], g, asset)
        rows.append(dict(geom=g,
                         n_bare=st0['n'], wr_bare=round(st0['wr'], 3),
                         exp_bare=round(st0['exp'], 3), pf_bare=round(st0['pf'], 3),
                         n_flt=st1['n'], wr_flt=round(st1['wr'], 3),
                         exp_flt=round(st1['exp'], 3), pf_flt=round(st1['pf'], 3),
                         d_wr=round(st1['wr'] - st0['wr'], 3),
                         d_exp=round(st1['exp'] - st0['exp'], 3)))
        valid = np.arange(warmup, n - g['hold'] - 2)
        valid = valid[np.isfinite(atr[valid]) & (atr[valid] > 0)]
        prep.append(dict(geom=g, sig_all=sig_all, labels_all=ls[sig_all],
                         labels_f=ls[sig_f], k_f=len(sig_f), atr=atr,
                         valid=valid, wr0=st0['wr'], exp0=st0['exp'],
                         wr1=st1['wr'], exp1=st1['exp']))
        if (gi + 1) % 12 == 0:
            print(f"    ... member {gi+1}/{len(mem)}", flush=True)

    live = [r for r in rows if 'd_wr' in r]
    if len(live) < 10:
        print(f"!!! only {len(live)} viable members on {card} — "
              f"insufficient for a family test", flush=True)
        rec = dict(card=card, status='INSUFFICIENT', n_viable=len(live),
                   members=rows)
        if save:
            json.dump(rec, open(f"{OUT}/{card}_oos.json", 'w'), default=float)
        return rec

    wr_bare = float(np.mean([r['wr_bare'] for r in live]))
    wr_flt = float(np.mean([r['wr_flt'] for r in live]))
    exp_bare = float(np.mean([r['exp_bare'] for r in live]))
    exp_flt = float(np.mean([r['exp_flt'] for r in live]))
    d_mean = float(np.mean([r['d_wr'] for r in live]))
    n_up = sum(1 for r in live if r['d_wr'] > 0)
    print(f"\n  OBSERVED over {len(live)} members:", flush=True)
    print(f"     BARE      mean WR={wr_bare:.3f}%  mean exp={exp_bare:+.3f}pip",
          flush=True)
    print(f"     FILTERED  mean WR={wr_flt:.3f}%  mean exp={exp_flt:+.3f}pip",
          flush=True)
    print(f"     ΔWR={d_mean:+.3f}pp   members improved: {n_up}/{len(live)} "
          f"({n_up/len(live)*100:.1f}%)", flush=True)

    # ---------------- مدلِ صفرِ ۱: جای‌گشتِ زمانی (خانوادهٔ فیلترشده) ------------
    print("\n  NULL-1: time permutation (does the FILTERED family have skill?)",
          flush=True)
    p1_wr, p1_exp = [], []
    for b in range(n_perm):
        wrs, exps = [], []
        for pr in prep:
            g, v = pr['geom'], pr['valid']
            if len(v) <= pr['k_f'] or pr['k_f'] < 5:
                continue
            pick = np.sort(rng.choice(v, size=pr['k_f'], replace=False))
            lab = rng.permutation(pr['labels_f'])
            st = _queue_stats(df, pick, lab, pr['atr'][pick], g, asset)
            if st['n'] > 0:
                wrs.append(st['wr'])
                exps.append(st['exp'])
        if wrs:
            p1_wr.append(float(np.mean(wrs)))
            p1_exp.append(float(np.mean(exps)))
        if (b + 1) % 25 == 0:
            a = np.array(p1_wr)
            print(f"    perm {b+1}/{n_perm}  null WR mean={a.mean():.3f} "
                  f"sd={a.std(ddof=1):.3f} max={a.max():.3f}", flush=True)

    # ---------------- مدلِ صفرِ ۲: زیرمجموعهٔ تصادفیِ هم‌انتخاب‌گر ---------------
    print("\n  NULL-2: equally-selective random subsets (does the FILTER add?)",
          flush=True)
    p2_d, p2_up = [], []
    for b in range(n_perm):
        ds, ups = [], 0
        for pr in prep:
            g, sa = pr['geom'], pr['sig_all']
            if pr['k_f'] >= len(sa) or pr['k_f'] < 5:
                continue
            idx = np.sort(rng.choice(len(sa), size=pr['k_f'], replace=False))
            st = _queue_stats(df, sa[idx], pr['labels_all'][idx],
                              pr['atr'][sa[idx]], g, asset)
            if st['n'] > 0:
                d = st['wr'] - pr['wr0']
                ds.append(d)
                ups += (d > 0)
        if ds:
            p2_d.append(float(np.mean(ds)))
            p2_up.append(ups / float(len(ds)) * 100.0)
        if (b + 1) % 25 == 0:
            a = np.array(p2_d)
            print(f"    perm {b+1}/{n_perm}  null ΔWR mean={a.mean():+.3f} "
                  f"sd={a.std(ddof=1):.3f} max={a.max():+.3f}", flush=True)

    from engine.rqs2 import expected_max_z
    bound = expected_max_z(1)      # خانواده پیش‌ثبت، فیلتر ثابت ⇒ N=1

    w1 = np.array(p1_wr)
    e1 = np.array(p1_exp)
    z1_wr = ((wr_flt - w1.mean()) / w1.std(ddof=1)) if w1.std(ddof=1) > 0 else 0.0
    z1_exp = ((exp_flt - e1.mean()) / e1.std(ddof=1)) if e1.std(ddof=1) > 0 else 0.0
    ge1 = int((w1 >= wr_flt).sum())
    p1 = (1.0 + ge1) / (len(w1) + 1.0)

    d2 = np.array(p2_d)
    z2 = ((d_mean - d2.mean()) / d2.std(ddof=1)) if d2.std(ddof=1) > 0 else 0.0
    ge2 = int((d2 >= d_mean).sum())
    p2 = (1.0 + ge2) / (len(d2) + 1.0)

    print(f"\n  {'='*74}", flush=True)
    print(f"  TEST-1  filtered family vs TIME null ({len(w1)} draws)", flush=True)
    print(f"     null WR  mean={w1.mean():.3f} sd={w1.std(ddof=1):.3f} "
          f"max={w1.max():.3f}   |  obs={wr_flt:.3f}", flush=True)
    print(f"     null exp mean={e1.mean():+.3f} sd={e1.std(ddof=1):.3f}"
          f"          |  obs={exp_flt:+.3f}", flush=True)
    print(f"     lift WR={wr_flt-w1.mean():+.3f}pp ({z1_wr:.2f}σ)   "
          f"exp={exp_flt-e1.mean():+.3f}pip ({z1_exp:.2f}σ)   p_emp={p1:.5f}",
          flush=True)
    print(f"  TEST-2  filter increment vs SUBSET null ({len(d2)} draws)",
          flush=True)
    print(f"     null ΔWR mean={d2.mean():+.3f} sd={d2.std(ddof=1):.3f} "
          f"max={d2.max():+.3f}  frac-improved={np.mean(p2_up):.1f}%", flush=True)
    print(f"     lift={d_mean-d2.mean():+.3f}pp ({z2:.2f}σ)   p_emp={p2:.5f}",
          flush=True)
    print(f"  N=1 bound = {bound:.3f}σ", flush=True)

    skill = bool(z1_wr > bound and z1_exp > bound and p1 < 0.05)
    filt = bool(z2 > bound and p2 < 0.05 and d_mean > 0)
    if skill and filt:
        verdict = 'TRANSFER CONFIRMED (skill + filter)'
    elif skill:
        verdict = 'PARTIAL: skill transfers, filter increment not proven'
    elif filt:
        verdict = 'PARTIAL: filter increments, but family lacks skill vs time null'
    else:
        verdict = 'TRANSFER FAILED'
    print(f"  ⇒ {verdict}", flush=True)
    print(f"  {'='*74}", flush=True)

    print("\n  top members after filtering (by WR):", flush=True)
    for r in sorted(live, key=lambda r: -r['wr_flt'])[:8]:
        g = r['geom']
        print(f"    p={g['p']:2d} m={g['mult']:<5} er={g['er_thr']:<5} "
              f"h={g['hold']:2d} | n {r['n_bare']:5d}->{r['n_flt']:5d} "
              f"WR {r['wr_bare']:5.2f}->{r['wr_flt']:5.2f} ({r['d_wr']:+5.2f}) "
              f"exp {r['exp_flt']:+8.2f}", flush=True)

    rec = dict(card=card, status='OK', ref_card=REF_CARD, quantiles=q,
               transferred_thresholds=thrs, gate_keep_frac=float(gate.mean()),
               n_members=len(live),
               wr_bare=round(wr_bare, 4), wr_flt=round(wr_flt, 4),
               exp_bare=round(exp_bare, 4), exp_flt=round(exp_flt, 4),
               d_wr_mean=round(d_mean, 4), n_improved=n_up,
               n_perm=len(w1),
               null1_wr_mean=round(float(w1.mean()), 4),
               null1_wr_sd=round(float(w1.std(ddof=1)), 4),
               null1_wr_max=round(float(w1.max()), 4),
               null1_exp_mean=round(float(e1.mean()), 4),
               z1_wr=round(float(z1_wr), 4), z1_exp=round(float(z1_exp), 4),
               p_emp1=round(p1, 6),
               null2_d_mean=round(float(d2.mean()), 4),
               null2_d_sd=round(float(d2.std(ddof=1)), 4),
               null2_frac_improved=round(float(np.mean(p2_up)), 2),
               z2=round(float(z2), 4), p_emp2=round(p2, 6),
               luck_bound_n1=round(float(bound), 4),
               skill_transfers=skill, filter_increments=filt,
               verdict=verdict, members=rows)
    if save:
        os.makedirs(OUT, exist_ok=True)
        json.dump(rec, open(f"{OUT}/{card}_oos.json", 'w'), default=float)
        print(f"  saved -> {OUT}/{card}_oos.json", flush=True)
    return rec


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-H4'
    nb = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    run(card, n_perm=nb)
