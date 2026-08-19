# -*- coding: utf-8 -*-
"""
S650 — آزمونِ نهایی روی نیمهٔ دومِ دست‌نخورده (مسیرِ C) — قفل‌شده طبق PREREG
=============================================================================
⛔ این اسکریپت طبقِ `research/S650_PREREG.md` (کامیت 6e47ccac) نوشته و **پیش از
اجرا** کامیت می‌شود. هیچ پارامتری این‌جا انتخاب نمی‌شود — همه از جدولِ منجمدِ
پیش‌ثبت خوانده می‌شوند. نیمهٔ دومِ هر TF **یک بار و فقط یک بار** لمس می‌شود.

روش:
  • دادهٔ آزمون = نیمهٔ دومِ data/mt5_full (سپرِ E-16 فعال).
  • معاملاتِ لایه با موتورِ **رسمی** `engine.scalp_engine.simulate_trades`
    (allow_overlap=False) — قانونِ داوری.
  • مدلِ صفرِ اندازه‌گیری‌شده: ورودِ بی‌قید روی همهٔ کندل‌های معتبرِ نیمهٔ دوم
    (سدِ برداری s346 که برابری‌اش با موتورِ رسمی اثبات شده) + K=600 زیرمجموعهٔ
    تصادفیِ هم‌اندازه با n هر سمت، بذرِ ثابت 650650 — الگوی s351_verdict.
  • داوری: `engine.rqs2.compute_rqs2` با هر ۵ ورودیِ اجباری:
    tp_pip، null(K≥500)، n_trials=17، split_bar=۷۰٪ نیمهٔ دوم، bar_time (+close).
  • چک‌پوینت: پس از هر TF، JSON + commit + push (قانونِ اندک‌اندک).

اجرا:  python3 strategies/s650_final_test.py [TF ...]
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
from strategies.s650_ehlers_explore import (               # noqa: E402
    _atr_rma_nb, _flex_nb, signals, parity_check,
    GEO_ATR_P, GEO_SL_K, GEO_RR, GEO_HOLD)
from tools import s434_fast_data as fd                     # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S650')
ASSET = 'XAUUSD'
SEED = 650650            # منجمد (PREREG)
PERM_K = 600             # منجمد (PREREG) — ≥ کفِ ۵۰۰
N_TRIALS = 17            # منجمد (PREREG) — ۱۷ آزمونِ hold-out، همه گزارش می‌شوند
SPLIT_FRAC = 0.70        # منجمد (PREREG) — قراردادِ H7

# جدولِ قفل‌شدهٔ PREREG — TF → (p_trend, p_reflex). تغییرش = نقضِ پیش‌ثبت.
LOCKED = {
    'M1': (55, 55), 'M3': (89, 55), 'M4': (89, 21), 'M5': (89, 21),
    'M6': (89, 21), 'M10': (89, 21), 'M12': (55, 21), 'M15': (55, 13),
    'M20': (89, 89), 'M30': (34, 34), 'H1': (89, 55), 'H2': (21, 13),
    'H3': (21, 21), 'H6': (34, 13), 'H8': (34, 13), 'H12': (55, 21),
    'D1': (34, 13),
}
ORDER = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
         'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1')


CHUNK = 250_000   # سقفِ رویداد در هر قطعه — فقط بهینه‌سازی حافظه، نه معنا


def _barrier_compact(df, idx, flag, atr, cfg):
    """سدِ دوطرفه برای همهٔ رویدادهای idx، قطعه‌قطعه (ضد OOM).

    خروجی فقط سه آرایهٔ فشرده: entry_bar(int64), exit_off(int16), win(bool).
    نتیجهٔ هر رویداد مستقل از بقیه است، پس قطعه‌بندی موبه‌مو همان نتیجهٔ
    محاسبهٔ یکجا را می‌دهد (استدلالِ رسمیِ سرصفحهٔ s346_fast).
    """
    ebs, offs, wins = [], [], []
    for s0 in range(0, len(idx), CHUNK):
        part = idx[s0:s0 + CHUNK]
        sl_dist = GEO_SL_K * atr[part]
        fo = barrier_outcomes(df, part, np.full(len(part), flag),
                              sl_dist, GEO_RR * sl_dist, GEO_HOLD,
                              float(cfg['pip']), float(cfg['spread_pip']),
                              float(cfg.get('slip_pip', 0.0)))
        ebs.append(fo['entry_bar'].astype(np.int64))
        offs.append(fo['exit_off'].astype(np.int16))
        wins.append(fo['win'].astype(bool))
    if not ebs:
        return None
    return (np.concatenate(ebs), np.concatenate(offs), np.concatenate(wins))


def build_null(df, atr, valid, n_long, n_short, rng):
    """مدلِ صفرِ اندازه‌گیری‌شده — ساختارِ کانونیِ RQS2 (الگوی s351).

    سدِ هر رویداد مستقل از صف است ⇒ یک بار (قطعه‌قطعه) محاسبه، سپس هر
    قرعه فقط زیرمجموعه می‌چیند و صفِ بی‌همپوشانی را اجرا می‌کند.
    """
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
    pt, pr = LOCKED[tf]
    d = fd.load_fast(ASSET, tf)
    src = d['src']
    assert 'mt5_full' in src, f"E-16 TRAP! src={src}"
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    # 🔓 نخستین و آخرین لمسِ نیمهٔ دوم — طبقِ PREREG
    df = df_full.iloc[half:].reset_index(drop=True)
    del df_full, d          # آزادسازی فوری حافظه (ضد OOM روی M1)
    close = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    atr = _atr_rma_nb(h, l, close, GEO_ATR_P)

    print(f"\n{'='*88}\n=== S650 FINAL :: {ASSET} {tf} — locked pt={pt} pr={pr} "
          f"| test=second half ({len(df):,} bars)\n    src={src}", flush=True)

    warmup = max(4 * 89, 4 * GEO_ATR_P, 300)
    ok = np.isfinite(atr) & (atr > 0)

    ls, ss = signals(close, pt, pr)
    ls &= ok
    ss &= ok
    ls[:warmup] = False
    ss[:warmup] = False

    sl_pip_arr = GEO_SL_K * atr / se.ASSETS[ASSET]['pip']
    tp_pip_arr = GEO_RR * sl_pip_arr

    # ---- معاملاتِ لایه با موتورِ رسمی (قانونِ داوری) ----
    tr = se.simulate_trades(df, ls, ss, sl_pip_arr, tp_pip_arr, ASSET,
                            max_hold=GEO_HOLD, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return dict(layer='S650', tf=tf, verdict='REJECT (no trades)',
                    locked=dict(p_trend=pt, p_reflex=pr), src=src)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int((tr['direction'] == 'short').sum())
    wr = float((tr['outcome'] == 'win').mean() * 100.0)
    print(f"    trades n={len(tr)} (L={n_long}/S={n_short}) wr={wr:.2f}% "
          f"exp={tr['pnl_pip'].mean():.2f}pip", flush=True)

    # ---- مدلِ صفرِ اندازه‌گیری‌شده (K=600، بذر 650650) ----
    valid = np.where(ok)[0]
    valid = valid[(valid >= warmup) & (valid + 1 + GEO_HOLD < len(df))]
    rng = np.random.default_rng(SEED)
    null = build_null(df, atr, valid, n_long, n_short, rng)

    # ---- داوریِ RQS2 v2.6 با هر ۵ ورودیِ اجباری ----
    med_sl = float(np.median(tr['sl_pip'].values))
    res = rqs2.compute_rqs2(
        tr, ASSET,
        sl_pip=med_sl, tp_pip=GEO_RR * med_sl,
        bar_time=df['time'].values, close=close,
        null=null, n_trials=N_TRIALS,
        split_bar=int(SPLIT_FRAC * len(df)))

    print(rqs2.format_rqs2(f'S650_{tf}', res), flush=True)

    out = dict(layer='S650', tf=tf, asset=ASSET, src=src,
               locked=dict(p_trend=pt, p_reflex=pr, atr_p=GEO_ATR_P,
                           sl_k=GEO_SL_K, rr=GEO_RR, hold=GEO_HOLD),
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
        subprocess.run(['git', 'add', 'results/_scan_S650'], cwd=ROOT,
                       check=True, capture_output=True)
        r = subprocess.run(
            ['git', 'commit', '-m',
             f"S650 FINAL {tf}: {out.get('verdict', '?')} "
             f"(hold-out second half, per PREREG 6e47ccac)"],
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
    print(f"S650 FINAL TEST — path C — locked per PREREG — TFs: {tfs}",
          flush=True)
    parity_check()
    for tf in tfs:
        fp = os.path.join(OUT, f'final_{tf}.json')
        if os.path.exists(fp):
            print(f"    ↷ {tf} already judged — hold-out touch limit! skip.",
                  flush=True)
            continue
        try:
            out = judge_tf(tf)
        except AssertionError:
            raise
        except Exception as e:                              # noqa: BLE001
            out = dict(layer='S650', tf=tf, verdict='ERROR', error=str(e))
            print(f"    ✖ {tf} ERROR: {e}", flush=True)
        _save_push(tf, out)
    print("\nS650 FINAL — DONE", flush=True)


if __name__ == '__main__':
    main()
