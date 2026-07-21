"""
S133 — ارزیابیِ سرمایه‌محورِ لایهٔ Squeeze→Breakout (مقایسهٔ سیب‌به‌سیب با رکورد)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate (WR).**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز XAUUSD + EURUSD. WR فقط عددِ گزارشی است.

انگیزه:
  s132 نشان داد ماشهٔ Squeeze→Breakout با «لاتِ ثابت ۰.۰۱» فقط ~+$1,154 می‌دهد. اما
  رکوردِ پروژه (+$101,259) با «ریسکِ درصدیِ ۱٪ + compounding» (se.run_capital) ساخته
  شده — نه لاتِ ثابت. این فایل همان سیگنال‌ها را با **دقیقاً همان موتورِ سرمایهٔ رکورد**
  اجرا می‌کند تا سودِ خالص **قابل‌مقایسه** به‌دست آید و روشن شود آیا این لایه ارزشِ
  افزوده‌شدن به پرتفوی را دارد یا نه.

روش (کنترلِ علمی):
  • همان ماشهٔ برندهٔ s132 (sqz_pct=0.25, breakout_lookback=6) + بهترین خروجِ ضدِ overfit.
  • se.run_capital(trades, 'XAUUSD', initial_capital=10000, risk_pct=1.0, compounding=True)
    — دقیقاً امضایی که s128 (لایهٔ +$15,659) و رکورد استفاده کرد.
  • sl_pip روی هر معامله ثبت می‌شود (برای تعیینِ لاتِ ریسکِ ثابت).
  • گیت‌های ضدِ overfit سرمایه‌محور: net کل + هر دو نیمه + هر ۴ پنجرهٔ WF مثبت.
  • چند خروجِ برترِ s132 آزمون می‌شوند تا برندهٔ سرمایه‌محور مشخص شود.
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

RESULTS = os.path.join(ROOT, 'results')


def cap_net(df, entries, tp, sl, tb, cat_sl=400.0):
    """سودِ خالصِ سرمایه‌محور (ریسکِ ۱٪ + compounding) — همان موتورِ رکورد."""
    if len(entries) == 0:
        return None
    exit_fn = make_hidden_exit(tp, sl, use_trend_break=tb)
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=MAX_HOLD_M15)
    if len(tr) == 0:
        return None
    tr = tr.copy()
    tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=10000.0, risk_pct=1.0, compounding=True)
    return st


def net_of(st):
    if not st:
        return 0.0
    for k in ('net_profit', 'net', 'total_net', 'net_usd'):
        if k in st:
            return float(st[k])
    return 0.0


def halves(df, tp, sl, tb, **trig):
    n = len(df); half = n // 2
    df1 = df.iloc[:half].reset_index(drop=True)
    df2 = df.iloc[half:].reset_index(drop=True)
    s1 = cap_net(df1, build_entries_squeeze(df1, **trig), tp, sl, tb)
    s2 = cap_net(df2, build_entries_squeeze(df2, **trig), tp, sl, tb)
    return net_of(s1), net_of(s2)


def walkforward(df, tp, sl, tb, k=4, **trig):
    n = len(df)
    bounds = [int(n * j / k) for j in range(k + 1)]
    nets = []
    for w in range(k):
        lo, hi = bounds[w], bounds[w + 1]
        seg = df.iloc[lo:hi].reset_index(drop=True)
        nets.append(net_of(cap_net(seg, build_entries_squeeze(seg, **trig), tp, sl, tb)))
    return nets


def main():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    trig = dict(sqz_pct=0.25, breakout_lookback=6)

    print("=" * 92)
    print("S133 — سودِ خالصِ سرمایه‌محورِ لایهٔ Squeeze→Breakout (ریسک ۱٪ + compounding)")
    print("=" * 92)
    print(f"داده: {len(df):,} کندلِ M15   ماشه: {trig}")
    print("موتورِ سرمایه: se.run_capital(XAUUSD, 10k, risk 1%, compounding) — همان رکورد.")
    print("baselineِ لایهٔ اسکالپِ رکورد (ScalpV2) = +$15,659 برای مقایسهٔ اندازه.\n")

    ent_full = build_entries_squeeze(df, **trig)
    print(f"تعدادِ کلِ ورودها روی ۱۵۰k: {len(ent_full)}\n")

    print(f"{'TP':>4} {'SL':>4} {'tb':>3} | {'net(cap)':>11} {'lots~':>7} | "
          f"{'½1':>10} {'½2':>10} {'WFمثبت':>7} {'گیت':>5}")
    print("-" * 92)

    # خروج‌های برترِ s132 (بر مبنای net لاتِ ثابت) را سرمایه‌محور بازآزمایی کن
    exit_grid = [
        (300, 90, False), (250, 120, True), (300, 90, True),
        (200, 120, True), (250, 90, False), (200, 90, False),
        (300, 120, True), (200, 90, True),
    ]
    rows = []
    for (tp, sl, tb) in exit_grid:
        st = cap_net(df, ent_full, tp, sl, tb)
        net = net_of(st)
        lots = st.get('avg_lots', st.get('mean_lots', float('nan'))) if st else float('nan')
        n1, n2 = halves(df, tp, sl, tb, **trig)
        wf = walkforward(df, tp, sl, tb, **trig)
        wf_pos = sum(1 for x in wf if x > 0)
        both = (n1 > 0 and n2 > 0)
        gate = "✅" if (both and wf_pos == 4 and net > 0) else ""
        print(f"{tp:>4} {sl:>4} {str(tb)[0]:>3} | {net:>11,.0f} {lots:>7.2f} | "
              f"{n1:>10,.0f} {n2:>10,.0f} {wf_pos:>7} {gate:>5}")
        rows.append(dict(tp=tp, sl=sl, tb=tb, net=net, half1=n1, half2=n2,
                         wf=wf, wf_pos=wf_pos, both=both))

    clean = [r for r in rows if r['both'] and r['wf_pos'] == 4 and r['net'] > 0]
    print("\n" + "=" * 92)
    if clean:
        win = max(clean, key=lambda r: r['net'])
        print(f"🏆 برندهٔ سرمایه‌محورِ ضدِ overfit: TP={win['tp']} SL={win['sl']} tb={win['tb']}")
        print(f"   سودِ خالصِ سرمایه‌محور = +${win['net']:,.0f}")
        print(f"   نیمه‌ها: +${win['half1']:,.0f} / +${win['half2']:,.0f}  |  WF={['%.0f'%x for x in win['wf']]}")
        print(f"\n   مقایسه با baselineِ اسکالپِ رکورد (+$15,659):")
        if win['net'] > 15659:
            print(f"   ✅ این لایه به‌تنهایی از baselineِ اسکالپ بزرگ‌تر است.")
        else:
            print(f"   ℹ️ کوچک‌تر از baselineِ اسکالپ؛ ارزشِ افزوده بستگی به ناهمبستگی دارد (گامِ بعد s134).")
    else:
        win = max(rows, key=lambda r: r['net']) if rows else None
        print("⚠️ هیچ خروجی همهٔ گیت‌های سرمایه‌محور را سبز نکرد.")
        if win:
            print(f"   بهترین (مشروط): TP={win['tp']} SL={win['sl']} tb={win['tb']} → "
                  f"+${win['net']:,.0f} (both={win['both']}, WF+={win['wf_pos']}/4)")

    out = dict(trigger=trig, n_entries=len(ent_full), rows=rows,
               winner=win if rows else None, clean_exists=bool(clean))
    with open(os.path.join(RESULTS, '_s133_squeeze_capital.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("\nخلاصه در results/_s133_squeeze_capital.json ذخیره شد.")
    print("قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD (نه WR).")


if __name__ == '__main__':
    main()
