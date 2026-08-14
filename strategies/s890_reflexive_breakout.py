#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S890 «شکستِ بازتابی» — اجرای پیش‌ثبت‌شده (مسیرِ C).

قرارداد: results/S890_PREREG_ReflexiveBreakout_Xauusd_MTF.md (کامیت 42ee0496)
  - LONG: گذرِ close از سقفِ closeِ L کندلِ قبل؛ SHORT آینه.
  - خانواده: L∈{21,34,55,89,144} × {follow, fade} = ۱۰ پیکربندی/TF.
  - کشف فقط روی ۷۰٪ اول؛ یک آزمونِ RQS2 روی کل با split_bar.
  - SL = 1.5×ATR(100)ِ میانهٔ نیمهٔ اکتشاف؛ TP = 1.5×SL؛ hold=64؛ بدونِ overlap.
  - null: جای‌گشتِ جهتِ تصادفی K=1000 seed=890 (سبکِ s346.build_null_perm).
  - n_trials = 190 (کلِ خانوادهٔ چند-TF، صادقانه).

اجرا:  python3 strategies/s890_reflexive_breakout.py M15
       (هر TF جدا ⇒ کامیتِ تدریجی، مقاوم به بی‌ثباتیِ سندباکس)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'
PIP = 0.1
SPREAD_PIP = 3.3
FIBS = [21, 34, 55, 89, 144]
SL_ATR_MULT = 1.5
RR = 1.5
MAX_HOLD = 64
N_TRIALS = 190           # ۱۰ پیکربندی × ۱۹ TF — قفلِ پیش‌ثبت
NULL_K = 1000
NULL_SEED = 890
OUT = 'results/_s890'


def atr_series(df, n=100):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().values


def signals(c, L, fade=False):
    s = pd.Series(c)
    hh = s.shift(1).rolling(L).max().values
    ll = s.shift(1).rolling(L).min().values
    up_now = c > hh
    dn_now = c < ll
    up_prev = np.roll(up_now, 1); up_prev[0] = False
    dn_prev = np.roll(dn_now, 1); dn_prev[0] = False
    lb = up_now & ~up_prev
    sb = dn_now & ~dn_prev
    lb[:L + 2] = False; sb[:L + 2] = False
    if fade:
        lb, sb = sb, lb          # fade: شکستِ سقف ⇒ شورت، شکستِ کف ⇒ لانگ
    return lb, sb


def simulate(df, ls, ss, sl_pip, tp_pip):
    """موتورِ رسمیِ پروژه (اسکلتِ GUIDE): ورود در openِ کندلِ بعد، صفر نشتِ
    آینده، اسپرد+اسلیپیج استاندارد، اسکیمای کاملِ موردنیازِ compute_rqs2."""
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    return tr


def build_null(df, ls, ss, K=NULL_K, seed=NULL_SEED):
    """نالِ جای‌گشتِ جهتِ تصادفی (سبکِ s346.build_null_perm) با hold=MAX_HOLD."""
    sig_idx = np.where(ls | ss)[0]
    c = df['close'].values.astype(np.float64)
    n = len(sig_idx)
    if n < 30:
        return None
    fwd = np.full(n, np.nan)
    for j, ei in enumerate(sig_idx):
        k = min(ei + MAX_HOLD, len(c) - 1)
        fwd[j] = c[k] - c[ei]
    fwd = fwd[np.isfinite(fwd)]
    if len(fwd) < 30:
        return None
    base_wins = fwd > 0
    rng = np.random.default_rng(seed)
    wrs = []
    for _ in range(K):
        signs = rng.integers(0, 2, size=len(fwd)).astype(bool)
        w = np.where(signs, base_wins, ~base_wins)
        wrs.append(w.mean() * 100.0)
    wrs = np.array(wrs)
    ref = float(np.mean(wrs))
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs)),
                perm_max=float(np.max(wrs)), perm_k=K)
    return {'long': dict(side), 'short': dict(side)}


