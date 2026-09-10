# -*- coding: utf-8 -*-
"""
S555 — رکوردِ کف (Floor Lift-Off) ⇒ ادامهٔ LONG — طلا، TFهای درشت
==================================================================
پیش‌ثبت: results/S555_PREREG_FLOOR_LIFTOFF_HIGHER_LOW_RECORD.md (commit 938a98c6)
که **پیش از نوشتنِ این فایل** به GitHub رفت. Path B — صفر اکتشاف.

  رویداد : low[t] > max(low[t−90 .. t−1])  — فقط لبهٔ تازه (ev & ~ev[t−1])
  گیت    : drift = close[t−1] − close[t−90] > 0   (فضای سیگنال ⊆ فضای نول)
  جهت    : LONG-only (قانون S522/S528)
  هندسه  : وراثت کلمه‌به‌کلمه از S526 ACCEPT — SL=1.5×ATR100(t−1)، TP=1.5×SL،
           mh=21، allow_overlap=False
  نول    : شرطی‌شده در فضای drift>0 — uncond (همهٔ کندل‌های drift>0) +
           perm K=1000 قرعهٔ هم‌حجم از همان فضا (SEED=20260909)
  بودجه  : n_trials=12

اجرا:  python3 strategies/s555_floor_liftoff.py [CARD ...]   (پیش‌فرض: H8 H6 H12 D1)
       python3 strategies/s555_floor_liftoff.py --smoke H8   (فقط شمارش سیگنال)
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                # noqa: E402
from engine import rqs2                                              # noqa: E402
from tools import s434_fast_data as fd                               # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df             # noqa: E402

ASSET = 'XAUUSD'
SEED = 20260909
N_TRIALS = 12
SPLIT_FRAC = 0.60
OUT = 'results/_scan_S555'
PREREG = '938a98c6'

# —— پیکربندی منجمدِ پیش‌ثبت ——
W = 90                # پنجرهٔ رکورد کف / درفت (S526/S950/S523)
SL_K = 1.5            # وراثت S526
RR = 1.5              # وراثت S526 (TP>SL ⇒ قانون بودجه)
ATR_GEO = 100         # ATR هندسه
MH = 21               # وراثت S526
WARM = 400
K_PERM = 1000
ROLE = {'H8': 'DECISIVE', 'H6': 'INFO', 'H12': 'INFO', 'D1': 'INFO'}
LADDER = ['H8', 'H6', 'H12', 'D1']


def log(msg):
    print(msg, flush=True)


def git_checkpoint(card):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-m',
                        f'S555 checkpoint: {card} judged (frozen prereg {PREREG})'],
                       check=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'],
                       check=False, timeout=120)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, timeout=120)
        log(f'    [git] checkpoint {card} pushed')
    except Exception as e:                                   # noqa: BLE001
        log(f'    [git] WARN checkpoint failed: {e} (فایل روی دیسک هست)')


def to_dt64(t):
    """درسِ BUG-EPOCH: لودر ثانیهٔ epoch (int64) می‌دهد — تبدیل صریح."""
    return t.astype('datetime64[s]').astype('datetime64[ns]')


def build_features(df):
    h = df['high'].astype(float)
    l = df['low'].astype(float)
    c = df['close'].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr_geo = tr.rolling(ATR_GEO).mean().shift(1)            # ATR100(t−1)
    prior_low_max = l.rolling(W).max().shift(1)              # max(low[t−90..t−1])
    ev = (l > prior_low_max).fillna(False).to_numpy()
    drift_pos = ((c.shift(1) - c.shift(W)) > 0).fillna(False).to_numpy()
    return ev, drift_pos, atr_geo.to_numpy(float)


def build_signal(df):
    """رکوردِ کف، لبهٔ تازه، گیتِ درفت، LONG. صفر پارامتر آزاد."""
    ev, drift_pos, atr_geo = build_features(df)
    ev_prev = np.roll(ev, 1)
    ev_prev[0] = False
    fresh = ev & ~ev_prev
    sig = fresh & drift_pos
    return sig, drift_pos, atr_geo, fresh


def run_card(card, smoke=False):
    t0 = time.time()
    role = ROLE[card]
    log(f'\n================ S555 · {ASSET} · {card} ({role}) ================')
    d = fd.load_fast(ASSET, card)
    src = d['src']
    if 'mt5_full' not in src:
        raise RuntimeError(f'{card}: دادهٔ full نیست ({src}) — توقف.')
    df = fd.as_dataframe(d)
    n = len(df)
    t64 = to_dt64(d['time'])
    pip = float(se.ASSETS[ASSET]['pip'])
    cost = float(se.ASSETS[ASSET]['spread_pip']) + \
        2.0 * float(se.ASSETS[ASSET].get('slip_pip', 0.0))
    span_y = float((t64[-1] - t64[0]) / np.timedelta64(1, 'D')) / 365.25
    log(f'  src={src}  bars={n:,}  span={span_y:.2f}y  warmup={WARM}  '
        f'geom: SL={SL_K}×ATR{ATR_GEO} RR={RR} mh={MH}')

    sig, drift_pos, atr_geo, fresh = build_signal(df)
    geo_ok = np.isfinite(atr_geo) & (atr_geo > 0)
    valid = np.zeros(n, bool)
    valid[WARM:n - MH - 2] = True
    sig &= geo_ok & valid
    fresh_all = fresh & geo_ok & valid
    nsig = int(sig.sum())
    n_fresh = int(fresh_all.sum())
    gate_pass = 100.0 * nsig / max(1, n_fresh)
    per_year = nsig / span_y
    # P2 (فقط گزارشی): سایهٔ پایینی نسبی کندل‌های رویداد در برابر کل
    lo = df['low'].to_numpy(float); op = df['open'].to_numpy(float)
    cl = df['close'].to_numpy(float); hi = df['high'].to_numpy(float)
    rng_ = np.maximum(hi - lo, 1e-9)
    lower_wick = (np.minimum(op, cl) - lo) / rng_
    p2_ev = float(np.nanmean(lower_wick[sig])) if nsig else None
    p2_all = float(np.nanmean(lower_wick[valid]))
    log(f'  fresh floor-records={n_fresh}  drift-gated signals={nsig} '
        f'({gate_pass:.1f}% pass, {per_year:.1f}/yr)  '
        f'P2 lower-wick: events={p2_ev} vs all={p2_all:.3f}')
    if smoke:
        return dict(card=card, n_fresh=n_fresh, n_sig=nsig, per_year=per_year)
    if nsig < 2:
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no signals)')
        _save(card, payload)
        return payload

    ev_idx = np.flatnonzero(sig)
    sl_dist = SL_K * atr_geo[ev_idx]
    st = queue_rr(df, ev_idx, np.ones(len(ev_idx), bool), sl_dist, ASSET, MH, RR)
    if st is None or st['n'] == 0:
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no trades)')
        _save(card, payload)
        return payload
    tr = trades_df(st)
    pnl = tr['pnl_pip'].values.astype(float)
    wr = float(100 * (pnl > 0).mean())
    e_pip = float(pnl.mean()) + cost
    log(f'  trades={len(tr)}  wr={wr:.2f}%  net={pnl.mean():+.2f} pip  '
        f'e_pip={e_pip:+.2f} vs c={cost:.2f}  '
        f'SLmed={np.median(tr["sl_pip"]):.0f}pip  [{time.time()-t0:.0f}s]')

    # —— نولِ پیش‌ثبت‌شده: شرطی در فضای drift>0، همان هندسه، LONG ——
    space = np.flatnonzero(drift_pos & geo_ok & valid)
    rng = np.random.default_rng(SEED)
    all_sl = SL_K * atr_geo[space]
    n_side = int(len(tr))
    dd = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
              perm_max=None, perm_k=None)
    s_all = queue_rr(df, space, np.ones(len(space), bool), all_sl, ASSET, MH, RR)
    if s_all:
        dd['uncond_wr'] = s_all['wr']
        dd['uncond_n'] = s_all['n']
    wrs = []
    m = min(n_side, len(space))
    for _ in range(K_PERM):
        pick = np.sort(rng.choice(len(space), size=m, replace=False))
        s_p = queue_rr(df, space[pick], np.ones(m, bool), all_sl[pick], ASSET, MH, RR)
        if s_p and s_p['n'] >= 30:
            wrs.append(s_p['wr'])
    if wrs:
        a = np.asarray(wrs, dtype='float64')
        dd.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                  perm_max=float(a.max()), perm_k=int(len(a)))
    null = {'long': dd,
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    log(f"      null long (cond drift>0 space={len(space)}): n={n_side} "
        f"uncond={dd['uncond_wr']} perm_mean={dd['perm_mean']} "
        f"sd={dd['perm_sd']} max={dd['perm_max']} k={dd['perm_k']}  "
        f"[{time.time()-t0:.0f}s]")

    te_ns = t64[tr['entry_bar'].to_numpy(int)].astype(np.int64)
    split_ns = int(np.quantile(te_ns, SPLIT_FRAC))
    holdout = te_ns >= split_ns
    log(f'  H7: disc={int((~holdout).sum())} · oos={int(holdout.sum())} '
        f'· split@{np.datetime64(split_ns, "ns")}')

    null_clean = {k: {kk: vv for kk, vv in v.items() if kk != 'uncond_n'}
                  for k, v in null.items()}
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=None, tp_pip=None,
                            bar_time=t64, close=df['close'].to_numpy(float),
                            null=null_clean, n_trials=N_TRIALS,
                            holdout_mask=holdout, allow_overlap=False)
    log('')
    log(rqs2.format_rqs2(f'S555_{card}', res))
    log(f'  PIP-EDGE LAW: e_pip={e_pip:+.2f} '
        f'{">" if e_pip > cost else "<="} c={cost:.2f} ⇒ '
        f'{"PASS" if e_pip > cost else "FAIL (BELOW_COST)"}')

    entry_times = t64[tr['entry_bar'].to_numpy(int)].astype(str).tolist()
    payload = dict(card=card, role=role, src=src, n_bars=int(n),
                   span_years=span_y, warmup=WARM,
                   config=dict(w=W, sl_k=SL_K, rr=RR, atr_geo=ATR_GEO, mh=MH,
                               side='long', gate='close[t-1]-close[t-90]>0',
                               event='low[t]>max(low[t-90..t-1]) fresh edge',
                               rule='S526-inherited geometry, verbatim'),
                   n_fresh=n_fresh, n_signals=nsig, gate_pass_pct=gate_pass,
                   per_year=per_year, p2_lower_wick_events=p2_ev,
                   p2_lower_wick_all=p2_all,
                   n_trades=int(len(tr)), wr=wr,
                   net_pip=float(pnl.mean()),
                   sl_pip_median=float(np.median(tr['sl_pip'])),
                   tp_pip_median=float(np.median(tr['tp_pip'])),
                   e_pip=e_pip, cost_pip=cost,
                   pip_edge_pass=bool(e_pip > cost),
                   null=null, null_space_bars=int(len(space)),
                   k_perm=K_PERM, n_trials=N_TRIALS,
                   split_frac=SPLIT_FRAC, split_ns=split_ns, seed=SEED,
                   verdict=res.get('verdict'),
                   rqs2_score=res.get('rqs2_score'), gates=res.get('gates'),
                   metrics=res.get('metrics'), entry_times=entry_times,
                   elapsed_s=round(time.time() - t0, 1))
    _save(card, payload)
    tr.to_csv(f'{OUT}/{card}_trades.csv', index=False)
    git_checkpoint(card)
    return payload


def _save(card, payload):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/{card}.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, default=str, indent=1)
    log(f'  saved -> {OUT}/{card}.json')


def main():
    args = sys.argv[1:]
    smoke = '--smoke' in args
    cards = [a for a in args if not a.startswith('--')] or LADDER
    for card in cards:
        try:
            run_card(card, smoke=smoke)
        except Exception as e:                               # noqa: BLE001
            import traceback
            traceback.print_exc()
            log(f'!! {card} failed: {e} — ادامه با کارتِ بعدی')
    log('\nS555 run complete.')


if __name__ == '__main__':
    main()
