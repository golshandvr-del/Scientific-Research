# -*- coding: utf-8 -*-
"""S940 — «چرخشِ چرخهٔ اِلرز» (Ehlers Cycle-Turn) — خانوادهٔ پیش‌ثبت‌شده.

پیش‌ثبت: results/S940_PREREG_multiplicity_route.md (کامیتِ 5c8c7ab9، پیش از
هر بک‌تستی). هیچ عددی در این فایل پس از دیدنِ داده انتخاب نشده است.

═══════════════════════════════════════════════════════════════════════════
فرضیهٔ اقتصادی
═══════════════════════════════════════════════════════════════════════════
قیمت هم‌نهشتِ دانشِ پراکندهٔ دو جمعیت است: روندروها (دیر) و میانگین‌گراها
(زود). میانِ این دو، مؤلفهٔ چرخه‌ایِ میان‌باندی می‌ماند. فیلترهای الرز
(high-pass + SuperSmoother دوقطبی Butterworth) برای جداسازیِ همین باند
طراحی شده‌اند. رویداد = عبورِ آشکارساز از صفر. cross، نه state — الگوی S382.

═══════════════════════════════════════════════════════════════════════════
خانوادهٔ منجمد (۶ عضو — از prereg، تغییرناپذیر)
═══════════════════════════════════════════════════════════════════════════
  آشکارساز ∈ {reflex, trendflex} × period ∈ {21, 34, 55}
  آستانه = صفر (ساختاری) · سمت = both · SL = 1.5×median(ATR(100)) هر کارت
  RR = 1.5 (TP>SL — قانونِ حفظِ بودجه) · ورود = closeِ کندلِ سیگنال
  صفِ تک‌معاملهٔ سراسری روی کلِ خانواده · اولویتِ SL در کندلِ مبهم
  آماره = معاملاتِ ادغام‌شدهٔ خانواده (نه بهترین عضو) · n_trials = 19

═══════════════════════════════════════════════════════════════════════════
چرا پیاده‌سازیِ برداری/numba و نه حلقهٔ بانک
═══════════════════════════════════════════════════════════════════════════
حلقهٔ بانک O(n×period) است — روی M1 (۵M کندل) ساعت‌ها. ریاضیِ الرز فرمِ
بسته دارد:
  trendflex: s[i] = ssf[i] − mean(ssf[i−1..i−period])
  reflex:    s[i] = ssf[i] + slope·(period+1)/2 − mean(...)،
             slope = (ssf[i−period] − ssf[i])/period
  خروجی:    s / sqrt(EWM(s², α=0.04))
برابریِ عددی با بانک در `verify_indicators()` اثبات می‌شود (همان ریاضی).
شبیه‌سازِ صف نیز مقابلِ شبیه‌سازِ پایتونیِ S382 روی دادهٔ **مصنوعی**
راستی‌آزمایی می‌شود (`verify_simulator()`) — تا هیچ نگاهِ پیش‌رسی به دادهٔ
واقعی نشود.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from numba import njit

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2 as R                     # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

# ── ثابت‌های منجمدِ prereg ────────────────────────────────────────────────
ASSET = 'XAUUSD'
DETECTORS = ('reflex', 'trendflex')
PERIODS = (21, 34, 55)          # فیبوناچی — قانونِ ضدِ گریدِ رند
ATR_P = 100
SL_K = 1.5
RR = 1.5                        # TP = 1.5×SL  (TP > SL)
N_TRIALS = 19                   # ۱۹ کارتِ طلا — یک آزمونِ خانواده per کارت
SPLIT_FRAC = 0.70
SEED = 20260814
OUT = 'results/_s940'
WARMUP = max(4 * max(PERIODS), 250)   # 220→250


def pip_size(asset: str) -> float:
    return 0.1 if asset.startswith('XAU') else 0.0001


# ═══════════════════════════════════════════════════════════════════════
# اندیکاتورها — numba، هم‌ارزِ عددیِ بانک
# ═══════════════════════════════════════════════════════════════════════
@njit(cache=True)
def _ssf_nb(xv, period):
    """SuperSmoother دوقطبی — عینِ _ssf_arr بانک."""
    n = xv.shape[0]
    out = np.empty(n)
    a = np.exp(-1.414 * np.pi / period)
    b = 2.0 * a * np.cos(1.414 * np.pi / period)
    c2 = b
    c3 = -a * a
    c1 = 1.0 - c2 - c3
    for i in range(n):
        if i < 2:
            out[i] = xv[i]
        else:
            out[i] = c1 * (xv[i] + xv[i - 1]) / 2.0 + c2 * out[i - 1] + c3 * out[i - 2]
    return out


@njit(cache=True)
def _flex_nb(xv, period, trend):
    """reflex/trendflex — فرمِ بستهٔ همان حلقهٔ بانک (O(n))."""
    n = xv.shape[0]
    ssf = _ssf_nb(xv, period / 2.0)
    out = np.zeros(n)
    ms = 0.0
    inv_p = 1.0 / period
    for i in range(period, n):
        # sum_{k=1..p} ssf[i-k]
        acc = 0.0
        for k in range(1, period + 1):
            acc += ssf[i - k]
        m = acc * inv_p
        if trend:
            s = ssf[i] - m
        else:
            slope = (ssf[i - period] - ssf[i]) * inv_p
            s = ssf[i] + slope * (period + 1) * 0.5 - m
        ms = 0.04 * s * s + 0.96 * ms
        out[i] = s / np.sqrt(ms) if ms > 0.0 else 0.0
    return out
# نکته: حلقهٔ داخلیِ acc را عمداً نگه داشتم تا **بیت‌به‌بیت** با بانک یکی
# باشد (ترتیبِ جمعِ اعشاری). numba همین حلقه را هم ~۱۰۰× سریع می‌کند؛
# O(n×55) روی 5M ≈ 275M عمل ≈ <1s در numba.


def atr_rma(high, low, close, p=ATR_P):
    """ATR با RMA (ewm alpha=1/p) — عینِ S382."""
    pc = np.empty_like(close)
    pc[0] = np.nan
    pc[1:] = close[:-1]
    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - pc), np.abs(low - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


# ═══════════════════════════════════════════════════════════════════════
# سیگنالِ خانواده — رویدادِ عبور از صفر، ادغامِ ۶ عضو
# ═══════════════════════════════════════════════════════════════════════
def family_dir(close: np.ndarray) -> np.ndarray:
    """آرایهٔ جهت: +1 long، −1 short، 0 هیچ/تعارض.

    قاعدهٔ تعارض (قطعی و محافظه‌کار): اگر در یک کندل هم رویدادِ long و هم
    short از اعضای مختلف برسد، ورود نمی‌کنیم — انتسابِ جهت به چنین کندلی
    یک فرضِ اندازه‌گیری‌نشده می‌بود.
    """
    n = close.shape[0]
    long_any = np.zeros(n, dtype=np.bool_)
    short_any = np.zeros(n, dtype=np.bool_)
    for det in DETECTORS:
        trend = det == 'trendflex'
        for p in PERIODS:
            x = _flex_nb(close, p, trend)
            prev = np.empty(n)
            prev[0] = 0.0
            prev[1:] = x[:-1]
            long_any |= (prev <= 0.0) & (x > 0.0)
            short_any |= (prev >= 0.0) & (x < 0.0)
    long_any[:WARMUP] = False
    short_any[:WARMUP] = False
    d = np.zeros(n, dtype=np.int8)
    d[long_any & ~short_any] = 1
    d[short_any & ~long_any] = -1
    return d


# ═══════════════════════════════════════════════════════════════════════
# شبیه‌سازِ صفِ تک‌معامله — numba؛ همان سه انتخابِ محافظه‌کارِ S382
#   ۱) قیدِ عدمِ هم‌پوشانیِ سراسری  ۲) اولویتِ SL در کندلِ مبهم
#   ۳) حذفِ معاملهٔ بازِ پایانِ داده
# ═══════════════════════════════════════════════════════════════════════
@njit(cache=True)
def _sim_queue_nb(high, low, close, dirs, sl_abs, tp_abs):
    n = close.shape[0]
    max_tr = n // 2 + 4
    e_bar = np.empty(max_tr, dtype=np.int64)
    x_bar = np.empty(max_tr, dtype=np.int64)
    tdir = np.empty(max_tr, dtype=np.int8)
    won = np.empty(max_tr, dtype=np.bool_)
    m = 0
    i = 0
    while i < n - 1:
        d = dirs[i]
        if d == 0:
            i += 1
            continue
        entry = close[i]
        if d == 1:
            sl_lvl = entry - sl_abs
            tp_lvl = entry + tp_abs
        else:
            sl_lvl = entry + sl_abs
            tp_lvl = entry - tp_abs
        j = i + 1
        res = 0  # 0=open, -1=loss, +1=win
        while j < n:
            if d == 1:
                hit_sl = low[j] <= sl_lvl
                hit_tp = high[j] >= tp_lvl
            else:
                hit_sl = high[j] >= sl_lvl
                hit_tp = low[j] <= tp_lvl
            if hit_sl:          # اولویتِ SL در کندلِ مبهم
                res = -1
                break
            if hit_tp:
                res = 1
                break
            j += 1
        if res == 0:            # معاملهٔ بازِ پایانِ داده — حذف
            break
        e_bar[m] = i
        x_bar[m] = j
        tdir[m] = d
        won[m] = res == 1
        m += 1
        i = j + 1               # صف: تا خروج، هیچ ورودِ تازه‌ای نیست
    return e_bar[:m], x_bar[:m], tdir[:m], won[:m]


def sim_queue(high, low, close, dirs, sl_abs, ps) -> pd.DataFrame:
    e, x, d, w = _sim_queue_nb(high, low, close, dirs, sl_abs, sl_abs * RR)
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * RR
    return pd.DataFrame(dict(
        entry_bar=e, exit_bar=x,
        outcome=np.where(w, 'win', 'loss'),
        pnl_pip=np.where(w, tp_pip, -sl_pip),
        sl_pip=sl_pip, tp_pip=tp_pip,
        direction=np.where(d == 1, 'long', 'short')))


@njit(cache=True)
def _wr_only_nb(high, low, close, dirs, sl_abs, tp_abs):
    """فقط WR — برای مدلِ صفر (بدونِ ساختِ DataFrame؛ K×۲ بار صدا می‌شود)."""
    e, x, d, w = _sim_queue_nb(high, low, close, dirs, sl_abs, tp_abs)
    m = w.shape[0]
    if m == 0:
        return -1.0, 0
    wins = 0
    for k in range(m):
        if w[k]:
            wins += 1
    return 100.0 * wins / m, m


# ═══════════════════════════════════════════════════════════════════════
# مدلِ صفرِ اندازه‌گیری‌شده — دو خطِ مبنا، به تفکیکِ سمت (الگوی S382/S351)
# ═══════════════════════════════════════════════════════════════════════
def build_null(high, low, close, sl_abs, n_long, n_short, n_bars,
               k_perm, strides, rng, verbose=True):
    tp_abs = sl_abs * RR
    lo, hi = WARMUP, n_bars - 2
    # حداقلِ معامله per قرعه: روی کارت‌های ریز (W1: ۸۱۳ کندل) قرعه‌ها
    # ساختاراً <۳۰ معامله می‌دهند و فیلترِ سختِ ۳۰ همه را حذف می‌کرد ⇒
    # perm_k=None ⇒ کرَشِ blend_null. این آستانه کیفیتِ قرعه است نه سدِ
    # معناداری؛ K≥500ِ prereg دست‌نخورده می‌ماند.
    m_min = 30 if n_bars >= 5000 else 5
    null = {}
    for side, sgn, n_side in (('long', 1, n_long), ('short', -1, n_short)):
        # سقفِ فیزیکی: هر قرعه حداکثر n_side معامله می‌دهد؛ اگر m_min > n_side
        # همهٔ قرعه‌ها حذف و perm_k=None ⇒ کرَشِ blend_null (دیده‌شده در W1ِ
        # S943 با n_long=3). آستانهٔ مؤثرِ این سمت را به n_side محدود می‌کنیم.
        m_min_side = max(1, min(m_min, n_side))
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1:
            # ① خریدارِ/فروشندهٔ کور — سخت‌ترین stride
            best = None
            for st in strides:
                dirs = np.zeros(n_bars, dtype=np.int8)
                dirs[lo:hi:st] = sgn
                wr, m = _wr_only_nb(high, low, close, dirs, sl_abs, tp_abs)
                if m >= m_min_side and (best is None or wr > best):
                    best = wr
                if verbose:
                    print(f'      uncond {side} stride={st}: wr={wr:.2f}% n={m}',
                          flush=True)
            d['uncond_wr'] = best
            # ② جای‌گشتِ زمانی — همان تعدادِ رویداد، K≥500
            pool = np.arange(lo, hi)
            wrs = []
            for _ in range(k_perm):
                pos = rng.choice(pool, size=min(n_side, len(pool)),
                                 replace=False)
                dirs = np.zeros(n_bars, dtype=np.int8)
                dirs[np.sort(pos)] = sgn
                wr, m = _wr_only_nb(high, low, close, dirs, sl_abs, tp_abs)
                if m >= m_min_side:
                    wrs.append(wr)
            if wrs:
                a = np.asarray(wrs, float)
                d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                         perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        if verbose:
            print(f'      null {side:<5} uncond={d["uncond_wr"]} '
                  f'perm_mean={d["perm_mean"]} sd={d["perm_sd"]} '
                  f'k={d["perm_k"]}', flush=True)
    return null


# ═══════════════════════════════════════════════════════════════════════
# راستی‌آزمایی‌ها — پیش از هر آزمونِ واقعی
# ═══════════════════════════════════════════════════════════════════════
def verify_indicators(n=4000, seed=7) -> float:
    """برابریِ عددی نسخهٔ numba با بانک روی گشتِ تصادفی (نه دادهٔ واقعی)."""
    from engine import indicator_bank as ib
    rng = np.random.default_rng(seed)
    xv = 2000.0 + np.cumsum(rng.normal(0, 1.0, n))
    df = pd.DataFrame(dict(open=xv, high=xv, low=xv, close=xv))
    worst = 0.0
    for det, fn in (('reflex', False), ('trendflex', True)):
        for p in PERIODS:
            a = ib.compute(det, df) if p == 20 else \
                (ib.reflex(df, p) if det == 'reflex' else ib.trendflex(df, p))
            b = _flex_nb(xv, p, fn)
            diff = float(np.nanmax(np.abs(a.to_numpy() - b)))
            worst = max(worst, diff)
    return worst


def verify_simulator(n=6000, seed=11) -> dict:
    """هم‌ارزیِ شبیه‌سازِ numba با شبیه‌سازِ پایتونیِ S382 روی دادهٔ مصنوعی.

    S382 تک‌سمته است؛ پس مقایسه با dirsِ فقط-long انجام می‌شود.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        '_s382', os.path.join(ROOT, 'strategies', 's382_williamsr_momentum.py'))
    s382 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s382)

    rng = np.random.default_rng(seed)
    c = 2000.0 + np.cumsum(rng.normal(0, 2.0, n))
    spread_hl = np.abs(rng.normal(0, 1.5, n))
    h = c + spread_hl
    l = c - spread_hl
    df = pd.DataFrame(dict(open=c, high=h, low=l, close=c))
    sig = pd.Series(False, index=df.index)
    pos = rng.choice(np.arange(300, n - 2), size=400, replace=False)
    sig.iloc[np.sort(pos)] = True
    sl_abs = 6.0
    ps = 0.1
    tr_ref = s382.simulate_trades(df, sig, sl_abs, RR, True, ps)

    dirs = np.zeros(n, dtype=np.int8)
    dirs[np.sort(pos)] = 1
    tr_new = sim_queue(h, l, c, dirs, sl_abs, ps)
    same_n = len(tr_ref) == len(tr_new)
    same_out = same_n and bool(
        (tr_ref['outcome'].to_numpy() == tr_new['outcome'].to_numpy()).all()
        and (tr_ref['entry_bar'].to_numpy() == tr_new['entry_bar'].to_numpy()).all()
        and (tr_ref['exit_bar'].to_numpy() == tr_new['exit_bar'].to_numpy()).all())
    return dict(n_ref=len(tr_ref), n_new=len(tr_new), identical=same_out)


