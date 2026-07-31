# -*- coding: utf-8 -*-
"""
S356 — بازداوریِ صادقانهٔ لایهٔ `S354 causal` با موتورِ **RQS2 v2.4**
====================================================================

پیش‌ثبت: `results/S356_PREREGISTRATION_S354_CAUSAL_V24_REJUDGE.md` (commitِ جدا،
پیش از اجرا). **هیچ پارامتری در این اسکریپت جست‌وجو نمی‌شود**؛ همه از بایگانیِ
`S354` قفل شده‌اند.

چرا این اسکریپت لازم بود
------------------------
رکوردِ بایگانی با شرطِ `WR > perm_max` کشته شد — همان آماره‌ای که `v2.4` به‌دلیلِ
**ناهمگرایی** رسماً بازنشسته کرد (نقصِ `F1`). پس حکمِ فعلیِ آن رکورد با معیارِ
فعلی صادر نشده و بازداوری، **حقِ لایه** است نه لطف به آن.

دو تفاوتِ مهندسیِ این اسکریپت با نسخهٔ بایگانی
---------------------------------------------
**۱) جدولِ برآمدِ پیش‌محاسبه‌شده (شتابِ ~۱۰۰۰×).** براکت ثابت است (`SL`/`TP` عددِ
   ثابتِ pip)، پس برآمدِ یک ورودِ لانگ در کندلِ `si` **فقط** به `si` وابسته است، نه
   به اینکه کدام ورودهای دیگر انتخاب شده‌اند. قاعدهٔ ناهم‌پوشانی تنها تعیین می‌کند
   کدام ورودها *گرفته* می‌شوند، نه اینکه برآمدشان چه باشد. پس برآمدِ همهٔ کندل‌ها
   **یک بار** برداری محاسبه می‌شود و هر قرعهٔ جای‌گشت به یک پیمایشِ `O(k)` تبدیل
   می‌شود. نتیجه بیت‌به‌بیت همان `_wr_long` بایگانی است و در اجرا **تأیضِ عددی**
   با مقدارِ ثبت‌شدهٔ بایگانی چاپ می‌شود.

**۲) دو p-value، نه یکی — و پاس‌شدن نیازِ *هر دو* است.**
   بازرسیِ کد نشان داد `blend_null` کلیدِ `p_perm` را **حمل نمی‌کند**، پس
   `compute_rqs2` همیشه به p **پارامتریکِ** `0.5·erfc(z/√2)` می‌افتد، هرچند اسپک
   از «p جای‌گشتی» حرف می‌زند. این اسکریپت `p` **تجربیِ** واقعی را هم از قرعه‌های
   خام می‌شمارد و **سخت‌گیرانه‌ترین** را ملاک می‌گیرد:

       ACCEPTِ صادقانه  ⇐  حکمِ موتور = ACCEPT   **و**   p_تجربی ≤ 0.001

   یعنی این اسکریپت نمی‌تواند لایه را از راهِ تفاوتِ دو خط‌کش «بخرد».

اجرا:
    python3 strategies/s356_v24_rejudge.py --cards XAUUSD-H1
    python3 strategies/s356_v24_rejudge.py --cards all
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                             # noqa: E402
from engine import rqs2 as R2                                     # noqa: E402
from strategies import s354_brooks_trend_resumption as base       # noqa: E402
from strategies.s354_causal_check import build_signals_causal     # noqa: E402

OUT = "results/_scan_S356"

# ────────────────────────── پیکربندیِ منجمدِ بایگانی ──────────────────────────
FROZEN = dict(
    n_open_frac=0.13,      # پنجرهٔ بازِ روز
    late_hour=16,          # پنجرهٔ پایانیِ CAUSAL (ساعتِ ثابتِ UTC)
    spike_k=0.8,           # آستانهٔ جهشِ leg اول بر حسبِ ATR
    tight_atr=12.0,        # سقفِ فشردگیِ رنجِ میانه
    regime=("r2_fib_55", "ge", 0.45),
    sl_k=1.3,              # SL = 1.3 × ATR_fib(per-TF)
    rr=2.0,                # TP = 2.0 × SL
)
N_TRIALS_HONEST = 96       # همان عددِ بایگانی
N_TRIALS_STRESS = 288      # ۹۶ × ۳ (جریمهٔ جاروبِ سه‌مقداریِ late_hour)
PERM_K_PRE = 2000          # پیش‌ثبت‌شده
PERM_K_HI = 5000           # صرفاً برای تفکیکِ بهترِ p (۰.۰۰۰۲ به‌جای ۰.۰۰۰۵)
SEEDS = (23, 101, 777)
P_BAR = 0.001

# قانونِ MTF: **همهٔ** تایم‌فریم‌های موجود در `data/`، برای هر دو ارز — با شروع از
# `XAUUSD-M1`. کارت‌های `D1`/`W1` عمداً حذف نشده‌اند، هرچند این لایه ماهیتِ
# درون‌روزی دارد (پنجرهٔ بازِ روز + ساعتِ ثابتِ ۱۶ UTC) و روی کندلِ روزانه/هفتگی
# احتمالاً `NO_SIGNAL` می‌دهد. **گزارشِ صریحِ «کاربردناپذیر» با دلیل**، از
# حذفِ خاموشِ کارت بهتر است: حذف کردن، همان اشتباهِ رایجِ شمارهٔ ۵ است.
CARDS_ALL = [
    "XAUUSD-M1", "XAUUSD-M5", "XAUUSD-M15", "XAUUSD-M30",
    "XAUUSD-H1",                                        # کارتِ اصلیِ بایگانی
    "XAUUSD-H4", "XAUUSD-D1", "XAUUSD-W1",
    "EURUSD-M1", "EURUSD-M5", "EURUSD-M15", "EURUSD-M30",
    "EURUSD-H1", "EURUSD-H4", "EURUSD-D1", "EURUSD-W1",
]


# ═════════════════════════ جدولِ برآمدِ برداری ═════════════════════════
def outcome_table(df, asset, sl_pip, tp_pip, mh):
    """برآمدِ یک ورودِ لانگ برای **هر** کندل، یک‌بار و برداری.

    معناشناسیِ بیت‌به‌بیتِ `_wr_long` بایگانی:
      · ورود در `open` کندلِ `si+1`
      · در هر کندل ابتدا `low ≤ ent−SL` (باخت) بررسی می‌شود، بعد `high ≥ ent+TP`
        (برد) ⇒ اگر هر دو در یک کندل بخورند، **باخت** (محافظه‌کارانه)
      · اگر تا `mh` کندل هیچ‌کدام نخورد ⇒ خروجِ زمانی روی `close`، با کسرِ هزینه

    خروجی: `res` (۱=برد، −۱=باخت، ۰=غیرقابلِ‌ورود) و `exit_bar`.
    """
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = cfg["pip"]
    cost = cfg["spread_pip"] + 2 * cfg.get("slip_pip", 0.0)
    sl_d, tp_d = sl_pip * pip, tp_pip * pip

    eb = np.arange(n) + 1                     # کندلِ ورود
    live = eb < n
    ent = np.where(live, o[np.minimum(eb, n - 1)], np.nan)
    res = np.zeros(n, dtype=np.int8)
    xbar = np.full(n, -1, dtype=np.int64)

    for j in range(mh):
        k = eb + j
        open_slot = live & (res == 0) & (k < n)
        if not open_slot.any():
            break
        kk = np.minimum(k, n - 1)
        lo_hit = open_slot & (l[kk] <= ent - sl_d)
        hi_hit = open_slot & (~lo_hit) & (h[kk] >= ent + tp_d)
        res[lo_hit] = -1
        xbar[lo_hit] = k[lo_hit]
        res[hi_hit] = 1
        xbar[hi_hit] = k[hi_hit]

    # خروجِ زمانی
    kend = np.minimum(eb + mh, n)              # انحصاری
    to = live & (res == 0) & (kend > eb)
    if to.any():
        last = c[np.maximum(kend - 1, 0)]
        won = ((last - ent) / pip - cost) > 0
        res[to] = np.where(won[to], 1, -1)
        xbar[to] = kend[to] - 1
    return res, xbar


def wr_of(picks, res, xbar):
    """WRِ مجموعه‌ای از ورودها با قاعدهٔ ناهم‌پوشانیِ بایگانی."""
    wins = used = 0
    last_exit = -1
    for si in picks:
        if si <= last_exit or res[si] == 0:
            continue
        used += 1
        last_exit = xbar[si]
        if res[si] == 1:
            wins += 1
    return (100.0 * wins / used) if used else None


def build_null(df, asset, sig, sl, tp, mh, k_perm, seed):
    """مدلِ صفرِ کانونی + p **تجربی** (که موتور نمی‌سازد)."""
    res, xbar = outcome_table(df, asset, sl, tp, mh)
    n = len(df)
    valid = np.arange(260, n - mh - 2)
    valid = valid[res[valid] != 0]
    k = int(np.asarray(sig).sum())
    uncond = wr_of(valid, res, xbar)

    rng = np.random.default_rng(seed)
    draws = np.empty(k_perm, dtype=float)
    got = 0
    for _ in range(k_perm):
        pick = np.sort(rng.choice(valid, size=min(k, valid.size), replace=False))
        w = wr_of(pick, res, xbar)
        if w is not None:
            draws[got] = w
            got += 1
    draws = draws[:got]
    long_null = dict(uncond_wr=uncond, perm_mean=float(draws.mean()),
                     perm_sd=float(draws.std(ddof=1)), perm_max=float(draws.max()),
                     perm_k=int(got))
    zero = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                perm_max=None, perm_k=0)
    return {"long": long_null, "short": zero}, draws


def empirical_p(draws, wr_obs):
    """p تجربیِ یک‌طرفه با برآوردگرِ محافظه‌کارانهٔ `(1+#{≥obs})/(1+K)`.

    عددِ `+1` استانداردِ آزمونِ مونت‌کارلو است (Davison & Hinkley 1997) و از
    گزارشِ `p = 0` جلوگیری می‌کند — که هرگز با نمونهٔ متناهی قابلِ اثبات نیست.
    """
    ge = int((draws >= wr_obs - 1e-12).sum())
    return (1.0 + ge) / (1.0 + len(draws)), ge


# ═════════════════════════════ اجرا برای یک کارت ═════════════════════════════
def run_card(card, verbose=True):
    asset, tf = card.split("-")
    path = os.path.join("data", f"{asset}_{tf}.csv")
    if not os.path.exists(path):
        return dict(card=card, status="NO_DATA")
    df = se.load_data(path)

    atr_pip = base._atr_pip(df, asset, base.TF_ATR_P.get(tf, 34))
    mh = base.TF_MAX_HOLD.get(tf, 20)
    sl = round(FROZEN["sl_k"] * atr_pip, 1)
    tp = round(FROZEN["rr"] * sl, 1)

    gate = base.regime_gate(df, FROZEN["regime"])
    sig = build_signals_causal(df, asset, tf, FROZEN["n_open_frac"],
                               FROZEN["late_hour"], FROZEN["spike_k"],
                               FROZEN["tight_atr"]) & gate
    n_sig = int(sig.sum())
    if verbose:
        print(f"\n=== {card} :: SL={sl}pip TP={tp}pip mh={mh} bars={len(df)} "
              f"signals={n_sig}", flush=True)
    if n_sig < 5:
        return dict(card=card, status="NO_SIGNAL", n_signals=n_sig,
                    sl=sl, tp=tp, maxhold=mh, bars=len(df))

    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 5:
        return dict(card=card, status="NO_TRADES", n_signals=n_sig)
    n = len(tr)
    wr_obs = 100.0 * float((tr["pnl_pip"] > 0).sum()) / n
    close = df["close"].values.astype(float)
    bar_time = df["time"].values
    split_bar = int(len(df) * 0.60)

    rec = dict(card=card, asset=asset, tf=tf, status="JUDGED",
               frozen=dict(FROZEN, regime="r2_fib_55>=0.45"),
               sl_pip=sl, tp_pip=tp, maxhold=mh, bars=len(df),
               n_signals=n_sig, n_trades=n, wr_obs=round(wr_obs, 2),
               seeds={}, honest={})

    for seed in SEEDS:
        k_perm = PERM_K_HI if (card == "XAUUSD-H1" and seed == SEEDS[0]) else PERM_K_PRE
        null, draws = build_null(df, asset, sig, sl, tp, mh, k_perm, seed)
        p_emp, n_ge = empirical_p(draws, wr_obs)
        out = {}
        for label, nt in (("honest", N_TRIALS_HONEST), ("stress", N_TRIALS_STRESS)):
            r = R2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp, bar_time=bar_time,
                                close=close, null=null, n_trials=nt,
                                split_bar=split_bar)
            m = r.get("metrics", {})
            out[label] = dict(verdict=r.get("verdict"), score=r.get("rqs2_score"),
                              gates=r.get("gates"), metrics=m,
                              notes=r.get("notes"))
        m0 = out["honest"]["metrics"]
        out["null"] = dict(uncond_wr=null["long"]["uncond_wr"],
                           perm_mean=null["long"]["perm_mean"],
                           perm_sd=null["long"]["perm_sd"],
                           perm_max=null["long"]["perm_max"],
                           perm_k=null["long"]["perm_k"])
        out["p_empirical"] = round(p_emp, 6)
        out["n_draws_ge_obs"] = n_ge
        out["p_parametric_engine"] = m0.get("skill_p_perm")
        out["honest_accept"] = bool(out["honest"]["verdict"] == "ACCEPT"
                                    and p_emp <= P_BAR)
        rec["seeds"][str(seed)] = out
        if verbose:
            print(f"  seed={seed} K={null['long']['perm_k']} | "
                  f"n={n} WR={wr_obs:.2f} lift={m0.get('skill_lift_pp')} "
                  f"z={m0.get('skill_z')}", flush=True)
            print(f"      engine: {out['honest']['verdict']} "
                  f"score={out['honest']['score']} "
                  f"p_param={out['p_parametric_engine']} | "
                  f"p_emp={p_emp:.6f} ({n_ge}/{null['long']['perm_k']} ≥ obs) "
                  f"perm_max={null['long']['perm_max']:.2f}", flush=True)
            print(f"      stress(n_trials=288): {out['stress']['verdict']} | "
                  f"HONEST_ACCEPT={out['honest_accept']}", flush=True)
            bad = [g for g, v in (out["honest"]["gates"] or {}).items() if v is not True]
            print(f"      failing/unknown gates: {bad or 'NONE'}", flush=True)

    verds = {s: v["honest"]["verdict"] for s, v in rec["seeds"].items()}
    rec["honest"] = dict(
        seed_stable=len(set(verds.values())) == 1,
        verdicts=verds,
        all_seeds_honest_accept=all(v["honest_accept"] for v in rec["seeds"].values()),
        stress_ok=all(v["stress"]["verdict"] == "ACCEPT" for v in rec["seeds"].values()),
    )
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default="XAUUSD-H1")
    args = ap.parse_args()
    cards = CARDS_ALL if args.cards == "all" else args.cards.split(",")
    os.makedirs(OUT, exist_ok=True)
    for card in cards:
        rec = run_card(card)
        # ⛳ قانونِ سومِ پروژه: هر کارت **فوراً** ذخیره می‌شود، منتظرِ بقیه نمی‌مانیم
        with open(os.path.join(OUT, f"{card}.json"), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1, default=float)
        print(f"  [saved] {OUT}/{card}.json  status={rec.get('status')} "
              f"honest={rec.get('honest')}", flush=True)


if __name__ == "__main__":
    main()
