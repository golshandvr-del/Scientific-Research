# -*- coding: utf-8 -*-
"""
S553 — «تداومِ رگه» (Streak Continuation) روی TFهای درشتِ طلا
================================================================
پیش‌ثبت: results/S553_PREREG_STREAK_CONTINUATION_COARSE.md (commit 69130ea0)
که **پیش از اجرای این اسکریپت** به GitHub رفت.

  رویداد : streak(بدنه) == 3 در لحظهٔ عبور (2→3) · هر دو جهت · k=3 قفلِ پیشینی
  خروج   : V-TIME — mh=6 (=2×3، قاعدهٔ افق=۲×مقیاسِ الگو) ·
           SL=TP=q98(MFE∪MAE) جهت‌آگاه، فقط از پارهٔ اکتشاف (۶۰٪ نخست)
  داوری  : trade-pooled دوجهته · نالِ دوطرفهٔ هم‌هندسه · n_trials=41 · SEED=20260824

اجرا:  python3 strategies/s553_streak_continuation.py [CARD ...]
       (پیش‌فرض: H8 H6 H12 D1 — حکم‌ساز اول)
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                # noqa: E402
from engine import rqs2                                              # noqa: E402
from tools import s434_fast_data as fd                               # noqa: E402
from strategies.s348_rr_sweep import queue_rr                        # noqa: E402

ASSET = 'XAUUSD'
K_STREAK = 3                       # قفلِ پیشینی — جاروب ممنوع
MH = 2 * K_STREAK                  # افق = ۲×مقیاسِ الگو
SEED = 20260824
N_TRIALS = 41
SPLIT_FRAC = 0.60
UNCOND_CAP = 150_000
OUT = 'results/_scan_S553'

K_PERM = {'H6': 1000, 'H8': 1000, 'H12': 2000, 'D1': 2000}
ROLE = {'H8': 'DECISIVE', 'H6': 'INFO', 'H12': 'INFO', 'D1': 'INFO'}
LADDER = ['H8', 'H6', 'H12', 'D1']


def log(msg):
    print(msg, flush=True)


def git_checkpoint(card):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-m',
                        f'S553 checkpoint: {card} judged (frozen prereg 69130ea0)'],
                       check=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'],
                       check=False, timeout=90)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, timeout=90)
        log(f'    [git] checkpoint {card} pushed')
    except Exception as e:                                   # noqa: BLE001
        log(f'    [git] WARN checkpoint failed: {e} (فایل روی دیسک هست)')


def to_dt64(t):
    """درسِ BUG-EPOCH ِ S550: لودر ثانیهٔ epoch (int64) می‌دهد — تبدیلِ صریح."""
    return t.astype('datetime64[s]').astype('datetime64[ns]')


def build_signal(df):
    """streak == K در لحظهٔ عبور (K−1 → K) — هر دو جهت، بدونِ گلچین."""
    o = df['open'].values.astype(float)
    c = df['close'].values.astype(float)
    n = len(o)
    sgn = np.sign(c - o).astype(np.int8)          # 0 رگه را می‌شکند
    streak = np.zeros(n, np.int64)
    for i in range(n):
        if sgn[i] != 0 and i > 0 and sgn[i] == sgn[i - 1]:
            streak[i] = streak[i - 1] + 1
        elif sgn[i] != 0:
            streak[i] = 1
    cross = streak == K_STREAK                     # فقط لحظهٔ عبور: streak دقیقاً K
    long_sig = cross & (sgn > 0)
    short_sig = cross & (sgn < 0)
    return long_sig, short_sig


def vtime_bracket(df, long_sig, short_sig, mh, disc_mask, pip):
    """SL=TP=q98(MFE∪MAE) جهت‌آگاه — فقط سیگنال‌های پارهٔ اکتشاف (عیناً S552)."""
    o = df['open'].values.astype(float)
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    n = len(o)
    mfes, maes = [], []
    for i in np.flatnonzero((long_sig | short_sig) & disc_mask):
        e = i + 1
        j1 = min(e + mh, n)
        if e >= n or e >= j1:
            continue
        entry = o[e]
        up = (h[e:j1].max() - entry) / pip
        dn = (entry - l[e:j1].min()) / pip
        if long_sig[i]:
            mfes.append(up)
            maes.append(dn)
        else:
            mfes.append(dn)
            maes.append(up)
    pool = np.concatenate([np.asarray(mfes), np.asarray(maes)])
    wide = round(float(np.percentile(pool, 98)), 1)
    return max(wide, 1.0), len(mfes)


def build_null(df, valid, sl_price, n_long, n_short, mh, k_perm, rng):
    """نالِ دوطرفهٔ اندازه‌گیری‌شده با هندسهٔ خودِ لایه (rr=1.0) — عیناً S552."""
    null = {}
    for side, n_side, is_long in (('long', n_long, True),
                                  ('short', n_short, False)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None, uncond_pool=None)
        if n_side >= 1 and len(valid) >= 2:
            vi = valid
            if len(vi) > UNCOND_CAP:
                sub = np.sort(rng.choice(len(vi), size=UNCOND_CAP, replace=False))
                vi_u = vi[sub]
                d['uncond_pool'] = int(UNCOND_CAP)
            else:
                vi_u = vi
                d['uncond_pool'] = int(len(vi))
            s_all = queue_rr(df, vi_u, np.full(len(vi_u), is_long),
                             np.full(len(vi_u), sl_price), ASSET, mh, 1.0)
            if s_all:
                d['uncond_wr'] = s_all['wr']
            if len(vi) > n_side:
                wrs = []
                for _ in range(k_perm):
                    pick = np.sort(rng.choice(len(vi), size=n_side, replace=False))
                    s_p = queue_rr(df, vi[pick], np.full(n_side, is_long),
                                   np.full(n_side, sl_price), ASSET, mh, 1.0)
                    if s_p:
                        wrs.append(s_p['wr'])
                if wrs:
                    a = np.asarray(wrs, dtype='float64')
                    d.update(perm_mean=float(a.mean()),
                             perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        log(f"      null {side}: n={n_side} uncond={d['uncond_wr']} "
            f"perm_mean={d['perm_mean']} sd={d['perm_sd']} k={d['perm_k']}")
    return null


def run_card(card):
    t0 = time.time()
    role = ROLE[card]
    k_perm = K_PERM[card]
    log(f'\n================ S553 · {ASSET} · {card} ({role}) ================')
    d = fd.load_fast(ASSET, card)
    src = d['src']
    if 'mt5_full' not in src:
        raise RuntimeError(f'{card}: دادهٔ full نیست — توقف.')
    df = fd.as_dataframe(d)
    n = len(df)
    t64 = to_dt64(d['time'])
    pip = float(se.ASSETS[ASSET]['pip'])
    cost = float(se.ASSETS[ASSET]['spread_pip']) + \
        2.0 * float(se.ASSETS[ASSET].get('slip_pip', 0.0))
    warm = min(260, max(30, n // 8))
    span_y = float((t64[-1] - t64[0]) / np.timedelta64(1, 'D')) / 365.25
    log(f'  src={src}  bars={n:,}  span={span_y:.2f}y  warmup={warm}  mh={MH}')

    long_sig, short_sig = build_signal(df)
    long_sig[:warm] = False
    short_sig[:warm] = False
    long_sig[n - MH - 2:] = False
    short_sig[n - MH - 2:] = False
    sel = long_sig | short_sig
    nsig = int(sel.sum())
    if nsig == 0:
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no signals)')
        _save(card, payload)
        return payload
    log(f'  signals={nsig} (L={int(long_sig.sum())}/S={int(short_sig.sum())})')

    sig_ns = t64[sel].astype(np.int64)
    split_ns = int(np.quantile(sig_ns, SPLIT_FRAC))
    disc_mask = t64.astype(np.int64) < split_ns
    wide, n_disc = vtime_bracket(df, long_sig, short_sig, MH, disc_mask, pip)
    log(f'  split@{np.datetime64(split_ns, "ns")} · disc_signals={n_disc}')
    log(f'  V-TIME bracket: SL=TP={wide} pip (q98 · {wide/cost:.0f}×cost) · '
        f'time exit @ mh={MH}')

    tr = se.simulate_trades(df, long_sig, short_sig, wide, wide, ASSET,
                            max_hold=MH, allow_overlap=False)
    if tr is None or len(tr) == 0:
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no trades)')
        _save(card, payload)
        return payload
    pnl = tr['pnl_pip'].values.astype(float)
    wr = float(100 * (pnl > 0).mean())
    e_pip = float(pnl.mean()) + cost
    isL = (tr['direction'] == 'long').to_numpy()
    nL, nS = int(isL.sum()), int((~isL).sum())
    log(f'  trades={len(tr)} (L={nL}/S={nS})  wr={wr:.2f}%  '
        f'net={pnl.mean():+.2f} pip  e_pip={e_pip:+.2f} vs c={cost:.2f}  '
        f'sideL_net={pnl[isL].mean() if nL else 0:+.2f}  '
        f'sideS_net={pnl[~isL].mean() if nS else 0:+.2f}  '
        f'[{time.time()-t0:.0f}s]')

    rng = np.random.default_rng(SEED)
    valid = np.arange(warm, max(warm + 2, n - MH - 1))
    fin = np.isfinite(df['close'].to_numpy())
    valid = valid[fin[valid]]
    log(f'  building measured null: k={k_perm} …')
    null = build_null(df, valid, wide * pip, nL, nS, MH, k_perm, rng)

    te_ns = t64[tr['entry_bar'].to_numpy(int)].astype(np.int64)
    holdout = te_ns >= split_ns
    log(f'  H7: disc={int((~holdout).sum())} · oos={int(holdout.sum())}')

    null_clean = {k: {kk: vv for kk, vv in v.items() if kk != 'uncond_pool'}
                  for k, v in null.items()}
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=float(wide), tp_pip=float(wide),
                            bar_time=t64, close=df['close'].to_numpy(float),
                            null=null_clean, n_trials=N_TRIALS,
                            holdout_mask=holdout, allow_overlap=False)
    log('')
    log(rqs2.format_rqs2(f'S553_{card}', res))
    log(f'  PIP-EDGE LAW: e_pip={e_pip:+.2f} '
        f'{">" if e_pip > cost else "<="} c={cost:.2f} ⇒ '
        f'{"PASS" if e_pip > cost else "FAIL (BELOW_COST)"}')

    entry_times = t64[tr['entry_bar'].to_numpy(int)].astype(str).tolist()
    payload = dict(card=card, role=role, src=src, n_bars=int(n),
                   span_years=span_y, warmup=int(warm), k_streak=K_STREAK,
                   geom=dict(sl=wide, tp=wide, mh=MH,
                             rule='V-TIME: SL=TP=q98(MFE∪MAE) disc-only'),
                   n_signals=nsig, n_disc_signals=int(n_disc),
                   n_trades=int(len(tr)), n_long=nL, n_short=nS, wr=wr,
                   net_pip=float(pnl.mean()),
                   net_pip_long=float(pnl[isL].mean()) if nL else None,
                   net_pip_short=float(pnl[~isL].mean()) if nS else None,
                   e_pip=e_pip, cost_pip=cost,
                   pip_edge_pass=bool(e_pip > cost),
                   null=null, k_perm=k_perm, n_trials=N_TRIALS,
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
    cards = sys.argv[1:] or LADDER
    for card in cards:
        try:
            run_card(card)
        except Exception as e:                               # noqa: BLE001
            import traceback
            traceback.print_exc()
            log(f'!! {card} failed: {e} — ادامه با کارتِ بعدی')
    log('\nS553 run complete.')


if __name__ == '__main__':
    main()
