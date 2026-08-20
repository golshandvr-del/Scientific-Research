#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S702 — چرخشِ Gann HiLo: فازِ جست‌وجو (مسیر C — فقط نیمهٔ اولِ هر کارت)
پیش‌ثبت: results/S702_PREREG_GANN_HILO_FLIP.md (commit d293844f)

قفل‌شده‌ها:
  P ∈ {8,13,21,34} · سمت ∈ {long,short,both} · k_sl ∈ {1.5,2.0} · RR=1.5
  SEED=702 · K_PERM_SCAN=200 · n_trials=456
  max_hold: M1..M6→240 · M10..M30→120 · H1..H3→64 · H6..H12→32 · D1→16 · W1/MN1→8
  فقط XAUUSD.
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import indicator_bank as ib
from tools import s434_fast_data as fd

SEED = 702
K_PERM = 200
PERIODS = [8, 13, 21, 34]
K_SLS = [1.5, 2.0]
RR = 1.5
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s702')
os.makedirs(OUT_DIR, exist_ok=True)

MAX_HOLD = {'M1':240,'M3':240,'M4':240,'M5':240,'M6':240,
            'M10':120,'M12':120,'M15':120,'M20':120,'M30':120,
            'H1':64,'H2':64,'H3':64,'H6':32,'H8':32,'H12':32,
            'D1':16,'W1':8,'MN1':8}
TFS = ['M1','M3','M4','M5','M6','M10','M12','M15','M20','M30',
       'H1','H2','H3','H6','H8','H12','D1','W1','MN1']


# --------------------------------------------------------------------------
# جهتِ Gann HiLo — مرجعِ حلقه‌ای (هم‌ارزِ ib.gann_hilo) و نسخهٔ برداری
# --------------------------------------------------------------------------
def gann_dir_loop(df, period):
    """مرجع: بازتولیدِ دقیقِ منطقِ ib.gann_hilo ولی با خروجیِ *جهت*."""
    cl = df['close'].values
    sh = df['high'].rolling(period).mean().values
    sl_ = df['low'].rolling(period).mean().values
    n = len(cl)
    out = np.zeros(n, dtype=np.int8)
    direction = 1
    for i in range(period, n):
        if cl[i] > sh[i - 1]:
            direction = 1
        elif cl[i] < sl_[i - 1]:
            direction = -1
        out[i] = direction
    return out


def gann_dir_fast(df, period):
    """برداری: رویدادِ چرخش + ffill. باید بیت-به-بیت با مرجع بخواند."""
    cl = df['close'].values
    sh = df['high'].rolling(period).mean().shift(1).values
    sl_ = df['low'].rolling(period).mean().shift(1).values
    n = len(cl)
    ev = np.zeros(n, dtype=np.float64)
    up = cl > sh          # NaN مقایسه ⇒ False (درست: پیش از period رویدادی نیست)
    dn = cl < sl_
    ev[dn] = -1.0
    ev[up] = 1.0          # up پس از dn ⇒ اولویتِ up، مطابقِ elifِ مرجع
    s = pd.Series(ev)
    s = s.mask(s == 0.0).ffill().fillna(1.0)   # جهتِ آغازین = +1 مطابقِ مرجع
    out = s.values.astype(np.int8)
    out[:period] = 0      # مرجع پیش از period صفر می‌گذارد
    return out


