# -*- coding: utf-8 -*-
"""
S346 — آزمونِ **انتقالِ خالص** لایهٔ پذیرفته‌شده به سایرِ کارت‌ها (قانونِ MTF، بندِ ۱)
================================================================================
منطق: لایهٔ `breakout/both p=13` روی `XAUUSD-D1` هر ۶ دروازه را پاس کرد و در
ابلیشنِ جهت هم متقارن ماند. اما «قبول روی یک تایم‌فریم» نتیجه‌گیریِ تک‌تایم‌فریمیِ
اشتباه (#۵) است. دو آزمونِ متفاوت لازم است:

  **الف) انتقالِ خالص (این فایل):** *دقیقاً* همان هندسه و همان آستانه‌های عددی
       روی کارت‌های دیگر اجرا می‌شود — **هیچ برازشی نه**. این سخت‌گیرانه‌ترین
       آزمونِ خارج‌ازنمونه‌ای است که وجود دارد: اگر لبه واقعاً ساختاری باشد باید
       دستِ‌کم علامتِ درست را در مقیاس‌های دیگر نشان دهد.

  **ب) بازبرازشِ اختصاصیِ هر کارت:** طبق بندِ ۲ قانونِ MTF («هر تایم‌فریم ممکن
       است بهبودِ متناسبِ خودش را لازم داشته باشد») — با `s346_joint.run_card`.

⚠️ نکتهٔ مقیاس (چرا انتقالِ خام می‌تواند گمراه‌کننده باشد):
آستانهٔ `B:std_fib_55 ≤ 0.888` یک عددِ **بُعددار** است (واحدِ قیمت). انحرافِ معیارِ
۵۵ کندلیِ طلا روی D1 و روی M5 دو مقیاسِ کاملاً متفاوت دارند. پس انتقالِ خام
عملاً روی تایم‌فریمِ ریزتر همیشه «true» و روی درشت‌تر همیشه «false» می‌شود.
⇒ به همین دلیل هر دو حالت گزارش می‌شود:
   • `RAW`      : آستانهٔ عددیِ عیناً منتقل‌شده (آزمونِ سخت، ولی مقیاس‌حساس)
   • `QUANTILE` : همان **چارکِ** آستانه در توزیعِ کارتِ مقصد بازسازی می‌شود
                  (آزمونِ منصفانه: «همان رژیم» نه «همان عدد»).
این تفکیک، خودِ سؤالِ علمی را تیز می‌کند: آیا لبه به یک *عدد* بند است یا به یک
*رژیم*؟ اگر QUANTILE منتقل شود ولی RAW نه، لبه رژیمی است — که مطلوب‌تر است.
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
from strategies.s346_verdict import read_cols, adjudicate_row, geom_str, flt_str

OUT = 'results/_scan_S346'

# ------------------------------------------------------------------------------
# لایهٔ مرجع: تنها کاندیدای XAUUSD-D1 که ابلیشنِ جهت را رد نکرد
#   both : RQS 83.9 | long تنها: RQS 82.9 | short تنها: RQS 82.2  ⇒ متقارن
# ------------------------------------------------------------------------------
REF_GEOM = dict(mode='breakout', side='both', p=13, mult=2.058, er_thr=0.146,
                sl_k=1.0, rr=1.0, hold=5, tp_mode='atr')
REF_FILTERS = [
    dict(col='B:cg_fib_13',  dir='ge', thr=-0.056374),
    dict(col='B:std_fib_55', dir='le', thr=0.88811),
]
REF_CARD = 'XAUUSD-D1'


def ref_quantiles(card=REF_CARD, geom=REF_GEOM, filters=REF_FILTERS):
    """چارکِ هر آستانه در توزیعِ کارتِ **مرجع** (تا در مقصد بازسازی شود)."""
    asset, path = CARDS[card]
    df = se.load_data(path)
    ch = adaptive_channel(df, p=geom['p'], mult=1.0)
    man = build_parts(card, df, ch)
    cols = read_cols(man, [f['col'] for f in filters])
    qs = []
    for f in filters:
        v = cols[f['col']]
        v = v[np.isfinite(v)]
        q = float((v <= f['thr']).mean())
        qs.append(q)
        print(f"   ref quantile of {f['col']} at thr={f['thr']:.6g}: q={q:.4f}",
              flush=True)
    return qs


def rescaled_filters(card, geom, filters, qs):
    """همان چارک‌ها را در توزیعِ کارتِ مقصد به آستانهٔ عددیِ نو ترجمه می‌کند."""
    asset, path = CARDS[card]
    df = se.load_data(path)
    ch = adaptive_channel(df, p=geom['p'], mult=1.0)
    man = build_parts(card, df, ch)
    cols = read_cols(man, [f['col'] for f in filters])
    out = []
    for f, q in zip(filters, qs):
        v = cols[f['col']]
        v = v[np.isfinite(v)]
        thr = float(np.quantile(v, q)) if len(v) else f['thr']
        out.append(dict(col=f['col'], dir=f['dir'], thr=thr))
    return out


def run(cards=None, save=True):
    cards = cards or [c for c in CARDS if c != REF_CARD]
    print(f"=== S346 PURE TRANSFER of the {REF_CARD} accepted layer ===", flush=True)
    print(f"   geom   : {geom_str(REF_GEOM)}", flush=True)
    print(f"   filters: {flt_str(REF_FILTERS)}", flush=True)
    print("   -- reference quantiles --", flush=True)
    qs = ref_quantiles()

    results = {}
    for card in cards:
        print(f"\n----- {card} -----", flush=True)
        cache = {}
        try:
            # الف) انتقالِ عددیِ خام
            r_raw, _ = adjudicate_row(card, REF_GEOM, REF_FILTERS,
                                      name='  RAW-thr', cache=cache)
            # ب) انتقالِ رژیمی (بازسازیِ چارک)
            fl_q = rescaled_filters(card, REF_GEOM, REF_FILTERS, qs)
            print(f"   rescaled: {flt_str(fl_q)}", flush=True)
            r_q, _ = adjudicate_row(card, REF_GEOM, fl_q,
                                    name='  QUANTILE', cache=cache)
            # ج) ابلیشنِ جهت روی نسخهٔ رژیمی (تقارن باید حفظ شود)
            abl = {}
            for sd in ('long', 'short'):
                ra, _ = adjudicate_row(card, REF_GEOM, fl_q, side=sd,
                                       name=f'  ABL {sd}', cache=cache)
                abl[sd] = ra
            results[card] = dict(raw=r_raw, quantile=r_q,
                                 filters_q=fl_q, ablation=abl)
        except Exception as e:
            print(f"   !! failed: {type(e).__name__}: {e}", flush=True)
            results[card] = dict(error=f"{type(e).__name__}: {e}")
        if save:
            with open(f"{OUT}/transfer_from_{REF_CARD}.json", 'w') as fh:
                json.dump(dict(ref_card=REF_CARD, geom=REF_GEOM,
                               filters=REF_FILTERS, ref_q=qs,
                               results=results), fh, default=float)
            print(f"   [checkpointed {card}]", flush=True)

    print("\n================ TRANSFER SUMMARY ================", flush=True)
    print(f"  {'card':13s} {'RAW':>26s} | {'QUANTILE':>26s} | symmetry", flush=True)
    for card, v in results.items():
        if 'error' in v:
            print(f"  {card:13s} ERROR {v['error'][:50]}", flush=True)
            continue
        a, b = v['raw'], v['quantile']

        def brief(r):
            m = r['metrics']
            return (f"RQS={r['rqs_score']:5.1f} n={m.get('n_trades', 0):5d} "
                    f"WR={m.get('win_rate', 0):5.2f}")
        la, sa = v['ablation']['long'], v['ablation']['short']
        sym = ('SYM' if (la['metrics'].get('win_rate', 0) >= 55 and
                         sa['metrics'].get('win_rate', 0) >= 55) else 'asym')
        print(f"  {card:13s} {brief(a):>26s} | {brief(b):>26s} | {sym} "
              f"L={la['metrics'].get('win_rate', 0):.1f} "
              f"S={sa['metrics'].get('win_rate', 0):.1f}", flush=True)
    return results


if __name__ == '__main__':
    args = sys.argv[1:]
    run(args or None)
