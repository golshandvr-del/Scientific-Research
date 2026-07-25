# -*- coding: utf-8 -*-
"""
S322 — کشفِ لایهٔ جدید: Ichimoku Kumo Trend-Pullback (اندیکاتورِ کاملاً بکر، ۰ استفادهٔ قبلی)
================================================================================
مرجع علمی: Goichi Hosoda (一目均衡表, 1969) — سیستمِ «تعادلِ یک-نگاهی».

منطقِ لایه (رویداد-محور):
  روندِ صعودیِ تأییدشده = close بالای ابر (Kumo) + ابرِ آینده صعودی (span_a_fut>span_b_fut)
  رویدادِ ورودِ LONG    = تقاطعِ Tenkan رو به بالای Kijun (tk_cross_up) هنگام pullback به Kijun
  → «buy the Kijun-bounce in an above-cloud uptrend» — کلاسیکِ Ichimoku.

بهبودهای شناور (قانونِ همه‌چیز شناور + بی‌نهایت):
  B1) عمقِ pullback به Kijun (kijun_atr_max)        — فاصلهٔ مجازِ قیمت تا Kijun
  B2) فیلترِ ضخامتِ ابر (cloud_thick_min، بر ATR)   — رژیم: ابرِ ضخیم = حمایتِ قوی
  B3) فیلترِ RSI                                     — حذفِ ورودِ اشباعِ خرید
  B4) شیبِ Kijun (kijun_slope_min، بر ATR)          — روندِ واقعیِ رو به بالا
  B5) TP/SL نامتقارن بر حسبِ ATR (غیر-رند)
  B6) دوطرفه (long+short، متقارن) — در صورتِ نیاز برای عبور از walk-forward

⚠️ همه forward-safe (ابرِ i از دادهٔ i-26). واحدها: ATR→pip با تقسیم بر pip.
"""
import sys; sys.path.insert(0, '.')
import numpy as np
import itertools
from engine import scalp_engine as se
from engine import indicators as ind
from engine import ichimoku as ich
from engine import rqs

PIP = se.ASSETS['XAUUSD']['pip']


def build_features(df):
    s = ich.cloud_signals(df)
    c = df['close'].values.astype(np.float64)
    atr = ind.atr(df, 14).values
    atr_pip = atr / PIP
    a = np.where(atr > 0, atr, np.nan)
    rsi_ = ind.rsi(df['close'], 14).values

    dist_kijun = (c - s['kijun']) / a
    # شیبِ Kijun بر حسبِ ATR (lookback=5)
    kij = s['kijun']
    kslope = np.full(len(df), np.nan)
    kslope[5:] = (kij[5:] - kij[:-5]) / a[5:]
    cloud_thick_atr = s['cloud_thickness'] / a

    tk_diff = s['tenkan'] - s['kijun']
    tk_cross_up = (tk_diff > 0) & (np.r_[True, tk_diff[:-1] <= 0])
    tk_cross_dn = (tk_diff < 0) & (np.r_[True, tk_diff[:-1] >= 0])

    # بهبودهای کیفیتِ کاشف‌شده (کلیدِ عبور از walk-forward):
    tk_gap = (s['tenkan'] - s['kijun']) / a            # B7) پهنای مومنتوم بر ATR
    dist_above = (c - s['cloud_top']) / a              # B8) جدایی قیمت از سقفِ ابر بر ATR
    dist_below = (s['cloud_bot'] - c) / a              # قرینه برای short

    return dict(
        close=c, atr_pip=atr_pip, rsi=rsi_,
        above_cloud=s['above_cloud'], below_cloud=s['below_cloud'],
        cloud_bull_fut=s['cloud_bull_fut'], cloud_bear_fut=s['cloud_bear_fut'],
        dist_kijun=np.nan_to_num(dist_kijun, nan=99),
        kslope=np.nan_to_num(kslope, nan=0.0),
        cloud_thick_atr=np.nan_to_num(cloud_thick_atr, nan=0.0),
        tk_cross_up=tk_cross_up, tk_cross_dn=tk_cross_dn,
        tk_gap=np.nan_to_num(tk_gap, nan=0.0),
        dist_above=np.nan_to_num(dist_above, nan=-99),
        dist_below=np.nan_to_num(dist_below, nan=-99),
    )


