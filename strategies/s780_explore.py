# -*- coding: utf-8 -*-
"""
S780 — فاز اکتشاف (مسیر C از §۶.۲ گزارش ممیزی RQS2)
=====================================================
قانون سخت: این اسکریپت **فقط نیمهٔ اول** دادهٔ کامل (data/mt5_full) را می‌بیند.
نیمهٔ دوم (پس از میانهٔ تقویمی) تا پیش‌ثبت (S780_PREREG) هرگز لمس نمی‌شود.

فرضیه: عبور رویدادیِ فیلترهای چرخه‌ای اِلرز (trendflex / reflex) از آستانه،
تداوم یا بازگشت قیمت طلا را پیش‌بینی می‌کند. دستهٔ cycle در بانک ۴۰۱ اندیکاتوری
تاکنون در هیچ لایهٔ زنده‌ای استفاده نشده (ضداشتباه #۳).

هندسه: SL/TP بر پایهٔ میانهٔ ATR(34) هر TF × ضرایب غیررُند (ضداشتباه #۶ و #۷).
TP هرگز < SL نیست (ضداشتباه #۸).

خروجی: جدول رتبه‌بندی پیکربندی‌ها روی نیمهٔ اول → یک پیکربندی برای پیش‌ثبت.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s780')
os.makedirs(OUT_DIR, exist_ok=True)

ASSET = 'XAUUSD'
# میانهٔ تقویمی دادهٔ کامل (از M15: بار میانی = 1541749500 ≈ 2018-11-09)
SPLIT_EPOCH = 1_541_749_500

# TFهای فاز اکتشاف (نمونهٔ نماینده؛ آزمون نهایی روی همهٔ ۱۹ TF خواهد بود)
EXPLORE_TFS = ['M5', 'M15', 'M30', 'H1', 'H4']

# خانوادهٔ اعلام‌شده — پیش از دیدن هر نتیجه‌ای ثابت است:
INDICATORS = ['trendflex', 'reflex']
THRESHOLDS = [0.83, 1.17, 1.46, 1.73, 2.10]      # غیررُند (ضداشتباه #7)
MODES = ['continuation', 'reversion']             # تداوم / بازگشت
GEOMS = [(1.31, 1.31), (1.31, 1.62), (1.87, 1.87), (1.87, 2.24)]  # (sl_atr, tp_atr), TP>=SL همیشه


def atr_pips(df: pd.DataFrame, period: int = 34) -> float:
    """میانهٔ ATR بر حسب pip طلا (pip=0.10$)."""
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period).mean().values
    med = np.nanmedian(atr)
    return med / 0.10  # pip طلا = 0.10 دلار


def event_cross(x: np.ndarray, thr: float):
    """سیگنال رویدادی: لحظهٔ عبور (نه وضعیت). up: از زیرِ +thr به بالای آن؛ dn: قرینه."""
    x = np.asarray(x, dtype=float)
    prev = np.roll(x, 1); prev[0] = np.nan
    up = (prev < thr) & (x >= thr)
    dn = (prev > -thr) & (x <= -thr)
    up &= np.isfinite(prev); dn &= np.isfinite(prev)
    return up, dn


def run_config(df, ind_vals, thr, mode, sl_atr, tp_atr, atr_pip, max_hold):
    up, dn = event_cross(ind_vals, thr)
    if mode == 'continuation':
        long_sig, short_sig = up, dn
    else:  # reversion
        long_sig, short_sig = dn, up
    sl_pip = round(sl_atr * atr_pip, 1)
    tp_pip = round(tp_atr * atr_pip, 1)
    if sl_pip <= 0:
        return None
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset=ASSET, max_hold=max_hold, allow_overlap=False)
    n = len(tr)
    if n < 30:
        return dict(n=n, wr=np.nan, be=np.nan, lift=np.nan, z=np.nan,
                    sl_pip=sl_pip, tp_pip=tp_pip, net_pip=np.nan)
    wins = (tr['pnl_pip'] > 0).sum()
    wr = wins / n
    # نقطهٔ سربه‌سر با هزینه (اسپرد در pnl لحاظ شده؛ سربه‌سر هندسی خام):
    be = sl_pip / (sl_pip + tp_pip)
    lift = (wr - be) * 100.0
    z = (wr - be) * np.sqrt(n) / np.sqrt(be * (1 - be))
    return dict(n=int(n), wr=round(wr * 100, 2), be=round(be * 100, 2),
                lift=round(lift, 2), z=round(z, 2),
                sl_pip=sl_pip, tp_pip=tp_pip,
                net_pip=round(float(tr['pnl_pip'].sum()), 1))


def main():
    rows = []
    for tf in EXPLORE_TFS:
        d = fd.load_fast(ASSET, tf)
        df_full = fd.as_dataframe(d)
        # ⚠️ فقط نیمهٔ اول — قانون مسیر C
        mask = df_full['time'].values < SPLIT_EPOCH
        df = df_full.loc[mask].reset_index(drop=True)
        print(f'[{tf}] first-half bars={len(df)}  src={d["src"]}', flush=True)
        ap = atr_pips(df)
        max_hold = fd.hold_bars_for(tf, 48)  # ۴۸ ساعت نگهداری حداکثری
        ind_cache = {name: np.asarray(ib.compute(name, df), dtype=float)
                     for name in INDICATORS}
        for name in INDICATORS:
            for thr in THRESHOLDS:
                for mode in MODES:
                    for sl_atr, tp_atr in GEOMS:
                        r = run_config(df, ind_cache[name], thr, mode,
                                       sl_atr, tp_atr, ap, max_hold)
                        if r is None:
                            continue
                        r.update(tf=tf, ind=name, thr=thr, mode=mode,
                                 sl_atr=sl_atr, tp_atr=tp_atr)
                        rows.append(r)
        print(f'[{tf}] done ({len(rows)} rows total)', flush=True)

    out = pd.DataFrame(rows)
    out_path = os.path.join(OUT_DIR, 'explore_first_half.csv')
    out.to_csv(out_path, index=False)
    n_cfg = len(INDICATORS) * len(THRESHOLDS) * len(MODES) * len(GEOMS) * len(EXPLORE_TFS)
    print(f'\n=== total configs explored (first half only): {n_cfg} ===')
    ok = out.dropna(subset=['z']).sort_values('z', ascending=False)
    print(ok.head(25).to_string(index=False))
    print(f'\nsaved -> {out_path}')


if __name__ == '__main__':
    t0 = time.time()
    main()
    print(f'elapsed: {time.time()-t0:.1f}s')
