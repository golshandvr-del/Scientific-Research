# -*- coding: utf-8 -*-
"""
S502 — احیای بیمار S202 «SoS rising-edge» با دروازهٔ درفت علّی | XAUUSD-H1
============================================================================
پیش‌ثبت: results/S502_PREREG_SOS_DRIFTGATE_H1.md (commit f50618bb — قبل از این اجرا)

قانون منجمد (صفر پارامتر آزاد):
  پایه   = sos_rising_edge(df, 2, 20, 32)  ← عین s202 (خود shift(1) دارد)
  گیت    = close[i-1] > close[i-91]        ← تعریف درفت L=90 عین S950-ACCEPT/S523 (علّی)
  خروج   = SL=250 / TP=375 pip · mh=96 · LONG-only · allow_overlap=False
مدل صفر هم‌شرط (درس S523): مرجع‌ها در فضای drift>0 نمونه‌گیری می‌شوند.
ابطالگرهای پیش‌ثبت‌شده: F1 (WR فیلترشده ≤ WR پایه)، F2 (کنترل ضد-درفت)، F3 (n<120).
داور: engine.rqs2.compute_rqs2 v2.6 · n_trials=268 · holdout=۴۰٪ آخر.
"""
import os, sys, json, warnings
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np
import pandas as pd

from s171_brooks_signs_of_strength_filter import load
from s202_h1_priceaction_battery import sos_rising_edge
import engine.scalp_engine as se
import engine.rqs2 as rqs2

SEED = 20260813
K_PERM = 2000
N_TRIALS = 268
SPLIT_FRAC = 0.60
SL_PIP, TP_PIP, MAX_HOLD = 250.0, 375.0, 96
DRIFT_L = 90                      # منجمد از S950/S523 — بدون جاروب
ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_scan_S502')
os.makedirs(OUT, exist_ok=True)


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=float)
    print(f"  💾 {name}", flush=True)


def drift_mask(df, L=DRIFT_L):
    """درفت علّی: close[i-1] > close[i-1-L] (فقط کندل‌های بسته)."""
    c = df['close'].to_numpy(float)
    m = np.zeros(len(df), bool)
    m[L + 1:] = c[L:-1] > c[:-L - 1]
    return m


def run(df, ls):
    tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), SL_PIP, TP_PIP,
                            ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    return tr


def wr_of(tr):
    return 100.0 * float(np.mean(tr['pnl_pip'] > 0)) if tr is not None and len(tr) else 0.0


def build_null_conditioned(df, sig, cond, sl, tp, mh, n_perm=K_PERM, seed=23):
    """مدل صفر کانونی، اما هر دو مرجع در فضای cond=True (درس S523).

    uncond_wr = ورود LONG در «همهٔ» بارهای معتبرِ هم‌شرط (رقیب بی‌مهارتِ هم‌رژیم)
    perm_*    = توزیع جایگشتی k ورودی تصادفی از همان فضا"""
    rng = np.random.default_rng(seed)
    o = df['open'].to_numpy(float); h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    n = len(df)
    cfg = se.ASSETS[ASSET]; pip = cfg['pip']
    cost = cfg['spread_pip'] + 2 * cfg.get('slip_pip', 0.0)
    sl_d, tp_d = sl * pip, tp * pip
    k = int(sig.sum())
    valid = np.arange(260, n - mh - 2)
    valid = valid[cond[valid]]                       # ⭐ هم‌شرط‌سازی

    def _wr_long(entries):
        wins = used = 0; last_exit = -1
        for si in entries:
            if si <= last_exit:
                continue
            eb = si + 1
            if eb >= n:
                continue
            ent = o[eb]; hit = None; kend = min(eb + mh, n)
            for kk in range(eb, kend):
                if l[kk] <= ent - sl_d:
                    hit = False; last_exit = kk; break
                if h[kk] >= ent + tp_d:
                    hit = True; last_exit = kk; break
            if hit is None:
                last = c[kend - 1]; last_exit = kend - 1
                hit = ((last - ent) / pip - cost) > 0
            used += 1
            if hit:
                wins += 1
        return (100.0 * wins / used) if used else None

    uncond = _wr_long(valid)
    perms = []
    for _ in range(n_perm):
        pick = np.sort(rng.choice(valid, size=min(k, len(valid)), replace=False))
        w = _wr_long(pick)
        if w is not None:
            perms.append(w)
    pa = np.array(perms)
    long_null = dict(uncond_wr=uncond, perm_mean=float(pa.mean()),
                     perm_sd=float(pa.std(ddof=1)), perm_max=float(pa.max()),
                     perm_k=len(pa))
    zero = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=0)
    return {'long': long_null, 'short': zero}


