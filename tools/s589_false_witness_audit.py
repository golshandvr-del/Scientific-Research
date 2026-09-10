# -*- coding: utf-8 -*-
"""S589 — ممیزیِ «شاهدِ کاذب» پیش از هرگونه سیم‌کشی · XAUUSD-H8 و XAUUSD-H4

چرا این فایل وجود دارد
======================
مکانیزمِ نمایشِ سایت (`runCard`: اولویتِ ENTRY > APPROACHING > NEUTRAL و جمعِ
لایه‌های هم‌جهت در `otherLayers`) همپوشانیِ **معمولی** را خودش حل می‌کند —
کاربر یک تصمیمِ اصلی می‌بیند و بقیه در فهرستِ فرعی می‌مانند. اما یک حالت هست
که آن مکانیزم **نمی‌تواند** حلش کند و فقط اندازه‌گیریِ قبلی می‌تواند:

    وقتی دو لایه در واقع **یک رویدادِ واحد** باشند با دو اسم.

آن‌وقت سایت دو کادر نشان می‌دهد، کاربر فکر می‌کند دو شاهدِ **مستقل** دارد،
در حالی که یک شاهد است که دو بار شمرده شده — «شاهدِ کاذب»: ریسک دوبرابر
می‌شود بدونِ اینکه اطلاعِ تازه‌ای اضافه شود.

سابقهٔ همین ریپو: `web_tool/src/strategy_registry.ts:863-866` دربارهٔ
S404/S408 می‌گوید jaccard=۶۹.۳٪ و «یکی، نه هر دو».

خطرِ مشخصِ S589
================
S589 = **همان رویدادِ پایهٔ S526** (`close[t] > max(close[t−90..t−1])`، لبهٔ
تازه) × گیتِ حجمِ نسبیِ هم‌اسلات (`RVOL_slot ≥ 1.0`).
سندِ ACCEPT خودش §۴ اعلام کرده: ۹۰.۶٪ ورودِ مشترک با S526 و ۶۱.۰٪ با S1520.

و اینجاست که خطر واقعی می‌شود: **S1520 همین حالا روی کارتِ XAUUSD-H8 وصل
است** (`CARD_LAYERS['XAUUSD-H8']`، آخرین ورودی). پس اگر S589 را روی همان
کارت وصل کنیم، دو لایه از **یک خانوادهٔ رویدادی** روی یک کارت می‌نشینند.
سندِ S589 عدد ۶۱.۰٪ را از یک اجرای دیگر نقل می‌کند؛ این ممیزی آن را
**مستقل بازتولید** می‌کند و سه چیز را از هم جدا می‌کند:

  ① زیرمجموعه بودن (share_of_a / share_of_b) — «آیا یک رویداد با دو اسم است؟»
  ② jaccard — سنجهٔ متقارنِ همان چیز، هم‌مقیاس با آستانهٔ S404/S408 (۶۹.۳٪)
  ③ جهت — همپوشانیِ هم‌جهت ریسک را جمع می‌کند (هر دو LONG-only ⇒ جمع‌شونده)

معیارِ حکم (ارثی از پروندهٔ S1911 در همین ریپو، بدون تغییر):
  · jaccard ≥ 0.60 **و** هم‌اندازگی (نسبتِ اندازه ≥ 0.75) ⇒ FALSE-WITNESS
    ⇒ «یکی، نه هر دو» (پروندهٔ S404/S408)
  · share بالا ولی اندازهٔ به‌مراتب کوچک‌تر ⇒ زیرمجموعهٔ فیلترِ کیفیت
    ⇒ وصل می‌شود اما **زیرِ** والدش و با سایزِ مشترک (پروندهٔ S966/S1911)

روش
====
هر دو لایه از **قواعدِ منجمدِ کامیت‌شدهٔ خودشان** بازتولید می‌شوند (نه از
پورتِ TS)، روی همان `data/mt5_full/XAUUSD_{H8,H4}.csv` و همان پنجرهٔ زمانی،
تا مقایسه هم‌تراز باشد.

کنترلِ اعتبارسنجیِ ابزار (همان الگویی که ابزارِ S1911 استفاده کرد): ابزار
باید عددِ **از قبل منتشرشدهٔ** سندِ S589 §۴ را بازتولید کند —
vs S526 = ۹۰.۶٪ و vs S1520 = ۶۱.۰٪ روی H8. اگر بازتولید نشد، خروجیِ ابزار
بی‌ارزش است و ممیزی متوقف می‌شود.

اجرا:  python3 tools/s589_false_witness_audit.py
خروجی: results/_s589/false_witness.json
"""
from __future__ import annotations

