#!/usr/bin/env python3
"""
Phase 18: SOROS II -- THE DOLLAR FACTOR: XAUUSD vs EURUSD cross-market structure
Both pairs share a USD leg. Questions:
  A) Correlation regime map: rolling 5d corr of M15 returns -- distribution & persistence
  B) Lead-lag: does EURUSD (deep FX liquidity) lead XAUUSD at M15 horizon, or vice versa?
  C) Divergence trade: when EUR says "dollar weak" but gold hasn't moved yet -> does gold catch up?
  D) First-bar-of-day: do the two first-bar edges fire on the SAME days (one dollar effect)
     or independently (two edges)?
"""
import pandas as pd, numpy as np, math

def load(sym):
    df = pd.read_csv(f'data/{sym}_M15.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.set_index('dt')[['open', 'high', 'low', 'close']]

xau = load('XAUUSD')
eur = load('EURUSD')
# align on common timestamps
j = xau.join(eur, lsuffix='_x', rsuffix='_e', how='inner')
print(f"XAU bars={len(xau)}  EUR bars={len(eur)}  common M15 stamps={len(j)}")
rx = np.diff(np.log(j.close_x.values))
re = np.diff(np.log(j.close_e.values))
idx = j.index[1:]

# ---------- A: correlation regime map ----------
print("\n=== A: rolling 5-day (480-bar) correlation of M15 returns ===")
w = 480
s_rx, s_re = pd.Series(rx, index=idx), pd.Series(re, index=idx)
rc = s_rx.rolling(w).corr(s_re).dropna()
qs = rc.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
print("  corr quantiles:", " ".join(f"q{int(q*100)}={v:+.2f}" for q, v in qs.items()))
print(f"  P(corr>0)={float((rc>0).mean()):.3f}   P(corr>0.3)={float((rc>0.3).mean()):.3f}   P(corr<0)={float((rc<0).mean()):.3f}")
# persistence: AC of the regime itself (sampled daily to avoid overlap artifacts)
rcd = rc.resample('1D').last().dropna()
print(f"  regime persistence: corr(today, +1d)={rcd.autocorr(1):+.2f}  (+5d)={rcd.autocorr(5):+.2f}  (+20d)={rcd.autocorr(20):+.2f}")

# ---------- B: lead-lag ----------
print("\n=== B: lead-lag cross-correlation (M15) ===")
for lag in [1, 2, 4, 8]:
    a = np.corrcoef(re[:-lag], rx[lag:])[0, 1]   # EUR leads XAU
    b = np.corrcoef(rx[:-lag], re[lag:])[0, 1]   # XAU leads EUR
    z_a = a*math.sqrt(len(rx)-lag); z_b = b*math.sqrt(len(rx)-lag)
    print(f"  lag={lag:2d} bars: EUR->XAU corr={a:+.4f} (z={z_a:+.1f})   XAU->EUR corr={b:+.4f} (z={z_b:+.1f})")

# ---------- C: divergence -> catch-up ----------
print("\n=== C: 1-hour divergence: EUR moved (dollar signal), XAU flat -> next hour XAU ===")
H = 4  # 4 bars = 1h
eh = pd.Series(re, index=idx).rolling(H).sum()
xh = pd.Series(rx, index=idx).rolling(H).sum()
fwd = pd.Series(rx, index=idx).rolling(H).sum().shift(-H)
se_e, se_x = eh.std(), xh.std()
m_all = eh.notna() & fwd.notna()
for tag, cond in [
    ("EUR up>1sd & XAU flat(<0.25sd)", (eh > se_e) & (xh.abs() < 0.25*se_x)),
    ("EUR dn>1sd & XAU flat(<0.25sd)", (eh < -se_e) & (xh.abs() < 0.25*se_x)),
    ("XAU up>1sd & EUR flat(<0.25sd) -> fwd EUR", (xh > se_x) & (eh.abs() < 0.25*se_e)),
]:
    m = cond & m_all
    if "fwd EUR" in tag:
        f = pd.Series(re, index=idx).rolling(H).sum().shift(-H)[m].dropna().values
    else:
        f = fwd[m].dropna().values
    # de-overlap: keep every H-th signal
    f = f[::H]
    if len(f) < 30: continue
    se = f.std()/math.sqrt(len(f))
    print(f"  {tag}: n={len(f):4d}  E[next 1h]={f.mean()*1e4:+.2f}bp  P(up)={(f>0).mean():.3f}  t={f.mean()/se:+.2f}")

# ---------- D: first-bar edges -- same dollar day or independent? ----------
print("\n=== D: are the two first-bar-of-day edges the same trade? ===")
def first_bars(df):
    d = df.copy(); d['date'] = d.index.date
    fb = d.groupby('date').first()
    return (fb.close - fb.open)
fx = first_bars(xau); fe = first_bars(eur)
both = pd.concat([fx.rename('xau'), fe.rename('eur')], axis=1).dropna()
cc = both.xau.corr(both.eur)
rr = both.xau.rank().corr(both.eur.rank())
agree = (np.sign(both.xau) == np.sign(both.eur)).mean()
print(f"  common days={len(both)}  corr(first-bar pnl)={cc:+.3f}  rank-corr={rr:+.3f}  sign-agreement={agree:.3f}")
# conditional: XAU first-bar edge on days EUR first bar was down (strong dollar open)?
for tag, m in [("EUR first-bar UP  ", both.eur > 0), ("EUR first-bar DOWN", both.eur < 0)]:
    v = both.xau[m].values
    se = v.std()/math.sqrt(len(v))
    print(f"  XAU first-bar | {tag}: n={len(v):4d}  E=${v.mean():+.3f}  t={v.mean()/se:+.2f}  P(up)={(v>0).mean():.3f}")
