# -*- coding: utf-8 -*-
"""
آزمونِ سلامتِ سطحِ خانوادهٔ S375 — «آیا بهبودِ +7.206 هم آلوده است؟»

═══════════════════════════════════════════════════════════════════════════
پرسش
═══════════════════════════════════════════════════════════════════════════
بررسیِ علیّت ثابت کرد فیلترِ Kennedy در سطحِ عضو، **علیّتِ معکوس** دارد:
تأیید همیشه ۰ تا ۵ کندل **پس از** سیگنالِ close می‌آید (میانه ۱، هیچ‌گاه پیش‌تر).

پرسشِ باقی‌مانده — و بنیادی‌ترین پرسشِ این نشست، چون کلِ انتخابِ کاندیدا روی
همین عدد بنا شد:

    بازوی Kennedy در سطحِ خانواده `z=4.333` و مازادِ `+7.206` داد.
    آیا **آن هم** مصنوعِ همان علیّتِ معکوس است؟

═══════════════════════════════════════════════════════════════════════════
پاسخِ نظری — و چرا کافی نیست
═══════════════════════════════════════════════════════════════════════════
از نظرِ منطقی بازوی Kennedy **آلوده نیست**، چون:
    · معامله در بارِ فعال‌شدنِ شرطِ Kennedy باز می‌شود، نه پیش‌تر.
    · هیچ اطلاعی از آیندهٔ آن بار استفاده نمی‌شود.
پس یک استراتژیِ **قابلِ معامله** است.

**ولی این استدلال کافی نیست.** چون یک مسیرِ آلودگیِ دیگر باز است:

    ⚠️ `simulate_trades` با `allow_overlap=False` اجرا می‌شود. اگر ورودها
       دیرتر بیفتند، **کدام معاملات به‌خاطرِ تداخل حذف می‌شوند هم عوض می‌شود**.
       اگر تصادفاً معاملاتِ بازنده حذف شوند، بهبود از «انتخابِ بهترِ ورود»
       نمی‌آید بلکه از «نظمِ بهترِ صف‌بندی» — که یک لبهٔ واقعی نیست.

═══════════════════════════════════════════════════════════════════════════
سه آزمونِ این فایل
═══════════════════════════════════════════════════════════════════════════
آزمونِ ۱ — تجزیهٔ meanR به سطحِ عضو:
    برای هر ۱۲ عضو، `meanR` دو بازو کنارِ هم. اگر بهبود در **بیشترِ** اعضا
    مثبت باشد ⇒ یک اثرِ سیستماتیک. اگر فقط در ۲–۳ عضو ⇒ تصادف.

آزمونِ ۲ — آزمونِ «ورودِ کور با همان تأخیر» (کلیدی‌ترین):
    اگر سودِ Kennedy فقط از «دیرتر وارد شدن» است، آنگاه یک بازوی ساختگی که
    **صرفاً `lag` کندل دیرتر** از سیگنالِ close وارد می‌شود (بدونِ هیچ شرطِ
    دامنه‌ای) باید همان سود را بدهد. `lag` = میانهٔ اندازه‌گیری‌شده = ۱.
    ⇒ اگر بازوی کور هم‌قدرِ Kennedy بود، قاعدهٔ Kennedy **هیچ اطلاعی**
      نمی‌افزاید و کلِ اثر «تأخیرِ محض» است. این یک ابطالِ جدی است.

آزمونِ ۳ — اثرِ صف‌بندی:
    نسبتِ سیگنال‌های خامِ حذف‌شده به‌خاطرِ تداخل، در دو بازو.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s366_stairs_channel_breakout import (                    # noqa: E402
    channel_context, FAM_K, FAM_M, FAM_S, HORIZON_MULT, MAX_HOLD_CAP,
    MIN_TRADES)
from strategies.s374_kennedy_break_gate import member_signals_mode       # noqa: E402
from strategies.s375_kennedy_single_instrument import (                  # noqa: E402
    GATE, OUT)

ASSET = "XAUUSD"
TF = "H1"
BLIND_LAG = 1          # میانهٔ اندازه‌گیری‌شدهٔ تأخیرِ Kennedy (CAUSALITY_*.json)


def shift_signal(sig, lag):
    """سیگنال را `lag` کندل به جلو می‌بَرد — «ورودِ کور با همان تأخیر».

    هیچ شرطِ دامنه‌ای اعمال نمی‌شود؛ فقط صبرِ مکانیکی. این بازوی مقایسه‌ای
    نشان می‌دهد چه مقدار از اثرِ Kennedy «اطلاع» است و چه مقدار «تأخیرِ محض».
    """
    out = np.zeros_like(sig)
    if lag <= 0:
        return sig.copy()
    out[lag:] = sig[:-lag]
    return out


def run_arm(df, ctxs, mode, mh, warm, n, blind_lag=0):
    rows = []
    allR = []
    n_raw = 0
    for k in FAM_K:
        for m_ in FAM_M:
            for s_ in FAM_S:
                ls, ss, slv, tpv, _ = member_signals_mode(
                    df, ctxs[k], m_, s_, ASSET, GATE, mode)
                if blind_lag:
                    ls = shift_signal(ls, blind_lag)
                    ss = shift_signal(ss, blind_lag)
                    slv = shift_signal(slv, blind_lag)
                    tpv = shift_signal(tpv, blind_lag)
                ls[:warm] = False
                ss[:warm] = False
                ls[n - mh - 2:] = False
                ss[n - mh - 2:] = False
                n_raw += int(ls.sum() + ss.sum())
                tr = se.simulate_trades(df, ls, ss, slv, tpv, ASSET,
                                        max_hold=mh, allow_overlap=False)
                if tr is None or len(tr) == 0:
                    continue
                sl = tr["sl_pip"].values.astype(float)
                okm = sl > 0
                if okm.sum() < MIN_TRADES:
                    continue
                R = tr["pnl_pip"].values[okm] / sl[okm]
                rows.append(dict(k=k, m=m_, s=s_, n=int(okm.sum()),
                                 meanR=round(float(R.mean()), 4)))
                allR.append(R)
    if not allR:
        return None
    pool = np.concatenate(allR)
    return dict(rows=rows, n_raw_sig=n_raw, n=int(len(pool)),
                trade_pooled=round(float(pool.mean()), 4),
                fam=round(float(np.mean([r["meanR"] for r in rows])), 4))


def main():
    df = se.load_data(f"data/{ASSET}_{TF}.csv")
    n = len(df)
    warm = min(260, max(30, n // 8))
    ctxs = {k: channel_context(df, k) for k in FAM_K}

    durs = []
    for k in FAM_K:
        l2, s2, _, _, d2 = member_signals_mode(df, ctxs[k], FAM_M[0], FAM_S[0],
                                               ASSET, GATE, "close")
        sel = l2 | s2
        if sel.any():
            durs.extend(d2[sel].tolist())
    mh = int(min(MAX_HOLD_CAP, max(5, round(HORIZON_MULT * float(np.median(durs))))))

    print(f"=== S375 FAMILY INTEGRITY :: {ASSET}-{TF}  mh={mh} ===")
    print(f"    blind arm lag = {BLIND_LAG} bar (median measured Kennedy lag)\n")

    arms = {}
    arms["close"] = run_arm(df, ctxs, "close", mh, warm, n)
    arms["kennedy"] = run_arm(df, ctxs, "kennedy", mh, warm, n)
    arms["blind"] = run_arm(df, ctxs, "close", mh, warm, n, blind_lag=BLIND_LAG)

    # ── آزمونِ ۱: تجزیهٔ سطحِ عضو ──
    print("-- آزمونِ ۱: meanR هر عضو در سه بازو --")
    print(f"   {'k':>2} {'m':>6} {'s':>6} | {'close':>18} | {'kennedy':>18}"
          f" | {'blind(+1)':>18} | {'Δken':>8} {'Δblind':>8}")
    idx = {(r["k"], r["m"], r["s"]): r for r in arms["close"]["rows"]}
    kidx = {(r["k"], r["m"], r["s"]): r for r in arms["kennedy"]["rows"]}
    bidx = {(r["k"], r["m"], r["s"]): r for r in arms["blind"]["rows"]}
    n_ken_better = n_blind_better = n_cmp = 0
    per_member = []
    for key in sorted(idx.keys()):
        c = idx[key]
        kk = kidx.get(key)
        bb = bidx.get(key)
        ck, cb = (kk["meanR"] if kk else None), (bb["meanR"] if bb else None)
        dk = (ck - c["meanR"]) if ck is not None else float("nan")
        db = (cb - c["meanR"]) if cb is not None else float("nan")
        if ck is not None and cb is not None:
            n_cmp += 1
            n_ken_better += int(dk > 0)
            n_blind_better += int(db > 0)
        print(f"   {key[0]:>2} {key[1]:>6} {key[2]:>6} |"
              f" n={c['n']:>4} R={c['meanR']:>+8.4f} |"
              f" n={(kk['n'] if kk else 0):>4} R={ck if ck is not None else float('nan'):>+8.4f} |"
              f" n={(bb['n'] if bb else 0):>4} R={cb if cb is not None else float('nan'):>+8.4f} |"
              f" {dk:>+8.4f} {db:>+8.4f}")
        per_member.append(dict(k=key[0], m=key[1], s=key[2],
                               R_close=c["meanR"], R_ken=ck, R_blind=cb,
                               d_ken=round(dk, 4) if ck is not None else None,
                               d_blind=round(db, 4) if cb is not None else None))

    print(f"\n   اعضایی که Kennedy بهبود داد : {n_ken_better}/{n_cmp}")
    print(f"   اعضایی که تأخیرِ کور بهبود داد: {n_blind_better}/{n_cmp}")

    # ── آزمونِ ۲: بازوی کور ──
    print(f"\n-- آزمونِ ۲ (کلیدی): تأخیرِ محض در برابرِ اطلاعِ Kennedy --")
    for tag in ("close", "kennedy", "blind"):
        a = arms[tag]
        print(f"   {tag:>8}: n={a['n']:>5}  trade_pooled={a['trade_pooled']:>+8.4f}"
              f"  fam={a['fam']:>+8.4f}  raw_sig={a['n_raw_sig']:>6}")
    d_ken = arms["kennedy"]["trade_pooled"] - arms["close"]["trade_pooled"]
    d_bld = arms["blind"]["trade_pooled"] - arms["close"]["trade_pooled"]
    print(f"\n   Δ Kennedy      = {d_ken:+.4f}")
    print(f"   Δ تأخیرِ کور   = {d_bld:+.4f}")
    info = d_ken - d_bld
    print(f"   ⇒ سهمِ **اطلاعِ** قاعده = {info:+.4f}"
          f"   (اگر ≈۰ ⇒ کلِ اثر تأخیرِ محض است)")

    # ── آزمونِ ۳: اثرِ صف‌بندی ──
    print(f"\n-- آزمونِ ۳: نرخِ حذفِ سیگنال به‌خاطرِ تداخل --")
    for tag in ("close", "kennedy", "blind"):
        a = arms[tag]
        keep = 100.0 * a["n"] / max(1, a["n_raw_sig"])
        print(f"   {tag:>8}: raw={a['n_raw_sig']:>6}  traded={a['n']:>5}"
              f"  نرخِ نگه‌داشت={keep:5.1f}%")

    verdict = ("INFO_NEGLIGIBLE_PURE_DELAY" if abs(info) < 0.02
               else ("INFO_POSITIVE" if info > 0 else "INFO_NEGATIVE"))
    print(f"\n   >>> {verdict}")

    out = dict(asset=ASSET, tf=TF, max_hold=mh, blind_lag=BLIND_LAG,
               arms={t: dict(n=arms[t]["n"],
                             trade_pooled=arms[t]["trade_pooled"],
                             fam=arms[t]["fam"],
                             n_raw_sig=arms[t]["n_raw_sig"])
                     for t in arms},
               d_kennedy=round(d_ken, 4), d_blind=round(d_bld, 4),
               info_share=round(info, 4),
               n_members_kennedy_better=n_ken_better,
               n_members_blind_better=n_blind_better,
               n_members_compared=n_cmp,
               per_member=per_member, verdict=verdict)
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/FAMILY_INTEGRITY_{ASSET}_{TF}.json"
    with open(p, "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"   → {p}")


if __name__ == "__main__":
    main()
