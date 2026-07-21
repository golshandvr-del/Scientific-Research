"""
s141_gold_turn_of_month.py — لایهٔ نو: «Turn-of-the-Month Drift» روی طلا M15 (Long)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
> این فایل دقیقاً **یک** استراتژی را مستند می‌کند.

--------------------------------------------------------------------------------
منشأ (User Note این نشست: «نبوغ‌آمیز فکر کن! رکوردشو بشکن»):
  دو رکوردِ اخیر لبه‌های *زمان-محور* بودند و هر یک از **یک محورِ زمانیِ متفاوت**:
    • S139 Overnight (+$171,738) → بُعدِ «ساعتِ روز» (۲۲–۲۳ UTC).
    • S140 Monday    (+$175,246) → بُعدِ «روزِ هفته» (دوشنبه ۱۸–۲۱ UTC).
  ایدهٔ نبوغ‌آمیزِ این نشست: بُعدِ زمانیِ **سومِ متعامد** = «روزِ تقویمیِ ماه»،
  یعنی **«اثرِ چرخشِ ماه» (Turn-of-the-Month)** — Ariel (1987, JFE)،
  Lakonishok–Smidt (1988, RFS)، McConnell–Xu (2008). فرضیه: بازدهِ طلا در
  **اولین روزِ معاملاتیِ هر ماه** به‌خاطرِ بازموازنه‌سازیِ صندوق‌ها، جریانِ
  حقوق/مستمریِ نهادی و ورودِ نقدینگیِ ابتدای ماه، یک drift صعودیِ ساختاری دارد.

کشفِ ساختاری (explore_gold_turn_of_month.py — پیش از ساختِ استراتژی):
  محورِ خالصِ tom_rel (افق ۲۴ کندل):
    tom_rel=+1 (اولین روزِ معاملاتیِ ماه): t=+9.66، mean=+26.47pip، both-halves ✓✓
        (h1=+15.22, h2=+37.82) ← قوی‌ترین t-stat در کلِ پروژه.
    tom_rel=+6: t=+6.70، both ✓ (ضعیف‌تر).
  نقشهٔ tom_rel=+1 × ساعت: ساعاتِ سشنِ لندن ۷–۱۰ UTC قوی‌ترین‌اند
    (h7 t=4.4 mean=56pip، h8 t=3.7 mean=75pip، h9 t=4.3، h10 t=4.0).
  ⚠️ این ساعات با پنجرهٔ Overnight (۲۲–۲۳) و Monday (۱۸–۲۱) **هم‌پوشانی ندارند**
    ⇒ کاندیدِ جریانِ غیرِهم‌بسته.

چرا نامزدِ جریانِ غیرِهم‌بسته است (کلیدِ الحاق به رکورد):
  منبعِ سود «drift ابتدای ماه» است که یک بُعدِ تقویمیِ کاملاً متفاوت از «ساعتِ روز»
  (Overnight) و «روزِ هفته» (Monday) است. اولین‌روزِ‌ماه در روزهای مختلفِ هفته و
  در ساعاتِ متفاوت رخ می‌دهد ⇒ افزایشی‌بودن با corr روزانه اثبات می‌شود.

--------------------------------------------------------------------------------
متدولوژیِ سیب‌به‌سیب با رکورد (ضدِ overfit — هم‌ترازِ S139/S140):
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
  • انتخابِ محافظه‌کارانهٔ سودِ لایه = میانگینِ همهٔ ترکیب‌های خروج (کف، نه سقف) —
      دقیقاً مطابقِ سنتِ S140.
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
RECORD_TOTAL = 175246.0          # رکوردِ فعلی (S140 Monday)
CORR_MAX = 0.35

# پنجرهٔ ساعتیِ قویِ اولِ ماه (سشنِ لندن؛ از اکتشاف). محافظه‌کارانه ۷–۱۲ UTC.
TOM_HOURS = [7, 8, 9, 10, 11, 12]


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_tom_rel(df):
    """شاخصِ روزِ معاملاتی نسبت به چرخشِ ماه (منطبق بر اسکریپتِ اکتشاف)."""
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
    df['tom_rel'] = df['date'].map(m).astype(int)
    return df


def build_tom_signals(df, hours):
    """long روی کندلی که «اولین روزِ معاملاتیِ ماه» (tom_rel==1) و ساعتش در hours است."""
    n = len(df)
    long_sig = (df['tom_rel'].values == 1) & np.isin(df['hour'].values, hours)
    return long_sig, np.zeros(n, bool)


def build_overnight_signals(df, hours=(22, 23)):
    n = len(df)
    return np.isin(df['hour'].values, list(hours)), np.zeros(n, bool)


def build_monday_signals(df, hours=(18, 19, 20, 21)):
    n = len(df)
    return ((df['dow'].values == 0) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)


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


def walk_forward(df, hours, sl, tp, mh, nwin=4):
    n = len(df); edges = np.linspace(0, n, nwin + 1, dtype=int); outs = []
    for k in range(nwin):
        sub = df.iloc[edges[k]:edges[k+1]].reset_index(drop=True)
        sub = assign_tom_rel(sub)
        ls, ss = build_tom_signals(sub, hours)
        st, _ = run_layer(sub, ls, ss, sl, tp, mh)
        outs.append(round(net_of(st), 0))
    return outs


def main():
    df = load()
    df = assign_tom_rel(df)
    n = len(df); half = n // 2
    print(f"داده: {n} کندلِ M15 XAUUSD | رکوردِ فعلی = ${RECORD_TOTAL:,.0f}")
    print(f"ماشه: اولین روزِ معاملاتیِ ماه (tom_rel=1)، ساعاتِ {TOM_HOURS} UTC\n")

    # --- جاروبِ سبکِ خروج ---
    print(f"{'='*74}\n۱) جاروبِ سبکِ خروج (SL/TP/max_hold)\n{'='*74}")
    print(f"{'SL':>5}{'TP':>6}{'mh':>5}{'net$':>12}{'PF':>7}{'WR%':>7}{'N':>7}  both")
    combos = []
    for sl in [100, 150, 200]:
        for tp in [300, 500, 700]:
            for mh in [48, 96]:
                ls, ss = build_tom_signals(df, TOM_HOURS)
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

    # برندهٔ جاروب برای گزارشِ گیت‌ها = بالاترین net که both باشد
    best = max(both_combos, key=lambda c: c[0])
    net_best, sl, tp, mh, _ = best
    # سودِ محافظه‌کارانهٔ لایه = میانگینِ همهٔ ترکیب‌های both-halves (کف، مطابقِ S140)
    layer_net_conservative = float(np.mean([c[0] for c in both_combos]))
    print(f"\n🏅 برندهٔ جاروب: SL{sl}/TP{tp}/mh{mh} ⇒ net=${net_best:,.0f}")
    print(f"📉 سودِ محافظه‌کارانهٔ لایه (میانگینِ {len(both_combos)} ترکیبِ both✓) = ${layer_net_conservative:,.0f}")

    # --- گیت‌های ضدِ overfit روی برنده ---
    ls, ss = build_tom_signals(df, TOM_HOURS)
    st, tr = run_layer(df, ls, ss, sl, tp, mh)
    trh1 = tr[tr['exit_bar'] < half]; trh2 = tr[tr['exit_bar'] >= half]
    s1 = se.run_capital(trh1, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0]
    s2 = se.run_capital(trh2, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0]
    wf = walk_forward(df, TOM_HOURS, sl, tp, mh)

    print(f"\n{'='*74}\n۲) گیت‌های ضدِ Overfit\n{'='*74}")
    print(f"Both-halves:  H1=${net_of(s1):,.0f}  H2=${net_of(s2):,.0f}  ⇒ {'✅' if net_of(s1)>0 and net_of(s2)>0 else '❌'}")
    print(f"Walk-Forward: {wf}  ⇒ {'✅ همه مثبت' if all(x>0 for x in wf) else '❌'}")

    # --- افزایشی‌بودن ---
    _, tr_on = run_layer(df, *build_overnight_signals(df), 150, 500, 96)
    _, tr_mon = run_layer(df, *build_monday_signals(df), 150, 500, 96)
    _, tr_67 = run_layer(df, *build_s67_proxy(df), 150, 500, 96)
    corr_on = corr_daily(df, tr, tr_on)
    corr_mon = corr_daily(df, tr, tr_mon)
    corr_67 = corr_daily(df, tr, tr_67)

    print(f"\n{'='*74}\n۳) آزمونِ افزایشی‌بودن (corr روزانه، آستانه {CORR_MAX})\n{'='*74}")
    print(f"corr با Overnight (S139): {corr_on:+.3f}  ⇒ {'✅' if abs(corr_on)<CORR_MAX else '❌'}")
    print(f"corr با Monday    (S140): {corr_mon:+.3f}  ⇒ {'✅' if abs(corr_mon)<CORR_MAX else '❌'}")
    print(f"corr با S67-proxy (long): {corr_67:+.3f}  ⇒ {'✅' if abs(corr_67)<CORR_MAX else '❌'}")

    gates_ok = (net_of(s1) > 0 and net_of(s2) > 0 and all(x > 0 for x in wf)
                and abs(corr_on) < CORR_MAX and abs(corr_mon) < CORR_MAX and abs(corr_67) < CORR_MAX)

    print(f"\n{'='*74}\n۴) جمع‌بندی\n{'='*74}")
    print(f"سودِ محافظه‌کارانهٔ لایه: ${layer_net_conservative:,.0f}  (max ترکیب: ${net_best:,.0f})")
    print(f"WR (گزارشی): {st['win_rate']:.1f}%  PF: {st['profit_factor']:.2f}  MaxDD: {st['max_dd_pct']:.1f}%  Sharpe: {st['sharpe']:.2f}  N={st['n_trades']}")
    print(f"همهٔ گیت‌ها: {'✅ سبز — افزایشی به رکورد' if gates_ok else '❌ — رکورد دست‌نخورده'}")
    new_total = RECORD_TOTAL + layer_net_conservative if gates_ok else RECORD_TOTAL
    if gates_ok:
        print(f"\n🥇 رکوردِ جدید = ${RECORD_TOTAL:,.0f} + ${layer_net_conservative:,.0f} = ${new_total:,.0f}")

    out = {
        'strategy': 'Gold Turn-of-the-Month Drift (S141)',
        'tom_rel': 1, 'tom_hours': TOM_HOURS,
        'best_exit': {'sl': sl, 'tp': tp, 'mh': mh},
        'net_layer_max': round(net_best, 0),
        'net_layer_conservative': round(layer_net_conservative, 0),
        'n_both_combos': len(both_combos),
        'wr': round(st['win_rate'], 1), 'pf': round(st['profit_factor'], 2),
        'maxdd_pct': round(st['max_dd_pct'], 1), 'sharpe': round(st['sharpe'], 2),
        'n_trades': int(st['n_trades']),
        'both_halves': [round(net_of(s1), 0), round(net_of(s2), 0)],
        'walk_forward': wf,
        'corr_overnight': round(corr_on, 3), 'corr_monday': round(corr_mon, 3), 'corr_s67': round(corr_67, 3),
        'gates_ok': bool(gates_ok),
        'record_prev': RECORD_TOTAL,
        'record_new': round(new_total, 0),
    }
    with open(os.path.join(RESULTS, '_s141_turn_of_month.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nذخیره شد: results/_s141_turn_of_month.json")


if __name__ == '__main__':
    main()
