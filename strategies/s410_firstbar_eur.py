# -*- coding: utf-8 -*-
"""
S410 — لایهٔ «کندلِ اولِ روزِ EURUSD» (MISSION_2، بازهٔ S410–S419)
==================================================================
پیش‌ثبت: results/S410_PREREG_FIRSTBAR_EUR.md (commit جداگانه، قبل از این فایل)

فازها:
  --tune    : پیمایشِ فضای منجمدِ پیش‌ثبت **فقط روی نیمهٔ اولِ** M15.
  --final   : آزمونِ یک‌ضربِ رسمی (پس از انجمادِ برنده در FROZEN_WINNER).

نکاتِ ضدِ خطا (درس‌های ثبت‌شدهٔ بایگانی):
  * ورودِ شبیه‌ساز در openِ کندلِ si+1 است ⇒ سیگنالِ «openِ اولین کندلِ روز»
    باید روی **آخرین کندلِ روزِ قبل** بنشیند (ضدِ look-ahead خودِ موتور).
  * max_hold بر حسبِ ساعت و با bars_per_hour اندازه‌گیری‌شده (ضدِ BUG-TFM).
  * «بدون TP» = TP=10000 pip واقعی در شبیه‌سازی؛ همان عدد صادقانه به داور
    پاس می‌شود (H2 با RR≥0.5 می‌سنجد؛ هیچ فرضِ پنهانی نیست).
  * انتخاب: argmax exp@2c (حاشیهٔ H9) مشروط به n≥200 و exp@2c>0 — منجمد در پیش‌ثبت.
"""
import os
import sys
import json

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                # noqa: E402

ASSET = 'EURUSD'
DATA = {'M15': 'data/EURUSD_M15.csv',
        'M30': 'data/EURUSD_M30.csv',
        'H1': 'data/EURUSD_H1.csv'}
XAU_D1 = 'data/XAUUSD_D1.csv'
OUT = 'results/_scan_S410'
os.makedirs(OUT, exist_ok=True)

NO_TP = 10000.0          # پیاده‌سازیِ «بدون TP» — سدِ واقعی ولی دور
HOLD_HOURS = (1.0, 1.5)  # منجمد در پیش‌ثبت
GEOMS = (('G1', 12.0, NO_TP), ('G2', 18.0, NO_TP), ('G3', 12.0, 12.0))
N_TRIALS = 80            # حسابداریِ پیش‌ثبت (بندِ ۶)
N_MIN_TUNE = 200         # کفِ n در تابعِ انتخاب (بندِ ۵)


def cost_pip(asset):
    cfg = se.ASSETS[asset]
    return float(cfg['spread_pip']) + 2.0 * float(cfg['slip_pip'])


def bars_per_hour(df):
    d = np.median(np.diff(df['time'].values.astype(np.float64)))
    return 3600.0 / d


# --------------------------- سیگنالِ پایه (منجمد) ---------------------------
def anchor_signal(df):
    """True روی آخرین کندلِ روز، وقتی کندلِ بعدی دقیقاً 00:00 UTC است."""
    dt = pd.to_datetime(df['time'].values, unit='s')
    hh = dt.hour.values
    mm = dt.minute.values
    nxt_is_midnight = np.zeros(len(df), dtype=bool)
    nxt_is_midnight[:-1] = (hh[1:] == 0) & (mm[1:] == 0)
    # روزِ تقویمی هم باید عوض شود (دفاع در برابرِ دادهٔ تکراری/خراب)
    day = dt.normalize().values
    day_change = np.zeros(len(df), dtype=bool)
    day_change[:-1] = day[1:] != day[:-1]
    return nxt_is_midnight & day_change


# ------------------------------ فیلترها (منجمد) ------------------------------
def net_disp(close, lb):
    d = np.zeros(len(close))
    d[lb:] = close[lb:] - close[:-lb]
    return d


