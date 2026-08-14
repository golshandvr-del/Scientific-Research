"""
s810_weekend_gap.py — لایه‌ی S810: رفتار گپ بازگشایی هفتگی طلا
================================================================================

پیش‌ثبت: results/S810_PREREG_WEEKEND_GAP_HOLDOUT.md (کامیت ac6d2afe — پیش از هر آزمون)
مسیر چندگانگی: C (hold-out). برش: 2019-01-01 00:00 UTC (epoch 1546300800).

فرضیه (شنون): آخر هفته ~۴۸ ساعت اطلاعات انباشته می‌شود و در گپ بازگشایی
تخلیه می‌گردد. رفتار قیمت پس از بازگشایی نسبت به اندازه/جهت گپ ساختار دارد.

سه فاز، سه زیرفرمان — هرگز با هم اجرا نمی‌شوند:
  --search   : پیمایش ۲۷۰ ترکیب قفل‌شده فقط روی نیمه‌ی اول (< split).
  --null     : ساخت مدل صفر سنجیده (K=500 جای‌گشت) برای پیکربندی برنده،
               روی رخدادهای نیمه‌ی دوم (همان استخری که داوری می‌شود).
  --judge    : «یک» آزمون روی نیمه‌ی محافظت‌شده با rqs2.compute_rqs2
               (n_trials=1, split_bar=SPLIT_IDX). پس از یک بار اجرا، قفل می‌شود.

forward-safety: رخداد = اولین کندل M1 پس از وقفه‌ی ≥24h. گپ در openِ همان
کندل معلوم است؛ سیگنال روی همان کندل گذاشته می‌شود و se.simulate_trades در
openِ کندلِ بعدی پر می‌کند ⇒ یک کندل تأخیر محافظه‌کارانه، صفر look-ahead.

قواعد صفر (درس S434):
  - جای‌گشت با تعدادِ معاملاتِ «لایه‌ی نهایی پس از آستانه» ساخته می‌شود، نه پایه.
  - کنترل همان SL/TP/max_hold/allow_overlap را دارد؛ فقط جهت تصادفی است.
  - استخر جای‌گشت فقط کندل‌های واجد (رخدادهای بازگشایی گذرکرده از آستانه) است.
  - خط مبنا = max(uncond_wr, perm_mean) به‌ازای هر سمت (محافظه‌کاری _side_null_ref).

نکته‌ی صداقتی (پیش از دیدن نتیجه نوشته شد): اگر لیفت هولد‌اوت < 4pp یا
z < 3.09 شود، حکم موتور عیناً گزارش می‌شود — REJECT/UNPROVEN/POWER-LIMITED
دست‌کاری یا بازتفسیر نمی‌شود. مسیر رسمی احیای POWER-LIMITED فقط rqs2_pool است.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s810')
os.makedirs(OUT_DIR, exist_ok=True)

SPLIT_EPOCH = 1546300800          # 2019-01-01 00:00 UTC — از پیش‌ثبت
WEEKEND_SEC = 24 * 3600           # وقفه‌ی ≥24h = رخداد بازگشایی هفتگی
SEED = 810
N_PERM = 500                      # K ≥ 500 طبق پیش‌ثبت (H3: perm_k>=500)

# ---- فضای جست‌وجوی قفل‌شده (عیناً از پیش‌ثبت؛ تغییر = هولد‌اوت سوخته) ----
GAP_THR_USD = [0.5, 1.0, 2.0, 3.0, 5.0]
LOGICS      = ['fill', 'cont']            # فیل: خلاف گپ | ادامه: هم‌جهت گپ
SL_PIPS     = [30, 50, 80]
RRS         = [1.0, 1.5, 2.0]             # TP = RR*SL ، قید TP>=SL
MAX_HOLDS   = [240, 480, 960]              # کندل M1


def load_m1():
    d = fd.load_fast('XAUUSD', 'M1')
    df = fd.as_dataframe(d)
    return d, df


def weekend_events(df: pd.DataFrame):
    """اندیس کندل بازگشایی (rb) و گپ دلاری open[rb]-close[rb-1]."""
    t = df['time'].values.astype(np.int64)
    dt = np.diff(t)
    brk = np.where(dt >= WEEKEND_SEC)[0]
    rb = brk + 1
    gap = df['open'].values[rb] - df['close'].values[rb - 1]
    return rb, gap


def build_signals(n: int, rb: np.ndarray, gap: np.ndarray,
                  thr_usd: float, logic: str):
    """سیگنال روی خودِ کندل بازگشایی ⇒ ورود در open کندل بعد (forward-safe)."""
    long_sig = np.zeros(n, bool)
    short_sig = np.zeros(n, bool)
    m = np.abs(gap) >= thr_usd
    ev, g = rb[m], gap[m]
    if logic == 'fill':      # انتظار پرشدن گپ: گپ بالا ⇒ short، گپ پایین ⇒ long
        short_sig[ev[g > 0]] = True
        long_sig[ev[g < 0]] = True
    else:                    # ادامه: هم‌جهت گپ
        long_sig[ev[g > 0]] = True
        short_sig[ev[g < 0]] = True
    return long_sig, short_sig


def run_combo(df, rb, gap, thr, logic, sl, rr, mh):
    ls, ss = build_signals(len(df), rb, gap, thr, logic)
    tp = sl * rr
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl, tp_pip=tp,
                            asset='XAUUSD', max_hold=mh, allow_overlap=False)
    return tr, tp


def wr_pct(tr) -> float | None:
    if tr is None or len(tr) == 0:
        return None
    return float((tr['outcome'].values == 'win').mean() * 100.0)


# ============================ فاز ۱: جست‌وجو ============================

def phase_search(df, rb, gap, split_idx):
    """۲۷۰ ترکیب فقط روی نیمه‌ی اول. غربالِ جای‌گشتیِ ارزان (K=12) برای رتبه‌بندی.
    هیچ حکمی از این فاز صادر نمی‌شود."""
    rng = np.random.default_rng(SEED)
    first = rb[df['time'].values[rb] < SPLIT_EPOCH]
    gap_first = gap[df['time'].values[rb] < SPLIT_EPOCH]
    print(f'[search] first-half events: {len(first)}')

    rows = []
    combo_id = 0
    for thr in GAP_THR_USD:
        m = np.abs(gap_first) >= thr
        ev, g = first[m], gap_first[m]
        for logic in LOGICS:
            for sl in SL_PIPS:
                for rr in RRS:
                    tp = sl * rr
                    for mh in MAX_HOLDS:
                        combo_id += 1
                        ls = np.zeros(len(df), bool)
                        ss = np.zeros(len(df), bool)
                        if logic == 'fill':
                            ss[ev[g > 0]] = True; ls[ev[g < 0]] = True
                        else:
                            ls[ev[g > 0]] = True; ss[ev[g < 0]] = True
                        tr = se.simulate_trades(df, ls, ss, sl_pip=sl, tp_pip=tp,
                                                asset='XAUUSD', max_hold=mh,
                                                allow_overlap=False)
                        w = wr_pct(tr)
                        n = 0 if tr is None else len(tr)
                        # غربال جای‌گشتی ارزان: جهت تصادفی روی همان رخدادها
                        z = lift = None
                        if n >= 100 and w is not None:
                            perm_wrs = []
                            for _ in range(12):
                                flip = rng.random(len(df)) < 0.5
                                pls = (ls | ss) & flip
                                pss = (ls | ss) & ~flip
                                ptr = se.simulate_trades(
                                    df, pls, pss, sl_pip=sl, tp_pip=tp,
                                    asset='XAUUSD', max_hold=mh,
                                    allow_overlap=False)
                                pw = wr_pct(ptr)
                                if pw is not None:
                                    perm_wrs.append(pw)
                            if len(perm_wrs) >= 8:
                                pm, psd = float(np.mean(perm_wrs)), float(np.std(perm_wrs) + 1e-9)
                                lift = w - pm
                                z = lift / psd
                        pnl = float(tr['pnl_pip'].sum()) if n else 0.0
                        rows.append(dict(combo=combo_id, thr=thr, logic=logic,
                                         sl=sl, rr=rr, tp=tp, mh=mh, n=n,
                                         wr=w, lift=lift, z=z, pnl_pip=pnl))
                        if combo_id % 27 == 0:
                            print(f'  ... {combo_id}/270 done', flush=True)
                            with open(os.path.join(OUT_DIR, 'search_first_half.json'), 'w') as f:
                                json.dump(rows, f, indent=1)
    with open(os.path.join(OUT_DIR, 'search_first_half.json'), 'w') as f:
        json.dump(rows, f, indent=1)
    # برنده: بیشینه‌ی z میان ترکیب‌های n>=100 و lift>0 (معیارِ اعلام‌شده)
    cand = [r for r in rows if r['z'] is not None and r['lift'] and r['lift'] > 0]
    cand.sort(key=lambda r: r['z'], reverse=True)
    winner = cand[0] if cand else None
    with open(os.path.join(OUT_DIR, 'winner.json'), 'w') as f:
        json.dump(winner, f, indent=1)
    print('[search] WINNER:', winner)
    return winner


# ============================ فاز ۲: مدل صفر ============================

def phase_null(df, rb, gap, winner):
    """صفر سنجیده روی رخدادهای نیمه‌ی دوم برای پیکربندی برنده. K=500.
    کانونی: {'long': {uncond_wr, perm_mean, perm_sd, perm_max, perm_k}, 'short': …}"""
    rng = np.random.default_rng(SEED + 1)
    t = df['time'].values
    second = t[rb] >= SPLIT_EPOCH
    m = np.abs(gap) >= winner['thr']
    ev = rb[second & m]
    g = gap[second & m]
    print(f'[null] second-half qualified events: {len(ev)}')

    sl, tp, mh = winner['sl'], winner['tp'], winner['mh']

    # جهت‌های لایه‌ی واقعی برای شمارش n به‌ازای هر سمت
    if winner['logic'] == 'fill':
        n_long = int((g < 0).sum()); n_short = int((g > 0).sum())
    else:
        n_long = int((g > 0).sum()); n_short = int((g < 0).sum())

    out = {}
    for side, n_side in (('long', n_long), ('short', n_short)):
        # بی‌قید: ورود به این سمت در «همه‌ی» رخدادهای واجد
        sig = np.zeros(len(df), bool); sig[ev] = True
        z0 = np.zeros(len(df), bool)
        tr = se.simulate_trades(df, sig if side == 'long' else z0,
                                z0 if side == 'long' else sig,
                                sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                                max_hold=mh, allow_overlap=False)
        uncond = wr_pct(tr)
        # جای‌گشت: n_side رخداد تصادفی از استخر واجد، K بار
        perm = []
        k_eff = 0
        if n_side > 0 and len(ev) >= n_side:
            for _ in range(N_PERM):
                pick = rng.choice(ev, size=n_side, replace=False)
                sig = np.zeros(len(df), bool); sig[pick] = True
                ptr = se.simulate_trades(df, sig if side == 'long' else z0,
                                         z0 if side == 'long' else sig,
                                         sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                                         max_hold=mh, allow_overlap=False)
                pw = wr_pct(ptr)
                if pw is not None:
                    perm.append(pw)
                k_eff += 1
                if k_eff % 50 == 0:
                    print(f'  [null:{side}] perm {k_eff}/{N_PERM}', flush=True)
        out[side] = dict(
            uncond_wr=uncond,
            perm_mean=float(np.mean(perm)) if perm else None,
            perm_sd=float(np.std(perm)) if perm else None,
            perm_max=float(np.max(perm)) if perm else None,
            perm_k=len(perm),
            n_side=n_side,
        )
        print(f'[null] {side}: {out[side]}')
    with open(os.path.join(OUT_DIR, 'null_holdout.json'), 'w') as f:
        json.dump(out, f, indent=1)
    return out


# ============================ فاز ۳: داوری ============================

def phase_judge(df, rb, gap, winner, null):
    """یک (۱) آزمون روی نیمه‌ی محافظت‌شده. n_trials=1 طبق مسیر C."""
    lock = os.path.join(OUT_DIR, 'HOLDOUT_SPENT.lock')
    if os.path.exists(lock):
        print('⛔ هولد‌اوت قبلاً مصرف شده — آزمون دوم ممنوع است (مسیر C).')
        return None
    split_idx = int(np.searchsorted(df['time'].values, SPLIT_EPOCH))
    ls, ss = build_signals(len(df), rb, gap, winner['thr'], winner['logic'])
    tr = se.simulate_trades(df, ls, ss, sl_pip=winner['sl'], tp_pip=winner['tp'],
                            asset='XAUUSD', max_hold=winner['mh'],
                            allow_overlap=False)
    # فقط معاملات هولد‌اوت داوری می‌شوند؛ split_bar به موتور داده می‌شود تا H7 هم بسنجد
    hold = tr[tr['entry_bar'].values >= split_idx].reset_index(drop=True)
    print(f'[judge] holdout trades: {len(hold)} (total {len(tr)})')
    nb = {s: {k: v for k, v in null[s].items() if k != 'n_side'} for s in ('long', 'short')}
    r = rqs2.compute_rqs2(
        hold, 'XAUUSD',
        sl_pip=winner['sl'], tp_pip=winner['tp'],
        bar_time=df['time'].values, null=nb, n_trials=1,
        split_bar=split_idx, close=df['close'].values)
    with open(lock, 'w') as f:
        f.write('holdout spent — one test only (path C)\n')
    res = dict(winner=winner, verdict=r['verdict'], score=r['rqs2_score'],
               gates=r['gates'], metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                                          for k, v in r['metrics'].items()},
               notes=r['notes'])
    with open(os.path.join(OUT_DIR, 'judgment_m1.json'), 'w') as f:
        json.dump(res, f, indent=1, default=str)
    print(rqs2.format_rqs2(r))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--search', action='store_true')
    ap.add_argument('--null', action='store_true')
    ap.add_argument('--judge', action='store_true')
    a = ap.parse_args()

    d, df = load_m1()
    print('src:', d['src'])
    rb, gap = weekend_events(df)
    split_idx = int(np.searchsorted(df['time'].values, SPLIT_EPOCH))
    print(f'events total={len(rb)}  split_idx={split_idx}')

    if a.search:
        phase_search(df, rb, gap, split_idx)
    if a.null:
        with open(os.path.join(OUT_DIR, 'winner.json')) as f:
            winner = json.load(f)
        phase_null(df, rb, gap, winner)
    if a.judge:
        with open(os.path.join(OUT_DIR, 'winner.json')) as f:
            winner = json.load(f)
        with open(os.path.join(OUT_DIR, 'null_holdout.json')) as f:
            null = json.load(f)
        phase_judge(df, rb, gap, winner, null)


if __name__ == '__main__':
    main()
