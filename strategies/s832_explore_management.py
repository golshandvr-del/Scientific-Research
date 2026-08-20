# -*- coding: utf-8 -*-
"""
S832 — کاوشِ ۳: مدیریت معامله + پنجره‌ی سنجیده — XAUUSD-H1 (فقط ۶۰٪ اکتشاف)
==============================================================================
پرسش: آیا PF=1.055 (سلول پایدار کاوش ۲) با یکی از این دو راه به ≥1.3 می‌رسد؟
  (الف) مدیریت معامله: be_trigger (SL→ورود پس از سود x×SL) و/یا trail (y×ATR)
  (ب) بازتعریف رنج آرام از سرشماری واقعی: ساعات 22..6 (wrap) به‌جای فرض 0..6

پایه: سلول برنده‌ی کاوش ۲ و همسایه‌هایش:
  slm ∈ {1.4, 2.1}, rr ∈ {2.0, 3.4}, hold=21
مدیریت: be ∈ {None, 0.5, 1.0}×SL  ×  trail ∈ {None, 1.0, 2.1}×ATR
گزارش: n, WR, lift, exp, PF کل + [E1, E2].
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SPLIT_IDX = 54798
WARMUP = 600
HALF = SPLIT_IDX // 2

d = fd.load_fast('XAUUSD', 'H1')
df = fd.as_dataframe(d).iloc[:SPLIT_IDX].reset_index(drop=True)
t = df['time'].values.astype(np.int64)
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64)
l = df['low'].values.astype(np.float64)
hour = (t // 3600) % 24
day = t // 86400
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr = np.empty_like(tr); atr[0] = tr[0]
a = 1.0 / 34
for i in range(1, len(tr)):
    atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
atr_pip = atr / se.ASSETS['XAUUSD']['pip']
n = len(df)

def build_signals(range_mode):
    """range_mode='asia' → ساعات 0..6 همان روز؛ 'quiet' → 22 دیروز تا 6 امروز (wrap)."""
    rhi = np.full(n, np.nan); rlo = np.full(n, np.nan)
    uniq_days = np.unique(day)
    for dd in uniq_days:
        if range_mode == 'asia':
            m = (day == dd) & (hour <= 6)
            need = 5
        else:  # quiet: 22,23 دیروز + 0..6 امروز
            m = ((day == dd - 1) & (hour >= 22)) | ((day == dd) & (hour <= 6))
            need = 6
        if m.sum() < need:
            continue
        md = (day == dd) & (hour >= 7)
        rhi[md] = h[m].max(); rlo[md] = l[m].min()
    in_win = (hour >= 7) & (hour <= 16)
    brk_up = in_win & np.isfinite(rhi) & (c > rhi)
    brk_dn = in_win & np.isfinite(rlo) & (c < rlo)
    first = np.zeros(n, bool)
    seen = set()
    for i in range(n):
        if (brk_up[i] or brk_dn[i]) and day[i] not in seen:
            first[i] = True
            seen.add(day[i])
    ls = first & brk_up
    ss = first & brk_dn & ~ls
    ls[:WARMUP] = False; ss[:WARMUP] = False
    return ls, ss

def pf_of(pnl):
    w = pnl[pnl > 0].sum(); lo_ = -pnl[pnl < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf

print(f'explore bars={n:,}  src={d["src"]}', flush=True)
MED_ATR = float(np.median(atr_pip[WARMUP:]))
print(f'median ATR34 = {MED_ATR:.1f} pip (мبنای اسکالر مدیریت)', flush=True)

HOLD = 21
for range_mode in ('asia', 'quiet'):
    ls, ss = build_signals(range_mode)
    print(f'\n########## range={range_mode}  (L={int(ls.sum())} S={int(ss.sum())}) ##########', flush=True)
    for slm in (1.4, 2.1):
        slp = np.clip(atr_pip * slm, 8, 5000)
        for rr in (2.0, 3.4):
            tpp = slp * rr
            for be_f in (None, 0.5, 1.0):
                for tr_f in (None, 1.0, 2.1):
                    # موتور فقط اسکالر می‌پذیرد (درس S830) — مبنا: میانه‌ی ATR
                    be_arr = None if be_f is None else float(MED_ATR * slm * be_f)
                    tr_arr = None if tr_f is None else float(MED_ATR * tr_f)
                    tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp,
                                             asset='XAUUSD', max_hold=HOLD,
                                             allow_overlap=False,
                                             be_trigger_pip=be_arr, trail_pip=tr_arr)
                    if len(tdf) < 60:
                        continue
                    pnl = tdf['pnl_pip'].values
                    eb = tdf['entry_bar'].values
                    wr = float((pnl > 0).mean() * 100)
                    med_sl = float(np.median(tdf['sl_pip']))
                    be_cost = (med_sl + 3.3) / (med_sl + med_sl * rr) * 100
                    pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
                    tag_be = '-' if be_f is None else f'{be_f}'
                    tag_tr = '-' if tr_f is None else f'{tr_f}'
                    print(f'  slm={slm} rr={rr} be={tag_be:>3} trail={tag_tr:>3}: '
                          f'n={len(tdf):5,} WR={wr:5.2f}% lift={wr-be_cost:+6.2f}pp '
                          f'exp={float(pnl.mean()):+7.2f}pip PF={pf:.3f} '
                          f'[E1={pf1:.3f} E2={pf2:.3f}]', flush=True)

print('\n[S832 explore-3 complete]', flush=True)
