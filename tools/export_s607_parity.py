# -*- coding: utf-8 -*-
"""
export_s607_parity.py — مرجعِ پریتیِ پایتون برای پورتِ **S607** به سایت
======================================================================
هدف: تولیدِ «حقیقتِ زمینی» تا پورتِ TypeScript بیت‌به‌بیت سنجیده شود، **بدون
بازنویسیِ هیچ فرمولی**. همهٔ توابع از همان ماشینِ منجمدی وارد می‌شوند که حکمِ
`ACCEPT 83.1` را ساخت:

  · `strategies.s840_engle_shock` → `ewma_z` (σ²=0.94σ²+0.06r²) · `atr_series`
    (وایلدر ۳۴) · `signals_for` (|z|≥z_thr، follow)
  · `strategies.s604_engle_drift` → `load_raw`، `BARS_PER_DAY`، `TF_HOLD`
  · `strategies.s605_engle_sigma_regime` → `sigma_series`، `regime_ratio`

سندِ حاکم: results/S607_EngleShockDualGatePool_Xauusd_D1H8H6_rqs2_83.1_ACCEPT.md
پیش‌ثبت:   results/S607_PREREG_ENGLE_DUAL_GATE.md (c7d5a3d7)

خروجی: results/_s607_parity/<TF>.json شاملِ
  · پارامترهای منجمدِ کارت (z_thr/mode/sl_k/rr/hold/warmup)
  · آخرین N کندلِ خام (برای تزریق به TS)
  · سری‌های z/atr/sigma/reg روی همان کندل‌ها
  · فهرستِ سیگنال‌های dual با جهت و SL/TP

⚠️ H12 هم صادر می‌شود ولی به‌عنوانِ **شاهدِ منفی**: انتخاب‌گرِ رسمی آن را با
   حاشیهٔ ۰.۱۵ از استخر حذف کرد ⇒ سایت **نباید** آن را وصل کند. اگر روزی کسی
   H12 را وصل کرد، این فایل مدرکِ خلافش است.

اجرا: python3 tools/export_s607_parity.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

import strategies.s604_engle_drift as B  # noqa: E402
import strategies.s605_engle_sigma_regime as S5  # noqa: E402
from strategies.s840_engle_shock import signals_for  # noqa: E402

import warnings  # noqa: E402
warnings.filterwarnings('ignore')

OUT = 'results/_s607_parity'
VERDICT = 'results/_s607_dual_gate/verdict.json'
CENSUS = 'results/_s607_dual_gate/census.json'

# پیکربندیِ منجمدِ S607 — عیناً از strategies/s607_engle_dual_gate.py
FROZEN = {'H8': dict(K=60, W=233), 'H12': dict(K=30, W=89), 'H6': dict(K=60, W=233)}
# اعضای رسمیِ استخرِ ACCEPT (از verdict.json خوانده و assert می‌شود)
OFFICIAL_CARDS = ['XAUUSD-D1', 'XAUUSD-H8', 'XAUUSD-H6']
# چند کندلِ آخر برای تزریق به TS صادر شود (سقفِ حجمِ فایل)
TAIL = 900


def dual_signals(m, K_days, W):
    """سیگنال‌های dual یک کارتِ گیت‌دار — منطقِ عیناً `s607.dual_member`."""
    w = m['w']
    idx, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    K = K_days * B.BARS_PER_DAY[m['tf']]
    cl = m['cl']
    reg = m['reg'][W][idx]
    calm = np.isfinite(reg) & (reg <= 1.0)
    drift_ok = np.zeros(len(idx), bool)
    for j, i in enumerate(idx):
        if i - 1 - K < 0:
            continue
        d = cl[i - 1] - cl[i - 1 - K]
        drift_ok[j] = (d > 0) if bool(isl[j]) else (d < 0)
    valid = np.isfinite(reg) & (idx - 1 - K >= 0)
    dual = drift_ok & calm & valid
    return idx, isl, dual, K


def raw_signals(m):
    """سیگنال‌های کارتِ خام (D1) — بدونِ هیچ گیتی."""
    w = m['w']
    idx, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    return idx, isl, np.ones(len(idx), bool), 0


def main():
    os.makedirs(OUT, exist_ok=True)
    verdict = json.load(open(VERDICT))
    census = json.load(open(CENSUS))
    cards = [mm['card'] for mm in verdict['members']]
    assert verdict['verdict'] == 'ACCEPT', verdict['verdict']
    assert cards == OFFICIAL_CARDS, f'اعضای رسمی عوض شده: {cards}'
    print(f"[verdict] {verdict['verdict']} RQS2={verdict['rqs2_score']} "
          f"members={cards}", flush=True)

    raws = {tf: B.load_raw(tf) for tf in B.CARDS}
    for tf, m in raws.items():
        sig = S5.sigma_series(m['cl'])
        # سلامتِ بازسازیِ σ: باید z=r/σ را عیناً بازتولید کند (بندِ s605)
        z_re = np.where(sig > 0, m['df']['close'].values * 0.0, np.nan)
        r = np.zeros(len(m['cl']))
        c = m['cl'].astype(np.float64)
        r[1:] = np.log(c[1:] / c[:-1])
        with np.errstate(divide='ignore', invalid='ignore'):
            z_re = np.where(sig > 0, r / sig, np.nan)
        ok = np.isfinite(m['z']) & np.isfinite(z_re)
        dz = float(np.max(np.abs(m['z'][ok] - z_re[ok]))) if ok.any() else 0.0
        assert dz < 1e-6, f'{tf}: بازسازیِ σ ناسالم — max|dz|={dz}'
        m['sigma'] = sig
        m['reg'] = {W: S5.regime_ratio(sig, W) for W in {89, 233}}
        print(f'[health] {tf}: max|dz|={dz:.2e} ✓', flush=True)

    for tf in B.CARDS:
        m = raws[tf]
        card = f'XAUUSD-{tf}'
        official = card in OFFICIAL_CARDS
        if tf == 'D1':
            idx, isl, sel, K = raw_signals(m)
            gate = None
        else:
            p = FROZEN[tf]
            idx, isl, sel, K = dual_signals(m, p['K'], p['W'])
            gate = dict(K_days=p['K'], K_bars=K, W=p['W'],
                        bars_per_day=B.BARS_PER_DAY[tf])
            # تطبیقِ سرشماری با آرتیفکتِ رسمی (ضدِ رگرسیونِ خاموش)
            assert int(sel.sum()) == census[tf]['n_dual'], \
                f"{tf}: n_dual={int(sel.sum())} != census {census[tf]['n_dual']}"
            print(f"[census-match] {tf}: n_dual={int(sel.sum())} ✓", flush=True)

        w = m['w']
        n = len(m['cl'])
        lo = max(0, n - TAIL)
        atr = m['atr']
        rows = []
        for j, i in enumerate(idx):
            if i < lo or not sel[j]:
                continue
            sl_pip = float(w['sl_k'] * atr[i])
            tp_pip = float(max(w['rr'] * sl_pip, sl_pip))   # ضدِ اشتباهِ #۸
            rows.append(dict(bar=int(i), time=int(m['df']['time'].values[i]),
                             dir='long' if bool(isl[j]) else 'short',
                             z=round(float(m['z'][i]), 8),
                             atr=round(float(atr[i]), 6),
                             sigma=round(float(m['sigma'][i]), 10),
                             reg=(None if gate is None else
                                  round(float(m['reg'][FROZEN[tf]['W']][i]), 8)),
                             sl_pip=round(sl_pip, 6), tp_pip=round(tp_pip, 6)))

        d = m['df']
        out = dict(
            tf=tf, card=card, official_member=official,
            note=('عضوِ رسمیِ استخرِ ACCEPT 83.1' if official else
                  'شاهدِ منفی — انتخاب‌گرِ رسمی این کارت را حذف کرد (margin 0.15)؛ وصل نشود'),
            params=dict(z_thr=w['z_thr'], mode=w['mode'], sl_k=w['sl_k'],
                        rr=w['rr'], hold=m['hold'], warmup=m['warmup'],
                        atr_p=34, lam=0.94),
            gate=gate,
            member_stats=(None if tf == 'D1' else
                          dict(n=census[tf]['n_member'], wr=census[tf]['wr'],
                               lift=census[tf]['lift'])),
            n_bars_total=int(n), tail_from=int(lo), tail_len=int(n - lo),
            candles=[dict(t=int(d['time'].values[i]),
                          o=round(float(d['open'].values[i]), 5),
                          h=round(float(d['high'].values[i]), 5),
                          l=round(float(d['low'].values[i]), 5),
                          c=round(float(d['close'].values[i]), 5))
                     for i in range(lo, n)],
            series=[dict(bar=int(i),
                         z=(None if not np.isfinite(m['z'][i]) else round(float(m['z'][i]), 8)),
                         atr=(None if not np.isfinite(atr[i]) else round(float(atr[i]), 6)),
                         sigma=(None if not np.isfinite(m['sigma'][i]) else round(float(m['sigma'][i]), 10)))
                    for i in range(lo, n)],
            signals=rows,
        )
        with open(f'{OUT}/{tf}.json', 'w') as fh:
            json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
        tag = 'OFFICIAL' if official else 'NEGATIVE-CONTROL'
        print(f'[saved] {OUT}/{tf}.json — {tag} · bars={n} tail={n - lo} '
              f'signals_in_tail={len(rows)}', flush=True)

    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
