"""
S69 — پرتفویِ چهار-ارزیِ سرمایه‌محور (تعریفِ جدیدِ «سودِ خالص»)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی در هر سند و هر کد): هدفِ پروژه **فقط و فقط
«سودِ خالصِ بیشتر»** است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است. تعدادِ معامله
در روز و Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**

--------------------------------------------------------------------------------
تعریفِ جدیدِ «سودِ خالص» (User Note این نوبت):
  تا امروز «سودِ خالص»ِ برندهٔ پروژه (S67 → +۳۷٬۱۵۶$) فقط روی **XAUUSD** بود.
  از این پس **سودِ خالص = مجموعِ سودِ خالصِ معامله روی هر چهار دارایی به‌طورِ هم‌زمان**:
      XAUUSD + DXY + EURUSD + AUDUSD
  حتی اگر منطقِ برندهٔ XAUUSD روی بقیه جواب ندهد، می‌توانیم برای هرکدام همان
  pipeline را جداگانه fit کنیم و ببینیم هر دارایی چه سهمی به سودِ خالصِ کل می‌دهد.

--------------------------------------------------------------------------------
این استراتژی «منطقِ برندهٔ S63–S67» را دقیقاً و بدونِ تغییر روی **هر دارایی جداگانه**
اجرا می‌کند (نه فقط طلا):
  ۱) ساختِ ۵۷ feature (features.build_features) — کاملاً generic (فقط OHLCV).
  ۲) دو مغزِ ML با walk-forward (Bull long / Bear short) → proba بدونِ نشتِ آینده.
  ۳) رژیمِ EMA50/200 + Efficiency-Ratio کافمن → سطل‌های trend/chop × hi/lo.
  ۴) TP-Plan + SL-Plan رژیم-آگاهِ forward-safe (engine/tpsl_plan.py).
  ۵) موتورِ سرمایه‌محور (engine/capital_engine.py) با **contract_size مخصوصِ هر دارایی**:
        XAUUSD → 100      (۱ لات = ۱۰۰ اونس، حرکتِ ۱$ = ۱۰۰$/لات)
        EURUSD → 100_000  (۱ لات = ۱۰۰k، حرکتِ ۱.۰ واحد = ۱۰۰٬۰۰۰$/لات)
        AUDUSD → 100_000
        DXY    → 1_000    (CFDِ شاخصِ دلار؛ فرضِ متعارف ~۱۰$/point برای ۱ لات = ۱۰۰۰×حرکت)

  هر دارایی سرمایهٔ مستقلِ خودش را دارد (۱۰٬۰۰۰$ ، ریسکِ ۱٪) — چون در عمل روی هر
  نماد یک حسابِ جدا (یا سبدِ ریسکِ جدا) می‌گذاریم. «سودِ خالصِ پرتفوی» = جمعِ چهارتا.

اعتبار: rolling walk-forward، جفتِ SL×TP یادگرفته فقط از گذشته، proba واک-فوروارد،
        اسپردِ مخصوصِ هر دارایی، کمیسیون ۷$/لات، بدونِ کامپاند (ریسکِ ثابت — صادقانه).
"""
import sys, os, gc, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from tpsl_plan import build_plan
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

# --- پارامترهای برنده (هم‌راستا با S66/S67 و router.ts سایت) ---
HZ = 48
N_FOLDS = 5; MIN_TRAIN = 0.45
SEEDS = [42, 7]
ER_WIN = 32
ER_TREND_THR = 0.15           # برندهٔ L40 (راهکار A). router.ts هم همین را دارد.
P_HI = 0.66; P_MIN = 0.58
EVAL_START = 24000            # هم‌راستا با LOOKBACK؛ ارزیابیِ OOS

LGB = dict(objective='binary', n_estimators=200, learning_rate=0.05,
           num_leaves=31, max_depth=6, min_child_samples=80,
           subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=1)

# ضریبِ ATR-نسبیِ آستانهٔ «روشن‌شدنِ سطل». برای XAUUSD، EXP_MIN=0.10 معادلِ
# 0.10/meanATR(=3.83) ≈ 0.026×meanATR است. همین ضریب را برای همهٔ دارایی‌ها به‌کار
# می‌بریم تا معیارِ کیفیتِ سطل scale-invariant شود (باگِ مقیاسِ کشف‌شدهٔ S69).
EXP_MIN_ATR_RATIO = 0.026

