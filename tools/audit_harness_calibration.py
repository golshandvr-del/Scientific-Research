# -*- coding: utf-8 -*-
"""
آزمونِ **کالیبراسیونِ هارنسِ ممیزی** — قبل از داوریِ هیچ لایه‌ای
================================================================================
پرسشِ این فایل یک چیز است و فقط یک چیز:

    «آیا داوری که ساختم، لایه‌ای که پروژه *قبلاً* با همین معیار سنجیده و
     حکمش را ثبت کرده، همان‌طور می‌خواند؟»

اگر جوابْ نه باشد، هر حکمی که این هارنس روی ۱۱۳ لایه صادر کند بی‌ارزش است —
و بدتر: **قابلِ‌باور به نظر می‌رسد**. مرجعِ کالیبراسیون:

    results/S382_WilliamsR_Xauusd_H4_rqs2-83.md
    → ACCEPT ، rqs2 = 83.5 ، rank_tier = A ، n = 869 ، card = XAUUSD_H4
      SL = 1.5×ATR(100) = 122.85 pip ، TP = 1.5×SL = 184.28 pip ، n_trials = 23755

چرا همین لایه انتخاب شد (و نه یک لایهٔ رد‌شده):
  · حکمش ACCEPT است، یعنی **همهٔ ده دروازه** را عبور کرده. یک لایهٔ REJECT فقط
    ثابت می‌کند «هارنسم لااقل یک دروازه را می‌بندد» — که آزمونِ ضعیفی است، چون
    هارنسِ خرابی که همه‌چیز را رد کند هم آن را پاس می‌کند. ACCEPT سخت‌ترین
    آزمونِ ممکن است: هر ده دروازه باید *درست* باز شوند.
  · هندسه، نمونه، `n_trials` و کارتش همه در سند **عددیِ صریح** ثبت شده‌اند، پس
    هیچ حدسی لازم نیست.

⚠️ انتظارِ واقع‌بینانه: نمرهٔ من نباید **عیناً** ۸۳.۵ شود. دو تفاوتِ صادقانه:
  ① بذر و تعدادِ جای‌گشت من (`seed=20260806, K=600`) با سند (`seed=20260805,
     K=2000`) یکی نیست ⇒ `perm_sd` و `perm_max` کمی جابه‌جا می‌شوند.
  ② شبیه‌سازِ من `engine/scalp_engine` است و سندِ S382 شبیه‌سازِ محلیِ خودش را
     داشت؛ هزینه و قاعدهٔ کندلِ مبهم یکی است ولی جزئیاتِ پیاده‌سازی نه.
معیارِ قبولی پس **همگراییِ حکم** است، نه تساویِ رقم:
    حکم = ACCEPT   و   |نمره − ۸۳.۵| ≤ ۱۲   و   n در بازهٔ ±۲۵٪ از ۸۶۹
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.audit_rqs2_rejudge import (  # noqa: E402
    load_card, judge_card, atr, PERM_K, SEED)

# ── مشخصاتِ قفل‌شدهٔ S382، عیناً از سندش ──
WILLR_P, WILLR_THR = 14, -13.0
ATR_P, SL_K, RR = 100, 1.5, 1.5
N_TRIALS = 23755
REF_VERDICT, REF_SCORE, REF_N = 'ACCEPT', 83.5, 869


def willr(df, p=WILLR_P):
    hh = df['high'].astype(float).rolling(p).max()
    ll = df['low'].astype(float).rolling(p).min()
    return -100.0 * (hh - df['close'].astype(float)) / (hh - ll).replace(0.0, np.nan)


def main():
    df = load_card('XAUUSD', 'H4')
    assert df is not None, 'XAUUSD_H4 missing'
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    print(f'card=XAUUSD-H4  bars={len(df)}  span={span:.2f}y  '
          f'first={df["dt"].iloc[0].date()}  last={df["dt"].iloc[-1].date()}')

    # هندسه: میانهٔ ATR(100) × ضریب — دقیقاً روشِ سند
    a = atr(df, ATR_P)
    sl_px = float(np.nanmedian(a)) * SL_K
    ps = 0.1                                    # pip طلا
    sl_pip = sl_px / ps
    tp_pip = sl_pip * RR
    print(f'median ATR(100)={np.nanmedian(a):.3f}  '
          f'SL={sl_pip:.2f}pip  TP={tp_pip:.2f}pip   '
          f'(سند: SL=122.85 / TP=184.28)')

    # سیگنال: گذر به بالای آستانه — رویداد، نه حالت
    w = willr(df)
    sig = ((w.shift(1) <= WILLR_THR) & (w > WILLR_THR)).fillna(False).to_numpy(bool)
    print(f'signals={int(sig.sum())}')

    r = judge_card('XAUUSD', 'H4', sig, np.zeros(len(df), bool),
                   sl_pip, tp_pip, max_hold=None, n_trials=N_TRIALS,
                   k=PERM_K, seed=SEED)

    print('\n── حکمِ هارنسِ من ──')
    for key in ('verdict', 'rqs2_score', 'n_trades', 'win_rate', 'net_profit',
                'profit_factor', 'rank_tier'):
        if key in r:
            print(f'  {key:14s} = {r[key]}')
    print('  gates:')
    for g, v in sorted((r.get('gates') or {}).items(),
                       key=lambda kv: int(kv[0][1:])):
        print(f'    {g:4s} {v}')

    ok_v = r.get('verdict') == REF_VERDICT
    ok_s = abs(float(r.get('rqs2_score', 0)) - REF_SCORE) <= 12.0
    ok_n = REF_N * 0.75 <= int(r.get('n_trades', 0)) <= REF_N * 1.25
    print(f'\nverdict match : {ok_v}  (mine={r.get("verdict")} ref={REF_VERDICT})')
    print(f'score  match : {ok_s}  (mine={r.get("rqs2_score")} ref={REF_SCORE})')
    print(f'n      match : {ok_n}  (mine={r.get("n_trades")} ref={REF_N})')
    print(f'\nCALIBRATION = {"PASS" if (ok_v and ok_s and ok_n) else "FAIL"}')

    os.makedirs(os.path.join(ROOT, 'results', '_audit_rename'), exist_ok=True)
    p = os.path.join(ROOT, 'results', '_audit_rename', 'calibration_s382.json')
    json.dump({'result': r, 'ref': {'verdict': REF_VERDICT, 'score': REF_SCORE,
                                    'n': REF_N},
               'pass': bool(ok_v and ok_s and ok_n),
               'sl_pip': sl_pip, 'tp_pip': tp_pip,
               'n_signals': int(sig.sum())},
              open(p, 'w'), ensure_ascii=False, indent=1, default=float)
    print(f'written -> {p}')


if __name__ == '__main__':
    main()
