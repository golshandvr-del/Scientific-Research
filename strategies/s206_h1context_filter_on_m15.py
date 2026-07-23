"""
s206_h1context_filter_on_m15.py — قانونِ سوم (جهتِ فیلتر): context‌ِ H1 روی SoS-M15 رکورد
================================================================================
راهِ ۱ (بهبودِ لایهٔ موجود): به‌جای افزودنِ SoS-H1 مستقل (که در S205 غیرافزایشی بود)،
حالتِ H1 را به‌عنوان **فیلترِ تأییدِ مولتی‌تایم‌فریم** روی ورودهای **SoS-M15 رکورد**
می‌آزماییم. برای هر ورودِ M15، آخرین کندلِ H1 ِ *بسته‌شده* (causal، merge_asof backward)
را می‌یابیم و شرط‌های context را روی آن می‌سنجیم.

فیلترهای کاندید روی H1: ATR14>ATR100 · price>EMA200 · EMA50>EMA200 · MACD>0 · RSI∈[35,70]
و ترکیب‌های دو‌تایی. معیارِ پذیرش (هدف = سودِ خالص):
   net_filtered > net_baseline  ∧  WR≥40  ∧  WF ۴/۴ مثبت.
اگر net کم شد اما WR بالا رفت ⇒ بهبود نیست (چون هدف سودِ خالص است)، مگر برای احیای
لایه‌های سوختهٔ WR-پایین (این‌جا موضوعیت ندارد چون SoS-M15 از پیش WR بالا دارد).
"""
import os, sys, json, itertools
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from engine import indicators as ind
from s171_brooks_signs_of_strength_filter import (
    load, cal, stats, sim, signs_of_strength_bull)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIGN = pd.Timestamp('2020-02-20')


def sos_edge(df):
    sos = signs_of_strength_bull(df, ema_period=20, win=32)
    strong = sos['score'] >= 2
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


def h1_context(dfh):
    """جدولِ ویژگی‌های context روی H1 (همه causal، مقدار در بستنِ همان کندلِ H1)."""
    c = dfh['close']
    e50 = ind.ema(c, 50).values; e200 = ind.ema(c, 200).values
    a14 = ind.atr(dfh, 14).values; a100 = ind.atr(dfh, 100).values
    r14 = ind.rsi(c, 14).values
    _, _, hist = ind.macd(c); hist = hist.values
    price = c.values
    feat = pd.DataFrame({
        'time': dfh['time'].values,
        'ATR14>ATR100': np.nan_to_num((a100 > 0) & (a14 > a100)).astype(int),
        'price>EMA200': np.nan_to_num(price > e200).astype(int),
        'EMA50>EMA200': np.nan_to_num(e50 > e200).astype(int),
        'MACD>0': np.nan_to_num(hist > 0).astype(int),
        'RSI∈[35,70]': np.nan_to_num((r14 >= 35) & (r14 <= 70)).astype(int),
    })
    return feat


def map_h1_to_m15(dfm, feat):
    """برای هر کندلِ M15، آخرین کندلِ H1 ِ بسته‌شده را بچسبان (causal).
       H1 در زمانِ t بازمی‌شود و در t+3600 بسته می‌شود ⇒ برای causality، تنها H1‌هایی
       مجازند که close-time ≤ زمانِ کندلِ M15 باشد. close-time = time + 3600."""
    f = feat.copy()
    f['avail'] = f['time'] + 3600           # لحظه‌ای که این کندلِ H1 در دسترس می‌شود
    left = dfm[['time']].copy().sort_values('time')
    right = f[['avail'] + [c for c in f.columns if c not in ('time', 'avail')]].sort_values('avail')
    m = pd.merge_asof(left, right, left_on='time', right_on='avail', direction='backward')
    return m.sort_index()


def eval_trades(t):
    if t is None or len(t) == 0:
        return dict(net=0, wr=0, n=0, pf=0, wf=[0, 0, 0, 0])
    s = stats(t, 'XAUUSD')
    tt = t.sort_values('entry_bar').reset_index(drop=True)
    k = 4; bnd = [int(len(tt) * i / k) for i in range(k + 1)]
    wf = [round(tt.iloc[bnd[i]:bnd[i+1]]['pnl_pip'].sum()) for i in range(k)]
    return dict(net=round(s['net']), wr=round(s['wr'], 1), n=s['n'],
                pf=round(s['pf'], 2), wf=wf)


