"""
استراتژی ۱۵: Meta-Labeling دو-مرحله‌ای (López de Prado) + رژیم نوسان
=====================================================================

مفهوم بنیادی متفاوت از استراتژی‌های ۱–۱۴:
همه‌ی مدل‌های ML قبلی (استراتژی ۴/۶/۷/۸/۹/۱۴) یک مدل واحد ساختند که مستقیماً
روی سؤال «آیا TP قبل از SL لمس می‌شود؟» آموزش می‌دید و با آستانه‌ی احتمال فیلتر
می‌کرد. این رویکرد به سقف WR ~۶۶-۶۸٪ اشباع شد.

اینجا از معماری **Meta-Labeling** کتاب «Advances in Financial Machine Learning»
(Marcos López de Prado، فصل ۳) استفاده می‌کنیم:

  مرحله ۱ — مدل اولیه (Primary): یک قانون ساده و شفاف که فقط **جهت و لحظه‌ی
            ورود** را تعیین می‌کند (recall بالا، precision پایین). ما از یک
            Volatility-Breakout استفاده می‌کنیم: خروج قیمت از فشردگی
            (squeeze) در جهت روند چند-تایم‌فریمی.

  مرحله ۲ — مدل متا (Meta): یک طبقه‌بند دودویی که فقط روی *سیگنال‌های اولیه*
            آموزش می‌بیند و یاد می‌گیرد «کدام‌یک از این سیگنال‌ها واقعاً به TP
            می‌رسند». خروجی متا = اندازه‌ی شرط (bet size) → اینجا صفر/یک
            (بگیر / نگیر). چون متا فقط precision سیگنال‌های اولیه را بالا می‌برد،
            انتظار می‌رود WR را از سقف مدل تک‌مرحله‌ای فراتر ببرد.

چرا ممکن است کار کند (فرضیه‌ی علمی):
مدل تک‌مرحله‌ای مجبور است هم «کجا وارد شوم» و هم «آیا برنده می‌شوم» را با هم یاد
بگیرد؛ این دو وظیفه‌ی متفاوت‌اند و ظرفیت مدل را تقسیم می‌کنند. با جدا کردن‌شان،
مدل متا تمام ظرفیتش را صرف تشخیص کیفیت می‌کند → precision (=WR) بالاتر.

اعتبارسنجی: Purged Walk-Forward با embargo (جلوگیری از نشت اطلاعات به‌خاطر
هم‌پوشانی برچسب‌های triple-barrier). این سخت‌گیرانه‌تر از walk-forward ساده‌ی
استراتژی‌های قبلی است.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scipy import stats
import lightgbm as lgb

import indicators as ind
from backtest import load_data, run_backtest, summary_line
import features as feat


# ---------------------------------------------------------------------------
# ۱) مدل اولیه (Primary): Volatility-Breakout در جهت روند چند-تایم‌فریمی
# ---------------------------------------------------------------------------
def primary_signals(df):
    """
    قانون اولیه (بدون look-ahead):
      - فشردگی نوسان: پهنای Bollinger در پایین‌ترین چارک ۱۰۰ کندل اخیر (squeeze)
      - شکست: close بالاتر از سقف Bollinger (بریک‌اوت صعودی)
      - فیلتر روند: close > EMA200 (فقط long — طلا بایاس صعودی ساختاری دارد)
    برمی‌گرداند: آرایه بولین سیگنال long.
    """
    close = df['close']
    lo_b, mid_b, up_b = ind.bollinger(close, 20, 2.0)
    bb_width = (up_b - lo_b) / close
    # آستانه‌ی squeeze: چارک پایین پهنا در پنجره‌ی ۱۰۰ کندل (فقط گذشته)
    width_q25 = bb_width.rolling(100).quantile(0.25)
    squeeze = bb_width <= width_q25

    ema200 = ind.ema(close, 200)
    ema50 = ind.ema(close, 50)
    uptrend = (close > ema200) & (ema50 > ema200)

    # بریک‌اوت: کندل قبل داخل باند، کندل جاری بسته بالای سقف باند
    broke_up = (close > up_b) & (close.shift(1) <= up_b.shift(1))

    sig = (squeeze.shift(1).fillna(False)) & broke_up & uptrend
    return sig.fillna(False).values


# ---------------------------------------------------------------------------
# ۲) برچسب Triple-Barrier برای *فقط سیگنال‌های اولیه*
# ---------------------------------------------------------------------------
def triple_barrier_labels(df, sig_idx, atr, horizon, tp_mult, sl_mult):
    """
    برای هر ایندکس سیگنال، برچسب ۱ اگر TP قبل از SL (و قبل از افق) لمس شود، وگرنه ۰.
    ورود فرضی در close همان کندل سیگنال (سازگار با فرض مدل؛ بک‌تست واقعی در open کندل بعد).
    خروجی: dict{idx: label}
    """
    high = df['high'].values; low = df['low'].values; close = df['close'].values
    atr_v = atr.values
    n = len(df)
    labels = {}
    for i in sig_idx:
        a = atr_v[i]
        if np.isnan(a) or a <= 0:
            continue
        entry = close[i]
        tp = entry + tp_mult * a
        sl = entry - sl_mult * a
        lab = 0
        end = min(i + 1 + horizon, n)
        for j in range(i + 1, end):
            hit_tp = high[j] >= tp
            hit_sl = low[j] <= sl
            if hit_sl and hit_tp:
                lab = 0; break     # ابهام = بدترین حالت
            if hit_tp:
                lab = 1; break
            if hit_sl:
                lab = 0; break
        labels[i] = lab
    return labels


# ---------------------------------------------------------------------------
# ۳) Purged Walk-Forward با embargo
# ---------------------------------------------------------------------------
def purged_walk_forward(df, X, sig_idx, labels, horizon,
                        n_folds=6, min_train_frac=0.40, embargo=50,
                        threshold=0.60, seeds=(42, 7, 123)):
    """
    آموزش مدل متا فقط روی سیگنال‌های اولیه، به‌صورت walk-forward با purge+embargo.
    برمی‌گرداند: آرایه بولین «کدام سیگنال‌های اولیه، متا تأیید کرده» (روی کل df).
    """
    n = len(df)
    sig_idx = np.array(sorted(sig_idx))
    y = np.array([labels[i] for i in sig_idx])
    feat_cols = X.columns.tolist()
    Xv = X.values

    # مرزهای fold بر اساس ایندکس زمانی کل df
    start = int(n * min_train_frac)
    bounds = np.linspace(start, n, n_folds + 1).astype(int)

    approved = np.zeros(n, dtype=bool)     # روی کل df
    proba_all = np.full(n, np.nan)

    for k in range(n_folds):
        test_lo, test_hi = bounds[k], bounds[k + 1]
        # سیگنال‌های تست در این بازه
        test_mask = (sig_idx >= test_lo) & (sig_idx < test_hi)
        # سیگنال‌های آموزش: قبل از test_lo، با purge افق و embargo
        train_cut = test_lo - horizon - embargo
        train_mask = sig_idx < train_cut
        if train_mask.sum() < 200 or test_mask.sum() == 0:
            continue

        tr_rows = sig_idx[train_mask]
        te_rows = sig_idx[test_mask]
        Xtr = Xv[tr_rows]; ytr = y[train_mask]
        Xte = Xv[te_rows]

        if len(np.unique(ytr)) < 2:
            continue

        # ensemble چند-seed برای کاهش واریانس
        proba = np.zeros(len(te_rows))
        for sd in seeds:
            model = lgb.LGBMClassifier(
                n_estimators=300, learning_rate=0.03, num_leaves=31,
                max_depth=6, subsample=0.8, colsample_bytree=0.8,
                min_child_samples=40, reg_lambda=1.0,
                random_state=sd, n_jobs=-1, verbose=-1,
            )
            model.fit(Xtr, ytr)
            proba += model.predict_proba(Xte)[:, 1]
        proba /= len(seeds)

        proba_all[te_rows] = proba
        approved[te_rows[proba >= threshold]] = True

    return approved, proba_all


def wilson_pvalue_gt(k, n, p0):
    """آزمون یک‌طرفه: آیا نرخ موفقیت واقعی > p0 است؟ (binomial، تقریب نرمال)"""
    if n == 0:
        return 1.0
    phat = k / n
    se = np.sqrt(p0 * (1 - p0) / n)
    z = (phat - p0) / se
    return 1 - stats.norm.cdf(z)


def main():
    print("در حال بارگذاری داده...")
    df = load_data(os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv'))
    print(f"تعداد کندل: {len(df)}")

    atr = ind.atr(df, 14)

    # --- feature ها (همان مجموعه‌ی غنی موجود) ---
    print("ساخت feature ها...")
    X_full = feat.build_features(df)

    # --- سیگنال‌های اولیه ---
    print("تولید سیگنال‌های اولیه (Volatility-Breakout squeeze در روند)...")
    prim = primary_signals(df)
    sig_idx = np.where(prim)[0]
    # حذف سیگنال‌هایی که feature یا atr ندارند
    valid = [i for i in sig_idx if i < len(df) - 60
             and not X_full.iloc[i].isna().any()
             and not np.isnan(atr.values[i])]
    sig_idx = np.array(valid)
    print(f"تعداد کاندید اولیه: {len(sig_idx)}")

    # آمار روزها برای فرکانس
    n_days = (df['dt'].dt.normalize().nunique())
    print(f"تعداد روزهای معاملاتی تقریبی: {n_days}")

    # پیکربندی‌های RR برای جاروب (BE = SL/(TP+SL))
    configs = [
        # (tp_mult, sl_mult, horizon, threshold)
        (1.0, 1.0, 32, 0.55),   # BE=50%
        (1.0, 1.2, 32, 0.55),   # BE=54.5%
        (1.0, 1.5, 48, 0.58),   # BE=60%
        (1.2, 1.2, 40, 0.58),   # BE=50%
        (1.5, 1.5, 48, 0.60),   # BE=50%
    ]

    X_sig = X_full.iloc[sig_idx].reset_index(drop=True)
    X_sig.index = sig_idx  # نگه‌داشتن ایندکس اصلی

    results = []
    for (tp_m, sl_m, hz, thr) in configs:
        be = sl_m / (tp_m + sl_m) * 100
        labels = triple_barrier_labels(df, sig_idx, atr, hz, tp_m, sl_m)
        # هم‌ترازسازی X با ایندکس‌های دارای برچسب
        keys = np.array(sorted(labels.keys()))
        Xk = X_full.iloc[keys].reset_index(drop=True)

        approved, proba = purged_walk_forward(
            df, Xk, keys, labels, horizon=hz,
            n_folds=6, min_train_frac=0.40, embargo=50, threshold=thr,
        )
        entries = np.zeros(len(df), dtype=bool)
        entries[approved] = True

        stats_bt, tr = run_backtest(
            df, entries, sl_points=None, tp_points=None, direction='long',
            spread=0.20, max_hold=hz, allow_overlap=False,
            sl_series=np.full(len(df), np.nan), tp_series=np.full(len(df), np.nan),
        ) if False else run_backtest_atr(df, entries, atr, tp_m, sl_m, hz)

        nt = stats_bt['n_trades']
        wr = stats_bt['win_rate']
        exp = stats_bt['expectancy']
        pnl = stats_bt['total_pnl']
        tpd = nt / n_days if n_days else 0
        pval = wilson_pvalue_gt(round(wr/100*nt), nt, be/100)
        print(f"TP{tp_m}/SL{sl_m} hz{hz} thr{thr} BE{be:.1f}% | "
              f"n={nt} WR={wr:.2f}% exp={exp:+.3f}$ PnL={pnl:+.0f}$ "
              f"trades/day={tpd:.2f} p={pval:.3f}")
        results.append(dict(tp=tp_m, sl=sl_m, hz=hz, thr=thr, be=be,
                            n=nt, wr=wr, exp=exp, pnl=pnl, tpd=tpd, pval=pval))

    return results


def run_backtest_atr(df, entries, atr, tp_mult, sl_mult, horizon):
    """بک‌تست با SL/TP مبتنی بر ATR در لحظه‌ی سیگنال."""
    atr_v = atr.values
    sl_series = atr_v * sl_mult
    tp_series = atr_v * tp_mult
    return run_backtest(
        df, entries, sl_points=None, tp_points=None, direction='long',
        spread=0.20, max_hold=horizon, allow_overlap=False,
        sl_series=sl_series, tp_series=tp_series,
    )


if __name__ == '__main__':
    main()
