# -*- coding: utf-8 -*-
"""S920 — «تصحیحِ خودجوش»: CRSI افراطی × رژیمِ ضدپایای هرست | XAUUSD | MTF

پیش‌ثبت: `results/S920_PREREG_V2_SPONTANEOUS_CORRECTION.md` (commit dff43dcd)
نسخهٔ ۱ (آنتروپی-سقوط) پس گرفته شد — مالکیتِ آن مفهوم با S880 است.

فرضیه (هایک ۱۹۴۵ + هرست ۱۹۵۱ + کانرز ۲۰۱۲)
--------------------------------------------------------------------------------
در رژیمِ ضدپایا (H<0.5) بازگشت به میانگین خاصیتِ *اندازه‌گیری‌شدهٔ* بازار است.
افراطِ سه‌مؤلفه‌ایِ ConnorsRSI در آن رژیم = فاصلهٔ موقتیِ قیمت از دانشِ تجمیعی؛
نظمِ خودجوش خودش تصحیح می‌کند — لایه فقط همراهِ تصحیح می‌شود.

سه انتخابِ محافظه‌کارانهٔ ارثی از S382:
  ۱) رویداد نه حالت (گذرِ آستانه)؛ ۲) قیدِ عدمِ همپوشانی؛ ۳) SL مقدم در کندلِ
  مبهم و حذفِ معاملهٔ بازِ پایانِ داده (هر دو داخلِ se.simulate_trades).

فازها:
  python3 strategies/s920_spontaneous_correction.py discover M1     # فقط نیمهٔ اول
  python3 strategies/s920_spontaneous_correction.py final M1        # یک‌بار، نیمهٔ دوم
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2 as R                   # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S920')
SEED = 20260814
K_PERM = 2000
ATR_P = 89           # فیبوناچی — ضدِ #۷

# ---------------- شبکهٔ قفل‌شدهٔ پیش‌ثبت (بیرونش جست‌وجو ممنوع) ----------------
GRID_THR = [8, 13, 21]
GRID_G = [0.45, 0.50]
GRID_A = [1.272, 1.618]
GRID_B = [1.272, 1.618]          # b = TP/SL — هرگز TP<SL (ضدِ #۸)
GRID_HOLD = [34, 89]
N_GRID = len(GRID_THR) * len(GRID_G) * len(GRID_A) * len(GRID_B) * len(GRID_HOLD)  # 48
N_TRIALS = max(78, N_GRID * 3)   # ×۳ تصمیمِ جهت — صادقانه، نه خوش‌بینانه

TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1']


# ═══════════════ اندیکاتورهای برداری‌شده (تعریفِ عینِ بانک) ═══════════════
# چرا بازنویسی: بانک حلقهٔ پایتونی دارد؛ روی M1 (۵M کندل) rankP=100 و R/S
# هرگز تمام نمی‌شوند. هر تابع علیه ib.compute راستی‌آزمایی عددی شده است
# (تستِ selftest پایین همین فایل؛ max_abs_diff < 1e-9).

def _rsi_wilder(x: np.ndarray, p: int) -> np.ndarray:
    """RSI با هموارسازیِ وایلدر — منطبق با rsi_s بانک (ewm alpha=1/p)."""
    n = len(x)
    d = np.diff(x, prepend=x[0])
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    au = np.empty(n); ad = np.empty(n)
    a = 1.0 / p
    au[0] = up[0]; ad[0] = dn[0]
    for i in range(1, n):
        au[i] = au[i-1] + a * (up[i] - au[i-1])
        ad[i] = ad[i-1] + a * (dn[i] - ad[i-1])
    rs = np.divide(au, ad, out=np.full(n, np.inf), where=ad != 0)
    return 100.0 - 100.0 / (1.0 + rs)


def crsi_fast(close: np.ndarray, rsiP=3, streakP=2, rankP=100) -> np.ndarray:
    n = len(close)
    r = _rsi_wilder(close, rsiP)
    # streak — همان حلقهٔ بانک (O(n)، ارزان)
    streak = np.zeros(n)
    s = 0
    for i in range(1, n):
        if close[i] > close[i-1]:
            s = s + 1 if s >= 0 else 1
        elif close[i] < close[i-1]:
            s = s - 1 if s <= 0 else -1
        else:
            s = 0
        streak[i] = s
    sr = _rsi_wilder(streak, streakP)
    # percent-rank بازده‌ها — برداری با sliding window
    ret = np.zeros(n)
    ret[1:] = np.where(close[:-1] != 0, (close[1:] - close[:-1]) / close[:-1], 0.0)
    rank = np.full(n, np.nan)
    from numpy.lib.stride_tricks import sliding_window_view
    if n > rankP:
        # چانک‌به‌چانک — همان دلیلِ hurst_fast (پرهیز از OOMِ کلاسِ S850)
        chunk = 50_000
        for lo in range(rankP, n, chunk):
            hi = min(lo + chunk, n)
            W = sliding_window_view(ret[lo - rankP:hi - 1], rankP)  # [i-rankP, i)
            cur = ret[lo:hi]
            below = (W < cur[:, None]).sum(axis=1)
            rank[lo:hi] = 100.0 * below / rankP
            del W, below
    return (r + sr + rank) / 3.0


def hurst_fast(close: np.ndarray, p=64, chunk=50_000) -> np.ndarray:
    """نمای هرست R/S — عینِ بانک، برداری‌شده **چانک‌به‌چانک**.

    چرا چانک: روی M1 (۵M کندل) ماتریسِ کاملِ n×p چند گیگابایت می‌شود؛
    S850 دقیقاً با همین کلاسِ خطا OOM شد (commit d77b682b). با chunk=50k
    هر بافر ≈ 25MB و با ۴ بافرِ هم‌زمان ≈ 100MB — امن روی سندباکسِ ~1GB
    (چانکِ 200k با ~400MB بافر + ~360MB داده، خودِ همین نشست OOM شد).
    """
    n = len(close)
    ret = np.zeros(n)
    with np.errstate(divide='ignore', invalid='ignore'):
        ret[1:] = np.where(close[:-1] != 0, np.log(close[1:] / close[:-1]), 0.0)
    ret = np.nan_to_num(ret)
    out = np.full(n, np.nan)
    if n <= p:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    logp = np.log(p)
    # بانک: for i in range(p, n): w = ret[i-p+1:i+1]
    for lo in range(p, n, chunk):
        hi = min(lo + chunk, n)
        # پنجرهٔ منتهی به i نیازمندِ ret[i-p+1 .. i]
        seg = ret[lo - p + 1:hi]
        W = sliding_window_view(seg, p)              # ردیفِ j ⇔ i = lo + j
        m = W.mean(axis=1, keepdims=True)
        dev = W - m
        cum = np.cumsum(dev, axis=1)
        Rng = cum.max(axis=1) - cum.min(axis=1)
        sd = np.sqrt((dev * dev).mean(axis=1))
        with np.errstate(divide='ignore', invalid='ignore'):
            h = np.where((sd > 0) & (Rng > 0), np.log(Rng / sd) / logp, 0.5)
        out[lo:hi] = h
        del W, m, dev, cum, Rng, sd, h
    return out


def atr_pip(df: pd.DataFrame, p=ATR_P, ps=0.1) -> np.ndarray:
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    a = pd.Series(tr).ewm(alpha=1.0/p, adjust=False).mean().to_numpy()
    return a / ps


def selftest():
    """راستی‌آزماییِ نسخه‌های برداری علیه بانک روی نمونهٔ کوچک."""
    from engine import indicator_bank as ib
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d).iloc[:4000].reset_index(drop=True)
    c = df['close'].to_numpy(float)
    for name, fast in (('crsi', crsi_fast(c)), ('hurst', hurst_fast(c))):
        ref = ib.compute(name, df).to_numpy()
        ok = np.isfinite(ref) & np.isfinite(fast)
        diff = float(np.abs(ref[ok] - fast[ok]).max())
        print(f'selftest {name}: n={int(ok.sum())} max_abs_diff={diff:.2e}')
        assert diff < 1e-9, f'{name} diverges from bank!'
    print('selftest PASSED — نسخه‌های برداری عینِ بانک‌اند')


# ═══════════════════════════ سیگنال و ارزیابی ═══════════════════════════

def build_events(C, H, thr, g):
    long_ev = np.zeros(len(C), bool)
    short_ev = np.zeros(len(C), bool)
    prev, cur = C[:-1], C[1:]
    hh = H[1:]
    with np.errstate(invalid='ignore'):
        long_ev[1:] = (prev >= thr) & (cur < thr) & (hh < g)
        short_ev[1:] = (prev <= 100-thr) & (cur > 100-thr) & (hh < g)
    return long_ev, short_ev


def eval_config(df, long_ev, short_ev, sl_pip, tp_pip, hold, side):
    ls = pd.Series(long_ev if side in ('long', 'both') else np.zeros(len(df), bool))
    ss = pd.Series(short_ev if side in ('short', 'both') else np.zeros(len(df), bool))
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset='XAUUSD', max_hold=hold, allow_overlap=False)
    return tr


def measured_null(df, n_long, n_short, sl_pip, tp_pip, hold, k=K_PERM, seed=SEED,
                  warmup=200):
    """مدلِ صفرِ اندازه‌گیری‌شده per-side: همان هندسه/شبیه‌ساز، زمان‌بندیِ تصادفی.

    همان شبیه‌سازِ لایه (se.simulate_trades) — درسِ s382_null_model:
    دو شبیه‌سازِ ناهمگام = تفاوتِ ابزار به‌جای تفاوتِ مهارت.
    """
    n = len(df)
    rng = np.random.default_rng(seed)
    valid = np.arange(warmup, n - 2)
    out = {}
    # WRِ بی‌قید (stride تا هزینه معقول بماند)
    stride = max(1, len(valid) // 20000)
    for side, cnt in (('long', n_long), ('short', n_short)):
        if cnt <= 0:
            out[side] = None
            continue
        sig_u = pd.Series(np.zeros(n, bool)); sig_u.iloc[valid[::stride]] = True
        z = pd.Series(np.zeros(n, bool))
        tru = se.simulate_trades(df, sig_u if side == 'long' else z,
                                 z if side == 'long' else sig_u,
                                 sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                 max_hold=hold, allow_overlap=False)
        uncond = 100.0 * float((tru['pnl_pip'] > 0).mean()) if len(tru) else None
        wrs = []
        for _ in range(k):
            pick = np.sort(rng.choice(valid, size=min(cnt * 3, len(valid)),
                                      replace=False))
            sig = pd.Series(np.zeros(n, bool)); sig.iloc[pick] = True
            trp = se.simulate_trades(df, sig if side == 'long' else z,
                                     z if side == 'long' else sig,
                                     sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                     max_hold=hold, allow_overlap=False)
            if len(trp) > cnt:
                trp = trp.iloc[:cnt]
            if len(trp):
                wrs.append(100.0 * float((trp['pnl_pip'] > 0).mean()))
        wrs = np.array(wrs)
        out[side] = dict(uncond_wr=uncond,
                         perm_mean=float(wrs.mean()), perm_sd=float(wrs.std(ddof=1)),
                         perm_max=float(wrs.max()), perm_k=int(len(wrs)))
    return out


def prep(tf, lo=None, hi=None):
    """بارگذاریِ کم-حافظه: برشِ آرایه‌ها **پیش از** ساختِ DataFrame و با
    copy=False — درسِ مستندِ گامِ ۴۸ (`as_dataframe`): کپیِ دوم روی M1
    سندباکس را می‌کُشد (دوبار Killed در تاریخِ پروژه + یک‌بار در همین نشست).
    """
    d = fd.load_fast('XAUUSD', tf)
    n_all = int(d['n_bars']) if 'n_bars' in d else len(d['close'])
    sl_ = slice(lo, hi)
    df = pd.DataFrame({k: d[k][sl_] for k in
                       ('time', 'open', 'high', 'low', 'close', 'volume')},
                      copy=False)
    meta = dict(src=d['src'], n_all=n_all)
    # آرایه‌های کاملِ dict را رها کن تا GC آزاد کند (فقط برش‌ها زنده می‌مانند)
    return meta, df


def discover(tf):
    """فاز ۱ — جست‌وجوی شبکهٔ ۴۸تایی فقط روی نیمهٔ اول."""
    os.makedirs(OUT, exist_ok=True)
    d, df = prep(tf)
    n_all = d['n_all']
    half = n_all // 2
    df = df.iloc[:half]           # view — بدونِ کپی
    c = np.ascontiguousarray(df['close'].to_numpy(float))
    import gc; gc.collect()
    t0 = time.time()
    C = crsi_fast(c)
    H = hurst_fast(c)
    apip = atr_pip(df)
    atr_med = float(np.nanmedian(apip))
    print(f'[{tf}] bars_all={n_all} half={half} src={d["src"]} '
          f'atr{ATR_P}_med={atr_med:.1f}pip  ind={time.time()-t0:.0f}s', flush=True)

    spread = se.ASSETS['XAUUSD']['spread_pip']
    results = []
    for thr in GRID_THR:
        for g in GRID_G:
            long_ev, short_ev = build_events(C, H, thr, g)
            nL, nS = int(long_ev.sum()), int(short_ev.sum())
            for a in GRID_A:
                sl = round(a * atr_med, 2)
                for b in GRID_B:
                    tp = round(b * sl, 2)
                    be = 100.0 * (sl + spread) / (sl + tp)
                    for hold in GRID_HOLD:
                        for side in ('long', 'short', 'both'):
                            tr = eval_config(df, long_ev, short_ev, sl, tp, hold, side)
                            if tr is None or len(tr) < 20:
                                continue
                            wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                            nn = len(tr)
                            edge = wr - be
                            results.append(dict(
                                thr=thr, g=g, a=a, b=b, hold=hold, side=side,
                                sl_pip=sl, tp_pip=tp, be_wr=round(be, 2),
                                n=nn, wr=round(wr, 2), edge_pp=round(edge, 2),
                                score=round(edge * np.sqrt(nn), 1),
                                exp_pip=round(float(tr['pnl_pip'].mean()), 2),
                                nL_ev=nL, nS_ev=nS))
            print(f'  thr={thr} g={g}: events L={nL} S={nS} '
                  f'done {time.time()-t0:.0f}s', flush=True)

    results.sort(key=lambda r: r['score'], reverse=True)
    best = results[0] if results else None
    payload = dict(tf=tf, src=d['src'], n_all=n_all, half_idx=half,
                   atr_med_pip=atr_med, n_grid=N_GRID, n_trials=N_TRIALS,
                   grid_results=results[:60], best=best,
                   phase='discover', ts=time.time())
    path = f'{OUT}/{tf}_discover.json'
    with open(path, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    if best:
        print(f'[{tf}] BEST(train): {best}', flush=True)
    else:
        print(f'[{tf}] NO-SURVIVOR در نیمهٔ اول (هیچ پیکربندی با n≥20)', flush=True)
    print(f'saved -> {path}', flush=True)
    return payload


def final(tf):
    """فاز ۲ — یک آزمونِ یگانه روی نیمهٔ دوم با پیکربندیِ قفل‌شدهٔ train."""
    dis_path = f'{OUT}/{tf}_discover.json'
    if not os.path.exists(dis_path):
        print(f'[{tf}] discover اول اجرا شود'); return None
    with open(dis_path) as f:
        dis = json.load(f)
    best = dis.get('best')
    if not best:
        print(f'[{tf}] NO-SURVIVOR — آزمونِ نهایی موضوعیت ندارد'); return None

    guard = f'{OUT}/{tf}_final.json'
    if os.path.exists(guard):
        print(f'[{tf}] ⛔ نیمهٔ دوم قبلاً لمس شده — مسیرِ C اجازهٔ تکرار نمی‌دهد')
        with open(guard) as f:
            return json.load(f)

    d, df = prep(tf)               # سریِ کامل — اندیکاتورها تاریخچه می‌خواهند
    n_all = d['n_all']
    half = n_all // 2
    c = df['close'].to_numpy(float)
    C = crsi_fast(c)
    H = hurst_fast(c)
    long_ev, short_ev = build_events(C, H, best['thr'], best['g'])
    # فقط رویدادهای نیمهٔ دوم
    long_ev[:half] = False
    short_ev[:half] = False
    sl, tp, hold, side = best['sl_pip'], best['tp_pip'], best['hold'], best['side']

    tr = eval_config(df, long_ev, short_ev, sl, tp, hold, side)
    print(f'[{tf}] FINAL trades={len(tr)}', flush=True)
    if tr is None or len(tr) < 5:
        payload = dict(tf=tf, phase='final', verdict='NO-TRADES', best=best,
                       n=0 if tr is None else len(tr), src=d['src'])
        with open(guard, 'w') as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
        return payload

    nL = int((tr['direction'] == 'long').sum()); nS = len(tr) - nL
    df2 = df.iloc[half:].reset_index(drop=True)
    null = measured_null(df2, nL, nS, sl, tp, hold)

    bar_time = df['time'].to_numpy()
    res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                         bar_time=bar_time, close=c, null=null,
                         n_trials=N_TRIALS, split_bar=half)
    print(R.format_rqs2(f'S920_{tf}', res), flush=True)
    payload = dict(tf=tf, phase='final', src=d['src'], best=best,
                   n=len(tr), verdict=res['verdict'], score=res.get('rqs2_score'),
                   gates=res.get('gates'), metrics=res.get('metrics'),
                   null=null, n_trials=N_TRIALS, ts=time.time())
    with open(guard, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    print(f'saved -> {guard}', flush=True)
    return payload


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'selftest'
    if cmd == 'selftest':
        selftest()
    elif cmd == 'discover':
        discover(sys.argv[2])
    elif cmd == 'final':
        final(sys.argv[2])
    else:
        print('usage: selftest | discover TF | final TF')