def build_filters(df, tune_slice, bph):
    """دیکشنری {نام: ماسکِ بولین روی کندل‌ها} — همه فقط با اطلاعاتِ گذشته.

    آستانه‌های داده‌محور (میانه‌ها، بدترین روزِ هفته) **فقط از tune_slice**
    (نیمهٔ اول) اندازه‌گیری می‌شوند و بیرونِ آن منجمد می‌مانند.
    """
    n = len(df)
    dt = pd.to_datetime(df['time'].values, unit='s')
    c = df['close'].values.astype(np.float64)
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)

    filt = {'F0': np.ones(n, dtype=bool)}

    # F1/F2 — جابه‌جاییِ خالصِ منفی (dip) در ۴ و ۸ کندلِ قبل از سیگنال
    filt['F1'] = net_disp(c, 4) < 0.0
    filt['F1'][:4] = False
    filt['F2'] = net_disp(c, 8) < 0.0
    filt['F2'][:8] = False

    # F3 — گپِ شبانه منفی: چون سیگنال روی آخرین کندلِ دیروز است و ورود در
    # openِ کندلِ 00:00، «گپ» = open(بعدی) − close(سیگنال) در لحظهٔ سیگنال
    # هنوز معلوم نیست ⇒ معادلِ بدونِ look-ahead: momentumِ کندلِ آخرِ دیروز
    # منفی (close < open همان کندل) — نزدیک‌ترین جانشینِ علّی.
    filt['F3'] = c < o

    # F4 — جهتِ دیروز نزولی: close آخرین کندلِ دیروز < openِ اولین کندلِ دیروز
    day = dt.normalize().values
    day_open = np.full(n, np.nan)
    cur_open = np.nan
    prev_day = None
    for i in range(n):
        if prev_day is None or day[i] != prev_day:
            cur_open = o[i]
            prev_day = day[i]
        day_open[i] = cur_open
    filt['F4'] = c < day_open   # روی کندلِ سیگنال (آخرین کندلِ روز) = جهتِ کلِ دیروز

    # F5 — RVOL پایین: رنجِ ۲۴h قبل < میانهٔ رنجِ ۲۴h روی نیمهٔ اول
    w24 = max(2, int(round(24.0 * bph)))
    hi_r = pd.Series(h).rolling(w24, min_periods=w24).max().values
    lo_r = pd.Series(l).rolling(w24, min_periods=w24).min().values
    rng24 = hi_r - lo_r
    med_rng = np.nanmedian(rng24[tune_slice])
    filt['F5'] = np.where(np.isfinite(rng24), rng24 < med_rng, False)

    # F6 — رژیمِ استقلالِ XAU-EUR: |corr غلتان ۲۰روزهٔ بازده‌های روزانه| < میانه
    xau = pd.read_csv(XAU_D1)
    xau['d'] = pd.to_datetime(xau['time'], unit='s').dt.normalize()
    xr = xau.set_index('d')['close'].pct_change()
    eur_daily = pd.Series(c, index=dt).resample('1D').last().dropna()
    er = eur_daily.pct_change()
    both = pd.concat([er.rename('e'), xr.rename('x')], axis=1).dropna()
    corr = both['e'].rolling(20).corr(both['x'])
    corr_lag = corr.shift(1)                       # فقط تا دیروز (ضدِ look-ahead)
    abs_corr_by_day = corr_lag.abs()
    day_idx = pd.Series(pd.to_datetime(day))
    ac = abs_corr_by_day.reindex(day_idx.values).values
    med_ac = np.nanmedian(ac[tune_slice])
    filt['F6'] = np.where(np.isfinite(ac), ac < med_ac, False)

    # F7 — حذفِ بدترین روزِ هفته: با دریفتِ خامِ ۴کندلیِ پس از لنگر، فقط
    # روی نیمهٔ اول اندازه‌گیری می‌شود (یک اندازه‌گیری، یک انتخاب).
    sig = anchor_signal(df)
    fwd4 = np.full(n, np.nan)
    fwd4[:-5] = c[5:] - o[1:-4]   # از openِ کندلِ ورود (si+1) تا closeِ ۴ کندل بعد
    pip = se.ASSETS[ASSET]['pip']
    wd_entry = pd.to_datetime(df['time'].values, unit='s').dayofweek.values
    wd_of_next = np.roll(wd_entry, -1)             # روزِ هفتهٔ کندلِ ورود
    stats = {}
    tune_sig = sig & tune_slice
    for w in range(7):
        m = tune_sig & (wd_of_next == w) & np.isfinite(fwd4)
        if m.sum() >= 30:
            stats[w] = float(np.mean(fwd4[m]) / pip)
    worst_wd = min(stats, key=stats.get) if stats else None
    filt['F7'] = (wd_of_next != worst_wd) if worst_wd is not None \
        else np.ones(n, dtype=bool)

    meta = dict(w24=w24, med_rng=float(med_rng), med_abs_corr=float(med_ac),
                worst_weekday=worst_wd, weekday_stats=stats)
    return filt, meta


# ------------------------------- ارزیابیِ سلول -------------------------------
def eval_cell(df, sig, sl, tp, max_hold):
    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, ASSET,
                            max_hold=max_hold, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    pnl = tr['pnl_pip'].values
    n = len(tr)
    exp_net = float(np.mean(pnl))
    c = cost_pip(ASSET)
    exp2c = exp_net - c                    # حاشیهٔ H9 (pnl از قبل هزینه‌دار است)
    wr = float((pnl > 0).mean() * 100.0)
    sd = float(np.std(pnl, ddof=1)) if n > 1 else float('nan')
    t = exp_net / (sd / np.sqrt(n)) if n > 1 and sd > 0 else float('nan')
    return dict(n=n, wr=wr, exp_net=exp_net, exp2c=exp2c, t=t,
                time_exit_pct=float((tr['bars_held'] >= max_hold - 1).mean() * 100))


