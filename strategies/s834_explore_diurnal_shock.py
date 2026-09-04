# -*- coding: utf-8 -*-
"""
S834 — کاوشِ ۱: شوکِ دامنه‌ی نرمال‌شده به ساعتِ روز (Diurnal-Normalized Range Shock) — فقط ۶۰٪ اکتشاف
=========================================================================================================
فرضیه: بازارِ طلا فصلیتِ درون‌روزیِ قویِ نوسان دارد (ساعت ۲۳..۷ سرور آرام، ۱۴..۱۸ فعال).
یک کندل با دامنه‌ی k× «دامنه‌ی معمولِ همان ساعت» رخدادِ اطلاعاتی است، حتی اگر نسبت به ATR
معمولی باشد. ATR/GARCH/BV (S840/S950/S965) کورِ ساعت‌اند — قلمروِ بکر (سرشماری: صفر مورد).

ویژگی: dnr_t = range_t / median{ range_s : hour(s)=hour(t), s در ۶۰ روزِ گذشته }  (causal)
کنترل: atr_t = range_t / ATR34[t-1]  — همان k، همان هندسه ⇒ آیا hour-norm اطلاعات می‌افزاید؟
جهت: follow = علامتِ body (درون‌زاد، آینه‌ای)؛ fade = مخالف (بررسیِ پادتقارن).
سنجه: INFO-lift = WR − WRِ نالِ جای‌گشتیِ جهت با همان هندسه (درس S832)، K=100.
رژیم: سه بلوکِ واقعی R1(<2013 گاو) R2(2013-15 خرس) R3(2016-20 رنج) — درس S833.
هندسه‌ی ساده: SL=2×ATR34، TP=1.3×SL، hold=21، بدون trail/BE.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

WARMUP = 1500          # ~۶۰ روز H1 برای پنجره‌ی ساعتی
K_NULL = 100
SEED = 834001
SLM, RR, HOLD = 2.0, 1.3, 21
LOOKBACK_DAYS = 60
R1_END = 1356998400    # 2013-01-01
R2_END = 1451606400    # 2016-01-01


def pf_of(p):
    w = p[p > 0].sum(); lo_ = -p[p < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf


def info_null(df, sig_bars, slp, tpp, hold, rng):
    wrs = []
    for _ in range(K_NULL):
        dirs = rng.integers(0, 2, size=len(sig_bars)).astype(bool)
        lm = np.zeros(len(df), bool); lm[sig_bars[dirs]] = True
        sm = np.zeros(len(df), bool); sm[sig_bars[~dirs]] = True
        t = se.simulate_trades(df, lm, sm, sl_pip=slp, tp_pip=tpp, asset='XAUUSD',
                               max_hold=hold, allow_overlap=False)
        if len(t):
            wrs.append((t['pnl_pip'].values > 0).mean() * 100)
    return float(np.mean(wrs)), float(np.std(wrs))


for TF, bars_per_day in (('H1', 24), ('H2', 12), ('H3', 8)):
    d = fd.load_fast('XAUUSD', TF)
    assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
    df_full = fd.as_dataframe(d)
    split = int(len(df_full) * 0.6)
    df = df_full.iloc[:split].reset_index(drop=True)
    t = df['time'].values.astype(np.int64)
    o = df['open'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(df)
    hour = (t // 3600) % 24
    rng_ = h - l
    body = c - o

    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.empty_like(tr); atr[0] = tr[0]; a = 1 / 34
    for i in range(1, n):
        atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
    atr_prev = np.concatenate([[atr[0]], atr[:-1]])
    atr_pip = atr / se.ASSETS['XAUUSD']['pip']
    slp = np.clip(atr_pip * SLM, 8, 5000); tpp = slp * RR

    # میانه‌ی causal دامنه‌ی همان ساعت در LOOKBACK_DAYS روزِ گذشته
    dnr = np.full(n, np.nan)
    for hr in np.unique(hour):
        idx = np.where(hour == hr)[0]
        r = rng_[idx]
        for j in range(LOOKBACK_DAYS, len(idx)):
            med = np.median(r[j - LOOKBACK_DAYS:j])
            if med > 0:
                dnr[idx[j]] = r[j] / med
    atrn = np.where(atr_prev > 0, rng_ / atr_prev, np.nan)

    warm = max(WARMUP // (24 // bars_per_day), 400)
    R1 = t < R1_END; R2 = (t >= R1_END) & (t < R2_END); R3 = t >= R2_END
    print(f'\n################ TF={TF} explore bars={n:,} src={d["src"]} '
          f'| R1={int(R1.sum())} R2={int(R2.sum())} R3={int(R3.sum())} ################', flush=True)
    rng = np.random.default_rng(SEED + bars_per_day)

    for feat_name, feat in (('DNR', dnr), ('ATRn', atrn)):
        for k in (2.0, 2.618, 3.5):
            x = (feat > k) & (body != 0)
            x[:warm] = False
            for mode in ('follow', 'fade'):
                if mode == 'follow':
                    ls = x & (body > 0); ss = x & (body < 0)
                else:
                    ls = x & (body < 0); ss = x & (body > 0)
                tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp, asset='XAUUSD',
                                         max_hold=HOLD, allow_overlap=False)
                if len(tdf) < 80:
                    print(f'  {feat_name} k={k} {mode}: n={len(tdf)} — کم، رد', flush=True)
                    continue
                pnl = tdf['pnl_pip'].values
                eb = tdf['entry_bar'].values
                sb = tdf['signal_bar'].values.astype(int)
                wr = (pnl > 0).mean() * 100
                if mode == 'follow':
                    nm, nsd = info_null(df, sb, slp, tpp, HOLD, rng)
                    null_cache = (nm, nsd)
                else:
                    nm, nsd = null_cache      # همان کندل‌ها ⇒ همان نال
                lift = wr - nm; z = lift / nsd if nsd > 0 else 0
                pw = lift * np.sqrt(len(pnl))
                te = t[eb]
                def wr_of(m):
                    return (pnl[m] > 0).mean() * 100 - nm if m.sum() >= 15 else np.nan
                l1, l2, l3 = wr_of(te < R1_END), wr_of((te >= R1_END) & (te < R2_END)), wr_of(te >= R2_END)
                flag = ' <<<' if (lift >= 4 and z >= 2 and min(l1, l2, l3) > 0) else ''
                print(f'  {feat_name:4s} k={k:5.3f} {mode:6s}: n={len(pnl):5,} WR={wr:5.2f}% '
                      f'null={nm:5.2f}%±{nsd:.2f} INFOlift={lift:+6.2f}pp z={z:+4.1f} pw={pw:5.0f} '
                      f'PF={pf_of(pnl):.3f} exp={pnl.mean():+6.2f} '
                      f'[R1={l1:+5.1f} R2={l2:+5.1f} R3={l3:+5.1f}]{flag}', flush=True)

print('\n[S834 explore-1 complete]', flush=True)
