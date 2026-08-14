#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S880 — جستجوی Path C روی **نیمهٔ اولِ** داده — Entropy Collapse → Structure Birth

پیش‌ثبت: results/S880_PREREG_EntropyCollapse_PathC.md (commit 874f0a59)

⚠️ این اسکریپت فقط نیمهٔ اولِ هر TF را می‌بیند. نیمهٔ دوم = hold-out، دست‌نخورده.

فضای جستجو (منجمد در پیش‌ثبت — ۷۲ پیکربندی در هر TF):
  p ∈ {21,34,55} · k ∈ {8,13} · a ∈ {1.2,1.6} · b ∈ {1.0,1.5} · hold ∈ {55,89,144}

انتخاب در هر TF: بیشترین lift×√n مشروط به WR > سربه‌سرِ هزینه‌دار و n ≥ 30.
چک‌پوینت: results/_scan_S880/XAUUSD_<TF>.json پس از هر TF.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, 'results', '_scan_S880')
os.makedirs(OUTDIR, exist_ok=True)

PIP = 0.1          # XAUUSD: 1 pip = $0.1/oz — اسپرد 0.33$ = 3.3 pip
SPREAD_PIP = 3.3

P_LIST = (21, 34, 55)
K_LIST = (8, 13)
A_LIST = (1.2, 1.6)
B_LIST = (1.0, 1.5)
HOLD_LIST = (55, 89, 144)

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']


def entropy_vec(close, p, bins=8, chunk=200_000):
    """آنتروپیِ شانونِ بازده — منطقِ عینِ بانک (indicator_bank.entropy)، برداری‌شده."""
    n = len(close)
    ret = np.zeros(n)
    ret[1:] = np.where(close[:-1] != 0, (close[1:] - close[:-1]) / close[:-1], 0.0)
    out = np.full(n, np.nan)
    # پنجرهٔ i شاملِ ret[i-p+1 .. i] — همان ایندکس‌گذاریِ بانک
    from numpy.lib.stride_tricks import sliding_window_view
    sw_all_start = p  # اولین ایندکسِ معتبرِ خروجی
    # sliding_window_view روی ret: پنجرهٔ j = ret[j..j+p-1] ⇒ خروجیِ i از پنجرهٔ i-p+1
    for c0 in range(sw_all_start, n, chunk):
        c1 = min(c0 + chunk, n)
        w = sliding_window_view(ret, p)[c0 - p + 1: c1 - p + 1]   # (m, p)
        mn = w.min(axis=1, keepdims=True)
        mx = w.max(axis=1, keepdims=True)
        rng = np.where((mx - mn) == 0, 1e-10, mx - mn)
        idx = np.minimum(bins - 1, ((w - mn) / rng * bins).astype(np.int64))
        m = idx.shape[0]
        flat = idx + (np.arange(m)[:, None] * bins)
        hist = np.bincount(flat.ravel(), minlength=m * bins).reshape(m, bins)
        pr = hist / p
        with np.errstate(divide='ignore', invalid='ignore'):
            term = np.where(pr > 0, pr * np.log2(pr), 0.0)
        out[c0:c1] = -term.sum(axis=1)
    return out


