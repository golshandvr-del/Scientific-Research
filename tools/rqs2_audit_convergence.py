"""حسابرسیِ همگرایی — آماره‌های ناهمگرا در برابر همگرا روی همان توزیعِ جای‌گشت.

پرسش: اگر به‌جای `perm_max` (بیشینه) از یک آماره‌ی **همگرا** استفاده شود، آیا
حکم پایدار می‌شود؟

سه آماره روی **همان** قرعه‌ها محاسبه می‌شود:
  ▸ perm_max            — بیشینه. ناهمگرا: با K بی‌کران رشد می‌کند (√(2 ln K)).
  ▸ perm_p99            — صدکِ ۹۹. همگرا: به صدکِ حقیقیِ توزیع میل می‌کند.
  ▸ p_perm = (1+#{draw ≥ obs})/(K+1)  — p-valueِ استانداردِ مونت‌کارلو. همگرا،
    و **آماره‌ی کانونیِ آزمونِ جای‌گشت در ادبیات آماری** (نه بیشینه).

اگر پراکندگیِ بین-بذریِ perm_max بزرگ و پراکندگیِ p_perm کوچک باشد، اثبات
می‌شود که ناپایداریِ حکم از انتخابِ آماره می‌آید نه از داده.

⚠️ فقط اندازه‌گیری — هیچ تغییری در معیار داده نمی‌شود.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                            # noqa: E402
from strategies import s354_brooks_trend_resumption as base      # noqa: E402
from strategies import s354_causal_check as cc                   # noqa: E402

OUT = 'results/_audit_H3/convergence.json'
K = 2000
SEEDS = [11, 23, 47, 101, 199]
ASSET, TF = 'XAUUSD', 'H1'


def draws_and_obs(df, sig, sl, tp, mh, seed, n_perm):
    """توزیعِ خامِ جای‌گشت (نگه‌داشتنِ همهٔ قرعه‌ها، برخلافِ build_null_canonical)."""
    rng = np.random.default_rng(seed)
    o = df['open'].values.astype(float)
    h = df['high'].values.astype(float)
    lo = df['low'].values.astype(float)
    c = df['close'].values.astype(float)
    n = len(df)
    cfg = se.ASSETS[ASSET]
    pip = cfg['pip']
    cost = cfg['spread_pip'] + 2 * cfg.get('slip_pip', 0.0)
    sl_d, tp_d = sl * pip, tp * pip
    valid = np.arange(260, n - mh - 2)

    def wr_long(entries):
        wins = used = 0
        last_exit = -1
        for si in entries:
            if si <= last_exit:
                continue
            eb = si + 1
            if eb >= n:
                continue
            ent = o[eb]
            hit = None
            kend = min(eb + mh, n)
            for kk in range(eb, kend):
                if lo[kk] <= ent - sl_d:
                    hit = False
                    last_exit = kk
                    break
                if h[kk] >= ent + tp_d:
                    hit = True
                    last_exit = kk
                    break
            if hit is None:
                last = c[kend - 1]
                last_exit = kend - 1
                hit = ((last - ent) / pip - cost) > 0
            used += 1
            if hit:
                wins += 1
        return (100.0 * wins / used) if used else None

    obs = wr_long(np.flatnonzero(sig))
    k = int(sig.sum())
    per = []
    for _ in range(n_perm):
        pick = np.sort(rng.choice(valid, size=k, replace=False))
        w = wr_long(pick)
        if w is not None:
            per.append(w)
    return np.array(per), obs


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df = se.load_data(f'data/{ASSET}_{TF}.csv')
    atr = base._atr_pip(df, ASSET, base.TF_ATR_P.get(TF, 34))
    mh = base.TF_MAX_HOLD.get(TF, 20)
    sl = round(1.3 * atr, 1)
    tp = round(2.0 * sl, 1)
    gate = base.regime_gate(df, ('r2_fib_55', 'ge', 0.45))
    sig = cc.build_signals_causal(df, ASSET, TF, 0.13, 16, 0.8, 12.0) & gate

    rows = []
    if os.path.exists(OUT):
        try:
            rows = json.load(open(OUT)).get('runs', [])
        except Exception:
            rows = []
    done = {r['seed'] for r in rows}

    for sd in SEEDS:
        if sd in done:
            continue
        per, obs = draws_and_obs(df, sig, sl, tp, mh, sd, K)
        pmax = float(per.max())
        p99 = float(np.percentile(per, 99))
        p95 = float(np.percentile(per, 95))
        pval = float((1 + int((per >= obs).sum())) / (len(per) + 1))
        row = dict(seed=sd, K=len(per), obs_wr=obs, perm_max=pmax,
                   perm_p99=p99, perm_p95=p95, p_perm=pval,
                   passes_max=(obs > pmax), passes_p99=(obs > p99),
                   passes_p95=(obs > p95), passes_p_lt_05=(pval < 0.05))
        rows.append(row)
        json.dump({'layer': f'S354 causal {ASSET}-{TF}', 'K': K, 'runs': rows},
                  open(OUT, 'w'), indent=1, default=float)
        print(f"seed={sd:4d} obs={obs:6.2f} | max={pmax:6.2f} p99={p99:6.2f} "
              f"p95={p95:6.2f} p={pval:.4f} | >max={row['passes_max']} "
              f">p99={row['passes_p99']} p<.05={row['passes_p_lt_05']}", flush=True)

    print('\n=== پراکندگیِ بین-بذری (پایداریِ آماره) ===', flush=True)
    for key in ('perm_max', 'perm_p99', 'perm_p95', 'p_perm'):
        v = [r[key] for r in rows]
        print(f"  {key:9s} range=[{min(v):.4f},{max(v):.4f}] "
              f"spread={max(v) - min(v):.4f}", flush=True)
    for key, lab in (('passes_max', 'wr>perm_max'), ('passes_p99', 'wr>p99'),
                     ('passes_p95', 'wr>p95'), ('passes_p_lt_05', 'p<0.05')):
        v = [r[key] for r in rows]
        print(f"  حکمِ «{lab}»: {sum(v)}/{len(v)} پاس  "
              f"{'(پایدار)' if len(set(v)) == 1 else '⚠️ (ناپایدار)'}", flush=True)


if __name__ == '__main__':
    main()
