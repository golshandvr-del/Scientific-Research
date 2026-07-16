"""
S58 — سبدِ ER-فیلترشدهٔ باکیفیت + معیارِ «اکشن/روز» (تعریفِ User Note از «معامله»)
================================================================================
ترکیبِ همهٔ درس‌های L21–L32:
  - سیگنالِ باکیفیت: threshold=0.72 + ER≥er_min (پایداریِ شرطیِ S57)
  - خروجِ چند-پله‌ای: هر ورود → چند «اکشن» (ورود + بستن‌های جزئی + خروجِ نهایی)
  - تنوعِ ۴-دارایی: فرکانسِ اکشنِ کافی حتی با گیتِ سخت

فرضیه: S57 نشان داد ER≥0.20 گپِ رژیمی را می‌بندد (PF~۱.۲ پایدار) اما فقط ۲.۹
**ورود**/روز می‌دهد. اما طبق تعریفِ User Note، هر ورود چند «اکشن»ی است که کاربر در
سایت اجرا می‌کند. اگر اکشن/روز ≥۵ شود و PF در هر دو نیمه ≥۱.۳، **همهٔ قیود برآورده‌اند**.

اینجا معیارِ فرکانس = **اکشن/روزِ تقویمی** (ستونِ n_actions موتور، دقیقاً مثلِ S49).
جاروبِ er_min برای یافتنِ نقطه‌ای که هم PF دو-نیمه ≥۱.۳ و هم اکشن/روز ≥۵.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
from dynamic_backtest import run_multistep_backtest
import warnings; warnings.filterwarnings('ignore')

SL_M = 1.5; SPREAD_ATR = 0.06
THRESH = 0.72; ER_N = 96
ASSETS = ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s55_proba_cache.npz')
ER_MINS = [0.15, 0.18, 0.20, 0.22, 0.25]

Z = np.load(CACHE, allow_pickle=True)
probas = {k: Z[k] for k in Z.files}


def efficiency_ratio(close, n):
    s = pd.Series(close)
    change = (s - s.shift(n)).abs()
    vol = s.diff().abs().rolling(n).sum()
    return (change / (vol + 1e-12)).shift(1).values


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
    ASSET_DATA[a] = dict(df=df, atr=atr, cL=cL, cS=cS, spread=SPREAD_ATR * am,
                         be=0.10 * am, er=efficiency_ratio(c, ER_N))


def trades_for(a, er_min):
    d = ASSET_DATA[a]; df = d['df']; atr = d['atr']
    reg = d['er'] >= er_min
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
        frames.append(tr[['asset', 'dt', 'pnl_R', 'n_actions']])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def metrics(tr, span_days):
    if tr is None or len(tr) == 0:
        return None
    n = len(tr); wr = (tr['pnl_R'] > 0).mean() * 100
    gp = tr.loc[tr['pnl_R'] > 0, 'pnl_R'].sum()
    gl = -tr.loc[tr['pnl_R'] < 0, 'pnl_R'].sum()
    pf = gp / gl if gl > 1e-9 else np.inf
    entries_per_day = n / tr['dt'].dt.date.nunique()
    # اکشن/روزِ تقویمی (معیارِ User Note، مثلِ S49): کلِ اکشن‌ها / کلِ روزهای تقویمی
    actions_per_cal = tr['n_actions'].sum() / span_days if span_days else 0
    return dict(n=n, wr=wr, pf=pf, exp=tr['pnl_R'].mean(),
                entries_per_day=entries_per_day, actions_per_cal=actions_per_cal)


print(f"=== S58: سبدِ ER-فیلترشده + معیارِ «اکشن/روز» (threshold={THRESH}) ===\n", flush=True)
print(f"{'er_min':>6} | {'n':>5} {'WR':>5} {'PF':>6} {'ورود/د':>6} {'اکشن/د':>7} | "
      f"{'ن۱PF':>6} {'ن۱WR':>5} {'ن۱اکشن':>7} | {'ن۲PF':>6} {'ن۲WR':>5} | {'قید':>5}")
print("-" * 92)

best = None
for er_min in ER_MINS:
    frames = [trades_for(a, er_min) for a in ASSETS]
    port = pd.concat([f for f in frames if len(f)], ignore_index=True).sort_values('dt').reset_index(drop=True)
    if len(port) == 0:
        continue
    t0, t1 = port['dt'].min(), port['dt'].max()
    tmid = t0 + (t1 - t0) / 2
    span_all = max(1, (t1 - t0).days)
    span_h = max(1, (tmid - t0).days)
    p1 = port[port['dt'] < tmid]; p2 = port[port['dt'] >= tmid]
    mALL = metrics(port, span_all)
    m1 = metrics(p1, span_h)
    m2 = metrics(p2, max(1, (t1 - tmid).days))
    if not (m1 and m2):
        continue
    # قید بر اساسِ «اکشن/روز» (تعریفِ User Note) در هر دو نیمه
    ok = (m1['pf'] > 1.3 and m2['pf'] > 1.3 and m1['wr'] > 60 and m2['wr'] > 60
          and m1['exp'] > 0 and m2['exp'] > 0
          and m1['actions_per_cal'] >= 5 and m2['actions_per_cal'] >= 5)
    flag = '✅' if ok else '❌'
    print(f"{er_min:>6.2f} | {mALL['n']:>5} {mALL['wr']:>4.1f}% {mALL['pf']:>6.3f} "
          f"{mALL['entries_per_day']:>6.2f} {mALL['actions_per_cal']:>7.2f} | "
          f"{m1['pf']:>6.3f} {m1['wr']:>4.1f}% {m1['actions_per_cal']:>7.2f} | "
          f"{m2['pf']:>6.3f} {m2['wr']:>4.1f}% | {flag:>5}")
    if ok and (best is None or m1['pf'] > best[1]):
        best = (er_min, m1['pf'], mALL, m1, m2)

print()
if best:
    er_min, _, mALL, m1, m2 = best
    print("🎯🎯🎯 همهٔ قیود در هر دو نیمه برآورده شد!")
    print(f"   ER≥{er_min}, threshold={THRESH}")
    print(f"   کل: WR={mALL['wr']:.1f}% PF={mALL['pf']:.3f} اکشن/روز={mALL['actions_per_cal']:.2f}")
    print(f"   نیمه۱: PF={m1['pf']:.3f} WR={m1['wr']:.1f}% اکشن/روز={m1['actions_per_cal']:.2f}")
    print(f"   نیمه۲: PF={m2['pf']:.3f} WR={m2['wr']:.1f}% اکشن/روز={m2['actions_per_cal']:.2f}")
else:
    print("با معیارِ اکشن/روز هم قیودِ دو-نیمه هم‌زمان برآورده نشد (به ستونِ ن۱PF نگاه کن).")

print("\nتمام.", flush=True)
