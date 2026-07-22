# -*- coding: utf-8 -*-
"""
S175-FINALIZE — سنجشِ لبهٔ واقعیِ «Failed-Breakout Reversal» (فصلِ ۳) و سهمِ مستقل
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪.

کاندیدِ برندهٔ گریدِ S175:
    XAUUSD  long  level=swing  k3  win3  SL200/TP300/mh96
    خام: net=+$8,590  WR=47.6%  n=1116  PF=1.10  (گیتِ کامل پاس)

نگرانیِ روش‌شناختی (هم‌سو با S172/S174): n بزرگ + PF پایین ⇒ ممکن است این عمدتاً
**long-biasِ ساختاریِ طلا** باشد نه لبهٔ اصیلِ price-action. دو آزمونِ لازم:

  آزمونِ ۱ — baseline long-bias:
     «خریدِ *بدونِ شرطِ failed-breakout* در همان رژیم/سطح» چقدر سود می‌دهد؟
     Δ(failed-breakout − baseline) باید مثبت و معنادار باشد تا شرطِ الگو ارزش بیفزاید.
     baseline = خرید هر بار که close بالای همان سطحِ swing است + bull bar (بدونِ piercing).

  آزمونِ ۲ — سهمِ مستقل (anti-double-counting، هم‌سو با S168/S172/S173):
     همپوشانیِ بار-به-بار (recent-12) با اجتماعِ پرتفویِ LONGِ طلا:
       High-2 (S168) + time-drifts (S139/140/141/142/144) + Signs-of-Strength (S171).
     سهمِ مستقل باید گیتِ کامل را پاس کند تا به‌عنوان لبهٔ نو ثبت شود.

خروجی: چاپِ کنسول + results/_s175_finalize.json
"""
import os, sys, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S            # load, lastn, sim, stats, halves, swing_pivots
import s175_brooks_failed_breakout as FB    # failed_breakout_signals, recent_swing_level, walk_forward
from engine import indicators as ind

OVERLAP_BARS = 12
WR_FLOOR = 40.0

CFG = dict(asset='XAUUSD', side='long', level_mode='swing', k=3, win=3,
           sl=200, tp=300, mh=96)


# ---------------------------------------------------------------------------
#  baseline: خریدِ بدونِ شرطِ piercing (فقط close بالای سطحِ swing + bull bar)
#  ⇒ اگر این هم به‌تنهایی سودِ مشابه بدهد، لبه فقط long-bias است نه failed-breakout.
# ---------------------------------------------------------------------------
def baseline_long_signal(df, k):
    high = df['high'].to_numpy(); low = df['low'].to_numpy()
    close = df['close'].to_numpy(); openp = df['open'].to_numpy()
    level = FB.recent_swing_level(high, low, k, 'low')
    raw = (close > level) & (close > openp) & ~np.isnan(level)   # بدونِ piercing
    return pd.Series(raw).shift(1).fillna(False).to_numpy()


# ---------------------------------------------------------------------------
#  بازسازیِ سیگنال‌های پرتفویِ LONGِ طلا (proxyهای causal، هم‌سو با finalizeهای قبلی)
# ---------------------------------------------------------------------------
def high2_signal(df, ef=20, es=50):
    """Brooks High-2 (S168): در روندِ صعودی، دومین بارِ high>high[1] پس از اصلاح ⇒ Long."""
    c = df['close']; h = df['high'].to_numpy()
    emaF = ind.ema(c, ef).to_numpy(); emaS = ind.ema(c, es).to_numpy()
    up = emaF > emaS
    hh = h > np.r_[np.nan, h[:-1]]              # high>high[1]
    cnt = np.zeros(len(df), int)
    # شمارشِ سادهٔ High-1/High-2 درونِ فازِ اصلاح (بازنشانی وقتی روند تازه می‌شود)
    c2 = 0
    sig = np.zeros(len(df), bool)
    for i in range(1, len(df)):
        if not up[i]:
            c2 = 0; continue
        if hh[i]:
            c2 += 1
            if c2 == 2:
                sig[i] = True
                c2 = 0
        # اگر کندلِ نزولیِ عمیق شد، شمارش ری‌ست نمی‌شود (سادگی)؛ کافی برای proxyِ همپوشانی
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def time_drift_union(df):
    """اجتماعِ ورودهای زمان-محورِ طلا (proxy): Overnight(22-23UTC)، Monday، Turn/Mid/
    End-of-Month. رویدادِ ورود = اولین کندلِ ورود به پنجره (نه شرطِ پیوسته)."""
    dt = df['dt']
    hour = dt.dt.hour.to_numpy()
    dow = dt.dt.dayofweek.to_numpy()
    dom = dt.dt.day.to_numpy()
    # روزهای کاری تا پایان ماه
    days_in_month = dt.dt.days_in_month.to_numpy()
    to_end = days_in_month - dom
    overnight = (hour >= 22) & (hour <= 23)
    monday = (dow == 0)
    turn = (dom <= 3)
    mid = np.isin(dom, [10, 13, 20])
    endpre = (to_end >= 6) & (to_end <= 8)
    cont = overnight | monday | turn | mid | endpre
    # رویدادِ ورود = لبهٔ رو-به-بالای عضویت در پنجره
    event = cont & ~np.r_[False, cont[:-1]]
    return pd.Series(event).shift(1).fillna(False).to_numpy()


