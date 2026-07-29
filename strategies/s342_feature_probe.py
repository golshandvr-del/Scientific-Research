# -*- coding: utf-8 -*-
"""
S342 — کاوشِ ویژگی‌ها: چرا لبهٔ LONG/ema55/N=21/r2>=0.35 فقط PF≈1.2 دارد؟
هدف: یافتنِ فیلترهایی که بردها را از باخت‌ها جدا کنند تا RQS+ از ۲۴ به ۸۰+ برسد.
(قانونِ بی‌نهایت بهبود + قانونِ جعبه‌ابزار docs/indicators/)
اجرا:  python3 -m strategies.s342_feature_probe XAUUSD M5
"""
import sys
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicator_bank as ib
from strategies.s342_scan import _run_above


def probe(asset, tf, slp=200, tpp=340):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    c = df['close'].to_numpy(float); h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    x = ib._c(df)
    ma = ib.ema_s(x, 55).to_numpy(float)
    run = _run_above(c, ma)
    r2 = ib.r2(df, p=21).to_numpy()
    atr = ib.atr_s(df, p=14).to_numpy()
    hu = ib.hurst(df, p=55).to_numpy()
    # اندیکاتورهای کاندیدِ فیلتر (جعبه‌ابزار)
    rsi = ib.compute('rsi', df).to_numpy() if 'rsi' in _safe_names() else None
    adx = _try(ib, 'adx', df)
    slope_lb = 5
    n_away = 21

    # ساختِ سیگنال‌های LONG پایه
    n = len(df)
    idxs = []
    for i in range(slope_lb + 2, n):
        if not (np.isfinite(r2[i]) and r2[i] >= 0.35):
            continue
        if not (np.isfinite(ma[i]) and np.isfinite(ma[i - slope_lb])):
            continue
        if ma[i] <= ma[i - slope_lb]:
            continue
        if run[i - 1] < n_away:
            continue
        if l[i] <= ma[i] and c[i - 1] > ma[i - 1]:
            idxs.append(i)

    print(f"# {asset} {tf}: {len(idxs)} base LONG signals")
    long_sig = np.zeros(n, bool); long_sig[idxs] = True
    tr = se.simulate_trades(df, long_sig, np.zeros(n, bool), sl_pip=slp, tp_pip=tpp,
                            asset=asset, max_hold=48, allow_overlap=False)
    tr = tr.reset_index(drop=True)
    print(f"# {len(tr)} trades taken; base WR={100*(tr.pnl_pip>0).mean():.1f}")

    # ویژگی‌ها روی signal_bar هر معامله
    feats = {}
    sb = tr['signal_bar'].to_numpy()
    feats['r2']        = r2[sb]
    feats['hurst']     = hu[sb]
    feats['run_len']   = run[sb - 1].astype(float)
    feats['pull_depth_atr'] = (c[sb] - ma[sb]) / atr[sb]      # عمقِ pullback نسبت به ATR (منفی=زیرِ MA)
    feats['ma_slope_atr']   = (ma[sb] - ma[sb - slope_lb]) / atr[sb]  # شیبِ روند نسبت به ATR
    feats['atr_norm']  = atr[sb] / c[sb] * 1000                # نوسانِ نسبی
    # فاصله از سقفِ ۵۰ کندلِ اخیر (test-of-high نزدیک‌تر؟)
    hh = pd.Series(h).rolling(50).max().to_numpy()
    feats['dist_from_hh_atr'] = (hh[sb] - c[sb]) / atr[sb]
    # ساعتِ روز
    hours = pd.to_datetime(df['time'], unit='s').dt.hour.to_numpy()
    feats['hour'] = hours[sb].astype(float)
    if adx is not None:
        feats['adx'] = adx[sb]

    win = (tr['pnl_pip'] > 0).to_numpy()
    print("\n# feature | win_mean | loss_mean | separation (|Δ|/std)")
    for name, v in feats.items():
        v = np.asarray(v, float)
        good = np.isfinite(v)
        wv = v[good & win]; lv = v[good & ~win]
        if len(wv) < 10 or len(lv) < 10:
            continue
        sd = np.nanstd(v[good]) or 1
        sep = abs(np.mean(wv) - np.mean(lv)) / sd
        print(f"{name:18s} | {np.mean(wv):8.3f} | {np.mean(lv):8.3f} | {sep:.3f}")

    # تستِ چند برشِ ساده روی قوی‌ترین ویژگی‌ها
    print("\n# quick filter cuts (WR & PF on subset):")
    for name in ['pull_depth_atr', 'dist_from_hh_atr', 'ma_slope_atr', 'run_len', 'hour', 'atr_norm']:
        v = np.asarray(feats[name], float)
        for q in [0.33, 0.5, 0.66]:
            thr = np.nanquantile(v, q)
            for direction in ['>=', '<=']:
                mask = (v >= thr) if direction == '>=' else (v <= thr)
                mask &= np.isfinite(v)
                if mask.sum() < 40:
                    continue
                sub = tr[mask]
                pos = sub.pnl_pip[sub.pnl_pip > 0].sum()
                neg = -sub.pnl_pip[sub.pnl_pip < 0].sum()
                pf = pos / neg if neg > 0 else 99
                wr = 100 * (sub.pnl_pip > 0).mean()
                if pf >= 1.5 and len(sub) >= 40:
                    print(f"  {name} {direction} {thr:.3f} | n={len(sub)} WR={wr:.1f} PF={pf:.2f} *")


def _safe_names():
    try:
        return set(ib.by_category('momentum') + ib.by_category('trend'))
    except Exception:
        return set()


def _try(mod, name, df):
    try:
        return mod.compute(name, df).to_numpy()
    except Exception:
        return None


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    probe(asset, tf)
