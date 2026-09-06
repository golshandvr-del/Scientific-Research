# -*- coding: utf-8 -*-
"""
S706 — Renko Trend-Birth — اسکن نیمهٔ جست‌وجو (مسیر C)
پیش‌ثبت: results/S706_PREREG_RENKO_TREND_BIRTH.md (کامیت 1bf2376b)
آجر b = β × median(ATR55 علّی، نیمهٔ جست‌وجو). رنکوی کلاسیک بر close:
  ادامه: close ≥ L_top + b  (آجر بالا)  /  close ≤ L_bot − b (آجر پایین)
  وارونگی دو-آجری: در روند بالا، close ≤ L_top − 2b ⇒ آجر پایین؛ متقارن.
رویداد (لبهٔ تازه): run برای نخستین بار به m برسد. جهت: cont/fade. ورود کندل بعد.
SL = k_sl × median(ATR55)، TP = 1.5×SL. SEED=706. درس BUG-EPOCH رعایت.
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SEED = 706
RR = 1.5
BETAS = [1.0, 1.618]
MS = [2, 3]
K_SLS = [1.0, 1.618]
K_PERM = 12000
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s706')
os.makedirs(OUT_DIR, exist_ok=True)

MAX_HOLD = {'M1':240,'M3':240,'M4':240,'M5':240,'M6':240,
            'M10':120,'M12':120,'M15':120,'M20':120,'M30':120,
            'H1':64,'H2':64,'H3':64,'H6':32,'H8':32,'H12':32,
            'D1':16,'W1':8,'MN1':8}
TFS = ['M1','M3','M4','M5','M6','M10','M12','M15','M20','M30',
       'H1','H2','H3','H6','H8','H12','D1','W1','MN1']


def true_range(df):
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    pc = np.empty_like(c); pc[0] = c[0]; pc[1:] = c[:-1]
    return np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))


def atr(tr, n):
    return pd.Series(tr).rolling(n).mean().values


def renko_run(close, b):
    """رنکوی کلاسیک بر close با وارونگی دو-آجری.
    خروجی: run[i] = تعداد آجرهای متوالی هم‌جهت پس از کندل i (علامت = جهت)؛
    0 تا اولین آجر."""
    n = len(close)
    run = np.zeros(n, dtype=np.int32)
    top = close[0]; bot = close[0]      # سقف و کف آخرین آجر
    trend = 0; r = 0
    for i in range(1, n):
        c = close[i]
        if trend == 0:
            if c >= top + b:
                k = int((c - top) // b); top = top + k*b; bot = top - b
                trend = 1; r = k
            elif c <= bot - b:
                k = int((bot - c) // b); bot = bot - k*b; top = bot + b
                trend = -1; r = k
        elif trend == 1:
            if c >= top + b:
                k = int((c - top) // b); top = top + k*b; bot = top - b; r += k
            elif c <= bot - b:                     # bot = top − b ⇒ close ≤ top − 2b
                k = int((bot - c) // b); bot = bot - k*b; top = bot + b
                trend = -1; r = k
        else:
            if c <= bot - b:
                k = int((bot - c) // b); bot = bot - k*b; top = bot + b; r += k
            elif c >= top + b:                     # top = bot + b ⇒ close ≥ bot + 2b
                k = int((c - top) // b); top = top + k*b; bot = top - b
                trend = 1; r = k
        run[i] = trend * r
    return run


def build_events(run, m):
    """لبهٔ تازه: |run| از زیر m به ≥m می‌رسد (یک رویداد به‌ازای هر روند)."""
    a = np.abs(run)
    prev = np.zeros_like(a); prev[1:] = a[:-1]
    # روند تازه: علامت تغییر کرده یا از 0 آمده ⇒ prev باید در «همین روند» باشد
    sgn = np.sign(run); psgn = np.zeros_like(sgn); psgn[1:] = sgn[:-1]
    same = (sgn == psgn)
    hit = (a >= m) & ((prev < m) | ~same)
    ev = np.where(hit, sgn, 0).astype(np.int8)
    return ev


def unit_test():
    """پاسخ معلوم: b=10. مسیر: 100→ +3 آجر (110,120,130) → نویز یک‌آجری (120: نباید وارونگی)
    → وارونگی دو-آجری (110) → ادامهٔ نزولی (100, 90) → نویز (100) → ادامه (80).
    با m=2: دقیقاً دو رویداد: +1 در کندل 120 (run=2) و −1 در کندل 100 (run نزولی=2)."""
    close = np.array([100, 105, 110, 120, 130, 120, 110, 100, 90, 100, 80], dtype=float)
    run = renko_run(close, 10.0)
    exp_run = [0, 0, 1, 2, 3, 3, -1, -2, -3, -3, -4]
    assert run.tolist() == exp_run, f'unit FAILED run={run.tolist()} expected={exp_run}'
    ev = build_events(run, 2)
    idx = np.nonzero(ev)[0].tolist()
    assert idx == [3, 7] and ev[3] == 1 and ev[7] == -1, f'unit FAILED events={idx} dirs={ev[idx].tolist()}'
    ev3 = build_events(run, 3)
    idx3 = np.nonzero(ev3)[0].tolist()
    assert idx3 == [4, 8], f'unit FAILED m=3 events={idx3}'
    # چند-آجری در یک کندل: 100→135 با b=10 ⇒ 3 آجر ⇒ run=3 ⇒ با m=2 رویداد در همان کندل
    run2 = renko_run(np.array([100., 135.]), 10.0)
    assert run2.tolist() == [0, 3], f'unit FAILED multi-brick run={run2.tolist()}'
    return {'run': run.tolist(), 'events_m2': idx, 'events_m3': idx3, 'multi': run2.tolist()}


def scan_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)
    max_hold = MAX_HOLD[tf]
    pip = 0.1

    tr = true_range(df)
    atr55 = atr(tr, 55)
    atr55_shift = np.full(len(df), np.nan)
    atr55_shift[1:] = atr55[:-1]
    atr55_med = float(np.nanmedian(atr55_shift))
    atr55_med_pip = atr55_med / pip

    rng = np.random.default_rng(SEED)
    out = {'tf': tf, 'src': d['src'], 'n_full': int(n_full), 'half_bar': int(half),
           'seed': SEED, 'atr55_med_pip': atr55_med_pip, 'rr': RR,
           'k_perm': K_PERM, 'cells': []}

    null_cache = {}
    def uncond_wr(k_sl, side, n_sample=K_PERM):
        key = (k_sl, side)
        if key in null_cache:
            return null_cache[key]
        sl_pip = k_sl * atr55_med_pip
        tp_pip = RR * sl_pip
        n_bars = len(df)
        lo = 200; hi = n_bars - max_hold - 2
        if hi <= lo:
            null_cache[key] = (float('nan'), 0)
            return null_cache[key]
        idx = rng.choice(np.arange(lo, hi), size=min(n_sample, n_bars // 4),
                         replace=False)
        sig = np.zeros(n_bars, dtype=bool); sig[idx] = True
        s_ser = pd.Series(sig, index=df.index)
        f_ser = pd.Series(np.zeros(n_bars, dtype=bool), index=df.index)
        tr_ = se.simulate_trades(df, s_ser if side == 'long' else f_ser,
                                 f_ser if side == 'long' else s_ser,
                                 sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                 max_hold=max_hold, allow_overlap=True)
        wr = float((tr_['outcome'] == 'win').mean() * 100) if len(tr_) else float('nan')
        null_cache[key] = (wr, int(len(tr_)))
        return null_cache[key]

    close = df['close'].values.astype('float64')
    for beta in BETAS:
        b = beta * atr55_med
        run = renko_run(close, b)
        for m in MS:
            ev = build_events(run, m)
            ev_next = np.zeros_like(ev)
            ev_next[1:] = ev[:-1]              # ورود کندل بعد
            for mode in ('cont', 'fade'):
                if mode == 'cont':
                    ls = pd.Series(ev_next == 1, index=df.index)
                    ss = pd.Series(ev_next == -1, index=df.index)
                else:
                    ls = pd.Series(ev_next == -1, index=df.index)
                    ss = pd.Series(ev_next == 1, index=df.index)
                for k_sl in K_SLS:
                    sl_pip = k_sl * atr55_med_pip
                    tp_pip = RR * sl_pip
                    cell = {'beta': beta, 'm': m, 'mode': mode, 'k_sl': k_sl,
                            'brick_pip': round(b / pip, 2),
                            'sl_pip': round(sl_pip, 2), 'tp_pip': round(tp_pip, 2),
                            'n_events': int((ev != 0).sum())}
                    trades = se.simulate_trades(df, ls, ss, sl_pip=sl_pip,
                                                tp_pip=tp_pip, asset='XAUUSD',
                                                max_hold=max_hold,
                                                allow_overlap=False)
                    n = len(trades)
                    cell['n'] = int(n)
                    if n < 30:
                        out['cells'].append(cell)
                        continue
                    wins = (trades['outcome'] == 'win')
                    wr = float(wins.mean() * 100)
                    gp = float(trades.loc[trades['pnl_pip'] > 0, 'pnl_pip'].sum())
                    gl = float(-trades.loc[trades['pnl_pip'] < 0, 'pnl_pip'].sum())
                    pf = gp / gl if gl > 0 else float('inf')
                    nl = int((trades['direction'] == 'long').sum())
                    wl, _ = uncond_wr(k_sl, 'long')
                    ws, _ = uncond_wr(k_sl, 'short')
                    w_frac = nl / n
                    p0 = w_frac * wl + (1 - w_frac) * ws
                    alpha = wr - p0
                    se_ = (100 * np.sqrt((p0/100) * (1 - p0/100) / n)) if n > 0 else float('nan')
                    z = alpha / se_ if se_ and se_ > 0 else float('nan')
                    nreq = ((3.09 * 100 * np.sqrt((p0/100)*(1-p0/100))) / alpha) ** 2 \
                           if alpha > 0 else None
                    cell.update(n=int(n), wr=round(wr, 3), uncond_wr=round(p0, 3),
                                alpha_pp=round(alpha, 3), z=round(float(z), 3),
                                pf=round(pf, 3),
                                exp_pip=round(float(trades['pnl_pip'].mean()), 3),
                                n_long=nl,
                                n_req=round(nreq, 1) if nreq else None)
                    out['cells'].append(cell)
    out['elapsed_s'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT_DIR, f'scan_{tf}.json'), 'w') as f:
        json.dump(out, f)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else TFS
    utp = os.path.join(OUT_DIR, 'unit_test.json')
    if not os.path.exists(utp):
        rep = unit_test()
        with open(utp, 'w') as f:
            json.dump(rep, f)
        print('UNIT TEST OK', rep, flush=True)
    for tf in tfs:
        p = os.path.join(OUT_DIR, f'scan_{tf}.json')
        if os.path.exists(p):
            print(f'{tf}: already scanned, skip', flush=True)
            continue
        r = scan_tf(tf)
        best = sorted([c for c in r['cells'] if 'z' in c],
                      key=lambda c: -(c.get('z') or -9))[:3]
        print(f"{tf}: done {r['elapsed_s']}s atr55={r['atr55_med_pip']:.0f}pip "
              f"top3={[(c['beta'],c['m'],c['mode'],c['k_sl'],c['n'],c.get('alpha_pp'),c.get('pf'),c.get('z')) for c in best]}",
              flush=True)
