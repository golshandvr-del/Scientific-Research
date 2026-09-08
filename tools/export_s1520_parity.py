# -*- coding: utf-8 -*-
"""S1520 — صادرکنندهٔ مرجعِ پریتی (گامِ ۱ از سیم‌کشی).

هدف: تولیدِ یک artifactِ مرجع از **همان ماشینِ منجمدی** که حکمِ ACCEPT 90.6 را
ساخت، تا پورتِ TypeScript بتواند بیت‌به‌بیت با آن سنجیده شود.

چرا این گام لازم است (درسِ سیم‌کشیِ S607، دام‌های ۱..۶):
  هر بار که یک لایه از پایتون به TS برده شد، پریتی دام‌هایی یافت که با چشم
  دیده نمی‌شدند — نحوهٔ warm-up، شیفتِ ATR، محاسبهٔ ناقصِ rolling در سرِ سری.
  پس **قبل** از نوشتنِ یک خط TS، مرجع را از خودِ ماشینِ حکم می‌گیریم.

ماشینِ منجمدِ حکمِ S1520 دقیقاً این است:
  · tools/s1520_informed_fresh_high_runner.py   (رویداد + گیت ρ)
  · strategies/s382_williamsr_momentum.py       (atr، simulate_trades، هندسه)
  · tools/s382_mtf_runner.py                    (sl_abs = median(ATR100)×1.5)

خروجی: results/_s1520_parity/XAUUSD_{H8,H4,H12}.json
  - سریِ علّی روی هر کندلِ صادرشده: priorMax90 · rho · atr100 · freshHigh · gated
  - همهٔ سیگنال‌ها (اندیس + زمان + قیمت)
  - هندسهٔ حکم: median(ATR100)، slPip، tpPip
  - **شاهدِ منفی**: کارت‌های H4 (REJECT 16.7) و H12 (UNPROVEN 27.1) هم صادر
    می‌شوند تا اثبات شود پورت روی آن‌ها هم سیگنالِ یکسان می‌سازد و «وصل‌نشدن»
    یک تصمیمِ حکمی است نه یک باگِ سکوت.

گیتِ سلامت (health gate): اگر بازتولیدِ n و WR از فایلِ حکمِ ثبت‌شده
  (results/_s1520/XAUUSD_H8_gated.json) منحرف شود، اسکریپت **می‌شکند** — چون
  در آن حالت مرجع بی‌ارزش است.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, 'results/_s1520_parity')

# --- ثابت‌های منجمد (عیناً از tools/s1520_informed_fresh_high_runner.py) ---
LOOKBACK = 90       # منجمد S526
RHO_THR = 0.618     # منجمد S965
ATR_P = 100         # منجمد S382
SL_K = 1.5          # منجمد S382
RR = 1.5            # منجمد S382 (TP > SL)

CARDS = ['XAUUSD_H8', 'XAUUSD_H4', 'XAUUSD_H12']

# آخرین N کندل که سریِ کاملشان صادر می‌شود (پریتی روی دنبالهٔ سری)
TAIL = 3000


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_card(card: str) -> pd.DataFrame:
    """عیناً load_full از رانرِ S1520: data/full سپس data/ — با gunzip از mt5_full."""
    full = os.path.join(ROOT, f'data/full/{card}.csv')
    if not os.path.exists(full):
        gz = os.path.join(ROOT, f'data/mt5_full/{card}.csv.gz')
        if os.path.exists(gz):
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with gzip.open(gz, 'rb') as fi, open(full, 'wb') as fo:
                shutil.copyfileobj(fi, fo)
    path = full if os.path.exists(full) else os.path.join(ROOT, f'data/{card}.csv')
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def fresh_high(df: pd.DataFrame) -> pd.Series:
    """عیناً fresh_high() رانر: لبهٔ تازه، نه حالت."""
    c = df['close']
    nh = (c > c.rolling(LOOKBACK).max().shift(1)).fillna(False)
    return nh & ~nh.shift(1).fillna(False)


def prior_max(df: pd.DataFrame) -> pd.Series:
    return df['close'].rolling(LOOKBACK).max().shift(1)


def rho_series(df: pd.DataFrame) -> pd.Series:
    """عیناً rho() رانر — **علامت‌دار** (بدنهٔ صعودی لازم)، نه قدرمطلق.

    دامِ پورت شمارهٔ ۱: S965 از |close−open| استفاده می‌کند (بی‌علامت، چون
    دوجهته است) ولی S1520 از (close−open) استفاده می‌کند (علامت‌دار، چون
    LONG-only است). اگر پورت اشتباهاً قدرمطلق بگیرد، کندل‌های **نزولی** با
    بدنهٔ بزرگ هم سیگنال می‌گیرند و جمعیت عوض می‌شود.
    """
    rng = (df['high'] - df['low']).replace(0, np.nan)
    return ((df['close'] - df['open']) / rng).fillna(0.0)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')

    summary = {}
    for card in CARDS:
        df = load_card(card)
        n = len(df)

        atr = L.atr(df, ATR_P)                       # Wilder ewm(alpha=1/100) — دامِ پورت ۲
        sl_abs = float(np.nanmedian(atr.to_numpy())) * SL_K
        ps = L.pip_size('XAUUSD')
        sl_pip = sl_abs / ps
        tp_pip = sl_pip * RR

        base = fresh_high(df)
        r = rho_series(df)
        gated = base & (r >= RHO_THR)
        counter = base & (r < RHO_THR)

        tr = L.simulate_trades(df, gated, sl_abs, RR, True, ps)
        n_tr = int(len(tr))
        wr = round(100.0 * float((tr['outcome'] == 'win').mean()), 2) if n_tr else None

        pmax = prior_max(df)
        i0 = max(0, n - TAIL)
        series = []
        for i in range(i0, n):
            series.append({
                'i': i,
                't': int(df['time'].iloc[i]),
                'o': float(df['open'].iloc[i]),
                'h': float(df['high'].iloc[i]),
                'l': float(df['low'].iloc[i]),
                'c': float(df['close'].iloc[i]),
                'priorMax': None if pd.isna(pmax.iloc[i]) else float(pmax.iloc[i]),
                'rho': float(r.iloc[i]),
                'atr': None if pd.isna(atr.iloc[i]) else float(atr.iloc[i]),
                'fresh': bool(base.iloc[i]),
                'gated': bool(gated.iloc[i]),
            })

        sig_idx = [int(x) for x in np.flatnonzero(gated.to_numpy())]
        cnt_idx = [int(x) for x in np.flatnonzero(counter.to_numpy())]

        rec = {
            'card': card,
            'bars': n,
            'span_years': round((df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25, 2),
            'frozen': {
                'lookback': LOOKBACK, 'rhoThr': RHO_THR,
                'atrP': ATR_P, 'slK': SL_K, 'rr': RR,
            },
            'geometry': {
                'medianAtr': float(np.nanmedian(atr.to_numpy())),
                'slAbs': sl_abs, 'slPip': round(sl_pip, 4), 'tpPip': round(tp_pip, 4),
            },
            'counts': {
                'fresh': int(base.sum()),
                'gated': int(gated.sum()),
                'counter': int(counter.sum()),
                'gatePassRatePct': round(100.0 * gated.sum() / max(1, base.sum()), 2),
                'trades': n_tr, 'wr': wr,
            },
            'signalIdx': sig_idx,
            'counterIdx': cnt_idx,
            'tailFrom': i0,
            'series': series,
        }
        with open(os.path.join(OUT, f'{card}.json'), 'w') as f:
            json.dump(rec, f, ensure_ascii=False)
        summary[card] = rec['counts'] | rec['geometry']
        print(f'{card}: bars={n} fresh={int(base.sum())} gated={int(gated.sum())} '
              f'({rec["counts"]["gatePassRatePct"]}%) trades={n_tr} wr={wr} '
              f'sl={sl_pip:.2f}pip tp={tp_pip:.2f}pip', flush=True)

    # ---- گیتِ سلامت: بازتولیدِ حکمِ ثبت‌شدهٔ H8 ----
    ref_path = os.path.join(ROOT, 'results/_s1520/XAUUSD_H8_gated.json')
    with open(ref_path) as f:
        ref = json.load(f)
    got = summary['XAUUSD_H8']
    checks = {
        'n_signals': (int(got['gated']), int(ref['n_signals'])),
        'n_trades': (int(got['trades']), int(ref['n_trades'])),
        'wr': (float(got['wr']), float(ref['wr'])),
        'sl_pip': (round(float(got['slPip']), 2), float(ref['sl_pip'])),
        'tp_pip': (round(float(got['tpPip']), 2), float(ref['tp_pip'])),
    }
    print('\n--- HEALTH GATE (reproduce the ACCEPT 90.6 verdict) ---')
    bad = []
    for k, (a, b) in checks.items():
        ok = (abs(a - b) < 0.011) if isinstance(a, float) else (a == b)
        print(f'  {k:10s} got={a} ref={b} {"OK" if ok else "MISMATCH"}')
        if not ok:
            bad.append(k)
    with open(os.path.join(OUT, 'health.json'), 'w') as f:
        json.dump({'checks': {k: {'got': v[0], 'ref': v[1]} for k, v in checks.items()},
                   'mismatch': bad}, f, ensure_ascii=False, indent=1)
    if bad:
        raise SystemExit(f'HEALTH GATE FAILED on {bad} — reference is worthless, stop.')
    print('HEALTH GATE PASSED — reference is bit-faithful to the verdict machinery.')


if __name__ == '__main__':
    main()
