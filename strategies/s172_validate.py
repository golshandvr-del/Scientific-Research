# -*- coding: utf-8 -*-
"""
S172-VALIDATE — اعتبارسنجیِ سخت‌گیرانهٔ کاندیدِ برندهٔ Two-Legged Reversal (طلا long)
================================================================================
> قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD)؛ WR≥۴۰٪ فقط کفِ هر لایه.

کاندیدِ خام: double-bottom→Long، XAUUSD، k5 tol0.0015 lb30 SL150/TP225 mh48
  ⇒ net +$20,435، WR ۵۱.۹٪، n۱۲۵۰، PF ۱.۲۷.

⚠️ هشدارِ کلیدی (کشف در پیش-تست): «خریدِ بی‌قیدِ طلا هر ۶۰ کندل» به‌تنهایی
   net≈+$11,600، WR ۴۸.۹٪، PF ۱.۱۳ می‌دهد — یعنی بخشِ عمدهٔ سود از **long-bias
   ساختاریِ طلا** (۱۴۵۰$→۳۴۰۰$) است، نه از ساختارِ double-bottom.

بنابراین این فایل چهار آزمونِ سخت اجرا می‌کند:
  ۱) walk-forward ۴-پنجره (به‌ویژه W1=۲۰۲۰-۲۲ که طلا رنج/پرنوسان بود).
  ۲) baseline هم‌تعداد (matched-n long-bias): سیگنالِ ما در برابر خریدِ تصادفیِ
     هم‌تعداد در همان رژیمِ صعودی. لبه فقط وقتی واقعی است که از baseline بهتر باشد.
  ۳) همپوشانی با پرتفویِ فعلی (S67-پایه به‌صورتِ ema-regime، S168 High-2، S171 SoS،
     لایه‌های زمان-محور) بر حسبِ روزهای هم‌پوشان.
  ۴) سهمِ مستقل (independent edge): معاملاتی که در هیچ لایهٔ دیگری تکرار نشده‌اند.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import indicators as ind
import s172_brooks_two_legs as S

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0
WR_FLOOR = 40.0

# کاندیدِ خامِ برنده (بیشترین net کل — عمدتاً long-bias)
CFG = dict(k=5, tol=0.0015, lb=30, sl=150, tp=225, mh=48)
# کاندیدِ نهاییِ قابلِ‌ثبت = double-bottomِ *تنگ* (ساختاری)، سهمِ مستقلِ کلِ پرتفوی.
# tol سخت‌گیرانه‌تر (۰.۱٪) ⇒ الگوی دو-پایهٔ واقعی؛ سهمِ مستقل هر دو نیمه مثبت + WF.
CFG_FINAL = dict(k=5, tol=0.001, lb=30, sl=250, tp=375, mh=48)


def net_wr_pf(df, sig, asset, sl, tp, mh, mask=None):
    z = np.zeros(len(df), bool)
    s = sig if mask is None else (sig & mask)
    r = S.stats(S.sim(df, s, z, sl, tp, mh, asset), asset)
    return r


def walk_forward(df, sig, asset, sl, tp, mh, nwin=4):
    """۴ پنجرهٔ زمانیِ متوالی؛ هر پنجره باید net>0 و WR≥40 داشته باشد."""
    n = len(df); bnds = [int(n * i / nwin) for i in range(nwin + 1)]
    rows = []
    for w in range(nwin):
        lo, hi = bnds[w], bnds[w + 1]
        sub = df.iloc[lo:hi].reset_index(drop=True)
        ss = sig[lo:hi]
        r = net_wr_pf(sub, ss, asset, sl, tp, mh)
        rows.append(dict(win=w + 1, lo=lo, hi=hi,
                         start=str(sub['dt'].iloc[0])[:10], end=str(sub['dt'].iloc[-1])[:10],
                         net=r['net'], wr=r['wr'], n=r['n'], pf=(r['pf'] if r['pf'] != float('inf') else 999.0)))
    return rows


def matched_baseline(df, sig, asset, sl, tp, mh, ema_f=10, ema_s=30, seed=0, reps=20):
    """baseline هم‌تعداد: به‌جای سیگنالِ ساختاری، همان تعدادِ ورودِ Long به‌صورتِ
    تصادفی در همان رژیمِ صعودی (ema_f>ema_s) پخش می‌شود. میانگینِ reps تکرار.
    اگر net سیگنالِ ما ≤ میانگینِ baseline ⇒ لبه صرفاً long-bias است (بی‌ارزش)."""
    c = df['close']; ef = ind.ema(c, ema_f).to_numpy(); es = ind.ema(c, ema_s).to_numpy()
    up = pd.Series(ef > es).shift(1).fillna(False).to_numpy()
    up_idx = np.where(up)[0]
    k = int(sig.sum())
    nets = []
    rng = np.random.default_rng(seed)
    for _ in range(reps):
        if k > len(up_idx):
            break
        pick = rng.choice(up_idx, size=k, replace=False)
        b = np.zeros(len(df), bool); b[pick] = True
        r = net_wr_pf(df, b, asset, sl, tp, mh)
        nets.append(r['net'])
    nets = np.array(nets) if nets else np.array([0.0])
    return dict(mean=float(nets.mean()), std=float(nets.std()),
                p95=float(np.percentile(nets, 95)), max=float(nets.max()), reps=len(nets), k=k)


def signal_days(df, sig):
    """مجموعهٔ روزهای تقویمی که سیگنال دارند (برای سنجشِ همپوشانی)."""
    idx = np.where(sig)[0]
    return set(df['dt'].iloc[idx].dt.floor('D').astype(str))


def main():
    print("=" * 100)
    print("S172-VALIDATE — اعتبارسنجیِ سختِ double-bottom→Long طلا (Brooks Two Legs)")
    print("=" * 100, flush=True)
    dfx = S.lastn(S.load('XAUUSD_M15'))
    k, tol, lb, sl, tp, mh = CFG['k'], CFG['tol'], CFG['lb'], CFG['sl'], CFG['tp'], CFG['mh']
    sig = S.two_leg_reversal_signals(dfx, k, tol, lb, 'long')
    full = net_wr_pf(dfx, sig, 'XAUUSD', sl, tp, mh)
    print(f"\nکلِ لایه: net=${full['net']:+,.0f}  WR={full['wr']:.1f}%  n={full['n']}  "
          f"PF={full['pf'] if full['pf']!=float('inf') else 999:.2f}")

    report = dict(cfg=CFG, full=full)

    # --- ۱) walk-forward ---
    print("\n### ۱) Walk-Forward ۴-پنجره ###")
    wf = walk_forward(dfx, sig, 'XAUUSD', sl, tp, mh)
    all_pos = True
    for r in wf:
        ok = r['net'] > 0 and r['wr'] >= WR_FLOOR
        all_pos &= ok
        print(f"  W{r['win']} [{r['start']}..{r['end']}] net=${r['net']:+8,.0f} "
              f"WR={r['wr']:5.1f}% n={r['n']:4d} PF={r['pf']:.2f}  {'✅' if ok else '❌'}")
    report['walk_forward'] = wf; report['wf_all_pos'] = bool(all_pos)
    print(f"  ⇒ همهٔ ۴ پنجره مثبت و WR≥40: {'✅ بله' if all_pos else '❌ خیر'}")

    # --- ۲) matched-n baseline ---
    print("\n### ۲) baseline هم‌تعداد (long-bias) — لبه در برابرِ خریدِ تصادفیِ صعودی ###")
    bl = matched_baseline(dfx, sig, 'XAUUSD', sl, tp, mh)
    edge = full['net'] - bl['mean']
    beats_p95 = full['net'] > bl['p95']
    print(f"  baseline (n={bl['k']}, reps={bl['reps']}): mean=${bl['mean']:+,.0f} "
          f"std=${bl['std']:,.0f} p95=${bl['p95']:+,.0f} max=${bl['max']:+,.0f}")
    print(f"  سیگنالِ ما = ${full['net']:+,.0f}  ⇒  لبهٔ فراتر از long-bias = ${edge:+,.0f}")
    print(f"  از p95 baseline بهتر است؟ {'✅ بله (لبهٔ آماریِ واقعی)' if beats_p95 else '❌ خیر (عمدتاً long-bias)'}")
    report['matched_baseline'] = bl
    report['edge_over_bias'] = float(edge)
    report['beats_p95'] = bool(beats_p95)

    # --- ۳) همپوشانی با پرتفوی ---
    print("\n### ۳) همپوشانی با لایه‌های موجود (بر حسبِ روزهای هم‌پوشان) ###")
    from s168_brooks_high2_low2 import count_high2_low2
    long_h2, _ = count_high2_low2(dfx, 20, 50)
    sig_h2 = pd.Series(long_h2).shift(1).fillna(False).to_numpy()
    # S171 SoS standalone (طبقِ رکورد)
    from s171_brooks_signs_of_strength_filter import signs_of_strength_bull
    sos = signs_of_strength_bull(dfx, ema_period=20, win=32)
    strong = sos['score'] >= 2
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    sig_sos = pd.Series(strong & (~prev)).shift(1).fillna(False).to_numpy()
    # لایه‌های زمان-محورِ طلا (اجتماع): Monday/Mid-Month/…
    dt = dfx['dt']
    dow = dt.dt.dayofweek.to_numpy(); hour = dt.dt.hour.to_numpy(); dom = dt.dt.day.to_numpy()
    time_union = ((dow == 0) & np.isin(hour, [18, 19, 20, 21])) | \
                 (np.isin(dom, [10, 13, 20]) & np.isin(hour, list(range(1, 13)))) | \
                 (np.isin(dom, [1, 2, 3]) & np.isin(hour, list(range(0, 6)))) | \
                 (np.isin(dom, list(range(22, 27))))
    time_union = pd.Series(time_union).shift(1).fillna(False).to_numpy()

    d_self = signal_days(dfx, sig)
    for name, other in (('S168 High-2', sig_h2), ('S171 SoS', sig_sos), ('Time-Union', time_union)):
        d_o = signal_days(dfx, other)
        inter = len(d_self & d_o)
        ov = inter / max(1, len(d_self)) * 100
        print(f"  vs {name:12s}: روزهای هم‌پوشان={inter:4d}  همپوشانی={ov:5.1f}% "
              f"(از {len(d_self)} روزِ سیگنال)")
        report.setdefault('overlap', {})[name] = dict(inter=inter, overlap_pct=ov,
                                                       self_days=len(d_self), other_days=len(d_o))

    # --- ۴) سهمِ مستقل (خارج از اجتماعِ همهٔ لایه‌ها) ---
    print("\n### ۴) سهمِ مستقل (معاملاتِ خارج از اجتماعِ H2∪SoS∪Time) ###")
    union_other = sig_h2 | sig_sos | time_union
    # ماسکِ کندلی: سیگنال‌هایی که در ۱۲ کندلِ اخیرِ هیچ لایهٔ دیگری نبوده‌اند
    other_recent = pd.Series(union_other).rolling(12, min_periods=1).max().fillna(0).to_numpy() > 0
    indep_mask = ~other_recent
    r_indep = net_wr_pf(dfx, sig, 'XAUUSD', sl, tp, mh, mask=indep_mask)
    print(f"  سهمِ مستقل: net=${r_indep['net']:+,.0f}  WR={r_indep['wr']:.1f}%  n={r_indep['n']}  "
          f"PF={r_indep['pf'] if r_indep['pf']!=float('inf') else 999:.2f}")
    # هر دو نیمهٔ سهمِ مستقل
    hv = S.halves(dfx, sig & indep_mask, np.zeros(len(dfx), bool), sl, tp, mh, 'XAUUSD')
    if hv:
        print(f"  نیمه‌ها: h1=${hv['h1']:+,.0f}  h2=${hv['h2']:+,.0f}")
    report['independent'] = dict(**r_indep, halves=hv)

    # --- تصمیمِ نهایی ---
    print("\n" + "=" * 100)
    indep_ok = bool(r_indep['n'] >= 30 and r_indep['net'] > 0 and r_indep['wr'] >= WR_FLOOR
                    and hv and hv['h1'] > 0 and hv['h2'] > 0)
    print(f"جمع‌بندی: walk-forward={'✅' if all_pos else '❌'}  "
          f"beats-baseline-p95={'✅' if beats_p95 else '❌'}  "
          f"independent-edge-ok={'✅' if indep_ok else '❌'}")
    report['independent_ok'] = indep_ok
    report['decision_note'] = (
        "سهمِ مستقل تنها بخشِ قابلِ‌ثبت است؛ کلِ net عمدتاً long-bias طلاست.")

    with open(os.path.join(RESULTS, '_s172_validate.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s172_validate.json")


if __name__ == '__main__':
    main()
