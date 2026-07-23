"""
s204_sos_h1_independent_filtered.py — قانونِ سومِ همپوشانی + قانونِ دومِ بهبود
================================================================================
S203 نشان داد سهمِ *واقعاً مستقلِ* SoS-H1 (روزهایی که SoS-M15 ترید ندارد) کوچک و
ناپایدار است (+$322، WF=[−1574,−453,+1087,+1746]). طبقِ قانونِ دومِ بهبود، یک لایه فقط
وقتی «سوخته» اعلام می‌شود که **هیچ ترکیبی از بهبودها** آن را نجات ندهد. پس این‌جا روی
همان تریدهای H1، فیلترهای context (تک و ترکیبی) را می‌آزماییم تا:
   (الف) کلِ SoS-H1 پایدارتر/پرسودتر شود، و مهم‌تر
   (ب) سهمِ *مستقلِ* SoS-H1 (بدونِ روزهای M15) به لبهٔ پایدار (WF ۴/۴ مثبت، WR≥۴۰) برسد.

فیلترها روی خودِ H1 محاسبه می‌شوند (causal): price>EMA200, EMA50>EMA200, ATR14>ATR100,
MACD>0, RSI∈[35,70], DXY<EMA200 — دقیقاً همان مجموعهٔ رکوردِ S171 (تابعِ confirms).
هر ترکیبِ ۱ و ۲ و ۳ فیلتری جاروب می‌شود. گیتِ سخت روی سهمِ مستقل: net>0 ∧ WF۴/۴>0 ∧ WR≥۴۰.
"""
import os, sys, json, itertools
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from s171_brooks_signs_of_strength_filter import (
    load, cal, stats, sim, signs_of_strength_bull, confirms, KEYS)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIGN = pd.Timestamp('2020-02-20')


def sos_edge(df):
    sos = signs_of_strength_bull(df, ema_period=20, win=32)
    strong = sos['score'] >= 2
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


def m15_trade_days():
    dfm = cal(load('XAUUSD_M15')); dfm = dfm[dfm['dt'] >= ALIGN].reset_index(drop=True)
    edge = sos_edge(dfm); z = np.zeros(len(dfm), bool)
    t = sim(dfm, edge, z, 300, 450, 96, 'XAUUSD')
    days = dfm['dt'].iloc[t['entry_bar'].values].dt.floor('D')
    return set(days.values)


def eval_trades(t, asset='XAUUSD'):
    if t is None or len(t) == 0:
        return dict(net=0, wr=0, n=0, pf=0, wf=[0, 0, 0, 0])
    s = stats(t, asset)
    tt = t.sort_values('entry_bar').reset_index(drop=True)
    k = 4; bnd = [int(len(tt) * i / k) for i in range(k + 1)]
    # pnl دلاری تقریبی با ۰.۰۱ لات پایه (فقط علامتِ WF مهم است)
    wf = [round(tt.iloc[bnd[i]:bnd[i+1]]['pnl_pip'].sum()) for i in range(k)]
    return dict(net=s['net'], wr=s['wr'], n=s['n'], pf=s['pf'], wf=wf)


