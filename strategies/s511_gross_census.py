# -*- coding: utf-8 -*-
"""
S511 — سرشماریِ لبهٔ ناخالصِ بانکِ ۴۰۱ اندیکاتوری روی کارت‌های ارضاپذیر طلا
================================================================================
پیش‌ثبت: `results/S511_PREREG_GROSS_EDGE_CENSUS_401.md` (کامیت 32a2e3fb، قبل از
هر عدد). انگیزه: یافتهٔ ۱ از S510 — گلوگاه سیگنالِ باخبر است، نه هندسه؛ و برای
پرهیز از اشتباه رایج #۳، کل بانک سرشماری می‌شود نه حدسِ من.

طرح (همه از پیش‌ثبت؛ اینجا فقط اجرا):
  * رویداد یکنواخت: کراسِ اندیکاتور به بالای q90 (A) یا پایین q10 (B)؛
    آستانه‌ها فقط از پنجرهٔ اکتشاف (۶۰٪ نخست). × دو جهت LONG/SHORT.
  * هندسهٔ منجمد: SL=1.272×median(ATR100|disc)، RR=2.058.
  * شبیه‌ساز: numba هم‌معنای S382 (parity اثبات‌شده در S510).
  * سنجهٔ سرشماری: exp_gross در اکتشاف؛ فهرست نهایی: n≥100 و exp_gross>0
    در هر دو نیمهٔ اکتشاف؛ رتبه بر exp_net.
  * قانون اندک‌اندک: checkpoint per (کارت × دسته) + از سرگیریِ خودکار.

اجرا:  python3 strategies/s511_gross_census.py --card M15|M30|H1
"""
import sys
import os
import json
import argparse
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import indicator_bank as ib                             # noqa: E402
from tools.s434_fast_data import load_fast, as_dataframe            # noqa: E402
from strategies.s510_rr_lowtf_wpr import atr_np, simulate           # noqa: E402

OUT = 'results/_scan_S511'

# ---------------------- ثابت‌های پیش‌ثبت‌شده (قفل) ----------------------
SEED = 20260814
SPLIT_FRAC = 0.60
WARMUP = 400
MIN_N = 100
SL_K = 1.272
RR = 2.058
Q_LO, Q_HI = 0.10, 0.90
COST_PIP = 3.3
PIP = 0.10


def load_card(tf):
    d = load_fast('XAUUSD', tf)
    print(f"[DATA] src={d['src']}  n_bars={d['n_bars']}  "
          f"span={d['first_utc']} .. {d['last_utc']}  ({d['span_years']}y)",
          flush=True)
    return d


def cross_above(x, thr):
    """رویداد A: گذر به بالای آستانه (حالت‌گذر، نه سطح)."""
    prev = np.empty_like(x)
    prev[0] = np.nan
    prev[1:] = x[:-1]
    return (prev <= thr) & (x > thr)


def cross_below(x, thr):
    """رویداد B: گذر به پایین آستانه."""
    prev = np.empty_like(x)
    prev[0] = np.nan
    prev[1:] = x[:-1]
    return (prev >= thr) & (x < thr)


def eval_cell(d_disc, sig_idx, sl_abs, half, is_long):
    """یک سلول سرشماری: شبیه‌سازی روی اکتشاف + سنجه‌های پیش‌ثبت‌شده.

    برای SHORT از قرینهٔ آینه‌ایِ داده استفاده می‌شود (high/low/close منفی و
    جابه‌جا) تا **همان** شبیه‌سازِ parity-اثبات‌شدهٔ LONG بدون نسخهٔ دوم به‌کار
    رود — انضباطِ ضدِ «دو نسخهٔ ناهمگام». آینه دقیق است: SL مقدم می‌مانَد چون
    نقشِ high/low هم عوض می‌شود.
    """
    if is_long:
        tr = simulate(d_disc, sig_idx, sl_abs, RR)
    else:
        mirror = {'high': -d_disc['low'], 'low': -d_disc['high'],
                  'close': -d_disc['close']}
        tr = simulate(mirror, sig_idx, sl_abs, RR)
    nt = len(tr)
    if nt == 0:
        return dict(n=0)
    pnl = tr['pnl_pip'].to_numpy()
    m1 = tr['entry_bar'].to_numpy() < half
    g = float(pnl.mean())
    g1 = float(pnl[m1].mean()) if m1.any() else np.nan
    g2 = float(pnl[~m1].mean()) if (~m1).any() else np.nan
    return dict(n=nt, exp_gross=round(g, 3), exp_net=round(g - COST_PIP, 3),
                g1=round(g1, 3) if np.isfinite(g1) else None,
                g2=round(g2, 3) if np.isfinite(g2) else None,
                wr=round(float((tr['outcome'] == 'win').mean() * 100), 2),
                qualified=bool(nt >= MIN_N and np.isfinite(g1)
                               and np.isfinite(g2) and g1 > 0 and g2 > 0))


