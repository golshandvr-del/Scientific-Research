# -*- coding: utf-8 -*-
"""
S333 — ممیزیِ همپوشانی با لایه‌های موجود (قانونِ اجباریِ همپوشانی)
================================================================================
لایهٔ جدید (S333): Mean-Reversion SHORT با z-score(34)>2.4 + RSI>70 + شمعِ نزولی،
  گیتِ رژیمِ hurst<0.5 و kurt<1.8، SL110/TP125 — روی XAUUSD M5 (RQS+ 81.6).

نزدیک‌ترین لایهٔ موجودِ هم‌دارایی/هم‌TF/هم‌جهت: S328 (RSI-21 Fade SHORT, XAU M5, RQS 94.2).
  چون هر دو «fade اشباعِ خرید ⇒ SHORT» روی XAU-M5‌اند، بیشترین ریسکِ همپوشانی با S328 است.

هدف (شبیه‌سازِ رویداد-محورِ استانداردِ پروژه):
  ۱) بازتولیدِ سیگنال‌های هر دو لایه با کانفیگِ نهاییِ قفل‌شده.
  ۲) اندازه‌گیریِ همپوشانیِ زمانیِ *بازه‌های معامله* (نه فقط کندلِ سیگنال):
       overlap% = |بازه‌های S333 که با هر بازهٔ S328 تقاطع دارند| / |کلِ بازه‌های S333|
  ۳) طبق بندِ ۳ قانونِ همپوشانی: بررسیِ استفاده از بخشِ همپوشان به‌عنوان فیلتر:
       آیا حذفِ بازه‌های همپوشانِ S333 با S328، RQS+ را بهبود می‌دهد؟
       آیا هم‌پوشانیِ S328 می‌تواند S333 را تقویت کند (هم‌جهت = تأییدِ متقابل)؟

خروجی: results/_s333_overlap_audit.json
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib
from strategies.s328_rsi21_mr_regime_revival import build_signals as s328_build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rsi_np(x, p=14):
    d = np.diff(x, prepend=x[0]); g = np.where(d > 0, d, 0.0); l = np.where(d < 0, -d, 0.0)
    ag = pd.Series(g).ewm(alpha=1/p, adjust=False).mean().values
    al = pd.Series(l).ewm(alpha=1/p, adjust=False).mean().values
    rs = ag / np.where(al == 0, np.nan, al)
    return 100 - 100/(1 + rs)


def s333_short_signal(df, z_win=34, z_thr=2.4, rsi_thr=70, h_thr=0.5, k_thr=1.8):
    """سیگنالِ SHORTِ نهاییِ S333 (کانفیگِ قفل‌شدهٔ XAU-M5)."""
    c = df['close'].values.astype(float); o = df['open'].values.astype(float)
    ma = pd.Series(c).rolling(z_win).mean().values
    sd = pd.Series(c).rolling(z_win).std().values
    z = (c - ma) / np.where(sd == 0, np.nan, sd)
    r = rsi_np(c, 14)
    bear_candle = (c < o) & (c < np.roll(c, 1))
    base = (z > z_thr) & (r > rsi_thr) & bear_candle
    hurst = np.nan_to_num(pd.Series(ib.compute('hurst', df)).values, nan=1.0)
    kurt = np.nan_to_num(pd.Series(ib.compute('kurt', df)).values, nan=99.0)
    sig = base & (hurst < h_thr) & (kurt < k_thr)
    return np.nan_to_num(sig, nan=0).astype(bool)


def intervals_from_signal(sig, max_hold):
    """هر سیگنال ⇒ بازهٔ [i, i+max_hold] (تقریبِ محافظه‌کارانهٔ طولِ نگه‌داری)."""
    idx = np.where(sig)[0]
    return [(i, i + max_hold) for i in idx]


def overlap_pct(iv_a, iv_b):
    """درصدِ بازه‌های A که با حداقل یک بازهٔ B تقاطع دارند."""
    if not iv_a:
        return 0.0, 0
    b_sorted = sorted(iv_b)
    b_starts = np.array([s for s, _ in b_sorted])
    b_ends = np.array([e for _, e in b_sorted])
    hit = 0
    for (s, e) in iv_a:
        # تقاطع اگر وجود بازه‌ای در B که s<=e_b و e>=s_b
        cross = np.any((b_starts <= e) & (b_ends >= s))
        if cross:
            hit += 1
    return 100.0 * hit / len(iv_a), hit


def main():
    asset, tf = 'XAUUSD', 'M5'
    path = os.path.join(ROOT, 'data', f'{asset}_{tf}.csv')
    df = pd.read_csv(path); df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.reset_index(drop=True)
    print(f"# داده: {len(df)} کندلِ {asset}_{tf}\n")

    # --- سیگنالِ S333 (SHORT) ---
    s333_sig = s333_short_signal(df)
    n333 = int(s333_sig.sum())

    # --- سیگنالِ S328 (SHORT) با کانفیگِ نهاییِ XAU-M5: rsi21, hi=75, adx_max=30 ---
    _, s328_sig = s328_build(df, rsi_period=21, lo=25, hi=75, adx_max=30)
    s328_sig = np.asarray(s328_sig, dtype=bool)
    n328 = int(s328_sig.sum())

    print(f"S333 سیگنالِ SHORT: n={n333}")
    print(f"S328 سیگنالِ SHORT: n={n328}")

    # --- همپوشانیِ بازه‌ای (S333 max_hold=20 ، S328 max_hold=24) ---
    iv333 = intervals_from_signal(s333_sig, 20)
    iv328 = intervals_from_signal(s328_sig, 24)
    ov_pct, ov_hit = overlap_pct(iv333, iv328)
    print(f"\n>>> همپوشانیِ زمانیِ بازه‌ها: {ov_hit}/{len(iv333)} = {ov_pct:.1f}% از بازه‌های S333 با S328 تقاطع دارند.")

    # همپوشانیِ کندلِ دقیق (سیگنالِ همزمان روی همان کندل)
    same_candle = int((s333_sig & s328_sig).sum())
    print(f">>> سیگنالِ همزمان روی همان کندل: {same_candle}")

    # --- بندِ ۳: بررسیِ استفاده از همپوشان به‌عنوان فیلتر ---
    # حالت الف: حذفِ بازه‌های S333 که با S328 همپوشان‌اند (آیا RQS بهتر می‌شود؟)
    empty = np.zeros(len(df), bool)
    tr_full = se.simulate_trades(df, empty, s333_sig, 110, 125, asset, max_hold=20, allow_overlap=False)
    r_full = rqs.compute_rqs(tr_full, asset, sl_pip=110, tp_pip=125)
    print(f"\nS333 کامل: RQS={r_full['rqs_score']} WR={r_full['metrics']['win_rate']}% n={r_full['metrics']['n_trades']}")

    # ماسکِ سیگنال‌های S333 که با S328 تقاطع ندارند (بخشِ ناهمپوشان)
    b_sorted = sorted(iv328)
    b_starts = np.array([s for s, _ in b_sorted]) if b_sorted else np.array([])
    b_ends = np.array([e for _, e in b_sorted]) if b_sorted else np.array([])
    idx333 = np.where(s333_sig)[0]
    keep_nonoverlap = np.zeros(len(df), bool)
    keep_overlap = np.zeros(len(df), bool)
    for i in idx333:
        s, e = i, i + 20
        cross = (len(b_starts) > 0) and np.any((b_starts <= e) & (b_ends >= s))
        if cross:
            keep_overlap[i] = True
        else:
            keep_nonoverlap[i] = True

    result = dict(asset=asset, tf=tf, n_s333=n333, n_s328=n328,
                  overlap_pct=round(ov_pct, 1), overlap_hits=ov_hit,
                  same_candle=same_candle,
                  rqs_full=r_full['rqs_score'],
                  wr_full=r_full['metrics']['win_rate'])

    if keep_nonoverlap.sum() >= 20:
        tr_no = se.simulate_trades(df, empty, keep_nonoverlap, 110, 125, asset, max_hold=20, allow_overlap=False)
        r_no = rqs.compute_rqs(tr_no, asset, sl_pip=110, tp_pip=125)
        print(f"S333 بدونِ بازه‌های همپوشان: RQS={r_no['rqs_score']} WR={r_no['metrics']['win_rate']}% n={r_no['metrics']['n_trades']}")
        result['rqs_nonoverlap'] = r_no['rqs_score']
        result['wr_nonoverlap'] = r_no['metrics']['win_rate']
    else:
        print(f"بخشِ ناهمپوشان n={int(keep_nonoverlap.sum())} < 20 — تستِ جدا بی‌معنا.")
        result['rqs_nonoverlap'] = None

    out_path = os.path.join(ROOT, 'results', '_s333_overlap_audit.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n✅ ذخیره: results/_s333_overlap_audit.json")


if __name__ == '__main__':
    main()
