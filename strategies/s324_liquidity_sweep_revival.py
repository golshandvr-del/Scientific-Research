# -*- coding: utf-8 -*-
"""
S324 — احیای لایهٔ سوختهٔ S165 (Liquidity Sweep + Reversal) با معیارِ RQS+ ≥ 80
================================================================================
مبنای احیا: results/S165_LiquiditySweepReversal_NetProfit_-1048.md
  منبعِ ایده: Telegram-Resource TM EXECUTION SUITE (ICT / Smart-Money، Pine v6).
  در عصرِ «net>0» با ۴۸ واریانتِ رند (SL/TP = 20/30, 20/40, 30/45) رد شد؛
  هیچ واریانتی net مثبت نساخت (WR 39-49٪).

تشخیصِ ریشه‌ایِ سوختن (کشفِ این نشست):
  (۱) TP > SL در هر ۳ ترکیب ⇒ WR_breakeven بالا (>40٪) ⇒ WR ذاتاً پایین ماند.
      برای RQS+ (WR≥60٪) این کشنده است.
  (۲) اعداد رند (اشتباه رایج #۷) — هیچ کاوشِ ATR-محور/غیر-رند نشد.
  (۳) بدونِ فیلترِ کیفیت (روند/نوسان/عمقِ sweep) ⇒ آمیزهٔ sweepِ واقعی و fake.

تزِ نو (چرا این‌بار زنده می‌شود — mean-reversion/fade ذاتاً WR-بالا):
  یک liquidity-sweep واقعی = شکارِ استاپ‌ها + بازگشتِ فوری. این یک الگوی fade است؛
  درسِ S304: «تمرکزِ احیا باید روی mean-reversion/fade باشد که ذاتاً WR بالا دارد».
  کلیدِ احیا = TP کوچکِ سریع (< SL) ⇒ WR_breakeven پایین ⇒ WR بالا + G1 معنادار.

بهبودهای شناور (قانونِ «همه چیز شناور» + بی‌نهایت):
  B1) SL/TP نامتقارنِ ATR-محورِ غیر-رند (TP<SL برای WR-بالا).
  B2) عمقِ sweep شناور: چقدر پایین‌تر از pivot جارو شود (sweep عمیق‌تر = بازگشتِ قوی‌تر).
  B3) displacement شناور (قدرتِ کندلِ بازگشت).
  B4) فیلترِ ساختار/روندِ بالاتر (EMA regime) شناور.
  B5) killzone شناور (روشن/خاموش).
  B6) فیلترِ RSI (ورود در ناحیهٔ اشباع) شناور.
  B7) swing_len شناور (تعریفِ pivotِ نقدینگی).
  B8) مولتی‌تایم‌فریم اجباری: XAUUSD {M5,M15,M30,H1,H4} + EURUSD {M5,M15,M30}.

⚠️ همه forward-safe: pivotها right-confirmed (t=k+swing)، context از گذشته، ورود open[t+1].
"""
import sys, os, time, itertools
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs
import warnings; warnings.filterwarnings('ignore')


def confirmed_pivots(df, swing_len):
    """آخرین pivotHigh/pivotLow تأییدشده تا t (forward-safe؛ منطبق با S165)."""
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    n = len(df); w = swing_len
    win = 2 * w + 1
    max_win = pd.Series(h).rolling(win, center=True).max().to_numpy()
    min_win = pd.Series(l).rolling(win, center=True).min().to_numpy()
    is_ph = np.zeros(n, bool); is_pl = np.zeros(n, bool)
    valid = np.arange(n)
    mask = (valid >= w) & (valid < n - w)
    is_ph[mask] = h[mask] >= max_win[mask]
    is_pl[mask] = l[mask] <= min_win[mask]
    last_ph = np.full(n, np.nan); last_pl = np.full(n, np.nan)
    for k in np.where(is_ph)[0]:
        t0 = k + w
        if t0 < n: last_ph[t0] = h[k]
    for k in np.where(is_pl)[0]:
        t0 = k + w
        if t0 < n: last_pl[t0] = l[k]
    last_ph = pd.Series(last_ph).ffill().to_numpy()
    last_pl = pd.Series(last_pl).ffill().to_numpy()
    return last_ph, last_pl


