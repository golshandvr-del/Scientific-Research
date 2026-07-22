# -*- coding: utf-8 -*-
"""
S170 — استفاده از ساختارِ Al Brooks High-2 (S168) به‌عنوان «فیلترِ تأیید» روی
لایه‌های زمان-محورِ مرزیِ موجود (راهِ اولِ پروژه: بهبود WR/سودِ لایه‌های موجود).
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت)
> هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR تابعِ هدف نیست اما هر لایهٔ
> فعال باید WR≥۴۰٪ داشته باشد. تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (تکمیلِ کارِ نیمه‌تمامِ نشستِ قبل + قانونِ همپوشانیِ پرامپت):
  در S168 لبهٔ ساختاریِ Brooks High-2 پذیرفته شد، اما گفته شد بخشِ همپوشانِ آن
  (~۵۶٪ که در پنجره‌های زمان-محور می‌افتد، WR≈۵۰.۱٪) «هنوز به‌عنوان فیلترِ تأیید
  تست نشده». طبقِ قانونِ صریحِ پرامپت (اگر به همپوشانی رسیدی، امکانِ استفاده به‌عنوان
  فیلتر را همان‌جا بررسی کن و به مراحلِ بعد موکول نکن)، این نشست دقیقاً همان را می‌آزماید.

فرضیهٔ ازپیش‌تعریف‌شده:
  لایه‌های زمان-محورِ مرزی (WR نزدیکِ کفِ ۴۰٪) فقط بر «پنجرهٔ تقویمی/ساعتی» تکیه دارند
  و هیچ تأییدِ ساختاریِ روند ندارند. اگر ورود را مشروط کنیم به «ساختارِ bull bar-counting
  به‌تازگی یک High-2 داده باشد» (تأییدِ ساختاریِ روندِ صعودی از کتابِ Brooks)، انتظار
  می‌رود کیفیتِ ورود بالا رود ⇒ WR افزایش یابد.

  دو حالتِ فیلتر آزموده می‌شود:
    A) «High-2 دقیقاً در N کندلِ اخیر» (پالسِ ساختاری تازه).
    B) «رژیمِ صعودیِ Brooks فعال» = آخرین رویدادِ bar-counting از نوعِ High (نه Low)
       بوده و رژیمِ EMA صعودی است (فیلترِ حالتی، پوششِ بیشتر).

  گیتِ پذیرشِ فیلتر (راهِ اولِ پروژه):
    • WR جدید ≥ WR baseline (بهبودِ کیفیت) و WR≥۴۰٪.
    • سودِ خالصِ لایهٔ فیلترشده ≥ سودِ خالصِ baseline (وگرنه فیلتر ارزش‌افزوده ندارد؛
      طبقِ قانونِ #۱ سودِ خالص حرفِ آخر را می‌زند).
  اگر هر دو برقرار شود ⇒ فیلتر به‌عنوان بهبود پذیرفته و Δnet به رکورد افزوده می‌شود.

متدولوژی سیب‌به‌سیب با S163 (همان baselineِ رکورد):
  • همان مشخصاتِ حساب (طلا ۳.۳pip، EURUSD ۱.۰pip، کمیسیون صفر).
  • همان بازهٔ ۴ سالِ اخیر، همان SL/TP/mh و همان فیلترِ امتیازیِ S163.
  • فیلترِ Brooks روی همان سیگنالِ baseline اعمال (AND) می‌شود.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import indicators as ind
from s168_brooks_high2_low2 import count_high2_low2

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK, YEARS = 10000.0, 1.0, 4
WR_FLOOR = 40.0
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def lastn(df, y=YEARS):
    end = df['dt'].iloc[-1]
    return df[df['dt'] >= end - pd.DateOffset(years=y)].reset_index(drop=True)


def cal(df):
    dt = df['dt']; df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek; df['dom'] = dt.dt.day
    return df


def stats(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values
    w = int((nu > 0).sum()); l = int((nu <= 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()); gl = float(-nu[nu <= 0].sum())
    return dict(net=float(st['net_profit']), n=n, wins=w, losses=l,
                wr=(w / n * 100 if n else 0.0), pf=(gp / gl if gl > 0 else float('inf')))


def sim(df, ls, shs, sl, tp, mh, asset):
    t = se.simulate_trades(df, ls, shs, sl, tp, asset, max_hold=mh, allow_overlap=False)
    if t is None or len(t) == 0:
        return None
    t = t.copy(); t['sl_pip'] = float(sl if np.isscalar(sl) else np.asarray(sl).flat[0])
    return t


def dxy(dfa):
    d = load('DXY_M15'); d['e'] = ind.ema(d['close'], 200)
    bear = (d['close'] < d['e']).astype(float)
    a = dfa[['time']].copy(); a['idx'] = np.arange(len(a))
    m = pd.merge_asof(a.sort_values('time'), d[['time']].assign(b=bear.values).sort_values('time'),
                      on='time', direction='backward').sort_values('idx')
    return np.nan_to_num(m['b'].values, nan=0) > 0.5


def confirms(df, keys):
    c = df['close']; e50 = ind.ema(c, 50).values; e200 = ind.ema(c, 200).values
    a14 = ind.atr(df, 14).values; a100 = ind.atr(df, 100).values; r14 = ind.rsi(c, 14).values
    _, _, hist = ind.macd(c); hist = hist.values; price = c.values
    allf = {'price>EMA200': np.nan_to_num(price > e200, nan=False).astype(bool),
            'EMA50>EMA200': np.nan_to_num(e50 > e200, nan=False).astype(bool),
            'ATR14>ATR100': np.nan_to_num((a100 > 0) & (a14 > a100), nan=False).astype(bool),
            'MACD>0': np.nan_to_num(hist > 0, nan=False).astype(bool),
            'RSI∈[35,70]': np.nan_to_num((r14 >= 35) & (r14 <= 70), nan=False).astype(bool),
            'DXY<EMA200': dxy(df)}
    sc = np.zeros(len(df), int)
    for k in keys:
        sc += allf[k].astype(int)
    return sc


KEYS = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'MACD>0', 'RSI∈[35,70]', 'DXY<EMA200']


def brooks_recent_high2(df, ema_fast, ema_slow, window):
    """فیلتر A: آیا در `window` کندلِ اخیر (شاملِ کندلِ فعلی) یک High-2 (long) رخ داده؟
    پالسِ ساختاریِ تازهٔ روندِ صعودیِ Brooks. shift-safe (رویداد روی کندلِ بسته‌شده،
    سپس با rolling روی گذشته). خروجی: bool روی هر کندل (آماده برای AND با سیگنال).
    """
    long_evt, _ = count_high2_low2(df, ema_fast, ema_slow)
    s = pd.Series(long_evt.astype(float))
    # آیا در پنجرهٔ [i-window+1 .. i] رویدادی بوده؟ فقط از گذشته/حال (causal).
    rolled = s.rolling(window, min_periods=1).sum().to_numpy()
    return rolled > 0


def brooks_bull_regime(df, ema_fast, ema_slow):
    """فیلتر B: آخرین رویدادِ bar-counting از نوعِ High بوده و رژیمِ EMA صعودی است.
    یک فیلترِ حالتیِ پوشش‌گسترده‌تر (نه فقط پالسِ لحظه‌ای).
    """
    long_evt, short_evt = count_high2_low2(df, ema_fast, ema_slow)
    n = len(df)
    last_high = np.zeros(n, dtype=bool)
    state = False
    for i in range(n):
        if long_evt[i]:
            state = True
        elif short_evt[i]:
            state = False
        last_high[i] = state
    ef = ind.ema(df['close'], ema_fast).to_numpy()
    es = ind.ema(df['close'], ema_slow).to_numpy()
    bull = ef > es
    return last_high & bull


def evaluate_layer(name, df, base_sig, sl, tp, mh, asset, ema_fast, ema_slow):
    z = np.zeros(len(df), bool)
    base = stats(sim(df, base_sig, z, sl, tp, mh, asset), asset)

    variants = []
    # فیلتر A — پالسِ High-2 اخیر، گریدِ پنجره
    for w in (8, 16, 32, 64, 96):
        filt = brooks_recent_high2(df, ema_fast, ema_slow, w)
        filt = pd.Series(filt).shift(1).fillna(False).to_numpy()  # تأییدِ کندلِ قبلی (ضدِ look-ahead)
        sig = base_sig & filt
        r = stats(sim(df, sig, z, sl, tp, mh, asset), asset)
        variants.append(dict(mode=f'A_recentHigh2_w{w}', **r))
    # فیلتر B — رژیمِ صعودیِ Brooks
    filtB = brooks_bull_regime(df, ema_fast, ema_slow)
    filtB = pd.Series(filtB).shift(1).fillna(False).to_numpy()
    sigB = base_sig & filtB
    rB = stats(sim(df, sigB, z, sl, tp, mh, asset), asset)
    variants.append(dict(mode='B_bullRegime', **rB))

    # پذیرش: WR جدید≥baseWR و WR≥۴۰ و net جدید≥ base net و n کافی
    def ok(v):
        return (v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['wr'] >= base['wr']
                and v['net'] >= base['net'])
    accepted = [v for v in variants if ok(v)]
    accepted.sort(key=lambda v: v['net'], reverse=True)
    best = accepted[0] if accepted else None
    return dict(name=name, asset=asset, base=base, variants=variants,
                best_filter=best,
                delta_net=(best['net'] - base['net']) if best else 0.0)


def main():
    print("=" * 100)
    print("S170 — فیلترِ تأییدِ ساختاریِ Brooks High-2 روی لایه‌های زمان-محورِ مرزی")
    print("گیت: WR↑ (≥base و ≥40) و net↑ (≥base). هدفِ نهایی = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    layers = []

    # ---------- طلا M15 ----------
    dfx = cal(lastn(cal(load('XAUUSD_M15'))))
    z = np.zeros(len(dfx), bool)
    sc_g = confirms(dfx, KEYS)

    # S140 Monday⁺ : baseline = Monday×hours & score>=3 ، SL100/TP300/mh96
    b140 = ((dfx['dow'].values == 0) & np.isin(dfx['hour'].values, [18, 19, 20, 21])) & (sc_g >= 3)
    layers.append(evaluate_layer('S140 Monday+', dfx, b140, 100, 300, 96, 'XAUUSD', 20, 50))

    # S142 Mid-Month⁺ : baseline = dom{10,13,20}×hours(1..12) ، SL100/TP500/mh96
    #   (baselineِ ساده با TP500 ثابت — همپایهٔ فیلترِ ساختاری؛ TP تطبیقی جداگانه در S163 است)
    b142 = np.isin(dfx['dom'].values, [10, 13, 20]) & np.isin(dfx['hour'].values, list(range(1, 13)))
    layers.append(evaluate_layer('S142 Mid-Month', dfx, b142, 100, 500, 96, 'XAUUSD', 20, 50))

    # ---------- یورو M15 ----------
    dfe = cal(lastn(cal(load('EURUSD_M15'))))
    sc_e = confirms(dfe, KEYS)
    b143 = (np.isin(dfe['dom'].values, [3, 9, 20]) &
            np.isin(dfe['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc_e >= 2))
    layers.append(evaluate_layer('S143 EURUSD Mid-Month+', dfe, b143, 20, 40, 96, 'EURUSD', 20, 50))

    # ---------- گزارش ----------
    print("\n" + "=" * 116)
    print(f"{'لایه':26s}{'baseWR':>8}{'baseNet':>11}   بهترین فیلتر (WR↑ و net↑)")
    print("-" * 116)
    total_delta = 0.0
    out = []
    for L in layers:
        b = L['base']; bf = L['best_filter']
        print(f"\n▶ {L['name']}  ({L['asset']})")
        print(f"   baseline: WR={b['wr']:.1f}%  net=${b['net']:+,.0f}  n={b['n']}  PF={b['pf']:.2f}")
        for v in L['variants']:
            mark = ''
            if v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['wr'] >= b['wr'] and v['net'] >= b['net']:
                mark = '  ✅ بهبود'
            print(f"     {v['mode']:20s} WR={v['wr']:5.1f}%  net=${v['net']:+9,.0f}  "
                  f"n={v['n']:4d}  PF={v['pf']:.2f}{mark}")
        if bf:
            d = bf['net'] - b['net']
            total_delta += d
            print(f"   🏅 بهترین: {bf['mode']}  ⇒ WR {b['wr']:.1f}%→{bf['wr']:.1f}%  "
                  f"net ${b['net']:+,.0f}→${bf['net']:+,.0f}  (Δ{d:+,.0f})")
        else:
            print(f"   ⛔ هیچ فیلتری هم‌زمان WR↑ و net↑ نداد ⇒ این لایه بی‌بهبود.")
        out.append(dict(name=L['name'], asset=L['asset'],
                        base_wr=b['wr'], base_net=b['net'], base_n=b['n'], base_pf=b['pf'],
                        best_filter=bf, variants=L['variants'], delta_net=L['delta_net']))

    print("\n" + "=" * 116)
    print(f"اثرِ خالصِ کلِ فیلترِ Brooks (جمعِ بهبودها) = ${total_delta:+,.0f}")
    print("=" * 116)
    record_before = 223246
    record_after = record_before + total_delta
    print(f"رکوردِ قبل = +${record_before:,.0f}   ⇒   رکوردِ پس از فیلتر = +${record_after:,.0f}")

    summary = dict(strategy='S170 Brooks High-2 as confirmation filter on time-drift layers',
                   layers=out, total_delta=float(total_delta),
                   record_before=record_before, record_after=float(record_after))
    with open(os.path.join(RESULTS, '_s170_brooks_filter.json'), 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=float)
    print("✅ ذخیره شد: results/_s170_brooks_filter.json")
    return summary


if __name__ == '__main__':
    main()
