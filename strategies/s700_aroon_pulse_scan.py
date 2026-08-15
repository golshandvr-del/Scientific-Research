#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S700 — تپشِ Aroon: فازِ جست‌وجو (مسیر C — فقط نیمهٔ اولِ هر کارت)
پیش‌ثبت: results/S700_PREREG_AROON_PULSE.md (commit 59986733)

قفل‌شده‌ها (از پیش‌ثبت):
  P ∈ {13,21,34,55} · θ ∈ {38.2,61.8,78.6} · سمت ∈ {long,short,both}
  k_sl ∈ {1.5,2.0} · RR = 1.5 (ثابت) · SEED=700 · K_PERM_SCAN=200
  max_hold: M1..M6→240 · M10..M30→120 · H1..H3→64 · H6..H12→32 · D1→16 · W1/MN1→8
  فقط XAUUSD — EURUSD به استثنای صریحِ کاربر ممنوع.
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import indicator_bank as ib
from tools import s434_fast_data as fd
import bottleneck as bn

SEED = 700
K_PERM = 200
PERIODS = [13, 21, 34, 55]
THRESHOLDS = [38.2, 61.8, 78.6]
K_SLS = [1.5, 2.0]
RR = 1.5
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s700')
os.makedirs(OUT_DIR, exist_ok=True)

MAX_HOLD = {'M1':240,'M3':240,'M4':240,'M5':240,'M6':240,
            'M10':120,'M12':120,'M15':120,'M20':120,'M30':120,
            'H1':64,'H2':64,'H3':64,'H6':32,'H8':32,'H12':32,
            'D1':16,'W1':8,'MN1':8}
TFS = ['M1','M3','M4','M5','M6','M10','M12','M15','M20','M30',
       'H1','H2','H3','H6','H8','H12','D1','W1','MN1']


# --------------------------------------------------------------------------
# Aroon سریع — هم‌ارزِ ریاضیِ engine.indicator_bank.aroon
#   مرجع: پنجرهٔ period+1، up = 100*(period - bars_since_max)/period
#   bn.move_argmax/argmin دقیقاً bars_since را می‌دهد (اثبات در __main__).
#   ⚠️ رفتارِ تساوی: مرجع np.argmax اولین (قدیمی‌ترین) را برمی‌گزیند؛
#   bottleneck جدیدترین را. برای هم‌ارزیِ کامل، assert زیر داور است —
#   اگر روی H1 عدمِ تطابقِ سیگنالی > 0 شد، اجرا متوقف می‌شود.
# --------------------------------------------------------------------------
def aroon_fast(df, period):
    h = df['high'].values.astype('float64')
    l = df['low'].values.astype('float64')
    n = len(h)
    # شکستِ تساوی: مرجعِ np.argmax قدیمی‌ترین فرین را برمی‌گزیند؛ bottleneck
    # جدیدترین را. بایاسِ یکنوای زیرِ کوانتومِ قیمت (۰.۰۱$) کهنه‌ترها را در
    # تساوی برنده می‌کند و هیچ مقایسهٔ غیرتساوی را تغییر نمی‌دهد:
    #   بیشینهٔ بایاسِ کل = 0.004 < 0.01 و گامِ آن > ulp(قیمت).
    bias = (np.arange(n, dtype='float64')[::-1]) * (0.004 / max(n, 1))
    h = h + bias   # قدیمی‌تر ⇒ بایاس بزرگ‌تر ⇒ در تساویِ سقف برنده
    l = l - bias   # قدیمی‌تر ⇒ کوچک‌تر ⇒ در تساویِ کف برنده
    w = period + 1
    since_max = bn.move_argmax(h, w)   # کندل از آخرین سقف
    since_min = bn.move_argmin(l, w)
    up = 100.0 * (period - since_max) / period
    dn = 100.0 * (period - since_min) / period
    return pd.Series(up - dn, index=df.index)


