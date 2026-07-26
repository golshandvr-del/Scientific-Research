# -*- coding: utf-8 -*-
"""
S328 — ممیزیِ همپوشانی با لایه‌های موجود (قانونِ اجباریِ همپوشانی)
================================================================================
لایهٔ جدید (S328): RSI21 از اشباعِ خرید (>hi) بازگشت ⇒ SHORT-fade، روی XAU M5/H1.
نزدیک‌ترین لایهٔ موجودِ هم‌دارایی/هم‌TF: S327 (Sell-Climax Reversal ⇒ LONG، XAU M5/H1).

هدفِ این اسکریپت (شبیه‌سازِ رویداد-محور):
  ۱) بازتولیدِ سیگنال‌های هر دو لایه با کانفیگِ نهاییِ قفل‌شده.
  ۲) اندازه‌گیریِ همپوشانیِ زمانیِ *بازه‌های معامله* (نه فقط کندلِ سیگنال):
       overlap% = |بازه‌های S328 که با هر بازهٔ S327 تقاطع دارند| / |کلِ بازه‌های S328|
  ۳) گزارشِ جهت: چون S327=LONG و S328=SHORT، بررسیِ تضاد/هم‌جهتی.
  ۴) طبق بندِ ۳ قانونِ همپوشانی: اگر بخشی همپوشان بود، امکانِ استفادهٔ آن به‌عنوان
     فیلتر بررسی می‌شود (اینجا: آیا حذفِ بازه‌های همپوشان RQS+ را تغییر می‌دهد؟).

خروجی: results/_s328_overlap_audit.json
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicators as ind
from strategies.s328_rsi21_mr_regime_revival import build_signals


# --- بازتولیدِ سیگنالِ S327 (Sell-Climax → LONG) با کانفیگِ نهاییِ TS ---
S327_CFG = {
    'XAUUSD-M5': dict(kBody=1.6, brMin=0.60, streakN=2, rsiMax=30, emaTrend=200, bodyMaLen=20),
    'XAUUSD-H1': dict(kBody=1.6, brMin=0.60, streakN=3, rsiMax=42, emaTrend=200, bodyMaLen=20),
}


def s327_signals(df, cfg):
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    close_s = pd.Series(c)
    ema_t = ind.ema(close_s, cfg['emaTrend']).to_numpy()
    rsi14 = ind.rsi(close_s, 14).to_numpy()
    body = c - o
    abody = np.abs(body)
    rng = np.maximum(h - l, 1e-9)
    body_ratio = abody / rng
    body_ma = pd.Series(abody).rolling(cfg['bodyMaLen']).mean().to_numpy()
    is_bear = body < 0
    is_climax = is_bear & (abody >= cfg['kBody'] * np.nan_to_num(body_ma, nan=1e18))
    strong = body_ratio >= cfg['brMin']
    # رگهٔ نزولی
    bear_int = is_bear.astype(int)
    streak = np.zeros(len(df), dtype=int)
    for i in range(1, len(df)):
        streak[i] = streak[i-1] + 1 if bear_int[i] else 0
    streak_ok = streak >= cfg['streakN']
    rsi_ok = rsi14 <= cfg['rsiMax']
    raw = is_climax & strong & streak_ok & rsi_ok
    return pd.Series(raw).shift(1).fillna(False).to_numpy()  # ورود روی کندلِ بعد


def intervals_from_signal(sig, max_hold):
    """بازه‌های [entry, entry+max_hold] از آرایهٔ سیگنال (allow_overlap=False تقریبی)."""
    idx = np.where(sig)[0]
    intervals = []
    busy_until = -1
    for i in idx:
        entry = i + 1
        if entry <= busy_until:
            continue
        end = entry + max_hold
        intervals.append((entry, end))
        busy_until = end
    return intervals


def overlap_pct(a_ivs, b_ivs):
    """درصدِ بازه‌های a که با حداقل یک بازهٔ b تقاطع دارند."""
    if not a_ivs:
        return 0.0, 0
    hits = 0
    for (a0, a1) in a_ivs:
        for (b0, b1) in b_ivs:
            if a0 < b1 and b0 < a1:   # تقاطع
                hits += 1
                break
    return hits / len(a_ivs) * 100.0, hits


def audit(asset, tf, f, s328_cfg, s327_key):
    df = se.load_data(f)
    # سیگنالِ S328 (SHORT)
    ls, ss = build_signals(df, 21, s328_cfg['lo'], s328_cfg['hi'],
                           adx_max=s328_cfg['adx'], er_max=None)
    s328_iv = intervals_from_signal(ss, s328_cfg['mh'])
    # سیگنالِ S327 (LONG)
    s327_sig = s327_signals(df, S327_CFG[s327_key])
    s327_iv = intervals_from_signal(s327_sig, 24)
    ov_pct, hits = overlap_pct(s328_iv, s327_iv)
    # همپوشانیِ کندلِ سیگنالِ دقیق (هم‌زمان هر دو ماشه):
    same_bar = int((ss & s327_sig).sum())
    result = dict(asset=asset, tf=tf, s328_short_trades=len(s328_iv),
                  s327_long_trades=len(s327_iv), overlap_pct=round(ov_pct, 1),
                  overlap_hits=hits, same_bar_signals=same_bar,
                  direction_note="S328=SHORT vs S327=LONG (جهت‌ها مخالف)")
    return result, df, ss, s327_sig


if __name__ == '__main__':
    configs = {
        'M5': dict(lo=25, hi=75, adx=30, mh=24, sl=62, tp=43, s327='XAUUSD-M5'),
        'H1': dict(lo=18, hi=82, adx=None, mh=24, sl=195, tp=210, s327='XAUUSD-H1'),
    }
    files = {'M5': 'data/XAUUSD_M5.csv', 'H1': 'data/XAUUSD_H1.csv'}
    out = {}
    print("=" * 90)
    print("S328 OVERLAP AUDIT — RSI-fade SHORT vs S327 Sell-Climax LONG (XAU M5/H1)")
    print("=" * 90)
    for tf, cfg in configs.items():
        res, df, ss, s327_sig = audit('XAUUSD', tf, files[tf], cfg, cfg['s327'])
        out[f'XAUUSD-{tf}'] = res
        print(f"\n--- XAUUSD-{tf} ---")
        print(f"  S328 SHORT trades : {res['s328_short_trades']}")
        print(f"  S327 LONG  trades : {res['s327_long_trades']}")
        print(f"  same-bar signals  : {res['same_bar_signals']}  (هر دو ماشه در یک کندل)")
        print(f"  interval overlap  : {res['overlap_pct']}%  ({res['overlap_hits']} بازه)")
        print(f"  جهت: {res['direction_note']}")
    with open('results/_s328_overlap_audit.json', 'w') as fp:
        json.dump(out, fp, indent=2, ensure_ascii=False)
    print("\n💾 ذخیره شد: results/_s328_overlap_audit.json")
