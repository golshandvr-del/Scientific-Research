# -*- coding: utf-8 -*-
"""
s145x_mgmt_cohort2.py — زیرساختِ مشترکِ دههٔ دومِ مأموریت ۵ (S1450–S1459)
================================================================================
پیش‌ثبت: results/S1450_PREREG_MGMT_DECADE2_PROTOCOL_AND_TP_EXTENSION.md §۰.

- داده: فقط data/mt5_full (هارد-گارد). H4 از H1 بازنمونه (4h, origin=epoch).
- بیماران (cohort 2): S526_H8, S1511_H6, S589_H8g, S589_H4g, S382_H4 (موتور s382)
  + S312_H1 (موتور trade_simulator؛ فقط اطلاع‌رسان).
- بازتولیدِ پایه از تعریفِ منجمدِ خودِ لایه‌ها (فقط خوانده می‌شوند).
- بازپخشِ engine-exact با «قاعدهٔ» قابل‌اتصال (rule object با متدهای
  on_bar(...) که می‌تواند exit یا تغییرِ TP/SL درخواست کند).
- توازی اجباری، مسیرِ C، حداقلِ ۲۰ معاملهٔ تغییریافته برای هولد‌اوت.

هیچ فایلِ موتور یا لایهٔ دیگری تغییر نمی‌کند.
"""
import os
import sys
import json
import importlib.util
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)
from strategies.s450_paired_replay import metrics, judge  # noqa: E402

FULL_DIR = os.path.join(ROOT, 'data', 'mt5_full')
MIN_CHANGED = 20
PATIENTS = ('S526_H8', 'S1511_H6', 'S589_H8g', 'S589_H4g', 'S382_H4', 'S312_H1')
INFORMATIONAL = ('S312_H1',)
PIP_VALUE_USD = 10.0   # طلا، ۱ لات