def make_signals(f, cfg, side):
    n = len(f['close'])
    trend_up = f['above_cloud'] & f['cloud_bull_fut']
    trend_dn = f['below_cloud'] & f['cloud_bear_fut']

    common_ok = (f['cloud_thick_atr'] >= cfg['thick_min'])

    long_sig = np.zeros(n, bool)
    short_sig = np.zeros(n, bool)

    gap_min = cfg.get('gap_min', 0.0)
    da_min = cfg.get('da_min', 0.0)

    if side in ('long', 'both'):
        long_sig = (trend_up & f['tk_cross_up'] & common_ok
                    & (f['dist_kijun'] >= -0.2) & (f['dist_kijun'] <= cfg['kijun_atr_max'])
                    & (f['kslope'] >= cfg['kslope_min'])
                    & (f['tk_gap'] >= gap_min) & (f['dist_above'] >= da_min)
                    & (f['rsi'] >= cfg['rsi_min']) & (f['rsi'] <= cfg['rsi_max']))
    if side in ('short', 'both'):
        short_sig = (trend_dn & f['tk_cross_dn'] & common_ok
                     & (f['dist_kijun'] <= 0.2) & (f['dist_kijun'] >= -cfg['kijun_atr_max'])
                     & (f['kslope'] <= -cfg['kslope_min'])
                     & (-f['tk_gap'] >= gap_min) & (f['dist_below'] >= da_min)
                     & (f['rsi'] <= 100 - cfg['rsi_min']) & (f['rsi'] >= 100 - cfg['rsi_max']))

    sl_pip = np.clip(cfg['sl_mult'] * f['atr_pip'], 5.0, None)
    tp_pip = np.clip(cfg['tp_mult'] * f['atr_pip'], 5.0, None)
    return long_sig, short_sig, sl_pip, tp_pip


def lite_stats(tr):
    if len(tr) == 0:
        return 0, 0, 0, 0
    pnl = tr['pnl_pip'].values
    wr = (pnl > 0).mean() * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 9.0
    return len(tr), wr, pf, pnl.sum()


GRID = dict(
    kijun_atr_max=[0.8, 1.2, 1.8],
    thick_min=[0.0, 0.3],
    kslope_min=[0.0, 0.15],
    rsi_min=[40, 45],
    rsi_max=[80, 90],
    sl_mult=[2.2, 2.6, 3.0],
    tp_mult=[2.4, 2.9, 3.6],
)


def main():
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M15'
    side = sys.argv[2] if len(sys.argv) > 2 else 'long'
    max_hold = int(sys.argv[3]) if len(sys.argv) > 3 else 36
    df = se.load_data(f'data/XAUUSD_{tf}.csv')
    f = build_features(df)
    print(f'[XAUUSD {tf}] rows={len(df)} side={side} mh={max_hold}')

    import time; t0 = time.time()
    keys = list(GRID.keys())
    res = []
    for combo in itertools.product(*[GRID[k] for k in keys]):
        if time.time() - t0 > 90:
            print('time budget hit'); break
        cfg = dict(zip(keys, combo))
        if cfg['tp_mult'] <= cfg['sl_mult'] - 0.6:
            continue
        ls, ss, sl, tp = make_signals(f, cfg, side)
        tr = se.simulate_trades(df, ls, ss, sl, tp, 'XAUUSD',
                                max_hold=max_hold, allow_overlap=False)
        n, wr, pf, net = lite_stats(tr)
        if n >= 40 and wr >= 58 and pf >= 1.25:
            sig = ls | ss
            med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
            r = rqs.compute_rqs(tr, 'XAUUSD',
                                sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
            res.append((r['rqs_score'], r['passed'], cfg, r['metrics'], r['gates']))

    res.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print(f'candidates (WR>=58 & PF>=1.25): {len(res)}  ({time.time()-t0:.0f}s)')
    print('=' * 118)
    for score, passed, cfg, m, g in res[:15]:
        gl = ''.join('1' if g[k] else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f'RQS={score:5.1f} {"PASS" if passed else "FAIL"} G[{gl}] '
              f'n={m["n_trades"]:3d} WR={m["win_rate"]:4.1f} PF={m["profit_factor"]:.2f} '
              f'DD={m["max_dd_pct"]:.1f} MCL={m["max_consec_losses"]} p={m["p_value"]:.3f} '
              f'net={m["net_profit"]:.0f} wf={[round(x) for x in m["wf_nets"]]} | '
              f'kmax{cfg["kijun_atr_max"]} th{cfg["thick_min"]} ks{cfg["kslope_min"]} '
              f'rsi{cfg["rsi_min"]}-{cfg["rsi_max"]} sl{cfg["sl_mult"]}tp{cfg["tp_mult"]}')
    if not res:
        print('NONE passed lite screen')


if __name__ == '__main__':
    main()
