"""S770 — «ادامهٔ گسترشِ دامنه بر مقیاسِ ADR» روی XAUUSD.

پیش‌ثبت: results/S770_PREREG_ADR_RANGE_EXPANSION_XAUUSD.md (کامیت 98cd3919).
مسیر چندگانگی: C (holdout). جستجو فقط روی ۶۰٪ نخست؛ حداکثر یک داوری per کارت.

فازها:
  --phase explore --tf M15      : اسکن ۱۵ پیکربندی روی پنجرهٔ اکتشاف یک کارت
  --phase adjudicate --tf M15   : داوری RQS2 کامل بهترین پیکربندی (طبق معیار پیش‌ثبت)

ثابت‌های قفل‌شده (PREREG §۸):
  SEED=20260816 · K_PERM=800 · SPLIT_FRAC=0.60 · ADR_P=21 · ATR_P=100 ·
  SL_K=1.272 · RR=2.058 · N_TRIALS=285 · THETAS/HOLDS طبق §۵
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se           # noqa: E402
from engine import rqs2                          # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

SEED = 20260816
K_PERM = 800
SPLIT_FRAC = 0.60
ADR_P = 21
ATR_P = 100
SL_K = 1.272
RR = 2.058
N_TRIALS = 285
THETAS = (0.35, 0.50, 0.65, 0.80, 1.00)
HOLDS = (16, 32, 64)
SCAN_DIR = os.path.join(ROOT, 'results', '_scan_S770')
MIN_N_EXPLORE = 30   # زیر این، سلول «سیگنال‌کم» گزارش می‌شود (صادقانه، نه حذف)


def load_card(tf):
    """بارگذاری کارت با نگهبانِ E-16: اگر src از mt5_full نبود، توقف."""
    if tf == 'H4':
        d = fd.load_fast('XAUUSD', 'H1')
        _guard_src(d['src'], 'H1(resample→H4)')
        df = fd.as_dataframe(d)
        df = resample_h4(df)
        src = d['src'] + '  [resampled H1→H4]'
    else:
        d = fd.load_fast('XAUUSD', tf)
        _guard_src(d['src'], tf)
        df = fd.as_dataframe(d)
        src = d['src']
    return df, src


def _guard_src(src, tf):
    if 'mt5_full' not in src:
        raise SystemExit(f'[E-16 GUARD] src={src} برای {tf} از mt5_full نیست — توقف. '
                         f'ابتدا tools/s434_fetch_mt5_full.py --unpack را اجرا کن.')


def resample_h4(df_h1):
    t = pd.to_datetime(df_h1['time'], unit='s')
    g = df_h1.set_index(t).resample('4h')
    out = pd.DataFrame({
        'open': g['open'].first(), 'high': g['high'].max(),
        'low': g['low'].min(), 'close': g['close'].last(),
        'volume': g['volume'].sum(),
    }).dropna()
    out['time'] = (out.index.astype('int64') // 10**9)
    return out.reset_index(drop=True)


def atr_series(df, p=ATR_P):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(p).mean().values
    return atr


def build_features(df):
    """frac = (close − dayOpen)/ADR21 — همه علّی (shift به گذشته)."""
    t = pd.to_datetime(df['time'], unit='s')
    day = t.dt.normalize().values
    daily = df.groupby(day).agg(hi=('high', 'max'), lo=('low', 'min'),
                                op=('open', 'first'))
    daily['rng'] = daily['hi'] - daily['lo']
    daily['adr'] = daily['rng'].rolling(ADR_P).mean().shift(1)
    adr = daily['adr'].reindex(day).values
    dopen = daily['op'].reindex(day).values
    c = df['close'].values
    frac = np.where(adr > 0, (c - dopen) / adr, np.nan)
    return frac


def signals_for(frac, theta):
    prev = np.roll(frac, 1); prev[0] = np.nan
    with np.errstate(invalid='ignore'):
        long_sig = (prev < theta) & (frac >= theta)
        short_sig = (prev > -theta) & (frac <= -theta)
    long_sig = np.nan_to_num(long_sig).astype(bool)
    short_sig = np.nan_to_num(short_sig).astype(bool)
    return long_sig, short_sig


def geometry(df):
    atr = atr_series(df)
    pip = se.ASSETS['XAUUSD']['pip']
    sl_pip = SL_K * atr / pip
    tp_pip = RR * sl_pip
    return sl_pip, tp_pip, atr


def p0_for_rr(rr):
    """WR سربه‌سر هندسی (بدون هزینه) = 1/(1+RR) — فقط برای گزارش توان."""
    return 1.0 / (1.0 + rr)


def explore_card(tf):
    os.makedirs(SCAN_DIR, exist_ok=True)
    df, src = load_card(tf)
    print(f'[S770 explore] tf={tf} src={src} bars={len(df):,}', flush=True)
    split = int(len(df) * SPLIT_FRAC)
    dfe = df.iloc[:split].reset_index(drop=True)
    frac = build_features(dfe)
    sl_pip, tp_pip, atr = geometry(dfe)
    valid = np.isfinite(frac) & np.isfinite(sl_pip) & (sl_pip > 0)
    half = split // 2

    cells = []
    for theta in THETAS:
        lsig, ssig = signals_for(frac, theta)
        lsig &= valid; ssig &= valid
        for hold in HOLDS:
            tr = se.simulate_trades(dfe, lsig, ssig, sl_pip, tp_pip,
                                    asset='XAUUSD', max_hold=hold,
                                    allow_overlap=False)
            n = len(tr)
            cell = dict(tf=tf, theta=theta, hold=hold, n=int(n))
            if n < MIN_N_EXPLORE:
                cell.update(status='LOW_SIGNAL')
            else:
                wr = float((tr['pnl_pip'] > 0).mean() * 100)
                expn = float(tr['pnl_pip'].mean())
                e1 = tr[tr['entry_bar'] < half]['pnl_pip']
                e2 = tr[tr['entry_bar'] >= half]['pnl_pip']
                g1 = float(e1.mean()) if len(e1) else float('nan')
                g2 = float(e2.mean()) if len(e2) else float('nan')
                p0 = p0_for_rr(RR) * 100
                lift = wr - p0
                zproxy = lift * np.sqrt(n) / 100.0
                cell.update(status='OK', wr=round(wr, 2), exp_net=round(expn, 3),
                            g1=round(g1, 3), g2=round(g2, 3),
                            lift_pp=round(lift, 2), zproxy=round(zproxy, 3),
                            stable=bool(g1 > 0 and g2 > 0))
            cells.append(cell)
            print(f'  θ={theta} hold={hold}: {json.dumps(cell, ensure_ascii=False)}',
                  flush=True)

    # معیار پیش‌ثبت‌شده: بیشینهٔ zproxy مشروط به پایداری دو-نیمه‌ای exp_net>0
    ok = [c for c in cells if c.get('status') == 'OK' and c.get('stable')
          and c.get('exp_net', -1) > 0]
    best = max(ok, key=lambda c: c['zproxy']) if ok else None
    out = dict(card=f'XAUUSD_{tf}', src=src, bars=len(df), split=split,
               cells=cells, best=best)
    fp = os.path.join(SCAN_DIR, f'{tf}_explore.json')
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'[S770 explore] {tf} → best={json.dumps(best, ensure_ascii=False)} '
          f'saved={fp}', flush=True)
    return out


def build_null(df, valid_idx, sl_pip, tp_pip, n_long, n_short, hold, rng):
    """نول اندازه‌گیری‌شده: بی‌قید + جایگشت K=800 با همان هندسهٔ منجمد."""
    null = {}
    vi = valid_idx
    for side, n_side in (('long', n_long), ('short', n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(vi) >= 2:
            sig = np.zeros(len(df), dtype=bool); sig[vi] = True
            zero = np.zeros(len(df), dtype=bool)
            tr_all = se.simulate_trades(df, sig if side == 'long' else zero,
                                        zero if side == 'long' else sig,
                                        sl_pip, tp_pip, asset='XAUUSD',
                                        max_hold=hold, allow_overlap=True)
            if len(tr_all):
                d['uncond_wr'] = float((tr_all['pnl_pip'] > 0).mean() * 100)
            if len(vi) > n_side:
                wrs = []
                for _ in range(K_PERM):
                    pick = np.sort(rng.choice(len(vi), size=n_side, replace=False))
                    pb = vi[pick]
                    sig = np.zeros(len(df), dtype=bool); sig[pb] = True
                    tr_p = se.simulate_trades(df, sig if side == 'long' else zero,
                                              zero if side == 'long' else sig,
                                              sl_pip, tp_pip, asset='XAUUSD',
                                              max_hold=hold, allow_overlap=True)
                    if len(tr_p):
                        wrs.append(float((tr_p['pnl_pip'] > 0).mean() * 100))
                if wrs:
                    a = np.asarray(wrs)
                    d.update(perm_mean=float(a.mean()),
                             perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        print(f'    null {side}: {json.dumps(d, ensure_ascii=False)}', flush=True)
    return null


def adjudicate_card(tf):
    """داوری کامل RQS2 روی کل نمونه با پیکربندی برندهٔ اکتشاف (یک بار، مسیر C)."""
    fp = os.path.join(SCAN_DIR, f'{tf}_explore.json')
    with open(fp) as f:
        ex = json.load(f)
    best = ex.get('best')
    if not best:
        print(f'[S770 adjudicate] {tf}: هیچ سلول پایداری در اکتشاف نبود ⇒ '
              f'REJECT-by-rule بدون داوری (بدون بدهی H5).', flush=True)
        out = dict(card=f'XAUUSD_{tf}', verdict='REJECT_BY_RULE',
                   reason='no stable positive cell in exploration')
        with open(os.path.join(SCAN_DIR, f'{tf}_verdict.json'), 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return out

    theta, hold = best['theta'], best['hold']
    df, src = load_card(tf)
    print(f'[S770 adjudicate] tf={tf} θ={theta} hold={hold} src={src} '
          f'bars={len(df):,}', flush=True)
    split = int(len(df) * SPLIT_FRAC)
    frac = build_features(df)
    sl_pip, tp_pip, atr = geometry(df)
    valid = np.isfinite(frac) & np.isfinite(sl_pip) & (sl_pip > 0)
    lsig, ssig = signals_for(frac, theta)
    lsig &= valid; ssig &= valid

    tr = se.simulate_trades(df, lsig, ssig, sl_pip, tp_pip, asset='XAUUSD',
                            max_hold=hold, allow_overlap=False)
    n = len(tr)
    n_long = int((tr['direction'] == 'long').sum()) if n else 0
    n_short = n - n_long
    print(f'  full-sample trades n={n} (long={n_long}, short={n_short})', flush=True)

    rng = np.random.default_rng(SEED)
    vi = np.where(valid)[0]
    null = build_null(df, vi, sl_pip, tp_pip, n_long, n_short, hold, rng)

    bar_time = df['time'].values
    med_sl = float(np.nanmedian(sl_pip))
    med_tp = float(np.nanmedian(tp_pip))
    r = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=med_sl, tp_pip=med_tp,
                          bar_time=bar_time, null=null, n_trials=N_TRIALS,
                          split_bar=split, close=df['close'].values)
    out = dict(card=f'XAUUSD_{tf}', src=src, theta=theta, hold=hold, n=n,
               verdict=r['verdict'], score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=_safe(r.get('metrics', {})))
    with open(os.path.join(SCAN_DIR, f'{tf}_verdict.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S770 adjudicate] {tf} → verdict={r['verdict']} "
          f"score={r.get('rqs2_score')} p_perm={r.get('metrics',{}).get('skill_p_perm')}",
          flush=True)
    return out


def _safe(m):
    return {k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
            for k, v in m.items()}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['explore', 'adjudicate'], required=True)
    ap.add_argument('--tf', required=True)
    a = ap.parse_args()
    if a.phase == 'explore':
        explore_card(a.tf)
    else:
        adjudicate_card(a.tf)
