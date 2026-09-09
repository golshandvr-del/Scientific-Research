# -*- coding: utf-8 -*-
"""
S708 — Shock Echo — اسکن نیمهٔ جست‌وجو (مسیر C)
پیش‌ثبت: results/S708_PREREG_SHOCK_ECHO.md (کامیت 9aba624a)
شوک (S965): R ≥ μ×ATR21[t−1] ∧ |close−open|/R ≥ 0.618؛ جهت sign(body).
پژواک: شوکِ t با شوکِ هم‌جهتِ s در [t−L, t−1] که s خودش پژواک نبوده (فقط دومینِ خوشه).
جهت fade/cont. ورود کندل بعد. SL = k_sl × median(ATR55)، TP = 1.5×SL. SEED=708.
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SEED = 708
RR = 1.5
MUS = [2.0, 2.618]
LS = [3, 8]
RHO_BODY = 0.618
K_SLS = [1.0, 1.618]
K_PERM = 12000
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s708')
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


def shock_dir(df, mu):
    """شوک مطلع S965 (ارثی): +1/−1/0."""
    o = df['open'].values.astype('float64'); h = df['high'].values.astype('float64')
    l = df['low'].values.astype('float64'); c = df['close'].values.astype('float64')
    R = h - l
    a21 = atr(true_range(df), 21)
    a21s = np.full(len(df), np.nan); a21s[1:] = a21[:-1]
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.abs(c - o) / R
    ok = (R > 0) & np.isfinite(a21s) & (R >= mu * a21s) & (rho >= RHO_BODY) & (c != o)
    return np.where(ok, np.sign(c - o), 0).astype(np.int8)


def build_events(df, mu, L):
    """پژواک: فقط دومین شوک هم‌جهت هر خوشه (پیش‌ثبت §۱).
    in_cluster[s] = s پژواک بوده یا دنبالهٔ خوشه. رویداد در t ⇔
      ∃ شوک هم‌جهت s∈[t−L,t−1] با in_cluster[s]=False  ∧  ∄ شوک هم‌جهت در پنجره با in_cluster=True.
    شوک سوم و بعدیِ خوشه رویداد نیست ولی خوشه را ادامه می‌دهد."""
    sd = shock_dir(df, mu)
    n = len(sd)
    ev = np.zeros(n, dtype=np.int8)
    in_cluster = np.zeros(n, dtype=bool)
    idx = np.nonzero(sd)[0]
    for j, t in enumerate(idx):
        k = j - 1
        has_fresh = False; has_cluster = False
        while k >= 0 and idx[k] >= t - L:
            s = idx[k]
            if sd[s] == sd[t]:
                if in_cluster[s]:
                    has_cluster = True
                else:
                    has_fresh = True
            k -= 1
        if has_cluster:
            in_cluster[t] = True
        elif has_fresh:
            ev[t] = sd[t]; in_cluster[t] = True
    return ev


def unit_test():
    rows = [(100.0, 100.6, 99.6, 100.2)] * 30          # آرام R=1 ⇒ ATR21≈1
    def shock_up(): return (100.0, 103.0, 99.9, 102.9)  # R=3.1 ρ=0.935
    def shock_dn(): return (103.0, 103.1, 100.0, 100.1)
    def big_doji(): return (100.0, 103.0, 99.9, 100.2)  # R بزرگ، بدنه کوچک ⇒ شوک نیست
    # کندل 45: ATR21 علّی پس از خوشهٔ 30–38 به ≈1.7 رسیده؛ شوک باید ≥2×ATR باشد ⇒ R=6
    def shock_dn_big(): return (106.0, 106.1, 100.0, 100.1)
    plan = {30: shock_up, 32: shock_up, 33: shock_up, 35: shock_dn, 38: big_doji, 45: shock_dn_big}
    for i in range(30, 50):
        rows.append(plan[i]() if i in plan else (100.0, 100.6, 99.6, 100.2))
    df = pd.DataFrame(rows, columns=['open','high','low','close'])
    df['time'] = 1_600_041_600 + np.arange(len(df)) * 3600
    sd = shock_dir(df, 2.0)
    assert np.nonzero(sd)[0].tolist() == [30, 32, 33, 35, 45], f'unit FAILED shocks {np.nonzero(sd)[0].tolist()}'
    ev3 = build_events(df, 2.0, 3); i3 = np.nonzero(ev3)[0].tolist()
    assert i3 == [32] and ev3[32] == 1, f'unit FAILED L=3: {i3}'     # 33 پژواکِ پژواک؛ 35 مخالف؛ 45 دور
    ev8 = build_events(df, 2.0, 8); i8 = np.nonzero(ev8)[0].tolist()
    assert i8 == [32], f'unit FAILED L=8: {i8}'                       # 45−35=10 > 8
    return {'shocks': [30, 32, 33, 35, 45], 'echo_L3': i3, 'echo_L8': i8}


def scan_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    n_full = int(d['n_bars'])
    half = n_full // 2
    # حافظه (سندباکس ۹۸۵MB؛ M1 = ۵M کندل): فقط نیمهٔ جست‌وجو را نگه می‌داریم؛
    # هیچ تغییری در منطق — همان iloc[:half] قبلی، فقط بدونِ نگه‌داشتنِ کل.
    d_half = {k: (v[:half] if isinstance(v, np.ndarray) and len(v) == n_full else v)
              for k, v in d.items()}
    src_path = d['src']
    del d
    import gc; gc.collect()
    df = fd.as_dataframe(d_half).reset_index(drop=True)
    max_hold = MAX_HOLD[tf]
    pip = 0.1

    tr = true_range(df)
    atr55 = atr(tr, 55)
    atr55_shift = np.full(len(df), np.nan)
    atr55_shift[1:] = atr55[:-1]
    atr55_med = float(np.nanmedian(atr55_shift))
    atr55_med_pip = atr55_med / pip

    rng = np.random.default_rng(SEED)
    out = {'tf': tf, 'src': src_path, 'n_full': int(n_full), 'half_bar': int(half),
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

    # چک‌پوینتِ سلول‌به‌سلول (M1: هر سلول در فرایندِ جدا — حافظهٔ ۹۸۵MB)
    ckpt_p = os.path.join(OUT_DIR, f'partial_{tf}.json')
    done_cells = []
    if os.path.exists(ckpt_p):
        done_cells = json.load(open(ckpt_p))['cells']
    done_keys = {(c['mu'], c['L'], c['mode'], c['k_sl']) for c in done_cells}
    out['cells'] = list(done_cells)
    only_one = os.environ.get('S708_ONE_CELL') == '1'
    n_new = 0
    for omega in MUS:
        for rho in LS:
            if only_one and n_new >= 1:
                break
            if all((omega, rho, md, ks) in done_keys for md in ('cont', 'fade') for ks in K_SLS):
                continue
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
                    if (omega, rho, mode, k_sl) in done_keys:
                        continue
                    n_new += 1
                    sl_pip = k_sl * atr55_med_pip
                    tp_pip = RR * sl_pip
                    cell = {'mu': omega, 'L': rho, 'mode': mode, 'k_sl': k_sl,
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
    n_total = len(MUS) * len(LS) * 2 * len(K_SLS)
    if len(out['cells']) < n_total:
        with open(ckpt_p, 'w') as f:
            json.dump(out, f)
        out['partial'] = True
        return out
    with open(os.path.join(OUT_DIR, f'scan_{tf}.json'), 'w') as f:
        json.dump(out, f)
    if os.path.exists(ckpt_p):
        os.remove(ckpt_p)
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
        if r.get('partial'):
            print(f"{tf}: partial checkpoint {len(r['cells'])} cells", flush=True)
            continue
        best = sorted([c for c in r['cells'] if 'z' in c],
                      key=lambda c: -(c.get('z') or -9))[:3]
        print(f"{tf}: done {r['elapsed_s']}s atr55={r['atr55_med_pip']:.0f}pip "
              f"top3={[(c['mu'],c['L'],c['mode'],c['k_sl'],c['n'],c.get('alpha_pp'),c.get('pf'),c.get('z')) for c in best]}",
              flush=True)
