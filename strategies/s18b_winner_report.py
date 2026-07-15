"""گزارش نهایی config برنده‌ی استراتژی ۱۸ (ensemble، TP1.0/SL1.5, thr0.58)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from scipy import stats
import lightgbm as lgb
import indicators as ind
import features as feat
from backtest import load_data, run_backtest
import s18_multisignal_ensemble as S

df = load_data(S.DATA)
n_days = df['dt'].dt.normalize().nunique()
atr = ind.atr(df, 14)
X = feat.build_features(df).copy()
logp = np.log(df['close'].values)
X['fracdiff_04'] = S.fracdiff_fixed(pd.Series(logp), d=0.4, thres=1e-3)
X['fracdiff_03'] = S.fracdiff_fixed(pd.Series(logp), d=0.3, thres=1e-3)
sig, stype = S.primary_signals(df)
X['sig_type'] = 0
X.loc[sig, 'sig_type'] = stype[sig]
sig_idx = np.array([i for i in np.where(sig)[0]
                    if i < len(df) - 60 and not np.isnan(atr.values[i])
                    and not X.iloc[i].isna().any()])

tp, sl, hz, thr = 1.0, 1.5, 48, 0.58
be = sl / (tp + sl)
labels = S.triple_barrier(df, sig_idx, atr, hz, tp, sl)
keys = np.array(sorted(labels.keys()))
approved = S.purged_wf(df, X, keys, labels, hz, thr)
entries = np.zeros(len(df), dtype=bool); entries[approved] = True
st, tr = run_backtest(df, entries, None, None, 'long', 0.20, hz, False,
                      sl_series=atr.values * sl, tp_series=atr.values * tp)
nt, wr = st['n_trades'], st['win_rate']
p = S.pvalue(round(wr / 100 * nt), nt, be)
d = df['dt'].dt.normalize().values[tr['entry_bar'].values]
perday = pd.Series(d).value_counts()
print(f"FINAL ensemble TP1.0/SL1.5 thr0.58: n={nt} WR={wr:.2f}% "
      f"exp={st['expectancy']:+.3f}$ PnL={st['total_pnl']:+.0f}$ "
      f"avgW={st['avg_win']:+.2f} avgL={st['avg_loss']:+.2f} p={p:.4f}")
print(f"tpd_cal={nt/n_days:.2f} active_mean={perday.mean():.2f} "
      f"median={perday.median():.0f} max={perday.max()} "
      f"days_with_3plus={(perday>=3).mean()*100:.1f}%")
# نوع سیگنال
tr = tr.reset_index(drop=True)
types = stype[tr['entry_bar'].values]
for t, name in [(0, 'pullback'), (1, 'breakout')]:
    m = types == t
    if m.sum():
        w = (tr.loc[m, 'outcome'] == 'win').mean() * 100
        print(f"  {name}: n={m.sum()} WR={w:.2f}%")
# پایداری 5 بلوک
print("STABILITY (5 blocks):")
for bi, b in enumerate(np.array_split(tr, 5)):
    w = (b['outcome'] == 'win').mean() * 100
    print(f"  block{bi+1}: n={len(b)} WR={w:.2f}% exp={b['pnl'].mean():+.3f}")
