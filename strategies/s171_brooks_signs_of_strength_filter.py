# -*- coding: utf-8 -*-
"""
S171 — فیلترِ «Signs of Strength» (فصلِ ۱۹ کتابِ Al Brooks: Trading Price Action TRENDS)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت)
> هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR تابعِ هدف نیست اما هر لایهٔ
> فعال باید WR≥۴۰٪ داشته باشد. تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (کتاب، فصلِ ۱۹ — «Signs of Strength in a Trend»):
  Brooks فهرستی از نشانه‌های عددیِ «روندِ قوی» می‌دهد که در آن باید فقط ورودِ هم‌جهت
  گرفت. مهم‌ترین‌های *قابلِ‌کدنویسی* که ما استخراج کردیم:
    (S1) «Most of the bars are trend bars in the direction of the trend» ⇒
         نسبتِ کندل‌های صعودی در پنجرهٔ اخیر بالا باشد (trend-bar ratio).
    (S2) «Bars with no/small tails … indicating urgency» + «little overlap of bodies»
         ⇒ میانگینِ نسبتِ |body|/range در پنجرهٔ اخیر بالا باشد (فوریتِ خریداران).
    (S3) «No two consecutive trend bar closes on the opposite side of the MA» +
         «sequence of 20 moving-average gap bars» ⇒ قیمت مدتی است پیوسته بالای EMA
         مانده و آن را لمس نکرده (MA-gap / یک‌طرفه بودنِ close نسبت به EMA).
    (S4) «Trending highs and lows (swings)» ⇒ higher-highs و higher-lows در پنجرهٔ اخیر.

  همهٔ این چهار نشانه ذاتاً causal و shift-safe محاسبه می‌شوند (فقط از گذشته/حال) و
  سپس یک کندل shift می‌شوند تا هیچ look-ahead نداشته باشند. این با ساختارِ Brooks
  High-2 (S168/S170) فرق دارد: آنجا «شمارشِ بار در اصلاح» ملاک بود؛ اینجا «کیفیتِ
  روندِ فعلی» به‌صورتِ نمرهٔ پیوسته سنجیده می‌شود.

فرضیهٔ ازپیش‌تعریف‌شده:
  لایه‌های روندی/زمان-محورِ مرزی (WR نزدیکِ کفِ ۴۰٪) هیچ سنجهٔ «قدرتِ روند» ندارند.
  اگر ورود را مشروط کنیم به «Signs-of-Strength score ≥ آستانه» انتظار می‌رود
  معاملاتِ ضعیف (در روندِ ضعیف/رنج) رد شوند ⇒ WR↑ و در حالتِ ایده‌آل net↑.

راهبردِ همپوشانی (قانونِ صریحِ پرامپت):
  این استراتژی *عمداً* به‌شکلِ «فیلترِ تأیید» طراحی شده (راهِ اولِ پروژه = بهبود).
  اگر روی لایه‌ای بهبودِ هم‌زمانِ WR↑ و net↑ بدهد، به‌عنوان بهبود ثبت می‌شود.

گیتِ پذیرش (سیب‌به‌سیب با S170):
  • WR جدید ≥ WR baseline و WR≥۴۰٪.
  • net جدید ≥ net baseline (وگرنه فیلتر ارزش‌افزوده ندارد).
  • n≥۳۰.
  • اعتبارسنجیِ نهایی (فایلِ walkforward جدا): net>0 در هر ۴ پنجره + هر دو نیمه.

متدولوژی: همان baselineهای S170 (همان SL/TP/mh/فیلترِ امتیازیِ S163) روی ۴ سالِ اخیر
با مشخصاتِ واقعیِ حساب (طلا ۳.۳pip، EURUSD ۱.۰pip، کمیسیون صفر).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import indicators as ind

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


# ============================================================================
#  Signs of Strength — نمرهٔ عددیِ قدرتِ روندِ صعودی (فصلِ ۱۹ Al Brooks)
# ============================================================================
def signs_of_strength_bull(df, ema_period=20, win=20):
    """چهار نشانهٔ عددیِ Brooks برای «روندِ صعودیِ قوی» (همه causal، shift-safe).

    خروجی: دیکشنری از سیگنال‌های بولی هر نشانه + نمرهٔ جمع (0..4).
      S1 trend_bar_ratio  : نسبتِ کندل‌های صعودی (close>open) در win کندلِ اخیر ≥ 0.60
      S2 body_urgency     : میانگینِ |body|/range در win کندلِ اخیر ≥ 0.55
      S3 ma_gap_oneside   : در win کندلِ اخیر هیچ close زیرِ EMA نبوده (یک‌طرفهٔ کامل)
      S4 trending_swings  : هم higher-high و هم higher-low بین نیمهٔ اول و دومِ پنجره
    """
    o = df['open'].to_numpy(); h = df['high'].to_numpy()
    l = df['low'].to_numpy(); c = df['close'].to_numpy()
    n = len(df)
    ema = ind.ema(pd.Series(c), ema_period).to_numpy()

    # --- S1: trend-bar ratio ---
    bull_bar = (c > o).astype(float)
    tb_ratio = pd.Series(bull_bar).rolling(win, min_periods=win).mean().to_numpy()
    s1 = np.nan_to_num(tb_ratio, nan=0.0) >= 0.60

    # --- S2: body / range urgency ---
    rng = np.maximum(h - l, 1e-12)
    body_frac = np.abs(c - o) / rng
    bf_mean = pd.Series(body_frac).rolling(win, min_periods=win).mean().to_numpy()
    s2 = np.nan_to_num(bf_mean, nan=0.0) >= 0.55

    # --- S3: MA-gap / یک‌طرفه بودنِ close نسبت به EMA (هیچ close زیرِ EMA در win اخیر) ---
    close_below = (c < ema).astype(float)
    below_cnt = pd.Series(close_below).rolling(win, min_periods=win).sum().to_numpy()
    s3 = np.nan_to_num(below_cnt, nan=win) <= 0.0

    # --- S4: trending highs & lows (swings) ---
    half = win // 2
    hh_recent = pd.Series(h).rolling(half, min_periods=half).max().to_numpy()
    hh_prev = pd.Series(h).shift(half).rolling(half, min_periods=half).max().to_numpy()
    ll_recent = pd.Series(l).rolling(half, min_periods=half).min().to_numpy()
    ll_prev = pd.Series(l).shift(half).rolling(half, min_periods=half).min().to_numpy()
    s4 = (np.nan_to_num(hh_recent, nan=-1) > np.nan_to_num(hh_prev, nan=1e18)) & \
         (np.nan_to_num(ll_recent, nan=-1) > np.nan_to_num(ll_prev, nan=1e18))

    score = s1.astype(int) + s2.astype(int) + s3.astype(int) + s4.astype(int)
    return dict(s1=s1, s2=s2, s3=s3, s4=s4, score=score)


def sos_filter(df, threshold, ema_period=20, win=20):
    """فیلترِ نهایی: نمرهٔ SoS ≥ آستانه؛ سپس shift(1) برای ضدِ look-ahead."""
    sos = signs_of_strength_bull(df, ema_period=ema_period, win=win)
    raw = sos['score'] >= threshold
    return pd.Series(raw).shift(1).fillna(False).to_numpy()


def evaluate_layer(name, df, base_sig, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    base = stats(sim(df, base_sig, z, sl, tp, mh, asset), asset)

    variants = []
    # گریدِ (window × آستانه) — window: افق نگاهِ روند؛ threshold: چند نشانه از ۴
    for win in (12, 20, 32):
        for thr in (2, 3, 4):
            filt = sos_filter(df, thr, ema_period=20, win=win)
            sig = base_sig & filt
            r = stats(sim(df, sig, z, sl, tp, mh, asset), asset)
            variants.append(dict(mode=f'SoS_w{win}_thr{thr}', win=win, thr=thr, **r))

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
    print("S171 — فیلترِ Signs of Strength (فصلِ ۱۹ Al Brooks) روی لایه‌های روندی/زمان-محورِ مرزی")
    print("گیت: WR↑ (≥base و ≥40) و net↑ (≥base). هدفِ نهایی = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    layers = []

    # ---------- طلا M15 ----------
    dfx = cal(lastn(cal(load('XAUUSD_M15'))))
    sc_g = confirms(dfx, KEYS)

    # S140 Monday⁺ : Monday×hours & score>=3 ، SL100/TP300/mh96
    b140 = ((dfx['dow'].values == 0) & np.isin(dfx['hour'].values, [18, 19, 20, 21])) & (sc_g >= 3)
    layers.append(evaluate_layer('S140 Monday+', dfx, b140, 100, 300, 96, 'XAUUSD'))

    # S142 Mid-Month : dom{10,13,20}×hours(1..12) ، SL100/TP500/mh96
    b142 = np.isin(dfx['dom'].values, [10, 13, 20]) & np.isin(dfx['hour'].values, list(range(1, 13)))
    layers.append(evaluate_layer('S142 Mid-Month', dfx, b142, 100, 500, 96, 'XAUUSD'))

    # ---------- یورو M15 ----------
    dfe = cal(lastn(cal(load('EURUSD_M15'))))
    sc_e = confirms(dfe, KEYS)
    b143 = (np.isin(dfe['dom'].values, [3, 9, 20]) &
            np.isin(dfe['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc_e >= 2))
    layers.append(evaluate_layer('S143 EURUSD Mid-Month+', dfe, b143, 20, 40, 96, 'EURUSD'))

    # ---------- گزارش ----------
    print("\n" + "=" * 116)
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
            print(f"     {v['mode']:16s} WR={v['wr']:5.1f}%  net=${v['net']:+9,.0f}  "
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
    print(f"اثرِ خالصِ کلِ فیلترِ Signs-of-Strength (جمعِ بهبودها) = ${total_delta:+,.0f}")
    print("=" * 116)
    record_before = 225130
    record_after = record_before + total_delta
    print(f"رکوردِ قبل = +${record_before:,.0f}   ⇒   رکوردِ پس از فیلتر = +${record_after:,.0f}")

    summary = dict(strategy='S171 Brooks Signs-of-Strength (ch.19) confirmation filter on trend/time-drift layers',
                   layers=out, total_delta=float(total_delta),
                   record_before=record_before, record_after=float(record_after))
    with open(os.path.join(RESULTS, '_s171_signs_of_strength.json'), 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=float)
    print("✅ ذخیره شد: results/_s171_signs_of_strength.json")
    return summary


if __name__ == '__main__':
    main()
