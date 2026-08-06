# -*- coding: utf-8 -*-
"""
ممیزیِ **لایهٔ دومِ آرشیو** — `S70` گیتِ سودآوریِ walk-forward برای هر دارایی
================================================================================
لایه: `results/S70_PerAsset_ProfitabilityGate_NetProfit_13436.md`
کد  : `strategies/s70_perasset_profitability_gate.py`
منطق: معاملاتِ S69 را می‌گیرد و هر معامله را فقط وقتی اجازه می‌دهد که مجموعِ
      pnl در `K=40` معاملهٔ **قبلیِ همان دارایی** مثبت بوده باشد (پنجرهٔ لغزان،
      کاملاً forward-safe). سیاستِ warmup: `gold_only`.

════════════════════════════════════════════════════════════════════════════
سه تصمیمِ صحتِ مخصوصِ این لایه
════════════════════════════════════════════════════════════════════════════

① **این لایه سیگنالِ نو نمی‌سازد؛ یک فیلترِ انتخابِ زیرمجموعه است.**
   پس مدلِ صفرِ درست، «ورودِ تصادفی روی زمان» **به‌تنهایی** نیست: هر فیلتری با
   کوچک‌کردنِ `n` واریانسِ `WR` را بالا می‌برد و به‌شانس لیفتِ مثبت نشان می‌دهد
   (§۲.۵ اسپک، آزمونِ خواهرِ فیلترها). اما اسپکِ `H3` مبنای کانونی را
   «جای‌گشتِ زمانی با همان تعدادِ سیگنال» تعریف می‌کند و همان اجرا می‌شود؛
   عددِ زیرمجموعهٔ تصادفی **جداگانه** گزارش می‌شود تا خواننده بتواند سهمِ
   «کوچک‌شدنِ نمونه» را از «مهارتِ گیت» تفکیک کند. پنهان نمی‌شود.

② **`n_trials` باید هزینهٔ جست‌وجویِ *ارثی* را هم بپردازد.** S70 روی خروجیِ
   S69 سوار است، پس تمامِ جست‌وجویی که S69 را ساخت در سابقهٔ این لایه هست،
   به‌علاوهٔ انتخابِ `K` و آستانه و سیاستِ warmup. کم‌شمردنش دقیقاً «دور زدنِ
   معیار» است (اشتباهِ رایجِ ۸) ⇒ فالبکِ بزرگ‌ترِ `N_TRIALS`.

③ **هر دارایی یک کارتِ مستقل** (قانونِ MTF). سندِ S70 عددِ `+13,436$` را
   جمعِ چهار دارایی گزارش کرده بود؛ RQS2 لایه را می‌سنجد نه سبد را.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import rqs2 as R                        # noqa: E402
from tools.audit_rqs2_rejudge import (              # noqa: E402
    load_card, bar_time_of, PERM_K, SEED)
from tools.audit_fast_null import build_null_fast   # noqa: E402
from tools.audit_runner import save_verdict, summarize  # noqa: E402

LAYER_FILE = 'S70_PerAsset_ProfitabilityGate_NetProfit_13436.md'
TF = 'M15'
MAX_HOLD = 48
PIP = {'XAUUSD': 0.1, 'EURUSD': 0.0001, 'AUDUSD': 0.0001}

GATE_K = 40                 # عیناً پارامترِ سندِ لایه
GATE_THRESHOLD = 0.0
N_TRIALS = 6000             # S69 (4000) + انتخابِ K/آستانه/warmup  ⇒ بزرگ‌تر
CARDS = ['XAUUSD', 'EURUSD', 'AUDUSD']


def apply_gate(tr: pd.DataFrame) -> np.ndarray:
    """
    گیتِ لغزانِ سودآوری — بازتولیدِ دقیقِ منطقِ سندِ لایه.

    برای معاملهٔ `i` (به ترتیبِ زمانِ خروج)، مجموعِ `pnl` معاملاتِ
    `[i-K, i-1]` سنجیده می‌شود. اگر `> threshold` بود اجازه می‌دهد.
    معاملاتِ warmup (کمتر از K سابقه) طبقِ `gold_only` فقط برای طلا مجازند.

    ⚠️ نکتهٔ forward-safety: پنجره **اکیداً** به `i-1` ختم می‌شود. اگر خودِ
    `i` در پنجره بیاید، گیت از نتیجهٔ معامله‌ای که هنوز رخ نداده استفاده
    می‌کند — نشتیِ آینده‌ای که کلِ لایه را بی‌اعتبار می‌کند.
    """
    p = tr['pnl_pip'].to_numpy(float)
    n = len(p)
    allow = np.zeros(n, bool)
    for i in range(n):
        if i < GATE_K:
            allow[i] = True          # warmup: gold_only در سطحِ کارت اعمال می‌شود
            continue
        allow[i] = float(p[i - GATE_K:i].sum()) > GATE_THRESHOLD
    return allow


def judge_asset(asset: str, warmup_allowed: bool) -> dict:
    csv = os.path.join(ROOT, 'results', f'_s69_trades_{asset}.csv')
    if not os.path.exists(csv):
        return {'card': f'{asset}-{TF}', 'verdict': 'INCOMPLETE',
                'rqs2_score': 0.0, 'reason': 'S69 trades not available'}
    df = load_card(asset, TF)
    if df is None:
        return {'card': f'{asset}-{TF}', 'verdict': 'INCOMPLETE',
                'rqs2_score': 0.0, 'reason': 'card data missing'}

    t = pd.read_csv(csv)
    ps = PIP[asset]
    tr = pd.DataFrame({
        'entry_bar': t['entry_bar'].astype(int),
        'exit_bar': t['exit_bar'].astype(int),
        'outcome': t['outcome'],
        'pnl_pip': t['pnl'].astype(float) / ps,
        'sl_pip': t['sl_dist'].astype(float) / ps,
        'direction': t['direction'],
    }).sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    win = tr['outcome'] == 'win'
    rr_obs = (tr.loc[win, 'pnl_pip'] / tr.loc[win, 'sl_pip']).replace(
        [np.inf, -np.inf], np.nan).dropna()
    rr_med = float(rr_obs.median()) if len(rr_obs) else 1.0
    tr['tp_pip'] = tr['sl_pip'] * rr_med

    allow = apply_gate(tr)
    if not warmup_allowed:
        allow[:GATE_K] = False       # سیاستِ gold_only برای کارت‌های غیرِطلا
    gated = tr.loc[allow].reset_index(drop=True)

    print(f'  {asset}: raw n={len(tr)} -> gated n={len(gated)} '
          f'({100.0*len(gated)/max(1,len(tr)):.1f}% kept)  rr_med={rr_med:.2f}',
          flush=True)
    if len(gated) < 10:
        return {'card': f'{asset}-{TF}', 'verdict': 'REJECT', 'rqs2_score': 0.0,
                'reason': f'gate left only {len(gated)} trades',
                'n_trades': int(len(gated))}

    sl_med = float(np.nanmedian(gated['sl_pip']))
    tp_med = float(np.nanmedian(gated['tp_pip']))
    n_by_side = {s: int((gated['direction'] == s).sum())
                 for s in ('long', 'short')}

    nul = {}
    for side in ('long', 'short'):
        if n_by_side[side] <= 0:
            nul[side] = {}
            continue
        nb = build_null_fast(df, asset, sl_med, tp_med, MAX_HOLD, side,
                             n_by_side[side], k=PERM_K, seed=SEED)
        nul[side] = nb or {}
        if nb:
            print(f'    null[{side}] uncond={nb["uncond_wr"]:.2f} '
                  f'perm_mean={nb["perm_mean"]:.2f} sd={nb["perm_sd"]:.2f}',
                  flush=True)

    bt = bar_time_of(df)
    r = R.compute_rqs2(gated, asset, sl_pip=sl_med, tp_pip=tp_med,
                       bar_time=bt, null=nul, n_trials=N_TRIALS,
                       split_bar=int(len(df) * 0.70),
                       close=df['close'].to_numpy(float))
    r['card'] = f'{asset}-{TF}'
    r['gate_kept_pct'] = round(100.0 * len(gated) / max(1, len(tr)), 1)
    r['rr_med_estimated'] = rr_med
    return r


def main():
    per_card = []
    for asset in CARDS:
        print(f'\n══ judging {asset}-{TF} ══', flush=True)
        r = judge_asset(asset, warmup_allowed=(asset == 'XAUUSD'))
        per_card.append(r)
        print('  ' + summarize(r), flush=True)
        p = save_verdict(LAYER_FILE, per_card, {
            'gate': f'rolling K={GATE_K} sum>{GATE_THRESHOLD}, warmup=gold_only',
            'trade_source': 'S69 reproduced trades (bit-exact vs archive)',
            'max_hold': MAX_HOLD, 'n_trials': N_TRIALS,
            'null_solver': 'vectorized (16/16 exact vs official engine)'})
        print(f'  saved -> {p}', flush=True)


if __name__ == '__main__':
    main()
