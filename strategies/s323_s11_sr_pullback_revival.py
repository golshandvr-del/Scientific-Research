# -*- coding: utf-8 -*-
"""
S323 — احیای لایهٔ سوختهٔ S11 (S/R Pullback + Golden Window) با معیارِ RQS+ ≥ 80
================================================================================
مبنای احیا: `results/SR_Pullback_Trend_Golden_PriceAction_71.md` (RQS-era: WR 70–73٪
اما «نامعنادار + کم‌فرکانس + ناپایدار»؛ در عصرِ WR/فرکانس رد شد).

تزِ نو (چرا این‌بار ممکن است زنده شود):
  در عصرِ قدیم، S11 به سه دلیل رد شد: (۱) p-value>0.05 (G1)، (۲) فرکانسِ <۳ معامله/روز،
  (۳) ناپایداریِ نیمه‌ها. اما معیارِ **RQS+ فرکانس را ملاک نمی‌داند** (فقط n≥30 لازم است).
  پس مانعِ «۳ معامله/روز» که S11 را کشت، در RQS+ **بی‌اثر** است. مسئله فقط G1(معناداری)
  و G4(پایداری) می‌ماند.

منطقِ پایه (حفظِ هستهٔ price-action):
  روندِ صعودیِ ساختاری (close>EMA50>EMA200) + pullback به یک **حمایتِ واقعیِ pivot-based**
  + فضای رشدِ کافی تا مقاومتِ بعدی ⇒ LONG.

بهبودهای شناور (قانونِ «همه چیز شناور» + بی‌نهایت):
  B1) TP/SL نامتقارنِ شناور بر پایهٔ ATR (غیر-رند) — کلیدِ G1: کاهشِ WR_breakeven برای
      بزرگ‌کردنِ WR_excess و معنادار کردنِ p-value.
  B2) پنجرهٔ طلایی به‌عنوان فیلترِ زمانیِ اختیاری (روشن/خاموش/شناور).
  B3) عمقِ pullback (near_max) و فضای رشد (room_min) شناور.
  B4) فیلترِ RSI شناور (ورود در اصلاح).
  B5) قیدِ سلامتِ روند (شیبِ EMA / ADX) شناور.
  B6) مولتی‌تایم‌فریم اجباری: XAUUSD {M5,M15,M30,H1,H4} + EURUSD {M5,M15,M30}.

⚠️ همه forward-safe: سطوحِ S/R از pivotهای تأییدشده (right-confirmed در structure.py)،
   contextها از دادهٔ گذشته، ورود روی open کندلِ بعد.
"""
import sys, os, time, itertools
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicators as ind
from engine import structure as st
from engine import rqs
import warnings; warnings.filterwarnings('ignore')


def build_features(df, asset):
    pip = se.ASSETS[asset]['pip']
    # tol را متناسب با دارایی تنظیم می‌کنیم (طلا مقیاسِ بزرگ‌تر)
    tol = 0.0008 if asset == 'EURUSD' else 0.0015
    piv = st.pivots(df, left=6, right=6)
    sr = st.sr_levels(df, piv, tol=tol, expiry=1500)
    atr = ind.atr(df, 14).values
    a = np.where(atr > 0, atr, np.nan)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    rsi = ind.rsi(df['close'], 14).values
    _adx, _, _ = ind.adx(df, 14)
    adx = _adx.values
    close = df['close'].values
    hour = df['dt'].dt.hour.values
    sup = sr['support'].values
    res = sr['resistance'].values

    dist_sup = (close - sup) / a          # فاصلهٔ قیمت تا حمایت (بر ATR)
    room = (res - close) / a              # فضای رشد تا مقاومت (بر ATR)
    atr_pip = atr / pip
    # شیبِ EMA50 بر حسبِ ATR (سلامتِ روند)
    ema_slope = np.full(len(df), np.nan)
    ema_slope[10:] = (ema50[10:] - ema50[:-10]) / a[10:]

    return dict(
        close=close, hour=hour, atr_pip=atr_pip, rsi=rsi, adx=np.nan_to_num(adx, nan=0.0),
        ema50=ema50, ema200=ema200,
        dist_sup=np.nan_to_num(dist_sup, nan=99.0),
        room=np.nan_to_num(room, nan=-99.0),
        ema_slope=np.nan_to_num(ema_slope, nan=0.0),
    )


