# -*- coding: utf-8 -*-
"""
S505 — Dual-Numeraire Fresh High: frozen S526 base (90-bar fresh close-high, LONG)
× gate «XAUEUR also at its 90-bar high» (external EURUSD_H1 series, causal).
XAUUSD H8/H6/H12/D1 · data/mt5_full (15.6y) · RQS2 v2.6 untouched.

Prereg: results/S505_PREREG_DUAL_NUMERAIRE_FRESH_HIGH.md (commit 57ae4fa7, BEFORE any PnL).
Harness = tools/s526_fresh_high_runner.py verbatim (S382 simulator, S382 null model
constants K=2000 seed=20260805, tools/s382_mtf_runner.run_card judge call, split 0.70),
so CONFIRMED/UNCONFIRMED cards are directly comparable with S526's committed numbers.
Only additions: (1) data path -> data/mt5_full, (2) the gate, (3) falsifiers F1..F5,
(4) S526 reproduction check (H8 must match n=200 / WR=55.50 ± 0.5pp before any gated judge).
"""
from __future__ import annotations
import importlib.util, json, os, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)

OUT = 'results/_scan_S505'
CARDS = ['XAUUSD_H8', 'XAUUSD_H6', 'XAUUSD_H12', 'XAUUSD_D1']
TF_SECONDS = {'H8': 8 * 3600, 'H6': 6 * 3600, 'H12': 12 * 3600, 'D1': 24 * 3600}
N_TRIALS = 13          # 8 own cells + 5 inherited from S526 (prereg §5)
LOOKBACK = 90          # frozen S950/S523/S526
S526_H8_REF = dict(n=200, wr=55.50)   # committed S526 doc numbers (reproduction gate)
F1_LO, F1_HI, F2_GAIN, F3_NMIN = 0.10, 0.90, 1.0, 60


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def drift_mask(df):
    c = df['close']
    return ((c.shift(1) - c.shift(LOOKBACK)) > 0).fillna(False)


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


# ---------------------------------------------------------------- EUR series
_EUR = None
def eur_close_map():
    global _EUR
    if _EUR is None:
        e = pd.read_csv('data/EURUSD_H1.csv')
        _EUR = pd.Series(e['close'].to_numpy(float), index=e['time'].to_numpy(np.int64)).sort_index()
    return _EUR


def eur_at_bar_close(df, tf):
    """Last EURUSD H1 close with time <= (bar open + TF - 1h)  == causal at bar close."""
    eur = eur_close_map()
    t_close = df['time'].to_numpy(np.int64) + TF_SECONDS[tf] - 3600
    pos = eur.index.searchsorted(t_close, side='right') - 1
    out = np.where(pos >= 0, eur.to_numpy()[np.clip(pos, 0, len(eur) - 1)], np.nan)
    # stale guard: EUR close must be within the bar (not older than TF) -> else invalid
    age = t_close - eur.index.to_numpy()[np.clip(pos, 0, len(eur) - 1)]
    out = np.where((pos >= 0) & (age < TF_SECONDS[tf]), out, np.nan)
    return pd.Series(out, index=df.index)


