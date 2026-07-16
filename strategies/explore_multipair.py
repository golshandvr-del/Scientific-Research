"""
اکتشاف: رابطهٔ آماری XAUUSD با سبد جفت‌ارزهای دلاری (DXY/EURUSD/AUDUSD/USDCHF).

هدف (Recipe-S25 مرحله ۱): پیش از ساختِ هر feature، به‌صورت کمی و آماری تأیید کنیم
که این جفت‌ارزها اطلاعاتِ جهت‌دارِ *برون‌زا* برای طلا دارند — و مهم‌تر، آیا این
اطلاعات هم‌زمان است یا پیش‌رو (lead) نسبت به حرکتِ بعدیِ طلا (چون فقط اطلاعات
پیش‌رو برای پیش‌بینی قابل‌استفاده است، بدون look-ahead).

قاعده: برای هر کندل M15 طلا در زمان t، فقط از کندل جفت‌ارزهایی استفاده می‌کنیم که
close آن‌ها <= t بسته شده (merge_asof backward). سپس همبستگیِ:
   sign( xau_future_return[t -> t+k] )  با  اطلاعاتِ تا زمانِ t از جفت‌ارزها
را می‌سنجیم. اگر معنادار باشد ⇒ سیگنالِ پیش‌رو داریم.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scipy import stats

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')

def load(path):
    d = pd.read_csv(path)
    d['dt'] = pd.to_datetime(d['time'], unit='s')
    d = d.sort_values('dt').drop_duplicates('dt').reset_index(drop=True)
    return d

def align_close(xau, other, name):
    """close جفت‌ارز دیگر را روی زمانِ کندل طلا هم‌تراز می‌کند (backward, no look-ahead)."""
    left = xau[['dt']].copy(); left['_row'] = np.arange(len(left))
    right = other[['dt', 'close']].rename(columns={'close': name}).sort_values('dt')
    m = pd.merge_asof(left.sort_values('dt'), right, on='dt',
                      direction='backward', tolerance=pd.Timedelta('2h'))
    m = m.sort_values('_row').reset_index(drop=True)
    return m[name].values

def main():
    print("در حال بارگذاری XAUUSD M15 ...")
    xau = load(os.path.join(DATA, 'XAUUSD_M15.csv'))
    n = len(xau)
    print(f"XAU M15: {n} کندل، {xau['dt'].min()} تا {xau['dt'].max()}")

    pairs = {
        'DXY':    'DXY_M15.csv',
        'EURUSD': 'EURUSD_M15.csv',
        'AUDUSD': 'AUDUSD_M15.csv',
        'USDCHF': 'USDCHF_M15.csv',
    }
    aligned = {}
    for nm, fn in pairs.items():
        p = os.path.join(DATA, fn)
        if not os.path.exists(p):
            print(f"  ! {fn} یافت نشد"); continue
        d = load(p)
        c = align_close(xau, d, nm)
        cov = np.isfinite(c).mean() * 100
        aligned[nm] = c
        print(f"  {nm}: p-پوشش هم‌ترازی = {cov:.1f}%  ({d['dt'].min()} تا {d['dt'].max()})")

    xc = xau['close'].values
    xau_ret1 = pd.Series(xc).pct_change().values  # بازدهِ همان کندل (هم‌زمان)

    # ---- ۱) همبستگی هم‌زمان بازدهِ طلا با بازدهِ هر جفت‌ارز ----
    print("\n=== ۱) همبستگی هم‌زمان بازده M15 (طلا ↔ جفت‌ارز) ===")
    for nm, c in aligned.items():
        r = pd.Series(c).pct_change().values
        mask = np.isfinite(xau_ret1) & np.isfinite(r)
        cc = np.corrcoef(xau_ret1[mask], r[mask])[0, 1]
        print(f"  corr(XAU, {nm}) = {cc:+.3f}   (n={mask.sum()})")

    # ---- ۲) قدرتِ پیش‌روِ سیگنال: بازده گذشتهٔ جفت‌ارز → بازده آیندهٔ طلا ----
    # سیگنال در زمان t (فقط اطلاعات تا t): بازدهِ k کندلِ اخیرِ جفت‌ارز.
    # هدف: بازدهِ h کندلِ آیندهٔ طلا (t -> t+h). این پیش‌بینی است، نه هم‌زمانی.
    print("\n=== ۲) قدرت پیش‌رو (predictive): بازده گذشته جفت‌ارز → بازده آینده طلا ===")
    for h in [1, 4, 8, 16]:
        fut = (pd.Series(xc).shift(-h) / pd.Series(xc) - 1).values  # بازده آینده طلا
        print(f"\n  افق آینده h={h} کندل ({h*15}دقیقه):")
        for nm, c in aligned.items():
            for k in [4, 16]:
                past = (pd.Series(c) / pd.Series(c).shift(k) - 1).values  # بازده گذشته جفت‌ارز
                mask = np.isfinite(fut) & np.isfinite(past)
                if mask.sum() < 1000:
                    continue
                cc, pv = stats.pearsonr(past[mask], fut[mask])
                sig = '***' if pv < 0.001 else ('**' if pv < 0.01 else ('*' if pv < 0.05 else ''))
                print(f"    {nm} ret_{k} → XAU_fut_{h}: corr={cc:+.4f} p={pv:.1e} {sig}")

    # ---- ۳) سیگنال سبد ترکیبی (composite dollar-strength) ----
    # فرض: DXY↑, USDCHF↑ = دلار قوی (طلا نزولی). EURUSD↑, AUDUSD↑ = دلار ضعیف (طلا صعودی).
    # سبد جهت‌دار (پیش‌بینیِ جهتِ طلا) = -DXY -USDCHF +EURUSD +AUDUSD  (بازده گذشته)
    print("\n=== ۳) سیگنال سبد ترکیبی «قدرت دلار» (بازده گذشته k، همه هم‌تراز) ===")
    for k in [4, 8, 16]:
        comp = np.zeros(n); cnt = np.zeros(n)
        for nm, c in aligned.items():
            r = (pd.Series(c) / pd.Series(c).shift(k) - 1).values
            z = (r - np.nanmean(r)) / (np.nanstd(r) + 1e-12)
            sgn = {'DXY': -1, 'USDCHF': -1, 'EURUSD': +1, 'AUDUSD': +1}[nm]
            valid = np.isfinite(z)
            comp[valid] += sgn * z[valid]; cnt[valid] += 1
        comp = np.where(cnt > 0, comp / np.maximum(cnt, 1), np.nan)  # میانگین سبد (جهتِ طلا)
        for h in [1, 4, 8, 16]:
            fut = (pd.Series(xc).shift(-h) / pd.Series(xc) - 1).values
            mask = np.isfinite(comp) & np.isfinite(fut)
            cc, pv = stats.pearsonr(comp[mask], fut[mask])
            sig = '***' if pv < 0.001 else ('**' if pv < 0.01 else ('*' if pv < 0.05 else ''))
            print(f"  basket_ret_{k} → XAU_fut_{h}: corr={cc:+.4f} p={pv:.1e} {sig} (n={mask.sum()})")

    # ---- ۴) آزمون جهت: وقتی سبد قوی صعودی، طلا چند درصد مواقع صعود کرد؟ ----
    print("\n=== ۴) نرخ اصابت جهت: سبد قوی (صدک بالا/پایین) → جهت آیندهٔ طلا h=4 ===")
    k = 8
    comp = np.zeros(n); cnt = np.zeros(n)
    for nm, c in aligned.items():
        r = (pd.Series(c) / pd.Series(c).shift(k) - 1).values
        z = (r - np.nanmean(r)) / (np.nanstd(r) + 1e-12)
        sgn = {'DXY': -1, 'USDCHF': -1, 'EURUSD': +1, 'AUDUSD': +1}[nm]
        valid = np.isfinite(z); comp[valid] += sgn * z[valid]; cnt[valid] += 1
    comp = np.where(cnt > 0, comp / np.maximum(cnt, 1), np.nan)
    fut = (pd.Series(xc).shift(-4) / pd.Series(xc) - 1).values
    mask = np.isfinite(comp) & np.isfinite(fut)
    cq = comp[mask]; fq = fut[mask]
    hi = cq >= np.quantile(cq, 0.8)   # سبد قویاً صعودیِ طلا
    lo = cq <= np.quantile(cq, 0.2)   # سبد قویاً نزولیِ طلا
    print(f"  سبد صعودی قوی (top20%): P(طلا صعود) = {(fq[hi] > 0).mean()*100:.2f}%  n={hi.sum()}")
    print(f"  سبد نزولی قوی (bot20%): P(طلا نزول) = {(fq[lo] < 0).mean()*100:.2f}%  n={lo.sum()}")
    print(f"  کل مبنا: P(طلا صعود) = {(fq > 0).mean()*100:.2f}%")

if __name__ == '__main__':
    main()
