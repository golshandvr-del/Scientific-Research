# -*- coding: utf-8 -*-
"""
S653 — Distributed Multi-Bar Shock Continuation — آزمونِ نهایی روی نیمهٔ دومِ دست‌نخورده (مسیرِ C) — قفل‌شده طبق PREREG
=============================================================================
⛔ طبقِ `research/S653_PREREG.md` (کامیت 0c1ab4f7) و **پیش از اجرا** کامیت
می‌شود. هیچ پارامتری این‌جا انتخاب نمی‌شود. نیمهٔ دوم هر TF یک‌بار لمس می‌شود.

روش (عیناً الگوی داوریِ S650–S652 — فقط سیگنال، هندسهٔ atr_ref و جدولِ قفل متفاوت):
  • معاملات با موتورِ رسمی `engine.scalp_engine.simulate_trades`
  • مدلِ صفر: K=600 زیرمجموعه از رخدادهای غیرشرطیِ هم‌هندسه، بذر 653653
  • داوری: `engine.rqs2.compute_rqs2` v2.6 با هر ۵ ورودی اجباری، n_trials=17
  • چک‌پوینتِ per-TF: JSON + commit + push · ضدِ OOM: سدِ قطعه‌قطعه (M1)
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import rqs2                                    # noqa: E402
from engine import scalp_engine as se                      # noqa: E402
from strategies.s346_fast import (barrier_outcomes,        # noqa: E402
                                  select_non_overlap)
from strategies.s650_ehlers_explore import _atr_rma_nb     # noqa: E402
from strategies.s653_multibar_shock_explore import (       # noqa: E402
    signals, GEO_ATR_P, GEO_SL_K, GEO_TP_K, GEO_RR, GEO_HOLD,
    SINGLE_BAR_CAP)
from tools import s434_fast_data as fd                     # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S653')
ASSET = 'XAUUSD'
SEED = 653653            # منجمد (PREREG)
PERM_K = 600             # منجمد
N_TRIALS = 17            # منجمد
SPLIT_FRAC = 0.70        # منجمد

# جدولِ قفل‌شدهٔ PREREG — TF → (k, theta). تغییرش = نقضِ پیش‌ثبت.
LOCKED = {
    'M1': (8, 1.618), 'M3': (3, 2.618), 'M4': (3, 2.618), 'M5': (3, 2.618),
    'M6': (3, 2.618), 'M10': (3, 2.618), 'M12': (3, 2.618),
    'M15': (5, 2.618), 'M20': (8, 2.618), 'M30': (8, 2.618),
    'H1': (8, 1.618), 'H2': (8, 1.618), 'H3': (5, 1.618), 'H6': (5, 1.618),
    'H8': (5, 1.618), 'H12': (8, 1.618), 'D1': (5, 1.618),
}
ORDER = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
         'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1')

CHUNK = 250_000   # ضدِ OOM — فقط بهینه‌سازیِ حافظه


def _barrier_compact(df, idx, flag, atr, cfg):
    ebs, offs, wins = [], [], []
    for s0 in range(0, len(idx), CHUNK):
        part = idx[s0:s0 + CHUNK]
        sl_dist = GEO_SL_K * atr[part]
        tp_dist = GEO_TP_K * atr[part]
        fo = barrier_outcomes(df, part, np.full(len(part), flag),
                              sl_dist, tp_dist, GEO_HOLD,
                              float(cfg['pip']), float(cfg['spread_pip']),
                              float(cfg.get('slip_pip', 0.0)))
        ebs.append(fo['entry_bar'].astype(np.int64))
        offs.append(fo['exit_off'].astype(np.int16))
        wins.append(fo['win'].astype(bool))
    if not ebs:
        return None
    return (np.concatenate(ebs), np.concatenate(offs), np.concatenate(wins))


def build_null(df, atr, valid, n_long, n_short, rng):
    cfg = se.ASSETS[ASSET]
    null = {}
    for side, flag, n_side in (('long', True, n_long),
                               ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) >= 2:
            fo = _barrier_compact(df, valid, flag, atr, cfg)
            if fo is not None:
                eb, off, win = fo
                m = len(eb)
                if m >= 2:
                    keep = select_non_overlap(eb, off)
                    if keep.sum() > 0:
                        d['uncond_wr'] = float(win[keep].mean() * 100.0)
                    if m > n_side:
                        wrs = []
                        for _ in range(PERM_K):
                            pick = np.sort(rng.choice(m, size=n_side,
                                                      replace=False))
                            k2 = select_non_overlap(eb[pick], off[pick])
                            if k2.sum() > 0:
                                wrs.append(float(win[pick][k2].mean() * 100.0))
                        if wrs:
                            a = np.asarray(wrs)
                            d.update(perm_mean=float(a.mean()),
                                     perm_sd=float(a.std(ddof=1)),
                                     perm_max=float(a.max()),
                                     perm_k=int(len(a)))
                del eb, off, win, fo
        null[side] = d
        print(f"      null {side:<5} uncond={d['uncond_wr']} "
              f"mean={d['perm_mean']} sd={d['perm_sd']} k={d['perm_k']}",
              flush=True)
    return null


def judge_tf(tf):
    t0 = time.time()
    k_, th_ = LOCKED[tf]
    d = fd.load_fast(ASSET, tf)
    src = d['src']
    assert 'mt5_full' in src, f"E-16 TRAP! src={src}"
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[half:].reset_index(drop=True)   # 🔓 لمسِ یگانه
    del df_full, d
    close = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    atr = _atr_rma_nb(h, l, close, GEO_ATR_P)

    print(f"\n{'='*88}\n=== S653 FINAL :: {ASSET} {tf} — locked k={k_} theta={th_} "
          f"| test=second half ({len(df):,} bars)\n    src={src}", flush=True)

    warmup = max(4 * GEO_ATR_P, 200)
    ok = np.isfinite(atr) & (atr > 0)

    ls, ss, atr_ref = signals(close, h, l, atr, k_, th_)
    okr = np.isfinite(atr_ref) & (atr_ref > 0)
    ls &= ok & okr
    ss &= ok & okr
    ls[:warmup] = False
    ss[:warmup] = False

    # هندسهٔ شناور بر پایهٔ atr_ref (ATR پیش از پنجره — علّی)، عیناً مانند اکسپلور
    atr_ref_f = np.where(okr, atr_ref, atr)
    sl_pip_arr = GEO_SL_K * atr_ref_f / se.ASSETS[ASSET]['pip']
    tp_pip_arr = GEO_TP_K * atr_ref_f / se.ASSETS[ASSET]['pip']

    tr = se.simulate_trades(df, ls, ss, sl_pip_arr, tp_pip_arr, ASSET,
                            max_hold=GEO_HOLD, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return dict(layer='S653', tf=tf, verdict='REJECT (no trades)',
                    locked=dict(k=k_, theta=th_), src=src)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int((tr['direction'] == 'short').sum())
    wr = float((tr['outcome'] == 'win').mean() * 100.0)
    print(f"    trades n={len(tr)} (L={n_long}/S={n_short}) wr={wr:.2f}% "
          f"exp={tr['pnl_pip'].mean():.2f}pip", flush=True)

    valid = np.where(ok)[0]
    valid = valid[(valid >= warmup) & (valid + 1 + GEO_HOLD < len(df))]
    rng = np.random.default_rng(SEED)
    null = build_null(df, atr, valid, n_long, n_short, rng)

    med_sl = float(np.median(tr['sl_pip'].values))
    res = rqs2.compute_rqs2(
        tr, ASSET,
        sl_pip=med_sl, tp_pip=(GEO_TP_K / GEO_SL_K) * med_sl,
        bar_time=df['time'].values, close=close,
        null=null, n_trials=N_TRIALS,
        split_bar=int(SPLIT_FRAC * len(df)))

    print(rqs2.format_rqs2(f'S653_{tf}', res), flush=True)

    out = dict(layer='S653', tf=tf, asset=ASSET, src=src,
               locked=dict(k=k_, theta=th_, atr_p=GEO_ATR_P,
                           sl_k=GEO_SL_K, tp_k=GEO_TP_K, rr=GEO_RR,
                           hold=GEO_HOLD, single_bar_cap=SINGLE_BAR_CAP),
               test_half='second', n_bars_test=len(df),
               n_trades=int(len(tr)), n_long=n_long, n_short=n_short,
               seed=SEED, perm_k=PERM_K, n_trials=N_TRIALS,
               verdict=res['verdict'], rqs2_score=res['rqs2_score'],
               gates=res['gates'], metrics=res['metrics'],
               notes=res['notes'], elapsed_s=round(time.time() - t0, 1))
    return out


def _save_push(tf, out):
    os.makedirs(OUT, exist_ok=True)
    fp = os.path.join(OUT, f'final_{tf}.json')
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"    ✔ saved {fp}", flush=True)
    try:
        subprocess.run(['git', 'add', 'results/_scan_S653'], cwd=ROOT,
                       check=True, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m',
             f"S653 FINAL {tf}: {out.get('verdict', '?')} "
             f"(hold-out second half, per PREREG 0c1ab4f7)"],
            cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'],
                           cwd=ROOT, capture_output=True, timeout=120)
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=ROOT,
                           capture_output=True, timeout=120)
            print(f"    ✔ git checkpoint pushed ({tf})", flush=True)
    except Exception as e:                                  # noqa: BLE001
        print(f"    ⚠ git checkpoint failed ({tf}): {e}", flush=True)


def main():
    tfs = sys.argv[1:] if len(sys.argv) > 1 else list(ORDER)
    print(f"S653 FINAL TEST — path C — locked per PREREG 0c1ab4f7 — TFs: {tfs}",
          flush=True)
    for tf in tfs:
        fp = os.path.join(OUT, f'final_{tf}.json')
        if os.path.exists(fp):
            print(f"    ↷ {tf} already judged — touch limit! skip.", flush=True)
            continue
        try:
            out = judge_tf(tf)
        except AssertionError:
            raise
        except Exception as e:                              # noqa: BLE001
            out = dict(layer='S653', tf=tf, verdict='ERROR', error=str(e))
            print(f"    ✖ {tf} ERROR: {e}", flush=True)
        _save_push(tf, out)
    print("\nS653 FINAL — DONE", flush=True)


if __name__ == '__main__':
    main()
