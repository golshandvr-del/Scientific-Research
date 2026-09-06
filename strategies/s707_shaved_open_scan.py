# -*- coding: utf-8 -*-
"""
S707 — Shaved-Open One-Sided Auction — اسکن نیمهٔ جست‌وجو (مسیر C)
پیش‌ثبت: results/S707_PREREG_SHAVED_OPEN_CANDLE.md (کامیت 8ce9e0d2)
رویداد بی‌بعد (L-S706): w_lo=(open−low)/R ≤ ω ∧ close>open ∧ R ≥ ρ×ATR21[t−1] ⇒ +1
                        w_hi=(high−open)/R ≤ ω ∧ close<open ∧ R ≥ ρ×ATR21[t−1] ⇒ −1
جهت cont/fade. ورود کندل بعد. SL = k_sl × median(ATR55)، TP = 1.5×SL. SEED=707.
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SEED = 707
RR = 1.5
OMEGAS = [0.0, 0.05]
RHOS = [1.0, 1.618]
EPS = 1e-9
K_SLS = [1.0, 1.618]
K_PERM = 12000
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s707')
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


def build_events(df, omega, rho):
    """رویداد بی‌بعد و علّی. خروجی int8: +1/−1/0."""
    o = df['open'].values.astype('float64'); h = df['high'].values.astype('float64')
    l = df['low'].values.astype('float64'); c = df['close'].values.astype('float64')
    R = h - l
    a21 = atr(true_range(df), 21)
    a21s = np.full(len(df), np.nan); a21s[1:] = a21[:-1]           # علّی
    with np.errstate(divide='ignore', invalid='ignore'):
        w_lo = (o - l) / R
        w_hi = (h - o) / R
    valid = (R > 0) & np.isfinite(a21s) & (R >= rho * a21s)
    up = valid & (w_lo <= omega + EPS) & (c > o)
    dn = valid & (w_hi <= omega + EPS) & (c < o)
    ev = np.zeros(len(df), dtype=np.int8)
    ev[up] = 1; ev[dn] = -1
    return ev


def unit_test():
    """پاسخ معلوم. ۳۰ کندل آرام (R=1) برای ATR21، سپس کندل‌های آزمون."""
    rows = []
    for i in range(30):
        rows.append((100.0, 100.6, 99.6, 100.2))            # R=1.0
    # 30: open=low, بدنهٔ بزرگ صعودی ⇒ +1
    rows.append((100.0, 103.0, 100.0, 102.8))
    # 31: open=high, نزولی بزرگ ⇒ −1
    rows.append((103.0, 103.0, 100.0, 100.2))
    # 32: سایهٔ پایینی 20% ⇒ هیچ (ω=0.05)
    rows.append((100.6, 103.0, 100.0, 102.8))
    # 33: بی‌سایه اما کوچک R=0.5 < ATR ⇒ هیچ
    rows.append((100.0, 100.5, 100.0, 100.4))
    # 34: open=low ∧ close=open (doji بی‌سایهٔ پایینی) ⇒ هیچ
    rows.append((100.0, 103.0, 100.0, 100.0))
    # 35: سایهٔ 4% ⇒ با ω=0.05 رویداد، با ω=0.0 هیچ
    rows.append((100.12, 103.0, 100.0, 102.9))
    df = pd.DataFrame(rows, columns=['open','high','low','close'])
    df['time'] = 1_600_041_600 + np.arange(len(df)) * 3600
    ev05 = build_events(df, 0.05, 1.0)
    idx05 = np.nonzero(ev05)[0].tolist()
    assert idx05 == [30, 31, 35] and ev05[30] == 1 and ev05[31] == -1 and ev05[35] == 1, \
        f'unit FAILED omega=0.05: {idx05} dirs={ev05[idx05].tolist()}'
    ev00 = build_events(df, 0.0, 1.0)
    idx00 = np.nonzero(ev00)[0].tolist()
    assert idx00 == [30, 31], f'unit FAILED omega=0.0: {idx00}'
    # ρ=1.618: کندل‌های R=3 ≥ 1.618 ⇒ همان؛ ATR≈1
    ev_r = build_events(df, 0.05, 1.618)
    assert np.nonzero(ev_r)[0].tolist() == [30, 31, 35], 'unit FAILED rho'
    return {'events_w05': idx05, 'dirs_w05': ev05[idx05].tolist(), 'events_w00': idx00}


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

    for omega in OMEGAS:
        for rho in RHOS:
            ev = build_events(df, omega, rho)
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
                    cell = {'omega': omega, 'rho': rho, 'mode': mode, 'k_sl': k_sl,
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
              f"top3={[(c['omega'],c['rho'],c['mode'],c['k_sl'],c['n'],c.get('alpha_pp'),c.get('pf'),c.get('z')) for c in best]}",
              flush=True)
