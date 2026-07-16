"""
استراتژی ۳۱ — «مغز نزولی تخصصی» (Bear-Specialist Brain) — پاسخ به User Note

انگیزه (User Note کاربر):
  کاربر متوجه شد سایت فقط long کار می‌کند و در روند نزولی هیچ معامله‌ای پیشنهاد
  نمی‌دهد. پیشنهاد داد یک «ماژول تشخیص روند + سه مغز تخصصی (صعودی/نزولی/رنج)» بسازیم.
  این کد اولین گام علمی است: آیا اصلاً یک مغز SHORT تخصصی که *فقط داخل زیررژیم
  نزولی* آموزش دیده و اجرا می‌شود، edge دارد؟

حفرهٔ باز پروژه (قانون L8 در strategy_plans.md):
  «سمت SHORT در کل دوره edge نداشت (روند کلان صعودی) — اما هرگز در زیر-رژیم
  نزولی جداگانه تست نشد.» ← این دقیقاً همان چیزی است که اینجا تست می‌کنیم.

روش (تکرار مو‌به‌مو Recipe-S25، فقط جهت وارون):
  - کاندید = زیررژیم نزولی سختگیرانه: close < EMA50 < EMA200 (آینهٔ دقیق کاندید S25).
  - برچسب = short-win: آیا TP نزولی (entry − TP_M·ATR) قبل از SL نزولی
    (entry + SL_M·ATR) در HZ کندل خورد؟  (make_target(..., 'short'))
  - همان ۵۹ feature کامل (build_features) — هیچ feature حذف/تغییر نمی‌شود (L10).
  - LightGBM ensemble 3-seed، Purged Walk-Forward با embargo=50 (بدون نشت).
  - بک‌تست واقعی با run_backtest(direction='short') + ورود open بعدی + اسپرد 0.2$.
  - جاروب آستانهٔ thr روی نقطهٔ کار پایه (TP1.0/SL1.5, HZ=48) و همچنین نقطهٔ
    PF-محورِ برندهٔ P01 (TP1.4/SL1.7) تا ببینیم مغز نزولی به هدف کاربر می‌رسد یا نه.
  - گزارش کامل: n, WR, PF, exp, pnl, tpd, p(WR>BE), و پایداری ۵-بلوکه.

معیار پذیرش «مغز نزولی معتبر»: WR>60 (p<0.05) + exp>0 + PF بهتر از تصادف،
پایدار در بلوک‌های زمانی. اگر برآورده شد → مغز نزولی وارد سایت سه‌مغزی می‌شود.
"""
import sys; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

# --- نقطهٔ کار (دو حالت) ---
N_FOLDS = 6
MIN_TRAIN_FRAC = 0.40
EMBARGO = 50
SPREAD = 0.20
SEEDS = [42, 7, 123]

WORK_POINTS = [
    # (name, HZ, TP_M, SL_M)
    ('BE60 (TP1.0/SL1.5)', 48, 1.0, 1.5),
    ('PF-point (TP1.4/SL1.7)', 48, 1.4, 1.7),
    ('Symmetric (TP1.3/SL1.5)', 48, 1.3, 1.5),
]


def _lgbm(seed):
    return lgb.LGBMClassifier(
        n_estimators=500, learning_rate=0.025, num_leaves=32,
        max_depth=6, subsample=0.8, colsample_bytree=0.75,
        min_child_samples=80, reg_lambda=2.0, random_state=seed, verbose=-1)


def purged_wf(X, Y, idx, n, seed):
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if te_start >= te_end:
            continue
        m = _lgbm(seed); m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:, 1]
    return proba


