# ============================================================================
# استراتژی ۸۹ — «آزمونِ افزایشی‌بودنِ لایهٔ MACD-in-Regime نسبت به برندهٔ فعلی (S67)»
# ----------------------------------------------------------------------------
# قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر». سود خالص = XAUUSD + EURUSD. WR گزارشی.
#
# پرسشِ کلیدیِ سودِ خالص: لایهٔ نوِ S88 (MACD-in-up-regime، LONG روی طلا M15) با
# برندهٔ فعلیِ طلا M15 (S67) **هم‌بسته** است یا یک جریانِ افزایشیِ مستقل؟ فقط اگر
# ناهم‌بسته و افزایشی باشد، سودِ خالصِ کل بالا می‌رود (رکوردِ فعلی +۵۸٬۲۹۵$).
#
# روش: هر دو لایه را روی همان دادهٔ M15 اجرا می‌کنیم، سود دلاریِ per-trade را در
# سطلِ روزانهٔ UTC تجمیع می‌کنیم، همبستگیِ سودِ روزانه و سودِ خالصِ ترکیبی
# (هم‌سرمایه، ریسکِ ۱٪ مستقل) را می‌سنجیم.
# ============================================================================
import sys, os, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, rsi, atr, macd
from engine import scalp_engine as SE

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'data', 'XAUUSD_M15.csv')
RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
CAP, RISK = 10_000.0, 1.0


def macd_regime_layer():
    """لایهٔ S88: MACD-in-up-regime LONG، سود per-trade با timestamp."""
    df = SE.load_data('data/XAUUSD_M15.csv')
    c = df['close']
    ema50 = ema(c, 50); ema200 = ema(c, 200)
    _, _, hist = macd(c)
    slope = ema50.diff(5)
    up = (ema50 > ema200) & (slope > 0)
    macd_up = (hist > 0) & (hist.shift(1) <= 0)
    long_sig = (macd_up & up).fillna(False).values
    tr = SE.simulate_trades(df, long_sig, np.zeros(len(df), bool), 150.0, 450.0,
                            'XAUUSD', max_hold=48, allow_overlap=False)
    stats, eq, pt = SE.run_capital_pertrade(tr, 'XAUUSD', df=df, initial_capital=CAP,
                                            risk_pct=RISK, compounding=False)
    pt['dt'] = pd.to_datetime(pt['dt'], utc=True) if 'dt' in pt else None
    return stats, pt


def s67_layer():
    """برندهٔ فعلیِ طلا M15 (از cache S61 + tpsl_plan)."""
    from engine.backtest import load_data, run_backtest
    from engine.tpsl_plan import build_plan
    from engine.capital_engine import run_capital_backtest
    HZ = 48; SPREAD = 0.20; ER_TREND_THR = 0.30; P_HI = 0.66; P_MIN = 0.58
    z = np.load(os.path.join(RES, '_s61_cache.npz'), allow_pickle=True)
    pL, pS = z['pL'], z['pS']; up_reg, down_reg = z['up_reg'], z['down_reg']
    er = z['er']; atrv = z['atrv']
    df = load_data('data/XAUUSD_M15.csv'); n = len(df)
    trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)
    baseL = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)

    def build_labels(base):
        ef = np.where(trendy, 'trend', 'chop'); pw = np.where(pL >= P_HI, 'hi', 'lo')
        lab = np.array([f'{a}_{b}' for a, b in zip(ef, pw)], dtype=object)
        lab[~base] = ''
        return lab
    labL = build_labels(baseL)
    eval_mask = np.zeros(n, bool); eval_mask[24000:] = True
    planL = build_plan('long', labL, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)
    s = planL.entries & eval_mask
    st, tr = run_backtest(df, s, None, None, 'long', spread=SPREAD, max_hold=HZ,
                          sl_series=planL.sl_series(), tp_series=planL.tp_series())
    sl = planL.sl_dist_for_trades(tr); w = planL.weights[tr['signal_bar'].values]
    order = tr['exit_bar'].values.argsort()
    tr = tr.iloc[order].reset_index(drop=True); sl = sl[order]; w = w[order]
    stats, eq = run_capital_backtest(tr, sl, weights=w, initial_capital=CAP,
                                     risk_pct=RISK, commission_per_lot=7.0, compounding=False)
    net_per = np.diff(eq); m = min(len(net_per), len(tr))
    pt = pd.DataFrame({'exit_bar': tr['exit_bar'].values[:m], 'net_usd': net_per[:m]})
    idx = np.clip(pt['exit_bar'].values, 0, len(df) - 1)
    pt['dt'] = pd.to_datetime(df['time'].values[idx], unit='s', utc=True)
    return stats, pt


def daily(pt):
    p = pt.dropna(subset=['dt']).copy()
    p['day'] = p['dt'].dt.floor('D')
    return p.groupby('day')['net_usd'].sum()


def main():
    print('=' * 90)
    s88, pt88 = macd_regime_layer()
    s67, pt67 = s67_layer()
    print('S88 (MACD-in-up) net=%+.1f$  n=%d  PF=%.2f' %
          (s88['net_profit'], s88['n_trades'], s88['profit_factor']))
    print('S67 (برندهٔ فعلی) net=%+.1f$  n=%d  PF=%.2f' %
          (s67['net_profit'], s67['n_trades'], s67['profit_factor']))
    print('-' * 90)
    d88 = daily(pt88); d67 = daily(pt67)
    idx = d88.index.union(d67.index)
    a = d88.reindex(idx).fillna(0.0); b = d67.reindex(idx).fillna(0.0)
    corr = np.corrcoef(a.values, b.values)[0, 1]
    combined = (a + b)
    print('همبستگیِ سودِ روزانهٔ S88 با S67: %.3f' % corr)
    print('سودِ خالصِ ترکیبی (S88+S67، هم‌سرمایه مستقل): %+.1f$' % combined.sum())
    print('  = S88 %+.1f$ + S67 %+.1f$' % (a.sum(), b.sum()))
    # فقط بازهٔ مشترک (S67 از کندلِ 24000 شروع می‌شود)
    both = pd.concat([a.rename('s88'), b.rename('s67')], axis=1)
    overlap = both[(both['s67'] != 0)]
    if len(overlap) > 5:
        c2 = np.corrcoef(overlap['s88'], overlap['s67'])[0, 1]
        print('همبستگی در بازهٔ فعالِ مشترکِ S67: %.3f  (n_days=%d)' % (c2, len(overlap)))
    print('=' * 90)
    out = dict(s88_net=s88['net_profit'], s67_net=s67['net_profit'],
               corr_daily=float(corr), combined_net=float(combined.sum()))
    with open(os.path.join(RES, '_s89_additivity.json'), 'w') as f:
        json.dump(out, f, indent=2)
    print('ذخیره شد: results/_s89_additivity.json')


if __name__ == '__main__':
    main()
