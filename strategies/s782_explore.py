# -*- coding: utf-8 -*-
"""
S782 — فاز اکتشاف (مسیر C اصلاح‌شده: جست‌وجو و تأیید هر دو در عصر مدرن)
========================================================================
درس S780+S781: مرز رژیمی ۲۰۱۸ در طلا، پایداری ۲۰۱۱–۲۰۱۸ را بی‌اعتبار می‌کند.
اینجا: جست‌وجو فقط روی 2018-11-09..2022-09-01؛ تأیید (بعداً، پس از پیش‌ثبت)
روی 2022-09-01..2026-08 که برای این فرضیه دست‌نخورده می‌ماند.

خانواده (ثابت، اعلام‌شده): الگوهای کندلی مومنتوم از دستهٔ pattern —
  cdl_marubozu (دوجهته با جهت بدنه)، cdl_engulf_bull/bear،
  cdl_3whitesoldiers/3blackcrows، cdl_beltuphold_bull/bear
تفسیر: تداوم. رتبه‌بندی: آلفای هر سمت نسبت به بی‌قید هم‌سمت (درس S780).
غربال: پایداری ثلثی در ناحیهٔ جست‌وجو (درس S781 — لازم ولی ناکافی؛ اینجا
رژیم-همگن است پس امید بیشتری به انتقال دارد).
"""
import os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s782')
os.makedirs(OUT, exist_ok=True)

ASSET = 'XAUUSD'
SEARCH_LO = 1_541_749_500          # 2018-11-09
SEARCH_HI = 1_661_990_400          # 2022-09-01
TFS = ['M30', 'H1']
GEOMS = [(1.87, 1.87), (1.87, 2.24), (2.23, 2.68), (1.53, 1.91)]

# جفت‌های (نام لانگ، نام شورت) — ماروبوزو جهتش را از بدنه می‌گیرد
PAIRS = [
    ('marubozu_dir', None),                      # ویژه: جهت از بدنه
    ('cdl_engulf_bull', 'cdl_engulf_bear'),
    ('cdl_3whitesoldiers', 'cdl_3blackcrows'),
    ('cdl_beltuphold_bull', 'cdl_beltuphold_bear'),
]


def atr_pips(df, period=34):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.nanmedian(pd.Series(tr).rolling(period).mean().values) / 0.10)


def sig_bool(name, df):
    """قرارداد بانک: صعودی=+100، نزولی=−100. هر مقدار غیرصفر یعنی وقوع الگو."""
    v = np.asarray(ib.compute(name, df), dtype=float)
    return np.nan_to_num(v) != 0


def uncond(df, side, sl, tp, mh, stride=3):
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
        m = (dfF['time'].values >= SEARCH_LO) & (dfF['time'].values < SEARCH_HI)
        df = dfF.loc[m].reset_index(drop=True)
        print(f'[{tf}] search region {len(df)} bars  src={d["src"]}', flush=True)
        ap = atr_pips(df); mh = fd.hold_bars_for(tf, 72)
        base = {}
        for g in GEOMS:
            sl = round(g[0] * ap, 1); tp = round(g[1] * ap, 1)
            base[g] = dict(sl=sl, tp=tp,
                           long=uncond(df, 'long', sl, tp, mh),
                           short=uncond(df, 'short', sl, tp, mh))
        for lname, sname in PAIRS:
            if lname == 'marubozu_dir':
                v = np.nan_to_num(np.asarray(ib.compute('cdl_marubozu', df), float))
                up, dn = v > 0, v < 0
                fam = 'marubozu'
            else:
                up, dn = sig_bool(lname, df), sig_bool(sname, df)
                fam = lname.replace('cdl_', '').replace('_bull', '')
            for g in GEOMS:
                b = base[g]
                tr = se.simulate_trades(df, up, dn, sl_pip=b['sl'], tp_pip=b['tp'],
                                        asset=ASSET, max_hold=mh, allow_overlap=False)
                n = len(tr)
                if n < 60:
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
                rows.append(dict(tf=tf, fam=fam, sl_atr=g[0], tp_atr=g[1],
                                 sl=b['sl'], tp=b['tp'], n=int(n),
                                 alpha=round(aw / ne, 2), z_alpha=round(float(z_pool), 2),
                                 net=round(float(tr['pnl_pip'].sum()), 1),
                                 L=parts.get('long'), S=parts.get('short')))
        print(f'[{tf}] done', flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, 'explore_search_region.csv'), index=False)
    ok = out[out.net > 0].sort_values('z_alpha', ascending=False)
    print(f'\nconfigs: {len(out)}  economic: {len(ok)}')
    print(ok.head(25).to_string(index=False))


if __name__ == '__main__':
    t0 = time.time(); main(); print(f'elapsed: {time.time()-t0:.1f}s')
