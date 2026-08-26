# -*- coding: utf-8 -*-
"""
S651 — «عدم‌توازنِ علامت» (Sign-Imbalance Continuation) — فازِ اکتشاف
======================================================================
دانشمند: رامانوجان — بلوکِ S650–S659 · مسیرِ C (ممیزی §6.2)

ایدهٔ لایه (نو، نه احیا — سرشماریِ بکارت انجام شد):
  frac_up[t]  = میانگینِ 1{close>close[-1]} روی پنجرهٔ W کندلِ اخیر
  LONG  : frac_up از پایین آستانهٔ θ عبور کند (لبهٔ گذر — ضدِ خوشه)
  SHORT : آینه‌ایِ کامل با frac_dn (تقارن)

چرا این نو است و چرا باید کار کند (سه قانونِ دیتابیس):
  ۱) S541: «هموارسازیِ بازگشتی = تأخیر، نه پیش‌بینی» → این‌جا صفر هموارسازی؛
     علامتِ خامِ کندل‌ها شمرده می‌شود.
  ۲) S602/S950 (هر دو ACCEPT): حرکتِ قویِ طلا در TFِ درشت «ادامه» می‌یابد →
     جهتِ ما ادامه است، نه بازگشت (متمایز از S326ِ سوخته).
  ۳) قاتلِ S650 کمبودِ توان بود (چگالیِ رخدادِ ~۷/سال). imbalance برخلافِ
     streakِ سخت‌گیرانه وقفه را تحمل می‌کند ⇒ رخدادِ بیشتر ⇒ توانِ بالاتر.

هندسهٔ منجمد (پیش از دیدنِ هر نتیجه):
  SL = 1.618 × ATR(34) Wilder   ·   TP = SL (RR=1.0 — درسِ S602/S950؛ TP≥SL)
  max_hold = 34 کندل · بدونِ هم‌پوشانی · اسپرد 3.3 پیپ

فضای جست‌وجو (همین‌جا پیش‌ثبت، نه بیشتر):
  W ∈ {8, 13, 21, 34, 55} (فیبوناچی) × θ ∈ {0.618, 0.764} (نسبتِ طلایی)
  ⇒ ۱۰ ترکیب. هندسه جست‌وجو نمی‌شود.

مسیرِ C: این اسکریپت فقط نیمهٔ اولِ داده را می‌بیند؛ منتخبِ هر TF سپس در
commitِ جدا پیش‌ثبت و نیمهٔ دوم یک‌بار لمس می‌شود.

دادهٔ اجباری: data/mt5_full (سپرِ E-16). چک‌پوینتِ per-TF با commit+push.
اجرا:  python3 strategies/s651_sign_imbalance_explore.py [TF ...]
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

OUT = os.path.join(ROOT, 'results', '_scan_S651')

# ---------------- پیش‌ثبتِ فضای جست‌وجو (مسیرِ C) ----------------
WINDOWS = (8, 13, 21, 34, 55)          # فیبوناچی
THETAS = (0.618, 0.764)                # نسبتِ طلایی — عددِ گرد ممنوع
COMBOS = tuple((w, th) for w in WINDOWS for th in THETAS)   # ۱۰ ترکیب

GEO_ATR_P = 34          # منجمد
GEO_SL_K = 1.618        # منجمد
GEO_RR = 1.0            # منجمد — TP = SL (درسِ S602/S950، قانونِ بودجه TP≥SL)
GEO_HOLD = 34           # منجمد
BASELINE_MAX_EVENTS = 400_000

TFS = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1')
ASSET = 'XAUUSD'        # هرگز EURUSD


def signals(close, w, theta):
    """لبهٔ گذرِ frac_up/frac_dn از θ — بدونِ هیچ هموارسازی."""
    n = len(close)
    up = np.zeros(n)
    dn = np.zeros(n)
    up[1:] = (close[1:] > close[:-1]).astype(np.float64)
    dn[1:] = (close[1:] < close[:-1]).astype(np.float64)
    cu = np.cumsum(up)
    cd = np.cumsum(dn)
    fu = np.full(n, np.nan)
    fdn = np.full(n, np.nan)
    fu[w:] = (cu[w:] - cu[:-w]) / w
    fdn[w:] = (cd[w:] - cd[:-w]) / w
    ls = np.zeros(n, dtype=bool)
    ss = np.zeros(n, dtype=bool)
    ls[w + 1:] = (fu[w + 1:] >= theta) & (fu[w:-1] < theta)
    ss[w + 1:] = (fdn[w + 1:] >= theta) & (fdn[w:-1] < theta)
    return ls, ss


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
    assert 'mt5_full' in src, f"E-16 TRAP! src={src} — توقف."
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

    warmup = max(2 * max(WINDOWS), 4 * GEO_ATR_P, 200)
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[(valid >= warmup) & (valid + 1 + GEO_HOLD < half)]

    print(f"\n{'='*88}\n=== S651 explore :: {ASSET} {tf} — bars(full)={n_full:,} "
          f"half={half:,} valid={len(valid):,}\n    src={src}", flush=True)

    out = dict(layer='S651', tf=tf, asset=ASSET, src=src, n_bars_full=n_full,
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
    for w, th in COMBOS:
        ls, ss = signals(close, w, th)
        ls &= ok
        ss &= ok
        ls[:warmup] = False
        ss[:warmup] = False
        li = np.where(ls)[0]
        si = np.where(ss)[0]
        li = li[li + 1 + GEO_HOLD < half]
        si = si[si + 1 + GEO_HOLD < half]
        rec = dict(w=int(w), theta=float(th))
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
        print(f"    W={w:>2} θ={th} | "
              f"L n={ln.get('n', 0):>7} z={ln.get('z_est', '—')} "
              f"lift={ln.get('lift', '—')} | "
              f"S n={sn.get('n', 0):>7} z={sn.get('z_est', '—')} "
              f"lift={sn.get('lift', '—')} | z_min={rec['z_min']}", flush=True)

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
        subprocess.run(['git', 'add', 'results/_scan_S651'], cwd=ROOT,
                       check=True, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m',
             f'S651 explore checkpoint: {tf} (first-half only, path C)'],
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
    print(f"S651 explore — path C — TFs: {tfs}", flush=True)
    for tf in tfs:
        try:
            out = explore_tf(tf)
        except AssertionError:
            raise
        except Exception as e:                              # noqa: BLE001
            out = dict(layer='S651', tf=tf, status='ERROR', error=str(e))
            print(f"    ✖ {tf} ERROR: {e}", flush=True)
        _save_and_push(tf, out)
    print("\nS651 explore — DONE", flush=True)


if __name__ == '__main__':
    main()