def sos_signal(df, w=32, thr=2):
    """Signs-of-Strength (S171): rising-edge نمرهٔ ۰..۴ قدرتِ روند ≥ thr ⇒ Long (proxy)."""
    c = df['close']; o = df['open'].to_numpy()
    close = c.to_numpy(); high = df['high'].to_numpy(); low = df['low'].to_numpy()
    ema20 = ind.ema(c, 20).to_numpy()
    rng = np.maximum(high - low, 1e-9)
    body = np.abs(close - o)
    up_bar = (close > o).astype(float)
    s1 = pd.Series(up_bar).rolling(w).mean().to_numpy() >= 0.60
    s2 = pd.Series(body / rng).rolling(w).mean().to_numpy() >= 0.55
    below = (close < ema20).astype(float)
    s3 = pd.Series(below).rolling(w).sum().to_numpy() == 0
    half = w // 2
    hh = pd.Series(high).rolling(half).max()
    ll = pd.Series(low).rolling(half).min()
    s4 = (hh.to_numpy() > hh.shift(half).to_numpy()) & (ll.to_numpy() > ll.shift(half).to_numpy())
    score = s1.astype(int) + s2.astype(int) + s3.astype(int) + np.nan_to_num(s4).astype(int)
    over = score >= thr
    rising = over & ~np.r_[False, over[:-1]]
    return pd.Series(rising).shift(1).fillna(False).to_numpy()


def independent_share(sig, union, n_bars=OVERLAP_BARS):
    recent = pd.Series(union.astype(float)).rolling(n_bars, min_periods=1).max().to_numpy() > 0
    return sig & (~recent)


def bar_overlap_pct(a, b, n_bars=OVERLAP_BARS):
    if a.sum() == 0:
        return 0.0
    recent = pd.Series(b.astype(float)).rolling(n_bars, min_periods=1).max().to_numpy() > 0
    return float((a & recent).sum()) / float(a.sum()) * 100


