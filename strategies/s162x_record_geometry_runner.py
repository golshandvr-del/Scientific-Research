# -*- coding: utf-8 -*-
"""S1620–S1629 — «هندسهٔ رکورد» — اقلیدس. رانر مشترک بلوک.

پایه: لبهٔ تازهٔ سقفِ ۹۰-کندلی (S526، منجمد). هارنس عیناً S1520:
`tools/s382_mtf_runner.run_card` + `tools/s382_null_model` (نول شرطی در فضای درفت>0)،
شبیه‌ساز S382. **تنها** چیزی که هر لایه تغییر می‌دهد، تابع گیت است.

استفاده:  python3 strategies/s162x_record_geometry_runner.py <layer> <mode> [CARDS...]
  layer ∈ CFG · mode ∈ {gated, counter, base}  (base = گیت خاموش = بازتولید S526 — گارد G0)
"""
from __future__ import annotations
import importlib.util, json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
LOOKBACK = 90  # منجمد S526

CFG = {
    # S1620: سن رکورد — فاصلهٔ t تا argmax(close[t-90..t-1]) ≥ 45
    's1620': dict(name='RecordAgeGate', cards=['XAUUSD_H8', 'XAUUSD_H6', 'XAUUSD_H12'], n_trials=7, age_min=45),
    # S1621: حاشیهٔ شکست — (close − prevmax90) / ATR100[t−1] ≥ 0.25
    's1621': dict(name='RecordMarginGate', cards=['XAUUSD_H8', 'XAUUSD_H6', 'XAUUSD_H12'], n_trials=6, margin_min=0.25),
}


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def drift_mask(df):
    c = df['close']; return ((c.shift(1) - c.shift(LOOKBACK)) > 0).fillna(False)


def fresh_high(df):
    c = df['close']; nh = (c > c.rolling(LOOKBACK).max().shift(1)).fillna(False)
    return nh & ~nh.shift(1).fillna(False)


def record_age(df):
    """age[t] = t − argmax(close[t−90..t−1]); tie ⇒ جدیدترین (age کوچک‌تر، محافظه‌کار)."""
    c = df['close'].to_numpy(float); n = len(c); age = np.full(n, np.nan)
    for t in range(LOOKBACK, n):
        w = c[t - LOOKBACK:t]                      # اندیس‌های t-90..t-1
        j = LOOKBACK - 1 - int(np.argmax(w[::-1]))  # آخرین بیشینه (جدیدترین در tie)
        age[t] = LOOKBACK - j                       # j=89 ⇒ age=1 ؛ j=0 ⇒ age=90
    return pd.Series(age, index=df.index)


def atr100_causal(df, p=100):
    """عیناً تابع atr ماژول S382 (RMA(TR,p))، شیفت ۱ ⇒ علّی."""
    h, l, c = df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean().shift(1)


def record_margin(df):
    c = df['close'].astype(float)
    prevmax = c.rolling(LOOKBACK).max().shift(1)
    return (c - prevmax) / atr100_causal(df)


def gate_fn(layer, cfg, df):
    if layer == 's1620':
        a = record_age(df); return a >= cfg['age_min'], a
    if layer == 's1621':
        m = record_margin(df); return m >= cfg['margin_min'], m
    raise KeyError(layer)


def main():
    layer = sys.argv[1]; cfg = CFG[layer]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'gated'
    assert mode in ('gated', 'counter', 'base')
    cards = [a for a in sys.argv[3:] if a.startswith('XAUUSD')] or cfg['cards']
    OUT = f'results/_{layer}'; os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')
    MTF.N_TRIALS = cfg['n_trials']

    def load_full(card):
        path = f'data/mt5_full/{card}.csv'
        assert os.path.exists(path) and 'mt5_full' in path, path   # گارد دادهٔ کامل
        df = pd.read_csv(path); df['dt'] = pd.to_datetime(df['time'], unit='s'); return df
    L.load = load_full

    stats = {}

    def signals(df):
        base = fresh_high(df)
        if mode == 'base':
            sig = base; g = None
        else:
            g, aux = gate_fn(layer, cfg, df)
            g = g.fillna(False) if hasattr(g, 'fillna') else g
            sig = base & (g if mode == 'gated' else ~g)
        nb, ns = int(base.sum()), int(sig.sum())
        stats.update(n_base=nb, n_sig=ns, pass_rate=round(100.0 * ns / max(1, nb), 1))
        print(f'  base={nb} sig={ns} pass-rate={stats["pass_rate"]}% mode={mode}', flush=True)
        return sig
    L.signals = signals

    # نول شرطی در فضای درفت>0 — عیناً S526/S1520
    def uncond_cond(L_, df, sl_abs, ps, stride):
        m = drift_mask(df).to_numpy(); idx = np.where(m)[0][::stride]
        sig = pd.Series(False, index=df.index); sig.iloc[idx] = True
        tr = L_.simulate_trades(df, sig, sl_abs, L_.RR, True, ps)
        return (None, 0) if len(tr) == 0 else (100.0 * float((tr['outcome'] == 'win').mean()), len(tr))

    def perm_cond(L_, df, sl_abs, ps, n_sig, k=NM.K, seed=NM.SEED):
        rng = np.random.default_rng(seed); n = len(df); m = drift_mask(df).to_numpy()
        valid = np.where(m[200:n - 2])[0] + 200; wrs = []
        for _ in range(k):
            pos = rng.choice(valid, size=min(n_sig, len(valid)), replace=False)
            sig = pd.Series(False, index=df.index); sig.iloc[np.sort(pos)] = True
            tr = L_.simulate_trades(df, sig, sl_abs, L_.RR, True, ps)
            if len(tr) >= 30: wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
        a = np.asarray(wrs, float)
        return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), max=float(a.max()), min=float(a.min()),
                    p95=float(np.percentile(a, 95)), k=int(len(a)))
    NM.uncond_baseline = uncond_cond; NM.perm_baseline = perm_cond

    print(f'{layer.upper()} {cfg["name"]} [{mode}] sl_k={L.SL_K} rr={L.RR} long | cond-null(drift>0) K={NM.K} n_trials={cfg["n_trials"]}', flush=True)
    for card in cards:
        stats.clear()
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True); continue
        r.update(layer=layer, mode=mode, lookback=LOOKBACK, cfg={k: v for k, v in cfg.items() if k != 'cards'}, **stats)
        json.dump(r, open(f'{OUT}/{card}_{mode}.json', 'w'), ensure_ascii=False, default=str)
        print(f'{card} [{mode}]: n={r.get("n_trades")} (sig={r.get("n_signals")}) sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} pmean={r.get("perm_mean")} pmax={r.get("perm_max")} z={r.get("z")} '
              f'pf={r.get("pf")} rqs2={r.get("rqs2")} verdict={r.get("verdict")}', flush=True)
        g = r.get('gates') or {}
        print('  gates: ' + ' '.join(f"H{i}{'✓' if g.get(f'H{i}') else '✗'}" for i in range(11)) + f'  notes={r.get("notes")}', flush=True)


if __name__ == '__main__':
    main()
