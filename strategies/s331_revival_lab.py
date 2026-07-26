"""
S331 — آزمایشگاهِ احیای S79 (XAUUSD Trend-Pullback) تحتِ RQS+
================================================================================
تشخیصِ پایه (از s331_s79_revival_audit.py):
  S79-M5 لبهٔ آماریِ اصیل دارد (G1✓ p=0.000، G4✓ walk-forward، G5✓)، اما رد می‌شود
  به‌خاطرِ سه چیز که همه از یک ریشه‌اند = «هندسهٔ خروجِ نامتقارن (R:R=1:2.4) + نگهداریِ
  بلند (۷۲ کندل)»:
    G0: WR=39٪ < 60٪
    G2: PF=1.21 < 1.3
    G3: MaxDD=17.4٪ > 8٪  و  MCL=14 > 8

فلسفهٔ احیا (تفکرِ غیرخطی):
  RQS+ یک «پروفایلِ معاملاتیِ» متفاوت می‌طلبد: WR بالا + دُمِ کوتاه. پس هندسهٔ خروج را
  معکوس می‌کنیم (TP نزدیک‌تر ⇒ WR بالا) و برای جبرانِ افتِ لبه، کیفیتِ ورود را با چند
  فیلترِ همزمان (قانونِ بی‌نهایتِ بهبود) بالا می‌بریم. همه‌چیز بر حسبِ ATR شناور است
  (قانونِ «همه‌چیز شناور است»)، نه اعدادِ رند.

این آزمایشگاه فضای بهبود را روی XAUUSD-M5 (نقطهٔ شروع طبقِ قانونِ مولتی‌تایم‌فریم) جارو
می‌کند و بهترین ترکیب‌ها را با RQS+ رتبه‌بندی می‌کند.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE
from engine import rqs as RQS
from itertools import product


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
    adx_ = pd.Series(dx).ewm(alpha=1/p, adjust=False).mean().values
    return adx_, pdi, mdi


def build_signal(df, ema_f, ema_s, rsi_p, rsi_th, adx_min, dist_atr_min, confirm):
    """
    سیگنالِ Long با کیفیتِ ورودِ بالا (چند فیلترِ همزمان):
      - روندِ صعودی:      ema_f > ema_s
      - pullback عمیق:    RSI < rsi_th
      - روندِ قوی:        ADX >= adx_min           (فیلترِ نو ۱ — ضدِ رنج/whipsaw)
      - کشش/عمقِ کافی:    (ema_f - close)/ATR >= dist_atr_min  (فیلترِ نو ۲ — فقط pullbackِ واقعی)
      - تأییدِ بازگشت:     اگر confirm=True، close کندلِ سیگنال > open آن (کندلِ صعودی)
    """
    c = df['close'].values
    o = df['open'].values
    e_f = ema(c, ema_f); e_s = ema(c, ema_s)
    r = rsi(c, rsi_p)
    adx_, _, _ = adx_series(df, 14)
    atr_ = atr_series(df, 14)
    dist_atr = (e_f - c) / (atr_ + 1e-9)   # چقدر زیرِ EMAِ سریع افتاده (بر حسبِ ATR)

    sig = (e_f > e_s) & (r < rsi_th) & (adx_ >= adx_min) & (dist_atr >= dist_atr_min)
    if confirm:
        sig = sig & (c > o)
    long_sig = np.nan_to_num(sig).astype(bool)
    return long_sig, np.zeros(len(df), bool), atr_


def setup_asset(base, tf, path):
    key = f'{base}_{tf}_TMP'
    cfg = SE.ASSETS[base].copy(); cfg['file'] = path
    SE.ASSETS[key] = cfg
    return key


def run_variant(df, key, atr_, long_sig, short_sig, sl_atr, tp_atr, max_hold, pip):
    """SL/TP شناور بر حسبِ ATR (به pip تبدیل می‌شود)."""
    sl_pip_arr = np.maximum(sl_atr * atr_ / pip, 1.0)
    tp_pip_arr = np.maximum(tp_atr * atr_ / pip, 1.0)
    tr = SE.simulate_trades(df, long_sig, short_sig, sl_pip_arr, tp_pip_arr, key, max_hold=max_hold)
    if tr is None or len(tr) < 30:
        return None, tr
    r = RQS.compute_rqs(tr, key)
    return r, tr


def main():
    base, tf, path = 'XAUUSD', 'M5', 'data/XAUUSD_M5.csv'
    key = setup_asset(base, tf, path)
    pip = SE.ASSETS[key]['pip']
    df = SE.load_data(path)

    print("=" * 120)
    print(f"  S331 آزمایشگاهِ احیای S79 — {base}-{tf} — جاروی فضای بهبود (ATR-scaled, WR-first)")
    print("=" * 120)

    # فضای جستجو — عمداً اعدادِ غیررند و متنوع (ضدِ اشتباهِ #7)
    rsi_ths     = [38, 42, 46]         # pullbackِ کم‌عمق‌تر ⇒ ورودِ بیشتر با WR بهتر
    adx_mins    = [18, 23, 28]         # فیلترِ قدرتِ روند
    dist_mins   = [0.0, 0.4, 0.8]      # عمقِ pullback بر حسبِ ATR
    confirms    = [True, False]
    # هندسهٔ خروجِ WR-first: TP نزدیک‌تر از SL (معکوسِ S79)
    sltp_pairs  = [(1.6, 1.1), (2.0, 1.3), (1.4, 0.9), (2.4, 1.5)]  # (sl_atr, tp_atr)
    holds       = [24, 40]

    results = []
    for rsi_th, adx_min, dist_min, confirm in product(rsi_ths, adx_mins, dist_mins, confirms):
        long_sig, short_sig, atr_ = build_signal(df, 20, 100, 21, rsi_th, adx_min, dist_min, confirm)
        if long_sig.sum() < 30:
            continue
        for (sl_atr, tp_atr), mh in product(sltp_pairs, holds):
            r, tr = run_variant(df, key, atr_, long_sig, short_sig, sl_atr, tp_atr, mh, pip)
            if r is None:
                continue
            m = r['metrics']
            results.append({
                'rsi_th': rsi_th, 'adx_min': adx_min, 'dist_min': dist_min,
                'confirm': confirm, 'sl_atr': sl_atr, 'tp_atr': tp_atr, 'mh': mh,
                'rqs': r['rqs_score'], 'passed': r['passed'], 'gates': r['gates'],
                'n': m['n_trades'], 'wr': m['win_rate'], 'pf': m['profit_factor'],
                'dd': m['max_dd_pct'], 'mcl': m['max_consec_losses'],
                'net': m['net_profit'], 'p': m['p_value'],
            })

    results.sort(key=lambda x: x['rqs'], reverse=True)
    print(f"\n  کل ترکیب‌های آزموده‌شده: {len(results)}")
    print(f"\n  --- ۲۰ ترکیبِ برتر بر اساسِ RQS+ ---")
    print(f"  {'RQS':>5} {'PASS':>5} | {'rsi':>3} {'adx':>3} {'dst':>4} {'cfm':>5} {'sl':>4} {'tp':>4} {'mh':>3} | "
          f"{'n':>4} {'WR':>5} {'PF':>5} {'DD':>5} {'MCL':>3} {'net':>8} | gates")
    for x in results[:20]:
        g = x['gates']; gl = ''.join('✓' if g[k] else '✗' for k in ['G0','G1','G2','G3','G4','G5'])
        print(f"  {x['rqs']:5.1f} {str(x['passed']):>5} | {x['rsi_th']:3d} {x['adx_min']:3d} {x['dist_min']:4.1f} "
              f"{str(x['confirm']):>5} {x['sl_atr']:4.1f} {x['tp_atr']:4.1f} {x['mh']:3d} | "
              f"{x['n']:4d} {x['wr']:5.1f} {x['pf']:5.2f} {x['dd']:5.1f} {x['mcl']:3d} {x['net']:8.0f} | {gl}")

    passed = [x for x in results if x['passed']]
    print(f"\n  ✅ تعدادِ ترکیب‌های پاس‌شده (RQS+ ≥ آستانهٔ ۶ گیت): {len(passed)}")
    print("=" * 120)


if __name__ == '__main__':
    main()
