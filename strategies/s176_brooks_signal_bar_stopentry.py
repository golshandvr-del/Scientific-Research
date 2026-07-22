# -*- coding: utf-8 -*-
"""
S176 — Al Brooks «Signal Bar + Stop-Entry Confirmation» (فصلِ ۴: Bar Basics —
       Signal Bars, Entry Bars, Setups, and Candle Patterns)

قانونِ شمارهٔ ۱ پروژه: هدف فقط **سودِ خالصِ بیشتر** (XAUUSD + EURUSD)؛ WR کفِ ۴۰٪
برای هر لایه است، نه هدف.

مفهومِ فصل ۴ (بُعدِ تازه = «مکانیزمِ ورود»، نه صرفاً سیگنال):
  • هر کندل یک setup-bar است؛ وقتی «entry stop» یک تیک آن‌سوی کندل خورد، آن کندل
    تبدیل به signal-bar می‌شود و کندلِ بعد entry-bar است.
  • قاعدهٔ صریحِ Brooks: «بهتر است با stop یک تیک بالا/زیرِ کندلِ قبلی وارد شوی؛ اگر
    استاپ نخورد، سفارش را لغو کن.» ⇒ این «تله‌های یک‌کندلی» را فیلتر می‌کند: ورود فقط
    وقتی معتبر است که بازار در جهتِ سیگنال follow-through نشان دهد.
  • قاعدهٔ «with-trend signal bar»: برای مبتدی فقط وقتی وارد شو که signal-bar یک
    trend-bar هم‌جهتِ روند باشد (bull-bar در روندِ صعودی).

آزمونِ این فایل — سه بخش:
  A) ستاپِ پایه (bull-bar در روندِ صعودی) با ورودِ market-on-next-open  ← baseline
  B) همان ستاپ + «stop-entry confirmation» (کندلِ بعد باید high سیگنال را رد کند)
     ← تزِ اصلیِ فصل ۴؛ آیا تأیید سودِ خالص/WR را بهتر می‌کند؟
  C) اگر (B) لبهٔ مستقلِ ضعیف داشت، «stop-entry confirmation» به‌عنوان *مکانیزمِ ورودِ
     جایگزین* روی سیگنال‌های موجود بررسی می‌شود (قانونِ همپوشانی، در فایلِ finalize).

همه causal و shift-safe؛ گیتِ سختِ ۴-گانهٔ پروژه: net>0 + هر دو نیمه + walk-forward
(۴ پنجره) + WR≥40 + n≥30.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s172_brooks_two_legs as S
import scalp_engine as se

TICK = {'XAUUSD': 0.01, 'EURUSD': 0.00001}   # یک «تیک» (حداقل حرکتِ قیمت)


# ----------------------------------------------------------------------------
# سیگنالِ ستاپ: bull/bear trend-bar هم‌جهتِ روند (with-trend signal bar)
# ----------------------------------------------------------------------------
def setup_signal(df, side, ema_fast, ema_slow, body_frac):
    """کندلِ ستاپ = trend-bar هم‌جهتِ روند. (روی کندلِ خودش؛ shift در انتها.)
      • long : close>open (bull bar) + بدنه ≥ body_frac×range + روندِ صعودی (ema_f>ema_s)
      • short: قرینه.
    خروجی: آرایهٔ bool روی کندلِ ستاپ (بدونِ shift — ورود/تأیید در مراحلِ بعد)."""
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    rng = np.maximum(h - l, 1e-9)
    body = np.abs(c - o)
    ef = S.se.ema(df['close'], ema_fast).to_numpy() if hasattr(S, 'se') else None
    # از indicators استفاده کن
    import indicators as ind
    ef = ind.ema(df['close'], ema_fast).to_numpy()
    es = ind.ema(df['close'], ema_slow).to_numpy()
    strong = body >= body_frac * rng
    if side == 'long':
        trend = ef > es
        bar = (c > o) & strong & trend
    else:
        trend = ef < es
        bar = (c < o) & strong & trend
    return bar, h, l


def to_entry_signal(setup, h, l, side, asset, confirm):
    """تبدیلِ کندلِ ستاپ به سیگنالِ ورود که به sim داده می‌شود.

    sim ورود را در open کندلِ (i+1) می‌گذارد. پس:
      • confirm=False (baseline A): سیگنال روی همان کندلِ ستاپ ⇒ ورود next-open.
      • confirm=True  (stop-entry B): ستاپ روی کندلِ i، اما ورود فقط اگر کندلِ i+1
        high[i] (long) را با ≥۱ تیک رد کند. آنگاه سیگنالِ ورود را روی i+1 می‌گذاریم
        ⇒ sim در open کندلِ i+2 وارد می‌شود (کاملاً causal، بدونِ نگاه به آینده).
    """
    n = len(setup)
    tick = TICK[asset]
    sig = np.zeros(n, dtype=bool)
    idx = np.where(setup)[0]
    if not confirm:
        # ورودِ next-open روی همان ستاپ
        sig[idx] = True
        # shift(1) لازم نیست: sim خودش i→i+1 می‌برد؛ اما ستاپ روی close همان کندل
        # محاسبه شده و آن کندل بسته شده ⇒ ورودِ next-open کاملاً causal است.
        return sig
    # confirm=True: بررسیِ رد شدنِ high/low سیگنال توسطِ کندلِ بعد
    for i in idx:
        j = i + 1
        if j >= n:
            continue
        if side == 'long':
            if h[j] > h[i] + tick:      # کندلِ بعد high ستاپ را رد کرد ⇒ تأیید
                sig[j] = True           # سیگنالِ ورود روی j ⇒ sim واردِ open[j+1]
        else:
            if l[j] < l[i] - tick:
                sig[j] = True
    return sig


def evaluate(df, asset, side, ema_fast, ema_slow, body_frac, confirm,
             sl, tp, mh, tag):
    setup, h, l = setup_signal(df, side, ema_fast, ema_slow, body_frac)
    sig = to_entry_signal(setup, h, l, side, asset, confirm)
    if sig.sum() < 30:
        return None
    ls = sig if side == 'long' else np.zeros(len(df), dtype=bool)
    shs = sig if side == 'short' else np.zeros(len(df), dtype=bool)
    tr = S.sim(df, ls, shs, sl, tp, mh, asset)
    if tr is None or len(tr) < 30:
        return None
    st = S.stats(tr, asset)
    h1, h2 = S.halves(df, ls, shs, sl, tp, mh, asset)
    # walk-forward ۴ پنجره
    wf = []
    n = len(df)
    for k in range(4):
        a = int(n * k / 4); b = int(n * (k + 1) / 4)
        sub = df.iloc[a:b].reset_index(drop=True)
        s2, h2b, l2b = setup_signal(sub, side, ema_fast, ema_slow, body_frac)
        sg = to_entry_signal(s2, h2b, l2b, side, asset, confirm)
        if sg.sum() < 8:
            wf.append((0.0, 0.0, 0)); continue
        l2 = sg if side == 'long' else np.zeros(len(sub), dtype=bool)
        s3 = sg if side == 'short' else np.zeros(len(sub), dtype=bool)
        t2 = S.sim(sub, l2, s3, sl, tp, mh, asset)
        if t2 is None or len(t2) == 0:
            wf.append((0.0, 0.0, 0)); continue
        s2s = S.stats(t2, asset)
        wf.append((round(s2s['net'], 1), round(s2s['wr'], 1), int(s2s['n'])))
    wf_ok = all(w[0] > 0 for w in wf)
    both_ok = (h1 > 0 and h2 > 0)
    accepted = (st['net'] > 0 and both_ok and wf_ok and st['wr'] >= 40 and st['n'] >= 30)
    return dict(tag=tag, asset=asset, side=side, confirm=confirm,
                ema=(ema_fast, ema_slow), body_frac=body_frac,
                sl=sl, tp=tp, mh=mh,
                net=round(st['net'], 1), wr=round(st['wr'], 2), n=int(st['n']),
                pf=round(st['pf'], 3), h1=round(h1, 1), h2=round(h2, 1),
                wf=wf, wf_ok=wf_ok, both_ok=both_ok, accepted=accepted)


def main():
    print("=" * 100)
    print("S176 — Al Brooks «Signal-Bar + Stop-Entry Confirmation» (فصلِ ۴)")
    print("A=baseline(next-open) | B=confirmed(stop-entry) — گیتِ سختِ ۴-گانه. هدف=سودِ خالص.")
    print("=" * 100)

    grid_ema = [(10, 30), (20, 50)]
    grid_body = [0.5, 0.6]
    grid_sltp = [(150, 300), (200, 300), (250, 375), (300, 450)]
    grid_mh = [48, 96]

    all_res = []
    accepted = []
    for asset in ('XAUUSD', 'EURUSD'):
        df = S.lastn(S.load(f'{asset}_M15'))
        print(f"\n### {asset}  (rows={len(df)}) ###")
        for side in ('long', 'short'):
            for confirm in (False, True):
                for (ef, es) in grid_ema:
                    for bf in grid_body:
                        for (sl, tp) in grid_sltp:
                            for mh in grid_mh:
                                tag = f"{'B' if confirm else 'A'}_{side}_ema{ef}/{es}_bf{bf}"
                                r = evaluate(df, asset, side, ef, es, bf, confirm,
                                             sl, tp, mh, tag)
                                if r is None:
                                    continue
                                all_res.append(r)
                                mark = '✅' if r['accepted'] else '  '
                                if r['accepted']:
                                    accepted.append(r)
                                if r['accepted'] or (r['net'] > 1500):
                                    print(f"  {mark}{'CONF' if confirm else 'BASE'} {side:5} "
                                          f"ema{ef}/{es} bf{bf} SL{sl}/TP{tp}/mh{mh}  "
                                          f"net=${r['net']:>9,.0f} WR={r['wr']:>5.1f}% "
                                          f"n={r['n']:>4} PF={r['pf']:.2f} "
                                          f"WF_ok={r['wf_ok']} both={r['both_ok']}")

    os.makedirs('results', exist_ok=True)
    with open('results/_s176_signalbar.json', 'w') as f:
        json.dump(dict(all=all_res, accepted=accepted), f, ensure_ascii=False, indent=1)

    print("\n" + "=" * 100)
    accepted.sort(key=lambda r: -r['net'])
    print(f"✅ ذخیره شد: results/_s176_signalbar.json (کل={len(all_res)}، پذیرفته={len(accepted)})")
    for r in accepted[:8]:
        print(f"  ✅ {r['asset']} {'CONF' if r['confirm'] else 'BASE'} {r['side']} "
              f"{r['tag']} net=${r['net']:+,.0f} WR={r['wr']}% n={r['n']} PF={r['pf']}")

    # مقایسهٔ مستقیمِ A در برابرِ B برای بهترین پیکربندی (تزِ فصل ۴)
    print("\n--- مقایسهٔ baseline(A) در برابرِ confirmed(B) روی هم‌ترازها ---")
    def best_of(confirm, side, asset):
        cand = [r for r in all_res if r['confirm'] == confirm and r['side'] == side and r['asset'] == asset]
        return max(cand, key=lambda r: r['net']) if cand else None
    for asset in ('XAUUSD', 'EURUSD'):
        for side in ('long', 'short'):
            a = best_of(False, side, asset); b = best_of(True, side, asset)
            if a and b:
                print(f"  {asset} {side:5}: A_best net=${a['net']:+,.0f}(WR{a['wr']},n{a['n']}) | "
                      f"B_best net=${b['net']:+,.0f}(WR{b['wr']},n{b['n']})")


if __name__ == '__main__':
    main()
