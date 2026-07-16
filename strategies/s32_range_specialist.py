"""
استراتژی ۳۲ — «مغز رنج تخصصی» (Range-Specialist Brain) — پاسخ به User Note (مغز سوم)

انگیزه: کاربر سه مغز خواست: صعودی (داریم) / نزولی (S31 ساخته شد) / رنج.
این مغز سوم است: بازار وقتی نه صعودی نه نزولی است (رنج/خنثی).

تعریف رژیم رنج (مکمل دقیق دو مغز دیگر):
  رنج = نه uptrend (close>EMA50>EMA200) و نه downtrend (close<EMA50<EMA200).
  یعنی EMA ها درهم‌تنیده‌اند یا قیمت بین آنهاست. به‌علاوه فیلتر ADX پایین برای
  تأکید بر بی‌روندی: adx < 25 (بازار بدون روند قوی).

منطق معاملاتی رنج = Mean-Reversion دوطرفه:
  در رنج، قیمت بین حمایت/مقاومت نوسان می‌کند. منطق کلاسیک: از کفِ رنج long، از
  سقفِ رنج short. اما به‌جای قانون خام (که S13 با آن شکست خورد)، دو مدل ML جدا:
    - مدل LONG رنج: کاندید = رنج + قیمت در نیمهٔ پایین باند (bb_pos<0.5)، برچسب long-win.
    - مدل SHORT رنج: کاندید = رنج + قیمت در نیمهٔ بالای باند (bb_pos>0.5)، برچسب short-win.
  هر کدام Purged Walk-Forward جدا. سیگنال نهایی = هرکدام که آستانه را رد کند.

نقطهٔ کار: در رنج، حرکات کوچک‌ترند؛ TP/SL محافظه‌کارتر آزمایش می‌شود.
معیار پذیرش: WR>60 یا (PF>1.3 + exp>0 + p<0.05) پایدار. اگر هیچ‌کدام → ثبت شکست.
"""
import sys; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS, MIN_TRAIN_FRAC, EMBARGO, SPREAD = 6, 0.40, 50, 0.20
SEEDS = [42, 7, 123]

WORK_POINTS = [
    ('BE60 (TP1.0/SL1.5)', 32, 1.0, 1.5),
    ('Tight-MR (TP1.0/SL1.2)', 32, 1.0, 1.2),
    ('PF-point (TP1.3/SL1.5)', 32, 1.3, 1.5),
]


def _lgbm(seed):
    return lgb.LGBMClassifier(n_estimators=500, learning_rate=0.025, num_leaves=32,
        max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
        reg_lambda=2.0, random_state=seed, verbose=-1)


def purged_wf(X, Y, idx, n, seed):
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold; te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if te_start >= te_end: continue
        m = _lgbm(seed); m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:, 1]
    return proba


