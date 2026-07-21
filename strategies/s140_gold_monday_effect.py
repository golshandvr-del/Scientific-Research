"""
s140_gold_monday_effect.py — لایهٔ نو: «Monday Week-Start Drift» روی طلا M15 (Long)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (User Note این نشست: «نبوغ‌آمیز فکر کن!»):
  رکوردِ قبلی (Overnight Drift, S139, +$171,738) با کشفِ یک بُعدِ اطلاعاتیِ *متعامد* —
  «ساعتِ روز» — به دست آمد. اما آن بُعد فقط از *یک* محورِ زمانی استفاده کرد.

  ایدهٔ نبوغ‌آمیزِ این نشست: یک بُعدِ زمانیِ **دوم و متعامد** که ادبیاتِ آکادمیک می‌شناسد
  ولی در پروژه هرگز آزموده نشده: **«اثرِ روزِ هفته» (Day-of-Week / Weekend Effect)**
  (Cross 1973؛ French 1980؛ برای طلا Ball–Torous–Tschoegl 1982، *J. Financial Economics*).

کشفِ ساختاری (explore_gold_dow_hour.py — پیش از ساختِ استراتژی):
  • محورِ روزِ هفته (افق ۲۴ کندل، تجمیعِ همه ساعات):
      Mon t=+6.11 (mean +6.33pip)  ← قوی‌ترین و پایدارترین
      Tue t=+5.56 (ولی نیمهٔ اولِ اکثرِ سلول‌ها منفی ⇒ ناپایدار)
      Wed/Thu/Fri ضعیف‌تر.
  • در سطحِ سلولیِ (روز×ساعت)، خوشهٔ «عصرِ دوشنبه ۱۸–۲۱ UTC» هر دو نیمهٔ داده مثبت است
      (Mon18 t=4.90 both✓، Mon19 t=4.14 both✓، Mon20 t=3.91 both✓، Mon21 t=5.35 both✓).
  • این خوشه با پنجرهٔ Overnight (۲۲–۲۳ *هرروزه*) **هم‌پوشانیِ ساعتی ندارد** و فقط
      *یک روز* از هفته است ⇒ فراوانی و مکانیزمِ کاملاً متفاوت ⇒ کاندیدِ جریانِ غیرِهم‌بسته.

چرا نامزدِ جریانِ غیرِهم‌بسته است (کلیدِ الحاق به رکورد):
  منبعِ سود «drift صعودیِ ساختاریِ ابتدای هفته» است (هضمِ اخبارِ آخرِ هفته + بازگشتِ
  نقدینگیِ نهادی در دوشنبه). این نه یک ماشهٔ قیمتی است و نه پنجرهٔ شبانهٔ روزانهٔ
  Overnight. **افزایشی‌بودن با آزمونِ همبستگیِ روزانه با S67 و با Overnight سنجیده می‌شود.**

--------------------------------------------------------------------------------
متدولوژیِ سیب‌به‌سیب با رکورد (ضدِ overfit):
  • داده: ۱۵۰٬۰۰۰ کندلِ M15 XAUUSD (همان فایلِ رکورد).
  • موتور: engine.scalp_engine (simulate_trades + run_capital) — همان موتورِ رکورد.
  • سرمایه: initial=10000, risk=1%, compounding=True (هم‌ترازِ Overnight/Squeeze).
  • ورود روی open کندلِ بعد از سیگنال (forward-safe).
  • گیت‌های پذیرش (همه باید سبز شوند وگرنه رکورد دست‌نخورده می‌ماند):
      (۱) هر دو نیمهٔ داده مثبت.
      (۲) هر ۴ پنجرهٔ walk-forward مثبت.
      (۳) |corr روزانه با S67 (long طلا)| < 0.35 (افزایشی).
      (۴) |corr روزانه با Overnight (S139)| < 0.35 (افزایشیِ واقعی، نه تکرارِ زمان‌محور).
  • جاروبِ سبکِ خروج فقط برای یافتنِ خروجِ منطقی؛ برنده باید در گیت‌ها robust بماند.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se

RESULTS = os.path.join(ROOT, 'results')
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')

CAP, RISK = 10000.0, 1.0
RECORD_TOTAL = 171738.0            # رکوردِ فعلی (S139 Overnight)
CORR_MAX = 0.35                    # سقفِ همبستگیِ روزانه برای «افزایشی»

# خوشهٔ عصرِ دوشنبه که در اکتشاف هر دو نیمه مثبت بود
MONDAY_HOURS = [18, 19, 20, 21]


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s')
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    return df.reset_index(drop=True)


def build_monday_signals(df, hours):
    """long روی کندلی که روزش دوشنبه و ساعتش در hours است ⇒ ورود در open کندلِ بعد."""
    n = len(df)
    long_sig = (df['dow'].values == 0) & np.isin(df['hour'].values, hours)
    return long_sig, np.zeros(n, bool)


def build_overnight_signals(df, hours=(22, 23)):
    """بازتولیدِ سیگنالِ Overnight (S139) برای آزمونِ همبستگی."""
    n = len(df)
    long_sig = np.isin(df['hour'].values, list(hours))
    return long_sig, np.zeros(n, bool)


def build_s67_proxy(df):
    """پروکسیِ ساده و forward-safe برای جریانِ long طلا (router S67): EMA20>EMA100 momentum.
    فقط برای آزمونِ همبستگیِ روزانه استفاده می‌شود (نه برای سود)."""
    c = df['close']
    ema20 = c.ewm(span=20, adjust=False).mean().values
    ema100 = c.ewm(span=100, adjust=False).mean().values
    long_sig = (ema20 > ema100)
    # فقط لبهٔ عبور (نه هر کندل) تا سیگنال پراکنده باشد
    edge = np.zeros(len(df), bool)
    edge[1:] = long_sig[1:] & ~long_sig[:-1]
    return edge, np.zeros(len(df), bool)


def run_layer(df, long_sig, short_sig, sl, tp, mh, be=None, trail=None):
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, 'XAUUSD',
                            max_hold=mh, be_trigger_pip=be, trail_pip=trail)
    if len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def net_of(st):
    return float(st['net_profit']) if st else 0.0


def daily_pnl(df, tr):
    """سریِ سود/زیانِ روزانه (بر حسبِ pip، بدونِ سرمایه) برای آزمونِ همبستگی."""
    if tr is None or len(tr) == 0:
        return pd.Series(dtype=float)
    day = pd.to_datetime(df['time'].iloc[tr['exit_bar'].values].values, unit='s').normalize()
    s = pd.Series(tr['pnl_pip'].values, index=day)
    return s.groupby(level=0).sum()


def corr_daily(df, tr_a, tr_b):
    a = daily_pnl(df, tr_a)
    b = daily_pnl(df, tr_b)
    j = pd.concat([a, b], axis=1).fillna(0.0)
    if len(j) < 10 or j.iloc[:, 0].std() == 0 or j.iloc[:, 1].std() == 0:
        return 0.0
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))


def walk_forward(df, hours, sl, tp, mh, nwin=4):
    n = len(df)
    edges = np.linspace(0, n, nwin + 1, dtype=int)
    outs = []
    for k in range(nwin):
        sub = df.iloc[edges[k]:edges[k+1]].reset_index(drop=True)
        ls, ss = build_monday_signals(sub, hours)
        st, _ = run_layer(sub, ls, ss, sl, tp, mh)
        outs.append(round(net_of(st), 0))
    return outs


def main():
    df = load()
    n = len(df)
    half = n // 2
    print(f"داده: {n} کندلِ M15 XAUUSD | رکوردِ فعلی = ${RECORD_TOTAL:,.0f}")
    print(f"خوشهٔ کاندید: دوشنبه ساعاتِ {MONDAY_HOURS} UTC\n")

    # --- جاروبِ سبکِ خروج (یافتنِ خروجِ منطقی، نه over-tune) ---
    print(f"{'='*72}\n۱) جاروبِ سبکِ خروج (SL/TP/max_hold)\n{'='*72}")
    print(f"{'SL':>5}{'TP':>6}{'mh':>5}{'net$':>12}{'PF':>7}{'WR%':>7}{'N':>7}  both")
    best = None
    for sl in [100, 150, 200]:
        for tp in [300, 500, 700]:
            for mh in [48, 96]:
                ls, ss = build_monday_signals(df, MONDAY_HOURS)
                st, tr = run_layer(df, ls, ss, sl, tp, mh)
                if st is None:
                    continue
                # both halves
                trh1 = tr[tr['exit_bar'] < half]; trh2 = tr[tr['exit_bar'] >= half]
                s1, _ = se.run_capital(trh1, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True) if len(trh1) else (None, None)
                s2, _ = se.run_capital(trh2, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True) if len(trh2) else (None, None)
                both = (net_of(s1) > 0 and net_of(s2) > 0)
                mark = "✓" if both else ""
                net = net_of(st)
                print(f"{sl:>5}{tp:>6}{mh:>5}{net:>12,.0f}{st['profit_factor']:>7.2f}{st['win_rate']:>7.1f}{st['n_trades']:>7}  {mark}")
                # برنده: بالاترین net که both نیز باشد
                if both and (best is None or net > best[0]):
                    best = (net, sl, tp, mh)

    if best is None:
        print("\n❌ هیچ ترکیبی both-halves-positive نبود ⇒ رکورد دست‌نخورده.")
        return

    net, sl, tp, mh = best
    print(f"\n🏅 برندهٔ جاروب: SL{sl}/TP{tp}/mh{mh} ⇒ net=${net:,.0f}")

    # --- گیت‌های ضدِ overfit ---
    ls, ss = build_monday_signals(df, MONDAY_HOURS)
    st, tr = run_layer(df, ls, ss, sl, tp, mh)
    trh1 = tr[tr['exit_bar'] < half]; trh2 = tr[tr['exit_bar'] >= half]
    s1, _ = se.run_capital(trh1, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    s2, _ = se.run_capital(trh2, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    wf = walk_forward(df, MONDAY_HOURS, sl, tp, mh)

    print(f"\n{'='*72}\n۲) گیت‌های ضدِ Overfit\n{'='*72}")
    print(f"Both-halves:  H1=${net_of(s1):,.0f}  H2=${net_of(s2):,.0f}  ⇒ {'✅' if net_of(s1)>0 and net_of(s2)>0 else '❌'}")
    print(f"Walk-Forward: {wf}  ⇒ {'✅ همه مثبت' if all(x>0 for x in wf) else '❌'}")

    # --- آزمونِ افزایشی‌بودن (همبستگیِ روزانه) ---
    on_l, on_s = build_overnight_signals(df)
    _, tr_on = run_layer(df, on_l, on_s, 150, 500, 96)
    s67_l, s67_s = build_s67_proxy(df)
    _, tr_s67 = run_layer(df, s67_l, s67_s, 150, 500, 96)
    corr_on = corr_daily(df, tr, tr_on)
    corr_67 = corr_daily(df, tr, tr_s67)

    print(f"\n{'='*72}\n۳) آزمونِ افزایشی‌بودن (corr روزانه، آستانه {CORR_MAX})\n{'='*72}")
    print(f"corr با Overnight (S139): {corr_on:+.3f}  ⇒ {'✅' if abs(corr_on)<CORR_MAX else '❌ همبسته'}")
    print(f"corr با S67-proxy (long): {corr_67:+.3f}  ⇒ {'✅' if abs(corr_67)<CORR_MAX else '❌ همبسته'}")

    gates_ok = (net_of(s1) > 0 and net_of(s2) > 0 and all(x > 0 for x in wf)
                and abs(corr_on) < CORR_MAX and abs(corr_67) < CORR_MAX)

    print(f"\n{'='*72}\n۴) جمع‌بندی\n{'='*72}")
    print(f"سودِ خالصِ مستقلِ لایه: ${net:,.0f}")
    print(f"WR (فقط گزارشی): {st['win_rate']:.1f}%  |  PF: {st['profit_factor']:.2f}  |  MaxDD: {st['max_dd_pct']:.1f}%  |  Sharpe: {st['sharpe']:.2f}")
    print(f"همهٔ گیت‌ها: {'✅ سبز — افزایشی به رکورد' if gates_ok else '❌ — رکورد دست‌نخورده'}")
    if gates_ok:
        new_total = RECORD_TOTAL + net
        print(f"\n🥇 رکوردِ جدید = ${RECORD_TOTAL:,.0f} + ${net:,.0f} = ${new_total:,.0f}")

    out = {
        'strategy': 'Gold Monday Week-Start Drift (S140)',
        'monday_hours': MONDAY_HOURS,
        'best': {'sl': sl, 'tp': tp, 'mh': mh},
        'net_layer': round(net, 0),
        'wr': round(st['win_rate'], 1), 'pf': round(st['profit_factor'], 2),
        'maxdd_pct': round(st['max_dd_pct'], 1), 'sharpe': round(st['sharpe'], 2),
        'n_trades': int(st['n_trades']),
        'both_halves': [round(net_of(s1), 0), round(net_of(s2), 0)],
        'walk_forward': wf,
        'corr_overnight': round(corr_on, 3), 'corr_s67': round(corr_67, 3),
        'gates_ok': bool(gates_ok),
        'record_prev': RECORD_TOTAL,
        'record_new': round(RECORD_TOTAL + net, 0) if gates_ok else RECORD_TOTAL,
    }
    with open(os.path.join(RESULTS, '_s140_monday.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nذخیره شد: results/_s140_monday.json")


if __name__ == '__main__':
    main()
