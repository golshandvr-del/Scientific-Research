#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S870 — «گذر از سطوحِ رُندِ روانیِ طلا» (Round-Level Cross) · XAUUSD چند-TF
پیاده‌سازیِ دقیقِ پیش‌ثبتِ results/S870_PREREG_V2_ROUND_LEVEL_CROSS.md

قرارداد (منجمد):
  رویداد   : تغییرِ سلولِ floor(close/step) بینِ دو کندلِ متوالی (close-به-close)
  debounce : هر سطحِ مشخص حداکثر یک رویداد در ۲۴ ساعت (اولین گذر می‌بَرد)
  ورود     : openِ کندلِ بعد (علّی)
  گونه‌ها  : step ∈ {25,50,100} × جهت ∈ {follow,fade} = ۶ (n_trials=6)
  هندسه    : SL = 1.5×ATR(100) لحظهٔ ورود (آرایه‌ای) · TP = 1.5×SL · هرگز TP<SL
  max_hold : ساختاری ≈ ۲ روزِ معاملاتی per-TF
  مسیرِ C  : جست‌وجو فقط در نیمهٔ اولِ میله‌ها؛ داوری روی کل با split_bar
  null     : جای‌گشتِ جهتِ رویدادها، K=1000، همان هندسه/کندل‌ها (صفرِ هندسی)
  SEED=20260814