def equivalence_audit():
    """برهانِ هم‌ارزی روی XAUUSD-H1 — پیش از هر اسکن. شکست ⇒ توقف."""
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d)
    report = {'src': d['src'], 'bars': int(len(df)), 'checks': []}
    for P in PERIODS:
        ref = ib.compute('aroon', df, period=P) if _ib_accepts_kw() else ib.aroon(df, P)
        fast = aroon_fast(df, P)
        diff = (ref - fast).abs()
        n_neq = int((diff > 1e-9).sum())
        # عدم تطابق سیگنالی (مهم‌تر از عدم تطابق مقدار):
        mm = 0
        for thr in THRESHOLDS:
            for sgn in (1, -1):
                t = sgn * thr
                if sgn > 0:
                    s_r = (ref.shift(1) <= t) & (ref > t)
                    s_f = (fast.shift(1) <= t) & (fast > t)
                else:
                    s_r = (ref.shift(1) >= t) & (ref < t)
                    s_f = (fast.shift(1) >= t) & (fast < t)
                mm += int((s_r.fillna(False) != s_f.fillna(False)).sum())
        report['checks'].append({'P': P, 'value_mismatch': n_neq, 'signal_mismatch': mm})
        assert mm == 0, f'Aroon equivalence FAILED P={P}: {mm} signal mismatches'
    with open(os.path.join(OUT_DIR, 'equivalence_audit.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return report


def _ib_accepts_kw():
    try:
        import inspect
        return 'period' in inspect.signature(ib.compute).parameters
    except Exception:
        return False


def scan_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)   # فقط نیمهٔ جست‌وجو
    max_hold = MAX_HOLD[tf]

    # هندسه: SL از ATR100 میانهٔ *نیمهٔ جست‌وجو* (بدون نگاه به hold-out)
    atr = ib.atr(df, 100) if hasattr(ib, 'atr') else None
    if atr is None:
        tr = np.maximum(df['high'] - df['low'],
             np.maximum((df['high'] - df['close'].shift(1)).abs(),
                        (df['low'] - df['close'].shift(1)).abs()))
        atr = tr.rolling(100).mean()
    pip = 0.1  # XAUUSD
    atr_med_pip = float(np.nanmedian(atr.values)) / pip

    rng = np.random.default_rng(SEED)
    out = {'tf': tf, 'src': d['src'], 'n_full': int(n_full), 'half_bar': int(half),
           'n_search': int(half), 'seed': SEED, 'atr100_med_pip': atr_med_pip,
           'rr': RR, 'k_perm': K_PERM, 'cells': []}

    # مدلِ صفرِ اسکن per (k_sl): خریدار/فروشندهٔ کورِ نمونه‌گیری‌شده
    null_cache = {}
    def uncond_wr(k_sl, side, n_sample=12000):
        key = (k_sl, side)
        if key in null_cache:
            return null_cache[key]
        sl_pip = k_sl * atr_med_pip
        tp_pip = RR * sl_pip
        n_bars = len(df)
        idx = rng.choice(np.arange(200, n_bars - max_hold - 2), size=min(n_sample, n_bars//4), replace=False)
        sig = np.zeros(n_bars, dtype=bool); sig[idx] = True
        s_ser = pd.Series(sig, index=df.index)
        f_ser = pd.Series(np.zeros(n_bars, dtype=bool), index=df.index)
        tr_ = se.simulate_trades(df, s_ser if side=='long' else f_ser,
                                 f_ser if side=='long' else s_ser,
                                 sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                 max_hold=max_hold, allow_overlap=True)
        wr = float((tr_['outcome']=='win').mean()*100) if len(tr_) else float('nan')
        null_cache[key] = (wr, int(len(tr_)))
        return null_cache[key]

    for P in PERIODS:
        a = aroon_fast(df, P)
        a_prev = a.shift(1)
        for thr in THRESHOLDS:
            long_sig  = ((a_prev <= thr) & (a > thr)).fillna(False)
            short_sig = ((a_prev >= -thr) & (a < -thr)).fillna(False)
            for k_sl in K_SLS:
                sl_pip = k_sl * atr_med_pip
                tp_pip = RR * sl_pip
                for side in ('long', 'short', 'both'):
                    ls = long_sig if side in ('long','both') else pd.Series(False, index=df.index)
                    ss = short_sig if side in ('short','both') else pd.Series(False, index=df.index)
                    tr_ = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                                             asset='XAUUSD', max_hold=max_hold,
                                             allow_overlap=False)
                    n = int(len(tr_))
                    cell = {'P': P, 'thr': thr, 'k_sl': k_sl, 'side': side,
                            'sl_pip': round(sl_pip,2), 'tp_pip': round(tp_pip,2), 'n': n}
                    if n >= 30:
                        wins = int((tr_['outcome']=='win').sum())
                        wr = wins/n*100
                        exp_pip = float(tr_['pnl_pip'].mean())
                        # مبنای مقایسه: خریدار/فروشندهٔ کور با همان هندسه
                        if side == 'both':
                            uw_l,_ = uncond_wr(k_sl,'long'); uw_s,_ = uncond_wr(k_sl,'short')
                            n_l = int((tr_['direction']=='long').sum())
                            uw = (uw_l*n_l + uw_s*(n-n_l))/n
                        else:
                            uw,_ = uncond_wr(k_sl, side)
                        lift_alpha = wr - uw
                        z = lift_alpha/100*np.sqrt(n)/np.sqrt(uw/100*(1-uw/100)) if 0<uw<100 else float('nan')
                        yrs = (df['time'].iloc[-1]-df['time'].iloc[0]).days/365.25 if hasattr(df['time'].iloc[0],'toordinal') else np.nan
                        cell.update({'wr': round(wr,3), 'uncond_wr': round(uw,3),
                                     'alpha_pp': round(lift_alpha,3), 'z': round(float(z),3),
                                     'exp_pip': round(exp_pip,3),
                                     'per_year': round(n/yrs,1) if yrs==yrs else None})
                    out['cells'].append(cell)
    out['elapsed_s'] = round(time.time()-t0, 1)
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
        best = sorted([c for c in r['cells'] if 'z' in c], key=lambda c: -abs(c.get('z') or 0))[:3]
        print(f"{tf}: done in {r['elapsed_s']}s, atr_med={r['atr100_med_pip']:.1f}pip, top3={[(c['P'],c['thr'],c['side'],c['n'],c.get('alpha_pp'),c.get('z')) for c in best]}", flush=True)
