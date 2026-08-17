# -*- coding: utf-8 -*-
"""
S550 — قاعدهٔ منجمدِ S312 روی پنجره‌های بکر و نردبانِ تایم‌فریم‌های نو
=======================================================================
پیش‌ثبت: results/S550_PREREG_S312_VIRGIN_WINDOWS_NEW_TFS.md (commit 06a01087)
که **پیش از اجرای این اسکریپت** به GitHub رفت. هیچ پارامتری جست‌وجو نمی‌شود:

  قاعده  : LONG · dom∈{10,13,20} · hour∈1..12 UTC با SESSION_OPEN · close>EMA200
  هندسه : زیرساعتی sl=tp=295 (ارثِ M15) · فراساعتی sl=tp=395 (ارثِ H1)
           mh = hold_bars_for(tf, 12h زیرساعتی / 24h فراساعتی) — جدولِ پیش‌ثبت
  overlap = False · WARMUP=300

بازوی A (مسیرِ C — حکم‌ساز، هر پنجره فقط یک بار):
  A1: M15 پنجرهٔ بکرِ [2011-01-03, 2020-02-20)  · 295/295/48
  A2: M5  پنجرهٔ بکرِ [2011-01-03, 2023-09-18)  · 295/295/144
بازوی B (اطلاع‌رسان — بدونِ ادعای پذیرش، همپوشانی ~۱۰۰٪ با H1 تمام‌طول):
  M1,M3,M4,M6,M10,M12,M20,H2,H3,H6,H8,H12 تمام‌طول

n_trials = 299 (۲۹۸ موروثیِ S312/S432 + ۱ برای انتقال)
مدلِ صفر: اندازه‌گیری‌شده با هندسهٔ **خودِ همین لایه** (rr=1.0, hold=mh) —
  درسِ S710 دربارهٔ build_null_side ِ S351 که GEO خودش را تحمیل می‌کرد.
K_PERM=2000؛ استثنای محاسباتیِ افشاشده: M1,M3,M4 → 500 (فقط بازوی B،
  که به‌هرحال ادعای پذیرش ندارد؛ H3 هم فقط k>=500 می‌خواهد).

افشای صادقانه: منبعِ M1 خودش از 2012-04-04 شروع می‌شود (سقفِ ۵M کندلِ
  سرورِ MT5) ⇒ span واقعی 14.3y؛ در JSON ثبت می‌شود.

چک‌پوینتِ اندک‌اندک: پس از هر کارت JSON در results/_scan_S550/ + commit+push.
اجرا:  python3 strategies/s550_midmonth_virgin.py [CARD ...]
       بدونِ آرگومان: نردبان از M1 به بالا؛ A2/A1 در جای طبیعی‌شان در نردبان.
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
from engine import indicators as ind                               # noqa: E402
from tools import s434_fast_data as fd                             # noqa: E402
from strategies.s348_rr_sweep import queue_rr                      # noqa: E402

# ---- ثابت‌های منجمدِ پیش‌ثبت (تغییرشان = نقضِ پیش‌ثبت) ----------------------
ASSET = 'XAUUSD'
DOM_SET = (10, 13, 20)
HOURS = tuple(range(1, 13))
EMA_P = 200
WARMUP = 300
SEED = 20260815
K_PERM_DEFAULT = 2000
K_PERM = {'M1': 500, 'M3': 500, 'M4': 500}      # افشاشده — فقط بازوی B
N_TRIALS = 299
SPLIT_FRAC = 0.60
UNCOND_CAP = 150_000
OUT = 'results/_scan_S550'

SUB_H = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20')
SUP_H = ('H2', 'H3', 'H6', 'H8', 'H12')

# کارت = (tf, برچسب, بازو, پنجرهٔ زمانی یا None=تمام‌طول)
CARDS = {
    'M1':  ('M1',  'B', None),
    'M3':  ('M3',  'B', None),
    'M4':  ('M4',  'B', None),
    'M5V': ('M5',  'A', ('2011-01-03', '2023-09-18')),   # A2 — پنجرهٔ بکر
    'M6':  ('M6',  'B', None),
    'M10': ('M10', 'B', None),
    'M12': ('M12', 'B', None),
    'M15V': ('M15', 'A', ('2011-01-03', '2020-02-20')),  # A1 — hold-out تأییدی
    'M20': ('M20', 'B', None),
    'H2':  ('H2',  'B', None),
    'H3':  ('H3',  'B', None),
    'H6':  ('H6',  'B', None),
    'H8':  ('H8',  'B', None),
    'H12': ('H12', 'B', None),
}
LADDER = ['M1', 'M3', 'M4', 'M5V', 'M6', 'M10', 'M12', 'M15V', 'M20',
          'H2', 'H3', 'H6', 'H8', 'H12']


def geom_for(tf):
    if tf in SUB_H:
        return 295, 295, fd.hold_bars_for(tf, 12.0)
    if tf in SUP_H:
        return 395, 395, fd.hold_bars_for(tf, 24.0)
    raise ValueError(tf)


def log(msg):
    print(msg, flush=True)


def git_checkpoint(card):
    """قانونِ اندک‌اندک: هر کارت بلافاصله به GitHub می‌رود."""
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-m',
                        f'S550 checkpoint: {card} judged (frozen prereg 06a01087)'],
                       check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True,
                       timeout=90)
        log(f'    [git] checkpoint {card} pushed')
    except Exception as e:                                   # noqa: BLE001
        log(f'    [git] WARN checkpoint failed: {e} (فایل روی دیسک هست)')


def slice_window(d, w):
    """برشِ پنجرهٔ بکر روی dict لودر — بدونِ کپیِ اضافه جز خودِ برش."""
    if w is None:
        return d
    t = d['time']
    lo = np.datetime64(w[0])
    hi = np.datetime64(w[1])
    m = (t >= lo) & (t < hi)
    out = {k: (v[m] if isinstance(v, np.ndarray) and len(v) == len(t) else v)
           for k, v in d.items()}
    out['n_bars'] = int(m.sum())
    return out


def build_signal(d, df):
    """بازتولیدِ وفادارِ S312 با معناشناسیِ SESSION_OPEN (پیش‌ثبت §2)."""
    dtidx = pd.DatetimeIndex(d['time'])
    dom = dtidx.day.to_numpy()
    sess = fd.session_open_signal(d, hours=HOURS, mode='SESSION_OPEN')
    ema = ind.ema(df['close'], EMA_P).to_numpy()
    close = df['close'].to_numpy(float)
    sig = np.isin(dom, DOM_SET) & sess & (close > ema)
    sig[:WARMUP] = False
    return sig


def build_null(df, valid, sl_price, n_long, mh, k_perm, rng):
    """مدلِ صفرِ اندازه‌گیری‌شده با هندسهٔ خودِ لایه: rr=1.0 و hold=mh."""
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
            for _ in range(k_perm):
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
        f"sd={d['perm_sd']} k={d['perm_k']} pool={d['uncond_pool']}")
    return null


def run_card(card):
    t0 = time.time()
    tf, arm, window = CARDS[card]
    sl, tp, mh = geom_for(tf)
    log(f'\n================ S550 · {ASSET} · {card} (tf={tf}, arm={arm}) '
        f'================')
    d0 = fd.load_fast(ASSET, tf)
    src = d0['src']
    if 'mt5_full' not in src:
        raise RuntimeError(f'{tf}: دادهٔ full نیست — توقف (قانونِ دادهٔ کامل).')
    d = slice_window(d0, window)
    df = fd.as_dataframe(d)
    n = len(df)
    span_y = (d['time'][-1] - d['time'][0]) / np.timedelta64(1, 'D') / 365.25
    log(f'  src={src}  bars={n:,}  span={span_y:.2f}y  window={window}  '
        f'geom={sl}/{tp}/mh={mh}')

    sig = build_signal(d, df)
    n_sig = int(sig.sum())
    log(f'  signals={n_sig} (SESSION_OPEN · dom{DOM_SET} · h1-12 · >EMA200)')
    if n_sig < 3:
        payload = dict(card=card, tf=tf, arm=arm, verdict='INCOMPLETE (signals<3)')
        _save(card, payload)
        return payload

    tr = se.simulate_trades(df, sig, np.zeros(n, bool), sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        payload = dict(card=card, tf=tf, arm=arm, verdict='INCOMPLETE (no trades)')
        _save(card, payload)
        return payload
    wr = float(100 * (tr['pnl_pip'] > 0).mean())
    log(f'  trades={len(tr)}  wr={wr:.2f}%  exp={tr["pnl_pip"].mean():+.2f} pip  '
        f'[{time.time()-t0:.0f}s]')

    # --- مدلِ صفر با هندسهٔ خودِ لایه ---
    pip = se.ASSETS[ASSET]['pip']
    valid = np.arange(WARMUP, max(WARMUP + 2, n - mh - 1))
    fin = np.isfinite(df['close'].to_numpy())
    valid = valid[fin[valid]]
    nL = int(len(tr))
    k_perm = K_PERM.get(tf, K_PERM_DEFAULT)
    rng = np.random.default_rng(SEED)
    log(f'  building measured null: k={k_perm} …')
    null = build_null(df, valid, sl * pip, nL, mh, k_perm, rng)

    # --- تقسیمِ اکتشاف/خارج‌نمونه: صدکِ ۶۰٪ِ زمانِ ورود (درسِ BUG-OOS) ---
    te = d['time'][tr['entry_bar'].to_numpy(int)].astype('datetime64[ns]')
    te_ns = te.astype(np.int64)
    split_ns = int(np.quantile(te_ns, SPLIT_FRAC))
    holdout = te_ns >= split_ns
    log(f'  split@{np.datetime64(split_ns, "ns")} · disc={int((~holdout).sum())} '
        f'· oos={int(holdout.sum())}')

    null_clean = {k: {kk: vv for kk, vv in v.items() if kk != 'uncond_pool'}
                  for k, v in null.items()}
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=float(sl), tp_pip=float(tp),
                            bar_time=d['time'], close=df['close'].to_numpy(float),
                            null=null_clean, n_trials=N_TRIALS,
                            holdout_mask=holdout, allow_overlap=False)
    log('')
    log(rqs2.format_rqs2(f'S550_{card}', res))

    payload = dict(card=card, tf=tf, arm=arm, window=window, src=src,
                   n_bars=int(n), span_years=float(span_y),
                   geom=dict(sl=sl, tp=tp, mh=int(mh)),
                   n_signals=n_sig, n_trades=int(len(tr)),
                   wr=wr, exp_pip=float(tr['pnl_pip'].mean()),
                   null=null, k_perm=k_perm, n_trials=N_TRIALS,
                   split_frac=SPLIT_FRAC, seed=SEED,
                   verdict=res.get('verdict'), rqs2_score=res.get('rqs2_score'),
                   gates=res.get('gates'), metrics=res.get('metrics'),
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
    log('\nS550 run complete.')


if __name__ == '__main__':
    main()
