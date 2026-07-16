"""
آموزش و صادرات مدل نهایی ربات/سایت — نسخهٔ S25 (ML + Weekly-Reversion Context).
=================================================================================
تفاوت با train_export_final.py (S14):
  - build_features حالا ۵۹ feature می‌سازد (دو feature زمانی جدید early_atr و
    weekly_rev اضافه شده‌اند). این‌ها در استراتژی ۲۵ قوی‌ترین سیگنال مدل شدند
    (early_atr رتبهٔ #۱). این اسکریپت مدل ONNX را روی همان ۵۹ feature بازآموزی
    و صادر می‌کند تا سایت زندهٔ web_tool «دقیقاً معادل استراتژی برندهٔ ۲۵» شود.

این اسکریپت:
1. با build_features کامل (۵۹ feature) + ensemble ۳-seed، WR>60٪ را Walk-Forward
   بازتولید و تأیید می‌کند (انتظار: WR≈۶۲٪، exp≈+۰.۵۳$، p≈۰.۰۲۷).
2. سه مدل ensemble را روی کل داده آموزش می‌دهد و به ONNX صادر می‌کند.
3. ترتیب کامل ۵۹ feature و آستانه را در فایل‌های متادیتای S25 ثبت می‌کند.

خروجی: xauusd_s25_model_{0,1,2}.onnx + model_meta_s25.txt + feature_order_s25.txt
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

# پارامترهای برندهٔ استراتژی ۲۵ (همان قالب S14 برای مقایسهٔ منصفانه)
HZ, TP_M, SL_M, THR = 48, 1.0, 1.5, 0.68
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
        tr_end = mt + k * fold; te_end = tr_end + fold if k < N_FOLDS - 1 else N
        m = lgb.LGBMClassifier(random_state=seed, **LGB_PARAMS)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1]
    return proba


def main():
    print("بارگذاری داده و ساخت featureهای کامل (۵۹ feature S25)...")
    df = load_data(DATA)
    atr = ind.atr(df, 14); atr_arr = atr.values
    c = df['close']; cv = c.values
    ema50 = ind.ema(c, 50).values; ema200 = ind.ema(c, 200).values
    n = len(df)
    feats = build_features(df); fc = list(feats.columns)
    cand = (cv > ema50) & (ema50 > ema200)
    y = make_target(df, HZ, TP_M, SL_M, atr, 'long')
    print(f"کاندید پایه: {int(cand.sum())} | تعداد feature: {len(fc)}")
    assert 'early_atr' in fc and 'weekly_rev' in fc, "feature های زمانی S25 غایب‌اند!"

    print("Walk-Forward Ensemble برای تأیید WR>60٪...")
    proba = np.nanmean(np.vstack([wf_proba(feats, fc, cand, y, n, sd) for sd in SEEDS]), axis=0)
    oos = ~np.isnan(proba)
    entries = cand & (proba >= THR) & oos
    s, tr = run_backtest(df, entries, None, None, 'long', spread=0.20, max_hold=HZ,
                         sl_series=SL_M * atr_arr, tp_series=TP_M * atr_arr,
                         allow_overlap=False)
    nt = s['n_trades']; wins = int(round(s['win_rate'] / 100 * nt))
    pval = stats.binomtest(wins, nt, BE / 100, alternative='greater').pvalue
    span_days = (df['dt'].max() - df['dt'].min()).days
    trading_days = span_days * 5 / 7
    tpd = (nt / trading_days) / (oos.sum() / n)
    print("=" * 64)
    print(f"تأیید S25 (thr={THR}): n={nt} WR={s['win_rate']:.2f}% "
          f"exp={s['expectancy']:+.3f}$ PnL={s['total_pnl']:+.0f}$ "
          f"tr/day={tpd:.2f} p={pval:.4f}")
    print("=" * 64)
    result = dict(n=nt, wr=s['win_rate'], exp=s['expectancy'], pnl=s['total_pnl'],
                  tpd=tpd, pval=pval)

    print("\nآموزش مدل نهایی (ensemble ۳-seed) روی کل داده برای صادرات ONNX...")
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
        m.fit(X, Y)
        models.append(m)
        onx = convert_lightgbm(m, initial_types=initial_type, zipmap=False, target_opset=12)
        p = os.path.join(os.path.dirname(__file__), f'xauusd_s25_model_{si}.onnx')
        with open(p, 'wb') as fp:
            fp.write(onx.SerializeToString())
        print(f"  مدل seed={sd} → {os.path.basename(p)} ({os.path.getsize(p)} bytes)")

    # اعتبارسنجی ONNX در برابر LightGBM (seed=42)
    sess = ort.InferenceSession(
        os.path.join(os.path.dirname(__file__), 'xauusd_s25_model_0.onnx'))
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
        ok = max_diff < 1e-4
        print(f"اعتبارسنجی ONNX: حداکثر اختلاف با LightGBM = {max_diff:.2e} "
              f"({'✅ OK' if ok else '⚠️'})")

    # متادیتا
    meta_path = os.path.join(os.path.dirname(__file__), 'model_meta_s25.txt')
    with open(meta_path, 'w') as fp:
        fp.write(f"THR={THR}\nHZ={HZ}\nTP_M={TP_M}\nSL_M={SL_M}\nBE={BE}\n")
        fp.write(f"WR={result['wr']:.2f}\nEXP={result['exp']:.4f}\nTPD={result['tpd']:.2f}\n")
        fp.write(f"PVAL={result['pval']:.4f}\nN_FEATURES={len(fc)}\nSEEDS={','.join(map(str,SEEDS))}\n")
    print(f"متادیتا: {os.path.basename(meta_path)}")

    fo_path = os.path.join(os.path.dirname(__file__), 'feature_order_s25.txt')
    with open(fo_path, 'w') as fp:
        for i, name in enumerate(fc):
            fp.write(f"{i}\t{name}\n")
    print(f"ترتیب feature: {os.path.basename(fo_path)} ({len(fc)} feature)")

    # فهرست feature ها را برای هماهنگ‌سازی TS چاپ کن
    print("\nترتیب کامل ۵۹ feature (برای features.ts):")
    print(fc)
    return result


if __name__ == '__main__':
    main()
