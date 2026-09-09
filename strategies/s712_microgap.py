# -*- coding: utf-8 -*-
"""
S712 — Intraday Micro-Gap Follow — XAUUSD — Path C
پیاده‌سازیِ عینِ results/S712_PREREG_intraday_microgap_follow.md (کامیت 6a9819a).

  python3 strategies/s712_microgap.py train M5,M15,M30,H1   # نیمهٔ اول هر TF، ۳ سلول θ
  python3 strategies/s712_microgap.py judge M5,M15,M30,H1   # θ برنده، کل‌داده، split=n//2

درس‌ها: BUG-EPOCH (ثانیه→datetime64[s])، BUG-ASI8 (gap از ثانیهٔ خام)،
قراردادِ barrier_outcomes (sig_idx=t ⇒ ورود open t+1).
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
FAMILY = ['M5', 'M15', 'M30', 'H1']
THETA_GRID = (0.146, 0.236, 0.382)
ATR_P = 34
SL_K = 1.272
RR = 1.618
HOLD_H = 8.0
MIN_N_TRAIN = 100
N_TRIALS = 16
SEED = 20260909
K_PERM = 500
UNCOND_CAP = 150_000
OUT = 'results/_scan_S712'


def log(m):
    print(m, flush=True)


def git_checkpoint(tag):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-q', '-m', f'S712 checkpoint: {tag}'], check=True)
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


def features(df, tf):
    """gap_t، واجد بودن (هم‌روزی)، ATR در t−1. همه علّی نسبت به ورود در t+1."""
    sec = df['time'].to_numpy().astype('int64')
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    tf_sec = fd.TF_MINUTES[tf] * 60.0
    gap = np.full(len(df), np.nan)
    gap[1:] = o[1:] - c[:-1]
    dt = np.full(len(df), np.inf)
    dt[1:] = np.diff(sec)
    eligible = dt <= max(1800.0, 1.5 * tf_sec)
    atr = atr_series(df, ATR_P)
    atr_prev = np.full(len(df), np.nan)
    atr_prev[1:] = atr[:-1]
    eligible &= np.isfinite(atr_prev) & (atr_prev > 0)
    eligible[:ATR_P * 3] = False           # گرم‌شدن ATR
    ratio = np.where(eligible, np.abs(gap) / np.where(atr_prev > 0, atr_prev, np.nan), np.nan)
    return gap, ratio, eligible, atr_prev


def events(gap, ratio, eligible, theta):
    ev = eligible & (ratio >= theta)
    # لبهٔ رویداد: کندل قبلی رویداد نباشد
    prev = np.concatenate([[False], ev[:-1]])
    ev &= ~prev
    idx = np.where(ev)[0]
    return idx, np.sign(gap[idx])


def run_side(df, sig, atr_prev, hold, is_long):
    if len(sig) == 0:
        return None
    return queue_rr(df, sig, np.full(len(sig), is_long, dtype=bool),
                    SL_K * atr_prev[sig], ASSET, hold, RR)


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


def simulate(df, tf, theta, gap, ratio, eligible, atr_prev, limit=None):
    hold = fd.hold_bars_for(tf, HOLD_H)
    idx, sgn = events(gap, ratio, eligible, theta)
    if limit is not None:
        keep = idx < limit
        idx, sgn = idx[keep], sgn[keep]
    st = merge_sides(run_side(df, idx[sgn > 0], atr_prev, hold, True),
                     run_side(df, idx[sgn < 0], atr_prev, hold, False))
    return st, hold, idx


def build_null(df, eligible, atr_prev, hold, n_long, n_short, rng):
    pool = np.where(eligible)[0]
    if len(pool) > UNCOND_CAP:
        pool = np.sort(rng.choice(pool, UNCOND_CAP, replace=False))
    cfg = se.ASSETS[ASSET]
    out = {}
    for side, is_long, k in (('long', True, n_long), ('short', False, n_short)):
        if k <= 0:
            out[side] = None; continue
        sl = SL_K * atr_prev[pool]
        fo = barrier_outcomes(df, pool, np.full(len(pool), is_long, dtype=bool), sl,
                              np.maximum(RR * sl, sl), hold, float(cfg['pip']),
                              float(cfg['spread_pip']), float(cfg.get('slip_pip', 0.0)))
        pnl_u = fo['pnl_pip']; m = len(pnl_u); kk = min(k, m)
        wrs = np.empty(K_PERM)
        for j in range(K_PERM):
            pick = rng.choice(m, size=kk, replace=False)
            wrs[j] = (pnl_u[pick] > 0).mean() * 100.0
        out[side] = dict(uncond_wr=float((pnl_u > 0).mean() * 100), perm_mean=float(wrs.mean()),
                         perm_sd=float(wrs.std(ddof=1)), perm_max=float(wrs.max()), perm_k=int(K_PERM))
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
        gap, ratio, eligible, atr_prev = features(df, tf)
        log(f'\nTRAIN {tf}: bars={n:,} split={split} src={d["src"]}')
        rows = []
        for th in THETA_GRID:
            st, hold, idx = simulate(df, tf, th, gap, ratio, eligible, atr_prev, limit=split)
            if st is None:
                rows.append(dict(theta=th, n=0, score=None)); log(f'  θ={th}: no trades'); continue
            # ⚠️ معاملاتی که ورودشان قبل از split است ولی خروجشان بعد — قبول (hold ≤ 8h، ناچیز)
            net = float(st['pnl'].sum())
            score = st['exp'] * np.sqrt(st['n']) if (st['n'] >= MIN_N_TRAIN and net > 0) else None
            rows.append(dict(theta=th, n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'], net=net,
                             n_events=int(len(idx)), score=None if score is None else float(score)))
            log(f'  θ={th}: events={len(idx)} n={st["n"]} wr={st["wr"]:.2f} exp={st["exp"]:.3f} '
                f'pf={st["pf"]:.3f} net={net:.0f} score={score}')
        cands = [r for r in rows if r['score'] is not None]
        winner = None
        if cands:
            cands.sort(key=lambda r: (-r['score'], -r['n']))
            winner = cands[0]['theta']
        res[tf] = dict(src=d['src'], n_bars=n, split=split, grid=rows, winner=winner)
        log(f'  WINNER {tf}: θ={winner}')
        json.dump(res, open(fp, 'w'), indent=1, ensure_ascii=False)
    git_checkpoint('TRAIN ' + ','.join(tfs))


def judge(tfs):
    T = json.load(open(f'{OUT}/TRAIN.json'))
    for tf in tfs:
        t0 = time.time()
        th = T[tf]['winner']
        d, df = load(tf)
        n = len(df); split = n // 2
        log(f'\n================ S712 · {ASSET} · {tf} (θ={th}) ============')
        if th is None:
            r = dict(verdict='REJECT', rqs2_score=0.0, passed=False,
                     notes=['no TRAIN cell met n>=100 & net>0 — glass ceiling; holdout untouched (prereg §3)'])
            payload = dict(tf=tf, src=d['src'], n_bars=n, split_bar=split, theta=None,
                           n_trials=N_TRIALS, seed=SEED, train=T[tf], rqs2=r)
            json.dump(payload, open(f'{OUT}/{tf}.json', 'w'), indent=1, ensure_ascii=False)
            log(f'S712_MicroGap_{tf:<4} | REJECT RQS2= 0.0 | glass ceiling on TRAIN')
            git_checkpoint(tf); continue
        gap, ratio, eligible, atr_prev = features(df, tf)
        st, hold, idx = simulate(df, tf, th, gap, ratio, eligible, atr_prev)
        log(f'  events={len(idx)} trades={st["n"]} wr={st["wr"]:.2f}% exp={st["exp"]:.3f} '
            f'pf={st["pf"]:.3f} hold={hold}  [{time.time()-t0:.0f}s]')
        # توزیع ساعت رویدادها (ابطال‌گر ب)
        hrs = pd.DatetimeIndex(df['time'].to_numpy()[idx].astype('int64').astype('datetime64[s]')).hour
        hour_hist = {int(k): int(v) for k, v in pd.Series(hrs).value_counts().sort_index().items()}
        log(f'  event hours: {hour_hist}')
        rng = np.random.default_rng(SEED)
        nl = int(st['is_long'].sum()); ns = st['n'] - nl
        null = build_null(df, eligible, atr_prev, hold, nl, ns, rng)
        tr = trades_df(st)
        sl_med = float(np.median(tr['sl_pip'])); tp_med = float(np.median(tr['tp_pip']))
        r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                              bar_time=df['time'].to_numpy(), close=df['close'].to_numpy(),
                              null=null, n_trials=N_TRIALS, split_bar=split, allow_overlap=False)
        log(rqs2.format_rqs2(f'S712_MicroGap_{tf}', r))
        payload = dict(tf=tf, src=d['src'], n_bars=n, split_bar=split, theta=th,
                       geometry=dict(atr_p=ATR_P, sl_k=SL_K, rr=RR, hold_bars=hold),
                       n_trials=N_TRIALS, seed=SEED, k_perm=K_PERM,
                       stats=dict(n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'],
                                  n_long=nl, n_short=ns, n_events=int(len(idx))),
                       event_hours=hour_hist, null=null, rqs2=r)
        json.dump(payload, open(f'{OUT}/{tf}.json', 'w'), indent=1, ensure_ascii=False, default=str)
        tr.to_csv(f'{OUT}/{tf}_trades.csv', index=False)
        log(f'  saved [{time.time()-t0:.0f}s]')
        git_checkpoint(tf)


if __name__ == '__main__':
    tfs = sys.argv[2].split(',') if len(sys.argv) > 2 else FAMILY
    train(tfs) if sys.argv[1] == 'train' else judge(tfs)
