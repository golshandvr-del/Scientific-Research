# -*- coding: utf-8 -*-
"""
S503 — قانون Resumption علّی S356 روی تایم‌فریم‌های بکر H2/H3 | XAUUSD
========================================================================
پیش‌ثبت: results/S503_PREREG_RESUMPTION_VIRGIN_H2H3.md (commit 8fbc17bf — قبل از این اجرا)

قانون منجمد (همه از S356-ACCEPT):
  سیگنال = build_signals_causal(0.13, 16, 0.8, 12.0) ∧ regime_gate(r2_fib_55≥0.45)
  SL = 1.3×ATRpip(21) · TP = 2×SL · LONG-only · allow_overlap=False
ثابت‌های ساختاری پیش‌ثبت‌شده: H2: bpd=12, mh=14 · H3: bpd=8, mh=12 · ATR_P=21
ابطالگرها: F1 (lift≤0 per-card)، F2 (n<60 per-card).
استخر شرطی: هر دو lift>0 هم‌مرتبه (نسبت≤2.5) + χ² p≥0.05.
داور: compute_rqs2 v2.6 · n_trials=54 · holdout ۴۰٪ آخر.
"""
import os, sys, json, warnings
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

import engine.scalp_engine as se
import engine.rqs2 as rqs2
from strategies import s354_brooks_trend_resumption as base
from strategies.s354_causal_check import build_signals_causal
from strategies.s354_improve_long import build_null_canonical
from strategies.s500_s354_h1h4_pool import chi2_homogeneity, blend_pool_null

SEED = 20260813
K_PERM = 2000
N_TRIALS = 54
SPLIT_FRAC = 0.60
ASSET = 'XAUUSD'
SIG = dict(n_open_frac=0.13, late_hour=16, spike_k=0.8, tight_atr=12.0)
REGIME = ('r2_fib_55', 'ge', 0.45)
SL_K, RR = 1.3, 2.0
# ثابت‌های ساختاری پیش‌ثبت‌شده (فرمول بسته، صفر جاروب)
TF_STRUCT = {'H2': dict(bpd=12, mh=14, atr_p=21),
             'H3': dict(bpd=8,  mh=12, atr_p=21)}
OUT = os.path.join(ROOT, 'results', '_scan_S503')
os.makedirs(OUT, exist_ok=True)

# تزریق ثابت‌های ساختاری به دیکشنری‌های base (فقط کلیدهای جدید H2/H3)
base.TF_BARS_PER_DAY['H2'] = 12
base.TF_BARS_PER_DAY['H3'] = 8
base.TF_ATR_P['H2'] = 21
base.TF_ATR_P['H3'] = 21
base.TF_MAX_HOLD['H2'] = 14
base.TF_MAX_HOLD['H3'] = 12


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=float)
    print(f"  💾 {name}", flush=True)


def member(tf, path):
    """اجرای قانون منجمد روی یک TF + null اندازه‌گیری‌شده."""
    df = se.load_data(path)
    atr_pip = base._atr_pip(df, ASSET, base.TF_ATR_P[tf])
    sl = round(SL_K * atr_pip, 1)
    tp = round(RR * sl, 1)
    mh = base.TF_MAX_HOLD[tf]
    gate = base.regime_gate(df, REGIME)
    sig = build_signals_causal(df, ASSET, tf, SIG['n_open_frac'], SIG['late_hour'],
                               SIG['spike_k'], SIG['tight_atr']) & gate
    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp,
                            ASSET, max_hold=mh, allow_overlap=False)
    n = 0 if tr is None else len(tr)
    wr = 100.0 * float((tr['pnl_pip'] > 0).mean()) if n else 0.0
    return dict(tf=tf, df=df, sig=sig, tr=tr, n=n, wr=wr,
                sl=float(sl), tp=float(tp), mh=mh,
                n_signals=int(sig.sum()))


def judge(m, null):
    """یک فراخوان داور v2.6 روی کارت m."""
    df, tr = m['df'], m['tr']
    dt_all = df['dt']
    entry_dt = dt_all.to_numpy()[tr['entry_bar'].to_numpy(int)]
    q = np.quantile(entry_dt.astype('datetime64[s]').astype(np.int64), SPLIT_FRAC)
    holdout = entry_dt.astype('datetime64[s]').astype(np.int64) >= q
    np.random.seed(SEED)
    return rqs2.compute_rqs2(tr, ASSET, sl_pip=m['sl'], tp_pip=m['tp'],
                             bar_time=dt_all, null=null, close=df['close'],
                             holdout_mask=holdout, n_trials=N_TRIALS,
                             allow_overlap=False)


def gates_line(v):
    g = v['gates']
    return ' '.join(f"H{i}:{'✓' if g.get('H%d' % i) else '✗'}" for i in range(11))


