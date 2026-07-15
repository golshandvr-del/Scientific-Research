"""
استراتژی ۱۴: VWAP-Regime Selective ML با هدف WR>60% + سودآور + فرکانس بالا

انگیزه (هدف بازتعریف‌شده کاربر: WR>60% به‌جای 70%):
کشف بنیادی پروژه: سقف WR معنادار با OHLCV حدود ۶۶–۶۸٪ است و RR نامتقارن به‌تنهایی
expectancy مثبت نمی‌سازد. اما با هدف پایین‌تر (>۶۰٪) فضای مانور بیشتری داریم:
می‌توانیم BE را روی ~۶۰٪ (TP1.0/SL1.5) بگذاریم و با فیلتر ML، WR را به‌طور
معنادار *بالاتر از BE* ببریم (edge مثبت = expectancy مثبت) و هم‌زمان فرکانس
کافی برای ربات (≥۳ معامله/روز) حفظ کنیم.

نوآوری‌ها نسبت به استراتژی‌های ۱–۱۳:
1. feature‌های جدید مبتنی بر VWAP روزانه لنگرشده + z-score حجم (از مقاله SSRN
   «Regime-Filtered Intraday Gold» و منابع VWAP-reversion).
2. BE هدف = ۶۰٪ (نه ۶۶–۷۵٪) → منطبق بر هدف جدید کاربر و آسان‌تر برای عبور معنادار.
3. context پایه وسیع (روند صعودی، بدون قید سشن سخت) → n بزرگ برای فرکانس بالا.
4. آزمون معناداری در برابر BE=60% + گزارش معامله/روز.

متد: LightGBM Walk-Forward (۶ fold)، ورود در OPEN کندل بعد، اسپرد ۰.۲$.
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

def walk_forward(df, feats, fc, cand, n, hz, tp_m, sl_m, seed=42):
    """proba out-of-sample برای کاندیدها با walk-forward."""
    atr = ind.atr(df, 14)
    y = make_target(df, hz, tp_m, sl_m, atr, 'long')
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=fc + ['y'])
    valid = valid[valid['cand']]
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

def trades_per_day(df, n_trades):
    span_days = (df['dt'].max() - df['dt'].min()).days
    trading_days = span_days * 5 / 7
    return n_trades / trading_days

def main():
    df = load_data(); df['hour'] = df['dt'].dt.hour
    atr = ind.atr(df, 14); atr_arr = atr.values
    c = df['close']; cv = c.values
    ema50 = ind.ema(c, 50).values; ema200 = ind.ema(c, 200).values
    n = len(df)
    feats = build_features(df); fc = list(feats.columns)

    # context پایه وسیع: فقط روند صعودی (برای فرکانس بالا). بدون قید سشن سخت.
    cand = (cv > ema50) & (ema50 > ema200)
    print(f"داده: {n} کندل | کاندید پایه (uptrend): {int(cand.sum())}")
    print(f"feature count: {len(fc)} (شامل VWAP/volume جدید)")

    # RR با BE هدف ~۶۰٪
    for hz, tp_m, sl_m in [(48, 1.0, 1.5), (32, 1.0, 1.5), (48, 1.0, 1.4)]:
        be = sl_m / (tp_m + sl_m) * 100
        proba = walk_forward(df, feats, fc, cand, n, hz, tp_m, sl_m, seed=42)
        oos_mask = ~np.isnan(proba)
        print(f"\n### RR TP={tp_m} SL={sl_m} hz={hz} | BE={be:.1f}% | OOS candles={int(oos_mask.sum())}")
        print(f"{'thr':>6}{'n':>7}{'WR%':>8}{'exp$':>9}{'pnl$':>9}{'tr/day':>8}{'edge':>7}{'pval':>8}")
        for thr in [0.50, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68]:
            entries = cand & (proba >= thr) & oos_mask
            s, tr = run_backtest(df, entries, None, None, 'long', spread=0.20,
                                 max_hold=hz, sl_series=sl_m*atr_arr,
                                 tp_series=tp_m*atr_arr, allow_overlap=False)
            nt = s['n_trades']
            if nt < 50: continue
            wins = int(round(s['win_rate']/100*nt))
            pval = stats.binomtest(wins, nt, be/100, alternative='greater').pvalue
            # فرکانس روی بخش OOS (که تقریبا 60% کل زمان است)
            oos_frac = oos_mask.sum() / n
            tpd = trades_per_day(df, nt) / oos_frac  # نرمال‌سازی به فرکانس معادل کل‌زمان
            edge = s['win_rate'] - be
            flag = ""
            if s['win_rate'] > 60 and s['expectancy'] > 0 and pval < 0.05 and tpd >= 3:
                flag = " <<<=== WINNER (WR>60 + exp>0 + sig + freq)"
            elif s['win_rate'] > 60 and s['expectancy'] > 0 and pval < 0.05:
                flag = " <== sig+profitable"
            elif s['win_rate'] > 60 and s['expectancy'] > 0:
                flag = " <-- WR>60 & profitable"
            print(f"{thr:>6.2f}{nt:>7}{s['win_rate']:>8.2f}{s['expectancy']:>9.3f}"
                  f"{s['total_pnl']:>9.1f}{tpd:>8.2f}{edge:>+7.1f}{pval:>8.3f}{flag}")

if __name__ == '__main__':
    main()
