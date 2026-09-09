# -*- coding: utf-8 -*-
"""S1511 — ممیزی هم‌پوشانی فوری (قانون overlap): S1511-H6 در برابر ACCEPTهای زنده/هم‌خانواده.

مراجع:
  A) S382-H4 لایو (data/XAUUSD_H4.csv، n≈869) — پنجرهٔ باز معامله (t_entry ≤ t < t_exit).
  B) S526-H8 (سقفِ تازهٔ ۹۰ close، drift>0) — پنجرهٔ باز معامله (mt5_full).
  C) S1520-H8 (S526 × ρ≥0.618) — پنجرهٔ باز معامله (mt5_full).
  D) S919-H6 event (شوک ≥2.618×ATR21[t−1] ∧ ρ≥0.618 ∧ drift241>0، LONG) — هم‌بار و پنجرهٔ ۱۶ کندل.
  E) overlap-as-filter: S1511 با/بدون رویداد S526 روی خودِ H6 در ۳ کندل اخیر.
تشخیصی — بدون داوری RQS2 جدید. خروجی: results/_scan_S1511/overlap_audit.json
"""
from __future__ import annotations
import importlib.util, json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); os.chdir(ROOT)
OUT = 'results/_scan_S1511'; COST = 3.3; LB = 90


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _b(s): return s.astype('boolean').fillna(False).astype(bool)


def load(path):
    df = pd.read_csv(path); df['dt'] = pd.to_datetime(df['time'], unit='s'); return df


def trades_t(L, df, sig):
    ps = L.pip_size('XAUUSD'); sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps).copy()
    dtv = df['dt'].values.astype('datetime64[ns]').astype(np.int64)
    tr['t_entry'] = dtv[tr['entry_bar'].values]; tr['t_exit'] = dtv[tr['exit_bar'].values]
    sl_pip = sl_abs / ps; be = 100.0 * (sl_pip + COST) / (sl_pip * L.RR + sl_pip)
    return tr, be


def seg(tr, be):
    n = len(tr)
    if n == 0: return dict(n=0, wr=None, lift=None)
    wr = 100.0 * float((tr['outcome'] == 'win').mean()); return dict(n=n, wr=round(wr, 2), lift=round(wr - be, 2))


def drift(df, k=LB):
    c = df['close']; return _b((c.shift(1) - c.shift(k)) > 0)


def fresh_floor(df):
    lo = df['low']; ff = _b(lo > lo.rolling(LB).max().shift(1)); return ff & ~ff.shift(1, fill_value=False) & drift(df)


def fresh_high(df):
    c = df['close']; nh = _b(c > c.rolling(LB).max().shift(1)); return nh & ~nh.shift(1, fill_value=False) & drift(df)


def rho(df):
    rng = (df['high'] - df['low']).replace(0, np.nan); return (df['close'] - df['open']) / rng


def s919_event(df):
    pc = df['close'].shift(1)
    tr_ = np.maximum(df['high'] - df['low'], np.maximum((df['high'] - pc).abs(), (df['low'] - pc).abs()))
    atr_prev = tr_.rolling(21).mean().shift(1)
    shock = _b((df['high'] - df['low']) >= 2.618 * atr_prev)
    r = _b(rho(df).abs() >= 0.618); up = _b(df['close'] > df['open'])
    d = _b((df['close'].shift(1) - df['close'].shift(241)) > 0)
    return shock & r & up & d


def window_hits(t_arr, iv_e, iv_x):
    order = np.argsort(iv_e); iv_e, iv_x = iv_e[order], iv_x[order]
    out = []
    for t in t_arr:
        j = np.searchsorted(iv_e, t, 'right') - 1; lo = max(0, j - 12)
        out.append(bool(np.any((iv_e[lo:j + 1] <= t) & (t < iv_x[lo:j + 1]))))
    return np.array(out, bool)


def vs_window(tr, be, tr_ref):
    ov = window_hits(tr['t_entry'].values, tr_ref['t_entry'].values, tr_ref['t_exit'].values)
    return dict(n_ref=int(len(tr_ref)), overlap_pct=round(100 * ov.mean(), 1), overlap=seg(tr[ov], be), non_overlap=seg(tr[~ov], be))


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    h6 = load('data/mt5_full/XAUUSD_H6.csv'); h8 = load('data/mt5_full/XAUUSD_H8.csv')
    tr, be = trades_t(L, h6, fresh_floor(h6))
    print(f'S1511-H6: n={len(tr)} (انتظار 279) be={be:.2f}', flush=True)
    res = dict(src='data/mt5_full', be=round(be, 2), all=seg(tr, be))
    h4 = load('data/XAUUSD_H4.csv'); tr4, _ = trades_t(L, h4, L.signals(h4))
    res['vs_S382_H4_live'] = vs_window(tr, be, tr4)
    tr526, _ = trades_t(L, h8, fresh_high(h8)); res['vs_S526_H8'] = vs_window(tr, be, tr526)
    tr1520, _ = trades_t(L, h8, fresh_high(h8) & _b(rho(h8) >= 0.618)); res['vs_S1520_H8'] = vs_window(tr, be, tr1520)
    ev = s919_event(h6); ev_idx = np.flatnonzero(ev.values); eb = tr['entry_bar'].values
    same = np.isin(eb, ev_idx)
    win16 = np.array([bool(np.any((ev_idx <= e) & (ev_idx > e - 16))) for e in eb])
    res['vs_S919_H6_event'] = dict(n_events=int(ev.sum()), samebar_pct=round(100 * same.mean(), 1), within16_pct=round(100 * win16.mean(), 1),
                                   within16=seg(tr[win16], be), outside16=seg(tr[~win16], be))
    e_idx = np.flatnonzero(fresh_high(h6).values)
    rec = np.array([bool(np.any((e_idx <= e) & (e_idx > e - 3))) for e in eb])
    res['filter_S526_recent3_on_H6'] = dict(with_s526=seg(tr[rec], be), without_s526=seg(tr[~rec], be))
    mid = len(tr) // 2
    res['halves_wr'] = [round(100 * float((tr.iloc[:mid]['outcome'] == 'win').mean()), 2), round(100 * float((tr.iloc[mid:]['outcome'] == 'win').mean()), 2)]
    res['first_last'] = [str(pd.Timestamp(tr['t_entry'].iloc[0])), str(pd.Timestamp(tr['t_entry'].iloc[-1]))]
    yrs = pd.to_datetime(tr['t_entry']).dt.year
    res['per_year'] = {int(y): seg(tr[yrs == y], be) for y in sorted(yrs.unique())}
    with open(f'{OUT}/overlap_audit.json', 'w') as f: json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
