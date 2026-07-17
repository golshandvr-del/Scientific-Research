# ============================================================================
# استراتژی ۸۸ — «تثبیت و اعتبارسنجیِ ماشهٔ MACD-in-Regime» (هستهٔ پاسخِ User Note)
# ----------------------------------------------------------------------------
# قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر». سود خالص = XAUUSD + EURUSD. WR گزارشی.
#
# کشفِ S87: بهترین «تشخیصِ رفتارِ چارت» = ماشهٔ E7 (عبورِ MACD-hist از زیرِ صفر به
# بالای صفر) وقتی رژیمِ کلان صعودی است (ema50>ema200 و شیبِ ema50>0). این ماشه در
# هر دو بازه (1y و full) با PF≈۱.۲۴ سودده بود — لبهٔ جهت‌دارِ واقعی، نه پیش‌بینیِ
# کورکورانهٔ هر کندل. این اسکریپت آن را سخت‌گیرانه اعتبارسنجی می‌کند:
#   ۱) تقسیمِ نیمه‌به‌نیمه (هر دو نیمه باید مثبت باشند).
#   ۲) walk-forward چهار-پنجره‌ای (پایداریِ زمانی).
#   ۳) نسخهٔ متقارن (long در صعود + short در نزول) برای پوششِ رژیمِ نزولی —
#      اثباتِ اینکه «تشخیصِ درستِ جهت» هم صعود و هم نزول را می‌گیرد.
#   ۴) گزارشِ توزیعِ long/short برای اثباتِ رفعِ بیماریِ «short-در-صعود».
# ============================================================================
import sys, os, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, rsi, atr, macd, adx
from engine import scalp_engine as SE

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'data', 'XAUUSD_M15.csv')
RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
ASSET = 'XAUUSD'
SL, TP, MAXHOLD = 150.0, 450.0, 48


def load():
    df = pd.read_csv(DATA)
    df.columns = [c.strip().lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def add_ind(d):
    c = d['close']
    d['ema50'] = ema(c, 50); d['ema200'] = ema(c, 200)
    d['rsi14'] = rsi(c, 14); d['atr14'] = atr(d, 14)
    _, _, hist = macd(c); d['macd_hist'] = hist
    d['ema50_slope'] = d['ema50'].diff(5)
    return d


def signals(d):
    """ماشهٔ MACD-in-Regime دو-طرفه (forward-safe)."""
    up = (d['ema50'] > d['ema200']) & (d['ema50_slope'] > 0)
    dn = (d['ema50'] < d['ema200']) & (d['ema50_slope'] < 0)
    macd_up = (d['macd_hist'] > 0) & (d['macd_hist'].shift(1) <= 0)
    macd_dn = (d['macd_hist'] < 0) & (d['macd_hist'].shift(1) >= 0)
    long_sig = (macd_up & up).fillna(False).values
    short_sig = (macd_dn & dn).fillna(False).values
    return long_sig, short_sig


def run(d, ls, ss):
    trades = SE.simulate_trades(d, ls, ss, SL, TP, ASSET,
                                max_hold=MAXHOLD, allow_overlap=False)
    stats, eq = SE.run_capital(trades, ASSET, initial_capital=10_000.0, risk_pct=1.0)
    return stats, trades


def rpt(name, s):
    print('%-26s net=%+9.1f$  ret=%+7.1f%%  n=%4d  WR=%.1f%%  PF=%.2f  DD=%.1f%%  Sharpe=%.2f'
          % (name, s['net_profit'], s['return_pct'], s['n_trades'],
             s['win_rate'], s['profit_factor'], s['max_dd_pct'], s['sharpe']))


def main():
    d = add_ind(load())
    ls, ss = signals(d)
    print('=' * 100)
    print('کلِ داده (۱۵۰k) | سیگنال‌های LONG=%d  SHORT=%d' % (ls.sum(), ss.sum()))
    print('=' * 100)

    # نسخهٔ LONG-only (چون کلِ بازه غالباً صعودی است)
    s_long, tr_long = run(d, ls, np.zeros(len(d), bool))
    rpt('LONG-only (MACD-in-up)', s_long)
    # نسخهٔ دو-طرفه (long-up + short-down)
    s_both, tr_both = run(d, ls, ss)
    rpt('BOTH (up-long+down-short)', s_both)
    # فقط short-in-down (اثباتِ اینکه حتی نزول را درست می‌گیرد)
    s_short, _ = run(d, np.zeros(len(d), bool), ss)
    rpt('SHORT-only (MACD-in-down)', s_short)
    print('-' * 100)

    # --- تقسیمِ نیمه‌به‌نیمه (LONG-only) ---
    n = len(d)
    half = n // 2
    d1 = d.iloc[:half].reset_index(drop=True)
    d2 = d.iloc[half:].reset_index(drop=True)
    for tag, dd in [('نیمهٔ اول', d1), ('نیمهٔ دوم', d2)]:
        l2, s2 = signals(dd)
        s, _ = run(dd, l2, np.zeros(len(dd), bool))
        rpt('LONG %s' % tag, s)
    print('-' * 100)

    # --- walk-forward چهار-پنجره‌ای (LONG-only) ---
    q = n // 4
    for k in range(4):
        seg = d.iloc[k*q:(k+1)*q].reset_index(drop=True)
        l2, _ = signals(seg)
        s, _ = run(seg, l2, np.zeros(len(seg), bool))
        rpt('WF پنجرهٔ %d/4' % (k+1), s)
    print('-' * 100)

    # --- بازهٔ یک‌سالِ اخیر ---
    cutoff = pd.to_datetime(load()['time'].max(), unit='s') - pd.Timedelta(days=365)
    d_1y = d[d['dt'] >= cutoff].reset_index(drop=True)
    l1y, s1y = signals(d_1y)
    s, _ = run(d_1y, l1y, np.zeros(len(d_1y), bool))
    rpt('یک‌سالِ اخیر LONG', s)
    s, _ = run(d_1y, l1y, s1y)
    rpt('یک‌سالِ اخیر BOTH', s)

    print('=' * 100)
    # ذخیرهٔ خلاصه برای فایلِ MD
    out = {
        'sl_pip': SL, 'tp_pip': TP, 'max_hold': MAXHOLD,
        'full_long': {k: s_long[k] for k in ['net_profit','return_pct','n_trades','win_rate','profit_factor','max_dd_pct','sharpe']},
        'full_both': {k: s_both[k] for k in ['net_profit','return_pct','n_trades','win_rate','profit_factor','max_dd_pct','sharpe']},
        'full_short': {k: s_short[k] for k in ['net_profit','return_pct','n_trades','win_rate','profit_factor','max_dd_pct']},
    }
    with open(os.path.join(RES, '_s88_summary.json'), 'w') as f:
        json.dump(out, f, indent=2)
    print('ذخیره شد: results/_s88_summary.json')


if __name__ == '__main__':
    main()
