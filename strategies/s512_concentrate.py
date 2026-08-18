# -*- coding: utf-8 -*-
"""
S512 — تغلیظ لبهٔ M30 با یک شرط تأیید دوم
================================================================================
پیش‌ثبت: `results/S512_PREREG_M30_CONCENTRATION.md` (commit ab3f1996 — قبل از
هر آزمون). پایهٔ منجمد: برندهٔ M30 سرشماری S511 = atr_fib_55 cross↑q90 / LONG،
SL = 1.272×ATR100(میانهٔ کشف — همان کد S511)، RR = 2.058.

خانوادهٔ شرط دوم: هر ۱۶۶ ردیف واجد شرایط سرشماری M30 (منهای خود پایه).
تعریف فیلتر (حالت، نه گذر): ev==A ⇒ ind[t] > q90(کشف)؛ ev==B ⇒ ind[t] < q10(کشف).
سیگنال پایه در بار t نگه داشته می‌شود ⟺ شرط حالت در همان بار برقرار باشد.

انتخاب فقط روی پنجرهٔ کشف (۶۰٪ اول):
  معتبر ⟺ n_filtered≥40 ∧ retention∈[0.15,0.85] ∧
          exp_net_filtered > exp_net_base در هر دو نیمهٔ کشف ∧ WR_f > WR_base
  برنده = بیشترین بهبود WR میان معتبرها.

مراحل:  select → identity (K=1000، سد چندک95 — درس S437) → null → judge
داوری: حداکثر یک compute_rqs2 روی کل نمونه، n_trials=4978 (بدهی تجمعی 4812+166).

اجرا:  python3 strategies/s512_concentrate.py --stage select|identity|null|judge
"""
import sys
import os
import json
import glob
import time
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2 as R                                        # noqa: E402
from engine import indicator_bank as ib                             # noqa: E402
from tools.s434_fast_data import as_dataframe                       # noqa: E402
from strategies.s510_rr_lowtf_wpr import atr_np, simulate           # noqa: E402
from strategies.s511_gross_census import (                          # noqa: E402
    cross_above, load_card, SPLIT_FRAC, WARMUP, SL_K, RR,
    Q_LO, Q_HI, PIP, COST_PIP)
from strategies.s511_gross_census import OUT as OUT511              # noqa: E402

# ── ثابت‌های پیش‌ثبت‌شدهٔ S512 ──────────────────────────────────────────────
SEED = 20260818
MIN_N_DISC = 40
RET_LO, RET_HI = 0.15, 0.85
K_IDENTITY = 1000
K_PERM = 2000
N_TRIALS = 4978          # 4812 (S511) + 166 (S512)
TF = 'M30'
OUT = 'results/_scan_S512'

BASE = dict(ind='atr_fib_55', ev='A', side='long')   # منجمد از S511


# ── خانوادهٔ پیش‌ثبت‌شده: ردیف‌های واجد شرایط سرشماری M30 ─────────────────
def load_family():
    rows = []
    for f in sorted(glob.glob(f'{OUT511}/{TF}_*.json')):
        tag = os.path.basename(f).split(f'{TF}_')[1].replace('.json', '')
        if tag in ('summary', 'null', 'rqs2', 'overlap'):
            continue
        d = json.load(open(f))
        rr = d['rows'] if isinstance(d, dict) and 'rows' in d else d
        for r in rr:
            if not r.get('qualified'):
                continue
            if (r['ind'], r['ev']) == (BASE['ind'], BASE['ev']):
                continue                      # این‌همانی بدیهی — حذف
            rows.append(dict(ind=r['ind'], ev=r['ev'], side=r['side']))
    # یکتا بر حسب (ind, ev, side)
    seen, fam = set(), []
    for r in rows:
        k = (r['ind'], r['ev'], r['side'])
        if k not in seen:
            seen.add(k)
            fam.append(r)
    return fam


