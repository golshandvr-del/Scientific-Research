# -*- coding: utf-8 -*-
"""
S413 — احیای «رانش دوشنبه» (S140) زیر RQS2 v2.6 — XAUUSD, mt5_full
================================================================================
پیش‌ثبت: results/S413_PREREG_MONDAY_DRIFT_REVIVAL.md (کامیت ccd13d47)

رویداد: کندل Monday & hour==H_start (وقت سرور) → LONG در open کندل بعد.
هندسه: SL=TP=1.5×ATR100 همان TF (متقارن). خروج زمانی hold_h ساعت.
نول سختگیرانهٔ متعامد: قوی‌ترِ (uncond) و (same-hour، روزهای سه‌شنبه..جمعه) —
تا اثرِ «ساعتِ روز» از اثرِ «دوشنبه‌بودن» جدا شود.

فاز ۱ (این فایل): tune فقط روی نیمهٔ اول (2011→~2018). فاز نهایی بعد از
کامیتِ فریزِ برنده اضافه می‌شود.
"""
import os
import sys
import json
import itertools
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs2

OUTDIR = os.path.join(ROOT, "results", "_scan_S413")
os.makedirs(OUTDIR, exist_ok=True)

SEED = 413
N_TRIALS = 450
K_TUNE = 500
ATR_P = 100
SLTP_K = 1.5          # فریز پیشینی — متقارن (SL=TP)

H_START = [17, 18, 19]
HOLD_H = [4, 8, 24]

QUAL = dict(n_min=150, lift_min=4.0, z_min=2.0)


def register(asset="XAUUSD", tf="H1"):
    se.ASSETS[asset] = dict(file=f"data/mt5_full/XAUUSD_{tf}.csv", pip=0.10,
                            contract=100.0, pip_value=10.0,
                            spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf="H1"):
    src = os.path.join(ROOT, "data", "mt5_full", f"XAUUSD_{tf}.csv")
    assert "mt5_full" in src  # تلهٔ E-16
    return se.load_data(src)


def bars_per_hour(df):
    dt = pd.to_datetime(df["dt"])
    span_h = (dt.iloc[-1] - dt.iloc[0]).total_seconds() / 3600.0
    return len(df) / span_h


def atr_pip(df, p=ATR_P, pip=0.10):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.nanmedian(pd.Series(tr).rolling(p).mean().values) / pip)


def event_mask(df, h_start, weekday=0):
    d = pd.to_datetime(df["dt"])
    return ((d.dt.weekday == weekday) & (d.dt.hour == h_start)).values


def _perm_wr(df, asset, sl, tp, n_side, allowed, rng, mh, k=K_TUNE):
    n = len(df)
    if n_side < 1 or allowed.size <= n_side:
        return None
    zero = np.zeros(n, dtype=bool)
    wrs = []
    for _ in range(k):
        bars = rng.choice(allowed, size=n_side, replace=False)
        sig = np.zeros(n, dtype=bool)
        sig[bars] = True
        tr = se.simulate_trades(df, sig, zero, sl, tp, asset,
                                max_hold=mh, allow_overlap=False)
        if tr is not None and len(tr) >= 1 and "outcome" in tr.columns:
            wrs.append(100.0 * float((tr["outcome"] == "win").mean()))
    if not wrs:
        return None
    a = np.asarray(wrs, dtype="float64")
    return dict(uncond_wr=float(a.mean()), perm_mean=float(a.mean()),
                perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()),
                perm_k=int(len(a)))


