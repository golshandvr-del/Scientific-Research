# -*- coding: utf-8 -*-
"""
s660_adjudicate.py — داور نهایی S660: XAUUSD-H6، نامزد منجمد PREREG-2
================================================================================
اسناد حاکم (به ترتیب):
  results/S660_PREREG_EHLERS_MOMENTUM_CONTINUATION_XAUUSD.md   (مسیر C)
  results/S660_PREREG_ADDENDUM_NOVELTY_AUDIT.md                (سد دوگانه 408/644)
  results/S660_PREREG2_FROZEN_CANDIDATE_H6.md                  (نامزد منجمد + P1..P3)

**یک** اجرا روی کل ۱۵.۶ سال با split_bar = n//2 (هولدآوت = نیمهٔ دوم).

گاردهای ارثی:
  BUG-PERMK      perm_k = تعداد جای‌گشت‌ها (نه اندازهٔ نمونه).
  BUG-NULLUNCOND نال با هندسه/هولد خودِ نامزد؛ بی‌قید با allow_overlap=True
                 (تعریف «بی‌قید» بدون همپوشانی بیان‌پذیر نیست — گارد s434).
  BUG-SCOREKEY   کلید امتیاز `rqs2_score`؛ `failed` از gates مشتق می‌شود.
  BUG-ZBARAPPROX سد از خروجی موتور خوانده می‌شود، نه sqrt(2 ln N).
  BUG-PIPGUESS   pip از se.ASSETS.
  BUG-GEOMDRIFT  هندسه از JSON چک‌پوینت explore_H6.json خوانده می‌شود؛ اینجا
                 هیچ عدد هندسی hard-code نمی‌شود.
  قید ۲          n<30 ⇒ حکم داده نمی‌شود.

تله‌های کنترل (s434_null_model):
  ۱) k جای‌گشت = تعداد سیگنال نهایی همان سمت؛ ۲) کنترل عین سیگنال جز زمان؛
  ۳) استخر فقط کندل‌های واجد [warmup, n-mh-1).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import scalp_engine as se                        # noqa: E402
from engine.rqs2 import compute_rqs2                         # noqa: E402
from tools import s434_fast_data as fd                       # noqa: E402
from tools.s670_trendflex_fast import trendflex_fast         # noqa: E402
from tools.s660_explore import laguerre_rsi_fast, WARMUP, MAX_HOLD  # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s660_final')
os.makedirs(OUT, exist_ok=True)

SEED = 20260815
N_PERM = 600                       # ≥500 (درس S435 گام ۸۷)
N_TRIALS_FAMILY = 408              # پیش‌ثبت اصلی
N_TRIALS_STRICT = 644              # الحاقیه — سد سختگیرانه‌تر ملاک
TF = 'H6'
ASSET = 'XAUUSD'

# ── نامزد منجمد: پارامترهای سیگنال از PREREG-2، هندسه از JSON چک‌پوینت ──
GAMMA = 0.786
THR = 90.0
TFX_P = 21
_cellfp = os.path.join(ROOT, 'results', '_scan_S660', 'explore_H6.json')
_cells = json.load(open(_cellfp))['cells']
_cell = [c for c in _cells
         if c['gamma'] == GAMMA and c['thr'] == THR
         and c['tfx_p'] == TFX_P and c['rr'] == 1.5][0]
SL_PIP = float(_cell['sl_pip'])    # BUG-GEOMDRIFT: از همان منبع اسکن
TP_PIP = float(_cell['tp_pip'])


def build_signals(c: np.ndarray):
    LR = laguerre_rsi_fast(c, GAMMA)
    TFX = trendflex_fast(c, TFX_P)
    cl = (LR > THR) & (TFX > 0)
    cs = (LR < (100.0 - THR)) & (TFX < 0)
    le = cl & ~np.concatenate(([False], cl[:-1]))
    sh = cs & ~np.concatenate(([False], cs[:-1]))
    return le, sh


def main() -> int:
    d = fd.load_fast(ASSET, TF)
    df = fd.as_dataframe(d)
    n = len(df)
    split = n // 2
    print(f'src = {d["src"]}')
    print(f'n = {n:,} | split_bar = {split:,} | SL={SL_PIP:.4f} TP={TP_PIP:.4f}')

    c = df['close'].values.astype(np.float64)
    le, sh = build_signals(c)
    valid = np.zeros(n, bool)
    valid[WARMUP:n - MAX_HOLD - 1] = True
    le &= valid
    sh &= valid
    n_sig = int(le.sum() + sh.sum())
    print(f'سیگنال کل‌داده: long={int(le.sum())} short={int(sh.sum())}')

    trades = se.simulate_trades(df, le, sh, SL_PIP, TP_PIP, ASSET,
                                max_hold=MAX_HOLD, allow_overlap=False)
    n_tr = len(trades)
    wr = 100.0 * float((trades['pnl_pip'] > 0).mean())
    print(f'معاملات کل‌داده: n={n_tr} WR={wr:.3f}% '
          f'net={trades["pnl_pip"].sum():.1f}pip')
    if n_tr < 30:
        print('قید ۲: n<30 ⇒ MEASUREMENT-LIMITED — حکم داده نمی‌شود.')
        return 2

    # ══ مدل صفر کانونی (سه تله بسته) ═══════════════════════════════════════
    rng = np.random.default_rng(SEED)
    vidx = np.flatnonzero(valid)

    def _wr01(t):
        return float((t['pnl_pip'].values > 0).mean()) if len(t) else None

    null = {}
    z = np.zeros(n, bool)
    for side_name, side_mask in (('long', le), ('short', sh)):
        k_side = int(side_mask.sum())          # تلهٔ ۱: k = سیگنال نهایی سمت
        if k_side == 0:
            null[side_name] = dict(uncond_wr=None, perm_mean=None,
                                   perm_sd=None, perm_max=None, perm_k=0)
            continue
        # بی‌قید: هر کندل واجد، همان هندسه، allow_overlap=True (گارد s434)
        if side_name == 'long':
            t_unc = se.simulate_trades(df, valid, z, SL_PIP, TP_PIP, ASSET,
                                       max_hold=MAX_HOLD, allow_overlap=True)
        else:
            t_unc = se.simulate_trades(df, z, valid, SL_PIP, TP_PIP, ASSET,
                                       max_hold=MAX_HOLD, allow_overlap=True)
        uncond_wr = _wr01(t_unc)
        # جای‌گشت زمانی: k سیگنال در زمان تصادفی، عین هندسه (تلهٔ ۲)
        perm_wrs = []
        for _ in range(N_PERM):
            pick = rng.choice(vidx, size=k_side, replace=False)  # تلهٔ ۳
            pm = np.zeros(n, bool)
            pm[pick] = True
            if side_name == 'long':
                tp_ = se.simulate_trades(df, pm, z, SL_PIP, TP_PIP, ASSET,
                                         max_hold=MAX_HOLD,
                                         allow_overlap=False)
            else:
                tp_ = se.simulate_trades(df, z, pm, SL_PIP, TP_PIP, ASSET,
                                         max_hold=MAX_HOLD,
                                         allow_overlap=False)
            w = _wr01(tp_)
            if w is not None:
                perm_wrs.append(w)
        pa = np.asarray(perm_wrs)
        null[side_name] = dict(
            uncond_wr=uncond_wr,
            perm_mean=float(pa.mean()),
            perm_sd=float(pa.std(ddof=1)),
            perm_max=float(pa.max()),
            perm_k=int(pa.size),               # BUG-PERMK
        )
        print(f'null[{side_name}]: uncond={uncond_wr:.4f} '
              f'perm_mean={pa.mean():.4f} sd={pa.std(ddof=1):.4f} '
              f'max={pa.max():.4f} k={pa.size}', flush=True)

    # ══ داوری — دو سد n_trials، حکم با سختگیرانه‌تر ═══════════════════════
    results = {}
    for tag, ntr in (('family_408', N_TRIALS_FAMILY),
                     ('strict_644', N_TRIALS_STRICT)):
        r = compute_rqs2(trades, ASSET, sl_pip=SL_PIP, tp_pip=TP_PIP,
                         bar_time=df['time'].values, null=null,
                         n_trials=ntr, split_bar=split,
                         close=df['close'].values)
        results[tag] = r
        m = r.get('metrics') or {}
        print(f'\n===== n_trials={ntr} ({tag}) =====')
        print('verdict :', r.get('verdict'))
        print('score   :', r.get('rqs2_score'))              # BUG-SCOREKEY
        print('gates   :', r.get('gates'))
        print('z       :', m.get('skill_z'),
              '| p_perm:', m.get('skill_p_perm'),
              '| z_luck_bound:', m.get('z_luck_bound'))      # BUG-ZBARAPPROX
        print('lift_pp :', m.get('skill_lift_pp'))

    # ذخیرهٔ خام برای MD رسمی
    def _clean(o):
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_clean(v) for v in o]
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return o

    payload = dict(src=d['src'], n=n, split_bar=split, n_signals=n_sig,
                   n_trades=n_tr, wr=wr, sl_pip=SL_PIP, tp_pip=TP_PIP,
                   gamma=GAMMA, thr=THR, tfx_p=TFX_P, max_hold=MAX_HOLD,
                   seed=SEED, n_perm=N_PERM, null=_clean(null),
                   results={k: _clean(v) for k, v in results.items()})
    fp = os.path.join(OUT, 'verdict_H6.json')
    with open(fp, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f'\nذخیره شد: {fp}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
