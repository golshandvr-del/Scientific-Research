# -*- coding: utf-8 -*-
"""S535 — سقفِ تازهٔ ۹۰ی طلایِ یورویی بدون سقفِ دلاری ⇒ LONG XAUUSD | H4/H6/H8/H12/D1.

پیش‌ثبت: results/S535_PREREG_XaueurFreshHighDivergence_Xauusd_H4H6H8H12D1.md
(commit 4c963463 — قبل از این اجرا). مسیر B، صفر پارامتر آزاد.

xaueur[t] = close[t] × eur_h1_close(آخرین کندل H1 پایان‌یافته ≤ پایان کندل t)  (علّی)
signal   = fresh-high-90(xaueur) edge  &  ~fresh-high-90(xauusd) state
بازوی مکمل 'both' (edge یورویی & دلاری در سقف) فقط گزارشی است (P1)، داوری نمی‌شود.
هارنس/هندسه/نول عیناً S382/S526. داده: data/mt5_full + data/EURUSD_H1.csv.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = 'results/_s535'
JUDGED = ['XAUUSD_H8', 'XAUUSD_H6', 'XAUUSD_H4', 'XAUUSD_H12', 'XAUUSD_D1']
REPORT_ONLY = ['XAUUSD_H3', 'XAUUSD_H2', 'XAUUSD_H1', 'XAUUSD_M30']
TF_SEC = dict(D1=86400, H12=43200, H8=28800, H6=21600, H4=14400, H3=10800,
              H2=7200, H1=3600, M30=1800)
N_TRIALS = 5
LOOKBACK = 90          # منجمد S526/S950
SEED = 20260819
MIN_YEARS = 14.0
EUR_PATH = 'data/EURUSD_H1.csv'


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_eur():
    e = pd.read_csv(EUR_PATH)
    e = e[['time', 'close']].copy()
    e['time'] = e['time'].astype('int64')
    # کندل H1 با شروع time در time+3600 پایان می‌یابد
    e['t_end'] = e['time'] + 3600
    return e.sort_values('t_end').reset_index(drop=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')
    MTF.N_TRIALS = N_TRIALS
    MTF.SEED = SEED
    NM.SEED = SEED
    eur = load_eur()
    state = {}

    def load_full(card):
        path = f'data/mt5_full/{card}.csv'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
        if span < MIN_YEARS:
            raise RuntimeError(f'DATASETDRIFT: {path} span={span:.1f}y')
        tf = card.split('_')[1]
        sec = TF_SEC[tf]
        g = pd.DataFrame({'t_end': df['time'].astype('int64') + sec})
        m = pd.merge_asof(g, eur[['t_end', 'close']].rename(columns={'close': 'eur'}),
                          on='t_end', direction='backward',
                          tolerance=7 * 86400)
        df['eur'] = m['eur'].to_numpy()
        state['src'] = dict(path=path, eur=EUR_PATH, rows=int(len(df)),
                            span_years=round(span, 2), eur_nan=int(df['eur'].isna().sum()),
                            first=str(df['dt'].iloc[0]), last=str(df['dt'].iloc[-1]))
        return df

    L.load = load_full

    def arms(df):
        c = df['close']
        xe = c * df['eur']
        fhE = (xe > xe.shift(1).rolling(LOOKBACK).max()).fillna(False).astype(bool)
        fhU = (c > c.shift(1).rolling(LOOKBACK).max()).fillna(False).astype(bool)
        edgeE = fhE & ~fhE.shift(1, fill_value=False)
        return (edgeE & ~fhU), (edgeE & fhU)

    def signals_div(df):
        return arms(df)[0]

    L.signals = signals_div

    cards = sys.argv[1:] or (JUDGED + REPORT_ONLY)
    print(f'S535 XAUEUR fresh-high divergence | edge FH{LOOKBACK}(xaueur) & ~FH{LOOKBACK}(xauusd) '
          f'| sl_k={L.SL_K} rr={L.RR} LONG | uncond null k={NM.K} seed={SEED} '
          f'n_trials={N_TRIALS}', flush=True)
    for card in cards:
        tag = ' [REPORT-ONLY]' if card in REPORT_ONLY else ''
        print(f'--- {card}{tag} ---', flush=True)
        try:
            r = MTF.run_card(card, L, NM)
            # بازوی مکمل — فقط گزارشی، بدون داوری RQS2 (P1)
            df = L.load(card)
            ps = L.pip_size('XAUUSD')
            sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
            both = arms(df)[1]
            trb = L.simulate_trades(df, both, sl_abs, L.RR, True, ps)
            r['both_arm_report_only'] = dict(
                n_signals=int(both.sum()), n_trades=int(len(trb)),
                wr=(round(100.0 * float((trb['outcome'] == 'win').mean()), 2)
                    if len(trb) else None),
                exp_pip=(round(float(trb['pnl_pip'].mean()), 2) if len(trb) else None))
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['lookback'] = LOOKBACK
        r['report_only'] = card in REPORT_ONLY
        r['data_src'] = state.get('src')
        r['seed'] = SEED
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        b = r['both_arm_report_only']
        print(f'{card}: span={r.get("span_years")}y nsig={r.get("n_signals")} '
              f'n={r.get("n_trades")} sl={r.get("sl_pip")}pip wr={r.get("wr")} '
              f'be={r.get("be")} lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")} || both(rpt): n={b["n_trades"]} '
              f'wr={b["wr"]} exp={b["exp_pip"]}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
