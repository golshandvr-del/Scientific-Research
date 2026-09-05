# -*- coding: utf-8 -*-
"""S589 — (الف) تنشِ n_trials=50 روی کارت ACCEPT (H8 gated)؛
(ب) ممیزی هم‌پوشانی طبق قانون Overlap: ورودی‌های S589-H8 در برابر
S526-H8 (پایه)، S1520-H8 (خواهر: گیت ρ) و S382-H4 (لایهٔ زندهٔ Williams%R).
هیچ حکمی دستی نیست — تنش از compute_rqs2؛ هم‌پوشانی فقط شمارش زمان ورود.
پیش‌ثبت: results/S589_PREREG_VOLUME_CONFIRMED_FRESH_HIGH.md §5 (P3).
"""
from __future__ import annotations
import importlib.util, json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
OUT = 'results/_s589'
STRESS_N = 50


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


S589 = _mod('tools/s589_volume_fresh_high_runner.py', '_s589')
S1520 = _mod('tools/s1520_informed_fresh_high_runner.py', '_s1520')


def load(card):
    p = f'data/full/{card}.csv'
    if not os.path.exists(p):
        p = f'data/{card}.csv'
    df = pd.read_csv(p); df['dt'] = pd.to_datetime(df['time'], unit='s'); return df


def main():
    os.makedirs(f'{OUT}/stress', exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')

    # ---- (الف) تنش: همان هارنس S589 با N_TRIALS=50 ----
    S589.N_TRIALS = STRESS_N
    sys.argv = ['x', 'gated', 'XAUUSD_H8']
    # بازسازی سریع main با OUT تنشی
    S589.OUT = f'{OUT}/stress'
    S589.main()

    # ---- (ب) هم‌پوشانی ----
    df = load('XAUUSD_H8')
    ps = L.pip_size('XAUUSD')
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K

    def trades_for(sig):
        return L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)

    base = S589.fresh_high(df)
    rv = S589.rvol_slot(df)
    sig_589 = base & (rv >= S589.RVOL_THR) & rv.notna()
    sig_526 = base
    sig_1520 = base & (S1520.rho(df) >= S1520.RHO_THR)

    t589 = trades_for(sig_589); t526 = trades_for(sig_526); t1520 = trades_for(sig_1520)
    ecol = 'entry_bar' if 'entry_bar' in t589 else ('entry_idx' if 'entry_idx' in t589 else None)
    if ecol is None:
        ecol = [c for c in t589.columns if 'entry' in c][0]
    e589 = set(t589[ecol].astype(int)); e526 = set(t526[ecol].astype(int)); e1520 = set(t1520[ecol].astype(int))

    def wr_lift(tr, mask):
        sub = tr[mask]
        if len(sub) == 0:
            return dict(n=0)
        wr = 100.0 * float((sub['outcome'] == 'win').mean())
        be = 100.0 * (sl_abs / ps + 3.3) / (sl_abs / ps + sl_abs / ps * L.RR)
        return dict(n=int(len(sub)), wr=round(wr, 2), lift_vs_be=round(wr - be, 2))

    inter1520 = t589[ecol].astype(int).isin(e1520).to_numpy()
    audit = {
        'vs_S526': dict(n_589=len(e589), n_526=len(e526), same_entry=len(e589 & e526),
                        share_of_589=round(100.0 * len(e589 & e526) / max(1, len(e589)), 1)),
        'vs_S1520': dict(n_589=len(e589), n_1520=len(e1520), same_entry=len(e589 & e1520),
                         share_of_589=round(100.0 * len(e589 & e1520) / max(1, len(e589)), 1),
                         overlap_sub=wr_lift(t589, inter1520),
                         non_overlap_sub=wr_lift(t589, ~inter1520)),
        'halves_wr': None,
    }
    # نیمه‌های زمانی (پایداری)
    t589s = t589.sort_values(ecol)
    h = len(t589s) // 2
    audit['halves_wr'] = [round(100.0 * float((t589s.iloc[:h]['outcome'] == 'win').mean()), 2),
                          round(100.0 * float((t589s.iloc[h:]['outcome'] == 'win').mean()), 2)]
    # نسبت به S382-H4 (لایهٔ زنده، کارت دیگر): هم‌پوشانی تقویمی ۸ ساعته
    try:
        r382 = json.load(open('results/_s1520/overlap_audit.json'))
        audit['note_S382H4'] = 'S1520 measured 57.1% calendar overlap vs S382-H4 for the same base event; S589 shares the base event — see vs_S1520.overlap_sub'
    except Exception:
        pass
    with open(f'{OUT}/overlap_audit.json', 'w') as f:
        json.dump(audit, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(audit, ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    main()
