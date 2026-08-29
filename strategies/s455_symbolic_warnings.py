# -*- coding: utf-8 -*-
"""
s455_symbolic_warnings.py — S455 · هشدارهای نمادین: دو کندلِ آرام + 𝔻𝔻 (M3+M4)
================================================================================
پیش‌ثبت: results/S455_PREREG_ADDENDUM_SYMBOLIC_WARNINGS.md (commit 99a1178b قبل از این اجرا).

الفبای عِلّی (قفل‌شده): r_i = ln(c_i/c_{i-1})؛ آستانه‌ها = چندک‌های 1/3 و 2/3 از |r|
روی پنجرهٔ اکیداً قبلی [i-500, i-1] (min_periods=500). آرام: |r|<q_low؛
بزرگ: |r|>=q_high؛ 𝔻=نزولِ بزرگ، 𝕌=صعودِ بزرگ. حرفِ تعریف‌نشده ⇒ هیچ گیتی فعال نیست.

سه واریانتِ قفل‌شده (فقط بازنده‌ها؛ معاملهٔ در سود هرگز لمس نمی‌شود):
  V_QQ      : دو کندلِ آرامِ متوالی ⇒ بازنده را ببند (M3).
  V_QQ_HOLD : همان، اما اگر کلمهٔ نجات (long:𝔻𝔻 / short:𝕌𝕌) در ۳ کندلِ اخیر
              دیده شده ⇒ خروج سرکوب می‌شود (گیتِ نگه‌داری M4).
  V_DDFAIL  : کلمهٔ 𝔻𝔻 (short:𝕌𝕌) کامل شد و بازنده‌ایم ⇒ یک کندل مهلت؛ اگر
              نجات (long:𝕌 / short:𝔻) نیامد و هنوز بازنده ⇒ ببند (M4).

بیماران: S312_M30, S312_M15, S312_H1 (ts) · S356_H1 (se,long) · S344_M15 (se,short)
· S382_H4 (s382). قراردادهای خروج عینِ S453/S454.

**آزمونِ توازی (اجباری):** بازپخش با vn=None باید pnl پایه را معامله‌به‌معامله
(tol=1e-6) بازتولید کند؛ وگرنه PARITY_FAIL و هیچ داوری.

مسیرِ C: کالیبراسیون فقط نیمهٔ اول؛ برنده = بهترین بهبودِ maxDD میانِ پاس‌شدگان؛
بدونِ پاس ⇒ REJECT_AT_CALIBRATION و نیمهٔ دوم باز نمی‌شود.

اجرا: python3 strategies/s455_symbolic_warnings.py <patient>
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

VARIANTS = ('V_QQ', 'V_QQ_HOLD', 'V_DDFAIL')  # قفل‌شده در پیش‌ثبت
W = 500  # پنجرهٔ چندکِ عِلّی — عددِ ثابتِ پیش‌ثبت


def symbols(df):
    """الفبای نمادینِ عِلّی: (quiet, bigdown, bigup) — همه False جایی که تعریف‌نشده."""
    c = df['close'].astype(float)
    r = np.log(c).diff()
    a = r.abs()
    ql = a.rolling(W, min_periods=W).quantile(1 / 3).shift(1)
    qh = a.rolling(W, min_periods=W).quantile(2 / 3).shift(1)
    quiet = (a < ql).to_numpy()          # NaN مقایسه ⇒ False
    big = (a >= qh).to_numpy()
    up = (r > 0).to_numpy()
    return quiet, big & ~up, big & up


def rule_step(vn, sym, i, is_long, losing, state):
    """ارزیابیِ قاعده در close کندلِ i. خروجی: (exit_now, state جدید).

    state فقط برای V_DDFAIL: اندیسِ کندلِ مهلت (grace) یا None."""
    if vn is None or i < 2:
        return False, state
    quiet, bigdn, bigup_ = sym
    if vn in ('V_QQ', 'V_QQ_HOLD'):
        if not (quiet[i] and quiet[i - 1] and losing):
            return False, state
        if vn == 'V_QQ_HOLD':
            resc = bigdn if is_long else bigup_   # کلمهٔ نجات‌خواه
            for j in (i - 2, i - 1, i):
                if j >= 1 and resc[j - 1] and resc[j]:
                    return False, state           # گیتِ نگه‌داری M4
        return True, state
    if vn == 'V_DDFAIL':
        word = bigdn if is_long else bigup_
        resc = bigup_ if is_long else bigdn
        if state is not None and i == state:      # کندلِ مهلت
            if losing and not resc[i]:
                return True, None                 # نجات نیامد ⇒ ببند
            state = None                          # نجات آمد / در سود ⇒ پاک
        if word[i - 1] and word[i] and losing:    # کلمهٔ 𝔻𝔻 کامل شد
            state = i + 1
        return False, state
    raise ValueError(vn)


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
            ex, st = rule_step(vn, sym, i, True, (c[i] - entry) <= 0.0, st)
            if ex:
                return (o[nb] - entry - cost) * contract, nb, 'sym_exit'
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
            return g / pip - spread, j, 'sym_exit'
        if j == eb:
            continue  # در کندلِ ورود ارزیابی نداریم (عینِ موتور)
        if vn is not None:
            fl = (c[j] - fill) if is_long else (fill - c[j])
            ex, st = rule_step(vn, sym, j, is_long, fl <= 0.0, st)
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
            ex, st = rule_step(vn, sym, j, True, (c[j] - entry) <= 0.0, st)
            if ex:
                return (c[j] - entry) / ps, j, 'sym_exit'
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
    p = os.path.join(ROOT, 'research', 'mgmt', f'S455_{name}.json')
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("saved:", p)


if __name__ == '__main__':
    for nm in (sys.argv[1:] or ['S312_M30']):
        run(nm)