def stage_census(tf):
    d = load_card(tf)
    n = d['n_bars']
    split = int(SPLIT_FRAC * n)
    half = split // 2
    a = atr_np(d['high'], d['low'], d['close'])
    sl_abs = float(np.nanmedian(a[:split])) * SL_K
    print(f'[CENSUS {tf}] split={split}  SL={sl_abs/PIP:.2f}pip  '
          f'TP={RR*sl_abs/PIP:.2f}pip', flush=True)

    d_disc = {k: d[k][:split] for k in ('high', 'low', 'close')}
    df_disc = as_dataframe({**{k: d[k][:split] for k in
                               ('time', 'open', 'high', 'low', 'close',
                                'volume')}})

    os.makedirs(OUT, exist_ok=True)
    cats = sorted(ib.categories())
    for cat in cats:
        cp = f'{OUT}/{tf}_{cat}.json'
        if os.path.exists(cp):
            print(f'[CENSUS {tf}] {cat}: checkpoint exists — skip', flush=True)
            continue
        names = ib.by_category(cat)
        rows = []
        skipped = 0
        t0 = time.time()
        for nm in names:
            try:
                x = ib.compute(nm, df_disc).to_numpy()
            except Exception as ex:
                skipped += 1
                rows.append(dict(ind=nm, error=str(ex)[:80]))
                continue
            x[:WARMUP] = np.nan
            finite = x[np.isfinite(x)]
            if len(finite) < 1000 or float(np.nanstd(finite)) <= 0:
                skipped += 1
                rows.append(dict(ind=nm, degenerate=True))
                continue
            q_lo = float(np.nanquantile(x, Q_LO))
            q_hi = float(np.nanquantile(x, Q_HI))
            if not (np.isfinite(q_lo) and np.isfinite(q_hi)) or q_lo >= q_hi:
                skipped += 1
                rows.append(dict(ind=nm, degenerate=True))
                continue
            for ev, sig_bool in (('A', cross_above(x, q_hi)),
                                 ('B', cross_below(x, q_lo))):
                sig_bool = np.nan_to_num(sig_bool, nan=False).astype(bool)
                sig_bool[:WARMUP] = False
                sig_idx = np.flatnonzero(sig_bool)
                if len(sig_idx) < 30:
                    continue
                for side in ('long', 'short'):
                    cell = eval_cell(d_disc, sig_idx, sl_abs, half,
                                     side == 'long')
                    if cell['n'] > 0:
                        rows.append(dict(ind=nm, ev=ev, side=side, **cell))
        qual = [r for r in rows if r.get('qualified')]
        with open(cp, 'w') as f:
            json.dump(dict(card=f'XAUUSD_{tf}', cat=cat, sl_abs=sl_abs,
                           split=split, n_names=len(names), skipped=skipped,
                           n_qualified=len(qual), rows=rows), f,
                      ensure_ascii=False)
        print(f'[CENSUS {tf}] {cat}: {len(names)} inds, {skipped} skipped, '
              f'{len(qual)} qualified  ({time.time()-t0:.0f}s)', flush=True)

    # جمع‌بندی کارت
    allq = []
    for cat in cats:
        with open(f'{OUT}/{tf}_{cat}.json') as f:
            j = json.load(f)
        allq += [r for r in j['rows'] if r.get('qualified')]
    allq.sort(key=lambda r: -r['exp_net'])
    with open(f'{OUT}/{tf}_summary.json', 'w') as f:
        json.dump(dict(card=f'XAUUSD_{tf}', n_qualified=len(allq),
                       top20=allq[:20]), f, ensure_ascii=False)
    print(f'[CENSUS {tf}] TOTAL qualified={len(allq)}')
    for r in allq[:10]:
        print(f"  {r['ind']} {r['ev']}/{r['side']}: n={r['n']} wr={r['wr']} "
              f"gross={r['exp_gross']} net={r['exp_net']} "
              f"h1={r['g1']} h2={r['g2']}")
    print(f'saved -> {OUT}/{tf}_summary.json')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--card', required=True, choices=['M15', 'M30', 'H1'])
    args = ap.parse_args()
    stage_census(args.card)