def base_fresh_high(c):
    nh = (c > c.rolling(LOOKBACK).max().shift(1)).fillna(False)
    # pandas>=3: bool.shift().fillna() -> object dtype, and ~object inverts INTs (-1/-2, truthy)
    # => the S526 one-liner silently returns the STATE (807) instead of the EDGE (361). Cast explicitly.
    return nh & ~nh.shift(1, fill_value=False).astype(bool)


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')
    MTF.N_TRIALS = N_TRIALS

    def load_full(card):
        df = pd.read_csv(f'data/mt5_full/{card}.csv')
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df
    L.load = load_full

    # conditioned null in drift>0 space — verbatim S526
    def uncond_cond(L_, df, sl_abs, ps, stride):
        m = drift_mask(df).to_numpy(); idx = np.where(m)[0][::stride]
        sig = pd.Series(False, index=df.index); sig.iloc[idx] = True
        tr = L_.simulate_trades(df, sig, sl_abs, L_.RR, True, ps)
        return (100.0 * float((tr['outcome'] == 'win').mean()), len(tr)) if len(tr) else (None, 0)

    def perm_cond(L_, df, sl_abs, ps, n_sig, k=NM.K, seed=NM.SEED):
        rng = np.random.default_rng(seed); n = len(df)
        m = drift_mask(df).to_numpy(); valid = np.where(m[200:n - 2])[0] + 200
        wrs = []
        for _ in range(k):
            pos = rng.choice(valid, size=min(n_sig, len(valid)), replace=False)
            sig = pd.Series(False, index=df.index); sig.iloc[np.sort(pos)] = True
            tr = L_.simulate_trades(df, sig, sl_abs, L_.RR, True, ps)
            if len(tr) >= 30:
                wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
        a = np.asarray(wrs, float)
        return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), max=float(a.max()),
                    min=float(a.min()), p95=float(np.percentile(a, 95)), k=int(len(a)))
    NM.uncond_baseline = uncond_cond; NM.perm_baseline = perm_cond

    print(f'S505 dual-numeraire fresh high | base=S526 frozen | gate=XAUEUR 90-high state | '
          f'sl_k={L.SL_K} rr={L.RR} long | null K={NM.K} seed={NM.SEED} | n_trials={N_TRIALS} | prereg 57ae4fa7',
          flush=True)

    summary = []
    for card in (sys.argv[1:] or CARDS):
        tf = card.split('_')[1]
        df = load_full(card); ps = L.pip_size('XAUUSD')
        sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
        c = df['close'].astype(float)
        sig_usd = base_fresh_high(c)
        eur = eur_at_bar_close(df, tf)
        xe = c / eur
        nh_eur = (xe > xe.rolling(LOOKBACK).max().shift(1)).fillna(False) & eur.notna()
        valid_eur = eur.notna()
        sig_conf = sig_usd & nh_eur & valid_eur
        sig_unc = sig_usd & ~nh_eur & valid_eur

        # --- step 0: base (S526 reproduction on mt5_full with my code) -----------------
        tr_base = L.simulate_trades(df, sig_usd, sl_abs, L.RR, True, ps)
        wr_base = 100.0 * float((tr_base['outcome'] == 'win').mean()) if len(tr_base) else None
        rec = dict(card=card, bars=len(df), eur_coverage=round(float(valid_eur.mean()), 4),
                   n_sig_base=int(sig_usd.sum()), n_base=int(len(tr_base)), wr_base=wr_base,
                   n_sig_conf=int(sig_conf.sum()), n_sig_unc=int(sig_unc.sum()))
        print(f"\n[{card}] bars={len(df):,} eur_cov={rec['eur_coverage']} | BASE sig={rec['n_sig_base']} "
              f"n={rec['n_base']} WR={wr_base:.2f} | conf_sig={rec['n_sig_conf']} unc_sig={rec['n_sig_unc']}", flush=True)
        if tf == 'H8':
            ok = (rec['n_base'] == S526_H8_REF['n']) and abs(wr_base - S526_H8_REF['wr']) <= 0.5
            rec['s526_repro_ok'] = bool(ok)
            print(f"   S526-H8 reproduction: n={rec['n_base']} (ref 200) WR={wr_base:.2f} (ref 55.50) -> {'OK' if ok else 'FAIL'}", flush=True)
            if not ok:
                rec['verdict'] = 'STOP_REPRO_FAIL'; save(f'{card}.json', rec); summary.append(rec)
                print('   STOP per prereg §8 (no judge call).'); continue

        # --- step 1: gated + control trades ---------------------------------------------
        tr_conf = L.simulate_trades(df, sig_conf, sl_abs, L.RR, True, ps)
        tr_unc = L.simulate_trades(df, sig_unc, sl_abs, L.RR, True, ps)
        wr_conf = 100.0 * float((tr_conf['outcome'] == 'win').mean()) if len(tr_conf) else None
        wr_unc = 100.0 * float((tr_unc['outcome'] == 'win').mean()) if len(tr_unc) else None
        rec.update(n_conf=int(len(tr_conf)), wr_conf=wr_conf, n_unc=int(len(tr_unc)), wr_unc=wr_unc)
        print(f"   CONFIRMED n={rec['n_conf']} WR={wr_conf} | UNCONFIRMED n={rec['n_unc']} WR={wr_unc}", flush=True)

        # --- falsifiers ------------------------------------------------------------------
        dead = []
        removed = 1.0 - rec['n_sig_conf'] / max(1, rec['n_sig_base']); rec['gate_removed_frac'] = round(removed, 4)
        if not (F1_LO <= removed <= F1_HI): dead.append(f'F1 gate removes {removed:.1%}')
        if rec['n_conf'] < F3_NMIN: dead.append(f"F3 n_conf={rec['n_conf']}<{F3_NMIN}")
        if wr_conf is None or wr_base is None or wr_conf < wr_base + F2_GAIN:
            dead.append(f"F2 WR_conf {wr_conf} < WR_base {wr_base:.2f}+{F2_GAIN}")
        if wr_unc is not None and wr_conf is not None and wr_unc >= wr_conf:
            rec['F5_flag'] = True; print('   F5 FLAG: unconfirmed >= confirmed -> UNPROVEN cap', flush=True)
        # supplementary (no judge): uncond in drift>0 ∧ nh_eur space
        m2 = (drift_mask(df) & nh_eur).to_numpy(); idx2 = np.where(m2)[0]
        if len(idx2) > 30:
            s2 = pd.Series(False, index=df.index); s2.iloc[idx2] = True
            t2 = L.simulate_trades(df, s2, sl_abs, L.RR, True, ps)
            rec['uncond_drift_and_eurhigh'] = round(100.0 * float((t2['outcome'] == 'win').mean()), 2) if len(t2) else None
            print(f"   supplementary uncond (drift>0 ∧ eur-high) = {rec['uncond_drift_and_eurhigh']}", flush=True)
        rec['falsifiers_dead'] = dead
        if dead:
            rec['verdict'] = 'SELF-REJECT'; print(f'   DEAD (no judge call): {dead}', flush=True)
            save(f'{card}.json', rec); summary.append(rec); save('summary.json', summary); continue

        # --- single judge call on CONFIRMED (harness verbatim) -----------------------------
        L.signals = (lambda s: (lambda df_: s))(sig_conf)
        r = MTF.run_card(card, L, NM)
        # F4 (uncond conditioned lift) checked from the judge's own null
        if r.get('uncond_wr') is not None and wr_conf - r['uncond_wr'] <= 0:
            r['F4_dead'] = True; r['verdict'] = 'SELF-REJECT(F4)'
        if rec.get('F5_flag') and r.get('verdict') == 'ACCEPT':
            r['verdict'] = 'UNPROVEN'; r['capped_by'] = 'F5'
        rec.update(judge=r, verdict=r.get('verdict'), rqs2=r.get('rqs2'))
        g = r.get('gates') or {}
        gates = ' '.join(f"H{i}:{'✓' if g.get('H%d' % i) else '✗'}" for i in range(11))
        print(f"S505-{tf}-CONFIRMED | {r.get('verdict')} RQS2={r.get('rqs2')} | n={r.get('n_trades')} WR={r.get('wr')} "
              f"lift={r.get('lift')} unc={r.get('uncond_wr')} pmax={r.get('perm_max')} z={r.get('z')} PF={r.get('pf')} | {gates}", flush=True)
        save(f'{card}.json', rec); summary.append(rec); save('summary.json', summary)
    print('\nDONE')


if __name__ == '__main__':
    main()