# ── ساخت زمینهٔ منجمد (داده، سیگنال پایه، هندسه) ──────────────────────────
def build_context():
    d = load_card(TF)
    n = d['n_bars']
    split = int(SPLIT_FRAC * n)
    half = split // 2
    df_full = as_dataframe({k: d[k] for k in
                            ('time', 'open', 'high', 'low', 'close', 'volume')})
    x = ib.compute(BASE['ind'], df_full).to_numpy()
    x[:WARMUP] = np.nan
    thr = float(np.nanquantile(x[:split], Q_HI))       # منجمد از کشف
    sig_bool = np.nan_to_num(cross_above(x, thr), nan=False).astype(bool)
    sig_bool[:WARMUP] = False
    a = atr_np(d['high'], d['low'], d['close'])
    sl_abs = float(np.nanmedian(a[:split])) * SL_K     # همان کد S511
    return dict(d=d, n=n, split=split, half=half, df_full=df_full,
                base_thr=thr, sig_bool=sig_bool, sl_abs=sl_abs)


def metrics(tr, half):
    """سنجه‌های کشف: exp_net کل و دو نیمه + WR."""
    if len(tr) == 0:
        return None
    pnl = tr['pnl_pip'].to_numpy()
    m1 = tr['entry_bar'].to_numpy() < half
    g1 = float(pnl[m1].mean()) if m1.any() else np.nan
    g2 = float(pnl[~m1].mean()) if (~m1).any() else np.nan
    return dict(n=len(tr),
                net=float(pnl.mean()) - COST_PIP,
                net1=(g1 - COST_PIP) if np.isfinite(g1) else None,
                net2=(g2 - COST_PIP) if np.isfinite(g2) else None,
                wr=100.0 * float((tr['outcome'] == 'win').mean()))


# ── مرحلهٔ ۱: انتخاب روی پنجرهٔ کشف ─────────────────────────────────────────
def stage_select():
    ctx = build_context()
    d, split, half = ctx['d'], ctx['split'], ctx['half']
    d_disc = {k: d[k][:split] for k in ('high', 'low', 'close')}
    df_disc = ctx['df_full'].iloc[:split]
    base_idx = np.flatnonzero(ctx['sig_bool'][:split])
    tr_base = simulate(d_disc, base_idx, ctx['sl_abs'], RR)
    mb = metrics(tr_base, half)
    print(f"[SELECT] base: n_sig={len(base_idx)} n_tr={mb['n']} "
          f"wr={mb['wr']:.2f}% net={mb['net']:+.3f} "
          f"(net1={mb['net1']:+.3f} net2={mb['net2']:+.3f})", flush=True)

    fam = load_family()
    print(f'[SELECT] family size = {len(fam)} (پیش‌ثبت: 166)', flush=True)

    rows, cache = [], {}
    t0 = time.time()
    for i, r in enumerate(fam):
        try:
            if r['ind'] not in cache:
                y = ib.compute(r['ind'], df_disc).to_numpy()
                y[:WARMUP] = np.nan
                cache[r['ind']] = y
            y = cache[r['ind']]
            q = float(np.nanquantile(y, Q_HI if r['ev'] == 'A' else Q_LO))
            cond = (y > q) if r['ev'] == 'A' else (y < q)
            cond = np.nan_to_num(cond, nan=False).astype(bool)
            keep = base_idx[cond[base_idx]]
            ret = len(keep) / max(len(base_idx), 1)
            row = dict(**r, thr=q, n_keep_sig=int(len(keep)),
                       retention=round(ret, 4))
            m = metrics(simulate(d_disc, keep, ctx['sl_abs'], RR), half) \
                if len(keep) else None
            if m:
                row.update(n=m['n'], wr=round(m['wr'], 2),
                           net=round(m['net'], 3),
                           net1=round(m['net1'], 3) if m['net1'] is not None else None,
                           net2=round(m['net2'], 3) if m['net2'] is not None else None)
                row['valid'] = bool(
                    m['n'] >= MIN_N_DISC
                    and RET_LO <= ret <= RET_HI
                    and m['net1'] is not None and m['net2'] is not None
                    and m['net1'] > mb['net1'] and m['net2'] > mb['net2']
                    and m['wr'] > mb['wr'])
                row['d_wr'] = round(m['wr'] - mb['wr'], 2)
            else:
                row.update(n=0, valid=False, d_wr=None)
            rows.append(row)
        except Exception as e:                              # noqa: BLE001
            rows.append(dict(**r, error=str(e)[:120], valid=False, d_wr=None))
        if (i + 1) % 40 == 0:
            print(f'  {i+1}/{len(fam)}  ({time.time()-t0:.0f}s)', flush=True)

    valid = [r for r in rows if r.get('valid')]
    valid.sort(key=lambda r: -r['d_wr'])
    winner = valid[0] if valid else None
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/select.json', 'w') as f:
        json.dump(dict(base=BASE, base_thr=ctx['base_thr'],
                       sl_abs=ctx['sl_abs'], split=split,
                       base_metrics=mb, n_family=len(fam),
                       n_valid=len(valid), winner=winner, rows=rows,
                       seed=SEED), f, ensure_ascii=False)
    print(f'[SELECT] valid={len(valid)}', flush=True)
    if winner:
        print(f"[SELECT] WINNER: {winner['ind']} {winner['ev']} "
              f"ret={winner['retention']} n={winner['n']} "
              f"wr={winner['wr']}% (base {mb['wr']:.2f}%) "
              f"d_wr=+{winner['d_wr']}pp net={winner['net']}", flush=True)
    else:
        print('[SELECT] هیچ نامزد معتبری نیست ⇒ REJECT-by-rule', flush=True)
    print(f'saved -> {OUT}/select.json')


