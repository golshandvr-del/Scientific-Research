"""
S72 — استراتژیِ شکست/مومنتومِ مخصوصِ فارکس (معکوسِ فرضیهٔ S71)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدفِ پروژه **فقط و فقط «سودِ خالصِ بیشتر»** است
— نه Win-Rate. WR گزارشی است؛ تعدادِ معامله و PF هم هدف نیستند. **ما دنبالِ پول
هستیم، نه آمارِ زیبا.** تعریفِ فعلیِ «سودِ خالص» = مجموعِ چهار دارایی هم‌زمان.

--------------------------------------------------------------------------------
فرضیه (چرا معکوسِ S71):
  S71 نشان داد mean-reversion در فارکس زیان‌ده است و WR فقط ~۲۰-۲۷٪ — یعنی وقتی
  قیمت از باندِ بولینگر می‌زند بیرون، به‌جای برگشت، **ادامه می‌دهد** (شکست/مومنتوم).
  پس اینجا خلافِ S71: در همان نقاطِ شکستِ باند، **در جهتِ شکست** وارد می‌شویم و در
  رژیمِ روندی (ER بالا) — با فیلترِ Donchian-breakout واقعی.
    • Long وقتی close بالای باندِ بالایی (یا سقفِ Donchian) در رژیمِ روندی.
    • Short وقتی close زیرِ باندِ پایینی (یا کفِ Donchian) در رژیمِ روندی.
    • TP بلندتر از SL (اجازهٔ دویدنِ روند)؛ SL کوتاهِ ATR.

اعتبار: shift-safe، قواعد ثابت، آزمونِ دو-نیمه، موتورِ سرمایه‌محورِ ریسکِ ثابتِ ۱٪.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

DONCH = 20           # پنجرهٔ Donchian
ER_WIN = 32
ER_TREND_THR = 0.15  # فقط رژیمِ روندی
SL_ATR = 1.0
TP_ATR = 2.5         # اجازهٔ دویدنِ روند (R:R = 2.5)
MAX_HOLD = 48

ASSETS = {
    'EURUSD': dict(file='data/EURUSD_M15.csv', contract=100_000.0, spread=0.00010),
    'AUDUSD': dict(file='data/AUDUSD_M15.csv', contract=100_000.0, spread=0.00012),
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
    print(f"\n{'='*80}\n=== {name} (breakout/momentum) ===\n{'='*80}", flush=True)
    df = load_data(cfg['file'])
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14); atrv = atr.values
    # Donchian بر پایهٔ close تا کندلِ i-1 (shift-safe)
    hh = df['high'].rolling(DONCH).max().shift(1).values
    ll = df['low'].rolling(DONCH).min().shift(1).values
    er = efficiency_ratio(c, ER_WIN)
    is_trend = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)

    valid = ~np.isnan(atrv) & ~np.isnan(hh) & ~np.isnan(ll)
    eval_mask = np.zeros(n, dtype=bool); eval_mask[EVAL_START:] = True

    long_sig = valid & is_trend & eval_mask & (c > hh)   # شکستِ سقف
    short_sig = valid & is_trend & eval_mask & (c < ll)  # شکستِ کف
    print(f"کندل‌ها={n} | روند={int(is_trend.sum())} | Long-brk={int(long_sig.sum())} | Short-brk={int(short_sig.sum())}", flush=True)

    sl_series = SL_ATR * atrv
    tp_series = TP_ATR * atrv

    def trades_for(direction, sig):
        st, tr = run_backtest(df, sig, None, None, direction, spread=cfg['spread'],
                              max_hold=MAX_HOLD, sl_series=sl_series, tp_series=tp_series)
        if len(tr) == 0:
            return tr, np.array([])
        return tr, sl_series[tr['signal_bar'].values]

    trL, slL = trades_for('long', long_sig)
    trS, slS = trades_for('short', short_sig)
    all_tr = pd.concat([trL, trS], ignore_index=True)
    all_sl = np.concatenate([slL, slS]) if (len(slL) or len(slS)) else np.array([])
    if len(all_tr) == 0:
        print("  هیچ معامله‌ای تولید نشد.", flush=True)
        return dict(name=name, n=0, net=0.0, ret=0.0, dd=0.0, pf=0.0, wr=0.0,
                    n_long=0, n_short=0, h1_net=0.0, h2_net=0.0)
    order = all_tr['exit_bar'].values.argsort()
    all_tr = all_tr.iloc[order].reset_index(drop=True); all_sl = all_sl[order]

    stats, _ = run_capital_backtest(all_tr, all_sl, weights=None,
                                    initial_capital=INITIAL_CAPITAL, risk_pct=RISK_PCT,
                                    commission_per_lot=COMMISSION, compounding=False,
                                    contract_size=cfg['contract'])
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
    print("=== S72: شکست/مومنتومِ مخصوصِ فارکس ===", flush=True)
    print(f"قانونِ #۱: فقط سودِ خالص. Donchian({DONCH}) breakout در رژیمِ روند (ER≥{ER_TREND_THR}), R:R={TP_ATR}/{SL_ATR}.", flush=True)
    results = {}
    for name, cfg in ASSETS.items():
        results[name] = run_asset(name, cfg)
    forex_net = results['EURUSD']['net'] + results['AUDUSD']['net']
    print(f"\n### سودِ خالصِ فارکس (EUR+AUD) با breakout = {forex_net:+.0f}$", flush=True)
    print(f"  (منطقِ طلا S69 = -13,797$ ؛ mean-reversion S71 = -20,147$)", flush=True)
    out = {k: results[k] for k in ASSETS}; out['_forex_net'] = forex_net
    with open(os.path.join(RES_DIR, '_s72_summary.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("خلاصه در results/_s72_summary.json ذخیره شد. تمام.", flush=True)


if __name__ == '__main__':
    main()
