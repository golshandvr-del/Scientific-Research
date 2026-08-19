# -*- coding: utf-8 -*-
"""
S784 — فاز اکتشاف (مسیر C — ناحیهٔ جست‌وجوی رژیم-همگن؛ hold-out قفل)
=====================================================================
فرضیه: رویداد اشباع جریان پول (MFI فرین) در طلا — خانوادهٔ volume که
در هیچ لایهٔ زنده‌ای نیست. دو تفسیر (تداوم/بازگشت)، دو سمت جدا.

انضباط جدید (درس S783): فقط نامزدی به آزمون تأییدی می‌رود که در ناحیهٔ
جست‌وجو z_alpha >= 3.09 داشته باشد (نسبت به بی‌قید هم‌سمت).

ناحیهٔ جست‌وجو: 2018-11-09 .. 2022-09-01  (time in [1541749500, 1661990400))
hold-out:       2022-09-01 .. انتها — در این فایل هرگز خوانده نمی‌شود.
"""
import os, sys, time, itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s784')
os.makedirs(OUT, exist_ok=True)

LO, HI = 1_541_749_500, 1_661_990_400   # ناحیهٔ جست‌وجو
ASSET = 'XAUUSD'
TFS = ['M30', 'H1', 'H2', 'H3']
# آستانه‌های غیررُند (ضداشتباه #7) روی MFI (0..100)
THRS = [(17.3, 82.7), (12.9, 87.1), (9.4, 90.6)]
GEOMS = [(1.53, 1.91), (1.87, 2.24), (2.23, 2.68)]   # SL_ATR, TP_ATR — همیشه TP>SL
MODES = ['reversal', 'continuation']


def atr_pips(df, period=34):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.nanmedian(pd.Series(tr).rolling(period).mean().values) / 0.10)


def enter_low(x, lo):
    """رویداد: ورود به ناحیهٔ فرین پایین (عبور رو به پایین از lo)."""
    x = np.asarray(x, float); p = np.roll(x, 1); p[0] = np.nan
    return (p > lo) & (x <= lo) & np.isfinite(p)


def enter_high(x, hi):
    x = np.asarray(x, float); p = np.roll(x, 1); p[0] = np.nan
    return (p < hi) & (x >= hi) & np.isfinite(p)


def uncond_wr(df, side, sl, tp, mh, stride=3):
    n = len(df); sig = np.zeros(n, bool); sig[300::stride] = True
    e = np.zeros(n, bool)
    a = (sig, e) if side == 'long' else (e, sig)
    tr = se.simulate_trades(df, a[0], a[1], sl_pip=sl, tp_pip=tp, asset=ASSET,
                            max_hold=mh, allow_overlap=False)
    return 100.0 * float((tr['pnl_pip'] > 0).mean()) if len(tr) else np.nan


def main():
    rows = []
    for tf in TFS:
        d = fd.load_fast(ASSET, tf)
        dfF = fd.as_dataframe(d)
        m = (dfF['time'].values >= LO) & (dfF['time'].values < HI)
        df = dfF.loc[m].reset_index(drop=True)
        print(f'\n### {tf}: {len(df)} bars  src={d["src"]}', flush=True)
        ap = atr_pips(df)
        mh = fd.hold_bars_for(tf, 72)
        mfi = np.asarray(ib.compute('mfi', df), float)

        # کش بی‌قید به‌ازای هندسه×سمت
        ucache = {}
        for (lo, hi), (slk, tpk), mode in itertools.product(THRS, GEOMS, MODES):
            sl = round(slk * ap, 1); tp = round(tpk * ap, 1)
            ev_lo = enter_low(mfi, lo)     # اشباع فروش
            ev_hi = enter_high(mfi, hi)    # اشباع خرید
            if mode == 'reversal':
                up, dn = ev_lo, ev_hi      # اشباع فروش → long
            else:
                up, dn = ev_hi, ev_lo      # اشباع خرید → long (تداوم)
            tr = se.simulate_trades(df, up, dn, sl_pip=sl, tp_pip=tp,
                                    asset=ASSET, max_hold=mh, allow_overlap=False)
            n = len(tr)
            if n < 60:
                continue
            ta, tn = 0.0, 0
            det = {}
            for side in ('long', 'short'):
                t = tr[tr['direction'] == side]; ns = len(t)
                if ns == 0:
                    continue
                wr = 100.0 * float((t['pnl_pip'] > 0).mean())
                key = (side, sl, tp)
                if key not in ucache:
                    ucache[key] = uncond_wr(df, side, sl, tp, mh)
                p0 = ucache[key]
                a = wr - p0
                ta += a * ns; tn += ns
                det[side] = (ns, round(wr, 1), round(p0, 1), round(a, 1))
            alpha = ta / tn
            p0m = np.mean([v[2] for v in det.values()]) / 100.0
            z = (alpha / 100.0) * np.sqrt(n) / np.sqrt(p0m * (1 - p0m))
            rows.append(dict(tf=tf, mode=mode, lo=lo, hi=hi, slk=slk, tpk=tpk,
                             sl=sl, tp=tp, n=n, alpha=round(alpha, 2),
                             z=round(z, 2), net=round(float(tr['pnl_pip'].sum())),
                             detail=str(det)))
            if abs(z) >= 2.0:
                print(f'  {mode[:4]} thr=({lo},{hi}) geom=({slk},{tpk}) '
                      f'n={n} alpha={alpha:+.2f} z={z:+.2f} '
                      f'net={rows[-1]["net"]:+d} {det}', flush=True)

    res = pd.DataFrame(rows).sort_values('z', ascending=False)
    res.to_csv(f'{OUT}/explore_search_region.csv', index=False)
    print(f'\n=== total configs valid: {len(res)} ===')
    print(res.head(12).to_string(index=False))
    print(f'\nconfigs with z>=3.09: {(res["z"]>=3.09).sum()}')


if __name__ == '__main__':
    t0 = time.time(); main(); print(f'elapsed: {time.time()-t0:.1f}s')
