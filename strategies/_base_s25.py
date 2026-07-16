"""
ماژول مشترک گروه F: بازتولید مدل پایهٔ برندهٔ S25 و ارائهٔ ابزارهای مشترک.

هدف: همهٔ طرح‌های گروه F (P30..P36) روی همین جریان پایه سوار می‌شوند، پس یک بار
مدل پایه + proba + برچسب‌ها + کاندید + feature ها را می‌سازیم و کش می‌کنیم تا
تکرار محاسبات گران (walk-forward LightGBM) لازم نباشد.

جریان پایه دقیقاً = S25:
  - long-only در uptrend  close>ema50>ema200
  - ۵۹ feature کامل (build_features شامل early_atr و weekly_rev)
  - LightGBM ensemble 3-seed، Purged Walk-Forward با embargo
  - نقطهٔ کار پیش‌فرض: HZ=48, TP=1.0, SL=1.5, thr=0.68 (نقطهٔ برندهٔ S25)

خروجی‌ها (توابع):
  load_base()  -> dict شامل df, atr, cand, feats, cols, y (برچسب برد/باخت), proba_ens
  purged_walk_forward(...) -> proba OOS با embargo
  eval_entries(...) -> آمار استاندارد یک ماسک ورود
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

# --- ثابت‌های نقطهٔ کار پایهٔ S25 ---
N_FOLDS = 6
MIN_TRAIN_FRAC = 0.40
EMBARGO = 50
HZ = 48
TP_M = 1.0
SL_M = 1.5
THRESH = 0.68
SPREAD = 0.20
SEEDS = [42, 7, 123]

_CACHE = {}


def _lgbm(seed):
    return lgb.LGBMClassifier(
        n_estimators=500, learning_rate=0.025, num_leaves=32,
        max_depth=6, subsample=0.8, colsample_bytree=0.75,
        min_child_samples=80, reg_lambda=2.0, random_state=seed, verbose=-1)


def purged_walk_forward(X, Y, idx, n, seed=42, embargo=EMBARGO,
                        n_folds=N_FOLDS, min_train_frac=MIN_TRAIN_FRAC,
                        return_models=False):
    """proba OOS با Purged Walk-Forward + embargo. idx = اندیس اصلی df هر ردیف valid."""
    N = len(X)
    mt = int(N * min_train_frac)
    fold = (N - mt) // n_folds
    proba = np.full(n, np.nan)
    models = []
    for k in range(n_folds):
        tr_end = mt + k * fold
        te_start = tr_end + embargo           # purge/embargo
        te_end = tr_end + fold if k < n_folds - 1 else N
        if te_start >= te_end:
            continue
        m = _lgbm(seed)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:, 1]
        if return_models:
            models.append(m)
    if return_models:
        return proba, models
    return proba


def load_base(verbose=True):
    """مدل پایهٔ S25 را می‌سازد و کش می‌کند. proba_ens = میانگین ۳ seed روی OOS."""
    if 'base' in _CACHE:
        return _CACHE['base']
    df = load_data()
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values

    if verbose:
        print("ساخت feature ها ...")
    feats = build_features(df)
    cols = list(feats.columns)

    # کاندید پایه S25: روند صعودی long-only
    cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)

    # برچسب برد/باخت در نقطهٔ کار پایه
    y = make_target(df, HZ, TP_M, SL_M, atr, 'long')

    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=cols + ['y'])
    valid = valid[valid['cand']]
    X = valid[cols].values
    Y = valid['y'].values.astype(int)
    idx = valid.index.values

    if verbose:
        print(f"کاندید پایه (uptrend long): {int(cand.sum())}, valid rows: {len(X)}")

    # proba ensemble OOS
    probas = [purged_walk_forward(X, Y, idx, n, seed=s) for s in SEEDS]
    proba_ens = np.nanmean(np.vstack(probas), axis=0)

    base = dict(df=df, n=n, c=c, atr=atr, ema50=ema50, ema200=ema200,
                feats=feats, cols=cols, cand=cand, y=y,
                X=X, Y=Y, idx=idx, valid_index=valid.index.values,
                proba_ens=proba_ens)
    _CACHE['base'] = base
    return base


def eval_entries(df, atr, entries, tp_m=TP_M, sl_m=SL_M, hz=HZ,
                 spread=SPREAD, label='', verbose=True):
    """آمار استاندارد یک ماسک ورود long. برمی‌گرداند dict یا None."""
    s, tr = run_backtest(df, entries, None, None, 'long', spread, hz,
                         sl_series=sl_m * atr.values, tp_series=tp_m * atr.values,
                         allow_overlap=False)
    nt = s['n_trades']
    if nt == 0:
        if verbose:
            print(f"{label}: no trades")
        return None
    span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
    tpd = nt / span_days * 7 / 5
    be = sl_m / (tp_m + sl_m) * 100
    wins = int(round(s['win_rate'] / 100 * nt))
    pv = binomtest(wins, nt, be / 100, alternative='greater').pvalue
    # Profit Factor
    gross_win = tr[tr['outcome'] == 'win']['pnl'].sum()
    gross_loss = abs(tr[tr['outcome'] == 'loss']['pnl'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
    if verbose:
        print(f"{label}: n={nt} WR={s['win_rate']:.2f}% PF={pf:.3f} "
              f"exp={s['expectancy']:+.3f}$ pnl={s['total_pnl']:+.1f}$ "
              f"tpd={tpd:.2f} p(WR>{be:.0f})={pv:.4f}")
    return dict(n=nt, wr=s['win_rate'], pf=pf, exp=s['expectancy'],
                pnl=s['total_pnl'], tpd=tpd, pv=pv, trades=tr, be=be)
