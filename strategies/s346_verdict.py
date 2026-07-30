# -*- coding: utf-8 -*-
"""
S346 — داوریِ رسمیِ RQS+ روی کاندیداهای مرحلهٔ اکتشاف + **ابلیشنِ اجباریِ جهت**
================================================================================
چرا این فایل جدا از `s346_adjudicate.py` است؟
--------------------------------------------------------------------------------
`s346_adjudicate.py` گیت را از `build_features` (بانکِ دستیِ ~۱۵۰ ستونی) می‌سازد،
ولی کاندیداهای مرحلهٔ `s346_joint` فیلترهایشان از **بانکِ ۴۰۱ اندیکاتوریِ mmap**
می‌آید (پیشوندِ `B:`). آن تابع روی چنین ستونی `KeyError` می‌دهد. اینجا گیت
مستقیماً از پارتیشن‌های `.npy` خوانده می‌شود — فقط ستون‌های موردِ نیاز، با
`mmap_mode='r'` (صفحاتِ لمس‌نشده هرگز به RAM نمی‌آیند).

⭐ دو آزمونِ اجباری که هر پذیرشی باید از آن بگذرد
--------------------------------------------------------------------------------
۱) **داوریِ رسمی:** `simulate_trades(..., allow_overlap=False)` + `compute_rqs`
   (۶ دروازه، لایهٔ سرمایه: DD٪، MCL، walk-forward چهارگانه). هیچ آمارِ اکتشافی
   جای این را نمی‌گیرد.

۲) **ابلیشنِ جهت (شکارِ «بتای بازارِ گاوی طلا»):** طلا در بازهٔ داده روندِ صعودیِ
   بزرگی داشته است. یک لایهٔ `breakout/long` روی D1 می‌تواند فقط «طلا بالا رفت»
   را بازتاب دهد، نه یک الگوی کشف‌شده. پس همان هندسه و **همان فیلترها** با
   `side='short'` و `side='both'` هم سنجیده می‌شود:

     • اگر long سود بدهد و short فاجعه باشد ⇒ لبه **متقارن نیست** ⇒ این
       «قرارگیریِ جهت‌دار (directional beta)» است و باید صریحاً چنین گزارش شود.
     • اگر هر دو سمت لبهٔ مثبت داشته باشند ⇒ الگو **واقعاً ساختاری** است.

   این هم‌ارزِ ابلیشنِ زمان است که برای سپرِ اشتباهِ #۱ اجرا می‌کنیم.
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from engine import rqs as RQS
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_geom import CARDS, event_mask
from strategies.s346_bank401 import build_parts

OUT = 'results/_scan_S346'


# ------------------------------------------------------------------------------
# خواندنِ گزینشیِ ستون از پارتیشن‌های mmap
# ------------------------------------------------------------------------------
def read_cols(man, cols):
    """
    فقط ستون‌های خواسته‌شده را از قطعاتِ `.npy` می‌خواند.
    نکتهٔ حافظه: `np.load(mmap_mode='r')` صفحه‌بندیِ تنبل دارد؛ برداشتنِ یک ستون
    از یک آرایهٔ C-contiguous گران‌تر از یک سطر است، اما همچنان کلِ فایل را به
    RAM نمی‌آورد و برای ۱–۱۴ ستون کاملاً ارزان است.
    """
    need = set(cols)
    out = {}
    for p, pc in zip(man['parts'], man['part_cols']):
        hit = [c for c in pc if c in need]
        if not hit:
            continue
        arr = np.load(p, mmap_mode='r')
        for c in hit:
            out[c] = np.asarray(arr[:, pc.index(c)], dtype=np.float64)
        del arr
    missing = need - set(out)
    if missing:
        raise KeyError(f"columns not in bank manifest: {sorted(missing)}")
    return out


def gate_from_bank(man, filters, n):
    """ماسکِ بولینِ هم‌طولِ df از فهرستِ فیلترهای آستانه‌ای بانکِ ۴۰۱."""
    if not filters:
        return np.ones(n, bool)
    cols = read_cols(man, [f['col'] for f in filters])
    g = np.ones(n, bool)
    for f in filters:
        v = cols[f['col']]
        m = (v >= f['thr']) if f['dir'] == 'ge' else (v <= f['thr'])
        # NaN هرگز سیگنال تولید نمی‌کند (گارد warmup اندیکاتورها)
        g &= (m & np.isfinite(v))
    return g


# ------------------------------------------------------------------------------
# داوری یک کاندیدا
# ------------------------------------------------------------------------------
def adjudicate_row(card, geom, filters, side=None, name=None, verbose=True,
                   cache=None):
    """
    داوریِ رسمیِ یک (هندسه × مجموعهٔ فیلتر). `side` برای ابلیشن بازنویسی می‌شود.
    `cache` یک dict برای نگه‌داشتنِ df/ch/manifest بینِ فراخوانی‌ها (گران‌ترین بخش).
    """
    asset, path = CARDS[card]
    cache = cache if cache is not None else {}

    if 'df' not in cache:
        cache['df'] = se.load_data(path)
    df = cache['df']

    pkey = f"ch{geom['p']}"
    if pkey not in cache:
        cache[pkey] = adaptive_channel(df, p=geom['p'], mult=1.0)
    ch = cache[pkey]

    mkey = f"man{geom['p']}"
    if mkey not in cache:
        cache[mkey] = build_parts(card, df, ch)
    man = cache[mkey]

    warmup = max(5 * geom['p'], 250)
    ls, ss = event_mask(df, ch, geom['mode'], geom['mult'], geom['er_thr'], warmup)

    gate = gate_from_bank(man, filters, len(df))
    ls = ls & gate
    ss = ss & gate

    sd = side or geom['side']
    if sd == 'long':
        ss = np.zeros(len(df), bool)
    elif sd == 'short':
        ls = np.zeros(len(df), bool)

    pip = se.ASSETS[asset]['pip']
    atr_a = ch['atr_a']
    sl_price = geom['sl_k'] * atr_a
    tp_price = geom['rr'] * sl_price
    with np.errstate(invalid='ignore'):
        sl_pip = np.nan_to_num(sl_price / pip, nan=0.0)
        tp_pip = np.nan_to_num(tp_price / pip, nan=0.0)
    # ⛔ قیدِ ضدِ تقلبِ #۸ حتی در داوری: TP هرگز کوچک‌تر از SL نیست
    tp_pip = np.maximum(tp_pip, sl_pip)

    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset,
                            max_hold=geom['hold'], allow_overlap=False)
    r = RQS.compute_rqs(tr, asset)
    nm = name or f"{card}:{geom['mode']}/{sd}"
    if verbose:
        print("  " + RQS.format_report(nm, r), flush=True)
        m = r['metrics']
        print(f"      net=${m.get('net_profit', 0):,.1f} "
              f"exp={m.get('expectancy_pip', 0):.2f}pip "
              f"DD={m.get('max_dd_pct', 0):.1f}% MCL={m.get('max_consec_losses', 0)} "
              f"p={m.get('p_value', 1):.2e} "
              f"WRbe={m.get('wr_breakeven', 0):.1f}% "
              f"excess={m.get('wr_excess', 0):+.1f}", flush=True)
        print(f"      wf={m.get('wf_nets')} half={m.get('half_nets')}", flush=True)
    return r, tr


def geom_str(g):
    return (f"{g['mode']}/{g['side']} p={g['p']} m={g['mult']} er={g['er_thr']} "
            f"sl={g['sl_k']} rr={g['rr']} h={g['hold']}")


def flt_str(fl):
    return ' & '.join(f"{f['col']}{'≥' if f['dir'] == 'ge' else '≤'}{f['thr']:.5g}"
                      for f in fl) or '(none)'


# ------------------------------------------------------------------------------
# اجرای گروهی: کاندیداها + ابلیشنِ جهت
# ------------------------------------------------------------------------------
def run(card, top_k=6, save=True):
    src = f"{OUT}/{card}_joint_notime.json"
    d = json.load(open(src))
    reached = [r for r in d['rows'] if r.get('reached')]
    if not reached:
        print(f"!!! {card}: no reached candidate in {src}", flush=True)
        return []

    # وابستگیِ p: فیلترهای CHAN:* با p مرجعِ بانک ساخته شده‌اند، نه p هندسه ⇒
    # بازتولیدِ دقیقِ آنها تضمین‌شده نیست. اولویت به کاندیداهای بدونِ CHAN.
    def chan_dep(r):
        return any(f['col'].startswith('CHAN') for f in r['filters'])

    clean = [r for r in reached if not chan_dep(r)]
    flagged = [r for r in reached if chan_dep(r)]
    if flagged:
        print(f"  ⚠ {len(flagged)} candidate(s) use CHAN:* filters (p-coupled to the "
              f"bank reference p) — deprioritized, not adjudicated here.", flush=True)

    # انتخابِ متنوع: (الف) بیشترین n، (ب) بیشترین WR، (ج) **متقارن‌ترین** (side=both)
    pool = []
    by_n = sorted(clean, key=lambda r: -r['ALL']['n'])
    by_wr = sorted(clean, key=lambda r: -min(r['D']['wr'], r['H']['wr']))
    both = [r for r in clean if r['geom']['side'] == 'both']
    both.sort(key=lambda r: -r['ALL']['n'])
    for src_list in (both[:2], by_n[:3], by_wr[:3]):
        for r in src_list:
            if r not in pool:
                pool.append(r)
    pool = pool[:top_k]

    print(f"=== S346 FORMAL ADJUDICATION :: {card} "
          f"({len(pool)} candidates, allow_overlap=False) ===", flush=True)

    cache = {}
    out = []
    for i, r in enumerate(pool, 1):
        g, fl = r['geom'], r['filters']
        print(f"\n[{i}/{len(pool)}] {geom_str(g)}", flush=True)
        print(f"   filters: {flt_str(fl)}", flush=True)
        print(f"   discovery(fast): base_n={r['base_n']} base_wr={r['base_wr']:.2f} "
              f"-> n={r['ALL']['n']} WR={r['ALL']['wr']:.2f} PF={r['ALL']['pf']:.2f} "
              f"| D n={r['D']['n']} WR={r['D']['wr']:.2f} "
              f"| H n={r['H']['n']} WR={r['H']['wr']:.2f}", flush=True)

        rec = dict(geom=g, filters=fl, discovery=dict(D=r['D'], H=r['H'], ALL=r['ALL'],
                                                      base_n=r['base_n'],
                                                      base_wr=r['base_wr']))
        # داوریِ رسمی (جهتِ اصلی)
        rr, tr = adjudicate_row(card, g, fl, name='  FORMAL', cache=cache)
        rec['formal'] = rr

        # ⭐ ابلیشنِ اجباریِ جهت
        print("   -- side ablation --", flush=True)
        rec['ablation'] = {}
        for sd in ('long', 'short', 'both'):
            if sd == g['side']:
                continue
            ra, _ = adjudicate_row(card, g, fl, side=sd,
                                   name=f'  ABL side={sd}', cache=cache)
            rec['ablation'][sd] = ra
        out.append(rec)

        if save:
            with open(f"{OUT}/{card}_verdict.json", 'w') as fh:
                json.dump(dict(card=card, results=out), fh, default=float)
            print(f"   [checkpointed {i}/{len(pool)}]", flush=True)

    # خلاصه
    print(f"\n================ {card} VERDICT SUMMARY ================", flush=True)
    for rec in out:
        f = rec['formal']
        fails = [k for k, v in f['gates'].items() if not v]
        print(f"  RQS={f['rqs_score']:5.1f} {f['verdict']:6s} "
              f"n={f['metrics'].get('n_trades', 0):4d} "
              f"WR={f['metrics'].get('win_rate', 0):5.2f} "
              f"PF={f['metrics'].get('profit_factor', 0):5.2f} "
              f"net=${f['metrics'].get('net_profit', 0):>9,.0f} "
              f"| fail={','.join(fails) or '-':12s} | {geom_str(rec['geom'])}",
              flush=True)
    return out


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-D1'
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    run(card, top_k=k)
