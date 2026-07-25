# -*- coding: utf-8 -*-
"""
S321g — احیای S52 MA-Ribbon روی XAUUSD M30: افزودنِ فیلترِ رژیمِ ADX (B6)
================================================================================
یافتهٔ کلیدیِ S321f (نگاشتِ زمانیِ walk-forward روی داده‌ی ۲۰۱۱–۲۰۲۶):
  W1 2011-2016 +259 | W2 2016-2020 -213 | W3 2020-2023 +134 | W4 2023-2026 +1729
تنها پنجرهٔ منفی = W2 (۲۰۱۶–۲۰۲۰) = رنجِ بلندمدتِ تاریخیِ طلا (۱۱۰۰–۱۳۵۰$).
مانعِ نهاییِ RQS = G4 (walk-forward) که به‌خاطرِ همین پنجرهٔ رنج رد می‌شود.

فرضیهٔ علمی (Wilder 1978 — ADX برای تفکیکِ روند از رنج طراحی شد):
  فیلترِ ADX≥thr معاملاتِ دورهٔ رنج (W2) را حذف می‌کند ⇒ W2 از منفی به خنثی/مثبت،
  ⇒ G4 پاس، هم‌زمان DD↓ و WR↑. عرضِ ریبون (wz) کافی نبود چون رنج هم می‌تواند
  عرض را باز کند؛ ADX «قدرتِ جهت‌دارِ روند» را مستقل می‌سنجد.

بهبودها (قانونِ همکاریِ بهبود + همه‌چیز شناور): B5 شیبِ ریبون + B6 رژیمِ ADX.
اجرا: python3 strategies/s321g_ribbon_m30_adx.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import itertools

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs

RIBBON_PERIODS = [8, 13, 21, 34, 55, 89, 144]
MID_PERIOD = 34


def build_features(df, pip):
    c = df['close']
    atr_ = ind.atr(df, 14)
    rsi_ = ind.rsi(c, 14)
    adx_ = ind.adx(df, 14)
    if isinstance(adx_, tuple):
        adx_ = adx_[0]
    adx_v = adx_.values if hasattr(adx_, 'values') else np.asarray(adx_)
    emas = [ind.ema(c, p) for p in RIBBON_PERIODS]
    E = np.column_stack([e.values for e in emas])
    top = np.nanmax(E, axis=1); bot = np.nanmin(E, axis=1)
    price = c.values
    asc = np.zeros(len(df)); pairs = 0
    for k in range(len(RIBBON_PERIODS) - 1):
        asc += (E[:, k] > E[:, k + 1]).astype(float); pairs += 1
    rib_order = 2 * (asc / pairs) - 1
    spread = (top - bot) / np.where(price != 0, price, np.nan)
    sp = pd.Series(spread)
    rib_width_z = np.nan_to_num(((sp - sp.rolling(200).mean()) /
                   (sp.rolling(200).std() + 1e-12)).values, nan=-9.0)
    band = (top - bot)
    pos_in_rib = np.where(band > 1e-9, (price - bot) / band, 0.5)
    atrv = atr_.values
    mid = ind.ema(c, MID_PERIOD).values
    slope5 = np.full(len(df), np.nan)
    slope5[5:] = (mid[5:] - mid[:-5]) / 5.0
    rib_slope = slope5 / np.where(atrv != 0, atrv, np.nan)
    return dict(close=price, open=df['open'].values, atr_pip=atrv / pip,
                rib_order=rib_order, rib_width_z=rib_width_z, pos_in_rib=pos_in_rib,
                rsi=rsi_.values, rib_slope=np.nan_to_num(rib_slope, nan=0.0),
                adx=np.nan_to_num(adx_v, nan=0.0))


def make_signals(feats, cfg, side):
    close = feats['close']; opn = feats['open']
    order = feats['rib_order']; wz = feats['rib_width_z']; pos = feats['pos_in_rib']
    rsi_ = feats['rsi']; atr_pip = feats['atr_pip']; slope = feats['rib_slope']; adx = feats['adx']
    bull = close > opn; bear = close < opn
    open_regime = wz >= cfg['wz_gate']
    adx_ok = adx >= cfg['adx_min']            # B6: رژیمِ روندِ قوی
    rsi_ok_l = (rsi_ >= cfg['rsi_min']) & (rsi_ <= cfg['rsi_max'])
    rsi_ok_s = (rsi_ <= (100 - cfg['rsi_min'])) & (rsi_ >= (100 - cfg['rsi_max']))
    slope_ok_l = slope >= cfg['slope_min']
    slope_ok_s = slope <= -cfg['slope_min']
    long_ok = ((order >= cfg['ord_thr']) & open_regime & adx_ok & bull & rsi_ok_l & slope_ok_l &
               (pos >= cfg['pull_min']) & (pos <= cfg['pull_max']))
    short_ok = ((order <= -cfg['ord_thr']) & open_regime & adx_ok & bear & rsi_ok_s & slope_ok_s &
                (pos >= (1 - cfg['pull_max'])) & (pos <= (1 - cfg['pull_min'])))
    if side == 'long':
        short_ok = np.zeros_like(short_ok, dtype=bool)
    elif side == 'short':
        long_ok = np.zeros_like(long_ok, dtype=bool)
    long_sig = np.nan_to_num(long_ok, nan=0).astype(bool)
    short_sig = np.nan_to_num(short_ok, nan=0).astype(bool)
    sl_pip = np.clip(np.nan_to_num(cfg['sl_mult'] * atr_pip, nan=0.0), 5.0, None)
    tp_pip = np.clip(np.nan_to_num(cfg['tp_mult'] * atr_pip, nan=0.0), 5.0, None)
    return long_sig, short_sig, sl_pip, tp_pip


def lite_stats(trades):
    n = len(trades)
    if n == 0:
        return 0, 0, 0, 0
    pnl = trades['pnl_pip'].values
    wr = (pnl > 0).sum() / n * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 999
    return n, wr, pf, pnl.sum()


def main():
    asset = 'XAUUSD'; tf = 'M30'; side = 'long'
    pip = se.ASSETS[asset]['pip']
    df = se.load_data(f'data/{asset}_{tf}.csv')
    print(f"[{asset} {tf}] rows={len(df)} side={side}")
    feats = build_features(df, pip)
    atr_med = float(np.nanmedian(feats['atr_pip']))
    base = dict(ord_thr=0.40, wz_gate=0.15, pull_min=0.05, pull_max=0.82,
                rsi_min=45, rsi_max=85, slope_min=0.0)
    adx_grid = [0, 18, 22, 25, 28, 32]
    sl_grid = [2.3, 2.6, 3.0]
    tp_grid = [2.4, 2.6, 3.0]
    be_grid = [0.0, 0.6]
    mh_grid = [40, 64]
    res = []
    t0 = time.time()
    for adx_min, sl_mult, tp_mult, be_mult, mh in itertools.product(
            adx_grid, sl_grid, tp_grid, be_grid, mh_grid):
        cfg = dict(base); cfg.update(adx_min=adx_min, sl_mult=sl_mult,
                                     tp_mult=tp_mult, be_mult=be_mult, max_hold=mh)
        ls, ss, sl, tp = make_signals(feats, cfg, side)
        be = None if be_mult <= 0 else be_mult * atr_med
        tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh,
                                allow_overlap=False, be_trigger_pip=be)
        n, wr, pf, net = lite_stats(tr)
        if n >= rqs.N_FLOOR and wr >= 59 and pf >= 1.28:
            med_tp = float(np.median(tp[ls | ss]))
            r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
            res.append((r['rqs_score'], r['passed'], cfg, r['metrics'], r['gates']))
    res.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print(f"candidates WR>=59 & PF>=1.28: {len(res)}  ({time.time()-t0:.0f}s)")
    print("=" * 115)
    for score, passed, cfg, m, g in res[:18]:
        gl = ''.join('1' if g[k] else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f"RQS={score:5.1f} {'PASS' if passed else 'FAIL'} G[{gl}] "
              f"n={m['n_trades']:3d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
              f"net={m['net_profit']:.0f} wf={m['wf_nets']} | "
              f"adx{cfg['adx_min']} sl{cfg['sl_mult']}tp{cfg['tp_mult']} "
              f"be{cfg['be_mult']} mh{cfg['max_hold']}")
    if not res:
        print("NONE reached WR>=59 & PF>=1.28")


if __name__ == '__main__':
    main()
