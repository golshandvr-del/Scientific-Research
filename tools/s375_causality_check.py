# -*- coding: utf-8 -*-
"""
بررسیِ علیّتِ فیلترِ S375 — آزمونِ «آیا این فیلتر از آینده خبر دارد؟»

═══════════════════════════════════════════════════════════════════════════
چرا این فایل حیاتی است
═══════════════════════════════════════════════════════════════════════════
ممیزیِ همپوشانی نشان داد فیلترِ Kennedy معاملاتِ بازوی `close` را با
`Δ meanR = +0.3050` تفکیک می‌کند (فیلترشده `+0.4408` در برابرِ ردشده `-0.1464`).

**ولی این عدد ممکن است کاملاً بی‌ارزش باشد.** چون فیلتر می‌گوید «آن معاملاتی را
نگه دار که کانالشان **بعداً** شرطِ Kennedy را برآورده کرد». اگر آن «بعداً» پس از
بارِ ورودِ `close` باشد، در لحظهٔ تصمیم این اطلاع **وجود نداشته** ⇒ نگاه به آینده
⇒ فیلتر غیرقابلِ معامله است و `+0.3050` یک سرابِ آماری.

منطقاً هم انتظارِ بد داریم: خودِ یافتهٔ نشستِ قبل اندازه گرفت که شرطِ Kennedy
**۱ تا ۷ کندل دیرتر** فعال می‌شود. یعنی احتمالاً همیشه پس از ورود.

═══════════════════════════════════════════════════════════════════════════
این فایل چه می‌کند
═══════════════════════════════════════════════════════════════════════════
۱) برای هر معاملهٔ بازوی `close` که فیلتر نگهش داشت، فاصلهٔ زمانیِ
   (بارِ فعال‌شدنِ Kennedy − بارِ ورودِ close) را می‌سنجد.

۲) سه دسته می‌شمارد:
      lag < 0   : Kennedy **پیش از** ورود فعال شد  ⇒ اطلاع در دسترس ⇒ مجاز ✅
      lag == 0  : همان بار                          ⇒ مرزی، مجاز ✅
      lag > 0   : Kennedy **پس از** ورود فعال شد    ⇒ نگاه به آینده ⇒ ممنوع ❌

۳) نسخهٔ **علّیِ** فیلتر را می‌سازد: فقط معاملاتی که در لحظهٔ ورود، شرطِ
   Kennedy از قبل برآورده بوده. و `meanR` آن را گزارش می‌کند.

اگر نسخهٔ علّی نمونهٔ ناچیز یا لبهٔ صفر داد، باید صریحاً گزارش شود که یافتهٔ
`+0.3050` **غیرقابلِ بهره‌برداری** است — نه توجیه، نه دور زدن.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s366_stairs_channel_breakout import (                    # noqa: E402
    channel_context, FAM_K, FAM_M, FAM_S, HORIZON_MULT, MAX_HOLD_CAP)
from strategies.s374_kennedy_break_gate import member_signals_mode       # noqa: E402
from strategies.s375_kennedy_single_instrument import (                  # noqa: E402
    GATE, ANCHOR, OUT)

ASSET = "XAUUSD"
TF = "H1"


def main():
    df = se.load_data(f"data/{ASSET}_{TF}.csv")
    n = len(df)
    warm = min(260, max(30, n // 8))
    ctx = channel_context(df, ANCHOR["k"])
    seg = np.asarray(ctx["seg"])

    durs = []
    for k in FAM_K:
        c2 = channel_context(df, k)
        l2, s2, _, _, d2 = member_signals_mode(df, c2, FAM_M[0], FAM_S[0],
                                               ASSET, GATE, "close")
        sel = l2 | s2
        if sel.any():
            durs.extend(d2[sel].tolist())
    mh = int(min(MAX_HOLD_CAP, max(5, round(HORIZON_MULT * float(np.median(durs))))))

    print(f"=== S375 CAUSALITY CHECK :: {ASSET}-{TF}  anchor={ANCHOR}  mh={mh} ===")

    # ── سیگنالِ خامِ هر دو حالت (پیش از simulate) ──
    sigs = {}
    for mode in ("close", "kennedy"):
        ls, ss, slv, tpv, _ = member_signals_mode(df, ctx, ANCHOR["m"],
                                                  ANCHOR["s"], ASSET, GATE, mode)
        ls[:warm] = False
        ss[:warm] = False
        ls[n - mh - 2:] = False
        ss[n - mh - 2:] = False
        sigs[mode] = (ls, ss, slv, tpv)

    ls_c, ss_c, slv_c, tpv_c = sigs["close"]
    ls_k, ss_k, _, _ = sigs["kennedy"]
    trig_k = ls_k | ss_k

    tr = se.simulate_trades(df, ls_c, ss_c, slv_c, tpv_c, ASSET,
                            max_hold=mh, allow_overlap=False)
    eb = tr["entry_bar"].values.astype(int)
    R = tr["pnl_pip"].values.astype(float) / tr["sl_pip"].values.astype(float)

    # بارِ فعال‌شدنِ Kennedy در هر seg
    k_bar_of_seg = {}
    for b in np.where(trig_k)[0]:
        s = int(seg[b])
        if s not in k_bar_of_seg:
            k_bar_of_seg[s] = int(b)

    lags, keep_causal, keep_any = [], [], []
    for i, b in enumerate(eb):
        # سیگنال در بارِ b-1 زده شد، ورود در بارِ b (کنوانسیونِ simulate_trades)
        sig_bar = int(b) - 1
        s = int(seg[sig_bar])
        kb = k_bar_of_seg.get(s)
        if kb is None:
            keep_any.append(False)
            keep_causal.append(False)
            continue
        keep_any.append(True)
        lag = kb - sig_bar
        lags.append(lag)
        keep_causal.append(lag <= 0)      # اطلاع در لحظهٔ تصمیم موجود بود

    keep_any = np.array(keep_any)
    keep_causal = np.array(keep_causal)
    lags = np.array(lags)

    print(f"\n-- توزیعِ تأخیرِ فعال‌شدنِ Kennedy نسبت به بارِ سیگنالِ close --")
    if len(lags):
        print(f"   n={len(lags)}  min={lags.min()}  p25={np.percentile(lags,25):.0f}"
              f"  median={np.median(lags):.0f}  p75={np.percentile(lags,75):.0f}"
              f"  max={lags.max()}  mean={lags.mean():.2f}")
        print(f"   lag <  0 (پیش از ورود ⇒ مجاز) : {int((lags<0).sum())}")
        print(f"   lag == 0 (همان بار  ⇒ مجاز)  : {int((lags==0).sum())}")
        print(f"   lag >  0 (پس از ورود ⇒ ممنوع): {int((lags>0).sum())}")

    print(f"\n-- مقایسهٔ فیلترِ «هرزمانی» (نگاه به آینده) با فیلترِ «علّی» --")
    print(f"   کاملِ close                : n={len(R):4d}  meanR={R.mean():+.4f}")
    if keep_any.any():
        print(f"   فیلترِ هرزمانی (بایاس‌دار) : n={int(keep_any.sum()):4d}"
              f"  meanR={R[keep_any].mean():+.4f}")
    if keep_causal.any():
        print(f"   فیلترِ علّی (قابلِ معامله) : n={int(keep_causal.sum()):4d}"
              f"  meanR={R[keep_causal].mean():+.4f}")
    else:
        print(f"   فیلترِ علّی (قابلِ معامله) : n=   0  ⇒ **هیچ معامله‌ای "
              f"در لحظهٔ ورود تأییدِ Kennedy نداشت**")

    verdict = ("CAUSAL_FILTER_EMPTY" if not keep_causal.any()
               else "CAUSAL_FILTER_HAS_SAMPLE")
    print(f"\n   >>> {verdict}")

    out = dict(asset=ASSET, tf=TF, anchor=ANCHOR, max_hold=mh,
               n_close=int(len(R)), meanR_close=round(float(R.mean()), 4),
               n_filter_anytime=int(keep_any.sum()),
               meanR_filter_anytime=(round(float(R[keep_any].mean()), 4)
                                     if keep_any.any() else None),
               n_filter_causal=int(keep_causal.sum()),
               meanR_filter_causal=(round(float(R[keep_causal].mean()), 4)
                                    if keep_causal.any() else None),
               lag_n=int(len(lags)),
               lag_min=int(lags.min()) if len(lags) else None,
               lag_median=float(np.median(lags)) if len(lags) else None,
               lag_max=int(lags.max()) if len(lags) else None,
               lag_mean=round(float(lags.mean()), 3) if len(lags) else None,
               n_lag_neg=int((lags < 0).sum()) if len(lags) else 0,
               n_lag_zero=int((lags == 0).sum()) if len(lags) else 0,
               n_lag_pos=int((lags > 0).sum()) if len(lags) else 0,
               verdict=verdict)
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/CAUSALITY_{ASSET}_{TF}.json"
    with open(p, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"   → {p}")


if __name__ == "__main__":
    main()
