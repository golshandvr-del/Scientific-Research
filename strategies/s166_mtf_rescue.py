# -*- coding: utf-8 -*-
"""
S166-MTF — آزمونِ نجاتِ چند-تایم‌فریمیِ HalfTrend flip + Heiken Ashi
================================================================================
انگیزه (ضدِ اشتباهاتِ رایجِ #۱، #۵، #۶):
S166 در نسخهٔ اول **فقط روی M15** آزموده و رد شد؛ علتِ شکست «over-trading»
(۸۰۰۰+ معامله) بود. اما یک سیستمِ trend-following که روی M15 بیش‌ازحد معامله
می‌کند، ممکن است روی تایم‌فریم‌های **بالاتر** (H4/D1/W1) — که سیگنالِ کم‌تر و
روندِ تمیزتر دارند — رفتارِ کاملاً متفاوتی داشته باشد. درست مثلِ S351 که M5
بازنده ولی D1 برنده بود. پس طبقِ قانونِ MTF، این‌جا همهٔ تایم‌فریم‌ها آزموده
می‌شوند، و SL/TP به‌جای عددِ ثابت، **بر حسبِ ATRِ هر تایم‌فریم** مقیاس می‌شود
(ضدِ اشتباهِ #۶: TP/SL یکسان برای همهٔ TFها ممنوع).

روش:
  • برای هر (asset ∈ {XAUUSD, EURUSD}) × (tf ∈ {M5,M15,M30,H1,H4,D1,W1}):
      – HalfTrend flip + HA filter (همان `signals` از s166 اصلی).
      – SL = k_sl · median(ATR14) بر حسبِ pip؛ TP = rr · SL (چند rr).
      – هر دو جهت (long/short) و long-only و short-only.
  • داوری با `compute_rqs2` (موتورِ دست‌نخورده).
  • طبقِ «قانونِ اندک اندک»: هر TF بلافاصله در JSON چک‌پوینت می‌شود.

خروجی: results/_scan_S166/<asset>_<tf>.json  (یکی به‌ازای هر کارت)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs2
from strategies.s166_halftrend_heikenashi import signals

OUTDIR = os.path.join(ROOT, "results", "_scan_S166")
os.makedirs(OUTDIR, exist_ok=True)

CAPITAL = 10_000.0

# پایه‌های دارایی (pip/contract/هزینه) — مستقل از تایم‌فریم.
ASSET_BASE = {
    "XAUUSD": dict(pip=0.10,   contract=100.0,     pip_value=10.0,
                   spread_pip=3.3, comm=0.0, slip_pip=0.0),
    "EURUSD": dict(pip=0.0001, contract=100_000.0, pip_value=10.0,
                   spread_pip=1.0, comm=0.0, slip_pip=0.3),
}
TFS = ["M5", "M15", "M30", "H1", "H4", "D1", "W1"]

# هندسهٔ ATR-محور (ضدِ اشتباهِ #۶): SL کسری از ATR، TP چند برابرِ SL.
SL_K = [1.0, 1.5, 2.0]          # ضریبِ ATR برای SL
RR = [1.0, 1.5, 2.0]            # نسبتِ TP/SL
AMPL = [2, 3]                   # amplitude برای HalfTrend
ATR_P = 100                     # دورهٔ ATR در HalfTrend (ثابت، causal)
MAX_HOLD = 24


def _register_asset(asset, tf):
    """asset را با فایلِ تایم‌فریمِ خواسته‌شده در ASSETS موتور ثبت می‌کند."""
    base = ASSET_BASE[asset]
    key = f"{asset}"
    se.ASSETS[key] = dict(file=f"data/{asset}_{tf}.csv", **base)
    return key


def _load(asset, tf):
    path = os.path.join(ROOT, f"data/{asset}_{tf}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def _atr_pip(df, asset, period=14):
    """میانهٔ ATR بر حسبِ pip — پایهٔ مقیاسِ SL/TP برای این تایم‌فریم."""
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = pd.Series(tr).rolling(period, min_periods=1).mean().to_numpy()
    pip = ASSET_BASE[asset]["pip"]
    return float(np.nanmedian(atr) / pip)


def judge_card(asset, tf):
    df = _load(asset, tf)
    if df is None or len(df) < 300:
        return dict(asset=asset, tf=tf, skip="no data or too few bars")
    key = _register_asset(asset, tf)
    atr_pip = _atr_pip(df, asset)

    best = None
    variants = []
    for ampl in AMPL:
        long_sig, short_sig = signals(df, ampl, ATR_P, use_ha=True)
        z = np.zeros(len(df), dtype=bool)
        for side, (ls, ss) in [("long", (long_sig, z)),
                               ("short", (z, short_sig)),
                               ("both", (long_sig, short_sig))]:
            for k in SL_K:
                sl = max(1.0, round(k * atr_pip, 1))
                for rr in RR:
                    tp = round(rr * sl, 1)
                    tr = se.simulate_trades(df, ls, ss, sl, tp, key,
                                            max_hold=MAX_HOLD, allow_overlap=False)
                    if tr is None or len(tr) < 20:
                        continue
                    tr = tr.copy()
                    tr["sl_pip"] = float(sl)
                    bar_time = df["dt"].values
                    res = rqs2.compute_rqs2(tr, key, sl_pip=sl, tp_pip=tp,
                                            bar_time=bar_time)
                    rec = dict(ampl=ampl, side=side, sl=sl, tp=tp, rr=rr,
                               n=res.get("n_trades"), wr=res.get("win_rate"),
                               pf=res.get("profit_factor"),
                               net=res.get("net_usd") if "net_usd" in res else None,
                               rqs2=res.get("score"), verdict=res.get("verdict"),
                               lift=res.get("skill_lift_pp"), z=res.get("skill_z"),
                               power_limited=res.get("power_limited"))
                    variants.append(rec)
                    key_metric = (res.get("verdict") == "ACCEPT",
                                  res.get("score") or 0.0)
                    if best is None or key_metric > best["_key"]:
                        rec2 = dict(rec)
                        rec2["_key"] = key_metric
                        best = rec2

    out = dict(asset=asset, tf=tf, atr_pip=round(atr_pip, 1),
               n_variants=len(variants), best=best, variants=variants)
    return out


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    order = []
    # ترتیب: طلا اول (طبقِ قانون MTF: از XAUUSD/M... شروع), سپس یورو.
    for asset in ["XAUUSD", "EURUSD"]:
        for tf in TFS:
            order.append((asset, tf))
    for asset, tf in order:
        card = f"{asset}_{tf}"
        if only and card not in only:
            continue
        print(f"[run] {card} ...", flush=True)
        out = judge_card(asset, tf)
        fp = os.path.join(OUTDIR, f"{card}.json")
        with open(fp, "w") as f:
            json.dump(out, f, ensure_ascii=False, indent=2, default=str)
        b = out.get("best")
        if b:
            print(f"[done] {card} | best verdict={b['verdict']} "
                  f"RQS2={b['rqs2']} n={b['n']} WR={b['wr']} PF={b['pf']} "
                  f"lift={b['lift']} z={b['z']} side={b['side']} "
                  f"sl={b['sl']} tp={b['tp']}", flush=True)
        else:
            print(f"[done] {card} | {out.get('skip','no valid variant')}",
                  flush=True)


if __name__ == "__main__":
    main()
