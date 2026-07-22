# -*- coding: utf-8 -*-
"""
S175 — Al Brooks «Failed Breakout Reversal» (فصلِ ۳: Breakouts, Trading Ranges,
Tests, and Reversals)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت)
> هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR تابعِ هدف نیست اما هر لایهٔ
> فعال باید WR≥۴۰٪ داشته باشد. تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (کتاب، فصلِ ۳ — «Breakouts, Trading Ranges, Tests, and Reversals»):

  مهم‌ترین مهارتِ صریحِ فصل (نقلِ Brooks، ص. ۷۷):
    «One of the most important skills that a trader can develop is the ability to
     reliably distinguish between a **successful and a failed breakout (a reversal)**.»

  مثالِ مکانیکیِ صریح (Fig 3.1، ص. ۸۰):
    «The market tested yesterday's low, but the **breakout failed and formed a lower
     low as it reversed up sharply** in a spike up to bar 4. A failed breakout to a
     new low indicates that the bulls and the bears agree that the price is too low.»

  تعریفِ «test» (ص. ۷۸): بازگشتِ قیمت به یک سطحِ حمایت/مقاومت — trend line،
  measured move، **prior swing high/low**، یا **yesterday's high/low/close**.
  «Every swing is a test of something.»

  ⇒ قاعدهٔ محوریِ قابل‌آزمون که پرتفوی هنوز *صریحاً* آن را ندارد:
     **Failed-Breakout Reversal حولِ یک سطحِ ساختاری**:
     - قیمت به زیرِ یک swing-low ساختاری (یا کفِ دیروز) می‌شکند (تستِ رو-به-پایین)،
       اما ظرفِ چند کندل breakout شکست می‌خورد (close دوباره بالای سطح) ⇒ تلهٔ خرسی
       ⇒ **LONG**.
     - قرینه: شکستِ ناموفق به بالای یک swing-high (یا سقفِ دیروز) ⇒ **SHORT**.

  تفاوت با لایه‌های موجود (چرا احتمالاً لبهٔ نو است):
    • S173 (Market Inertia): شکستِ کفِ *lb-کندلِ اخیرِ متحرک* در روندِ برقرار
      (اینرسیِ ادامهٔ روند). آنجا سطح یک rolling-min ساده است و شرطِ rejection ندارد.
    • S175 (اینجا): سطح یک **pivotِ ساختاریِ واقعی** (swing) یا **سطحِ تقویمیِ دیروز**
      است، و شرطِ **rejection/برگشتِ صریح** (close دوباره آن‌طرفِ سطح) لازم است.
      این «test → failed breakout → reversal» است، نه صرفِ اینرسیِ روند.

تعریفِ مکانیکی (همه causal، shift-safe):
  1) سطحِ ساختاری:
     - حالتِ 'swing': نزدیک‌ترین swing-low/high تأییدشدهٔ اخیر (swing_pivots از S172،
       با تأخیرِ تأییدِ k کندل ⇒ فقط pivotهای «دیده‌شده تا کنون»).
     - حالتِ 'yday': کف/سقفِ روزِ تقویمیِ قبل (rolling روزانه، shift-safe).
  2) breakout: low[i] < level (برای long) طیِ پنجرهٔ اخیر رخ داده.
  3) failed/rejection: close[i] دوباره بالای level برمی‌گردد **و** کندل یک bar برگشتی
     است (bull bar: close>open برای long) ⇒ سیگنالِ LONG روی کندلِ بعد.
  همه با shift(1) نهایی وارد بک‌تست می‌شوند (ضدِ look-ahead).

گیتِ سخت (سیب‌به‌سیب با S168/S171/S172/S173):
  net>0 AND WR≥40 AND هر دو نیمه مثبت AND walk-forward هر ۴ پنجره (net>0 & WR≥40)
  AND n≥30.

خروجی: results/_s175_failed_breakout.json
"""
import os, sys, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S      # load, lastn, sim, stats, halves, swing_pivots
from engine import indicators as ind

WR_FLOOR = 40.0


