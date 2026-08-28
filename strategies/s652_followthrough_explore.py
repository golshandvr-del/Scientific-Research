# -*- coding: utf-8 -*-
"""
S652 — «بستِ فراتر» (Follow-Through Close Continuation) — فازِ اکتشاف
======================================================================
دانشمند: رامانوجان — بلوکِ S650–S659 · مسیرِ C (ممیزی §6.2)

ایدهٔ لایه (نو — سرشماریِ بکارت: `close above high` = صفر پرونده):
  LONG  : close[t] > high[t-1] برای c کندلِ متوالی، و کندلِ t-c چنین نباشد
          (لبهٔ رشته — رویداد، نه حالت)، به‌علاوهٔ حاشیهٔ اختیاری
          close[t] ≥ high[t-1] + m×ATR(34)
  SHORT : آینه‌ایِ کامل (close[t] < low[t-1] − m×ATR)

چرا باید کار کند (قوانینِ دیتابیس):
  ۱) بزرگی‌محور است — بست باید از کلِ دامنهٔ کندلِ قبل فراتر رود
     (درسِ S651: شمارشِ علامت بدونِ بزرگی = حذفِ سیگنال).
  ۲) ادامه‌دهنده است (S602/S604/S950 — هر سه ACCEPT).
  ۳) صفر هموارسازی (قانونِ S541).
  ۴) متمایز از S792ِ سوخته (شمعِ شوکِ range≥2.618×ATR — این‌جا شرط نسبت به
     کندلِ قبل است نه ATR) و متمایز از S720ِ موازی (کششِ z چندمقیاسی).

هندسهٔ منجمد: SL=1.618×ATR(34) Wilder · TP=SL (RR=1.0) · hold=34 ·
بدونِ هم‌پوشانی · اسپرد 3.3

فضای جست‌وجو (پیش‌ثبت، نه بیشتر): c ∈ {1,2,3} × m ∈ {0, 0.618} ⇒ ۶ ترکیب.
مسیرِ C: فقط نیمهٔ اول. چک‌پوینتِ per-TF با commit+push. سپرِ E-16 فعال.
اجرا:  python3 strategies/s652_followthrough_explore.py [TF ...]
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from strategies.s346_fast import (barrier_outcomes,        # noqa: E402
                                  select_non_overlap)
from strategies.s650_ehlers_explore import _atr_rma_nb     # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S652')

# ---------------- پیش‌ثبتِ فضای جست‌وجو ----------------
CONSEC = (1, 2, 3)
MARGINS = (0.0, 0.618)      # ×ATR — نسبتِ طلایی، عددِ گرد ممنوع
COMBOS = tuple((c, m) for c in CONSEC for m in MARGINS)     # ۶ ترکیب

GEO_ATR_P = 34
GEO_SL_K = 1.618
GEO_RR = 1.0                # TP = SL — درسِ S602/S950
GEO_HOLD = 34
BASELINE_MAX_EVENTS = 400_000

TFS = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1')
ASSET = 'XAUUSD'


def signals(close, high, low, atr, c, m):
    """لبهٔ رشتهٔ c کندلِ follow-through با حاشیهٔ m×ATR."""
    n = len(close)
    ft_up = np.zeros(n, dtype=bool)
    ft_dn = np.zeros(n, dtype=bool)
    ft_up[1:] = close[1:] > (high[:-1] + m * atr[1:])
    ft_dn[1:] = close[1:] < (low[:-1] - m * atr[1:])
    # رشتهٔ دقیقاً c تایی که در t تمام می‌شود و در t-c برقرار نبوده
    run_u = np.ones(n, dtype=bool)
    run_d = np.ones(n, dtype=bool)
    for k in range(c):
        run_u[c:] &= ft_up[c - k:n - k]
        run_d[c:] &= ft_dn[c - k:n - k]
    run_u[:c] = False
    run_d[:c] = False
    edge_u = run_u.copy()
    edge_d = run_d.copy()
    edge_u[c:] &= ~ft_up[:n - c]
    edge_d[c:] &= ~ft_dn[:n - c]
    return edge_u, edge_d


def eval_events(df, sig_idx, is_long, atr, cfg):
    if len(sig_idx) == 0:
        return None
    sl_dist = GEO_SL_K * atr[sig_idx]
    tp_dist = GEO_RR * sl_dist
    fo = barrier_outcomes(df, sig_idx, is_long, sl_dist, tp_dist, GEO_HOLD,
                          float(cfg['pip']), float(cfg['spread_pip']),
                          float(cfg.get('slip_pip', 0.0)))
    if len(fo['entry_bar']) == 0:
        return None
    keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
    pnl = fo['pnl_pip'][keep]
    if len(pnl) == 0:
        return None
    win = pnl > 0
    return dict(n=int(len(pnl)), wr=float(win.mean() * 100.0),
                exp=float(pnl.mean()))


def explore_tf(tf):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    src = d['src']
    assert 'mt5_full' in src, f"E-16 TRAP! src={src}"
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)   # 🔒 فقط نیمهٔ اول
    del df_full
    close = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    atr = _atr_rma_nb(h, l, close, GEO_ATR_P)
    cfg = se.ASSETS[ASSET]

    warmup = max(4 * GEO_ATR_P, 200)
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[(valid >= warmup) & (valid + 1 + GEO_HOLD < half)]

    print(f"\n{'='*88}\n=== S652 explore :: {ASSET} {tf} — bars(full)={n_full:,} "
          f"half={half:,} valid={len(valid):,}\n    src={src}", flush=True)

    out = dict(layer='S652', tf=tf, asset=ASSET, src=src, n_bars_full=n_full,
               half_idx=half, first_half_only=True, path='C',
               geometry=dict(atr_p=GEO_ATR_P, sl_k=GEO_SL_K, rr=GEO_RR,
                             hold=GEO_HOLD),
               n_combos=len(COMBOS), combos=[])

    if len(valid) < 500:
        out['status'] = 'TOO_SHORT'
        return out

    stride = max(1, len(valid) // BASELINE_MAX_EVENTS)
    vb = valid[::stride]
    base = {}
    for side, flag in (('long', True), ('short', False)):
        st = eval_events(df, vb, np.full(len(vb), flag), atr, cfg)
        if st is None:
            out['status'] = 'NO_BASELINE'
            return out
        base[side] = st
        print(f"    baseline {side:<5} n={st['n']:,} wr={st['wr']:.2f}% "
              f"(stride={stride})", flush=True)
    out['baseline'] = {k: {kk: v[kk] for kk in ('n', 'wr', 'exp')}
                       for k, v in base.items()}

    ok = np.isfinite(atr) & (atr > 0)
    for c, m in COMBOS:
        ls, ss = signals(close, h, l, atr, c, m)
        ls &= ok
        ss &= ok
        ls[:warmup] = False
        ss[:warmup] = False
        li = np.where(ls)[0]
        si = np.where(ss)[0]
        li = li[li + 1 + GEO_HOLD < half]
        si = si[si + 1 + GEO_HOLD < half]
        rec = dict(c=int(c), m=float(m))
        zs = []
        for side, idx, flag in (('long', li, True), ('short', si, False)):
            st = eval_events(df, idx, np.full(len(idx), flag), atr, cfg)
            if st is None or st['n'] < 30:
                rec[side] = dict(n=0 if st is None else st['n'])
                zs.append(-9.0)
                continue
            p0 = base[side]['wr'] / 100.0
            lift = st['wr'] - base[side]['wr']
            z = (lift / 100.0) * np.sqrt(st['n'] / (p0 * (1 - p0)))
            rec[side] = dict(n=st['n'], wr=round(st['wr'], 3),
                             exp=round(st['exp'], 3), lift=round(lift, 3),
                             z_est=round(float(z), 3))
            zs.append(float(z))
        rec['z_min'] = round(min(zs), 3)
        rec['z_sum'] = round(sum(max(z, 0.0) for z in zs), 3)
        out['combos'].append(rec)
        ln = rec.get('long', {})
        sn = rec.get('short', {})
        print(f"    c={c} m={m} | "
              f"L n={ln.get('n', 0):>7} z={ln.get('z_est', '—')} "
              f"lift={ln.get('lift', '—')} exp={ln.get('exp', '—')} | "
              f"S n={sn.get('n', 0):>7} z={sn.get('z_est', '—')} "
              f"lift={sn.get('lift', '—')} exp={sn.get('exp', '—')} | "
              f"z_min={rec['z_min']}", flush=True)

    ranked = sorted(out['combos'], key=lambda r: r['z_min'], reverse=True)
    out['best_by_zmin'] = ranked[0] if ranked else None
    out['status'] = 'OK'
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def _save_and_push(tf, out):
    os.makedirs(OUT, exist_ok=True)
    fp = os.path.join(OUT, f'explore_{tf}.json')
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"    ✔ saved {fp}", flush=True)
    try:
        subprocess.run(['git', 'add', 'results/_scan_S652'], cwd=ROOT,
                       check=True, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m',
             f'S652 explore checkpoint: {tf} (first-half only, path C)'],
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
    tfs = sys.argv[1:] if len(sys.argv) > 1 else list(TFS)
    print(f"S652 explore — path C — TFs: {tfs}", flush=True)
    for tf in tfs:
        try:
            out = explore_tf(tf)
        except AssertionError:
            raise
        except Exception as e:                              # noqa: BLE001
            out = dict(layer='S652', tf=tf, status='ERROR', error=str(e))
            print(f"    ✖ {tf} ERROR: {e}", flush=True)
        _save_and_push(tf, out)
    print("\nS652 explore — DONE", flush=True)


if __name__ == '__main__':
    main()