def full_gate(df, sig, asset, side, sl, tp, mh, label):
    z = np.zeros(len(df), bool)
    if side == 'long':
        tr = S.sim(df, sig, z, sl, tp, mh, asset)
    else:
        tr = S.sim(df, z, sig, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return dict(label=label, n=(r['n'] if r else 0), ok=False, reason='n<30')
    hv = S.halves(df, sig if side == 'long' else z,
                  z if side == 'long' else sig, sl, tp, mh, asset)
    wf = FB.walk_forward(df, sig, side, sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    ok = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    return dict(label=label, net=round(r['net'], 1), wr=round(r['wr'], 2),
                n=r['n'], pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
                h1=round(hv['h1'], 1) if hv else None,
                h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok, ok=ok)


def main():
    print("=" * 100)
    print("S175-FINALIZE — لبهٔ واقعیِ Failed-Breakout Reversal + سهمِ مستقل (فصلِ ۳)")
    print("=" * 100)

    asset = CFG['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
    sl, tp, mh = CFG['sl'], CFG['tp'], CFG['mh']

    # سیگنالِ خام
    sig = FB.failed_breakout_signals(df, CFG['level_mode'], CFG['k'], CFG['win'], 'long')
    print(f"\nS175 خام: n_signals={int(sig.sum())}")
    raw = full_gate(df, sig, asset, 'long', sl, tp, mh, 'S175 raw')
    print(f"  خام: net={raw.get('net'):+.0f} WR={raw.get('wr')} n={raw['n']} PF={raw.get('pf')} "
          f"h1={raw.get('h1')} h2={raw.get('h2')} WF={'/'.join(f'{x[0]:+.0f}' for x in raw.get('wf',[]))} "
          f"=> {'OK' if raw['ok'] else 'X'}")

    # آزمونِ ۱ — baseline long-bias
    base_sig = baseline_long_signal(df, CFG['k'])
    base = full_gate(df, base_sig, asset, 'long', sl, tp, mh, 'baseline (no-pierce)')
    print(f"\nآزمونِ ۱ — baseline long-bias (خرید بالای سطحِ swing بدونِ piercing):")
    print(f"  baseline: net={base.get('net'):+.0f} WR={base.get('wr')} n={base['n']} PF={base.get('pf')}")
    if raw.get('net') is not None and base.get('net') is not None:
        delta = raw['net'] - base['net']
        print(f"  Δ(failed-breakout − baseline) = {delta:+.0f}  "
              f"⇒ {'شرطِ الگو ارزش می‌افزاید ✅' if delta > 0 else 'شرطِ الگو ارزش نمی‌افزاید — عمدتاً long-bias ⛔'}")

    # آزمونِ ۲ — سهمِ مستقل نسبت به پرتفویِ LONGِ طلا
    h2 = high2_signal(df)
    td = time_drift_union(df)
    sos = sos_signal(df)
    union = h2 | td | sos
    print(f"\nپرتفویِ LONGِ طلا (proxy): High2 n={int(h2.sum())}  time-drift n={int(td.sum())}  "
          f"SoS n={int(sos.sum())}  اجتماع n={int(union.sum())}")
    ov_h2 = bar_overlap_pct(sig, h2)
    ov_td = bar_overlap_pct(sig, td)
    ov_sos = bar_overlap_pct(sig, sos)
    ov_all = bar_overlap_pct(sig, union)
    print(f"\nهمپوشانیِ بار-به-بار (recent-{OVERLAP_BARS}):")
    print(f"  ∩ High-2      = {ov_h2:.0f}%")
    print(f"  ∩ time-drift  = {ov_td:.0f}%")
    print(f"  ∩ SoS         = {ov_sos:.0f}%")
    print(f"  ∩ اجتماعِ کل  = {ov_all:.0f}%")

    indep = independent_share(sig, union)
    r_ind = full_gate(df, indep, asset, 'long', sl, tp, mh, 'indep-of-LONG-portfolio')
    print(f"\nآزمونِ ۲ — سهمِ مستقل (پس از حذفِ همپوشانی با اجتماعِ LONG):")
    if r_ind.get('net') is None:
        print(f"  n={r_ind['n']} reason={r_ind.get('reason')}  => {'OK' if r_ind['ok'] else 'X'}")
    else:
        print(f"  net={r_ind.get('net'):+.0f} WR={r_ind.get('wr')} n={r_ind['n']} PF={r_ind.get('pf')} "
              f"h1={r_ind.get('h1')} h2={r_ind.get('h2')} "
              f"WF={'/'.join(f'{x[0]:+.0f}' for x in r_ind.get('wf',[]))}  => {'OK ✅' if r_ind['ok'] else 'X'}")

    # تصمیم
    print("\n" + "=" * 100)
    delta_ok = (raw.get('net') is not None and base.get('net') is not None
                and (raw['net'] - base['net']) > 0)
    if r_ind['ok'] and delta_ok:
        print(f"✅ لبهٔ نوِ اصیل: سهمِ مستقلِ ثبت‌پذیر net=${r_ind['net']:+,.0f} WR={r_ind['wr']}% "
              f"n={r_ind['n']} PF={r_ind['pf']} (گیتِ کامل + Δ baseline مثبت).")
    else:
        reasons = []
        if not delta_ok:
            reasons.append("Δ baseline مثبت نیست (عمدتاً long-bias)")
        if not r_ind['ok']:
            reasons.append("سهمِ مستقل گیتِ کامل را پاس نکرد")
        print(f"⛔ ثبت نمی‌شود ⇒ {' + '.join(reasons)}. (احتمالاً فقط به‌عنوان فیلتر یا رد.)")
    print("=" * 100)

    out = dict(strategy='S175_finalize', cfg=CFG,
               raw=raw, baseline=base,
               delta_vs_baseline=(round(raw['net'] - base['net'], 1)
                                  if (raw.get('net') is not None and base.get('net') is not None) else None),
               overlap={'high2': round(ov_h2, 1), 'time_drift': round(ov_td, 1),
                        'sos': round(ov_sos, 1), 'union': round(ov_all, 1)},
               independent=r_ind)
    os.makedirs('results', exist_ok=True)
    with open('results/_s175_finalize.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s175_finalize.json")


if __name__ == '__main__':
    main()
