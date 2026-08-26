"""
s811_mtf_scan.py — غربال MTF لایه‌ی S811 (تریگر چرخه‌ای Roofing) روی همه‌ی کارت‌های طلا
================================================================================

جایگاه: پس از حکم REJECT هولد‌اوت M1 (لیفت −0.30pp، z=−2.1). قانون MTF
پروژه الزام می‌کند رخداد روی همه‌ی تایم‌فریم‌ها غربال شود. این فایل **غربال**
است نه داور: هیچ حکمی صادر نمی‌کند؛ فقط لیفت/z نسبت به null اندازه‌گیری‌شده
(K=200 جای‌گشت جهت) گزارش می‌کند.

روش: مسیر سریع numba از tools/s811_fast_null (precompute + replay) که پیش‌تر
مقابل se.simulate_trades روی برش ۴۰۰هزار کندلی اعتبارسنجی دقیق شد
(39.1266 == 39.1266). هر کارت جدید هم روی برش کوچک مقابل موتور رسمی
sanity-check می‌شود (اختلاف > 0.05pp ⇒ توقف).

هندسه‌ی قفل‌شده از برنده‌ی نیمه‌ی اول: logic=cycle، gate=none،
SL=15، TP=22.5 (RR=1.5). max_hold = ۶۰ دقیقه‌ی دیواری (کف ۲ کندل).

صداقت: هولد‌اوت M1 مصرف شده و حکم REJECT است؛ این غربال روی **کل** داده‌ی
هر کارت اجرا می‌شود ولی فقط برای بستن پرونده است. کارت z-بالا ⇒ لایه‌ی
جدید با پیش‌ثبت و هولد‌اوت تازه لازم دارد؛ هولد‌اوت سوخته احیا نمی‌شود.

W1/MN1 حذف (مرز ساختاری). H4 با resample از H1 (تله‌ی E-16).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se        # noqa: E402
from engine import indicator_bank as ib      # noqa: E402
from tools import s434_fast_data as fd       # noqa: E402
from tools.s811_fast_null import precompute_outcomes, nonoverlap_wr  # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s811', 'mtf_scan.json')
SEED = 812
N_PERM = 200
SL, TP = 15.0, 22.5
HOLD_MIN = 60  # دقیقه‌ی دیواری
PIP = 0.1
SPREAD = 3.3

TF_MIN = {'M1': 1, 'M3': 3, 'M4': 4, 'M5': 5, 'M6': 6, 'M10': 10, 'M12': 12,
          'M15': 15, 'M20': 20, 'M30': 30, 'H1': 60, 'H2': 120, 'H3': 180,
          'H4': 240, 'H6': 360, 'H8': 480, 'H12': 720, 'D1': 1440}
TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1']


def load_tf(tf):
    """آرایه‌های numpy (open/high/low/close/time) + src؛ بدون کپی اضافی."""
    if tf == 'H4':
        d = fd.load_fast('XAUUSD', 'H1')
        df = fd.as_dataframe(d)
        df = df.set_index(pd.to_datetime(df['time'], unit='s'))
        r = df.resample('4h').agg({'open': 'first', 'high': 'max',
                                   'low': 'min', 'close': 'last'}).dropna()
        r['time'] = r.index.astype('int64') // 10**9
        r = r.reset_index(drop=True)
        arrs = {k: r[k].values.astype(np.float64)
                for k in ('open', 'high', 'low', 'close')}
        arrs['time'] = r['time'].values.astype(np.int64)
        return arrs, d['src'] + ' (resampled H1->H4)'
    d = fd.load_fast('XAUUSD', tf)
    arrs = {k: np.asarray(d[k], dtype=np.float64)
            for k in ('open', 'high', 'low', 'close')}
    arrs['time'] = np.asarray(d['time'], dtype=np.int64)
    return arrs, d['src']


def roof_of(close):
    """roof از بانک اندیکاتور با دیتافریم حداقلی (فقط close لازم است)."""
    df = pd.DataFrame({'close': close})
    return np.asarray(ib.compute('roof', df), dtype=np.float64)


def sanity_check(arrs, sig_idx, dirs, mh, win_L, win_S, exit_L, exit_S, valid):
    """برش اول ≤200k کندل: مقایسه‌ی WR مسیر سریع با موتور رسمی."""
    ncut = min(200_000, len(arrs['open']))
    m = sig_idx < (ncut - mh - 2)
    if m.sum() < 30:
        return None  # برش خیلی کوچک؛ چک بی‌معنا
    si = sig_idx[m]; dd = dirs[m]
    wl, nl, ws, ns_ = nonoverlap_wr(si, dd, win_L[m], win_S[m],
                                    exit_L[m], exit_S[m], valid[m])
    tot = nl + ns_
    if tot == 0:
        return None
    wr_fast = 100.0 * (wl + ws) / tot
    df = pd.DataFrame({k: arrs[k][:ncut] for k in
                       ('open', 'high', 'low', 'close', 'time')})
    ls = np.zeros(ncut, bool); ss = np.zeros(ncut, bool)
    ls[si[dd == 1]] = True; ss[si[dd == 0]] = True
    tr = se.simulate_trades(df, ls, ss, sl_pip=SL, tp_pip=TP,
                            max_hold=mh, asset='XAUUSD')
    if tr is None or len(tr) == 0:
        return None
    wr_ref = float((tr['outcome'].values == 'win').mean() * 100)
    if abs(wr_fast - wr_ref) > 0.05:
        raise RuntimeError(f'fast-path divergence: {wr_fast:.4f} vs {wr_ref:.4f}')
    return round(wr_fast, 4), round(wr_ref, 4)


def scan_tf(tf, rng):
    arrs, src = load_tf(tf)
    close = arrs['close']
    n = len(close)
    # کش M1 (roof از قبل محاسبه و ذخیره شده)
    cache = os.path.join(ROOT, 'results', '_s811', 'features_m1.npz')
    if tf == 'M1' and os.path.exists(cache):
        roof = np.load(cache)['roof']
    else:
        roof = roof_of(close)
    up = np.zeros(n, bool); dn = np.zeros(n, bool)
    up[1:] = (roof[1:] > 0) & (roof[:-1] <= 0)
    dn[1:] = (roof[1:] < 0) & (roof[:-1] >= 0)
    del roof
    sig_idx = np.where(up | dn)[0].astype(np.int64)
    dirs = up[sig_idx].astype(np.int8)  # 1=long(cycle up), 0=short
    tfm = TF_MIN[tf]
    mh = max(2, round(HOLD_MIN / tfm))
    if len(sig_idx) < 30:
        return dict(tf=tf, src=src, n_events=int(len(sig_idx)),
                    note='too few events')
    win_L, win_S, exit_L, exit_S, valid = precompute_outcomes(
        arrs['open'], arrs['high'], arrs['low'], close,
        sig_idx, SL * PIP, TP * PIP, mh, SPREAD, PIP)
    sc = sanity_check(arrs, sig_idx, dirs, mh,
                      win_L, win_S, exit_L, exit_S, valid)
    # لایه‌ی واقعی
    wl, nl, ws, ns_ = nonoverlap_wr(sig_idx, dirs, win_L, win_S,
                                    exit_L, exit_S, valid)
    tot = nl + ns_
    if tot < 30:
        return dict(tf=tf, src=src, n=int(tot), note='too few trades')
    wr = 100.0 * (wl + ws) / tot
    # null: جای‌گشت جهت
    perms = np.empty(N_PERM)
    for i in range(N_PERM):
        pd_ = (rng.random(len(sig_idx)) < 0.5).astype(np.int8)
        pwl, pnl_, pws, pns = nonoverlap_wr(sig_idx, pd_, win_L, win_S,
                                            exit_L, exit_S, valid)
        pt = pnl_ + pns
        perms[i] = 100.0 * (pwl + pws) / pt if pt > 0 else np.nan
    pm = float(np.nanmean(perms))
    psd = max(float(np.nanstd(perms, ddof=1)), 1e-9)
    lift = wr - pm
    z = lift / psd
    out = dict(tf=tf, src=src, n=int(tot), n_events=int(len(sig_idx)),
               wr=round(wr, 3), perm_mean=round(pm, 3),
               perm_sd=round(psd, 4), perm_k=N_PERM,
               lift_pp=round(lift, 3), z=round(z, 2), mh=mh)
    if sc:
        out['sanity_fast_vs_engine'] = list(sc)
    return out


def git_ckpt(tf):
    try:
        subprocess.run(['git', 'add', OUT], cwd=ROOT, check=True)
        subprocess.run(['git', 'commit', '-m',
                        f'S811 MTF checkpoint: {tf}'], cwd=ROOT, check=True,
                       capture_output=True)
    except Exception as e:  # noqa: BLE001
        print(f'  [ckpt warn] {e}')


def main():
    rng = np.random.default_rng(SEED)
    res = {}
    if os.path.exists(OUT):
        res = json.load(open(OUT))
    for tf in TF_ORDER:
        if tf in res:
            print(f'{tf}: cached, skip', flush=True)
            continue
        print(f'--- {tf} ---', flush=True)
        r = scan_tf(tf, rng)
        res[tf] = r
        json.dump(res, open(OUT, 'w'), indent=1)
        print(f'  {r}', flush=True)
        git_ckpt(tf)
    print('MTF scan done.')


if __name__ == '__main__':
    main()
