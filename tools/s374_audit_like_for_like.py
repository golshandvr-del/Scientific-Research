# -*- coding: utf-8 -*-
"""
بازرسیِ مستقلِ S374 — «مقایسهٔ هم‌سنگ» (like-for-like)

═══════════════════════════════════════════════════════════════════════════
چرا این ابزار لازم شد
═══════════════════════════════════════════════════════════════════════════
اجرای نخستِ S374 روی H4 نتیجه‌ای داد که **خلافِ پیش‌بینیِ پیش‌ثبت‌شده** بود و
بیش از حد خوب می‌نمود (`e_pip` طلا از ۱۱.۶۷ به ۳۲.۹۷). طبقِ پروتکل، نخستین
فرضیه در برابرِ نتیجهٔ خیلی‌خوب **تقلبِ آماری** است، نه کشف.

بازرسیِ دستی دو مسئله یافت:

① **نشتِ آینده — بررسی شد و وجود ندارد.** `engine/scalp_engine.py:146` ورود را
   روی `entry_bar = si + 1` و با `o[entry_bar]` انجام می‌دهد. پس هنگامِ ورود،
   کندلِ سیگنال **بسته شده** و `high`/`low` آن کاملاً معلوم‌اند. استفاده از
   `high`/`low`ِ کندلِ سیگنال **forward-safe** است.

② **سوگیریِ انتخابِ عضو — وجود دارد و باید اندازه‌گیری شود.** شرطِ Kennedy
   اکیداً سخت‌تر است، پس بعضی اعضا زیرِ `MIN_TRADES` می‌افتند و **حذف**
   می‌شوند. در H4 چهار عضوِ `XAUUSD,k=2` حذف شدند. آمارهٔ خانواده روی اعضای
   **باقی‌مانده** محاسبه می‌شود ⇒ دو حالت روی **مجموعه‌های متفاوتی از اعضا**
   مقایسه می‌شوند. این یک مقایسهٔ ناهم‌سنگ است.

═══════════════════════════════════════════════════════════════════════════
جهتِ سوگیری — اندازه‌گیری‌شده، نه فرض‌شده
═══════════════════════════════════════════════════════════════════════════
در H4 اعضای حذف‌شده در حالتِ پایه `meanR=+0.1826` داشتند در برابرِ `+0.0219`
برای اعضای باقی‌مانده ⇒ حذفشان **به زیانِ** حالتِ Kennedy است، نه به سودش.

⇒ دلتای صادقانه (هم‌سنگ) **بزرگ‌تر** از دلتای خام است: `+0.1399` در برابرِ
   `+0.1131`. یعنی سوگیری در H4 **محافظه‌کارانه** است.

ولی جهتِ سوگیری یک **یافتهٔ تجربی روی یک کارت** است، نه یک قانون. این ابزار
آن را روی **هر** کارت اندازه می‌گیرد و اجازه نمی‌دهد فرض شود.

═══════════════════════════════════════════════════════════════════════════
سه سنجهٔ گزارش‌شده
═══════════════════════════════════════════════════════════════════════════
`delta_raw`     : اختلافِ حالت‌ها روی مجموعه‌های اعضای خودشان (سنجهٔ اجرای اصلی)
`delta_l4l`     : اختلاف روی **اشتراکِ** مجموعه‌ها (مقایسهٔ هم‌سنگ)
`bias_direction`: علامتِ (`delta_l4l − delta_raw`)
                  منفی ⇒ سوگیری به **سودِ** Kennedy بود (خطرناک)
                  مثبت ⇒ سوگیری به **زیانِ** Kennedy بود (محافظه‌کارانه)

⚠️ این ابزار **حکم صادر نمی‌کند**. فقط اندازه می‌گیرد. حکم در فایلِ لایه است.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCAN = "results/_scan_S374"
KEY = ("asset", "k", "m", "s")


def _mkey(m):
    return tuple(m[x] for x in KEY)


def audit_card(tf):
    path = f"{SCAN}/{tf}.json"
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    if "base" not in d or "kennedy" not in d:
        return dict(tf=tf, status=d.get("verdict", "NO_ARMS"))

    bm = {_mkey(m): m for m in d["base"]["members"]}
    km = {_mkey(m): m for m in d["kennedy"]["members"]}
    inter = sorted(set(bm) & set(km), key=str)
    dropped = sorted(set(bm) - set(km), key=str)
    added = sorted(set(km) - set(bm), key=str)

    base_all = float(np.mean([bm[k]["meanR"] for k in bm]))
    ken_all = float(np.mean([km[k]["meanR"] for k in km]))
    base_int = float(np.mean([bm[k]["meanR"] for k in inter])) if inter else float("nan")
    ken_int = float(np.mean([km[k]["meanR"] for k in inter])) if inter else float("nan")

    delta_raw = ken_all - base_all
    delta_l4l = ken_int - base_int
    bias = delta_l4l - delta_raw

    drop_meanR = float(np.mean([bm[k]["meanR"] for k in dropped])) if dropped else float("nan")
    keep_meanR = base_int

    # نگه‌داشتِ سیگنال روی اعضای مشترک (بی‌اثر از حذفِ اعضا)
    nb = sum(bm[k]["n"] for k in inter)
    nk = sum(km[k]["n"] for k in inter)

    # نگه‌داشتِ خامِ هندسی (شاملِ اعضای حذف‌شده) از شمارِ سیگنالِ خام
    rb = sum(e["n_raw_sig"] for e in d["base"]["econ"].values())
    rk = sum(e["n_raw_sig"] for e in d["kennedy"]["econ"].values())

    # آیا هر عضوِ مشترک بهبود یافت؟ (آزمونِ علامت — مصون از وزن‌دهی)
    wins = sum(1 for k in inter if km[k]["meanR"] > bm[k]["meanR"])

    return dict(
        tf=tf, status="OK",
        n_base=len(bm), n_ken=len(km), n_inter=len(inter),
        n_dropped=len(dropped), n_added=len(added),
        dropped=[list(x) for x in dropped],
        base_all=round(base_all, 4), ken_all=round(ken_all, 4),
        base_inter=round(base_int, 4), ken_inter=round(ken_int, 4),
        delta_raw=round(delta_raw, 4), delta_l4l=round(delta_l4l, 4),
        bias=round(bias, 4),
        bias_direction=("CONSERVATIVE (hurt kennedy)" if bias > 0 else
                        "OPTIMISTIC (helped kennedy)" if bias < 0 else "NONE"),
        dropped_base_meanR=(round(drop_meanR, 4) if dropped else None),
        kept_base_meanR=round(keep_meanR, 4),
        retention_inter_pct=round(100.0 * nk / nb, 1) if nb else None,
        retention_rawsig_pct=round(100.0 * rk / rb, 1) if rb else None,
        sign_test_wins=wins, sign_test_n=len(inter),
    )


def main():
    tfs = sys.argv[1:] or ["M5", "M15", "M30", "H1", "H4"]
    out = []
    print("=" * 78)
    print("S374 LIKE-FOR-LIKE AUDIT  —  independent of the layer's own verdict")
    print("=" * 78)
    for tf in tfs:
        r = audit_card(tf)
        if r is None:
            print(f"\n[{tf}] (no result file yet)")
            continue
        if r.get("status") != "OK":
            print(f"\n[{tf}] status={r['status']}")
            out.append(r)
            continue
        print(f"\n[{tf}]  members: base={r['n_base']} ken={r['n_ken']} "
              f"inter={r['n_inter']} dropped={r['n_dropped']} added={r['n_added']}")
        if r["n_dropped"]:
            print(f"       dropped members' BASE meanR = {r['dropped_base_meanR']:+.4f}"
                  f"   vs kept = {r['kept_base_meanR']:+.4f}")
        print(f"       delta_raw (own member sets) = {r['delta_raw']:+.4f}")
        print(f"       delta_l4l (shared members)  = {r['delta_l4l']:+.4f}")
        print(f"       bias = {r['bias']:+.4f}  ⇒ {r['bias_direction']}")
        print(f"       retention: rawsig={r['retention_rawsig_pct']}%"
              f"  shared-members={r['retention_inter_pct']}%")
        print(f"       sign test: {r['sign_test_wins']}/{r['sign_test_n']}"
              f" shared members improved")
        out.append(r)

    os.makedirs(SCAN, exist_ok=True)
    with open(f"{SCAN}/_audit_like_for_like.json", "w") as f:
        json.dump(out, f, indent=1)
    print(f"\n[saved] {SCAN}/_audit_like_for_like.json")


if __name__ == "__main__":
    main()
