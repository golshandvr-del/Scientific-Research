# -*- coding: utf-8 -*-
"""
S432 — احیای `S312 MidMonthDrift` روی کارت‌های `H1`+`M15` از راهِ **تجمیعِ تقویمی**
================================================================================
پیش‌ثبت: `results/S432_PREREG_S312_H1M15_POOLING.md` (پیش از هر عدد commit شد)
نامزد از: `results/_s432_priority/priority_rank.json` (رتبهٔ ۱، پس از دو اصلاحِ
          خود-گرفتهٔ `BUG-SCALEBIAS` و `BUG-SCALEBIAS-2`)

تشخیص (چرا این نامزد):
  همین سازوکار روی کارتِ `M30` حکمِ `ACCEPT` با `z=3.66` گرفته و **در سایت
  وصل است** ⇒ لبه **اثبات‌شده** است. کارتِ `H1` تنها در `H3` افتاده
  (`z=2.72` در برابرِ سدِ `3.09` ⇒ فقط ۰.۳۷σ کم) و `n=260` زیرِ سقفِ
  شیشه‌ایِ `n_required_for_h3 = 336.5` است ⇒ کمبودِ **توان**، نه نبودِ لبه.
  `M15` هم همان سازوکار با `n=129` و `z=1.71` است.
  تجمیع ⇒ `n = 260 + 129 = 389 > 336.5` ⇒ سقف ریاضیاً شکسته می‌شود.

⚠️ آنچه این اسکریپت **نمی‌کند** (و دلیلش):
  • هیچ جست‌وجوی `TP/SL` — چون `H9` از قبل پاس است (۸۵٪ امید پس از ۲× هزینه
    می‌ماند). درسِ `S430`: هندسه را وقتی عوض کن که `H9` مانع باشد، نه `H3`.
  • هیچ فیلترِ نو — چون فیلتر `n` را **کوچک** می‌کند و `z` را **پایین**
    می‌آورد ⇒ از سد دورتر می‌شویم نه نزدیک‌تر. این محاسبه است، نه سلیقه.
  ⇒ صفر پارامترِ جست‌وجو‌شده ⇒ هیچ چندگانگیِ نو.

هندسهٔ ارثی (از `s312_oos_check.py`، دست‌نخورده):
  `M15`: sl=tp=295 · max_hold=48        `H1`: sl=tp=395 · max_hold=24
  فیلترِ کیفیت: `close > EMA200` (روشن، همان حکم)
  قانونِ پایه: `day_of_month ∈ {10,13,20}` و `hour ∈ 1..12` ⇒ `LONG`
"""

from __future__ import annotations

import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from engine import indicators as ind                               # noqa: E402
from engine.rqs2_pool import pool_cards                            # noqa: E402
from strategies import s333_s79_pullback_revival as s333           # noqa: E402  (ثبتِ ASSETSِ per-TF)
from strategies.s351_verdict import build_null_side                # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_scan_S432')

# ---- قیدهای **پیش‌ثبت‌شده** (از سندِ PREREG؛ اینجا فقط بازتاب می‌شوند) ----
POOL_MEMBERS = ['XAUUSD_H1', 'XAUUSD_M15']   # `C2`: قفل — `M30` عمداً بیرون
SEED = 20260805
K_PERM = 2000                                # `C8`: حکمِ قبلی K=600 داشت
SPLIT_FRAC = 0.60
C5_MAX_MEMBER_SHARE = 0.75                   # دو عضو ⇒ سقفِ ۵۰٪ ناممکن است

# هندسهٔ ارثی — **جست‌وجو نشده**، از `s312_oos_check.py` عیناً
GEOM = {
    'XAUUSD_M15': dict(sl=295, tp=295, mh=48),
    'XAUUSD_M30': dict(sl=295, tp=295, mh=36),
    'XAUUSD_H1':  dict(sl=395, tp=395, mh=24),
}

# قانونِ پایهٔ S312 — صفر پارامترِ آزاد
DOM_SET = frozenset((10, 13, 20))
HOURS = frozenset(range(1, 13))
EMA_P = 200
WARMUP = 300

