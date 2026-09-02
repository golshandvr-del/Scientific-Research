# -*- coding: utf-8 -*-
"""
S653 — «شوکِ چندکندلیِ توزیع‌شده» (Distributed Multi-Bar Shock) — فازِ اکتشاف
==============================================================================
دانشمند: رامانوجان — بلوکِ S650–S659 · مسیرِ C (ممیزی §6.2)

ایدهٔ لایه (نو — سرشماریِ بکارت: `multi-bar shock`/`k-bar move`/`cumulative move`
= صفر پرونده):
  حرکتِ خالصِ k کندل: mv[t] = close[t] − close[t−k]
  شوکِ توزیع‌شده = |mv[t]| ≥ θ × ATR21[t−k−1]   (ATR علّی — پیش از پنجره)
  و **هیچ کندلِ منفردی** در پنجرهٔ (t−k+1..t) خودش شوک نباشد:
      max(high−low در پنجره) < 1.618 × ATR21[t−k−1]
  ⇒ این دقیقاً مکملِ خانوادهٔ single-bar ACCEPT است (S965/S602/S770/S950 همه
  «یک کندلِ بزرگ» را می‌گیرند؛ این‌جا حرکتِ بزرگ روی چند کندلِ عادی پخش شده).
  LONG اگر mv>0 (follow — قاعدهٔ ۵بار تأییدشدهٔ طلا)، SHORT آینه‌ای.
  رویداد = لبه: در t−1 شرط برقرار نبوده (event, not state).

چرا باید کار کند (قوانینِ دیتابیس):
  ۱) بزرگیِ **مطلق** نسبت به ATR (درسِ S651 و S652: علامت یا آستانهٔ نسبی کافی نیست).
  ۲) ادامه‌دهنده (S602/S604/S770/S950/S965 — پنج ACCEPT مستقل).
  ۳) صفر هموارسازی (قانونِ S541). ۴) TP>SL (S965: 1.272/2.058).
  متمایز از S544 (رگهٔ کلوزهای صعودی بدون بزرگی)، S660 (LagRSI اشباع)،
  S720 (z چندمقیاسی SMA/STD) و S792/S965 (شوکِ تک‌کندلی).

هندسهٔ منجمد: SL=1.272×ATR21[t−k−1] · TP=2.058×ATR21[t−k−1] (RR=1.618) ·
hold=16 · بدونِ هم‌پوشانی · اسپرد 3.3

فضای جست‌وجو (پیش‌ثبت، نه بیشتر): k ∈ {3,5,8} × θ ∈ {1.618, 2.618} ⇒ ۶ ترکیب.
  (شبکهٔ A = θ∈{2.618,4.236} فقط روی H1 نیمهٔ اول اجرا شد: n≤31 — کم‌بسامد؛
   جایگزین شد پیش از commit. آرتیفکتش نگه داشته شد. در PREREG افشا می‌شود.)
مسیرِ C: فقط نیمهٔ اول. چک‌پوینتِ per-TF با commit+push. سپرِ E-16 فعال.
اجرا:  python3 strategies/s653_multibar_shock_explore.py [TF ...]
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

OUT = os.path.join(ROOT, 'results', '_scan_S653')

# ---------------- پیش‌ثبتِ فضای جست‌وجو ----------------
KS = (3, 5, 8)                       # فیبوناچی
THETAS = (1.618, 2.618)              # φ, φ² — شبکهٔ A (2.618/4.236) روی H1 n<100 داد؛
                                     # آرتیفکت: explore_H1_gridA_theta2618_4236.json (افشای صادقانه)
COMBOS = tuple((k, th) for k in KS for th in THETAS)       # ۶ ترکیب
SINGLE_BAR_CAP = 1.618               # هیچ کندلی در پنجره range ≥ این × ATR نباشد

GEO_ATR_P = 21
GEO_SL_K = 1.272
GEO_TP_K = 2.058
GEO_RR = GEO_TP_K / GEO_SL_K         # ≈1.618
GEO_HOLD = 16
BASELINE_MAX_EVENTS = 400_000

TFS = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1')
ASSET = 'XAUUSD'


def signals(close, high, low, atr, k, theta):
    """لبهٔ شوکِ چندکندلیِ توزیع‌شده. atr_ref[t] = ATR[t-k-1] (علّی).
    برمی‌گرداند (long_mask, short_mask, atr_ref) — atr_ref برای هندسهٔ شناور."""
    n = len(close)
    atr_ref = np.full(n, np.nan)
    atr_ref[k + 1:] = atr[:n - k - 1]
    mv = np.full(n, np.nan)
    mv[k:] = close[k:] - close[:n - k]
    rng_bar = high - low
    acc = rng_bar.copy()
    for j in range(1, k):
        acc[j:] = np.maximum(acc[j:], rng_bar[:n - j])
    win_max = np.full(n, np.nan)
    win_max[k - 1:] = acc[k - 1:]
    ok = (np.isfinite(atr_ref) & (atr_ref > 0) & np.isfinite(mv)
          & np.isfinite(win_max))
    no_single = ok & (win_max < SINGLE_BAR_CAP * atr_ref)
    st_up = no_single & (mv >= theta * atr_ref)
    st_dn = no_single & (mv <= -theta * atr_ref)
    edge_u = st_up.copy()
    edge_d = st_dn.copy()
    edge_u[1:] &= ~st_up[:-1]
    edge_d[1:] &= ~st_dn[:-1]
    edge_u[:k + 1] = False
    edge_d[:k + 1] = False
    return edge_u, edge_d, atr_ref


def eval_events(df, sig_idx, is_long, atr, cfg):
    if len(sig_idx) == 0:
        return None
    sl_dist = GEO_SL_K * atr[sig_idx]
    tp_dist = GEO_TP_K * atr[sig_idx]
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

    print(f"\n{'='*88}\n=== S653 explore :: {ASSET} {tf} — bars(full)={n_full:,} "
          f"half={half:,} valid={len(valid):,}\n    src={src}", flush=True)

    out = dict(layer='S653', tf=tf, asset=ASSET, src=src, n_bars_full=n_full,
               half_idx=half, first_half_only=True, path='C',
               geometry=dict(atr_p=GEO_ATR_P, sl_k=GEO_SL_K, tp_k=GEO_TP_K,
                             rr=round(GEO_RR, 4), hold=GEO_HOLD,
                             single_bar_cap=SINGLE_BAR_CAP),
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

    for k, th in COMBOS:
        ls, ss, atr_ref = signals(close, h, l, atr, k, th)
        ls[:warmup] = False
        ss[:warmup] = False
        li = np.where(ls)[0]
        si = np.where(ss)[0]
        li = li[li + 1 + GEO_HOLD < half]
        si = si[si + 1 + GEO_HOLD < half]
        rec = dict(k=int(k), theta=float(th))
        zs = []
        for side, idx, flag in (('long', li, True), ('short', si, False)):
            st = eval_events(df, idx, np.full(len(idx), flag), atr_ref, cfg)
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
        rec['z_max'] = round(max(zs), 3)
        rec['z_sum'] = round(sum(max(z, 0.0) for z in zs), 3)
        out['combos'].append(rec)
        ln = rec.get('long', {})
        sn = rec.get('short', {})
        print(f"    k={k} θ={th} | "
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
        subprocess.run(['git', 'add', 'results/_scan_S653'], cwd=ROOT,
                       check=True, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m',
             f'S653 explore checkpoint: {tf} (first-half only, path C)'],
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
    print(f"S653 explore — path C — TFs: {tfs}", flush=True)
    for tf in tfs:
        try:
            out = explore_tf(tf)
        except AssertionError:
            raise
        except Exception as e:                              # noqa: BLE001
            out = dict(layer='S653', tf=tf, status='ERROR', error=str(e))
            print(f"    ✖ {tf} ERROR: {e}", flush=True)
        _save_and_push(tf, out)
    print("\nS653 explore — DONE", flush=True)


if __name__ == '__main__':
    main()
