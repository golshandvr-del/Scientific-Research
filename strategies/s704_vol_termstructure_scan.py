# -*- coding: utf-8 -*-
"""
S704 — Volatility Term-Structure Cross — اسکن نیمهٔ جست‌وجو (مسیر C)
پیش‌ثبت: results/S704_PREREG_VOL_TERMSTRUCTURE_CROSS.md (کامیت 882910cb)
رویداد: VR = ATR8(t-1)/ATR89(t-1) از زیر θ به بالای θ عبور کند
        پس از حداقل ۳ کندل متوالی زیر θ (ضدلرزش).
جهت: sign(close(t-1) - close(t-35)) — دریفت ۳۴ کندلی علّی.
cont = هم‌جهت دریفت | fade = خلاف دریفت. ورود: open کندل بعد.
SL = k_sl × ATR55(t-1)، TP = 1.5×SL. SEED=704.
درس BUG-EPOCH: محور زمانی s434 ثانیهٔ یونیکس int64 است.
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SEED = 704
RR = 1.5
THETAS = [1.3, 1.6, 2.0]
K_SLS = [1.0, 1.618]
DRIFT_L = 34
QUIET_MIN = 3
K_PERM = 12000
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s704')
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


def build_events(df, theta):
    """رویداد: عبور VR از زیر θ به بالای θ پس از ≥QUIET_MIN کندل زیر θ.
    همه‌چیز علّی: VR(t) از ATRهای shift(1). جهت: دریفت ۳۴ کندلی علّی.
    خروجی: بردار int8 (+1 دریفت‌مثبت، −1 دریفت‌منفی، 0 بدون رویداد)."""
    tr = true_range(df)
    a_fast = atr(tr, 8); a_slow = atr(tr, 89)
    with np.errstate(divide='ignore', invalid='ignore'):
        vr_raw = a_fast / a_slow
    vr = np.full(len(df), np.nan)
    vr[1:] = vr_raw[:-1]                     # shift(1) — علّی
    below = vr < theta                       # nan ⇒ False (نه بالا نه پایین معتبر)
    above = vr >= theta
    valid = ~np.isnan(vr)
    # شمار کندل‌های متوالیِ زیر θ تا t-1
    run = np.zeros(len(df), dtype=np.int32)
    for i in range(1, len(df)):
        run[i] = run[i-1] + 1 if (below[i-1] and valid[i-1]) else 0
    cross = above & valid & (run >= QUIET_MIN)
    c = df['close'].values
    drift = np.zeros(len(df))
    drift[DRIFT_L+1:] = c[DRIFT_L:-1] - c[:-DRIFT_L-1]   # close(t-1)-close(t-1-34)
    ev = np.zeros(len(df), dtype=np.int8)
    ev[cross & (drift > 0)] = 1
    ev[cross & (drift < 0)] = -1
    return ev


def unit_test():
    """آزمون واحد مصنوعی — پاسخ معلوم. شکست ⇒ توقف.
    ۳۰۰ کندل: دریفت صعودی یکنواخت؛ TR کوچک ثابت تا کندل ۲۰۰،
    سپس انفجار پایدار (دامنه ۱۰×). انتظار: دقیقاً یک رویداد +1
    در نخستین کندلی که VR علّی از θ=1.6 رد شود."""
    t0 = 1_600_041_600  # نیمه‌شب دقیق — درس BUG-EPOCH-ALIGN از S703
    n = 300
    rows = []
    px = 100.0
    for i in range(n):
        px += 0.5                       # دریفت صعودی ⇒ drift>0 همه‌جا
        amp = 0.2 if i < 200 else 2.0   # انفجار از کندل ۲۰۰
        o = px; h = px + amp; l = px - amp; c = px + amp * 0.5
        rows.append(dict(time=t0 + i * 3600, open=o, high=h, low=l, close=c))
    df = pd.DataFrame(rows)
    ev = build_events(df, 1.6)
    idx = np.nonzero(ev)[0]
    # VR = ATR8/ATR89: بعد از انفجار، ATR8 سریع ↑ ولی ATR89 کند ⇒ عبور از 1.6
    # باید دقیقاً یک خوشهٔ عبور باشد و اولین رویداد در بازهٔ (200, 215] رخ دهد
    assert len(idx) >= 1, f'unit test FAILED: no event, expected one after bar 200'
    first = int(idx[0])
    assert 200 < first <= 215, f'unit test FAILED: first event at {first}, expected in (200,215]'
    assert ev[first] == 1, f'unit test FAILED: expected +1 (up-drift), got {ev[first]}'
    # هیچ رویدادی پیش از انفجار
    assert all(i > 200 for i in idx), f'unit test FAILED: events before burst: {[i for i in idx if i<=200]}'
    # پس از تثبیت رژیم بالای θ نباید رویداد تکراری بیاید (ضدلرزش run>=3)
    assert len(idx) <= 2, f'unit test FAILED: too many events {idx.tolist()} (debounce broken)'
    return {'events': idx.tolist(), 'dirs': ev[idx].tolist()}


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
    atr55_med_pip = float(np.nanmedian(atr55_shift)) / pip

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

    for theta in THETAS:
        ev = build_events(df, theta)
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
                cell = {'theta': theta, 'mode': mode, 'k_sl': k_sl,
                        'sl_pip': round(sl_pip, 2), 'tp_pip': round(tp_pip, 2)}
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
                # نول: WR غیرشرطی هم‌هندسه، وزن‌دهی به سهم لانگ/شورت واقعی
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
              f"top3={[(c['theta'],c['mode'],c['k_sl'],c['n'],c.get('alpha_pp'),c.get('pf'),c.get('z')) for c in best]}",
              flush=True)
