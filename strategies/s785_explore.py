# -*- coding: utf-8 -*-
"""
S785 — فاز اکتشاف: پس‌لرزهٔ شوک حجم، هم‌راستا با درفت (مسیر C — الگوی S950)
==============================================================================
کشف فقط روی ۶۰٪ نخست دادهٔ کامل ۱۵.۶ ساله؛ ۴۰٪ پایانی تا داوری لمس نمی‌شود.

فرضیه: کندلی که حجم تیک آن از صدک فرینِ علّی بگذرد، حامل ورود اطلاعات است؛
اگر جهت کندل با درفت رژیم (close[t-1]-close[t-D]) هم‌راستا باشد، تداوم می‌گیرد.
دستهٔ volume — در هیچ لایهٔ زنده‌ای نیست. رویداد گسسته (درس برندگان S404/S560/S950).

خانوادهٔ پیش‌اعلام: TF×q×D×k_sl×RR — همهٔ اعضا همین‌جا شمارش می‌شوند (n_trials صادقانه).
"""
import os, sys, time, itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s785')
os.makedirs(OUT, exist_ok=True)

ASSET = 'XAUUSD'
TFS = ['H2', 'H3', 'H4', 'H6', 'H8']
QS = [0.943, 0.977]            # صدک فرین حجم (غیررُند)
DRIFTS = [55, 89]              # پنجرهٔ درفت (فیبوناچی)
K_SLS = [1.618, 2.058]         # ضریب SL بر ATR(89) علّی
RRS = [1.0, 1.272]             # TP = RR×SL — همیشه TP>=SL
VWIN = 233                     # پنجرهٔ رولینگ صدک حجم (فیبوناچی)
DISC_FRAC = 0.60


def causal_atr_pips(df, period=89):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period).mean().shift(1).values  # علّی تا t-1
    return atr / 0.10


def causal_vol_thresh(v, win, q):
    s = pd.Series(v.astype(float))
    thr = s.rolling(win).quantile(q).shift(1).values  # علّی تا t-1
    return thr


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

        c = df['close'].values.astype(float)
        o = df['open'].values.astype(float)
        v = df['volume'].values.astype(float)
        atrp = causal_atr_pips(df)
        atr_med = float(np.nanmedian(atrp))
        mh = 34  # افق ثابت ۳۴ کندل (الگوی S950)

        body = c - o
        pc1 = np.roll(c, 1); pc1[0] = np.nan

        for q, D in itertools.product(QS, DRIFTS):
            thr = causal_vol_thresh(v, VWIN, q)
            shock = np.isfinite(thr) & (v >= thr)
            drift = pc1 - np.roll(c, D + 1)
            drift[:D + 2] = np.nan
            up_ev = shock & (body > 0) & (drift > 0)
            dn_ev = shock & (body < 0) & (drift < 0)
            # ورود در open کندل بعد را شبیه‌ساز رسمی خودش انجام می‌دهد
            for k_sl, rr in itertools.product(K_SLS, RRS):
                n_family += 1
                sl = round(k_sl * atr_med, 1)
                tp = round(rr * sl, 1)
                tr = se.simulate_trades(df, up_ev, dn_ev, sl_pip=sl, tp_pip=tp,
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
                    p0 = uncond_wr(df, side, sl, tp, mh)
                    a = wr - p0
                    ta += a * ns; tn += ns
                    det[side] = (ns, round(wr, 1), round(p0, 1), round(a, 1))
                alpha = ta / tn
                p0m = np.mean([x[2] for x in det.values()]) / 100.0
                z = (alpha / 100.0) * np.sqrt(n) / np.sqrt(p0m * (1 - p0m))
                net = round(float(tr['pnl_pip'].sum()))
                rows.append(dict(tf=tf, q=q, D=D, k_sl=k_sl, rr=rr, sl=sl, tp=tp,
                                 n=n, alpha=round(alpha, 2), z=round(z, 2),
                                 net=net, detail=str(det)))
                if z >= 2.3:
                    print(f'  q={q} D={D} k={k_sl} rr={rr} n={n} '
                          f'alpha={alpha:+.2f} z={z:+.2f} net={net:+d} {det}', flush=True)

    res = pd.DataFrame(rows).sort_values('z', ascending=False)
    res.to_csv(f'{OUT}/explore_discovery.csv', index=False)
    print(f'\n=== family size (honest n_trials base): {n_family} ===')
    print(f'valid rows (n>=60): {len(res)}')
    print(res.head(12).to_string(index=False))
    print(f'\nconfigs with z>=3.09: {(res["z"] >= 3.09).sum()}')


if __name__ == '__main__':
    t0 = time.time(); main(); print(f'elapsed: {time.time()-t0:.1f}s')
