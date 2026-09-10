# -*- coding: utf-8 -*-
"""
S414 — بازداوریِ تأییدیِ S344 (Brooks Trend-from-Open, XAUUSD-M15 SHORT) روی mt5_full
پیش‌ثبت: results/S414_PREREG_S344_TFO_FULLDATA_CONFIRMATORY.md (کامیت 82602c91)
هیچ tune. دو بازوی هندسه (A لفظی، B نرمال‌شده با ATR — حاکم). holdout = پنجرهٔ بکرِ
پیش از 2020-02-20. نول = قوی‌ترِ (بی‌قید, درونِ گیتِ r2h)، K=500، هم‌هندسه.
"""
import os, sys, json, time
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import rqs2
from engine import indicator_bank as ib
from strategies.s344_brooks_trend_from_open import trend_from_open_signals

OUT = os.path.join(ROOT, "results", "_scan_S414"); os.makedirs(OUT, exist_ok=True)
SEED = 414; K = 500; N_TRIALS = 79
ASSET, TF = "XAUUSD", "M15"
SPLIT_T = pd.Timestamp("2020-02-20")
MH = 32
SL_A, TP_A = 220.0, 340.0
RR = TP_A / SL_A
ATR_P = 100; PIP = 0.10
# S344 frozen signal params
SIG = dict(n_open=4, f_range=0.20, pull_max=0.62, min_spike_frac=0.20)


def load():
    src = os.path.join(ROOT, "data", "mt5_full", f"{ASSET}_{TF}.csv")
    assert "mt5_full" in src
    se.ASSETS[ASSET] = dict(file=src, pip=PIP, contract=100.0, pip_value=10.0,
                            spread_pip=3.3, comm=0.0, slip_pip=0.0)
    df = se.load_data(src)
    return df, src


def atr100_pip(df):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    a = pd.Series(tr).rolling(ATR_P).mean().shift(1).values / PIP   # علّی
    return a


def regime_r2h(df):
    r2 = ib.r2(df, p=34).to_numpy(); hu = ib.hurst(df, p=55).to_numpy()
    return (r2 >= 0.30) & (hu >= 0.52) & np.isfinite(r2) & np.isfinite(hu)


def perm_wr(df, sl_arr, tp_arr, n_side, allowed, rng, k=K):
    n = len(df); zero = np.zeros(n, bool); wrs = []
    for _ in range(k):
        bars = rng.choice(allowed, size=n_side, replace=False)
        sig = np.zeros(n, bool); sig[bars] = True
        tr = se.simulate_trades(df, zero, sig, sl_arr, tp_arr, ASSET,
                                max_hold=MH, allow_overlap=False)
        if tr is not None and len(tr):
            wrs.append(100.0 * float((tr["outcome"] == "win").mean()))
    a = np.asarray(wrs, float)
    return dict(uncond_wr=float(a.mean()), perm_mean=float(a.mean()),
                perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()), perm_k=int(len(a)))


def build_null(df, sl_arr, tp_arr, n_short, gate, rng, valid):
    n = len(df); all_bars = np.arange(300, n - MH - 1)
    all_bars = all_bars[valid[all_bars]]
    gate_bars = all_bars[gate[all_bars]]
    c = {"uncond": perm_wr(df, sl_arr, tp_arr, n_short, all_bars, rng)}
    if gate_bars.size > n_short:
        c["gated_r2h"] = perm_wr(df, sl_arr, tp_arr, n_short, gate_bars, rng)
    tag = max(c, key=lambda k: c[k]["uncond_wr"])
    empty = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)
    return {"long": empty, "short": c[tag]}, dict(chosen=tag, wrs={k: round(v["uncond_wr"], 2) for k, v in c.items()})


