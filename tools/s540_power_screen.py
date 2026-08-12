# -*- coding: utf-8 -*-
"""
s540_power_screen.py — غربالِ توانِ S540: مولدِ منجمدِ S382 روی تایم‌فریم‌های بکر
================================================================================

چرا این ابزار وجود دارد
--------------------------------------------------------------------------------
مأموریتِ S540: قاعدهٔ **منجمدشدهٔ** S382 (WillR(14) گذر به بالای −13 → LONG،
SL=1.5×ATR(100)، TP=1.5×SL) روی تایم‌فریم‌هایی که در تاریخِ پروژه **هرگز**
کارتی نداشته‌اند: H2, H3, H6, H8, H12 — با دادهٔ کاملِ ۱۵.۶سالهٔ mt5_full.

انگیزهٔ ریاضی: جدولِ MTF قبلیِ S382 یک گرادیانِ تمیز نشان می‌دهد —
لیفت در M5..H1 منفی است، در H4 ناگهان +7.83pp و در D1 مثبت ولی کم‌توان.
پس تابعِ «لبه بر حسبِ مقیاسِ زمانی» جایی بینِ H1 و H4 علامت عوض می‌کند و
شکلش فراتر از H4 مجهول است. H2/H3 منطقهٔ گذارند و H6/H8/H12 منطقهٔ فراتر.

سه انتخابِ طراحی (هر یک ضدِ یک خطای شناخته‌شده)
--------------------------------------------------------------------------------
۱. **صفر پارامترِ جدید.** همهٔ ثابت‌ها بی‌کم‌وکاست از strategies/s382 وارد
   می‌شوند (import، نه کپی). اگر اینجا چیزی «تنظیم» شود، n_trials منفجر
   می‌شود و سدِ H5 را خودم بالا برده‌ام — تلهٔ mass-search.

۲. **غربال، نه داور.** K=12 جای‌گشت فقط برای برآوردِ perm_mean کافی است
   (SE ≈ sd/√12). هیچ حکمی از این فایل صادر نمی‌شود؛ هر کارتِ امیدبخش
   بعداً با مدلِ صفرِ کاملِ K≥500 و داورِ rqs2 سنجیده می‌شود.

۳. **ذخیرهٔ افزایشی.** پس از هر کارت، JSON نوشته می‌شود (قانونِ ذخیرهٔ
   افزایشی — سندباکس ناپایدار است). ترتیبِ اجرا از ارزان به گران:
   H12 → H8 → H6 → H3 → H2.

خطِ مبنای دوگانه (وام از tools/s382_null_model.py)
--------------------------------------------------------------------------------
① uncond_wr: ورود در هر کندلِ stride-ام با همان براکت — بتای روندِ طلا.
② perm: همان تعدادِ سیگنال با زمان‌بندیِ تصادفی — نویزِ نمونهٔ محدود.
لیفتِ گزارش‌شده نسبت به **بزرگ‌ترینِ** این دو است (سخت‌ترین رقیبِ بی‌مهارت)،
همان قراردادِ _side_null_ref در rqs2.

فرمولِ توان (docs/TRIAGE_POWER_ALL_LAYERS.md):
    n_needed = n_obs · (z_luck / z_obs)²  با z_luck = 3.09
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import importlib.util
_spec = importlib.util.spec_from_file_location(
    's382', os.path.join(ROOT, 'strategies', 's382_williamsr_momentum.py'))
S382 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S382)

OUT = os.path.join(ROOT, 'results', '_s540_power')
DATA_DIR = 'data/full'          # دادهٔ کاملِ ۱۵.۶ساله — نه data/ کوتاه
# از ارزان به گران — اگر سندباکس ریست شد بیشترین کارتِ ذخیره‌شده بماند
CARDS = ['XAUUSD_H12', 'XAUUSD_H8', 'XAUUSD_H6', 'XAUUSD_H3', 'XAUUSD_H2']
K_SCREEN = 12
SEED = 20260812                 # بذرِ ثابت — بازتولیدپذیری
Z_LUCK = 3.09                   # p_perm ≤ 0.001 یک‌سویه


def load_full(card):
    path = f'{DATA_DIR}/{card}.csv'
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    # گاردِ BUG-DATASETDRIFT — چاپِ مسیر/سطر/بازه در سرِ خروجی
    print(f'[data] {path}  rows={len(df)}  '
          f'range={df["dt"].iloc[0]} .. {df["dt"].iloc[-1]}', flush=True)
    return df


def wr_of(df, sig, sl_abs, ps):
    tr = S382.simulate_trades(df, sig, sl_abs, S382.RR, True, ps)
    if len(tr) == 0:
        return 0.0, 0, tr
    return 100.0 * (tr['outcome'] == 'win').mean(), len(tr), tr


def uncond_baseline(df, sl_abs, ps, stride):
    """ورودِ کور در هر کندلِ stride-ام — بتای روند، نه آلفای لایه."""
    sig = pd.Series(False, index=df.index)
    sig.iloc[np.arange(S382.ATR_P, len(df) - 2, stride)] = True
    wr, n, _ = wr_of(df, sig, sl_abs, ps)
    return wr, n


def perm_baseline(df, sl_abs, ps, n_sig, k, seed):
    """همان تعدادِ سیگنال، زمان‌بندیِ جای‌گشت‌شده."""
    rng = np.random.default_rng(seed)
    lo, hi = S382.ATR_P, len(df) - 2
    wrs = []
    for _ in range(k):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        sig = pd.Series(False, index=df.index)
        sig.iloc[np.sort(pos)] = True
        wr, _, _ = wr_of(df, sig, sl_abs, ps)
        wrs.append(wr)
    return float(np.mean(wrs)), float(np.std(wrs, ddof=1)), float(np.max(wrs))


def screen_card(card):
    t0 = time.time()
    df = load_full(card)
    ps = S382.pip_size('XAUUSD')
    a = S382.atr(df)
    sl_abs = float(np.nanmedian(a.to_numpy())) * S382.SL_K
    sig = S382.signals(df)
    n_sig = int(sig.fillna(False).sum())

    wr, n_tr, tr = wr_of(df, sig, sl_abs, ps)
    span_y = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25

    # خطِ مبنای ①
    stride = max(1, (len(df) - S382.ATR_P) // max(n_sig * 3, 300))
    uwr, un = uncond_baseline(df, sl_abs, ps, stride)
    # خطِ مبنای ②
    pm, psd, pmax = perm_baseline(df, sl_abs, ps, n_sig, K_SCREEN, SEED)

    base = max(uwr, pm)                      # سخت‌ترین رقیب
    lift = wr - base
    # z با p0 = base (تقریبِ دوجمله‌ای — غربال است، نه داور)
    p0 = base / 100.0
    se = (p0 * (1 - p0) / max(n_tr, 1)) ** 0.5 * 100.0
    z = lift / se if se > 0 else 0.0
    n_needed = int(np.ceil(n_tr * (Z_LUCK / z) ** 2)) if z > 0 else -1

    res = dict(card=card, data=f'{DATA_DIR}/{card}.csv', rows=len(df),
               span_years=round(span_y, 2), n_signals=n_sig, n_trades=n_tr,
               per_year=round(n_tr / span_y, 1),
               sl_pip=round(sl_abs / ps, 2), tp_pip=round(sl_abs * S382.RR / ps, 2),
               wr=round(wr, 2), uncond_wr=round(uwr, 2), uncond_n=un,
               perm_mean=round(pm, 2), perm_sd=round(psd, 2),
               perm_max=round(pmax, 2), base=round(base, 2),
               lift=round(lift, 2), z_screen=round(z, 2),
               n_needed_z309=n_needed, k_perm=K_SCREEN, seed=SEED,
               elapsed_s=round(time.time() - t0, 1))
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/{card}.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f'[done] {card}: n={n_tr} wr={wr:.2f} base={base:.2f} '
          f'lift={lift:+.2f}pp z≈{z:.2f} n_needed={n_needed} '
          f'({time.time()-t0:.0f}s)', flush=True)
    return res


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for card in CARDS:
        if only and card not in only:
            continue
        done = f'{OUT}/{card}.json'
        if os.path.exists(done):
            print(f'[skip] {card} — checkpoint exists', flush=True)
            continue
        screen_card(card)


if __name__ == '__main__':
    main()
