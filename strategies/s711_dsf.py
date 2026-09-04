# -*- coding: utf-8 -*-
"""
S711 — Day-So-Far Intraday Momentum — XAUUSD — Path C
======================================================
پیاده‌سازیِ عینِ پیش‌ثبتِ results/S711_PREREG_intraday_momentum_dsf.md
(کامیت‌شده قبل از هر شبیه‌سازی). هیچ پارامتری خارج از آن سند نیست.

⚠️ این فایل نسخهٔ بازنویسی‌شده پس از ریستِ سندباکس است (نسخهٔ اول در
   کامیت‌های محلیِ push‌نشده گم شد). مشخصات از prereg گرفته شده، نه از حافظه.
   نتیجهٔ TRAIN در نسخهٔ گم‌شده: برندهٔ h=19 q=78.6 — همین‌جا دوباره از
   صفر با همان کد قطعی و seed محاسبه می‌شود؛ اگر متفاوت شود، صادقانه ثبت.

فازها:
  python3 strategies/s711_dsf.py train              # فقط نیمهٔ اول H1، ۶ سلول
  python3 strategies/s711_dsf.py judge H1,M30,M15,M5  # برندهٔ منجمد، کل‌داده

باگ‌های مستندِ این لایه:
  BUG-EPOCH  (S710): d['time'] ثانیه است؛ هرگز مستقیم datetime64[ns] نشود.
  BUG-ASI8   (S711): در pandas 2، DatetimeIndex ساخته‌شده از datetime64[s]
             رزولوشن ثانیه دارد و .asi8 آن ثانیه است نه ns. gap را از خام بگیر.
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import rqs2                                    # noqa: E402
from engine import scalp_engine as se                     # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df   # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402

# ─── پارامترهای منجمد (prereg §2, §3) ────────────────────────────────────
ASSET = 'XAUUSD'
TRAIN_TF = 'H1'
FAMILY = ['H1', 'M30', 'M15', 'M5']
H_GRID = (16, 19, 21)
Q_GRID = (61.8, 78.6)
ATR_P = 34
GEO_K = 2.618              # SL = TP = 2.618 × ATR(34)
RR = 1.0                   # V-TIME متقارن
MIN_BARS_FROM_OPEN = 3
MIN_HIST = 60              # حداقل نمونهٔ تاریخی برای چندک انبساطی
MIN_N_TRAIN = 150
N_TRIALS = 10              # 6 سلول TRAIN + 4 کارت خانواده
SEED = 20260826
K_PERM = 500
OUT = 'results/_scan_S711'
BPH = {'M5': 12, 'M15': 4, 'M30': 2, 'H1': 1}   # bars per hour


def log(m):
    print(m, flush=True)


def git_checkpoint(tag):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-q', '-m',
                        f'S711 checkpoint: {tag} (frozen prereg params)'], check=True)
        subprocess.run(['git', 'pull', '--rebase', '-q', 'origin', 'main'],
                       check=False, timeout=120)
        subprocess.run(['git', 'push', '-q', 'origin', 'main'], check=True, timeout=120)
        log(f'    [git] checkpoint {tag} pushed')
    except Exception as e:                                   # noqa: BLE001
        log(f'    [git] WARN checkpoint failed: {e} (فایل روی دیسک هست)')


# ─── ابزارهای علّی ───────────────────────────────────────────────────────
def atr_series(df, p):
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def day_structure(df):
    """شکست روز طبق prereg: gap > max(1800s, 1.5×TF_seconds)."""
    sec = df['time'].to_numpy().astype('int64')          # ثانیه (BUG-EPOCH)
    gap = np.diff(sec)                                    # BUG-ASI8: از خام
    tf_sec = float(np.median(gap))
    brk = np.where(gap > max(1800.0, 1.5 * tf_sec))[0] + 1
    starts = np.concatenate([[0], brk])
    day_id = np.zeros(len(sec), dtype=np.int64)
    day_id[starts] = 1
    day_id = np.cumsum(day_id) - 1
    hours = pd.DatetimeIndex(sec.astype('datetime64[s]')).hour.to_numpy()
    return starts, day_id, hours


def day_events(df, h):
    """اندیسِ اولین کندلِ ساعت h در هر روز (≥3 کندل از شروع) + dsf علّی.

    dsf = close[i-1] − open[start_of_day]  — فقط کندل‌های بستهٔ قبلی.
    """
    starts, day_id, hours = day_structure(df)
    o = df['open'].to_numpy()
    c = df['close'].to_numpy()
    n = len(df)
    is_h = hours == h
    # اولین وقوعِ ساعت h در هر روز: is_h و (کندل قبلی ساعت h نیست یا روز دیگر است)
    prev_is_h = np.concatenate([[False], is_h[:-1]])
    prev_same_day = np.concatenate([[False], day_id[1:] == day_id[:-1]])
    first_h = is_h & ~(prev_is_h & prev_same_day)
    idx = np.where(first_h)[0]
    idx = idx[idx >= 1]
    ds = starts[day_id[idx]]
    ok = (idx - ds) >= MIN_BARS_FROM_OPEN
    idx = idx[ok]
    ds = ds[ok]
    dsf = c[idx - 1] - o[ds]
    return idx, dsf


def causal_threshold_mask(dsf, q):
    """|dsf| > چندک انبساطیِ علّیِ q از |dsf|های *قبلی* (بدون خودِ نمونه)."""
    a = np.abs(dsf)
    keep = np.zeros(len(a), dtype=bool)
    for i in range(MIN_HIST, len(a)):
        thr = np.quantile(a[:i], q / 100.0)
        keep[i] = a[i] > thr
    return keep


def geometry(df, tf, h):
    atr = atr_series(df, ATR_P)
    sl_dist = GEO_K * atr                       # واحد قیمت
    hold = (23 - h) * BPH[tf]
    return sl_dist, max(1, hold)


def run_side(df, idx, sl_dist_arr, hold, is_long):
    """idx = کندلِ ساعت h (ورود در open آن). قراردادِ barrier_outcomes:
    sig_idx = کندلِ سیگنال و ورود در sig_idx+1 ⇒ sig_idx = idx−1.
    ATR نیز از کندلِ سیگنال (idx−1) خوانده می‌شود — علّی."""
    if len(idx) == 0:
        return None
    sig = idx - 1
    return queue_rr(df, sig, np.full(len(sig), is_long, dtype=bool),
                    sl_dist_arr[sig], ASSET, hold, RR)


def merge_sides(stl, sts):
    parts = [s for s in (stl, sts) if s is not None]
    if not parts:
        return None
    keys = ('pnl', 'win', 'entry_bar', 'exit_bar', 'is_long', 'sl_pip', 'tp_pip')
    st = {k: np.concatenate([p[k] for p in parts]) for k in keys}
    order = np.argsort(st['entry_bar'], kind='stable')
    st = {k: v[order] for k, v in st.items()}
    pnl = st['pnl']
    win = pnl > 0
    gw = float(pnl[win].sum()); gl = float(-pnl[~win].sum())
    st.update(n=int(len(pnl)), wr=float(win.mean() * 100), exp=float(pnl.mean()),
              pf=float(gw / gl) if gl > 0 else 999.0)
    return st


# ─── مدل صفر (prereg §4): استخر uncond = همهٔ روزهای واجد در ساعت h ──────
def build_null(df, all_idx, sl_dist, hold, n_long, n_short, rng, k_perm=K_PERM):
    """K جای‌گشت از انتخاب تصادفیِ k رویداد از استخرِ بدون‌آستانه، هر سمت جدا."""
    out = {}
    for side, is_long, k in (('long', True, n_long), ('short', False, n_short)):
        if k <= 0:
            out[side] = None
            continue
        st_u = run_side(df, all_idx, sl_dist, hold, is_long)
        uncond_wr = float(st_u['wr']) if st_u else float('nan')
        # جای‌گشت: نتیجهٔ هر رویداد استخر (با همین هندسه) را یک بار حساب می‌کنیم؛
        # queue_rr غیرهم‌پوشان است، پس pnl per-event از barrier_outcomes مستقیم:
        from strategies.s346_fast import barrier_outcomes
        cfg = se.ASSETS[ASSET]
        sig = all_idx - 1
        fo = barrier_outcomes(df, sig, np.full(len(sig), is_long, dtype=bool),
                              sl_dist[sig], np.maximum(RR * sl_dist[sig], sl_dist[sig]),
                              hold, float(cfg['pip']), float(cfg['spread_pip']),
                              float(cfg.get('slip_pip', 0.0)))
        pnl_u = fo['pnl_pip']
        m = len(pnl_u)
        kk = min(k, m)
        wrs = np.empty(k_perm)
        for j in range(k_perm):
            pick = rng.choice(m, size=kk, replace=False)
            wrs[j] = (pnl_u[pick] > 0).mean() * 100.0
        out[side] = dict(uncond_wr=float((pnl_u > 0).mean() * 100.0),
                         perm_mean=float(wrs.mean()), perm_sd=float(wrs.std(ddof=1)),
                         perm_max=float(wrs.max()), perm_k=int(k_perm))
        log(f'    null {side} uncond={out[side]["uncond_wr"]:.2f} '
            f'mean={out[side]["perm_mean"]:.2f} sd={out[side]["perm_sd"]:.2f} k={k_perm}')
    return out


# ─── فاز TRAIN (فقط نیمهٔ اول H1) ──────────────────────────────────────
def train():
    d = fd.load_fast(ASSET, TRAIN_TF)
    df_full = fd.as_dataframe(d)
    n = len(df_full)
    split = n // 2
    df = df_full.iloc[:split].reset_index(drop=True)      # نیمهٔ دوم: دست‌نخورده
    log(f'TRAIN {TRAIN_TF}: bars={n:,} split={split} src={d["src"]}')
    rows = []
    for h in H_GRID:
        idx, dsf = day_events(df, h)
        sl_dist, hold = geometry(df, TRAIN_TF, h)
        for q in Q_GRID:
            keep = causal_threshold_mask(dsf, q)
            ii, dd = idx[keep], dsf[keep]
            st = merge_sides(run_side(df, ii[dd > 0], sl_dist, hold, True),
                             run_side(df, ii[dd < 0], sl_dist, hold, False))
            if st is None:
                rows.append(dict(h=h, q=q, n=0, score=None)); continue
            net = float(st['pnl'].sum())
            score = st['exp'] * np.sqrt(st['n']) if (st['n'] >= MIN_N_TRAIN and net > 0) else None
            rows.append(dict(h=h, q=q, n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'],
                             net=net, score=None if score is None else float(score)))
            log(f'  h={h} q={q}: n={st["n"]} wr={st["wr"]:.2f} exp={st["exp"]:.3f} '
                f'pf={st["pf"]:.3f} net={net:.0f} score={score}')
    cands = [r for r in rows if r['score'] is not None]
    winner = None
    if cands:
        cands.sort(key=lambda r: (-r['score'], -r['n'], r['h']))
        winner = dict(h=cands[0]['h'], q=cands[0]['q'])
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(phase='train', tf=TRAIN_TF, src=d['src'], split=split, n_bars=n,
                   grid=rows, winner=winner, seed=SEED),
              open(f'{OUT}/TRAIN.json', 'w'), indent=1, ensure_ascii=False)
    log(f'\nWINNER (frozen): {winner}')
    git_checkpoint('TRAIN')
    return winner


# ─── فاز JUDGE (برندهٔ منجمد، کل‌داده، split=n//2) ──────────────────────
def judge(tfs):
    W = json.load(open(f'{OUT}/TRAIN.json'))['winner']
    if W is None:
        log('no winner — glass ceiling; nothing to judge'); return
    h, q = W['h'], W['q']
    for tf in tfs:
        t0 = time.time()
        d = fd.load_fast(ASSET, tf)
        df = fd.as_dataframe(d)
        n = len(df)
        split = n // 2
        log(f'\n================ S711 · {ASSET} · {tf} (h={h}, q={q}) ============')
        idx, dsf = day_events(df, h)
        sl_dist, hold = geometry(df, tf, h)
        keep = causal_threshold_mask(dsf, q)
        ii, dd = idx[keep], dsf[keep]
        st = merge_sides(run_side(df, ii[dd > 0], sl_dist, hold, True),
                         run_side(df, ii[dd < 0], sl_dist, hold, False))
        if st is None:
            log('  no trades'); continue
        log(f'  trades={st["n"]} wr={st["wr"]:.2f}% exp={st["exp"]:.3f} pf={st["pf"]:.3f} '
            f'hold={hold} bars  [{time.time()-t0:.0f}s]')
        rng = np.random.default_rng(SEED)
        nl = int(st['is_long'].sum()); ns = int(st['n'] - nl)
        null = build_null(df, idx, sl_dist, hold, nl, ns, rng)
        tr = trades_df(st)
        sl_med = float(np.median(tr['sl_pip'])); tp_med = float(np.median(tr['tp_pip']))
        r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                              bar_time=df['time'].to_numpy(),
                              close=df['close'].to_numpy(), null=null,
                              n_trials=N_TRIALS, split_bar=split, allow_overlap=False)
        log(rqs2.format_rqs2(f'S711_DSF_{tf}', r))
        os.makedirs(OUT, exist_ok=True)
        payload = dict(tf=tf, src=d['src'], n_bars=n, split_bar=split, winner=W,
                       geometry=dict(atr_p=ATR_P, k=GEO_K, rr=RR, hold_bars=hold),
                       n_trials=N_TRIALS, seed=SEED, k_perm=K_PERM,
                       stats=dict(n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'],
                                  n_long=nl, n_short=ns),
                       null=null, rqs2=r)
        json.dump(payload, open(f'{OUT}/{tf}.json', 'w'), indent=1,
                  ensure_ascii=False, default=str)
        tr.to_csv(f'{OUT}/{tf}_trades.csv', index=False)
        log(f'  saved -> {OUT}/{tf}.json  [{time.time()-t0:.0f}s total]')
        git_checkpoint(tf)


def main():
    if len(sys.argv) < 2 or sys.argv[1] == 'train':
        train()
    elif sys.argv[1] == 'judge':
        judge(sys.argv[2].split(',') if len(sys.argv) > 2 else FAMILY)


if __name__ == '__main__':
    main()
