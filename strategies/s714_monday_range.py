# -*- coding: utf-8 -*-
"""
S714 — Monday-Range Weekly Breakout — XAUUSD — Path C (zero-search; TRAIN = power gate)
پیاده‌سازیِ عینِ results/S714_PREREG_monday_range_weekly_breakout.md (کامیت 72264455).

  python3 strategies/s714_monday_range.py judge M15,M30,H1,H4
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
FAMILY = ['M15', 'M30', 'H1']
INFO = ['H4']
ATR_P = 89
RANGE_MIN_K = 0.618
SL_K = 1.272
RR = 1.618
HOLD_H = 48.0
DAY_COVERAGE = 0.75
MIN_N_TRAIN = 60
N_TRIALS = 4
SEED = 20260911
K_PERM = 500
UNCOND_CAP = 150_000
OUT = 'results/_scan_S714'


def log(m):
    print(m, flush=True)


def git_checkpoint(tag):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-q', '-m', f'S714 checkpoint: {tag}'], check=True)
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
    """رویدادها: اولین بستهٔ سه‌شنبه–جمعه خارج از [ML, MH] دوشنبهٔ همان هفته.
    برمی‌گرداند: idx_event (کندل j)، جهت، ماسک کندل‌های واجدِ null (سه‌شنبه–جمعهٔ هفته‌های واجد)."""
    sec = df['time'].to_numpy().astype('int64')
    ts = pd.DatetimeIndex(sec.astype('datetime64[s]'))
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy()
    n = len(df)
    atr = atr_series(df, ATR_P)
    dow = ts.dayofweek.to_numpy()
    # شناسهٔ هفته: تعداد روز از مبدأ، تقسیم بر ۷ با مبدأ دوشنبه
    days = (sec // 86400).astype(np.int64)
    week_id = (days - 3) // 7          # 1970-01-01 پنج‌شنبه بود ⇒ −3 مبدأ را به دوشنبه می‌برد
    bars_per_day = int(round(1440 / fd.TF_MINUTES[tf]))
    need = int(np.ceil(DAY_COVERAGE * bars_per_day))
    ev_idx, ev_dir, ev_dow = [], [], []
    null_mask = np.zeros(n, dtype=bool)
    order = np.arange(n)
    # گروه‌بندی سریع با تغییر week_id
    starts = np.concatenate([[0], np.where(np.diff(week_id) != 0)[0] + 1, [n]])
    for a, b in zip(starts[:-1], starts[1:]):
        sl_ = slice(a, b)
        d_ = dow[sl_]
        mon = order[sl_][d_ == 0]
        if len(mon) < need:
            continue
        MH = h[mon].max(); ML = l[mon].min()
        rest = order[sl_][d_ > 0]
        if len(rest) == 0:
            continue
        null_mask[rest] = True
        j0 = rest[0]
        if not np.isfinite(atr[j0 - 1]) or (MH - ML) < RANGE_MIN_K * atr[j0 - 1]:
            continue
        up = c[rest] > MH; dn = c[rest] < ML
        hit = np.where(up | dn)[0]
        if len(hit) == 0:
            continue
        j = rest[hit[0]]
        ev_idx.append(j); ev_dir.append(1 if c[j] > MH else -1); ev_dow.append(int(dow[j]))
    ev_idx = np.asarray(ev_idx, dtype=np.int64); ev_dir = np.asarray(ev_dir)
    ev_idx_ok = ev_idx < n - 2
    return dict(idx=ev_idx[ev_idx_ok], dir=ev_dir[ev_idx_ok], dow=np.asarray(ev_dow)[ev_idx_ok],
                atr=atr, null_mask=null_mask)


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


def simulate(df, F, hold, limit=None):
    idx, dirn = F['idx'], F['dir']
    if limit is not None:
        keep = idx < limit; idx, dirn = idx[keep], dirn[keep]
    sl = SL_K * F['atr'][idx]
    return merge_sides(run_side(df, idx[dirn > 0], sl[dirn > 0], hold, True),
                       run_side(df, idx[dirn < 0], sl[dirn < 0], hold, False))


def build_null(df, F, hold, n_long, n_short, rng):
    pool = np.where(F['null_mask'])[0]
    pool = pool[pool < len(df) - 2]
    if len(pool) > UNCOND_CAP:
        pool = np.sort(rng.choice(pool, UNCOND_CAP, replace=False))
    sl_all = SL_K * F['atr'][pool]
    ok = np.isfinite(sl_all) & (sl_all > 0); pool, sl_all = pool[ok], sl_all[ok]
    cfg = se.ASSETS[ASSET]
    out = {}
    for side, is_long, k in (('long', True, n_long), ('short', False, n_short)):
        if k <= 0:
            out[side] = None; continue
        fo = barrier_outcomes(df, pool, np.full(len(pool), is_long, dtype=bool), sl_all,
                              np.maximum(RR * sl_all, sl_all), hold, float(cfg['pip']),
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


def judge(tfs):
    os.makedirs(OUT, exist_ok=True)
    for tf in tfs:
        t0 = time.time()
        d, df = load(tf)
        n = len(df); split = n // 2
        hold = fd.hold_bars_for(tf, HOLD_H)
        role = 'info' if tf in INFO else 'family'
        log(f'\n================ S714 · {ASSET} · {tf} ({role}) hold={hold} ============')
        F = features(df, tf)
        # --- دروازهٔ توان روی نیمهٔ اول (prereg §3) ---
        st_tr = simulate(df, F, hold, limit=split)
        tr_stats = None if st_tr is None else dict(n=st_tr['n'], wr=st_tr['wr'], exp=st_tr['exp'],
                                                    pf=st_tr['pf'], net=float(st_tr['pnl'].sum()))
        log(f'  TRAIN gate: {tr_stats}')
        if st_tr is None or st_tr['n'] < MIN_N_TRAIN or float(st_tr['pnl'].sum()) <= 0:
            r = dict(verdict='REJECT', rqs2_score=0.0, passed=False,
                     notes=['TRAIN power gate failed (n<60 or net<=0) — holdout untouched (prereg §3)'])
            json.dump(dict(tf=tf, role=role, src=d['src'], n_bars=n, split_bar=split, train=tr_stats,
                           n_events_total=int(len(F['idx'])), n_trials=N_TRIALS, seed=SEED, rqs2=r),
                      open(f'{OUT}/{tf}.json', 'w'), indent=1, ensure_ascii=False)
            log(f'S714_MondayRange_{tf:<4} | REJECT RQS2= 0.0 | TRAIN gate failed')
            git_checkpoint(tf); continue
        # --- داوری کل‌داده ---
        st = simulate(df, F, hold)
        dow_hist = {int(k): int(v) for k, v in pd.Series(F['dow']).value_counts().sort_index().items()}
        log(f'  events={len(F["idx"])} dow={dow_hist} trades={st["n"]} wr={st["wr"]:.2f}% '
            f'exp={st["exp"]:.3f} pf={st["pf"]:.3f}  [{time.time()-t0:.0f}s]')
        rng = np.random.default_rng(SEED)
        nl = int(st['is_long'].sum()); ns = st['n'] - nl
        null = build_null(df, F, hold, nl, ns, rng)
        tr = trades_df(st)
        sl_med = float(np.median(tr['sl_pip'])); tp_med = float(np.median(tr['tp_pip']))
        r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                              bar_time=df['time'].to_numpy(), close=df['close'].to_numpy(),
                              null=null, n_trials=N_TRIALS, split_bar=split, allow_overlap=False)
        log(rqs2.format_rqs2(f'S714_MondayRange_{tf}', r))
        payload = dict(tf=tf, role=role, src=d['src'], n_bars=n, split_bar=split, train=tr_stats,
                       geometry=dict(atr_p=ATR_P, range_min_k=RANGE_MIN_K, sl_k=SL_K, rr=RR, hold_bars=hold),
                       n_trials=N_TRIALS, seed=SEED, k_perm=K_PERM,
                       stats=dict(n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'], n_long=nl, n_short=ns,
                                  n_events=int(len(F['idx']))),
                       event_dow=dow_hist, null=null, rqs2=r)
        json.dump(payload, open(f'{OUT}/{tf}.json', 'w'), indent=1, ensure_ascii=False, default=str)
        tr.to_csv(f'{OUT}/{tf}_trades.csv', index=False)
        log(f'  saved [{time.time()-t0:.0f}s]')
        git_checkpoint(tf)


if __name__ == '__main__':
    tfs = sys.argv[2].split(',') if len(sys.argv) > 2 else FAMILY + INFO
    judge(tfs)
