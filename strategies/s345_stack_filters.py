# -*- coding: utf-8 -*-
"""
S345 — انباشتِ فیلترها (قانونِ همکاریِ بهبودها + قانونِ بی‌نهایت + جعبه‌ابزارِ ۴۰۱ اندیکاتوری).

یافتهٔ probeِ قبلی: حذفِ زیرمجموعهٔ **Turn-of-Month** (روزِ ۱–۳ ماه، همپوشان با S141)
RQS+ لایهٔ XAU-M15-long را از ۸۹.۸ به **۹۰.۷** برد (WR ۶۱.۰۶→۶۲.۳۸، PF ۲.۲۰→۲.۳۰)
در حالی که حذفِ دوشنبه (S140) آن را **بدتر** کرد ⇒ همپوشانی **یکنواخت نیست**.

این اسکریپت دو کارِ علمی می‌کند:
  (الف) **انباشتِ چندفیلتریِ حریصانه (greedy stacking)** روی جعبه‌ابزارِ بانک:
        از پایهٔ بهبودیافته (drop_TOM) شروع می‌کند و در هر دور، مؤثرترین فیلترِ بعدی
        را از میانِ دهه‌ها کاندید (اندیکاتورهای بانک با دوره‌های **Lucas/Fibonacci
        غیررند** — پادزهرِ اشتباهِ #۷) اضافه می‌کند؛ تا وقتی RQS+ بالا می‌رود.
  (ب) **احیای M30** که فقط `G4` را می‌شکند (n=۴۷): آیا فیلترِ کیفیتی، پنجره‌های
        walk-forward را مثبت می‌کند؟

قیدهای سخت:
  * TP > SL همیشه (ضدِ اشتباهِ #۸) — TP/SL دست‌نخورده از پایه می‌آید.
  * حداقلِ n پس از هر فیلتر ≥ ۴۵ (تا G4/G1 معنا داشته باشد) — از قربانی‌کردنِ
    نمونه برای WRِ آرایشی جلوگیری می‌کند.

اجرا: PYTHONPATH=. python3 strategies/s345_stack_filters.py [M15|M30]
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib
from strategies.s345_brooks_reversal_day import reversal_day_signals, load_tf
from strategies.s345_overlap_validate import regime_mask, eval_sig

OUT_DIR = os.path.join(ROOT, "results", "_scan_S345")

BASE = {
    "M15": dict(asset="XAUUSD", tf="M15", side="long", n_open=4, k_spike=1.1,
                slope_min=0.05, win=(0.40, 0.95), reg="r2_lo", sl=240, tp=400,
                maxhold=40, min_n=45),
    "M30": dict(asset="XAUUSD", tf="M30", side="long", n_open=4, k_spike=1.1,
                slope_min=0.05, win=(0.40, 0.95), reg=None, sl=270, tp=460,
                maxhold=28, min_n=40),
}


def build_candidates(df):
    """کاندیدهای فیلتر از بانکِ ۴۰۱ اندیکاتوری + فیلترهای تقویمی/ساختاری.
    آستانه‌ها **غیررند** و دوره‌ها **Lucas/Fibonacci** (ضدِ اشتباهِ #۷)."""
    n = len(df)
    dt = pd.DatetimeIndex(pd.to_datetime(df["time"], unit="s"))
    cands = {}

    def add(name, mask):
        m = np.asarray(mask, bool)
        if 0.05 * n < m.sum() < 0.98 * n:      # فیلترِ بی‌اثر/خیلی سخت را دور بریز
            cands[name] = m

    def bank(name, fn, label=None):
        try:
            v = ib.compute(name, df).to_numpy(dtype=float)
        except Exception:
            return
        try:
            add(label or name, fn(v) & np.isfinite(v))
        except Exception:
            pass

    # --- تقویمی/ساختاری (زیرمجموعه‌های همپوشانِ لایه‌های موجود) ---
    add("drop_TOM(dom>3)", dt.day > 3)
    add("drop_dom_10_13_20", ~np.isin(dt.day, [10, 13, 20]))
    add("drop_preEOM", ~(((dt.days_in_month - dt.day) >= 6) & ((dt.days_in_month - dt.day) <= 8)))
    add("drop_friday", dt.dayofweek != 4)
    add("keep_mon_tue_wed", np.isin(dt.dayofweek, [0, 1, 2]))

    # --- رژیم/کیفیتِ آماری (دوره‌های fib/lucas) ---
    for p in ["r2_fib_21", "r2_fib_34", "r2_fib_55"]:
        bank(p, lambda v: v <= 0.47, f"{p}<=0.47")
        bank(p, lambda v: v <= 0.62, f"{p}<=0.62")
    bank("hurst", lambda v: v <= 0.47, "hurst<=0.47")
    bank("hurst", lambda v: v >= 0.43, "hurst>=0.43")
    for p in ["chop_fib_13", "chop_fib_21", "chop_fib_34"]:
        bank(p, lambda v: v >= 43.0, f"{p}>=43")
        bank(p, lambda v: v >= 51.0, f"{p}>=51")

    # --- مومنتوم/خستگی (کلیدِ reversal طبقِ docs/indicators/momentum.md) ---
    for p in ["rsi_lucas_11", "rsi_lucas_18", "rsi_lucas_29", "rsi_lucas_47"]:
        bank(p, lambda v: v <= 43.0, f"{p}<=43")     # فروشِ افراطی ⇒ چرخشِ صعودی
        bank(p, lambda v: v <= 37.0, f"{p}<=37")
    for p in ["cmo_fib_13", "cmo_fib_21", "cmo_fib_34"]:
        bank(p, lambda v: v <= -13.0, f"{p}<=-13")
    bank("fisher", lambda v: v <= -0.7, "fisher<=-0.7")
    bank("tsi", lambda v: v <= -7.0, "tsi<=-7")
    bank("bop", lambda v: v >= 0.07, "bop>=0.07")    # فشارِ خریدارِ تازه
    bank("kdj_j", lambda v: v <= 23.0, "kdj_j<=23")
    bank("mfi", lambda v: v <= 43.0, "mfi<=43")

    # --- کارایی/کشش (Efficiency Ratio با دوره‌های Lucas) ---
    for p in ["er_lucas_11", "er_lucas_18", "er_lucas_29"]:
        bank(p, lambda v: v <= 0.31, f"{p}<=0.31")
        bank(p, lambda v: v >= 0.11, f"{p}>=0.11")

    # --- نوسان (اندازهٔ حرکت باید کافی باشد) ---
    bank("atr_pct", lambda v: v >= 0.07, "atr_pct>=0.07")
    for p in ["atr_fib_13", "atr_fib_21"]:
        bank(p, lambda v: v >= np.nanmedian(v) * 0.83, f"{p}>=0.83med")

    # --- جهت/ساختار (تأییدِ چرخش) ---
    bank("vortex", lambda v: v >= -0.13, "vortex>=-0.13")
    bank("aroon", lambda v: v <= -13.0, "aroon<=-13")   # کف‌های تازه ⇒ آمادهٔ چرخش
    bank("adx", lambda v: v >= 21.0, "adx>=21")
    bank("adx", lambda v: v <= 43.0, "adx<=43")
    bank("ema_dist_atr", lambda v: v <= -0.43, "ema_dist_atr<=-0.43")  # زیرِ EMA کش‌آمده
    bank("cci", lambda v: v <= -73.0, "cci<=-73")
    bank("willr", lambda v: v <= -67.0, "willr<=-67")
    return cands


def stack(tf_key, max_depth=6):
    B = BASE[tf_key]
    df = load_tf(B["asset"], B["tf"])
    sig0 = reversal_day_signals(df, B["tf"], B["side"], n_open=B["n_open"],
                                k_spike=B["k_spike"], slope_min_frac=B["slope_min"],
                                entry_from_frac=B["win"][0], entry_to_frac=B["win"][1])
    sig0 = sig0 & regime_mask(df, B["reg"])

    cands = build_candidates(df)
    print(f"\n######### {B['asset']} {B['tf']} — greedy filter stacking "
          f"({len(cands)} candidates from 401-indicator bank) #########", flush=True)

    def ev(s):
        return eval_sig(df, s, B["side"], B["asset"], B["sl"], B["tp"],
                        B["maxhold"], min_n=B["min_n"])

    cur = sig0.copy()
    cur_r = ev(cur)
    print(f"BASE: {cur_r}", flush=True)
    chosen = []
    history = [dict(step=0, filters=[], result=cur_r)]

    for depth in range(1, max_depth + 1):
        best_name, best_r, best_sig = None, None, None
        for nm, m in cands.items():
            if nm in chosen:
                continue
            s = cur & m
            if s.sum() < B["min_n"]:
                continue
            r = ev(s)
            if r is None:
                continue
            # معیارِ انتخاب: RQS+ بالاتر؛ گره‌شکن: PF بالاتر
            if best_r is None or (r["rqs"], r["pf"]) > (best_r["rqs"], best_r["pf"]):
                best_name, best_r, best_sig = nm, r, s
        if best_r is None or best_r["rqs"] <= cur_r["rqs"] + 1e-9:
            print(f"  (depth {depth}: هیچ فیلترِ بعدی RQS+ را بالا نبرد ⇒ توقفِ حریصانه)", flush=True)
            break
        chosen.append(best_name)
        cur, cur_r = best_sig, best_r
        history.append(dict(step=depth, filters=list(chosen), result=cur_r))
        flag = "ACC" if cur_r["passed"] else "rej"
        print(f"  +{best_name:26} -> {flag} RQS={cur_r['rqs']:5.1f} G[{cur_r['gates']}] "
              f"n={cur_r['n']:4} WR={cur_r['wr']:5.2f} PF={cur_r['pf']} net={cur_r['net']}", flush=True)

    out = dict(base=history[0]["result"], chosen=chosen, final=cur_r, history=history,
               config=B, n_candidates=len(cands))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"_stack_{B['tf']}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(f"\nFINAL {B['tf']}: filters={chosen}\n  {cur_r}", flush=True)
    print(f"saved -> results/_scan_S345/_stack_{B['tf']}.json", flush=True)
    return out


if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "M15").upper()
    if which == "ALL":
        for k in BASE:
            stack(k)
    else:
        stack(which)