def equivalence_audit():
    """برهانِ هم‌ارزی روی XAUUSD-H1 — پیش از هر اسکن. شکست ⇒ توقف."""
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d)
    report = {'src': d['src'], 'bars': int(len(df)), 'checks': []}
    for P in PERIODS:
        ref = gann_dir_loop(df, P)
        fast = gann_dir_fast(df, P)
        mm_dir = int((ref != fast).sum())
        # سازگاری با خطِ ib.gann_hilo: خروجیِ مرجعِ بانک sl اگر dir=1 و sh اگر dir=-1
        line = ib.gann_hilo(df, P).values
        sh = df['high'].rolling(P).mean().values
        sl_ = df['low'].rolling(P).mean().values
        expect = np.where(ref == 1, sl_, sh)
        ok = np.isfinite(line) & (ref != 0)
        mm_line = int((np.abs(line[ok] - expect[ok]) > 1e-9).sum())
        report['checks'].append({'P': P, 'dir_mismatch': mm_dir,
                                 'line_mismatch': mm_line})
        assert mm_dir == 0, f'Gann dir equivalence FAILED P={P}: {mm_dir}'
        assert mm_line == 0, f'Gann line vs ib.gann_hilo FAILED P={P}: {mm_line}'
    with open(os.path.join(OUT_DIR, 'equivalence_audit.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return report


def scan_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)   # فقط نیمهٔ جست‌وجو
    max_hold = MAX_HOLD[tf]

    # هندسه: SL از ATR100 میانهٔ نیمهٔ جست‌وجو
    tr_r = np.maximum(df['high'] - df['low'],
          np.maximum((df['high'] - df['close'].shift(1)).abs(),
                     (df['low'] - df['close'].shift(1)).abs()))
    atr = tr_r.rolling(100).mean()
    pip = 0.1
    atr_med_pip = float(np.nanmedian(atr.values)) / pip

    rng = np.random.default_rng(SEED)
    out = {'tf': tf, 'src': d['src'], 'n_full': int(n_full), 'half_bar': int(half),
           'seed': SEED, 'atr100_med_pip': atr_med_pip,
           'rr': RR, 'k_perm': K_PERM, 'cells': []}

    null_cache = {}
    def uncond_wr(k_sl, side, n_sample=12000):
        key = (k_sl, side)
        if key in null_cache:
            return null_cache[key]
        sl_pip = k_sl * atr_med_pip
        tp_pip = RR * sl_pip
        n_bars = len(df)
        idx = rng.choice(np.arange(200, n_bars - max_hold - 2),
                         size=min(n_sample, n_bars // 4), replace=False)
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

    for P in PERIODS:
        dirs = gann_dir_fast(df, P)
        d_prev = np.roll(dirs, 1); d_prev[0] = 0
        long_sig = pd.Series((d_prev == -1) & (dirs == 1), index=df.index)
        short_sig = pd.Series((d_prev == 1) & (dirs == -1), index=df.index)
        for k_sl in K_SLS:
            sl_pip = k_sl * atr_med_pip
            tp_pip = RR * sl_pip
            for side in ('long', 'short', 'both'):
                ls = long_sig if side in ('long', 'both') else pd.Series(False, index=df.index)
                ss = short_sig if side in ('short', 'both') else pd.Series(False, index=df.index)
                tr_ = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                                         asset='XAUUSD', max_hold=max_hold,
                                         allow_overlap=False)
                n = int(len(tr_))
                cell = {'P': P, 'k_sl': k_sl, 'side': side,
                        'sl_pip': round(sl_pip, 2), 'tp_pip': round(tp_pip, 2), 'n': n}
                if n >= 30:
                    pnl = tr_['pnl_pip'].to_numpy()
                    wins = int((pnl > 0).sum())
                    wr = wins / n * 100
                    gp = float(pnl[pnl > 0].sum())
                    gl = float(-pnl[pnl < 0].sum())
                    pf = (gp / gl) if gl > 0 else float('inf')
                    if side == 'both':
                        uw_l, _ = uncond_wr(k_sl, 'long'); uw_s, _ = uncond_wr(k_sl, 'short')
                        n_l = int((tr_['direction'] == 'long').sum())
                        uw = (uw_l * n_l + uw_s * (n - n_l)) / n
                    else:
                        uw, _ = uncond_wr(k_sl, side)
                    alpha = wr - uw
                    z = alpha/100*np.sqrt(n)/np.sqrt(uw/100*(1-uw/100)) if 0 < uw < 100 else float('nan')
                    n_req = (3.09*100*np.sqrt(uw/100*(1-uw/100))/alpha)**2 if alpha > 0 else None
                    cell.update({'wr': round(wr, 3), 'uncond_wr': round(uw, 3),
                                 'alpha_pp': round(alpha, 3), 'z': round(float(z), 3),
                                 'pf': round(pf, 3),
                                 'exp_pip': round(float(pnl.mean()), 3),
                                 'n_req': round(n_req, 0) if n_req else None})
                out['cells'].append(cell)
    out['elapsed_s'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT_DIR, f'scan_{tf}.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else TFS
    if not os.path.exists(os.path.join(OUT_DIR, 'equivalence_audit.json')):
        rep = equivalence_audit()
        print('EQUIVALENCE OK', rep['checks'], flush=True)
    for tf in tfs:
        p = os.path.join(OUT_DIR, f'scan_{tf}.json')
        if os.path.exists(p):
            print(f'{tf}: already scanned, skip', flush=True)
            continue
        r = scan_tf(tf)
        best = sorted([c for c in r['cells'] if 'z' in c],
                      key=lambda c: -abs(c.get('z') or 0))[:3]
        print(f"{tf}: done in {r['elapsed_s']}s atr={r['atr100_med_pip']:.1f}pip "
              f"top3={[(c['P'],c['side'],c['n'],c.get('alpha_pp'),c.get('pf'),c.get('z')) for c in best]}",
              flush=True)
