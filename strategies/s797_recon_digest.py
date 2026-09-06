# -*- coding: utf-8 -*-
"""
S797 recon — Shock → Digestion → Continuation (SDC) روی XAUUSD — فقط نیمهٔ اول (Path C).

رویداد i: range_i = high−low ≥ θ·ATR21[i−1] (ATR علّی). جهت = sign(close_i−open_i).
کندل j=i+1 (هضم) — سه بازو:
  base   : بدون شرط روی j (پایهٔ P1 با همان زمان‌بندی ورود)
  pause  : range_j ≤ 0.5·range_i  و  close_j درون [low_i, high_i]
  retest : برای شوک صعودی: low_j ≤ close_i − 0.382·range_i  و  close_j > open_i (آینه برای نزولی)
ورود: open کندل j+1 هم‌جهت شوک (سیگنال روی j). SL=k·ATR21[j]، TP=RR·SL.
گیت درفت اختیاری Ld (close[j]−close[j−Ld] هم‌جهت).
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

PIP = 0.10
TFS = ['H6', 'H8', 'H12', 'D1']
MH = {'H6': 20, 'H8': 15, 'H12': 10, 'D1': 5}     # ≈ ۵ روز، ثابت
HERE = os.path.dirname(os.path.abspath(__file__))


def atr_n(h, l, c, p=21):
    n = len(c)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    tr = np.r_[h[0] - l[0], tr]
    a = np.empty(n); a[0] = tr[0]; al = 2 / (p + 1)
    for i in range(1, n):
        a[i] = a[i - 1] + (tr[i] - a[i - 1]) * al
    return np.r_[np.nan, a[:-1]]      # علّی: ATR تا کندل قبل


CACHE = {}
def card(tf):
    if tf not in CACHE:
        d = fd.load_fast('XAUUSD', tf); df = fd.as_dataframe(d)
        assert 'mt5_full' in d['src'], 'E-16 guard'
        df = df.iloc[:len(df) // 2].reset_index(drop=True)
        o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
        CACHE[tf] = dict(df=df, o=o, h=h, l=l, c=c, atr=atr_n(h, l, c), src=d['src'],
                         half_time=int(df['time'].values[-1]))
    return CACHE[tf]


def signals(tf, theta, arm, Ld):
    C = card(tf); o, h, l, c, atr = C['o'], C['h'], C['l'], C['c'], C['atr']; n = len(c)
    rng_ = h - l
    shock = (rng_ >= theta * atr) & ~np.isnan(atr) & (c != o)
    dirn = np.sign(c - o)
    # شیفت به کندل j = i+1
    sh_j = np.r_[False, shock[:-1]]; d_j = np.r_[0.0, dirn[:-1]]
    hi_i = np.r_[np.nan, h[:-1]]; lo_i = np.r_[np.nan, l[:-1]]; op_i = np.r_[np.nan, o[:-1]]
    cl_i = np.r_[np.nan, c[:-1]]; rg_i = np.r_[np.nan, rng_[:-1]]
    if arm == 'base':
        cond = np.ones(n, bool)
    elif arm == 'pause':
        cond = (rng_ <= 0.5 * rg_i) & (c <= hi_i) & (c >= lo_i)
    elif arm == 'retest':
        up = (d_j > 0) & (l <= cl_i - 0.382 * rg_i) & (c > op_i)
        dn = (d_j < 0) & (h >= cl_i + 0.382 * rg_i) & (c < op_i)
        cond = up | dn
    sig = sh_j & cond & ~np.isnan(atr)
    if Ld > 0:
        dr = np.full(n, np.nan); dr[Ld:] = c[Ld:] - c[:n - Ld]     # close[j] − close[j−Ld] (علّی در لحظهٔ سیگنال j)
        sig = sig & ~np.isnan(dr) & (np.sign(dr) == d_j)
    return sig & (d_j > 0), sig & (d_j < 0)


def run(tf, theta, arm, Ld, k, rr):
    C = card(tf); ls, ss = signals(tf, theta, arm, Ld)
    atr_j = np.r_[C['atr'][1:], np.nan]          # ATR شامل کندل j (برای هندسه در لحظهٔ سیگنال)
    sl = np.where(~np.isnan(atr_j), k * atr_j / PIP, 0.0)
    tr = se.simulate_trades(C['df'], ls, ss, sl, sl * rr, 'XAUUSD', max_hold=MH[tf], allow_overlap=False)
    return tr, ls, ss, sl


def stats(tr):
    p = tr['pnl_pip'].values; gw = p[p > 0].sum(); gl = -p[p < 0].sum()
    return dict(n=int(len(p)), wr=round(100 * float((p > 0).mean()), 2), exp=round(float(p.mean()), 2),
                pf=round(float(gw / gl), 3) if gl > 0 else None, net=round(float(p.sum()), 1))


out = dict(grid=[], src={}, half_time={}); n_cfg = 0
for tf in TFS:
    out['src'][tf] = card(tf)['src']; out['half_time'][tf] = card(tf)['half_time']
    for theta in (2.058, 2.618):
        for Ld in (0, 90):
            for arm in ('base', 'pause', 'retest'):
                for k in (1.272, 1.618):
                    for rr in (1.0, 1.618):
                        n_cfg += 1
                        tr, *_ = run(tf, theta, arm, Ld, k, rr)
                        if len(tr) < 25:
                            continue
                        out['grid'].append(dict(tf=tf, theta=theta, Ld=Ld, arm=arm, k=k, rr=rr, **stats(tr)))
G = out['grid']
print('configs=', n_cfg, 'with>=25 trades=', len(G), 'positive exp=', sum(g['exp'] > 0 for g in G))
# مقایسهٔ P1: هر بازو در برابر base با همان (tf,theta,Ld,k,rr)
key = lambda g: (g['tf'], g['theta'], g['Ld'], g['k'], g['rr'])
base = {key(g): g for g in G if g['arm'] == 'base'}
p1 = []
for g in G:
    if g['arm'] == 'base': continue
    b = base.get(key(g))
    if b:
        p1.append(dict(**{k_: g[k_] for k_ in ('tf', 'theta', 'Ld', 'arm', 'k', 'rr', 'n', 'wr', 'pf', 'exp')},
                       base_n=b['n'], base_wr=b['wr'], base_pf=b['pf'], d_wr=round(g['wr'] - b['wr'], 2)))
p1.sort(key=lambda x: -(x['exp'] * math.sqrt(x['n'])))
print('--- top by exp*sqrt(n) (arm vs base) ---')
for r in p1[:15]: print(r)
print('--- best base rows ---')
for g in sorted([g for g in G if g['arm'] == 'base'], key=lambda x: -x['exp'] * math.sqrt(x['n']))[:6]: print(g)
out['p1'] = p1; out['n_configs_total'] = n_cfg
with open(os.path.join(HERE, 's797_recon_results.json'), 'w') as f:
    json.dump(out, f, indent=1, default=str)
print('TOTAL_CONFIGS_TESTED=', n_cfg)
