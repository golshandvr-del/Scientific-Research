# -*- coding: utf-8 -*-
"""
S840 — لایهٔ «شوک استانداردشدهٔ ARCH» به سبک رابرت انگل
=========================================================
پیش‌ثبت: results/S840_PREREG_engle_standardized_shock.md (کامیت faf6e27b)
مسیر تعدد: C (تأیید Holdout) — جستجو فقط روی نیمهٔ اول، یک آزمون منجمد روی نیمهٔ دوم.

ایده (Engle 1982): واریانس شرطی و خوشه‌ای است. σ²_t = λσ²_{t-1} + (1−λ)r²_{t-1}
(IGARCH بدون ثابت / RiskMetrics λ=0.94). z_t = r_t/σ_t «سورپرایز ARCH» است.
رویداد ورود: |z_t| ≥ z_thr روی کندل بسته‌شده؛ ورود در open کندل بعد.

سپرها:
  • تلهٔ E-16: لودر tools/s434_fast_data (mt5_full، ۱۵.۶ سال).
  • اشتباه #۸: tp = max(rr·sl, sl) — TP هرگز < SL.
  • اشتباه #۷: اعداد غیر-رند (شبکهٔ فیبوناچی).
  • نشتِ نگاه به آینده: سیگنال اکتشاف فقط sig < split − hold − 2.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                    # noqa: E402
from engine import rqs2                                  # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402
from strategies.s346_fast import barrier_outcomes, select_non_overlap  # noqa: E402

ASSET = 'XAUUSD'
OUT = 'results/_scan_S840'
SEED = 840

# ---------------- شبکهٔ پیش‌ثبت‌شده (منجمد — عیناً PREREG) ----------------
LAMBDA = 0.94                       # RiskMetrics — جستجو نمی‌شود
Z_GRID = (1.618, 2.058, 2.618)
MODES = ('fade', 'follow')
SLK_GRID = (1.0, 1.272, 1.618)
RR_GRID = (1.0, 1.272, 1.618)
ATR_P = 34                          # فیبوناچی — جستجو نمی‌شود
N_GRID = len(Z_GRID) * len(MODES) * len(SLK_GRID) * len(RR_GRID)   # = 54
MIN_N_IS = 30
SPLIT_FRAC = 0.50                   # مسیر C — نیمه/نیمه (پیش‌ثبت‌شده)
N_PERM = 800                        # ≥ 500 (الزام H3)
NULL_POOL_CAP = 300_000             # سقفِ محاسباتی استخر null (زیرنمونهٔ seeded)

TF_HOLD = {  # max_hold پیش‌ثبت‌شده بر حسب TF (فیبوناچی)
    'M1': 89, 'M3': 89, 'M4': 89, 'M5': 89, 'M6': 89,
    'M10': 55, 'M12': 55, 'M15': 55, 'M20': 55, 'M30': 55,
    'H1': 34, 'H2': 34, 'H3': 34, 'H6': 34, 'H8': 34, 'H12': 34,
    'D1': 21, 'W1': 13, 'MN1': 13,
}
ALL_TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
           'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']


def cost_pip(asset=ASSET):
    cfg = se.ASSETS[asset]
    return float(cfg['spread_pip']) + 2.0 * float(cfg.get('slip_pip', 0.0))


def atr_series(h, l, c, p=ATR_P):
    """ATR وایلدر — کاملاً علّی."""
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.full(len(tr), np.nan)
    if len(tr) <= p:
        return out
    acc = tr[:p].mean()
    out[p - 1] = acc
    a = 1.0 / p
    for i in range(p, len(tr)):
        acc = acc + a * (tr[i] - acc)
        out[i] = acc
    return out


def ewma_z(close, lam=LAMBDA):
    """بازدهِ استانداردشده z_t = r_t/σ_t با σ²_t = λσ²_{t-1}+(1−λ)r²_{t-1}.

    کاملاً علّی: σ²_t فقط از r_{t-1} و قبل‌تر ساخته می‌شود؛ z_t پس از بستن کندل t
    قابل‌محاسبه است و ورود در open کندل t+1 انجام می‌شود.
    """
    c = np.asarray(close, dtype=np.float64)
    r = np.zeros(len(c))
    with np.errstate(divide='ignore', invalid='ignore'):
        r[1:] = np.log(c[1:] / c[:-1])
    r[~np.isfinite(r)] = 0.0
    var = np.full(len(c), np.nan)
    k0 = min(50, len(c) - 1)
    if k0 < 5:
        return np.full(len(c), np.nan), r
    v = float(np.var(r[1:k0 + 1]))
    if v <= 0:
        v = 1e-12
    var[k0] = v
    for t in range(k0 + 1, len(c)):
        v = lam * v + (1.0 - lam) * r[t - 1] * r[t - 1]
        var[t] = v
    sd = np.sqrt(var)
    with np.errstate(divide='ignore', invalid='ignore'):
        z = np.where(sd > 0, r / sd, np.nan)
    return z, r


def signals_for(z, atr, z_thr, mode, warmup, lo=None, hi=None):
    """اندیس سیگنال‌ها + جهت. lo/hi بازهٔ مجاز اندیس (برای جداسازی IS)."""
    valid = np.isfinite(z) & np.isfinite(atr) & (atr > 0)
    up = valid & (z >= z_thr)
    dn = valid & (z <= -z_thr)
    if mode == 'fade':
        long_m, short_m = dn, up
    else:                                   # follow
        long_m, short_m = up, dn
    sig_m = long_m | short_m
    idx = np.where(sig_m)[0]
    idx = idx[idx >= warmup]
    if lo is not None:
        idx = idx[idx >= lo]
    if hi is not None:
        idx = idx[idx < hi]
    if len(idx) == 0:
        return idx, np.zeros(0, bool)
    return idx, long_m[idx]


def queue_frozen(df, sig, is_long, sl_dist, hold, rr):
    """سیم‌کشیِ s348.queue_rr — سپر اشتباه #۸ داخل tp."""
    cfg = se.ASSETS[ASSET]
    tp_dist = np.maximum(rr * sl_dist, sl_dist)
    fo = barrier_outcomes(df, sig, is_long, sl_dist, tp_dist, hold,
                          float(cfg['pip']), float(cfg['spread_pip']),
                          float(cfg.get('slip_pip', 0.0)))
    if len(fo['entry_bar']) == 0:
        return None
    keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
    pnl = fo['pnl_pip'][keep]
    if len(pnl) == 0:
        return None
    win = pnl > 0
    gl = float(-pnl[~win].sum())
    return dict(n=int(len(pnl)), wr=float(win.mean() * 100.0),
                exp=float(pnl.mean()),
                pf=float(pnl[win].sum() / gl) if gl > 0 else 999.0,
                pnl=pnl, win=win,
                entry_bar=fo['entry_bar'][keep],
                exit_bar=fo['entry_bar'][keep] + fo['exit_off'][keep],
                is_long=fo['is_long'][keep],
                sl_pip=fo['sl_pip'][keep], tp_pip=fo['tp_pip'][keep])


