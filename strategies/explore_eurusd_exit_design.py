"""
explore_eurusd_exit_design.py — طراحیِ صحیحِ خروج برای drift ساعتِ 0 UTC
================================================================================
قانونِ #۱: فقط سودِ خالص (XAUUSD+EURUSD).

درسِ بک‌تستِ اول: TP/SL بزرگِ ATR-based نامناسب بود چون drift فقط ~2-3 pip است.
پروفایل نشان داد بهترین راه «خروجِ زمان‌محور در 4-6 کندل» است. اینجا شبکه‌ای از
طرح‌های خروج را روی همان سیگنالِ ساعت0 (buy-the-dip) با موتورِ سرمایه می‌سنجیم تا
بهترین ترکیبِ (SL_pip, TP_pip, max_hold) برای سودِ خالص را پیدا کنیم — با گزارشِ
دو-نیمه برای اطمینان از پایداری (نه overfit).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

PIP = 0.0001
CFG = dict(file='data/EURUSD_M15.csv', contract=100_000.0, spread=0.00010)
INITIAL_CAPITAL = 10_000.0; RISK_PCT = 1.0; COMMISSION = 7.0; EVAL_START = 24000
PULLBACK_LOOKBACK = 4

def build_long_sig(df):
    n = len(df)
    hour = pd.to_datetime(df['time'], unit='s').dt.hour.values
    c = df['close'].values
    eval_mask = np.zeros(n, dtype=bool); eval_mask[EVAL_START:] = True
    is_last_before_h0 = np.zeros(n, dtype=bool)
    is_last_before_h0[:-1] = (hour[1:] == 0) & (hour[:-1] != 0)
    prior = np.zeros(n); prior[PULLBACK_LOOKBACK:] = c[PULLBACK_LOOKBACK:] - c[:-PULLBACK_LOOKBACK]
    return is_last_before_h0 & eval_mask & (prior < 0)

def evaluate(df, sig, sl_pip, tp_pip, max_hold):
    n = len(df)
    sl_series = np.full(n, sl_pip * PIP)
    tp_series = np.full(n, tp_pip * PIP)
    st, tr = run_backtest(df, sig, None, None, 'long', spread=CFG['spread'],
                          max_hold=max_hold, sl_series=sl_series, tp_series=tp_series)
    if len(tr) == 0: return None
    sld = sl_series[tr['signal_bar'].values]
    order = tr['exit_bar'].values.argsort()
    tr = tr.iloc[order].reset_index(drop=True); sld = sld[order]
    stats, _ = run_capital_backtest(tr, sld, weights=None, initial_capital=INITIAL_CAPITAL,
                                    risk_pct=RISK_PCT, commission_per_lot=COMMISSION,
                                    compounding=False, contract_size=CFG['contract'])
    mid = tr['exit_bar'].median(); m1 = tr['exit_bar'].values <= mid
    def hn(mk):
        if mk.sum()==0: return 0.0
        s,_ = run_capital_backtest(tr[mk].reset_index(drop=True), sld[mk], weights=None,
                                   initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                   commission_per_lot=COMMISSION, compounding=False,
                                   contract_size=CFG['contract'])
        return s['net_profit']
    return stats, hn(m1), hn(~m1)

def main():
    df = load_data(CFG['file'])
    sig = build_long_sig(df)
    print(f"=== طراحیِ خروج (Long فقط، ساعت0 buy-the-dip، n_sig={int(sig.sum())}) ===\n", flush=True)
    print(f"{'SL':>4} {'TP':>4} {'hold':>5} | {'net$':>8} {'WR%':>6} {'PF':>5} {'DD%':>7} {'Shrp':>5} | {'H1$':>7} {'H2$':>7}  {'both+':>6}")
    results = []
    for sl_pip in [6, 8, 10, 12, 15]:
        for tp_pip in [4, 6, 8, 10, 12, 15]:
            for max_hold in [4, 6, 8, 12]:
                r = evaluate(df, sig, sl_pip, tp_pip, max_hold)
                if r is None: continue
                s, h1, h2 = r
                bothpos = "YES" if (h1>0 and h2>0) else ""
                results.append((s['net_profit'], sl_pip, tp_pip, max_hold, s, h1, h2, bothpos))
    # مرتب بر net، اما پایداری (both+) مهم
    results.sort(key=lambda x: x[0], reverse=True)
    for net, sl_pip, tp_pip, mh, s, h1, h2, bp in results[:25]:
        print(f"{sl_pip:>4} {tp_pip:>4} {mh:>5} | {s['net_profit']:>8.0f} {s['win_rate']:>6.1f} "
              f"{s['profit_factor']:>5.2f} {s['max_dd_pct']:>7.1f} {s['sharpe']:>5.2f} | "
              f"{h1:>7.0f} {h2:>7.0f}  {bp:>6}", flush=True)
    print("\nتمام. (نکته: ملاکِ انتخابِ نهایی = net بالا + هر دو نیمه مثبت، نه overfitِ تک‌نقطه.)", flush=True)

if __name__ == '__main__':
    main()