# ============================================================================
#  سطحِ ساختاریِ اخیر — نزدیک‌ترین swing-low/high تأییدشده تا هر کندل
#  (causal: pivot در i فقط از i+k به بعد «دیده» می‌شود)
# ============================================================================
def recent_swing_level(high, low, k, kind):
    """آرایه‌ای هم‌طولِ داده: در هر اندیس، مقدارِ نزدیک‌ترین swing-low (kind='low')
    یا swing-high (kind='high') که تا آن لحظه تأیید شده باشد (با تأخیرِ k کندل).
    NaN تا زمانی که هیچ pivot دیده نشده."""
    n = len(high)
    sh, sl_ = S.swing_pivots(high, low, k)
    level = np.full(n, np.nan)
    last = np.nan
    for i in range(n):
        # pivotِ اندیسِ i-k تا اینجا تأیید شده (نیاز به k کندلِ راست)
        j = i - k
        if j >= 0:
            if kind == 'low' and sl_[j]:
                last = low[j]
            elif kind == 'high' and sh[j]:
                last = high[j]
        level[i] = last
    return level


# ============================================================================
#  سطحِ تقویمیِ دیروز (کف/سقفِ روزِ قبل) — shift-safe
# ============================================================================
def yesterday_level(df, kind):
    d = df['dt'].dt.normalize()
    if kind == 'low':
        daily = df.groupby(d)['low'].transform('min')
    else:
        daily = df.groupby(d)['high'].transform('max')
    # مقدارِ «روزِ قبل»: بیشینه/کمینهٔ کاملِ روزِ گذشته. با نگاشتِ per-day و shift روزانه.
    day_val = df.groupby(d)['low'].min() if kind == 'low' else df.groupby(d)['high'].max()
    prev = day_val.shift(1)                      # مقدارِ روزِ قبل
    mapping = prev.to_dict()
    return d.map(mapping).to_numpy(dtype=float)


# ============================================================================
#  سیگنالِ Failed-Breakout Reversal
# ============================================================================
def failed_breakout_signals(df, level_mode, k, win, side):
    """
    side='long' : سطحِ حمایتی (swing-low یا کفِ دیروز). طیِ `win` کندلِ اخیر low زیرِ
                  level رفته (breakout رو-به-پایین) ولی close دوباره بالای level و
                  کندلِ فعلی bull bar (close>open) ⇒ failed breakout ⇒ LONG.
    side='short': قرینه روی سطحِ مقاومتی (swing-high یا سقفِ دیروز) ⇒ SHORT.
    """
    high = df['high'].to_numpy(); low = df['low'].to_numpy()
    close = df['close'].to_numpy(); openp = df['open'].to_numpy()
    n = len(df)

    if side == 'long':
        level = (recent_swing_level(high, low, k, 'low') if level_mode == 'swing'
                 else yesterday_level(df, 'low'))
    else:
        level = (recent_swing_level(high, low, k, 'high') if level_mode == 'swing'
                 else yesterday_level(df, 'high'))

    lvl = pd.Series(level)
    if side == 'long':
        broke = (pd.Series(low) < lvl)                        # breakout رو-به-پایین
        broke_recent = broke.rolling(win, min_periods=1).max().astype(bool).to_numpy()
        # rejection: close دوباره بالای سطح + bull bar
        reject = (close > level) & (close > openp)
        # خودِ این کندل نباید یک شکستِ تازهٔ پایین‌رونده باشد (close باید بالای سطح بسته باشد)
        raw = broke_recent & reject & ~np.isnan(level)
    else:
        broke = (pd.Series(high) > lvl)
        broke_recent = broke.rolling(win, min_periods=1).max().astype(bool).to_numpy()
        reject = (close < level) & (close < openp)
        raw = broke_recent & reject & ~np.isnan(level)

    return pd.Series(raw).shift(1).fillna(False).to_numpy()


# ============================================================================
#  ارزیابی با گیتِ کامل (net + WR + هر دو نیمه + walk-forward ۴ پنجره)
# ============================================================================
def walk_forward(df, sig, side, sl, tp, mh, asset, nwin=4):
    n = len(df); b = [int(n * i / nwin) for i in range(nwin + 1)]
    out = []
    for w in range(nwin):
        lo, hi = b[w], b[w + 1]
        sub = df.iloc[lo:hi].reset_index(drop=True)
        s = sig[lo:hi]
        zz = np.zeros(hi - lo, bool)
        if side == 'long':
            r = S.stats(S.sim(sub, s, zz, sl, tp, mh, asset), asset)
        else:
            r = S.stats(S.sim(sub, zz, s, sl, tp, mh, asset), asset)
        out.append((r['net'], r['wr'], r['n']))
    return out


