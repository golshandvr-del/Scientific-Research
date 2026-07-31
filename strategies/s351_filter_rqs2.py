# -*- coding: utf-8 -*-
"""
S351 — داورِ **رسمیِ RQS2** برای «بهبودِ S333 با فیلترِ جهتیِ ساختارِ LPSB»
================================================================================
یافتهٔ نشست (اندازه‌گیری‌شده در `s351_overlap_filter.py`): وضعیتِ ساختارِ
لگ-متناسب (`state ∈ {+1,−1}`) یک **فیلترِ جهتیِ صفر-پارامتر** است که در هر
چهار کارتِ گلد به‌طورِ یکنواخت لایهٔ پذیرفته‌شدهٔ S333 را بهتر می‌کند وقتی
`state == −1` (بازگشتِ لانگ از یک ساختارِ نزولیِ واقعی).

RQS+ قدیمی این را تأیید کرد (۹۴.۷/۹۲.۴/۳۳.۸/۹۳.۹ در برابرِ پایهٔ ۹۱.۳/۹۱.۷/
۹۱.۱/۸۹.۸). اما معیارِ حاکمِ پروژه **RQS2 v2.3** است، نه RQS+. این فایل
همان مقایسه را زیرِ RQS2ِ کامل (۱۱ دروازه + مدلِ صفرِ سمت‌به‌سمت) انجام می‌دهد
تا ثابت شود «بهبود» یک ارتقای رسمی است، نه تورمِ WR.

--------------------------------------------------------------------------------
⛔ سپرهای انصاف (هم‌سان با overlap_filter، حالا زیرِ RQS2)
--------------------------------------------------------------------------------
  ۱) هندسه = همان `BEST_CFG` خودِ S333 (sl/tp/max_hold per-TF). دست‌نخورده.
  ۲) `state` علّی است (فقط پیوتِ بسته‌شده). بدونِ repaint.
  ۳) فیلتر صفر-پارامتر: `state == −1` تنها انتخاب است. غیرِقابلِ over-fit.
  ۴) LPSB = عضوِ مرکزیِ پیش‌ثبت‌شده (L=8, f=0.33).
  ۵) چندگانگی: فضای جست‌وجو = ۲ علامتِ حالت × ۴ کارت = ۸ ⇒ n_trials=8
     (محافظه‌کارانه؛ حتی با آنکه علامتِ برنده از پیش با منطق تعیین شده بود).

خروجی: `S351_LPSBStructureFilter_*.md`-ready JSON در results/_scan_S351/
"""
import os
import sys
import json
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies import s333_s79_pullback_revival as s333           # noqa: E402
from strategies.s351_lpsb import lpsb_signals                      # noqa: E402
from strategies.s351_verdict import CENTRAL, build_null_side       # noqa: E402

OUT = 'results/_scan_S351'
WARMUP = 300
N_MULT = 8                    # ۲ علامتِ حالت × ۴ کارت (بدبینانه)
SPLIT_FRAC = 0.60
SEED = 12345

CARDS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1']


def _win_col(tr):
    """simulate_trades ممکن است ستونِ win نداشته باشد؛ از pnl_pip بساز."""
    if 'win' not in tr.columns:
        tr = tr.copy()
        tr['win'] = (tr['pnl_pip'].to_numpy() > 0).astype(int)
    return tr


def judge(card, n_perm=300, verbose=True):
    cfg = s333.BEST_CFG[card]
    asset = 'XAUUSD'
    path = se.ASSETS[card]['file']
    if not os.path.exists(path):
        return dict(card=card, verdict='NO_DATA')

    df = se.load_data(path)
    n = len(df)
    close = df['close'].to_numpy(float)
    bar_time = df['dt'].values if 'dt' in df.columns else None
    split = int(n * SPLIT_FRAC)

    # ---------- سیگنالِ S333 (دست‌نخورده) و حالتِ ساختارِ LPSB ----------
    base = s333.build_layer(df, cfg)
    _, _, state = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)

    filt = base & (state == -1)              # فیلترِ برنده (اندازه‌گیری‌شده)

    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']

    # trades — پایه و فیلترشده، با همان هندسهٔ S333
    tr_b, _ = s333.evaluate(df, base, card, sl, tp, mh)
    tr_f, _ = s333.evaluate(df, filt, card, sl, tp, mh)
    if tr_b is None or tr_f is None or len(tr_f) < 3:
        return dict(card=card, verdict='TOO_FEW')

    tr_b = _win_col(tr_b)
    tr_f = _win_col(tr_f)

    # ---------- مدلِ صفرِ سمت‌به‌سمت (هندسهٔ منجمدِ S333) ----------
    # S333 لانگ-محور است ⇒ همهٔ معاملات long؛ null را با همان n و sl/tp می‌سازیم.
    valid = np.where(np.isfinite(close))[0]
    valid = valid[valid >= WARMUP]
    sl_arr = np.full(n, float(sl))          # SL ثابتِ S333 بر حسبِ pip → قیمت

    def _rqs2(tr, label):
        nL = int((tr['direction'] == 'long').sum())
        nS = int(len(tr) - nL)
        rng = np.random.default_rng(SEED)
        # build_null_side انتظارِ sl بر حسبِ قیمت دارد؛ S333 sl بر حسبِ pip است.
        # pip گلد=0.1 ⇒ فاصلهٔ قیمت = sl*pip. اما چون S333 SL ثابت دارد،
        # از خودِ tp/sl مدیانِ trades استفاده می‌کنیم (سازگار با موتور).
        sl_price = sl * se.ASSETS[asset]['pip']
        null = build_null_side(df, asset, valid,
                               np.full(n, sl_price),
                               nL, nS, n_perm, rng, verbose=False)
        r = rqs2.compute_rqs2(tr, asset, n_trials=N_MULT,
                              sl_pip=float(sl), tp_pip=float(tp),
                              bar_time=bar_time, null=null,
                              split_bar=split, close=close)
        if verbose:
            print(rqs2.format_rqs2(f'{card} {label}', r), flush=True)
        return r

    if verbose:
        print(f"\n{'='*90}\n=== S351 FILTER-RQS2 :: {card} "
              f"(bars={n:,}) ===", flush=True)
        print(f"    S333 geom: sl={sl} tp={tp} mh={mh} | "
              f"base_n={len(tr_b)} filtered_n={len(tr_f)}", flush=True)

    r_base = _rqs2(tr_b, 'BASE    ')
    r_filt = _rqs2(tr_f, 'FILTERED')

    out = dict(card=card, asset=asset, bars=n, cfg=dict(cfg),
               n_mult=N_MULT, split_bar=split,
               lpsb_member=dict(CENTRAL),
               n_base=len(tr_b), n_filtered=len(tr_f),
               base={k: r_base[k] for k in
                     ('verdict', 'rqs2_score', 'gates', 'metrics', 'notes')
                     if k in r_base},
               filtered={k: r_filt[k] for k in
                         ('verdict', 'rqs2_score', 'gates', 'metrics', 'notes')
                         if k in r_filt})
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f'{card}_filter_rqs2.json')
    with open(p, 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    if verbose:
        print(f"    [checkpoint] {p}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cards', nargs='*', default=CARDS)
    ap.add_argument('--n-perm', type=int, default=300)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    cards = a.cards if a.cards else CARDS
    for card in cards:
        judge(card, n_perm=a.n_perm, verbose=not a.quiet)


if __name__ == '__main__':
    main()
