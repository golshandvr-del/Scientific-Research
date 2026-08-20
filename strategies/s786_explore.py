# -*- coding: utf-8 -*-
"""
S786 — فاز اکتشاف: ردِ جاروی نقدینگی درون‌کندلی (Wick-Rejection) — مسیر C
===========================================================================
کشف فقط روی ۶۰٪ نخست دادهٔ کامل ۱۵.۶ ساله؛ ۴۰٪ hold-out لمس نمی‌شود.

فرضیه: کندل با سایهٔ غالب (سهم سایه ≥ آستانهٔ طلایی) و دامنهٔ بزرگ (≥k×ATR علّی)
= جاروی نقدینگی + ردّ آن. جهتِ ردّ (بستهٔ کندل در سمت مقابل سایه) تداوم می‌گیرد:
سایهٔ پایینی غالب → LONG؛ سایهٔ بالایی غالب → SHORT. اختیاری: هم‌راستایی درفت.

رویداد گسستهٔ ساختاری (الگوی برندگان S404/S560/S950)، دستهٔ pattern (بدون لایهٔ زنده).
خانوادهٔ پیش‌اعلام همین‌جا کامل شمارش می‌شود (n_trials صادقانه).
"""
import os, sys, time, itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s786')
os.makedirs(OUT, exist_ok=True)

ASSET = 'XAUUSD'
TFS = ['H2', 'H3', 'H6', 'H8']          # H4 عمداً غایب (فایل کوتاه؛ دام E-16)
WICK_SHARES = [0.618, 0.708]            # سهم سایهٔ غالب از دامنه (غیررُند)
RANGE_KS = [1.272, 1.618]               # دامنه ≥ k × ATR(89) علّی
DRIFT_MODES = ['none', 'align89']       # فیلتر هم‌راستایی درفت ۸۹ کندلی
K_SLS = [1.618, 2.058]                  # SL = k × ATRmed(89) علّی
RRS = [1.0, 1.272]                      # TP = RR × SL — همیشه TP>=SL
MAX_HOLD = 34
DISC_FRAC = 0.60


def causal_atr(df, period=89):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(period).mean().shift(1).values  # علّی تا t-1


def uncond_wr(df, side, sl, tp, mh, stride=3):
    n = len(df); sig = np.zeros(n, bool); sig[300::stride] = True
    e = np.zeros(n, bool)
    a = (sig, e) if side == 'long' else (e, sig)
    tr = se.simulate_trades(df, a[0], a[1], sl_pip=sl, tp_pip=tp, asset=ASSET,
                            max_hold=mh, allow_overlap=False)
    return 100.0 * float((tr['pnl_pip'] > 0).mean()) if len(tr) else np.nan


def main():
    rows = []
    n_family = 0
    for tf in TFS:
        d = fd.load_fast(ASSET, tf)
        dfF = fd.as_dataframe(d)
        n_disc = int(DISC_FRAC * len(dfF))
        df = dfF.iloc[:n_disc].reset_index(drop=True)
        print(f'\n### {tf}: disc {len(df)}/{len(dfF)} bars  src={d["src"]}', flush=True)

        o = df['open'].values.astype(float)
        h = df['high'].values.astype(float)
        l = df['low'].values.astype(float)
        c = df['close'].values.astype(float)
        atr = causal_atr(df)
        atr_med_pip = float(np.nanmedian(atr)) / 0.10
        rng = h - l
        rng_safe = np.where(rng > 0, rng, np.nan)
        up_wick = h - np.maximum(o, c)
        lo_wick = np.minimum(o, c) - l
        lo_share = lo_wick / rng_safe
        up_share = up_wick / rng_safe
        pc1 = np.roll(c, 1); pc1[0] = np.nan
        drift89 = pc1 - np.roll(c, 90); drift89[:91] = np.nan

        ucache = {}
        for ws, rk, dm in itertools.product(WICK_SHARES, RANGE_KS, DRIFT_MODES):
            big = np.isfinite(atr) & (rng >= rk * atr)
            long_ev = big & (lo_share >= ws)    # جاروی پایین رد شد → LONG
            short_ev = big & (up_share >= ws)   # جاروی بالا رد شد → SHORT
            if dm == 'align89':
                long_ev = long_ev & (drift89 > 0)
                short_ev = short_ev & (drift89 < 0)
            for k_sl, rr in itertools.product(K_SLS, RRS):
                n_family += 1
                sl = round(k_sl * atr_med_pip, 1)
                tp = round(rr * sl, 1)
                tr = se.simulate_trades(df, long_ev, short_ev, sl_pip=sl, tp_pip=tp,
                                        asset=ASSET, max_hold=MAX_HOLD,
                                        allow_overlap=False)
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
                        ucache[key] = uncond_wr(df, side, sl, tp, MAX_HOLD)
                    p0 = ucache[key]
                    a = wr - p0
                    ta += a * ns; tn += ns
                    det[side] = (ns, round(wr, 1), round(p0, 1), round(a, 1))
                alpha = ta / tn
                p0m = np.mean([x[2] for x in det.values()]) / 100.0
                z = (alpha / 100.0) * np.sqrt(n) / np.sqrt(p0m * (1 - p0m))
                net = round(float(tr['pnl_pip'].sum()))
                rows.append(dict(tf=tf, ws=ws, rk=rk, drift=dm, k_sl=k_sl, rr=rr,
                                 sl=sl, tp=tp, n=n, alpha=round(alpha, 2),
                                 z=round(z, 2), net=net, detail=str(det)))
                if z >= 2.3:
                    print(f'  ws={ws} rk={rk} {dm} k={k_sl} rr={rr} n={n} '
                          f'alpha={alpha:+.2f} z={z:+.2f} net={net:+d} {det}', flush=True)

    res = pd.DataFrame(rows).sort_values('z', ascending=False)
    res.to_csv(f'{OUT}/explore_discovery.csv', index=False)
    print(f'\n=== family size (honest n_trials base): {n_family} ===')
    print(f'valid rows (n>=60): {len(res)}')
    print(res.head(14).to_string(index=False))
    print(f'\nconfigs with z>=3.09: {(res["z"] >= 3.09).sum()}')
    print(f'configs with z<=-3.09 (mirror fade edge): {(res["z"] <= -3.09).sum()}')


if __name__ == '__main__':
    t0 = time.time(); main(); print(f'elapsed: {time.time()-t0:.1f}s')
