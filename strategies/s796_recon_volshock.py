# -*- coding: utf-8 -*-
"""
S796 recon — Volume Shock Fade × Drift-Aligned (شوک حجم) روی XAUUSD
فقط نیمهٔ اول هر کارت (Path C). هیچ عددی از نیمهٔ دوم در این فایل تولید نمی‌شود.

بازسازی نشست قبل (فایل اولیه با بازنشانی سندباکس گم شد؛ همان منطق، همان شبکه).
مرحله A: شبکهٔ 5TF × 3K × 2mode × 3Ld × 2ksl  (≤180 پیکربندی)
مرحله B: استخر {H3,H6,H8,H12} برای حالت fade×drift با نول سریع
مرحله C: حساسیت اطراف نامزد
"""
import sys, os, json, math, bisect
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

PIP = 0.10
TFS = ['H3', 'H6', 'H8', 'H12', 'D1']
MH = {'H3': 24, 'H6': 16, 'H8': 13, 'H12': 10, 'D1': 8}
HERE = os.path.dirname(os.path.abspath(__file__))


def atr89(h, l, c):
    n = len(c)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    tr = np.r_[h[0] - l[0], tr]
    a = np.empty(n); a[0] = tr[0]; al = 2 / 90
    for i in range(1, n):
        a[i] = a[i - 1] + (tr[i] - a[i - 1]) * al
    return np.r_[np.nan, a[:-1]]          # علّی: شیفت ۱ کندل


