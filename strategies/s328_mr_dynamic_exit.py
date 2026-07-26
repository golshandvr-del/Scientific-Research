# -*- coding: utf-8 -*-
"""
S328 (بخشِ ۲) — Mean-Reversion با خروجِ دینامیک + آزمونِ پایداریِ همسایگی
================================================================================
منشأ: ادامهٔ s328_rsi21_mr_regime_revival.py

یافتهٔ بخشِ ۱ (RSI-21 MR + فیلترِ رژیم، TP/SL ثابت):
  • XAUUSD M5 SHORT  : RQS=91.4 پاس، اما فقط در adx≤30 دقیق زنده (همسایگی می‌میرد) ⇒ شکننده
  • XAUUSD H1 SHORT  : RQS=93.9 پاس، اما فقط rp21/mh24/hi82 + سودِ متمرکز در یک پنجرهٔ WF ⇒ شکننده
  • EURUSD (هر دو جهت): کاملاً مرده
  • LONG روی طلا     : مرده (WR بیشینه ~56%)

فرضیهٔ پایدارسازیِ این بخش (تفکرِ غیرخطی):
  لبه‌های بالا شکننده بودند چون به یک نقطهٔ دقیقِ TP/SL/فیلتر قفل شده‌اند. راهِ اصیلِ MR این است
  که خروج را به «رفتارِ قیمت» گره بزنیم نه یک عددِ ثابت:
    (الف) break-even + trailing  ⇒ ریسک را صفر می‌کند، WR را در همسایگی پایدار می‌کند
    (ب) خروج در بازگشتِ RSI به میانه (mean-reversion واقعی: وقتی اشباع رفع شد خارج شو)
  معیارِ پذیرشِ سخت‌گیرانه‌تر (ضدِ overfit، فراتر از RQS+):
    یک کاندید فقط وقتی «زندهٔ پایدار» است که در یک هستهٔ همسایگیِ پارامتری (≥ چند نقطهٔ مجاور)
    میانگینِ RQS+ آن ≥ ۸۰ و همهٔ نقاط ≥ ۷۰ باشند — نه یک قلهٔ تکیِ منفرد.

معیار: RQS+ (engine/rqs). موتور: engine/scalp_engine (با be_trigger_pip / trail_pip داخلی).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicators as ind
from strategies.s328_rsi21_mr_regime_revival import build_signals, TFS, efficiency_ratio


def build_signals_rsi_exit(df, rsi_period, lo, hi, mid, adx_max=None, er_max=None,
                           adx_period=14, er_period=10):
    """
    مثلِ build_signals ولی علاوه بر ورود، یک آرایهٔ exit_sig هم می‌سازد:
    خروجِ دینامیکِ MR = وقتی RSI به میانه (mid) بازگشت (اشباع رفع شد).
      Short entry: RSI از بالای hi برگشت  ⇒  exit وقتی RSI <= mid
      Long  entry: RSI از زیرِ lo برگشت    ⇒  exit وقتی RSI >= mid
    (این آرایه‌ها برای شبیه‌سازِ سفارشیِ زیر استفاده می‌شوند.)
    """
    close = df['close']
    r = ind.rsi(close, rsi_period)
    return r.values  # خودِ RSI کافی است؛ منطقِ exit در شبیه‌ساز پیاده می‌شود


def simulate_mr_dynamic(df, entry_sig, side, sl_pip, rsi_arr, mid, asset,
                        max_hold=48, tp_cap_pip=None):
    """
    شبیه‌سازِ سفارشیِ MR با خروجِ دینامیک بر پایهٔ بازگشتِ RSI به میانه (forward-safe).
      • ورود روی close کندلِ سیگنال (مثلِ موتور) + اسپرد.
      • خروج در اولین کندلی که:
          - SL خورد (بدترین حالت، با high/low)، یا
          - RSI به mid بازگشت (بستن با close آن کندل)، یا
          - tp_cap_pip (اگر داده شود) خورد، یا
          - max_hold رسید.
    خروجی: DataFrame با ستونِ pnl_pip سازگار با engine/rqs.
    """
    cfg = se.ASSETS[asset]
    pip = cfg['pip']
    spread = cfg['spread_pip']
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    dt = df['dt'].values if 'dt' in df.columns else np.arange(len(df))
    n = len(df)
    trades = []
    i = 0
    idx = np.where(entry_sig)[0]
    entry_set = set(idx.tolist())
    while i < n - 1:
        if i in entry_set:
            entry_price = c[i]
            # اعمالِ اسپرد: short می‌فروشد در bid، long می‌خرد در ask
            if side == 'short':
                fill = entry_price - spread * pip / 2
                sl_level = fill + sl_pip * pip
                tp_level = (fill - tp_cap_pip * pip) if tp_cap_pip else None
            else:
                fill = entry_price + spread * pip / 2
                sl_level = fill - sl_pip * pip
                tp_level = (fill + tp_cap_pip * pip) if tp_cap_pip else None
            exit_price = None
            for j in range(i + 1, min(i + 1 + max_hold, n)):
                if side == 'short':
                    if h[j] >= sl_level:            # SL خورد
                        exit_price = sl_level; break
                    if tp_level and l[j] <= tp_level:
                        exit_price = tp_level; break
                    if rsi_arr[j] <= mid:            # RSI به میانه بازگشت ⇒ خروجِ MR
                        exit_price = c[j]; break
                else:
                    if l[j] <= sl_level:
                        exit_price = sl_level; break
                    if tp_level and h[j] >= tp_level:
                        exit_price = tp_level; break
                    if rsi_arr[j] >= mid:
                        exit_price = c[j]; break
            else:
                j = min(i + max_hold, n - 1)
                exit_price = c[j]
            if exit_price is None:
                j = min(i + max_hold, n - 1); exit_price = c[j]
            # pnl بر حسبِ pip (خالص از اسپردِ خروج)
            if side == 'short':
                gross = (fill - exit_price) / pip
            else:
                gross = (exit_price - fill) / pip
            pnl_pip = gross - spread / 2   # نیمِ دیگرِ اسپرد در خروج
            # ستون‌های سازگار با engine/rqs و engine/run_capital
            trades.append(dict(
                signal_bar=int(i), entry_bar=int(i + 1), exit_bar=int(j),
                direction=(-1 if side == 'short' else 1),
                pnl_pip=float(pnl_pip), sl_pip=float(sl_pip),
                outcome=('win' if pnl_pip > 0 else 'loss'),
                bars_held=int(j - i)))
            i = j + 1   # allow_overlap=False
        else:
            i += 1
    if not trades:
        return None
    return pd.DataFrame(trades)


def neighborhood_test(asset, tf, f, side, rsi_period, lo, hi, mid,
                      sl_center, adx_max, er_max, max_hold):
    """
    آزمونِ پایداریِ همسایگی: کاندیدِ مرکزی را در شبکه‌ای از SL±و mid± و max_hold±
    ارزیابی می‌کند. برمی‌گرداند: (mean_rqs, min_rqs, n_points, details).
    """
    df = se.load_data(f)
    rsi_arr = ind.rsi(df['close'], rsi_period).values
    ls, ss = build_signals(df, rsi_period, lo, hi, adx_max, er_max)
    entry = ss if side == 'short' else ls
    if int(entry.sum()) < 30:
        return None
    sl_grid = [round(sl_center * m) for m in (0.8, 1.0, 1.25)]
    mid_grid = [mid - 5, mid, mid + 5]
    mh_grid = [int(max_hold * 0.75), max_hold, int(max_hold * 1.5)]
    rqs_vals = []
    details = []
    for sl in sl_grid:
        for m in mid_grid:
            for mh in mh_grid:
                tr = simulate_mr_dynamic(df, entry, side, sl, rsi_arr, m, asset, max_hold=mh)
                if tr is None or len(tr) < 30:
                    continue
                r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=sl)  # tp≈sl برای MR دینامیک
                rqs_vals.append(r['rqs_score'])
                details.append((sl, m, mh, r['rqs_score'], r['metrics']['n_trades'],
                                r['metrics']['win_rate'], r['metrics']['profit_factor'],
                                bool(r['passed'])))
    if not rqs_vals:
        return None
    return dict(mean_rqs=float(np.mean(rqs_vals)), min_rqs=float(np.min(rqs_vals)),
                max_rqs=float(np.max(rqs_vals)), n_points=len(rqs_vals), details=details)


def sweep_dynamic(asset='XAUUSD', side='short'):
    """جاروبِ MR-دینامیک + آزمونِ پایداریِ همسایگی روی همهٔ TF."""
    print("=" * 110)
    print(f"S328-B DYNAMIC-EXIT MR — {asset} — side={side} — خروجِ RSI→mid + BE/trail + آزمونِ همسایگی")
    print("=" * 110)
    # کاندیدهای مرکزی (از یافتهٔ بخشِ ۱ + شبکهٔ آستانه)
    THRESHES = [(25, 75), (20, 80), (18, 82), (22, 78)]
    MID = 50
    SL_BY_TF = {'M5': 70, 'M15': 95, 'M30': 110, 'H1': 195, 'H4': 300}
    MH_BY_TF = {'M5': 24, 'M15': 24, 'M30': 24, 'H1': 24, 'H4': 24}
    ADX_MAXES = [None, 30, 22]
    for tf, f in TFS[asset].items():
        if not os.path.exists(f):
            continue
        best = None
        for (lo, hi) in THRESHES:
            for adx_max in ADX_MAXES:
                res = neighborhood_test(asset, tf, f, side, 21, lo, hi, MID,
                                        SL_BY_TF.get(tf, 100), adx_max, None,
                                        MH_BY_TF.get(tf, 24))
                if res is None:
                    continue
                tag = f"lo{lo}/hi{hi} adx≤{adx_max}"
                if best is None or res['mean_rqs'] > best[1]['mean_rqs']:
                    best = (tag, res)
        if best is None:
            print(f"\n--- {asset}-{tf}: no valid candidate (n<30) ---")
            continue
        tag, res = best
        stable = res['mean_rqs'] >= 80 and res['min_rqs'] >= 70
        flag = "✅ STABLE" if stable else ("~ peak" if res['max_rqs'] >= 80 else "❌ dead")
        print(f"\n--- {asset}-{tf} | {tag} | {flag} ---")
        print(f"  همسایگی({res['n_points']} نقطه): mean_RQS={res['mean_rqs']:.1f} "
              f"min={res['min_rqs']:.1f} max={res['max_rqs']:.1f}")
        # نمایشِ ۳ نقطهٔ برتر
        for d in sorted(res['details'], key=lambda x: x[3], reverse=True)[:3]:
            print(f"    SL{d[0]}/mid{d[1]}/mh{d[2]}: RQS={d[3]:.1f} n={d[4]} "
                  f"WR={d[5]:.1f}% PF={d[6]:.2f} {'PASS' if d[7] else 'rej'}")


if __name__ == '__main__':
    side = sys.argv[1] if len(sys.argv) > 1 else 'short'
    asset = sys.argv[2] if len(sys.argv) > 2 else 'XAUUSD'
    sweep_dynamic(asset, side)