def evaluate(df, asset, sig, side, sl, tp, mh, meta):
    z = np.zeros(len(df), bool)
    if side == 'long':
        tr = S.sim(df, sig, z, sl, tp, mh, asset)
    else:
        tr = S.sim(df, z, sig, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return None
    hv = S.halves(df, sig if side == 'long' else z,
                  z if side == 'long' else sig, sl, tp, mh, asset)
    wf = walk_forward(df, sig, side, sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    accept = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    d = dict(asset=asset, side=side, sl=sl, tp=tp, mh=mh,
             net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
             pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
             h1=round(hv['h1'], 1) if hv else None,
             h2=round(hv['h2'], 1) if hv else None,
             wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
             wf_ok=wf_ok, both_ok=both_ok, accepted=accept)
    d.update(meta)
    return d


def main():
    print("=" * 100)
    print("S175 — Al Brooks «Failed Breakout Reversal» (فصلِ ۳)")
    print("گیت: net>0 + هر دو نیمه + walk-forward هر ۴ پنجره + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    grids = {
        'XAUUSD': [(200, 300), (250, 375), (300, 450), (150, 300)],
        'EURUSD': [(20, 30), (30, 45), (25, 50), (15, 30)],
    }
    mhs = [24, 48, 96]
    ks = [3, 5]
    wins = [3, 5, 8]
    level_modes = ['swing', 'yday']

    results = []
    accepted = []

    for asset in ('XAUUSD', 'EURUSD'):
        df = S.lastn(S.load(asset + '_M15'))
        print(f"\n### {asset}  (rows={len(df)}) ###", flush=True)
        for side in ('long', 'short'):
            for lm in level_modes:
                for k in (ks if lm == 'swing' else [3]):   # k فقط برای swing معنا دارد
                    for win in wins:
                        meta = dict(level_mode=lm, k=k, win=win)
                        sig = failed_breakout_signals(df, lm, k, win, side)
                        if sig.sum() < 30:
                            continue
                        for (sl, tp) in grids[asset]:
                            for mh in mhs:
                                r = evaluate(df, asset, sig, side, sl, tp, mh, meta)
                                if r is None:
                                    continue
                                results.append(r)
                                if r['accepted']:
                                    accepted.append(r)

        best = sorted([x for x in results if x['asset'] == asset],
                      key=lambda x: -x['net'])[:8]
        print(f"  {asset}: بهترین‌ها بر اساس net")
        for x in best:
            tag = '✅ACCEPT' if x['accepted'] else 'reject'
            print(f"    {tag} {x['side']:5s} {x['level_mode']:5s} k{x['k']} win{x['win']} "
                  f"SL{x['sl']}/TP{x['tp']}/mh{x['mh']:2d}  net=${x['net']:+8,.0f} "
                  f"WR={x['wr']:5.1f}% n={x['n']:4d} PF={x['pf']:.2f} "
                  f"WF_ok={x['wf_ok']} both={x['both_ok']}")

    print("\n" + "=" * 100)
    accepted.sort(key=lambda x: -x['net'])
    print(f"تعدادِ کاندیدِ پذیرفته (گیتِ کامل): {len(accepted)}")
    for x in accepted[:10]:
        print(f"  ✅ {x['asset']} {x['side']} {x['level_mode']} k{x['k']} win{x['win']} "
              f"net=${x['net']:+,.0f} WR={x['wr']:.1f}% n={x['n']} PF={x['pf']:.2f}")

    os.makedirs('results', exist_ok=True)
    out = dict(strategy='S175_FailedBreakout_ch3',
               n_total=len(results), n_accepted=len(accepted),
               results=results, accepted=accepted)
    with open('results/_s175_failed_breakout.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n✅ ذخیره شد: results/_s175_failed_breakout.json "
          f"(کل={len(results)}، پذیرفته={len(accepted)})")


if __name__ == '__main__':
    main()