# ───────────────────────────── داده ─────────────────────────────
def load_full_df(tf):
    if tf == 'H4':
        p = os.path.join(FULL_DIR, 'XAUUSD_H1.csv.gz')
        assert 'mt5_full' in p and os.path.exists(p), 'E-16 GUARD'
        h1 = pd.read_csv(p)
        h1['dt'] = pd.to_datetime(h1['time'], unit='s', utc=True)
        g = h1.set_index('dt').resample('4h', origin='epoch', offset='0h')
        df = pd.DataFrame({'open': g['open'].first(), 'high': g['high'].max(),
                           'low': g['low'].min(), 'close': g['close'].last(),
                           'volume': g['volume'].sum()}).dropna().reset_index()
        df['time'] = (df['dt'].astype('int64') // 10**9).astype('int64')
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
    else:
        p = os.path.join(FULL_DIR, f'XAUUSD_{tf}.csv.gz')
        assert 'mt5_full' in p and os.path.exists(p), f'E-16 GUARD: {p}'
        df = pd.read_csv(p)
    for col in ('open', 'high', 'low', 'close'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ───────────────────────── سیگنال‌های منجمدِ لایه‌ها ─────────────────────────
LOOKBACK = 90


def _drift(df):
    c = df['close']
    return ((c.shift(1) - c.shift(LOOKBACK)) > 0).fillna(False)


def sig_s526(df):
    c = df['close']
    nh = (c > c.rolling(LOOKBACK).max().shift(1)).fillna(False)
    return nh & ~nh.shift(1).fillna(False)


def sig_s1511(df):
    lo = df['low']
    ff = (lo > lo.rolling(LOOKBACK).max().shift(1)).fillna(False).astype(bool)
    return ff & ~ff.shift(1, fill_value=False) & _drift(df)


def _rvol_slot(df):
    v = df['volume'].astype(float)
    hour = df['dt'].dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(30, min_periods=20).median())
    return v / ref.replace(0, np.nan)


def sig_s589(df):
    rv = _rvol_slot(df)
    return sig_s526(df) & (rv >= 1.0) & rv.notna()


# ───────────────────────── بازپخشِ engine-exact ─────────────────────────
def replay_s382(trade, arr, rule, sl_abs, rr, ps):
    """قراردادِ s382.simulate_trades: ورود close[e]، از e+1: SL-first، TP.
    rule.on_bar(i, entry, fl, sl_lvl, tp_lvl, state) -> (action, state)
    action: None | ('exit',) | ('tp', new_tp) | ('sl', new_sl)
    خروجی: (pnl_pip, exit_bar, reason) یا None (باز در انتهای داده)."""
    o, h, l, c = arr
    e = int(trade.entry_bar)
    entry = c[e]
    sl_lvl = entry - sl_abs
    tp_lvl = entry + sl_abs * rr
    n = len(o)
    st = None
    j = e + 1
    while j < n:
        if l[j] <= sl_lvl:
            return (sl_lvl - entry) / ps, j, 'sl'
        if h[j] >= tp_lvl:
            return (tp_lvl - entry) / ps, j, 'tp'
        if rule is not None:
            act, st = rule.on_bar(j, entry, c[j] - entry, sl_lvl, tp_lvl, st, True)
            if act is not None:
                if act[0] == 'exit':
                    return (c[j] - entry) / ps, j, 'rule_exit'
                if act[0] == 'tp':
                    tp_lvl = act[1]
                elif act[0] == 'sl':
                    sl_lvl = act[1]
        j += 1
    return None


def replay_ts(trade, arr, rule, max_hold, spec):
    """قراردادِ trade_simulator (S312 LONG). pnl_usd بر ۱ لات."""
    o, h, l, c = arr
    e = int(trade.entry_bar)
    entry = float(trade.entry_price)
    pip = spec['pip']; contract = spec['contract']; cost = spec['cost_price']
    sl = entry - float(trade.sl_pip) * pip
    tp = entry + float(trade.tp_pip) * pip
    n = len(o)
    st = None
    i = e
    while i < n - 1:
        nb = i + 1
        if o[nb] <= sl:
            return (o[nb] - entry - cost) * contract, nb, 'sl_gap'
        if o[nb] >= tp:
            return (o[nb] - entry - cost) * contract, nb, 'tp_gap'
        if l[nb] <= sl:
            return (sl - entry - cost) * contract, nb, 'sl'
        if h[nb] >= tp:
            return (tp - entry - cost) * contract, nb, 'tp'
        if (i + 1) - e >= max_hold:
            return (o[nb] - entry - cost) * contract, nb, 'strategy_close'
        if rule is not None and i > e:
            act, st = rule.on_bar(i, entry, c[i] - entry, sl, tp, st, True)
            if act is not None:
                if act[0] == 'exit':
                    return (o[nb] - entry - cost) * contract, nb, 'rule_exit'
                if act[0] == 'tp':
                    tp = act[1]
                elif act[0] == 'sl':
                    sl = act[1]
        i += 1
    return (c[n - 1] - entry - cost) * contract, n - 1, 'eod'


# ───────────────────────────── بیماران ─────────────────────────────
def load_patient(name, make_rule):
    """make_rule(df, vn) -> rule object یا None (vn=None ⇒ پایه).
    خروجی: df, tr, rf(t, vn)->pnl_usd, base_usd, meta"""
    if name == 'S312_H1':
        from engine import trade_simulator as TS
        from strategies.sim_strategies import S312_MidMonth_Long
        from strategies.s450_mgmt_first_hour_low import BEST
        df = load_full_df('H1')
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
        kw = BEST['H1']
        spec = TS.asset_spec('XAUUSD')
        tr, _ = TS.simulate(df, S312_MidMonth_Long(**kw), 'XAUUSD', tf='H1',
                            warmup=220, max_bars_hold=kw['max_hold'])
        arr = tuple(df[k].values.astype(float) for k in ('open', 'high', 'low', 'close'))
        rules = {}

        def rf(t, vn):
            if vn not in rules:
                rules[vn] = None if vn is None else make_rule(df, vn)
            return replay_ts(t, arr, rules[vn], kw['max_hold'], spec)[0]
        return df, tr, rf, tr['pnl_usd'].to_numpy(float), dict(engine='ts', **kw)

    L = _mod('strategies/s382_williamsr_momentum.py', '_s382_c2')
    ps = L.pip_size('XAUUSD')
    if name == 'S382_H4':
        df = load_full_df('H4'); sig = L.signals(df)
    elif name == 'S526_H8':
        df = load_full_df('H8'); sig = sig_s526(df)
    elif name == 'S1511_H6':
        df = load_full_df('H6'); sig = sig_s1511(df)
    elif name == 'S589_H8g':
        df = load_full_df('H8'); sig = sig_s589(df)
    elif name == 'S589_H4g':
        df = load_full_df('H4'); sig = sig_s589(df)
    else:
        raise ValueError(name)
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
    arr = tuple(df[k].values.astype(float) for k in ('open', 'high', 'low', 'close'))
    rules = {}
    base_pip = tr['pnl_pip'].to_numpy(float)

    def rf(t, vn):
        if vn not in rules:
            rules[vn] = None if vn is None else make_rule(df, vn)
        out = replay_s382(t, arr, rules[vn], sl_abs, L.RR, ps)
        if out is None:      # بازِ انتهای داده بعد از تغییرِ قاعده ⇒ pnl پایه (افشا)
            return None
        return out[0] * PIP_VALUE_USD
    meta = dict(engine='s382', sl_pip=sl_abs / ps, tp_pip=sl_abs * L.RR / ps, n_bars=len(df))
    return df, tr, rf, base_pip * PIP_VALUE_USD, meta


# ───────────────────────────── اجرای استاندارد ─────────────────────────────
def run(code, name, variants, make_rule, winner_key='maxDD'):
    df, tr, rf, base, meta = load_patient(name, make_rule)
    n = len(tr)
    par = np.array([rf(t, None) for t in tr.itertuples(index=False)], float)
    mism = np.abs(par - base) > 1e-6
    print(f"[{name}] parity: {int(mism.sum())}/{n} mismatches (max|Δ|={np.abs(par-base).max():.9f}) "
          f"bars={len(df)} span={df['dt'].iloc[0].date()}..{df['dt'].iloc[-1].date()}")
    if mism.any():
        _save(code, name, dict(patient=name, status='PARITY_FAIL', n_mismatch=int(mism.sum()), n=n))
        return
    eb = tr['entry_bar'].to_numpy(int); mid = len(df) // 2
    m1 = eb < mid; m2 = ~m1
    cal = {}
    for vn in variants:
        raw = [rf(t, vn) for t in tr.itertuples(index=False)]
        n_open = sum(1 for x in raw if x is None)
        mg = np.array([b if x is None else x for x, b in zip(raw, base)], float)
        nch = int((np.abs(mg - base) > 1e-9).sum())
        j1 = judge(metrics(base[m1]), metrics(mg[m1]))
        under = nch < MIN_CHANGED
        cal[vn] = dict(mgmt_h1=metrics(mg[m1]), judge_h1=j1, n_changed=nch,
                       n_openend=n_open, underpowered=under, _mg=mg)
        print(f"[{name}] {vn}: changed={nch}/{n} openend={n_open} H1={j1['verdict']}"
              f"{' (UNDERPOWERED)' if under else ''} profit_ok={j1.get('profit_ok')} "
              f"improves={j1.get('improves')} avg {metrics(base[m1])['avg']:.1f}->{metrics(mg[m1])['avg']:.1f}")
    passers = [v for v in variants if cal[v]['judge_h1']['verdict'] == 'PASS' and not cal[v]['underpowered']]
    common = dict(patient=name, n=n, informational=name in INFORMATIONAL, meta=meta,
                  data_source='data/mt5_full (H4 resampled from H1)', n_bars=int(len(df)),
                  span=[str(df['dt'].iloc[0]), str(df['dt'].iloc[-1])],
                  baseline_h1=metrics(base[m1]), baseline_h2=metrics(base[m2]),
                  calibration={v: {k: x for k, x in cal[v].items() if k != '_mg'} for v in variants})
    if not passers:
        _save(code, name, dict(status='REJECT_AT_CALIBRATION', **common))
        print(f"[{name}] REJECT at calibration — holdout never opened")
        return

    def score(v):
        b = metrics(base[m1]); g = cal[v]['mgmt_h1']
        if winner_key == 'avg':
            return g['avg'] - b['avg']
        return (b['maxDD'] - g['maxDD']) / b['maxDD'] if b['maxDD'] > 0 else 0.0
    win = max(passers, key=score)
    mg = cal[win]['_mg']
    j2 = judge(metrics(base[m2]), metrics(mg[m2]))
    out = dict(status='JUDGED', variant_winner=win, final_verdict=j2['verdict'],
               treatment_full=metrics(mg), baseline_full=metrics(base),
               judge_full=judge(metrics(base), metrics(mg)),
               h1=dict(base=metrics(base[m1]), mgmt=metrics(mg[m1]), judge=cal[win]['judge_h1']),
               h2=dict(base=metrics(base[m2]), mgmt=metrics(mg[m2]), judge=j2), **common)
    _save(code, name, out)
    print(f"[{name}] winner {win} → H2 (holdout) verdict = {j2['verdict']}")
    print("  H2 base:", out['h2']['base']); print("  H2 mgmt:", out['h2']['mgmt'])


def _save(code, name, out):
    os.makedirs(os.path.join(ROOT, 'research', 'mgmt'), exist_ok=True)
    p = os.path.join(ROOT, 'research', 'mgmt', f'{code}_{name}.json')
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("saved:", p)
