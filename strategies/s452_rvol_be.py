# -*- coding: utf-8 -*-
"""
s452_rvol_be.py — S452 · قفلِ سربه‌سرِ RVOL-شرطی (مادهٔ M2)
================================================================================
پیش‌ثبت: results/S452_PREREG_ADDENDUM_RVOL_ADAPTIVE.md (commit قبل از این اجرا).

قاعدهٔ ثابت: در بسته‌شدنِ کندلِ i در حینِ پوزیشن، اگر RVOL(i)<θ و معامله در
سود است ⇒ SL به نقطهٔ ورود (فقط سفت‌شدن). TP دست‌نخورده. θ ∈ {0.5,0.7,0.9}
با مسیرِ C: کالیبراسیون فقط روی نیمهٔ اول، آزمونِ یگانه روی نیمهٔ دوم.

چون SL حرکت می‌کند، بازپخش باید مسیرِ کاملِ براکت را با قراردادِ خودِ موتورِ
لایهٔ پایه شبیه‌سازی کند. سه قرارداد:
  conv='ts'  (engine/trade_simulator — S312): چکِ گپِ open، سپس SL-first
             intrabar؛ MANAGE در close کندلِ i از کندلِ i+2 مؤثر است (همان
             ترتیب حلقهٔ موتور)؛ خروجِ زمانی با CLOSE استراتژی در open.
  conv='se'  (engine/scalp_engine — S356/S344): چکِ hit در خودِ کندلِ ورود،
             کندلِ مبهم ⇒ SL، exit روی خودِ سطح؛ آپدیتِ SL بعد از چکِ exit
             و نه در کندلِ ورود ⇒ از کندلِ بعد مؤثر؛ خروجِ زمانی روی close.
  conv='s382' (شبیه‌سازِ اختصاصیِ S382): بدونِ max_hold، SL-first، exit روی
             سطح، بدونِ کسرِ هزینه در pnl_pip.

**آزمونِ توازی (اجباری، از پیش‌ثبت):** بازپخش با θ=None باید pnl پایه را
معامله‌به‌معامله (tol=1e-6) بازتولید کند؛ در غیرِ این صورت اجرای بیمار
نامعتبر اعلام می‌شود و داوری نمی‌شود.

اجرا: python3 strategies/s452_rvol_be.py <patient>
      patient ∈ {S312_M30, S312_M15, S312_H1, S356_H1, S344_M15, S382_H4}
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

THETAS = (0.5, 0.7, 0.9)   # قفل‌شده در پیش‌ثبت
RVOL_P = 55                # پنجرهٔ فیبوناچی، قفل‌شده


def rvol_series(df):
    v = pd.to_numeric(df['volume'], errors='coerce').astype(float)
    med = v.rolling(RVOL_P, min_periods=RVOL_P).median()
    rv = np.where(med.to_numpy() > 0, v.to_numpy() / med.to_numpy(), np.inf)
    return rv  # inf ⇒ قاعده هرگز فعال نمی‌شود (ایمن در دادهٔ بی‌حجم)


# ─────────────────────────── بازپخشِ یک معامله ───────────────────────────
def replay_ts(trade, arr, rv, theta, max_hold, spec):
    """قراردادِ trade_simulator (S312 LONG). برمی‌گرداند pnl_usd بر ۱ لات."""
    o, h, l, c = arr
    e = int(trade.entry_bar)
    entry = float(trade.entry_price)
    pip = spec['pip']; contract = spec['contract']; cost = spec['cost_price']
    sl = entry - float(trade.sl_pip) * pip
    tp = entry + float(trade.tp_pip) * pip
    n = len(o)
    cur_sl = sl
    pend_sl = None            # MANAGE ثبت‌شده در close کندلِ i ⇒ مؤثر از i+2
    i = e                     # حلقهٔ موتور از iteration e (کندلِ e بسته)
    while i < n - 1:
        nb = i + 1
        # (۱) چکِ hit کندلِ nb با cur_sl فعلی
        if o[nb] <= cur_sl:
            return (o[nb] - entry - cost) * contract, nb, 'sl_gap'
        if o[nb] >= tp:
            return (o[nb] - entry - cost) * contract, nb, 'tp_gap'
        if l[nb] <= cur_sl:
            return (cur_sl - entry - cost) * contract, nb, 'sl'
        if h[nb] >= tp:
            return (tp - entry - cost) * contract, nb, 'tp'
        # (۲) advise در close کندلِ i: CLOSE استراتژی (max_hold) در open کندلِ i+1
        if (i + 1) - e >= max_hold:
            return (o[nb] - entry - cost) * contract, nb, 'strategy_close'
        # (۳) اعمالِ MANAGE ثبت‌شده از iteration قبل (مؤثر از این‌جا به بعد ⇒ i+2)
        if pend_sl is not None:
            cur_sl = max(cur_sl, pend_sl)
            pend_sl = None
        # (۴) قاعدهٔ S452 در close کندلِ i (فقط سفت‌شدن)
        if theta is not None and rv[i] < theta and c[i] > entry:
            pend_sl = entry
        i += 1
    return (c[n - 1] - entry - cost) * contract, n - 1, 'eod'


def replay_se(trade, arr, rv, theta, max_hold, cfg, is_long, tp_pip):
    """قراردادِ scalp_engine (S356 LONG / S344 SHORT). pnl_pip خالص."""
    o, h, l, c = arr
    eb = int(trade.entry_bar)
    fill = float(trade.entry_price)
    pip = cfg['pip']; spread = cfg['spread_pip']; slip = cfg['slip_pip']
    sl_d = float(trade.sl_pip) * pip
    tp_d = float(tp_pip) * pip
    if is_long:
        cur_sl = fill - sl_d; tp_lvl = fill + tp_d
    else:
        cur_sl = fill + sl_d; tp_lvl = fill - tp_d
    n = len(o)
    end = min(eb + max_hold, n)
    for j in range(eb, end):
        if is_long:
            hit_sl = l[j] <= cur_sl; hit_tp = h[j] >= tp_lvl
        else:
            hit_sl = h[j] >= cur_sl; hit_tp = l[j] <= tp_lvl
        if hit_sl:  # مبهم ⇒ SL (بدبینانه، عینِ موتور)
            xf = cur_sl - slip * pip if is_long else cur_sl + slip * pip
            g = (xf - fill) if is_long else (fill - xf)
            return g / pip - spread, j, 'sl'
        if hit_tp:
            xf = tp_lvl - slip * pip if is_long else tp_lvl + slip * pip
            g = (xf - fill) if is_long else (fill - xf)
            return g / pip - spread, j, 'tp'
        if j == eb:
            continue  # در کندلِ ورود هیچ آپدیتی (عینِ موتور)
        # قاعدهٔ S452 در close کندلِ j ⇒ مؤثر از کندلِ j+1
        if theta is not None and rv[j] < theta:
            if (is_long and c[j] > fill) or ((not is_long) and c[j] < fill):
                cur_sl = max(cur_sl, fill) if is_long else min(cur_sl, fill)
    xb = end - 1
    xf = c[xb] - slip * pip if is_long else c[xb] + slip * pip
    g = (xf - fill) if is_long else (fill - xf)
    return g / pip - spread, xb, 'time'


def replay_s382(trade, arr, rv, theta, ps, sl_abs, rr):
    """قراردادِ شبیه‌سازِ اختصاصیِ S382 (LONG، بدونِ max_hold، بدونِ هزینه)."""
    o, h, l, c = arr
    e = int(trade.entry_bar)
    entry = c[e]
    cur_sl = entry - sl_abs
    tp_lvl = entry + sl_abs * rr
    n = len(o)
    j = e + 1
    while j < n:
        if l[j] <= cur_sl:
            return (cur_sl - entry) / ps, j, 'sl'
        if h[j] >= tp_lvl:
            return (tp_lvl - entry) / ps, j, 'tp'
        if theta is not None and rv[j] < theta and c[j] > entry:
            cur_sl = max(cur_sl, entry)
        j += 1
    return None  # معاملهٔ باز — در پایه هم حذف شده


# ───────────────────────────── بیماران ─────────────────────────────
def load_patient(name):
    """برمی‌گرداند: (df, trades, replay_fn(trade, theta)->(pnl_usd, ...))."""
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
        rv = rvol_series(df)

        def rf(t, theta):
            pnl, xb, r = replay_ts(t, arr, rv, theta, kw['max_hold'], spec)
            return pnl  # USD بر ۱ لات
        base_usd = tr['pnl_usd'].to_numpy(float)
        return df, tr, rf, base_usd

    if name == 'S356_H1':
        from engine import scalp_engine as se
        from strategies.s450_paired_s356 import reproduce_baseline
        df, tr, meta = reproduce_baseline()
        cfg = se.ASSETS['XAUUSD']; pv = cfg['pip_value']
        arr = (df['open'].values.astype(float), df['high'].values.astype(float),
               df['low'].values.astype(float), df['close'].values.astype(float))
        rv = rvol_series(df)

        def rf(t, theta):
            pnl_pip, xb, r = replay_se(t, arr, rv, theta, meta['max_hold'],
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
        rv = rvol_series(df)

        def rf(t, theta):
            pnl_pip, xb, r = replay_se(t, arr, rv, theta, CFG['maxhold'],
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
        rv = rvol_series(df)

        def rf(t, theta):
            out = replay_s382(t, arr, rv, theta, ps, sl_abs, s382.RR)
            return out[0] * 10.0 if out else None  # pip_value طلا = 10$
        base_usd = tr['pnl_pip'].to_numpy(float) * 10.0
        return df, tr, rf, base_usd

    raise ValueError(name)


def run(name):
    df, tr, rf, base_usd = load_patient(name)
    n = len(tr)
    # ── آزمونِ توازی: قاعدهٔ خاموش باید پایه را بیت‌به‌بیت بازتولید کند ──
    par = np.array([rf(t, None) for t in tr.itertuples(index=False)], float)
    mism = np.abs(par - base_usd) > 1e-6
    print(f"[{name}] parity: {int(mism.sum())}/{n} mismatches "
          f"(max|Δ|={np.abs(par-base_usd).max():.9f})")
    if mism.any():
        bad = np.where(mism)[0][:5]
        for b in bad:
            print("  bad:", b, "base=", base_usd[b], "replay=", par[b])
        out = dict(patient=name, status='PARITY_FAIL',
                   n_mismatch=int(mism.sum()), n=n)
        _save(name, out)
        return

    eb = tr['entry_bar'].to_numpy(int)
    mid = len(df) // 2
    m1 = eb < mid; m2 = ~m1

    # ── کالیبراسیون فقط روی نیمهٔ اول (مسیرِ C) ──
    cal = {}
    for th in THETAS:
        mg = np.array([rf(t, th) for t in tr.itertuples(index=False)], float)
        j1 = judge(metrics(base_usd[m1]), metrics(mg[m1]))
        cal[th] = dict(mgmt_h1=metrics(mg[m1]), judge_h1=j1,
                       _mg=mg)  # نگهداری برای نیمهٔ دوم (فقط θ برنده استفاده می‌شود)
        print(f"[{name}] θ={th}: H1 verdict={j1['verdict']} "
              f"(profit_ok={j1.get('profit_ok')}, improves={j1.get('improves')})")

    passers = [th for th in THETAS if cal[th]['judge_h1']['verdict'] == 'PASS']
    if not passers:
        out = dict(patient=name, status='REJECT_AT_CALIBRATION',
                   n=n, baseline_h1=metrics(base_usd[m1]),
                   calibration={str(th): {k: v for k, v in cal[th].items()
                                          if k != '_mg'} for th in THETAS},
                   note='هیچ θ در نیمهٔ اول معیارِ پیش‌ثبت را پاس نکرد؛ '
                        'نیمهٔ دوم هرگز باز نشد (مسیرِ C).')
        _save(name, out)
        print(f"[{name}] REJECT at calibration — holdout never opened")
        return

    # تابعِ انتخابِ قفل‌شده: بیشترین بهبودِ maxDD در نیمهٔ اول
    def dd_improve(th):
        b = metrics(base_usd[m1])['maxDD']; g = cal[th]['mgmt_h1']['maxDD']
        return (b - g) / b if b > 0 else 0.0
    win = max(passers, key=dd_improve)
    mg = cal[win]['_mg']
    j2 = judge(metrics(base_usd[m2]), metrics(mg[m2]))
    out = dict(patient=name, status='JUDGED', theta_winner=win, n=n,
               baseline_full=metrics(base_usd), treatment_full=metrics(mg),
               judge_full=judge(metrics(base_usd), metrics(mg)),
               h1=dict(base=metrics(base_usd[m1]), mgmt=metrics(mg[m1]),
                       judge=cal[win]['judge_h1']),
               h2=dict(base=metrics(base_usd[m2]), mgmt=metrics(mg[m2]),
                       judge=j2),
               final_verdict=j2['verdict'],
               calibration={str(th): {k: v for k, v in cal[th].items()
                                      if k != '_mg'} for th in THETAS})
    _save(name, out)
    print(f"[{name}] winner θ={win} → H2 (holdout) verdict = {j2['verdict']}")
    print("  H2 base:", out['h2']['base'])
    print("  H2 mgmt:", out['h2']['mgmt'])


def _save(name, out):
    os.makedirs(os.path.join(ROOT, 'research', 'mgmt'), exist_ok=True)
    p = os.path.join(ROOT, 'research', 'mgmt', f'S452_{name}.json')
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("saved:", p)


if __name__ == '__main__':
    for nm in (sys.argv[1:] or ['S312_M30']):
        run(nm)