def build_features(df, asset, swing_len):
    pip = se.ASSETS[asset]['pip']
    o = df['open'].values.astype(float)
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    c = df['close'].values.astype(float)
    n = len(df)
    atr = ind.atr(df, 14).values
    a = np.where(atr > 0, atr, np.nan)
    atr_pip = atr / pip
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    rsi = ind.rsi(df['close'], 14).values
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    hour = df['dt'].dt.hour.values

    ph, pl = confirmed_pivots(df, swing_len)
    # عمقِ sweep بر حسبِ ATR (چقدر پایین‌تر از pivot جارو شد، سپس پس‌گرفته شد)
    depth_low = np.where(~np.isnan(pl), (pl - l) / a, np.nan)   # >0 یعنی low زیر pivot رفت
    depth_high = np.where(~np.isnan(ph), (h - ph) / a, np.nan)
    # قدرتِ بازگشت (displacement) بر حسبِ ATR
    disp = np.abs(c - o) / a
    # آیا close دوباره بالای/زیرِ pivot بسته شد (بازگشت تأیید شد)
    recl_low = (~np.isnan(pl)) & (l < pl) & (c > pl)
    recl_high = (~np.isnan(ph)) & (h > ph) & (c < ph)

    return dict(
        o=o, c=c, atr_pip=atr_pip, rsi=rsi, ema50=ema50, ema200=ema200, hour=hour,
        depth_low=np.nan_to_num(depth_low, nan=-99.0),
        depth_high=np.nan_to_num(depth_high, nan=-99.0),
        disp=np.nan_to_num(disp, nan=0.0),
        recl_low=recl_low, recl_high=recl_high, n=n,
    )


def make_signals(f, cfg, side):
    n = f['n']
    # sweep + reclaim پایه
    sw_lo = f['recl_low'] & (f['depth_low'] >= cfg['depth_min'])
    sw_hi = f['recl_high'] & (f['depth_high'] >= cfg['depth_min'])
    disp_ok = f['disp'] >= cfg['disp_min']
    # فیلترِ رژیم (B4): long فقط هم‌سو با ساختار، short هم‌سو
    if cfg['regime']:
        long_reg = f['c'] > f['ema200']
        short_reg = f['c'] < f['ema200']
    else:
        long_reg = np.ones(n, bool); short_reg = np.ones(n, bool)
    # فیلترِ RSI (B6): long در ناحیهٔ اشباعِ فروش، short در اشباعِ خرید
    if cfg['rsi_on']:
        long_rsi = f['rsi'] <= cfg['rsi_lo']
        short_rsi = f['rsi'] >= cfg['rsi_hi']
    else:
        long_rsi = np.ones(n, bool); short_rsi = np.ones(n, bool)
    # killzone (B5)
    if cfg['kill']:
        kz = ((f['hour'] >= 2) & (f['hour'] <= 5)) | ((f['hour'] >= 7) & (f['hour'] <= 10))
    else:
        kz = np.ones(n, bool)

    long_sig = sw_lo & disp_ok & long_reg & long_rsi & kz
    short_sig = sw_hi & disp_ok & short_reg & short_rsi & kz
    long_sig[:300] = False; short_sig[:300] = False
    if side == 'long':
        short_sig = np.zeros(n, bool)
    elif side == 'short':
        long_sig = np.zeros(n, bool)

    sl_pip = np.clip(cfg['sl_mult'] * f['atr_pip'], 5.0, None)
    tp_pip = np.clip(cfg['tp_mult'] * f['atr_pip'], 5.0, None)
    return long_sig, short_sig, sl_pip, tp_pip


