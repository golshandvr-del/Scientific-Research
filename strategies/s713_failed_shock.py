# -*- coding: utf-8 -*-
"""
S713 — Failed Informed-Shock Reversal — XAUUSD — Path C
پیاده‌سازیِ عینِ results/S713_PREREG_failed_shock_reversal.md (کامیت 81a643e5).

  python3 strategies/s713_failed_shock.py train M30,H1,H2,H3
  python3 strategies/s713_failed_shock.py judge M30,H1,H2,H3
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import rqs2                                    # noqa: E402
from engine import scalp_engine as se                     # noqa: E402
from strategies.s346_fast import barrier_outcomes         # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df   # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402

ASSET = 'XAUUSD'
FAMILY = ['M30', 'H1', 'H2']
INFO = ['H3']
D_GRID = ('mid', 'open')
ATR_P = 21
SHOCK_K = 2.618
RHO_MIN = 0.618
SL_K = 1.272
RR = 1.618
HOLD = 13
WARMUP = 250
MIN_N_TRAIN = 60
N_TRIALS = 12
SEED = 20260910
K_PERM = 500
UNCOND_CAP = 150_000
OUT = 'results/_scan_S713'


def log(m):
    print(m, flush=True)


def git_checkpoint(tag):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-q', '-m', f'S713 checkpoint: {tag}'], check=True)
        subprocess.run(['git', 'pull', '--rebase', '-q', 'origin', 'main'], check=False, timeout=120)
        subprocess.run(['git', 'push', '-q', 'origin', 'main'], check=True, timeout=120)
        log(f'    [git] checkpoint {tag} pushed')
    except Exception as e:                                   # noqa: BLE001
        log(f'    [git] WARN checkpoint failed: {e}')


def load(tf):
    d = fd.load_fast(ASSET, tf)
    assert 'mt5_full' in d['src'], f'دادهٔ کامل نیست: {d["src"]}'
    return d, fd.as_dataframe(d)


def atr_series(df, p):
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def features(df):
    """شوک در t (لبهٔ رویداد)، dir، سطوح mid/open، ATR در t−1."""
    o = df['open'].to_numpy(); h = df['high'].to_numpy()
    l = df['low'].to_numpy(); c = df['close'].to_numpy()
    n = len(df)
    atr = atr_series(df, ATR_P)
    atr_prev = np.full(n, np.nan); atr_prev[1:] = atr[:-1]
    rng = h - l
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(rng > 0, np.abs(c - o) / rng, 0.0)
    shock = (rng >= SHOCK_K * atr_prev) & (rho >= RHO_MIN) & (c != o)
    shock[:WARMUP] = False
    prev_shock = np.concatenate([[False], shock[:-1]])
    shock &= ~prev_shock                           # لبهٔ رویداد
    shock[-2:] = False                             # نیاز به t+1 و t+2
    t = np.where(shock)[0]
    dirn = np.sign(c[t] - o[t])
    return dict(t=t, dir=dirn, mid=(h[t] + l[t]) / 2.0, open=o[t], atr_prev=atr_prev, close=c)


def failed_mask(F, D):
    c1 = F['close'][F['t'] + 1]
    level = F['mid'] if D == 'mid' else F['open']
    return F['dir'] * (c1 - level) < 0


def run_side(df, sig, sl_price, hold, is_long):
    if len(sig) == 0:
        return None
    return queue_rr(df, sig, np.full(len(sig), is_long, dtype=bool), sl_price, ASSET, hold, RR)


def merge_sides(stl, sts):
    parts = [s for s in (stl, sts) if s is not None]
    if not parts:
        return None
    keys = ('pnl', 'win', 'entry_bar', 'exit_bar', 'is_long', 'sl_pip', 'tp_pip')
    st = {k: np.concatenate([p[k] for p in parts]) for k in keys}
    order = np.argsort(st['entry_bar'], kind='stable')
    st = {k: v[order] for k, v in st.items()}
    pnl = st['pnl']; win = pnl > 0
    gw = float(pnl[win].sum()); gl = float(-pnl[~win].sum())
    st.update(n=int(len(pnl)), wr=float(win.mean() * 100), exp=float(pnl.mean()),
              pf=float(gw / gl) if gl > 0 else 999.0)
    return st


def simulate(df, F, D, limit=None, follow=False):
    """reversal (پیش‌فرض) یا follow (فقط ابطال‌گر ج — گزارش، بدون داوری)."""
    m = failed_mask(F, D)
    t = F['t'][m]; dirn = F['dir'][m]
    if limit is not None:
        keep = t < limit; t, dirn = t[keep], dirn[keep]
    sig = t + 1                                    # ورود open t+2
    sl = SL_K * F['atr_prev'][t]                   # ATR در t−1
    trade_dir = dirn if follow else -dirn
    st = merge_sides(run_side(df, sig[trade_dir > 0], sl[trade_dir > 0], HOLD, True),
                     run_side(df, sig[trade_dir < 0], sl[trade_dir < 0], HOLD, False))
    return st, t


def build_null(df, F, n_long, n_short, rng):
    """استخر = همهٔ t+1 پس از هر شوک (بدون شرط ناکامی)، هر دو جهت."""
    pool = F['t'] + 1
    sl_all = SL_K * F['atr_prev'][F['t']]
    if len(pool) > UNCOND_CAP:
        sel = np.sort(rng.choice(len(pool), UNCOND_CAP, replace=False)); pool, sl_all = pool[sel], sl_all[sel]
    cfg = se.ASSETS[ASSET]
    out = {}
    for side, is_long, k in (('long', True, n_long), ('short', False, n_short)):
        if k <= 0:
            out[side] = None; continue
        fo = barrier_outcomes(df, pool, np.full(len(pool), is_long, dtype=bool), sl_all,
                              np.maximum(RR * sl_all, sl_all), HOLD, float(cfg['pip']),
                              float(cfg['spread_pip']), float(cfg.get('slip_pip', 0.0)))
        pnl_u = fo['pnl_pip']; m = len(pnl_u); kk = min(k, m)
        wrs = np.empty(K_PERM)
        for j in range(K_PERM):
            pick = rng.choice(m, size=kk, replace=False)
            wrs[j] = (pnl_u[pick] > 0).mean() * 100.0
        out[side] = dict(uncond_wr=float((pnl_u > 0).mean() * 100), perm_mean=float(wrs.mean()),
                         perm_sd=float(wrs.std(ddof=1)), perm_max=float(wrs.max()), perm_k=int(K_PERM),
                         pool_n=int(m))
        log(f'    null {side}: uncond={out[side]["uncond_wr"]:.2f} mean={out[side]["perm_mean"]:.2f} '
            f'sd={out[side]["perm_sd"]:.2f} pool={m}')
    return out


def train(tfs):
    os.makedirs(OUT, exist_ok=True)
    fp = f'{OUT}/TRAIN.json'
    res = json.load(open(fp)) if os.path.exists(fp) else {}
    for tf in tfs:
        d, df = load(tf)
        n = len(df); split = n // 2
        F = features(df)
        n_shock_train = int((F['t'] < split).sum())
        log(f'\nTRAIN {tf}: bars={n:,} split={split} shocks(train)={n_shock_train} src={d["src"]}')
        rows = []
        for D in D_GRID:
            st, t = simulate(df, F, D, limit=split)
            if st is None:
                rows.append(dict(D=D, n=0, score=None)); log(f'  D={D}: no trades'); continue
            net = float(st['pnl'].sum())
            score = st['exp'] * np.sqrt(st['n']) if (st['n'] >= MIN_N_TRAIN and net > 0) else None
            rows.append(dict(D=D, n=st['n'], n_events=int(len(t)), wr=st['wr'], exp=st['exp'],
                             pf=st['pf'], net=net, score=None if score is None else float(score)))
            log(f'  D={D}: events={len(t)} n={st["n"]} wr={st["wr"]:.2f} exp={st["exp"]:.3f} '
                f'pf={st["pf"]:.3f} net={net:.0f} score={score}')
        cands = [r for r in rows if r['score'] is not None]
        winner = None
        if cands:
            cands.sort(key=lambda r: (-r['score'], -r['n']))
            winner = cands[0]['D']
        res[tf] = dict(src=d['src'], n_bars=n, split=split, n_shock_train=n_shock_train,
                       grid=rows, winner=winner)
        log(f'  WINNER {tf}: D={winner}')
        json.dump(res, open(fp, 'w'), indent=1, ensure_ascii=False)
    git_checkpoint('TRAIN ' + ','.join(tfs))


def judge(tfs):
    T = json.load(open(f'{OUT}/TRAIN.json'))
    for tf in tfs:
        t0 = time.time()
        D = T[tf]['winner']
        d, df = load(tf)
        n = len(df); split = n // 2
        role = 'info' if tf in INFO else 'family'
        log(f'\n================ S713 · {ASSET} · {tf} (D={D}, {role}) ============')
        if D is None:
            r = dict(verdict='REJECT', rqs2_score=0.0, passed=False,
                     notes=['no TRAIN cell met n>=60 & net>0 — glass ceiling; holdout untouched (prereg §3)'])
            json.dump(dict(tf=tf, role=role, src=d['src'], n_bars=n, split_bar=split, D=None,
                           n_trials=N_TRIALS, seed=SEED, train=T[tf], rqs2=r),
                      open(f'{OUT}/{tf}.json', 'w'), indent=1, ensure_ascii=False)
            log(f'S713_FailedShock_{tf:<4} | REJECT RQS2= 0.0 | glass ceiling on TRAIN')
            git_checkpoint(tf); continue
        F = features(df)
        st, t = simulate(df, F, D)
        log(f'  shocks={len(F["t"])} failed={len(t)} trades={st["n"]} wr={st["wr"]:.2f}% '
            f'exp={st["exp"]:.3f} pf={st["pf"]:.3f}  [{time.time()-t0:.0f}s]')
        # ابطال‌گر (ج): follow پس از ناکامی — فقط گزارش
        stf, _ = simulate(df, F, D, follow=True)
        follow_stats = None if stf is None else dict(n=stf['n'], wr=stf['wr'], exp=stf['exp'], pf=stf['pf'])
        log(f'  [falsifier c] follow-after-failure: {follow_stats}')
        rng = np.random.default_rng(SEED)
        nl = int(st['is_long'].sum()); ns = st['n'] - nl
        null = build_null(df, F, nl, ns, rng)
        tr = trades_df(st)
        sl_med = float(np.median(tr['sl_pip'])); tp_med = float(np.median(tr['tp_pip']))
        r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                              bar_time=df['time'].to_numpy(), close=df['close'].to_numpy(),
                              null={k: ({kk: vv for kk, vv in v.items() if kk != 'pool_n'} if v else None)
                                    for k, v in null.items()},
                              n_trials=N_TRIALS, split_bar=split, allow_overlap=False)
        log(rqs2.format_rqs2(f'S713_FailedShock_{tf}', r))
        payload = dict(tf=tf, role=role, src=d['src'], n_bars=n, split_bar=split, D=D,
                       geometry=dict(atr_p=ATR_P, shock_k=SHOCK_K, rho_min=RHO_MIN, sl_k=SL_K, rr=RR, hold=HOLD),
                       n_trials=N_TRIALS, seed=SEED, k_perm=K_PERM,
                       stats=dict(n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'], n_long=nl, n_short=ns,
                                  n_shocks=int(len(F['t'])), n_failed=int(len(t))),
                       falsifier_c_follow=follow_stats, null=null, rqs2=r)
        json.dump(payload, open(f'{OUT}/{tf}.json', 'w'), indent=1, ensure_ascii=False, default=str)
        tr.to_csv(f'{OUT}/{tf}_trades.csv', index=False)
        log(f'  saved [{time.time()-t0:.0f}s]')
        git_checkpoint(tf)


if __name__ == '__main__':
    tfs = sys.argv[2].split(',') if len(sys.argv) > 2 else FAMILY + INFO
    train(tfs) if sys.argv[1] == 'train' else judge(tfs)
