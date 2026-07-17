"""
S76 — Range-Scalp روی الگوی Marubozu در رنجِ کم‌نوسان (پاسخ به بخشِ دومِ User Note)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدف **فقط و فقط سودِ خالصِ بیشتر** — نه WR.
سودِ خالص = XAUUSD + EURUSD. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**

--------------------------------------------------------------------------------
انگیزه (User Note — دومین بخشِ صحبتِ تریدر):
  «چرا سایتت در بازارِ رنج معامله نمی‌گوید؟ آنجا هنرِ نوسان‌گیری/اسکالپ به کار می‌آید.»
  موتورِ برندهٔ S67 در رنج/بی‌روند عمداً خنثی می‌ماند (سودِ خالص را حفظ می‌کند).
  پس اگر یک لبهٔ **رنج-محورِ ناهمبسته** پیدا کنیم، می‌تواند سودِ خالصِ کل را بدونِ
  دست‌زدن به S67 بالا ببرد (مثلِ منطقِ پرتفویِ ناهمبستهٔ S36).

کشفِ اکتشافی (explore_candle_patterns.py):
  تنها الگوی صعودیِ اثبات‌شده در **رنجِ کم‌نوسان**، `bull_marubozu` بود:
    • M15 RANGE: mean=+۱.۵۱bps, t=+۲.۹۸ (در برابرِ TREND که معکوس بود!)
    • H1 LOVOL:  mean=+۳.۶۰bps, t=+۲.۳۸, WR=۵۴.۶٪
  یعنی یک کندلِ بدنه-بزرگِ بدونِ سایه در محیطِ آرام ⇒ ادامهٔ کوتاهِ صعودی (اسکالپ).

طراحی (فقط جایی که S67 خنثی است ⇒ ناهمبسته):
  • ورود Long روی bull_marubozu وقتی رژیم = رنجِ کم‌نوسان (ADX پایین یا ATR پایین).
  • اسکالپِ کوتاه: TP/SL کوچک، hold کوتاه (چون لبه فوری و کوچک است).
  • اسکن می‌کنیم تا ببینیم آیا سودِ both-halves-positive می‌دهد.

اگر سودِ خالصِ مثبت و پایدار ⇒ به پرتفوی اضافه و رکورد جابه‌جا می‌شود.
اگر نه ⇒ درسِ منفیِ صادقانه (تأییدِ اینکه رنج واقعاً سخت است).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

SPREAD = 0.20


def build(df):
    df = df.copy()
    df['atr'] = ind.atr(df, 14)
    a, _, _ = ind.adx(df, 14); df['adx'] = a
    return df


def marubozu_range_signals(df, adx_max, atr_lo_pct):
    """bull_marubozu در رنجِ کم‌نوسان."""
    o, h, l, c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    n = len(df)
    body = c - o; body_abs = np.abs(body)
    up_wick = h - np.maximum(o, c); lo_wick = np.minimum(o, c) - l
    body_ma = pd.Series(body_abs).rolling(20).mean().values
    bull_maru = (body > 0) & (body_abs >= 1.5 * body_ma) & (up_wick + lo_wick <= 0.2 * body_abs)
    # رژیمِ رنجِ کم‌نوسان
    atr = df['atr'].values
    atr_thr = pd.Series(atr).rolling(500, min_periods=100).apply(
        lambda x: np.nanpercentile(x, atr_lo_pct), raw=True).values
    calm = (df['adx'].values <= adx_max) & (atr <= atr_thr)
    return bull_maru & calm


def test(df, entries, tp_mult, sl_mult, hold):
    atr = df['atr'].values
    st, tr = run_backtest(df, entries, None, None, 'long', spread=SPREAD, max_hold=hold,
                          allow_overlap=False, sl_series=sl_mult*atr, tp_series=tp_mult*atr)
    if len(tr) < 30:
        return None
    sl_dist = sl_mult * atr[tr['signal_bar'].values]
    cap, _ = run_capital_backtest(tr, sl_dist, initial_capital=10_000.0, risk_pct=1.0,
                                  commission_per_lot=7.0, compounding=False)
    mid = len(df) // 2; hs = []
    for m in [(tr['signal_bar'] < mid), (tr['signal_bar'] >= mid)]:
        hh = tr[m]
        if len(hh):
            hc, _ = run_capital_backtest(hh.reset_index(drop=True),
                                         sl_mult*atr[hh['signal_bar'].values],
                                         initial_capital=10_000.0, risk_pct=1.0,
                                         commission_per_lot=7.0, compounding=False)
            hs.append(hc['net_profit'])
        else:
            hs.append(0)
    return cap, hs


def main():
    print("=" * 78)
    print("  S76 — Range-Scalp Marubozu (XAUUSD M15) — پاسخ به «معامله در رنج»")
    print("=" * 78)
    df = load_data('data/XAUUSD_M15.csv'); df = build(df)
    best = None
    print(f"  {'adx':>4}{'atrP':>5}{'tp':>5}{'sl':>5}{'hold':>5}{'n':>6}{'netP':>9}{'WR%':>6}{'H1':>8}{'H2':>8}")
    for adx_max in [15, 20, 25]:
        for atr_lo in [33, 50]:
            sig = marubozu_range_signals(df, adx_max, atr_lo)
            if sig.sum() < 30:
                continue
            for tp in [0.5, 0.8, 1.0, 1.5]:
                for sl in [0.5, 0.8, 1.0]:
                    for hold in [4, 8, 16]:
                        r = test(df, sig, tp, sl, hold)
                        if r is None:
                            continue
                        cap, hs = r
                        if cap['net_profit'] > 0 and hs[0] > 0 and hs[1] > 0:
                            print(f"  {adx_max:>4}{atr_lo:>5}{tp:>5}{sl:>5}{hold:>5}{cap['n_trades']:>6}"
                                  f"{cap['net_profit']:>+9.0f}{cap['win_rate']:>6.1f}{hs[0]:>+8.0f}{hs[1]:>+8.0f}")
                            if best is None or cap['net_profit'] > best[0]:
                                best = (cap['net_profit'], adx_max, atr_lo, tp, sl, hold, cap, hs)
    print()
    if best:
        np_, adx_max, atr_lo, tp, sl, hold, cap, hs = best
        print(f"  ★ بهترین both-halves-positive: adx≤{adx_max} atrP≤{atr_lo} tp={tp} sl={sl} hold={hold}")
        print(f"    netP={np_:+.0f}$ n={cap['n_trades']} WR={cap['win_rate']:.1f}% "
              f"PF={cap['profit_factor']:.2f} maxDD={cap['max_dd_pct']:.1f}% Sharpe={cap['sharpe']:.2f}")
        print(f"    H1={hs[0]:+.0f}$ H2={hs[1]:+.0f}$")
        print(f"\n  اگر مثبت: رکوردِ کل = 44,458$ + {np_:+.0f}$ = {44458+np_:+.0f}$")
    else:
        print("  ❌ هیچ ترکیبِ both-halves-positive سوددهی یافت نشد — رنج واقعاً سخت است.")


if __name__ == '__main__':
    main()