def lite_stats(tr):
    if tr is None or len(tr) == 0:
        return 0, 0.0, 0.0, 0.0
    pnl = tr['pnl_pip'].values
    wr = (pnl > 0).mean() * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 9.0
    return len(tr), wr, pf, pnl.sum()


# گرید شناورِ غیر-رند (اجتناب از اشتباه #۷)
GRID = dict(
    swing_len=[8, 12],
    depth_min=[0.05, 0.25, 0.6],     # عمقِ sweep بر ATR
    disp_min=[0.3, 0.6, 1.0],        # قدرتِ کندلِ بازگشت
    regime=[True, False],
    rsi_on=[True, False],
    rsi_lo=[38, 45], rsi_hi=[55, 62],
    kill=[True, False],
    # TP < SL برای WR-بالا (کلیدِ احیا) — غیر-رند
    sl_mult=[1.7, 2.3, 3.0],
    tp_mult=[0.7, 1.0, 1.3],
)


def scan(asset, tf, sides, mhs, budget=200):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    keys = [k for k in GRID.keys()]
    t0 = time.time()
    res = []
    # features وابسته به swing_len ⇒ کش بر حسبِ swing_len
    fcache = {}
    combos = list(itertools.product(*[GRID[k] for k in keys]))
    for combo in combos:
        if time.time() - t0 > budget:
            print(f'  [time budget hit at {asset} {tf} — scanned partial]'); break
        cfg = dict(zip(keys, combo))
        if cfg['tp_mult'] >= cfg['sl_mult']:
            continue
        sw = cfg['swing_len']
        if sw not in fcache:
            fcache[sw] = build_features(df, asset, sw)
        f = fcache[sw]
        for side in sides:
            for max_hold in mhs:
                ls, ss, sl, tp = make_signals(f, cfg, side)
                if not (ls.any() or ss.any()):
                    continue
                tr = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                        max_hold=max_hold, allow_overlap=False)
                n, wr, pf, net = lite_stats(tr)
                if n >= 30 and wr >= 58 and pf >= 1.2:
                    sig = ls | ss
                    med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
                    r = rqs.compute_rqs(tr, asset,
                                        sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
                    c2 = dict(cfg); c2['max_hold'] = max_hold; c2['side'] = side
                    res.append((r['rqs_score'], r['passed'], c2, r['metrics'], r['gates']))
    res.sort(key=lambda x: (x[1], x[0]), reverse=True)
    return res


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    MH = {'M5': [96, 144, 216], 'M15': [48, 72, 96], 'M30': [32, 48, 72],
          'H1': [16, 24, 36], 'H4': [8, 12, 18]}
    mhs = MH.get(tf, [48, 72, 96])
    sides = ['long', 'short']
    print(f'=== S324 Liquidity-Sweep Revival | {asset} {tf} ===')
    res = scan(asset, tf, sides, mhs)
    print(f'candidates (n>=30, WR>=58, PF>=1.2): {len(res)}')
    print('=' * 130)
    for score, passed, cfg, m, g in res[:15]:
        gl = ''.join('1' if g[k] else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f'RQS={score:5.1f} {"PASS" if passed else "FAIL"} G[{gl}] {cfg["side"]:5s} '
              f'n={m["n_trades"]:3d} WR={m["win_rate"]:4.1f} PF={m["profit_factor"]:.2f} '
              f'DD={m["max_dd_pct"]:.1f} MCL={m["max_consec_losses"]} p={m["p_value"]:.3f} '
              f'net={m["net_profit"]:.0f} wf={[round(x) for x in m["wf_nets"]]} | '
              f'sw{cfg["swing_len"]} dep{cfg["depth_min"]} dsp{cfg["disp_min"]} '
              f'reg{int(cfg["regime"])} rsi{int(cfg["rsi_on"])}({cfg["rsi_lo"]}/{cfg["rsi_hi"]}) '
              f'kz{int(cfg["kill"])} sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} mh{cfg["max_hold"]}')
    if not res:
        print('NONE passed lite screen')


if __name__ == '__main__':
    main()
