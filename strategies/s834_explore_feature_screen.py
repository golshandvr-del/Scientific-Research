# -*- coding: utf-8 -*-
"""
S834 — کاوشِ ۲: غربالِ چندویژگیِ قلمروهای بکر — فقط ۶۰٪ اکتشاف — H1/H3/H8
=========================================================================
همه‌ی ویژگی‌ها در سرشماریِ نتایج (results/S*_rqs2_*.md) صفر استفاده دارند:
  FORCE : Force Index (Elder) = EMA13(vol×Δc)، z نسبت به sd غلتانِ 144 ⇒ عبورِ تازه از ±k
  VR    : Variance Ratio (Lo–MacKinlay) VR(q=8, win=89) عبورِ تازه بالای k ⇒ جهت = علامتِ بازدهِ 8 کندلی
  VOLRAT: نسبتِ نوسانِ close-to-close به Parkinson (win=34) — CC≫P یعنی جهش‌های بین‌کندلی
          ⇒ عبورِ تازه از k، جهت = علامتِ بازدهِ 8 کندلی
  AGE   : عبورِ تازه‌ی close از EMA55 پس از ≥k کندل در سمتِ مقابل (سنِ روندِ قبلی) ⇒ جهتِ عبور
سنجه: INFO-lift نسبت به نالِ جای‌گشتیِ جهت با همان هندسه (K=80)، pw=lift·√n،
      و سه رژیمِ واقعی R1(<2013) R2(2013-15) R3(2016-20). fade هم چاپ می‌شود (پادتقارن).
هندسه‌ی ساده: SL=2×ATR34، TP=1.3×SL، hold=21، بدون trail/BE.
"""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

K_NULL = 80
SEED = 834002
SLM, RR, HOLD = 2.0, 1.3, 21
R1_END = 1356998400; R2_END = 1451606400