import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, 'results', '_s589')
OUT_FILE = os.path.join(OUT_DIR, 'false_witness.json')

# ── آستانهٔ حکم — از سابقهٔ S404/S408 در همین ریپو (jaccard ۶۹.۳٪) ──────────
JACCARD_FALSE_WITNESS = 0.60
SIZE_RATIO_COMPARABLE = 0.75    # هم‌اندازگی: min(n)/max(n)

# ── ثابت‌های منجمد (همه از فایل‌های کامیت‌شدهٔ خودِ لایه‌ها) ──────────────────
LOOKBACK = 90          # S526 → S1520 → S589
RVOL_THR = 1.0         # S589 (tools/s589_volume_fresh_high_runner.py)
SLOT_WIN = 30          # S589
SLOT_MINP = 20         # S589
RHO_THR = 0.618        # S965 → S1520 (tools/s1520_informed_fresh_high_runner.py)


def load(card: str) -> pd.DataFrame:
    """دادهٔ کاملِ ۱۵.۶ ساله از mt5_full (همان منبعی که حکم روی آن صادر شد)."""
    path = os.path.join(ROOT, 'data', 'mt5_full', f'{card}.csv.gz')
    with gzip.open(path, 'rt') as f:
        df = pd.read_csv(f)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    assert 'volume' in df.columns, 'BUG-NOVOLUME: volume column missing'
    return df


def fresh_high(df: pd.DataFrame) -> pd.Series:
    """رویدادِ پایهٔ منجمدِ S526 — لبهٔ تازه، نه حالتِ ماندگار."""
    c = df['close']
    nh = (c > c.rolling(LOOKBACK).max().shift(1)).fillna(False)
    return nh & ~nh.shift(1).fillna(False)


def rvol_slot(df: pd.DataFrame) -> pd.Series:
    """S589: volume[t] / median(volume of previous 30 bars, same hour-of-day)."""
    v = df['volume'].astype(float)
    hour = df['dt'].dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    return v / ref.replace(0, np.nan)


def rho(df: pd.DataFrame) -> pd.Series:
    """S1520/S965: نسبتِ بدنه به دامنه — **علامت‌دار** (LONG-only)."""
    rng = (df['high'] - df['low']).replace(0, np.nan)
    return ((df['close'] - df['open']) / rng).fillna(0.0)


def sig_s589(df: pd.DataFrame) -> np.ndarray:
    rv = rvol_slot(df)
    return (fresh_high(df) & (rv >= RVOL_THR) & rv.notna()).to_numpy()


def sig_s1520(df: pd.DataFrame) -> np.ndarray:
    return (fresh_high(df) & (rho(df) >= RHO_THR)).to_numpy()


def sig_s526(df: pd.DataFrame) -> np.ndarray:
    """والدِ بی‌گیت — برای کنترلِ اعتبارسنجیِ ابزار."""
    return fresh_high(df).to_numpy()


