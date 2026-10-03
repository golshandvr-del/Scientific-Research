# -*- coding: utf-8 -*-
"""S572 — صادرکنندهٔ مرجعِ عددیِ پریتی (TS ↔ Python) روی XAUUSD-M30 و H1.

چرا: سیم‌کشیِ یک لایه یعنی ادعای اینکه «کارتی که روی سایت روشن می‌شود همان
چیزی است که RQS2 پذیرفت». این ادعا فقط اگر پورت با **عددِ اندازه‌گیری‌شده**
سنجیده شود معتبر است. این ابزار همان مرجع را می‌سازد:

  ۱) مجموعهٔ **شمارهٔ کندلِ سیگنال‌ها** (نه فقط تعدادشان) برای هر عضو.
  ۲) n_signals · هندسهٔ آینه‌ای SL/TP (pip) · maxHold.
  ۳) ۴۰۰ کندلِ آخرِ سری‌های میانی (support/resistance/atr/ema50/ema200/rsi/adx)
     برای عیب‌یابیِ تفصیلیِ پورت.

گاردِ سلامت: n_signals باید عیناً members.json را بازتولید کند
(M30: 156 · H1: 37). وگرنه ابزار **سخت شکست می‌خورد**.

اجرا: python3 tools/export_s572_parity.py
خروجی: results/_s572_parity/{XAUUSD_M30,XAUUSD_H1}.json
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

from engine import scalp_engine as se
from engine import indicators as ind
from strategies.s357_s323_v24_rejudge import DEPLOYED_CFG, signals_backtested

OUT_DIR = 'results/_s572_parity'
MEMBERS = {'XAUUSD-M30': 156, 'XAUUSD-H1': 37}   # از results/_s572_mirror/members.json


def load_df(asset: str, tf: str) -> tuple[pd.DataFrame, str]:
    """مخزن فایل‌های mt5_full را فشرده (.csv.gz) نگه می‌دارد؛ همان را می‌خوانیم."""
    import gzip
    src = f'data/mt5_full/{asset}_{tf}.csv.gz'
    assert os.path.exists(src), f'E-16 GUARD: {src} نیست'
    with gzip.open(src, 'rt') as f:
        df = pd.read_csv(f)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df, src


def build_reference(card: str) -> dict:
    asset, tf = card.split('-')
    df, src = load_df(asset, tf)
    cfg = DEPLOYED_CFG[card]

    atr14 = ind.atr(df, 14).values
    pip = se.ASSETS[asset]['pip']
    atr_pip_med = float(np.nanmedian(atr14[260:]) / pip)
    sl = round(cfg['tpMult'] * atr_pip_med, 1)   # آینه: SL = tpMult قدیم
    tp = round(cfg['slMult'] * atr_pip_med, 1)   # آینه: TP = slMult قدیم
    assert tp >= sl, f'{card}: mirror must give TP>=SL (got SL={sl} TP={tp})'

    sig = signals_backtested(df, asset, dict(
        nearMax=cfg['nearMax'], roomMin=cfg['roomMin'], rsiMax=cfg['rsiMax'],
        slopeMin=cfg['slopeMin'], adxMin=cfg['adxMin'], golden=cfg['golden'],
        hLo=cfg['hLo'], hHi=cfg['hHi']))

    # ⚠️ عددِ منتشرشدهٔ members.json (۱۵۶/۳۷) تعدادِ **معامله پس از FIFO** است، نه
    #    تعدادِ سیگنالِ خام. هندسهٔ آینه‌ای + allow_overlap=False همان چیزی است که
    #    حکم رویش صادر شد؛ پس گاردِ سلامت روی n_trades است نه n_signals.
    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=int(cfg['maxHold']), allow_overlap=False)
    n_sig = int(sig.sum())
    n_tr = int(len(tr))
    health = (n_tr == MEMBERS[card])
    print(f'{card}: n_signals={n_sig} n_trades={n_tr} (pub {MEMBERS[card]}) '
          f'SL={sl} TP={tp} (RR={tp/sl:.2f}) mh={cfg["maxHold"]} '
          f'health={"OK" if health else "FAIL"}', flush=True)

    # ── سری‌های میانیِ ۴۰۰ کندلِ آخر برای عیب‌یابیِ تفصیلی ──────────────────
    from engine import structure as st
    tol = 0.0015
    piv = st.pivots(df, left=6, right=6)
    sr = st.sr_levels(df, piv, tol=tol, expiry=1500)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    rsi14 = ind.rsi(df['close'], 14).values
    adx_arr, _, _ = ind.adx(df, 14)
    adx_arr = np.nan_to_num(adx_arr.values, nan=0.0)
    close = df['close'].values
    a = np.where(atr14 > 0, atr14, np.nan)
    slope = np.full(len(df), np.nan)
    slope[10:] = (ema50[10:] - ema50[:-10]) / a[10:]
    slope = np.nan_to_num(slope, nan=0.0)

    def rnd(arr, k=5):
        return [None if not np.isfinite(x) else round(float(x), k) for x in arr[-400:]]

    return {
        'card': card, 'bars': int(len(df)), 'data_src': src,
        'frozen': {
            'nearMax': cfg['nearMax'], 'roomMin': cfg['roomMin'], 'rsiMax': cfg['rsiMax'],
            'slopeMin': cfg['slopeMin'], 'adxMin': cfg['adxMin'],
            'golden': cfg['golden'], 'hLo': cfg['hLo'], 'hHi': cfg['hHi'],
            'slMult': cfg['slMult'], 'tpMult': cfg['tpMult'], 'maxHold': cfg['maxHold'],
            'pivotLen': cfg['pivotLen'], 'mirror_sl_pip': sl, 'mirror_tp_pip': tp,
            'pip_size': pip, 'entry': 'open_next_bar', 'side': 'long',
        },
        'counts': {'n_signals': n_sig, 'n_trades': n_tr},
        'signal_bars': [int(x) for x in np.flatnonzero(sig)],
        'trade_entry_bars': [int(b) for b in tr['entry_bar'].values] if n_tr else [],
        'tail': {
            'from_index': int(len(df) - 400),
            'support': rnd(sr['support'].values),
            'resistance': rnd(sr['resistance'].values),
            'atr14': rnd(atr14),
            'ema50': rnd(ema50),
            'ema200': rnd(ema200),
            'rsi14': rnd(rsi14),
            'adx14': rnd(adx_arr),
            'slope': rnd(slope),
            'close': rnd(close),
            'sig': [int(x) for x in sig[-400:]],
        },
        'health_ok': bool(health),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_ok = True
    for card in MEMBERS:
        rec = build_reference(card)
        all_ok = all_ok and rec['health_ok']
        out = os.path.join(OUT_DIR, card.replace('-', '_') + '.json')
        with open(out, 'w') as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        print(f'saved -> {out}', flush=True)
    if not all_ok:
        raise SystemExit('S572 PARITY REFERENCE INVALID: members not reproduced')


if __name__ == '__main__':
    main()
