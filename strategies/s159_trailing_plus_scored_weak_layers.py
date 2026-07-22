# -*- coding: utf-8 -*-
"""
s159_trailing_plus_scored_weak_layers.py
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است. تعدادِ معامله و Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم،
> نه آمارِ زیبا.** تنها تابعِ هدف: **سودِ خالصِ تجمعیِ پس از اسپرد/اسلیپیج/کمیسیون.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

--------------------------------------------------------------------------------
انگیزه: S157/S158 نشان دادند لایه‌های R:R-خیلی-بالا (S142 با ۵:۱، S81 با ۱۰:۱، S143
با ۶:۱) ذاتاً WR-پایین‌اند؛ فیلترِ خالص برای رساندنِ WR≥40٪ یا سود را نابود می‌کند یا
کافی نیست. راهِ ساختاریِ درست برای بالا بردنِ WR *بدونِ* کشتنِ سود:
  **قفلِ سودِ جزئی با trailing-stop + break-even.** با trailing، معاملاتی که به سود
  رفته‌اند و برمی‌گردند به‌جای «باخت»، در ناحیهٔ سود بسته می‌شوند ⇒ WR واقعی بالا می‌رود.
  این دقیقاً «کشف ≠ گرفتن» (L61) را جبران می‌کند.

این اسکریپت برای هر لایهٔ ضعیف، grid کوچکی از (best-scored-filter × BE × trail × TP)
را می‌آزماید و نقطه‌ای را انتخاب می‌کند که **هم WR≥40٪ و هم سودِ خالص ≥ baseline** باشد،
با بیشینه‌سازیِ سودِ خالص در میانِ واجدین شرط.

مشخصاتِ واقعیِ حساب و پنجرهٔ ۴ ساله دقیقاً مثلِ S157/S158/ممیزی.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK, YEARS = 10000.0, 1.0, 4

se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)
se.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def last_n_years(df, years=YEARS):
    end = df['dt'].iloc[-1]; start = end - pd.DateOffset(years=years)
    return df[df['dt'] >= start].reset_index(drop=True), start, end


def add_calendar(df):
    dt = df['dt']
    df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day; df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df


def stats_capital(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP,
                                        risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values if len(pt) else np.array([])
    wins = int((nu > 0).sum()); losses = int((nu <= 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()) if n else 0.0
    gl = float(-nu[nu <= 0].sum()) if n else 0.0
    return dict(net=float(st['net_profit']), n=n, wins=wins, losses=losses,
                wr=(wins / n * 100.0 if n else 0.0),
                pf=(gp / gl if gl > 0 else float('inf')))


def run_layer(df, ls, shs, sl, tp, mh, asset='XAUUSD', be=None, trail=None):
    tr = se.simulate_trades(df, ls, shs, sl, tp, asset, max_hold=mh,
                            allow_overlap=False, be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    return tr


def align_dxy(df_asset):
    dxy = load('DXY_M15')
    dxy['ema200'] = ind.ema(dxy['close'], 200)
    bear = (dxy['close'] < dxy['ema200']).astype(float)
    a = df_asset[['time']].copy(); a['idx'] = np.arange(len(a))
    m = pd.merge_asof(a.sort_values('time'),
                      dxy[['time']].assign(bear=bear.values).sort_values('time'),
                      on='time', direction='backward').sort_values('idx')
    return (np.nan_to_num(m['bear'].values, nan=0.0) > 0.5)


def build_confirms(df):
    c = df['close']
    e50 = ind.ema(c, 50).values; e200 = ind.ema(c, 200).values
    a14 = ind.atr(df, 14).values; a100 = ind.atr(df, 100).values
    r14 = ind.rsi(c, 14).values
    _, _, hist = ind.macd(c); hist = hist.values
    price = c.values
    return {
        'price>EMA200': np.nan_to_num(price > e200, nan=False).astype(bool),
        'EMA50>EMA200': np.nan_to_num(e50 > e200, nan=False).astype(bool),
        'ATR14>ATR100': np.nan_to_num((a100 > 0) & (a14 > a100), nan=False).astype(bool),
        'MACD>0': np.nan_to_num(hist > 0, nan=False).astype(bool),
        'RSI∈[35,70]': np.nan_to_num((r14 >= 35) & (r14 <= 70), nan=False).astype(bool),
        'DXY<EMA200': align_dxy(df),
    }


def scored_mask(conf, keys, k):
    score = np.zeros(len(next(iter(conf.values()))), dtype=int)
    for key in keys:
        score += conf[key].astype(int)
    return score >= k


def optimize_layer(name, df, base_long, base_short, sl, tp0, mh, asset, conf, keys,
                   tp_grid, be_grid, trail_grid, k_grid):
    """grid: (k فیلترِ امتیازی × TP × BE × trail). قید: WR≥40 و net≥baseline."""
    print("\n" + "=" * 100)
    print(f"لایه: {name}  (baseline SL{sl}/TP{tp0}/mh{mh}، {asset})")
    is_short = base_short.any()
    # baseline (بدونِ هیچ تغییری، دقیقاً مثلِ ممیزی)
    b_be = 8 if is_short else None; b_trail = 8 if is_short else None
    tr0 = run_layer(df, base_long, base_short, sl, tp0, mh, asset, be=b_be, trail=b_trail)
    b = stats_capital(tr0, asset)
    print(f"BASELINE  n={b['n']:>5} WR={b['wr']:>5.1f}%  net={b['net']:>+11,.0f}  PF={b['pf']:.2f}")
    print("-" * 100)

    best = None; tried = 0
    for k in k_grid:
        m = scored_mask(conf, keys, k) if k > 0 else np.ones(len(df), bool)
        for tp in tp_grid:
            for be in be_grid:
                for tr_p in trail_grid:
                    if is_short:
                        ls = np.zeros(len(df), bool); shs = base_short & m
                    else:
                        ls = base_long & m; shs = np.zeros(len(df), bool)
                    tr = run_layer(df, ls, shs, sl, tp, mh, asset, be=be, trail=tr_p)
                    s = stats_capital(tr, asset)
                    tried += 1
                    if s['wr'] >= 40.0 and s['net'] >= b['net'] - 1e-6 and s['n'] >= 30:
                        cand = dict(k=k, tp=tp, be=be, trail=tr_p, **s)
                        if best is None or s['net'] > best['net']:
                            best = cand
    print(f"grid آزموده: {tried} ترکیب")
    if best:
        print(f"🥇 بهترین (WR≥40 و net≥baseline): k≥{best['k']} فیلتر، TP{best['tp']}، "
              f"BE{best['be']}، trail{best['trail']}")
        print(f"    WR {b['wr']:.1f}%→{best['wr']:.1f}%   net {b['net']:+,.0f}→{best['net']:+,.0f} "
              f"(Δ{best['net']-b['net']:+,.0f})   PF {b['pf']:.2f}→{best['pf']:.2f}   n={best['n']}")
    else:
        print("⚠️ هیچ ترکیبی هم‌زمان WR≥40 و حفظِ سود را رعایت نکرد.")
    return {'baseline': b, 'best': best}


def main():
    print("=" * 100)
    print("S159 — بهینه‌سازیِ مشترک (فیلترِ امتیازی × trailing/BE × TP) روی لایه‌های ضعیف")
    print("=" * 100, flush=True)
    report = {}

    dfx = add_calendar(load('XAUUSD_M15'))
    dfx4, _, _ = last_n_years(dfx); dfx4 = add_calendar(dfx4.copy())
    conf_g = build_confirms(dfx4)
    KEYS_G = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'MACD>0', 'RSI∈[35,70]', 'DXY<EMA200']
    n = len(dfx4); zeros = np.zeros(n, bool)

    # ---- S142 Mid-Month: baseline SL100/TP500/mh96 ----
    base_s142 = np.isin(dfx4['dom'].values, [10, 13, 20]) & np.isin(dfx4['hour'].values, list(range(1, 13)))
    report['S142'] = optimize_layer('S142 Mid-Month', dfx4, base_s142, zeros, 100, 500, 96, 'XAUUSD',
                                    conf_g, KEYS_G,
                                    tp_grid=[200, 250, 300, 400, 500],
                                    be_grid=[None, 50, 80, 120],
                                    trail_grid=[None, 40, 60, 100],
                                    k_grid=[0, 1, 2, 3])

    # ---- S81 M30 Swing: baseline SL120/TP1200/mh144 ----
    dfm30 = add_calendar(load('XAUUSD_M30'))
    dfm30_4, _, _ = last_n_years(dfm30); dfm30_4 = dfm30_4.reset_index(drop=True)
    c30 = dfm30_4['close']
    e20 = ind.ema(c30, 20).values; e100b = ind.ema(c30, 100).values; r14 = ind.rsi(c30, 14).values
    base_s81 = np.nan_to_num((e20 > e100b) & (r14 < 35), nan=False).astype(bool)
    conf_81 = build_confirms(dfm30_4)
    KEYS_81 = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'DXY<EMA200']
    report['S81'] = optimize_layer('S81 Swing-Pullback', dfm30_4, base_s81,
                                   np.zeros(len(dfm30_4), bool), 120, 1200, 144, 'XAUUSD_M30',
                                   conf_81, KEYS_81,
                                   tp_grid=[200, 300, 400, 500, 700, 1000, 1200],
                                   be_grid=[None, 60, 100, 150],
                                   trail_grid=[None, 60, 100, 150],
                                   k_grid=[0, 1, 2])

    # ---- S143 EURUSD: baseline SL20/TP120/mh96 ----
    dfe = add_calendar(load('EURUSD_M15'))
    dfe4, _, _ = last_n_years(dfe); dfe4 = add_calendar(dfe4.copy())
    conf_e = build_confirms(dfe4)
    KEYS_E = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'MACD>0', 'RSI∈[35,70]', 'DXY<EMA200']
    ne = len(dfe4); ze = np.zeros(ne, bool)
    base_s143 = np.isin(dfe4['dom'].values, [3, 9, 20]) & np.isin(dfe4['hour'].values,
                                                                  [1, 2, 3, 4, 5, 11, 12, 13, 14, 15])
    report['S143'] = optimize_layer('S143 EURUSD Mid-Month', dfe4, base_s143, ze, 20, 120, 96, 'EURUSD',
                                    conf_e, KEYS_E,
                                    tp_grid=[40, 60, 80, 100, 120],
                                    be_grid=[None, 10, 15, 20],
                                    trail_grid=[None, 10, 15, 20],
                                    k_grid=[0, 1, 2, 3])

    with open(os.path.join(RESULTS, '_s159_trailing_scored.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s159_trailing_scored.json")
    return report


if __name__ == '__main__':
    main()