def make_signals(f, cfg):
    n = len(f['close'])
    uptrend = (f['close'] > f['ema50']) & (f['ema50'] > f['ema200'])
    near_sup = (f['dist_sup'] > 0) & (f['dist_sup'] < cfg['near_max'])
    room_ok = f['room'] > cfg['room_min']
    rsi_ok = f['rsi'] < cfg['rsi_max']
    slope_ok = f['ema_slope'] >= cfg['slope_min']
    adx_ok = f['adx'] >= cfg['adx_min']
    if cfg['golden']:
        golden = (f['hour'] >= cfg['h_lo']) & (f['hour'] <= cfg['h_hi'])
    else:
        golden = np.ones(n, bool)
    long_sig = uptrend & near_sup & room_ok & rsi_ok & slope_ok & adx_ok & golden
    long_sig[:300] = False
    short_sig = np.zeros(n, bool)
    sl_pip = np.clip(cfg['sl_mult'] * f['atr_pip'], 5.0, None)
    tp_pip = np.clip(cfg['tp_mult'] * f['atr_pip'], 5.0, None)
    return long_sig, short_sig, sl_pip, tp_pip


def lite_stats(tr):
    if len(tr) == 0:
        return 0, 0.0, 0.0, 0.0
    pnl = tr['pnl_pip'].values
    wr = (pnl > 0).mean() * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 9.0
    return len(tr), wr, pf, pnl.sum()


# گرید شناور (مقادیر غیر-رند برای اجتناب از اشتباه #۷)
GRID = dict(
    near_max=[0.55, 0.85, 1.2],
    room_min=[1.3, 2.0],
    rsi_max=[55, 70, 100],
    slope_min=[0.0, 0.15],
    adx_min=[0, 18],
    golden=[True, False],
    h_lo=[19], h_hi=[23],
    sl_mult=[1.6, 2.1, 2.6],
    tp_mult=[0.8, 1.1, 1.5],
)


def scan(asset, tf, mhs, budget=110):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    f = build_features(df, asset)
    keys = list(GRID.keys())
    t0 = time.time()
    res = []
    for combo in itertools.product(*[GRID[k] for k in keys]):
        if time.time() - t0 > budget:
            print(f'  [time budget hit at {asset} {tf}]'); break
        cfg = dict(zip(keys, combo))
        # TP باید معنادار کوچک‌تر از SL باشد تا WR بالا رود (breakeven پایین)
        if cfg['tp_mult'] >= cfg['sl_mult']:
            continue
        for max_hold in mhs:
            ls, ss, sl, tp = make_signals(f, cfg)
            tr = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                    max_hold=max_hold, allow_overlap=False)
            n, wr, pf, net = lite_stats(tr)
            if n >= 30 and wr >= 60 and pf >= 1.25:
                sig = ls | ss
                med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
                r = rqs.compute_rqs(tr, asset,
                                    sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
                c2 = dict(cfg); c2['max_hold'] = max_hold
                res.append((r['rqs_score'], r['passed'], c2, r['metrics'], r['gates']))
    res.sort(key=lambda x: (x[1], x[0]), reverse=True)
    return res


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M15'
    # max_hold متناسب با TF (M5 نیاز به کندلِ بیشتری برای همان زمانِ نگهداری دارد)
    MH = {'M5': [144, 216, 288], 'M15': [48, 72, 96], 'M30': [32, 48, 72],
          'H1': [16, 24, 36], 'H4': [8, 12, 18]}
    mhs = MH.get(tf, [48, 72, 96])
    print(f'=== S323 SR-Pullback Revival | {asset} {tf} ===')
    res = scan(asset, tf, mhs)
    print(f'candidates (n>=30, WR>=60, PF>=1.25): {len(res)}')
    print('=' * 120)
    for score, passed, cfg, m, g in res[:15]:
        gl = ''.join('1' if g[k] else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f'RQS={score:5.1f} {"PASS" if passed else "FAIL"} G[{gl}] '
              f'n={m["n_trades"]:3d} WR={m["win_rate"]:4.1f} PF={m["profit_factor"]:.2f} '
              f'DD={m["max_dd_pct"]:.1f} MCL={m["max_consec_losses"]} p={m["p_value"]:.3f} '
              f'net={m["net_profit"]:.0f} wf={[round(x) for x in m["wf_nets"]]} | '
              f'near{cfg["near_max"]} room{cfg["room_min"]} rsi{cfg["rsi_max"]} '
              f'slp{cfg["slope_min"]} adx{cfg["adx_min"]} gold{cfg["golden"]} '
              f'sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} mh{cfg["max_hold"]}')
    if not res:
        print('NONE passed lite screen')


if __name__ == '__main__':
    main()
