# -*- coding: utf-8 -*-
"""
S211e — مرحله ۳ و ۴ User Note: تقویتِ لایهٔ 13/100/200 با اندیکاتورهای کمیاب
================================================================================
لایهٔ پایه (S211d): XAUUSD M15 LONG، ست SMA 13/100/200، stack-pullback،
    net=+$10,559, WR=47.7%, WF=[1673, 54, 1557, 4985] ✅ (اما پنجرهٔ دومِ WF
    شکننده = +$54).

مرحله ۳ (دانشِ خودم) + مرحله ۴ (جستجوی اینترنت: Vortex/Choppiness/Keltner/
Donchian/Kaufman-ER/Force-Index — همه کمتر-شناخته‌شده از MA/RSI ساده):
    این‌ها را به‌عنوان *فیلترِ تأیید* روی لایهٔ پایه می‌آزماییم (قانونِ بهبود:
    هر تعداد فیلتر مجاز). هدف: افزایشِ net *و/یا* تقویتِ پنجرهٔ دومِ شکننده،
    بدونِ نقضِ گیت.

اندیکاتورهای کمیاب (تعریفِ مستقل — استانداردِ کلاسیک):
  • Vortex (VI+ / VI-): جهت و قدرتِ روند از range حرکتِ صعودی/نزولی.
  • Choppiness Index (CI): 0..100 — CI پایین = روند، CI بالا = رنج/چاپی.
  • Kaufman Efficiency Ratio (ER): |Δ خالص| / Σ|Δ| — کیفیتِ روند.
  • Keltner position: جای close نسبت به کانالِ EMA±ATR.
  • Donchian breakout distance: فاصله تا سقفِ n-کندلی.
  • Elder Force Index (EFI): (close−close_prev)×volume ⇒ فشارِ خریدار.
"""
import sys, os, json, itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import sma, ema, atr
from engine.scalp_engine import simulate_trades, run_capital, ASSETS


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


