# -*- coding: utf-8 -*-
"""
S175-FILTER — استفاده از «Failed-Breakout Reversal» (فصلِ ۳) به‌عنوان فیلترِ تأیید
روی لایه‌های زمان-محورِ مرزیِ موجود (راهِ اولِ پروژه: بهبودِ WR/سودِ لایه‌های موجود).
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت)
> هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR تابعِ هدف نیست اما هر لایهٔ
> فعال باید WR≥۴۰٪ داشته باشد. تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (قانونِ همپوشانیِ پرامپت — پیش از رفتن به فصلِ بعد):
  در S175-finalize، لبهٔ Failed-Breakout به‌عنوان لایهٔ مستقل رد شد (سهمِ مستقل
  walk-forward را پاس نکرد، ۶۰٪ همپوشان با اجتماعِ LONG، عمدتاً ۵۵٪ با High-2).
  اما دو یافتهٔ مهم:
    • Δ(failed-breakout − baseline no-pierce) = +$1,722 (>0) ⇒ شرطِ الگو *واقعاً*
      کیفیتِ ورود را بالا می‌برد؛ صرفاً long-bias نیست.
    • همپوشانیِ بالا با پرتفوی ⇒ نامزدِ عالیِ «فیلترِ تأیید».
  طبقِ قانونِ صریحِ پرامپت (اگر به همپوشانی رسیدی، امکانِ فیلتر را همان‌جا بررسی کن و
  به مراحلِ بعد موکول نکن) این فایل failed-breakout را به‌عنوان فیلتر می‌آزماید.

فرضیه:
  لایه‌های زمان-محورِ مرزی فقط بر «پنجرهٔ تقویمی/ساعتی» تکیه دارند. اگر ورود را مشروط
  کنیم به «به‌تازگی یک failed-breakout-reversal روی یک سطحِ حمایتِ ساختاری رخ داده»
  (تأییدِ اینکه خریداران از سطحِ حمایت دفاع کرده‌اند)، کیفیتِ ورود بالا می‌رود.

  فیلتر: fbo_recent(w) = «آیا در w کندلِ اخیر یک failed-breakout-reversal LONG رخ داده؟»
  با AND روی سیگنالِ baseline. shift-safe.

گیتِ پذیرشِ فیلتر (هم‌سو با S170):
  WR جدید ≥ WR baseline  AND  WR≥۴۰٪  AND  net جدید ≥ net baseline  AND  n≥۳۰.
  (طبقِ قانونِ #۱ سودِ خالص حرفِ آخر را می‌زند — اگر net نیفتد اما WR بالا رود، پذیرش.)

متدولوژی سیب‌به‌سیب با S170 (همان baselineهای مرزی).
خروجی: results/_s175_fbo_filter.json
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from engine import scalp_engine as se
from engine import indicators as ind
import s175_brooks_failed_breakout as FB

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


def halves(df, ls, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    tr = sim(df, ls, z, sl, tp, mh, asset)
    if tr is None or len(tr) < 30:
        return None
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=False)
    nu = pt['net_usd']; h = len(nu) // 2
    return dict(h1=float(nu.iloc[:h].sum()), h2=float(nu.iloc[h:].sum()))


def dxy(dfa):
    d = load('DXY_M15'); d['e'] = ind.ema(d['close'], 200)
    bear = (d['close'] < d['e']).astype(float)
    a = dfa[['time']].copy(); a['idx'] = np.arange(len(a))
    m = pd.merge_asof(a.sort_values('time'), d[['time']].assign(b=bear.values).sort_values('time'),
                      on='time', direction='backward').sort_values('idx')
    return np.nan_to_num(m['b'].values, nan=0) > 0.5


KEYS = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'MACD>0', 'RSI∈[35,70]', 'DXY<EMA200']


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


def fbo_recent(df, k, win_pat, w):
    """فیلتر: آیا در w کندلِ اخیر یک failed-breakout-reversal LONG رخ داده؟
    (سیگنالِ خامِ FB قبلاً shift(1) دارد؛ اینجا rolling روی گذشته ⇒ causal.)"""
    fb = FB.failed_breakout_signals(df, 'swing', k, win_pat, 'long')  # bool، shift-safe
    rolled = pd.Series(fb.astype(float)).rolling(w, min_periods=1).sum().to_numpy()
    return rolled > 0


def evaluate_layer(name, df, base_sig, sl, tp, mh, asset, k=3, win_pat=3):
    z = np.zeros(len(df), bool)
    base = stats(sim(df, base_sig, z, sl, tp, mh, asset), asset)
    hv_b = halves(df, base_sig, sl, tp, mh, asset)

    variants = []
    for w in (8, 16, 32, 64, 96):
        filt = fbo_recent(df, k, win_pat, w)
        sig = base_sig & filt
        r = stats(sim(df, sig, z, sl, tp, mh, asset), asset)
        hv = halves(df, sig, sl, tp, mh, asset)
        r['both_ok'] = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
        variants.append(dict(mode=f'fbo_recent_w{w}', **r))

    def ok(v):
        return (v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['wr'] >= base['wr']
                and v['net'] >= base['net'] and v['both_ok'])
    accepted = [v for v in variants if ok(v)]
    accepted.sort(key=lambda v: v['net'], reverse=True)
    best = accepted[0] if accepted else None
    return dict(name=name, asset=asset, base=base, base_both=hv_b, variants=variants,
                best_filter=best, delta_net=(best['net'] - base['net']) if best else 0.0)


def main():
    print("=" * 100)
    print("S175-FILTER — Failed-Breakout Reversal (فصلِ ۳) به‌عنوان فیلترِ تأیید روی لایه‌های مرزی")
    print("گیت: WR↑ (≥base و ≥40) و net↑ (≥base) و هر دو نیمه مثبت. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    layers = []

    # ---------- طلا M15 ----------
    dfx = cal(lastn(load('XAUUSD_M15')))
    sc_g = confirms(dfx, KEYS)

    # S140 Monday⁺
    b140 = ((dfx['dow'].values == 0) & np.isin(dfx['hour'].values, [18, 19, 20, 21])) & (sc_g >= 3)
    layers.append(evaluate_layer('S140 Monday+', dfx, b140, 100, 300, 96, 'XAUUSD'))

    # S142 Mid-Month
    b142 = np.isin(dfx['dom'].values, [10, 13, 20]) & np.isin(dfx['hour'].values, list(range(1, 13)))
    layers.append(evaluate_layer('S142 Mid-Month', dfx, b142, 100, 500, 96, 'XAUUSD'))

    # S144 End-of-Month Pre-End (نامزدِ ضعیفِ audit، +$1,097)
    dom = dfx['dom'].values
    dim = dfx['dt'].dt.days_in_month.values
    to_end = dim - dom
    b144 = (to_end >= 6) & (to_end <= 8) & np.isin(dfx['hour'].values, list(range(1, 13)))
    layers.append(evaluate_layer('S144 EndOfMonth', dfx, b144, 100, 400, 96, 'XAUUSD'))

    # ---------- یورو M15 ----------
    dfe = cal(lastn(load('EURUSD_M15')))
    sc_e = confirms(dfe, KEYS)
    b143 = (np.isin(dfe['dom'].values, [3, 9, 20]) &
            np.isin(dfe['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc_e >= 2))
    layers.append(evaluate_layer('S143 EURUSD Mid-Month+', dfe, b143, 20, 40, 96, 'EURUSD'))

    # ---------- گزارش ----------
    print("\n" + "=" * 116)
    total_delta = 0.0
    out = []
    for L in layers:
        b = L['base']; bf = L['best_filter']; hb = L['base_both']
        both_b = bool(hb and hb['h1'] > 0 and hb['h2'] > 0)
        print(f"\n▶ {L['name']}  ({L['asset']})")
        print(f"   baseline: WR={b['wr']:.1f}%  net=${b['net']:+,.0f}  n={b['n']}  PF={b['pf']:.2f}  both_ok={both_b}")
        for v in L['variants']:
            mark = ''
            if (v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['wr'] >= b['wr']
                    and v['net'] >= b['net'] and v['both_ok']):
                mark = '  ✅ بهبود'
            print(f"     {v['mode']:16s} WR={v['wr']:5.1f}%  net=${v['net']:+9,.0f}  "
                  f"n={v['n']:4d}  PF={v['pf']:.2f}  both={v['both_ok']}{mark}")
        if bf:
            d = bf['net'] - b['net']
            total_delta += d
            print(f"   🏅 بهترین: {bf['mode']}  ⇒ WR {b['wr']:.1f}%→{bf['wr']:.1f}%  "
                  f"net ${b['net']:+,.0f}→${bf['net']:+,.0f}  (Δ{d:+,.0f})")
        else:
            print(f"   ⛔ هیچ فیلتری هم‌زمان WR↑ و net↑ و both_ok نداد ⇒ این لایه بی‌بهبود.")
        out.append(dict(name=L['name'], asset=L['asset'],
                        base_wr=b['wr'], base_net=b['net'], base_n=b['n'], base_pf=b['pf'],
                        best_filter=bf, variants=L['variants'], delta_net=L['delta_net']))

    print("\n" + "=" * 116)
    print(f"اثرِ خالصِ کلِ فیلترِ Failed-Breakout (جمعِ بهبودها) = ${total_delta:+,.0f}")
    print("=" * 116)

    summary = dict(strategy='S175 Failed-Breakout as confirmation filter on time-drift layers',
                   layers=out, total_delta=float(total_delta))
    with open(os.path.join(RESULTS, '_s175_fbo_filter.json'), 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=float)
    print("✅ ذخیره شد: results/_s175_fbo_filter.json")
    return summary


if __name__ == '__main__':
    main()
