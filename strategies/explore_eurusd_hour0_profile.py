"""
explore_eurusd_hour0_profile.py — پروفایلِ دقیقِ سیگنالِ «ساعتِ 0 UTC صعودی»
================================================================================
قانونِ #۱: فقط سودِ خالص. سودِ خالص = XAUUSD + EURUSD.

کشفِ پایدار: ساعتِ 0 UTC یک drift صعودیِ بسیار قوی و پایدار دارد (t≈+10..+15 در هر
4 دورهٔ زمانی). قبل از ساختِ استراتژی، پروفایلِ بهینهٔ نگهداری را می‌سنجیم:
  • بهترین افقِ نگهداری (چند کندل پس از باز شدنِ کندلِ ساعتِ 0) کدام است؟
  • میانگین/انحراف/MFE/MAE برای انتخابِ TP/SL منطقی.
همه shift-safe. هیچ بهینه‌سازیِ overfitِ کل-داده نمی‌کنیم؛ فقط توصیفِ آماری.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width', 220)

PIP = 0.0001

def main():
    df = load_data('data/EURUSD_M15.csv')
    n = len(df)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['dt'].dt.hour
    df['minute'] = df['dt'].dt.minute
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values

    # کندلِ ورود: اولین کندلِ ساعتِ 0 UTC (minute==0). ورود در open همان کندل شبیه‌سازی
    # (در عمل: در open کندلِ بعد از تشخیص؛ اینجا برای پروفایل از open کندلِ ساعت0 استفاده می‌کنیم)
    entry_idx = df.index[(df['hour']==0) & (df['minute']==0)].values
    entry_idx = entry_idx[(entry_idx > 100) & (entry_idx < n - 100)]
    print(f"=== پروفایلِ سیگنالِ ساعتِ 0 UTC (n={len(entry_idx)} روز) ===\n", flush=True)

    # بازدهِ صعودی (Long) در افق‌های مختلف از open کندلِ ساعت0
    print("### بازدهِ Long از open کندلِ ساعت0 در افق‌های مختلف (pip)")
    print(f"{'hold':>6} {'mean':>8} {'median':>8} {'std':>8} {'WR%':>7} {'sum':>10}")
    best = None
    for hold in [1,2,3,4,6,8,12,16,20,24,32,40,48]:
        entry = o[entry_idx]
        exit_ = c[np.minimum(entry_idx + hold, n-1)]
        ret = (exit_ - entry) / PIP
        wr = (ret > 0).mean() * 100
        s = ret.sum()
        print(f"{hold:>6} {ret.mean():>8.2f} {np.median(ret):>8.2f} {ret.std():>8.2f} {wr:>7.1f} {s:>10.0f}", flush=True)
        if best is None or ret.mean() > best[1]:
            best = (hold, ret.mean())

    # MFE/MAE برای تعیینِ TP/SL: در افقِ 8 کندل، بیشترین سود و بیشترین ضررِ درون‌معامله
    print("\n### MFE/MAE در افقِ نگهداریِ 8 کندل (برای طراحیِ TP/SL)")
    hold = 8
    mfe_list, mae_list = [], []
    for ei in entry_idx:
        entry = o[ei]
        window_h = h[ei:ei+hold]; window_l = l[ei:ei+hold]
        mfe = (window_h.max() - entry) / PIP
        mae = (entry - window_l.min()) / PIP
        mfe_list.append(mfe); mae_list.append(mae)
    mfe = np.array(mfe_list); mae = np.array(mae_list)
    print(f"  MFE (حداکثر سودِ درون‌معامله): میانگین={mfe.mean():.1f}  میانه={np.median(mfe):.1f}  p75={np.percentile(mfe,75):.1f}")
    print(f"  MAE (حداکثر ضررِ درون‌معامله): میانگین={mae.mean():.1f}  میانه={np.median(mae):.1f}  p75={np.percentile(mae,75):.1f}")

    # آیا فیلترِ جهتِ کندلِ آسیا (23 UTC قبلی) کمک می‌کند؟
    print("\n### فیلترِ زمینه: آیا جهتِ چند کندلِ قبل از ساعت0 سیگنال را تقویت می‌کند؟")
    hold = 8
    for lookback in [4, 8, 16]:
        entry = o[entry_idx]
        prior = (c[entry_idx-1] - c[entry_idx-1-lookback]) / PIP  # حرکتِ قبل از ورود
        fut = (c[np.minimum(entry_idx+hold,n-1)] - entry) / PIP
        # وقتی قبلش نزولی بود (pullback) در برابر وقتی صعودی بود
        up_prior = prior > 0
        print(f"  lookback={lookback:>2}: قبل‌صعودی fut_mean={fut[up_prior].mean():+.2f} (n={up_prior.sum()}) | "
              f"قبل‌نزولی fut_mean={fut[~up_prior].mean():+.2f} (n={(~up_prior).sum()})", flush=True)

    print("\nتمام.", flush=True)

if __name__ == '__main__':
    main()
