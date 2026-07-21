"""
S134 — آزمونِ افزایشی‌بودنِ لایهٔ Squeeze→Breakout در پرتفویِ رکورد (+$101,259)
================================================================================
مرجعِ قانونِ #۱ (PARADIGM.md): معیارِ موفقیت فقط «سودِ خالص = XAUUSD + EURUSD»
است، نه WR. یک لایهٔ جدید فقط وقتی ارزش دارد که سودِ خالصِ *کلِ پرتفوی* را بالا
ببرد — نه اینکه صرفاً به‌تنهایی مثبت باشد.

چرا این آزمون حیاتی است؟
------------------------
s133 نشان داد لایهٔ Squeeze با موتورِ سرمایه‌محور (ریسک ۱٪، compounding=True)
به‌تنهایی ≈ +$20,435 می‌دهد. اما این با تنظیماتِ پرتفویِ رکورد (compounding=False،
از طریقِ SE.simulate_trades + run_capital_pertrade) یکی نیست. درسِ S88 در README:
یک لایهٔ سودده اگر با لایه‌های موجود «هم‌پوشانِ زمانی/جهتی» باشد، سودِ اضافه‌اش
تکراری است و پرتفوی را بالا نمی‌برد.

روشِ سیب‌به‌سیب (کاملاً هم‌تراز با s130):
  • لایهٔ Squeeze با SE.simulate_trades(long_sig, ...) + run_capital_pertrade
    (compounding=False، ریسک ۱٪) ساخته می‌شود — دقیقاً مثلِ ۵ لایهٔ رکورد.
  • per-trade هر دو پرتفوی (۵-لایه پایه و ۶-لایه) در بازهٔ YEARS_BACK سالِ اخیر
    (همان فیلترِ s130) جمع می‌شود.
  • گزارش: سودِ خالصِ پایه، سودِ خالصِ ۶-لایه، Δ، و همبستگیِ روزانهٔ لایهٔ نو
    با پرتفویِ پایه (اگر همبستگی بالا باشد ⇒ تکراری).

هیچ overfit-ی: پارامترِ ماشهٔ Squeeze همان برندهٔ s133 است (بدونِ جاروبِ دوباره).

قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD (نه WR).
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import engine.scalp_engine as SE
from strategies import s130_portfolio_periodic_equity as S130
from strategies.s132_squeeze_breakout_m15 import (
    build_entries_squeeze, bollinger_bandwidth, rolling_min_percentile,
)

# ثابت‌های هم‌تراز با s130
CAP = S130.CAP            # 10_000
RISK = S130.RISK          # 1.0
YEARS_BACK = S130.YEARS_BACK  # 4

# برندهٔ s133 (بدونِ جاروبِ دوباره — جلوگیری از overfit)
SQZ_TP = 300.0
SQZ_SL = 90.0
SQZ_MAX_HOLD = 96         # ۲۴ ساعت روی M15 (مثلِ s132)


def build_squeeze_layer():
    """لایهٔ Squeeze با تنظیماتِ کاملاً هم‌تراز با ۵ لایهٔ رکورد (s130)."""
    asset = 'XAUUSD'   # M15 = دارایی پیش‌فرضِ XAUUSD در ASSETS
    df = SE.load_data(SE.ASSETS[asset]['file'])
    n = len(df)

    # ماشهٔ ورود (long-only) → آرایهٔ بولین برای simulate_trades
    entries = build_entries_squeeze(df, sqz_pct=0.15, breakout_lookback=10,
                                    trend_gate=True)
    long_sig = np.zeros(n, dtype=bool)
    for (i, side) in entries:
        if 0 <= i < n:
            long_sig[i] = True
    short_sig = np.zeros(n, dtype=bool)

    tr = SE.simulate_trades(df, long_sig, short_sig,
                            SQZ_SL, SQZ_TP, asset, max_hold=SQZ_MAX_HOLD)
    stats, eq, pt = SE.run_capital_pertrade(tr, asset, df=df,
                                            initial_capital=CAP,
                                            risk_pct=RISK, compounding=False)
    return dict(name='S132 (طلا M15 · Squeeze→Breakout)', stats=stats, pt=pt)


def portfolio_net(layers, cutoff=None):
    """جمعِ per-trade همهٔ لایه‌ها در بازهٔ اخیر ⇒ سودِ خالصِ کل."""
    total = 0.0
    per_layer = {}
    all_dt = []
    for L in layers:
        pt = S130.filter_recent(L['pt'], years=YEARS_BACK, cutoff=cutoff)
        net = float(pt['net_usd'].sum()) if len(pt) else 0.0
        per_layer[L['name']] = dict(net=net, n=int(len(pt)))
        total += net
        if len(pt):
            all_dt.append(pt[['dt', 'net_usd']].copy())
    return total, per_layer, all_dt


def daily_series(pt_list):
    """سریِ سود/زیانِ روزانه از فهرستِ per-trade frameها."""
    if not pt_list:
        return pd.Series(dtype=float)
    df = pd.concat(pt_list, ignore_index=True)
    df['day'] = pd.to_datetime(df['dt']).dt.floor('D')
    return df.groupby('day')['net_usd'].sum()


def main():
    print("=" * 92)
    print("S134 — آزمونِ افزایشی‌بودنِ لایهٔ Squeeze→Breakout در پرتفویِ رکورد")
    print("=" * 92)

    # ۱) ساختِ ۵ لایهٔ رکورد (بازاستفاده از s130)
    print("\n── ساختِ ۵ لایهٔ رکورد (S67 · ScalpV2 · S81 · SHORT · S73) ──", flush=True)
    base_layers = [
        S130.layer_s67(),
        S130.layer_scalpv2(),
        S130.layer_s81(),
        S130.layer_short(),
        S130.layer_s73(),
    ]
    print("  ✓ ۵ لایه ساخته شد.", flush=True)

    # ۲) ساختِ لایهٔ جدید Squeeze
    print("\n── ساختِ لایهٔ نو: S132 Squeeze→Breakout (طلا M15) ──", flush=True)
    sq = build_squeeze_layer()
    print(f"  ✓ لایهٔ Squeeze ساخته شد: {len(sq['pt'])} معامله (کلِ تاریخچه).", flush=True)

    # هم‌ترازیِ cutoff: مثلِ s130 از آخرین dtِ همهٔ لایه‌ها
    all_layers = base_layers + [sq]
    max_dt = max(L['pt']['dt'].max() for L in all_layers if len(L['pt']))
    cutoff = max_dt - pd.DateOffset(years=YEARS_BACK)

    # ۳) سودِ خالصِ پایه (۵ لایه) و ۶-لایه
    base_net, base_per, base_dt = portfolio_net(base_layers, cutoff=cutoff)
    full_net, full_per, full_dt = portfolio_net(all_layers, cutoff=cutoff)
    delta = full_net - base_net

    print("\n" + "=" * 92)
    print(f"بازهٔ ارزیابی: {YEARS_BACK} سالِ اخیر (از {cutoff.date()} تا {max_dt.date()})")
    print("-" * 92)
    print("سهمِ هر لایه (سودِ خالص، تعدادِ معامله):")
    for name, v in full_per.items():
        print(f"   {name:42s}  net={v['net']:>12,.0f}$   n={v['n']}")
    print("-" * 92)
    print(f"  سودِ خالصِ پایه (۵ لایه)   : {base_net:>14,.0f}$")
    print(f"  سودِ خالصِ کل  (۶ لایه)    : {full_net:>14,.0f}$")
    print(f"  Δ افزایشیِ لایهٔ Squeeze   : {delta:>+14,.0f}$")
    print("=" * 92)

    # ۴) همبستگیِ روزانهٔ لایهٔ Squeeze با پرتفویِ پایه
    sq_pt = S130.filter_recent(sq['pt'], years=YEARS_BACK, cutoff=cutoff)
    base_daily = daily_series(base_dt)
    sq_daily = daily_series([sq_pt[['dt', 'net_usd']]]) if len(sq_pt) else pd.Series(dtype=float)
    if len(base_daily) and len(sq_daily):
        joined = pd.concat([base_daily.rename('base'), sq_daily.rename('sq')], axis=1).fillna(0.0)
        corr = float(joined['base'].corr(joined['sq'])) if len(joined) > 2 else float('nan')
    else:
        corr = float('nan')
    print(f"\nهمبستگیِ روزانهٔ Squeeze با پرتفویِ پایه: {corr:+.3f}")
    print("  (نزدیک به صفر ⇒ جریانِ ناهمبسته و مطلوب؛ نزدیک به ۱ ⇒ تکراری.)")

    # ۵) داوریِ نهایی طبقِ قانونِ #۱
    verdict = "افزایشی ✅ (سودِ خالصِ کل بالا رفت)" if delta > 0 else "غیر-افزایشی ❌ (سودِ خالصِ کل بالا نرفت)"
    print(f"\nداوری: {verdict}")

    out = dict(
        eval_years=YEARS_BACK,
        cutoff=str(cutoff.date()),
        base_net=base_net,
        full_net=full_net,
        delta=delta,
        daily_corr=corr,
        squeeze_layer=dict(tp=SQZ_TP, sl=SQZ_SL, max_hold=SQZ_MAX_HOLD,
                           n_trades_recent=int(len(sq_pt)),
                           net_recent=float(sq_pt['net_usd'].sum()) if len(sq_pt) else 0.0),
        per_layer=full_per,
        additive=bool(delta > 0),
    )
    os.makedirs(os.path.join(ROOT, 'results'), exist_ok=True)
    with open(os.path.join(ROOT, 'results', '_s134_squeeze_additivity.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nخلاصه در results/_s134_squeeze_additivity.json ذخیره شد.")
    print("قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD (نه WR).")


if __name__ == '__main__':
    main()
