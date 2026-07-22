# -*- coding: utf-8 -*-
"""
S170 — اعتبارسنجیِ ضدِ overfit برای تنها بهبودِ پذیرفته‌شده:
       S143 EURUSD Mid-Month⁺  +  فیلترِ Brooks High-2 (recent-High2 پنجرهٔ ۹۶).

قانونِ #۱: هدف سودِ خالص؛ WR≥۴۰ کفِ اجباری. این فایل فقط اعتبارِ زمانیِ بهبود را می‌سنجد.

گیتِ سختِ پذیرش (همه باید سبز شوند وگرنه بهبود رد و رکورد دست‌نخورده می‌ماند):
  (۱) net کلِ فیلترشده > net کلِ baseline (Δ>0).
  (۲) هر دو نیمهٔ داده: net_filtered ≥ net_base (فیلتر در هر دو نیمه ارزش‌افزوده دارد
      یا دست‌کم زیان نمی‌زند) و WR_filtered ≥ ۴۰.
  (۳) هر ۴ پنجرهٔ walk-forward: net_filtered ≥ net_base (فیلتر پایدار در زمان است).
  (۴) WR کلِ فیلترشده ≥ WR baseline و ≥ ۴۰.
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
WINDOW = 96
EMA_F, EMA_S = 20, 50
SL, TP, MH = 20, 40, 96
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


def statd(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values; w = int((nu > 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()); gl = float(-nu[nu <= 0].sum())
    return dict(net=float(st['net_profit']), n=n, wr=(w / n * 100 if n else 0.0),
                pf=(gp / gl if gl > 0 else float('inf')))


def sim(df, ls, asset):
    z = np.zeros(len(df), bool)
    t = se.simulate_trades(df, ls, z, SL, TP, asset, max_hold=MH, allow_overlap=False)
    if t is None or len(t) == 0:
        return None
    t = t.copy(); t['sl_pip'] = float(SL)
    return t


def dxy_align(dfa):
    d = load('DXY_M15'); d['e'] = ind.ema(d['close'], 200)
    bear = (d['close'] < d['e']).astype(float)
    a = dfa[['time']].copy(); a['idx'] = np.arange(len(a))
    m = pd.merge_asof(a.sort_values('time'), d[['time']].assign(b=bear.values).sort_values('time'),
                      on='time', direction='backward').sort_values('idx')
    return np.nan_to_num(m['b'].values, nan=0) > 0.5


def confirms(df):
    keys = ['price>EMA200', 'EMA50>EMA200', 'ATR14>ATR100', 'MACD>0', 'RSI∈[35,70]', 'DXY<EMA200']
    c = df['close']; e50 = ind.ema(c, 50).values; e200 = ind.ema(c, 200).values
    a14 = ind.atr(df, 14).values; a100 = ind.atr(df, 100).values; r14 = ind.rsi(c, 14).values
    _, _, hist = ind.macd(c); hist = hist.values; price = c.values
    allf = {'price>EMA200': np.nan_to_num(price > e200, nan=False).astype(bool),
            'EMA50>EMA200': np.nan_to_num(e50 > e200, nan=False).astype(bool),
            'ATR14>ATR100': np.nan_to_num((a100 > 0) & (a14 > a100), nan=False).astype(bool),
            'MACD>0': np.nan_to_num(hist > 0, nan=False).astype(bool),
            'RSI∈[35,70]': np.nan_to_num((r14 >= 35) & (r14 <= 70), nan=False).astype(bool),
            'DXY<EMA200': dxy_align(df)}
    sc = np.zeros(len(df), int)
    for k in keys:
        sc += allf[k].astype(int)
    return sc


def build_base(df):
    sc = confirms(df)
    return (np.isin(df['dom'].values, [3, 9, 20]) &
            np.isin(df['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc >= 2))


def brooks_filter(df):
    long_evt, _ = count_high2_low2(df, EMA_F, EMA_S)
    s = pd.Series(long_evt.astype(float))
    rolled = s.rolling(WINDOW, min_periods=1).sum().to_numpy() > 0
    return pd.Series(rolled).shift(1).fillna(False).to_numpy()


def main():
    print("=" * 96)
    print("S170 validate — پایداریِ فیلترِ Brooks روی S143 EURUSD Mid-Month⁺ (window=96)")
    print("=" * 96, flush=True)

    dfe = cal(lastn(cal(load('EURUSD_M15'))))
    base_sig = build_base(dfe)
    filt = brooks_filter(dfe)
    filt_sig = base_sig & filt

    b_all = statd(sim(dfe, base_sig, 'EURUSD'), 'EURUSD')
    f_all = statd(sim(dfe, filt_sig, 'EURUSD'), 'EURUSD')
    print(f"\nکل:  baseline WR={b_all['wr']:.1f}% net=${b_all['net']:+,.0f} n={b_all['n']}")
    print(f"     فیلتر   WR={f_all['wr']:.1f}% net=${f_all['net']:+,.0f} n={f_all['n']}  "
          f"(Δnet={f_all['net']-b_all['net']:+,.0f})")

    # --- both-halves ---
    n = len(dfe); half = n // 2
    d1 = dfe.iloc[:half].reset_index(drop=True); d2 = dfe.iloc[half:].reset_index(drop=True)
    halves = []
    for tag, d in (('H1', d1), ('H2', d2)):
        bs = build_base(d); fs = bs & brooks_filter(d)
        b = statd(sim(d, bs, 'EURUSD'), 'EURUSD'); f = statd(sim(d, fs, 'EURUSD'), 'EURUSD')
        halves.append((tag, b, f))
        print(f"\n{tag}: base WR={b['wr']:.1f}% net=${b['net']:+,.0f} n={b['n']}  |  "
              f"filt WR={f['wr']:.1f}% net=${f['net']:+,.0f} n={f['n']}  Δ={f['net']-b['net']:+,.0f}")

    # --- walk-forward ۴ پنجره ---
    edges = np.linspace(0, n, 5, dtype=int); wf = []
    print("\nWalk-forward (۴ پنجره):")
    for k in range(4):
        d = dfe.iloc[edges[k]:edges[k+1]].reset_index(drop=True)
        bs = build_base(d); fs = bs & brooks_filter(d)
        b = statd(sim(d, bs, 'EURUSD'), 'EURUSD'); f = statd(sim(d, fs, 'EURUSD'), 'EURUSD')
        wf.append((b, f))
        print(f"  W{k+1}: base net=${b['net']:+8,.0f} WR={b['wr']:5.1f}%  |  "
              f"filt net=${f['net']:+8,.0f} WR={f['wr']:5.1f}% n={f['n']:3d}  Δ={f['net']-b['net']:+,.0f}")

    # --- گیت‌ها ---
    g1 = f_all['net'] > b_all['net']
    g2 = all((f['net'] >= b['net'] and f['wr'] >= WR_FLOOR) for _, b, f in halves)
    g3 = all((f['net'] >= b['net']) for b, f in wf)
    g4 = (f_all['wr'] >= b_all['wr'] and f_all['wr'] >= WR_FLOOR)

    print("\n" + "=" * 96)
    print(f"گیت ۱ (Δnet کل>0):                    {'✅' if g1 else '❌'}")
    print(f"گیت ۲ (هر دو نیمه: filt≥base و WR≥40): {'✅' if g2 else '❌'}")
    print(f"گیت ۳ (هر ۴ پنجره: filt≥base):        {'✅' if g3 else '❌'}")
    print(f"گیت ۴ (WR کل ↑ و ≥40):                {'✅' if g4 else '❌'}")
    all_ok = g1 and g2 and g3 and g4
    print("-" * 96)
    print(f"نتیجه: {'✅ فیلتر پایدار — پذیرفته' if all_ok else '⛔ فیلتر ناپایدار — رد (رکورد دست‌نخورده)'}")
    delta = (f_all['net'] - b_all['net']) if all_ok else 0.0
    print(f"Δ سودِ خالصِ رسمی = ${delta:+,.0f}")

    out = dict(layer='S143 EURUSD Mid-Month+ / Brooks High-2 filter (w96)',
               base_all=b_all, filt_all=f_all,
               halves=[dict(tag=t, base=b, filt=f) for t, b, f in halves],
               walk_forward=[dict(base=b, filt=f) for b, f in wf],
               gates=dict(g1=bool(g1), g2=bool(g2), g3=bool(g3), g4=bool(g4)),
               accepted=bool(all_ok), delta_net=float(delta))
    with open(os.path.join(RESULTS, '_s170_walkforward.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("✅ ذخیره شد: results/_s170_walkforward.json")


if __name__ == '__main__':
    main()
