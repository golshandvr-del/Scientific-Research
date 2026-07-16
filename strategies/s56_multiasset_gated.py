"""
S56 — سبدِ چند-دارایی + گیتِ threshold (غلیظ‌کردنِ لبه) — تنها راهِ سازگار با L30
================================================================================
L30/S55: تنوع فرکانس می‌دهد نه لبه؛ و خودِ خروجِ پویا لبه نمی‌سازد — «گیتِ ورود»
می‌سازد. پس اینجا گیت را برمی‌گردانیم: threshold بالاتر = فقط باکیفیت‌ترین سیگنال‌ها.
چون ۴ دارایی داریم، حتی با گیتِ سخت هم فرکانسِ کل باید ≥۵ بماند (مزیتِ تنوع).

هدف: نقطه‌ای که PF>1.3 در **هر دو نیمه** + WR>60 + معامله/روز≥۵ (روی سبد).

روش: جاروبِ threshold ∈ {0.62 … 0.74}. برای هر threshold، خروجِ پویا (be_offset
مقیاس‌شده به ATR) روی هر دارایی، ادغامِ سبد، گزارشِ دو-نیمه. از cacheِ S55 استفاده می‌شود.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
from dynamic_backtest import run_multistep_backtest
import warnings; warnings.filterwarnings('ignore')

SL_M = 1.5; SPREAD_ATR = 0.06
ASSETS = ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s55_proba_cache.npz')
THRESHOLDS = [0.62, 0.64, 0.66, 0.68, 0.70, 0.72, 0.74]

assert os.path.exists(CACHE), "ابتدا s55 را اجرا کنید تا cache ساخته شود."
Z = np.load(CACHE, allow_pickle=True)
probas = {k: Z[k] for k in Z.files}

# پیش‌محاسبهٔ داده/کاندید/ATR هر دارایی (یک‌بار)
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
    ASSET_DATA[a] = dict(df=df, atr=atr, cL=cL, cS=cS,
                         spread=SPREAD_ATR * am, be=0.10 * am)


def trades_for(a, thr):
    d = ASSET_DATA[a]; df = d['df']; atr = d['atr']
    frames = []
    for direction, cand in [('long', d['cL']), ('short', d['cS'])]:
        p = probas[f'{a}_{direction}']
        entries = cand & (p >= thr) & ~np.isnan(p)
        if entries.sum() == 0: continue
        _s, tr = run_multistep_backtest(df, entries, direction, atr, sl_mult=SL_M,
                                        tp_mults=(0.8, 1.5, 2.5), tp_fracs=(0.34, 0.33, 0.33),
                                        trail_mult=1.5, be_offset=d['be'], spread=d['spread'],
                                        max_hold=200, allow_overlap=False)
        if len(tr) == 0: continue
        tr = tr.copy()
        tr['pnl_R'] = tr['r_mult']
        tr['asset'] = a
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
    exp = tr['pnl_R'].mean()
    days = tr['dt'].dt.date.nunique()
    per_day = n / days if days else 0
    return dict(n=n, wr=wr, pf=pf, exp=exp, per_day=per_day)


print("=== S56: جاروبِ threshold روی سبدِ چند-دارایی ===\n", flush=True)
print(f"{'thr':>5} | {'کل: n':>6} {'WR':>5} {'PF':>5} {'t/d':>5} | "
      f"{'نیمه۱ PF':>8} {'WR':>5} | {'نیمه۲ PF':>8} {'WR':>5} | {'همه‌قید':>7}")
print("-" * 78)

best = None
for thr in THRESHOLDS:
    frames = [trades_for(a, thr) for a in ASSETS]
    port = pd.concat([f for f in frames if len(f)], ignore_index=True)
    if len(port) == 0:
        continue
    port = port.sort_values('dt').reset_index(drop=True)
    tmid = port['dt'].min() + (port['dt'].max() - port['dt'].min()) / 2
    mALL = metrics(port)
    m1 = metrics(port[port['dt'] < tmid])
    m2 = metrics(port[port['dt'] >= tmid])
    if not (m1 and m2):
        continue
    ok = (m1['pf'] > 1.3 and m2['pf'] > 1.3 and m1['wr'] > 60 and m2['wr'] > 60
          and m1['exp'] > 0 and m2['exp'] > 0 and mALL['per_day'] >= 5)
    flag = '✅' if ok else '❌'
    print(f"{thr:>5.2f} | {mALL['n']:>6} {mALL['wr']:>4.1f}% {mALL['pf']:>5.3f} "
          f"{mALL['per_day']:>5.1f} | {m1['pf']:>8.3f} {m1['wr']:>4.1f}% | "
          f"{m2['pf']:>8.3f} {m2['wr']:>4.1f}% | {flag:>7}")
    if ok and (best is None or mALL['pf'] > best[1]):
        best = (thr, mALL['pf'], mALL, m1, m2)

print()
if best:
    thr, _, mALL, m1, m2 = best
    print(f"🎯 پیکربندیِ سازگار یافت شد: threshold={thr}")
    print(f"   کل: WR={mALL['wr']:.1f}% PF={mALL['pf']:.3f} exp={mALL['exp']:+.3f}R "
          f"معامله/روز={mALL['per_day']:.1f}")
    print(f"   نیمه۱: PF={m1['pf']:.3f} WR={m1['wr']:.1f}% | "
          f"نیمه۲: PF={m2['pf']:.3f} WR={m2['wr']:.1f}%")
else:
    print("❌ هیچ threshold همهٔ قیود را در هر دو نیمه هم‌زمان برآورده نکرد.")
    print("   → غلیظ‌کردنِ لبه با threshold کافی نیست؛ لبه در نیمهٔ اول ذاتاً ضعیف است (L29/L30).")

print("\nتمام.", flush=True)