def compare(a: np.ndarray, b: np.ndarray, name_a: str, name_b: str) -> dict:
    ia, ib = set(np.where(a)[0]), set(np.where(b)[0])
    inter = ia & ib
    union = ia | ib
    na, nb = len(ia), len(ib)
    size_ratio = (min(na, nb) / max(na, nb)) if max(na, nb) else 0.0
    jac = (len(inter) / len(union)) if union else 0.0
    return {
        'a': name_a, 'b': name_b,
        'n_a': na, 'n_b': nb,
        'shared': len(inter),
        'share_of_a': round(100.0 * len(inter) / na, 1) if na else 0.0,
        'share_of_b': round(100.0 * len(inter) / nb, 1) if nb else 0.0,
        'jaccard': round(jac, 4),
        'size_ratio': round(size_ratio, 4),
        'false_witness': bool(jac >= JACCARD_FALSE_WITNESS
                              and size_ratio >= SIZE_RATIO_COMPARABLE),
    }


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    report: dict = {
        'thresholds': {
            'jaccard_false_witness': JACCARD_FALSE_WITNESS,
            'size_ratio_comparable': SIZE_RATIO_COMPARABLE,
            'precedent': 'strategy_registry.ts:863-866 (S404/S408 jaccard 69.3% => one, not both)',
        },
        'cards': {},
    }

    for card in ('XAUUSD_H8', 'XAUUSD_H4'):
        df = load(card)
        s589, s1520, s526 = sig_s589(df), sig_s1520(df), sig_s526(df)
        card_rep = {
            'bars': int(len(df)),
            'span_years': round((df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 86400), 2),
            'n_events': {'S589': int(s589.sum()), 'S1520': int(s1520.sum()),
                         'S526_base': int(s526.sum())},
            'vs_S1520_LIVE_ON_H8': compare(s589, s1520, 'S589', 'S1520'),
            'vs_S526_parent_unwired': compare(s589, s526, 'S589', 'S526'),
        }
        report['cards'][card] = card_rep
        print(f'{card}: bars={len(df)} S589={int(s589.sum())} '
              f'S1520={int(s1520.sum())} S526={int(s526.sum())}', flush=True)
        for k in ('vs_S1520_LIVE_ON_H8', 'vs_S526_parent_unwired'):
            r = card_rep[k]
            print(f'  {k}: shared={r["shared"]} share_of_S589={r["share_of_a"]}% '
                  f'jaccard={r["jaccard"]} size_ratio={r["size_ratio"]} '
                  f'FALSE_WITNESS={r["false_witness"]}', flush=True)

    # ── کنترلِ اعتبارسنجیِ ابزار: بازتولیدِ اعدادِ منتشرشدهٔ سندِ S589 §۴ ────────
    # سند روی H8 گفته: vs S526 = 90.6٪ و vs S1520 = 61.0٪ (سهم از ۱۵۹ معامله).
    # اینجا سطحِ **رویداد** سنجیده می‌شود نه معاملهٔ پس از FIFO، پس عدد دقیقاً
    # برابر نیست؛ ولی باید در همان همسایگی باشد وگرنه ابزار غلط است.
    h8 = report['cards']['XAUUSD_H8']
    ctrl = {
        'published_vs_S526_trades': 90.6,
        'measured_vs_S526_events': h8['vs_S526_parent_unwired']['share_of_a'],
        'published_vs_S1520_trades': 61.0,
        'measured_vs_S1520_events': h8['vs_S1520_LIVE_ON_H8']['share_of_a'],
    }
    # S589 زیرمجموعهٔ ساختاریِ کاملِ S526 است (گیت روی همان رویداد) ⇒ باید ۱۰۰٪ باشد
    ctrl['subset_of_S526_exact'] = bool(h8['vs_S526_parent_unwired']['share_of_a'] == 100.0)
    ctrl['s1520_within_10pp_of_published'] = bool(
        abs(h8['vs_S1520_LIVE_ON_H8']['share_of_a'] - 61.0) <= 10.0)
    ctrl['tool_valid'] = bool(ctrl['subset_of_S526_exact']
                              and ctrl['s1520_within_10pp_of_published'])
    report['control'] = ctrl
    print(f'\ncontrol: {json.dumps(ctrl, ensure_ascii=False)}', flush=True)

    with open(OUT_FILE, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f'saved -> {OUT_FILE}', flush=True)

    if not ctrl['tool_valid']:
        raise SystemExit('TOOL-INVALID: could not reproduce published S589 overlap numbers')


if __name__ == '__main__':
    main()