# ---- چندگانگیِ صادقانه ------------------------------------------------------
# `S312` در ممیزیِ اصلی `n_trials=149` داشت. آن هزینه **ارثی** است و باید
# پرداخت شود (نمی‌توان با عوض کردنِ اسکریپت از آن فرار کرد). خودِ تصمیمِ
# «تجمیعِ H1+M15» را هم یک درجهٔ آزادی می‌شماریم ⇒ ۱۴۹ × ۲ = ۲۹۸.
N_TRIALS_INHERITED = 298


def build_s312_layer(df):
    """
    ماسکِ ورودِ `S312` — بازتولیدِ **وفادارِ** `sim_strategies.S312_MidMonth_Long`
    با `quality_filter=True`.

    ⚠️ درسِ `S430` (باگِ بازتولید): آنجا فیلترِ `dip` را «۴ کندلِ نزولیِ پیاپی»
    فهمیدم در حالی که قانونِ واقعی جابه‌جاییِ خالص بود ⇒ نسخهٔ من ۱۰ برابر
    سخت‌گیرتر شد و نزدیک بود لایهٔ سالمی را «مرده» اعلام کنم. پس اینجا هر
    شرط را سطر-به-سطر از کلاسِ اصلی برداشتم:
        `dom ∈ {10,13,20}` و `hour ∈ 1..12` و `close > EMA200`
    فیلترِ `ATR` در پیکربندیِ حکم **بی‌اثر** است (`atr_lo=0`, `atr_hi=1e9`)
    پس عمداً پیاده نمی‌شود — افزودنش یک شرطِ همیشه-درست است و صرفاً
    توهمِ وفاداریِ بیشتر می‌دهد.
    """
    dt = df['dt']
    dom = dt.dt.day.to_numpy()
    hour = dt.dt.hour.to_numpy()
    ema = ind.ema(df['close'], EMA_P).to_numpy()
    close = df['close'].to_numpy(float)

    m_time = np.isin(dom, list(DOM_SET)) & np.isin(hour, list(HOURS))
    m_qual = close > ema
    sig = m_time & m_qual
    sig[:WARMUP] = False
    return sig


def _win_col(tr):
    if 'win' not in tr.columns:
        tr = tr.copy()
        tr['win'] = (tr['pnl_pip'].to_numpy() > 0).astype(int)
    return tr


def card_population(card, n_perm=K_PERM, verbose=True):
    """جمعیتِ یک عضوِ استخر = ماسکِ `S312` + هندسهٔ ارثیِ همان کارت."""
    g = GEOM[card]
    asset = 'XAUUSD'
    path = se.ASSETS[card]['file']
    if not os.path.exists(path):
        print(f'   [غایب] {path}', flush=True)
        return None

    df = se.load_data(path)
    n = len(df)
    close = df['close'].to_numpy(float)
    dt = df['dt'].values if 'dt' in df.columns else np.arange(n)

    sig = build_s312_layer(df)
    sl, tp, mh = g['sl'], g['tp'], g['mh']
    tr, _ = s333.evaluate(df, sig, card, sl, tp, mh)
    if tr is None or len(tr) < 3:
        return None
    tr = _win_col(tr)

    # ---- مبنای **اندازه‌گیری‌شده** روی همان کارت (نه عددِ فرضی) ----
    valid = np.where(np.isfinite(close))[0]
    valid = valid[valid >= WARMUP]
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    rng = np.random.default_rng(SEED)
    sl_price = sl * se.ASSETS[asset]['pip']
    null = build_null_side(df, asset, valid, np.full(n, sl_price),
                           nL, nS, n_perm, rng, verbose=verbose)

    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
    refs, wts = [], []
    for side, cnt in (('long', nL), ('short', nS)):
        u = null[side].get('uncond_wr')
        if u is not None and cnt > 0:
            refs.append(u * cnt)
            wts.append(cnt)
    ref = (sum(refs) / sum(wts)) if wts else None
    lift = (wr - ref) if ref is not None else None

    return dict(card=card, asset=asset, tr=tr, dt=dt, lift=lift,
                n=int(len(tr)), wr=wr, ref_wr=ref, null=null,
                n_long=nL, n_short=nS, n_base=int(sig.sum()),
                sl_pip=float(sl), tp_pip=float(tp), max_hold=int(mh),
                exp_pip=float(np.mean(tr['pnl_pip'])),
                bars=int(n))