def run_tf(tf):
    print('=' * 72)
    print(f"S890 Reflexive Breakout · XAUUSD-{tf} · path C (prereg 42ee0496)")
    print('=' * 72)
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d.get('src', '?')
    N = len(df)
    split = int(N * 0.70)
    print(f"src={src}  bars={N}  split(discovery 70%)={split}")
    print(f"span: {df['time'].iloc[0]} → {df['time'].iloc[-1]}")

    a = atr_series(df.iloc[:split], 100)
    med_atr = float(np.nanmedian(a))
    sl_pip = SL_ATR_MULT * med_atr / PIP
    tp_pip = RR * sl_pip
    be = (sl_pip + SPREAD_PIP) / (sl_pip + tp_pip) * 100.0
    print(f"medATR(discovery)={med_atr:.4f}  SL={sl_pip:.2f}pip  TP={tp_pip:.2f}pip  BE(cost)={be:.2f}%")

    c = df['close'].values
    dfe = df.iloc[:split].reset_index(drop=True)

    # ---------- کشف: فقط ۷۰٪ اول ----------
    best = None
    for L in FIBS:
        for fade in (False, True):
            ls_e, ss_e = signals(dfe['close'].values, L, fade)
            tr = simulate(dfe, ls_e, ss_e, sl_pip, tp_pip)
            if tr is None or len(tr) < 40:
                continue
            n = len(tr); wr = float((tr['pnl_pip'] > 0).mean() * 100)
            net = float(tr['pnl_pip'].sum())
            score = wr + 0.001 * net
            tag = f"L{L}{'·fade' if fade else '·follow'}"
            print(f"  {tag:>12}: n={n:>6}  WR={wr:6.2f}%  net={net:>10.1f}  score={score:7.3f}")
            if best is None or score > best['score']:
                best = dict(L=L, fade=fade, score=score, is_n=n,
                            is_wr=round(wr, 2), is_net=round(net, 1))
    if best is None:
        res = dict(card=f'XAUUSD-{tf}', verdict='INCOMPLETE',
                   reason='discovery produced <40 trades for every config', src=src)
        _save(tf, res)
        print("DISCOVERY EMPTY → INCOMPLETE")
        return

    print(f"\nLOCKED: L={best['L']} fade={best['fade']}  "
          f"IS: n={best['is_n']} WR={best['is_wr']}% net={best['is_net']}")

    # ---------- آزمونِ نهایی: کل داده، یک بار ----------
    ls, ss = signals(c, best['L'], best['fade'])
    tr = simulate(df, ls, ss, sl_pip, tp_pip)
    null = build_null(df, ls, ss)
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_TRIALS, split_bar=split,
                          close=c)
    n_all = len(tr); wr_all = float((tr['pnl_pip'] > 0).mean() * 100)
    net_all = float(tr['pnl_pip'].sum())
    hm = tr['entry_bar'].values >= split
    oos_n = int(hm.sum())
    oos_wr = float((tr.loc[hm, 'pnl_pip'] > 0).mean() * 100) if oos_n else float('nan')
    print(f"\nFULL: n={n_all}  WR={wr_all:.2f}%  net={net_all:.1f}pip")
    print(f"OOS(30%): n={oos_n}  WR={oos_wr:.2f}%")
    print(f"VERDICT: {r.get('verdict')}  score={r.get('score')}")
    for k in ('gates', 'notes'):
        if k in r:
            print(f"{k}: {r[k]}")

    res = dict(card=f'XAUUSD-{tf}', prereg='42ee0496', src=src, bars=N,
               split=split, sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
               locked=best, n=n_all, wr=round(wr_all, 2), net_pip=round(net_all, 1),
               oos_n=oos_n, oos_wr=round(oos_wr, 2) if oos_n else None,
               null=null, rqs2=r)
    _save(tf, res)
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


def _save(tf, res):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"saved → {OUT}/rqs2_XAUUSD-{tf}.json")


if __name__ == '__main__':
    run_tf(sys.argv[1] if len(sys.argv) > 1 else 'M1')
