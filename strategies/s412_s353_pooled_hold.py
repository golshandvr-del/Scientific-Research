# -*- coding: utf-8 -*-
"""
S412 — احیای S353 XAUUSD-D1: ادغامِ رسمیِ ۵ واریانت + آزادسازیِ افقِ نگه‌داری
================================================================================
پیش‌ثبت: results/S412_PREREG_S353_POOLED_HOLD_RELEASE.md (کامیت 86233217)

مسئله: کارتِ ادغامیِ S353 (ممیزی: n=313، exp=+107.4، lift=+4.62، z=1.64) فقط
در p-value کم آورد (0.051 در برابر 0.001). ۱۴۱۸ سیگنالِ خام دارد ولی max_hold=24
روی D1 یعنی ۲۴ روز — قفلِ ضدهم‌پوشانی ۷۸٪ سیگنال‌ها را می‌بلعد. فرضیه: کوتاه‌کردنِ
افقِ نگه‌داری n را بزرگ می‌کند و z ∝ lift·√n را از 1.64 به سمتِ ۳σ می‌برد —
به شرطی که lift فرونریزد (اگر بریزد یعنی سود از دنبالهٔ hold طولانی بود؛ توقف).

مسیر C: این فایل فعلاً فقط tune روی نیمهٔ اول دارد. فاز نهایی پس از کامیتِ
فریزِ برنده اضافه می‌شود؛ نیمهٔ دوم تا آن لحظه باکره می‌ماند.
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
from engine import indicator_bank as ib
from strategies.s166_halftrend_heikenashi import signals

OUTDIR = os.path.join(ROOT, "results", "_scan_S412")
os.makedirs(OUTDIR, exist_ok=True)

SEED = 412
N_TRIALS = 1300          # حسابداری صادقانه (پیش‌ثبت §۲)
N_PERM_TUNE = 500        # K در tune (کف قابل‌داوری H3)

# ---------------- پایهٔ فریزشده (از کارتِ ادغامیِ ممیزی؛ هیچ tune ندارد) ----------------
AMPL = 2
ATR_P = 100
R2_P = 29
HURST_P = 55
SL_K = 2.0
ENT_P = 34
PCT_WIN = 233
# ۴ ترکیبِ گیتِ متمایزِ ۵ واریانتِ برتر (دوتایشان گیتِ یکسان با rr متفاوت داشتند)
GATES_POOL = [
    dict(r2_q=0.35, hurst_min=0.55, ent_q=1.00),
    dict(r2_q=0.50, hurst_min=0.50, ent_q=0.65),
    dict(r2_q=0.65, hurst_min=0.50, ent_q=0.65),
    dict(r2_q=0.50, hurst_min=0.55, ent_q=1.00),
]

# ---------------- فضای tune (پیش‌ثبت §۲ — ۸ سلول، فقط نیمهٔ اول) ----------------
HOLD_DAYS = [5, 8, 13, 21]
RR = [1.0, 1.5]

# شرایط صلاحیت (فریز پیش از دیدن نتایج)
QUAL_N_MIN = 100
QUAL_LIFT_MIN = 4.0


def _register(asset="XAUUSD"):
    se.ASSETS[asset] = dict(file=f"data/{asset}_D1.csv", pip=0.10,
                            contract=100.0, pip_value=10.0,
                            spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf="D1", asset="XAUUSD"):
    return se.load_data(os.path.join(ROOT, "data", f"{asset}_{tf}.csv"))


def bars_per_day(df):
    """اندازه‌گیریِ واقعی از داده (ضد BUG-TFM) — نه فرضِ عددی."""
    dt = pd.to_datetime(df["dt"])
    span_days = (dt.iloc[-1] - dt.iloc[0]).total_seconds() / 86400.0
    return len(df) / span_days


def atr_pip(df, p=ATR_P, pip=0.10):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    a = pd.Series(tr).rolling(p).mean().values
    return float(np.nanmedian(a) / pip)


def _pct_rank(s, win=PCT_WIN):
    return s.rolling(win).apply(lambda w: float((w <= w[-1]).mean()), raw=True)


def pooled_long_signal(df):
    """اجتماعِ سیگنال‌های لانگِ ۴ گیتِ فریزشده روی سیگنالِ خامِ HalfTrend."""
    long_raw, _ = signals(df, AMPL, ATR_P, True)
    long_raw = np.asarray(long_raw, dtype=bool)
    r2s = ib.r2(df, p=R2_P)
    hs = ib.hurst(df, p=HURST_P)
    ent = ib.entropy(df, p=ENT_P)
    r2_pct = _pct_rank(r2s)
    ent_pct = _pct_rank(ent)
    union = np.zeros(len(df), dtype=bool)
    for g in GATES_POOL:
        m = (r2_pct >= g["r2_q"]).fillna(False).values
        m &= (hs >= g["hurst_min"]).fillna(False).values
        if g["ent_q"] < 1.0:
            m &= (ent_pct <= g["ent_q"]).fillna(False).values
        union |= (long_raw & m)
    # ماسکِ «دروازه باز» برای مدلِ صفرِ gated (اجتماعِ گیت‌ها، بدون سیگنالِ خام)
    gate_any = np.zeros(len(df), dtype=bool)
    for g in GATES_POOL:
        m = (r2_pct >= g["r2_q"]).fillna(False).values
        m &= (hs >= g["hurst_min"]).fillna(False).values
        if g["ent_q"] < 1.0:
            m &= (ent_pct <= g["ent_q"]).fillna(False).values
        gate_any |= m
    return union, gate_any


def _perm_wr(df, asset, sl, tp, n_side, allowed_bars, rng, max_hold,
             n_perm=N_PERM_TUNE):
    n = len(df)
    if n_side < 1 or allowed_bars.size <= n_side:
        return None
    zero = np.zeros(n, dtype=bool)
    wrs = []
    for _ in range(n_perm):
        bars = rng.choice(allowed_bars, size=n_side, replace=False)
        sig = np.zeros(n, dtype=bool)
        sig[bars] = True
        tr = se.simulate_trades(df, sig, zero, sl, tp, asset,
                                max_hold=max_hold, allow_overlap=False)
        if tr is not None and len(tr) >= 1 and "outcome" in tr.columns:
            wrs.append(100.0 * float((tr["outcome"] == "win").mean()))
    if not wrs:
        return None
    a = np.asarray(wrs, dtype="float64")
    return dict(uncond_wr=float(a.mean()), perm_mean=float(a.mean()),
                perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()),
                perm_k=int(len(a)))


def build_null_dual(df, asset, sl, tp, n_long, gate, rng, max_hold):
    """نولِ دوگانهٔ سختگیرانهٔ خانوادهٔ S353: قوی‌ترِ uncond/gated (فقط لانگ)."""
    n = len(df)
    lo, hi = 260, n - max_hold - 1
    if hi <= lo:
        return None, {}
    all_bars = np.arange(lo, hi)
    g = np.zeros(n, dtype=bool)
    g[:min(n, len(gate))] = gate[:min(n, len(gate))]
    gated_bars = all_bars[g[all_bars]]
    cands = []
    u = _perm_wr(df, asset, sl, tp, n_long, all_bars, rng, max_hold)
    if u:
        cands.append(("uncond", u))
    if gated_bars.size > n_long:
        gd = _perm_wr(df, asset, sl, tp, n_long, gated_bars, rng, max_hold)
        if gd:
            cands.append(("gated", gd))
    if not cands:
        return None, {}
    tag, best = max(cands, key=lambda kv: kv[1]["uncond_wr"])
    null = {"long": best,
            "short": dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    diag = dict(chosen=tag, wrs={k: round(v["uncond_wr"], 2) for k, v in cands})
    return null, diag


def tune():
    asset = "XAUUSD"
    _register(asset)
    df_full = load()
    idx_split = len(df_full) // 2
    t_split = str(df_full["dt"].iloc[idx_split])
    df = df_full.iloc[:idx_split].reset_index(drop=True)
    bpd = bars_per_day(df_full)
    apip = atr_pip(df)
    sl = round(SL_K * apip, 1)
    print(f"[tune] first-half n_bars={len(df)} split@{t_split} "
          f"bars/day={bpd:.3f} ATR_pip={apip:.1f} SL={sl}", flush=True)

    union, gate_any = pooled_long_signal(df)
    print(f"[tune] pooled raw long signals (first half): {int(union.sum())}",
          flush=True)

    bar_time = df["dt"].values
    zero = np.zeros(len(df), dtype=bool)
    rng = np.random.default_rng(SEED)
    rows = []
    for hold_d, rr in itertools.product(HOLD_DAYS, RR):
        mh = max(1, int(round(hold_d * bpd)))
        tp = round(rr * sl, 1)
        tr = se.simulate_trades(df, union, zero, sl, tp, asset,
                                max_hold=mh, allow_overlap=False)
        if tr is None or len(tr) < 30:
            rows.append(dict(hold_d=hold_d, rr=rr, mh=mh, n=0, skipped=True))
            print(f"[cell] hold={hold_d}d rr={rr} → <30 trades, skip", flush=True)
            continue
        tr = tr.copy()
        tr["sl_pip"] = float(sl)
        n_long = int((tr["direction"] == "long").sum())
        null, ndiag = build_null_dual(df, asset, sl, tp, n_long, gate_any,
                                      rng, mh)
        res = rqs2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp,
                                bar_time=bar_time, null=null,
                                n_trials=N_TRIALS)
        m = res.get("metrics", {})
        exp = m.get("expectancy_pip")
        exp2c = m.get("expectancy_at_2x_cost")
        lift = m.get("skill_lift_pp")
        nn = m.get("n_trades")
        z = m.get("skill_z")
        qual = (exp2c is not None and exp2c > 0
                and lift is not None and lift >= QUAL_LIFT_MIN
                and nn is not None and nn >= QUAL_N_MIN)
        metric = (lift or -99.0) * ((nn or 0) ** 0.5)
        rows.append(dict(hold_d=hold_d, rr=rr, mh=mh, sl=sl, tp=tp,
                         n=nn, wr=m.get("win_rate"), pf=m.get("profit_factor"),
                         exp=exp, exp2c=exp2c, lift=lift, z=z,
                         verdict=res.get("verdict"), qualified=qual,
                         metric=round(metric, 2), null_diag=ndiag,
                         gates=res.get("gates")))
        print(f"[cell] hold={hold_d}d(mh={mh}) rr={rr} | n={nn} WR={m.get('win_rate')} "
              f"PF={m.get('profit_factor')} exp={exp} exp@2c={exp2c} "
              f"lift={lift} z={z} qual={qual} metric={metric:.1f}", flush=True)

    qualified = [r for r in rows if r.get("qualified")]
    winner = max(qualified, key=lambda r: r["metric"]) if qualified else None
    out = dict(seed=SEED, split_idx=idx_split, t_split=t_split,
               bars_per_day=round(bpd, 4), atr_pip=round(apip, 2), sl=sl,
               n_signals_first_half=int(union.sum()),
               cells=rows, n_qualified=len(qualified),
               winner=winner, stop_rule_fired=(winner is None))
    path = os.path.join(OUTDIR, "tune.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"[saved] {path}", flush=True)
    if winner:
        print(f"[WINNER] hold={winner['hold_d']}d rr={winner['rr']} "
              f"metric={winner['metric']}", flush=True)
    else:
        print("[STOP RULE] no qualifying cell — holdout stays virgin.", flush=True)
    return out


if __name__ == "__main__":
    tune()