def atr_pip(high, low, close, p=89):
    """میانهٔ ATR(p) کلاسیک روی نیمهٔ اول → پیپ (هندسهٔ منجمدِ هر TF)."""
    tr = np.maximum(high[1:] - low[1:],
         np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    if len(tr) < p:
        return None
    k = np.ones(p) / p
    atr = np.convolve(tr, k, mode='valid')
    return float(np.median(atr)) / PIP


def build_events(E, close, p, k, q30, q70):
    """رویدادِ فروریزش + جهت از رانش — بدونِ نگاهِ جلو."""
    n = len(close)
    hi = E > q70
    run = np.zeros(n, dtype=bool)
    for j in range(1, k + 1):
        run[j:] |= hi[:-j]
    cross = (E < q30) & run
    edge = cross & ~np.concatenate(([False], cross[:-1]))
    drift = np.zeros(n)
    drift[p:] = close[p:] - close[:-p]
    long_sig = edge & (drift > 0)
    short_sig = edge & (drift < 0)
    return long_sig, short_sig


def wr_of(trades):
    """trades = DataFrameِ scalp_engine با ستونِ pnl_pip."""
    if trades is None or len(trades) == 0:
        return None, 0
    wins = int((trades['pnl_pip'] > 0).sum())
    return 100.0 * wins / len(trades), len(trades)


def uncond_wr(df, side, n_sig, sl_pip, tp_pip, hold, rng, draws=3):
    """WR بی‌قید: قرعه‌های تصادفیِ هم‌اندازه/هم‌هندسه (برآوردِ فازِ جستجو)."""
    n = len(df)
    lo, hi_i = 200, n - hold - 2
    if hi_i <= lo:
        return None
    wrs = []
    for _ in range(draws):
        pick = rng.choice(np.arange(lo, hi_i), size=min(n_sig, hi_i - lo), replace=False)
        sig = np.zeros(n, dtype=bool); sig[pick] = True
        z = np.zeros(n, dtype=bool)
        tr = se.simulate_trades(df, sig if side == 'long' else z,
                                z if side == 'long' else sig,
                                sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                max_hold=hold, allow_overlap=False)
        w, m = wr_of(tr)
        if w is not None:
            wrs.append(w)
    return float(np.mean(wrs)) if wrs else None


def scan_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    src = d['src']
    close_all = np.asarray(d['close'], float)
    n_all = len(close_all)
    half = n_all // 2
    df_all = fd.as_dataframe(d)
    df1 = df_all.iloc[:half].reset_index(drop=True)
    close = df1['close'].values
    high = df1['high'].values; low = df1['low'].values
    apip = atr_pip(high, low, close, 89)
    out = {'tf': tf, 'src': src, 'n_all': int(n_all), 'half_idx': int(half),
           'time_range_half': [int(df1['time'].iloc[0]), int(df1['time'].iloc[-1])],
           'atr89_median_pip': apip, 'configs': [], 'quantiles': {}}
    if apip is None or half < 500:
        out['skip'] = 'too few bars'
        return out

    rng = np.random.default_rng(880)
    # کشِ WR بی‌قید per (side, geometry, hold, ~n)
    ucache = {}

    for p in P_LIST:
        E = entropy_vec(close, p)
        v = E[~np.isnan(E)]
        if len(v) < 100:
            continue
        q30 = float(np.quantile(v, 0.30)); q70 = float(np.quantile(v, 0.70))
        out['quantiles'][f'p{p}'] = {'q30': q30, 'q70': q70}
        for k in K_LIST:
            ls, ss = build_events(E, close, p, k, q30, q70)
            nL, nS = int(ls.sum()), int(ss.sum())
            for a in A_LIST:
                sl = round(a * apip, 1)
                for b in B_LIST:
                    tp = round(b * sl, 1)
                    be = 100.0 * (sl + SPREAD_PIP) / (sl + tp)
                    for hold in HOLD_LIST:
                        tr = se.simulate_trades(df1, ls, ss, sl_pip=sl, tp_pip=tp,
                                                asset='XAUUSD', max_hold=hold,
                                                allow_overlap=False)
                        wr, n = wr_of(tr)
                        cfg = {'p': p, 'k': k, 'a': a, 'b': b, 'hold': hold,
                               'sl_pip': sl, 'tp_pip': tp, 'be_wr': round(be, 2),
                               'n': n, 'wr': None if wr is None else round(wr, 2),
                               'nL_sig': nL, 'nS_sig': nS}
                        if wr is not None and n >= 30:
                            # lift نسبت به WR بی‌قیدِ ترکیبی (وزن به نسبتِ معاملاتِ هر سمت)
                            nl_t = int((tr['direction'] == 'long').sum())
                            ns_t = n - nl_t
                            parts = []
                            for side, m in (('long', nl_t), ('short', ns_t)):
                                if m == 0:
                                    continue
                                key = (side, sl, tp, hold)
                                if key not in ucache:
                                    ucache[key] = uncond_wr(df1, side, max(m, 300),
                                                            sl, tp, hold, rng)
                                if ucache[key] is not None:
                                    parts.append((m, ucache[key]))
                            if parts:
                                uw = sum(m * w for m, w in parts) / sum(m for m, _ in parts)
                                cfg['uncond_wr'] = round(uw, 2)
                                cfg['lift'] = round(wr - uw, 2)
                                cfg['score'] = round((wr - uw) * np.sqrt(n), 1)
                        out['configs'].append(cfg)
    # انتخابِ نامزدِ TF طبق معیارِ منجمد
    valid = [c for c in out['configs']
             if c.get('lift') is not None and c['wr'] > c['be_wr'] and c['n'] >= 30
             and c['lift'] > 0]
    out['best'] = max(valid, key=lambda c: c['score']) if valid else None
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def main():
    only = sys.argv[1:] or TFS
    for tf in only:
        fp = os.path.join(OUTDIR, f'XAUUSD_{tf}.json')
        if os.path.exists(fp):
            print(tf, 'exists, skip'); continue
        try:
            res = scan_tf(tf)
        except FileNotFoundError as e:
            res = {'tf': tf, 'skip': str(e)}
        with open(fp, 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        b = res.get('best')
        print(tf, 'done', res.get('elapsed_s'), 's | best:',
              json.dumps(b, ensure_ascii=False) if b else 'None', flush=True)


if __name__ == '__main__':
    main()
