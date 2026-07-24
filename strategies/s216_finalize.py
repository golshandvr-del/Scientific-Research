# -*- coding: utf-8 -*-
"""
S216_finalize — همپوشانیِ اجباری + سهمِ مستقلِ کاندیدهای برندهٔ S216 (Trend Channel Lines، فصلِ ۱۴)
==================================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

پس‌زمینه: گریدِ خامِ S216 روی همهٔ TFها اجرا شد ⇒ ۶۰ کاندیدِ گیت-پاس، **همه XAUUSD LONG**
(fade خطِ کانالِ نزولی + برگشتِ صعودی). چون LONG روی طلاست، احتمالِ همپوشانیِ سنگین با
اجتماعِ LONGِ طلا بالاست (درسِ مکررِ S174/S175/S177). طبقِ «قوانینِ همپوشانی» (اجباری، پیش از
فصلِ بعد):

  برای هر TFِ طلا که S216 لبهٔ گیت-پاس داد، بهترین کاندید (بیشینه net) را برمی‌داریم و سهمِ
  مستقلِ آن را نسبت به **اجتماعِ کاملِ لایه‌های LONG طلا** (build_union_mask ِ S214 —
  زمان-محورها ∪ Brooks High-2/Low-2) + **همچنین ∪ خطوطِ روندِ S215** (چون S215 هم LONG طلاست
  و تازه پذیرفته شده — باید anti-double-counting شود) می‌سنجیم:
    1) چند درصد از معاملاتِ S216 با union همپوشان است؟ (با کدام لایه)
    2) سهمِ مستقل (bar-not-in-union) گیتِ سختِ ۴-گانه را می‌گذراند؟ ⇒ لبهٔ نو
    3) راهِ سومِ همپوشانی: WRِ بخشِ همپوشان vs مستقل (نامزدِ فیلترِ تأیید)

خروجی: results/_s216_finalize.json + جدولِ سهمِ مستقلِ قابلِ ثبت برای هر TF.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s216_brooks_trend_channel_line as X
import s215_brooks_trend_line as TL          # برای ساختِ ماسکِ S215 (خطوطِ روندِ LONG طلا)
import s214_finalize as F214                 # build_union_mask + wf_halves_from_trades

RESULTS = os.path.join(ROOT, 'results')
MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24, 'H4': 16, 'D1': 10}

# پارامترهای پذیرفتهٔ S215 (خطِ روندِ LONG) برای هر TFِ طلا — از سندِ S215 (results/_s215_finalize.json).
# این‌ها را به‌عنوان بخشی از union در نظر می‌گیریم تا S216 دوباره‌شماری نکند.
S215_ACCEPTED = {
    'XAUUSD_M5':  dict(side='long', ef=10, es=30, k=5, pen=0.6, max_gap=40, sl=150, tp=300),
    'XAUUSD_M15': dict(side='long', ef=10, es=30, k=5, pen=0.6, max_gap=40, sl=150, tp=300),
    'XAUUSD_M30': dict(side='long', ef=10, es=30, k=5, pen=0.6, max_gap=40, sl=200, tp=400),
    'XAUUSD_H1':  dict(side='long', ef=20, es=50, k=5, pen=0.6, max_gap=40, sl=200, tp=400),
    'XAUUSD_H4':  dict(side='long', ef=20, es=50, k=5, pen=0.6, max_gap=40, sl=250, tp=500),
}


def best_per_tf():
    rows = json.load(open(os.path.join(RESULTS, '_s216_trend_channel_line.json')))
    best = {}
    for r in rows:
        if not r['accepted'] or not r['tf'].startswith('XAUUSD'):
            continue
        tf = r['tf']
        if tf not in best or r['net'] > best[tf]['net']:
            best[tf] = r
    return best


def parse_ema(s):
    a, b = s.split('/'); return int(a), int(b)


def s215_mask_for_tf(df, tf):
    """ماسکِ بار-به-بارِ سیگنال‌های S215 (خطِ روندِ LONG) روی همان TF، اگر پذیرفته‌شده باشد."""
    cfg = S215_ACCEPTED.get(tf)
    if cfg is None:
        return np.zeros(len(df), bool)
    sig = TL.trend_line_signals(df, cfg['side'], cfg['ef'], cfg['es'], cfg['k'], cfg['pen'], cfg['max_gap'])
    # سیگنال روی entry_bar؛ چون همپوشانیِ بار-به-بار می‌سنجیم، خودِ ماسکِ سیگنال کافی است
    # اما برای اطمینان، پنجرهٔ کوچکی حولِ هر سیگنال را هم می‌پوشانیم (±۱ کندل).
    m = np.asarray(sig, bool).copy()
    idx = np.where(m)[0]
    for i in idx:
        a = max(0, i - 1); b = min(len(m), i + 2)
        m[a:b] = True
    return m


def analyze(tf, cand):
    asset = 'XAUUSD'
    df = S.lastn(S.load(tf), y=4)
    ef, es = parse_ema(cand['ema'])
    tag = tf.split('_')[1]
    mh = MH.get(tag, 48)
    sig = X.trend_channel_line_signals(df, cand['side'], ef, es, cand['k'], cand['pen'],
                                       cand['max_gap'], second_pen=cand['second_pen'])
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, cand['sl'], cand['tp'], mh, asset)  # cand همه long
    if tr is None or len(tr) == 0:
        return None

    union_mask, time_mask, brooks_mask = F214.build_union_mask(df)
    s215_mask = s215_mask_for_tf(df, tf)
    full_union = union_mask | s215_mask       # ∪ خطوطِ روندِ S215 (anti-double-counting)

    total = len(tr)
    ct = cb = cu = c215 = cfull = 0
    indep_flag = []
    for _, t in tr.iterrows():
        i = int(t['entry_bar'])
        if i >= len(full_union):
            i = len(full_union) - 1
        ct += bool(time_mask[i]); cb += bool(brooks_mask[i]); cu += bool(union_mask[i])
        c215 += bool(s215_mask[i]); cfull += bool(full_union[i])
        indep_flag.append(not bool(full_union[i]))
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
                     union_noTL=round(cu/total*100, 1), s215=round(c215/total*100, 1),
                     full_union=round(cfull/total*100, 1),
                     indep_share=round(len(tr_ind)/total*100, 1)),
        raw=dict(net=round(s_all['net'], 1), wr=round(s_all['wr'], 2), n=s_all['n']),
        indep=dict(net=round(s_ind['net'], 1), wr=round(s_ind['wr'], 2), n=s_ind['n'],
                   pf=(round(s_ind['pf'], 3) if s_ind['pf'] != float('inf') else 999.0),
                   **(wfh or {}), passes=passes),
        overlap_part=dict(net=round(s_ov['net'], 1), wr=round(s_ov['wr'], 2), n=s_ov['n']),
        total=total)


def main():
    print("=" * 96)
    print("S216_finalize — همپوشانیِ اجباری: سهمِ مستقلِ Trend-Channel-Line (فصلِ ۱۴) نسبت به Union-All ∪ S215")
    print("=" * 96, flush=True)

    best = best_per_tf()
    print(f"TFهای گیت-پاس: {sorted(best.keys())}\n", flush=True)
    out = {}
    tot_indep_registerable = 0.0
    for tf in sorted(best):
        cand = best[tf]
        print(f"\n{'─'*90}\n### {tf}  کاندید: {cand['side']} ema{cand['ema']} k{cand['k']} "
              f"sp{int(cand['second_pen'])} pen{cand['pen']} gap{cand['max_gap']} "
              f"SL{cand['sl']}/TP{cand['tp']} (raw net=${cand['net']:+,.0f}, WR{cand['wr']})", flush=True)
        try:
            a = analyze(tf, cand)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"  [err] {e}"); continue
        if a is None:
            print("  [no trades]"); continue
        ov = a['overlap']
        print(f"  همپوشانیِ بار-به-بار (total={a['total']}): زمان={ov['time']}%  "
              f"Brooks_H2L2={ov['brooks']}%  S215(TrendLine)={ov['s215']}%")
        print(f"    ⇒ Union-All(بدونِ TL)={ov['union_noTL']}%  Full-Union(با S215)={ov['full_union']}%  "
              f"⇒ سهمِ مستقل={ov['indep_share']}%")
        ind = a['indep']
        print(f"  مستقل: net=${ind['net']:+,.0f} WR{ind['wr']} n{ind['n']} PF{ind.get('pf')} "
              f"WF={ind.get('wf')} h1={ind.get('h1')} h2={ind.get('h2')}  "
              f"⇒ {'✅ لبهٔ نوِ مستقل' if ind['passes'] else '❌ سهمِ مستقل گیت را رد'}")
        ovp = a['overlap_part']
        print(f"  بخشِ همپوشان: net=${ovp['net']:+,.0f} WR{ovp['wr']} n{ovp['n']} "
              f"(اگر WRِ همپوشان بالاتر از مستقل بود ⇒ ارزشِ فیلترِ تأیید)")
        if ind['passes']:
            tot_indep_registerable += ind['net']
        out[tf] = a

    with open(os.path.join(RESULTS, '_s216_finalize.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\n{'='*96}")
    print(f"مجموعِ سودِ خالصِ مستقلِ قابلِ ثبت (محافظه‌کارانه، فقط سهمِ non-union): "
          f"${tot_indep_registerable:+,.0f}")
    print("saved: results/_s216_finalize.json")


if __name__ == '__main__':
    main()
