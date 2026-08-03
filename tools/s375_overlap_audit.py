# -*- coding: utf-8 -*-
"""
ممیزیِ همپوشانیِ S375 — بندِ ۷ پیش‌ثبت + قانونِ سومِ پروژه

قانونِ سومِ پروژه می‌گوید همپوشانی باید **پیش از رفتن به مرحلهٔ بعد** سنجیده
شود و امکانِ «استفاده از بخشِ همپوشان به‌عنوانِ فیلتر» بررسی گردد.

این فایل سه پرسش را عددی پاسخ می‌دهد، در **دو فضای متفاوت**:

  فضای ۱ — کانال (کدام الگو معامله شد؟)
      اشتراکِ `seg_id`ها میانِ بازوی close و بازوی kennedy.
      انتظار: ≈۱۰۰٪ (زیرمجموعهٔ محض) ⇒ لبهٔ الگویی نو نیست.

  فضای ۲ — کندل (کدام بارِ ورود؟)
      اشتراکِ ایندکسِ بارِ ورود.
      انتظار: ≈۰٪ ⇒ لبه از **قیمتِ ورود** می‌آید، نه از غربالِ الگو.

  فضای ۳ — پرسشِ اجباریِ فیلتر
      «آیا بخشِ همپوشان به‌عنوانِ فیلتر ارزش دارد؟» یعنی: اگر همان معاملاتِ
      بازوی close را برداریم و **فقط** آن‌هایی را نگه داریم که بعداً شرطِ
      Kennedy را هم برآورده می‌کنند (بدونِ عوض‌کردنِ قیمتِ ورود)، آیا بهبود
      رخ می‌دهد؟

⚠️ تفکیکِ فضای ۳ از بازوی Kennedy حیاتی است:
      بازوی Kennedy       = ورودِ دیرتر با قیمتِ بهتر  (اثرِ قیمت)
      فیلترِ فضای ۳       = ورودِ **همان‌جا**، فقط انتخابِ الگوها (اثرِ غربال)
   اگر فضای ۳ بهبود نداد ولی بازوی Kennedy داد، اثبات می‌شود سودِ قاعده از
   **قیمت** است و نه از **انتخاب** — و این تفکیک با هیچ آمارهٔ تجمیعی
   قابلِ استخراج نیست.
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


def collect(df, ctx, m, s, mode, mh, warm, n):
    ls, ss, slv, tpv, _ = member_signals_mode(df, ctx, m, s, ASSET, GATE, mode)
    ls[:warm] = False
    ss[:warm] = False
    ls[n - mh - 2:] = False
    ss[n - mh - 2:] = False
    return ls, ss, slv, tpv


def main():
    df = se.load_data(f"data/{ASSET}_{TF}.csv")
    n = len(df)
    warm = min(260, max(30, n // 8))
    ctx = channel_context(df, ANCHOR["k"])

    # افقِ نگهداری: عیناً همان که در داوری استفاده شد (از بازوی پایه)
    durs = []
    for k in FAM_K:
        c2 = channel_context(df, k)
        l2, s2, _, _, d2 = member_signals_mode(df, c2, FAM_M[0], FAM_S[0],
                                               ASSET, GATE, "close")
        sel = l2 | s2
        if sel.any():
            durs.extend(d2[sel].tolist())
    mh = int(min(MAX_HOLD_CAP, max(5, round(HORIZON_MULT * float(np.median(durs))))))

    seg = ctx["seg"]
    print(f"=== S375 OVERLAP AUDIT :: {ASSET}-{TF}  anchor={ANCHOR}  mh={mh} ===")

    arms = {}
    for mode in ("close", "kennedy"):
        ls, ss, slv, tpv = collect(df, ctx, ANCHOR["m"], ANCHOR["s"],
                                   mode, mh, warm, n)
        tr = se.simulate_trades(df, ls, ss, slv, tpv, ASSET,
                                max_hold=mh, allow_overlap=False)
        eb = tr["entry_bar"].values.astype(int)
        R = tr["pnl_pip"].values.astype(float) / tr["sl_pip"].values.astype(float)
        arms[mode] = dict(sig=(ls | ss), bars=set(eb.tolist()),
                          segs=set(np.asarray(seg)[eb - 1].tolist()),
                          n=len(tr), R=R, eb=eb,
                          pnl=float(tr["pnl_pip"].sum()),
                          exp=float(tr["pnl_pip"].mean()))

    c, k = arms["close"], arms["kennedy"]

    # ── فضای ۱: کانال ──
    inter_seg = c["segs"] & k["segs"]
    ov_seg = 100.0 * len(inter_seg) / max(1, len(k["segs"]))
    # ── فضای ۲: کندل ──
    inter_bar = c["bars"] & k["bars"]
    ov_bar = 100.0 * len(inter_bar) / max(1, len(k["bars"]))

    print(f"\n-- فضای ۱ (کانال): kennedy segs={len(k['segs'])}  "
          f"close segs={len(c['segs'])}  اشتراک={len(inter_seg)}"
          f"  ⇒ همپوشانی = {ov_seg:.1f}%")
    print(f"-- فضای ۲ (کندلِ ورود): kennedy bars={len(k['bars'])}  "
          f"close bars={len(c['bars'])}  اشتراک={len(inter_bar)}"
          f"  ⇒ همپوشانی = {ov_bar:.1f}%")

    # ── فضای ۳: پرسشِ اجباریِ فیلتر ──
    # معاملاتِ بازوی close که کانالشان بعداً شرطِ Kennedy را هم برآورده کرد.
    # قیمتِ ورود **عوض نمی‌شود** — فقط انتخاب.
    mask_flt = np.array([int(seg[b - 1]) in k["segs"] for b in c["eb"]])
    Rf = c["R"][mask_flt]
    Rn = c["R"][~mask_flt]
    print(f"\n-- فضای ۳ (پرسشِ اجباریِ قانونِ سوم): آیا بخشِ همپوشان "
          f"به‌عنوانِ **فیلتر** ارزش دارد؟")
    print(f"   بازوی close کامل        : n={c['n']:4d}  meanR={c['R'].mean():+.4f}"
          f"  Σpip={c['pnl']:+9.1f}  exp={c['exp']:+7.2f}p")
    print(f"   زیرمجموعهٔ فیلترشده     : n={int(mask_flt.sum()):4d}"
          f"  meanR={Rf.mean() if len(Rf) else float('nan'):+.4f}")
    print(f"   بقیه (ردشده با فیلتر)  : n={int((~mask_flt).sum()):4d}"
          f"  meanR={Rn.mean() if len(Rn) else float('nan'):+.4f}")
    d_filter = (float(Rf.mean()) - float(c["R"].mean())) if len(Rf) else float("nan")
    print(f"   Δ meanR (فیلتر − کامل) = {d_filter:+.4f}")
    print(f"\n   بازوی kennedy (ورودِ دیرتر) : n={k['n']:4d}"
          f"  meanR={k['R'].mean():+.4f}  Σpip={k['pnl']:+9.1f}"
          f"  exp={k['exp']:+7.2f}p")
    d_price = float(k["R"].mean()) - float(c["R"].mean())
    print(f"   Δ meanR (kennedy − کامل)   = {d_price:+.4f}")

    print(f"\n-- تفکیکِ اثر (کلیدِ تشخیص) --")
    print(f"   اثرِ **غربالِ الگو** (فضای ۳) = {d_filter:+.4f}")
    print(f"   اثرِ **قیمتِ ورود** (باقی)   = {d_price - d_filter:+.4f}")

    out = dict(asset=ASSET, tf=TF, anchor=ANCHOR, max_hold=mh,
               space1_channel_overlap_pct=round(ov_seg, 2),
               space2_entrybar_overlap_pct=round(ov_bar, 2),
               n_close=c["n"], n_kennedy=k["n"],
               n_filtered=int(mask_flt.sum()),
               meanR_close=round(float(c["R"].mean()), 4),
               meanR_filtered=round(float(Rf.mean()), 4) if len(Rf) else None,
               meanR_rejected=round(float(Rn.mean()), 4) if len(Rn) else None,
               meanR_kennedy=round(float(k["R"].mean()), 4),
               d_filter_effect=round(d_filter, 4),
               d_price_effect=round(d_price - d_filter, 4),
               d_total=round(d_price, 4),
               pnl_close=round(c["pnl"], 1), pnl_kennedy=round(k["pnl"], 1),
               exp_close=round(c["exp"], 3), exp_kennedy=round(k["exp"], 3))
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/OVERLAP_AUDIT_{ASSET}_{TF}.json"
    with open(p, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"\n   → {p}")


if __name__ == "__main__":
    main()
