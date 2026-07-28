# -*- coding: utf-8 -*-
"""
s335_overlap_audit.py — ممیزیِ همپوشانیِ رویداد-محورِ لایهٔ S335
================================================================================
قانونِ همپوشانیِ پروژه: پیش از افزودنِ لایه باید دقیقاً سنجید که با کدام لایهٔ
فعال و چند درصد همپوشانی دارد — با شبیه‌سازِ رویداد-محور. اگر بخشی همپوشان بود،
همان بخش را به‌عنوانِ فیلترِ احیا امتحان کن.

نزدیک‌ترین رقیبِ مفهومی: **S333** (احیای S79) — تنها لایهٔ LONGِ روند-محور روی هر سه
کارتِ XAU M5/M15/H1. هر دو «خریدِ کفِ موقت درونِ روندِ صعودی»‌اند اما مکانیزمِ
تشخیصشان کاملاً متفاوت است:
  • S333 : EMA-روند + پول‌بکِ RSI (rsi_turn/price_turn)     ← price-action/oscillator
  • S335 : trendflex-روند + چرخشِ چرخهٔ reflex (zero_up/dip) ← DSP/cycle اِهلرز

معیارِ همپوشانی (محافظه‌کارانه): درصدِ کندل‌های ورودِ S335 که با کندلِ ورودِ S333 در
پنجرهٔ ±tol کندل هم‌زمان‌اند (چون هر دو روی همان TF/asset‌اند، هم‌ترازیِ اندیسِ کندل
منصفانه است). دو جهته گزارش می‌شود (نسبت به S335 و نسبت به S333).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from engine import scalp_engine as se
import strategies.s335_mtf as M
import strategies.s333_s79_pullback_revival as S333

# پارامترهای نهاییِ S335 per-TF (از اسکنِ MTF — ACCEPT)
S335_FINAL = {
    'M5':  dict(trigger='zero_up',  rf_dip=1.0, tf_min=0.2, hu_min=0.53, r2_min=None, chop_max=38.2,
                sl=170, tp=255, hold=60),
    'M15': dict(trigger='dip_turn', rf_dip=1.0, tf_min=0.5, hu_min=0.50, r2_min=0.55, chop_max=None,
                sl=200, tp=340, hold=64),
    'H1':  dict(trigger='dip_turn', rf_dip=1.0, tf_min=0.5, hu_min=0.50, r2_min=None, chop_max=38.2,
                sl=480, tp=720, hold=40),
}

# پیکربندیِ S333 per-TF (از فایلِ منبعِ S333)
S333_CFG = {
    'M5':  dict(ef=20, es=100, rp=21, rth=35, confirm='rsi_turn'),
    'M15': dict(ef=20, es=100, rp=21, rth=35, confirm='rsi_turn'),
    'H1':  dict(ef=20, es=100, rp=21, rth=35, confirm='rsi_turn'),
}


def s335_entry_bars(df, cfg):
    S = M.precompute(df)
    sig = M.build_signal(S, cfg['trigger'], cfg['rf_dip'], cfg['tf_min'],
                         cfg['hu_min'], cfg['r2_min'], cfg['chop_max'])
    return np.where(sig)[0]


def s333_entry_bars(df, cfg):
    sig = S333.core_signal_confirmed(df, cfg['ef'], cfg['es'], cfg['rp'], cfg['rth'],
                                     confirm=cfg['confirm'])
    sig = np.asarray(sig, dtype=bool)
    return np.where(sig)[0]


def overlap(a_bars, b_bars, tol=1):
    """درصدِ a که در پنجرهٔ ±tol با یک عضوِ b هم‌زمان است (و برعکس)."""
    if len(a_bars) == 0:
        return 0.0, 0.0, 0
    bset = set(b_bars.tolist())
    hit = 0
    for x in a_bars:
        if any((x + d) in bset for d in range(-tol, tol + 1)):
            hit += 1
    pct_a = 100.0 * hit / len(a_bars)
    pct_b = 100.0 * hit / len(b_bars) if len(b_bars) else 0.0
    return pct_a, pct_b, hit


if __name__ == '__main__':
    print("S335 vs S333 — همپوشانیِ رویداد-محورِ کندلِ ورود (±1 کندل)\n" + "=" * 66)
    for tf in ['M5', 'M15', 'H1']:
        fpath = f'data/XAUUSD_{tf}.csv'
        if not os.path.exists(fpath):
            print(f"[skip] {fpath}"); continue
        df = se.load_data(fpath)
        a = s335_entry_bars(df, S335_FINAL[tf])
        b = s333_entry_bars(df, S333_CFG[tf])
        pa, pb, hit = overlap(a, b, tol=1)
        print(f"\nXAUUSD {tf}: S335 entries={len(a)}  S333 entries={len(b)}  co-timed(±1)={hit}")
        print(f"   → {pa:.1f}% از ورودهای S335 با S333 هم‌زمان‌اند")
        print(f"   → {pb:.1f}% از ورودهای S333 با S335 هم‌زمان‌اند")
