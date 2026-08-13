# -*- coding: utf-8 -*-
"""
s680_lagsat_explore.py — اکتشافِ S680 «LAGSAT» فقط روی **نیمهٔ اول** (مسیرِ C)
================================================================================

پیش‌ثبت: results/S680_PREREG_LAGSAT_SATURATION_DURATION.md (کامیتِ a43a26af،
پیش از اجرای این فایل).

فرضیه: ماندنِ laguerre_rsi(γ) به مدتِ D کندلِ پیاپی در ناحیهٔ اشباع =
پایداریِ مومنتوم ⇒ ورودِ **هم‌جهت با اشباع** در کندلِ گذرِ شمارنده از D.

گریدِ قفل‌شده (دقیقاً همان پیش‌ثبت — ۴۰۵ سلول per کارت):
  γ از دوره‌های لوکاس  per ∈ {4,7,11,18,29,47,76,123,199} → γ=1−2/(per+1)   (۹)
  D  ∈ {3,5,8,13,21}                                                        (۵)
  hi ∈ {76,82,89}  (lo = 100−hi)                                            (۳)
  RR ∈ {1.0,1.5,2.0}                                                        (۳)

هندسه (قفل، جست‌وجو نمی‌شود): SL = 1.618 × میانهٔ ATR34ِ نیمهٔ اول (پیپِ
غیررند)، TP = RR×SL — هرگز TP<SL. max_hold per-TF از جدولِ پیش‌ثبت.

گاردها:
  BUG-PIPGUESS  — pip/spread از ASSETS موتور خوانده می‌شود.
  BUG-GEOMDRIFT — هندسهٔ هر کارت در JSONِ خروجی ذخیره می‌شود؛ داورِ نهایی
                  از همین JSON می‌خوانَد، بازمحاسبه نمی‌کند.
  ضدنشتی        — سیگنال روی closeِ کندلِ i؛ موتور در openِ i+1 وارد می‌شود.
  مسیرِ C       — این فایل فقط df.iloc[:n//2] را می‌بیند. نیمهٔ دوم دست‌نخورده.

خروجی: results/_s680_explore/explore_<TF>.json (هر کارت بلافاصله ذخیره).
هیچ حکمی اینجا صادر نمی‌شود — فقط غربالِ نامزد برای داوریِ یگانهٔ نهایی.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se           # noqa: E402
from engine.indicator_bank import _laguerre_levels  # noqa: E402
from tools import s434_fast_data as fd          # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s680_explore')

# ── گریدِ پیش‌ثبت‌شده — دست نزن ─────────────────────────────────────────────
LUCAS_PERS = [4, 7, 11, 18, 29, 47, 76, 123, 199]
GAMMAS = [(p, 1.0 - 2.0 / (p + 1)) for p in LUCAS_PERS]
DURS = [3, 5, 8, 13, 21]
HIS = [76.0, 82.0, 89.0]
RRS = [1.0, 1.5, 2.0]
SL_MULT = 1.618          # قفل — بُعدِ جست‌وجو نیست
ATR_PER = 34             # قفل — غیررند (فیبوناچی)

MAX_HOLD = {'M1': 34, 'M3': 34, 'M4': 34, 'M5': 34,
            'M6': 21, 'M10': 21, 'M12': 21, 'M15': 21, 'M20': 21, 'M30': 21,
            'H1': 13, 'H2': 13, 'H3': 13, 'H4': 13,
            'H6': 13, 'H8': 13, 'H12': 13,
            'D1': 8, 'W1': 8, 'MN1': 5}


def atr_pips(df: pd.DataFrame, asset: str, per: int = ATR_PER) -> pd.Series:
    cfg = se.ASSETS[asset]
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(per).mean() / cfg['pip']


def runlen_true(mask: np.ndarray) -> np.ndarray:
    """طولِ دنبالهٔ Trueِ منتهی به هر اندیس (۰ اگر False)."""
    n = len(mask)
    out = np.zeros(n, dtype=np.int64)
    run = 0
    for i in range(n):
        run = run + 1 if mask[i] else 0
        out[i] = run
    return out


def explore_card(asset: str, tf: str, verbose: bool = True) -> dict:
    t0 = time.time()
    d = fd.load_fast(asset, tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)   # ← فقط نیمهٔ اول
    n = len(df)

    cfg = se.ASSETS[asset]
    cost = cfg['spread_pip'] + 2.0 * cfg['slip_pip']
    mh = MAX_HOLD[tf]

    # هندسهٔ قفل‌شده از نیمهٔ اول
    med_atr = float(atr_pips(df, asset).median())
    sl = round(SL_MULT * med_atr, 1)
    if sl <= 0 or not np.isfinite(sl):
        raise ValueError(f'{tf}: SL نامعتبر ({sl})')

    if verbose:
        print(f'[{asset}-{tf}] src={d["src"]} n_full={n_full:,} half={n:,} '
              f'medATR{ATR_PER}={med_atr:.2f}pip SL={sl} mh={mh} '
              f'cost={cost:.2f}pip', flush=True)

    cells = []
    close_only = df[['close']]
    for per, g in GAMMAS:
        L0, L1, L2, L3 = _laguerre_levels(df['close'].values.astype(np.float64), g)
        cu = np.zeros_like(L0); cd = np.zeros_like(L0)
        for a, b in ((L0, L1), (L1, L2), (L2, L3)):
            up = a >= b
            cu += np.where(up, a - b, 0.0)
            cd += np.where(~up, b - a, 0.0)
        tot = cu + cd
        lrsi = np.where(tot != 0, 100.0 * cu / tot, 50.0)

        for hi in HIS:
            lo = 100.0 - hi
            r_above = runlen_true(lrsi > hi)
            r_below = runlen_true(lrsi < lo)
            for D in DURS:
                # لبهٔ گذر: شمارنده دقیقاً به D می‌رسد (یک شلیک per دنباله)
                long_sig = r_above == D
                short_sig = r_below == D
                n_sig = int(long_sig.sum() + short_sig.sum())
                if n_sig < 30:
                    for rr in RRS:
                        cells.append(dict(per=per, g=round(g, 4), hi=hi, D=D,
                                          rr=rr, n=n_sig, skipped='n_sig<30'))
                    continue
                for rr in RRS:
                    tp = round(rr * sl, 1)
                    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp,
                                            asset, max_hold=mh,
                                            allow_overlap=False)
                    if tr is None or len(tr) == 0:
                        cells.append(dict(per=per, g=round(g, 4), hi=hi, D=D,
                                          rr=rr, n=0, skipped='no_trades'))
                        continue
                    pnl = tr['pnl_pip'].values
                    ntr = len(pnl)
                    wr = 100.0 * float((pnl > 0).sum()) / ntr
                    be = 100.0 * (sl + cost) / (sl + tp)   # WR سربه‌سرِ هزینه‌دار
                    lift_be = wr - be
                    exp_pip = float(pnl.mean())
                    nL = int((tr['direction'] == 'long').sum()) \
                        if 'direction' in tr.columns else -1
                    cells.append(dict(per=per, g=round(g, 4), hi=hi, D=D,
                                      rr=rr, n=ntr, n_long=nL, wr=round(wr, 2),
                                      be_wr=round(be, 2),
                                      lift_be=round(lift_be, 2),
                                      exp_pip=round(exp_pip, 3),
                                      z_screen=round(
                                          (wr - be) / 100.0
                                          * np.sqrt(ntr)
                                          / np.sqrt(be / 100 * (1 - be / 100)),
                                          2)))
        if verbose:
            done = sum(1 for c in cells if 'skipped' not in c)
            print(f'  γ(per={per}) تمام شد — سلولِ معتبر تاکنون: {done} '
                  f'({time.time() - t0:.0f}s)', flush=True)

    out = dict(asset=asset, tf=tf, src=d['src'], n_full=n_full, n_half=n,
               half_span=[str(df["time"].iloc[0]), str(df["time"].iloc[-1])],
               sl_pip=sl, atr_per=ATR_PER, sl_mult=SL_MULT, max_hold=mh,
               cost_pip=cost, grid_cells=len(cells), cells=cells,
               elapsed_s=round(time.time() - t0, 1))
    os.makedirs(OUT_DIR, exist_ok=True)
    fp = os.path.join(OUT_DIR, f'explore_{tf}.json')
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    ok = [c for c in cells if 'skipped' not in c and c['n'] >= 30]
    ok.sort(key=lambda c: c['z_screen'], reverse=True)
    if verbose:
        print(f'\n═══ {asset}-{tf}: {len(ok)} سلولِ معتبر — ۱۰ صدرِ z_screen ═══')
        for c in ok[:10]:
            print(f"  per={c['per']:>3} hi={c['hi']:.0f} D={c['D']:>2} "
                  f"rr={c['rr']} n={c['n']:>5} wr={c['wr']:.1f}% "
                  f"be={c['be_wr']:.1f}% lift={c['lift_be']:+.1f}pp "
                  f"z={c['z_screen']:+.2f} exp={c['exp_pip']:+.2f}pip",
                  flush=True)
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tfs', default='M1')
    a = ap.parse_args()
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            explore_card(a.asset, tf)
        except Exception as e:  # noqa: BLE001
            print(f'!! {a.asset}-{tf}: {type(e).__name__}: {e}', flush=True)
    print('\n[explore done]', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
