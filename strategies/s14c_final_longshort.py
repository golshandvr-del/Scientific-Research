"""
استراتژی ۱۴ (نسخه نهایی): VWAP-Regime Selective ML — Long+Short متقارن.

هدف: تثبیت WR>60% + exp>0 + freq>=3/day با p-value<0.05 از طریق افزایش n
با افزودن سمت SHORT متقارن (روند نزولی close<ema50<ema200) به سمت LONG.

- Ensemble ۳ seed برای هر دو جهت.
- RR=TP1.0/SL1.5 (BE=60%) — منطبق بر بهترین نتیجه s14b.
- ادغام معاملات long+short، آزمون معناداری روی مجموع (n بزرگ‌تر → p معنادارتر اگر edge واقعی).
- اعتبارسنجی پایداری زمانی (نیمه اول/دوم) + گزارش معامله/روز.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 6; MIN_TRAIN_FRAC = 0.40; SEEDS = [42, 7, 123]

def wf_proba(df, feats, fc, cand, n, hz, tp_m, sl_m, direction, seed):
    atr = ind.atr(df, 14)
    y = make_target(df, hz, tp_m, sl_m, atr, direction)
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=fc + ['y']); valid = valid[valid['cand']]
    X = valid[fc].values; Y = valid['y'].values.astype(int); idx = valid.index.values
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k*fold; te_end = tr_end+fold if k<N_FOLDS-1 else N
        m = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.025, num_leaves=32,
            max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:,1]
    return proba

def ens_proba(df, feats, fc, cand, n, hz, tp_m, sl_m, direction):
    ps = [wf_proba(df, feats, fc, cand, n, hz, tp_m, sl_m, direction, sd) for sd in SEEDS]
    return np.nanmean(np.vstack(ps), axis=0)

def main():
    df = load_data(); df['hour'] = df['dt'].dt.hour
    atr = ind.atr(df, 14); atr_arr = atr.values
    c = df['close']; cv = c.values
    ema50 = ind.ema(c, 50).values; ema200 = ind.ema(c, 200).values
    n = len(df); feats = build_features(df); fc = list(feats.columns)

    cand_long  = (cv > ema50) & (ema50 > ema200)
    cand_short = (cv < ema50) & (ema50 < ema200)
    print(f"کاندید long(uptrend)={int(cand_long.sum())} | short(downtrend)={int(cand_short.sum())}")

    hz, tp_m, sl_m = 48, 1.0, 1.5
    be = sl_m/(tp_m+sl_m)*100
    pL = ens_proba(df, feats, fc, cand_long,  n, hz, tp_m, sl_m, 'long')
    pS = ens_proba(df, feats, fc, cand_short, n, hz, tp_m, sl_m, 'short')
    oosL = ~np.isnan(pL); oosS = ~np.isnan(pS)
    oos_frac = (oosL | oosS).sum() / n
    span_days = (df['dt'].max()-df['dt'].min()).days; trading_days = span_days*5/7

    print(f"\n### Long+Short ENSEMBLE | RR TP={tp_m} SL={sl_m} hz={hz} | BE={be:.1f}%")
    print(f"{'thr':>6}{'n':>7}{'WR%':>8}{'exp$':>9}{'pnl$':>9}{'tr/day':>8}{'edge':>7}{'pval':>8}")
    for thr in [0.62,0.64,0.65,0.66,0.67,0.68,0.70]:
        eL = cand_long  & (pL>=thr) & oosL
        eS = cand_short & (pS>=thr) & oosS
        sL, trL = run_backtest(df, eL, None, None, 'long', spread=0.20, max_hold=hz,
                               sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr, allow_overlap=False)
        sS, trS = run_backtest(df, eS, None, None, 'short', spread=0.20, max_hold=hz,
                               sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr, allow_overlap=False)
        tr = pd.concat([trL, trS], ignore_index=True)
        nt = len(tr)
        if nt < 50: continue
        wins = (tr['outcome']=='win').sum()
        wr = wins/nt*100; exp = tr['pnl'].mean(); pnl = tr['pnl'].sum()
        pval = stats.binomtest(int(wins), nt, be/100, alternative='greater').pvalue
        tpd = (nt/trading_days)/oos_frac
        edge = wr - be
        flag = ""
        if wr>60 and exp>0 and pval<0.05 and tpd>=3:
            flag = " <<<=== WINNER"
        elif wr>60 and exp>0 and pval<0.05:
            flag = " <== sig"
        elif wr>60 and exp>0:
            flag = " <-- profitable"
        print(f"{thr:>6.2f}{nt:>7}{wr:>8.2f}{exp:>9.3f}{pnl:>9.1f}{tpd:>8.2f}{edge:>+7.1f}{pval:>8.3f}{flag}")

    # اعتبارسنجی پایداری برای thr=0.66 (نقطه شیرین احتمالی)
    thr = 0.66
    eL = cand_long & (pL>=thr) & oosL; eS = cand_short & (pS>=thr) & oosS
    _, trL = run_backtest(df, eL, None, None, 'long', spread=0.20, max_hold=hz,
                          sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr, allow_overlap=False)
    _, trS = run_backtest(df, eS, None, None, 'short', spread=0.20, max_hold=hz,
                          sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr, allow_overlap=False)
    tr = pd.concat([trL, trS], ignore_index=True).sort_values('entry_bar')
    mid = tr['entry_bar'].median()
    print(f"\n--- پایداری زمانی thr={thr} (BE={be:.1f}%) ---")
    for label, sub in [('long-only', trL),('short-only', trS),
                       ('نیمه اول', tr[tr['entry_bar']<=mid]),('نیمه دوم', tr[tr['entry_bar']>mid])]:
        if len(sub)==0: continue
        w=(sub['outcome']=='win').sum(); tt=len(sub)
        pv=stats.binomtest(int(w),tt,be/100,alternative='greater').pvalue
        print(f"  {label}: n={tt} WR={w/tt*100:.2f}% exp={sub['pnl'].mean():+.3f}$ pval={pv:.3f}")

if __name__ == '__main__':
    main()
