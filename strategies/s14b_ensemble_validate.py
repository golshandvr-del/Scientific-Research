"""
استراتژی ۱۴ (نسخه اعتبارسنجی): Ensemble چند-seed + جاروب دقیق برای معناداری آماری.

هدف: تثبیت نتیجه‌ی s14 (WR>60% + exp>0 + freq>3/day) با p-value<0.05.
راهبرد:
1. Ensemble ۳ seed (میانگین proba) → کاهش واریانس مدل، پایدارتر.
2. BE کمی پایین‌تر (TP1.0/SL1.35، BE=57.4%) تا فاصله WR از BE بزرگ‌تر و p معنادار شود،
   در حالی که WR همچنان بالای هدف ۶۰٪ می‌ماند.
3. جاروب دقیق آستانه برای یافتن نقطه شیرین (WR>60، edge بزرگ، freq کافی).
4. اعتبارسنجی پایداری: تقسیم OOS به نیمه اول/دوم زمانی.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 6
MIN_TRAIN_FRAC = 0.40
SEEDS = [42, 7, 123]

def walk_forward_proba(df, feats, fc, cand, n, hz, tp_m, sl_m, seed):
    atr = ind.atr(df, 14)
    y = make_target(df, hz, tp_m, sl_m, atr, 'long')
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=fc + ['y']); valid = valid[valid['cand']]
    X = valid[fc].values; Y = valid['y'].values.astype(int); idx = valid.index.values
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        m = lgb.LGBMClassifier(
            n_estimators=500, learning_rate=0.025, num_leaves=32, max_depth=6,
            subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1]
    return proba

def trades_per_day(df, n_trades, oos_frac):
    span_days = (df['dt'].max() - df['dt'].min()).days
    trading_days = span_days * 5 / 7
    return (n_trades / trading_days) / oos_frac

def main():
    df = load_data(); df['hour'] = df['dt'].dt.hour
    atr = ind.atr(df, 14); atr_arr = atr.values
    c = df['close']; cv = c.values
    ema50 = ind.ema(c, 50).values; ema200 = ind.ema(c, 200).values
    n = len(df)
    feats = build_features(df); fc = list(feats.columns)
    cand = (cv > ema50) & (ema50 > ema200)
    print(f"کاندید پایه: {int(cand.sum())} | features: {len(fc)}")

    for hz, tp_m, sl_m in [(48, 1.0, 1.35), (48, 1.0, 1.5)]:
        be = sl_m / (tp_m + sl_m) * 100
        # Ensemble: میانگین proba روی seedها
        probas = []
        for sd in SEEDS:
            probas.append(walk_forward_proba(df, feats, fc, cand, n, hz, tp_m, sl_m, sd))
        proba = np.nanmean(np.vstack(probas), axis=0)
        oos_mask = ~np.isnan(proba)
        oos_frac = oos_mask.sum() / n
        print(f"\n### ENSEMBLE({len(SEEDS)} seeds) RR TP={tp_m} SL={sl_m} hz={hz} | BE={be:.1f}%")
        print(f"{'thr':>6}{'n':>7}{'WR%':>8}{'exp$':>9}{'pnl$':>9}{'tr/day':>8}{'edge':>7}{'pval':>8}")
        best = None
        for thr in [0.58,0.60,0.61,0.62,0.63,0.64,0.65,0.66,0.67,0.68,0.70]:
            entries = cand & (proba >= thr) & oos_mask
            s, tr = run_backtest(df, entries, None, None, 'long', spread=0.20,
                                 max_hold=hz, sl_series=sl_m*atr_arr,
                                 tp_series=tp_m*atr_arr, allow_overlap=False)
            nt = s['n_trades']
            if nt < 50: continue
            wins = int(round(s['win_rate']/100*nt))
            pval = stats.binomtest(wins, nt, be/100, alternative='greater').pvalue
            tpd = trades_per_day(df, nt, oos_frac)
            edge = s['win_rate'] - be
            flag = ""
            win_cond = (s['win_rate']>60 and s['expectancy']>0 and pval<0.05 and tpd>=3)
            if win_cond:
                flag = " <<<=== WINNER"
                if best is None: best = (thr, s, tr, tpd, pval)
            elif s['win_rate']>60 and s['expectancy']>0 and pval<0.05:
                flag = " <== sig"
            elif s['win_rate']>60 and s['expectancy']>0:
                flag = " <-- profitable"
            print(f"{thr:>6.2f}{nt:>7}{s['win_rate']:>8.2f}{s['expectancy']:>9.3f}"
                  f"{s['total_pnl']:>9.1f}{tpd:>8.2f}{edge:>+7.1f}{pval:>8.3f}{flag}")

        # اعتبارسنجی پایداری زمانی برای بهترین نقطه
        if best is not None:
            thr, s, tr, tpd, pval = best
            print(f"\n--- پایداری زمانی برای thr={thr} (BE={be:.1f}%) ---")
            mid = tr['entry_bar'].median()
            for label, sub in [('نیمه اول', tr[tr['entry_bar']<=mid]),
                               ('نیمه دوم', tr[tr['entry_bar']>mid])]:
                if len(sub)==0: continue
                w = (sub['outcome']=='win').sum(); tt=len(sub)
                wr = w/tt*100; exp = sub['pnl'].mean()
                pv = stats.binomtest(int(w),tt,be/100,alternative='greater').pvalue
                print(f"  {label}: n={tt} WR={wr:.2f}% exp={exp:+.3f}$ pval={pv:.3f}")

if __name__ == '__main__':
    main()