def tune():
    df = se.load_data(DATA['M15'])
    n = len(df)
    split = n // 2
    tune_slice = np.zeros(n, dtype=bool)
    tune_slice[:split] = True
    bph = bars_per_hour(df)
    c = cost_pip(ASSET)
    print(f"[S410 tune] bars={n:,} split_bar={split:,} "
          f"({df['dt'].iloc[0]} → {df['dt'].iloc[split-1]}) "
          f"bars/hour={bph:.2f} cost={c:.2f}pip", flush=True)

    dfa = df.iloc[:split].reset_index(drop=True)   # نیمهٔ دوم هرگز لمس نمی‌شود
    filters, fmeta = build_filters(df, tune_slice, bph)
    print(f"[filters] {json.dumps(fmeta, ensure_ascii=False)}", flush=True)

    base = anchor_signal(dfa)
    print(f"[anchor] events in first half: {int(base.sum())}", flush=True)

    rows = []
    for fname, fmask in filters.items():
        sig = base & fmask[:split]
        for hh in HOLD_HOURS:
            mh = int(round(hh * bph))
            for gname, sl, tp in GEOMS:
                r = eval_cell(dfa, sig, sl, tp, mh)
                if r is None:
                    continue
                r.update(filter=fname, hold_h=hh, geom=gname, sl=sl, tp=tp,
                         max_hold=mh)
                rows.append(r)
                print(f"  {fname} h={hh} {gname:2} sl={sl:4.0f} tp={tp:6.0f} "
                      f"| n={r['n']:4d} wr={r['wr']:5.1f} "
                      f"exp={r['exp_net']:+.3f} exp@2c={r['exp2c']:+.3f} "
                      f"t={r['t']:+.2f} texit={r['time_exit_pct']:.0f}%",
                      flush=True)

    res = pd.DataFrame(rows)

    # مرحلهٔ دوتایی: دو فیلترِ برتر به معیارِ منجمد (بهترین سلولِ هر فیلتر)
    single = res[res['filter'] != 'F0']
    best_per_f = (single.sort_values('exp2c', ascending=False)
                  .groupby('filter').head(1).sort_values('exp2c',
                                                         ascending=False))
    top2 = best_per_f['filter'].tolist()[:2]
    print(f"\n[pairwise] top-2 filters by best-cell exp@2c: {top2}", flush=True)
    if len(top2) == 2:
        sig = base & filters[top2[0]][:split] & filters[top2[1]][:split]
        for hh in HOLD_HOURS:
            mh = int(round(hh * bph))
            for gname, sl, tp in GEOMS:
                r = eval_cell(dfa, sig, sl, tp, mh)
                if r is None:
                    continue
                r.update(filter='+'.join(top2), hold_h=hh, geom=gname,
                         sl=sl, tp=tp, max_hold=mh)
                rows.append(r)
                print(f"  {r['filter']} h={hh} {gname:2} "
                      f"| n={r['n']:4d} wr={r['wr']:5.1f} "
                      f"exp={r['exp_net']:+.3f} exp@2c={r['exp2c']:+.3f} "
                      f"t={r['t']:+.2f}", flush=True)
        res = pd.DataFrame(rows)

    # تابعِ انتخابِ منجمد (پیش‌ثبت بندِ ۵)
    ok = res[(res['n'] >= N_MIN_TUNE) & (res['exp2c'] > 0)]
    if len(ok) == 0:
        print("\n[SELECTION] هیچ سلولی exp@2c>0 با n>=200 ندارد ⇒ توقفِ کامل، "
              "REJECT-قبل-از-آزمون (نیمهٔ دوم لمس نمی‌شود).", flush=True)
        winner = None
    else:
        winner = ok.sort_values(['exp2c', 't'], ascending=False).iloc[0].to_dict()
        print(f"\n[WINNER] {json.dumps(winner, ensure_ascii=False, default=str)}",
              flush=True)

    out = dict(split_bar=split, bars=n, bars_per_hour=bph, cost_pip=c,
               filters_meta=fmeta, cells=rows, top2=top2,
               winner=winner, n_trials=N_TRIALS)
    with open(os.path.join(OUT, 'tune.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f"[saved] {OUT}/tune.json", flush=True)


if __name__ == '__main__':
    if '--tune' in sys.argv:
        tune()
    else:
        print("usage: python strategies/s410_firstbar_eur.py --tune", flush=True)
