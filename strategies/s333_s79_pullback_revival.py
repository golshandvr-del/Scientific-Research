# -*- coding: utf-8 -*-
"""
S333 — احیای S79 (Gold Trend-Pullback) با معیارِ RQS+ و هدفِ WR≥۶۰٪
================================================================================
هستهٔ S79 (سوخته در عصرِ سودِ خالص): در روندِ صعودیِ کلان (EMA_fast>EMA_slow) وقتی
RSI افت کرد (pullback) خرید کن. S79 با R:R نامتقارنِ ۱:۲.۴ برای «بیشینه‌کردنِ سودِ
خالص» تنظیم شده بود ⇒ WR=۳۹٪ و ناپایداریِ walk-forward (Q2≈۰). این دقیقاً «تلهٔ
TP نامتقارن» است که RQS+ آن را رد می‌کند.

فرضیهٔ احیا (خطی+غیرخطی):
  ۱) لبهٔ «buy-dip در روند» واقعی است (long-biasِ ساختاریِ طلا).
  ۲) برای WR≥۶۰٪ باید هندسهٔ payoff را وارونه کرد: TP کوچک‌ترِ نزدیک تا برد سریع و
     پرتکرار بیفتد (mean-reversion payoff)، نه TP بزرگِ دور.
  ۳) معاملاتِ بی‌کیفیت (رنج/چاپی) که Q2 را می‌کشتند با فیلترهای رژیمیِ بانکِ ۴۰۱‌تایی
     حذف می‌شوند (r2/hurst/chop/er/trend_gate) — «همه‌چیز شناور است».

این اسکریپت:
  • هسته را روی هر TF از هر جفت‌ارز جدا می‌سازد،
  • SL/TP غیررند per-TF را اسکن می‌کند،
  • فیلترهای رژیمیِ بانک را دسته‌به‌دسته امتحان می‌کند،
  • برای بهترین ترکیبِ هر TF، RQS+ کامل (۶ گیت) را گزارش می‌دهد.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE
from engine import rqs
from engine import indicator_bank as ib

# ---- ثبتِ همهٔ ترکیب‌های (جفت‌ارز×TF) در ASSETS با هزینهٔ واقعیِ حساب ----
# طلا: pip=0.10, spread=3.3pip(0.33$/oz), comm=0, slip=0  (User Note جدید)
# یورو: pip=0.0001, spread=1.0pip, comm=0, slip=0.3
def _reg_asset(key, file, pair):
    if pair == 'XAUUSD':
        SE.ASSETS[key] = dict(file=file, pip=0.10, contract=100.0, pip_value=10.0,
                              spread_pip=3.3, comm=0.0, slip_pip=0.0)
    else:
        SE.ASSETS[key] = dict(file=file, pip=0.0001, contract=100_000.0, pip_value=10.0,
                              spread_pip=1.0, comm=0.0, slip_pip=0.3)

TF_FILES = {
    'XAUUSD': {'M5':'data/XAUUSD_M5.csv','M15':'data/XAUUSD_M15.csv',
               'M30':'data/XAUUSD_M30.csv','H1':'data/XAUUSD_H1.csv','H4':'data/XAUUSD_H4.csv'},
    'EURUSD': {'M5':'data/EURUSD_M5.csv','M15':'data/EURUSD_M15.csv','M30':'data/EURUSD_M30.csv'},
}
for pair, tfs in TF_FILES.items():
    for tf, f in tfs.items():
        _reg_asset(f'{pair}_{tf}', f, pair)


def ema(x, s):
    return pd.Series(x).ewm(span=s, adjust=False).mean().values

def rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def core_signal(df, ema_fast, ema_slow, rsi_p, rsi_th):
    """هستهٔ S79: روندِ صعودیِ کلان + pullbackِ RSI (فقط Long)."""
    c = df['close'].values
    ef = ema(c, ema_fast); es = ema(c, ema_slow); r = rsi(c, rsi_p)
    long_sig = np.nan_to_num((ef > es) & (r < rsi_th)).astype(bool)
    return long_sig


def apply_regime(df, base_sig, filters):
    """اعمالِ فیلترهای رژیمیِ بانک (لیستی از (name, op, thr)). op: 'gt'|'lt'."""
    sig = base_sig.copy()
    for (name, op, thr) in filters:
        s = ib.compute(name, df).values
        s = np.nan_to_num(s, nan=(-1e9 if op == 'gt' else 1e9))
        sig = sig & ((s > thr) if op == 'gt' else (s < thr))
    return sig


def evaluate(df, sig, asset, sl, tp, max_hold):
    tr = SE.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset, max_hold=max_hold)
    if len(tr) == 0:
        return None, None
    r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
    return tr, r


def brief(r):
    """یک‌خطی‌سازیِ متریک‌های RQS+ برای اسکن."""
    m = r['metrics']; g = r['gates']
    gs = ''.join('✓' if g[k] else '✗' for k in ['G0','G1','G2','G3','G4','G5'])
    return (f"n={m['n_trades']:4d} WR={m['win_rate']:5.1f}% PF={m['profit_factor']:.2f} "
            f"DD={m['max_dd_pct']:4.1f}% MCL={m['max_consec_losses']:2d} "
            f"exp={m['expectancy_pip']:+6.2f} p={m['p_value']:.3f} "
            f"RQS={r['rqs_score']:5.1f} [{gs}] {'ACCEPT' if r['passed'] else 'reject'}")


if __name__ == '__main__':
    print('module ready — import and call core_signal/apply_regime/evaluate/brief')
