# -*- coding: utf-8 -*-
"""
S216_filter_probe — راهِ سومِ «قوانینِ همپوشانی» (اجباری، پیش از فصلِ بعد)
=========================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

پس‌زمینه: در s216_finalize، هر ۴ کاندیدِ Trend-Channel-Line (فصلِ ۱۴) در «سهمِ مستقل» رد
شدند (همپوشانیِ ۵۰-۶۹٪ با اجتماعِ LONGِ طلا). اما در همهٔ TFها، «بخشِ همپوشان» WRِ بالاتری
از «بخشِ مستقل» داشت. طبقِ راهِ سومِ قانونِ همپوشانی، پیش از رفتن به فصلِ بعد باید صریحاً
بیازماییم: آیا سیگنالِ «overshoot خطِ کانالِ نزولی + برگشت» به‌عنوانِ **فیلترِ تأییدِ سیگنال**
روی لایه‌های LONGِ موجود (زمان-محور و S215) WR را بالا می‌برد؟

روش (بدونِ نگاه به آینده): برای هر لایهٔ پایهٔ LONG، ماسکِ بار-به-بارِ «context» را از
سیگنالِ TCL می‌سازیم: کندلی «در بافتِ TCL» است اگر در W کندلِ گذشته حداقل یک سیگنالِ
TCL-overshoot رخ داده باشد (یعنی بازار تازه یک overshoot را fade کرده و برگشته). سپس
معاملاتِ لایهٔ پایه را به دو دسته می‌کنیم:
  (A) ورودشان داخلِ بافتِ TCL بود  vs  (B) خارج از آن.
اگر WR/PFِ دستهٔ A به‌طورِ معنادار بهتر از B و از کلِ لایه باشد ⇒ TCL نامزدِ فیلترِ مثبت.
اگر برعکس ⇒ نامزدِ فیلترِ منفی (رد سیگنال) — که آن هم برای پروژه ارزشمند است.

لایه‌های پایه‌ای که می‌آزماییم (LONGِ طلا، همان TFهای گیت-پاسِ S216):
  1) لایهٔ زمان-محورِ ساده (EMA-fast>EMA-slow ⇒ pullback-continuation LONG) — تقریبِ union زمان.
  2) لایهٔ S215 (Trend-Line failed-breakout LONG) روی TFهای پذیرفته.
خروجی: results/_s216_filter_probe.json + جدولِ A/B برای هر (لایه، TF).
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s216_brooks_trend_channel_line as X
import s215_brooks_trend_line as TL
import s216_finalize as FIN

RESULTS = os.path.join(ROOT, 'results')
MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24, 'H4': 16, 'D1': 10}
CTX_WINDOW = {'M5': 12, 'M15': 8, 'H1': 6, 'H4': 4}   # چند کندل پس از سیگنالِ TCL «بافت» بماند


def tcl_context_mask(df, cand, tf):
    """ماسکِ بافتِ TCL: True برای کندل‌هایی که در W کندلِ گذشته یک سیگنالِ TCL-overshoot دیده‌اند."""
    tag = tf.split('_')[1]
    ef, es = FIN.parse_ema(cand['ema'])
    sig = X.trend_channel_line_signals(df, cand['side'], ef, es, cand['k'], cand['pen'],
                                       cand['max_gap'], second_pen=cand['second_pen'])
    sig = np.asarray(sig, bool)
    W = CTX_WINDOW.get(tag, 6)
    ctx = np.zeros(len(df), bool)
    idx = np.where(sig)[0]
    for i in idx:
        a = i; b = min(len(ctx), i + W + 1)
        ctx[a:b] = True
    return ctx


def base_time_signals(df, ef=20, es=50, k=5, pen=0.6, max_gap=40):
    """لایهٔ زمان-محورِ ساده: pullback-continuation LONG (تقریبِ اجتماعِ لایه‌های زمان طلا).
    از خودِ ابزارِ trend_line_signals به‌عنوانِ نمایندهٔ pullback استفاده نمی‌کنیم؛ به‌جایش یک
    قاعدهٔ سادهٔ EMA-pullback می‌سازیم تا مستقل از S215 باشد."""
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    ema_f = pd.Series(c).ewm(span=ef, adjust=False).mean().values
    ema_s = pd.Series(c).ewm(span=es, adjust=False).mean().values
    n = len(df); sig = np.zeros(n, bool)
    for i in range(es + 2, n):
        up = ema_f[i] > ema_s[i]                       # روندِ صعودی
        pulled = l[i-1] <= ema_f[i-1] * 1.0005         # کندلِ قبل به EMA-fast pullback کرد
        bounce = c[i] > c[i-1] and c[i] > o[i]         # کندلِ فعلی صعودی (برگشت)
        if up and pulled and bounce:
            sig[i] = True
    return sig


def stats_split(df, base_sig, ctx, sl, tp, mh, asset='XAUUSD'):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, base_sig, z, sl, tp, mh, asset)
    if tr is None or len(tr) == 0:
        return None
    inctx = []
    for _, t in tr.iterrows():
        i = int(t['entry_bar'])
        if i >= len(ctx): i = len(ctx) - 1
        inctx.append(bool(ctx[i]))
    inctx = np.array(inctx, bool)
    trA = tr[inctx].reset_index(drop=True)     # در بافتِ TCL
    trB = tr[~inctx].reset_index(drop=True)    # خارج
    sa = S.stats(tr, asset)
    A = S.stats(trA, asset) if len(trA) else dict(net=0, wr=0, n=0, pf=0)
    B = S.stats(trB, asset) if len(trB) else dict(net=0, wr=0, n=0, pf=0)
    def clean(d):
        return dict(net=round(d['net'],1), wr=round(d['wr'],2), n=d['n'],
                    pf=(round(d['pf'],3) if d['pf']!=float('inf') else 999.0))
    return dict(all=clean(sa), inctx=clean(A), outctx=clean(B))


def main():
    print("=" * 96)
    print("S216_filter_probe — راهِ سومِ همپوشانی: آیا TCL-overshoot فیلترِ تأییدِ لایه‌های LONG است؟")
    print("=" * 96, flush=True)

    best = FIN.best_per_tf()
    out = {}
    for tf in sorted(best):
        cand = best[tf]
        tag = tf.split('_')[1]
        mh = MH.get(tag, 48)
        df = S.lastn(S.load(tf), y=4)
        ctx = tcl_context_mask(df, cand, tf)
        ctx_share = round(ctx.mean()*100, 1)
        print(f"\n{'─'*90}\n### {tf}  (بافتِ TCL روی {ctx_share}% کندل‌ها؛ کاندید sp{int(cand['second_pen'])} "
              f"pen{cand['pen']} k{cand['k']})", flush=True)
        res = {}

        # لایهٔ ۱: زمان-محورِ ساده (EMA pullback-continuation LONG)
        for (ef, es) in [(20, 50), (10, 30)]:
            bs = base_time_signals(df, ef=ef, es=es)
            sp = stats_split(df, bs, ctx, cand['sl'], cand['tp'], mh)
            if sp is None:
                continue
            a, A, B = sp['all'], sp['inctx'], sp['outctx']
            key = f"time_ema{ef}/{es}"
            res[key] = sp
            wr_gain = A['wr'] - a['wr']
            flag = "✅فیلترِ+" if (A['n']>=20 and A['wr'] >= a['wr']+3 and A['wr']>=40) else \
                   ("⛔رد-سیگنال" if (B['n']>=20 and A['wr'] <= a['wr']-5) else "—")
            print(f"  [{key}] کل: net${a['net']:+.0f} WR{a['wr']} n{a['n']}  |  "
                  f"در-بافت(A): net${A['net']:+.0f} WR{A['wr']} n{A['n']}  |  "
                  f"خارج(B): net${B['net']:+.0f} WR{B['wr']} n{B['n']}  ΔWR={wr_gain:+.1f} {flag}")

        # لایهٔ ۲: S215 (Trend-Line failed-breakout LONG) اگر روی این TF پذیرفته باشد
        cfg = FIN.S215_ACCEPTED.get(tf)
        if cfg is not None:
            s215_sig = TL.trend_line_signals(df, cfg['side'], cfg['ef'], cfg['es'], cfg['k'],
                                             cfg['pen'], cfg['max_gap'])
            sp = stats_split(df, np.asarray(s215_sig, bool), ctx, cfg['sl'], cfg['tp'], mh)
            if sp is not None:
                a, A, B = sp['all'], sp['inctx'], sp['outctx']
                res['S215_trendline'] = sp
                wr_gain = A['wr'] - a['wr']
                flag = "✅فیلترِ+" if (A['n']>=20 and A['wr'] >= a['wr']+3 and A['wr']>=40) else \
                       ("⛔رد-سیگنال" if (B['n']>=20 and A['wr'] <= a['wr']-5) else "—")
                print(f"  [S215-TL] کل: net${a['net']:+.0f} WR{a['wr']} n{a['n']}  |  "
                      f"در-بافت(A): net${A['net']:+.0f} WR{A['wr']} n{A['n']}  |  "
                      f"خارج(B): net${B['net']:+.0f} WR{B['wr']} n{B['n']}  ΔWR={wr_gain:+.1f} {flag}")
        out[tf] = dict(ctx_share=ctx_share, layers=res)

    with open(os.path.join(RESULTS, '_s216_filter_probe.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nsaved: results/_s216_filter_probe.json")
    print("\nراهنما: ✅فیلترِ+ ⇒ حضورِ بافتِ TCL، WRِ لایه را ≥۳ واحد بالا می‌برد (نامزدِ فیلترِ تأیید).")
    print("        ⛔رد-سیگنال ⇒ داخلِ بافت WR افت می‌کند ⇒ TCL به‌عنوان فیلترِ منفی/پرهیز.")


if __name__ == '__main__':
    main()
