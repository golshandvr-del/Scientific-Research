# -*- coding: utf-8 -*-
"""S1581 — صادرکنندهٔ مرجعِ عددیِ پریتی (TS ↔ Python) روی XAUUSD-H6.

چرا: سیم‌کشیِ یک لایه یعنی ادعای اینکه «کارتی که روی سایت روشن می‌شود همان
چیزی است که RQS2 پذیرفت». این ادعا فقط اگر پورت با **عددِ اندازه‌گیری‌شده**
سنجیده شود معتبر است، نه با متنِ سند. این ابزار همان مرجع را می‌سازد:

  ۱) مجموعهٔ **شمارهٔ کندلِ سیگنال‌ها** (نه فقط تعدادشان — چون تساویِ تعداد
     تضمینِ تساویِ جای‌گیری نیست).
  ۲) n_signals · n_trades (پس از FIFO) · WR · هندسهٔ SL/TP (pip و دلار).
  ۳) توزیعِ نگه‌داری (کمینه/میانه/p95/بیشینه) — برای انتخابِ سقفِ اجراییِ maxHold.
  ۴) ۴۰۰ کندلِ آخرِ سری‌های میانی (سدِ کف، RVOL) برای عیب‌یابیِ تفصیلی.

گاردِ سلامت: n_signals باید ۳۲۶ و n_trades باید ۲۱۹ و WR باید 52.97 باشد
(results/_s1581/XAUUSD_H6_gated.json). وگرنه ابزار **سخت شکست می‌خورد**.

اجرا: python3 tools/export_s1581_parity.py
خروجی: results/_s1581_parity/XAUUSD_H6.json
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CARD = 'XAUUSD_H6'
LOOKBACK = 90
RVOL_THR, SLOT_WIN, SLOT_MINP = 1.0, 30, 20
OUT = 'results/_s1581_parity/XAUUSD_H6.json'

PUBLISHED_SIGNALS = 326
PUBLISHED_TRADES = 219
PUBLISHED_WR = 52.97


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _b(s):
    return s.astype('boolean').fillna(False).astype(bool)


def load():
    path = f'data/mt5_full/{CARD}.csv.gz'
    assert 'mt5_full' in path and os.path.exists(path), f'E-16 GUARD: {path}'
    with gzip.open(path, 'rt') as f:
        df = pd.read_csv(f)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    df = load()

    lo, c = df['low'], df['close']
    ff = _b(lo > lo.rolling(LOOKBACK).max().shift(1))
    fresh = ff & ~ff.shift(1, fill_value=False)
    drift = _b((c.shift(1) - c.shift(LOOKBACK)) > 0)
    base = fresh & drift

    v = df['volume'].astype(float)
    hour = df['dt'].dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    rv = v / ref.replace(0, np.nan)
    sig = base & rv.notna() & (rv >= RVOL_THR)

    ps = L.pip_size('XAUUSD')                      # 0.1 — قراردادِ پروژه
    a = L.atr(df)
    sl_abs = float(np.nanmedian(a.to_numpy())) * L.SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * L.RR

    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
    n_sig = int(sig.sum())
    n_tr = int(len(tr))
    wr = round(100.0 * float((tr['outcome'] == 'win').mean()), 2) if n_tr else None
    hold = (tr['exit_bar'] - tr['entry_bar']) if n_tr else pd.Series([], dtype=int)

    health = (n_sig == PUBLISHED_SIGNALS and n_tr == PUBLISHED_TRADES
              and abs(wr - PUBLISHED_WR) < 0.01)
    print(f'{CARD}: n_signals={n_sig} (pub {PUBLISHED_SIGNALS}) n_trades={n_tr} '
          f'(pub {PUBLISHED_TRADES}) wr={wr} (pub {PUBLISHED_WR}) sl_pip={sl_pip:.2f} '
          f'sl_abs={sl_abs:.5f} health={"OK" if health else "FAIL"}', flush=True)

    rec = {
        'card': CARD,
        'bars': int(len(df)),
        'span_years': round((df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 86400), 2),
        'data_src': 'data/mt5_full/XAUUSD_H6.csv.gz',
        'frozen': {
            'lookback': LOOKBACK, 'rvol_thr': RVOL_THR,
            'slot_win': SLOT_WIN, 'slot_minp': SLOT_MINP,
            'atr_p': L.ATR_P, 'sl_k': L.SL_K, 'rr': L.RR,
            'sl_pip': round(sl_pip, 2), 'tp_pip': round(tp_pip, 2),
            'sl_abs_price': round(sl_abs, 5),
            'pip_size': ps, 'entry': 'close_of_signal_bar', 'side': 'long',
        },
        'counts': {
            'n_base_events': int(base.sum()),
            'n_signals': n_sig, 'n_trades': n_tr, 'wr': wr,
            'pass_rate': round(100.0 * n_sig / max(1, int(base.sum())), 1),
        },
        'hold_bars': {
            'min': int(hold.min()), 'median': int(hold.median()),
            'p95': int(np.percentile(hold, 95)), 'max': int(hold.max()),
        } if n_tr else None,
        'signal_bars': [int(x) for x in np.flatnonzero(sig.to_numpy())],
        'published': {'n_signals': PUBLISHED_SIGNALS, 'n_trades': PUBLISHED_TRADES, 'wr': PUBLISHED_WR},
        'health_ok': bool(health),
    }

    # سری‌های میانیِ ۴۰۰ کندلِ آخر (برای عیب‌یابیِ تفصیلیِ پورت)
    tail = 400
    rec['tail'] = {
        'from_index': int(len(df) - tail),
        'prior_min_low': [None if not np.isfinite(x) else round(float(x), 5)
                          for x in (lo.rolling(LOOKBACK).max().shift(1).to_numpy()[-tail:])],
        'ff': [int(x) for x in ff.to_numpy()[-tail:]],
        'fresh': [int(x) for x in fresh.to_numpy()[-tail:]],
        'drift': [int(x) for x in drift.to_numpy()[-tail:]],
        'rvol': [None if not np.isfinite(x) else round(float(x), 6)
                 for x in rv.to_numpy()[-tail:]],
        'sig': [int(x) for x in sig.to_numpy()[-tail:]],
    }

    with open(OUT, 'w') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(f'saved -> {OUT}', flush=True)

    if not health:
        raise SystemExit('S1581 PARITY REFERENCE INVALID: published numbers not reproduced')


if __name__ == '__main__':
    main()
