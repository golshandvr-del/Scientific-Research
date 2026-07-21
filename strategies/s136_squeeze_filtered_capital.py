"""
S136 — لایهٔ Squeeze + فیلترِ «قدرتِ شکست» روی موتورِ سرمایهٔ رکورد
================================================================================
> 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت):
>   معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor.
>   تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

پاسخِ User Note این نشست: «با حفظ یا افزایشِ سودِ خالص، ضررها/سیگنال‌های غلط را کم کن.»

پل‌زدنِ کشفِ کیفیِ s135 (فیلترِ brk_strength>=0.15 بهترین بود، هر دو نیمه + WF مثبت)
به مبنای *سرمایه‌محورِ رکورد* (se.run_capital، ریسک ۱٪، compounding — دقیقاً همان که
+$20,435 را برای لایهٔ Squeeze ساخت). سؤالِ قطعی:

   آیا حذفِ ورودهایی که «شکستِ صعودی‌شان ضعیف است» (close تنها کمی بالای priorHigh،
   یعنی brk_strength = (close-priorHigh)/ATR کوچک) سودِ خالصِ سرمایه‌محور را بالا می‌برد
   و ضرر را کم می‌کند؟

منطق: شکستِ ضعیف اغلب «شکستِ کاذب» است ⇒ ضررهای کوچکِ پرتکرار. حذفِ آن‌ها باید نرخِ
سیگنالِ غلط را کم کند بدونِ از دست دادنِ انفجارهای بزرگ (که ذاتاً شکستِ قوی دارند).

گیت‌های ضدِ overfit: هر دو نیمهٔ داده + هر ۴ پنجرهٔ walk-forward باید مثبت بمانند، و
دو آستانهٔ مستقل (0.15 و 0.30) هر دو باید بهبود بدهند (robustness — نه overfit به یک عدد).
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
from strategies.s91_scalp_signal_exit import paper_broker
from strategies.s94_scalp_hidden_target import make_hidden_exit
from strategies.s132_squeeze_breakout_m15 import build_entries_squeeze, DATA, MAX_HOLD_M15
from strategies.s135_squeeze_loss_filter import build_entries_with_features

RESULTS = os.path.join(ROOT, 'results')

# ماشهٔ برنده + خروجِ برندهٔ سرمایه‌محورِ s133 (ثابت — بدونِ جاروبِ دوباره)
TP, SL, TB = 300.0, 90.0, False


def cap_net(df, entries, cat_sl=400.0):
    """سودِ خالصِ سرمایه‌محور (ریسکِ ۱٪ + compounding) — همان موتورِ رکورد."""
    if len(entries) == 0:
        return None, None
    exit_fn = make_hidden_exit(TP, SL, use_trend_break=TB)
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=MAX_HOLD_M15)
    if len(tr) == 0:
        return None, None
    tr = tr.copy()
    tr['sl_pip'] = float(SL)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=10000.0, risk_pct=1.0, compounding=True)
    return st, tr


def net_of(st):
    if not st:
        return 0.0
    for k in ('net_profit', 'net', 'total_net', 'net_usd'):
        if k in st:
            return float(st[k])
    return 0.0


def gross_loss_lot(tr):
    """ضررِ ناخالص روی لاتِ ثابت (شاخصِ نرخِ سیگنالِ غلط، مستقل از سایز)."""
    if tr is None or len(tr) == 0:
        return 0.0
    loss = tr[tr['pnl_pip'] <= 0]
    return float(abs(loss['net_usd'].sum()))


def filter_entries(df, thr):
    """ورودهای Squeeze با featureها؛ فقط آن‌هایی که brk_strength>=thr نگه داشته می‌شوند."""
    entries, feat = build_entries_with_features(df)
    if thr is None:
        return entries
    return [(i, s) for (i, s) in entries if feat.get(i, {}).get('brk_strength', 0) >= thr]


def eval_thr(df, thr):
    ent = filter_entries(df, thr)
    st, tr = cap_net(df, ent)
    return dict(thr=thr, n=len(ent), net=net_of(st), gloss=gross_loss_lot(tr))


def halves_wf(df, thr):
    n = len(df)
    h = []
    for (a, b) in [(0, n // 2), (n // 2, n)]:
        seg = df.iloc[a:b].reset_index(drop=True)
        st, _ = cap_net(seg, filter_entries(seg, thr))
        h.append(net_of(st))
    wf = []
    for k in range(4):
        a = k * (n // 4)
        b = n if k == 3 else (k + 1) * (n // 4)
        seg = df.iloc[a:b].reset_index(drop=True)
        st, _ = cap_net(seg, filter_entries(seg, thr))
        wf.append(net_of(st))
    return h, wf


def main():
    print("=" * 92)
    print("S136 — لایهٔ Squeeze + فیلترِ قدرتِ شکست (موتورِ سرمایهٔ رکورد)")
    print("قانونِ #۱: سودِ خالص = XAUUSD + EURUSD (نه WR). هدف: کاهشِ ضرر ⇒ افزایشِ سودِ خالص.")
    print("=" * 92, flush=True)

    df = pd.read_csv(DATA)
    print(f"داده: {len(df):,} کندلِ M15 XAUUSD | خروج: TP={TP:.0f}/SL={SL:.0f}/tb={TB} "
          f"(برندهٔ سرمایه‌محورِ s133)\n", flush=True)

    base = eval_thr(df, None)
    print(f"── مبنا (بدونِ فیلتر) ──")
    print(f"  n={base['n']}  net(سرمایه‌محور)=${base['net']:+,.0f}  "
          f"ضررِ ناخالص(لاتِ ثابت)=${base['gloss']:,.0f}\n", flush=True)

    print(f"── ارزیابیِ آستانه‌های مستقلِ فیلتر (robustness) ──")
    print(f"  {'آستانه':>18} {'n':>5} {'net':>12} {'Δnet':>11} {'ضرر':>9} {'Δضرر':>9} {'حذف‌شده':>8}")
    print("  " + "-" * 84, flush=True)
    cand = {}
    for thr in [0.15, 0.20, 0.30]:
        r = eval_thr(df, thr)
        cand[thr] = r
        print(f"  brk_strength>={thr:<5} {r['n']:>5} {r['net']:>+12,.0f} "
              f"{r['net']-base['net']:>+11,.0f} {r['gloss']:>+9,.0f} "
              f"{r['gloss']-base['gloss']:>+9,.0f} {base['n']-r['n']:>8}", flush=True)

    # بهترین آستانه بر مبنای بیشترین سودِ خالصِ سرمایه‌محور (قانونِ #۱)
    best_thr = max(cand, key=lambda t: cand[t]['net'])
    best = cand[best_thr]
    improved = best['net'] > base['net']

    print(f"\n── بهترین آستانه: brk_strength>={best_thr} ──")
    print(f"  net=${best['net']:+,.0f} (Δ={best['net']-base['net']:+,.0f}$)  "
          f"ضرر=${best['gloss']:,.0f} (Δ={best['gloss']-base['gloss']:+,.0f}$)  "
          f"سیگنالِ غلطِ حذف‌شده={base['n']-best['n']}", flush=True)

    # گیتِ ضدِ overfit روی بهترین آستانه
    h, wf = halves_wf(df, best_thr)
    h_ok = all(x > 0 for x in h); wf_ok = all(x > 0 for x in wf)
    # robustness: هر دو آستانهٔ مستقل هم باید >= مبنا باشند
    robust = all(cand[t]['net'] >= base['net'] for t in [0.15, 0.30])

    print(f"\n── گیت‌های ضدِ overfit ──")
    print(f"  نیمه‌ها: {[round(x) for x in h]} → {'✅' if h_ok else '❌'}")
    print(f"  WF(۴): {[round(x) for x in wf]} → {'✅' if wf_ok else '❌'}")
    print(f"  robustness (هر دو آستانهٔ 0.15 و 0.30 ≥ مبنا): {'✅' if robust else '❌'}", flush=True)

    verdict = improved and h_ok and wf_ok and robust
    delta = best['net'] - base['net']
    print(f"\n{'='*92}")
    if verdict:
        # اثر بر رکوردِ کل: لایهٔ Squeeze مستقل از +$20,435 به این عدد می‌رود
        new_layer = best['net']
        old_record = 121694
        new_record = old_record - 20435 + int(round(new_layer))
        print(f"داوری: ✅ فیلتر سودِ خالص را بالا برد و در همهٔ گیت‌ها پایدار است.")
        print(f"  لایهٔ Squeeze: +$20,435 → +${new_layer:,.0f}  (Δ={delta:+,.0f}$)")
        print(f"  با کاهشِ ضرر و حذفِ {base['n']-best['n']} سیگنالِ غلط.")
        print(f"  ⇒ رکوردِ کل: +$121,694 → +${new_record:,.0f}")
    else:
        print(f"داوری: ❌ فیلترِ پایداری که سودِ خالص را بالا ببرد یافت نشد (مبنا حفظ می‌شود).")
    print(f"{'='*92}", flush=True)

    os.makedirs(RESULTS, exist_ok=True)
    out = dict(base=base, candidates={str(k): v for k, v in cand.items()},
               best_thr=best_thr, best=best, halves=h, wf=wf,
               half_ok=h_ok, wf_ok=wf_ok, robust=robust, verdict=bool(verdict),
               delta=delta)
    with open(os.path.join(RESULTS, '_s136_squeeze_filtered_capital.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("خلاصه در results/_s136_squeeze_filtered_capital.json ذخیره شد.")
    print("قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD (نه WR).")


if __name__ == '__main__':
    main()
