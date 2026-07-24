# -*- coding: utf-8 -*-
"""
S215_finalize — همپوشانیِ اجباری + سهمِ مستقلِ کاندیدهای برندهٔ S215 (Trend Lines، فصلِ ۱۳)
=========================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

طبقِ «قوانینِ همپوشانی» (اجباری، پیش از فصلِ بعد):
  برای هر TFِ طلا که S215 لبهٔ گیت-پاس داد، بهترین کاندید (بیشینه net) را برمی‌داریم و
  سهمِ مستقلِ آن را نسبت به **اجتماعِ کاملِ لایه‌های LONG طلا** (build_union_mask ِ S214 —
  زمان-محورها ∪ Brooks High-2/Low-2) می‌سنجیم:
    1) چند درصد از معاملاتِ S215 با union همپوشان است؟ (با کدام لایه)
    2) سهمِ مستقل (bar-not-in-union) گیتِ سختِ ۴-گانه را می‌گذراند؟ ⇒ لبهٔ نو
    3) راهِ سومِ همپوشانی: آیا «تستِ اخیرِ خطِ روند» به‌عنوان فیلترِ تأیید روی
       بخشِ همپوشان ارزش دارد؟ (WRِ بخشِ همپوشان vs غیرهمپوشان گزارش می‌شود)

خروجی: results/_s215_finalize.json + جدولِ سهمِ مستقلِ قابلِ ثبت برای هر TF.
"""
import os, sys, json, glob
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s215_brooks_trend_line as X
import s214_finalize as F214            # build_union_mask + wf_halves_from_trades

RESULTS = os.path.join(ROOT, 'results')


def best_per_tf():
    """بهترین کاندید گیت-پاسِ هر TFِ طلا (بیشینه net) از فایل‌های part."""
    best = {}
    for p in sorted(glob.glob(os.path.join(RESULTS, '_s215_part_*.json'))):
        rows = json.load(open(p))
        acc = [r for r in rows if r['accepted'] and r['tf'].startswith('XAUUSD')]
        if not acc:
            continue
        best[rows[0]['tf']] = max(acc, key=lambda r: r['net'])
    return best


def parse_ema(s):
    a, b = s.split('/'); return int(a), int(b)


def analyze(tf, cand):
    asset = 'XAUUSD'
    df = S.lastn(S.load(tf), y=4)
    ef, es = parse_ema(cand['ema'])
    sig = X.trend_line_signals(df, cand['side'], ef, es, cand['k'], cand['pen'], cand['max_gap'])
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, cand['sl'], cand['tp'], cand['mh'], asset)
    if tr is None or len(tr) == 0:
        return None

    union_mask, time_mask, brooks_mask = F214.build_union_mask(df)
    total = len(tr)
    ct = cb = cu = 0
    indep_flag = []
    for _, t in tr.iterrows():
        i = int(t['entry_bar'])
        if i >= len(union_mask):
            i = len(union_mask) - 1
        ct += bool(time_mask[i]); cb += bool(brooks_mask[i]); cu += bool(union_mask[i])
        indep_flag.append(not bool(union_mask[i]))
    indep_flag = np.array(indep_flag, bool)
    tr_ind = tr[indep_flag].reset_index(drop=True)
    tr_ov = tr[~indep_flag].reset_index(drop=True)

    s_all = S.stats(tr, asset)
    s_ind = S.stats(tr_ind, asset) if len(tr_ind) else dict(net=0, wr=0, n=0, pf=0)
    s_ov = S.stats(tr_ov, asset) if len(tr_ov) else dict(net=0, wr=0, n=0, pf=0)

    wfh = F214.wf_halves_from_trades(tr_ind, asset)
    passes = False
    if wfh:
        passes = (s_ind['net'] > 0 and s_ind['wr'] >= 40 and wfh['h1'] > 0 and wfh['h2'] > 0
                  and all(w > 0 for w in wfh['wf']) and s_ind['n'] >= 30)

    return dict(
        tf=tf, cand=cand,
        overlap=dict(time=round(ct/total*100, 1), brooks=round(cb/total*100, 1),
                     union=round(cu/total*100, 1), indep_share=round(len(tr_ind)/total*100, 1)),
        raw=dict(net=round(s_all['net'], 1), wr=round(s_all['wr'], 2), n=s_all['n']),
        indep=dict(net=round(s_ind['net'], 1), wr=round(s_ind['wr'], 2), n=s_ind['n'],
                   pf=(round(s_ind['pf'], 3) if s_ind['pf'] != float('inf') else 999.0),
                   **(wfh or {}), passes=passes),
        overlap_part=dict(net=round(s_ov['net'], 1), wr=round(s_ov['wr'], 2), n=s_ov['n']),
        total=total)


def main():
    print("=" * 96)
    print("S215_finalize — همپوشانیِ اجباری: سهمِ مستقلِ Trend-Line (فصلِ ۱۳) نسبت به Union-All طلا")
    print("=" * 96, flush=True)

    best = best_per_tf()
    out = {}
    tot_indep_registerable = 0.0
    for tf in sorted(best):
        cand = best[tf]
        print(f"\n{'─'*90}\n### {tf}  کاندید: {cand['side']} ema{cand['ema']} k{cand['k']} "
              f"pen{cand['pen']} gap{cand['max_gap']} SL{cand['sl']}/TP{cand['tp']} "
              f"(raw net=${cand['net']:+,.0f})", flush=True)
        try:
            a = analyze(tf, cand)
        except Exception as e:
            print(f"  [err] {e}"); continue
        if a is None:
            print("  [no trades]"); continue
        ov = a['overlap']
        print(f"  همپوشانیِ بار-به-بار (total={a['total']}): زمان={ov['time']}%  "
              f"Brooks_H2L2={ov['brooks']}%  Union-All={ov['union']}%  ⇒ سهمِ مستقل={ov['indep_share']}%")
        ind = a['indep']
        print(f"  مستقل: net=${ind['net']:+,.0f} WR{ind['wr']} n{ind['n']} PF{ind.get('pf')} "
              f"WF={ind.get('wf')}  ⇒ {'✅ لبهٔ نوِ مستقل' if ind['passes'] else '❌ سهمِ مستقل گیت را رد'}")
        ovp = a['overlap_part']
        print(f"  بخشِ همپوشان: net=${ovp['net']:+,.0f} WR{ovp['wr']} n{ovp['n']} "
              f"(اگر WRِ همپوشان بالاتر از مستقل بود ⇒ ارزشِ فیلترِ تأیید)")
        if ind['passes']:
            tot_indep_registerable += ind['net']
        out[tf] = a

    with open(os.path.join(RESULTS, '_s215_finalize.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\n{'='*96}")
    print(f"مجموعِ سودِ خالصِ مستقلِ قابلِ ثبت (محافظه‌کارانه، فقط سهمِ non-union): "
          f"${tot_indep_registerable:+,.0f}")
    print("saved: results/_s215_finalize.json")


if __name__ == '__main__':
    main()
