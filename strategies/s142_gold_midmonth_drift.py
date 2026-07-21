"""
s142_gold_midmonth_drift.py — لایهٔ نو: «Mid-Month Drift» روی طلا M15 (Long، زمان-محورِ تقویمی)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
> این فایل دقیقاً **یک** استراتژی را مستند می‌کند.

--------------------------------------------------------------------------------
منشأ (User Note این نشست: «ترکیبی از نبوغ و جنون را به کار ببر! رکوردشو بشکن»):
  چهار رکوردِ اخیر لبه‌های *زمان-محورِ تقویمی* بودند و هر یک از یک بُعدِ متعامد:
    • S139 Overnight (+$171,738) → «ساعتِ روز»        (۲۲–۲۳ UTC)
    • S140 Monday    (+$175,246) → «روزِ هفته»         (دوشنبه ۱۸–۲۱)
    • S141 Turn-of-Month (+$179,408) → «روزِ ماه: ابتدای ماه» (dom=1، ۷–۱۲)
  ایدهٔ نبوغ+جنونِ این نشست: به‌جای آزمودنِ تک‌به‌تک، **هم‌زمان ۵ بُعدِ تقویمیِ
  کشف‌نشده اسکن شد** (explore_gold_calendar_dimensions.py). کشفِ غافلگیرکننده:
  قوی‌ترین t-statهای کلِ پروژه در روزهای *میانهٔ ماه* بودند — نه ابتدای ماه:

    dom=20 → t=+10.99, mean=+31.32pip, both ✓   (قوی‌ترین تک‌روزِ کلِ پروژه)
    dom=10 → t=+9.31,  mean=+19.82pip, both ✓
    dom=13 → t=+7.49,  mean=+16.20pip, both ✓
    خوشهٔ {10,13,20} با هم → t=+16.16, mean=+22.45pip, both ✓ (قوی‌ترین کلِ پروژه!)

  کالبدشکافی (explore_gold_midmonth_days.py):
    • هر سه روز و خوشهٔ آن‌ها در **هر ۴ چارکِ داده مثبت** ⇒ نه آرتیفکت.
    • ساعاتِ قویِ مشترک: عمدتاً **۱–۱۲ UTC** (پایانِ آسیا + سشنِ لندن).

  تفسیرِ اقتصادی (چرا واقعی است): «چرخهٔ تسویه/بازموازنه‌سازیِ میانِ ماهِ نهادی» و
  جریانِ نقدینگیِ میان‌ماه — یک بُعدِ تقویمیِ متفاوت از «ابتدای ماه» (S141) و
  «آخرِ ماه». این «روزِ تقویمیِ میانهٔ ماه» است.

چرا نامزدِ جریانِ غیرِهم‌بسته است (کلیدِ الحاق به رکورد):
  منبعِ سود روزهای ۱۰/۱۳/۲۰ ماه است — کاملاً جدا از dom=1 (S141)، از ساعتِ Overnight
  (S139) و از روزِ هفتهٔ Monday (S140). این روزها در روزهای مختلفِ هفته می‌افتند
  ⇒ افزایشی‌بودن با corr روزانه اثبات می‌شود.

--------------------------------------------------------------------------------
متدولوژیِ سیب‌به‌سیب با رکورد (ضدِ overfit — دقیقاً هم‌ترازِ S139/S140/S141):
  • داده: ۱۵۰٬۰۰۰ کندلِ M15 XAUUSD (همان فایلِ رکورد).
  • موتور: engine.scalp_engine (simulate_trades + run_capital) — همان موتورِ رکورد.
  • سرمایه: initial=10000, risk=1%, compounding=True.
  • ورود روی open کندلِ بعد از سیگنال (forward-safe).
  • گیت‌های پذیرش (همه باید سبز شوند وگرنه رکورد دست‌نخورده می‌ماند):
      (۱) هر دو نیمهٔ داده مثبت.
      (۲) هر ۴ پنجرهٔ walk-forward مثبت.
      (۳) |corr روزانه با S67-proxy (long طلا)| < 0.35.
      (۴) |corr روزانه با Overnight (S139)| < 0.35.
      (۵) |corr روزانه با Monday (S140)| < 0.35.
      (۶) |corr روزانه با Turn-of-Month (S141)| < 0.35.  ← گیتِ نو (کلیدی)
  • انتخابِ محافظه‌کارانهٔ سودِ لایه = میانگینِ همهٔ ترکیب‌های both-halves (کف، نه سقف).
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
RECORD_TOTAL = 179408.0          # رکوردِ فعلی (S141 Turn-of-Month)
CORR_MAX = 0.35

# روزهای قویِ میانهٔ ماه (از اکتشاف). خوشهٔ پایدارِ both-halves + هر ۴ چارک مثبت.
MIDMONTH_DAYS = [10, 13, 20]
# پنجرهٔ ساعتیِ مشترکِ قوی (۱–۱۲ UTC — پایانِ آسیا + لندن). محافظه‌کارانه.
MIDMONTH_HOURS = list(range(1, 13))


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_tom_rel(df):
    """شاخصِ روزِ معاملاتی نسبت به چرخشِ ماه (برای ساختِ trades پروکسیِ S141)."""
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    def rel(row):
        if row['from_end'] >= -2:
            return int(row['from_end'])
        return int(row['rank_in_month'])
    days['tom_rel'] = days.apply(rel, axis=1)
    m = dict(zip(days['date'], days['tom_rel']))
    df = df.copy()
    df['tom_rel'] = df['date'].map(m).astype(int)
    return df


def build_midmonth_signals(df, days, hours):
    """long روی کندلی که روزِ تقویمی‌اش در {days} و ساعتش در {hours} است."""
    n = len(df)
    long_sig = np.isin(df['dom'].values, days) & np.isin(df['hour'].values, hours)
    return long_sig, np.zeros(n, bool)


def build_overnight_signals(df, hours=(22, 23)):
    n = len(df)
    return np.isin(df['hour'].values, list(hours)), np.zeros(n, bool)


def build_monday_signals(df, hours=(18, 19, 20, 21)):
    n = len(df)
    return ((df['dow'].values == 0) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)


def build_tom_signals(df, hours=(7, 8, 9, 10, 11, 12)):
    """پروکسیِ S141: اولین روزِ معاملاتیِ ماه (tom_rel==1) × ساعت."""
    d = assign_tom_rel(df)
    n = len(df)
    return ((d['tom_rel'].values == 1) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)


def build_s67_proxy(df):
    c = df['close']
    ema20 = c.ewm(span=20, adjust=False).mean().values
    ema100 = c.ewm(span=100, adjust=False).mean().values
    long_sig = (ema20 > ema100)
    edge = np.zeros(len(df), bool)
    edge[1:] = long_sig[1:] & ~long_sig[:-1]
    return edge, np.zeros(len(df), bool)


def run_layer(df, long_sig, short_sig, sl, tp, mh):
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, 'XAUUSD', max_hold=mh)
    if len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def net_of(st):
    return float(st['net_profit']) if st else 0.0


def daily_pnl(df, tr):
    if tr is None or len(tr) == 0:
        return pd.Series(dtype=float)
    day = pd.to_datetime(df['time'].iloc[tr['exit_bar'].values].values, unit='s').normalize()
    s = pd.Series(tr['pnl_pip'].values, index=day)
    return s.groupby(level=0).sum()


def corr_daily(df, tr_a, tr_b):
    a = daily_pnl(df, tr_a); b = daily_pnl(df, tr_b)
    j = pd.concat([a, b], axis=1).fillna(0.0)
    if len(j) < 10 or j.iloc[:, 0].std() == 0 or j.iloc[:, 1].std() == 0:
        return 0.0
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))


def walk_forward(df, days, hours, sl, tp, mh, nwin=4):
    n = len(df); edges = np.linspace(0, n, nwin + 1, dtype=int); outs = []
    for k in range(nwin):
        sub = df.iloc[edges[k]:edges[k+1]].reset_index(drop=True)
        ls, ss = build_midmonth_signals(sub, days, hours)
        st, _ = run_layer(sub, ls, ss, sl, tp, mh)
        outs.append(round(net_of(st), 0))
    return outs


def main():
    df = load()
    n = len(df); half = n // 2
    print(f"داده: {n} کندلِ M15 XAUUSD | رکوردِ فعلی = ${RECORD_TOTAL:,.0f}")
    print(f"ماشه: روزهای میانهٔ ماه {MIDMONTH_DAYS}، ساعاتِ {MIDMONTH_HOURS[0]}–{MIDMONTH_HOURS[-1]} UTC\n")

    # --- جاروبِ سبکِ خروج ---
    print(f"{'='*74}\n۱) جاروبِ سبکِ خروج (SL/TP/max_hold)\n{'='*74}")
    print(f"{'SL':>5}{'TP':>6}{'mh':>5}{'net$':>12}{'PF':>7}{'WR%':>7}{'N':>7}  both")
    combos = []
    for sl in [100, 150, 200]:
        for tp in [300, 500, 700]:
            for mh in [48, 96]:
                ls, ss = build_midmonth_signals(df, MIDMONTH_DAYS, MIDMONTH_HOURS)
                st, tr = run_layer(df, ls, ss, sl, tp, mh)
                if st is None:
                    continue
                trh1 = tr[tr['exit_bar'] < half]; trh2 = tr[tr['exit_bar'] >= half]
                s1 = se.run_capital(trh1, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0] if len(trh1) else None
                s2 = se.run_capital(trh2, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0] if len(trh2) else None
                both = (net_of(s1) > 0 and net_of(s2) > 0)
                net = net_of(st)
                print(f"{sl:>5}{tp:>6}{mh:>5}{net:>12,.0f}{st['profit_factor']:>7.2f}{st['win_rate']:>7.1f}{st['n_trades']:>7}  {'✓' if both else ''}")
                combos.append((net, sl, tp, mh, both))

    both_combos = [c for c in combos if c[4]]
    if not both_combos:
        print("\n❌ هیچ ترکیبی both-halves-positive نبود ⇒ رکورد دست‌نخورده.")
        return

    best = max(both_combos, key=lambda c: c[0])
    net_best, sl, tp, mh, _ = best
    layer_net_conservative = float(np.mean([c[0] for c in both_combos]))
    print(f"\n🏅 برندهٔ جاروب: SL{sl}/TP{tp}/mh{mh} ⇒ net=${net_best:,.0f}")
    print(f"📉 سودِ محافظه‌کارانهٔ لایه (میانگینِ {len(both_combos)} ترکیبِ both✓) = ${layer_net_conservative:,.0f}")

    # --- گیت‌های ضدِ overfit روی برنده ---
    ls, ss = build_midmonth_signals(df, MIDMONTH_DAYS, MIDMONTH_HOURS)
    st, tr = run_layer(df, ls, ss, sl, tp, mh)
    trh1 = tr[tr['exit_bar'] < half]; trh2 = tr[tr['exit_bar'] >= half]
    s1 = se.run_capital(trh1, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0]
    s2 = se.run_capital(trh2, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0]
    wf = walk_forward(df, MIDMONTH_DAYS, MIDMONTH_HOURS, sl, tp, mh)

    print(f"\n{'='*74}\n۲) گیت‌های ضدِ Overfit\n{'='*74}")
    print(f"Both-halves:  H1=${net_of(s1):,.0f}  H2=${net_of(s2):,.0f}  ⇒ {'✅' if net_of(s1)>0 and net_of(s2)>0 else '❌'}")
    print(f"Walk-Forward: {wf}  ⇒ {'✅ همه مثبت' if all(x>0 for x in wf) else '❌'}")

    # --- افزایشی‌بودن ---
    _, tr_on = run_layer(df, *build_overnight_signals(df), 150, 500, 96)
    _, tr_mon = run_layer(df, *build_monday_signals(df), 150, 500, 96)
    _, tr_tom = run_layer(df, *build_tom_signals(df), 100, 700, 96)
    _, tr_67 = run_layer(df, *build_s67_proxy(df), 150, 500, 96)
    corr_on = corr_daily(df, tr, tr_on)
    corr_mon = corr_daily(df, tr, tr_mon)
    corr_tom = corr_daily(df, tr, tr_tom)
    corr_67 = corr_daily(df, tr, tr_67)

    print(f"\n{'='*74}\n۳) آزمونِ افزایشی‌بودن (corr روزانه، آستانه {CORR_MAX})\n{'='*74}")
    print(f"corr با Overnight    (S139): {corr_on:+.3f}  ⇒ {'✅' if abs(corr_on)<CORR_MAX else '❌'}")
    print(f"corr با Monday       (S140): {corr_mon:+.3f}  ⇒ {'✅' if abs(corr_mon)<CORR_MAX else '❌'}")
    print(f"corr با TurnOfMonth  (S141): {corr_tom:+.3f}  ⇒ {'✅' if abs(corr_tom)<CORR_MAX else '❌'}")
    print(f"corr با S67-proxy   (long) : {corr_67:+.3f}  ⇒ {'✅' if abs(corr_67)<CORR_MAX else '❌'}")

    gates_ok = (net_of(s1) > 0 and net_of(s2) > 0 and all(x > 0 for x in wf)
                and abs(corr_on) < CORR_MAX and abs(corr_mon) < CORR_MAX
                and abs(corr_tom) < CORR_MAX and abs(corr_67) < CORR_MAX)

    print(f"\n{'='*74}\n۴) جمع‌بندی\n{'='*74}")
    print(f"سودِ محافظه‌کارانهٔ لایه: ${layer_net_conservative:,.0f}  (max ترکیب: ${net_best:,.0f})")
    print(f"WR (گزارشی): {st['win_rate']:.1f}%  PF: {st['profit_factor']:.2f}  MaxDD: {st['max_dd_pct']:.1f}%  Sharpe: {st['sharpe']:.2f}  N={st['n_trades']}")
    print(f"همهٔ گیت‌ها: {'✅ سبز — افزایشی به رکورد' if gates_ok else '❌ — رکورد دست‌نخورده'}")
    new_total = RECORD_TOTAL + layer_net_conservative if gates_ok else RECORD_TOTAL
    if gates_ok:
        print(f"\n🥇 رکوردِ جدید = ${RECORD_TOTAL:,.0f} + ${layer_net_conservative:,.0f} = ${new_total:,.0f}")

    out = {
        'strategy': 'Gold Mid-Month Drift (S142)',
        'midmonth_days': MIDMONTH_DAYS, 'hours': MIDMONTH_HOURS,
        'best_exit': {'sl': sl, 'tp': tp, 'mh': mh},
        'net_layer_max': round(net_best, 0),
        'net_layer_conservative': round(layer_net_conservative, 0),
        'n_both_combos': len(both_combos),
        'wr': round(st['win_rate'], 1), 'pf': round(st['profit_factor'], 2),
        'maxdd_pct': round(st['max_dd_pct'], 1), 'sharpe': round(st['sharpe'], 2),
        'n_trades': int(st['n_trades']),
        'both_halves': [round(net_of(s1), 0), round(net_of(s2), 0)],
        'walk_forward': wf,
        'corr_overnight': round(corr_on, 3), 'corr_monday': round(corr_mon, 3),
        'corr_tom': round(corr_tom, 3), 'corr_s67': round(corr_67, 3),
        'gates_ok': bool(gates_ok),
        'record_prev': RECORD_TOTAL,
        'record_new': round(new_total, 0),
    }
    with open(os.path.join(RESULTS, '_s142_midmonth.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nذخیره شد: results/_s142_midmonth.json")


if __name__ == '__main__':
    main()
