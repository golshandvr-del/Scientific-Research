"""
s202_h1_priceaction_battery.py — بردنِ لایه‌های *غیرزمانیِ* price-action روی XAUUSD H1
================================================================================
پاسخِ اعتراضِ کاربر: «بسه انقدر روی زمان مانور نده! ما کتاب خوندیم و استراتژی‌های
غیرزمانی کشف کردیم.»  ⇒ این‌بار به‌جای Overnight/Monday/MonthEffect، دو لایهٔ
price-action ِ Al Brooks که آخرین کشف‌های پذیرفته‌شدهٔ پروژه بودند را روی H1 می‌بریم:

  • S171 «Signs of Strength» (SoS)  — LONG  — w32/thr2 — رکوردِ M15: SL300/TP450/mh96
  • S173 «Market Inertia»           — SHORT — ema20/50·adx>28·lb20 — رکوردِ M15: SL250/TP375/mh48

منطقِ سیگنال دست‌نخورده از ماژول‌های اصلی import می‌شود (نه بازنویسی). فقط:
  1) داده = XAUUSD_H1 (به‌جای M15)
  2) max_hold متناسب با H1 (هر کندلِ H1 = ۴ کندلِ M15 ⇒ mh_H1 = mh_M15 / 4) + جاروب
  3) TP/SL چون pip-native اند ثابت‌اند و فقط همسایه‌ها جاروب می‌شوند
گیتِ سخت: net>0 و هر دو نیمه مثبت و WF ۴/۴ مثبت و WR≥۴۰٪ (ضدِ overfit).

خروجی روی هر دو بازه گزارش می‌شود: (الف) کلِ H1 (۲۰۱۱+، عمقِ کامل)  (ب) هم‌تراز با M15 (۲۰۲۰+).
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from engine import scalp_engine as se
from engine import indicators as ind
from s171_brooks_signs_of_strength_filter import (
    load, cal, stats, sim, signs_of_strength_bull)
from s173_brooks_market_inertia import inertia_signals

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M15_ALIGN_START = pd.Timestamp('2020-02-20')  # شروعِ داده M15 برای مقایسهٔ سیب‌به‌سیب


# ---------- سیگنال‌ها (منطق اصلی، فقط بسته‌بندی) -----------------------------
def sos_rising_edge(df, thr, ema_period, win):
    sos = signs_of_strength_bull(df, ema_period=ema_period, win=win)
    strong = sos['score'] >= thr
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


# ---------- گیتِ سخت -----------------------------------------------------------
def both_halves(df, longs, shorts, sl, tp, mh, asset):
    n = len(df); mid = n // 2
    a = stats(sim(df.iloc[:mid].reset_index(drop=True), longs[:mid], shorts[:mid], sl, tp, mh, asset), asset)
    b = stats(sim(df.iloc[mid:].reset_index(drop=True), longs[mid:], shorts[mid:], sl, tp, mh, asset), asset)
    return a['net'], b['net']


def walk_forward(df, longs, shorts, sl, tp, mh, asset, k=4):
    n = len(df); bnd = [int(n * i / k) for i in range(k + 1)]
    outs = []
    for i in range(k):
        lo, hi = bnd[i], bnd[i + 1]
        r = stats(sim(df.iloc[lo:hi].reset_index(drop=True),
                      longs[lo:hi], shorts[lo:hi], sl, tp, mh, asset), asset)
        outs.append(r['net'])
    return outs


def evaluate(df, longs, shorts, sl, tp, mh, asset, label):
    full = stats(sim(df, longs, shorts, sl, tp, mh, asset), asset)
    if full['n'] == 0:
        return dict(label=label, ok=False, reason='no-trades', net=0, wr=0, n=0)
    h1net, h2net = both_halves(df, longs, shorts, sl, tp, mh, asset)
    wf = walk_forward(df, longs, shorts, sl, tp, mh, asset, 4)
    ok = (full['net'] > 0 and h1net > 0 and h2net > 0 and min(wf) > 0 and full['wr'] >= 40.0)
    return dict(label=label, ok=ok, net=full['net'], wr=full['wr'], n=full['n'],
                pf=full['pf'], h1=h1net, h2=h2net, wf=[round(x) for x in wf],
                sl=sl, tp=tp, mh=mh)


def prow(r):
    tag = '✅' if r['ok'] else '  '
    if r.get('reason') == 'no-trades':
        print(f"  {tag} {r['label']:34s}  (بدون معامله)"); return
    print(f"  {tag} {r['label']:34s} net=${r['net']:+9,.0f}  WR={r['wr']:4.1f}%  "
          f"n={r['n']:4d}  PF={r['pf']:.2f}  halves=({r['h1']:+,.0f},{r['h2']:+,.0f})  "
          f"WF={r['wf']}")


def run_layer(name, side, dfx, base_sl, base_tp, base_mh_m15, sig_fn, band):
    """base_mh_m15 = mh در M15 ⇒ mh پایه در H1 = /4 ؛ سپس جاروب همسایه."""
    print("\n" + "=" * 92)
    print(f"لایهٔ غیرزمانی: {name}  ({side})  |  {band}")
    print("=" * 92, flush=True)
    longs = sig_fn(dfx)
    shorts = np.zeros(len(dfx), bool)
    if side == 'short':
        shorts, longs = longs, np.zeros(len(dfx), bool)
    print(f"  تعداد سیگنالِ خام: {int(longs.sum() + shorts.sum())}")

    mh_base = max(6, round(base_mh_m15 / 4))
    winners = []
    # جاروب: SL/TP همسایه (pip-native) × mh متناسب H1
    for sl in [base_sl - 50, base_sl, base_sl + 50, base_sl + 100]:
        for tp in [base_tp - 75, base_tp, base_tp + 150, base_tp + 300]:
            for mh in sorted(set([max(6, mh_base // 2), mh_base, mh_base * 2, mh_base * 4])):
                if sl <= 0 or tp <= 0:
                    continue
                r = evaluate(dfx, longs, shorts, sl, tp, mh, 'XAUUSD',
                             f"{name[:12]} SL{sl}/TP{tp}/mh{mh}")
                if r['ok']:
                    winners.append(r)
    if winners:
        winners.sort(key=lambda x: -x['net'])
        print(f"  🏆 گیت-پاس‌ها ({len(winners)}):")
        for r in winners[:6]:
            prow(r)
    else:
        # بهترین از نظر net را برای دیدِ کیفی نشان بده حتی اگر گیت رد شد
        allr = []
        for sl in [base_sl, base_sl + 50]:
            for tp in [base_tp, base_tp + 150]:
                for mh in [mh_base, mh_base * 2]:
                    allr.append(evaluate(dfx, longs, shorts, sl, tp, mh, 'XAUUSD',
                                         f"{name[:12]} SL{sl}/TP{tp}/mh{mh}"))
        allr.sort(key=lambda x: -x['net'])
        print("  ❌ هیچ ترکیبی گیتِ سخت را پاس نکرد. بهترین از نظر net (کیفی):")
        for r in allr[:3]:
            prow(r)
    return winners


def main():
    print("#" * 92)
    print("# s202 — لایه‌های *غیرزمانیِ* price-action (Brooks) روی XAUUSD H1")
    print("# S171 Signs-of-Strength (LONG) + S173 Market-Inertia (SHORT)")
    print("#" * 92, flush=True)

    df_full = cal(load('XAUUSD_H1'))
    df_align = df_full[df_full['dt'] >= M15_ALIGN_START].reset_index(drop=True)
    print(f"\nH1 کل: {len(df_full):,} کندل  ({df_full['dt'].min()} → {df_full['dt'].max()})")
    print(f"H1 هم‌تراز با M15 (۲۰۲۰+): {len(df_align):,} کندل")

    sos_fn = lambda d: sos_rising_edge(d, 2, 20, 32)
    inertia_short_fn = lambda d: inertia_signals(d, 20, 50, 28, 20, 'short')

    all_winners = {}
    for band, dfx in [('کلِ H1 (۲۰۱۱+)', df_full), ('هم‌تراز M15 (۲۰۲۰+)', df_align)]:
        w1 = run_layer('SoS(SignsOfStrength)', 'long', dfx, 300, 450, 96, sos_fn, band)
        w2 = run_layer('MarketInertia', 'short', dfx, 250, 375, 48, inertia_short_fn, band)
        all_winners[band] = dict(SoS=w1, Inertia=w2)

    # ذخیرهٔ خلاصه
    def top(ws):
        return (sorted(ws, key=lambda x: -x['net'])[0] if ws else None)
    summary = {}
    for band, d in all_winners.items():
        summary[band] = {k: top(v) for k, v in d.items()}
    with open(os.path.join(ROOT, 'results', '_s202_h1_priceaction.json'), 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "#" * 92)
    print("# خلاصهٔ نهایی (بهترین گیت-پاسِ هر لایه در هر بازه):")
    for band, d in summary.items():
        print(f"\n  ▶ {band}")
        for layer, r in d.items():
            if r:
                print(f"     ✅ {layer}: net=${r['net']:+,.0f}  WR={r['wr']:.1f}%  "
                      f"SL{r['sl']}/TP{r['tp']}/mh{r['mh']}")
            else:
                print(f"     ❌ {layer}: گیت-پاس ندارد روی این بازه")
    print("#" * 92)


if __name__ == '__main__':
    main()
