# -*- coding: utf-8 -*-
"""
S351 — اسکنِ سریعِ pip-محورِ کلِ ۱۵ کارت (مرحلهٔ شناسایی، پیش از RQS2 کامل)
================================================================================
هدف: قبل از خرج‌کردنِ زمانِ RQS2 کامل روی همهٔ کارت‌ها، یک تصویرِ خامِ mtf بگیر.
برای هر کارت، ۹ عضوِ خانواده (بدونِ فیلتر) روی کلِ داده اجرا می‌شوند و
میانگینِ خانواده (= آمارهٔ N=1 طبقِ §۲.۵) گزارش می‌شود.

خروجی: results/_scan_S351/<card>_raw.json  (برای هر کارت جداگانه چک‌پوینت)

قانونِ «اندک اندک»: این اسکریپت در بک‌گراند اجرا می‌شود و برای هر کارت نتیجه را
بلافاصله می‌نویسد؛ منتظرِ اتمامِ همه نمی‌مانیم.
"""
import os
import sys
import json
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from strategies.s351_lpsb import (atr_series, member_stats,        # noqa: E402
                                  members, CARDS, OUT)


def scan_card(card):
    asset, path = CARDS[card]
    if not os.path.exists(path):
        return None
    df = se.load_data(path)
    atr = atr_series(df)
    rows = []
    for m in members():
        st, sig, il = member_stats(df, atr, asset, m['L'], m['f'])
        rows.append(dict(L=m['L'], f=m['f'], **{k: st[k] for k in
                    ('n_sig', 'n', 'wr', 'exp', 'pf')}))
    # میانگینِ خانواده (N=1) — وزنِ برابر برای هر عضو
    valid = [r for r in rows if r['n'] > 0]
    if valid:
        fam = dict(
            n_mean=float(np.mean([r['n'] for r in valid])),
            wr_mean=float(np.mean([r['wr'] for r in valid])),
            exp_mean=float(np.mean([r['exp'] for r in valid])),
            pf_mean=float(np.mean([r['pf'] for r in valid])),
            exp_best=float(max(r['exp'] for r in valid)),
            pf_best=float(max(r['pf'] for r in valid)),
        )
    else:
        fam = dict(n_mean=0, wr_mean=0, exp_mean=0, pf_mean=0,
                   exp_best=0, pf_best=0)
    return dict(card=card, asset=asset, bars=int(len(df)),
                family=fam, members=rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    cards = list(CARDS.keys())
    print(f"=== S351 raw scan · {len(cards)} cards ===", flush=True)
    summary = []
    for card in cards:
        t0 = time.time()
        res = scan_card(card)
        if res is None:
            print(f"[SKIP] {card} (no data)", flush=True)
            continue
        # چک‌پوینتِ فوریِ هر کارت
        fp = os.path.join(OUT, f"{card}_raw.json")
        with open(fp, 'w') as fh:
            json.dump(res, fh, indent=2)
        fam = res['family']
        print(f"[{card:12s}] bars={res['bars']:7d} "
              f"n~{fam['n_mean']:6.0f} WR={fam['wr_mean']:5.2f}% "
              f"exp_mean={fam['exp_mean']:+6.2f} pf_mean={fam['pf_mean']:.3f} "
              f"| best: exp={fam['exp_best']:+6.2f} pf={fam['pf_best']:.3f} "
              f"[{time.time()-t0:.1f}s]", flush=True)
        summary.append(res)
    with open(os.path.join(OUT, '_summary_raw.json'), 'w') as fh:
        json.dump(summary, fh, indent=2)
    print("=== DONE raw scan ===", flush=True)


if __name__ == '__main__':
    main()
