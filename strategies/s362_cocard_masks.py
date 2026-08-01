# -*- coding: utf-8 -*-
"""
S362-MASKS — بازتولیدِ **دقیقِ** لایه‌های هم‌کارتِ S341 به‌صورتِ ماسکِ بولیِ برداری.

هدف: گامِ ۳ت سندِ `results/S362_PREREGISTRATION_S341_OVERLAP_AS_FILTER.md`.

⚠️ **چرا این ماژول از صفر نوشته شد و هستهٔ پایتونیِ موجود استفاده نشد.**
پیش‌ثبتِ S362 (بندِ ۳) شرط گذاشت که هر منبعِ فیلتر باید «هستهٔ دقیق» **و**
«پیکربندیِ مستقرشده» داشته باشد. هنگامِ پیاده‌سازی کشف شد که این شرط برای دو لایه
**برقرار نیست**:

* `strategies/s333_brooks_regime_filter.brooks_high2_signal(df, ema_fast=20,
  ema_slow=50)` یک ماشهٔ «High-2»ِ Brooks است، ولی لایهٔ **مستقرِ** S333 در
  `web_tool/src/s333_pullback.ts` چیزِ دیگری است: `EMA20 > EMA100` + `RSI21`
  با سه حالتِ تأیید + گیتِ `hurst(64)` + گیتِ اختیاریِ `er_lucas_29`.
* `strategies/s335_macd_momentum_short_scalp.long_signal(df, trend_gate, warmup)`
  یک اسکالپِ MACD است، ولی لایهٔ **مستقرِ** S335 در
  `web_tool/src/s335_reflex_cycle.ts` چرخهٔ `reflex/trendflex/hurst` است.

اگر آن دو تابع را «همان لایه» فرض می‌کردم، فیلترِ آزموده‌شده **لایهٔ روی سایت
نبود** و کلِ گامِ ۳ت بی‌اعتبار می‌شد — و بدتر: یک خطای نوعِ دوم می‌ساخت که در
گزارشِ نهایی به‌صورتِ «همپوشانی کمکی نکرد» ظاهر می‌شد. بنابراین هر چهار لایه
**از منبعِ TSِ مستقر** به پایتون برگردانده شدند، و برابری با همان TS در
`strategies/s362_parity_masks.mjs` **عددی اثبات** می‌شود، نه ادعا.

پارامترها **عیناً** از `*_CFG`ِ همان فایل‌های TS نقل شده‌اند؛ هیچ پارامترِ جدیدی
اینجا انتخاب نمی‌شود (الزامِ بندِ ۳ پیش‌ثبت).
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import indicator_bank as ib                                  # noqa: E402

# ═════════════════ پیکربندی‌های مستقر، عیناً از فایل‌های TS ═════════════════
# streak_reversal_s326.ts :: STREAK_REV_CFG
S326_CFG = {
    'XAUUSD-M5':  dict(streakN=5, rsiMax=30, emaTrend=200, runMinAtr=0.0, atrP=14),
    'XAUUSD-M30': dict(streakN=5, rsiMax=30, emaTrend=200, runMinAtr=2.5, atrP=14),
    'EURUSD-M15': dict(streakN=4, rsiMax=30, emaTrend=200, runMinAtr=0.0, atrP=14),
}

# sell_climax_s327.ts :: SELL_CLIMAX_CFG
S327_CFG = {
    'XAUUSD-M5':  dict(kBody=1.6, brMin=0.60, streakN=2, rsiMax=30, emaTrend=200,
                       atrP=14, bodyMaLen=20),
    'XAUUSD-M15': dict(kBody=2.5, brMin=0.45, streakN=3, rsiMax=35, emaTrend=200,
                       atrP=14, bodyMaLen=20),
    'XAUUSD-M30': dict(kBody=2.5, brMin=0.45, streakN=2, rsiMax=35, emaTrend=200,
                       atrP=14, bodyMaLen=20),
    'XAUUSD-H1':  dict(kBody=1.6, brMin=0.60, streakN=3, rsiMax=42, emaTrend=200,
                       atrP=14, bodyMaLen=20),
    'XAUUSD-H4':  dict(kBody=2.5, brMin=0.60, streakN=0, rsiMax=35, emaTrend=200,
                       atrP=14, bodyMaLen=20),
    'EURUSD-M30': dict(kBody=1.6, brMin=0.60, streakN=2, rsiMax=30, emaTrend=200,
                       atrP=14, bodyMaLen=20),
}

# s333_pullback.ts :: S333_CFG   (erTh غایب ⇒ گیتِ ER خاموش، عیناً مثلِ TS)
S333_CFG = {
    'XAUUSD-M5':  dict(emaFast=20, emaSlow=100, rsiP=21, rsiTh=35,
                       confirm='rsi_turn',  hurstTh=0.57, erTh=0.25),
    'XAUUSD-M15': dict(emaFast=20, emaSlow=100, rsiP=21, rsiTh=32,
                       confirm='none',      hurstTh=0.57, erTh=None),
    'XAUUSD-M30': dict(emaFast=20, emaSlow=100, rsiP=21, rsiTh=35,
                       confirm='price_turn', hurstTh=0.53, erTh=None),
    'XAUUSD-H1':  dict(emaFast=20, emaSlow=100, rsiP=21, rsiTh=32,
                       confirm='none',      hurstTh=0.50, erTh=0.25),
}

# s335_reflex_cycle.ts :: S335_CFG
S335_CFG = {
    'XAUUSD-M5':  dict(trigger='zero_up', pRf=21, pTf=34, pHu=55, pR2=21, pChop=21,
                       rfDip=1.0, tfMin=0.2, huMin=0.53, r2Min=None, chopMax=38.2),
    'XAUUSD-M15': dict(trigger='dip_turn', pRf=21, pTf=34, pHu=55, pR2=21, pChop=21,
                       rfDip=1.0, tfMin=0.5, huMin=0.50, r2Min=0.55, chopMax=None),
    'XAUUSD-M30': dict(trigger='dip_turn', pRf=21, pTf=34, pHu=55, pR2=21, pChop=21,
                       rfDip=1.0, tfMin=0.5, huMin=0.50, r2Min=None, chopMax=38.2),
    'XAUUSD-H1':  dict(trigger='dip_turn', pRf=21, pTf=34, pHu=55, pR2=21, pChop=21,
                       rfDip=1.0, tfMin=0.5, huMin=0.50, r2Min=None, chopMax=38.2),
}


# ═══════════════════════════ کمکی‌های مشترک ═══════════════════════════
def _down_streak(o, c):
    """طولِ رگهٔ نزولیِ متوالی (`close < open`) که به کندلِ `i` **ختم** می‌شود.

    بازتولیدِ `downStreak` در TS: حلقه از ابتدا، با `run=0` در هر کندلِ غیرنزولی.
    """
    n = len(c)
    out = np.zeros(n, dtype=np.int32)
    run = 0
    for i in range(n):
        run = run + 1 if c[i] < o[i] else 0
        out[i] = run
    return out


def _nan_to_false(x):
    return np.where(np.isfinite(x), x, np.nan)


# ═══════════════════════════ ماسکِ هر لایه ═══════════════════════════
def mask_s326(df, cfg):
    """`active`ِ لایهٔ مستقرِ S326 (streak-reversal) برای **هر** کندل."""
    o = df['open'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(c)
    r = ib.rsi_s(df['close'], 14).to_numpy()
    e = ib.ema_s(df['close'], cfg['emaTrend']).to_numpy()
    a = ib.atr_s(df, cfg['atrP']).to_numpy()
    st = _down_streak(o, c)

    # شتابِ رگه بر ATR: (close[i-streak] − close[i]) / ATR ، نزولی ⇒ مثبت
    idx = np.arange(n) - st
    ok_idx = (st >= 1) & (idx >= 0)
    run_amp = np.zeros(n)
    run_amp[ok_idx] = (c[idx[ok_idx]] - c[ok_idx]) / a[ok_idx]

    finite = np.isfinite(r) & np.isfinite(e) & np.isfinite(a) & (a > 0)
    need = max(cfg['emaTrend'], cfg['atrP']) + cfg['streakN'] + 2
    warm = np.arange(n) >= (need - 1)

    run_ok = True if cfg['runMinAtr'] <= 0 else (run_amp >= cfg['runMinAtr'])
    return (finite & warm & (st >= cfg['streakN']) & (r <= cfg['rsiMax'])
            & (c > e) & run_ok)


def mask_s327(df, cfg):
    """`active`ِ لایهٔ مستقرِ S327 (sell-climax) برای **هر** کندل."""
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(c)
    r = ib.rsi_s(df['close'], 14).to_numpy()
    e = ib.ema_s(df['close'], cfg['emaTrend']).to_numpy()
    a = ib.atr_s(df, cfg['atrP']).to_numpy()

    body = np.abs(c - o)
    rng = np.maximum(h - l, 1e-12)
    br = body / rng
    is_bear = c < o

    # میانگینِ `bodyMaLen`-کندلیِ |body| روی بازهٔ [i-bodyMaLen, i-1] — یعنی
    # shift(1)، بدونِ خودِ کندلِ جاری. گاردِ TS: فقط وقتی i-1 >= bodyMaLen.
    L = cfg['bodyMaLen']
    cs = np.concatenate(([0.0], np.cumsum(body)))
    body_ma = np.full(n, np.nan)
    i0 = L + 1                      # کوچک‌ترین i که i-1 >= L
    if n > i0:
        ii = np.arange(i0, n)
        body_ma[ii] = (cs[ii] - cs[ii - L]) / L

    st = _down_streak(o, c)
    finite = np.isfinite(r) & np.isfinite(e) & np.isfinite(a) & (a > 0)
    need = max(cfg['emaTrend'], cfg['atrP'], cfg['bodyMaLen']) + cfg['streakN'] + 2
    warm = np.arange(n) >= (need - 1)

    body_ok = np.isfinite(body_ma) & (body_ma > 0) & (body >= cfg['kBody'] * body_ma)
    br_ok = True if cfg['brMin'] <= 0 else (br >= cfg['brMin'])
    st_ok = True if cfg['streakN'] <= 0 else (st >= cfg['streakN'])
    return (finite & warm & is_bear & body_ok & br_ok & st_ok
            & (r <= cfg['rsiMax']) & (c > e))


def mask_s333(df, cfg):
    """`active`ِ لایهٔ مستقرِ S333 (pullback-buy در روند) برای **هر** کندل."""
    c = df['close'].to_numpy(float)
    h = df['high'].to_numpy(float)
    n = len(c)
    ef = ib.ema_s(df['close'], cfg['emaFast']).to_numpy()
    es = ib.ema_s(df['close'], cfg['emaSlow']).to_numpy()
    r = ib.rsi_s(df['close'], cfg['rsiP']).to_numpy()
    hu = ib.hurst(df, p=64).to_numpy()

    up = ef > es
    th = cfg['rsiTh']
    r_prev = np.concatenate(([np.nan], r[:-1]))
    h_prev = np.concatenate(([np.nan], h[:-1]))

    if cfg['confirm'] == 'none':
        core = up & (r < th)
    elif cfg['confirm'] == 'rsi_turn':
        core = up & (r_prev < th) & (r > r_prev) & (r < th + 10)
    else:                                          # price_turn
        dipped = (r < th) | (r_prev < th)
        core = up & dipped & (c > h_prev)

    # `nz()`ِ TS مقدارِ NaN را صفر می‌کند ⇒ گیت با آستانهٔ مثبت رد می‌شود.
    hu_ok = np.where(np.isfinite(hu), hu, 0.0) > cfg['hurstTh']
    if cfg['erTh'] is not None:
        er = ib.compute('er_lucas_29', df).to_numpy()
        er_ok = np.where(np.isfinite(er), er, 0.0) > cfg['erTh']
    else:
        er_ok = True

    need = max(cfg['emaSlow'], 64) + 5
    warm = np.arange(n) >= (need - 1)
    return warm & core & hu_ok & er_ok


def mask_s335(df, cfg):
    """`active`ِ لایهٔ مستقرِ S335 (reflex cycle) برای **هر** کندل."""
    n = len(df)
    rf = ib.reflex(df, period=cfg['pRf']).to_numpy()
    tf = ib.trendflex(df, period=cfg['pTf']).to_numpy()
    hu = ib.hurst(df, p=cfg['pHu']).to_numpy()
    rf_prev = np.concatenate(([np.nan], rf[:-1]))

    tf_ok = np.isfinite(tf) & (tf > cfg['tfMin'])
    hu_ok = np.isfinite(hu) & (hu > cfg['huMin'])
    if cfg['r2Min'] is not None:
        r2 = ib.r2(df, p=cfg['pR2']).to_numpy()
        r2_ok = np.isfinite(r2) & (r2 > cfg['r2Min'])
    else:
        r2_ok = True
    if cfg['chopMax'] is not None:
        ch = ib.chop(df, p=cfg['pChop']).to_numpy()
        ch_ok = np.isfinite(ch) & (ch < cfg['chopMax'])
    else:
        ch_ok = True

    fin = np.isfinite(rf) & np.isfinite(rf_prev)
    if cfg['trigger'] == 'zero_up':
        trig = fin & (rf_prev <= 0) & (rf > 0)
    else:                                          # dip_turn
        trig = fin & (rf_prev <= -cfg['rfDip']) & (rf > rf_prev)

    need = max(cfg['pHu'], cfg['pTf'], cfg['pR2'], cfg['pChop']) + 5
    warm = np.arange(n) >= (need - 1)
    return warm & tf_ok & hu_ok & r2_ok & ch_ok & trig


# ═══════════════════ مجموعهٔ منابعِ فیلتر برای یک کارت ═══════════════════
BUILDERS = {'S326': (mask_s326, S326_CFG), 'S327': (mask_s327, S327_CFG),
            'S333': (mask_s333, S333_CFG), 'S335': (mask_s335, S335_CFG)}

# خانوادهٔ منطقی — برای گزارشِ فرضیهٔ دوسویهٔ بندِ ۴ پیش‌ثبت
FAMILY = {'S326': 'reversal', 'S327': 'reversal', 'S333': 'trend', 'S335': 'trend'}


def build_sources(df, card):
    """ماسکِ همهٔ لایه‌های هم‌کارتِ **در دسترس** + دو ترکیبِ تجمعی.

    لایه‌ای که برای این کارت پیکربندیِ مستقر ندارد **حذف نمی‌شود بی‌صدا**؛ در
    کلیدِ `missing` گزارش می‌شود تا پوششِ واقعی در سندِ نهایی قابلِ ممیزی باشد.
    """
    out, missing = {}, []
    for name, (fn, cfgs) in BUILDERS.items():
        cfg = cfgs.get(card)
        if cfg is None:
            missing.append(name)
            continue
        out[name] = fn(df, cfg).astype(bool)
    rev = [out[k] for k in ('S326', 'S327') if k in out]
    trd = [out[k] for k in ('S333', 'S335') if k in out]
    if rev:
        out['ANY_REVERSAL'] = np.logical_or.reduce(rev)
    if trd:
        out['ANY_TREND'] = np.logical_or.reduce(trd)
    return out, missing