def main():
    print("=" * 96)
    print("s204 — قانونِ سوم/دوم: بهبودِ سهمِ مستقلِ SoS-H1 با فیلترهای context")
    print("=" * 96, flush=True)

    dfh = cal(load('XAUUSD_H1')); dfh = dfh[dfh['dt'] >= ALIGN].reset_index(drop=True)
    edge = sos_edge(dfh); z = np.zeros(len(dfh), bool)
    base_t = sim(dfh, edge, z, 250, 750, 96, 'XAUUSD')
    base_t = base_t.copy()
    base_t['day'] = dfh['dt'].iloc[base_t['entry_bar'].values].dt.floor('D').values

    m15days = m15_trade_days()
    indep_mask_days = ~base_t['day'].isin(m15days)

    # فیلترهای context روی H1 (مقدار در entry_bar)
    conf = {k: confirms(dfh, [k]) for k in KEYS}   # هر کلید: آرایهٔ score 0/1 روی H1
    # نگاشتِ entry_bar → مقدارِ فیلتر (causal: از signal_bar استفاده می‌کنیم)
    sb = base_t['signal_bar'].values

    def passes(keys):
        m = np.ones(len(base_t), bool)
        for k in keys:
            m &= conf[k][sb].astype(bool)
        return m

    print("\n— مرجع (بدون فیلتر) —")
    print(f"  کلِ SoS-H1     : ", eval_trades(base_t))
    print(f"  سهمِ مستقل     : ", eval_trades(base_t[indep_mask_days]))

    # جاروبِ فیلترها: تک، دوتایی، سه‌تایی
    results = []
    combos = []
    for r in (1, 2, 3):
        combos += list(itertools.combinations(KEYS, r))

    for keys in combos:
        fmask = passes(keys)
        # کلِ H1 با فیلتر
        allf = eval_trades(base_t[fmask])
        # سهمِ مستقل با فیلتر
        indf = eval_trades(base_t[fmask & indep_mask_days.values])
        gate_indep = (indf['net'] > 0 and indf['n'] >= 20 and indf['wr'] >= 40
                      and min(indf['wf']) > 0)
        gate_all = (allf['net'] > 0 and allf['n'] >= 30 and allf['wr'] >= 40
                    and min(allf['wf']) > 0)
        results.append(dict(keys=keys, allf=allf, indf=indf,
                            gate_indep=gate_indep, gate_all=gate_all))

    # بهترین سهمِ مستقلِ گیت-پاس
    indep_win = [x for x in results if x['gate_indep']]
    indep_win.sort(key=lambda x: -x['indf']['net'])
    all_win = [x for x in results if x['gate_all']]
    all_win.sort(key=lambda x: -x['allf']['net'])

    print("\n" + "=" * 96)
    print(f"سهمِ *مستقلِ* گیت-پاس (net>0 ∧ WF۴/۴>0 ∧ WR≥۴۰ ∧ n≥۲۰): {len(indep_win)} ترکیب")
    for x in indep_win[:8]:
        print(f"  ✅ {'+'.join(x['keys']):55s} net=${x['indf']['net']:+7,.0f} "
              f"WR={x['indf']['wr']:.1f}% n={x['indf']['n']:3d} WF={x['indf']['wf']}")
    if not indep_win:
        print("  ❌ هیچ ترکیبِ فیلتری سهمِ مستقل را به لبهٔ پایدار نرساند.")
        # بهترین‌ها از نظر net برای دیدِ کیفی
        results.sort(key=lambda x: -x['indf']['net'])
        print("  بهترین‌های کیفی (سهمِ مستقل):")
        for x in results[:5]:
            print(f"     {'+'.join(x['keys']):55s} net=${x['indf']['net']:+7,.0f} "
                  f"WR={x['indf']['wr']:.1f}% n={x['indf']['n']:3d} WF={x['indf']['wf']}")

    print(f"\nکلِ SoS-H1 فیلترشدهٔ گیت-پاس: {len(all_win)} ترکیب")
    for x in all_win[:6]:
        print(f"  ✅ {'+'.join(x['keys']):55s} net=${x['allf']['net']:+7,.0f} "
              f"WR={x['allf']['wr']:.1f}% n={x['allf']['n']:3d} WF={x['allf']['wf']}")

    out = dict(
        base_all=eval_trades(base_t),
        base_indep=eval_trades(base_t[indep_mask_days]),
        best_indep=[dict(keys=x['keys'], **x['indf']) for x in indep_win[:5]],
        best_all=[dict(keys=x['keys'], **x['allf']) for x in all_win[:5]],
    )
    with open(os.path.join(ROOT, 'results', '_s204_sos_h1_filtered.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("\nذخیره شد: results/_s204_sos_h1_filtered.json")


if __name__ == '__main__':
    main()