"""
import os, sys, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import rqs2 as R
from tools import s434_fast_data as fd

SEED = 20260814
K_PERM = 1000
N_TRIALS = 6
STEPS = [25.0, 50.0, 100.0]
LOGICS = ['follow', 'fade']
ATR_P = 100
SL_K = 1.5
RR = 1.5
ASSET = 'XAUUSD'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s870')

# max_hold ساختاری ≈ ۲ روزِ معاملاتی (پیش‌ثبت §۴)
MAX_HOLD = {'M1': 2880, 'M3': 960, 'M4': 720, 'M5': 576, 'M6': 480,
            'M10': 288, 'M12': 240, 'M15': 192, 'M20': 144, 'M30': 96,
            'H1': 48, 'H2': 24, 'H3': 16, 'H4': 12, 'H6': 8, 'H8': 6,
            'H12': 4, 'D1': 3, 'W1': 2, 'MN1': 2}

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']


def atr(df, p=ATR_P):
    h = df['high'].astype(float); l = df['low'].astype(float)
    c = df['close'].astype(float); pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def load_tf(tf):
    """H4 و سایرِ TFهای غایب: resample از H1 (دستورِ راهنما)."""
    try:
        d = fd.load_fast(ASSET, tf)
        return fd.as_dataframe(d), d.get('src')
    except Exception:
        if tf == 'H4':
            d = fd.load_fast(ASSET, 'H1')
            df = fd.as_dataframe(d)
            t = pd.to_datetime(df['time'], unit='s')
            g = df.set_index(t).resample('4h').agg(
                open=('open', 'first'), high=('high', 'max'),
                low=('low', 'min'), close=('close', 'last')).dropna()
            g['time'] = g.index.astype('int64') // 10**9
            return g.reset_index(drop=True), d.get('src') + ' [resampled H1->H4]'
        raise


def detect_events(close, tsec, step):
    """رویدادِ گذرِ تثبیت‌شده + debounce ۲۴ساعته per-level. خروجی:
    idx رویداد (اندیسِ کندلِ رویداد)، جهتِ گذر (+1/−1)."""
    cell = np.floor(close / step)
    d = np.diff(cell)
    raw = np.nonzero(d != 0)[0] + 1          # اندیسِ کندلی که سلولش عوض شد
    dirs = np.sign(d[raw - 1]).astype(int)
    # debounce: کلید = سطحِ گذرشده (سلولِ مقصد در up، سلولِ مبدأ در down ⇒
    # سطحِ فیزیکیِ یکسان). سطحِ گذرشده = max(cell_prev, cell_now) پایین‌مرز.
    lev = np.where(dirs > 0, cell[raw], cell[raw - 1])
    last_t = {}
    keep = np.zeros(len(raw), dtype=bool)
    for i, (ix, lv) in enumerate(zip(raw, lev)):
        key = float(lv)
        t = tsec[ix]
        if key not in last_t or (t - last_t[key]) >= 86400:
            keep[i] = True
            last_t[key] = t
    return raw[keep], dirs[keep]


def build_signals(n, ev_idx, ev_dir, logic):
    """ورود در openِ کندلِ بعد ⇒ سیگنال روی کندلِ ev_idx گذاشته می‌شود و
    موتورِ se ورود را در openِ کندلِ بعد انجام می‌دهد (قراردادِ موتور)."""
    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)
    up = ev_dir > 0
    if logic == 'follow':
        long_sig[ev_idx[up]] = True
        short_sig[ev_idx[~up]] = True
    else:  # fade
        short_sig[ev_idx[up]] = True
        long_sig[ev_idx[~up]] = True
    # آخرین کندل سیگنال نگیرد
    long_sig[-1] = False; short_sig[-1] = False
    return long_sig, short_sig


def run_variant(df, sl_arr, tp_arr, ev_idx, ev_dir, logic, mh, lo=None, hi=None):
    n = len(df)
    if lo is not None:
        mask = (ev_idx >= lo) & (ev_idx < hi)
        ev_idx = ev_idx[mask]; ev_dir = ev_dir[mask]
    ls, ss = build_signals(n, ev_idx, ev_dir, logic)
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                            asset=ASSET, max_hold=mh, allow_overlap=False)
    return tr


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return np.nan, 0
    w = (tr['pnl_pip'] > 0).mean()
    return 100.0 * w, len(tr)


def measured_null(df, sl_arr, tp_arr, ev_idx, ev_dir, mh, k=K_PERM, seed=SEED):
    """صفرِ هندسیِ اندازه‌گیری‌شده: جهتِ هر رویداد تصادفی، همان کندل‌ها/هندسه.
    خروجی به قالبِ per-side که rqs2 می‌پذیرد."""
    rng = np.random.default_rng(seed)
    n = len(df)
    wrs = np.empty(k)
    n_long_w = []; n_short_w = []
    for j in range(k):
        rd = rng.choice([-1, 1], size=len(ev_idx))
        ls = np.zeros(n, dtype=bool); ss = np.zeros(n, dtype=bool)
        ls[ev_idx[rd > 0]] = True; ss[ev_idx[rd < 0]] = True
        ls[-1] = False; ss[-1] = False
        tr = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                                asset=ASSET, max_hold=mh, allow_overlap=False)
        if len(tr):
            wrs[j] = 100.0 * (tr['pnl_pip'] > 0).mean()
            for side, acc in (('long', n_long_w), ('short', n_short_w)):
                m = tr['direction'] == side
                if m.any():
                    acc.append(100.0 * (tr.loc[m, 'pnl_pip'] > 0).mean())
        else:
            wrs[j] = np.nan
    wrs = wrs[~np.isnan(wrs)]
    def blk(arr):
        arr = np.asarray(arr, float)
        if len(arr) == 0:
            arr = wrs
        return dict(uncond_wr=float(np.mean(arr)), perm_mean=float(np.mean(arr)),
                    perm_sd=float(np.std(arr, ddof=1)), perm_max=float(np.max(arr)),
                    perm_k=int(len(arr)))
    return {'long': blk(n_long_w), 'short': blk(n_short_w)}, \
           dict(mean=float(wrs.mean()), sd=float(wrs.std(ddof=1)),
                hi=float(wrs.max()), k=int(len(wrs)))


def process_tf(tf):
    t0 = time.time()
    df, src = load_tf(tf)
    n = len(df)
    mh = MAX_HOLD.get(tf, 48)
    tsec = df['time'].to_numpy(float)
    close = df['close'].to_numpy(float)
    a = atr(df).to_numpy(float)
    ps = 0.1  # pip طلا = 0.1$
    sl_arr = np.maximum(SL_K * a / ps, 1e-9)
    tp_arr = sl_arr * RR
    split = n // 2

    # ---- گامِ ۱: جست‌وجوی IS (نیمهٔ اول) روی ۶ گونه ----
    rows = []
    events = {}
    for step in STEPS:
        ev_idx, ev_dir = detect_events(close, tsec, step)
        events[step] = (ev_idx, ev_dir)
        for logic in LOGICS:
            tr = run_variant(df, sl_arr, tp_arr, ev_idx, ev_dir, logic, mh,
                             lo=0, hi=split)
            wr, m = wr_of(tr)
            pnl = float(tr['pnl_pip'].sum()) if len(tr) else 0.0
            rows.append(dict(step=step, logic=logic, n=m, wr=wr, pnl_pip=pnl))
    # z تقریبی IS با صفرِ سریعِ K=200 روی هر step (برای انتخاب؛ نه داوری)
    rng = np.random.default_rng(SEED)
    for step in STEPS:
        ev_idx, ev_dir = events[step]
        m = (ev_idx < split)
        ei, ed = ev_idx[m], ev_dir[m]
        if len(ei) == 0:
            continue
        wrs = []
        for j in range(200):
            rd = rng.choice([-1, 1], size=len(ei))
            ls = np.zeros(n, bool); ss = np.zeros(n, bool)
            ls[ei[rd > 0]] = True; ss[ei[rd < 0]] = True
            ls[-1] = False; ss[-1] = False
            tr = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                                    asset=ASSET, max_hold=mh, allow_overlap=False)
            if len(tr):
                wrs.append(100.0 * (tr['pnl_pip'] > 0).mean())
        mu, sd = (np.mean(wrs), np.std(wrs, ddof=1)) if wrs else (np.nan, np.nan)
        for r in rows:
            if r['step'] == step and r['n'] > 0 and sd and sd > 0:
                r['lift'] = r['wr'] - mu
                r['z_is'] = (r['wr'] - mu) / sd
    for r in rows:
        r.setdefault('lift', np.nan); r.setdefault('z_is', np.nan)

    # انتخابِ برنده: بیشینهٔ z_is (پیش‌ثبت §۵)
    valid = [r for r in rows if np.isfinite(r.get('z_is', np.nan))]
    winner = max(valid, key=lambda r: r['z_is']) if valid else None

    out = dict(tf=tf, src=src, bars=n, split_bar=split, max_hold=mh,
               sl_median_pip=float(np.nanmedian(sl_arr)),
               is_grid=rows, winner=winner, elapsed_s=round(time.time() - t0, 1))

    # معیارِ ابطالِ ۱: هیچ گونه‌ای z_is ≥ 2.0 ندارد ⇒ کارت مرده، هولد‌اوت خرج نمی‌شود
    if winner is None or winner['z_is'] < 2.0:
        out['verdict'] = 'DEAD_IS'
        out['reason'] = 'no IS variant reached z>=2.0 (prereg invalidation #1)'
        return out

    # ---- گامِ ۲: داوریِ نهایی روی کلِ دوره با null کامل K=1000 ----
    step, logic = winner['step'], winner['logic']
    ev_idx, ev_dir = events[step]
    tr_full = run_variant(df, sl_arr, tp_arr, ev_idx, ev_dir, logic, mh)
    null_ps, null_flat = measured_null(df, sl_arr, tp_arr, ev_idx, ev_dir, mh)
    # هندسهٔ مؤثر برای گزارش به rqs2: میانگینِ SL/TP معاملاتِ واقعی
    sl_eff = float(tr_full['sl_pip'].mean()) if 'sl_pip' in tr_full.columns and len(tr_full) \
        else float(np.nanmedian(sl_arr))
    tp_eff = sl_eff * RR
    res = R.compute_rqs2(tr_full, ASSET, sl_pip=sl_eff, tp_pip=tp_eff,
                         bar_time=df['time'].to_numpy(), close=close,
                         null=null_ps, n_trials=N_TRIALS, split_bar=split)
    out['full'] = dict(n=len(tr_full),
                       wr=wr_of(tr_full)[0],
                       pnl_pip=float(tr_full['pnl_pip'].sum()),
                       null_flat=null_flat)
    out['rqs2'] = {k: res.get(k) for k in ('verdict', 'rqs2_score', 'gates')}
    out['rqs2_metrics'] = res.get('metrics')
    out['verdict'] = res.get('verdict')
    out['score'] = res.get('rqs2_score')
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        ck = os.path.join(OUT, f'checkpoint_{tf}.json')
        if os.path.exists(ck):
            print(f'[skip] {tf} (checkpoint exists)', flush=True)
            continue
        print(f'[run ] {tf} ...', flush=True)
        try:
            out = process_tf(tf)
        except Exception as e:
            out = dict(tf=tf, error=str(e))
        with open(ck, 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        w = out.get('winner') or {}
        print(f"[done] {tf}: verdict={out.get('verdict')} score={out.get('score')} "
              f"winner={w.get('logic')}/step{w.get('step')} z_is={w.get('z_is')} "
              f"({out.get('elapsed_s')}s)", flush=True)


if __name__ == '__main__':
    main()
