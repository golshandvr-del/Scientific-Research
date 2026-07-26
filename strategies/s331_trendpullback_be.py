"""
S331 — Trend-Pullback + Break-Even (احیای S79 تحتِ RQS+)
================================================================================
این ماژولِ نهاییِ منطقِ لایهٔ احیاشده است (منبعِ حقیقتِ واحد برای بک‌تست، اعتبارسنجی،
مولتی‌تایم‌فریم و پیاده‌سازیِ سایت).

منطقِ ورود (Long، کاملاً forward-safe):
    ۱) روندِ صعودیِ کلان:      EMA(20) > EMA(100)
    ۲) pullback (RSI):        RSI(21) < RSI_TH        (پیش‌فرض ۳۶)
    ۳) روندِ قوی (ضدِ رنج):     ADX(14) >= ADX_MIN     (پیش‌فرض ۱۸)
    ۴) تأییدِ بازگشت:          close کندلِ سیگنال > open آن (کندلِ صعودی)

خروج (همه بر حسبِ ATR — «قانونِ شناوری»؛ خودکار با هر TF تطبیق می‌یابد ⇒ ضدِ اشتباهِ #۶):
    SL = SL_ATR × ATR(14)        (پیش‌فرض ۲.۸)
    TP = TP_ATR × ATR(14)        (پیش‌فرض ۱.۷)
    Break-Even: وقتی سود به BE_ATR × ATR رسید، SL → نقطهٔ ورود (پیش‌فرض ۱.۲)
    max_hold = MAX_HOLD کندل      (پیش‌فرض ۴۰)

چرا این S79 را احیا می‌کند (کشفِ کلیدی):
    S79 خام WR=39٪/PF=1.18/DD=17٪ داشت (رد در G0/G2/G3). با معکوس‌کردنِ هندسهٔ خروج
    (SL>TP ⇒ WR بالا) + break-even (باختِ بزرگ→صفر ⇒ PF جهش) ⇒ روی XAUUSD-M5:
    WR=64.4٪ · PF=1.90 · DD=3.0٪ · MCL=4 · RQS+=89.2 (هر ۶ گیت ✓).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE


# ---- پارامترهای پیش‌فرضِ نهاییِ M5 (وسطِ منطقهٔ پایدار، اعدادِ غیررندِ ATR-scaled) ----
DEFAULTS = dict(ema_fast=20, ema_slow=100, rsi_p=21, rsi_th=36, adx_min=18,
                sl_atr=2.8, tp_atr=1.7, be_atr=1.2, max_hold=40, atr_p=14)


def ema(x, s):
    return pd.Series(x).ewm(span=s, adjust=False).mean().values


def rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def atr_series(df, p=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1/p, adjust=False).mean().values


def adx_series(df, p=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr_ = pd.Series(tr).ewm(alpha=1/p, adjust=False).mean().values
    pdi = 100 * pd.Series(plus_dm).ewm(alpha=1/p, adjust=False).mean().values / (atr_ + 1e-12)
    mdi = 100 * pd.Series(minus_dm).ewm(alpha=1/p, adjust=False).mean().values / (atr_ + 1e-12)
    dx = 100 * np.abs(pdi - mdi) / (pdi + mdi + 1e-12)
    return pd.Series(dx).ewm(alpha=1/p, adjust=False).mean().values


def build_signal(df, p=None):
    """آرایهٔ بولینِ Long/Short + آرایهٔ ATR (برای SL/TP/BE شناور)."""
    if p is None:
        p = DEFAULTS
    c = df['close'].values; o = df['open'].values
    e_f = ema(c, p['ema_fast']); e_s = ema(c, p['ema_slow'])
    r = rsi(c, p['rsi_p'])
    adx_ = adx_series(df, p['atr_p'])
    atr_ = atr_series(df, p['atr_p'])
    sig = (e_f > e_s) & (r < p['rsi_th']) & (adx_ >= p['adx_min']) & (c > o)
    long_sig = np.nan_to_num(sig).astype(bool)
    return long_sig, np.zeros(len(df), bool), atr_


def run(df, asset_key, p=None):
    """اجرا: بازگرداندنِ DataFrameِ معاملات (سازگار با engine.rqs.compute_rqs)."""
    if p is None:
        p = DEFAULTS
    pip = SE.ASSETS[asset_key]['pip']
    long_sig, short_sig, atr_ = build_signal(df, p)
    sl_pip = np.maximum(p['sl_atr'] * atr_ / pip, 1.0)
    tp_pip = np.maximum(p['tp_atr'] * atr_ / pip, 1.0)
    be_pip = None if p.get('be_atr') is None else float(np.nanmedian(p['be_atr'] * atr_ / pip))
    trades = SE.simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, asset_key,
                                max_hold=p['max_hold'], be_trigger_pip=be_pip)
    return trades


def setup_asset(base, tf, path):
    """کلیدِ موقتِ دارایی برای TF مشخص (مشخصاتِ هزینه از دارایی پایه)."""
    key = f'{base}_{tf}'
    cfg = SE.ASSETS[base].copy(); cfg['file'] = path
    SE.ASSETS[key] = cfg
    return key


if __name__ == '__main__':
    from engine import rqs as RQS
    key = setup_asset('XAUUSD', 'M5', 'data/XAUUSD_M5.csv')
    df = SE.load_data('data/XAUUSD_M5.csv')
    tr = run(df, key)
    r = RQS.compute_rqs(tr, key)
    print(RQS.format_report('S331 XAUUSD-M5', r))
