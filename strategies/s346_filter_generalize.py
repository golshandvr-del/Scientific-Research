# -*- coding: utf-8 -*-
"""
S346 — آزمونِ **تعمیم‌پذیریِ فیلتر** روی خانوادهٔ پیش‌ثبت‌شده

پرسشِ دقیق
-----------
فیلترهای لایهٔ `C1` روی **یک** عضوِ خانواده برازش شدند
(`breakout/both p=13 mult=2.058 er=0.146 hold=5`). پس ۵۳ عضوِ دیگر نسبت به آن
برازش **خارج از نمونه** هستند.

    اگر فیلتر یک **خاصیتِ ساختاریِ ابزار** باشد ⇒ باید تقریباً همهٔ ۵۴ عضو را بالا ببرد.
    اگر فیلتر به **نویزِ همان یک عضو** برازش شده باشد ⇒ روی بقیه بی‌اثر یا مضر است.

این تمایز، مستقل از اندازهٔ فضای جست‌وجو، به پرسشِ «آیا فیلتر واقعی است؟» پاسخ
می‌دهد — و همان چیزی است که جریمهٔ چندگانگی نمی‌تواند بگوید (جریمه فقط می‌گوید
«شانسِ بهترین‌بودن چقدر است»، نه «آیا تعمیم می‌یابد»).

طرحِ آزمون (آزمونِ زوجی با مدلِ صفرِ «فیلترِ تصادفیِ هم‌انتخاب‌گر»)
--------------------------------------------------------------------
برای هر عضو m:
    Δ_m = WR_m(با فیلتر) − WR_m(بی‌فیلتر)
آمارهٔ آزمون: میانگینِ Δ روی همهٔ ۵۴ عضو.

⚠️ مدلِ صفرِ **درست** اینجا «زمانِ تصادفی» نیست، بلکه **فیلترِ تصادفی با همان
میزانِ انتخاب‌گری** است. چرا؟ چون هر فیلتری با کم‌کردنِ n، واریانسِ WR را بالا
می‌برد و شانسِ Δ مثبت می‌دهد. مدلِ صفر باید همان اثرِ «کوچک‌شدنِ نمونه» را
داشته باشد ولی هیچ اطلاعاتی نداشته باشد ⇒ زیرمجموعهٔ تصادفیِ **هم‌اندازه**.

نکتهٔ ظریفِ دوم: زیرمجموعهٔ تصادفی روی **رویدادها** اعمال می‌شود نه معاملات، و
سپس صفِ بی‌همپوشانی از نو ساخته می‌شود — چون فیلتر کردن، خودِ صفِ معاملات را
عوض می‌کند (رویدادِ حذف‌شده جا برای رویدادِ بعدی باز می‌کند).
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from strategies.s346_adaptive_channel import adaptive_channel      # noqa: E402
from strategies.s346_geom import CARDS, event_mask                 # noqa: E402
from strategies.s346_fast import (barrier_outcomes,                # noqa: E402
                                  select_non_overlap, stats)
from strategies.s346_bank401 import build_parts                    # noqa: E402
from strategies.s346_family import members, _queue_stats           # noqa: E402

OUT = 'results/_scan_S346'

# فیلترهای **پیش‌ثبت‌شدهٔ** لایهٔ C1 — عیناً، بدونِ هیچ بازبرازشی
C1_FILTERS = [
    dict(col='B:cg_fib_13',  dir='ge', thr=-0.05637353658676148),
    dict(col='B:std_fib_55', dir='le', thr=0.8881055116653442),
]


def gate_from_bank(man, filters, n):
    """ماسکِ دروازه از پارتیشن‌های mmapِ بانکِ ۴۰۱."""
    need = {f['col'] for f in filters}
    col = {}
    for p, pc in zip(man['parts'], man['part_cols']):
        hit = [c for c in pc if c in need]
        if not hit:
            continue
        arr = np.load(p, mmap_mode='r')
        for c in hit:
            col[c] = np.asarray(arr[:, pc.index(c)], dtype='float64')
    g = np.ones(n, bool)
    for f in filters:
        v = col.get(f['col'])
        if v is None:
            raise SystemExit(f"column {f['col']} missing from bank")
        m = (v >= f['thr']) if f['dir'] == 'ge' else (v <= f['thr'])
        g &= (m & np.isfinite(v))      # NaN هرگز سیگنال تولید نمی‌کند
    return g


def run(card='XAUUSD-D1', n_perm=300, seed=17, save=True):
    asset, path = CARDS[card]
    df = se.load_data(path)
    n = len(df)
    rng = np.random.default_rng(seed)

    print(f"=== S346 FILTER GENERALISATION :: {card} (bars={n}) ===", flush=True)
    print("    pre-registered filters (verbatim from C1, no refit):", flush=True)
    for f in C1_FILTERS:
        print(f"       {f['col']} {f['dir']} {f['thr']:.6g}", flush=True)
    print("    fitted on member: breakout/both p=13 m=2.058 er=0.146 h=5",
          flush=True)

    ch_ref = adaptive_channel(df, p=13, mult=2.058)
    man = build_parts(card, df, ch_ref)
    gate = gate_from_bank(man, C1_FILTERS, n)
    print(f"    gate keeps {gate.sum():,}/{n:,} bars "
          f"({gate.mean()*100:.1f}%)", flush=True)

    mem = members()
    rows, d_obs = [], []
    prep = []
    ch_cache = {}
    for gi, g in enumerate(mem):
        k = (g['p'], g['mult'])
        if k not in ch_cache:
            ch_cache[k] = adaptive_channel(df, p=g['p'], mult=g['mult'])
        ch = ch_cache[k]
        warmup = max(5 * g['p'], 250)
        ls, ss = event_mask(df, ch, g['mode'], g['mult'], g['er_thr'], warmup)
        ev = ls | ss
        sig_all = np.where(ev)[0]
        if len(sig_all) < 20:
            continue
        sig_f = np.where(ev & gate)[0]
        if len(sig_f) < 10:
            continue
        atr = ch['atr_a']
        st0 = _queue_stats(df, sig_all, ls[sig_all], atr[sig_all], g, asset)
        st1 = _queue_stats(df, sig_f, ls[sig_f], atr[sig_f], g, asset)
        delta = st1['wr'] - st0['wr']
        d_obs.append(delta)
        is_fit = (g['p'] == 13 and g['mult'] == 2.058 and
                  g['er_thr'] == 0.146 and g['hold'] == 5)
        rows.append(dict(geom=g, fitted_member=bool(is_fit),
                         n_bare=st0['n'], wr_bare=round(st0['wr'], 3),
                         exp_bare=round(st0['exp'], 3),
                         n_flt=st1['n'], wr_flt=round(st1['wr'], 3),
                         exp_flt=round(st1['exp'], 3),
                         d_wr=round(delta, 3),
                         d_exp=round(st1['exp'] - st0['exp'], 3)))
        prep.append(dict(geom=g, sig_all=sig_all, labels=ls[sig_all],
                         atr=atr, keep_k=len(sig_f), wr0=st0['wr'],
                         exp0=st0['exp']))
        if (gi + 1) % 12 == 0:
            print(f"    ... member {gi+1}/{len(mem)}", flush=True)

    d_obs = np.array(d_obs)
    oos = [r for r in rows if not r['fitted_member']]
    n_up = sum(1 for r in oos if r['d_wr'] > 0)
    mean_d = float(d_obs.mean())
    mean_d_oos = float(np.mean([r['d_wr'] for r in oos]))
    mean_de_oos = float(np.mean([r['d_exp'] for r in oos]))

    print(f"\n  OBSERVED  mean ΔWR over all {len(rows)} members = "
          f"{mean_d:+.3f}pp", flush=True)
    print(f"            mean ΔWR over the {len(oos)} OUT-OF-SAMPLE members = "
          f"{mean_d_oos:+.3f}pp", flush=True)
    print(f"            mean Δexp (OOS) = {mean_de_oos:+.3f}pip", flush=True)
    print(f"            members improved: {n_up}/{len(oos)} "
          f"({n_up/len(oos)*100:.1f}%)", flush=True)

    # ---- مدلِ صفر: زیرمجموعهٔ تصادفیِ هم‌اندازه (فیلترِ بی‌اطلاع) ----
    perm_d, perm_up = [], []
    for b in range(n_perm):
        ds, ups = [], 0
        for pr in prep:
            g = pr['geom']
            sa = pr['sig_all']
            if pr['keep_k'] >= len(sa) or pr['keep_k'] < 5:
                continue
            idx = np.sort(rng.choice(len(sa), size=pr['keep_k'], replace=False))
            st = _queue_stats(df, sa[idx], pr['labels'][idx],
                              pr['atr'][sa[idx]], g, asset)
            if st['n'] > 0:
                d = st['wr'] - pr['wr0']
                ds.append(d)
                ups += (d > 0)
        if ds:
            perm_d.append(float(np.mean(ds)))
            perm_up.append(ups / float(len(ds)) * 100.0)
        if (b + 1) % 25 == 0:
            a = np.array(perm_d)
            print(f"    perm {b+1}/{n_perm}  null ΔWR mean={a.mean():+.3f} "
                  f"sd={a.std(ddof=1):.3f} max={a.max():+.3f}", flush=True)

    pd_ = np.array(perm_d)
    ge = int((pd_ >= mean_d).sum())
    p_emp = (1.0 + ge) / (len(pd_) + 1.0)
    z = ((mean_d - pd_.mean()) / pd_.std(ddof=1)) if pd_.std(ddof=1) > 0 else 0.0

    from engine.rqs2 import expected_max_z
    bound = expected_max_z(1)          # فیلتر ثابت، خانواده پیش‌ثبت ⇒ N=1
    verdict = ('FILTER GENERALISES' if (z > bound and p_emp < 0.05 and
                                        mean_d_oos > 0) else 'DOES NOT GENERALISE')

    print(f"\n  {'='*72}", flush=True)
    print(f"  NULL (random equally-selective subsets, {len(pd_)} draws):",
          flush=True)
    print(f"     ΔWR mean={pd_.mean():+.3f} sd={pd_.std(ddof=1):.3f} "
          f"range=[{pd_.min():+.3f}, {pd_.max():+.3f}]", flush=True)
    print(f"     fraction-improved mean={np.mean(perm_up):.1f}%", flush=True)
    print(f"  OBSERVED ΔWR={mean_d:+.3f}  ⇒  lift={mean_d - pd_.mean():+.3f}pp "
          f"({z:.2f}σ)   p_emp={p_emp:.5f}  (#draws>=obs: {ge})", flush=True)
    print(f"  N=1 (fixed filter on pre-registered family) ⇒ bound={bound:.3f}σ",
          flush=True)
    print(f"  ⇒ {verdict}", flush=True)
    print(f"  {'='*72}", flush=True)

    print("\n  top members after filtering (by WR):", flush=True)
    for r in sorted(rows, key=lambda r: -r['wr_flt'])[:10]:
        g = r['geom']
        tag = ' <-FITTED' if r['fitted_member'] else ''
        print(f"    p={g['p']:2d} m={g['mult']:<5} er={g['er_thr']:<5} "
              f"h={g['hold']:2d} | n {r['n_bare']:4d}->{r['n_flt']:4d} "
              f"WR {r['wr_bare']:5.2f}->{r['wr_flt']:5.2f} "
              f"({r['d_wr']:+5.2f}) exp {r['exp_flt']:+7.2f}{tag}", flush=True)

    rec = dict(card=card, filters=C1_FILTERS, gate_keep_frac=float(gate.mean()),
               n_members=len(rows), mean_d_wr=round(mean_d, 4),
               mean_d_wr_oos=round(mean_d_oos, 4),
               mean_d_exp_oos=round(mean_de_oos, 4),
               n_improved_oos=n_up, n_oos=len(oos),
               n_perm=len(pd_), null_d_mean=round(float(pd_.mean()), 4),
               null_d_sd=round(float(pd_.std(ddof=1)), 4),
               null_d_max=round(float(pd_.max()), 4),
               z=round(float(z), 4), p_emp=round(p_emp, 6),
               luck_bound_n1=round(float(bound), 4), verdict=verdict,
               members=rows)
    if save:
        with open(f"{OUT}/{card}_filtergen.json", 'w') as fh:
            json.dump(rec, fh, default=float)
        print(f"  saved -> {OUT}/{card}_filtergen.json", flush=True)
    return rec


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-D1'
    nb = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    run(card, n_perm=nb)
