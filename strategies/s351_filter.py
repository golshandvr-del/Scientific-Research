# -*- coding: utf-8 -*-
"""
S351 — کاوشِ فیلترِ رژیم برای «شکستِ ساختارِ لگ-متناسب» (LPSB)
================================================================================
فرضیهٔ علمی (پیش‌ثبت‌شده، پیش از دیدنِ نتیجه):
--------------------------------------------------------------------------------
    LPSB یک سیگنالِ **breakout** است. breakout فقط وقتی سودده است که بازار
    **پایدار/روندی** باشد (نه اره‌ای). پس یک دروازهٔ رژیم که فقط شکست‌های
    درونِ رژیمِ روندی را نگه دارد، باید lift و z را افزایش دهد.

پشتوانهٔ سند (docs/indicators/statistical.md):
    «H>0.55 ⇒ فقط لایهٔ breakout» — این عیناً برای LPSB نوشته شده.
    S332 روی M15 با ترکیبِ r2+hurst از مرگ نجات یافت (RQS+=91.2).

⛔ چرا این «نرم‌کردنِ معیار» نیست:
    ۱) آستانهٔ فیلتر **فقط روی ۶۰٪ اکتشاف** بهینه می‌شود؛ حکم روی ۴۰٪
       holdoutِ دست‌نخورده صادر می‌شود (H7 خودش این را می‌سنجد).
    ۲) هزینهٔ جست‌وجوی فیلتر در n_trials لحاظ می‌شود (بانک ≈ 301 بُعد).
    ۳) آستانه‌ها غیررند/فیبوناچی‌اند (ضدِ اشتباه #۷).
    ۴) هندسه همان منجمدِ S351 است؛ فقط دروازهٔ ورود اضافه می‌شود.

روش:
    برای هر (کارت × فیلتر × آستانه) روی ۶۰٪ اکتشاف lift را می‌سنجیم، بهترین
    آستانه را قفل می‌کنیم، سپس RQS2 کامل روی کلِ سری (با split=۶۰٪) با شمارشِ
    چندگانگیِ بدبینانه اجرا می‌شود. هر کارت جداگانه چک‌پوینت می‌شود.
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies.s348_rr_sweep import (queue_rr, trades_df,          # noqa: E402
                                      cost_pip, SPLIT_FRAC)
from strategies.s351_lpsb import (atr_series, lpsb_signals,         # noqa: E402
                                  CARDS, GEO_SL_K, GEO_RR, GEO_HOLD,
                                  ATR_P, SEED)
from strategies.s351_verdict import build_null_side, CENTRAL        # noqa: E402
from strategies import bank_filters as bf                           # noqa: E402

OUT = 'results/_scan_S351'

# ------------------ فیلترهای رژیمِ کاندیدا (پیش‌ثبت‌شده) ------------------
# هر فیلتر: (نام, تابعِ سازنده, آستانه‌های فیبوناچی/غیررند, جهتِ «نگه‌دار اگر ≥»)
# دوره‌ها فیبوناچی‌اند (۵۵، ۳۴، ۲۱) طبقِ اشتباهِ #۷.
FILTERS = {
    'hurst55':   (lambda df: bf.hurst(df, period=55),
                  (0.50, 0.52, 0.55, 0.58, 0.618), '>='),
    'r2_34':     (lambda df: bf.r2(df, period=34),
                  (0.236, 0.382, 0.5, 0.618, 0.786), '>='),
    'er_21':     (lambda df: bf.kaufman_er(df, period=21),
                  (0.20, 0.30, 0.382, 0.5, 0.618), '>='),
    'chop_21':   (lambda df: bf.chop(df, period=21),
                  (61.8, 50.0, 45.0, 38.2, 30.0), '<='),   # روند = chop پایین
}

# شمارشِ چندگانگیِ بدبینانه: فیلترها × آستانه‌ها × کارت
N_FILTER_SPACE = sum(len(v[1]) for v in FILTERS.values())   # کلِ (فیلتر,آستانه)
N_OFFICIAL = N_FILTER_SPACE * len(CARDS)                    # حکمِ بدبینانه


def apply_filter(vals, thr, direction):
    if direction == '>=':
        return vals >= thr
    return vals <= thr


def run_card(card, n_perm=200, verbose=True):
    asset, path = CARDS[card]
    if not os.path.exists(path):
        _save(card, dict(card=card, verdict='NO_DATA'))
        return
    df = se.load_data(path)
    n = len(df)
    atr = atr_series(df)
    close = df['close'].values.astype('float64')
    bar_time = df['dt'].values if 'dt' in df.columns else None
    warmup = max(4 * (2 * 13 + 1), 250)
    split = int(n * SPLIT_FRAC)
    c = cost_pip(asset)

    print(f"\n{'='*92}\n=== S351-FILTER :: {card} (bars={n:,}) "
          f"central L={CENTRAL['L']} f={CENTRAL['f']} ===", flush=True)
    print(f"    FROZEN geom sl_k={GEO_SL_K} rr={GEO_RR} hold={GEO_HOLD} · "
          f"cost={c:.2f}pip · N_official={N_OFFICIAL}", flush=True)

    if n < warmup + 100:
        _save(card, dict(card=card, asset=asset, bars=n, verdict='TOO_SHORT'))
        return

    # سیگنالِ خامِ عضوِ مرکزی
    ls, ss, _ = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=warmup)
    base_sel = (ls | ss) & np.isfinite(atr) & (atr > 0)
    base_sig = np.where(base_sel)[0]
    if len(base_sig) < 20:
        _save(card, dict(card=card, asset=asset, bars=n, verdict='NO_SIGNAL'))
        return

    # پیش‌محاسبهٔ همهٔ فیلترها یک‌بار
    filt_vals = {}
    for fname, (fn, thrs, dirn) in FILTERS.items():
        try:
            filt_vals[fname] = np.asarray(fn(df), dtype=float)
        except Exception as e:                                   # noqa: BLE001
            print(f"    !! filter {fname} failed: {e}", flush=True)

    # ---- مرحلهٔ اکتشاف: بهترین (فیلتر,آستانه) بر پایهٔ lift روی ۶۰٪ نخست ----
    def eval_combo(vals, thr, dirn, lo, hi):
        gate = apply_filter(vals, thr, dirn)
        sel = base_sel & gate
        sel[:max(lo, warmup)] = False
        if hi is not None:
            sel[hi:] = False
        sig = np.where(sel)[0]
        if len(sig) < 10:
            return None
        st = queue_rr(df, sig, ls[sig], GEO_SL_K * atr[sig],
                      asset, GEO_HOLD, GEO_RR)
        if st is None or st['n'] < 10:
            return None
        return st

    best = None
    for fname, (fn, thrs, dirn) in FILTERS.items():
        if fname not in filt_vals:
            continue
        vals = filt_vals[fname]
        for thr in thrs:
            st = eval_combo(vals, thr, dirn, warmup, split)   # فقط اکتشاف
            if st is None:
                continue
            # امتیازِ اکتشاف = امیدِ ریاضی (نه WR؛ ضدِ اشتباه #۸)
            score = st['exp']
            if best is None or score > best['score']:
                best = dict(fname=fname, thr=thr, dirn=dirn, score=score,
                            n_disc=st['n'], wr_disc=st['wr'], exp_disc=st['exp'])
        if verbose:
            print(f"    scanned {fname}", flush=True)

    if best is None:
        _save(card, dict(card=card, asset=asset, bars=n, verdict='NO_GATE'))
        return
    print(f"    BEST gate (discovery only): {best['fname']} "
          f"{best['dirn']} {best['thr']} · n_disc={best['n_disc']} "
          f"WR={best['wr_disc']:.2f}% exp={best['exp_disc']:+.2f}", flush=True)

    # ---- داوریِ کامل: همان دروازه روی کلِ سری، split در ۶۰٪ ----
    vals = filt_vals[best['fname']]
    gate = apply_filter(vals, best['thr'], best['dirn'])
    sel = base_sel & gate
    sel[:warmup] = False
    sig = np.where(sel)[0]
    st = queue_rr(df, sig, ls[sig], GEO_SL_K * atr[sig], asset,
                  GEO_HOLD, GEO_RR)
    if st is None or st['n'] < 5:
        _save(card, dict(card=card, asset=asset, bars=n, verdict='NO_TRADES'))
        return
    tr = trades_df(st)
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    rbe = rqs2.breakeven_wr_cost(sl_med, tp_med, 2.0 * c)
    print(f"    FILTERED n={st['n']} (L={nL} S={nS}) WR={st['wr']:.2f}% "
          f"exp={st['exp']:+.3f}pip PF={st['pf']:.3f} · robust BE={rbe:.1f}%",
          flush=True)

    # null با همان دروازه (استخرِ null فقط کندل‌های عبوردهنده از فیلتر)
    valid = np.where(np.isfinite(atr) & (atr > 0) & gate)[0]
    valid = valid[valid >= warmup]
    rng = np.random.default_rng(SEED)
    print(f"    null pool = {len(valid):,} gated bars · {n_perm} perms/side",
          flush=True)
    null = build_null_side(df, asset, valid, GEO_SL_K * atr, nL, nS,
                           n_perm, rng, verbose)

    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                  null=null, split_bar=split, close=close)
    res = {}
    for tag, nt in (('official', N_OFFICIAL), ('single', 1)):
        r = rqs2.compute_rqs2(tr, asset, n_trials=nt, **common)
        res[tag] = r
        print(rqs2.format_rqs2(f'{card} {tag:<8}', r), flush=True)

    out = dict(card=card, asset=asset, bars=n, cost_pip=c, split_bar=split,
               central=dict(CENTRAL),
               frozen=dict(sl_k=GEO_SL_K, rr=GEO_RR, hold=GEO_HOLD, atr_p=ATR_P),
               gate=dict(filter=best['fname'], thr=best['thr'],
                         dir=best['dirn']),
               n_official=N_OFFICIAL,
               realised=dict(n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'],
                             sl_pip=sl_med, tp_pip=tp_med,
                             rr_eff=tp_med/sl_med, robust_be=float(rbe),
                             n_long=nL, n_short=nS),
               verdict=res['official']['verdict'])
    for tag in ('official', 'single'):
        r = res[tag]
        out[f'rqs2_{tag}'] = {k: r[k] for k in
                              ('verdict', 'rqs2_score', 'gates', 'metrics',
                               'notes') if k in r}
    _save(card, out)


def _save(card, out):
    os.makedirs(OUT, exist_ok=True)
    p = f'{OUT}/{card}_filter.json'
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(f"    [checkpoint] {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cards', nargs='*', default=None)
    ap.add_argument('--n-perm', type=int, default=200)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    order = a.cards if a.cards else list(CARDS.keys())
    for card in order:
        if card not in CARDS:
            print(f"!! unknown card {card}", flush=True)
            continue
        try:
            run_card(card, n_perm=a.n_perm, verbose=not a.quiet)
        except Exception as e:                                   # noqa: BLE001
            import traceback
            print(f"!! {card} FAILED: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()


if __name__ == '__main__':
    main()