def eval_short(df, atr, entries, tp_m, sl_m, hz, label='', verbose=True):
    """آمار استاندارد یک ماسک ورود SHORT."""
    s, tr = run_backtest(df, entries, None, None, 'short', SPREAD, hz,
                         sl_series=sl_m * atr.values, tp_series=tp_m * atr.values,
                         allow_overlap=False)
    nt = s['n_trades']
    if nt == 0:
        if verbose: print(f"{label}: no trades")
        return None
    span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
    tpd = nt / span_days * 7 / 5
    be = sl_m / (tp_m + sl_m) * 100
    wins = int(round(s['win_rate'] / 100 * nt))
    pv = binomtest(wins, nt, be / 100, alternative='greater').pvalue
    gross_win = tr[tr['outcome'] == 'win']['pnl'].sum()
    gross_loss = abs(tr[tr['outcome'] == 'loss']['pnl'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
    if verbose:
        print(f"{label}: n={nt} WR={s['win_rate']:.2f}% PF={pf:.3f} "
              f"exp={s['expectancy']:+.3f}$ pnl={s['total_pnl']:+.1f}$ "
              f"tpd={tpd:.2f} p(WR>{be:.0f})={pv:.4f}")
    return dict(n=nt, wr=s['win_rate'], pf=pf, exp=s['expectancy'],
                pnl=s['total_pnl'], tpd=tpd, pv=pv, trades=tr, be=be)


def five_block_stability(df, atr, entries, tp_m, sl_m, hz):
    """پایداری WR/exp در ۵ بلوک زمانی مساوی."""
    s, tr = run_backtest(df, entries, None, None, 'short', SPREAD, hz,
                         sl_series=sl_m * atr.values, tp_series=tp_m * atr.values,
                         allow_overlap=False)
    if len(tr) == 0:
        return []
    edges = np.linspace(0, len(df), 6).astype(int)
    out = []
    for b in range(5):
        m = (tr['entry_bar'] >= edges[b]) & (tr['entry_bar'] < edges[b + 1])
        sub = tr[m]
        if len(sub) == 0:
            out.append((b + 1, 0, np.nan, np.nan)); continue
        wr = (sub['outcome'] == 'win').mean() * 100
        out.append((b + 1, len(sub), wr, sub['pnl'].mean()))
    return out


def main():
    print("=" * 72)
    print("استراتژی ۳۱ — مغز نزولی تخصصی (Bear-Specialist) — پاسخ به User Note")
    print("=" * 72)
    df = load_data()
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values

    print("ساخت feature ها ...")
    feats = build_features(df)
    cols = list(feats.columns)

    # کاندید = زیررژیم نزولی سختگیرانه (آینهٔ کاندید صعودی S25)
    cand_bear = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)
    print(f"کندل‌های زیررژیم نزولی (کاندید short): {int(cand_bear.sum())} "
          f"({cand_bear.sum()/n*100:.1f}% از کل)")

    results = {}
    for name, hz, tp_m, sl_m in WORK_POINTS:
        print(f"\n{'='*72}\nنقطهٔ کار: {name}  (HZ={hz}, TP={tp_m}, SL={sl_m})\n{'='*72}")
        y = make_target(df, hz, tp_m, sl_m, atr, 'short')
        data = feats.copy(); data['y'] = y; data['cand'] = cand_bear
        valid = data.dropna(subset=cols + ['y']); valid = valid[valid['cand']]
        X = valid[cols].values; Y = valid['y'].values.astype(int)
        idx = valid.index.values
        print(f"نمونه‌های valid برای آموزش short: {len(X)}  "
              f"(نرخ short-win خام: {Y.mean()*100:.1f}%)")

        # proba ensemble OOS
        proba = np.nanmean(np.vstack([purged_wf(X, Y, idx, n, s) for s in SEEDS]), axis=0)

        best = None
        for thr in [0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.72]:
            ent = cand_bear & ~np.isnan(proba) & (proba >= thr)
            r = eval_short(df, atr, ent, tp_m, sl_m, hz, label=f'  thr={thr:.2f}')
            if r and r['wr'] > 60 and r['exp'] > 0 and r['pv'] < 0.05:
                if best is None or r['pf'] > best['pf']:
                    best = {**r, 'thr': thr}
        results[name] = {'proba': proba, 'best': best, 'hz': hz, 'tp': tp_m, 'sl': sl_m}
        if best:
            print(f"\n  ✅ بهترین نقطهٔ معتبر: thr={best['thr']:.2f} "
                  f"WR={best['wr']:.2f}% PF={best['pf']:.3f} exp={best['exp']:+.3f}$ "
                  f"tpd={best['tpd']:.2f} p={best['pv']:.4f}")
            print("  پایداری ۵-بلوکه:")
            ent = cand_bear & ~np.isnan(proba) & (proba >= best['thr'])
            for blk, nb, wr, ex in five_block_stability(df, atr, ent, tp_m, sl_m, hz):
                print(f"    بلوک {blk}: n={nb} WR={wr:.1f}% exp={ex:+.3f}$")
        else:
            print("\n  ❌ هیچ آستانه‌ای هم‌زمان WR>60 + exp>0 + p<0.05 نداد در این نقطهٔ کار.")

    return results, df, atr, cand_bear, cols, feats


def best_proba(res):
    return res['proba']


if __name__ == '__main__':
    main()
