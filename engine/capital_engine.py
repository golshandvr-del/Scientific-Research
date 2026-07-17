"""
capital_engine.py — موتورِ سرمایه‌محور با ریسکِ درصدی و مدلِ لاتِ واقعیِ XAUUSD
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدفِ پروژه **فقط و فقط «سودِ خالصِ بیشتر»**
است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است. تعدادِ معامله در روز و Profit
Factor هم هدف نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**

------------------------------------------------------------------------------
انگیزه (پاسخ به User Note نکتهٔ ۱):
  موتورِ قبلی (`engine/backtest.py`) مفهومِ «سرمایه» را مدل نمی‌کرد. `pnl` هر معامله
  = اختلافِ خامِ قیمت به دلار (یعنی سود/زیان روی ۱ اونس = ۰.۰۱ لاتِ استاندارد).
  پس عددِ «۶۸۲۳$» یا «۷۳۵۰$» عملاً **بی‌مقیاس (scale-free)** بود و به هیچ سرمایهٔ
  اولیه‌ای گره نمی‌خورد. این ماژول این نقص را برطرف می‌کند:

  ۱) **سرمایهٔ اولیهٔ مشخص** (پیش‌فرض ۱۰٬۰۰۰$).
  ۲) **ریسکِ درصدیِ هر معامله** (پیش‌فرض ۱٪ از equityِ جاری): حجمِ لات طوری تعیین
     می‌شود که اگر SL بخورد، دقیقاً `risk_pct%` از سرمایهٔ فعلی از دست برود.
  ۳) **مدلِ لاتِ واقعیِ XAUUSD:** ۱ لاتِ استاندارد = ۱۰۰ اونس، پس حرکتِ ۱$ در قیمت
     = ۱۰۰$ سود/زیان به‌ازای هر ۱ لات (`CONTRACT_SIZE = 100`).
  ۴) **کارمزد/کمیسیون** به‌ازای هر لات در هر گِرد (پیش‌فرض ۷$ رفت‌وبرگشت برای هر لات).
  ۵) **کامپاند (compounding):** چون ریسک درصدی از equityِ جاری است، سود به‌صورت
     مرکب رشد می‌کند (اختیاری: می‌توان به ریسکِ ثابت-دلاری سوییچ کرد).

  این‌طوری «سودِ خالص» یک عددِ **واقعی و قابلِ تفسیر** می‌شود: «با X دلار سرمایه و
  ریسکِ Y٪ در هر معامله، پس از N معامله، equity به Z دلار رسید».

------------------------------------------------------------------------------
تفاوت با موتورِ خام:
  - خروجیِ backtest.py «مجموعِ حرکتِ قیمتی» بود؛ اینجا «رشدِ equity به دلار» است.
  - وزنِ Kelly (از روتر) به‌عنوانِ **ضریبِ مقیاسِ ریسک** استفاده می‌شود: ریسکِ مؤثرِ
    هر معامله = `risk_pct × kelly_weight` (کلیپ‌شده به سقفِ ریسک برای ایمنی).

نکته دربارهٔ نشتِ آینده:
  این موتور فقط «حسابداریِ سرمایه» را روی معاملاتِ ازپیش‌تولیدشده انجام می‌دهد؛
  خودش هیچ تصمیمِ ورودی نمی‌گیرد، پس هیچ look-ahead جدیدی وارد نمی‌کند.
"""
import numpy as np
import pandas as pd


# --- ثابت‌های مدلِ واقعیِ XAUUSD ---
CONTRACT_SIZE = 100.0     # ۱ لات = ۱۰۰ اونس → حرکتِ ۱$ قیمت = ۱۰۰$ برای ۱ لات
DEFAULT_CAPITAL = 10_000.0
DEFAULT_RISK_PCT = 1.0    # درصدِ ریسک از equityِ جاری در هر معامله
DEFAULT_COMMISSION_PER_LOT = 7.0   # کمیسیونِ رفت‌وبرگشت به‌ازای هر لاتِ استاندارد
MIN_LOT = 0.01            # حداقلِ حجمِ قابلِ معامله (micro lot)
MAX_LOT = 100.0           # سقفِ ایمنیِ حجم
MAX_EFFECTIVE_RISK_PCT = 5.0   # سقفِ ایمنیِ ریسکِ مؤثر (پس از ضربِ وزنِ Kelly)


