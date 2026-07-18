"""
s115_short_apples_to_apples.py — مقایسهٔ منصفانهٔ نامزدِ خروجِ SHORT با رکورد
================================================================================
کشفِ حیاتیِ s114:
  عددِ نجومیِ $127,424 به این خاطر بود که من run_capital را با compounding=True
  (پیش‌فرض) صدا زدم، ولی رکوردِ +$14,979 با **compounding=False** ساخته شده بود
  (`se.run_capital(tr, 'XAUUSD', 10000, 1.0, False)`). مقایسهٔ آن دو غلط است.

این اسکریپت «سیب با سیب» مقایسه می‌کند: هر دو پارامترِ خروج (baselineِ رکورد و
نامزدِ s113) را **با دقیقاً همان تنظیماتِ رکورد** (initial=10000, risk=1.0,
compounding=False) روی کلِ ۱۵۰k اجرا می‌کند.

سپس اگر نامزد بهتر بود:
  • both-halves روی ۳ سالِ اخیر (از s113 ✅)
  • walk-forward چهار-پنجره روی کلِ داده
  • استرس به اسپرد (از s114: تا ~۸pip مثبت می‌ماند)
  • آزمونِ افزایشی‌بودن (SHORT ناهمبسته با long ⇒ Δ به رکوردِ کل)

قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود):
  فقط و فقط دنبالِ «سودِ خالصِ بیشتر» هستیم — WR مهم نیست.
  تعریفِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')
RECORD_TOTAL = 76082.0
RECORD_XAU_LONG = 51880.0     # سهمِ long‌های XAUUSD (S67+S91+S81)
RECORD_EUR = 9223.0           # سهمِ EURUSD (S73)
RECORD_SHORT = 14979.0        # سهمِ SHORTِ فعلیِ رکورد (baseline)

# دقیقاً تنظیماتِ رکورد:
CAP_ARGS = dict(initial_capital=10000, risk_pct=1.0, compounding=False)

BASELINE = dict(sl_pip=40, tp_pip=200, max_hold=12, be_trigger_pip=8, trail_pip=8)
CANDIDATE = dict(sl_pip=60, tp_pip=200, max_hold=8, be_trigger_pip=6, trail_pip=6)


def load(years=None):
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    if years:
        cut = df['dt'].max() - pd.Timedelta(days=365 * years)
        df = df[df['dt'] >= cut].reset_index(drop=True)
    return df


def short_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def long_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] < mid[:-1]]) & (p > mid)


def run_exact(df, sig, p):
    """با دقیقاً تنظیماتِ رکورد (compounding=False)."""
    long_flat = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_flat, sig, asset='XAUUSD', **p)
    if tr is None or len(tr) == 0:
        return None, None
    st, _ = se.run_capital(tr, 'XAUUSD', CAP_ARGS['initial_capital'],
                           CAP_ARGS['risk_pct'], CAP_ARGS['compounding'])
    return st, tr


def daily_pnl(df, trades):
    if trades is None or len(trades) == 0:
        return pd.Series(dtype=float)
    exit_dt = df['dt'].values[trades['exit_bar'].values.astype(int)]
    day = pd.to_datetime(exit_dt).normalize()
    s = pd.Series(trades['pnl_pip'].values, index=day)
    return s.groupby(level=0).sum()


def main():
    print("=" * 80)
    print("s115 — مقایسهٔ منصفانهٔ «سیب با سیب» (compounding=False، دقیقاً مثلِ رکورد)")
    print("=" * 80)
    df = load(None)
    sig = short_signal(df)

    st_base, _ = run_exact(df, sig, BASELINE)
    st_cand, tr_cand = run_exact(df, sig, CANDIDATE)
    print(f"\nکلِ ۱۵۰k با تنظیماتِ رکورد (compounding=False):")
    print(f"  baselineِ رکورد (SL40/BE8/tr8/mh12): ${st_base['net_profit']:>9,.0f}"
          f"   n={st_base['n_trades']}  PF={st_base['profit_factor']:.2f}  DD={st_base['max_dd_pct']:.1f}%")
    print(f"  نامزدِ s113   (SL60/BE6/tr6/mh8):   ${st_cand['net_profit']:>9,.0f}"
          f"   n={st_cand['n_trades']}  PF={st_cand['profit_factor']:.2f}  DD={st_cand['max_dd_pct']:.1f}%")
    print(f"  (مرجعِ فایلِ رکورد برای baseline: ~$14,979)")

    gain = st_cand['net_profit'] - st_base['net_profit']
    print(f"\n  Δ نامزد − baseline = ${gain:+,.0f}")

    # ─── walk-forward چهار-پنجره ───
    print(f"\nWalk-forward (۴ پنجرهٔ زمانی) روی نامزد:")
    n = len(df); edges = [0, n//4, n//2, 3*n//4, n]
    wf = []
    all_pos = True
    for i in range(4):
        seg = df.iloc[edges[i]:edges[i+1]].reset_index(drop=True)
        s = short_signal(seg)
        st, _ = run_exact(seg, s, CANDIDATE)
        net = st['net_profit'] if st else 0.0
        wf.append(net)
        if net <= 0: all_pos = False
        d0 = seg['dt'].min().date(); d1 = seg['dt'].max().date()
        print(f"  W{i+1} ({d0}→{d1}): ${net:>9,.0f}   PF={st['profit_factor']:.2f}" if st else f"  W{i+1}: —")

    # ─── ناهمبستگی با long ───
    lo = long_signal(df)
    _, tr_lo = run_exact(df, lo, CANDIDATE)
    d_sh = daily_pnl(df, tr_cand); d_lo = daily_pnl(df, tr_lo)
    joined = pd.concat([d_sh.rename('s'), d_lo.rename('l')], axis=1).fillna(0.0)
    corr = joined['s'].corr(joined['l'])
    print(f"\nناهمبستگیِ نامزد با long-XAUUSD: corr={corr:+.3f}")

    # ─── افزایشی‌بودن ───
    print("\n" + "=" * 80)
    new_short = st_cand['net_profit']
    new_xau = RECORD_XAU_LONG + new_short
    new_total = RECORD_EUR + new_xau
    print(f"آزمونِ افزایشی‌بودن به رکورد:")
    print(f"  رکوردِ فعلی:  long-XAU ${RECORD_XAU_LONG:,.0f} + SHORT ${RECORD_SHORT:,.0f}"
          f" + EUR ${RECORD_EUR:,.0f} = ${RECORD_TOTAL:,.0f}")
    print(f"  نامزد جایگزینِ SHORT: ${RECORD_SHORT:,.0f} → ${new_short:,.0f}"
          f"  (Δ ${new_short-RECORD_SHORT:+,.0f})")
    print(f"  رکوردِ جدید:  ${new_total:,.0f}   (Δ ${new_total-RECORD_TOTAL:+,.0f})")

    verdict = (gain > 0 and all_pos and abs(corr) < 0.35 and new_total > RECORD_TOTAL)
    print("\n" + "=" * 80)
    if verdict:
        print(f"✅✅ رکوردِ جدید تأیید شد: ${new_total:,.0f}  (قبلی ${RECORD_TOTAL:,.0f})")
        print(f"    نامزدِ SHORTِ بهینه‌شده افزایشی، ناهمبسته و در هر ۴ پنجره مثبت است.")
    else:
        reasons = []
        if gain <= 0: reasons.append("سودِ کمتر از baseline")
        if not all_pos: reasons.append("پنجرهٔ walk-forward منفی")
        if abs(corr) >= 0.35: reasons.append(f"همبستگیِ بالا ({corr:+.2f})")
        print(f"⚠️ رکورد هنوز تأیید نشد — دلایل: {', '.join(reasons) if reasons else 'نامعلوم'}")
    print("=" * 80)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s115_apples.json'), 'w') as f:
        json.dump({'baseline_net_150k': st_base['net_profit'],
                   'candidate_net_150k': st_cand['net_profit'],
                   'gain': gain, 'walk_forward': wf, 'wf_all_positive': all_pos,
                   'corr_with_long': corr, 'new_total': new_total,
                   'record_prev': RECORD_TOTAL, 'verdict': bool(verdict)},
                  f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s115_apples.json")


if __name__ == '__main__':
    main()
