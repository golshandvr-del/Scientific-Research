# -*- coding: utf-8 -*-
"""
S554 — عبورِ ناپایداریِ نوسان (Vol-of-Vol Instability Cross) — طلا، TFهای درشت
================================================================================
پیش‌ثبت: results/S554_PREREG_VOL_OF_VOL_INSTABILITY_CROSS.md (commit c6b7fc42)
که **پیش از نوشتنِ این فایل** به GitHub رفت. Path B — صفر اکتشاف.

  رویداد : VoV=std21(TR/ATR55(t−1)) از زیرِ q90غلتان(250, t−1) به بالا عبور کند
  جهت    : sign(close(t) − close(t−34)) — تداوم (قانون S522/S950)
  هندسه  : وراثت کلمه‌به‌کلمه از S770 ACCEPT — SL=1.272×ATR100(t−1)،
           TP=2.058×SL، mh=16، allow_overlap=False
  نول    : جایگشتِ جهت روی همان رویدادها با همان هندسه (پیش‌ثبت‌شده)
  بودجه  : n_trials=55 · SEED=20260826 · K_PERM: H8/H6=1000، H12/D1=2000

اجرا:  python3 strategies/s554_vov_instability.py [CARD ...]
       (پیش‌فرض: H8 H6 H12 D1 — حکم‌ساز اول)
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                # noqa: E402
from engine import rqs2                                              # noqa: E402
from tools import s434_fast_data as fd                               # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df             # noqa: E402

ASSET = 'XAUUSD'
SEED = 20260826
N_TRIALS = 55
SPLIT_FRAC = 0.60
UNCOND_CAP = 150_000          # افشا؛ عملاً رویدادها بسیار کمترند
OUT = 'results/_scan_S554'
PREREG = 'c6b7fc42'

# —— پیکربندی منجمدِ پیش‌ثبت (سلول یکتا؛ ۵۴ واریانتِ ذهنی فقط در بودجه) ——
VOV_WIN = 21          # پنجرهٔ std
ATR_NORM = 55         # نرمال‌سازِ TR
THR_Q = 0.90          # چندکِ غلتان
THR_WIN = 250         # پنجرهٔ چندک (min_periods=100)
DRIFT_L = 34          # افقِ دریفتِ جهت
SL_K = 1.272          # وراثت S770
RR = 2.058            # وراثت S770 (TP>SL ⇒ قانون بودجه)
ATR_GEO = 100         # ATR هندسه
MH = 16               # وراثت S770
WARM = 400            # ≥ 55+21+250+34 — اعتبار اندیکاتورها

K_PERM = {'H8': 1000, 'H6': 1000, 'H12': 2000, 'D1': 2000}
ROLE = {'H8': 'DECISIVE', 'H6': 'INFO', 'H12': 'INFO', 'D1': 'INFO'}
LADDER = ['H8', 'H6', 'H12', 'D1']


def log(msg):
    print(msg, flush=True)


def git_checkpoint(card):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-m',
                        f'S554 checkpoint: {card} judged (frozen prereg {PREREG})'],
                       check=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'],
                       check=False, timeout=90)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, timeout=90)
        log(f'    [git] checkpoint {card} pushed')
    except Exception as e:                                   # noqa: BLE001
        log(f'    [git] WARN checkpoint failed: {e} (فایل روی دیسک هست)')


def to_dt64(t):
    """درسِ BUG-EPOCH: لودر ثانیهٔ epoch (int64) می‌دهد — تبدیل صریح."""
    return t.astype('datetime64[s]').astype('datetime64[ns]')


def build_features(df):
    h = df['high'].astype(float)
    l = df['low'].astype(float)
    c = df['close'].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr_norm = tr.rolling(ATR_NORM).mean().shift(1)          # ATR55(t−1)
    x = tr / atr_norm                                        # رنجِ نرمال‌شده
    vov = x.rolling(VOV_WIN).std(ddof=1)                     # VoV(t)
    thr = vov.rolling(THR_WIN, min_periods=100).quantile(THR_Q).shift(1)
    atr_geo = tr.rolling(ATR_GEO).mean().shift(1)            # ATR100(t−1)
    drift = np.sign(c - c.shift(DRIFT_L))                    # دریفت ۳۴کندلی
    return vov, thr, atr_geo, drift


def build_signal(df):
    """عبورِ VoV از بالای آستانهٔ غلتان + جهت = تداومِ دریفت. صفر پارامتر آزاد."""
    vov, thr, atr_geo, drift = build_features(df)
    v = vov.values
    t = thr.values
    ok = np.isfinite(v) & np.isfinite(t)
    ok_prev = np.roll(ok, 1)
    ok_prev[0] = False
    v_prev = np.roll(v, 1)
    t_prev = np.roll(t, 1)
    cross = ok & ok_prev & (v_prev <= t_prev) & (v > t)
    d = drift.values
    long_sig = cross & (d > 0)
    short_sig = cross & (d < 0)                              # دریفت صفر ⇒ بدون سیگنال
    return long_sig, short_sig, atr_geo.values


def run_card(card):
    t0 = time.time()
    role = ROLE[card]
    k_perm = K_PERM[card]
    log(f'\n================ S554 · {ASSET} · {card} ({role}) ================')
    d = fd.load_fast(ASSET, card)
    src = d['src']
    if 'mt5_full' not in src:
        raise RuntimeError(f'{card}: دادهٔ full نیست — توقف.')
    df = fd.as_dataframe(d)
    n = len(df)
    t64 = to_dt64(d['time'])
    pip = float(se.ASSETS[ASSET]['pip'])
    cost = float(se.ASSETS[ASSET]['spread_pip']) + \
        2.0 * float(se.ASSETS[ASSET].get('slip_pip', 0.0))
    span_y = float((t64[-1] - t64[0]) / np.timedelta64(1, 'D')) / 365.25
    log(f'  src={src}  bars={n:,}  span={span_y:.2f}y  warmup={WARM}  '
        f'geom: SL={SL_K}×ATR{ATR_GEO} RR={RR} mh={MH}')

    long_sig, short_sig, atr_geo = build_signal(df)
    long_sig[:WARM] = False
    short_sig[:WARM] = False
    long_sig[n - MH - 2:] = False
    short_sig[n - MH - 2:] = False
    geo_ok = np.isfinite(atr_geo) & (atr_geo > 0)
    long_sig &= geo_ok
    short_sig &= geo_ok
    sel = long_sig | short_sig
    nsig = int(sel.sum())
    if nsig < 2:
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no signals)')
        _save(card, payload)
        return payload
    log(f'  signals={nsig} (L={int(long_sig.sum())}/S={int(short_sig.sum())})')

    ev = np.flatnonzero(sel)                                 # رویدادها
    ev_long = long_sig[ev]                                   # جهتِ قاعده
    sl_dist = SL_K * atr_geo[ev]                             # فاصلهٔ SL قیمتی

    st = queue_rr(df, ev, ev_long, sl_dist, ASSET, MH, RR)
    if st is None or st['n'] == 0:
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no trades)')
        _save(card, payload)
        return payload
    tr = trades_df(st)
    pnl = tr['pnl_pip'].values.astype(float)
    wr = float(100 * (pnl > 0).mean())
    e_pip = float(pnl.mean()) + cost
    isL = (tr['direction'] == 'long').to_numpy()
    nL, nS = int(isL.sum()), int((~isL).sum())
    log(f'  trades={len(tr)} (L={nL}/S={nS})  wr={wr:.2f}%  '
        f'net={pnl.mean():+.2f} pip  e_pip={e_pip:+.2f} vs c={cost:.2f}  '
        f'SLmed={np.median(tr["sl_pip"]):.0f}pip  '
        f'sideL_net={pnl[isL].mean() if nL else 0:+.2f}  '
        f'sideS_net={pnl[~isL].mean() if nS else 0:+.2f}  '
        f'[{time.time()-t0:.0f}s]')

    # —— نولِ پیش‌ثبت‌شده: جایگشتِ جهت روی همان رویدادها، همان هندسه ——
    rng = np.random.default_rng(SEED)
    all_sl = SL_K * atr_geo[ev]
    null = {}
    for side, n_side, is_long in (('long', nL, True), ('short', nS, False)):
        dd = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                  perm_max=None, perm_k=None, uncond_pool=int(len(ev)))
        if n_side >= 1:
            s_all = queue_rr(df, ev, np.full(len(ev), is_long),
                             all_sl, ASSET, MH, RR)
            if s_all:
                dd['uncond_wr'] = s_all['wr']
            if len(ev) > 1:
                wrs = []
                for _ in range(k_perm):
                    m = min(n_side, len(ev))
                    pick = np.sort(rng.choice(len(ev), size=m, replace=False))
                    s_p = queue_rr(df, ev[pick], np.full(m, is_long),
                                   all_sl[pick], ASSET, MH, RR)
                    if s_p:
                        wrs.append(s_p['wr'])
                if wrs:
                    a = np.asarray(wrs, dtype='float64')
                    dd.update(perm_mean=float(a.mean()),
                              perm_sd=float(a.std(ddof=1)),
                              perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = dd
        log(f"      null {side}: n={n_side} uncond={dd['uncond_wr']} "
            f"perm_mean={dd['perm_mean']} sd={dd['perm_sd']} k={dd['perm_k']}")

    te_ns = t64[tr['entry_bar'].to_numpy(int)].astype(np.int64)
    split_ns = int(np.quantile(te_ns, SPLIT_FRAC))
    holdout = te_ns >= split_ns
    log(f'  H7: disc={int((~holdout).sum())} · oos={int(holdout.sum())} '
        f'· split@{np.datetime64(split_ns, "ns")}')

    null_clean = {k: {kk: vv for kk, vv in v.items() if kk != 'uncond_pool'}
                  for k, v in null.items()}
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=None, tp_pip=None,
                            bar_time=t64, close=df['close'].to_numpy(float),
                            null=null_clean, n_trials=N_TRIALS,
                            holdout_mask=holdout, allow_overlap=False)
    log('')
    log(rqs2.format_rqs2(f'S554_{card}', res))
    log(f'  PIP-EDGE LAW: e_pip={e_pip:+.2f} '
        f'{">" if e_pip > cost else "<="} c={cost:.2f} ⇒ '
        f'{"PASS" if e_pip > cost else "FAIL (BELOW_COST)"}')

    entry_times = t64[tr['entry_bar'].to_numpy(int)].astype(str).tolist()
    payload = dict(card=card, role=role, src=src, n_bars=int(n),
                   span_years=span_y, warmup=WARM,
                   config=dict(vov_win=VOV_WIN, atr_norm=ATR_NORM, thr_q=THR_Q,
                               thr_win=THR_WIN, drift_l=DRIFT_L,
                               sl_k=SL_K, rr=RR, atr_geo=ATR_GEO, mh=MH,
                               rule='S770-inherited geometry, verbatim'),
                   n_signals=nsig, n_trades=int(len(tr)),
                   n_long=nL, n_short=nS, wr=wr,
                   net_pip=float(pnl.mean()),
                   net_pip_long=float(pnl[isL].mean()) if nL else None,
                   net_pip_short=float(pnl[~isL].mean()) if nS else None,
                   sl_pip_median=float(np.median(tr['sl_pip'])),
                   tp_pip_median=float(np.median(tr['tp_pip'])),
                   e_pip=e_pip, cost_pip=cost,
                   pip_edge_pass=bool(e_pip > cost),
                   null=null, k_perm=k_perm, n_trials=N_TRIALS,
                   split_frac=SPLIT_FRAC, split_ns=split_ns, seed=SEED,
                   verdict=res.get('verdict'),
                   rqs2_score=res.get('rqs2_score'), gates=res.get('gates'),
                   metrics=res.get('metrics'), entry_times=entry_times,
                   elapsed_s=round(time.time() - t0, 1))
    _save(card, payload)
    tr.to_csv(f'{OUT}/{card}_trades.csv', index=False)
    git_checkpoint(card)
    return payload


def _save(card, payload):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/{card}.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, default=str, indent=1)
    log(f'  saved -> {OUT}/{card}.json')


def main():
    cards = sys.argv[1:] or LADDER
    for card in cards:
        try:
            run_card(card)
        except Exception as e:                               # noqa: BLE001
            import traceback
            traceback.print_exc()
            log(f'!! {card} failed: {e} — ادامه با کارتِ بعدی')
    log('\nS554 run complete.')


if __name__ == '__main__':
    main()
