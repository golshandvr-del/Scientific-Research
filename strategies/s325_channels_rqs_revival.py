# -*- coding: utf-8 -*-
"""
S325 — احیای لایهٔ سوختهٔ S219 (Al Brooks «Channels» / position-in-channel) با معیارِ RQS+ ≥ 80
================================================================================
مبنای احیا: results/S219_BrooksChannels_Xauusd_M5M15M30H4_293236_46.md
  ایده: Al Brooks, «Trading Price Action: Trends», فصلِ ۱۵ (Channels).
  «BUY NEAR THE BOTTOM of the channel» — خرید در نیمهٔ پایینِ کانالِ صعودی.
  S219 با معیارِ قدیمِ net-profit پذیرفته شد (WR ۴۶–۵۸٪ روی ۴ TF طلا) اما در
  ممیزیِ RQS+ (S300) به‌خاطرِ WR<60٪ و TP>SL حذف/سوخته شد.

تشخیصِ ریشه‌ایِ سوختن (چرا در RQS+ افتاد):
  (۱) TP > SL در همهٔ کانفیگ‌ها (SL150/TP300، SL200/TP400 ...) ⇒ WR_breakeven بالا ⇒
      WR ذاتاً ۴۶–۵۸٪ ماند. برای RQS+ (گیتِ G0: WR≥60٪) کشنده است.
  (۲) pos_max نسبتاً بالا (0.4–0.6) ⇒ ورودهای نه‌چندان-عمیق در کانال هم پذیرفته شدند.
  (۳) بدونِ فیلترِ RSI/عمقِ pullback ⇒ آمیزهٔ ورودهای باکیفیت و بی‌کیفیت.

تزِ احیا (چرا این‌بار RQS+ می‌گیرد):
  «buy-low در کانالِ صعودی» ذاتاً یک الگوی fade/mean-reversion است ⇒ اگر TP کوچکِ سریع
  (< SL) بگیریم و فقط عمیق‌ترین/باکیفیت‌ترین pullbackها را بپذیریم، WR بالای ۶۰٪ می‌رود.
  این دقیقاً توصیهٔ S304 است (تمرکزِ احیا روی fade با WR-بالا).

بهبودهای شناور (قانونِ «همه چیز شناور» + بی‌نهایت):
  B1) SL/TP نامتقارنِ ATR-محورِ غیر-رند (TP<SL برای WR-بالا) — به‌جای SL/TP ثابتِ pip.
  B2) pos_max شناورِ سخت‌گیرانه (فقط عمقِ کانال).
  B3) فیلترِ RSI اشباعِ فروش (long در RSI پایین) شناور.
  B4) k (نیم-پنجرهٔ pivot) و max_gap شناور.
  B5) anti-range و require_pullback (از S219 ارث‌بری).
  B6) max_hold شناورِ مخصوصِ هر TF.
  B7) مولتی‌تایم‌فریمِ اجباری: XAUUSD {M5,M15,M30,H1,H4}.

منطقِ ساختِ کانال از S219 مستقیماً import می‌شود (channel_signals)؛ شبیه‌سازی و ارزیابی
با موتورِ رویداد-محورِ RQS+ (engine.scalp_engine + engine.rqs) انجام می‌شود.
اجرا: python3 strategies/s325_channels_rqs_revival.py XAUUSD M15
"""
import sys, os, time, itertools
sys.path.insert(0, '.')
sys.path.insert(0, 'strategies')
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs
import warnings; warnings.filterwarnings('ignore')

import s219_brooks_channels as S219


def build_extra(df, asset):
    """فیچرهای کمکیِ RQS-محور: atr_pip و rsi."""
    pip = se.ASSETS[asset]['pip']
    atr = ind.atr(df, 14).to_numpy()
    atr_pip = atr / pip
    rsi = ind.rsi(df['close'], 14).to_numpy()
    return atr_pip, rsi


def make_signals(df, asset, cfg, side):
    """سیگنالِ channel (منطقِ S219) + فیلترِ RSI شناور + SL/TP نامتقارنِ ATR-محور."""
    atr_pip, rsi = build_extra(df, asset)
    # سیگنالِ خامِ channel از S219 (این خودش shift(1) اعمال می‌کند ⇒ ورودِ next-open)
    raw = S219.channel_signals(df, side, cfg['ema_fast'], cfg['ema_slow'],
                               cfg['k'], cfg['pos_max'], cfg['max_gap'],
                               require_pullback=True, anti_range=True)
    n = len(df)
    # فیلترِ RSI (B3): long فقط در اشباعِ فروش، short در اشباعِ خرید
    if cfg['rsi_on']:
        if side == 'long':
            rsi_ok = rsi <= cfg['rsi_lo']
        else:
            rsi_ok = rsi >= cfg['rsi_hi']
        # RSI باید در کندلِ سیگنال (قبل از shift) سنجیده شود؛ raw از قبل shift شده،
        # پس RSI را هم یک کندل shift می‌کنیم تا هم‌تراز شود.
        rsi_ok = pd.Series(rsi_ok).shift(1).fillna(False).to_numpy()
        raw = raw & rsi_ok

    long_sig = raw if side == 'long' else np.zeros(n, bool)
    short_sig = raw if side == 'short' else np.zeros(n, bool)

    sl_pip = np.clip(cfg['sl_mult'] * atr_pip, 5.0, None)
    tp_pip = np.clip(cfg['tp_mult'] * atr_pip, 5.0, None)
    return long_sig, short_sig, sl_pip, tp_pip


