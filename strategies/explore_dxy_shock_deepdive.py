"""
explore_dxy_shock_deepdive.py — کاوشِ عمیقِ لبهٔ «شوکِ DXY → واکنشِ معکوسِ طلا»
================================================================================
> قانونِ شمارهٔ ۱: تنها معیار = سودِ خالص (XAUUSD + EURUSD). فقط اکتشاف.

اکتشافِ اول (explore_dxy_shock_gold_reaction) لبهٔ زیر را یافت:
  شوکِ ۱-کندلیِ DXY (|ret1|>2σ) ⇒ طلا در کندلِ بعدی معکوس واکنش می‌دهد:
    up-shock ⇒ h1 mean=-2.96pip (t=-2.63)  |  dn-shock ⇒ h1 mean=+1.73pip (t=+2.03)

این کاوش عمیق‌تر می‌شود:
  ۱) جاروبِ آستانهٔ شوک (1.5σ..3.0σ) — کدام آستانه قوی‌ترین t و بیشترین مقدار؟
  ۲) پایداریِ دو-نیمه (both halves) برای هر آستانه.
  ۳) فیلترِ ساعت (آیا شوک در سشنِ US/EU قوی‌تر است؟).
  ۴) قیدِ «طلا هم‌سو حرکت نکرده باشد» (آیا واگراییِ لحظه‌ای لبه را تیزتر می‌کند؟).
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
PIP = 0.10
XAU = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
DXY = os.path.join(ROOT, 'data', 'DXY_M15.csv')


def load_aligned():
    x = pd.read_csv(XAU); d = pd.read_csv(DXY)
    x['dt'] = pd.to_datetime(x['time'], unit='s')
    d['dt'] = pd.to_datetime(d['time'], unit='s')
    x = x.sort_values('dt').reset_index(drop=True)
    d = d.sort_values('dt').reset_index(drop=True)
    d['dxy_ret1'] = d['close'].pct_change(1)
    dsub = d[['dt', 'close', 'dxy_ret1']].rename(columns={'close': 'dxy_close'})
    m = pd.merge_asof(x, dsub, on='dt', direction='backward')
    m['hour'] = m['dt'].dt.hour
    m['gold_ret1'] = m['close'].pct_change(1)
    return m


def fwd_pip(c, h):
    n = len(c); fut = np.full(n, np.nan)
    fut[:n-h] = (c[h:] - c[:n-h]) / PIP
    return fut


def tstat(v):
    v = v[~np.isnan(v)]
    if len(v) < 20: return 0.0, 0.0, 0
    return v.mean(), v.mean() / (v.std(ddof=1)/np.sqrt(len(v)) + 1e-12), len(v)


def main():
    m = load_aligned()
    c = m['close'].values; n = len(m)
    sh = m['dxy_ret1'].values
    std = np.nanstd(sh)
    half = n // 2

    print("=" * 78)
    print("کاوشِ عمیق: شوکِ ۱-کندلیِ DXY → واکنشِ معکوسِ طلا (n=%d)" % n)
    print("=" * 78)

    # --- ۱) جاروبِ آستانه، افقِ h=1 و h=2 ---
    for h in [1, 2]:
        fut = fwd_pip(c, h)
        print(f"\n### افقِ طلا h={h} — جاروبِ آستانهٔ شوک ###")
        print(f"{'thr(σ)':>7s} | {'DIR':>4s} | {'mean pip':>9s} | {'t':>6s} | {'N':>5s} | "
              f"{'h1 نیمه':>8s} | {'h2 نیمه':>8s} | both✓")
        for k in [1.5, 2.0, 2.5, 3.0]:
            thr = k * std
            for lbl, mask in [('DN→L', sh < -thr), ('UP→S', sh > thr)]:
                mask = mask & ~np.isnan(sh)
                # جهتِ معامله: dn-shock ⇒ long طلا ; up-shock ⇒ short طلا
                sign = +1.0 if lbl == 'DN→L' else -1.0
                pnl = sign * fut
                mu, t, N = tstat(pnl[mask])
                mu1, _, _ = tstat(pnl[mask & (np.arange(n) < half)])
                mu2, _, _ = tstat(pnl[mask & (np.arange(n) >= half)])
                both = '✓' if (mu1 > 0 and mu2 > 0) else '✗'
                print(f"{k:>7.1f} | {lbl:>4s} | {mu:>+9.2f} | {t:>+6.2f} | {N:>5d} | "
                      f"{mu1:>+8.2f} | {mu2:>+8.2f} | {both}")

    # --- ۲) فیلترِ ساعت (h=1، آستانه 2σ) ---
    print("\n### فیلترِ ساعت (h=1، آستانه=2σ، هر دو جهت ترکیب) ###")
    fut = fwd_pip(c, 1); thr = 2.0 * std
    dn = (sh < -thr); up = (sh > thr)
    pnl = np.where(dn, fut, np.where(up, -fut, np.nan))
    trade_mask = (dn | up) & ~np.isnan(sh)
    for hrs, name in [(range(0,8),'آسیا 0-7'), (range(7,13),'لندن 7-12'),
                      (range(13,17),'همپوشانی 13-16'), (range(16,22),'US 16-21'),
                      (range(22,24),'overnight 22-23')]:
        mask = trade_mask & np.isin(m['hour'].values, list(hrs))
        mu, t, N = tstat(pnl[mask])
        print(f"  {name:18s}: mean={mu:+7.2f}pip  t={t:+5.2f}  N={N}")

    # --- ۳) قیدِ واگراییِ لحظه‌ای (طلا هنوز هم‌سو با شوک واکنش نداده) ---
    print("\n### قیدِ واگرایی: طلا در همان کندل هنوز معکوسِ شوک واکنش نداده (h=1، 2σ) ###")
    gret = m['gold_ret1'].values
    # dn-shock (دلار پایین) + طلا هنوز بالا نرفته (gold_ret1 <= 0) ⇒ فرصتِ long بکرتر
    dn_div = dn & (gret <= 0) & ~np.isnan(gret)
    up_div = up & (gret >= 0) & ~np.isnan(gret)
    pnl_div = np.where(dn_div, fut, np.where(up_div, -fut, np.nan))
    mask_div = (dn_div | up_div)
    mu, t, N = tstat(pnl_div[mask_div])
    mu_all, t_all, N_all = tstat(pnl[trade_mask])
    print(f"  بدونِ قیدِ واگرایی:  mean={mu_all:+7.2f}pip  t={t_all:+5.2f}  N={N_all}")
    print(f"  با قیدِ واگرایی:     mean={mu:+7.2f}pip  t={t:+5.2f}  N={N}")


if __name__ == '__main__':
    main()