def eval_dir(df, atr, entries, direction, tp_m, sl_m, hz, label='', be_ref=None, verbose=True):
    s, tr = run_backtest(df, entries, None, None, direction, SPREAD, hz,
                         sl_series=sl_m*atr.values, tp_series=tp_m*atr.values, allow_overlap=False)
    nt = s['n_trades']
    if nt == 0:
        if verbose: print(f"{label}: no trades")
        return None
    span = (df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    tpd = nt/span*7/5
    be = sl_m/(tp_m+sl_m)*100
    wins = int(round(s['win_rate']/100*nt))
    pv = binomtest(wins, nt, be/100, alternative='greater').pvalue
    gw = tr[tr['outcome']=='win']['pnl'].sum(); gl = abs(tr[tr['outcome']=='loss']['pnl'].sum())
    pf = gw/gl if gl>0 else float('inf')
    if verbose:
        print(f"{label}: n={nt} WR={s['win_rate']:.2f}% PF={pf:.3f} exp={s['expectancy']:+.3f}$ "
              f"pnl={s['total_pnl']:+.1f}$ tpd={tpd:.2f} p(WR>{be:.0f})={pv:.4f}")
    return dict(n=nt, wr=s['win_rate'], pf=pf, exp=s['expectancy'], pnl=s['total_pnl'],
                tpd=tpd, pv=pv, trades=tr, be=be, entries=entries)


def main():
    print("="*72)
    print("استراتژی ۳۲ — مغز رنج تخصصی (Range-Specialist) — مغز سوم")
    print("="*72)
    df = load_data(); n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    adx, pdi, mdi = ind.adx(df, 14)
    print("ساخت feature ها ...")
    feats = build_features(df); cols = list(feats.columns)
    bb_pos = feats['bb_pos'].values

    uptrend = (c > ema50) & (ema50 > ema200)
    downtrend = (c < ema50) & (ema50 < ema200)
    is_range = (~uptrend) & (~downtrend) & (adx.values < 25) & ~np.isnan(atr.values)
    print(f"کندل‌های رنج (نه صعودی نه نزولی، ADX<25): {int(is_range.sum())} "
          f"({is_range.sum()/n*100:.1f}% از کل)")

    for name, hz, tp_m, sl_m in WORK_POINTS:
        print(f"\n{'='*72}\nنقطهٔ کار: {name} (HZ={hz}, TP={tp_m}, SL={sl_m})\n{'='*72}")
        y_long = make_target(df, hz, tp_m, sl_m, atr, 'long')
        y_short = make_target(df, hz, tp_m, sl_m, atr, 'short')

        # مدل LONG رنج: از نیمهٔ پایین باند (نزدیک کف رنج)
        cand_L = is_range & (bb_pos < 0.5)
        # مدل SHORT رنج: از نیمهٔ بالای باند (نزدیک سقف رنج)
        cand_S = is_range & (bb_pos > 0.5)

        # آموزش/OOS هر جهت
        def fit_dir(cand, y):
            data = feats.copy(); data['y'] = y; data['cand'] = cand
            valid = data.dropna(subset=cols+['y']); valid = valid[valid['cand']]
            if len(valid) < 500: return None, 0, 0
            X = valid[cols].values; Y = valid['y'].values.astype(int); idx = valid.index.values
            proba = np.nanmean(np.vstack([purged_wf(X, Y, idx, n, s) for s in SEEDS]), axis=0)
            return proba, len(X), Y.mean()

        pL, nL, wrL = fit_dir(cand_L, y_long)
        pS, nS, wrS = fit_dir(cand_S, y_short)
        print(f"LONG رنج: {nL} نمونه (خام win {wrL*100:.1f}%) | "
              f"SHORT رنج: {nS} نمونه (خام win {wrS*100:.1f}%)")

        # جاروب آستانه (long و short جدا، سپس ترکیب)
        best = None
        for thr in [0.58, 0.60, 0.62, 0.64, 0.66, 0.68]:
            rL = rS = None
            if pL is not None:
                entL = cand_L & ~np.isnan(pL) & (pL >= thr)
                rL = eval_dir(df, atr, entL, 'long', tp_m, sl_m, hz, label=f'  thr={thr:.2f} LONG', verbose=True)
            if pS is not None:
                entS = cand_S & ~np.isnan(pS) & (pS >= thr)
                rS = eval_dir(df, atr, entS, 'short', tp_m, sl_m, hz, label=f'  thr={thr:.2f} SHORT', verbose=True)
            # ترکیب دوطرفه (WR وزنی، PF کل)
            if rL and rS:
                nt = rL['n']+rS['n']
                wins = rL['wr']/100*rL['n'] + rS['wr']/100*rS['n']
                wr = wins/nt*100
                pnl = rL['pnl']+rS['pnl']
                gw = rL['trades'][rL['trades']['outcome']=='win']['pnl'].sum() + rS['trades'][rS['trades']['outcome']=='win']['pnl'].sum()
                gl = abs(rL['trades'][rL['trades']['outcome']=='loss']['pnl'].sum()) + abs(rS['trades'][rS['trades']['outcome']=='loss']['pnl'].sum())
                pf = gw/gl if gl>0 else float('inf')
                span = (df['dt'].iloc[-1]-df['dt'].iloc[0]).days
                tpd = nt/span*7/5
                exp = pnl/nt
                be = rL['be']
                pv = binomtest(int(round(wins)), nt, be/100, alternative='greater').pvalue
                print(f"  → COMBINED thr={thr:.2f}: n={nt} WR={wr:.2f}% PF={pf:.3f} exp={exp:+.3f}$ pnl={pnl:+.1f}$ tpd={tpd:.2f} p={pv:.4f}")
                ok = (wr>60 and exp>0 and pv<0.05) or (pf>1.3 and exp>0 and pv<0.05)
                if ok and (best is None or pf>best['pf']):
                    best = dict(thr=thr, n=nt, wr=wr, pf=pf, exp=exp, pnl=pnl, tpd=tpd, pv=pv)
        if best:
            print(f"\n  ✅ بهترین نقطهٔ معتبر رنج: {best}")
        else:
            print("\n  ❌ هیچ آستانه‌ای معیار پذیرش (WR>60 یا PF>1.3+p<0.05) را نداد.")


if __name__ == '__main__':
    main()