def main():
    print("=" * 96)
    print("s206 — فیلترِ context‌ِ H1 روی SoS-M15 رکورد (قانونِ سوم، جهتِ فیلتر / راهِ ۱ بهبود)")
    print("=" * 96, flush=True)

    dfm = cal(load('XAUUSD_M15')); dfm = dfm[dfm['dt'] >= ALIGN].reset_index(drop=True)
    dfh = cal(load('XAUUSD_H1'));  dfh = dfh[dfh['dt'] >= ALIGN].reset_index(drop=True)

    # baseline: SoS-M15 رکورد
    edge = sos_edge(dfm); z = np.zeros(len(dfm), bool)
    base_t = sim(dfm, edge, z, 300, 450, 96, 'XAUUSD').copy()
    base = eval_trades(base_t)
    print(f"\nBASELINE  SoS-M15 (SL300/TP450/mh96): net=${base['net']:+,} · WR={base['wr']}% · "
          f"n={base['n']} · PF={base['pf']} · WF={base['wf']}")

    # نگاشتِ context H1 → M15 (causal)
    feat = h1_context(dfh)
    h1map = map_h1_to_m15(dfm, feat)
    feat_cols = ['ATR14>ATR100', 'price>EMA200', 'EMA50>EMA200', 'MACD>0', 'RSI∈[35,70]']
    # مقدارِ فیلتر در signal_bar هر تریدِ M15
    sb = base_t['signal_bar'].values
    h1_at_sig = {c: np.nan_to_num(h1map[c].values)[sb].astype(bool) for c in feat_cols}

    # جاروبِ فیلترها: تک و دوتایی
    combos = [(c,) for c in feat_cols] + list(itertools.combinations(feat_cols, 2))
    rows = []
    for keys in combos:
        m = np.ones(len(base_t), bool)
        for k in keys:
            m &= h1_at_sig[k]
        r = eval_trades(base_t[m])
        improved = (r['net'] > base['net'] and r['wr'] >= 40 and min(r['wf']) > 0
                    and r['n'] >= 30)
        rows.append(dict(keys=keys, r=r, improved=improved,
                         d_net=r['net'] - base['net']))

    rows.sort(key=lambda x: -x['r']['net'])
    print("\n— نتایجِ فیلتر (مرتب بر net) —")
    for x in rows[:12]:
        tag = '✅بهبود' if x['improved'] else '      '
        print(f"  {tag} H1[{'+'.join(x['keys']):26s}] net=${x['r']['net']:+7,} "
              f"(Δ{x['d_net']:+,}) WR={x['r']['wr']:.1f}% n={x['r']['n']:3d} "
              f"PF={x['r']['pf']} WF={x['r']['wf']}")

    winners = [x for x in rows if x['improved']]
    print("\n" + "=" * 96)
    if winners:
        best = winners[0]
        print(f"✅ بهترین بهبود: H1[{'+'.join(best['keys'])}]  Δnet={best['d_net']:+,}  "
              f"(net ${base['net']:+,} → ${best['r']['net']:+,})")
        verdict = 'IMPROVE'
    else:
        print("❌ هیچ فیلترِ context‌ِ H1 نتوانست net‌ِ SoS-M15 را افزایش دهد (با حفظِ WF/WR).")
        print("   فیلترها یا net را کم کردند (حذفِ تریدِ سودده) یا WF را شکستند.")
        verdict = 'NONE'
    print("=" * 96)

    out = dict(baseline=base, verdict=verdict,
               top=[dict(keys=x['keys'], **x['r'], d_net=x['d_net']) for x in rows[:10]],
               winners=[dict(keys=x['keys'], **x['r'], d_net=x['d_net']) for x in winners[:5]])
    with open(os.path.join(ROOT, 'results', '_s206_h1_filter_on_m15.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("ذخیره شد: results/_s206_h1_filter_on_m15.json")


if __name__ == '__main__':
    main()
