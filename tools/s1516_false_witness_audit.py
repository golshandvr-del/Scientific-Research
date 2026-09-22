# -*- coding: utf-8 -*-
"""S1516 — ممیزیِ «شاهدِ کاذب» پیش از هرگونه سیم‌کشی · XAUUSD-H6 و XAUUSD-H4

چرا این فایل وجود دارد
======================
مکانیزمِ نمایشِ سایت (`runCard`: اولویتِ ENTRY > APPROACHING > NEUTRAL و جمعِ
بقیهٔ لایه‌ها در `otherLayers`) همپوشانیِ **معمولی** را خودش حل می‌کند. اما یک
حالت هست که آن مکانیزم ساختاراً نمی‌تواند حلش کند و فقط اندازه‌گیریِ قبلی
می‌تواند:

    وقتی دو لایه در واقع **یک رویدادِ واحد** باشند با دو اسم.

آن‌وقت سایت دو کادر نشان می‌دهد و کاربر می‌پندارد دو شاهدِ مستقل دارد، در حالی
که یک شاهد دوبار شمرده شده — ریسک دوبرابر می‌شود بدونِ افزودنِ هیچ اطلاعِ تازه.

سابقهٔ همین ریپو: `web_tool/src/strategy_registry.ts:794-797` دربارهٔ S404/S408
می‌گوید jaccard ۶۹.۳٪ و «یکی، نه هر دو».

خطرِ مشخصِ S1516
=================
S1516 = رکوردِ تازهٔ **کف** (`low[t] > max(low[t−L..t−1])`، لبهٔ تازه) × گیتِ
درفتِ علّی، با L تقویم‌همتا (H6→120 · H4→180). سندِ ACCEPT خودش §۴ اعلام کرده
که با S382-H4ِ **زنده** ۴۵.۹٪/۴۹.۷٪ همپوشانیِ پنجره دارد و با S1511 (وصل نیست)
۹۸.۸٪. پس دو پرسش باید **قبل** از سیم‌کشی پاسخ بگیرد:

  ① روی کارتِ H6 در برابرِ سه ساکنِ زنده (S919 · S955 · S607) — آیا یکی از
    آن‌ها همان رویداد است با اسمِ دیگر؟
  ② روی کارتِ H4 در برابرِ سه ساکنِ زنده (S382 · S589 · S547) — همان پرسش.
    ⚠️ اینجا خطرِ ساختاریِ ویژه‌ای هست: S589 هم یک «رکوردِ تازه» است، فقط روی
    **سقف** به‌جای **کف**. هم‌خانوادهٔ مفهومی‌اند، پس باید عدد بگیرد نه حدس.

معیارِ حکم (ارثی از پروندهٔ S1911/S589 در همین ریپو، بدونِ هیچ تغییر):
  · jaccard ≥ 0.60 **و** هم‌اندازگی (size_ratio ≥ 0.75) ⇒ FALSE-WITNESS
    ⇒ «یکی، نه هر دو» (پروندهٔ S404/S408)
  · share بالا ولی اندازهٔ به‌مراتب کوچک‌تر ⇒ زیرمجموعهٔ فیلترِ کیفیت
    ⇒ وصل می‌شود اما **زیرِ** والدش و با سایزِ مشترک (پروندهٔ S966/S1911)

روش
====
هر لایه از **قاعدهٔ منجمدِ کامیت‌شدهٔ خودش** بازتولید می‌شود (نه از پورتِ TS)،
روی همان `data/mt5_full/XAUUSD_{H6,H4}.csv.gz` که حکم روی آن صادر شد، و مقایسه
در سطحِ **شمارهٔ کندل** انجام می‌شود تا هم‌تراز باشد.

کنترلِ اعتبارسنجیِ ابزار (همان الگویی که ابزارِ S589/S1911 استفاده کردند): ابزار
باید عددِ **از قبل منتشرشدهٔ** خودِ سند را بازتولید کند — تعدادِ رویدادِ S1516 روی
H6 باید ۴۱۳ و روی H4 باید ۵۰۸ باشد (`results/_scan_S1516/XAUUSD_*.json::n_event`).
اگر بازتولید نشد، خروجیِ ابزار بی‌ارزش است و ممیزی متوقف می‌شود.

اجرا:  python3 tools/s1516_false_witness_audit.py
خروجی: results/_s1516/false_witness.json
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

OUT_DIR = os.path.join(ROOT, 'results', '_s1516')
OUT_FILE = os.path.join(OUT_DIR, 'false_witness.json')

# ── آستانهٔ حکم — از سابقهٔ S404/S408 در همین ریپو (jaccard ۶۹.۳٪) ──────────
JACCARD_FALSE_WITNESS = 0.60
SIZE_RATIO_COMPARABLE = 0.75    # هم‌اندازگی: min(n)/max(n)

# ── ثابت‌های منجمد (هر یک از فایلِ کامیت‌شدهٔ همان لایه) ─────────────────────
L_CAL = {'XAUUSD_H6': 120, 'XAUUSD_H4': 180}   # S1516 (قانونِ S1523: ۳۰ روزِ معاملاتی)
LB_FRESH_HIGH = 90        # S526 → S1520 → S589
RVOL_THR = 1.0            # S589
SLOT_WIN = 30             # S589
SLOT_MINP = 20            # S589
RHO_THR = 0.618           # S965 → S919 → S1520
SHOCK_K = 2.618           # S965 → S919
ATR_SHOCK_P = 21          # S965 → S919
DRIFT_K_S919 = 240        # S919 (۶۰ روز × ۴ کندلِ H6)
WILLR_P = 14              # S382
WILLR_THR = -13.0         # S382 — غیررند، از جاروبِ خودش
K_JUMP = 2.6              # S950 → S955
BV_WIN = 89               # S950 → S955
W_REG = 233               # S605 → S955 / S607
LAMBDA_IG = 0.94          # S840 → S607 (IGARCH)
Z_ENGLE = 2.618           # S607
DRIFT_K_S607_H6 = 240     # S607 روی H6


def load(card: str) -> pd.DataFrame:
    """دادهٔ کاملِ ۱۵.۶ ساله از mt5_full — همان منبعی که حکمِ S1516 روی آن صادر شد."""
    path = os.path.join(ROOT, 'data', 'mt5_full', f'{card}.csv.gz')
    assert 'mt5_full' in path and os.path.exists(path), f'E-16 GUARD: {path}'
    with gzip.open(path, 'rt') as f:
        df = pd.read_csv(f)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def _b(s) -> pd.Series:
    return s.astype('boolean').fillna(False).astype(bool)


# ═══════════════════════ لایهٔ نامزد: S1516 ═══════════════════════════════
def sig_s1516(df: pd.DataFrame, L: int) -> np.ndarray:
    """رکوردِ تازهٔ کف با پنجرهٔ تقویم‌همتا × گیتِ درفتِ علّی — عیناً
    `strategies/s1516_cal_floor.py::sig_fresh`."""
    lo, c = df['low'], df['close']
    ff = _b(lo > lo.rolling(L).max().shift(1))
    fresh = ff & ~ff.shift(1, fill_value=False)
    drift = _b((c.shift(1) - c.shift(L)) > 0)
    return (fresh & drift).to_numpy()


def sig_s1511(df: pd.DataFrame) -> np.ndarray:
    """والدِ بی‌افقِ S1516 (L=90) — برای کنترلِ اعتبارسنجی. روی سایت وصل نیست."""
    return sig_s1516(df, 90)


# ═══════════════════ ساکنانِ زندهٔ کارتِ H6 ═══════════════════════════════
def _atr_sma(df: pd.DataFrame, p: int) -> pd.Series:
    pc = df['close'].shift(1)
    tr = np.maximum(df['high'] - df['low'],
                    np.maximum((df['high'] - pc).abs(), (df['low'] - pc).abs()))
    return tr.rolling(p).mean()


def _rho(df: pd.DataFrame) -> pd.Series:
    rng = (df['high'] - df['low']).replace(0, np.nan)
    return (df['close'] - df['open']) / rng


def sig_s919(df: pd.DataFrame) -> np.ndarray:
    """S919 — شوکِ مطلعِ هم‌راستا با قرارداد (H6). عیناً tools/s1516_overlap_audit.py::s919_event
    ولی **دوسویه** (سندِ S919: جهت = follow)، چون آن ابزار فقط بازوی LONG را می‌سنجید."""
    atr_prev = _atr_sma(df, ATR_SHOCK_P).shift(1)
    shock = _b((df['high'] - df['low']) >= SHOCK_K * atr_prev)
    r = _b(_rho(df).abs() >= RHO_THR)
    up = _b(df['close'] > df['open'])
    c = df['close']
    dpos = _b((c.shift(1) - c.shift(DRIFT_K_S919 + 1)) > 0)
    dneg = _b((c.shift(1) - c.shift(DRIFT_K_S919 + 1)) < 0)
    return (shock & r & ((up & dpos) | (~up & dneg))).to_numpy()


def _sigma_bv(df: pd.DataFrame, win: int = BV_WIN) -> pd.Series:
    """واریانسِ Bipower علّی — پایهٔ S950/S955."""
    r = np.log(df['close'] / df['close'].shift(1))
    bp = (r.abs() * r.abs().shift(1)) * (np.pi / 2.0)
    return np.sqrt(bp.rolling(win).mean()).shift(1)


def _sigma_rm(df: pd.DataFrame) -> pd.Series:
    """σ سبکِ RiskMetrics (λ=0.94) — پایهٔ گیتِ آرامشِ S605/S955/S607."""
    r = np.log(df['close'] / df['close'].shift(1)).fillna(0.0).to_numpy()
    n = len(r)
    var = np.full(n, np.nan)
    seed = 50
    if n <= seed:
        return pd.Series(var, index=df.index)
    v = float(np.nanvar(r[1:seed + 1]))
    for i in range(seed, n):
        v = LAMBDA_IG * v + (1.0 - LAMBDA_IG) * r[i - 1] ** 2
        var[i] = v
    return pd.Series(np.sqrt(var), index=df.index)


def _calm(df: pd.DataFrame) -> pd.Series:
    """reg_t = σ_t ÷ میانهٔ σ(t−W..t−1) ≤ 1 — گیتِ آرامشِ مشترکِ S955/S607."""
    sig = _sigma_rm(df)
    med = sig.rolling(W_REG).median().shift(1)
    return _b((sig / med) <= 1.0)


def sig_s955(df: pd.DataFrame) -> np.ndarray:
    """S955 — جهشِ مرتونِ هم‌راستا با رانش × گیتِ آرامش (H6/H8/H12)."""
    r = np.log(df['close'] / df['close'].shift(1))
    sbv = _sigma_bv(df)
    jump = _b(r.abs() > K_JUMP * sbv)
    c = df['close']
    drift = c.shift(1) - c.shift(BV_WIN + 1)
    aligned = _b(((r > 0) & (drift > 0)) | ((r < 0) & (drift < 0)))
    return (jump & aligned & _calm(df)).to_numpy()


def sig_s607(df: pd.DataFrame, drift_k: int) -> np.ndarray:
    """S607 — شوکِ انگل (IGARCH |z|≥2.618) × گیتِ روندِ علّی × گیتِ آرامش."""
    r = np.log(df['close'] / df['close'].shift(1))
    sig = _sigma_rm(df)
    z = r / sig
    shock = _b(z.abs() >= Z_ENGLE)
    c = df['close']
    d = c.shift(1) - c.shift(1 + drift_k)
    aligned = _b(((z > 0) & (d > 0)) | ((z < 0) & (d < 0)))
    return (shock & aligned & _calm(df)).to_numpy()


# ═══════════════════ ساکنانِ زندهٔ کارتِ H4 ═══════════════════════════════
def sig_s382(df: pd.DataFrame) -> np.ndarray:
    """S382 — گذرِ Williams %R(14) به بالای −۱۳. **رویداد** است نه حالت."""
    hh = df['high'].rolling(WILLR_P).max()
    ll = df['low'].rolling(WILLR_P).min()
    w = -100.0 * (hh - df['close']) / (hh - ll).replace(0, np.nan)
    return _b((w.shift(1) <= WILLR_THR) & (w > WILLR_THR)).to_numpy()


def sig_s589(df: pd.DataFrame) -> np.ndarray:
    """S589 — سقفِ تازهٔ ۹۰ × RVOL هم‌اسلات ≥ ۱. هم‌خانوادهٔ مفهومیِ S1516
    (رکوردِ تازه) ولی روی **سقف**، پس مقایسه‌اش اجباری است نه اختیاری."""
    c = df['close']
    nh = _b(c > c.rolling(LB_FRESH_HIGH).max().shift(1))
    fresh = nh & ~nh.shift(1, fill_value=False)
    v = df['volume'].astype(float)
    hour = df['dt'].dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    rv = v / ref.replace(0, np.nan)
    return (fresh & (rv >= RVOL_THR) & rv.notna()).to_numpy()


def sig_s547(df: pd.DataFrame) -> np.ndarray:
    """S547 — درفتِ پیش‌تعطیلات: ورود در openِ اولین کندلِ روزِ P.
    قاعده‌اش **تقویمی** است و از فایلِ منجمدِ خودِ پروژه خوانده می‌شود
    (`results/s547/p_days.json`) — بازسازیِ دستیِ تعطیلات دقیقاً همان کاری است
    که سندِ S547 گام ۲ از آن پرهیز داد."""
    p = os.path.join(ROOT, 'results', 's547', 'p_days.json')
    if not os.path.exists(p):
        return np.zeros(len(df), bool)
    with open(p) as f:
        raw = json.load(f)
    days = set(raw['p_days'] if isinstance(raw, dict) else raw)
    d = df['dt'].dt.strftime('%Y-%m-%d')
    isp = d.isin(days)
    # اولین کندلِ آن روز (ورودِ سند = openِ روزِ P)
    first = isp & (~isp.shift(1, fill_value=False) | (d != d.shift(1)))
    return _b(first).to_numpy()


def compare(a: np.ndarray, b: np.ndarray, name_a: str, name_b: str) -> dict:
    ia, ib = set(np.where(a)[0]), set(np.where(b)[0])
    inter, union = ia & ib, ia | ib
    na, nb = len(ia), len(ib)
    size_ratio = (min(na, nb) / max(na, nb)) if max(na, nb) else 0.0
    jac = (len(inter) / len(union)) if union else 0.0
    return {
        'a': name_a, 'b': name_b,
        'n_a': na, 'n_b': nb, 'shared': len(inter),
        'share_of_a': round(100.0 * len(inter) / na, 1) if na else 0.0,
        'share_of_b': round(100.0 * len(inter) / nb, 1) if nb else 0.0,
        'jaccard': round(jac, 4),
        'size_ratio': round(size_ratio, 4),
        'false_witness': bool(jac >= JACCARD_FALSE_WITNESS
                              and size_ratio >= SIZE_RATIO_COMPARABLE),
    }


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    report = {
        'thresholds': {
            'jaccard_false_witness': JACCARD_FALSE_WITNESS,
            'size_ratio_comparable': SIZE_RATIO_COMPARABLE,
            'precedent': 'strategy_registry.ts:794-797 (S404/S408 jaccard 69.3% => one, not both)',
        },
        'cards': {},
    }

    # ساکنانِ **زندهٔ** هر کارت — از CARD_LAYERS خوانده شد، نه حدس زده شد:
    #   XAUUSD-H6 ⇒ ['S919','S955','S607']
    #   XAUUSD-H4 ⇒ ['S382','S589','S547']
    LIVE = {
        'XAUUSD_H6': [
            ('S919', lambda d: sig_s919(d), 'wired on H6 (top of CARD_LAYERS)'),
            ('S955', lambda d: sig_s955(d), 'wired on H6'),
            ('S607', lambda d: sig_s607(d, DRIFT_K_S607_H6), 'wired on H6 (H6-DUAL pool member)'),
        ],
        'XAUUSD_H4': [
            ('S382', lambda d: sig_s382(d), 'wired on H4 (top of CARD_LAYERS)'),
            ('S589', lambda d: sig_s589(d), 'wired on H4 — CONCEPTUAL SIBLING (fresh record, high side)'),
            ('S547', lambda d: sig_s547(d), 'wired on H4 (calendar layer)'),
        ],
    }

    for card in ('XAUUSD_H6', 'XAUUSD_H4'):
        df = load(card)
        L = L_CAL[card]
        cand = sig_s1516(df, L)
        rep = {
            'L': L,
            'bars': int(len(df)),
            'span_years': round((df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 86400), 2),
            'n_events': {'S1516': int(cand.sum())},
            'vs_live_incumbents': {},
        }
        print(f'\n{card} (L={L}): bars={len(df)} S1516_events={int(cand.sum())}', flush=True)

        for name, fn, why in LIVE[card]:
            other = fn(df)
            rec = compare(cand, other, 'S1516', name)
            rec['why_this_reference'] = why
            rep['vs_live_incumbents'][name] = rec
            rep['n_events'][name] = int(other.sum())
            print(f'  vs {name} [{why}]: n_{name}={int(other.sum())} '
                  f'shared={rec["shared"]} share_of_S1516={rec["share_of_a"]}% '
                  f'jaccard={rec["jaccard"]} size_ratio={rec["size_ratio"]} '
                  f'FALSE_WITNESS={rec["false_witness"]}', flush=True)

        # والدِ وصل‌نشده (S1511, L=90) — قیدِ ماندگار، نه تعارضِ امروز
        rep['vs_S1511_parent_unwired'] = compare(cand, sig_s1511(df), 'S1516', 'S1511')
        r = rep['vs_S1511_parent_unwired']
        print(f'  vs S1511 [parent L=90, NOT wired]: shared={r["shared"]} '
              f'share_of_S1516={r["share_of_a"]}% jaccard={r["jaccard"]} '
              f'FALSE_WITNESS={r["false_witness"]}', flush=True)
        report['cards'][card] = rep

    # ── کنترلِ اعتبارسنجیِ ابزار: بازتولیدِ n_event منتشرشدهٔ خودِ اسکن ──────────
    ctrl = {}
    ok = True
    for card, published in (('XAUUSD_H6', 413), ('XAUUSD_H4', 508)):
        got = report['cards'][card]['n_events']['S1516']
        ctrl[f'{card}_n_event_published'] = published
        ctrl[f'{card}_n_event_measured'] = got
        ctrl[f'{card}_match'] = bool(got == published)
        ok = ok and got == published
    ctrl['tool_valid'] = bool(ok)
    report['control'] = ctrl
    print(f'\ncontrol: {json.dumps(ctrl, ensure_ascii=False)}', flush=True)

    with open(OUT_FILE, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f'saved -> {OUT_FILE}', flush=True)

    if not ok:
        raise SystemExit('TOOL-INVALID: could not reproduce published S1516 event counts')


if __name__ == '__main__':
    main()
