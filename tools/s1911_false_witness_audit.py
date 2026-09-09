# -*- coding: utf-8 -*-
"""S1911 — ممیزیِ «شاهدِ کاذب» پیش از هرگونه سیم‌کشی · XAUUSD-H8

چرا این فایل وجود دارد
======================
مکانیزمِ نمایشِ سایت (`runCard`: اولویتِ ENTRY > APPROACHING > NEUTRAL و فیلترِ
NEUTRAL از `otherLayers`) همپوشانیِ **معمولی** را خودش حل می‌کند — کاربر یک
تصمیمِ اصلی می‌بیند و بقیه در فهرستِ فرعی می‌مانند. اما یک حالت هست که آن
مکانیزم **نمی‌تواند** حلش کند و فقط اندازه‌گیریِ قبلی می‌تواند:

    وقتی دو لایه در واقع **یک رویدادِ واحد** باشند با دو اسم.

آن‌وقت سایت دو کادر نشان می‌دهد، کاربر فکر می‌کند دو شاهدِ **مستقل** دارد،
در حالی که یک شاهد است که دو بار شمرده شده — این «شاهدِ کاذب» است و ریسک را
دوبرابر می‌کند بدونِ اینکه اطلاعِ تازه‌ای اضافه شود.

سابقهٔ همین ریپو: `web_tool/src/strategy_registry.ts:794-797` دربارهٔ S404/S408
می‌گوید jaccard=۶۹.۳٪ و «یکی، نه هر دو».

خطرِ مشخصِ S1911
================
قاعدهٔ S1911 = رویدادِ S965 (`rng ≥ 2.618·ATR21[t−1]` ∧ `ρ ≥ 0.618` ∧ follow)
**∩** گیتِ آرامشِ σ (`σ_t ≤ median(σ_{t−233..t−1})`). یعنی از پیش می‌دانیم
زیرمجموعهٔ ساختاریِ S965 است و S965 **همین حالا روی کارتِ XAUUSD-H8 وصل است**.
سندِ خودِ S1911 §۴ هم همپوشانیِ ۵۶٪ با S966-H8 را اعلام کرده.

پس این ممیزی سه چیز را جدا می‌کند:
  ① زیرمجموعه بودن (share_of_a / share_of_b) — «آیا یک رویداد با دو اسم است؟»
  ② jaccard — سنجهٔ متقارنِ همان چیز، هم‌مقیاس با آستانهٔ S404/S408 (۶۹.۳٪)
  ③ جهت — همپوشانیِ هم‌جهت ریسک را جمع می‌کند؛ مخالف، هجِ خودزنی می‌سازد

روش
====
منطقِ هر لایهٔ وصل‌شدهٔ کارتِ H8 از **همان فایلِ پایتونِ مرجعِ خودش** بازتولید
می‌شود (نه از پورتِ TS)، روی همان `data/mt5_full/XAUUSD_H8.csv` و همان
پنجرهٔ زمانی، تا مقایسه هم‌تراز باشد. σ و رژیم عیناً از
`strategies/s605_engle_sigma_regime` import می‌شوند — بازنویسی نمی‌شوند.

اجرا:  python3 tools/s1911_false_witness_audit.py
خروجی: results/_s1911_ckpt/false_witness_h8.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import s434_fast_data as fd                    # noqa: E402
import strategies.s605_engle_sigma_regime as S5           # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s1911_ckpt')
OUT_FILE = os.path.join(OUT_DIR, 'false_witness_h8.json')

# آستانهٔ حکم — از سابقهٔ S404/S408 در همین ریپو (jaccard ۶۹.۳٪ ⇒ «یکی، نه هر دو»)
JACCARD_FALSE_WITNESS = 0.60
SHARE_SUBSET = 0.90

# ── ثابت‌های منجمدِ لایه‌ها (همه از فایل‌های کامیت‌شدهٔ خودشان) ────────────────
ATR_WIN, THETA, RHO_MIN = 21, 2.618, 0.618     # S965 / S966 / S1911
W_CALM = 233                                   # S606 → S1911
K_DRIFT_S966 = 180                             # S966
MH_KYLE = 16                                   # S965 / S966 / S1911
BV_WIN_S950 = 89                               # S950
K_JUMP_S950 = 2.6                              # S950
MH_S950 = 34                                   # S950


def _rollmean(x, w):
    """بازتولیدِ دقیقِ `_rollsum(x, w)/w`: در i<w−1 هم مقسوم‌علیه w است."""
    x = np.asarray(x, float)
    cs = np.concatenate(([0.0], np.cumsum(x)))
    n = len(x)
    out = np.empty(n)
    for i in range(n):
        lo = max(0, i - w + 1)
        out[i] = (cs[i + 1] - cs[lo]) / w
    return out


def base_features(df):
    """ATR21 علّی + رنج + ρ + علامتِ بدنه — عیناً features() لایه‌های کایل."""
    o = df['open'].to_numpy(float); h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    n = len(c)
    tr = np.zeros(n)
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr = _rollmean(tr, ATR_WIN)
    atr_prev = np.empty(n); atr_prev[0] = atr[0]; atr_prev[1:] = atr[:-1]
    rng = h - l
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(rng > 0, np.abs(c - o) / rng, 0.0)
    return dict(o=o, h=h, l=l, c=c, n=n, atr_prev=atr_prev, rng=rng, rho=rho,
                body=np.sign(c - o))


def kyle_shock_events(f):
    """رویدادِ پایهٔ منجمدِ S965: شوکِ رنج × ماندگاری ρ × بدنهٔ ناصفر."""
    with np.errstate(invalid='ignore'):
        shock = (f['rng'] >= THETA * np.nan_to_num(f['atr_prev'], nan=np.inf)) & (f['rng'] > 0)
    return shock & (f['rho'] >= RHO_MIN) & (f['body'] != 0)


def ev_s965(f, warm):
    """S965 — وصل‌شده روی کارت. شوکِ کایل، بی‌هیچ گیت."""
    idx = np.arange(f['n'])
    return kyle_shock_events(f) & (idx >= warm)


def ev_s966(f, warm):
    """S966 — وصل‌شده. S965 ∩ گیتِ درفتِ علّیِ K=180 هم‌جهتِ بدنه."""
    c = f['c']; n = f['n']
    drift_ok = np.zeros(n, bool)
    for t in range(K_DRIFT_S966 + 2, n):
        d = c[t - 1] - c[t - 1 - K_DRIFT_S966]
        drift_ok[t] = (d > 0 and f['body'][t] > 0) or (d < 0 and f['body'][t] < 0)
    return ev_s965(f, warm) & drift_ok


def ev_s1911(f, warm):
    """S1911 — نامزدِ این نشست. S965 ∩ گیتِ آرامشِ σ (reg ≤ 1)."""
    reg = S5.regime_ratio(S5.sigma_series(f['c']), W_CALM)
    with np.errstate(invalid='ignore'):
        calm = np.isfinite(reg) & (reg <= 1.0)
    return ev_s965(f, warm) & calm


def ev_s950(f, warm):
    """S950 — وصل‌شده. جهشِ Bipower هم‌راستا با رانشِ ۸۹کندلی (ماشهٔ متفاوت)."""
    c = f['c']; n = f['n']
    r = np.zeros(n)
    r[1:] = np.log(c[1:] / c[:-1])
    # واریانسِ Bipower علّی: میانگینِ |r_t|·|r_{t−1}| روی پنجرهٔ BV_WIN، شیفتِ ۱
    bp = np.zeros(n)
    bp[2:] = np.abs(r[2:]) * np.abs(r[1:-1])
    mu1 = np.sqrt(2.0 / np.pi)
    bv = _rollmean(bp, BV_WIN_S950) / (mu1 * mu1)
    sig = np.sqrt(np.maximum(bv, 0.0))
    sig_prev = np.empty(n); sig_prev[0] = sig[0]; sig_prev[1:] = sig[:-1]
    with np.errstate(divide='ignore', invalid='ignore'):
        jump = np.abs(r) > K_JUMP_S950 * np.where(sig_prev > 0, sig_prev, np.inf)
    drift = np.zeros(n, bool)
    aligned = np.zeros(n, bool)
    for t in range(BV_WIN + 2, n):
        d = c[t - 1] - c[t - 1 - BV_WIN]
        drift[t] = d > 0
        aligned[t] = (d > 0 and r[t] > 0) or (d < 0 and r[t] < 0)
    idx = np.arange(n)
    return jump & aligned & (idx >= warm)


def direction_of(f, ev):
    """جهتِ لایه‌های کایل = علامتِ بدنه؛ برای S950 = علامتِ بازدهِ همان کندل."""
    return np.where(ev, f['body'], 0)


def dir_s950(f, ev):
    c = f['c']; n = f['n']
    r = np.zeros(n); r[1:] = np.log(c[1:] / c[:-1])
    return np.where(ev, np.sign(r), 0)


def pair_stats(name_a, ev_a, dir_a, name_b, ev_b, dir_b, mh_a, mh_b, times):
    """سنجه‌های شاهدِ کاذب: هم‌کندل، jaccard، سهمِ هر طرف، توافقِ جهت، هم‌پنجره."""
    ia = set(np.flatnonzero(ev_a).tolist())
    ib = set(np.flatnonzero(ev_b).tolist())
    inter = sorted(ia & ib)
    union = ia | ib
    jac = len(inter) / len(union) if union else 0.0
    same = opp = 0
    for i in inter:
        if dir_a[i] != 0 and dir_b[i] != 0:
            if dir_a[i] == dir_b[i]:
                same += 1
            else:
                opp += 1
    # هم‌پوشانیِ پنجرهٔ نگه‌داری (نه فقط هم‌کندل): آیا وقتی A باز است، B شلیک می‌کند؟
    hold = 0
    ib_sorted = np.array(sorted(ib))
    for i in sorted(ia):
        if ib_sorted.size and np.any((ib_sorted >= i) & (ib_sorted <= i + mh_a)):
            hold += 1
    verdict = 'independent'
    if jac >= JACCARD_FALSE_WITNESS:
        verdict = 'FALSE-WITNESS-RISK'
    elif len(ia) and len(inter) / len(ia) >= SHARE_SUBSET:
        verdict = 'A-subset-of-B'
    elif len(ib) and len(inter) / len(ib) >= SHARE_SUBSET:
        verdict = 'B-subset-of-A'
    return {
        'a': name_a, 'b': name_b,
        'n_a': len(ia), 'n_b': len(ib),
        'same_bar_overlap': len(inter),
        'jaccard': round(jac, 4),
        'share_of_a': round(len(inter) / len(ia), 4) if ia else None,
        'share_of_b': round(len(inter) / len(ib), 4) if ib else None,
        'same_direction': same, 'opposite_direction': opp,
        'a_open_when_b_fires': hold,
        'a_open_when_b_fires_pct': round(100.0 * hold / len(ia), 1) if ia else None,
        'verdict': verdict,
        'first_shared_bar_utc': str(pd.to_datetime(times[inter[0]], unit='s')) if inter else None,
        'last_shared_bar_utc': str(pd.to_datetime(times[inter[-1]], unit='s')) if inter else None,
    }


def main():
    d = fd.load_fast('XAUUSD', 'H8')
    df = fd.as_dataframe(d)
    src = d.get('src', '?') if isinstance(d, dict) else '?'
    times = pd.to_numeric(df['time']).to_numpy()
    f = base_features(df)
    warm = max(ATR_WIN, W_CALM + 60, BV_WIN_S950) + 2

    layers = {}
    e965 = ev_s965(f, warm);   layers['S965'] = (e965, direction_of(f, e965), MH_KYLE)
    e966 = ev_s966(f, warm);   layers['S966'] = (e966, direction_of(f, e966), MH_KYLE)
    e1911 = ev_s1911(f, warm); layers['S1911'] = (e1911, direction_of(f, e1911), MH_KYLE)
    e950 = ev_s950(f, warm);   layers['S950'] = (e950, dir_s950(f, e950), MH_S950)

    pairs = []
    for other in ('S965', 'S966', 'S950'):
        ea, da, mha = layers['S1911']
        eb, db, mhb = layers[other]
        pairs.append(pair_stats('S1911', ea, da, other, eb, db, mha, mhb, times))
    # مرجعِ کنترل: S966 در برابر S965 (عددِ منتشرشدهٔ ۱۰۰٪ باید بازتولید شود)
    ea, da, mha = layers['S966']
    eb, db, mhb = layers['S965']
    control = pair_stats('S966', ea, da, 'S965', eb, db, mha, mhb, times)

    risky = [p for p in pairs if p['verdict'] != 'independent']
    out = {
        'what': 'ممیزیِ شاهدِ کاذب برای S1911 پیش از سیم‌کشی روی کارتِ XAUUSD-H8',
        'why': ('مکانیزمِ نمایشِ سایت همپوشانیِ معمولی را حل می‌کند، ولی نمی‌تواند تشخیص دهد '
                'که دو لایه یک رویدادِ واحد با دو اسم‌اند. آن حالت «شاهدِ کاذب» است: کاربر دو '
                'کادر می‌بیند و دو شاهدِ مستقل فرض می‌کند، در حالی که یک شاهد دو بار شمرده '
                'شده ⇒ ریسک دوبرابر، اطلاعِ تازه صفر. سابقه: strategy_registry.ts:794-797 '
                'دربارهٔ S404/S408 (jaccard ۶۹.۳٪ ⇒ «یکی، نه هر دو»).'),
        'data': {'src': src, 'bars': int(len(df)), 'tf': 'H8', 'warm': int(warm),
                 'from_utc': str(pd.to_datetime(times[0], unit='s')),
                 'to_utc': str(pd.to_datetime(times[-1], unit='s'))},
        'thresholds': {'jaccard_false_witness': JACCARD_FALSE_WITNESS,
                       'share_subset': SHARE_SUBSET,
                       'precedent': 'S404/S408 jaccard 0.693 ⇒ one, not both'},
        'event_counts': {k: int(v[0].sum()) for k, v in layers.items()},
        'pairs_vs_wired_layers': pairs,
        'control_s966_vs_s965': control,
        'false_witness_pairs': [p['b'] for p in risky],
        'decision': ('BLOCK' if risky else 'CLEAR'),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(f'\n[ckpt] {OUT_FILE}')


if __name__ == '__main__':
    main()