# ── مرحلهٔ ۲: آزمون عملیات-همانی (درس S437) ────────────────────────────────
def stage_identity():
    with open(f'{OUT}/select.json') as f:
        S = json.load(f)
    w = S['winner']
    if not w:
        raise SystemExit('no winner — identity test موضوعیت ندارد')
    ctx = build_context()
    d, split, half = ctx['d'], ctx['split'], ctx['half']
    d_disc = {k: d[k][:split] for k in ('high', 'low', 'close')}
    base_idx = np.flatnonzero(ctx['sig_bool'][:split])
    k_keep = int(w['n_keep_sig'])

    rng = np.random.default_rng(SEED)
    wrs = []
    for k in range(K_IDENTITY):
        sub = np.sort(rng.choice(base_idx, size=k_keep, replace=False))
        t = simulate(d_disc, sub, ctx['sl_abs'], RR)
        if len(t) >= 10:
            wrs.append(100.0 * float((t['outcome'] == 'win').mean()))
        if (k + 1) % 200 == 0:
            print(f'  identity {k+1}/{K_IDENTITY}', flush=True)
    arr = np.asarray(wrs, float)
    p95 = float(np.percentile(arr, 95))
    obs = float(w['wr'])
    passed = bool(obs > p95)
    print(f"[IDENTITY] winner wr={obs:.2f}%  random-removal: "
          f"mean={arr.mean():.2f} p95={p95:.2f} max={arr.max():.2f} "
          f"k={len(arr)}  ->  {'PASS' if passed else 'FAIL'}", flush=True)
    with open(f'{OUT}/identity.json', 'w') as f:
        json.dump(dict(winner=w, obs_wr=obs, p95=p95,
                       mean=float(arr.mean()), max=float(arr.max()),
                       k=len(arr), passed=passed, seed=SEED),
                  f, ensure_ascii=False)
    print(f'saved -> {OUT}/identity.json')


# ── سیگنال نهایی روی کل نمونه (پایه ∧ فیلتر، آستانه‌ها منجمد از کشف) ───────
def full_filtered_signals(ctx, w):
    y = ib.compute(w['ind'], ctx['df_full']).to_numpy()
    y[:WARMUP] = np.nan
    split = ctx['split']
    q = float(np.nanquantile(y[:split], Q_HI if w['ev'] == 'A' else Q_LO))
    cond = (y > q) if w['ev'] == 'A' else (y < q)
    cond = np.nan_to_num(cond, nan=False).astype(bool)
    keep = ctx['sig_bool'] & cond
    return np.flatnonzero(keep), q


