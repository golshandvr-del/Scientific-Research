# -*- coding: utf-8 -*-
"""
S655 — NFP Announcement-Bar Informed Continuation — داوریِ نهایی (مسیرِ A، صفر پارامتر آزاد)
==============================================================================
⛔ طبقِ `research/S655_PREREG.md` (کامیت e2315871) و **پیش از اجرا** کامیت می‌شود.
هیچ جست‌وجویی وجود ندارد؛ کلِ دادهٔ ۱۵.۶ سالهٔ mt5_full یک بار داوری می‌شود.

رویداد: کندلی که لحظهٔ 08:30 America/New_York روزِ انتشارِ NFP (اولین جمعهٔ ماه؛
تعطیل ⇒ پنجشنبهٔ قبل) درونِ بازهٔ آن است. جهت = بدنهٔ همان کندل (follow).
بازوها: RHO (ρ≥0.618) اصلی · ALL کنترل (P1).
هندسه: SL=0.618×R، TP=1.0×R (R=دامنهٔ کندلِ اعلان)، hold=16، بدونِ هم‌پوشانی.
مدلِ صفر: K=600 زیرمجموعه از کندل‌های غیرشرطی با همان قاعده، بذر 655655.
n_trials=34 (۱۷ TF × ۲ بازو). فقط اکتشاف — هیچ تغییری در سایت.
"""
import json
import os
import subprocess
import sys
import time
import zoneinfo

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import rqs2                                    # noqa: E402
from engine import scalp_engine as se                      # noqa: E402
from strategies.s346_fast import (barrier_outcomes,        # noqa: E402
                                  select_non_overlap)
from strategies.s650_ehlers_explore import _atr_rma_nb     # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S655')
ASSET = 'XAUUSD'
SEED = 655655
PERM_K = 600
N_TRIALS = 34
SPLIT_FRAC = 0.70
RHO_MIN = 0.618
SL_K = 0.618          # × R
TP_K = 1.000          # × R
HOLD = 16
ORDER = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
         'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1')
TF_SEC = {'M1': 60, 'M3': 180, 'M4': 240, 'M5': 300, 'M6': 360, 'M10': 600,
          'M12': 720, 'M15': 900, 'M20': 1200, 'M30': 1800, 'H1': 3600,
          'H2': 7200, 'H3': 10800, 'H6': 21600, 'H8': 28800, 'H12': 43200,
          'D1': 86400}
CHUNK = 250_000
NULL_MAX = 400_000   # سقفِ استخرِ نول (ضدِ OOM؛ بذر و K تغییر نمی‌کنند)
NY = zoneinfo.ZoneInfo('America/New_York')


def release_instants_utc(t0_utc, t1_utc):
    """لحظه‌های انتشار (epoch seconds, UTC): اولین جمعهٔ هر ماه 08:30 NY؛ تعطیل ⇒ پنجشنبهٔ قبل."""
    hol = set(USFederalHolidayCalendar().holidays(
        start='2010-01-01', end='2027-12-31').date)
    p0 = pd.Timestamp(t0_utc, unit='s').to_period('M')
    p1 = pd.Timestamp(t1_utc, unit='s').to_period('M')
    out = []
    for m in pd.period_range(p0, p1, freq='M'):
        d = m.start_time.normalize()
        while d.weekday() != 4:
            d += pd.Timedelta(days=1)
        if d.date() in hol:
            d -= pd.Timedelta(days=1)
        rel = pd.Timestamp(d.year, d.month, d.day, 8, 30, tz=NY)
        out.append(int(rel.tz_convert('UTC').timestamp()))
    return np.asarray(out, dtype=np.int64)


def announcement_bars(times, tf):
    """اندیسِ کندل‌هایی که لحظهٔ انتشار درونِ [time, time+TF) آن‌هاست."""
    rel = release_instants_utc(int(times[0]), int(times[-1]))
    idx = np.searchsorted(times, rel, side='right') - 1
    ok = (idx >= 0)
    idx = idx[ok]
    rel = rel[ok]
    inside = (rel - times[idx]) < TF_SEC[tf]
    return np.unique(idx[inside]), len(rel)


def _barrier_compact(df, idx, flag, rng_bar, cfg):
    ebs, offs, wins = [], [], []
    for s0 in range(0, len(idx), CHUNK):
        part = idx[s0:s0 + CHUNK]
        R = rng_bar[part]
        fo = barrier_outcomes(df, part, np.full(len(part), flag),
                              SL_K * R, TP_K * R, HOLD,
                              float(cfg['pip']), float(cfg['spread_pip']),
                              float(cfg.get('slip_pip', 0.0)))
        ebs.append(fo['entry_bar'].astype(np.int64))
        offs.append(fo['exit_off'].astype(np.int16))
        wins.append(fo['win'].astype(bool))
    if not ebs:
        return None
    return (np.concatenate(ebs), np.concatenate(offs), np.concatenate(wins))


