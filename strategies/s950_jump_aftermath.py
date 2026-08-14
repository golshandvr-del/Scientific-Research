# -*- coding: utf-8 -*-
"""
S950 — «پس‌لرزهٔ پرش» (Merton Jump-Diffusion Aftermath) · XAUUSD
================================================================================
پیش‌ثبت: `results/S950_PREREG_jump_aftermath.md` (commit 2e6aaa1d — پیش از اجرا).

فرضیه: کندلی که |r| آن چند برابرِ مقیاسِ انتشارِ محلی (σ از Bipower Variation)
است، عضوِ جمعیتِ diffusion نیست؛ رفتارِ پس از آن (ادامه/بازگشت) ممکن است
سیستماتیک باشد.

مسیرِ چندگانگی: C (کشف روی ۶۰٪ اول، داوریِ یک‌باره با split_bar=60%).
n_trials = 24 (خانوادهٔ قفل‌شدهٔ پیش‌ثبت). مدلِ صفر: جای‌گشتِ جهت، K=1000.

قانونِ اندک‌اندک: هر TF بلافاصله در `results/_scan_S950/<TF>.json` checkpoint.
"""
import sys
import os
import gc
import json
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_scan_S950'
os.makedirs(OUT, exist_ok=True)

SEED = 20260812
K_PERM = 1000
SPLIT_FRAC = 0.60
BV_WIN = 89                                    # فیبوناچی (پیش‌ثبت)
ATR_WIN = 89
MAX_HOLD = 34                                  # فیبوناچی (پیش‌ثبت)

# خانوادهٔ قفل‌شده (پیش‌ثبت §۳) — ۳×۲×۲×۲ = ۲۴ عضو
K_JUMP = [2.6, 3.4, 4.5]
MODES = ['continuation', 'reversal']
SL_A = [1.272, 2.058]
RR_LIST = [1.0, 1.618]
N_TRIALS = 24

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']


def features(df):
    """r، σ_BV (تا کندلِ قبل)، ATR(89) بر حسبِ pip — همگی causal."""
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(c)
    r = np.zeros(n)
    r[1:] = np.log(c[1:] / c[:-1])
    absr = np.abs(r)
    # Bipower: (pi/2)*mean(|r_i||r_{i-1}|) روی BV_WIN — با کانولوشن سریع
    prod = absr[1:] * absr[:-1]                      # طول n-1، اندیسِ i ⇒ |r_{i+1}||r_i|
    kern = np.ones(BV_WIN) / BV_WIN
    bv_full = np.convolve(prod, kern, mode='full')[:len(prod)]  # میانگینِ BV_WIN موردِ آخر تا i
    bv = np.zeros(n)
    # bv[t] باید فقط دادهٔ تا t-1 را ببیند: prod[j] = |r_{j+1}|·|r_j| ⇒ آخرین جفتِ مجاز j+1 = t-1
    bv[2:] = bv_full[:n - 2]
    sigma_bv = np.sqrt(np.maximum(bv * (np.pi / 2.0), 0.0))
    del absr, prod, bv_full, bv          # آزادسازیِ میانی‌ها (M1: هر کدام 40MB)
    # ATR(89) causal (شیفتِ ۱)
    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr = np.convolve(tr_arr, kern, mode='full')[:n]
    atr_causal = np.zeros(n)
    atr_causal[1:] = atr[:-1]
    del tr_arr, atr
    gc.collect()
    return r, sigma_bv, atr_causal


def member_signals(r, sigma_bv, k, mode, warm):
    """ماسکِ سیگنالِ long/short برای یک عضو."""
    valid = np.arange(len(r)) >= warm
    valid &= sigma_bv > 0
    jump_up = valid & (r > k * sigma_bv)
    jump_dn = valid & (r < -k * sigma_bv)
    if mode == 'continuation':
        return jump_up, jump_dn
    return jump_dn, jump_up


def run_member(df, r, sigma_bv, atr_px, k, mode, a, rr, asset, pip):
    ls, ss = member_signals(r, sigma_bv, k, mode, warm=BV_WIN + 2)
    sl_pip_arr = np.maximum(a * atr_px / pip, 1e-9)
    tp_pip_arr = sl_pip_arr * rr
    tr = se.simulate_trades(df, ls, ss, sl_pip_arr, tp_pip_arr, asset,
                            max_hold=MAX_HOLD, allow_overlap=False)
    return tr, ls, ss, sl_pip_arr, tp_pip_arr


def zproxy(tr, sl_med, tp_med, cost=3.3):
    if tr is None or len(tr) < 30:
        return -99.0, None
    n = len(tr)
    wr = float((tr['pnl_pip'] > 0).mean())
    be = (sl_med + cost) / (sl_med + tp_med)
    z = (wr - be) * np.sqrt(n) / max(np.sqrt(be * (1 - be)), 1e-9)
    return float(z), dict(n=n, wr=wr * 100, be=be * 100)


