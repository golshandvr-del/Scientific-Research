# -*- coding: utf-8 -*-
"""
S333 — احیای S79 (Gold Trend-Pullback) با معیارِ RQS+ و هدفِ WR≥۶۰٪
================================================================================
هستهٔ S79 (سوخته در عصرِ سودِ خالص): در روندِ صعودیِ کلان (EMA_fast>EMA_slow) وقتی
RSI افت کرد (pullback) خرید کن. S79 با R:R نامتقارنِ ۱:۲.۴ برای «بیشینه‌کردنِ سودِ
خالص» تنظیم شده بود ⇒ WR=۳۹٪ و ناپایداریِ walk-forward (Q2≈۰). این دقیقاً «تلهٔ
TP نامتقارن» است که RQS+ آن را رد می‌کند.

فرضیهٔ احیا (خطی+غیرخطی) — نسخهٔ اصلاح‌شده (علمیِ اصیل):
  ۱) لبهٔ «buy-dip در روند» واقعی است (long-biasِ ساختاریِ طلا).
  ۲) *** اصلِ روش‌شناختی (تصحیحِ کاربر) ***: افزایشِ WR باید از «دقتِ محلِ ورود/خروج»
     بیاید، نه از هندسهٔ TP<SL. زیرا با TP<SL نقطهٔ سربه‌سرِ WR بالا می‌رود
     (breakeven = SL/(SL+TP)) و WRِ بالا «مصنوعی» می‌شود ⇒ خودفریبی و نقضِ ماهیتِ
     علمی. بنابراین هندسه را «منصفانه» نگه می‌داریم: TP ≥ SL (سربه‌سر ≤ ۵۰٪)، تا
     هر WRِ گزارش‌شده لبهٔ *واقعی* باشد. RQS+/G1 دقیقاً همین را با p-value می‌سنجد.
  ۳) WR فقط از دو منبعِ علمی بالا می‌رود:
       الف) فیلترِ رژیم: فقط در رژیمِ پایدار/رونددار وارد شو (hurst/r2/er) —
            معاملاتِ چاپیِ بی‌کیفیت که Q2 را می‌کشتند حذف می‌شوند.
       ب) دقتِ ورود: صبر تا «تأییدِ بازگشتِ» pullback (close برمی‌گردد بالای
          کفِ اخیر / RSI از کفِ خود برمی‌گردد) — ورود در نقطهٔ دقیق‌ترِ چرخش،
          نه صرفاً «RSI پایین است».
     «همه‌چیز شناور است»: آستانه‌ها و فیلترها per-TF و per-pair تنظیم می‌شوند.

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
    """هستهٔ S79 خام: روندِ صعودیِ کلان + pullbackِ RSI (فقط Long) — بدونِ تأییدِ بازگشت."""
    c = df['close'].values
    ef = ema(c, ema_fast); es = ema(c, ema_slow); r = rsi(c, rsi_p)
    long_sig = np.nan_to_num((ef > es) & (r < rsi_th)).astype(bool)
    return long_sig


def core_signal_confirmed(df, ema_fast, ema_slow, rsi_p, rsi_th, confirm='rsi_turn'):
    """هستهٔ دقت‌محور: روندِ صعودی + pullback + *تأییدِ بازگشت* (افزایشِ WR از راهِ علمی).

    منطق: به‌جای ورود صرفاً چون «RSI پایین است»، صبر می‌کنیم تا pullback واقعاً
    *تمام و در حالِ چرخش* باشد. این ورود را از «وسطِ سقوطِ چاقو» به «کفِ تأییدشده»
    منتقل می‌کند ⇒ WR از دقتِ نقطهٔ ورود بالا می‌رود، نه از هندسهٔ TP/SL.

      confirm:
        'none'      → مثلِ هستهٔ خام (RSI<th فعال).
        'rsi_turn'  → کندلِ قبلی RSI<th بود و RSI حالا بالاتر از کندلِ قبل رفت
                      (RSI از کفِ خود برگشت) و هنوز RSI<th+10 (هنوز در ناحیهٔ ارزش).
        'price_turn'→ RSI اخیراً زیرِ th رفت + close > high کندلِ قبلی
                      (بازگشتِ قیمتی: کندلِ صعودیِ تأییدی).
    """
    c = df['close'].values
    h = df['high'].values
    ef = ema(c, ema_fast); es = ema(c, ema_slow); r = rsi(c, rsi_p)
    up_trend = ef > es
    r_prev = np.concatenate([[r[0]], r[:-1]])
    c_prevhigh = np.concatenate([[h[0]], h[:-1]])

    if confirm == 'none':
        sig = up_trend & (r < rsi_th)
    elif confirm == 'rsi_turn':
        # کفِ RSI شکل گرفت: کندلِ قبل در ناحیهٔ اشباع بود، حالا RSI برمی‌گردد بالا.
        sig = up_trend & (r_prev < rsi_th) & (r > r_prev) & (r < rsi_th + 10)
    elif confirm == 'price_turn':
        # RSI اخیراً به ناحیهٔ pullback رفت + کندلِ تأییدیِ صعودی (close از high قبلی رد شد).
        dipped = (r < rsi_th) | (r_prev < rsi_th)
        sig = up_trend & dipped & (c > c_prevhigh)
    else:
        raise ValueError(confirm)
    return np.nan_to_num(sig).astype(bool)


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


# ---- بهترین پیکربندیِ هر TF (per-TF، غیررند — رفعِ اشتباه #۶/#۷) ----
# منطق: هستهٔ دقت‌محور (pullback + تأییدِ بازگشت) + فیلترِ رژیمِ persistence.
# *** هندسهٔ منصفانه: TP >= SL همیشه (breakeven <= 50%) ⇒ WR واقعی است نه تورمِ هندسی. ***
# هر TF جدا اسکن می‌شود؛ TP/SL و آستانهٔ فیلتر مخصوصِ خودش را دارد.
BEST_CFG = {
    # asset_tf: dict(ef, es, rp, rth, confirm, hurst, [er], [r2], sl, tp, mh)
    'XAUUSD_M5':  dict(ef=20, es=100, rp=21, rth=35, confirm='rsi_turn',
                       hurst=0.57, er=0.25,           sl=120, tp=120, mh=96),
}


def build_layer(df, cfg):
    """سیگنالِ نهاییِ لایه = هستهٔ دقت‌محور + فیلترِ رژیمِ Hurst (+ ER / R² اختیاری)."""
    base = core_signal_confirmed(df, cfg['ef'], cfg['es'], cfg['rp'], cfg['rth'],
                                 confirm=cfg.get('confirm', 'rsi_turn'))
    hu = ib.compute('hurst', df).values
    sig = base & (np.nan_to_num(hu, nan=-1.0) > cfg['hurst'])
    if cfg.get('er') is not None:
        er = ib.compute('er_lucas_29', df).values
        sig = sig & (np.nan_to_num(er, nan=-1.0) > cfg['er'])
    if cfg.get('r2') is not None:
        r2 = ib.compute('r2_fib_89', df).values
        sig = sig & (np.nan_to_num(r2, nan=-1.0) > cfg['r2'])
    return sig


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
