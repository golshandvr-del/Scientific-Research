# -*- coding: utf-8 -*-
"""
s459_overnight_norescue.py — S459 · خروجِ «شبِ بی‌نجات» (Overnight No-Rescue) — دادهٔ کامل mt5_full
================================================================================
پیش‌ثبت: results/S459_PREREG_ADDENDUM_OVERNIGHT_NO_RESCUE_EXIT.md (کامیت قبل از اجرا).

قانونِ داده: همهٔ بیماران روی data/mt5_full (۱۵.۶ سال). H4 از H1ِ کامل بازنمونه
(resample 4h, origin=epoch؛ ۹۹.۹۹۶٪ یکسان با H4 قدیمی روی هم‌پوشانی). لودرهای
engine.trade_simulator.load_data / engine.scalp_engine.load_data / s382.load در
زمانِ اجرا (monkey-patch) به mt5_full هدایت می‌شوند — هیچ فایلِ موتور تغییر نمی‌کند.

قاعده (قفل‌شده): در close آخرین کندلِ «ساعتِ اول» هر روزِ جدیدِ بعد از روزِ ورود:
  V_FH1: بازنده ⇒ خروج · V_FH2: فقط از دومین روزِ جدید · V_FHW: V_FH1 + ساعتِ اول
  حتی سربه‌سر را لمس نکرد (long: fh_high<entry؛ short: fh_low>entry).
مرزِ روز = گپ > TF+30 دقیقه؛ N کندلِ ساعتِ اول: M15→4, M30→2, H1→1, H4→1.
اجرا: ts/se → open بعد پس از تقدمِ SL/TP/max_hold؛ S382 → close. برنده‌ها لمس نمی‌شوند.

توازی اجباری (vn=None ⇒ pnl پایهٔ بازتولیدشده روی دادهٔ کامل)؛ مسیرِ C.
اجرا: python3 strategies/s459_overnight_norescue.py <patient>
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from strategies.s450_paired_replay import metrics, judge

VARIANTS = ('V_FH1', 'V_FH2', 'V_FHW')  # قفل‌شده در پیش‌ثبت
TF_MIN = {'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240}
FH_BARS = {'M15': 4, 'M30': 2, 'H1': 1, 'H4': 1}
GAP_EXTRA_MIN = 30
_TF = {'tf': None}
FULL_DIR = os.path.join(ROOT, 'data', 'mt5_full')


# ───────────────────────── دادهٔ کامل (mt5_full) ─────────────────────────
def load_full_df(tf):
    """OHLCV کامل از mt5_full؛ H4 از H1 بازنمونه (رویهٔ S570/S750)."""
    if tf == 'H4':
        h1 = pd.read_csv(os.path.join(FULL_DIR, 'XAUUSD_H1.csv.gz'))
        h1['dt'] = pd.to_datetime(h1['time'], unit='s', utc=True)
        g = h1.set_index('dt').resample('4h', origin='epoch', offset='0h')
        df = pd.DataFrame({'open': g['open'].first(), 'high': g['high'].max(),
                           'low': g['low'].min(), 'close': g['close'].last(),
                           'volume': g['volume'].sum()}).dropna().reset_index()
        df['time'] = (df['dt'].astype('int64') // 10**9).astype('int64')
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
    else:
        df = pd.read_csv(os.path.join(FULL_DIR, f'XAUUSD_{tf}.csv.gz'))
    for col in ('open', 'high', 'low', 'close'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)


def _tf_from_path(p):
    base = os.path.basename(str(p)).replace('.csv', '').replace('.gz', '')
    return base.split('_')[-1]


def patch_loaders():
    """هدایتِ لودرهای موتور به mt5_full — فقط در حافظهٔ این پروسه."""
    from engine import trade_simulator as TS
    from engine import scalp_engine as se
    from strategies import s382_williamsr_momentum as s382

    def ts_load(tf_or_path, asset=None):
        df = load_full_df(_tf_from_path(tf_or_path))
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
        return df

    def se_load(path):
        df = load_full_df(_tf_from_path(path))
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df.reset_index(drop=True)

    def s382_load(card):
        df = load_full_df(_tf_from_path(card))
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    TS.load_data = ts_load
    se.load_data = se_load
    s382.load = s382_load


# ───────────────────────── ساختارِ روز / ساعتِ اول ─────────────────────────
def symbols(df):
    """(day_id, is_fh_close, fh_high, fh_low) — همه علّی. fh_* فقط در کندلِ
    آخرِ ساعتِ اول معتبر (وگرنه NaN)."""
    tf = _TF['tf']
    t = df['time'].to_numpy(np.int64)
    hi = df['high'].to_numpy(float); lo = df['low'].to_numpy(float)
    n = len(df); nb = FH_BARS[tf]; gap = (TF_MIN[tf] + GAP_EXTRA_MIN) * 60
    day = np.zeros(n, np.int64); fhc = np.zeros(n, bool)
    fhh = np.full(n, np.nan); fhl = np.full(n, np.nan)
    d = 0; bid = 0; ch = -np.inf; cl = np.inf
    for i in range(n):
        if i > 0 and (t[i] - t[i - 1]) > gap:
            d += 1; bid = 0; ch = -np.inf; cl = np.inf
        if bid < nb:
            ch = max(ch, hi[i]); cl = min(cl, lo[i])
        if bid == nb - 1:
            fhc[i] = True; fhh[i] = ch; fhl[i] = cl
        day[i] = d; bid += 1
    return day, fhc, fhh, fhl


def rule_step(vn, sym, i, is_long, losing, state, fl=None, tp_dist=None, e=None, entry=None):
    if vn is None:
        return False, state
    day, fhc, fhh, fhl = sym
    if not fhc[i] or day[i] <= day[e] or not losing:
        return False, state
    if vn == 'V_FH2' and day[i] < day[e] + 2:
        return False, state
    if vn == 'V_FHW':
        tried = (fhh[i] >= entry) if is_long else (fhl[i] <= entry)
        if tried:
            return False, state
    return True, state


# ─────────────────────────── بازپخشِ یک معامله ───────────────────────────
def replay_ts(trade, arr, sym, vn, max_hold, spec):
    """قراردادِ trade_simulator (S312 LONG). خروجی pnl_usd بر ۱ لات."""
    o, h, l, c = arr
    e = int(trade.entry_bar)
    entry = float(trade.entry_price)
    pip = spec['pip']; contract = spec['contract']; cost = spec['cost_price']
    sl = entry - float(trade.sl_pip) * pip
    tp = entry + float(trade.tp_pip) * pip
    n = len(o)
    st = None
    i = e
    while i < n - 1:
        nb = i + 1
        # (۱) چکِ hit کندلِ nb — همیشه مقدم
        if o[nb] <= sl:
            return (o[nb] - entry - cost) * contract, nb, 'sl_gap'
        if o[nb] >= tp:
            return (o[nb] - entry - cost) * contract, nb, 'tp_gap'
        if l[nb] <= sl:
            return (sl - entry - cost) * contract, nb, 'sl'
        if h[nb] >= tp:
            return (tp - entry - cost) * contract, nb, 'tp'
        # (۲) خروجِ زمانی استراتژی (max_hold) در open کندلِ بعد
        if (i + 1) - e >= max_hold:
            return (o[nb] - entry - cost) * contract, nb, 'strategy_close'
        # (۳) قاعدهٔ S455 در close کندلِ i (بعد از کندلِ ورود)
        if vn is not None and i > e:
            fl = c[i] - entry
            ex, st = rule_step(vn, sym, i, True, fl <= 0.0, st, fl, tp - entry, e, entry)
            if ex:
                return (o[nb] - entry - cost) * contract, nb, 'fh_exit'
        i += 1
    return (c[n - 1] - entry - cost) * contract, n - 1, 'eod'


def replay_se(trade, arr, sym, vn, max_hold, cfg, is_long, tp_pip):
    """قراردادِ scalp_engine (S356 LONG / S344 SHORT). pnl_pip خالص."""
    o, h, l, c = arr
    eb = int(trade.entry_bar)
    fill = float(trade.entry_price)
    pip = cfg['pip']; spread = cfg['spread_pip']; slip = cfg['slip_pip']
    sl_d = float(trade.sl_pip) * pip
    tp_d = float(tp_pip) * pip
    if is_long:
        sl_lvl = fill - sl_d; tp_lvl = fill + tp_d
    else:
        sl_lvl = fill + sl_d; tp_lvl = fill - tp_d
    n = len(o)
    end = min(eb + max_hold, n)
    pend_exit = False   # ثبت در close کندلِ j ⇒ اجرا در open کندلِ j+1
    st = None
    for j in range(eb, end):
        if is_long:
            hit_sl = l[j] <= sl_lvl; hit_tp = h[j] >= tp_lvl
        else:
            hit_sl = h[j] >= sl_lvl; hit_tp = l[j] <= tp_lvl
        if hit_sl:  # مبهم ⇒ SL (عینِ موتور)
            xf = sl_lvl - slip * pip if is_long else sl_lvl + slip * pip
            g = (xf - fill) if is_long else (fill - xf)
            return g / pip - spread, j, 'sl'
        if hit_tp:
            xf = tp_lvl - slip * pip if is_long else tp_lvl + slip * pip
            g = (xf - fill) if is_long else (fill - xf)
            return g / pip - spread, j, 'tp'
        if pend_exit:
            xf = o[j] - slip * pip if is_long else o[j] + slip * pip
            g = (xf - fill) if is_long else (fill - xf)
            return g / pip - spread, j, 'fh_exit'
        if j == eb:
            continue  # در کندلِ ورود ارزیابی نداریم (عینِ موتور)
        if vn is not None:
            fl = (c[j] - fill) if is_long else (fill - c[j])
            ex, st = rule_step(vn, sym, j, is_long, fl <= 0.0, st, fl, tp_d, eb, fill)
            if ex:
                pend_exit = True
    xb = end - 1
    xf = c[xb] - slip * pip if is_long else c[xb] + slip * pip
    g = (xf - fill) if is_long else (fill - xf)
    return g / pip - spread, xb, 'time'


def replay_s382(trade, arr, sym, vn, ps, sl_abs, rr):
    """قراردادِ شبیه‌سازِ S382 (LONG، بدونِ mh، بدونِ هزینه، ورود در close)."""
    o, h, l, c = arr
    e = int(trade.entry_bar)
    entry = c[e]
    sl_lvl = entry - sl_abs
    tp_lvl = entry + sl_abs * rr
    n = len(o)
    st = None
    j = e + 1
    while j < n:
        if l[j] <= sl_lvl:
            return (sl_lvl - entry) / ps, j, 'sl'
        if h[j] >= tp_lvl:
            return (tp_lvl - entry) / ps, j, 'tp'
        # قاعدهٔ S455: خروج در close همان کندلِ ارزیابی (قراردادِ این شبیه‌ساز)
        if vn is not None:
            fl = c[j] - entry
            ex, st = rule_step(vn, sym, j, True, fl <= 0.0, st, fl, sl_abs * rr, e, entry)
            if ex:
                return (c[j] - entry) / ps, j, 'fh_exit'
        j += 1
    return None  # معاملهٔ بازِ انتهای داده — در پایه هم حذف شده


# ───────────────────────────── بیماران ─────────────────────────────
def load_patient(name):
    _TF['tf'] = name.split('_')[1]
    patch_loaders()
    if name.startswith('S312'):
        from engine import trade_simulator as TS
        from strategies.sim_strategies import S312_MidMonth_Long
        from strategies.s450_mgmt_first_hour_low import BEST
        tf = name.split('_')[1]
        kw = BEST[tf]
        df = TS.load_data(f'XAUUSD_{tf}')
        spec = TS.asset_spec('XAUUSD')
        tr, _ = TS.simulate(df, S312_MidMonth_Long(**kw), 'XAUUSD', tf=tf,
                            warmup=220, max_bars_hold=kw['max_hold'])
        arr = (df['open'].values.astype(float), df['high'].values.astype(float),
               df['low'].values.astype(float), df['close'].values.astype(float))
        sym = symbols(df)

        def rf(t, vn):
            pnl, xb, r = replay_ts(t, arr, sym, vn, kw['max_hold'], spec)
            return pnl
        base_usd = tr['pnl_usd'].to_numpy(float)
        return df, tr, rf, base_usd

    if name == 'S356_H1':
        from engine import scalp_engine as se
        from strategies.s450_paired_s356 import reproduce_baseline
        df, tr, meta = reproduce_baseline()
        cfg = se.ASSETS['XAUUSD']; pv = cfg['pip_value']
        arr = (df['open'].values.astype(float), df['high'].values.astype(float),
               df['low'].values.astype(float), df['close'].values.astype(float))
        sym = symbols(df)

        def rf(t, vn):
            pnl_pip, xb, r = replay_se(t, arr, sym, vn, meta['max_hold'],
                                       cfg, True, meta['tp_pip'])
            return pnl_pip * pv
        base_usd = tr['pnl_pip'].to_numpy(float) * pv
        return df, tr, rf, base_usd

    if name == 'S344_M15':
        from engine import scalp_engine as se
        from strategies.s451_paired_s344 import reproduce_baseline, CFG
        df, tr = reproduce_baseline()
        cfg = se.ASSETS['XAUUSD']; pv = cfg['pip_value']
        arr = (df['open'].values.astype(float), df['high'].values.astype(float),
               df['low'].values.astype(float), df['close'].values.astype(float))
        sym = symbols(df)

        def rf(t, vn):
            pnl_pip, xb, r = replay_se(t, arr, sym, vn, CFG['maxhold'],
                                       cfg, False, CFG['tp'])
            return pnl_pip * pv
        base_usd = tr['pnl_pip'].to_numpy(float) * pv
        return df, tr, rf, base_usd

    if name == 'S382_H4':
        from strategies import s382_williamsr_momentum as s382
        df = s382.load(s382.CARD)
        ps = s382.pip_size(s382.ASSET)
        a = s382.atr(df)
        sl_abs = float(np.nanmedian(a.to_numpy())) * s382.SL_K
        sig = s382.signals(df)
        tr = s382.simulate_trades(df, sig, sl_abs, s382.RR, True, ps)
        arr = (df['open'].values.astype(float), df['high'].values.astype(float),
               df['low'].values.astype(float), df['close'].values.astype(float))
        sym = symbols(df)

        def rf(t, vn):
            out = replay_s382(t, arr, sym, vn, ps, sl_abs, s382.RR)
            return out[0] * 10.0 if out else None  # pip_value طلا = 10$
        base_usd = tr['pnl_pip'].to_numpy(float) * 10.0
        return df, tr, rf, base_usd

    raise ValueError(name)


def run(name):
    df, tr, rf, base_usd = load_patient(name)
    n = len(tr)
    # ── آزمونِ توازی ──
    par = np.array([rf(t, None) for t in tr.itertuples(index=False)], float)
    mism = np.abs(par - base_usd) > 1e-6
    print(f"[{name}] parity: {int(mism.sum())}/{n} mismatches "
          f"(max|Δ|={np.abs(par-base_usd).max():.9f})")
    if mism.any():
        for b in np.where(mism)[0][:5]:
            print("  bad:", b, "base=", base_usd[b], "replay=", par[b])
        _save(name, dict(patient=name, status='PARITY_FAIL',
                         n_mismatch=int(mism.sum()), n=n))
        return

    eb = tr['entry_bar'].to_numpy(int)
    mid = len(df) // 2
    m1 = eb < mid; m2 = ~m1

    cal = {}
    for vn in VARIANTS:
        mg = np.array([rf(t, vn) for t in tr.itertuples(index=False)], float)
        nch = int((np.abs(mg - base_usd) > 1e-9).sum())
        j1 = judge(metrics(base_usd[m1]), metrics(mg[m1]))
        cal[vn] = dict(mgmt_h1=metrics(mg[m1]), judge_h1=j1,
                       n_changed=nch, _mg=mg)
        print(f"[{name}] {vn}: changed={nch}/{n} H1 verdict={j1['verdict']} "
              f"(profit_ok={j1.get('profit_ok')}, improves={j1.get('improves')})")

    passers = [vn for vn in VARIANTS if cal[vn]['judge_h1']['verdict'] == 'PASS']
    if not passers:
        _save(name, dict(patient=name, status='REJECT_AT_CALIBRATION', n=n,
                         data_source='data/mt5_full (H4 resampled from H1)', n_bars=int(len(df)),
                         span=[str(pd.to_datetime(df['time'].iloc[0], unit='s')), str(pd.to_datetime(df['time'].iloc[-1], unit='s'))],
                         baseline_h1=metrics(base_usd[m1]),
                         calibration={vn: {k: v for k, v in cal[vn].items()
                                           if k != '_mg'} for vn in VARIANTS},
                         note='هیچ واریانت در نیمهٔ اول پاس نشد؛ '
                              'نیمهٔ دوم هرگز باز نشد (مسیرِ C).'))
        print(f"[{name}] REJECT at calibration — holdout never opened")
        return

    def dd_improve(vn):
        b = metrics(base_usd[m1])['maxDD']; g = cal[vn]['mgmt_h1']['maxDD']
        return (b - g) / b if b > 0 else 0.0
    win = max(passers, key=dd_improve)
    mg = cal[win]['_mg']
    j2 = judge(metrics(base_usd[m2]), metrics(mg[m2]))
    out = dict(patient=name, status='JUDGED', variant_winner=win, n=n,
               data_source='data/mt5_full (H4 resampled from H1)', n_bars=int(len(df)),
               span=[str(pd.to_datetime(df['time'].iloc[0], unit='s')), str(pd.to_datetime(df['time'].iloc[-1], unit='s'))],
               baseline_full=metrics(base_usd), treatment_full=metrics(mg),
               judge_full=judge(metrics(base_usd), metrics(mg)),
               h1=dict(base=metrics(base_usd[m1]), mgmt=metrics(mg[m1]),
                       judge=cal[win]['judge_h1']),
               h2=dict(base=metrics(base_usd[m2]), mgmt=metrics(mg[m2]),
                       judge=j2),
               final_verdict=j2['verdict'],
               calibration={vn: {k: v for k, v in cal[vn].items()
                                 if k != '_mg'} for vn in VARIANTS})
    _save(name, out)
    print(f"[{name}] winner {win} → H2 (holdout) verdict = {j2['verdict']}")
    print("  H2 base:", out['h2']['base'])
    print("  H2 mgmt:", out['h2']['mgmt'])


def _save(name, out):
    os.makedirs(os.path.join(ROOT, 'research', 'mgmt'), exist_ok=True)
    p = os.path.join(ROOT, 'research', 'mgmt', f'S459_{name}.json')
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("saved:", p)


if __name__ == '__main__':
    for nm in (sys.argv[1:] or ['S312_M30']):
        run(nm)
