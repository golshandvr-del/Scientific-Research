# -*- coding: utf-8 -*-
"""
S177 — Al Brooks «Signal Bars: Reversal Bars» (فصلِ ۵ کتابِ Trading Price Action: TRENDS)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت)
> هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR تابعِ هدف نیست اما هر لایهٔ
> فعال باید WR≥۴۰٪ داشته باشد. تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (کتاب، فصلِ ۵ — «Signal Bars: Reversal Bars»، ص. ۸۹–۱۰۰):
  «A reversal bar is one of the most reliable signal bars.» Brooks معیارهای دقیقِ
  یک reversal barِ *قوی* را می‌دهد که هیچ‌کدام هنوز به‌صورتِ هندسیِ کندلی کدنویسی
  نشده‌اند (S172 pivotِ ساختاری بود، S174 sell-climax، S175 failed-breakout):

  Bull reversal bar (سیگنالِ Long در انتهای legِ نزولی):
    • بدنهٔ صعودی: close>open  (یا دستِ‌کم close بالای midpoint)
    • دنبالهٔ پایینیِ بلند: lower_tail ≈ ۱/۳..۱/۲ ارتفاعِ کندل
    • دنبالهٔ بالاییِ کوچک/صفر: upper_tail ≤ small
    • overlap-guard: اگر midpointِ کندلِ برگشتی بالای low کندلِ قبلی باشد ⇒ overlap
      زیاد ⇒ احتمالاً trading range ⇒ رد.  (Brooks ص. ۹۲)
    • close-reversal-count (قدرت): close > بیشینهٔ closeهای cc کندلِ اخیر و
      high > بیشینهٔ highهای hh کندلِ اخیر.  (Brooks ص. ۹۰: «close above the close
      of the past eight bars and its high above the high of the past five bars»)
  Bear reversal bar: قرینهٔ کامل (upper_tail بلند، close زیرِ closeهای اخیر، …).

  context = «test of extreme»: reversal bar باید نزدیکِ کفِ اخیر (bull) / سقفِ اخیر
  (bear) در پنجرهٔ lb شکل بگیرد ⇒ واقعاً چیزی برای برگشت هست.

آزمونِ این فایل:
  • هر دو جهت (long=bull reversal, short=bear reversal) روی XAUUSD و EURUSD.
  • گریدِ کاملِ tail_frac / up_frac / cc / hh / lb / SL / TP / mh.
  • گیتِ سختِ ۴-گانه: net>0 + هر دو نیمه + walk-forward(۴ پنجره) + WR≥40 + n≥30.

سهمِ مستقل + همپوشانی در فایلِ finalize (پس از یافتنِ کاندیدِ خام).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S          # load/lastn/sim/stats/halves + cost-calibrated ASSETS
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0


# ============================================================================
#  reversal-bar signal (Brooks ch.5) — همه causal، shift(1) در انتها
# ============================================================================
def reversal_bar_signals(df, side, tail_frac, up_frac, cc, hh, lb, ema_fast, ema_slow):
    """آرایهٔ bool سیگنالِ ورود (روی کندلِ برگشتی؛ shift(1) در انتها ⇒ ورودِ next-open).

    long  (bull reversal bar): close>open + دنبالهٔ پایینیِ بلند + بالاییِ کوتاه +
          close>max(close[-cc:]) + high>max(high[-hh:]) + overlap-guard +
          context = نزدیک کفِ lb کندلِ اخیر + رژیمِ نزولی/خنثی (ضدِروند در کف).
    short (bear reversal bar): قرینه.
    """
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    rng = np.maximum(h - l, 1e-9)
    mid = (h + l) / 2.0
    upper_tail = h - np.maximum(o, c)
    lower_tail = np.minimum(o, c) - l

    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()

    # بیشینهٔ close/high در cc/hh کندلِ *قبل* (shift(1) ⇒ فقط گذشته)
    close_s = pd.Series(c)
    high_s = pd.Series(h)
    low_s = pd.Series(l)
    prev_close_max = close_s.shift(1).rolling(cc).max().to_numpy()
    prev_close_min = close_s.shift(1).rolling(cc).min().to_numpy()
    prev_high_max = high_s.shift(1).rolling(hh).max().to_numpy()
    prev_low_min = low_s.shift(1).rolling(hh).min().to_numpy()
    # کف/سقفِ پنجرهٔ context (lb کندلِ قبل)
    ctx_low = low_s.shift(1).rolling(lb).min().to_numpy()
    ctx_high = high_s.shift(1).rolling(lb).max().to_numpy()

    sig = np.zeros(n, bool)
    if side == 'long':
        bull_body = c > o
        long_lower = lower_tail >= tail_frac * rng
        small_upper = upper_tail <= up_frac * rng
        crev = c > np.nan_to_num(prev_close_max, nan=1e18)     # close برگردانِ closeهای اخیر
        hrev = h > np.nan_to_num(prev_high_max, nan=1e18)      # high برگردانِ highهای اخیر
        overlap_ok = mid > np.roll(l, 1)                        # midpoint بالای low کندلِ قبلی
        overlap_ok[0] = False
        # context: کندل نزدیکِ کفِ lb اخیر (تستِ extreme) + رژیمِ غیرصعودی
        near_low = l <= np.nan_to_num(ctx_low, nan=-1e18) + (np.nan_to_num(ctx_high, nan=0) - np.nan_to_num(ctx_low, nan=0)) * 0.15
        regime = ef <= es                                       # نزولی/خنثی (کف)
        sig = bull_body & long_lower & small_upper & crev & hrev & overlap_ok & near_low & regime
    else:
        bear_body = c < o
        long_upper = upper_tail >= tail_frac * rng
        small_lower = lower_tail <= up_frac * rng
        crev = c < np.nan_to_num(prev_close_min, nan=-1e18)
        lrev = l < np.nan_to_num(prev_low_min, nan=-1e18)
        overlap_ok = mid < np.roll(h, 1)
        overlap_ok[0] = False
        near_high = h >= np.nan_to_num(ctx_high, nan=-1e18) - (np.nan_to_num(ctx_high, nan=0) - np.nan_to_num(ctx_low, nan=0)) * 0.15
        regime = ef >= es                                       # صعودی/خنثی (سقف)
        sig = bear_body & long_upper & small_lower & crev & lrev & overlap_ok & near_high & regime

    sig = np.nan_to_num(sig, nan=0).astype(bool)
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def evaluate(df, asset, sig, side, sl, tp, mh):
    z = np.zeros(len(df), bool)
    if side == 'long':
        tr = S.sim(df, sig, z, sl, tp, mh, asset)
    else:
        tr = S.sim(df, z, sig, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if r['n'] < 30:
        return None
    hv = S.halves(df, sig if side == 'long' else z, z if side == 'long' else sig, sl, tp, mh, asset)
    # walk-forward ۴ پنجره
    wf = []
    n = len(df)
    for k in range(4):
        a = int(n * k / 4); b = int(n * (k + 1) / 4)
        sub = df.iloc[a:b].reset_index(drop=True)
        sg = sig[a:b]
        z2 = np.zeros(len(sub), bool)
        if sg.sum() < 6:
            wf.append((0.0, 0.0, 0)); continue
        t2 = S.sim(sub, sg if side == 'long' else z2, z2 if side == 'long' else sg, sl, tp, mh, asset)
        if t2 is None or len(t2) == 0:
            wf.append((0.0, 0.0, 0)); continue
        s2 = S.stats(t2, asset)
        wf.append((round(s2['net'], 1), round(s2['wr'], 1), int(s2['n'])))
    wf_ok = all(w[0] > 0 for w in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    acc = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok and r['n'] >= 30)
    return dict(asset=asset, side=side, sl=sl, tp=tp, mh=mh,
                net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
                pf=(round(r['pf'], 3) if r['pf'] != float('inf') else 999.0),
                h1=(round(hv['h1'], 1) if hv else None),
                h2=(round(hv['h2'], 1) if hv else None),
                wf=wf, wf_ok=wf_ok, both_ok=both_ok, accepted=acc)


def main():
    print("=" * 100)
    print("S177 — Al Brooks «Reversal Bars» (فصلِ ۵): هندسهٔ کندلِ برگشتی + close-reversal-count")
    print("گیت: net>0 + هر دو نیمه + walk-forward ۴/۴ + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    dfx = S.lastn(S.load('XAUUSD_M15'))
    dfe = S.lastn(S.load('EURUSD_M15'))
    grids = {'XAUUSD': [(150, 225), (200, 300), (250, 375), (300, 450)],
             'EURUSD': [(15, 22), (20, 30), (25, 45), (30, 45)]}
    mhs = [16, 32, 48, 96]
    # پارامترهای هندسهٔ کندل
    tail_fracs = [0.33, 0.5]
    up_fracs = [0.25, 0.35]
    ccs = [4, 8]
    hhs = [3, 5]
    lbs = [20, 40]
    emas = [(20, 50), (10, 30)]

    all_res = []
    for asset, df in (('XAUUSD', dfx), ('EURUSD', dfe)):
        print(f"\n### {asset}  (rows={len(df)}) ###", flush=True)
        for side in ('long', 'short'):
            for (ef, es) in emas:
                for tf in tail_fracs:
                    for uf in up_fracs:
                        for cc in ccs:
                            for hh in hhs:
                                for lb in lbs:
                                    sig = reversal_bar_signals(df, side, tf, uf, cc, hh, lb, ef, es)
                                    if sig.sum() < 30:
                                        continue
                                    for (sl, tp) in grids[asset]:
                                        for mh in mhs:
                                            r = evaluate(df, asset, sig, side, sl, tp, mh)
                                            if r is None:
                                                continue
                                            r.update(ema_fast=ef, ema_slow=es, tail_frac=tf,
                                                     up_frac=uf, cc=cc, hh=hh, lb=lb,
                                                     nsig=int(sig.sum()))
                                            all_res.append(r)
            best = sorted([x for x in all_res if x['asset'] == asset and x['side'] == side],
                          key=lambda x: x['net'], reverse=True)[:6]
            print(f"  {asset} {side}: بهترین‌ها بر اساس net")
            for x in best:
                tag = '✅ACCEPT' if x['accepted'] else 'reject '
                print(f"    {tag} ema{x['ema_fast']}/{x['ema_slow']} tf{x['tail_frac']} uf{x['up_frac']} "
                      f"cc{x['cc']} hh{x['hh']} lb{x['lb']} SL{x['sl']}/TP{x['tp']}/mh{x['mh']:2d} "
                      f"net=${x['net']:+9,.0f} WR={x['wr']:5.1f}% n={x['n']:4d} PF={x['pf']:.2f} "
                      f"WF_ok={x['wf_ok']} both={x['both_ok']}")

    acc = [x for x in all_res if x['accepted']]
    acc.sort(key=lambda x: x['net'], reverse=True)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s177_reversal_bar.json'), 'w') as f:
        json.dump(dict(all=all_res, accepted=acc), f, ensure_ascii=False, indent=1, default=float)

    print("\n" + "=" * 100)
    print(f"✅ ذخیره شد: results/_s177_reversal_bar.json (کل={len(all_res)}، پذیرفته={len(acc)})")
    for x in acc[:10]:
        print(f"  ✅ {x['asset']} {x['side']} net=${x['net']:+,.0f} WR={x['wr']}% n={x['n']} "
              f"PF={x['pf']} wf={x['wf']}")


if __name__ == '__main__':
    main()
