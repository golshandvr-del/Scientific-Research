# -*- coding: utf-8 -*-
"""
S654 — «شوکِ مطلعِ سِشِنی» (Session-Slot Informed Shock) — فازِ اکتشاف
==============================================================================
دانشمند: رامانوجان — بلوکِ S650–S659 · شمارهٔ ۵ از ۱۰ · مسیرِ C (ممیزی §6.2)

سرشماریِ بکارت (پیش از نوشتنِ این فایل):
  • خانوادهٔ زندهٔ طلا = شوکِ تک‌کندلیِ بزرگ در TF درشت + follow + TP≥SL
    (S602/S604/S606/S607/S770/S950/S965/S966/S919/S1520 — همه ACCEPT).
  • گیت‌های آزموده روی این خانواده: درفت (S966/S919/S604)، رژیم σ (S606)،
    دو گیت (S607)، حجم (S848 در جریان)، پذیرش (S967 REJECT).
  • گیتِ «زمانِ روز / سِشِنِ کندلِ شوک» روی این خانواده: **صفر پرونده**.
    Admati–Pfleiderer (1988): صفر ارجاع در results/.
  • لایه‌های سِشِنیِ قبلی (S892/S894/S583/S832/S634/S635) همه *بی‌شرطِ شوک*
    بودند (درفتِ ساعتی) و REJECT شدند — این‌جا سِشِن فقط **گیت** روی رویداد است.

فرضیهٔ علّی (Admati–Pfleiderer 1988، تمرکزِ معامله‌گرانِ مطلع در ساعاتِ
پرنقدینگی): شوکی که در سِشِنِ نقدشونده (لندن/نیویورک) شکل می‌گیرد، حاملِ
اطلاعات است و ادامه دارد؛ شوکِ سِشِنِ آسیا (بازارِ کم‌عمق) نقدینگی‌محور است و
برمی‌گردد. کندل‌های H8 دقیقاً روی 0/8/16 UTC نشسته‌اند = سه سِشِن به‌طورِ
طبیعی هم‌تراز (بررسی شد: H8 start hours = {0,8,16}).

رویدادِ پایه (منجمد از S965 — جست‌وجو نمی‌شود، جز θ که در گرید افشا شده):
  range[t] = high−low ≥ θ × ATR21[t−1]   (ATR علّی)
  ρ = |close−open| / range ≥ 0.618          (retention — S965)
  جهت: follow با بدنه (صعودی→LONG، نزولی→SHORT)
گیتِ سِشِن: ساعتِ شروعِ کندلِ شوک (UTC) ∈ slot:
  ASIA=[0,8) · LONDON=[8,16) · NY=[16,24)   (H12: فقط دو slot 0–12/12–24؛ D1+: بی‌معنا ⇒ N/A)
هندسهٔ منجمد (S965): SL=1.272×ATR21[t−1] · TP=2.058×ATR21[t−1] (RR 1.618) ·
  hold=16 · بدونِ هم‌پوشانی · اسپرد 3.3

فضای جست‌وجو (پیش‌ثبت، نه بیشتر): θ ∈ {2.058, 2.618} × slot ∈ {A, L, N} ⇒ ۶ ترکیب.
  به‌علاوه «ungated» (بدونِ گیت) فقط برای P1 (گیت باید اطلاعات‌افزا باشد) — انتخاب نمی‌شود.
مسیرِ C: فقط نیمهٔ اول. چک‌پوینتِ per-TF با commit+push. سپرِ E-16 فعال.
اجرا:  python3 strategies/s654_session_shock_explore.py [TF ...]
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

OUT = os.path.join(ROOT, 'results', '_scan_S654')

# ---------------- پیش‌ثبتِ فضای جست‌وجو ----------------
THETAS = (2.058, 2.618)              # φ^1.5 , φ² — S965 از 2.618 استفاده کرد
RHO_MIN = 0.618                      # منجمد (S965)
SLOTS = {'ASIA': (0, 8), 'LONDON': (8, 16), 'NY': (16, 24)}
SLOTS_H12 = {'AM': (0, 12), 'PM': (12, 24)}
COMBOS = tuple((th, s) for th in THETAS for s in SLOTS)    # ۶ ترکیب

GEO_ATR_P = 21
GEO_SL_K = 1.272
GEO_TP_K = 2.058
GEO_RR = GEO_TP_K / GEO_SL_K
GEO_HOLD = 16

ASSET = 'XAUUSD'
TFS = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1')
NO_SLOT_TFS = ('D1', 'W1', 'MN1')    # سِشِن بی‌معنا
BASELINE_MAX_EVENTS = 60_000
MIN_N = 30


def base_events(open_, high, low, close, atr, theta):
    """شوکِ مطلعِ S965: range ≥ θ·ATR[t−1] و ρ ≥ 0.618. برمی‌گرداند (up, dn, atr_ref)."""
    n = len(close)
    atr_ref = np.full(n, np.nan)
    atr_ref[1:] = atr[:-1]
    rng_bar = high - low
    body = close - open_
    ok = np.isfinite(atr_ref) & (atr_ref > 0) & (rng_bar > 0)
    with np.errstate(invalid='ignore', divide='ignore'):
        rho = np.where(rng_bar > 0, np.abs(body) / np.where(rng_bar > 0, rng_bar, 1.0), 0.0)
    shock = ok & (rng_bar >= theta * atr_ref) & (rho >= RHO_MIN)
    up = shock & (body > 0)
    dn = shock & (body < 0)
    return up, dn, atr_ref


def slot_mask(hour, slot_rng):
    lo, hi = slot_rng
    return (hour >= lo) & (hour < hi)


def signals(open_, high, low, close, atr, hour, theta, slot_rng):
    up, dn, atr_ref = base_events(open_, high, low, close, atr, theta)
    if slot_rng is not None:
        m = slot_mask(hour, slot_rng)
        up = up & m
        dn = dn & m
    return up, dn, atr_ref


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


def _side_stats(df, idx, flag, atr_ref, cfg, base_side):
    st = eval_events(df, idx, np.full(len(idx), flag), atr_ref, cfg)
    if st is None or st['n'] < MIN_N:
        return dict(n=0 if st is None else st['n']), -9.0
    p0 = base_side['wr'] / 100.0
    lift = st['wr'] - base_side['wr']
    z = (lift / 100.0) * np.sqrt(st['n'] / (p0 * (1 - p0)))
    return dict(n=st['n'], wr=round(st['wr'], 3), exp=round(st['exp'], 3),
                lift=round(lift, 3), z_est=round(float(z), 3)), float(z)


def explore_tf(tf):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    src = d['src']
    assert 'mt5_full' in src, f"E-16 TRAP! src={src}"
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)   # 🔒 فقط نیمهٔ اول
    hour = d['hour'][:half].astype(np.int16)
    del df_full
    o = df['open'].values.astype(np.float64)
    close = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    atr = _atr_rma_nb(h, l, close, GEO_ATR_P)
    cfg = se.ASSETS[ASSET]

    warmup = max(4 * GEO_ATR_P, 200)
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[(valid >= warmup) & (valid + 1 + GEO_HOLD < half)]

    print(f"\n{'='*88}\n=== S654 explore :: {ASSET} {tf} — bars(full)={n_full:,} "
          f"half={half:,} valid={len(valid):,}\n    src={src}", flush=True)

    slots = SLOTS_H12 if tf == 'H12' else SLOTS
    combos = tuple((th, s) for th in THETAS for s in slots)
    out = dict(layer='S654', tf=tf, asset=ASSET, src=src, n_bars_full=n_full,
               half_idx=half, first_half_only=True, path='C',
               geometry=dict(atr_p=GEO_ATR_P, sl_k=GEO_SL_K, tp_k=GEO_TP_K,
                             rr=round(GEO_RR, 4), hold=GEO_HOLD,
                             rho_min=RHO_MIN),
               slots={k: list(v) for k, v in slots.items()},
               n_combos=len(combos), combos=[], ungated=[])

    if tf in NO_SLOT_TFS:
        out['status'] = 'NO_SLOT (session undefined at this TF)'
        return out
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

    # ungated (فقط برای P1 — انتخاب نمی‌شود)
    for th in THETAS:
        ls, ss, atr_ref = signals(o, h, l, close, atr, hour, th, None)
        ls[:warmup] = False
        ss[:warmup] = False
        li = np.where(ls)[0]
        si = np.where(ss)[0]
        li = li[li + 1 + GEO_HOLD < half]
        si = si[si + 1 + GEO_HOLD < half]
        rec = dict(theta=float(th), slot='UNGATED')
        rec['long'], zl = _side_stats(df, li, True, atr_ref, cfg, base['long'])
        rec['short'], zs = _side_stats(df, si, False, atr_ref, cfg, base['short'])
        rec['z_min'] = round(min(zl, zs), 3)
        out['ungated'].append(rec)
        print(f"    θ={th} UNGATED | L n={rec['long'].get('n', 0):>6} "
              f"z={rec['long'].get('z_est', '—')} lift={rec['long'].get('lift', '—')} | "
              f"S n={rec['short'].get('n', 0):>6} z={rec['short'].get('z_est', '—')} "
              f"lift={rec['short'].get('lift', '—')}", flush=True)

    for th, sname in combos:
        ls, ss, atr_ref = signals(o, h, l, close, atr, hour, th, slots[sname])
        ls[:warmup] = False
        ss[:warmup] = False
        li = np.where(ls)[0]
        si = np.where(ss)[0]
        li = li[li + 1 + GEO_HOLD < half]
        si = si[si + 1 + GEO_HOLD < half]
        rec = dict(theta=float(th), slot=sname)
        rec['long'], zl = _side_stats(df, li, True, atr_ref, cfg, base['long'])
        rec['short'], zs = _side_stats(df, si, False, atr_ref, cfg, base['short'])
        rec['z_min'] = round(min(zl, zs), 3)
        rec['z_max'] = round(max(zl, zs), 3)
        rec['z_sum'] = round(max(zl, 0.0) + max(zs, 0.0), 3)
        out['combos'].append(rec)
        print(f"    θ={th} {sname:<6} | L n={rec['long'].get('n', 0):>6} "
              f"z={rec['long'].get('z_est', '—')} lift={rec['long'].get('lift', '—')} "
              f"exp={rec['long'].get('exp', '—')} | "
              f"S n={rec['short'].get('n', 0):>6} z={rec['short'].get('z_est', '—')} "
              f"lift={rec['short'].get('lift', '—')} exp={rec['short'].get('exp', '—')} | "
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
        subprocess.run(['git', 'add', 'results/_scan_S654'], cwd=ROOT,
                       check=True, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m',
             f'S654 explore checkpoint: {tf} (first-half only, path C)'],
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
    print(f"S654 explore — path C — TFs: {tfs}", flush=True)
    for tf in tfs:
        try:
            out = explore_tf(tf)
        except AssertionError:
            raise
        except Exception as e:                              # noqa: BLE001
            out = dict(layer='S654', tf=tf, status='ERROR', error=str(e))
            print(f"    ✖ {tf} ERROR: {e}", flush=True)
        _save_and_push(tf, out)
    print("\nS654 explore — DONE", flush=True)


if __name__ == '__main__':
    main()