# --- مشخصاتِ قراردادِ هر دارایی (هم‌راستا با ASSET_SPECS در router.ts) ---
# spread به «واحدِ قیمتِ همان دارایی». برای فارکس اسپردِ تقریبیِ ۱ پیپ = 0.0001 است.
ASSETS = {
    'XAUUSD': dict(file='data/XAUUSD_M15.csv', contract=100.0,     spread=0.20,    tradable=True),
    'EURUSD': dict(file='data/EURUSD_M15.csv', contract=100_000.0, spread=0.00010, tradable=True),
    'AUDUSD': dict(file='data/AUDUSD_M15.csv', contract=100_000.0, spread=0.00012, tradable=True),
    # DXY یک شاخص است. به‌عنوانِ CFDِ متعارف مدل می‌کنیم (~۱۰$/point ⇒ contract≈1000).
    'DXY':    dict(file='data/DXY_M15.csv',    contract=1_000.0,   spread=0.030,   tradable=True),
}

INITIAL_CAPITAL = 10_000.0
RISK_PCT = 1.0
COMMISSION = 7.0


def efficiency_ratio(close, win):
    close = pd.Series(close)
    change = close.diff(win).abs()
    vol = close.diff().abs().rolling(win).sum()
    er = (change / vol).replace([np.inf, -np.inf], np.nan)
    return er.shift(1).values


def wf_proba(X_all, cols_ok, cand, y, seed, n):
    valid_mask = cols_ok & cand & ~np.isnan(y)
    idx = np.where(valid_mask)[0]
    if len(idx) < 500:
        return np.full(n, np.nan, dtype=np.float32)
    X = X_all[idx]; Y = y[idx].astype(np.int8)
    N = len(X); mt = int(N * MIN_TRAIN); fold = max(1, (N - mt) // N_FOLDS)
    proba = np.full(n, np.nan, dtype=np.float32)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if tr_end >= N:
            break
        m = lgb.LGBMClassifier(random_state=seed, **LGB)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1].astype(np.float32)
        del m; gc.collect()
    return proba


def build_labels(pL, pS, trendy, baseL, baseS, n):
    def lab_for(p, base):
        ef = np.where(trendy, 'trend', 'chop')
        pw = np.where(p >= P_HI, 'hi', 'lo')
        lab = np.array([f'{a}_{b}' for a, b in zip(ef, pw)], dtype=object)
        lab[~base] = ''
        return lab
    return lab_for(pL, baseL), lab_for(pS, baseS)


