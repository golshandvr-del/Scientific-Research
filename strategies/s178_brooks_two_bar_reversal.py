# -*- coding: utf-8 -*-
"""
S178 — Al Brooks «Signal Bars: Other Types → Two-Bar Reversal» (فصلِ ۶، تمرکز SHORT)

  مفهومِ محوریِ نو (فصل ۶): «Two-Bar Reversal» — یکی از رایج‌ترین ستاپ‌های برگشتی.
  دو کندلِ trend-barِ قوی و تقریباً هم‌اندازه در جهتِ مخالف:
    • short setup (تمرکزِ این نشست): bull trend-bar (buy-climax) سپس bear trend-bar
      (breakoutِ نزولی)، در تستِ سقفِ اخیر ⇒ SHORT.
    • long setup (قرینه): bear trend-bar سپس bull trend-bar، در تستِ کفِ اخیر ⇒ LONG.
  فیلترِ trap (Brooks): entry فقط وقتی low کندلِ دوم زیرِ low *هر دو* کندل باشد (SHORT)
    یا high کندلِ دوم بالای high هر دو کندل (LONG) — برای اجتنابِ bear/bull trap.

  چرا SHORT؟ درسِ S177 (فصل ۵): مفاهیمِ برگشتیِ LONG با اجتماعِ LONGِ طلا ۶۶٪ هم‌پوشان‌اند؛
  پرتفوی به لبهٔ SHORT نیاز دارد. فصل ۶ صریحاً الگوی قرینهٔ SHORT را می‌دهد.

  همه causal (shift(1) در انتها ⇒ ورودِ next-open). گیتِ سختِ ۴-گانه:
    net>0 + هر دو نیمه + walk-forward(۴ پنجره، هر ۴ مثبت) + WR≥40 + n≥30.
  هدف = سودِ خالصِ بیشتر (XAUUSD + EURUSD).
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
#  two-bar reversal signal (Brooks ch.6) — همه causal، shift(1) در انتها
# ============================================================================
def two_bar_reversal_signals(df, side, body_frac, size_tol, lb, ema_fast, ema_slow):
    """آرایهٔ bool سیگنالِ ورود روی کندلِ دومِ الگو (shift(1) در انتها ⇒ ورودِ next-open).

    short: کندلِ i-1 bull trend-bar قوی + کندلِ i bear trend-bar قوی، هم‌اندازه،
           در تستِ سقفِ lb اخیر، رژیمِ صعودی/خنثی، فیلترِ trap (low_i < min(low_i, low_{i-1})
           عملاً low_i باید زیرِ low_{i-1} هم باشد ⇒ شکستِ کلِ الگو).
    long:  قرینه.
    """
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    rng = np.maximum(h - l, 1e-9)
    body = np.abs(c - o)

    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()

    low_s = pd.Series(l); high_s = pd.Series(h)
    ctx_low = low_s.shift(1).rolling(lb).min().to_numpy()
    ctx_high = high_s.shift(1).rolling(lb).max().to_numpy()

    # کندلِ قبلی (i-1)
    o1 = np.roll(o, 1); c1 = np.roll(c, 1); h1 = np.roll(h, 1); l1 = np.roll(l, 1)
    body1 = np.roll(body, 1); rng1 = np.roll(rng, 1)

    strong_i = body >= body_frac * rng
    strong_1 = body1 >= body_frac * rng1
    both_strong = strong_i & strong_1
    # اندازهٔ تقریباً برابر
    same_size = np.abs(body - body1) <= size_tol * np.maximum(body, body1)

    sig = np.zeros(n, bool)
    if side == 'short':
        bull_1 = c1 > o1                                   # کندلِ اول: صعودی (buy-climax)
        bear_i = c < o                                     # کندلِ دوم: نزولی (breakout نزول)
        # فیلترِ trap: low کندلِ دوم زیرِ low کندلِ اول (شکستِ کلِ الگو، نه فقط کندلِ دوم)
        trap_ok = l < l1
        near_high = h >= np.nan_to_num(ctx_high, nan=-1e18) - \
            (np.nan_to_num(ctx_high, nan=0) - np.nan_to_num(ctx_low, nan=0)) * 0.15
        regime = ef >= es                                  # صعودی/خنثی (سقف)
        sig = bull_1 & bear_i & both_strong & same_size & trap_ok & near_high & regime
    else:
        bear_1 = c1 < o1                                   # کندلِ اول: نزولی (sell-climax)
        bull_i = c > o                                     # کندلِ دوم: صعودی (breakout صعود)
        trap_ok = h > h1
        near_low = l <= np.nan_to_num(ctx_low, nan=1e18) + \
            (np.nan_to_num(ctx_high, nan=0) - np.nan_to_num(ctx_low, nan=0)) * 0.15
        regime = ef <= es                                  # نزولی/خنثی (کف)
        sig = bear_1 & bull_i & both_strong & same_size & trap_ok & near_low & regime

    sig[0] = False; sig[1] = False
    sig = np.nan_to_num(sig, nan=0).astype(bool)
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def evaluate(df, asset, sig, side, sl, tp, mh):
    z = np.zeros(len(df), bool)
    if side == 'long':
        tr = S.sim(df, sig, z, sl, tp, mh, asset)
    else:
        tr = S.sim(df, z, sig, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if r is None or r['n'] < 30:
        return None
    hv = S.halves(df, sig if side == 'long' else z, z if side == 'long' else sig, sl, tp, mh, asset)
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
    print("S178 — Al Brooks «Two-Bar Reversal» (فصلِ ۶): الگوی دو-کندلی + trap-filter (تمرکز SHORT)")
    print("گیت: net>0 + هر دو نیمه + walk-forward ۴/۴ + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    dfx = S.lastn(S.load('XAUUSD_M15'))
    dfe = S.lastn(S.load('EURUSD_M15'))
    grids = {'XAUUSD': [(150, 225), (200, 300), (250, 375), (300, 450)],
             'EURUSD': [(15, 22), (20, 30), (25, 45), (30, 45)]}
    mhs = [16, 32, 48, 96]
    body_fracs = [0.5, 0.6, 0.7]
    size_tols = [0.4, 0.6, 1.0]     # اختلافِ مجازِ اندازهٔ دو بدنه
    lbs = [20, 40]
    emas = [(20, 50), (10, 30)]

    all_res = []
    for asset, df in (('XAUUSD', dfx), ('EURUSD', dfe)):
        print(f"\n### {asset}  (rows={len(df)}) ###", flush=True)
        for side in ('short', 'long'):
            for (ef, es) in emas:
                for bf in body_fracs:
                    for st in size_tols:
                        for lb in lbs:
                            sig = two_bar_reversal_signals(df, side, bf, st, lb, ef, es)
                            if sig.sum() < 30:
                                continue
                            for (sl, tp) in grids[asset]:
                                for mh in mhs:
                                    r = evaluate(df, asset, sig, side, sl, tp, mh)
                                    if r is None:
                                        continue
                                    r.update(ema_fast=ef, ema_slow=es, body_frac=bf,
                                             size_tol=st, lb=lb, nsig=int(sig.sum()))
                                    all_res.append(r)
            best = sorted([x for x in all_res if x['asset'] == asset and x['side'] == side],
                          key=lambda x: x['net'], reverse=True)[:6]
            print(f"  {asset} {side}: بهترین‌ها بر اساس net")
            for x in best:
                tag = '✅ACCEPT' if x['accepted'] else 'reject '
                print(f"    {tag} ema{x['ema_fast']}/{x['ema_slow']} bf{x['body_frac']} st{x['size_tol']} "
                      f"lb{x['lb']} SL{x['sl']}/TP{x['tp']}/mh{x['mh']:2d} "
                      f"net=${x['net']:+9,.0f} WR={x['wr']:5.1f}% n={x['n']:4d} PF={x['pf']:.2f} "
                      f"WF_ok={x['wf_ok']} both={x['both_ok']}")

    acc = [x for x in all_res if x['accepted']]
    acc.sort(key=lambda x: x['net'], reverse=True)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s178_two_bar_reversal.json'), 'w') as f:
        json.dump(dict(all=all_res, accepted=acc), f, ensure_ascii=False, indent=1, default=float)

    print("\n" + "=" * 100)
    print(f"✅ ذخیره شد: results/_s178_two_bar_reversal.json (کل={len(all_res)}، پذیرفته={len(acc)})")
    for x in acc[:10]:
        print(f"  ✅ {x['asset']} {x['side']} net=${x['net']:+,.0f} WR={x['wr']}% n={x['n']} "
              f"PF={x['pf']} wf={x['wf']}")


if __name__ == '__main__':
    main()
