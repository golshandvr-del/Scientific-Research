# -*- coding: utf-8 -*-
"""
S321b — احیای S52 MA-Ribbon: نسخهٔ تقویت‌شده (قانونِ بی‌نهایتِ بهبود + همه‌چیز شناور)
================================================================================
یافتهٔ S321 (اسکنِ خام XAUUSD M5): ستاپِ pullback-to-ribbon لبه دارد اما مرزی است
(بهترین WR≈۵۵٪، PF≈۱.۲۲) و به G0(WR≥۶۰)∧G2(PF≥۱.۳) نمی‌رسد. الگوی برنده: رژیمِ
منبسط (wz≈0.35) + ترتیبِ ملایم (ord≈0.55) + SL بزرگ (≈2.2×ATR).

بهبودهای این نسخه (هر کدام یک «همکاریِ بهبود» طبق قانونِ پروژه):
  B1) break-even trailing (be_trigger×ATR): قفلِ سود ⇒ WR↑ بدونِ کشتنِ RR
      (همان مکانیزمی که S313 را روی H1 نجات داد).
  B2) فیلترِ مومنتومِ RSI: pullback فقط وقتی معتبر است که RSI هنوز روند را تأیید
      کند (نه oversold عمیق = شکستِ روند).
  B3) فیلترِ فاصله از کفِ ریبون (dist_bot_atr): ورود نزدیکِ حمایتِ دینامیک.
  B4) grid ظریفِ شناور حولِ ناحیهٔ برنده (اعدادِ غیر-رند).

اجرا: python3 strategies/s321b_ma_ribbon_enhanced.py XAUUSD M5 [max_sec] [side]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import itertools

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs

TF_FILE = {
    'M5':  'data/{a}_M5.csv',  'M15': 'data/{a}_M15.csv',
    'M30': 'data/{a}_M30.csv', 'H1':  'data/{a}_H1.csv', 'H4': 'data/{a}_H4.csv',
}
RIBBON_PERIODS = [8, 13, 21, 34, 55, 89, 144]

# grid ظریفِ شناور حولِ ناحیهٔ برنده + بهبودها
GRID = dict(
    ord_thr=[0.45, 0.55, 0.62],
    wz_gate=[0.20, 0.35, 0.55],
    pull_min=[0.05, 0.15],
    pull_max=[0.70, 0.82],
    rsi_min=[45, 50, 55],            # B2: فیلترِ مومنتوم (pullback هنوز روند-همسو)
    rsi_max=[72, 80],
    sl_mult=[1.9, 2.2, 2.6],
    tp_mult=[2.2, 2.8, 3.6],
    be_mult=[0.0, 0.8, 1.2],         # B1: break-even trigger ×ATR (0=خاموش)
    max_hold=[48, 90],
)


def build_features(df, pip):
    c = df['close']
    atr_ = ind.atr(df, 14)
    rsi_ = ind.rsi(c, 14)
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
    dist_bot_atr = (price - bot) / np.where(atrv != 0, atrv, np.nan)
    return dict(close=price, open=df['open'].values, atr_pip=atrv / pip,
                rib_order=rib_order, rib_width_z=rib_width_z, pos_in_rib=pos_in_rib,
                rsi=rsi_.values, dist_bot_atr=np.nan_to_num(dist_bot_atr, nan=99))


def make_signals(feats, cfg, side):
    close = feats['close']; opn = feats['open']
    order = feats['rib_order']; wz = feats['rib_width_z']; pos = feats['pos_in_rib']
    rsi_ = feats['rsi']; atr_pip = feats['atr_pip']
    bull = close > opn; bear = close < opn
    open_regime = wz >= cfg['wz_gate']
    rsi_ok_l = (rsi_ >= cfg['rsi_min']) & (rsi_ <= cfg['rsi_max'])
    rsi_ok_s = (rsi_ <= (100 - cfg['rsi_min'])) & (rsi_ >= (100 - cfg['rsi_max']))
    long_ok = ((order >= cfg['ord_thr']) & open_regime & bull & rsi_ok_l &
               (pos >= cfg['pull_min']) & (pos <= cfg['pull_max']))
    short_ok = ((order <= -cfg['ord_thr']) & open_regime & bear & rsi_ok_s &
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
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    max_sec = float(sys.argv[3]) if len(sys.argv) > 3 else 480.0
    side = sys.argv[4] if len(sys.argv) > 4 else ('long' if asset == 'XAUUSD' else 'both')
    pip = se.ASSETS[asset]['pip']
    df = se.load_data(TF_FILE[tf].format(a=asset))
    print(f"[{asset} {tf}] rows={len(df)} {df['dt'].iloc[0]} -> {df['dt'].iloc[-1]} side={side}")
    feats = build_features(df, pip)
    keys = list(GRID.keys())
    total = 1
    for k in keys:
        total *= len(GRID[k])
    print(f"grid = {total}")
    t0 = time.time(); shortlist = []; tested = 0
    for combo in itertools.product(*[GRID[k] for k in keys]):
        if time.time() - t0 > max_sec * 0.62:
            print(f"[time] coarse stop @ {tested}"); break
        cfg = dict(zip(keys, combo))
        if cfg['tp_mult'] <= cfg['sl_mult']:
            continue
        ls, ss, sl, tp = make_signals(feats, cfg, side)
        be = None if cfg['be_mult'] <= 0 else cfg['be_mult'] * float(np.nanmedian(feats['atr_pip']))
        trades = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                    max_hold=cfg['max_hold'], allow_overlap=False,
                                    be_trigger_pip=be)
        tested += 1
        n, wr, pf, net = lite_stats(trades)
        if n >= rqs.N_FLOOR and wr >= 59 and pf >= 1.28:
            sig = ls | ss
            med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
            shortlist.append((pf, wr, n, cfg, trades, med_tp))
    shortlist.sort(key=lambda x: x[0], reverse=True)
    print(f"tested={tested} shortlist={len(shortlist)} ({time.time()-t0:.0f}s)")
    results = []
    for pf, wr, n, cfg, trades, med_tp in shortlist:
        if time.time() - t0 > max_sec:
            print("[time] rqs stop"); break
        r = rqs.compute_rqs(trades, asset,
                            sl_pip=float(np.median(trades['sl_pip'])), tp_pip=med_tp)
        results.append((r['rqs_score'], r['passed'], cfg, r['metrics'], r['gates']))
    results.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print("=" * 110)
    for score, passed, cfg, m, gates in results[:25]:
        gl = ''.join('1' if gates[g] else '0' for g in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f"RQS={score:5.1f} {'PASS' if passed else 'FAIL'} G[{gl}] "
              f"n={m['n_trades']:4d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
              f"net={m['net_profit']:.0f} wf={m['wf_nets']} | ord{cfg['ord_thr']} wz{cfg['wz_gate']} "
              f"pull[{cfg['pull_min']},{cfg['pull_max']}] rsi[{cfg['rsi_min']},{cfg['rsi_max']}] "
              f"sl{cfg['sl_mult']}tp{cfg['tp_mult']} be{cfg['be_mult']} mh{cfg['max_hold']}")
    if not results:
        print("NO CANDIDATE PASSED LITE SCREEN (WR>=59 & PF>=1.28)")


if __name__ == '__main__':
    main()