# ═══════════════════════════════════════════════════════════════════════
# اجرای یک کارت — کاملِ prereg
# ═══════════════════════════════════════════════════════════════════════
def run_card(tf: str, verbose=True) -> dict:
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, tf)
    n_bars = int(d['n_bars'])
    high, low, close = d['high'], d['low'], d['close']
    bar_time = d['time']
    ps = pip_size(ASSET)

    print(f"\n{'='*84}\n=== S940 EhlersCycleTurn :: {ASSET}_{tf}  "
          f"bars={n_bars:,}  span={d['span_years']}y\n"
          f"    src={d['src']}  ({d['first_utc']} → {d['last_utc']})", flush=True)

    if n_bars < WARMUP + 200:
        out = dict(card=f'{ASSET}_{tf}', verdict='TOO_SHORT', bars=n_bars)
        _save(tf, out)
        return out

    atr = atr_rma(high, low, close)
    sl_abs = float(np.nanmedian(atr)) * SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * RR
    print(f'    geom: SL={sl_pip:.2f}pip  TP={tp_pip:.2f}pip  rr={RR}  '
          f'(median ATR({ATR_P})×{SL_K})', flush=True)

    dirs = family_dir(close)
    nL_sig = int((dirs == 1).sum())
    nS_sig = int((dirs == -1).sum())
    print(f'    family events: long={nL_sig:,}  short={nS_sig:,}', flush=True)

    tr = sim_queue(high, low, close, dirs, sl_abs, ps)
    if len(tr) < 5:
        out = dict(card=f'{ASSET}_{tf}', verdict='NO_TRADES', bars=n_bars,
                   n_trades=int(len(tr)))
        _save(tf, out)
        return out
    nL = int((tr['direction'] == 'long').sum())
    nS = int((tr['direction'] == 'short').sum())
    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f'    trades={len(tr):,} (L={nL:,} S={nS:,})  wr={wr:.2f}%', flush=True)

    # مدلِ صفر — K و strideها تابعِ حجم (prereg §۴)
    k_perm = 500 if n_bars > 1_500_000 else 1000
    strides = (7, 21) if n_bars > 1_000_000 else (3, 7, 13)
    rng = np.random.default_rng(SEED)
    print(f'    building null: K={k_perm}  strides={strides}  seed={SEED}',
          flush=True)
    null = build_null(high, low, close, sl_abs, nL, nS, n_bars,
                      k_perm, strides, rng, verbose=verbose)

    split_bar = int(SPLIT_FRAC * n_bars)
    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=bar_time, close=close, null=null,
                         n_trials=N_TRIALS, split_bar=split_bar)
    print()
    print(R.format_rqs2(f'S940_EhlersCycleTurn_{ASSET}_{tf}', res), flush=True)

    payload = dict(card=f'{ASSET}_{tf}', src=d['src'],
                   first_utc=d['first_utc'], last_utc=d['last_utc'],
                   span_years=d['span_years'], bars=n_bars,
                   sl_pip=sl_pip, tp_pip=tp_pip, rr=RR,
                   events_long=nL_sig, events_short=nS_sig,
                   n_trades=int(len(tr)), n_long=nL, n_short=nS, wr=wr,
                   null=null, k_perm=k_perm, seed=SEED, rqs2=res)
    _save(tf, payload)
    tr.to_csv(f'{OUT}/{ASSET}_{tf}_trades.csv', index=False)
    return payload


def _save(tf, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/{ASSET}_{tf}_rqs2.json', 'w') as f:
        json.dump(obj, f, ensure_ascii=False, default=str)


if __name__ == '__main__':
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M1'
    run_card(tf)