def run_one_asset(name, cfg):
    print(f"\n{'='*90}\n=== دارایی: {name}  (contract={cfg['contract']:.0f}, spread={cfg['spread']}) ===\n{'='*90}", flush=True)
    df = load_data(cfg['file'])
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14); atrv = atr.values
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values

    up_reg = (c > ema50) & (ema50 > ema200)
    down_reg = (c < ema50) & (ema50 < ema200)
    er = efficiency_ratio(c, ER_WIN)
    trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)

    cL = up_reg & ~np.isnan(atrv)
    cS = down_reg & ~np.isnan(atrv)
    print(f"کندل‌ها={n} | صعودی={cL.sum()} | نزولی={cS.sum()} | روندی(ER≥{ER_TREND_THR})={int(trendy.sum())}", flush=True)

    feats = build_features(df)
    X_all = feats.values.astype(np.float32)
    cols_ok = ~np.isnan(X_all).any(axis=1)
    del feats; gc.collect()

    print("  proba Bull-ML ...", flush=True)
    yL = make_target(df, HZ, 1.0, 1.5, atr, 'long').astype(np.float32)
    pL = np.nanmean(np.vstack([wf_proba(X_all, cols_ok, cL, yL, s, n) for s in SEEDS]), axis=0)
    print("  proba Bear-ML ...", flush=True)
    yS = make_target(df, HZ, 1.4, 1.7, atr, 'short').astype(np.float32)
    pS = np.nanmean(np.vstack([wf_proba(X_all, cols_ok, cS, yS, s, n) for s in SEEDS]), axis=0)
    del X_all, cols_ok; gc.collect()

    baseL = cL & ~np.isnan(atrv) & (pL >= P_MIN)
    baseS = cS & ~np.isnan(atrv) & (pS >= P_MIN)
    labL, labS = build_labels(pL, pS, trendy, baseL, baseS, n)

    eval_mask = np.zeros(n, dtype=bool); eval_mask[EVAL_START:] = True

    # آستانهٔ exp_minِ ATR-نسبی: برای XAUUSD عملاً همان EXP_MIN=0.10، برای فارکس/DXY
    # متناسب با مقیاسِ قیمتِ خودشان (جلوگیری از باگِ صفر-معامله).
    mean_atr = float(np.nanmean(atrv))
    exp_min = EXP_MIN_ATR_RATIO * mean_atr
    print(f"  meanATR={mean_atr:.6f}  → exp_min(ATR-نسبی)={exp_min:.6f}", flush=True)
    print("  ساختِ TP/SL-Plan (Bull) ...", flush=True)
    planL = build_plan('long', labL, atrv, df, run_backtest, spread=cfg['spread'], max_hold=HZ, exp_min=exp_min)
    print("  ساختِ TP/SL-Plan (Bear) ...", flush=True)
    planS = build_plan('short', labS, atrv, df, run_backtest, spread=cfg['spread'], max_hold=HZ, exp_min=exp_min)

    def get_trades(direction, plan):
        s = plan.entries & eval_mask
        st, tr = run_backtest(df, s, None, None, direction, spread=cfg['spread'], max_hold=HZ,
                              sl_series=plan.sl_series(), tp_series=plan.tp_series())
        if len(tr) == 0:
            return tr, np.array([]), np.array([])
        sl_dist = plan.sl_dist_for_trades(tr)
        w = plan.weights[tr['signal_bar'].values]
        return tr, sl_dist, w

    trL, slL, wL = get_trades('long', planL)
    trS, slS, wS = get_trades('short', planS)
    all_tr = pd.concat([trL, trS], ignore_index=True)
    all_sl = np.concatenate([slL, slS]) if (len(slL) or len(slS)) else np.array([])
    all_w = np.concatenate([wL, wS]) if (len(wL) or len(wS)) else np.array([])
    if len(all_tr) == 0:
        print("  هیچ معامله‌ای تولید نشد.", flush=True)
        return dict(name=name, n=0, net=0.0, ret=0.0, dd=0.0, pf=0.0, wr=0.0,
                    n_bull=0, n_bear=0, eq=np.array([INITIAL_CAPITAL]))
    order = all_tr['exit_bar'].values.argsort()
    all_tr = all_tr.iloc[order].reset_index(drop=True)
    all_sl = all_sl[order]; all_w = all_w[order]

    # موتورِ سرمایه با contract مخصوصِ همان دارایی (ریسکِ ثابت — صادقانه)
    s_fixed, eq = run_capital_backtest(all_tr, all_sl, weights=all_w,
                                       initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                       commission_per_lot=COMMISSION, compounding=False,
                                       contract_size=cfg['contract'])
    # کامپاند (سقفِ نظری) برای اطلاع
    s_comp, _ = run_capital_backtest(all_tr, all_sl, weights=all_w,
                                     initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                     commission_per_lot=COMMISSION, compounding=True,
                                     contract_size=cfg['contract'])

    print(f"\n  >>> {name}: n={s_fixed['n_trades']} (Bull={len(trL)}, Bear={len(trS)})  "
          f"netP(ثابت)={s_fixed['net_profit']:+.0f}$ ({s_fixed['return_pct']:+.1f}%)  "
          f"maxDD={s_fixed['max_dd_pct']:.1f}%  PF={s_fixed['profit_factor']:.2f}  "
          f"WR={s_fixed['win_rate']:.1f}%  avgLot={s_fixed['avg_lot']:.2f}", flush=True)
    print(f"      (کامپاند سقفِ نظری: netP={s_comp['net_profit']:+.0f}$ / {s_comp['return_pct']:+.1f}%)", flush=True)

    # آزمونِ دو-نیمه (پایداری)
    mid = all_tr['exit_bar'].median()
    m1 = all_tr['exit_bar'].values <= mid
    halves = {}
    for hn, mask in [('H1', m1), ('H2', ~m1)]:
        h = all_tr[mask].reset_index(drop=True)
        if len(h) == 0:
            halves[hn] = (0, 0.0, 0.0, 0.0); continue
        sh, _ = run_capital_backtest(h, all_sl[mask], weights=all_w[mask],
                                     initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                     commission_per_lot=COMMISSION, compounding=False,
                                     contract_size=cfg['contract'])
        halves[hn] = (sh['n_trades'], sh['net_profit'], sh['return_pct'], sh['max_dd_pct'])
        print(f"      {hn}: n={sh['n_trades']:4d}  netP={sh['net_profit']:+9.0f}$  "
              f"({sh['return_pct']:+6.1f}%)  maxDD={sh['max_dd_pct']:.1f}%", flush=True)

    return dict(name=name, n=s_fixed['n_trades'], net=s_fixed['net_profit'],
                ret=s_fixed['return_pct'], dd=s_fixed['max_dd_pct'],
                pf=s_fixed['profit_factor'], wr=s_fixed['win_rate'],
                sharpe=s_fixed['sharpe'], avglot=s_fixed['avg_lot'],
                net_comp=s_comp['net_profit'],
                n_bull=len(trL), n_bear=len(trS),
                h1=halves['H1'], h2=halves['H2'], eq=eq, tradable=cfg['tradable'])


