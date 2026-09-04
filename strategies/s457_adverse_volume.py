# -*- coding: utf-8 -*-
"""
s457_adverse_volume.py — S457 · خروجِ بازنده در اوجِ حجمِ مخالف (Adverse Volume Climax)
================================================================================
پیش‌ثبت: results/S457_PREREG_ADDENDUM_ADVERSE_VOLUME_CLIMAX_EXIT.md (کامیت قبل از اجرا).

قاعده (قفل‌شده): در close کندلِ i بعد از ورود، اگر rvol_i = vol_i/median(vol_{i-54..i})
>= θ و کندل مخالفِ جهتِ معامله بسته شده و سودِ شناور <= 0 ⇒ خروج (ts/se: open بعد
پس از تقدمِ SL/TP/max_hold؛ S382: close). θ ∈ {1.5, 2.0, 3.0}. rvol تعریف‌نشده ⇒ ∞
⇒ هرگز فعال نمی‌شود. معاملهٔ در سود لمس نمی‌شود.

بیماران/قراردادها عینِ S453–S456. توازی اجباری؛ مسیرِ C.
اجرا: python3 strategies/s457_adverse_volume.py <patient>
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

VARIANTS = ('R15', 'R20', 'R30')  # قفل‌شده در پیش‌ثبت
THETA = {'R15': 1.5, 'R20': 2.0, 'R30': 3.0}
RVOL_P = 55


def symbols(df):
    """(rvol, bearish, bullish) — rvol=inf جایی که میانه تعریف‌نشده/صفر."""
    v = pd.to_numeric(df['volume'], errors='coerce').astype(float)
    med = v.rolling(RVOL_P, min_periods=RVOL_P).median().to_numpy()
    with np.errstate(invalid='ignore', divide='ignore'):
        rv = np.where(med > 0, v.to_numpy() / med, np.inf)
    rv = np.where(np.isnan(rv), np.inf, rv)
    o = df['open'].to_numpy(float); c = df['close'].to_numpy(float)
    return rv, c < o, c > o


def rule_step(vn, sym, i, is_long, losing, state, fl=None, tp_dist=None):
    if vn is None:
        return False, state
    rv, bear, bull = sym
    adverse = bear[i] if is_long else bull[i]
    if losing and adverse and rv[i] >= THETA[vn] and np.isfinite(rv[i]):
        return True, state
    return False, state


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
            ex, st = rule_step(vn, sym, i, True, fl <= 0.0, st, fl, tp - entry)
            if ex:
                return (o[nb] - entry - cost) * contract, nb, 'vol_exit'
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
            return g / pip - spread, j, 'vol_exit'
        if j == eb:
            continue  # در کندلِ ورود ارزیابی نداریم (عینِ موتور)
        if vn is not None:
            fl = (c[j] - fill) if is_long else (fill - c[j])
            ex, st = rule_step(vn, sym, j, is_long, fl <= 0.0, st, fl, tp_d)
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
            ex, st = rule_step(vn, sym, j, True, fl <= 0.0, st, fl, sl_abs * rr)
            if ex:
                return (c[j] - entry) / ps, j, 'vol_exit'
        j += 1
    return None  # معاملهٔ بازِ انتهای داده — در پایه هم حذف شده


# ───────────────────────────── بیماران ─────────────────────────────
def load_patient(name):
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
    p = os.path.join(ROOT, 'research', 'mgmt', f'S457_{name}.json')
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("saved:", p)


if __name__ == '__main__':
    for nm in (sys.argv[1:] or ['S312_M30']):
        run(nm)
