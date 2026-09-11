# -*- coding: utf-8 -*-
"""
s664_adjudicate.py — داور نهایی S664: XAUUSD-H8، تک‌کارت منجمد PREREG-2
================================================================================
اسناد حاکم:
  results/S664_PREREG_ENGLE_SHOCK_THINTAIL_REGIME_XAUUSD.md  (a246d7cc، مسیر C)
  results/S664_PREREG2_FROZEN_SINGLE_H8_W89.md               (تک‌کارت H8 W=89)
**یک** اجرا روی کل ۱۵.۶ سال mt5_full با split_bar = n//2 (هولدآوت = نیمهٔ دوم).
معماری عیناً s660_adjudicate.py (اثبات‌شده S660) — فقط سیگنال عوض شده:
  شوک انگل |z|≥2.618 (RiskMetrics) + گیت K_t ≤ median_233(K) با K=excess kurt(z, W=89).
گاردهای ارثی: PERMK/NULLUNCOND/SCOREKEY/ZBARAPPROX/PIPGUESS/GEOMDRIFT/WRUNITS/قید۲/E-16.
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
from tools.s664_explore import build_signals as _bs, WARMUP, MAX_HOLD  # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s664_final')
os.makedirs(OUT, exist_ok=True)

SEED = 20260819
N_PERM = 600                       # ≥500 (درس S435 گام ۸۷)
N_TRIALS_FAMILY = 505              # بدهی خانوادگی بلوک S66x
N_TRIALS_STRICT = 741              # سخت‌گیرانه
TF = 'H8'
ASSET = 'XAUUSD'
W = 89                             # منجمد PREREG-2

_cellfp = os.path.join(ROOT, 'results', '_scan_S664', 'explore_H8.json')
_cells = json.load(open(_cellfp))['cells']
_cell = [c for c in _cells if c['W'] == W and c['rr'] == 1.0][0]
SL_PIP = float(_cell['sl_pip'])    # BUG-GEOMDRIFT: از همان منبع اسکن
TP_PIP = float(_cell['tp_pip'])


def build_signals(c: np.ndarray, valid: np.ndarray):
    S = _bs(c, W, valid)          # gated = شوک ∧ دم‌نازک (لبه، valid داخل)
    return S['gated']


def main() -> int:
    d = fd.load_fast(ASSET, TF)
    df = fd.as_dataframe(d)
    n = len(df)
    split = n // 2
    print(f'src = {d["src"]}')
    assert 'mt5_full' in d['src'], f'E-16! {d["src"]}'
    print(f'n = {n:,} | split_bar = {split:,} | SL={SL_PIP:.4f} TP={TP_PIP:.4f}')

    c = df['close'].values.astype(np.float64)
    valid = np.zeros(n, bool)
    valid[WARMUP:n - MAX_HOLD - 1] = True
    le, sh = build_signals(c, valid)
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
        # BUGFIX (واحد): ساختار کانونی null «درصد» می‌خواهد (s434 خط ۹۳: ×100).
        # نسخهٔ اول کسر ۰..۱ برمی‌گرداند ⇒ lift جعلی ۴۳pp و z=165. اصلاح شد.
        return float(100.0 * (t['pnl_pip'].values > 0).mean()) if len(t) else None

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
    for tag, ntr in (('family_505', N_TRIALS_FAMILY),
                     ('strict_741', N_TRIALS_STRICT)):
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
                   W=W, theta=2.618, max_hold=MAX_HOLD,
                   seed=SEED, n_perm=N_PERM, null=_clean(null),
                   results={k: _clean(v) for k, v in results.items()})
    fp = os.path.join(OUT, 'verdict_H8.json')
    with open(fp, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f'\nذخیره شد: {fp}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