def build_null_orthogonal(df, asset, sl, tp, n_long, h_start, rng, mh):
    """قوی‌ترِ دو نول: بی‌قید / همان-ساعت-روزهای-دیگر (سه‌شنبه..جمعه)."""
    n = len(df)
    lo, hi = 260, n - mh - 1
    all_bars = np.arange(lo, hi)
    d = pd.to_datetime(df["dt"])
    same_hour_other = ((d.dt.hour == h_start)
                       & (d.dt.weekday >= 1) & (d.dt.weekday <= 4)).values
    sh_bars = all_bars[same_hour_other[all_bars]]
    cands = []
    u = _perm_wr(df, asset, sl, tp, n_long, all_bars, rng, mh)
    if u:
        cands.append(("uncond", u))
    if sh_bars.size > n_long:
        s = _perm_wr(df, asset, sl, tp, n_long, sh_bars, rng, mh)
        if s:
            cands.append(("same_hour_other_days", s))
    if not cands:
        return None, {}
    tag, best = max(cands, key=lambda kv: kv[1]["uncond_wr"])
    null = {"long": best,
            "short": dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    return null, dict(chosen=tag,
                      wrs={k: round(v["uncond_wr"], 2) for k, v in cands})


def tune(tf="H1"):
    asset = "XAUUSD"
    register(asset, tf)
    df_full = load(tf)
    idx_split = len(df_full) // 2
    t_split = str(df_full["dt"].iloc[idx_split])
    df = df_full.iloc[:idx_split].reset_index(drop=True)
    bph = bars_per_hour(df_full)
    apip = atr_pip(df)
    sl = round(SLTP_K * apip, 1)
    print(f"[tune] {tf} first-half bars={len(df)} split@{t_split} "
          f"bars/h={bph:.3f} ATR_pip={apip:.1f} SL=TP={sl}", flush=True)

    bar_time = df["dt"].values
    zero = np.zeros(len(df), dtype=bool)
    rng = np.random.default_rng(SEED)
    rows = []
    for h_start, hold_h in itertools.product(H_START, HOLD_H):
        mh = max(1, int(round(hold_h * bph)))
        sig = event_mask(df, h_start)
        tr = se.simulate_trades(df, sig, zero, sl, sl, asset,
                                max_hold=mh, allow_overlap=False)
        if tr is None or len(tr) < 30:
            rows.append(dict(h_start=h_start, hold_h=hold_h, mh=mh, n=0,
                             skipped=True))
            continue
        tr = tr.copy()
        tr["sl_pip"] = float(sl)
        n_long = int((tr["direction"] == "long").sum())
        null, ndiag = build_null_orthogonal(df, asset, sl, sl, n_long,
                                            h_start, rng, mh)
        res = rqs2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=sl,
                                bar_time=bar_time, null=null,
                                n_trials=N_TRIALS)
        m = res.get("metrics", {})
        nn, lift, z = m.get("n_trades"), m.get("skill_lift_pp"), m.get("skill_z")
        exp2c = m.get("expectancy_at_2x_cost")
        qual = (exp2c is not None and exp2c > 0
                and lift is not None and lift >= QUAL["lift_min"]
                and nn is not None and nn >= QUAL["n_min"]
                and z is not None and z >= QUAL["z_min"])
        metric = (lift or -99.0) * ((nn or 0) ** 0.5)
        rows.append(dict(h_start=h_start, hold_h=hold_h, mh=mh, sl=sl,
                         n=nn, wr=m.get("win_rate"), pf=m.get("profit_factor"),
                         exp=m.get("expectancy_pip"), exp2c=exp2c,
                         lift=lift, z=z, verdict=res.get("verdict"),
                         qualified=qual, metric=round(metric, 2),
                         null_diag=ndiag))
        print(f"[cell] H{h_start} hold={hold_h}h(mh={mh}) | n={nn} "
              f"WR={m.get('win_rate')} PF={m.get('profit_factor')} "
              f"exp2c={exp2c} lift={lift} z={z} null={ndiag.get('chosen')} "
              f"qual={qual}", flush=True)

    qualified = [r for r in rows if r.get("qualified")]
    winner = max(qualified, key=lambda r: r["metric"]) if qualified else None
    out = dict(seed=SEED, tf=tf, split_idx=idx_split, t_split=t_split,
               bars_per_hour=round(bph, 4), atr_pip=round(apip, 2), sl=sl,
               cells=rows, n_qualified=len(qualified), winner=winner,
               stop_rule_fired=(winner is None))
    path = os.path.join(OUTDIR, "tune.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"[saved] {path}", flush=True)
    print(("[WINNER] " + json.dumps({k: winner[k] for k in
           ('h_start', 'hold_h', 'metric')})) if winner else
          "[STOP RULE] no qualifying cell — holdout stays virgin.", flush=True)
    return out


if __name__ == "__main__":
    tune()
