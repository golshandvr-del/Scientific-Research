# -*- coding: utf-8 -*-
"""
S570 — آزمونِ تأییدیِ تک‌شاتِ S323 روی دادهٔ کاملِ ۱۵.۶ ساله
================================================================================

پیش‌ثبت: `results/S570_PREREG_s323_fulldata_confirmatory.md` (کامیتِ 4bea6234،
**قبل** از اجرای این فایل). خلاصهٔ عهد:

  · هیچ جست‌وجویی نیست — پیکربندی منجمدِ بایگانی، بیت‌به‌بیت از s357.
  · آزمونِ حاکم فقط `XAUUSD-M30 × backtested` است؛ بقیهٔ TFها اکتشافی/توصیفی.
  · n_trials صادقانه = ۲۸۰۰ (تاریخچهٔ s323+s323c+s358..s360)، تنش = ۵۶۰۰.
  · EURUSD مطلقاً آزموده نمی‌شود (استثنای صریحِ کاربر).
  · دادهٔ کامل از `tools/s434_fast_data.py` — `src` هر کارت در خروجی ثبت می‌شود
    تا دامِ E-16 (دادهٔ کوتاهِ data/*.csv) اثباتاً دور زده شده باشد.

چرا این فایل به‌جای بازنویسی، **از s357 وارد می‌کند**: هر بازنویسیِ منطقِ سیگنال
یا مدلِ صفر، یک درجهٔ آزادیِ پنهانِ جدید است. با import، حکمِ S570 با حکمِ S357
بیت‌به‌بیت هم‌پروتکل می‌ماند و تنها متغیرِ مستقل «طولِ داده» است — همان چیزی که
فرضیه دربارهٔ آن است.

تشخیصِ رژیم (بندِ ۶.۳ پیش‌ثبت): WR/lift به تفکیکِ چهار پنجرهٔ از‌پیش‌اعلام‌شده
گزارش می‌شود تا drift-riding از ساختارِ واقعی تمیز داده شود.

اجرا:
    python3 strategies/s570_s323_fulldata_retest.py --cards XAUUSD-M30   # حاکم
    python3 strategies/s570_s323_fulldata_retest.py                      # همه (اکتشافی)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, '.')

import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs2 as R2
from tools import s434_fast_data as fd

# منطقِ منجمد — وارد می‌شود، بازنویسی نمی‌شود
from strategies.s357_s323_v24_rejudge import (
    DEPLOYED_CFG, TF_FALLBACK, SEEDS, P_BAR,
    signals_backtested, signals_deployed, build_null, empirical_p,
)

import warnings
warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════════
# ثابت‌های پیش‌ثبت‌شدهٔ S570 (بندهای ۴ و ۵ پیش‌ثبت)
# ═══════════════════════════════════════════════════════════════════════════
PERM_K = 2000
N_TRIALS_HONEST = 2800
N_TRIALS_STRESS = 5600
OUT_DIR = 'results/_s570_s323_fulldata'

# فقط طلا — استثنای صریحِ کاربر. M30 حاکم است و اول اجرا می‌شود.
ALL_CARDS = ['XAUUSD-M30', 'XAUUSD-M15', 'XAUUSD-H1',
             'XAUUSD-M5', 'XAUUSD-M1', 'XAUUSD-H4', 'XAUUSD-D1']
GOVERNING = ('XAUUSD-M30', 'backtested')

# پنجره‌های رژیم — بندِ ۶.۳ پیش‌ثبت، اعلام‌شده پیش از دیدنِ هر عدد
REGIMES = [
    ('bull_2011_2013', '2011-01-01', '2013-01-31'),
    ('bear_2013_2015', '2013-02-01', '2015-12-31'),
    ('range_2016_2019', '2016-01-01', '2019-05-31'),
    ('bull_2019_2026', '2019-06-01', '2026-12-31'),
]


def cfg_for(card: str) -> dict:
    if card in DEPLOYED_CFG:
        return dict(DEPLOYED_CFG[card], _source='frozen')
    tf = card.split('-')[1]
    src, mh = TF_FALLBACK[tf]
    return dict(DEPLOYED_CFG[src], maxHold=mh, _source=f'inherited:{src}')


def load_full(asset: str, tf: str):
    """دادهٔ کامل از لایهٔ سریعِ S434؛ H4 از H1 بازنمونه می‌شود (mt5_full H4 ندارد)."""
    if tf == 'H4':
        d = fd.load_fast(asset, 'H1')
        df = fd.as_dataframe(d)
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
        g = df.set_index('dt').resample('4h', origin='epoch', offset='0h')
        out = pd.DataFrame({
            'open': g['open'].first(), 'high': g['high'].max(),
            'low': g['low'].min(), 'close': g['close'].last(),
            'volume': g['volume'].sum(),
        }).dropna().reset_index()
        out['time'] = (out['dt'].astype('int64') // 10**9).astype('int64')
        return out, d['src'] + ' (resampled H1→H4)'
    d = fd.load_fast(asset, tf)
    df = fd.as_dataframe(d)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df, d['src']


def regime_breakdown(tr: pd.DataFrame, df: pd.DataFrame):
    """WR و n به تفکیکِ پنجره‌های از‌پیش‌اعلام‌شده — تشخیصِ drift-rider."""
    if tr is None or not len(tr):
        return {}
    # زمانِ ورودِ هر معامله
    ent_bar = tr['entry_bar'].values if 'entry_bar' in tr.columns else None
    if ent_bar is None:
        return {'note': 'entry_bar absent'}
    t = pd.to_datetime(df['time'].values[ent_bar.astype(int)], unit='s', utc=True)
    win = (tr['pnl_pip'].values > 0)
    out = {}
    for name, a, b in REGIMES:
        m = (t >= pd.Timestamp(a, tz='UTC')) & (t <= pd.Timestamp(b, tz='UTC'))
        n = int(m.sum())
        out[name] = dict(n=n, wr=round(100.0 * win[m].mean(), 2) if n else None)
    return out


def run_card(card: str, variant: str, k_perm: int) -> dict:
    asset, tf = card.split('-')
    t0 = time.time()
    df, src = load_full(asset, tf)
    cfg = cfg_for(card)

    atr14 = ind.atr(df, 14).values
    pip = se.ASSETS[asset]['pip']
    atr_pip_med = float(np.nanmedian(atr14[260:]) / pip)
    sl = round(cfg['slMult'] * atr_pip_med, 1)
    tp = round(cfg['tpMult'] * atr_pip_med, 1)
    mh = int(cfg['maxHold'])

    # نگاشتِ نامِ cfg به قراردادِ signals_backtested (کلیدهای snake_case آنجا
    # مستقیم از cfg خوانده می‌شوند با نام‌های camelCase — s357 همین‌طور صدا می‌زد)
    if variant == 'backtested':
        sig = signals_backtested(df, asset, dict(
            nearMax=cfg['nearMax'], roomMin=cfg['roomMin'], rsiMax=cfg['rsiMax'],
            slopeMin=cfg['slopeMin'], adxMin=cfg['adxMin'], golden=cfg['golden'],
            hLo=cfg['hLo'], hHi=cfg['hHi'],
        ))
    else:
        sig = signals_deployed(df, cfg)
    n_sig = int(sig.sum())

    governing = (card, variant) == GOVERNING
    print(f"\n=== {card} [{variant}]{' ⚖️ GOVERNING' if governing else ' (exploratory)'} "
          f"src={src}\n    bars={len(df)} span={df['dt'].iloc[0].date()}→"
          f"{df['dt'].iloc[-1].date()} SL={sl} TP={tp} RR={tp/sl:.3f} mh={mh} "
          f"signals={n_sig} ({time.time()-t0:.0f}s)", flush=True)

    base = dict(session='S570', card=card, asset=asset, tf=tf, variant=variant,
                governing=governing, data_src=src, bars=len(df),
                span=[str(df['dt'].iloc[0]), str(df['dt'].iloc[-1])],
                cfg={k: v for k, v in cfg.items()},
                sl_pip=sl, tp_pip=tp, rr=round(tp / sl, 4), maxhold=mh,
                n_signals=n_sig)
    if n_sig < 5:
        return dict(base, status='NO_SIGNAL')

    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 5:
        return dict(base, status='NO_TRADES', n_trades=0 if tr is None else len(tr))

    n = len(tr)
    wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / n
    close = df['close'].values.astype(float)
    bar_time = df['time'].values
    split_bar = int(len(df) * 0.60)

    rec = dict(base, status='JUDGED', n_trades=n, wr_obs=round(wr_obs, 2),
               regimes=regime_breakdown(tr, df), seeds={})
    print(f"    n_trades={n} WR={wr_obs:.2f}% regimes={rec['regimes']}", flush=True)

    for seed in SEEDS:
        null, draws = build_null(df, asset, sig, sl, tp, mh, k_perm, seed)
        p_emp, n_ge = empirical_p(draws, wr_obs)
        out = {}
        for label, nt in (('honest', N_TRIALS_HONEST), ('stress', N_TRIALS_STRESS)):
            r = R2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp, bar_time=bar_time,
                                close=close, null=null, n_trials=nt,
                                split_bar=split_bar)
            out[label] = dict(verdict=r.get('verdict'), score=r.get('rqs2_score'),
                              gates=r.get('gates'), metrics=r.get('metrics'),
                              notes=r.get('notes'))
        out['null'] = {k: null['long'][k] for k in
                       ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_max', 'perm_k')}
        out['p_empirical'] = round(p_emp, 6)
        out['n_draws_ge_obs'] = n_ge
        out['honest_accept'] = bool(out['honest']['verdict'] == 'ACCEPT'
                                    and p_emp <= P_BAR)
        rec['seeds'][str(seed)] = out
        m0 = out['honest']['metrics']
        g = out['honest']['gates']
        gl = ''.join('1' if g.get(k) else ('?' if g.get(k) is None else '0')
                     for k in R2.GATE_NAMES)
        print(f"  seed={seed} K={out['null']['perm_k']} | "
              f"null={out['null']['uncond_wr']:.2f} lift={m0.get('skill_lift_pp')} "
              f"z={m0.get('skill_z')} p_emp={p_emp:.6f} ({n_ge}/{out['null']['perm_k']}) | "
              f"honest={out['honest']['verdict']}({out['honest']['score']}) "
              f"stress={out['stress']['verdict']}({out['stress']['score']}) G[{gl}]",
              flush=True)

    rec['all_seeds_accept'] = all(v['honest_accept'] for v in rec['seeds'].values())
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default=','.join(ALL_CARDS))
    ap.add_argument('--variant', default='backtested',
                    choices=['deployed', 'backtested', 'both'])
    ap.add_argument('--k', type=int, default=PERM_K)
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    cards = [c.strip() for c in a.cards.split(',') if c.strip()]
    assert all(c.startswith('XAUUSD') for c in cards), 'EURUSD ممنوع (استثنای کاربر)'
    variants = ['backtested', 'deployed'] if a.variant == 'both' else [a.variant]

    print(f"S570 — آزمونِ تأییدیِ S323 روی دادهٔ کامل | cards={cards} "
          f"variants={variants} K={a.k} seeds={SEEDS} "
          f"n_trials={N_TRIALS_HONEST}/{N_TRIALS_STRESS}", flush=True)

    for card in cards:
        for variant in variants:
            fp = os.path.join(OUT_DIR, f"{card}_{variant}.json")
            if os.path.exists(fp):
                print(f"  ↷ skip {fp} (checkpoint exists)", flush=True)
                continue
            try:
                rec = run_card(card, variant, a.k)
            except Exception as e:  # noqa: BLE001
                rec = dict(card=card, variant=variant, status='ERROR', error=repr(e))
                print(f"  !! {card}[{variant}] ERROR {e!r}", flush=True)
            with open(fp, 'w', encoding='utf-8') as fh:
                json.dump(rec, fh, ensure_ascii=False, indent=1, default=str)
            print(f"  → wrote {fp}", flush=True)

    print("\nDONE", flush=True)


if __name__ == '__main__':
    main()