RES_DIR = os.path.join(os.path.dirname(__file__), '..', 'results')


def run_single_to_json(name):
    """یک دارایی را اجرا و نتیجه را در results/_s69_<name>.json می‌ریزد (برای اجرای کم-مموری در subprocess)."""
    cfg = ASSETS[name]
    r = run_one_asset(name, cfg)
    out = {k: (v if not isinstance(v, np.ndarray) else None) for k, v in r.items() if k != 'eq'}
    with open(os.path.join(RES_DIR, f'_s69_{name}.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print(f"\n[{name}] ذخیره شد در _s69_{name}.json", flush=True)


def main():
    """Orchestrator: هر دارایی در یک subprocessِ جدا اجرا می‌شود (سقفِ مموریِ ~۱GB)."""
    import subprocess
    print("=== S69: پرتفویِ چهار-ارزیِ سرمایه‌محور (تعریفِ جدیدِ سودِ خالص) ===", flush=True)
    print(f"قانونِ #۱: فقط سودِ خالص. سرمایهٔ هر دارایی={INITIAL_CAPITAL:.0f}$، ریسک={RISK_PCT}%، ریسکِ ثابت.", flush=True)
    print("هر دارایی در subprocessِ جدا اجرا می‌شود تا مموری آزاد شود.\n", flush=True)
    for name in ASSETS:
        print(f"\n>>> اجرای subprocess برای {name} ...", flush=True)
        rc = subprocess.call([sys.executable, os.path.abspath(__file__), name])
        if rc != 0:
            print(f"!!! {name} با کدِ {rc} خطا داد (احتمالاً مموری). ادامه می‌دهیم.", flush=True)

    # جمع‌آوریِ نتایجِ JSON هر دارایی
    results = {}
    for name in ASSETS:
        p = os.path.join(RES_DIR, f'_s69_{name}.json')
        if os.path.exists(p):
            with open(p) as fh:
                results[name] = json.load(fh)
        else:
            results[name] = dict(name=name, n=0, net=0.0, ret=0.0, dd=0.0, pf=0.0,
                                  wr=0.0, n_bull=0, n_bear=0, net_comp=0.0, tradable=True)

    print(f"\n\n{'#'*90}\n### جمع‌بندیِ پرتفوی — تعریفِ جدیدِ «سودِ خالص» = جمعِ چهار دارایی\n{'#'*90}", flush=True)
    print(f"{'دارایی':10s} {'n':>5s} {'Bull':>5s} {'Bear':>5s} {'netP$':>11s} {'بازده%':>9s} "
          f"{'maxDD%':>8s} {'PF':>6s} {'WR%':>6s}", flush=True)
    total_net = 0.0; total_net_comp = 0.0; total_n = 0
    tradable_net = 0.0
    for name in ASSETS:
        r = results[name]
        total_net += r['net']; total_net_comp += r.get('net_comp', 0.0); total_n += r['n']
        if r.get('tradable', True) and name != 'DXY':
            tradable_net += r['net']
        print(f"{name:10s} {r['n']:5d} {r['n_bull']:5d} {r['n_bear']:5d} {r['net']:+11.0f} "
              f"{r['ret']:+9.1f} {r['dd']:8.1f} {r['pf']:6.2f} {r['wr']:6.1f}", flush=True)
    print("-" * 90, flush=True)
    print(f"{'جمعِ کل':10s} {total_n:5d} {'':5s} {'':5s} {total_net:+11.0f}$  "
          f"(کامپاندِ سقفِ نظری: {total_net_comp:+.0f}$)", flush=True)
    print(f"\n★ سودِ خالصِ پرتفوی (چهار دارایی، ریسکِ ثابت ۱٪ روی ۱۰k$ هرکدام) = {total_net:+.0f}$", flush=True)
    print(f"★ سودِ خالصِ سه داراییِ معامله‌پذیرِ خالص (XAU+EUR+AUD، بدونِ DXY) = {tradable_net:+.0f}$", flush=True)
    print(f"  مقایسه: برندهٔ قبلی S67 (فقط XAUUSD) = +37,156$", flush=True)

    # ذخیرهٔ خلاصه برای گزارش
    out = {name: results[name] for name in ASSETS}
    out['_portfolio'] = dict(total_net=total_net, total_net_comp=total_net_comp,
                             total_n=total_n, tradable_net_no_dxy=tradable_net)
    with open(os.path.join(RES_DIR, '_s69_summary.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("\nخلاصه در results/_s69_summary.json ذخیره شد. تمام.", flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ASSETS:
        run_single_to_json(sys.argv[1])
    else:
        main()
