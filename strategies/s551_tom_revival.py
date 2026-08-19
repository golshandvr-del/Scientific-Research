# -*- coding: utf-8 -*-
"""
S551 — احیای S141 «رانش چرخش ماه» زیر RQS2 v2.6 روی تمام‌طول
==============================================================
پیش‌ثبت: results/S551_PREREG_S141_TOM_FULLSPAN_H1.md (commit b39cef49 / push 19568bdb)
که **پیش از اجرای این اسکریپت** به GitHub رفت. صفر پارامتر جست‌وجوشده:

  قاعده  : LONG · اولین روزِ معاملاتیِ ماه · hour∈7..12 UTC (SESSION_OPEN)
           بدونِ هیچ فیلترِ اندیکاتوری (وفادار به S141/S306؛ ردِ S222c)
  هندسه : H1 (حکم‌ساز) 395/395/24 · M30 (اطلاع) 295/295/36 · M15 (اطلاع) 295/295/48
  overlap = False · WARMUP=300

«اولین روزِ معاملاتی»: رتبهٔ تاریخِ متمایزِ کندل‌ها درونِ (سال,ماه) == 1 —
  مقاوم به تعطیلیِ آغازِ ماه، همان تعریفِ S141/S306.

n_trials=299 · SEED=20260817 · K_PERM=2000 · نولِ اندازه‌گیری‌شده با هندسهٔ خودِ لایه.
چک‌پوینت پس از هر کارت: JSON + commit + push (قانونِ اندک‌اندک).
اجرا:  python3 strategies/s551_tom_revival.py [CARD ...]   (پیش‌فرض: M15 M30 H1)
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from tools import s434_fast_data as fd                             # noqa: E402
from strategies.s348_rr_sweep import queue_rr                      # noqa: E402

ASSET = 'XAUUSD'
HOURS = tuple(range(7, 13))
WARMUP = 300
SEED = 20260817
K_PERM = 2000
N_TRIALS = 299
SPLIT_FRAC = 0.60
UNCOND_CAP = 150_000
OUT = 'results/_scan_S551'

GEOM = {'H1': (395, 395, 24), 'M30': (295, 295, 36), 'M15': (295, 295, 48)}
ROLE = {'H1': 'DECISIVE', 'M30': 'INFO', 'M15': 'INFO'}
LADDER = ['M15', 'M30', 'H1']


def log(msg):
    print(msg, flush=True)


def git_checkpoint(card):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-m',
                        f'S551 checkpoint: {card} judged (frozen prereg b39cef49)'],
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


def build_signal(d):
    """LONG: اولین روزِ معاملاتیِ ماه × ساعت 7..12 با SESSION_OPEN."""
    t64 = to_dt64(d['time'])
    dtidx = pd.DatetimeIndex(t64)
    # رتبهٔ روزِ معاملاتی درونِ ماه: رتبهٔ تاریخِ متمایز (dense rank)
    df_days = pd.DataFrame({'ym': dtidx.year * 100 + dtidx.month,
                            'date': dtidx.normalize()})
    rank = df_days.groupby('ym')['date'].transform(
        lambda s: s.rank(method='dense')).to_numpy()
    first_td = rank == 1
    sess = fd.session_open_signal(d, hours=HOURS, mode='SESSION_OPEN')
    sig = first_td & sess
    sig[:WARMUP] = False
    return sig, t64


def build_null(df, valid, sl_price, n_long, mh, rng):
    """نولِ اندازه‌گیری‌شده با هندسهٔ خودِ لایه (rr=1.0, hold=mh) — الگوی S550."""
    null = {'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
             perm_max=None, perm_k=None, uncond_pool=None)
    if n_long >= 1 and len(valid) >= 2:
        vi = valid
        if len(vi) > UNCOND_CAP:
            sub = np.sort(rng.choice(len(vi), size=UNCOND_CAP, replace=False))
            vi_u = vi[sub]
            d['uncond_pool'] = int(UNCOND_CAP)
        else:
            vi_u = vi
            d['uncond_pool'] = int(len(vi))
        s_all = queue_rr(df, vi_u, np.full(len(vi_u), True),
                         np.full(len(vi_u), sl_price), ASSET, mh, 1.0)
        if s_all:
            d['uncond_wr'] = s_all['wr']
        if len(vi) > n_long:
            wrs = []
            for _ in range(K_PERM):
                pick = np.sort(rng.choice(len(vi), size=n_long, replace=False))
                s_p = queue_rr(df, vi[pick], np.full(n_long, True),
                               np.full(n_long, sl_price), ASSET, mh, 1.0)
                if s_p:
                    wrs.append(s_p['wr'])
            if wrs:
                a = np.asarray(wrs, dtype='float64')
                d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                         perm_max=float(a.max()), perm_k=int(len(a)))
    null['long'] = d
    log(f"      null long uncond={d['uncond_wr']} perm_mean={d['perm_mean']} "
        f"sd={d['perm_sd']} k={d['perm_k']}")
    return null


def run_card(card):
    t0 = time.time()
    sl, tp, mh = GEOM[card]
    role = ROLE[card]
    log(f'\n================ S551 · {ASSET} · {card} ({role}) ================')
    d = fd.load_fast(ASSET, card)
    src = d['src']
    if 'mt5_full' not in src:
        raise RuntimeError(f'{card}: دادهٔ full نیست — توقف.')
    df = fd.as_dataframe(d)
    n = len(df)
    sig, t64 = build_signal(d)
    span_y = float((t64[-1] - t64[0]) / np.timedelta64(1, 'D')) / 365.25
    n_sig = int(sig.sum())
    log(f'  src={src}  bars={n:,}  span={span_y:.2f}y  geom={sl}/{tp}/mh={mh}')
    log(f'  signals={n_sig} (first-trading-day × h7-12 SESSION_OPEN, no filter)')

    tr = se.simulate_trades(df, sig, np.zeros(n, bool), sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no trades)')
        _save(card, payload)
        return payload
    wr = float(100 * (tr['pnl_pip'] > 0).mean())
    log(f'  trades={len(tr)}  wr={wr:.2f}%  exp={tr["pnl_pip"].mean():+.2f} pip  '
        f'[{time.time()-t0:.0f}s]')

    pip = se.ASSETS[ASSET]['pip']
    valid = np.arange(WARMUP, max(WARMUP + 2, n - mh - 1))
    fin = np.isfinite(df['close'].to_numpy())
    valid = valid[fin[valid]]
    nL = int(len(tr))
    rng = np.random.default_rng(SEED)
    log(f'  building measured null: k={K_PERM} …')
    null = build_null(df, valid, sl * pip, nL, mh, rng)

    te_ns = t64[tr['entry_bar'].to_numpy(int)].astype(np.int64)
    split_ns = int(np.quantile(te_ns, SPLIT_FRAC))
    holdout = te_ns >= split_ns
    log(f'  split@{np.datetime64(split_ns, "ns")} · disc={int((~holdout).sum())} '
        f'· oos={int(holdout.sum())}')

    null_clean = {k: {kk: vv for kk, vv in v.items() if kk != 'uncond_pool'}
                  for k, v in null.items()}
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=float(sl), tp_pip=float(tp),
                            bar_time=t64, close=df['close'].to_numpy(float),
                            null=null_clean, n_trials=N_TRIALS,
                            holdout_mask=holdout, allow_overlap=False)
    log('')
    log(rqs2.format_rqs2(f'S551_{card}', res))

    # زمان‌های ورود برای ممیزی همپوشانی (قانون همپوشانی — گام بعد)
    entry_times = t64[tr['entry_bar'].to_numpy(int)].astype(str).tolist()

    payload = dict(card=card, role=role, src=src, n_bars=int(n),
                   span_years=span_y, geom=dict(sl=sl, tp=tp, mh=int(mh)),
                   n_signals=n_sig, n_trades=int(len(tr)), wr=wr,
                   exp_pip=float(tr['pnl_pip'].mean()), null=null,
                   k_perm=K_PERM, n_trials=N_TRIALS, split_frac=SPLIT_FRAC,
                   seed=SEED, verdict=res.get('verdict'),
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
    log('\nS551 run complete.')


if __name__ == '__main__':
    main()
