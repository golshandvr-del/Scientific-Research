# -*- coding: utf-8 -*-
"""
S369 — داوریِ کاملِ ۱۱ دروازهٔ RQS2 روی **عضوِ لنگرگاهیِ** XAUUSD-H1

طبقِ `results/S369_PREREG_anchor_judgement.md` (پیش از اجرا commit شد):

  · عضو با **متن** انتخاب شد، نه با عملکرد:
        k=3   (میانهٔ محورِ (2,3,5))
        f=0.70 (نسبتِ خودِ Brooks: 10 tick / 14 tick)
        g=1.00 (هدفِ کاملِ pullback — خوانشِ measured-move)
        s=1.00 (حد ضرر = کلِ ارتفاعِ نوسان)
    ⇒ هزینهٔ انتخاب = صفر ⇒ `n_trials` همان ۶۱ می‌ماند.

  · `n_trials = 61` = شمارشِ صادقانهٔ **همهٔ** آزمون‌های سطح-کارتِ فصلِ ۲۶
        (S364:15 · S365:11 · S366:19 · S367:1 · S369:15)
    این عدد به دروازهٔ کرانِ شانس داده می‌شود. عمداً بزرگ‌تر از «فقط این لایه»
    گرفته شده تا کلِ تاریخِ جست‌وجوی فصل روی همین یک نتیجه بار شود.

  · `holdout_mask` = ورودهای نیمهٔ دوم. چون عضو از **متن** آمده و نه از نیمهٔ اول،
    نیمهٔ دوم یک holdoutِ واقعیِ دست‌نخورده است.

⚠️ بندِ قفلِ پیش‌ثبت: اگر لنگر رد شود، **حق آزمودنِ عضوِ دیگری نیست**.
"""

from __future__ import annotations

import os
import sys
import json

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from engine import rqs2                                                  # noqa: E402
from strategies.s364_stairs_family import (                              # noqa: E402
    stairs_context, TF_MAX_HOLD,
)
from strategies.s369_stair_continuation import continuation_signals      # noqa: E402
from strategies.s364_deploy_judge import build_null                      # noqa: E402

OUT = "results/_scan_S369"

# ── لنگرِ متنی (تغییرناپذیر — بندِ ۲ پیش‌ثبت) ──
ANCHOR = dict(k=3, f=0.70, g=1.00, s=1.00)

# ── شمارشِ صادقانهٔ چندگانگیِ کلِ فصل (بندِ ۳ پیش‌ثبت) ──
N_TRIALS = 61


def run(asset="XAUUSD", tf="H1", seed=369):
    path = f"data/{asset}_{tf}.csv"
    df = se.load_data(path)
    n = len(df)
    mh = TF_MAX_HOLD[tf]
    warm = min(260, max(30, n // 8))
    split = n // 2
    rng = np.random.default_rng(seed)

    print(f"\n=== S369 ANCHOR-JUDGE :: {asset}-{tf} (bars={n:,}, mh={mh}) ===")
    print(f"   anchor (text-chosen, zero selection cost) = {ANCHOR}")
    print(f"   n_trials = {N_TRIALS}  (all card-level tests of chapter 26)")

    ctx = stairs_context(df, ANCHOR["k"])
    ls, ss, slv, tpv = continuation_signals(
        df, ctx, ANCHOR["f"], ANCHOR["g"], ANCHOR["s"], asset)
    ls[:warm] = False
    ss[:warm] = False
    ls[n - mh - 2:] = False
    ss[n - mh - 2:] = False

    trades = se.simulate_trades(df, ls, ss, slv, tpv, asset,
                                max_hold=mh, allow_overlap=False)
    if trades is None or len(trades) == 0:
        print("   !! no trades")
        return None

    sl = trades["sl_pip"].values.astype(float)
    tp = trades["tp_pip"].values.astype(float) if "tp_pip" in trades else None
    eb = trades["entry_bar"].values.astype(int)

    # H2 با بریکتِ شناور: میانگینِ حسابی = سربه‌سرِ *دقیقِ* پرتفوی (نه میانه)
    mean_sl = float(np.mean(sl[sl > 0]))
    if tp is None:
        tp = tpv[eb - 1]
    mean_tp = float(np.mean(tp[sl > 0]))
    share_tp_lt_sl = float(np.mean(tp[sl > 0] < sl[sl > 0]))

    print(f"   n_trades={len(trades)}  mean SL={mean_sl:.2f}pip  "
          f"mean TP={mean_tp:.2f}pip  RR={mean_tp / mean_sl:.3f}  "
          f"share(TP<SL)={share_tp_lt_sl:.3f}")

    null, ndiag = build_null(df, asset, tf, trades, ls, ss, slv, tpv,
                             ctx, warm, mh, rng)

    bar_time = df["time"].values if "time" in df else np.arange(n)
    holdout_mask = (eb >= split)
    print(f"   holdout trades (2nd half) = {int(holdout_mask.sum())}"
          f" / {len(trades)}")

    res = rqs2.compute_rqs2(
        trades, asset,
        sl_pip=mean_sl, tp_pip=mean_tp,
        # ⚠️ باید آرایهٔ **کاملِ زمانِ کندل‌ها** باشد، نه زمانِ هر معامله.
        #    `calendar_windows` داخلاً `bt[clip(exit_bar, 0, len(bt)-1)]` می‌زند؛
        #    اگر آرایهٔ ۱۱۰-تایی بدهیم، exit_barهای ~۹۰٬۰۰۰ همگی به ۱۰۹ کلیپ
        #    می‌شوند و هر ۱۱۰ معامله در یک سطلِ تقویمی می‌افتند ⇒ H6/H10 دروغین.
        bar_time=bar_time,
        null=null, n_trials=N_TRIALS,
        holdout_mask=holdout_mask, split_bar=split,
        close=df["close"].values.astype(float),
        allow_overlap=False,
    )

    g = res.get("gates", {})
    m = res.get("metrics", {})
    print(f"\n   VERDICT = {res.get('verdict')}   score={res.get('score')}")
    print("   gates: " + "  ".join(
        f"{k}={'OK' if v else 'X'}" for k, v in g.items()))
    print(f"   z_obs={m.get('z_obs')}  z_luck_bound={m.get('z_luck_bound')}"
          f"  z_margin={m.get('z_margin')}")
    print(f"   PF={m.get('profit_factor')}  WR={m.get('win_rate')}"
          f"  net={m.get('net_profit')}")
    for r in res.get("reasons", [])[:8]:
        print(f"     · {r}")

    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/ANCHORJUDGE_{asset}_{tf}.json"
    with open(p, "w") as fh:
        json.dump(dict(anchor=ANCHOR, n_trials=N_TRIALS,
                       mean_sl=round(mean_sl, 3), mean_tp=round(mean_tp, 3),
                       share_tp_lt_sl=round(share_tp_lt_sl, 4),
                       n_holdout=int(holdout_mask.sum()),
                       null_diag=ndiag, result=res), fh,
                  indent=1, ensure_ascii=False, default=str)
    print(f"   saved -> {p}")
    return res


if __name__ == "__main__":
    run()