def cmed(v, w=89):
    """میانهٔ علّی پنجرهٔ w (فقط کندل‌های < i)."""
    n = len(v); out = np.full(n, np.nan); buf = []; q = deque()
    for i in range(n):
        if len(q) == w:
            old = q.popleft(); buf.pop(bisect.bisect_left(buf, old))
        if buf:
            m = len(buf); out[i] = buf[m // 2] if m % 2 else 0.5 * (buf[m // 2 - 1] + buf[m // 2])
        bisect.insort(buf, v[i]); q.append(v[i])
    return out


CACHE = {}
def card(tf):
    if tf not in CACHE:
        d = fd.load_fast('XAUUSD', tf); df = fd.as_dataframe(d)
        assert 'mt5_full' in d['src'], 'E-16 guard'
        half = len(df) // 2
        df = df.iloc[:half].reset_index(drop=True)
        h = df['high'].values; l = df['low'].values; c = df['close'].values
        v = df['volume'].values.astype(float)
        CACHE[tf] = dict(df=df, atr=atr89(h, l, c), vmed=cmed(v), v=v, c=c,
                         src=d['src'], half_time=int(df['time'].values[-1]))
    return CACHE[tf]


def signals(tf, K, mode, Ld):
    C = card(tf); c = C['c']; n = len(c)
    relv = C['v'] / C['vmed']; r = np.r_[0.0, np.diff(c)]
    sig = (relv >= K) & ~np.isnan(C['vmed']) & ~np.isnan(C['atr']) & (r != 0)
    dirn = np.sign(r)
    if mode == 'fade':
        dirn = -dirn
    if Ld > 0:
        dr = np.full(n, np.nan); dr[Ld:] = c[Ld - 1:-1] - c[:n - Ld]   # درفت علّی تا i-1
        sig = sig & ~np.isnan(dr) & (np.sign(dr) == dirn)
    return sig & (dirn > 0), sig & (dirn < 0)


def run(tf, K, mode, Ld, ksl, rr=1.0):
    C = card(tf); ls, ss = signals(tf, K, mode, Ld)
    sl = np.where(~np.isnan(C['atr']), ksl * C['atr'] / PIP, 0.0)
    return se.simulate_trades(C['df'], ls, ss, sl, sl * rr, 'XAUUSD', max_hold=MH[tf], allow_overlap=False), ls, ss, sl


def stats(tr):
    p = tr['pnl_pip'].values
    gw = p[p > 0].sum(); gl = -p[p < 0].sum()
    return dict(n=int(len(p)), wr=round(100 * (p > 0).mean(), 2), exp=round(float(p.mean()), 2),
                pf=round(float(gw / gl), 3) if gl > 0 else None, net=round(float(p.sum()), 1))


out = dict(stage_A=[], stage_B=[], stage_C=[], src={}, half_time={})
n_configs = 0
# ---------- A: شبکه ----------
for tf in TFS:
    out['src'][tf] = card(tf)['src']; out['half_time'][tf] = card(tf)['half_time']
    for K in (1.618, 2.058, 2.618):
        for mode in ('cont', 'fade'):
            for Ld in (0, 90, 233):
                for ksl in (1.618, 2.618):
                    n_configs += 1
                    tr, *_ = run(tf, K, mode, Ld, ksl)
                    if len(tr) < 30:
                        continue
                    out['stage_A'].append(dict(tf=tf, K=K, mode=mode, Ld=Ld, ksl=ksl, **stats(tr)))
A = sorted(out['stage_A'], key=lambda x: -x['exp'] * math.sqrt(x['n']))
print('A: configs=', n_configs, 'with>=30 trades=', len(A), 'positive=', sum(r['exp'] > 0 for r in A))
for r in A[:10]:
    print('  ', r)

# ---------- B: استخر fade×drift با نول سریع (10 قرعه/کارت) ----------
rng = np.random.default_rng(796)
for K in (2.058, 2.618):
    for Ld in (90, 233):
        tn = tw = nn_ = nw = 0; net = 0.0; parts = {}
        for tf in ('H3', 'H6', 'H8', 'H12'):
            n_configs += 0  # استخر = ترکیب اعضای قبلاً شمرده‌شده
            tr, ls, ss, sl = run(tf, K, 'fade', Ld, 2.618)
            if len(tr) == 0:
                continue
            C = card(tf); df = C['df']; n = len(df)
            tn += len(tr); tw += int((tr['pnl_pip'] > 0).sum()); net += tr['pnl_pip'].sum()
            nL, nS = int(ls.sum()), int(ss.sum())
            valid = np.where(~np.isnan(C['atr']) & ~np.isnan(C['vmed']))[0]
            for _ in range(10):
                idx = rng.choice(valid, nL + nS, replace=False)
                l2 = np.zeros(n, bool); s2 = np.zeros(n, bool); l2[idx[:nL]] = True; s2[idx[nL:]] = True
                t2 = se.simulate_trades(df, l2, s2, sl, sl, 'XAUUSD', max_hold=MH[tf], allow_overlap=False)
                nn_ += len(t2); nw += int((t2['pnl_pip'] > 0).sum())
            parts[tf] = stats(tr)
        wr = 100 * tw / tn; nu = 100 * nw / nn_; lift = wr - nu; z = lift / (50 / math.sqrt(tn))
        rec = dict(K=K, Ld=Ld, ksl=2.618, n=tn, wr=round(wr, 2), null=round(nu, 2), lift=round(lift, 2),
                   z_proxy=round(z, 2), net=round(net, 0), members=parts)
        out['stage_B'].append(rec); n_configs += 1
        print('B:', json.dumps(rec, default=str)[:300])

# ---------- C: حساسیت اطراف K=2.618 Ld=90 ----------
for K in (2.4, 2.618, 2.8):
    for Ld in (75, 90, 110):
        for ksl in (2.058, 2.618, 3.33):
            pn = []
            for tf in ('H3', 'H6', 'H8', 'H12'):
                tr, *_ = run(tf, K, 'fade', Ld, ksl)
                if len(tr):
                    pn.append(tr['pnl_pip'].values)
            p = np.concatenate(pn); gw = p[p > 0].sum(); gl = -p[p < 0].sum()
            rec = dict(K=K, Ld=Ld, ksl=ksl, n=int(len(p)), wr=round(100 * (p > 0).mean(), 2),
                       pf=round(float(gw / gl), 3), net=round(float(p.sum()), 0))
            out['stage_C'].append(rec); n_configs += 1
            print('C:', rec)

out['n_configs_total'] = n_configs
with open(os.path.join(HERE, 's796_recon_results.json'), 'w') as f:
    json.dump(out, f, indent=1, default=str)
print('TOTAL_CONFIGS_TESTED=', n_configs)