def main():
    print('=' * 80)
    print('S502 — SoS rising-edge × drift-gate(L=90) | XAUUSD-H1 (prereg f50618bb)')
    print('=' * 80, flush=True)

    df = load('XAUUSD_H1')
    print(f"data: {len(df):,} bars | {df['dt'].min()} -> {df['dt'].max()}", flush=True)

    # --- گام ۱: دروازهٔ بازتولید لنگر S202 (بی‌فیلتر) --------------------------
    base_ls = sos_rising_edge(df, 2, 20, 32)
    tr_base = run(df, base_ls)
    n_b, wr_b = len(tr_base), wr_of(tr_base)
    ok = (abs(n_b - 603) <= 0.05 * 603) and (abs(wr_b - 52.57) <= 2.0)
    save('repro_anchor.json', {'n': n_b, 'wr': wr_b, 'ok': ok})
    print(f"[1] anchor repro: n={n_b} wr={wr_b:.2f} -> {'OK' if ok else 'FAIL'}", flush=True)
    if not ok:
        print('STOP: anchor reproduction failed (prereg §5).'); return

    # --- گام ۲: اعمال گیت درفت -------------------------------------------------
    dm = drift_mask(df)
    ls = base_ls & dm
    tr = run(df, ls)
    n_f, wr_f = len(tr), wr_of(tr)
    print(f"[2] drift-gated: signals={int(ls.sum())}/{int(base_ls.sum())} "
          f"trades={n_f} WR={wr_f:.2f} (base {wr_b:.2f})", flush=True)

    # --- گام ۳: ابطالگرهای پیش‌ثبت‌شده -----------------------------------------
    if n_f < 120:
        save('falsifiers.json', {'F3_n': n_f, 'self_reject': 'F3'})
        print(f"SELF-REJECT per prereg §5 F3: n={n_f} < 120."); return
    f1_dead = wr_f <= wr_b
    ls_anti = base_ls & (~dm)
    tr_anti = run(df, ls_anti)
    n_a, wr_a = (len(tr_anti), wr_of(tr_anti)) if tr_anti is not None else (0, 0.0)
    f2_dead = (n_a >= 30) and (wr_a >= wr_f)
    save('falsifiers.json', {'F1_wr_filtered': wr_f, 'F1_wr_base': wr_b,
                             'F1_dead': f1_dead,
                             'F2_anti_n': n_a, 'F2_anti_wr': wr_a, 'F2_dead': f2_dead,
                             'F3_n': n_f})
    print(f"[3] falsifiers: F1 {'DEAD' if f1_dead else 'pass'} | "
          f"F2 anti-drift n={n_a} WR={wr_a:.2f} {'DEAD' if f2_dead else 'pass'} | "
          f"F3 n={n_f} pass", flush=True)
    if f1_dead or f2_dead:
        print('SELF-REJECT per prereg §5.'); return

    # --- گام ۴: null هم‌شرط + قضاوت v2.6 ---------------------------------------
    null = build_null_conditioned(df, ls, dm, SL_PIP, TP_PIP, MAX_HOLD,
                                  n_perm=K_PERM, seed=23)
    save('null_conditioned.json', {'long': null['long']})
    print(f"[4] conditioned null: uncond_wr={null['long']['uncond_wr']:.2f} "
          f"perm_mean={null['long']['perm_mean']:.2f} "
          f"perm_sd={null['long']['perm_sd']:.2f} "
          f"perm_max={null['long']['perm_max']:.2f}", flush=True)

    dt_all = df['dt']
    entry_dt = dt_all.to_numpy()[tr['entry_bar'].to_numpy(int)]
    q = np.quantile(entry_dt.astype('datetime64[s]').astype(np.int64), SPLIT_FRAC)
    holdout = entry_dt.astype('datetime64[s]').astype(np.int64) >= q

    np.random.seed(SEED)
    verdict = rqs2.compute_rqs2(
        tr, ASSET, sl_pip=SL_PIP, tp_pip=TP_PIP,
        bar_time=dt_all, null=null, close=df['close'],
        holdout_mask=holdout, n_trials=N_TRIALS, allow_overlap=False)

    m = verdict['metrics']; g = verdict['gates']
    save('verdict.json', verdict)
    gates_str = ' '.join(f"H{i}:{'✓' if g.get('H%d' % i) else '✗'}" for i in range(11))
    print(f"S502 | {verdict['verdict']} RQS2={verdict['rqs2_score']:.1f} | "
          f"n={m.get('n_trades')} WR={m.get('win_rate')} lift={m.get('skill_lift_pp')} "
          f"z={m.get('skill_z')} PF={m.get('profit_factor')} | {gates_str}", flush=True)


if __name__ == '__main__':
    main()