# ── مرحلهٔ ۳: مدل صفر (پروتکل S382/S510/S511) ──────────────────────────────
def stage_null():
    with open(f'{OUT}/identity.json') as f:
        ident = json.load(f)
    if not ident['passed']:
        raise SystemExit('identity FAIL — طبق پیش‌ثبت، داوری ممنوع است')
    w = ident['winner']
    ctx = build_context()
    d, n = ctx['d'], ctx['n']
    sig_idx, q_full = full_filtered_signals(ctx, w)
    tr = simulate(d, sig_idx, ctx['sl_abs'], RR)
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f"[NULL] filtered: n_sig={len(sig_idx)} n_tr={len(tr)} "
          f"wr={obs_wr:.2f}%", flush=True)

    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.arange(WARMUP, n - 2, stride, dtype=np.int64)
        t0 = simulate(d, idx, ctx['sl_abs'], RR)
        wr0 = 100.0 * float((t0['outcome'] == 'win').mean()) if len(t0) else None
        uncond_rows.append((stride, wr0, len(t0)))
        print(f'  uncond stride={stride}: n={len(t0)} wr={wr0:.2f}%', flush=True)
    uncond_wr = max(r[1] for r in uncond_rows if r[1] is not None)

    rng = np.random.default_rng(SEED)
    space = np.arange(WARMUP, n - 2, dtype=np.int64)
    wrs = []
    for k in range(K_PERM):
        pos = np.sort(rng.choice(space, size=min(len(sig_idx), len(space)),
                                 replace=False))
        tp_ = simulate(d, pos, ctx['sl_abs'], RR)
        if len(tp_) >= 30:
            wrs.append(100.0 * float((tp_['outcome'] == 'win').mean()))
        if (k + 1) % 400 == 0:
            print(f'  perm {k+1}/{K_PERM}', flush=True)
    arr = np.asarray(wrs, float)
    perm = dict(mean=float(arr.mean()), sd=float(arr.std(ddof=1)),
                max=float(arr.max()), k=int(len(arr)))
    z = (obs_wr - perm['mean']) / perm['sd'] if perm['sd'] > 0 else float('nan')
    print(f"  perm: mean={perm['mean']:.2f} sd={perm['sd']:.2f} "
          f"max={perm['max']:.2f}  ->  z={z:.2f}", flush=True)

    side_null = dict(uncond_wr=uncond_wr, perm_mean=perm['mean'],
                     perm_sd=perm['sd'], perm_max=perm['max'],
                     perm_k=perm['k'])
    empty = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
    with open(f'{OUT}/null.json', 'w') as f:
        json.dump(dict(winner=w, thr_full=q_full, obs_wr=obs_wr,
                       n_trades=len(tr), sl_abs=ctx['sl_abs'],
                       uncond=uncond_rows, perm=perm,
                       null={'long': side_null, 'short': empty},
                       seed=SEED, k=K_PERM, z_preview=z),
                  f, ensure_ascii=False)
    print(f'saved -> {OUT}/null.json')


# ── مرحلهٔ ۴: داوری رسمی — تنها فراخوان compute_rqs2 ───────────────────────
def stage_judge():
    with open(f'{OUT}/null.json') as f:
        nm = json.load(f)
    w = nm['winner']
    ctx = build_context()
    d, split = ctx['d'], ctx['split']
    sig_idx, _ = full_filtered_signals(ctx, w)
    sl_abs = float(nm['sl_abs'])
    tr = simulate(d, sig_idx, sl_abs, RR)

    res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_abs / PIP,
                         tp_pip=RR * sl_abs / PIP,
                         bar_time=d['time'], close=d['close'],
                         null=nm['null'], n_trials=N_TRIALS, split_bar=split)
    tag = f"S512_M30_atr_fib_55+{w['ind']}_{w['ev']}"
    print(R.format_rqs2(tag, res))
    with open(f'{OUT}/rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/trades.csv', index=False)
    print(f'saved -> {OUT}/rqs2.json + trades.csv')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True,
                    choices=['select', 'identity', 'null', 'judge'])
    args = ap.parse_args()
    {'select': stage_select, 'identity': stage_identity,
     'null': stage_null, 'judge': stage_judge}[args.stage]()