def discover_is(df, z, atr, split, warmup, hold, verbose=True):
    """جستجو فقط روی نیمهٔ اول. hi = split−hold−2 ⇒ صفر نشت به OOS."""
    c = cost_pip()
    hi = split - hold - 2
    rows = []
    for z_thr in Z_GRID:
        for mode in MODES:
            sig, isl = signals_for(z, atr, z_thr, mode, warmup, hi=hi)
            if len(sig) < MIN_N_IS:
                continue
            for slk in SLK_GRID:
                sl_dist = slk * atr[sig]
                for rr in RR_GRID:
                    st = queue_frozen(df, sig, isl, sl_dist, hold, rr)
                    if st is None or st['n'] < MIN_N_IS:
                        continue
                    sl_med = float(np.median(st['sl_pip']))
                    tp_med = float(np.median(st['tp_pip']))
                    be = 100.0 * (sl_med + 2.0 * c) / (sl_med + tp_med)
                    rows.append(dict(z_thr=z_thr, mode=mode, sl_k=slk, rr=rr,
                                     n=st['n'], wr=round(st['wr'], 2),
                                     exp=round(st['exp'], 4),
                                     pf=round(st['pf'], 3),
                                     sl_med=round(sl_med, 2),
                                     tp_med=round(tp_med, 2),
                                     be=round(be, 2),
                                     passes_be=bool(st['wr'] > be)))
    ok = [r for r in rows if r['passes_be']]
    best = max(ok, key=lambda r: r['exp']) if ok else None
    if verbose:
        print(f"    IS grid evaluated: {len(rows)}/{N_GRID} combos with n>=30 · "
              f"{len(ok)} pass robust-BE", flush=True)
        if best:
            print(f"    IS WINNER: z>={best['z_thr']} {best['mode']} "
                  f"sl_k={best['sl_k']} rr={best['rr']} → n={best['n']} "
                  f"WR={best['wr']}% exp={best['exp']:+.3f}pip", flush=True)
    return rows, best


