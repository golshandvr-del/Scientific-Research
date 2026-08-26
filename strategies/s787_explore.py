# -*- coding: utf-8 -*-
"""
S787 — فاز اکتشاف: تکمیل رگهٔ چند-کندلی در TFهای بالا (مسیر C)
================================================================
کشف فقط روی ۶۰٪ نخست دادهٔ کامل ۱۵.۶ ساله؛ ۴۰٪ پایانی لمس نمی‌شود.
داوری نهایی (در صورت یافتن نامزد z>=3.09) روی کل داده با split_bar=60%
انجام خواهد شد — الگوی برندگان S602/S770/S950، نه hold-out-only (خطای S780-S784).

فرضیه: رویداد «تکمیل رگهٔ L بستهٔ هم‌جهت» (شمارنده دقیقاً به L می‌رسد) در
H8/H12/D1 اطلاعات جهت‌دار دارد — یا تداوم (momentum چند-روزه) یا بازگشت
(اشباع رگه). رویداد گسستهٔ نادر؛ خانوادهٔ streak در TF بالا هرگز آزموده نشده
(S326 فقط M5/M15 را سوزاند).

خانوادهٔ کامل پیش‌اعلام: 3TF × 3L × 2mode × 2k_sl × 2RR = 72 عضو.
"""
import os, sys, time, itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s787')
os.makedirs(OUT, exist_ok=True)

ASSET = 'XAUUSD'
TFS = ['H8', 'H12', 'D1']
LENS = [3, 4, 5]
MODES = ['cont', 'rev']
K_SLS = [1.618, 2.058]
RRS = [1.0, 1.272]
MAX_HOLD = 21          # فیبوناچی
DISC_FRAC = 0.60


def causal_atr_pips(df, period=89):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period).mean().shift(1).values
    return atr / 0.10


def streak_events(c, L):
    """رویداد: شمارندهٔ رگهٔ بسته‌های هم‌جهت دقیقاً به L می‌رسد (یک‌بار در هر رگه)."""
    r = np.sign(np.diff(c, prepend=c[0]))
    n = len(c)
    cnt = np.zeros(n)
    for i in range(1, n):
        if r[i] > 0:
            cnt[i] = cnt[i - 1] + 1 if cnt[i - 1] > 0 else 1
        elif r[i] < 0:
            cnt[i] = cnt[i - 1] - 1 if cnt[i - 1] < 0 else -1
        else:
            cnt[i] = 0
    up_done = (cnt == L)      # دقیقاً L بستهٔ صعودی
    dn_done = (cnt == -L)
    return up_done, dn_done


def uncond_wr(df, side, sl, tp, mh, stride=3):
    n = len(df); sig = np.zeros(n, bool); sig[120::stride] = True
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
        assert 'mt5_full' in d['src'], f'E-16! src={d["src"]}'
        dfF = fd.as_dataframe(d)
        n_disc = int(DISC_FRAC * len(dfF))
        df = dfF.iloc[:n_disc].reset_index(drop=True)
        print(f'\n### {tf}: disc {len(df)}/{len(dfF)} bars  src={d["src"]}', flush=True)

        c = df['close'].values.astype(float)
        atrp = causal_atr_pips(df)
        atr_med = float(np.nanmedian(atrp))

        ucache = {}
        for L, mode in itertools.product(LENS, MODES):
            upd, dnd = streak_events(c, L)
            if mode == 'cont':
                up_ev, dn_ev = upd, dnd
            else:
                up_ev, dn_ev = dnd, upd
            for k_sl, rr in itertools.product(K_SLS, RRS):
                n_family += 1
                sl = round(k_sl * atr_med, 1)
                tp = round(rr * sl, 1)
                tr = se.simulate_trades(df, up_ev, dn_ev, sl_pip=sl, tp_pip=tp,
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
                rows.append(dict(tf=tf, L=L, mode=mode, k_sl=k_sl, rr=rr, sl=sl,
                                 tp=tp, n=n, alpha=round(alpha, 2), z=round(z, 2),
                                 net=net, detail=str(det)))
                if abs(z) >= 2.3:
                    print(f'  L={L} {mode} k={k_sl} rr={rr} n={n} '
                          f'alpha={alpha:+.2f} z={z:+.2f} net={net:+d} {det}', flush=True)

    res = pd.DataFrame(rows).sort_values('z', ascending=False)
    res.to_csv(f'{OUT}/explore_discovery.csv', index=False)
    print(f'\n=== family size (honest n_trials base): {n_family} ===')
    print(f'valid rows (n>=60): {len(res)}')
    print(res.head(14).to_string(index=False))
    print(f'\nconfigs with z>=3.09: {(res["z"] >= 3.09).sum()}')


if __name__ == '__main__':
    t0 = time.time(); main(); print(f'elapsed: {time.time()-t0:.1f}s')
