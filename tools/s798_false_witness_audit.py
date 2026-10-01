# -*- coding: utf-8 -*-
"""S798 — ممیزیِ «شاهدِ کاذب» پیش از هرگونه سیم‌کشی · XAUUSD-H8

چرا این فایل وجود دارد
======================
مکانیزمِ نمایشِ سایت (`runCard`: اولویتِ ENTRY > APPROACHING > NEUTRAL، یک primary و
بقیه در otherLayers) همپوشانیِ **معمولی** را خودش حل می‌کند. یک حالت را نمی‌تواند:
وقتی دو لایه در واقع **یک رویدادِ واحد با دو اسم** باشند. آن‌وقت کاربر دو کادر
می‌بیند و دو شاهدِ مستقل فرض می‌کند، در حالی که یک شاهد دوبار شمرده شده ⇒ ریسکِ
دوبرابر بدونِ اطلاعِ تازه. سابقهٔ ریپو: strategy_registry.ts (S404/S408، jaccard
۶۹.۳٪ ⇒ «یکی، نه هر دو») و S955/S1913 (هر چهار عددِ حکم یکی ⇒ یک لایه، دو نام).

خطرِ مشخصِ S798
===============
سندِ S798 §۴ بند ۴ خودش می‌گوید: «هم‌پوشانی احتمالی با S965/S919/S602 (همه شوک
H6/H8): رویداد پایه مشترک است … حسابرسی هم‌پوشانی معاملات انجام نشده». قاعدهٔ S798
= کندلِ H8 ساعتِ 08 UTC با `rng ≥ 2.618·ATR21_EMA[i−1]` و بدنهٔ ناصفر، follow.
یعنی هم‌خانوادهٔ شوکِ رنجِ S965 (همان θ=2.618، ولی ATR21 **EMA** به‌جای SMA، **بدونِ ρ**،
**با** قیدِ نشست). پس باید اندازه گرفت، نه فرض کرد.

روش
===
S798 عیناً از `strategies/s798_final.py` (atr21 + قاعده) بازتولید می‌شود؛ هر ساکنِ
کارتِ XAUUSD-H8 (S955·S965·S770·S966·S1911·S607·S1520·S589) از **مرجعِ پایتونیِ خودش**
یا artifactِ پریتیِ منجمدِ خودش، روی همان `data/mt5_full/XAUUSD_H8.csv`. مقایسه روی
**کندلِ رویداد** (کندلی که بسته‌شدنش ماشه است) — همان لحظه‌ای که سایت هر دو کادر را
هم‌زمان نشان می‌دهد.

حکم (هم‌تراز با tools/s1911_false_witness_audit.py و results/_s955_ckpt):
  FALSE-WITNESS  ⇔ jaccard ≥ 0.60 ∧ max(share) ≥ 0.90   (سابقهٔ S404/S408 ⇒ حذف)
  quality-filter ⇔ share ≥ 0.90 ولی jaccard پایین       (سابقهٔ S966/S1911 ⇒ مجاز با قید)
  independent    ⇔ هیچ‌کدام

کنترل‌ها (اعتبارِ ابزار): ① S798 باید ۷۹ سیگنال و ۷۹ معاملهٔ WR 74.68 را بازتولید کند
(عددِ سند)؛ ② S966 ⊂ S965 (share_of_a=۱۰۰٪، عددِ منتشرشده)؛ ③ S1911 = ۸۲ رویداد ⊂ S965.

اجرا:  python3 tools/s798_false_witness_audit.py
خروجی: results/_s798/false_witness_h8.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from tools import s434_fast_data as fd                     # noqa: E402
from engine import scalp_engine as se                      # noqa: E402
import strategies.s798_final as S798                       # noqa: E402
import strategies.s605_engle_sigma_regime as S5            # noqa: E402
import strategies.s604_engle_drift as B604                 # noqa: E402
from strategies.s840_engle_shock import signals_for as s840_signals   # noqa: E402
from strategies.s950_jump_aftermath import features as s950_features, BV_WIN   # noqa: E402
import strategies.s770_adr_expansion as S770               # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s798')
OUT_FILE = os.path.join(OUT_DIR, 'false_witness_h8.json')

JACCARD_FALSE_WITNESS = 0.60
SHARE_SUBSET = 0.90

# ── S798 (منجمد در strategies/S798_PREREG.md @8c5a19d8) ─────────────────────────
HOUR, THETA798, KSL798, RR798, MH798 = S798.HOUR, S798.THETA, S798.KSL, S798.RR, S798.MH
# ── ساکنان (هر عدد از فایلِ کامیت‌شدهٔ خودِ لایه) ────────────────────────────────
ATR_WIN, THETA, RHO_MIN, WARM_KYLE = 21, 2.618, 0.618, 250       # S965/S966
K_DRIFT_S966 = 180                                                # S966
W_CALM = 233                                                      # S1911/S955/S607
K_JUMP_S955 = 2.6                                                 # S955
S770_THETA_H8 = 0.65                                              # web_tool S770_CFG['XAUUSD-H8']
S607_K_DAYS, S607_W = 60, 233                                     # s607 FROZEN['H8']


def _rollsum(x, w):
    cs = np.concatenate(([0.0], np.cumsum(x)))
    out = np.empty(len(x))
    for i in range(len(x)):
        out[i] = cs[i + 1] - cs[max(0, i - w + 1)]
    return out


def ev_s798(df):
    o, h, l, c = [df[k].values.astype(float) for k in ('open', 'high', 'low', 'close')]
    hr = pd.to_datetime(df['time'], unit='s').dt.hour.values
    atr = S798.atr21(h, l, c)
    valid = ~np.isnan(atr)
    with np.errstate(invalid='ignore'):
        sig = valid & (hr == HOUR) & ((h - l) >= THETA798 * atr) & (c != o)
    return sig, np.sign(c - o).astype(int), atr


def kyle_base(df):
    o, h, l, c = [df[k].values.astype(float) for k in ('open', 'high', 'low', 'close')]
    n = len(c)
    tr = np.zeros(n)
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr = _rollsum(tr, ATR_WIN) / ATR_WIN
    atr_prev = np.empty(n); atr_prev[0] = atr[0]; atr_prev[1:] = atr[:-1]
    rng = h - l
    rho = np.divide(np.abs(c - o), rng, out=np.zeros(n), where=rng > 0)
    body = np.sign(c - o).astype(int)
    shock = (rng >= THETA * atr_prev) & (rng > 0) & (atr_prev > 1e-12)
    ev = shock & (rho >= RHO_MIN) & (body != 0) & (np.arange(n) >= WARM_KYLE)
    return ev, body, c


def ev_s966(df):
    ev, body, c = kyle_base(df)
    n = len(c); K = K_DRIFT_S966
    du = np.zeros(n, bool); dd = np.zeros(n, bool)
    du[K + 1:] = c[K:-1] > c[:-(K + 1)]
    dd[K + 1:] = c[K:-1] < c[:-(K + 1)]
    return ev & (((body > 0) & du) | ((body < 0) & dd)), body


def ev_s1911(df):
    # عیناً strategies/s1911_kyle_shock_calm.signals (کندلِ رویداد، پیش از شیفتِ ورود)
    o, h, l, c = [df[k].values.astype(float) for k in ('open', 'high', 'low', 'close')]
    n = len(c)
    tr = np.zeros(n)
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr = pd.Series(tr).rolling(ATR_WIN).mean().to_numpy()
    atr_prev = np.full(n, np.nan); atr_prev[1:] = atr[:-1]
    rng = h - l
    shock = (rng >= THETA * np.nan_to_num(atr_prev, nan=np.inf)) & (rng > 0)
    rho = np.divide(np.abs(c - o), rng, out=np.zeros(n), where=rng > 0)
    reg = S5.regime_ratio(S5.sigma_series(c), W_CALM)
    warm = max(ATR_WIN, W_CALM + 60) + 2
    body = np.sign(c - o).astype(int)
    with np.errstate(invalid='ignore'):
        ev = shock & (rho >= RHO_MIN) & (body != 0) & (np.arange(n) >= warm) & ~np.isnan(reg) & (reg <= 1.0)
    return ev, body


def ev_s955(df):
    # عیناً strategies/s955_jump_aftermath_calm.judge_tf (بازوی calm)
    c = df['close'].values.astype(np.float64); n = len(c)
    r, sbv, _ = s950_features(df)
    valid = (np.arange(n) >= BV_WIN + 2) & (sbv > 0)
    up = valid & (r > K_JUMP_S955 * sbv); dn = valid & (r < -K_JUMP_S955 * sbv)
    drift = np.zeros(n); drift[BV_WIN + 1:] = c[BV_WIN:-1] - c[:-(BV_WIN + 1)]
    reg = S5.regime_ratio(S5.sigma_series(c), W_CALM)
    with np.errstate(invalid='ignore'):
        calm = np.isfinite(reg) & (reg <= 1.0)
    ls = up & (drift > 0) & calm; ss = dn & (drift < 0) & calm
    return ls | ss, np.where(ls, 1, np.where(ss, -1, 0))


def ev_s770(df):
    frac = S770.build_features(df)
    ls, ss = S770.signals_for(frac, S770_THETA_H8)
    return ls | ss, np.where(ls, 1, np.where(ss, -1, 0))


def ev_s607(n_bars):
    # عیناً strategies/s607_engle_dual_gate.dual_member روی B604.load_raw('H8')
    m = B604.load_raw('H8')
    assert len(m['cl']) == n_bars
    w = m['w']
    idx, isl = s840_signals(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    reg = S5.regime_ratio(S5.sigma_series(m['cl']), S607_W)[idx]
    K = S607_K_DAYS * B604.BARS_PER_DAY['H8']
    cl = m['cl']
    keep = np.zeros(len(idx), bool)
    for j, i in enumerate(idx):
        if i - 1 - K < 0 or not np.isfinite(reg[j]) or reg[j] > 1.0:
            continue
        d = cl[i - 1] - cl[i - 1 - K]
        keep[j] = (d > 0) if bool(isl[j]) else (d < 0)
    ev = np.zeros(n_bars, bool); dirn = np.zeros(n_bars, int)
    ev[idx[keep]] = True
    dirn[idx[keep]] = np.where(isl[keep], 1, -1)
    return ev, dirn


def ev_from_artifact(path, key, n_bars):
    d = json.load(open(os.path.join(ROOT, path)))
    assert int(d['bars']) == n_bars, (path, d['bars'], n_bars)
    ev = np.zeros(n_bars, bool); ev[np.asarray(d[key], int)] = True
    return ev, np.where(ev, 1, 0)                         # S1520/S589: LONG-only


def pair_stats(a, ea, da, b, eb, db, times, mh_a):
    ia = set(np.flatnonzero(ea).tolist()); ib = set(np.flatnonzero(eb).tolist())
    inter = sorted(ia & ib); union = ia | ib
    jac = len(inter) / len(union) if union else 0.0
    sa = len(inter) / len(ia) if ia else 0.0
    sb = len(inter) / len(ib) if ib else 0.0
    same = sum(1 for i in inter if da[i] != 0 and da[i] == db[i])
    opp = sum(1 for i in inter if da[i] != 0 and db[i] != 0 and da[i] != db[i])
    ibs = np.array(sorted(ib))
    hold = sum(1 for i in sorted(ia) if ibs.size and np.any((ibs >= i - mh_a) & (ibs <= i + mh_a)))
    if jac >= JACCARD_FALSE_WITNESS and max(sa, sb) >= SHARE_SUBSET:
        verdict = 'FALSE-WITNESS'
    elif sa >= SHARE_SUBSET:
        verdict = 'A-subset-of-B-quality-filter'
    elif sb >= SHARE_SUBSET:
        verdict = 'B-subset-of-A-quality-filter'
    else:
        verdict = 'independent'
    return {
        'a': a, 'b': b, 'n_a': len(ia), 'n_b': len(ib),
        'same_bar_overlap': len(inter), 'jaccard': round(jac, 4),
        'share_of_a': round(sa, 4), 'share_of_b': round(sb, 4),
        'same_direction': same, 'opposite_direction': opp,
        'a_events_with_b_within_maxhold': hold,
        'a_events_with_b_within_maxhold_pct': round(100.0 * hold / len(ia), 1) if ia else None,
        'verdict': verdict,
        'shared_bars_utc': [str(pd.to_datetime(times[i], unit='s')) for i in inter][:20],
    }


def main():
    d = fd.load_fast('XAUUSD', 'H8')
    df = fd.as_dataframe(d)
    src = d.get('src', '?')
    assert 'mt5_full' in src, src
    times = pd.to_numeric(df['time']).to_numpy()
    n = len(df)

    e798, d798, atr798 = ev_s798(df)
    # ── کنترلِ ① : بازتولیدِ حکمِ S798 ───────────────────────────────────────────
    pip = se.ASSETS['XAUUSD']['pip']
    sl = np.where(~np.isnan(atr798), KSL798 * atr798 / pip, 0.0)
    ls = e798 & (d798 > 0); ss = e798 & (d798 < 0)
    tr = se.simulate_trades(df, ls, ss, sl, sl * RR798, 'XAUUSD', max_hold=MH798, allow_overlap=False)
    wr = round(100 * float((tr['pnl_pip'] > 0).mean()), 2)
    ctrl1 = dict(signals=int(e798.sum()), long=int(ls.sum()), short=int(ss.sum()),
                 trades=int(len(tr)), wr=wr, expected=dict(signals=79, trades=79, wr=74.68),
                 ok=bool(int(e798.sum()) == 79 and len(tr) == 79 and abs(wr - 74.68) < 0.01))
    assert ctrl1['ok'], ctrl1

    e965, b965, _ = kyle_base(df)
    e966, b966 = ev_s966(df)
    e1911, b1911 = ev_s1911(df)
    e955, b955 = ev_s955(df)
    e770, b770 = ev_s770(df)
    e607, b607 = ev_s607(n)
    e1520, b1520 = ev_from_artifact('results/_s1520_parity/XAUUSD_H8.json', 'signalIdx', n)
    e589, b589 = ev_from_artifact('results/_s589_parity/XAUUSD_H8.json', 'signal_bars', n)

    incumbents = [('S955', e955, b955), ('S965', e965, b965), ('S770', e770, b770),
                  ('S966', e966, b966), ('S1911', e1911, b1911), ('S607', e607, b607),
                  ('S1520', e1520, b1520), ('S589', e589, b589)]
    pairs = [pair_stats('S798', e798, d798, nm, ev, dv, times, MH798) for nm, ev, dv in incumbents]

    # ── کنترل‌های ② و ③ : سوابقِ منتشرشده باید بازتولید شوند ─────────────────────
    c966 = pair_stats('S966', e966, b966, 'S965', e965, b965, times, 16)
    c1911 = pair_stats('S1911', e1911, b1911, 'S965', e965, b965, times, 16)
    ctrl2 = dict(pair='S966 vs S965', share_of_a=c966['share_of_a'], expected_share_of_a=1.0,
                 ok=c966['share_of_a'] == 1.0)
    ctrl3 = dict(pair='S1911 vs S965', n_s1911=c1911['n_a'], share_of_a=c1911['share_of_a'],
                 jaccard=c1911['jaccard'], expected=dict(n=82, share_of_a=1.0, jaccard=0.569),
                 ok=bool(c1911['n_a'] == 82 and c1911['share_of_a'] == 1.0))

    # اتحادِ ساکنان: چند رویدادِ S798 روی هیچ ساکنی هم‌کندل نیست؟
    union = np.zeros(n, bool)
    for _, ev, _ in incumbents:
        union |= ev
    novel = int((e798 & ~union).sum())

    risky = [p for p in pairs if p['verdict'] == 'FALSE-WITNESS']
    constrained = [p for p in pairs if p['verdict'].endswith('quality-filter')]
    top = max(pairs, key=lambda p: p['jaccard'])
    out = {
        'what': 'ممیزیِ شاهدِ کاذب برای S798 پیش از سیم‌کشی روی کارتِ XAUUSD-H8 (۸ ساکن)',
        'why': ('سندِ S798 §۴ بند ۴: هم‌پوشانی با شوک‌های H8 «انجام نشده». مکانیزمِ نمایش '
                'رویدادِ واحد با دو اسم را تشخیص نمی‌دهد؛ فقط اندازه‌گیری می‌تواند. سابقه: '
                'S404/S408 jaccard ۶۹.۳٪ ⇒ «یکی، نه هر دو».'),
        'data': {'src': src, 'bars': int(n), 'tf': 'H8',
                 'from_utc': str(pd.to_datetime(times[0], unit='s')),
                 'to_utc': str(pd.to_datetime(times[-1], unit='s'))},
        'thresholds': {'jaccard_false_witness': JACCARD_FALSE_WITNESS, 'share_subset': SHARE_SUBSET},
        'controls': {'c1_s798_reproduces_verdict': ctrl1,
                     'c2_s966_subset_s965': ctrl2,
                     'c3_s1911_subset_s965': ctrl3},
        'event_counts': {'S798': int(e798.sum()), **{nm: int(ev.sum()) for nm, ev, _ in incumbents}},
        'pairs_vs_wired_layers': pairs,
        'max_jaccard': {'vs': top['b'], 'jaccard': top['jaccard']},
        's798_events_with_no_same_bar_incumbent': novel,
        's798_novel_pct': round(100.0 * novel / max(1, int(e798.sum())), 1),
        'false_witness_pairs': [p['b'] for p in risky],
        'quality_filter_pairs': [p['b'] for p in constrained],
        'decision': ('BLOCK' if risky else 'CLEAR-WITH-CONSTRAINTS' if constrained else 'CLEAR'),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    slim = {k: v for k, v in out.items() if k != 'pairs_vs_wired_layers'}
    print(json.dumps(slim, ensure_ascii=False, indent=1, default=str))
    for p in pairs:
        print(f"  S798 vs {p['b']:6s} n_b={p['n_b']:4d} same={p['same_bar_overlap']:3d} "
              f"jac={p['jaccard']:.4f} shareA={p['share_of_a']:.3f} shareB={p['share_of_b']:.3f} "
              f"opp={p['opposite_direction']} win±mh={p['a_events_with_b_within_maxhold_pct']}% -> {p['verdict']}")
    print(f'\n[ckpt] {OUT_FILE}')


if __name__ == '__main__':
    main()
