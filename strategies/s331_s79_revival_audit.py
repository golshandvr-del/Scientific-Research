"""
S331 — احیای S79 (XAUUSD M5 Trend-Pullback) تحتِ پارادایمِ RQS+
================================================================================
هدف: S79 اصلی («EMA20>EMA100 + RSI21<35 ⇒ Long، SL50/TP120») در پارادایمِ قدیمی
سودده بود (+$4,256) اما با معیارِ RQS+ رد می‌شود (WR≈39٪ ⇒ G0 رد، MaxDD≈15٪ ⇒ G3 رد).

این ماژول فقط «گامِ ۰ = ممیزیِ پایه» است: S79ِ خام را روی هر ۵ تایم‌فریمِ XAUUSD
(M5,M15,M30,H1,H4) و روی EURUSD اجرا و RQS+ آن را گزارش می‌کند تا دقیقاً بفهمیم
کدام گیت‌ها رد می‌شوند و از کجا باید احیا را شروع کنیم.

قاعدهٔ مولتی‌تایم‌فریم: هر TF جداگانه سنجیده می‌شود؛ از XAUUSD M5 شروع.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE
from engine import rqs as RQS

# ---- منطقِ خامِ S79 ----
EMA_FAST = 20
EMA_SLOW = 100
RSI_PERIOD = 21
RSI_TH = 35
SL_PIP = 50
TP_PIP = 120
MAX_HOLD = 72


def ema(x, s):
    return pd.Series(x).ewm(span=s, adjust=False).mean().values


def rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def build_signals_s79(df):
    c = df['close'].values
    long_sig = np.nan_to_num((ema(c, EMA_FAST) > ema(c, EMA_SLOW)) & (rsi(c, RSI_PERIOD) < RSI_TH)).astype(bool)
    short_sig = np.zeros(len(df), bool)
    return long_sig, short_sig


# دارایی‌ها و فایل‌های TF (طلا 5 تایم‌فریم + یورو M5/M15/M30)
TF_FILES = {
    'XAUUSD': {'M5': 'data/XAUUSD_M5.csv', 'M15': 'data/XAUUSD_M15.csv',
               'M30': 'data/XAUUSD_M30.csv', 'H1': 'data/XAUUSD_H1.csv',
               'H4': 'data/XAUUSD_H4.csv'},
    'EURUSD': {'M5': 'data/EURUSD_M5.csv', 'M15': 'data/EURUSD_M15.csv',
               'M30': 'data/EURUSD_M30.csv'},
}


def audit_one(asset_base, tf, path):
    """اجرای S79 خام روی یک TF و برگرداندنِ RQS+."""
    # کلیدِ موقتِ دارایی با فایلِ همان TF (طلا pip=0.10 spread=3.3؛ یورو pip=0.0001 spread=1.0)
    key = f'{asset_base}_{tf}_TMP'
    base = SE.ASSETS[asset_base].copy()
    base['file'] = path
    SE.ASSETS[key] = base
    df = SE.load_data(path)
    long_sig, short_sig = build_signals_s79(df)
    tr = SE.simulate_trades(df, long_sig, short_sig, SL_PIP, TP_PIP, key, max_hold=MAX_HOLD)
    r = RQS.compute_rqs(tr, key, sl_pip=SL_PIP, tp_pip=TP_PIP)
    return r


def main():
    print("=" * 110)
    print("  S331 — ممیزیِ پایهٔ S79 خام (EMA20>EMA100 + RSI21<35, SL50/TP120) تحتِ RQS+")
    print("=" * 110)
    for base, tfs in TF_FILES.items():
        for tf, path in tfs.items():
            r = audit_one(base, tf, path)
            print(RQS.format_report(f'{base}-{tf}', r))
    print("=" * 110)


if __name__ == '__main__':
    main()
