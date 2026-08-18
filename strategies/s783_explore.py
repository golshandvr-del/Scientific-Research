# -*- coding: utf-8 -*-
"""
S783 — فاز اکتشاف (مسیر C اصلاح‌شده — جست‌وجو در ناحیهٔ رژیم-همگن)
====================================================================
جست‌وجو: 2018-11-09 .. 2022-09-01 · hold-out (لمس‌نشده): 2022-09-01 .. 2026-08

فرضیه: تغییر وضعیت رویدادیِ اندیکاتورهای composite که جهت را از «ساختار روند»
می‌گیرند (نه سوگیری صعودی) — elder_impulse (سبز/قرمز شدن) و er_lucas
(نسبت کارایی کافمن با پنجره‌های لوکاس؛ جهت از علامت تغییر خالص قیمت).

رتبه‌بندی: آلفای هر سمت نسبت به بی‌قید هم‌سمت + غربال پایداری ثلثی + پیش‌شرط توان.
"""
import os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s783')
os.makedirs(OUT, exist_ok=True)

ASSET = 'XAUUSD'
SEARCH_LO, SEARCH_HI = 1_541_749_500, 1_661_990_400
TFS = ['M30', 'H1']
GEOMS = [(1.87, 1.87), (1.87, 2.24), (2.23, 2.68), (1.53, 1.91)]
ER_WINDOWS = [11, 18, 29, 47]        # لوکاس (ضداشتباه #7)
ER_THRS = [0.31, 0.42, 0.53]         # آستانهٔ کارایی، غیررُند


def atr_pips(df, period=34):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.nanmedian(pd.Series(tr).rolling(period).mean().values) / 0.10)


def uncond(df, side, sl, tp, mh, stride=3):
    n = len(df); sig = np.zeros(n, bool); sig[300::stride] = True
    e = np.zeros(n, bool)
    a = (sig, e) if side == 'long' else (e, sig)
    tr = se.simulate_trades(df, a[0], a[1], sl_pip=sl, tp_pip=tp, asset=ASSET,
                            max_hold=mh, allow_overlap=False)
    return 100.0 * float((tr['pnl_pip'] > 0).mean()) if len(tr) else np.nan


def state_entry(state):
    """رویداد: لحظهٔ ورود به وضعیت (True پس از False) — سیگنال رویدادی، نه وضعیتی."""
    s = np.asarray(state, bool)
    p = np.roll(s, 1); p[0] = True
    return s & ~p


def signal_sets(df):
    """dict نام → (long_events, short_events)"""
    out = {}
    # ۱) elder_impulse: +1 سبز، −1 قرمز (تأیید قرارداد در زمان اجرا)
    ei = np.nan_to_num(np.asarray(ib.compute('elder_impulse', df), float))
    out['elder_impulse'] = (state_entry(ei > 0), state_entry(ei < 0))
    # ۲) er_lucas جهت‌دار: ER بالای آستانه + جهت از تغییر خالص پنجره
    c = df['close'].values.astype(float)
    for w in ER_WINDOWS:
        er = np.nan_to_num(np.asarray(ib.compute(f'er_lucas_{w}', df), float))
        net = c - np.roll(c, w); net[:w] = 0.0
        for thr in ER_THRS:
            longst = (er >= thr) & (net > 0)
            shortst = (er >= thr) & (net < 0)
            out[f'er{w}@{thr}'] = (state_entry(longst), state_entry(shortst))
    return out


def main():
    rows = []
    for tf in TFS:
        d = fd.load_fast(ASSET, tf)
        dfF = fd.as_dataframe(d)
        m = (dfF['time'].values >= SEARCH_LO) & (dfF['time'].values < SEARCH_HI)
        df = dfF.loc[m].reset_index(drop=True)
        print(f'[{tf}] search {len(df)} bars  src={d["src"]}', flush=True)
        ap = atr_pips(df); mh = fd.hold_bars_for(tf, 72)
        base = {}
        for g in GEOMS:
            sl = round(g[0] * ap, 1); tp = round(g[1] * ap, 1)
            base[g] = dict(sl=sl, tp=tp,
                           long=uncond(df, 'long', sl, tp, mh),
                           short=uncond(df, 'short', sl, tp, mh))
        for name, (up, dn) in signal_sets(df).items():
            for g in GEOMS:
                b = base[g]
                tr = se.simulate_trades(df, up, dn, sl_pip=b['sl'], tp_pip=b['tp'],
                                        asset=ASSET, max_hold=mh, allow_overlap=False)
                n = len(tr)
                if n < 80:
                    continue
                parts, aw, ne = {}, 0.0, 0
                for side in ('long', 'short'):
                    t = tr[tr['direction'] == side]; ns = len(t)
                    if ns == 0:
                        continue
                    wr = 100.0 * float((t['pnl_pip'] > 0).mean())
                    p0 = b[side]
                    a = wr - p0
                    zs = (a / 100) * np.sqrt(ns) / np.sqrt((p0/100) * (1 - p0/100))
                    parts[side] = (ns, round(wr, 2), round(a, 2), round(zs, 2))
                    aw += a * ns; ne += ns
                z_pool = sum(parts[s][3] * np.sqrt(parts[s][0]) for s in parts) / \
                         np.sqrt(sum(parts[s][0] for s in parts))
                # پیش‌شرط توان: هر دو سمت باید α>0 داشته باشند (مکانیزم دوطرفه)
                two_sided = all(parts[s][2] > 0 for s in parts) if len(parts) == 2 else False
                rows.append(dict(tf=tf, sig=name, sl_atr=g[0], tp_atr=g[1],
                                 sl=b['sl'], tp=b['tp'], n=int(n),
                                 alpha=round(aw / ne, 2), z_alpha=round(float(z_pool), 2),
                                 two_sided=two_sided,
                                 net=round(float(tr['pnl_pip'].sum()), 1),
                                 L=parts.get('long'), S=parts.get('short')))
        print(f'[{tf}] done', flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, 'explore_search_region.csv'), index=False)
    ok = out[(out.net > 0) & out.two_sided].sort_values('z_alpha', ascending=False)
    print(f'\nconfigs: {len(out)}  economic+two-sided: {len(ok)}')
    print(ok.head(20).to_string(index=False))


if __name__ == '__main__':
    t0 = time.time(); main(); print(f'elapsed: {time.time()-t0:.1f}s')