def pf_of(p):
    w = p[p > 0].sum(); lo_ = -p[p < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf


def ema(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().values


def fresh_cross(v, k):
    prev = np.concatenate([[np.nan], v[:-1]])
    return (v > k) & ~(prev > k)


def info_null(df, sig_bars, slp, tpp, rng):
    wrs = []
    for _ in range(K_NULL):
        dirs = rng.integers(0, 2, size=len(sig_bars)).astype(bool)
        lm = np.zeros(len(df), bool); lm[sig_bars[dirs]] = True
        sm = np.zeros(len(df), bool); sm[sig_bars[~dirs]] = True
        t = se.simulate_trades(df, lm, sm, sl_pip=slp, tp_pip=tpp, asset='XAUUSD',
                               max_hold=HOLD, allow_overlap=False)
        if len(t):
            wrs.append((t['pnl_pip'].values > 0).mean() * 100)
    return float(np.mean(wrs)), float(np.std(wrs))


for TF in ('H1', 'H3', 'H8'):
    d = fd.load_fast('XAUUSD', TF)
    assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
    df_full = fd.as_dataframe(d)
    split = int(len(df_full) * 0.6)
    df = df_full.iloc[:split].reset_index(drop=True)
    t = df['time'].values.astype(np.int64)
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64); l = df['low'].values.astype(np.float64)
    v = df['volume'].values.astype(np.float64)
    n = len(df)
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = ema(tr, 2 * 34 - 1)
    atr_pip = atr / se.ASSETS['XAUUSD']['pip']
    slp = np.clip(atr_pip * SLM, 8, 5000); tpp = slp * RR
    r1 = np.diff(np.log(c), prepend=np.log(c[0]))
    ret8 = np.full(n, np.nan); ret8[8:] = c[8:] - c[:-8]
    WARM = 400

    feats, lbls = {}, {}
    # FORCE
    fi = ema(v * (c - prev_c), 13)
    sd = pd.Series(fi).rolling(144).std().values
    fz = fi / np.where(sd > 0, sd, np.nan)
    feats['FORCE'] = [(fresh_cross(fz, k), np.sign(fz)) for k in (2.0, 2.618)] + \
                     [(fresh_cross(-fz, k), np.sign(fz)) for k in (2.0, 2.618)]
    lbls['FORCE'] = ['+2.0', '+2.618', '-2.0', '-2.618']
    # VR
    q, win = 8, 89
    rq = pd.Series(np.log(c)).diff(q).values
    var1 = pd.Series(r1).rolling(win).var().values
    varq = pd.Series(rq).rolling(win).var().values
    vr = varq / (q * np.where(var1 > 0, var1, np.nan))
    feats['VR'] = [(fresh_cross(vr, k), np.sign(ret8)) for k in (1.2, 1.4, 1.6)]
    lbls['VR'] = ['1.2', '1.4', '1.6']
    # VOLRAT
    cc = pd.Series(r1).rolling(34).std().values
    park = np.sqrt(pd.Series(np.log(h / l) ** 2).rolling(34).mean().values / (4 * np.log(2)))
    volrat = cc / np.where(park > 0, park, np.nan)
    feats['VOLRAT'] = [(fresh_cross(volrat, k), np.sign(ret8)) for k in (1.1, 1.25, 1.4)]
    lbls['VOLRAT'] = ['1.1', '1.25', '1.4']
    # AGE
    e55 = ema(c, 55)
    above = c > e55
    age = np.zeros(n, int)
    for i in range(1, n):
        age[i] = age[i-1] + 1 if above[i] == above[i-1] else 0
    prev_age = np.concatenate([[0], age[:-1]])
    flip = np.concatenate([[False], above[1:] != above[:-1]])
    feats['AGE'] = [(flip & (prev_age >= k), np.where(above, 1.0, -1.0)) for k in (21, 55, 89)]
    lbls['AGE'] = ['21', '55', '89']

    print(f'\n################ TF={TF} explore bars={n:,} src={d["src"]} ################', flush=True)
    rng = np.random.default_rng(SEED + ord(TF[1]))
    for fname, cells in feats.items():
        for (x, dirsign), lbl in zip(cells, lbls[fname]):
            x = x & np.isfinite(dirsign) & (dirsign != 0); x[:WARM] = False
            nm = nsd = None
            for mode in ('follow', 'fade'):
                sgn = dirsign if mode == 'follow' else -dirsign
                ls = x & (sgn > 0); ss = x & (sgn < 0)
                tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp, asset='XAUUSD',
                                         max_hold=HOLD, allow_overlap=False)
                if len(tdf) < 60:
                    print(f'  {fname:6s} k={lbl:6s}: n={len(tdf)} — کم، رد', flush=True)
                    break
                pnl = tdf['pnl_pip'].values; eb = tdf['entry_bar'].values
                sb = tdf['signal_bar'].values.astype(int)
                wr = (pnl > 0).mean() * 100
                if nm is None:
                    nm, nsd = info_null(df, sb, slp, tpp, rng)
                lift = wr - nm; z = lift / nsd if nsd > 0 else 0; pw = lift * np.sqrt(len(pnl))
                te = t[eb]
                def wr_of(m):
                    return (pnl[m] > 0).mean() * 100 - nm if m.sum() >= 15 else np.nan
                l1, l2, l3 = wr_of(te < R1_END), wr_of((te >= R1_END) & (te < R2_END)), wr_of(te >= R2_END)
                flag = ' <<<' if (lift >= 4 and z >= 2 and np.nanmin([l1, l2, l3]) > 0) else ''
                print(f'  {fname:6s} k={lbl:6s} {mode:6s}: n={len(pnl):5,} WR={wr:5.2f}% null={nm:5.2f}%±{nsd:.2f} '
                      f'INFOlift={lift:+6.2f}pp z={z:+4.1f} pw={pw:5.0f} PF={pf_of(pnl):.3f} '
                      f'exp={pnl.mean():+6.2f} [R1={l1:+5.1f} R2={l2:+5.1f} R3={l3:+5.1f}]{flag}', flush=True)

print('\n[S834 explore-2 complete]', flush=True)
