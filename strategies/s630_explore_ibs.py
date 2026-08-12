# -*- coding: utf-8 -*-
"""
S630 — کاوشِ IBS (Internal Bar Strength) روی طلا — «فقط نیمهٔ نخستِ داده»
==========================================================================
مسیرِ چندگانگی: Route C (hold-out).
این اسکریپت **اکتشاف** است، نه آزمونِ نهایی. هرگز به نیمهٔ دومِ داده دست نمی‌زند.
نیمهٔ دوم مُهروموم می‌ماند تا پس از پیش‌ثبتِ (PREREG) کامیت‌شده، فقط «یک» آزمونِ
نهایی روی آن اجرا شود.

مفهوم: IBS = (close - low) / (high - low) ∈ [0,1]
  IBS پایین = بسته‌شدن نزدیکِ کفِ کندل = اشباعِ فشارِ فروشِ درون‌کندلی → فرضیهٔ
  بازگشت (long). قرینه برای IBS بالا (short).

چرا IBS خام روی M1 کافی نیست: تقریباً هر کندلِ نزولیِ کوچکی IBS پایین می‌گیرد.
پس رویدادمحورش می‌کنیم: میانگینِ IBS در k کندلِ اخیر (IBS_k) که خودش کمیاب‌تر و
معنادارتر است — «اشباعِ چندکندلی» نه نویزِ تک‌کندل. k از دنبالهٔ فیبوناچی
(قانونِ غیررند #7) و آستانه‌ها غیررند.

هندسه: SL = TP = 1.5 × ATR(100) (متقارن، هرگز TP<SL — اشتباه #8 ممنوع).
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = sys.argv[1] if len(sys.argv) > 1 else 'M1'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's630_explore')
os.makedirs(OUT, exist_ok=True)

t0 = time.time()
d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
SRC = d['src']

# ---- فقط نیمهٔ نخست (Route C — اکتشاف) ----
half = len(df) // 2
df = df.iloc[:half].reset_index(drop=True)

h, l, c = df['high'].values, df['low'].values, df['close'].values
rng = h - l
ibs = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)
ibs_s = pd.Series(ibs)

# ATR(100) برای هندسهٔ شناور
tr = np.maximum(h - l, np.maximum(abs(h - np.roll(c, 1)), abs(l - np.roll(c, 1))))
tr[0] = h[0] - l[0]
atr = pd.Series(tr).rolling(100).mean().values
med_atr = float(np.nanmedian(atr))
pip = 0.1  # XAUUSD pip
SL_K = 1.5
sl_pip = med_atr * SL_K / pip
tp_pip = sl_pip  # متقارن

print(f'TF={TF} src={SRC}')
print(f'bars(first half)={len(df)}  medATR={med_atr:.4f}$  SL=TP={sl_pip:.2f}pip')
print(f'IBS dist: p5={np.percentile(ibs,5):.3f} p25={np.percentile(ibs,25):.3f} '
      f'p50={np.percentile(ibs,50):.3f} p75={np.percentile(ibs,75):.3f} p95={np.percentile(ibs,95):.3f}')

# ---- خطِ پایهٔ بذردار: WR ورودِ بی‌قید با همان هندسه (برای سنجشِ lift خام) ----
rs = np.random.RandomState(3141592)
base_idx = np.sort(rs.choice(np.arange(200, len(df) - 200), size=min(4000, len(df) // 50), replace=False))
base_lo = pd.Series(False, index=df.index); base_lo.iloc[base_idx[::2]] = True
base_hi = pd.Series(False, index=df.index); base_hi.iloc[base_idx[1::2]] = True
base_tr = se.simulate_trades(df, base_lo, base_hi, sl_pip=sl_pip, tp_pip=tp_pip,
                             asset='XAUUSD', max_hold=64, allow_overlap=False)
base_wins = base_tr['outcome'].eq('win') if 'outcome' in base_tr else (base_tr['pnl_pip'] > 0)
BASE_WR = float(base_wins.mean()) if len(base_tr) else float('nan')
print(f'baseline (random entry, seeded): n={len(base_tr)}  wr={BASE_WR*100:.2f}%')

results = []
# خانوادهٔ اکتشافی: k فیبوناچی، آستانه‌های غیررند
for k in [3, 5, 8, 13]:
    ibs_k = ibs_s.rolling(k).mean()
    for thr in [0.145, 0.19, 0.235]:
        # رویداد: ورودِ میانگینِ IBS_k به زیرِ آستانه (گذر، نه سطح)
        lo_evt = (ibs_k.shift(1) >= thr) & (ibs_k < thr)
        hi_evt = (ibs_k.shift(1) <= 1 - thr) & (ibs_k > 1 - thr)
        n_lo, n_hi = int(lo_evt.sum()), int(hi_evt.sum())
        if n_lo + n_hi < 50:
            results.append(dict(k=k, thr=thr, n_long=n_lo, n_short=n_hi, note='too_rare'))
            continue
        tr_df = se.simulate_trades(df, lo_evt.fillna(False), hi_evt.fillna(False),
                                   sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                   max_hold=64, allow_overlap=False)
        if len(tr_df) == 0:
            continue
        wins = tr_df['outcome'].eq('win') if 'outcome' in tr_df else (tr_df['pnl_pip'] > 0)
        wr = float(wins.mean())
        n = len(tr_df)
        by = tr_df.groupby('direction')['pnl_pip'].agg(['count', 'mean']) if 'direction' in tr_df else None
        rec = dict(k=k, thr=thr, n=n, wr=round(wr * 100, 3),
                   lift_pp=round((wr - BASE_WR) * 100, 3),
                   z_rough=round((wr - BASE_WR) / max(1e-9, (BASE_WR * (1 - BASE_WR) / n) ** 0.5), 2),
                   mean_pnl_pip=round(float(tr_df['pnl_pip'].mean()), 3))
        if by is not None:
            for side in by.index:
                rec[f'{side}_n'] = int(by.loc[side, 'count'])
                rec[f'{side}_mean'] = round(float(by.loc[side, 'mean']), 3)
        results.append(rec)
        print(rec, flush=True)

out_path = f'{OUT}/{TF}_ibs_scan.json'
with open(out_path, 'w') as f:
    json.dump(dict(tf=TF, src=SRC, half_bars=len(df), sl_pip=sl_pip, tp_pip=tp_pip,
                   baseline_wr=BASE_WR, baseline_n=int(len(base_tr)),
                   results=results, elapsed_s=round(time.time() - t0, 1)), f, ensure_ascii=False, indent=1)
print(f'\nsaved -> {out_path}  ({time.time()-t0:.0f}s)')
