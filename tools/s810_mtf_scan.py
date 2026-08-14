"""
s810_mtf_scan.py — غربال MTF لایه‌ی S810 (گپ بازگشایی هفتگی) روی همه‌ی کارت‌های طلا
================================================================================

جایگاه: پس از حکم REJECT هولد‌اوت M1 (لیفت −1.83pp). قانون MTF پروژه الزام
می‌کند رخداد روی همه‌ی تایم‌فریم‌ها غربال شود. این فایل **غربال** است نه داور
(الگوی s434_mtf_skill_scan): هیچ حکمی صادر نمی‌کند؛ فقط لیفت/z گزارش می‌کند.

هندسه قفل‌شده از برنده‌ی نیمه‌ی اول: thr=0.5$, logic=cont, SL=80, TP=80.
max_hold به زمان دیواری ثابت ۸ ساعت ترجمه می‌شود (480 دقیقه‌ی M1) — کف ۲ کندل.

صداقت: چون هولد‌اوت M1 مصرف شده و حکم REJECT است، این غربال روی **کل**
داده‌ی هر کارت اجرا می‌شود ولی نتایجش فقط برای بستن پرونده (و راهنمایی
لایه‌های آینده) است؛ اگر کارتی z بالا نشان دهد، لایه‌ی جدید با پیش‌ثبت جدید
و هولد‌اوت تازه لازم است — هولد‌اوت سوخته احیا نمی‌شود.

W1/MN1 حذف: کندل‌هایشان وقفه‌ی آخرهفته را می‌بلعند ⇒ صفر رخداد (مرز ساختاری).
H4 با resample از H1 ساخته می‌شود (H4 در mt5_full غایب است — تله‌ی E-16).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se        # noqa: E402
from tools import s434_fast_data as fd       # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s810', 'mtf_scan.json')
SEED = 811
N_PERM = 40
THR, SL, TP = 0.5, 80, 80
HOLD_MIN = 480  # دقیقه (۸ ساعت)

TF_MIN = {'M1': 1, 'M3': 3, 'M4': 4, 'M5': 5, 'M6': 6, 'M10': 10, 'M12': 12,
          'M15': 15, 'M20': 20, 'M30': 30, 'H1': 60, 'H2': 120, 'H3': 180,
          'H4': 240, 'H6': 360, 'H8': 480, 'H12': 720, 'D1': 1440}
TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1']


def load_tf(tf):
    if tf == 'H4':
        d = fd.load_fast('XAUUSD', 'H1')
        df = fd.as_dataframe(d)
        df = df.set_index(pd.to_datetime(df['time'], unit='s'))
        r = df.resample('4h').agg({'open': 'first', 'high': 'max',
                                   'low': 'min', 'close': 'last'}).dropna()
        r['time'] = r.index.astype('int64') // 10**9
        return r.reset_index(drop=True), d['src'] + ' (resampled H1->H4)'
    d = fd.load_fast('XAUUSD', tf)
    return fd.as_dataframe(d), d['src']


def scan_tf(tf, rng):
    df, src = load_tf(tf)
    t = df['time'].values.astype(np.int64)
    tfm = TF_MIN[tf]
    # وقفه‌ی آخرهفته: فاصله‌ی زمانی > 3× طول کندل و ≥ 24h
    dt = np.diff(t)
    brk = np.where((dt >= 24 * 3600) & (dt > 3 * tfm * 60))[0]
    rb = brk + 1
    if len(rb) < 30:
        return dict(tf=tf, src=src, n_events=int(len(rb)),
                    note='structural: too few weekend events')
    gap = df['open'].values[rb] - df['close'].values[rb - 1]
    m = np.abs(gap) >= THR
    ev, g = rb[m], gap[m]
    mh = max(2, round(HOLD_MIN / tfm))
    n = len(df)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[ev[g > 0]] = True; ss[ev[g < 0]] = True   # cont
    tr = se.simulate_trades(df, ls, ss, sl_pip=SL, tp_pip=TP,
                            asset='XAUUSD', max_hold=mh, allow_overlap=False)
    ntr = 0 if tr is None else len(tr)
    if ntr < 50:
        return dict(tf=tf, src=src, n_events=int(len(ev)), n_trades=ntr,
                    note='too few trades for screen')
    wr = float((tr['outcome'].values == 'win').mean() * 100)
    pnl = float(tr['pnl_pip'].sum())
    perms = []
    for _ in range(N_PERM):
        flip = rng.random(n) < 0.5
        pls = (ls | ss) & flip; pss = (ls | ss) & ~flip
        ptr = se.simulate_trades(df, pls, pss, sl_pip=SL, tp_pip=TP,
                                 asset='XAUUSD', max_hold=mh, allow_overlap=False)
        if ptr is not None and len(ptr):
            perms.append(float((ptr['outcome'].values == 'win').mean() * 100))
    pm, psd = float(np.mean(perms)), float(np.std(perms) + 1e-9)
    lift = wr - pm
    return dict(tf=tf, src=src, n_events=int(len(ev)), n_trades=ntr, mh=mh,
                wr=round(wr, 2), perm_mean=round(pm, 2), perm_sd=round(psd, 2),
                lift_pp=round(lift, 2), z=round(lift / psd, 2),
                pnl_pip=round(pnl, 1))


def main():
    rng = np.random.default_rng(SEED)
    rows = []
    if os.path.exists(OUT):
        rows = json.load(open(OUT))
    done = {r['tf'] for r in rows}
    for tf in TF_ORDER:
        if tf in done:
            print(f'[skip] {tf} already scanned'); continue
        print(f'[scan] {tf} ...', flush=True)
        try:
            r = scan_tf(tf, rng)
        except Exception as e:
            r = dict(tf=tf, error=str(e))
        rows.append(r)
        print('   ', r, flush=True)
        with open(OUT, 'w') as f:
            json.dump(rows, f, indent=1)
        # checkpoint به گیت به‌ازای هر کارت (قانون checkpoint)
        os.system(f'cd {ROOT} && git add {OUT} >/dev/null 2>&1 && '
                  f'git commit -m "S810 MTF checkpoint: {tf}" >/dev/null 2>&1 && '
                  f'git push origin main >/dev/null 2>&1')
    print('[done] all TFs')


if __name__ == '__main__':
    main()