def build_null_perm(df, ls, ss, hold, K=K_PERM, seed=SEED):
    """جای‌گشتِ جهت روی همان کندل‌های ورود (الگوی کانونیِ s346_holdout_c)."""
    sig_idx = np.where(ls | ss)[0]
    if len(sig_idx) < 30:
        return None
    c = df['close'].values.astype(np.float64)
    rng = np.random.default_rng(seed)
    end = np.minimum(sig_idx + hold, len(c) - 1)
    fwd = c[end] - c[sig_idx]
    fwd = fwd[np.isfinite(fwd)]
    m = len(fwd)
    if m < 30:
        return None
    base_wins = fwd > 0
    # جای‌گشتِ تکه‌تکه (chunked) — هم‌ارزِ ریاضیِ ماتریسِ یک‌جا، اما بدونِ OOM
    # (همان rng و همان ترتیبِ فراخوانی ⇒ همان توزیع؛ فقط تخصیصِ حافظه تکه‌ای است)
    wrs = np.empty(K, dtype=np.float64)
    CH = 50
    pos = 0
    while pos < K:
        kk = min(CH, K - pos)
        signs = rng.integers(0, 2, size=(kk, m)).astype(bool)
        w = np.where(signs, base_wins[None, :], ~base_wins[None, :])
        wrs[pos:pos + kk] = w.mean(axis=1) * 100.0
        pos += kk
        del signs, w
    ref = float(np.mean(wrs))
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs)),
                perm_max=float(np.max(wrs)), perm_k=K)
    return {'long': dict(side), 'short': dict(side)}


def judge_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    src = d['src']
    del d
    gc.collect()
    asset = 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    n_bars = len(df)
    split = int(n_bars * SPLIT_FRAC)
    r, sigma_bv, atr_px = features(df)

    # ---------- کشف: فقط ۶۰٪ اول ----------
    # ⚠️ بدونِ کپی: iloc+reset_index روی M1 حدود 200MB کپی می‌ساخت و OOM می‌داد.
    # برشِ numpy روی آرایه‌ها view است؛ copy=False فقط ارجاع می‌دهد (موتور فقط می‌خواند).
    df1 = pd.DataFrame({col: df[col].values[:split]
                        for col in ('time', 'open', 'high', 'low', 'close')},
                       copy=False)
    r1, s1, a1 = r[:split], sigma_bv[:split], atr_px[:split]
    best = None
    for k in K_JUMP:
        for mode in MODES:
            for a in SL_A:
                for rr in RR_LIST:
                    tr, ls, ss, slp, tpp = run_member(df1, r1, s1, a1,
                                                      k, mode, a, rr, asset, pip)
                    if tr is None or len(tr) == 0:
                        continue
                    sl_med = float(np.median(tr['sl_pip'].values))
                    tp_med = sl_med * rr
                    z, info = zproxy(tr, sl_med, tp_med)
                    if best is None or z > best['z']:
                        best = dict(k=k, mode=mode, a=a, rr=rr, z=z, info=info)
    # آزادسازیِ حافظهٔ فازِ کشف پیش از داوری (سندباکسِ ~1GB؛ M1 = ۵M کندل)
    del df1, r1, s1, a1
    gc.collect()
    if best is None:
        rec = dict(tf=tf, src=src, verdict='NO-SIGNAL', n_bars=n_bars)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    # ---------- داوریِ یک‌باره روی کلِ داده ----------
    k, mode, a, rr = best['k'], best['mode'], best['a'], best['rr']
    tr, ls, ss, slp, tpp = run_member(df, r, sigma_bv, atr_px,
                                      k, mode, a, rr, asset, pip)
    if tr is None or len(tr) == 0:
        rec = dict(tf=tf, src=src, verdict='NO-TRADES', best=best, n_bars=n_bars)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * rr
    null = build_null_perm(df, ls, ss, MAX_HOLD)
    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS, split_bar=split,
                            close=df['close'].values)
    m = res['metrics']
    rec = dict(tf=tf, src=src, n_bars=n_bars,
               member=dict(k=k, mode=mode, sl_atr=a, rr=rr,
                           sl_pip_med=sl_med, tp_pip_med=tp_med),
               discovery=best['info'],
               verdict=res['verdict'], score=res['rqs2_score'],
               gates={g: (None if v is None else bool(v))
                      for g, v in res['gates'].items()},
               n=int(m.get('n_trades', 0)), wr=m.get('win_rate'),
               pf=m.get('profit_factor'), net=m.get('net_profit'),
               lift=m.get('skill_lift_pp'), z=m.get('skill_z'),
               p_perm=m.get('skill_p_perm'),
               notes=res['notes'][:6], sec=round(time.time() - t0, 1))
    json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1,
              default=str)
    return rec


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        try:
            rec = judge_tf(tf)
            print(f"[{tf}] verdict={rec.get('verdict')} score={rec.get('score')} "
                  f"n={rec.get('n')} wr={rec.get('wr')} lift={rec.get('lift')} "
                  f"z={rec.get('z')} ({rec.get('sec')}s)", flush=True)
        except Exception as e:                                     # noqa: BLE001
            print(f"[{tf}] ERROR {e!r}", flush=True)
            json.dump(dict(tf=tf, error=repr(e)),
                      open(f'{OUT}/{tf}.json', 'w'))


if __name__ == '__main__':
    main()