def main():
    print('=' * 80)
    print('S503 — S356 resumption on virgin H2/H3 | XAUUSD (prereg 8fbc17bf)')
    print('=' * 80, flush=True)

    # --- گام ۰: دروازهٔ بازتولید H1 (بیت‌سازگاری با S356/S500) ------------------
    mH1 = member('H1', os.path.join(ROOT, 'data', 'XAUUSD_H1.csv'))
    ok = (mH1['n'] == 117) and (abs(mH1['wr'] - 51.28) <= 0.5)
    save('repro_h1.json', {'n': mH1['n'], 'wr': mH1['wr'], 'ok': ok})
    print(f"[0] H1 repro gate: n={mH1['n']} wr={mH1['wr']:.2f} -> "
          f"{'OK' if ok else 'FAIL'}", flush=True)
    if not ok:
        print('STOP: H1 reproduction failed (prereg §3.1).'); return

    # --- گام ۱: کارت‌های بکر -----------------------------------------------------
    cards = {}
    for tf in ('H2', 'H3'):
        m = member(tf, os.path.join(ROOT, 'data', 'mt5_full', f'XAUUSD_{tf}.csv'))
        cards[tf] = m
        print(f"[1] {tf}: bars={len(m['df']):,} signals={m['n_signals']} "
              f"n={m['n']} WR={m['wr']:.2f} SL={m['sl']} TP={m['tp']} mh={m['mh']}",
              flush=True)

    # --- گام ۲: null اندازه‌گیری‌شده + ابطالگرها + داوری per-card ----------------
    summary = {}
    for tf, m in cards.items():
        if m['n'] < 60:
            summary[tf] = dict(n=m['n'], self_reject='F2_n<60')
            print(f"[2] {tf}: F2 n={m['n']} < 60 -> card dead (no judge call)",
                  flush=True)
            continue
        null = build_null_canonical(m['df'], m['sig'], m['sl'], m['tp'], m['mh'],
                                    n_perm=K_PERM, seed=SEED)
        m['null'] = null
        ref = null['long']['uncond_wr']
        lift = m['wr'] - ref
        m['lift'] = lift
        print(f"[2] {tf}: ref={ref:.2f} lift={lift:+.2f}pp", flush=True)
        if lift <= 0:
            summary[tf] = dict(n=m['n'], wr=m['wr'], ref=ref, lift=lift,
                               self_reject='F1_lift<=0')
            print(f"    {tf}: F1 lift<=0 -> card dead (no judge call)", flush=True)
            continue
        v = judge(m, null)
        mt = v['metrics']
        summary[tf] = dict(n=m['n'], wr=m['wr'], ref=ref, lift=lift,
                           verdict=v['verdict'], rqs2=v['rqs2_score'],
                           z=mt.get('skill_z'), pf=mt.get('profit_factor'),
                           gates=gates_line(v))
        save(f'verdict_{tf}.json', v)
        print(f"    {tf} | {v['verdict']} RQS2={v['rqs2_score']:.1f} "
              f"z={mt.get('skill_z')} | {gates_line(v)}", flush=True)

    save('cards_summary.json', summary)

    # --- گام ۳: استخر شرطی (قیدهای پیش‌ثبت §3.3) --------------------------------
    lifts = {tf: cards[tf].get('lift') for tf in ('H2', 'H3')}
    can_pool = all(l is not None and l > 0 for l in lifts.values()) and \
               cards['H2']['n'] >= 60 and cards['H3']['n'] >= 60
    if can_pool:
        lo, hi = sorted(lifts.values())
        ratio = hi / max(lo, 1e-9)
        members = [dict(card=f'XAUUSD_{tf}', tr=cards[tf]['tr'],
                        n=cards[tf]['n'], null=cards[tf]['null'],
                        dt=cards[tf]['df']['dt'].values) for tf in ('H2', 'H3')]
        chi2, p = chi2_homogeneity(members)
        print(f"[3] pool guards: lift_ratio={ratio:.2f} (<=2.5?) "
              f"chi2={chi2:.3f} p={p:.3f} (>=0.05?)", flush=True)
        if ratio <= 2.5 and p >= 0.05:
            # تجمیع FIFO تقویمی
            rows = []
            for tf in ('H2', 'H3'):
                m = cards[tf]
                t = m['tr'].copy()
                t['src_card'] = f'XAUUSD_{tf}'
                t['entry_dt'] = m['df']['dt'].to_numpy()[t['entry_bar'].to_numpy(int)]
                t['exit_dt'] = m['df']['dt'].to_numpy()[
                    np.minimum(t['exit_bar'].to_numpy(int), len(m['df']) - 1)]
                rows.append(t)
            allt = pd.concat(rows).sort_values('entry_dt').reset_index(drop=True)
            keep = []
            busy_until = pd.Timestamp('1970-01-01')
            for i, r in allt.iterrows():
                if r['entry_dt'] >= busy_until:
                    keep.append(i)
                    busy_until = r['exit_dt']
            pool = allt.loc[keep].reset_index(drop=True)
            null_p = blend_pool_null(members, pool)
            # محور زمانی H2 (ریزتر) برای داور
            df_axis = cards['H2']['df']
            entry_dt = pool['entry_dt'].to_numpy().astype('datetime64[s]').astype(np.int64)
            q = np.quantile(entry_dt, SPLIT_FRAC)
            holdout = entry_dt >= q
            sl_med = float(np.median([cards['H2']['sl'], cards['H3']['sl']]))
            tp_med = float(np.median([cards['H2']['tp'], cards['H3']['tp']]))
            np.random.seed(SEED)
            vp = rqs2.compute_rqs2(pool, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                                   bar_time=df_axis['dt'], null=null_p,
                                   close=df_axis['close'], holdout_mask=holdout,
                                   n_trials=N_TRIALS, allow_overlap=False)
            mt = vp['metrics']
            save('verdict_pool.json', vp)
            print(f"    POOL | {vp['verdict']} RQS2={vp['rqs2_score']:.1f} "
                  f"n={mt.get('n_trades')} z={mt.get('skill_z')} | {gates_line(vp)}",
                  flush=True)
        else:
            print('    pool guards failed -> no pool (per prereg).', flush=True)
    else:
        print('[3] pool preconditions not met -> no pool.', flush=True)

    print('DONE.', flush=True)


if __name__ == '__main__':
    main()