# ---------------- اندیکاتورهای کمیاب ----------------
def vortex(df, period=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    n = len(df)
    tr = np.zeros(n); vmp = np.zeros(n); vmm = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
        vmp[i] = abs(h[i] - l[i-1])
        vmm[i] = abs(l[i] - h[i-1])
    def roll(x):
        s = pd.Series(x).rolling(period).sum().values
        return s
    str_ = roll(tr); str_[str_ == 0] = np.nan
    vip = roll(vmp) / str_
    vim = roll(vmm) / str_
    return vip, vim


def choppiness(df, period=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    n = len(df)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
    atr_sum = pd.Series(tr).rolling(period).sum().values
    hh = pd.Series(h).rolling(period).max().values
    ll = pd.Series(l).rolling(period).min().values
    rng = hh - ll
    rng[rng <= 0] = np.nan
    ci = 100.0 * np.log10(atr_sum / rng) / np.log10(period)
    return ci


def kaufman_er(df, period=10):
    c = df['close'].values
    n = len(df)
    er = np.full(n, np.nan)
    for i in range(period, n):
        change = abs(c[i] - c[i-period])
        vol = np.sum(np.abs(np.diff(c[i-period:i+1])))
        er[i] = change / vol if vol > 0 else 0.0
    return er


def keltner_pos(df, period=20, mult=2.0):
    c = df['close'].values
    mid = ema(df['close'], period).values
    a = atr(df, period).values
    upper = mid + mult * a
    lower = mid - mult * a
    rng = upper - lower
    rng[rng <= 0] = np.nan
    return (c - lower) / rng  # 0..1


def donchian_dist(df, period=20):
    h = df['high'].values
    c = df['close'].values
    a = atr(df, 14).values
    hh = pd.Series(h).rolling(period).max().shift(1).values
    a2 = a.copy(); a2[a2 <= 0] = np.nan
    return (hh - c) / a2  # فاصلهٔ close تا سقفِ کانال بر حسبِ ATR (کوچک=نزدیکِ شکست)


def force_index(df, period=13):
    c = df['close'].values
    v = df['volume'].values
    n = len(df)
    fi = np.zeros(n)
    for i in range(1, n):
        fi[i] = (c[i] - c[i-1]) * v[i]
    return pd.Series(fi).ewm(span=period, adjust=False).mean().values


# ---------------- سیگنالِ پایه + فیلتر ----------------
def base_long(df, pf=13, pm=100, ps=200):
    c = df['close'].values.astype(float)
    l = df['low'].values.astype(float)
    sf = sma(df['close'], pf).values
    sm = sma(df['close'], pm).values
    ss = sma(df['close'], ps).values
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    for i in range(ps + 1, n):
        if np.isnan(ss[i]) or np.isnan(sm[i]) or np.isnan(sf[i]):
            continue
        if sf[i] > sm[i] > ss[i] and l[i - 1] <= sf[i - 1] and c[i] > sf[i]:
            sig[i] = True
    return sig


def _net(t, asset):
    if t is None or len(t) == 0:
        return 0.0
    return run_capital(t, asset)[0]['net_profit']


def gate(trades, df, asset):
    if trades is None or len(trades) == 0:
        return dict(n=0, net=0, wr=0, pass_gate=False)
    net = _net(trades, asset)
    wr = 100.0 * (trades['outcome'] == 'win').mean()
    half = len(df) // 2
    h1 = _net(trades[trades['signal_bar'] < half], asset)
    h2 = _net(trades[trades['signal_bar'] >= half], asset)
    wf = []
    b = np.linspace(0, len(df), 5).astype(int)
    for k in range(4):
        tw = trades[(trades['signal_bar'] >= b[k]) & (trades['signal_bar'] < b[k+1])]
        wf.append(_net(tw, asset))
    pg = (net > 0 and h1 > 0 and h2 > 0 and all(w > 0 for w in wf) and wr >= 40.0)
    return dict(n=len(trades), net=round(net), wr=round(wr, 1),
                h1=round(h1), h2=round(h2), wf=[round(w) for w in wf], pass_gate=bool(pg),
                wf_min=round(min(wf)))


def main():
    asset = 'XAUUSD'; tf = 'M15'
    path = f'data/XAUUSD_{tf}.csv'
    ASSETS[asset]['file'] = path
    df = load(path)
    sl, tp, mh = 150, 300, 32
    n = len(df); zeros = np.zeros(n, dtype=bool)

    base = base_long(df)
    print("=" * 100)
    print("S211e — تقویتِ لایهٔ 13/100/200 M15 LONG با اندیکاتورهای کمیاب")
    print("=" * 100)
    g0 = gate(simulate_trades(df, base, zeros, sl, tp, asset, max_hold=mh), df, asset)
    print(f"پایه (بدونِ فیلتر): net={g0['net']} wr={g0['wr']} wf={g0['wf']} wf_min={g0['wf_min']} pass={g0['pass_gate']}")

    # پیش‌محاسبهٔ اندیکاتورها
    vip, vim = vortex(df, 14)
    ci = choppiness(df, 14)
    er = kaufman_er(df, 10)
    kp = keltner_pos(df, 20, 2.0)
    dd = donchian_dist(df, 20)
    fi = force_index(df, 13)

    filters = {
        'Vortex VI+>VI-':      (vip > vim),
        'Choppiness<50 (روند)': (ci < 50),
        'Choppiness<45':       (ci < 45),
        'Kaufman ER>0.3':      (er > 0.3),
        'Kaufman ER>0.2':      (er > 0.2),
        'Keltner pos>0.5':     (kp > 0.5),
        'Keltner pos<0.9':     (kp < 0.9),
        'Donchian dist<2ATR':  (dd < 2.0),
        'Force Index>0':       (fi > 0),
    }

    print("\n[تک-فیلتر] هر اندیکاتور به‌تنهایی روی لایهٔ پایه:")
    print(f"{'filter':>24} {'n':>5} {'net':>8} {'wr':>5} {'wf_min':>7} {'h1':>7} pass")
    single = {}
    for name, mask in filters.items():
        m = np.asarray(mask, dtype=bool)
        m = m & ~np.isnan(np.where(m, 1.0, np.nan))  # nan→False
        sig = base & np.nan_to_num(mask.astype(float), nan=0.0).astype(bool)
        g = gate(simulate_trades(df, sig, zeros, sl, tp, asset, max_hold=mh), df, asset)
        single[name] = g
        mark = "✅" if g['pass_gate'] else ""
        print(f"{name:>24} {g['n']:>5} {g['net']:>8} {g['wr']:>5} {g['wf_min']:>7} {g['h1']:>7} {mark}")

    # فیلترهایی که wf_min را بهبود می‌دهند (بدونِ نابودیِ net)
    print("\n[ترکیب] بهترین فیلترها با هم (هدف: تقویتِ پنجرهٔ دومِ WF + net بالا):")
    combos = [
        ['Choppiness<50 (روند)'],
        ['Vortex VI+>VI-', 'Choppiness<50 (روند)'],
        ['Vortex VI+>VI-', 'Kaufman ER>0.2'],
        ['Choppiness<50 (روند)', 'Force Index>0'],
        ['Vortex VI+>VI-', 'Choppiness<50 (روند)', 'Force Index>0'],
        ['Vortex VI+>VI-', 'Choppiness<50 (روند)', 'Keltner pos>0.5'],
        ['Vortex VI+>VI-', 'Kaufman ER>0.2', 'Force Index>0'],
    ]
    best = dict(g0, combo=['(base)'], score=(1 if g0['pass_gate'] else 0, g0['wf_min'], g0['net']))
    for combo in combos:
        sig = base.copy()
        for name in combo:
            sig = sig & np.nan_to_num(filters[name].astype(float), nan=0.0).astype(bool)
        g = gate(simulate_trades(df, sig, zeros, sl, tp, asset, max_hold=mh), df, asset)
        mark = "✅PASS" if g['pass_gate'] else ""
        print(f"  {'+'.join(combo):>62} n={g['n']:>4} net={g['net']:>7} wr={g['wr']:>5} "
              f"wf_min={g['wf_min']:>6} wf={g['wf']} {mark}")
        score = (1 if g['pass_gate'] else 0, g['wf_min'], g['net'])
        if score > best['score']:
            best = dict(g, combo=combo, score=score)

    print(f"\n>>> بهترین ترکیب: {best['combo']}")
    print(f"    net={best['net']} wr={best['wr']} wf={best.get('wf')} wf_min={best['wf_min']} pass={best['pass_gate']}")

    os.makedirs('results', exist_ok=True)
    with open('results/_s211e_rare_filters.json', 'w') as f:
        json.dump(dict(base=g0, single=single, best=best), f, indent=2, default=str)
    print("saved: results/_s211e_rare_filters.json")


if __name__ == '__main__':
    main()
