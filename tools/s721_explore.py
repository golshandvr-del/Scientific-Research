# -*- coding: utf-8 -*-
"""
s721_explore.py — اکتشافِ لایهٔ نو `S721`: «فشارِ ردِ جهت‌دارِ سایه‌ها» روی طلا
================================================================================
⚠️ فقط روی **نیمهٔ اولِ** داده (مسیرِ چندگانگیِ C). نیمهٔ دوم دست‌نخورده می‌ماند.

مفهوم (الهام از docs/indicators/pattern.md گروه ۲ — «طولِ سایه را به‌عنوان
شدتِ رد کمّی کن»):
  سایهٔ پایینی = min(open,close) − low  → ردِ فروش (دفاعِ خریدار از کف)
  سایهٔ بالایی = high − max(open,close) → ردِ خرید (دفاعِ فروشنده از سقف)
  R(W) = (Σlower − Σupper) / (Σlower + Σupper) روی پنجرهٔ W ∈ [−1,+1]
  رویدادِ ورود: عبورِ **لبه‌ایِ** R از ±thr (رویداد نه حالت — درسِ S382).
  mode='cont': R>+thr ⇒ LONG (دفاعِ مکررِ کف ⇒ ادامهٔ صعود)
  mode='rev' : R>+thr ⇒ SHORT (اشباعِ دفاع ⇒ بازگشت)
  هر دو جهت آزموده می‌شود؛ داده تصمیم می‌گیرد.

نوبودگی: grep روی results/*.md — «wick» فقط در S327 (کلایمکسِ تک‌کندلی،
REJECT). هیچ لایه‌ای فشارِ تجمعیِ سایه را نیازموده.

هندسه: SL = k×ATR(89)ِ میانه، TP = rr×SL (rr≥1 همیشه). max_hold = W کندل
(هم‌مقیاس با سیگنال — علاجِ BUG-TFM).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402
from tools.s720_explore import atr_median, bars_per_hour, uncond_wr  # noqa: E402

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_s721_explore')

# ── فضای جست‌وجو (شمارشِ صادقانه برای n_trials پیش‌ثبت) ───────────────────
WS = (13, 34, 89)                 # پنجرهٔ تجمیعِ سایه‌ها (فیبوناچی)
THRS = (0.15, 0.25, 0.35, 0.45)   # آستانهٔ عدم‌تقارنِ R
KS = (1.3, 2.1, 3.4)              # ضریبِ SL روی ATR(89)
RRS = (1.0, 1.5, 2.0)             # TP/SL — هرگز <1
MODES = ('cont', 'rev')
# سلول‌ها: 3×4×3×3×2 = 216 در هر TF (همه در n_trials شمرده می‌شوند)


def wick_ratio(df: pd.DataFrame, w: int) -> np.ndarray:
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    up = h - np.maximum(o, c)
    dn = np.minimum(o, c) - l
    su = pd.Series(up).rolling(w).sum().to_numpy()
    sd = pd.Series(dn).rolling(w).sum().to_numpy()
    tot = su + sd
    with np.errstate(invalid='ignore', divide='ignore'):
        r = np.where(tot > 0, (sd - su) / tot, 0.0)
    return r


def rejection_signals(df: pd.DataFrame, w: int, thr: float, mode: str = 'cont'):
    """لبهٔ عبورِ R از ±thr. خروجی: (long_sig, short_sig)."""
    r = np.nan_to_num(wick_ratio(df, w))
    hi = r > thr          # دفاعِ مکررِ کف (خریدار قوی)
    lo = r < -thr         # دفاعِ مکررِ سقف (فروشنده قوی)
    hp = np.roll(hi, 1); hp[0] = False
    lp = np.roll(lo, 1); lp[0] = False
    hi_e = hi & ~hp
    lo_e = lo & ~lp
    if mode == 'cont':
        return hi_e, lo_e      # دفاعِ کف ⇒ LONG
    return lo_e, hi_e          # بازگشتی


def explore_tf(tf: str):
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    half = len(df) // 2
    df = df.iloc[:half].reset_index(drop=True)   # ⚠️ فقط نیمهٔ اول
    src = d['src']
    atr = atr_median(df)
    pip = se.ASSETS[ASSET]['pip']
    rows = []
    for w in WS:
        mh = w                                  # هم‌مقیاس با پنجرهٔ سیگنال
        for mode in MODES:
            for thr in THRS:
                ls, ss = rejection_signals(df, w, thr, mode)
                n_ev = int(ls.sum() + ss.sum())
                for k in KS:
                    sl = round(k * atr / pip, 1)
                    if sl <= 6.6:               # SL < ۲×هزینه = خودکشیِ H9
                        continue
                    for rr in RRS:
                        tp = round(sl * rr, 1)
                        tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                                                max_hold=mh, allow_overlap=False)
                        if len(tr) < 30:
                            rows.append(dict(tf=tf, w=w, mode=mode, thr=thr, k=k,
                                             rr=rr, sl=sl, tp=tp, n=len(tr), note='n<30'))
                            continue
                        wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                        exp = float(tr['pnl_pip'].mean())
                        nl = int((tr['direction'] == 'long').sum())
                        ns = int((tr['direction'] == 'short').sum())
                        be = 100.0 * (sl + 3.3) / (sl + tp)
                        rows.append(dict(tf=tf, w=w, mode=mode, thr=thr, k=k, rr=rr,
                                         sl=sl, tp=tp, n=len(tr), n_long=nl, n_short=ns,
                                         wr=round(wr, 2), be=round(be, 2),
                                         margin=round(wr - be, 2),
                                         exp_pip=round(exp, 3), n_events=n_ev))
    return dict(tf=tf, src=src, bars_half=len(df),
                atr89_med_pip=round(atr / pip, 2), rows=rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    tfs = sys.argv[1:] or ['M1']
    for tf in tfs:
        print(f'── S721 اکتشاف · {ASSET}-{tf} · فقط نیمهٔ اول ──', flush=True)
        res = explore_tf(tf)
        print(f"src={res['src']} bars={res['bars_half']} ATR89={res['atr89_med_pip']}pip", flush=True)
        pos = [r for r in res['rows'] if r.get('margin') is not None and r['margin'] > 0]
        for r in sorted(pos, key=lambda x: -x['margin'])[:12]:
            print(f"  + w={r['w']} {r['mode']} thr={r['thr']} k={r['k']} rr={r['rr']} "
                  f"SL={r['sl']}/TP={r['tp']} n={r['n']} (L{r['n_long']}/S{r['n_short']}) "
                  f"WR={r['wr']}% BE={r['be']}% حاشیه=+{r['margin']}pp", flush=True)
        if not pos:
            print('  هیچ سلولِ مثبتی نیست.', flush=True)
        with open(os.path.join(OUT, f'explore_{tf}.json'), 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f'  ذخیره شد → results/_s721_explore/explore_{tf}.json', flush=True)


if __name__ == '__main__':
    main()
