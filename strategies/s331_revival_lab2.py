"""
S331 — آزمایشگاهِ احیای S79 — نسلِ دوم (هدف: عبور از G2/PF)
================================================================================
نتیجهٔ نسلِ اول (s331_revival_lab.py):
  با معکوس‌کردنِ هندسهٔ خروج (SL>TP) + فیلترهای ADX/confirm:
    WR 39٪→69٪ (G0✓)، DD 17.4٪→6.1٪ (G3✓)، MCL 14→3، G1/G4/G5 ✓
  تنها گیتِ مقاوم: **G2 (PF=1.18 < 1.3)**.

فلسفهٔ نسلِ دوم (تفکرِ غیرخطی):
  PF پایین است چون SL بزرگ (۲.۴ ATR) هر باخت را گران می‌کند. برای بالابردنِ PF
  بدونِ کشتنِ WR، دو اهرمِ نو:
    (الف) **break-even + trailing** (موتور پشتیبانی می‌کند): باختِ بالقوه را پس از
          حرکتِ مساعد به صفر/سود قفل می‌کند ⇒ کاهشِ اندازهٔ باخت‌ها ⇒ PF بالاتر.
    (ب) **فیلترِ رژیمِ قوی‌تر**: فقط در روندِ صعودیِ *تأییدشده* (فاصله از EMA200 مثبت
        + شیبِ مثبت) وارد شو ⇒ بردها بزرگ‌تر، باخت‌ها کمتر.
  همه بر حسبِ ATR شناور (قانونِ شناوری).
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
    return pd.Series(dx).ewm(alpha=1/p, adjust=False).mean().values, pdi, mdi


def slope_norm(x, p):
    xi = np.arange(p); xm = xi.mean(); den = ((xi - xm) ** 2).sum()
    s = pd.Series(x).rolling(p).apply(lambda y: ((xi - xm) * (y - y.mean())).sum() / den, raw=True).values
    return s / (np.asarray(x) + 1e-9)


def build_signal(df, rsi_th, adx_min, regime):
    """
    regime: 'basic' = ema20>ema100 ؛ 'strong' = + close>ema200 + slope50>0
    confirm همیشه True (کندلِ صعودیِ سیگنال) — از نسلِ اول ثابت شد بهترین است.
    """
    c = df['close'].values; o = df['open'].values
    e20 = ema(c, 20); e100 = ema(c, 100); e200 = ema(c, 200)
    r = rsi(c, 21)
    adx_, _, _ = adx_series(df, 14)
    sig = (e20 > e100) & (r < rsi_th) & (adx_ >= adx_min) & (c > o)
    if regime == 'strong':
        sl50 = slope_norm(c, 50)
        sig = sig & (c > e200) & (sl50 > 0)
    return np.nan_to_num(sig).astype(bool), np.zeros(len(df), bool)


def setup_asset(base, tf, path):
    key = f'{base}_{tf}_TMP'
    cfg = SE.ASSETS[base].copy(); cfg['file'] = path
    SE.ASSETS[key] = cfg
    return key


def main():
    base, tf, path = 'XAUUSD', 'M5', 'data/XAUUSD_M5.csv'
    key = setup_asset(base, tf, path)
    pip = SE.ASSETS[key]['pip']
    df = SE.load_data(path)
    atr_ = atr_series(df, 14)

    print("=" * 124)
    print(f"  S331 نسلِ دوم — {base}-{tf} — هدف: عبور از G2/PF با break-even + trailing + رژیمِ قوی")
    print("=" * 124)

    rsi_ths   = [36, 40, 44]
    adx_mins  = [18, 24]
    regimes   = ['basic', 'strong']
    sltp      = [(2.4, 1.5), (2.0, 1.4), (2.8, 1.7)]     # (sl_atr, tp_atr)
    holds     = [40, 60]
    # break-even trigger و trailing بر حسبِ ATR (None = خاموش)
    be_trigs  = [None, 0.8, 1.2]     # وقتی سود به این×ATR رسید SL→BE
    trails    = [None, 1.5, 2.2]     # تریلینگ به فاصلهٔ این×ATR

    results = []
    for rsi_th, adx_min, regime in product(rsi_ths, adx_mins, regimes):
        long_sig, short_sig = build_signal(df, rsi_th, adx_min, regime)
        if long_sig.sum() < 30:
            continue
        for (sl_atr, tp_atr), mh, be, tr_ in product(sltp, holds, be_trigs, trails):
            sl_pip_arr = np.maximum(sl_atr * atr_ / pip, 1.0)
            tp_pip_arr = np.maximum(tp_atr * atr_ / pip, 1.0)
            # be/trail را به آرایهٔ pip تبدیل کن (میانهٔ ATR × ضریب) — موتور اسکالر می‌خواهد
            be_pip = None if be is None else float(np.nanmedian(be * atr_ / pip))
            tr_pip = None if tr_ is None else float(np.nanmedian(tr_ * atr_ / pip))
            trades = SE.simulate_trades(df, long_sig, short_sig, sl_pip_arr, tp_pip_arr, key,
                                        max_hold=mh, be_trigger_pip=be_pip, trail_pip=tr_pip)
            if trades is None or len(trades) < 30:
                continue
            rr = RQS.compute_rqs(trades, key)
            m = rr['metrics']
            results.append({
                'rsi_th': rsi_th, 'adx_min': adx_min, 'regime': regime,
                'sl_atr': sl_atr, 'tp_atr': tp_atr, 'mh': mh, 'be': be, 'tr': tr_,
                'rqs': rr['rqs_score'], 'passed': rr['passed'], 'gates': rr['gates'],
                'n': m['n_trades'], 'wr': m['win_rate'], 'pf': m['profit_factor'],
                'dd': m['max_dd_pct'], 'mcl': m['max_consec_losses'], 'net': m['net_profit'],
            })

    results.sort(key=lambda x: (x['passed'], x['rqs']), reverse=True)
    print(f"\n  کل ترکیب‌ها: {len(results)}")
    passed = [x for x in results if x['passed']]
    print(f"  ✅ پاس‌شده: {len(passed)}\n")
    print(f"  {'RQS':>5} {'P':>1} | {'rsi':>3} {'adx':>3} {'reg':>6} {'sl':>4} {'tp':>4} {'mh':>3} "
          f"{'be':>4} {'tr':>4} | {'n':>4} {'WR':>5} {'PF':>5} {'DD':>5} {'MCL':>3} {'net':>7} | gates")
    for x in results[:25]:
        g = x['gates']; gl = ''.join('✓' if g[k] else '✗' for k in ['G0','G1','G2','G3','G4','G5'])
        print(f"  {x['rqs']:5.1f} {'Y' if x['passed'] else '.':>1} | {x['rsi_th']:3d} {x['adx_min']:3d} "
              f"{x['regime']:>6} {x['sl_atr']:4.1f} {x['tp_atr']:4.1f} {x['mh']:3d} "
              f"{str(x['be']):>4} {str(x['tr']):>4} | {x['n']:4d} {x['wr']:5.1f} {x['pf']:5.2f} "
              f"{x['dd']:5.1f} {x['mcl']:3d} {x['net']:7.0f} | {gl}")
    print("=" * 124)


if __name__ == '__main__':
    main()
