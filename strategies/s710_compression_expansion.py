# -*- coding: utf-8 -*-
"""
S710 — «فشردگی → گسترش» (Compression → Expansion Breakout) — داوریِ نهایی
===========================================================================
پیش‌ثبت: results/S710_PREREG_compression_expansion_breakout.md (commit 6ce8e14b)
که **پیش از اجرای این اسکریپت** به GitHub رفت. هیچ پارامتری اینجا جست‌وجو
نمی‌شود — همه از پیش‌ثبت منجمدند:

  فشردگی : chop_fib_55 >= 61.8
  ماشه   : close > HH13(shift 1)  |  close < LL13(shift 1)
  SL      = 1.000 × ATR(21)   (pip، خودکالیبره به همان کندل)
  TP      = 1.618 × SL        (TP > SL همیشه — ضدِ اشتباهِ #۸)
  hold    = hold_bars_for(tf, 24h)  (ضدِ اشتباهِ #۶)
  overlap = False (یک حساب/یک معامله)

مسیرِ چندگانگی: B — خانوادهٔ {M1,M5,M15,M30,H1} + اطلاعاتی {H4,D1}
n_trials = 7 (کلِ خانواده؛ هیچ جارویی انجام نشد)

مدلِ صفرِ اندازه‌گیری‌شده — با هندسهٔ **خودِ همین لایه** (نه GEO ثابتِ S351):
  همان SL=ATR21 و rr=1.618 و hold، روی بارهای تصادفی از همان استخرِ معتبر،
  به تفکیکِ سمت، K جای‌گشت (M1,M5: 500 — قیدِ محاسباتی؛ بقیه: 2000).
  برای M1 استخرِ uncond با زیرنمونهٔ 150k بار تخمین زده می‌شود (خطای
  نمونه‌گیریِ WR ~0.15pp در برابرِ آستانهٔ 4pp ناچیز — صادقانه ثبت می‌شود).

چک‌پوینتِ اندک‌اندک: پس از هر TF یک JSON در results/_scan_S710/ + commit+push.
دادهٔ اجباری: data/mt5_full — src هر کارت ثبت و اگر full نبود پرچم می‌خورد.

اجرا:  python3 strategies/s710_compression_expansion.py [TF ...]
       بدونِ آرگومان: M1 M5 M15 M30 H1 H4 D1 (خانواده اول، M1 نخست).
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
from engine import indicator_bank as ib                            # noqa: E402
from tools import s434_fast_data as fd                             # noqa: E402
from strategies.s348_rr_sweep import queue_rr                      # noqa: E402

# ---- ثابت‌های منجمدِ پیش‌ثبت (تغییرشان = نقضِ پیش‌ثبت) ----------------------
ASSET = 'XAUUSD'
CHOP_NAME = 'chop_fib_55'
CHOP_TH = 61.8
BRK_N = 13
ATR_P = 21
SL_K = 1.000
RR = 1.618                      # tp = 1.618 × sl  ⇒ TP > SL همیشه
WARMUP = 55                     # طولانی‌ترین پنجرهٔ اندیکاتور
SEED = 20260805
N_TRIALS = 7
SPLIT_FRAC = 0.70
FAMILY = ['M1', 'M5', 'M15', 'M30', 'H1']
INFO = ['H4', 'D1']
K_PERM = {'M1': 500, 'M5': 500}          # پیش‌فرضِ بقیه: 2000
UNCOND_CAP = 150_000                     # سقفِ استخرِ uncond (فقط M1 می‌رسد)
OUT = 'results/_scan_S710'


def log(msg):
    print(msg, flush=True)


def git_checkpoint(tf):
    """قانونِ اندک‌اندک: هر کارت بلافاصله به GitHub می‌رود."""
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-m',
                        f'S710 checkpoint: {tf} judged (frozen prereg params)'],
                       check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True,
                       timeout=60)
        log(f'    [git] checkpoint {tf} pushed')
    except Exception as e:                                   # noqa: BLE001
        log(f'    [git] WARN checkpoint failed: {e} (ادامه می‌دهیم؛ فایل روی دیسک هست)')


def atr_series(df, p):
    """ATR ویلدر (RMA) — همان تعریفِ بانک."""
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def build_signals(df):
    """سیگنال‌های منجمدِ پیش‌ثبت. shift(1) روی کانال ⇒ بدونِ look-ahead."""
    chop = ib.compute(CHOP_NAME, df)
    hh = df['high'].rolling(BRK_N).max().shift(1)
    ll = df['low'].rolling(BRK_N).min().shift(1)
    comp = (chop >= CHOP_TH)
    long_sig = (comp & (df['close'] > hh)).to_numpy()
    short_sig = (comp & (df['close'] < ll)).to_numpy()
    long_sig[:WARMUP] = False
    short_sig[:WARMUP] = False
    return long_sig, short_sig, chop


def build_null(df, valid, sl_dist_arr, n_long, n_short, hold, k_perm, rng):
    """مبنای اندازه‌گیری‌شده به تفکیکِ سمت — با هندسهٔ خودِ S710.

    چرا نه build_null_side ِ S351؟ چون آن تابع GEO_HOLD=12 و GEO_RR=1.618ِ
    S351 را استفاده می‌کند؛ مبنای درست باید *دقیقاً* هندسهٔ همین لایه را
    داشته باشد وگرنه lift بی‌معناست. queue_rr هر دو را پارامتری می‌گیرد.
    """
    null = {}
    for side, is_long_flag, n_side in (('long', True, n_long),
                                       ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None, uncond_pool=None)
        if n_side >= 1 and len(valid) >= 2:
            slv = sl_dist_arr[valid]
            ok = np.isfinite(slv) & (slv > 0)
            vi, slv = valid[ok], slv[ok]
            if len(vi) >= 2:
                # --- uncond: کلِ استخر (با سقفِ صادقانه برای M1) ---
                if len(vi) > UNCOND_CAP:
                    sub = np.sort(rng.choice(len(vi), size=UNCOND_CAP,
                                             replace=False))
                    vi_u, slv_u = vi[sub], slv[sub]
                    d['uncond_pool'] = int(UNCOND_CAP)
                else:
                    vi_u, slv_u = vi, slv
                    d['uncond_pool'] = int(len(vi))
                s_all = queue_rr(df, vi_u, np.full(len(vi_u), is_long_flag),
                                 slv_u, ASSET, hold, RR)
                if s_all:
                    d['uncond_wr'] = s_all['wr']
                # --- جای‌گشت: نمونهٔ n_side از استخر، k_perm بار ---
                if len(vi) > n_side:
                    wrs = []
                    for _ in range(k_perm):
                        pick = np.sort(rng.choice(len(vi), size=n_side,
                                                  replace=False))
                        s_p = queue_rr(df, vi[pick],
                                       np.full(n_side, is_long_flag),
                                       slv[pick], ASSET, hold, RR)
                        if s_p:
                            wrs.append(s_p['wr'])
                    if wrs:
                        a = np.asarray(wrs, dtype='float64')
                        d.update(perm_mean=float(a.mean()),
                                 perm_sd=float(a.std(ddof=1)),
                                 perm_max=float(a.max()),
                                 perm_k=int(len(a)))
        null[side] = d
        log(f'      null {side:<5} uncond={d["uncond_wr"]} '
            f'perm_mean={d["perm_mean"]} sd={d["perm_sd"]} k={d["perm_k"]}')
    return null


def run_tf(tf):
    t0 = time.time()
    log(f'\n================ S710 · {ASSET} · {tf} ================')
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    is_full = 'mt5_full' in src
    log(f'  src={src}  bars={len(df):,}  years={d["span_years"]:.2f}  '
        f'full={is_full}')
    if not is_full and tf not in INFO:
        raise RuntimeError(f'{tf}: دادهٔ full نیست و کارتِ خانواده است — توقف '
                           f'(درسِ E-16).')

    hold = fd.hold_bars_for(tf)
    pip = se.ASSETS[ASSET]['pip']

    long_sig, short_sig, _ = build_signals(df)
    n_sig = int(long_sig.sum() + short_sig.sum())
    log(f'  signals={n_sig} (L={int(long_sig.sum())} S={int(short_sig.sum())})'
        f'  hold={hold}')

    atr = atr_series(df, ATR_P).to_numpy()
    sl_pip_arr = SL_K * atr / pip
    tp_pip_arr = RR * sl_pip_arr           # 1.618×SL — منجمد

    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip_arr, tp_pip_arr,
                            ASSET, max_hold=hold, allow_overlap=False)
    if tr is None or len(tr) == 0:
        log('  هیچ معامله‌ای نشد — کارت INCOMPLETE.')
        return dict(tf=tf, src=src, verdict='INCOMPLETE (no trades)')
    log(f'  trades={len(tr)}  wr={100 * (tr["pnl_pip"] > 0).mean():.2f}%  '
        f'exp={tr["pnl_pip"].mean():.2f} pip  [{time.time() - t0:.0f}s]')

    # --- مدلِ صفرِ اندازه‌گیری‌شده (همان هندسه) ---
    n = len(df)
    valid = np.arange(WARMUP, n - hold - 1)
    fin = np.isfinite(df['close'].to_numpy())
    valid = valid[fin[valid]]
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    k_perm = K_PERM.get(tf, 2000)
    rng = np.random.default_rng(SEED)
    sl_dist_arr = SL_K * atr               # بر حسبِ قیمت برای queue_rr
    log(f'  building measured null: k={k_perm} …')
    null = build_null(df, valid, sl_dist_arr, nL, nS, hold, k_perm, rng)

    # --- داوریِ رسمی v2.6 با همهٔ ورودی‌ها ---
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = float(RR * sl_med)
    split_bar = int(SPLIT_FRAC * n)
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=df['time'].to_numpy(),
                            close=df['close'].to_numpy(float),
                            null={k: {kk: vv for kk, vv in v.items()
                                      if kk != 'uncond_pool'}
                                  for k, v in null.items()},
                            n_trials=N_TRIALS, split_bar=split_bar)
    log('')
    log(rqs2.format_rqs2(f'S710_CompExp_{tf}', res))

    os.makedirs(OUT, exist_ok=True)
    payload = dict(tf=tf, src=src, is_full=is_full, family=(tf in FAMILY),
                   n_bars=int(n), span_years=float(d['span_years']),
                   hold=int(hold), n_signals=n_sig,
                   n_trades=int(len(tr)), n_long=nL, n_short=nS,
                   sl_pip_med=sl_med, tp_pip_med=tp_med,
                   wr=float(100 * (tr['pnl_pip'] > 0).mean()),
                   exp_pip=float(tr['pnl_pip'].mean()),
                   null=null, rqs2=res, k_perm=k_perm,
                   n_trials=N_TRIALS, split_bar=split_bar, seed=SEED,
                   elapsed_s=round(time.time() - t0, 1))
    with open(f'{OUT}/{tf}.json', 'w') as f:
        json.dump(payload, f, ensure_ascii=False, default=str, indent=1)
    tr.to_csv(f'{OUT}/{tf}_trades.csv', index=False)
    log(f'  saved -> {OUT}/{tf}.json  [{time.time() - t0:.0f}s total]')
    git_checkpoint(tf)
    return payload


def main():
    tfs = sys.argv[1:] or (FAMILY + INFO)
    for tf in tfs:
        try:
            run_tf(tf)
        except Exception as e:                               # noqa: BLE001
            import traceback
            traceback.print_exc()
            log(f'!! {tf} failed: {e} — ادامه با TF بعدی')
    log('\nS710 run complete.')


if __name__ == '__main__':
    main()
