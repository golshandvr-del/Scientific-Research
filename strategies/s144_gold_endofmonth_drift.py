"""
s144_gold_endofmonth_drift.py — لایهٔ نو: «End-of-Month (Pre-End) Drift» روی طلا M15
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
> این فایل دقیقاً **یک** استراتژی را مستند می‌کند.

--------------------------------------------------------------------------------
منشأ (User Note: «آخرین رکورد s143 بود. سعی کن رکوردشو بشکنی»):
  ماتریسِ پژوهشی شکافِ #۱ را «End-of-Month Drift روی طلا» معرفی کرد — بُعدِ
  تقویمیِ *پنجم* که هرگز لایهٔ مستقل نشده. پنج بُعدِ قبلی همه در رکورد بودند:
    • S139 Overnight (ساعتِ روز، ۲۲–۲۳)
    • S140 Monday    (روزِ هفته)
    • S141 Turn-of-Month (ابتدای ماه: اولین روزِ معاملاتی)
    • S142 Mid-Month  (میانهٔ ماه: dom={10,13,20})
    • S143 EURUSD Mid-Month (همان بُعد روی یورو)

  کشفِ اکتشاف (explore_gold_endofmonth_drift.py) — نبوغ + جنون:
    «جنون» = فرضِ اولیه این بود که drift در *آخرین* روزِ ماه است (from_end=-1).
    اما اکتشاف نشان داد from_end=-1 **منفی** است (t=-1.56، چارک۳ منفی ⇒ آرتیفکت).
    «نبوغ» = کشفِ غافلگیرکننده که drift واقعی **۶–۷ روزِ معاملاتی مانده به پایانِ
    ماه** است — نه خودِ پایان:
        from_end=-6 → t=+3.64, mean=+6.79pip
        from_end=-7 → t=+3.45, mean=+7.46pip
        خوشهٔ {-6,-7} → t=+4.99, mean=+7.13pip, both-halves ✓ (h1=+3.33, h2=+10.94)
        خوشهٔ {-6,-7,-3} → t=+5.08, هر ۴ چارک مثبت ✅ (نه آرتیفکت)
    ساعاتِ حاملِ drift: **۱۶–۲۳ UTC** (سشنِ آمریکا/عصرِ لندن).

  تفسیرِ اقتصادی (چرا واقعی است، نه آرتیفکت): «پیش‌پوزیشن‌گیریِ نهادی پیش از
  پایانِ ماه» — صندوق‌ها و مدیرانِ پرتفوی چند روز *قبل* از بسته‌شدنِ ماه شروع به
  بازموازنه‌سازی و window-dressing می‌کنند (نه در آخرین روز که نقدینگی و اسپرد بد
  است). این با McConnell–Xu (2008) هم‌راستاست: بازدهِ turn-of-month در روزهای
  *پیش از* پایان انباشته می‌شود. متفاوت از ابتدای ماه (S141) و میانهٔ ماه (S142).

چرا نامزدِ جریانِ غیرِهم‌بسته است (کلیدِ الحاق به رکورد):
  منبعِ سود روزهای ۶–۷ مانده به پایانِ ماه است — این روزها در روزهای مختلفِ هفته
  و ساعاتِ متفاوت از dom={1,10,13,20} می‌افتند. پنجرهٔ ساعتیِ عصر (۱۶–۲۱) عمداً
  محافظه‌کارانه انتخاب شد تا از Overnight (۲۲–۲۳، S139) جدا بماند.

--------------------------------------------------------------------------------
متدولوژیِ سیب‌به‌سیب با رکورد (ضدِ overfit — دقیقاً هم‌ترازِ S139/S140/S141/S142):
  • داده: ۱۵۰٬۰۰۰ کندلِ M15 XAUUSD (همان فایلِ رکورد).
  • موتور: engine.scalp_engine (simulate_trades + run_capital) — همان موتورِ رکورد.
  • سرمایه: initial=10000, risk=1%, compounding=True، هزینهٔ واقعیِ طلا.
  • ورود روی open کندلِ بعد از سیگنال (forward-safe).
  • گیت‌های پذیرش (همه باید سبز شوند وگرنه رکورد دست‌نخورده می‌ماند):
      (۱) هر دو نیمهٔ داده مثبت.
      (۲) هر ۴ پنجرهٔ walk-forward مثبت.
      (۳) |corr روزانه با S67-proxy (long طلا)| < 0.35.
      (۴) |corr روزانه با Overnight (S139)| < 0.35.
      (۵) |corr روزانه با Monday (S140)| < 0.35.
      (۶) |corr روزانه با Turn-of-Month (S141)| < 0.35.
      (۷) |corr روزانه با Mid-Month (S142)| < 0.35.  ← گیتِ نو (کلیدی)
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
RECORD_TOTAL = 195269.0          # رکوردِ فعلی (S143 EURUSD Mid-Month)
CORR_MAX = 0.35

# روزهای پیش از پایانِ ماه (از اکتشاف). خوشهٔ پایدارِ both-halves + هر ۴ چارک مثبت.
# from_end = -1 یعنی آخرین روزِ معاملاتیِ ماه؛ -6/-7 یعنی ۶/۷ روز مانده به پایان.
PRE_END_DAYS = [-6, -7, -3]
# پنجرهٔ ساعتیِ عصر (۱۶–۲۱ UTC) — محافظه‌کارانه، جدا از Overnight (۲۲–۲۳).
PRE_END_HOURS = [16, 17, 18, 19, 20, 21]


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    m = dict(zip(days['date'], days['from_end']))
    df = df.copy()
    df['from_end'] = df['date'].map(m).astype(int)
    return df


def assign_tom_rel(df):
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


def build_eom_signals(df, days, hours):
    """long روی کندلی که روزِ نسبی‌اش به پایانِ ماه در {days} و ساعتش در {hours} است."""
    n = len(df)
    long_sig = np.isin(df['from_end'].values, days) & np.isin(df['hour'].values, hours)
    return long_sig, np.zeros(n, bool)


def build_overnight_signals(df, hours=(22, 23)):
    n = len(df)
    return np.isin(df['hour'].values, list(hours)), np.zeros(n, bool)


def build_monday_signals(df, hours=(18, 19, 20, 21)):
    n = len(df)
    return ((df['dow'].values == 0) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)


def build_tom_signals(df, hours=(7, 8, 9, 10, 11, 12)):
    d = assign_tom_rel(df)
    n = len(df)
    return ((d['tom_rel'].values == 1) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)


def build_midmonth_signals(df, days=(10, 13, 20), hours=tuple(range(1, 13))):
    n = len(df)
    return (np.isin(df['dom'].values, list(days)) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)


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
        ls, ss = build_eom_signals(sub, days, hours)
        st, _ = run_layer(sub, ls, ss, sl, tp, mh)
        outs.append(round(net_of(st), 0))
    return outs


def main():
    df = load()
    df = assign_from_end(df)
    n = len(df); half = n // 2
    print(f"داده: {n} کندلِ M15 XAUUSD | رکوردِ فعلی = ${RECORD_TOTAL:,.0f}")
    print(f"ماشه: روزهای پیش از پایانِ ماه {PRE_END_DAYS}، ساعاتِ {PRE_END_HOURS} UTC\n")

    # --- جاروبِ سبکِ خروج (هم‌ترازِ S142) ---
    print(f"{'='*74}\n۱) جاروبِ سبکِ خروج (SL/TP/max_hold)\n{'='*74}")
    print(f"{'SL':>5}{'TP':>6}{'mh':>5}{'net$':>12}{'PF':>7}{'WR%':>7}{'N':>7}  both")
    combos = []
    for sl in [100, 150, 200]:
        for tp in [300, 500, 700]:
            for mh in [48, 96]:
                ls, ss = build_eom_signals(df, PRE_END_DAYS, PRE_END_HOURS)
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
        _save(None)
        return

    best = max(both_combos, key=lambda c: c[0])
    net_best, sl, tp, mh, _ = best
    layer_net_conservative = float(np.mean([c[0] for c in both_combos]))
    print(f"\n🏅 برندهٔ جاروب: SL{sl}/TP{tp}/mh{mh} ⇒ net=${net_best:,.0f}")
    print(f"📉 سودِ محافظه‌کارانهٔ لایه (میانگینِ {len(both_combos)} ترکیبِ both✓) = ${layer_net_conservative:,.0f}")

    # --- گیت‌های ضدِ overfit روی برنده ---
    ls, ss = build_eom_signals(df, PRE_END_DAYS, PRE_END_HOURS)
    st, tr = run_layer(df, ls, ss, sl, tp, mh)
    trh1 = tr[tr['exit_bar'] < half]; trh2 = tr[tr['exit_bar'] >= half]
    s1 = se.run_capital(trh1, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0]
    s2 = se.run_capital(trh2, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0]
    wf = walk_forward(df, PRE_END_DAYS, PRE_END_HOURS, sl, tp, mh)

    print(f"\n{'='*74}\n۲) گیت‌های ضدِ Overfit\n{'='*74}")
    print(f"Both-halves:  H1=${net_of(s1):,.0f}  H2=${net_of(s2):,.0f}  ⇒ {'✅' if net_of(s1)>0 and net_of(s2)>0 else '❌'}")
    print(f"Walk-Forward: {wf}  ⇒ {'✅ همه مثبت' if all(x>0 for x in wf) else '❌'}")

    # --- افزایشی‌بودن (corr با همهٔ ۵ لایهٔ زمانی + S67) ---
    _, tr_on = run_layer(df, *build_overnight_signals(df), 150, 500, 96)
    _, tr_mon = run_layer(df, *build_monday_signals(df), 150, 500, 96)
    _, tr_tom = run_layer(df, *build_tom_signals(df), 100, 700, 96)
    _, tr_mm = run_layer(df, *build_midmonth_signals(df), 100, 500, 96)
    _, tr_67 = run_layer(df, *build_s67_proxy(df), 150, 500, 96)
    corr_on = corr_daily(df, tr, tr_on)
    corr_mon = corr_daily(df, tr, tr_mon)
    corr_tom = corr_daily(df, tr, tr_tom)
    corr_mm = corr_daily(df, tr, tr_mm)
    corr_67 = corr_daily(df, tr, tr_67)

    print(f"\n{'='*74}\n۳) آزمونِ افزایشی‌بودن (corr روزانه، آستانه {CORR_MAX})\n{'='*74}")
    print(f"corr با Overnight    (S139): {corr_on:+.3f}  ⇒ {'✅' if abs(corr_on)<CORR_MAX else '❌'}")
    print(f"corr با Monday       (S140): {corr_mon:+.3f}  ⇒ {'✅' if abs(corr_mon)<CORR_MAX else '❌'}")
    print(f"corr با TurnOfMonth  (S141): {corr_tom:+.3f}  ⇒ {'✅' if abs(corr_tom)<CORR_MAX else '❌'}")
    print(f"corr با MidMonth     (S142): {corr_mm:+.3f}  ⇒ {'✅' if abs(corr_mm)<CORR_MAX else '❌'}")
    print(f"corr با S67-proxy   (long) : {corr_67:+.3f}  ⇒ {'✅' if abs(corr_67)<CORR_MAX else '❌'}")

    gates_ok = (net_of(s1) > 0 and net_of(s2) > 0 and all(x > 0 for x in wf)
                and abs(corr_on) < CORR_MAX and abs(corr_mon) < CORR_MAX
                and abs(corr_tom) < CORR_MAX and abs(corr_mm) < CORR_MAX
                and abs(corr_67) < CORR_MAX)

    print(f"\n{'='*74}\n۴) جمع‌بندی\n{'='*74}")
    print(f"سودِ محافظه‌کارانهٔ لایه: ${layer_net_conservative:,.0f}  (max ترکیب: ${net_best:,.0f})")
    print(f"WR (گزارشی): {st['win_rate']:.1f}%  PF: {st['profit_factor']:.2f}  MaxDD: {st['max_dd_pct']:.1f}%  Sharpe: {st['sharpe']:.2f}  N={st['n_trades']}")
    print(f"همهٔ گیت‌ها: {'✅ سبز — افزایشی به رکورد' if gates_ok else '❌ — رکورد دست‌نخورده'}")
    new_total = RECORD_TOTAL + layer_net_conservative if gates_ok else RECORD_TOTAL
    if gates_ok:
        print(f"\n🥇 رکوردِ جدید = ${RECORD_TOTAL:,.0f} + ${layer_net_conservative:,.0f} = ${new_total:,.0f}")

    _save({
        'strategy': 'Gold End-of-Month (Pre-End) Drift (S144)',
        'pre_end_days': PRE_END_DAYS, 'hours': PRE_END_HOURS,
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
        'corr_tom': round(corr_tom, 3), 'corr_midmonth': round(corr_mm, 3),
        'corr_s67': round(corr_67, 3),
        'gates_ok': bool(gates_ok),
        'record_prev': RECORD_TOTAL,
        'record_new': round(new_total, 0),
    })


def _save(out):
    if out is None:
        out = {'strategy': 'Gold End-of-Month (Pre-End) Drift (S144)',
               'gates_ok': False, 'record_prev': RECORD_TOTAL, 'record_new': RECORD_TOTAL,
               'note': 'no both-halves combo'}
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s144_endofmonth.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nذخیره شد: results/_s144_endofmonth.json")


if __name__ == '__main__':
    main()