def judge(arm, df, sig, sl_arr, tp_arr, gate, valid, src):
    t0 = time.time()
    zero = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, zero, sig, sl_arr, tp_arr, ASSET, max_hold=MH, allow_overlap=False)
    tr = tr.copy()
    sl_med = float(np.median(tr["sl_pip"])) if "sl_pip" in tr.columns else float(np.median(sl_arr[tr["entry_bar"].values - 1]))
    tp_med = sl_med * RR
    tr["sl_pip"] = sl_arr[(tr["entry_bar"].values - 1).clip(0)] if "sl_pip" not in tr.columns else tr["sl_pip"]
    n_short = int(len(tr))
    rng = np.random.default_rng(SEED)
    null, ndiag = build_null(df, sl_arr, tp_arr, n_short, gate, rng, valid)
    bar_time = df["dt"].values
    entry_t = pd.to_datetime(bar_time[tr["entry_bar"].values])
    hold = (entry_t < SPLIT_T).values          # پنجرهٔ بکر = خارج‌ازنمونه
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                            null=null, n_trials=N_TRIALS, holdout_mask=hold,
                            close=df["close"].values)
    m = res.get("metrics", {})
    # آمارِ جداگانهٔ پنجرهٔ بکر / دیده‌شده (اطلاع‌رسان)
    def part(mask):
        s = tr[mask]
        return dict(n=int(len(s)), wr=round(100 * float((s["outcome"] == "win").mean()), 2) if len(s) else None,
                    pnl_pip=round(float(s["pnl_pip"].sum()), 1) if len(s) else None)
    out = dict(arm=arm, src=src, n_bars=int(len(df)), span=[str(df["dt"].iloc[0]), str(df["dt"].iloc[-1])],
               n_signals=int(sig.sum()), n_trades=n_short, sl_pip_med=round(sl_med, 1), tp_pip_med=round(tp_med, 1),
               mh=MH, seed=SEED, K=K, n_trials=N_TRIALS, null=null["short"], null_diag=ndiag,
               virgin_pre2020=part(hold), seen_post2020=part(~hold),
               verdict=res.get("verdict"), score=res.get("rqs2_score"), gates=res.get("gates"),
               notes=res.get("notes"), metrics=m, elapsed_s=round(time.time() - t0, 1))
    with open(os.path.join(OUT, f"arm_{arm}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n[{arm}] {res.get('verdict')} RQS2={res.get('rqs2_score')} | n={m.get('n_trades')} WR={m.get('win_rate')} "
          f"PF={m.get('profit_factor')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p={m.get('skill_p_perm')} "
          f"exp={m.get('expectancy_pip')} exp2c={m.get('expectancy_at_2x_cost')} oos={m.get('oos')}")
    print(f"      gates={res.get('gates')} null={ndiag} virgin={out['virgin_pre2020']} seen={out['seen_post2020']}", flush=True)
    return out


def main():
    df, src = load()
    print(f"[data] {src} bars={len(df)} {df['dt'].iloc[0]} → {df['dt'].iloc[-1]}", flush=True)
    sig = trend_from_open_signals(df, TF, "short", **SIG)
    gate = regime_r2h(df)
    sig_g = sig & gate
    print(f"[sig] raw={int(sig.sum())} gated(r2h)={int(sig_g.sum())} gate_pass={gate.mean():.3f}", flush=True)
    atr = atr100_pip(df); valid = np.isfinite(atr) & (atr > 0)
    n = len(df)
    # بازوی A — لفظی
    slA = np.full(n, SL_A); tpA = np.full(n, TP_A)
    # بازوی B — نرمال‌شده: k_sl از پنجرهٔ دیده‌شده (فرمولی، طبق پیش‌ثبت)
    seen = (df["dt"] >= SPLIT_T).values
    atr_med_seen = float(np.nanmedian(atr[seen]))
    k_sl = SL_A / atr_med_seen
    slB = np.where(valid, k_sl * atr, np.nan); tpB = slB * RR
    slB = np.nan_to_num(slB, nan=0.0); tpB = np.nan_to_num(tpB, nan=0.0)
    print(f"[geom] ATR100_med(seen)={atr_med_seen:.2f} k_sl={k_sl:.3f} RR={RR:.3f}", flush=True)
    sig_g = sig_g & valid
    outs = {}
    outs["B"] = judge("B", df, sig_g, slB, tpB, gate, valid, src)
    outs["A"] = judge("A", df, sig_g, slA, tpA, gate, valid, src)
    summ = dict(k_sl=round(k_sl, 3), atr_med_seen=round(atr_med_seen, 2),
                governing="B", verdict_official=outs["B"]["verdict"], score_official=outs["B"]["score"],
                A=dict(verdict=outs["A"]["verdict"], score=outs["A"]["score"]))
    json.dump(summ, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    print("[summary]", summ, flush=True)


if __name__ == "__main__":
    main()
