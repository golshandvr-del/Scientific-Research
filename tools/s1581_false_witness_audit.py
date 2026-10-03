# -*- coding: utf-8 -*-
"""S1581 — ممیزیِ «شاهدِ کاذب» پیش از سیم‌کشی · XAUUSD-H6

چرا این فایل وجود دارد
======================
مکانیزمِ نمایشِ سایت (`runCard`) همپوشانیِ **معمولی** را خودش حل می‌کند. تنها
حالتی که آن مکانیزم ساختاراً نمی‌بیند و فقط اندازه‌گیریِ قبلی می‌تواند:

    وقتی دو لایه در واقع **یک رویدادِ واحد** باشند با دو اسم.

سابقهٔ همین ریپو: `web_tool/src/strategy_registry.ts:794-797` دربارهٔ S404/S408
می‌گوید jaccard ۶۹.۳٪ و «یکی، نه هر دو».

خطرِ مشخصِ S1581
================
S1581 = کفِ تازهٔ ۹۰ (S1511) × گیتِ حجمِ هم‌اسلات (S589، RVOL≥1.0). کارتِ ACCEPT
تنها **H6** است (RQS2 88.0). ممیزیِ خودِ سندِ S1581 (`results/_s1581/overlap_audit.json`)
فقط دو مرجعِ **وصل‌نشده** را سنجیده بود: S1511 (والد، ۹۰٪) و رویدادِ S526 (۱۹.۶٪).
هیچ‌کدام از چهار ساکنِ **زندهٔ** H6 اندازه‌گیری نشده بود. و مهم‌تر: ممیزیِ زمانِ
سیم‌کشیِ S1516 صریحاً هشدار داده بود که «هر کس روزی S1511 را وصل کند: یکی، نه
هر دو» (jaccard 0.809 با والدش).

پرسش‌های اجباری:
  ① S1581-H6 در برابرِ ساکنانِ زندهٔ H6 (S919 · S955 · S607 · S1516) — آیا یکی
     از آن‌ها همان رویداد است با اسمِ دیگر؟
  ② S1581-H6 در برابرِ **والدِ** وصل‌نشدهٔ S1511 (L=90) و **پسرخالهٔ** زندهٔ
     S1516-H6 (کفِ تازه با L تقویم‌همتا=120) — هر دو «رویدادِ کفِ تازه»اند، پس
     عدد باید حکم کند نه حدس.

معیارِ حکم (ارثی از پروندهٔ S1911/S589/S1516 در همین ریپو، بدونِ تغییر):
  · jaccard ≥ 0.60 **و** هم‌اندازگی (size_ratio ≥ 0.75) ⇒ FALSE-WITNESS
    ⇒ «یکی، نه هر دو» (پروندهٔ S404/S408)
  · share بالا ولی اندازهٔ به‌مراتب کوچک‌تر ⇒ زیرمجموعهٔ فیلترِ کیفیت
    ⇒ وصل می‌شود اما **زیرِ** والدش و با سایزِ مشترک (پروندهٔ S966/S1911)

کنترلِ اعتبارسنجیِ ابزار: باید عددِ **از قبل منتشرشدهٔ** خودِ سندِ S1581 را
بازتولید کند — تعدادِ **سیگنال** (n_signals) روی H6 باید **۳۲۶** باشد و تعدادِ
**معامله** (n_trades، پس از FIFO) باید **۲۱۹** باشد
(`results/_s1581/XAUUSD_H6_gated.json`). اگر بازتولید نشد، ابزار بی‌اعتبار است.

اجرا:  python3 tools/s1581_false_witness_audit.py
خروجی: results/_s1581/false_witness.json
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

OUT_DIR = os.path.join(ROOT, 'results', '_s1581')
OUT_FILE = os.path.join(OUT_DIR, 'false_witness.json')

# ── آستانهٔ حکم — از سابقهٔ S404/S408 در همین ریپو (jaccard ۶۹.۳٪) ──────────
JACCARD_FALSE_WITNESS = 0.60
SIZE_RATIO_COMPARABLE = 0.75    # هم‌اندازگی: min(n)/max(n)

# ── ثابت‌های منجمد (هر یک از فایلِ کامیت‌شدهٔ همان لایه) ─────────────────────
LB_S1581 = 90             # S1511 (منجمد S950/S523/S526)
RVOL_THR = 1.0            # S589
SLOT_WIN = 30             # S589
SLOT_MINP = 20            # S589
L_CAL_S1516_H6 = 120      # S1516 (۳۰ روزِ معاملاتی روی H6)
LB_FRESH_HIGH = 90        # S526 → S1520 → S589
SHOCK_K = 2.618           # S965 → S919
ATR_SHOCK_P = 21          # S965 → S919
RHO_THR = 0.618           # S965 → S919
DRIFT_K_S919 = 240        # S919
K_JUMP = 2.6              # S950 → S955
BV_WIN = 89               # S950 → S955
W_REG = 233               # S605 → S955 / S607
LAMBDA_IG = 0.94          # S840 → S607
Z_ENGLE = 2.618           # S607
DRIFT_K_S607_H6 = 240     # S607 روی H6

#: کنترل — اعدادِ منتشرشدهٔ سندِ S1581 روی H6.
PUBLISHED_SIGNALS = 326
PUBLISHED_TRADES = 219


def load(card: str) -> pd.DataFrame:
    """دادهٔ کاملِ ۱۵.۶ ساله از mt5_full — همان منبعی که حکمِ S1581 روی آن صادر شد."""
    path = os.path.join(ROOT, 'data', 'mt5_full', f'{card}.csv.gz')
    assert 'mt5_full' in path and os.path.exists(path), f'E-16 GUARD: {path}'
    with gzip.open(path, 'rt') as f:
        df = pd.read_csv(f)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def _b(s) -> pd.Series:
    return s.astype('boolean').fillna(False).astype(bool)


# ═══════════════════════ لایهٔ نامزد: S1581 ═══════════════════════════════
def _drift_mask(df: pd.DataFrame, L: int) -> pd.Series:
    c = df['close']
    return _b((c.shift(1) - c.shift(L)) > 0)


def _ff_state(df: pd.DataFrame, L: int) -> pd.Series:
    lo = df['low']
    return _b(lo > lo.rolling(L).max().shift(1))


def sig_s1511(df: pd.DataFrame, L: int = LB_S1581) -> np.ndarray:
    """S1511 (و والدِ S1581) — کفِ تازهٔ L-کندلی × گیتِ درفتِ علّی."""
    ff = _ff_state(df, L)
    fresh = ff & ~ff.shift(1, fill_value=False)
    return (fresh & _drift_mask(df, L)).to_numpy()


def rvol_slot(df: pd.DataFrame) -> pd.Series:
    """S589 — حجم ÷ میانهٔ ۳۰ رخدادِ قبلیِ همان ساعتِ روز (shift(1) درونِ گروه)."""
    v = df['volume'].astype(float)
    hour = df['dt'].dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    return v / ref.replace(0, np.nan)


def sig_s1581(df: pd.DataFrame) -> np.ndarray:
    """S1581 — رویدادِ پایهٔ S1511 ∧ گیتِ حجمِ هم‌اسلات (RVOL≥1) — عیناً
    `strategies/s1581_fresh_floor_volume.py::make_signals('gated')`."""
    base = pd.Series(sig_s1511(df), index=df.index)
    rv = rvol_slot(df)
    return (base & rv.notna() & (rv >= RVOL_THR)).to_numpy()


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
    """S919 — شوکِ مطلعِ هم‌راستا با قرارداد (H6). عیناً tools/s1516_false_witness_audit.py."""
    atr_prev = _atr_sma(df, ATR_SHOCK_P).shift(1)
    shock = _b((df['high'] - df['low']) >= SHOCK_K * atr_prev)
    r = _b(_rho(df).abs() >= RHO_THR)
    up = _b(df['close'] > df['open'])
    c = df['close']
    dpos = _b((c.shift(1) - c.shift(DRIFT_K_S919 + 1)) > 0)
    dneg = _b((c.shift(1) - c.shift(DRIFT_K_S919 + 1)) < 0)
    return (shock & r & ((up & dpos) | (~up & dneg))).to_numpy()


def _sigma_bv(df: pd.DataFrame, win: int = BV_WIN) -> pd.Series:
    r = np.log(df['close'] / df['close'].shift(1))
    bp = (r.abs() * r.abs().shift(1)) * (np.pi / 2.0)
    return np.sqrt(bp.rolling(win).mean()).shift(1)


def _sigma_rm(df: pd.DataFrame) -> pd.Series:
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
    sig = _sigma_rm(df)
    med = sig.rolling(W_REG).median().shift(1)
    return _b((sig / med) <= 1.0)


def sig_s955(df: pd.DataFrame) -> np.ndarray:
    """S955 — جهشِ مرتونِ هم‌راستا با رانش × گیتِ آرامش (H6)."""
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


def sig_s1516_h6(df: pd.DataFrame) -> np.ndarray:
    """S1516-H6 — کفِ تازهٔ تقویم‌همتا (L=120) × گیتِ درفت — پسرخالهٔ زندهٔ S1581."""
    return sig_s1511(df, L_CAL_S1516_H6)


def sig_s526_event(df: pd.DataFrame) -> np.ndarray:
    """رویدادِ سقفِ تازهٔ S526 (والدِ سقف‌محورها) — مرجعِ مفهومیِ متضاد."""
    c = df['close']
    nh = _b(c > c.rolling(LB_FRESH_HIGH).max().shift(1))
    return (nh & ~nh.shift(1, fill_value=False)).to_numpy()


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
        'layer': 'S1581',
        'card': 'XAUUSD_H6',
        'rule': 'fresh-floor 90 (S1511) x slot-RVOL>=1.0 (S589)',
        'thresholds': {
            'jaccard_false_witness': JACCARD_FALSE_WITNESS,
            'size_ratio_comparable': SIZE_RATIO_COMPARABLE,
            'precedent': 'strategy_registry.ts:794-797 (S404/S408 jaccard 69.3% => one, not both)',
        },
    }

    card = 'XAUUSD_H6'
    df = load(card)
    cand = sig_s1581(df)
    base_1511 = sig_s1511(df)
    rv = rvol_slot(df)
    n_base = int(base_1511.sum())
    n_pass = int((pd.Series(base_1511, index=df.index) & rv.notna() & (rv >= RVOL_THR)).sum())

    rep = {
        'bars': int(len(df)),
        'span_years': round((df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 86400), 2),
        'n_signals': int(cand.sum()),
        'n_base_events_S1511_rule': n_base,
        'pass_rate_pct': round(100.0 * n_pass / max(1, n_base), 1),
        'vs_live_incumbents': {},
    }
    print(f'\n{card}: bars={len(df)} S1581_signals={int(cand.sum())} '
          f'base={n_base} pass_rate={rep["pass_rate_pct"]}%', flush=True)

    # ساکنانِ **زندهٔ** H6 — از CARD_LAYERS خوانده شد، نه حدس زده شد:
    #   XAUUSD-H6 ⇒ ['S919','S955','S607','S1516']
    LIVE = [
        ('S919', lambda d: sig_s919(d), 'wired on H6 (top of CARD_LAYERS)'),
        ('S955', lambda d: sig_s955(d), 'wired on H6'),
        ('S607', lambda d: sig_s607(d, DRIFT_K_S607_H6), 'wired on H6 (H6-DUAL pool member)'),
        ('S1516', lambda d: sig_s1516_h6(d), 'wired on H6 — CONCEPTUAL SIBLING (fresh FLOOR, calendar L=120)'),
    ]
    for name, fn, why in LIVE:
        other = fn(df)
        rec = compare(cand, other, 'S1581', name)
        rec['why_this_reference'] = why
        rep['vs_live_incumbents'][name] = rec
        print(f'  vs {name} [{why}]: n_{name}={int(other.sum())} '
              f'shared={rec["shared"]} share_of_S1581={rec["share_of_a"]}% '
              f'jaccard={rec["jaccard"]} size_ratio={rec["size_ratio"]} '
              f'FALSE_WITNESS={rec["false_witness"]}', flush=True)

    # والدِ وصل‌نشدهٔ S1511 (همان رویداد بدونِ گیت) — قیدِ ماندگار، نه تعارضِ امروز
    rep['vs_S1511_parent_unwired'] = compare(cand, base_1511, 'S1581', 'S1511')
    r = rep['vs_S1511_parent_unwired']
    print(f'  vs S1511 [parent L=90, NOT wired]: shared={r["shared"]} '
          f'share_of_S1581={r["share_of_a"]}% jaccard={r["jaccard"]} '
          f'size_ratio={r["size_ratio"]} FALSE_WITNESS={r["false_witness"]}', flush=True)

    # مرجعِ مفهومیِ متضاد (سقف‌محور) — برای اطمینان از اینکه گیت، رویداد را به
    # «سقف» منتقل نکرده باشد.
    rep['vs_S526_highside_event'] = compare(cand, sig_s526_event(df), 'S1581', 'S526_event')
    r = rep['vs_S526_highside_event']
    print(f'  vs S526 high-side event [not wired]: shared={r["shared"]} '
          f'jaccard={r["jaccard"]} FALSE_WITNESS={r["false_witness"]}', flush=True)

    report['cards'] = {card: rep}

    # ── کنترلِ اعتبارسنجی: بازتولیدِ n_signals منتشرشدهٔ خودِ artifactِ S1581 ──
    got = rep['n_signals']
    ctrl = {
        'published_n_signals': PUBLISHED_SIGNALS,
        'measured_n_signals': got,
        'match': bool(got == PUBLISHED_SIGNALS),
        'source': 'results/_s1581/XAUUSD_H6_gated.json::n_signals',
    }
    report['control'] = ctrl
    print(f'\ncontrol: {json.dumps(ctrl, ensure_ascii=False)}', flush=True)

    with open(OUT_FILE, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f'saved -> {OUT_FILE}', flush=True)

    if not ctrl['match']:
        raise SystemExit('TOOL-INVALID: could not reproduce published S1581 signal count')


if __name__ == '__main__':
    main()
