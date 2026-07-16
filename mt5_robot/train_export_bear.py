"""
آموزش و صادرات «مغز نزولی» (Bear-Specialist, S31) به ONNX برای اجرای مرورگری.
=================================================================================
هم‌ساختار train_export_s25.py اما:
  - جهت = SHORT
  - کاندید = زیررژیم نزولی: close < EMA50 < EMA200
  - برچسب = short-win
  - نقطهٔ کار PF-محور برندهٔ S31: HZ=48, TP=1.4, SL=1.7, THR=0.66
  - همان ۵۹ feature کامل build_features (feature parity با مغز صعودی)

خروجی: xauusd_bear_model_{0,1,2}.onnx + model_meta_bear.txt + feature_order_bear.txt
سپس مدل‌ها به web_tool/public/static/models/ کپی می‌شوند.
"""
import sys, os
ENGINE = os.path.join(os.path.dirname(__file__), '..', 'engine')
sys.path.insert(0, ENGINE)
import numpy as np
import pandas as pd
import lightgbm as lgb
from scipy import stats
import indicators as ind
from backtest import load_data, run_backtest
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')

# نقطهٔ کار برندهٔ مغز نزولی (S31 PF-point)
HZ, TP_M, SL_M, THR = 48, 1.4, 1.7, 0.66
BE = SL_M / (TP_M + SL_M) * 100
SEEDS = [42, 7, 123]
N_FOLDS = 6
MIN_TRAIN_FRAC = 0.40

LGB_PARAMS = dict(n_estimators=500, learning_rate=0.025, num_leaves=32, max_depth=6,
                  subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
                  reg_lambda=2.0, verbose=-1)


def wf_proba(feats, fc, cand, y, n, seed):
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=fc + ['y']); valid = valid[valid['cand']]
    X = valid[fc].values; Y = valid['y'].values.astype(int); idx = valid.index.values
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold; te_start = tr_end + 50
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if te_start >= te_end: continue
        m = lgb.LGBMClassifier(random_state=seed, **LGB_PARAMS)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:, 1]
    return proba


def main():
    print("بارگذاری داده و ساخت feature ها (۵۹ feature، مشترک با مغز صعودی)...")
    df = load_data(DATA)
    atr = ind.atr(df, 14); atr_arr = atr.values
    c = df['close']; cv = c.values
    ema50 = ind.ema(c, 50).values; ema200 = ind.ema(c, 200).values
    n = len(df)
    feats = build_features(df); fc = list(feats.columns)
    cand = (cv < ema50) & (ema50 < ema200)   # زیررژیم نزولی
    y = make_target(df, HZ, TP_M, SL_M, atr, 'short')
    print(f"کاندید نزولی: {int(cand.sum())} | تعداد feature: {len(fc)}")

    print("Walk-Forward Ensemble برای تأیید edge نزولی...")
    proba = np.nanmean(np.vstack([wf_proba(feats, fc, cand, y, n, sd) for sd in SEEDS]), axis=0)
    oos = ~np.isnan(proba)
    entries = cand & (proba >= THR) & oos
    s, tr = run_backtest(df, entries, None, None, 'short', spread=0.20, max_hold=HZ,
                         sl_series=SL_M * atr_arr, tp_series=TP_M * atr_arr,
                         allow_overlap=False)
    nt = s['n_trades']; wins = int(round(s['win_rate'] / 100 * nt))
    pval = stats.binomtest(wins, nt, BE / 100, alternative='greater').pvalue
    gw = tr[tr['outcome']=='win']['pnl'].sum(); gl = abs(tr[tr['outcome']=='loss']['pnl'].sum())
    pf = gw/gl if gl>0 else float('inf')
    print("=" * 64)
    print(f"تأیید مغز نزولی (thr={THR}): n={nt} WR={s['win_rate']:.2f}% PF={pf:.3f} "
          f"exp={s['expectancy']:+.3f}$ PnL={s['total_pnl']:+.0f}$ p(WR>{BE:.0f})={pval:.4f}")
    print("=" * 64)
    result = dict(n=nt, wr=s['win_rate'], pf=pf, exp=s['expectancy'], pnl=s['total_pnl'], pval=pval)

    print("\nآموزش مدل نهایی نزولی (ensemble ۳-seed) روی کل کاندید نزولی...")
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=fc + ['y']); valid = valid[valid['cand']]
    X = valid[fc].values.astype(np.float32); Y = valid['y'].values.astype(int)

    from onnxmltools.convert import convert_lightgbm
    from onnxmltools.convert.common.data_types import FloatTensorType
    import onnxruntime as ort
    initial_type = [('input', FloatTensorType([None, len(fc)]))]

    models = []
    for si, sd in enumerate(SEEDS):
        m = lgb.LGBMClassifier(random_state=sd, **LGB_PARAMS)
        m.fit(X, Y); models.append(m)
        onx = convert_lightgbm(m, initial_types=initial_type, zipmap=False, target_opset=12)
        p = os.path.join(os.path.dirname(__file__), f'xauusd_bear_model_{si}.onnx')
        with open(p, 'wb') as fp:
            fp.write(onx.SerializeToString())
        print(f"  مدل seed={sd} → {os.path.basename(p)} ({os.path.getsize(p)} bytes)")

    sess = ort.InferenceSession(os.path.join(os.path.dirname(__file__), 'xauusd_bear_model_0.onnx'))
    in_name = sess.get_inputs()[0].name
    sample = X[:300]
    lgb_p = models[0].predict_proba(sample)[:, 1]
    onx_out = sess.run(None, {in_name: sample})
    onx_p = None
    for arr in onx_out:
        a = np.array(arr)
        if a.ndim == 2 and a.shape[1] == 2:
            onx_p = a[:, 1]; break
    if onx_p is not None:
        max_diff = float(np.max(np.abs(lgb_p - onx_p)))
        print(f"اعتبارسنجی ONNX نزولی: حداکثر اختلاف = {max_diff:.2e} "
              f"({'✅ OK' if max_diff < 1e-4 else '⚠️'})")

    meta_path = os.path.join(os.path.dirname(__file__), 'model_meta_bear.txt')
    with open(meta_path, 'w') as fp:
        fp.write(f"DIRECTION=short\nTHR={THR}\nHZ={HZ}\nTP_M={TP_M}\nSL_M={SL_M}\nBE={BE}\n")
        fp.write(f"WR={result['wr']:.2f}\nPF={result['pf']:.3f}\nEXP={result['exp']:.4f}\n")
        fp.write(f"PVAL={result['pval']:.4f}\nN_FEATURES={len(fc)}\nSEEDS={','.join(map(str,SEEDS))}\n")
    print(f"متادیتا: {os.path.basename(meta_path)}")

    fo_path = os.path.join(os.path.dirname(__file__), 'feature_order_bear.txt')
    with open(fo_path, 'w') as fp:
        for i, name in enumerate(fc):
            fp.write(f"{i}\t{name}\n")
    print(f"ترتیب feature: {os.path.basename(fo_path)}")
    return result


if __name__ == '__main__':
    main()
