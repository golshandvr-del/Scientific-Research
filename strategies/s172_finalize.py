# -*- coding: utf-8 -*-
"""
S172-FINALIZE — ثبتِ رسمیِ سهمِ مستقلِ Two-Legged Double-Bottom (طلا long)
================================================================================
> قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD)؛ WR≥۴۰٪ فقط کفِ هر لایه.

کاندیدِ نهایی (CFG_FINAL در s172_validate): double-bottomِ *تنگ* ساختاری
  k5 tol0.001 lb30 SL250/TP375 mh48 روی XAUUSD long.

منطق:
  کاندیدِ خام (tol0.0015) net کلِ +$20,435 داشت اما ۹۰٪ همپوشان با S168 و عمدتاً
  long-bias بود. با سخت‌کردنِ tol به ۰.۱٪ (double-bottomِ واقعاً تنگ) و سپس کسرِ
  کاملِ همپوشانی با **کلِ پرتفویِ فعلی** (S168 High-2 ∪ S171 SoS ∪ لایه‌های زمان-محور)،
  سهمِ مستقلِ باقی‌مانده هر دو نیمه مثبت است و walk-forward هر ۴ پنجره را پاس می‌کند
  ⇒ طبقِ **تصمیمِ محافظه‌کارانهٔ ضدِ دوباره‌شماری** (هم‌سو با S168/S171) فقط این سهم ثبت می‌شود.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import s172_brooks_two_legs as S
from s172_validate import CFG_FINAL
from s168_brooks_high2_low2 import count_high2_low2
from s171_brooks_signs_of_strength_filter import signs_of_strength_bull

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0
RECORD_BEFORE = 233260


def build_portfolio_union(dfx):
    long_h2, _ = count_high2_low2(dfx, 20, 50)
    sig_h2 = pd.Series(long_h2).shift(1).fillna(False).to_numpy()
    sos = signs_of_strength_bull(dfx, ema_period=20, win=32)
    strong = sos['score'] >= 2
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    sig_sos = pd.Series(strong & (~prev)).shift(1).fillna(False).to_numpy()
    dt = dfx['dt']; dow = dt.dt.dayofweek.to_numpy(); hour = dt.dt.hour.to_numpy(); dom = dt.dt.day.to_numpy()
    tu = ((dow == 0) & np.isin(hour, [18, 19, 20, 21])) | \
         (np.isin(dom, [10, 13, 20]) & np.isin(hour, list(range(1, 13)))) | \
         (np.isin(dom, [1, 2, 3]) & np.isin(hour, list(range(0, 6)))) | \
         (np.isin(dom, list(range(22, 27))))
    tu = pd.Series(tu).shift(1).fillna(False).to_numpy()
    return sig_h2, sig_sos, tu, (sig_h2 | sig_sos | tu)


def wf(dfx, sig, sl, tp, mh, nwin=4):
    n = len(dfx); b = [int(n * i / nwin) for i in range(nwin + 1)]; out = []
    for w in range(nwin):
        lo, hi = b[w], b[w + 1]; sub = dfx.iloc[lo:hi].reset_index(drop=True)
        r = S.stats(S.sim(sub, sig[lo:hi], np.zeros(hi - lo, bool), sl, tp, mh, 'XAUUSD'), 'XAUUSD')
        out.append(dict(win=w + 1, start=str(sub['dt'].iloc[0])[:10], end=str(sub['dt'].iloc[-1])[:10],
                        net=r['net'], wr=r['wr'], n=r['n']))
    return out


def day_overlap(dfx, a, b):
    da = set(dfx['dt'].iloc[np.where(a)[0]].dt.floor('D').astype(str))
    db = set(dfx['dt'].iloc[np.where(b)[0]].dt.floor('D').astype(str))
    return len(da & db), len(da), (len(da & db) / max(1, len(da)) * 100)


def main():
    print("=" * 100)
    print("S172-FINALIZE — ثبتِ سهمِ مستقلِ double-bottomِ تنگِ ساختاری (Brooks Two Legs)")
    print("=" * 100, flush=True)
    dfx = S.lastn(S.load('XAUUSD_M15'))
    k, tol, lb, sl, tp, mh = (CFG_FINAL[x] for x in ('k', 'tol', 'lb', 'sl', 'tp', 'mh'))
    z = np.zeros(len(dfx), bool)

    sig = S.two_leg_reversal_signals(dfx, k, tol, lb, 'long')
    full = S.stats(S.sim(dfx, sig, z, sl, tp, mh, 'XAUUSD'), 'XAUUSD')
    print(f"\nکلِ لایهٔ تنگ: net=${full['net']:+,.0f} WR={full['wr']:.1f}% n={full['n']} PF={full['pf'] if full['pf']!=float('inf') else 999:.2f}")

    sig_h2, sig_sos, tu, union = build_portfolio_union(dfx)
    # همپوشانیِ روزانه با هر لایه
    print("\nهمپوشانیِ روزانهٔ لایهٔ خام با پرتفوی:")
    for name, other in (('S168 High-2', sig_h2), ('S171 SoS', sig_sos), ('Time-Union', tu), ('Union-All', union)):
        inter, tot, ov = day_overlap(dfx, sig, other)
        print(f"  vs {name:12s}: {inter}/{tot} = {ov:.1f}%")

    # سهمِ مستقل = خارج از اجتماعِ کلِ پرتفوی (پنجرهٔ ۱۲ کندلی)
    other_recent = pd.Series(union).rolling(12, min_periods=1).max().fillna(0).to_numpy() > 0
    indep = sig & (~other_recent)
    r = S.stats(S.sim(dfx, indep, z, sl, tp, mh, 'XAUUSD'), 'XAUUSD')
    hv = S.halves(dfx, indep, z, sl, tp, mh, 'XAUUSD')
    wfr = wf(dfx, indep, sl, tp, mh)
    wf_ok = all(x['net'] > 0 and x['wr'] >= WR_FLOOR for x in wfr)
    halves_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    gate = bool(r['n'] >= 30 and r['net'] > 0 and r['wr'] >= WR_FLOOR and halves_ok and wf_ok)

    print(f"\n### سهمِ مستقل (خارج از اجتماعِ کلِ پرتفوی) ###")
    print(f"  net=${r['net']:+,.0f} WR={r['wr']:.1f}% n={r['n']} PF={r['pf'] if r['pf']!=float('inf') else 999:.2f}")
    print(f"  نیمه‌ها: h1=${hv['h1']:+,.0f}  h2=${hv['h2']:+,.0f}  ⇒ هر دو مثبت: {'✅' if halves_ok else '❌'}")
    print("  walk-forward:")
    for x in wfr:
        print(f"    W{x['win']} [{x['start']}..{x['end']}] net=${x['net']:+7,.0f} WR={x['wr']:5.1f}% n={x['n']:3d} "
              f"{'✅' if (x['net']>0 and x['wr']>=WR_FLOOR) else '❌'}")
    print(f"\n  گیتِ نهایی (net>0 + WR≥40 + هر دو نیمه + WF): {'✅ پذیرفته' if gate else '❌ رد'}")

    delta = round(r['net']) if gate else 0
    record_after = RECORD_BEFORE + delta
    print(f"\n  Δ سودِ خالصِ رسمی = ${delta:+,}  ⇒  رکورد: +${RECORD_BEFORE:,} → +${record_after:,}")

    out = dict(cfg_final=CFG_FINAL, full=full,
               overlap={n: day_overlap(dfx, sig, o)[2] for n, o in
                        (('S168', sig_h2), ('SoS', sig_sos), ('Time', tu), ('Union', union))},
               independent=dict(**r, h1=hv['h1'], h2=hv['h2']),
               walk_forward=wfr, gate=gate, delta=delta,
               record_before=RECORD_BEFORE, record_after=record_after)
    with open(os.path.join(RESULTS, '_s172_finalize.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s172_finalize.json")


if __name__ == '__main__':
    main()
