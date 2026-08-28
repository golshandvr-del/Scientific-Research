# -*- coding: utf-8 -*-
"""
S789 — فاز اکتشاف: اکسترمم تازه پس از خمودگی (Dormancy-Gated Fresh Extreme)
===========================================================================
کشف فقط روی ۶۰٪ نخست دادهٔ کامل ۱۵.۶ ساله؛ ۴۰٪ پایانی لمس نمی‌شود.
انضباط: z_alpha >= 3.09 لازمهٔ ورود به داوری (درس S780-S788).

فرضیه: رویداد گسستهٔ «ثبت اولین سقف/کف W-کندلی تازه پس از حداقل D کندل
خمودگی (بدون اکسترمم تازهٔ هم‌سو)» در H6/H8/H12/D1 طلا جهت‌دار است.
گیت این‌جا «ساختار زمانی» (dormancy) است — متمایز از گیت نوسانی S800
(چندک atr_pct) و متمایز از سطح ایستای S788. خانواده بکر (grep: dormancy/
days-since هیچ سابقه‌ای ندارد).

خانوادهٔ کامل پیش‌اعلام: 4TF × 2W × 2D × 2mode × 2k_sl × 2RR = 128 عضو.
"""
import os, sys, itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from strategies.s788_explore import causal_atr, simulate, uncond_wr  # بازاستفادهٔ هندسه

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s789')
os.makedirs(OUT, exist_ok=True)

ASSET = 'XAUUSD'
TFS = ['H6', 'H8', 'H12', 'D1']
WINS = [89, 144]            # پنجرهٔ اکسترمم (فیبوناچی)
DORMS = [21, 34]            # حداقل خمودگی (کندل بدون اکسترمم هم‌سو)
MODES = ['cont', 'rev']     # cont: long روی سقف تازه / short روی کف تازه
K_SLS = [1.618, 2.058]
RRS = [1.0, 1.272]
MAX_HOLD = 21
DISC_FRAC = 0.60
PIP = 0.10


def fresh_extreme_events(df, W, D):
    """up[i]: سقف W-کندلی تازه پس از >=D کندل بدون سقف تازه. متقارن برای کف."""
    h, l = df['high'].values, df['low'].values
    roll_hi = pd.Series(h).rolling(W).max().shift(1).values
    roll_lo = pd.Series(l).rolling(W).min().shift(1).values
    n = len(h)
    up = np.zeros(n, dtype=bool)
    dn = np.zeros(n, dtype=bool)
    last_hi = -10**9
    last_lo = -10**9
    for i in range(n):
        if np.isfinite(roll_hi[i]) and h[i] > roll_hi[i]:
            if i - last_hi >= D:
                up[i] = True
            last_hi = i
        if np.isfinite(roll_lo[i]) and l[i] < roll_lo[i]:
            if i - last_lo >= D:
                dn[i] = True
            last_lo = i
    return up, dn


def main():
    rows = []
    data = {}
    for tf in TFS:
        d = fd.load_fast(ASSET, tf)
        assert 'mt5_full' in d['src'], f"E-16 trap: {d['src']}"
        df = fd.as_dataframe(d)
        cut = int(len(df) * DISC_FRAC)
        data[tf] = df.iloc[:cut].reset_index(drop=True)
        print(f"{tf}: full={len(df)} disc={cut}", flush=True)

    ucache = {}
    for tf, W, D, mode, k_sl, rr in itertools.product(
            TFS, WINS, DORMS, MODES, K_SLS, RRS):
        df = data[tf]
        atr = causal_atr(df, 89)
        atr_pips = atr / PIP
        up, dn = fresh_extreme_events(df, W, D)
        if mode == 'cont':
            legs = [('long', np.where(up)[0]), ('short', np.where(dn)[0])]
        else:
            legs = [('short', np.where(up)[0]), ('long', np.where(dn)[0])]
        outs_all, nets_all = [], []
        alpha_w, nsum = 0.0, 0
        for side, idx in legs:
            outs, nets, _ = simulate(df, idx, side, k_sl, rr, atr_pips, MAX_HOLD)
            if len(outs) == 0:
                continue
            key = (tf, side, k_sl, rr)
            if key not in ucache:
                ucache[key] = uncond_wr(df, side, k_sl, rr, atr_pips, MAX_HOLD)
            p0 = ucache[key]
            alpha_w += (100.0 * outs.mean() - p0) * len(outs)
            nsum += len(outs)
            outs_all.append(outs); nets_all.append(nets)
        if nsum < 40:
            rows.append(dict(tf=tf, W=W, D=D, mode=mode, k_sl=k_sl, rr=rr,
                             n=nsum, alpha=np.nan, z=np.nan, net=np.nan))
            continue
        outs_c = np.concatenate(outs_all)
        nets_c = np.concatenate(nets_all)
        alpha = alpha_w / nsum
        z = (alpha / 100.0) * np.sqrt(nsum) / 0.5
        rows.append(dict(tf=tf, W=W, D=D, mode=mode, k_sl=k_sl, rr=rr,
                         n=nsum, alpha=round(alpha, 2), z=round(z, 2),
                         net=round(nets_c.sum(), 0)))
        print(f"{tf} W={W} D={D} {mode} k={k_sl} rr={rr}: n={nsum} "
              f"a={alpha:+.2f} z={z:+.2f} net={nets_c.sum():+.0f}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, 'explore_discovery.csv'), index=False)
    ok = out.dropna(subset=['z']).sort_values('z', ascending=False)
    print("\n=== TOP 12 by z ===")
    print(ok.head(12).to_string(index=False))
    print(f"\nfamily members this round: {len(rows)}")


if __name__ == '__main__':
    main()