def run_capital_backtest(trades, sl_dist, weights=None,
                         initial_capital=DEFAULT_CAPITAL,
                         risk_pct=DEFAULT_RISK_PCT,
                         commission_per_lot=DEFAULT_COMMISSION_PER_LOT,
                         compounding=True,
                         contract_size=CONTRACT_SIZE):
    """
    حسابداریِ سرمایه روی معاملاتِ ازپیش‌تولیدشده.

    پارامترها:
      trades   : DataFrame خروجیِ run_backtest (باید ستون‌های `pnl`, `signal_bar`,
                 `exit_bar`, `outcome` داشته باشد). `pnl` = حرکتِ خامِ قیمت به دلار
                 (سود/زیان روی ۱ اونس).
      sl_dist  : فاصلهٔ SL به دلار برای هر معامله (آرایه هم‌طولِ trades، به ترتیبِ
                 همان معاملات). این تعیین می‌کند برای ریسکِ ثابتِ درصدی چه حجمی لازم است.
      weights  : وزنِ Kelly هر معامله (ضریبِ مقیاسِ ریسک). اگر None → همه ۱.
      initial_capital : سرمایهٔ اولیه به دلار.
      risk_pct : درصدِ پایهٔ ریسک از equityِ جاری در هر معامله.
      commission_per_lot : کمیسیونِ رفت‌وبرگشت به‌ازای هر لات.
      compounding : اگر True ریسک از equityِ جاری (مرکب)؛ اگر False از سرمایهٔ اولیه.

    خروجی: دیکشنریِ آمارِ سرمایه‌محور + آرایهٔ equity curve.
    """
    if trades is None or len(trades) == 0:
        return _empty_stats(initial_capital), np.array([initial_capital])

    tr = trades.sort_values('exit_bar').reset_index(drop=True)
    n = len(tr)
    sl_dist = np.asarray(sl_dist, dtype=np.float64)
    if len(sl_dist) != n:
        raise ValueError(f"sl_dist طول {len(sl_dist)} با تعدادِ معاملات {n} نمی‌خواند")
    if weights is None:
        weights = np.ones(n)
    else:
        weights = np.asarray(weights, dtype=np.float64)
        weights[weights <= 0] = 1.0

    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    eq_curve = [initial_capital]
    r_returns = []        # بازدهِ درصدیِ هر معامله (برای Sharpe)
    lots_used = []
    wins = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_commission = 0.0
    ruined_at = None

    for i in range(n):
        pnl_per_oz = tr['pnl'].iloc[i]          # حرکتِ قیمت به دلار روی ۱ اونس
        sld = sl_dist[i]
        w = weights[i]

        # ریسکِ مؤثرِ درصدی (پایه × وزنِ Kelly، کلیپ‌شده به سقفِ ایمنی)
        eff_risk_pct = min(risk_pct * w, MAX_EFFECTIVE_RISK_PCT)
        risk_base = equity if compounding else initial_capital
        risk_dollars = risk_base * eff_risk_pct / 100.0

        # حجمِ لات: اگر SL بخورد، دقیقاً risk_dollars از دست برود.
        # زیانِ SL به‌ازای ۱ لات = sl_dist × contract_size (+ کمیسیون).
        if sld <= 0:
            lots = MIN_LOT
        else:
            loss_per_lot_at_sl = sld * contract_size + commission_per_lot
            lots = risk_dollars / loss_per_lot_at_sl
        lots = float(np.clip(round(lots, 2), MIN_LOT, MAX_LOT))
        lots_used.append(lots)

        # سود/زیانِ دلاریِ واقعیِ این معامله
        pnl_dollars = pnl_per_oz * contract_size * lots
        commission = commission_per_lot * lots
        net = pnl_dollars - commission
        total_commission += commission

        if net >= 0:
            gross_profit += net
        else:
            gross_loss += -net

        equity_before = equity
        equity += net
        eq_curve.append(equity)
        if tr['outcome'].iloc[i] == 'win':
            wins += 1
        r_returns.append(net / equity_before if equity_before > 0 else 0.0)

        peak = max(peak, equity)
        dd = equity - peak
        max_dd = min(max_dd, dd)

        if equity <= 0 and ruined_at is None:
            ruined_at = i
            break

    eq_curve = np.array(eq_curve)
    net_profit = equity - initial_capital
    r_returns = np.array(r_returns)
    sharpe = (r_returns.mean() / r_returns.std() * np.sqrt(len(r_returns))
              if len(r_returns) > 1 and r_returns.std() > 0 else 0.0)
    max_dd_pct = (max_dd / peak * 100.0) if peak > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    stats = {
        'initial_capital': initial_capital,
        'final_equity': equity,
        'net_profit': net_profit,
        'return_pct': net_profit / initial_capital * 100.0,
        'n_trades': n if ruined_at is None else ruined_at + 1,
        'win_rate': wins / n * 100.0 if n else 0.0,
        'max_dd': max_dd,
        'max_dd_pct': max_dd_pct,
        'profit_factor': profit_factor,
        'sharpe': sharpe,
        'total_commission': total_commission,
        'avg_lot': float(np.mean(lots_used)) if lots_used else 0.0,
        'net_over_dd': net_profit / abs(max_dd) if max_dd < 0 else float('inf'),
        'ruined': ruined_at is not None,
    }
    return stats, eq_curve


def _empty_stats(initial_capital):
    return {
        'initial_capital': initial_capital, 'final_equity': initial_capital,
        'net_profit': 0.0, 'return_pct': 0.0, 'n_trades': 0, 'win_rate': 0.0,
        'max_dd': 0.0, 'max_dd_pct': 0.0, 'profit_factor': 0.0, 'sharpe': 0.0,
        'total_commission': 0.0, 'avg_lot': 0.0, 'net_over_dd': 0.0, 'ruined': False,
    }


def summary_line(name, s):
    return (f"{name}: cap={s['initial_capital']:.0f}$ → "
            f"equity={s['final_equity']:.0f}$  netP={s['net_profit']:+.0f}$ "
            f"({s['return_pct']:+.1f}%)  n={s['n_trades']}  WR={s['win_rate']:.1f}%  "
            f"maxDD={s['max_dd']:.0f}$ ({s['max_dd_pct']:.1f}%)  PF={s['profit_factor']:.2f}  "
            f"Sharpe={s['sharpe']:.2f}  avgLot={s['avg_lot']:.2f}")
