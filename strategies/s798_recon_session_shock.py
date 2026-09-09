# -*- coding: utf-8 -*-
"""
S798 recon — Session-Conditional Shock Continuation روی XAUUSD — فقط نیمهٔ اول (Path C).

فرضیه: ارزش اطلاعاتی یک کندل شوک به «کدام نشست» بستگی دارد. شوک نشست لندن (کشف قیمت،
فیکس) ادامه می‌یابد؛ شوک نشست آسیا/اواخر نیویورک (نقدینگی کم) نویز است.
کندل‌های H8: 00 (آسیا) / 08 (لندن) / 16 (نیویورک). H6: 00/06/12/18. H12: 00/12.

رویداد در i: range_i ≥ θ·ATR21[i−1] (ATR علّی)، جهت = sign(close−open)، اختیاری ρ ≥ 0.618.
ورود open(i+1) هم‌جهت. SL=k·ATR21[i−1]، TP=RR·SL. فقط اگر hour(i) ∈ نشست مورد نظر.
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se

PIP = 0.10
HERE = os.path.dirname(os.path.abspath(__file__))
TFS = {'H6': (0, 6, 12, 18), 'H8': (0, 8, 16), 'H12': (0, 12)}
MH = {'H6': 16, 'H8': 12, 'H12': 8}   # ≈ ۴ روز، ثابت


def atr21(h, l, c, p=21):
    n = len(c)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    tr = np.r_[h[0] - l[0], tr]
    a = np.empty(n); a[0] = tr[0]; al = 2 / (p + 1)
    for i in range(1, n):
        a[i] = a[i - 1] + (tr[i] - a[i - 1]) * al
    return np.r_[np.nan, a[:-1]]


CACHE = {}
def card(tf):
    if tf not in CACHE:
        d = fd.load_fast('XAUUSD', tf); df = fd.as_dataframe(d)
        assert 'mt5_full' in d['src'], 'E-16 guard'
        df = df.iloc[:len(df) // 2].reset_index(drop=True)
        o, h, l, c = [df[k].values for k in ('open', 'high', 'low', 'close')]
        hr = pd.to_datetime(df['time'], unit='s').dt.hour.values
        CACHE[tf] = dict(df=df, o=o, h=h, l=l, c=c, hr=hr, atr=atr21(h, l, c), src=d['src'],
                         half_time=int(df['time'].values[-1]))
    return CACHE[tf]


def run(tf, theta, hour, rho, k, rr):
    C = card(tf); o, h, l, c, atr, hr = C['o'], C['h'], C['l'], C['c'], C['atr'], C['hr']
    rng_ = h - l
    ret = np.where(rng_ > 0, np.abs(c - o) / np.where(rng_ > 0, rng_, 1), 0)
    sig = (rng_ >= theta * atr) & ~np.isnan(atr) & (c != o) & (ret >= rho)
    if hour is not None:
        sig &= (hr == hour)
    d = np.sign(c - o)
    ls = sig & (d > 0); ss = sig & (d < 0)
    sl = np.where(~np.isnan(atr), k * atr / PIP, 0.0)
    tr = se.simulate_trades(C['df'], ls, ss, sl, sl * rr, 'XAUUSD', max_hold=MH[tf], allow_overlap=False)
    return tr, ls, ss, sl


def stats(tr):
    p = tr['pnl_pip'].values; gw = p[p > 0].sum(); gl = -p[p < 0].sum()
    return dict(n=int(len(p)), wr=round(100 * float((p > 0).mean()), 2), exp=round(float(p.mean()), 2),
                pf=round(float(gw / gl), 3) if gl > 0 else None, net=round(float(p.sum()), 1))


rng = np.random.default_rng(798)
def null_wr(tf, ls, ss, sl, rr, draws=12):
    C = card(tf); df = C['df']; n = len(df); nL, nS = int(ls.sum()), int(ss.sum())
    valid = np.where(sl > 0)[0]; nn = nw = 0
    for _ in range(draws):
        idx = rng.choice(valid, nL + nS, replace=False)
        l2 = np.zeros(n, bool); s2 = np.zeros(n, bool); l2[idx[:nL]] = True; s2[idx[nL:]] = True
        t2 = se.simulate_trades(df, l2, s2, sl, sl * rr, 'XAUUSD', max_hold=MH[tf], allow_overlap=False)
        nn += len(t2); nw += int((t2['pnl_pip'] > 0).sum())
    return 100 * nw / nn if nn else float('nan')


out = dict(grid=[], src={}, half_time={}); n_cfg = 0
for tf, hours in TFS.items():
    out['src'][tf] = card(tf)['src']; out['half_time'][tf] = card(tf)['half_time']
    for theta in (1.618, 2.058, 2.618):
        for rho in (0.0, 0.618):
            for k, rr in ((1.272, 2.058), (1.618, 1.0)):
                for hour in (None,) + tuple(hours):
                    n_cfg += 1
                    tr, ls, ss, sl = run(tf, theta, hour, rho, k, rr)
                    if len(tr) < 25:
                        continue
                    st = stats(tr)
                    nu = null_wr(tf, ls, ss, sl, rr)
                    lift = st['wr'] - nu
                    rec = dict(tf=tf, theta=theta, rho=rho, k=k, rr=rr, hour=hour, null=round(nu, 2),
                               lift=round(lift, 2), zproxy=round(lift / (50 / math.sqrt(st['n'])), 2), **st)
                    out['grid'].append(rec)
                    print(rec, flush=True)
out['n_configs_total'] = n_cfg
with open(os.path.join(HERE, 's798_recon_results.json'), 'w') as f:
    json.dump(out, f, indent=1, default=str)
print('TOTAL_CONFIGS_TESTED=', n_cfg)
# خلاصه: برای هر (tf,theta,rho,k,rr) مقایسهٔ نشست‌ها با all-hours
print('\n=== session vs all-hours (lift pp) ===')
G = out['grid']
for key in sorted({(g['tf'], g['theta'], g['rho'], g['k']) for g in G}):
    rows = [g for g in G if (g['tf'], g['theta'], g['rho'], g['k']) == key]
    allh = [g for g in rows if g['hour'] is None]
    s = f'{key}: ' + ' | '.join(f"h={g['hour']}:n={g['n']},lift={g['lift']:+.1f},pf={g['pf']}" for g in sorted(rows, key=lambda x: (x['hour'] is None, x['hour'] or -1)))
    print(s)
