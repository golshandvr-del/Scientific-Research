# -*- coding: utf-8 -*-
"""
S781 — فاز اکتشاف (مسیر C — فقط نیمهٔ اول)
=============================================
درس S780: رتبه‌بندی با سربه‌سر هندسی، بتا را با آلفا اشتباه می‌گیرد.
اینجا معیار رتبه‌بندی از همان آغاز: **آلفای هر سمت نسبت به ورود بی‌قیدِ
هم‌سمت با همان هندسه** است (uncond baseline per side/geom).

فرضیه: عبور رویدادی z-score قیمت (پنجره‌های فیبوناچی) از کشیدگی حدی →
بازگشت (mean reversion). دستهٔ statistical تاکنون در هیچ لایهٔ زنده‌ای نیست.

خانوادهٔ اعلام‌شده (ثابت پیش از دیدن نتیجه):
  اندیکاتور: zscore_fib_55 / zscore_fib_89 / zscore_fib_144
  آستانه: 2.17, 2.63, 3.08  (غیررُند)
  حالت: reversion (ورود خلاف جهت کشیدگی) و continuation (کنترل)
  هندسه: (1.87,1.87) (1.87,2.24) (2.23,2.68) (1.53,1.91) — TP>=SL همیشه
  TF: M30, H1 (تنها ناحیهٔ اقتصادی؛ درس دور اول S780)
"""
import os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s781')
os.makedirs(OUT, exist_ok=True)

ASSET = 'XAUUSD'
SPLIT_EPOCH = 1_541_749_500
TFS = ['M30', 'H1']
INDS = ['zscore_fib_55', 'zscore_fib_89', 'zscore_fib_144']
THRS = [2.17, 2.63, 3.08]
MODES = ['reversion', 'continuation']
GEOMS = [(1.87, 1.87), (1.87, 2.24), (2.23, 2.68), (1.53, 1.91)]


def atr_pips(df, period=34):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.nanmedian(pd.Series(tr).rolling(period).mean().values) / 0.10)


def event_cross(x, thr):
    x = np.asarray(x, float)
    p = np.roll(x, 1); p[0] = np.nan
    up = (p < thr) & (x >= thr) & np.isfinite(p)      # کشیدگی به بالا
    dn = (p > -thr) & (x <= -thr) & np.isfinite(p)    # کشیدگی به پایین
    return up, dn


def uncond_side(df, side, sl_pip, tp_pip, max_hold, stride=3):
    n = len(df); sig = np.zeros(n, bool); sig[300::stride] = True
    empty = np.zeros(n, bool)
    a = (sig, empty) if side == 'long' else (empty, sig)
    tr = se.simulate_trades(df, a[0], a[1], sl_pip=sl_pip, tp_pip=tp_pip,
                            asset=ASSET, max_hold=max_hold, allow_overlap=False)
    return 100.0 * float((tr['pnl_pip'] > 0).mean()) if len(tr) else np.nan


def main():
    rows = []
    for tf in TFS:
        d = fd.load_fast(ASSET, tf)
        dfF = fd.as_dataframe(d)
        df = dfF.loc[dfF['time'].values < SPLIT_EPOCH].reset_index(drop=True)
        print(f'[{tf}] first half {len(df)} bars  src={d["src"]}', flush=True)
        ap = atr_pips(df)
        mh = fd.hold_bars_for(tf, 72)
        # خط مبنای بی‌قید هر (سمت، هندسه) — یک بار
        base = {}
        for sl_a, tp_a in GEOMS:
            sl = round(sl_a * ap, 1); tp = round(tp_a * ap, 1)
            base[(sl_a, tp_a)] = dict(
                long=uncond_side(df, 'long', sl, tp, mh),
                short=uncond_side(df, 'short', sl, tp, mh),
                sl=sl, tp=tp)
            print(f'  base geom({sl_a},{tp_a}): uncond L={base[(sl_a,tp_a)]["long"]:.2f} '
                  f'S={base[(sl_a,tp_a)]["short"]:.2f}', flush=True)
        ind_cache = {nm: np.asarray(ib.compute(nm, df), float) for nm in INDS}
        for nm in INDS:
            for thr in THRS:
                up, dn = event_cross(ind_cache[nm], thr)
                for mode in MODES:
                    # reversion: کشیدگی بالا → short، کشیدگی پایین → long
                    ls = (dn, up) if mode == 'reversion' else (up, dn)
                    for g in GEOMS:
                        b = base[g]
                        tr = se.simulate_trades(df, ls[0], ls[1], sl_pip=b['sl'],
                                                tp_pip=b['tp'], asset=ASSET,
                                                max_hold=mh, allow_overlap=False)
                        n = len(tr)
                        if n < 60:
                            continue
                        # آلفای تفکیکی هر سمت نسبت به بی‌قیدِ هم‌سمت
                        za, alpha_w, n_eff = 0.0, 0.0, 0
                        parts = {}
                        for side in ('long', 'short'):
                            t = tr[tr['direction'] == side]
                            ns = len(t)
                            if ns == 0:
                                continue
                            wr = 100.0 * float((t['pnl_pip'] > 0).mean())
                            p0 = b[side]
                            alpha = wr - p0
                            zs = (alpha / 100.0) * np.sqrt(ns) / np.sqrt((p0/100)*(1-p0/100))
                            parts[side] = (ns, round(wr, 2), round(alpha, 2), round(zs, 2))
                            alpha_w += alpha * ns; n_eff += ns
                        alpha_pool = alpha_w / n_eff if n_eff else np.nan
                        # z ترکیبی: وزن‌دهی ریشه‌ای دو سمت
                        z_pool = sum(parts[s][3] * np.sqrt(parts[s][0]) for s in parts) / \
                                 np.sqrt(sum(parts[s][0] for s in parts))
                        rows.append(dict(tf=tf, ind=nm, thr=thr, mode=mode,
                                         sl_atr=g[0], tp_atr=g[1], sl=b['sl'], tp=b['tp'],
                                         n=int(n), alpha=round(alpha_pool, 2),
                                         z_alpha=round(float(z_pool), 2),
                                         net=round(float(tr['pnl_pip'].sum()), 1),
                                         L=parts.get('long'), S=parts.get('short')))
        print(f'[{tf}] done ({len(rows)} rows)', flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, 'explore_first_half.csv'), index=False)
    ok = out[out.net > 0].sort_values('z_alpha', ascending=False)
    print(f'\nconfigs: {len(out)}  economic(net>0): {len(ok)}')
    print(ok.head(25).to_string(index=False))


if __name__ == '__main__':
    t0 = time.time(); main(); print(f'elapsed: {time.time()-t0:.1f}s')
