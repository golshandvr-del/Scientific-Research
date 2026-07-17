"""
S71 — استراتژیِ برگشت‌به‌میانگینِ مخصوصِ فارکس (خلافِ منطقِ trend-followingِ طلا)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی در هر سند و هر کد): هدفِ پروژه **فقط و فقط
«سودِ خالصِ بیشتر»** است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است؛ تعدادِ معامله
و Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.** تعریفِ فعلیِ
«سودِ خالص» = مجموعِ سودِ خالصِ چهار دارایی (XAUUSD+DXY+EURUSD+AUDUSD) هم‌زمان.

--------------------------------------------------------------------------------
فرضیهٔ علمی (چرا خلافِ طلا):
  S69/S70 ثابت کردند منطقِ trend-following و long-biasedِ طلا روی EURUSD/AUDUSD
  زیان‌ده است. دلیلِ ساختاری: فارکسِ major در M15 بیشتر **برگشت‌به‌میانگین (mean-
  reverting)** است تا روندی؛ حرکت‌های افراطی معمولاً اصلاح می‌شوند. پس اینجا **خلافِ
  انحراف** معامله می‌کنیم:
    • فقط در رژیمِ رنج (ER پایین ⇒ چون در روندِ قوی، برگشت‌به‌میانگین خطرناک است).
    • Long وقتی close زیرِ باندِ پایینِ بولینگر و RSI اشباعِ فروش (< RSI_LO).
    • Short وقتی close بالای باندِ بالایی و RSI اشباعِ خرید (> RSI_HI).
    • TP = برگشت به میانگین (SMA میانی) با ضریبِ ATR؛ SL = ATR-multiple (کوتاه).

اعتبار (forward-safe):
  همهٔ اندیکاتورها فقط از گذشته/جاری (shift-safe). قواعد ثابت و ساده (بدونِ بهینه‌سازیِ
  روی کلِ داده). آزمونِ دو-نیمه (H1/H2) برای پایداری. موتورِ سرمایه‌محورِ ریسکِ ثابتِ ۱٪.
  این استراتژی هیچ ML ندارد ⇒ سبک و سریع.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

# --- قواعدِ ثابتِ mean-reversion ---
BB_PERIOD = 20
BB_MULT = 2.2
RSI_PERIOD = 14
RSI_LO = 28.0        # اشباعِ فروش → Long
RSI_HI = 72.0        # اشباعِ خرید → Short
ER_WIN = 32
ER_RANGE_THR = 0.15  # فقط وقتی ER < این ⇒ رژیمِ رنج (خلافِ طلا که ER≥0.15 می‌خواست)
SL_ATR = 1.2         # SL کوتاه
TP_ATR = 1.6         # TP تا حدودِ میانگین
MAX_HOLD = 32

ASSETS = {
    'EURUSD': dict(file='data/EURUSD_M15.csv', contract=100_000.0, spread=0.00010),
    'AUDUSD': dict(file='data/AUDUSD_M15.csv', contract=100_000.0, spread=0.00012),
    'XAUUSD': dict(file='data/XAUUSD_M15.csv', contract=100.0,     spread=0.20),  # کنترل: باید بد باشد
    'DXY':    dict(file='data/DXY_M15.csv',    contract=1_000.0,   spread=0.03),
}
INITIAL_CAPITAL = 10_000.0
RISK_PCT = 1.0
COMMISSION = 7.0
EVAL_START = 24000
RES_DIR = os.path.join(os.path.dirname(__file__), '..', 'results')


def efficiency_ratio(close, win):
    close = pd.Series(close)
    change = close.diff(win).abs()
    vol = close.diff().abs().rolling(win).sum()
    er = (change / vol).replace([np.inf, -np.inf], np.nan)
    return er.shift(1).values


def run_asset(name, cfg):
    print(f"\n{'='*80}\n=== {name} (mean-reversion) ===\n{'='*80}", flush=True)
    df = load_data(cfg['file'])
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14); atrv = atr.values
    mid, upper, lower = ind.bollinger(df['close'], BB_PERIOD, BB_MULT)
    mid = mid.values; upper = upper.values; lower = lower.values
    rsi = ind.rsi(df['close'], RSI_PERIOD).values
    er = efficiency_ratio(c, ER_WIN)
    is_range = np.nan_to_num(er < ER_RANGE_THR, nan=False).astype(bool)

    valid = ~np.isnan(atrv) & ~np.isnan(upper) & ~np.isnan(rsi)
    eval_mask = np.zeros(n, dtype=bool); eval_mask[EVAL_START:] = True

    # سیگنال‌ها (shift-safe: همه بر پایهٔ close کندلِ i؛ ورود در open کندلِ i+1 توسطِ موتور)
    long_sig = valid & is_range & eval_mask & (c < lower) & (rsi < RSI_LO)
    short_sig = valid & is_range & eval_mask & (c > upper) & (rsi > RSI_HI)
    print(f"کندل‌ها={n} | رنج={int(is_range.sum())} | Long-sig={int(long_sig.sum())} | Short-sig={int(short_sig.sum())}", flush=True)

    sl_series = SL_ATR * atrv
    tp_series = TP_ATR * atrv

    def trades_for(direction, sig):
        st, tr = run_backtest(df, sig, None, None, direction, spread=cfg['spread'],
                              max_hold=MAX_HOLD, sl_series=sl_series, tp_series=tp_series)
        if len(tr) == 0:
            return tr, np.array([])
        sld = sl_series[tr['signal_bar'].values]
        return tr, sld

    trL, slL = trades_for('long', long_sig)
    trS, slS = trades_for('short', short_sig)
    all_tr = pd.concat([trL, trS], ignore_index=True)
    all_sl = np.concatenate([slL, slS]) if (len(slL) or len(slS)) else np.array([])
    if len(all_tr) == 0:
        print("  هیچ معامله‌ای تولید نشد.", flush=True)
        return dict(name=name, n=0, net=0.0, ret=0.0, dd=0.0, pf=0.0, wr=0.0,
                    n_long=0, n_short=0, h1_net=0.0, h2_net=0.0)
    order = all_tr['exit_bar'].values.argsort()
    all_tr = all_tr.iloc[order].reset_index(drop=True)
    all_sl = all_sl[order]

    stats, _ = run_capital_backtest(all_tr, all_sl, weights=None,
                                    initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                    commission_per_lot=COMMISSION, compounding=False,
                                    contract_size=cfg['contract'])
    # دو-نیمه
    mid_bar = all_tr['exit_bar'].median()
    m1 = all_tr['exit_bar'].values <= mid_bar
    def half_net(mk):
        if mk.sum() == 0: return 0.0
        s, _ = run_capital_backtest(all_tr[mk].reset_index(drop=True), all_sl[mk], weights=None,
                                    initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                    commission_per_lot=COMMISSION, compounding=False,
                                    contract_size=cfg['contract'])
        return s['net_profit']
    h1, h2 = half_net(m1), half_net(~m1)
    print(f"  >>> {name}: n={stats['n_trades']} (L={len(trL)},S={len(trS)})  "
          f"net={stats['net_profit']:+.0f}$ ({stats['return_pct']:+.1f}%)  "
          f"maxDD={stats['max_dd_pct']:.1f}%  PF={stats['profit_factor']:.2f}  "
          f"WR={stats['win_rate']:.1f}%   H1={h1:+.0f}$  H2={h2:+.0f}$", flush=True)
    return dict(name=name, n=stats['n_trades'], net=stats['net_profit'], ret=stats['return_pct'],
                dd=stats['max_dd_pct'], pf=stats['profit_factor'], wr=stats['win_rate'],
                n_long=len(trL), n_short=len(trS), h1_net=h1, h2_net=h2)


def main():
    print("=== S71: برگشت‌به‌میانگینِ مخصوصِ فارکس ===", flush=True)
    print(f"قانونِ #۱: فقط سودِ خالص. BB({BB_PERIOD},{BB_MULT}) + RSI({RSI_LO}/{RSI_HI}) در رژیمِ رنج (ER<{ER_RANGE_THR}).", flush=True)
    results = {}
    for name, cfg in ASSETS.items():
        results[name] = run_asset(name, cfg)
    print(f"\n{'#'*80}\n### جمع‌بندی\n{'#'*80}", flush=True)
    forex_net = results['EURUSD']['net'] + results['AUDUSD']['net']
    print(f"سودِ خالصِ فارکس (EUR+AUD) با mean-reversion = {forex_net:+.0f}$", flush=True)
    print(f"  (مقایسه: همین دو با منطقِ طلا در S69 = -13,797$)", flush=True)
    out = {k: results[k] for k in ASSETS}
    out['_forex_net'] = forex_net
    with open(os.path.join(RES_DIR, '_s71_summary.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("\nخلاصه در results/_s71_summary.json ذخیره شد. تمام.", flush=True)


if __name__ == '__main__':
    main()
