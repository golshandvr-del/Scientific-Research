# -*- coding: utf-8 -*-
"""
S183 — Al Brooks «Outside Bars» (فصلِ ۷): هندسهٔ engulfing یک-کندلی + بستن روی extreme + trap

  مفهومِ محوریِ نو (فصل ۷): «Outside Bar» = کندلی که کاملاً کندلِ قبل را دربر می‌گیرد
  (high_i>high_{i-1} و low_i<low_{i-1}). Brooks: در وسطِ رنج بی‌معنی است، اما وقتی در
  جهتِ روند/برگشت رخ دهد و روی extreme خود ببندد، مثلِ یک strong trend bar عمل می‌کند و
  با به‌دام‌انداختنِ طرفِ مقابل (trap) حرکتِ قوی می‌سازد؛ معمولاً دو پا از extreme.
    • long setup: bull outside bar که روی بالای دامنه می‌بندد، در تستِ کفِ اخیر (رژیمِ کف/خنثی)
      + trap: low_i زیرِ low_{i-1} رفته (شکستِ ناموفقِ نزول) سپس صعودی بسته.
    • short setup (قرینه): bear outside bar که روی کفِ دامنه می‌بندد، در تستِ سقفِ اخیر.

  تمایز از پرتفوی: S177 reversal-barِ تک‌کندلی بدونِ شرطِ engulf؛ S178 two-bar (دو کندلِ
  هم‌اندازه). اینجا شرطِ سختِ «دربرگیریِ کاملِ کندلِ قبل» + «بستن روی extreme» است.

  همه causal (shift(1) در انتها ⇒ ورودِ next-open). گیتِ سختِ ۴-گانه:
    net>0 + هر دو نیمه + walk-forward(۴ پنجره، هر ۴ مثبت) + WR≥40 + n≥30.
  هدف = سودِ خالصِ بیشتر (XAUUSD + EURUSD). چارچوبِ evaluate/main هم‌ترازِ S178 (سیب‌به‌سیب).
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
#  outside-bar signal (Brooks ch.7) — همه causal، shift(1) در انتها
# ============================================================================
def outside_bar_signals(df, side, close_frac, lb, ema_fast, ema_slow, require_trap):
    """آرایهٔ bool سیگنالِ ورود روی کندلِ outside (shift(1) در انتها ⇒ ورودِ next-open).

    long: کندلِ i یک bull outside bar (high_i>high_{i-1} و low_i<low_{i-1} و close>open)
          که روی بالای دامنه می‌بندد (close ≥ high - close_frac×range)، در تستِ کفِ lb اخیر،
          رژیمِ کف/خنثی (ema_fast ≤ ema_slow). trap (اختیاری): low_i زیرِ low_{i-1} (شکستِ ناموفق).
    short: قرینه.
    """
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    rng = np.maximum(h - l, 1e-9)

    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()

    low_s = pd.Series(l); high_s = pd.Series(h)
    ctx_low = low_s.shift(1).rolling(lb).min().to_numpy()
    ctx_high = high_s.shift(1).rolling(lb).max().to_numpy()
    span = np.nan_to_num(ctx_high, nan=0) - np.nan_to_num(ctx_low, nan=0)

    # کندلِ قبلی (i-1)
    h1 = np.roll(h, 1); l1 = np.roll(l, 1)

    # outside bar: کاملاً کندلِ قبل را دربر می‌گیرد
    is_outside = (h > h1) & (l < l1)

    sig = np.zeros(n, bool)
    if side == 'long':
        bull_i = c > o                                         # outside bar صعودی
        close_top = c >= h - close_frac * rng                  # بستن نزدیکِ high
        near_low = l <= np.nan_to_num(ctx_low, nan=1e18) + span * 0.15   # تستِ کفِ اخیر
        regime = ef <= es                                      # کف/خنثی
        trap_ok = (l < l1) if require_trap else np.ones(n, bool)  # شکستِ ناموفقِ نزول
        sig = is_outside & bull_i & close_top & near_low & regime & trap_ok
    else:
        bear_i = c < o                                         # outside bar نزولی
        close_bot = c <= l + close_frac * rng                  # بستن نزدیکِ low
        near_high = h >= np.nan_to_num(ctx_high, nan=-1e18) - span * 0.15  # تستِ سقفِ اخیر
        regime = ef >= es                                      # سقف/خنثی
        trap_ok = (h > h1) if require_trap else np.ones(n, bool)  # شکستِ ناموفقِ صعود
        sig = is_outside & bear_i & close_bot & near_high & regime & trap_ok

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
    print("S183 — Al Brooks «Outside Bars» (فصلِ ۷): engulfing یک-کندلی + close-on-extreme + trap")
    print("گیت: net>0 + هر دو نیمه + walk-forward ۴/۴ + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    dfx = S.lastn(S.load('XAUUSD_M15'))
    dfe = S.lastn(S.load('EURUSD_M15'))
    grids = {'XAUUSD': [(150, 225), (200, 300), (250, 375), (300, 450)],
             'EURUSD': [(15, 22), (20, 30), (25, 45), (30, 45)]}
    mhs = [16, 32, 48, 96]
    close_fracs = [0.2, 0.3, 0.4]     # چقدر نزدیک به extreme بسته شود (کسری از range)
    lbs = [20, 40]
    emas = [(20, 50), (10, 30)]
    traps = [True, False]

    all_res = []
    for asset, df in (('XAUUSD', dfx), ('EURUSD', dfe)):
        print(f"\n### {asset}  (rows={len(df)}) ###", flush=True)
        for side in ('long', 'short'):
            for (ef, es) in emas:
                for cf in close_fracs:
                    for lb in lbs:
                        for tr_req in traps:
                            sig = outside_bar_signals(df, side, cf, lb, ef, es, tr_req)
                            if sig.sum() < 30:
                                continue
                            for (sl, tp) in grids[asset]:
                                for mh in mhs:
                                    r = evaluate(df, asset, sig, side, sl, tp, mh)
                                    if r is None:
                                        continue
                                    r.update(ema_fast=ef, ema_slow=es, close_frac=cf,
                                             lb=lb, trap=tr_req, nsig=int(sig.sum()))
                                    all_res.append(r)
            best = sorted([x for x in all_res if x['asset'] == asset and x['side'] == side],
                          key=lambda x: x['net'], reverse=True)[:6]
            print(f"  {asset} {side}: بهترین‌ها بر اساس net")
            for x in best:
                tag = '✅ACCEPT' if x['accepted'] else 'reject '
                print(f"    {tag} ema{x['ema_fast']}/{x['ema_slow']} cf{x['close_frac']} "
                      f"lb{x['lb']} trap{int(x['trap'])} SL{x['sl']}/TP{x['tp']}/mh{x['mh']:2d} "
                      f"net=${x['net']:+9,.0f} WR={x['wr']:5.1f}% n={x['n']:4d} PF={x['pf']:.2f} "
                      f"WF_ok={x['wf_ok']} both={x['both_ok']}")

    acc = [x for x in all_res if x['accepted']]
    acc.sort(key=lambda x: x['net'], reverse=True)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s183_outside_bar.json'), 'w') as f:
        json.dump(dict(all=all_res, accepted=acc), f, ensure_ascii=False, indent=1, default=float)

    print("\n" + "=" * 100)
    print(f"✅ ذخیره شد: results/_s183_outside_bar.json (کل={len(all_res)}، پذیرفته={len(acc)})")
    for x in acc[:10]:
        print(f"  ✅ {x['asset']} {x['side']} net=${x['net']:+,.0f} WR={x['wr']}% n={x['n']} "
              f"PF={x['pf']} wf={x['wf']}")
    if not acc:
        print("  ⛔ هیچ کاندیدِ خامی گیتِ ۴-گانه را پاس نکرد.")


if __name__ == '__main__':
    main()