# گرید شناورِ غیر-رند (اجتناب از اشتباه #۷). TP<SL کلیدِ احیا.
GRID = dict(
    ema=[(10, 30), (20, 50)],
    k=[3, 5],
    pos_max=[0.25, 0.35, 0.5],       # سخت‌گیرانه‌تر از S219 (که 0.4–0.6 بود)
    max_gap=[40, 80],
    rsi_on=[True, False],
    rsi_lo=[38, 45], rsi_hi=[55, 62],
    sl_mult=[1.9, 2.5, 3.2],          # ATR-محورِ غیر-رند
    tp_mult=[0.7, 1.0, 1.3],          # TP < SL
)


def eval_cfg(df, asset, cfg, side, mh):
    ls, ss, sl, tp = make_signals(df, asset, cfg, side)
    if not (ls | ss).any():
        return None
    tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 30:
        return None
    sig = ls | ss
    med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
    r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
    return r


def scan(asset, tf, sides, mhs, budget=320):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    keys = list(GRID.keys())
    combos = list(itertools.product(*[GRID[k] for k in keys]))
    t0 = time.time()
    rows = []
    passed = []
    for combo in combos:
        if time.time() - t0 > budget:
            print(f"  [time budget hit at {asset} {tf} — scanned partial]")
            break
        d = dict(zip(keys, combo))
        cfg = dict(ema_fast=d['ema'][0], ema_slow=d['ema'][1], k=d['k'],
                   pos_max=d['pos_max'], max_gap=d['max_gap'],
                   rsi_on=d['rsi_on'], rsi_lo=d['rsi_lo'], rsi_hi=d['rsi_hi'],
                   sl_mult=d['sl_mult'], tp_mult=d['tp_mult'])
        if cfg['tp_mult'] >= cfg['sl_mult']:
            continue
        for side in sides:
            for mh in mhs:
                r = eval_cfg(df, asset, cfg, side, mh)
                if r is None:
                    continue
                m = r['metrics']
                c2 = dict(cfg); c2['side'] = side; c2['max_hold'] = mh
                rows.append((r['rqs_score'], c2, m, r['gates'], r['passed']))
                if r['passed']:
                    passed.append((r['rqs_score'], c2, m, r['gates']))
    rows.sort(key=lambda x: x[0], reverse=True)
    passed.sort(key=lambda x: x[0], reverse=True)
    return rows, passed


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M15'
    # max_hold مخصوصِ هر TF (اجتناب از اشتباه #۶)
    mh_map = {'M5': [48, 96], 'M15': [32, 64], 'M30': [24, 48],
              'H1': [16, 32], 'H4': [8, 16]}
    mhs = mh_map.get(tf, [32, 64])
    print(f"=== S325 Channels-RQS Revival | {asset} {tf} ===")
    rows, passed = scan(asset, tf, ['long', 'short'], mhs)
    print(f"total evaluated (n>=30): {len(rows)}  |  PASSED(RQS+>=80): {len(passed)}")
    print("--- top 8 by RQS+ ---")
    for score, cfg, m, g, ps in rows[:8]:
        verdict = 'PASS' if ps else 'FAIL'
        gs = ''.join('1' if g[k] else '0' for k in sorted(g.keys()))
        print(f"RQS={score:5.1f} {verdict} G[{gs}] {cfg['side']:5s} n={m['n_trades']:4d} "
              f"WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f} "
              f"MCL={m['max_consec_losses']} p={m['p_value']:.3f} net={m['net_profit']:.0f} "
              f"wf={[round(x) for x in m['wf_nets']]} | ema{cfg['ema_fast']}/{cfg['ema_slow']} "
              f"k{cfg['k']} pos{cfg['pos_max']} rsi{cfg['rsi_on']} sl{cfg['sl_mult']}tp{cfg['tp_mult']} mh{cfg['max_hold']}")
    # ذخیرهٔ برنده‌ها
    import json
    out = {}
    if passed:
        best = passed[0]
        out[f'{asset}_{tf}'] = dict(rqs=best[0], cfg=best[1],
                                    metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                                             for k, v in best[2].items() if k != 'equity_curve'})
        fn = f'results/_s325_{asset}_{tf}.json'
        with open(fn, 'w', encoding='utf-8') as fp:
            json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
        print(f"saved {fn}")


if __name__ == '__main__':
    main()
