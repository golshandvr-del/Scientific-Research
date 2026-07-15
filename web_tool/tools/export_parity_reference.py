"""
صادرات مرجع parity برای ابزار وب (اجرای واقعی ONNX در مرورگر).
=================================================================
این اسکریپت روی همان داده‌ی XAUUSD_M15.csv:
1. آخرین N کندل را برمی‌دارد (به‌همراه کل تاریخچه برای محاسبه اندیکاتورها).
2. ۵۷ feature را دقیقاً با engine/features.py می‌سازد.
3. احتمال ensemble ۳-seed ONNX را محاسبه می‌کند.
4. همه را در web_tool/tools/parity_reference.json ذخیره می‌کند.

خروجی مرجع طلایی است تا پیاده‌سازی TypeScript (buildFeatures + onnxruntime-web)
در برابر آن اعتبارسنجی شود و تضمین کند سیگنال مرورگر «دقیقاً معادل ربات» است.
"""
import sys, os, json
HERE = os.path.dirname(__file__)
ENGINE = os.path.join(HERE, '..', '..', 'engine')
ROBOT = os.path.join(HERE, '..', '..', 'mt5_robot')
sys.path.insert(0, ENGINE)
import numpy as np
import pandas as pd
import indicators as ind
from backtest import load_data
from features import build_features
import onnxruntime as ort
import warnings; warnings.filterwarnings('ignore')

DATA = os.path.join(HERE, '..', '..', 'data', 'XAUUSD_M15.csv')
N_EXPORT = 8   # چند کندل آخر را به‌عنوان مرجع صادر کنیم
SEEDS_MODELS = [
    os.path.join(ROBOT, 'xauusd_s14_model_0.onnx'),
    os.path.join(ROBOT, 'xauusd_s14_model_1.onnx'),
    os.path.join(ROBOT, 'xauusd_s14_model_2.onnx'),
]


def ensemble_proba(X):
    """میانگین احتمال کلاس ۱ روی ۳ مدل ONNX (دقیقاً منطق ربات)."""
    probs = []
    for mp in SEEDS_MODELS:
        sess = ort.InferenceSession(mp)
        in_name = sess.get_inputs()[0].name
        out = sess.run(None, {in_name: X.astype(np.float32)})
        p = None
        for arr in out:
            a = np.array(arr)
            if a.ndim == 2 and a.shape[1] == 2:
                p = a[:, 1]; break
        probs.append(p)
    return np.mean(np.vstack(probs), axis=0)


def main():
    df = load_data(DATA)
    feats = build_features(df)
    fc = list(feats.columns)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    cv = df['close'].values

    valid = feats.dropna()
    tail_idx = valid.tail(N_EXPORT).index.tolist()

    X_all = valid[fc].values.astype(np.float32)
    p_all = ensemble_proba(X_all)
    # نگاشت اندیس‌های tail به موقعیت در valid
    pos = {idx: k for k, idx in enumerate(valid.index.tolist())}

    rows = []
    for idx in tail_idx:
        row = feats.loc[idx]
        features = {name: float(row[name]) for name in fc}
        cand = bool((cv[idx] > ema50[idx]) and (ema50[idx] > ema200[idx]))
        prob = float(p_all[pos[idx]])
        rows.append({
            'idx': int(idx),
            'time': int(df.loc[idx, 'time']),
            'dt': str(df.loc[idx, 'dt']),
            'close': float(df.loc[idx, 'close']),
            'cand_regime': cand,          # فیلتر رژیم پایه S14
            'ensemble_proba': prob,       # احتمال ensemble (کلاس long-win)
            'signal_long': bool(cand and prob >= 0.68),
            'features': features,
        })

    out = {
        'feature_order': fc,
        'n_features': len(fc),
        'threshold': 0.68,
        'note': 'مرجع طلایی: feature + احتمال ensemble ۳-seed ONNX برای اعتبارسنجی TS',
        'rows': rows,
    }
    outpath = os.path.join(HERE, 'parity_reference.json')
    with open(outpath, 'w') as fp:
        json.dump(out, fp, indent=2, ensure_ascii=False)
    print(f"صادر شد: {outpath}")
    print(f"تعداد feature: {len(fc)} | کندل‌های مرجع: {len(rows)}")
    for r in rows:
        print(f"  idx={r['idx']} dt={r['dt']} close={r['close']:.2f} "
              f"cand={r['cand_regime']} proba={r['ensemble_proba']:.4f} "
              f"signal={r['signal_long']}")


if __name__ == '__main__':
    main()
