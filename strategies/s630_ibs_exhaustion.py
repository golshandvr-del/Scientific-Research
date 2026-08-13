# -*- coding: utf-8 -*-
"""
S630 — IBS Exhaustion — آزمونِ نهاییِ پیش‌ثبت‌شده (Route C hold-out)
=====================================================================
پیش‌ثبت: research/S630_PREREG.md (کامیت c2875946 — پیش از این اجرا).

پیکربندی قفل‌شده (تغییرناپذیر):
  XAUUSD H1 — نیمهٔ دومِ data/mt5_full (مُهروموم در اکتشاف)
  long : گذرِ mean(IBS,5) به زیرِ 0.235
  short: گذرِ mean(IBS,5) به بالای 0.765
  SL = TP = 1.5 × median ATR(100)   (متقارن — هرگز TP<SL)
  max_hold=64، بدون هم‌پوشانی
  null: بی‌قید (سخت‌ترین stride) + جایگشتِ زمانی K=1000، بذر 630630
  n_trials=1 (یک آزمونِ پیش‌ثبت‌شده)، split_bar=70%

انتخاب‌های محافظه‌کارانه (میراث S382):
  * همان شبیه‌ساز (se.simulate_trades) برای لایه و مدلِ صفر — تفاوتِ
    شبیه‌ساز نباید با تفاوتِ مهارت اشتباه شود.
  * قیدِ عدمِ هم‌پوشانی روی مدلِ صفر هم اعمال می‌شود (مقایسهٔ عادلانه).
  * بذرِ ثابت — بازتولیدپذیری.
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2 as R

# ---- پیکربندی قفل‌شده (PREREG) ----
ASSET, TF = 'XAUUSD', 'H1'
K_IBS = 5
THR = 0.235
SL_K = 1.5
MAX_HOLD = 64
PERM_K = 1000
SEED = 630630
N_TRIALS = 1
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', '_s630')
os.makedirs(OUT, exist_ok=True)


def build_signals(df):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    rng = h - l
    ibs = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)
    ibs_k = pd.Series(ibs).rolling(K_IBS).mean()
    lo = ((ibs_k.shift(1) >= THR) & (ibs_k < THR)).fillna(False)
    hi = ((ibs_k.shift(1) <= 1 - THR) & (ibs_k > 1 - THR)).fillna(False)
    return lo, hi


def side_wr(tr, side):
    s = tr[tr['direction'] == side] if 'direction' in tr else tr
    if len(s) == 0:
        return None, 0
    return 100.0 * float((s['outcome'] == 'win').mean()), len(s)


def main():
    t0 = time.time()
    d = fd.load_fast(ASSET, TF)
    df_full = fd.as_dataframe(d)
    SRC = d['src']
    half = len(df_full) // 2
    df = df_full.iloc[half:].reset_index(drop=True)   # ← نیمهٔ دومِ مُهروموم
    print(f'src={SRC}  full_bars={len(df_full)}  holdout_bars={len(df)}')

    h, l, c = df['high'].values, df['low'].values, df['close'].values
    tr_ = np.maximum(h - l, np.maximum(abs(h - np.roll(c, 1)), abs(l - np.roll(c, 1))))
    tr_[0] = h[0] - l[0]
    atr = pd.Series(tr_).rolling(100).mean().values
    med_atr = float(np.nanmedian(atr))
    pip = 0.1
    sl_pip = med_atr * SL_K / pip
    tp_pip = sl_pip
    print(f'medATR={med_atr:.4f}$  SL=TP={sl_pip:.2f}pip (symmetric, RR=1)')

    lo, hi = build_signals(df)
    n_lo, n_hi = int(lo.sum()), int(hi.sum())
    print(f'signals: long={n_lo}  short={n_hi}')

    trades = se.simulate_trades(df, lo, hi, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    obs_wr = 100.0 * float((trades['outcome'] == 'win').mean())
    lwr, ln = side_wr(trades, 'long')
    swr, sn = side_wr(trades, 'short')
    print(f'trades={len(trades)}  wr={obs_wr:.2f}%  '
          f'long: n={ln} wr={lwr if lwr is None else round(lwr,2)}%  '
          f'short: n={sn} wr={swr if swr is None else round(swr,2)}%')

    # ---- مدل صفر ① : ورودِ بی‌قید (سخت‌ترین stride) — به تفکیکِ جهت ----
    uncond = {}
    for side_name, is_long in (('long', True), ('short', False)):
        best = None
        for stride in (3, 7, 13):
            sig = pd.Series(False, index=df.index)
            sig.iloc[::stride] = True
            if is_long:
                t = se.simulate_trades(df, sig, pd.Series(False, index=df.index),
                                       sl_pip=sl_pip, tp_pip=tp_pip, asset=ASSET,
                                       max_hold=MAX_HOLD, allow_overlap=False)
            else:
                t = se.simulate_trades(df, pd.Series(False, index=df.index), sig,
                                       sl_pip=sl_pip, tp_pip=tp_pip, asset=ASSET,
                                       max_hold=MAX_HOLD, allow_overlap=False)
            if len(t) < 30:
                continue
            wr = 100.0 * float((t['outcome'] == 'win').mean())
            print(f'  uncond[{side_name}] stride={stride}: n={len(t)} wr={wr:.2f}%')
            best = wr if best is None else max(best, wr)
        uncond[side_name] = best

    # ---- مدل صفر ② : جایگشتِ زمانی K=1000 — همان تعداد سیگنالِ هر جهت ----
    rng_ = np.random.default_rng(SEED)
    n = len(df)
    lo_margin, hi_margin = 200, n - 2
    perm = {'long': [], 'short': []}
    for it in range(PERM_K):
        pos = rng_.choice(np.arange(lo_margin, hi_margin), size=n_lo + n_hi, replace=False)
        pos = np.sort(pos)
        pick = rng_.permutation(n_lo + n_hi)
        lo_sig = pd.Series(False, index=df.index)
        hi_sig = pd.Series(False, index=df.index)
        lo_sig.iloc[pos[pick[:n_lo]]] = True
        hi_sig.iloc[pos[pick[n_lo:]]] = True
        t = se.simulate_trades(df, lo_sig, hi_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                               asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
        for side in ('long', 'short'):
            wr_s, n_s = side_wr(t, side)
            if wr_s is not None and n_s >= 30:
                perm[side].append(wr_s)
        if (it + 1) % 100 == 0:
            print(f'  perm {it+1}/{PERM_K}  ({time.time()-t0:.0f}s)', flush=True)

    null = {}
    for side in ('long', 'short'):
        a = np.asarray(perm[side], float)
        null[side] = dict(uncond_wr=uncond[side],
                          perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                          perm_max=float(a.max()), perm_k=int(len(a)))
        print(f'  null[{side}]: uncond={uncond[side]:.2f}  perm_mean={a.mean():.2f} '
              f'sd={a.std(ddof=1):.3f} max={a.max():.2f} k={len(a)}')

    with open(f'{OUT}/null_model.json', 'w') as f:
        json.dump(dict(seed=SEED, k=PERM_K, null=null, uncond=uncond), f, ensure_ascii=False)

    # ---- داوری RQS2 با ورودی کامل ----
    split_bar = int(0.70 * len(df))
    res = R.compute_rqs2(trades, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=df['time'].values, close=df['close'].values,
                         null=null, n_trials=N_TRIALS, split_bar=split_bar)
    print()
    print(R.format_rqs2(f'S630_IBS_Exhaustion_{TF}_holdout', res))

    with open(f'{OUT}/{TF}_rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    trades.to_csv(f'{OUT}/{TF}_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/{TF}_rqs2.json  (+trades, +null_model)  total {time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()
