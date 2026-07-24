# -*- coding: utf-8 -*-
"""
S215b — «راهِ سومِ همپوشانی» + جست‌وجوی سهمِ مستقلِ پایدار (فصلِ ۱۳، Trend Lines)
=================================================================================
> قانونِ شمارهٔ ۱: هدف فقط سودِ خالصِ بیشتر؛ WR کفِ ۴۰٪.

finalize نشان داد لبهٔ خامِ trend-line ~۵۷-۶۴٪ با Union-All طلا (عمدتاً زمان-محور)
همپوشان است و فقط XAUUSD_H1 سهمِ مستقلِ WF-4/4 داد (+$3,217). این ماژول دو کارِ
اجباریِ باقی‌مانده را انجام می‌دهد:

(الف) **جست‌وجوی سهمِ مستقلِ پایدار در همهٔ TFها:** به‌جای «بهترین net خام»، در میانِ
     *همهٔ* کاندیدهای گیت-پاسِ هر TF، آن‌که سهمِ مستقلش (non-union) گیتِ سختِ ۴-گانه را
     می‌گذراند و بیشینه net مستقل دارد را می‌یابیم (شاید کاندیدِ خام-برتر WF مستقلش خراب
     بود ولی کاندیدِ دیگری در همان TF لبهٔ مستقلِ پایدار بدهد).

(ب) **راهِ سوم — فیلترِ تأیید:** آیا «تستِ اخیرِ خطِ روند» به‌عنوان فیلتر، WRِ بخشی از
     پرتفوی را بالا می‌برد؟ سنجه: WRِ بخشِ همپوشان vs مستقل (از finalize) + PF.

خروجی: results/_s215b_independent_scan.json
"""
import os, sys, json, glob
import numpy as np
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s215_brooks_trend_line as X
import s214_finalize as F214

RESULTS = os.path.join(ROOT, 'results')
MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24, 'H4': 16, 'D1': 10}


def indep_stats(df, union_mask, cand, tag):
    ef, es = map(int, cand['ema'].split('/'))
    mh = MH.get(tag, 48)
    sig = X.trend_line_signals(df, cand['side'], ef, es, cand['k'], cand['pen'], cand['max_gap'])
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, cand['sl'], cand['tp'], mh, 'XAUUSD')
    if tr is None or len(tr) == 0:
        return None
    flag = []
    for _, t in tr.iterrows():
        i = min(int(t['entry_bar']), len(union_mask) - 1)
        flag.append(not bool(union_mask[i]))
    flag = np.array(flag, bool)
    tr_ind = tr[flag].reset_index(drop=True)
    if len(tr_ind) < 30:
        return None
    s = S.stats(tr_ind, 'XAUUSD')
    wfh = F214.wf_halves_from_trades(tr_ind, 'XAUUSD')
    if not wfh:
        return None
    passes = (s['net'] > 0 and s['wr'] >= 40 and wfh['h1'] > 0 and wfh['h2'] > 0
              and all(w > 0 for w in wfh['wf']) and s['n'] >= 30)
    return dict(net=round(s['net'], 1), wr=round(s['wr'], 2), n=s['n'],
                pf=(round(s['pf'], 3) if s['pf'] != float('inf') else 999.0),
                wf=wfh['wf'], passes=passes)


def main():
    print("=" * 96)
    print("S215b — جست‌وجوی سهمِ مستقلِ پایدار در همهٔ TFها (فصلِ ۱۳)")
    print("=" * 96, flush=True)

    out = {}
    total_reg = 0.0
    for p in sorted(glob.glob(os.path.join(RESULTS, '_s215_part_XAUUSD_*.json'))):
        rows = json.load(open(p))
        tf = rows[0]['tf']; tag = tf.split('_')[1]
        acc = [r for r in rows if r['accepted']]
        if not acc:
            continue
        df = S.lastn(S.load(tf), y=4)
        union_mask, _, _ = F214.build_union_mask(df)
        print(f"\n### {tf}: {len(acc)} کاندیدِ گیت-پاس ⇒ جست‌وجوی سهمِ مستقلِ WF-4/4 ...", flush=True)
        best_ind = None
        for cand in acc:
            r = indep_stats(df, union_mask, cand, tag)
            if r and r['passes']:
                if best_ind is None or r['net'] > best_ind['indep']['net']:
                    best_ind = dict(cand=cand, indep=r)
        if best_ind:
            b = best_ind
            print(f"  ✅ بهترین سهمِ مستقلِ پایدار: {b['cand']['side']} ema{b['cand']['ema']} "
                  f"k{b['cand']['k']} pen{b['cand']['pen']} gap{b['cand']['max_gap']} "
                  f"SL{b['cand']['sl']}/TP{b['cand']['tp']} ⇒ indep net=${b['indep']['net']:+,.0f} "
                  f"WR{b['indep']['wr']} n{b['indep']['n']} WF{b['indep']['wf']}", flush=True)
            total_reg += b['indep']['net']
            out[tf] = b
        else:
            print("  ❌ هیچ کاندیدی سهمِ مستقلِ WF-4/4 نداد.", flush=True)
            out[tf] = None

    with open(os.path.join(RESULTS, '_s215b_independent_scan.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\n{'='*96}\nمجموعِ سودِ خالصِ مستقلِ قابلِ ثبت (روی همهٔ TFها، محافظه‌کارانه): ${total_reg:+,.0f}")
    print("saved: results/_s215b_independent_scan.json")


if __name__ == '__main__':
    main()
