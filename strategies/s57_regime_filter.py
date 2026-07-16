"""
S57 — فیلترِ رژیمِ زندهٔ بازار (efficiency-ratio) → پایداریِ «شرطی» به‌جای «زمانی»
================================================================================
بینشِ L29/L31: مشکل «نیمهٔ اول» نیست، بلکه **رژیمِ کم‌روند** است که در نیمهٔ اول
(۲۰۲۱–۲۰۲۲) متراکم‌تر بود. اگر یک فیلترِ رژیمِ زنده (بدونِ look-ahead) بسازیم که فقط
در رژیمِ پرروند اجازهٔ معامله دهد، دوره‌های بد در **هر دو نیمه** حذف می‌شوند و شکافِ
دو-نیمه باید بسته شود (پایداریِ شرطی).

سنجهٔ رژیم: **Kaufman Efficiency Ratio (ER)** روی close:
    ER = |close[t] - close[t-N]| / Σ|close[i]-close[i-1]|   (i=t-N+1..t)
ER≈1 → روندِ خالص؛ ER≈0 → نوسانِ درجا (رنج). فقط از گذشته (بدونِ look-ahead).

روش:
  - ER با پنجرهٔ N=96 (یک روزِ M15) روی هر دارایی؛ shift(1) برای اطمینان از گذشته.
  - گیتِ رژیم: ورود فقط اگر ER[entry] ≥ er_min.
  - همان threshold=0.72 (بهترین نقطهٔ فرکانس‌دارِ S56) + خروجِ پویا.
  - جاروبِ er_min و گزارشِ دو-نیمه؛ هدف = بستنِ شکافِ نیمه۱/نیمه۲.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
from dynamic_backtest import run_multistep_backtest
import warnings; warnings.filterwarnings('ignore')

SL_M = 1.5; SPREAD_ATR = 0.06
THRESH = 0.72
ER_N = 96
ASSETS = ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s55_proba_cache.npz')
ER_MINS = [0.0, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

Z = np.load(CACHE, allow_pickle=True)
probas = {k: Z[k] for k in Z.files}


def efficiency_ratio(close, n):
    close = pd.Series(close)
    change = (close - close.shift(n)).abs()
    vol = close.diff().abs().rolling(n).sum()
    er = change / (vol + 1e-12)
    return er.shift(1).values          # shift(1): فقط گذشته، بدونِ look-ahead


ASSET_DATA = {}
for a in ASSETS:
    df = load_data(f'data/{a}_M15.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    c = df['close'].values
    atr = ind.atr(df, 14)
    e50 = ind.ema(df['close'], 50).values
    e200 = ind.ema(df['close'], 200).values
    cL = (c > e50) & (e50 > e200) & ~np.isnan(atr.values)
    cS = (c < e50) & (e50 < e200) & ~np.isnan(atr.values)
    am = np.nanmean(atr.values)
    er = efficiency_ratio(c, ER_N)
    ASSET_DATA[a] = dict(df=df, atr=atr, cL=cL, cS=cS,
                         spread=SPREAD_ATR * am, be=0.10 * am, er=er)


def trades_for(a, er_min):
    d = ASSET_DATA[a]; df = d['df']; atr = d['atr']; er = d['er']
    reg = er >= er_min
    frames = []
    for direction, cand in [('long', d['cL']), ('short', d['cS'])]:
        p = probas[f'{a}_{direction}']
        entries = cand & (p >= THRESH) & ~np.isnan(p) & reg
        if entries.sum() == 0: continue
        _s, tr = run_multistep_backtest(df, entries, direction, atr, sl_mult=SL_M,
                                        tp_mults=(0.8, 1.5, 2.5), tp_fracs=(0.34, 0.33, 0.33),
                                        trail_mult=1.5, be_offset=d['be'], spread=d['spread'],
                                        max_hold=200, allow_overlap=False)
        if len(tr) == 0: continue
        tr = tr.copy(); tr['pnl_R'] = tr['r_mult']; tr['asset'] = a
        tr['dt'] = df['dt'].iloc[tr['entry_bar'].values].values
        frames.append(tr[['asset', 'dt', 'pnl_R']])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def metrics(tr):
    if tr is None or len(tr) == 0:
        return None
    n = len(tr); wr = (tr['pnl_R'] > 0).mean() * 100
    gp = tr.loc[tr['pnl_R'] > 0, 'pnl_R'].sum()
    gl = -tr.loc[tr['pnl_R'] < 0, 'pnl_R'].sum()
    pf = gp / gl if gl > 1e-9 else np.inf
    return dict(n=n, wr=wr, pf=pf, exp=tr['pnl_R'].mean(),
                per_day=n / tr['dt'].dt.date.nunique())


print(f"=== S57: فیلترِ رژیم (ER, N={ER_N}) + threshold={THRESH} ===\n", flush=True)
print(f"{'er_min':>6} | {'کل n':>6} {'WR':>5} {'PF':>6} {'t/d':>5} | "
      f"{'نیمه۱PF':>7} {'WR':>5} | {'نیمه۲PF':>7} {'WR':>5} | {'گپ':>5} {'قید':>5}")
print("-" * 80)

best = None
for er_min in ER_MINS:
    frames = [trades_for(a, er_min) for a in ASSETS]
    port = pd.concat([f for f in frames if len(f)], ignore_index=True)
    if len(port) == 0:
        continue
    port = port.sort_values('dt').reset_index(drop=True)
    tmid = port['dt'].min() + (port['dt'].max() - port['dt'].min()) / 2
    mALL = metrics(port); m1 = metrics(port[port['dt'] < tmid]); m2 = metrics(port[port['dt'] >= tmid])
    if not (m1 and m2):
        continue
    gap = m2['pf'] - m1['pf']
    ok = (m1['pf'] > 1.3 and m2['pf'] > 1.3 and m1['wr'] > 60 and m2['wr'] > 60
          and m1['exp'] > 0 and m2['exp'] > 0 and mALL['per_day'] >= 5)
    flag = '✅' if ok else '❌'
    print(f"{er_min:>6.2f} | {mALL['n']:>6} {mALL['wr']:>4.1f}% {mALL['pf']:>6.3f} "
          f"{mALL['per_day']:>5.1f} | {m1['pf']:>7.3f} {m1['wr']:>4.1f}% | "
          f"{m2['pf']:>7.3f} {m2['wr']:>4.1f}% | {gap:>5.2f} {flag:>5}")
    if ok and (best is None or m1['pf'] > best[1]):
        best = (er_min, m1['pf'], mALL, m1, m2)

print()
if best:
    er_min, _, mALL, m1, m2 = best
    print(f"🎯🎯 پیکربندیِ سازگار یافت شد! ER≥{er_min}, threshold={THRESH}")
    print(f"   کل: WR={mALL['wr']:.1f}% PF={mALL['pf']:.3f} معامله/روز={mALL['per_day']:.1f}")
    print(f"   نیمه۱: PF={m1['pf']:.3f} WR={m1['wr']:.1f}% | نیمه۲: PF={m2['pf']:.3f} WR={m2['wr']:.1f}%")
else:
    print("فیلترِ رژیم شکاف را کم کرد اما هنوز همهٔ قیودِ دو-نیمه هم‌زمان برآورده نشد.")
    print("(به روندِ ستونِ «گپ» نگاه کن: آیا ER گپ را می‌بندد؟)")

print("\nتمام.", flush=True)