def build_null_oos(df, atr, valid_oos, sl_k, rr, hold, n_long, n_short,
                   n_perm=N_PERM, verbose=True):
    """مبنای اندازه‌گیری‌شده روی استخر OOS (طبق PREREG §۴) به تفکیک سمت."""
    rng = np.random.default_rng(SEED)
    pool = valid_oos
    if len(pool) > NULL_POOL_CAP:
        pool = np.sort(rng.choice(pool, size=NULL_POOL_CAP, replace=False))
    null = {}
    for side, flag, n_side in (('long', True, n_long), ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(pool) >= 2:
            sl_all = sl_k * atr[pool]
            s_all = queue_frozen(df, pool, np.full(len(pool), flag), sl_all,
                                 hold, rr)
            if s_all:
                d['uncond_wr'] = s_all['wr']
            if len(pool) > n_side:
                wrs = []
                for _ in range(n_perm):
                    pick = np.sort(rng.choice(len(pool), size=n_side,
                                              replace=False))
                    s_p = queue_frozen(df, pool[pick], np.full(n_side, flag),
                                       sl_k * atr[pool[pick]], hold, rr)
                    if s_p:
                        wrs.append(s_p['wr'])
                if wrs:
                    a = np.asarray(wrs, dtype='float64')
                    d.update(perm_mean=float(a.mean()),
                             perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        if verbose:
            print(f"      null[{side:<5}] n_side={n_side} uncond={d['uncond_wr']} "
                  f"perm_mean={d['perm_mean']} sd={d['perm_sd']} "
                  f"k={d['perm_k']}", flush=True)
    return null


def trades_from_st(st):
    return pd.DataFrame(dict(
        pnl_pip=st['pnl'],
        outcome=np.where(st['win'], 'win', 'loss'),
        sl_pip=st['sl_pip'], tp_pip=st['tp_pip'],
        entry_bar=st['entry_bar'].astype(int),
        exit_bar=st['exit_bar'].astype(int),
        direction=np.where(st['is_long'], 'long', 'short'),
    ))


def _slim(r):
    keep = dict(verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
                gates={k: v for k, v in r.get('gates', {}).items()},
                notes=r.get('notes'))
    m = r.get('metrics', {})
    keep['metrics'] = {k: m[k] for k in m
                       if isinstance(m[k], (int, float, str, bool, type(None)))}
    return keep


def _save(tf, out):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"    checkpoint saved → {path}", flush=True)


def run_tf(tf, verbose=True):
    hold = TF_HOLD[tf]
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    warmup = 250 if n >= 5000 else max(60, n // 10)
    split = int(n * SPLIT_FRAC)
    c = cost_pip()

    print(f"\n{'=' * 88}\n=== S840 Engle-Shock :: {ASSET}-{tf} "
          f"(bars={n:,} src={d.get('src', '?')} span={d.get('span_years', '?')}y) ===",
          flush=True)
    print(f"    λ={LAMBDA} ATR_P={ATR_P} hold={hold} split@{split:,} (50%) "
          f"warmup={warmup} cost={c:.2f}pip grid={N_GRID}", flush=True)

    out = dict(tf=tf, asset=ASSET, bars=n, src=str(d.get('src')),
               span_years=d.get('span_years'), hold=hold, split_bar=split,
               warmup=warmup, grid=N_GRID)

    if n < warmup + 4 * hold + 100:
        out['verdict'] = 'INCOMPLETE'
        out['reason'] = 'TOO_SHORT'
        _save(tf, out)
        return out

    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr = atr_series(h, l, cl)
    z, _ = ewma_z(cl)

    # -------- مرحلهٔ ۱: جستجوی IS (نیمهٔ اول، بدون نشت) --------
    rows, best = discover_is(df, z, atr, split, warmup, hold, verbose)
    out['is_grid'] = rows
    if best is None:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'NO_IS_CANDIDATE (هیچ ترکیبی BE مستحکم را در IS پاس نکرد)'
        print(f"    → {tf}: UNPROVEN — no IS candidate; OOS untouched.", flush=True)
        _save(tf, out)
        return out
    out['is_winner'] = best

    # -------- مرحلهٔ ۲: آزمون منجمدِ یگانه روی کل داده (H7=OOS) --------
    sig, isl = signals_for(z, atr, best['z_thr'], best['mode'], warmup)
    st = queue_frozen(df, sig, isl, best['sl_k'] * atr[sig], hold, best['rr'])
    if st is None or st['n'] < 5:
        out['verdict'] = 'INCOMPLETE'
        out['reason'] = 'NO_TRADES_FULL'
        _save(tf, out)
        return out
    tr = trades_from_st(st)
    n_oos = int((tr['entry_bar'] >= split).sum())
    sl_med = float(np.median(tr['sl_pip']))
    tp_med = float(np.median(tr['tp_pip']))
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(len(tr) - n_long)
    print(f"    FULL frozen run: n={len(tr)} (L={n_long} S={n_short}) "
          f"n_OOS={n_oos} WR={st['wr']:.2f}% exp={st['exp']:+.3f}pip "
          f"SL={sl_med:.1f} TP={tp_med:.1f}", flush=True)

    # -------- مرحلهٔ ۳: null اندازه‌گیری‌شده از استخر OOS --------
    valid = np.where(np.isfinite(z) & np.isfinite(atr) & (atr > 0))[0]
    valid_oos = valid[(valid >= split) & (valid >= warmup)]
    print(f"    null pool (OOS) = {len(valid_oos):,} bars (cap {NULL_POOL_CAP:,}) "
          f"· {N_PERM} perms/side", flush=True)
    null = build_null_oos(df, atr, valid_oos, best['sl_k'], best['rr'], hold,
                          n_long, n_short, verbose=verbose)

    # -------- مرحلهٔ ۴: داوری RQS2 — رسمی (مسیر C: n_trials=1) + حساسیت --------
    bar_time = df['time'].values if 'time' in df.columns else None
    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                  null=null, split_bar=split, close=cl)
    res_official = rqs2.compute_rqs2(tr, ASSET, n_trials=1, **common)
    res_cons = rqs2.compute_rqs2(tr, ASSET, n_trials=N_GRID, **common)
    print(rqs2.format_rqs2(f'{tf} OFFICIAL(pathC) ', res_official), flush=True)
    print(rqs2.format_rqs2(f'{tf} SENS(n_t={N_GRID}) ', res_cons), flush=True)

    out['full'] = dict(n=len(tr), n_long=n_long, n_short=n_short, n_oos=n_oos,
                       wr=round(st['wr'], 2), exp=round(st['exp'], 4),
                       pf=round(st['pf'], 3), sl_med=round(sl_med, 2),
                       tp_med=round(tp_med, 2))
    out['null'] = null
    out['rqs2_official'] = _slim(res_official)
    out['rqs2_sensitivity'] = _slim(res_cons)
    out['verdict'] = res_official['verdict']
    out['rqs2_score'] = res_official.get('rqs2_score')
    _save(tf, out)
    print(f"    → {tf}: {out['verdict']} (score={out['rqs2_score']})", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else ALL_TFS
    for tf in tfs:
        run_tf(tf)