def build_null(df, rng_bar, valid, n_long, n_short, rng):
    cfg = se.ASSETS[ASSET]
    null = {}
    for side, flag, n_side in (('long', True, n_long),
                               ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) >= 2:
            fo = _barrier_compact(df, valid, flag, rng_bar, cfg)
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
    d = fd.load_fast(ASSET, tf)
    src = d['src']
    assert 'mt5_full' in src, f"E-16 TRAP! src={src}"
    df = fd.as_dataframe(d)
    times = d['time'].astype(np.int64)
    del d
    n = len(df)
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    rng_bar = h - l
    pip = se.ASSETS[ASSET]['pip']

    ann, n_rel = announcement_bars(times, tf)
    ann = ann[(ann + 1 + HOLD < n) & (ann >= 1)]
    print(f"\n{'='*88}\n=== S655 FINAL :: {ASSET} {tf} — bars={n:,} releases={n_rel} "
          f"announcement bars={len(ann)}\n    src={src}", flush=True)

    # P0 — blind sanity (before any PnL): R / ATR21[t-1]
    atr = _atr_rma_nb(h, l, c, 21)
    with np.errstate(invalid='ignore', divide='ignore'):
        ratio = rng_bar[ann] / atr[ann - 1]
    ratio = ratio[np.isfinite(ratio)]
    p0_med = float(np.median(ratio)) if len(ratio) else float('nan')
    print(f"    P0 median R/ATR21[t-1] = {p0_med:.3f}  (n={len(ratio)})", flush=True)

    body = c[ann] - o[ann]
    with np.errstate(invalid='ignore', divide='ignore'):
        rho = np.where(rng_bar[ann] > 0, np.abs(body) / np.where(rng_bar[ann] > 0, rng_bar[ann], 1.0), 0.0)
    valid = np.where(np.isfinite(rng_bar) & (rng_bar > 0))[0]
    valid = valid[(valid >= 200) & (valid + 1 + HOLD < n)]
    # ضدِ OOM (فقط حافظه، نه منطق): استخرِ نول با stride یکنواخت به ≤ NULL_MAX کندل
    # محدود می‌شود (M1 با ۵M کندل در ۹۸۵MB کشته شد — dmesg oom-kill pid 17392).
    if len(valid) > NULL_MAX:
        stride = int(np.ceil(len(valid) / NULL_MAX))
        valid = valid[::stride]
        print(f"    null pool subsampled: stride={stride} -> {len(valid):,} bars",
              flush=True)

    out = dict(layer='S655', tf=tf, asset=ASSET, src=src, n_bars=n,
               n_releases=n_rel, n_announcement_bars=int(len(ann)),
               p0_median_R_over_ATR21=round(p0_med, 4),
               geometry=dict(sl_k=SL_K, tp_k=TP_K, hold=HOLD, rho_min=RHO_MIN),
               seed=SEED, perm_k=PERM_K, n_trials=N_TRIALS, arms={})

    for arm in ('RHO', 'ALL'):
        sel = (rho >= RHO_MIN) if arm == 'RHO' else np.ones(len(ann), bool)
        sel &= (body != 0)
        idx = ann[sel]
        ls = np.zeros(n, bool)
        ss = np.zeros(n, bool)
        ls[idx[(c[idx] - o[idx]) > 0]] = True
        ss[idx[(c[idx] - o[idx]) < 0]] = True
        sl_pip_arr = SL_K * rng_bar / pip
        tp_pip_arr = TP_K * rng_bar / pip
        rec = dict(arm=arm, n_signals=int(len(idx)))
        if len(idx) < 5:
            rec.update(verdict='NO-TRADES (n<5)')
            out['arms'][arm] = rec
            print(f"    [{arm}] n_signals={len(idx)} — too few", flush=True)
            continue
        tr = se.simulate_trades(df, ls, ss, sl_pip_arr, tp_pip_arr, ASSET,
                                max_hold=HOLD, allow_overlap=False)
        if tr is None or len(tr) == 0:
            rec.update(verdict='NO-TRADES')
            out['arms'][arm] = rec
            continue
        n_long = int((tr['direction'] == 'long').sum())
        n_short = int((tr['direction'] == 'short').sum())
        wr = float((tr['outcome'] == 'win').mean() * 100.0)
        print(f"    [{arm}] trades n={len(tr)} (L={n_long}/S={n_short}) wr={wr:.2f}% "
              f"exp={tr['pnl_pip'].mean():.2f}pip", flush=True)
        rng = np.random.default_rng(SEED)
        null = build_null(df, rng_bar, valid, n_long, n_short, rng)
        med_sl = float(np.median(tr['sl_pip'].values))
        res = rqs2.compute_rqs2(
            tr, ASSET, sl_pip=med_sl, tp_pip=(TP_K / SL_K) * med_sl,
            bar_time=df['time'].values, close=c, null=null,
            n_trials=N_TRIALS, split_bar=int(SPLIT_FRAC * n))
        print(rqs2.format_rqs2(f'S655_{tf}_{arm}', res), flush=True)
        rec.update(n_trades=int(len(tr)), n_long=n_long, n_short=n_short,
                   verdict=res['verdict'], rqs2_score=res['rqs2_score'],
                   gates=res['gates'], metrics=res['metrics'], notes=res['notes'])
        out['arms'][arm] = rec
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def _save_push(tf, out):
    os.makedirs(OUT, exist_ok=True)
    fp = os.path.join(OUT, f'final_{tf}.json')
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"    ✔ saved {fp}", flush=True)
    v = out.get('arms', {}).get('RHO', {}).get('verdict', '?')
    try:
        subprocess.run(['git', 'add', 'results/_scan_S655'], cwd=ROOT,
                       check=True, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m',
             f"S655 FINAL {tf}: RHO={v} (full mt5_full, per PREREG e2315871)"],
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
    print(f"S655 FINAL — path A — per PREREG e2315871 — TFs: {tfs}", flush=True)
    for tf in tfs:
        fp = os.path.join(OUT, f'final_{tf}.json')
        if os.path.exists(fp):
            print(f"    ↷ {tf} already judged — skip.", flush=True)
            continue
        try:
            out = judge_tf(tf)
        except AssertionError:
            raise
        except Exception as e:                              # noqa: BLE001
            out = dict(layer='S655', tf=tf, verdict='ERROR', error=str(e))
            print(f"    ✖ {tf} ERROR: {e}", flush=True)
        _save_push(tf, out)
    print("\nS655 FINAL — DONE", flush=True)


if __name__ == '__main__':
    main()
