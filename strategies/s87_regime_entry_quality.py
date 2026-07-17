# ============================================================================
# استراتژی ۸۷ — «بهبودِ کیفیتِ ورود در جهتِ رژیم» (ادامهٔ پاسخِ User Note)
# ----------------------------------------------------------------------------
# قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر». سود خالص = XAUUSD + EURUSD. WR گزارشی.
#
# کشفِ S86: فیلترِ رژیمِ جهت، ضررِ متقارن را از −۶٬۹۹۴$ به −۸۶$ رساند (رفعِ بیماریِ
# short-در-صعود)، اما RSI-pullbackِ خام هنوز سودده نیست (WR≈۳۵٪، PF<۱). مشکل:
# «کیفیتِ نقطهٔ ورود». این اسکریپت چند تعریفِ ورودِ باکیفیت‌تر را در جهتِ رژیمِ
# صعودی می‌سنجد و بهترین SL/TP را جاروب می‌کند. همه forward-safe، هزینهٔ واقعیِ کاربر.
#
# داراییِ آزمون: XAUUSD M15، بازهٔ یک‌سالِ اخیر + کلِ داده (اعتبارسنجیِ دو-بازه‌ای).
# ============================================================================
import sys, os
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, rsi, atr, macd, adx
from engine import scalp_engine as SE

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'data', 'XAUUSD_M15.csv')
ASSET = 'XAUUSD'


def load(period='1y'):
    df = pd.read_csv(DATA)
    df.columns = [c.strip().lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    if period == '1y':
        cutoff = df['dt'].max() - pd.Timedelta(days=365)
        df = df[df['dt'] >= cutoff].reset_index(drop=True)
    df['dt'] = pd.to_datetime(df['time'], unit='s')  # tz-naive برای موتور
    return df


def add_ind(d):
    c = d['close']
    d['ema20'] = ema(c, 20); d['ema50'] = ema(c, 50)
    d['ema100'] = ema(c, 100); d['ema200'] = ema(c, 200)
    d['rsi14'] = rsi(c, 14)
    d['atr14'] = atr(d, 14)
    _, _, hist = macd(c); d['macd_hist'] = hist
    a, pdi, mdi = adx(d, 14)
    d['adx'] = a; d['plus_di'] = pdi; d['minus_di'] = mdi
    d['ema50_slope'] = d['ema50'].diff(5)
    d['hh20'] = d['high'].rolling(20).max()
    return d


def run(d, long_sig, sl, tp, max_hold=48):
    trades = SE.simulate_trades(d, long_sig, np.zeros(len(d), bool), sl, tp, ASSET,
                                max_hold=max_hold, allow_overlap=False)
    stats, _ = SE.run_capital(trades, ASSET, initial_capital=10_000.0, risk_pct=1.0)
    return stats


def rpt(name, s):
    print('%-30s net=%+9.1f$  ret=%+7.1f%%  n=%4d  WR=%.1f%%  PF=%.2f  DD=%.1f%%'
          % (name, s['net_profit'], s['return_pct'], s['n_trades'],
             s['win_rate'], s['profit_factor'], s['max_dd_pct']))


def main():
    for period in ['1y', 'full']:
        d = add_ind(load(period))
        print('=' * 96)
        print('بازه: %s | کندل‌ها=%d' % (period, len(d)))
        print('=' * 96)

        up = (d['ema50'] > d['ema200']) & (d['ema50_slope'] > 0)
        up_strong = up & (d['adx'] > 25)          # روندِ قوی
        c = d['close']

        # تعاریفِ ورود (همه در جهتِ رژیمِ صعودی):
        entries = {
            'E1 RSI<40 + up':          (d['rsi14'] < 40) & up,
            'E2 RSI<40 + up_strong':   (d['rsi14'] < 40) & up_strong,
            'E3 pull-EMA50 + up':      (c < d['ema50']) & (c > d['ema200']) & up,
            'E4 pull-EMA20 + up_strong': (c < d['ema20']) & up_strong,
            'E5 breakout-HH20 + up':   (c >= d['hh20'].shift(1)) & up,
            'E6 breakout + up_strong': (c >= d['hh20'].shift(1)) & up_strong,
            'E7 MACD>0 cross + up':    (d['macd_hist'] > 0) & (d['macd_hist'].shift(1) <= 0) & up,
            'E8 +DI>-DI turn + up_strong': (d['plus_di'] > d['minus_di']) & (d['plus_di'].shift(1) <= d['minus_di'].shift(1)) & up_strong,
        }
        # بهترین SL/TP برای هر ورود (جاروبِ کوچک)
        grids = [(60, 180), (80, 240), (120, 240), (120, 360), (150, 450)]
        for ename, sig in entries.items():
            best = None
            for sl, tp in grids:
                s = run(d, sig.fillna(False).values, float(sl), float(tp))
                if s['n_trades'] >= 15 and (best is None or s['net_profit'] > best[0]['net_profit']):
                    best = (s, sl, tp)
            if best is None:
                print('%-30s (بدونِ ترکیبِ معتبر: n<15)' % ename)
            else:
                s, sl, tp = best
                rpt('%s [SL%d/TP%d]' % (ename, sl, tp), s)


if __name__ == '__main__':
    main()
