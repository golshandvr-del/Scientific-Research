# -*- coding: utf-8 -*-
"""
S706 — داوریِ نهایی (یک آزمون، مسیر C)
سلولِ منجمدشده در جست‌وجو (نیمهٔ اول): XAUUSD-D1 · β=1.0 · m=2 · cont · k_sl=1.0
هندسهٔ منجمد: SL = 1.0 × median(ATR55 علّیِ نیمهٔ جست‌وجو) ؛ TP = 1.5×SL
بازسازی روی دادهٔ کامل؛ split_bar = n_full//2 ؛ نول K=1000 دوطرفه؛ n_trials=304.
درس BUG-EPOCH: cast دو مرحله‌ای [s]→[ns].
پیش‌ثبت: results/S706_PREREG_RENKO_TREND_BIRTH.md (کامیت 1bf2376b)
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine.rqs2 import compute_rqs2

SEED = 706
K_PERM = 1000
N_TRIALS = 304
TF = "D1"
BETA = 1.0
M = 2
K_SL = 1.0
RR = 1.5
MAX_HOLD = 16
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s706')

# — همان توابع اسکن (کپی عینی؛ تغییری ممنوع) —
from importlib import util as _u
_spec = _u.spec_from_file_location(
    's706scan', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             's706_renko_scan.py'))
_scan = _u.module_from_spec(_spec); _spec.loader.exec_module(_scan)
true_range = _scan.true_range
atr = _scan.atr
build_events = _scan.build_events
renko_run = _scan.renko_run


def main():
    rng = np.random.default_rng(SEED)
    d = fd.load_fast('XAUUSD', TF)
    assert 'mt5_full' in d['src'], f"E-16 TRAP: src={d['src']}"
    df = fd.as_dataframe(d)
    n = len(df)
    half = n // 2
    pip = 0.1

    # BUG-EPOCH: ثانیهٔ یونیکس → [s] → [ns]
    dt = df['time'].values.astype('datetime64[s]').astype('datetime64[ns]')

    # هندسهٔ منجمد از نیمهٔ جست‌وجو (بازتولید عینی اسکن)
    df_half = df.iloc[:half].reset_index(drop=True)
    tr_h = true_range(df_half)
    a55_h = atr(tr_h, 55)
    a55_shift = np.full(len(df_half), np.nan)
    a55_shift[1:] = a55_h[:-1]
    atr55_med_pip = float(np.nanmedian(a55_shift)) / pip
    sl_pip = K_SL * atr55_med_pip
    tp_pip = RR * sl_pip
    print(f"[هندسه منجمد] atr55_med(search)={atr55_med_pip:.2f}pip "
          f"SL={sl_pip:.2f} TP={tp_pip:.2f}", flush=True)

    # رویدادها روی دادهٔ کامل — همان build_events اسکن
    b = BETA * atr55_med_pip * pip                   # آجر منجمد از نیمهٔ جست‌وجو
    run = renko_run(df['close'].values.astype('float64'), b)
    ev = build_events(run, M)
    ev_next = np.zeros_like(ev)
    ev_next[1:] = ev[:-1]
    print(f"[رنکو] brick={b/pip:.2f}pip n_events(full)={(ev!=0).sum()}", flush=True)
    ls = pd.Series(ev_next == 1, index=df.index)   # cont: هم‌جهت آجرها
    ss = pd.Series(ev_next == -1, index=df.index)

    trades = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset='XAUUSD', max_hold=MAX_HOLD,
                                allow_overlap=False)
    n_tr = len(trades)
    wins = (trades['pnl_pip'].to_numpy() > 0).astype(np.float64)
    wr = float(wins.mean() * 100)
    n_long = int((trades['direction'] == 'long').sum())
    n_short = n_tr - n_long
    print(f"[کل داده] n={n_tr} (L={n_long}/S={n_short}) WR={wr:.2f}%", flush=True)

    # ---------- نولِ اندازه‌گیری‌شده روی دادهٔ کامل (دوطرفه، K=1000) ----------
    null_path = os.path.join(OUT, 'final_null_D1.json')
    if os.path.exists(null_path):
        null = json.load(open(null_path))
        print('[نول] از کش', flush=True)
    else:
        null = {}
        lo, hi = 200, n - MAX_HOLD - 2
        idx_all = np.arange(lo, hi)
        no_sig = pd.Series(np.zeros(n, dtype=bool), index=df.index)
        for side, n_side in (('long', n_long), ('short', n_short)):
            sig = np.zeros(n, dtype=bool); sig[idx_all] = True
            s_ser = pd.Series(sig, index=df.index)
            u_tr = se.simulate_trades(df, s_ser if side == 'long' else no_sig,
                                      no_sig if side == 'long' else s_ser,
                                      sl_pip=sl_pip, tp_pip=tp_pip,
                                      asset='XAUUSD', max_hold=MAX_HOLD,
                                      allow_overlap=True)
            w = (u_tr['pnl_pip'].to_numpy() > 0).astype(np.float64)
            uwr = float(w.mean() * 100)
            if n_side >= 3:
                perms = np.empty(K_PERM)
                for k in range(K_PERM):
                    take = rng.choice(len(w), size=min(n_side, len(w)),
                                      replace=False)
                    perms[k] = w[take].mean() * 100
                null[side] = dict(uncond_wr=uwr, perm_mean=float(perms.mean()),
                                  perm_sd=float(perms.std(ddof=1)),
                                  perm_max=float(perms.max()), perm_k=K_PERM,
                                  n_uncond=int(len(w)))
            else:
                null[side] = dict(uncond_wr=uwr, perm_mean=None, perm_sd=None,
                                  perm_max=None, perm_k=None)
            print(f"[نول {side}] uncond={uwr:.2f}% (n_uncond={len(w)})", flush=True)
        json.dump(null, open(null_path, 'w'), ensure_ascii=False, indent=1)

    # ---------- یک آزمون نهایی ----------
    res = compute_rqs2(trades, 'XAUUSD', sl_pip=sl_pip, tp_pip=tp_pip,
                       bar_time=dt, null=null, n_trials=N_TRIALS,
                       split_bar=half, close=df['close'].values,
                       initial_capital=10000.0, allow_overlap=False)
    line = (f"S706-D1 OFFICIAL | {res['verdict']} RQS2={res['rqs2_score']:.1f} | "
            f"n={n_tr} WR={wr:.2f}% | gates="
            + ' '.join(f"{g}:{'✓' if v else ('✗' if v is False else '?')}"
                       for g, v in res['gates'].items()))
    print(line, flush=True)
    print(json.dumps(res['metrics'], ensure_ascii=False, default=str), flush=True)
    for note in res['notes']:
        print('NOTE:', note, flush=True)
    json.dump({'line': line, 'gates': {k: bool(v) if v is not None else None
                                       for k, v in res['gates'].items()},
               'metrics': {k: (str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v)
                           for k, v in res['metrics'].items()},
               'verdict': res['verdict'], 'score': res['rqs2_score'],
               'notes': res['notes'], 'n': n_tr, 'wr': wr,
               'sl_pip': sl_pip, 'tp_pip': tp_pip, 'split_bar': half,
               'n_trials': N_TRIALS, 'seed': SEED},
              open(os.path.join(OUT, 'final_verdict.json'), 'w'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
