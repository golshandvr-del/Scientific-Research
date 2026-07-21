"""
s145_gold_short_preeom.py — لایهٔ نو: «Gold Pre-EOM SHORT Drift» روی طلا M15
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
> این فایل دقیقاً **یک** استراتژی را مستند می‌کند.

--------------------------------------------------------------------------------
منشأ (User Note این نشست): «s144 رکورد دارد؛ رکوردشو بزن. راستی چرا روی SHORT کاری
نمی‌کنیم؟ SHORT یک غولِ شکست‌ناپذیر بوده تا اینجا!»

کشفِ اکتشاف (explore_gold_calendar_short.py + explore_gold_short_eom_deep.py):
  همهٔ لایه‌های رکوردشکنِ اخیر (S139..S144) long و از محورِ «drift تقویمیِ صعودی»
  بودند. اما محورِ تقویمی در جهتِ SHORT هرگز اسکن نشده بود. اسکن نشان داد:
    • قوی‌ترین drift نزولیِ ساختاریِ طلا در روزهای **۹-۱۰ روزِ معاملاتی مانده به
      پایانِ ماه** (from_end ∈ {-9,-10}) است — کاملاً متمایز و *متعامد* با پنجرهٔ
      long ِ S144 (from_end ∈ {-6,-7,-8}).
    • خوشهٔ {-9,-10} + ساعاتِ ۱۶–۲۱ UTC: t=-5.46، mean=-12.35pip، **هر دو نیمهٔ
      داده منفی** (h1=-10.6, h2=-14.1pip) ⇒ drift نزولیِ پایدار.

تفسیرِ اقتصادی: این «آینهٔ» پیش‌پوزیشن‌گیریِ نهادی است. حدودِ دو هفتهٔ مانده به
پایانِ ماه، پیش از موجِ خریدِ turn-of-month (که S141/S144 آن را long می‌گیرند)، یک
فازِ کاهشِ ریسک/فروشِ نهادی رخ می‌دهد (تسویهٔ موقعیت‌های ماهِ جاری، تأمینِ نقدینگی).
این پیش از فازِ window-dressing/بازموازنه‌سازیِ صعودیِ اواخرِ ماه می‌آید.

چرا نامزدِ جریانِ غیرِهم‌بسته است (کلیدِ الحاق به رکورد):
  • جهت = SHORT (برخلافِ همهٔ لایه‌های تقویمیِ رکورد که long هستند) ⇒ ذاتاً corr پایین.
  • روزها = from_end {-9,-10} که با هیچ لایهٔ دیگری همپوشانی ندارند
    (S144 long در {-6,-7,-8}؛ S141 long در rank=1؛ S142 در dom={10,13,20}).

--------------------------------------------------------------------------------
متدولوژیِ سیب‌به‌سیب با رکورد (ضدِ overfit — دقیقاً هم‌ترازِ S139..S144):
  • داده: ۱۵۰٬۰۰۰ کندلِ M15 XAUUSD (همان فایلِ رکورد).
  • موتور: engine.scalp_engine (simulate_trades + run_capital) — همان موتورِ رکورد.
  • سرمایه: initial=10000, risk=1%, compounding=True، هزینهٔ واقعیِ طلا.
  • ورود روی open کندلِ بعد از سیگنال (forward-safe).
  • ماشهٔ ورود *از پیش تعیین‌شده* (نه بهینه‌سازیِ کور): SHORT روی هر کندلی که
    from_end ∈ {-9,-10} و hour ∈ {16..21}. فقط سبکِ خروج (SL/TP/max_hold) جارو می‌شود.
  • گیت‌های پذیرش (همه باید سبز شوند وگرنه رکورد دست‌نخورده می‌ماند):
      (۱) هر دو نیمهٔ داده مثبت.
      (۲) هر ۴ پنجرهٔ walk-forward مثبت.
      (۳) |corr روزانه با S67-proxy (long طلا)| < 0.35.
      (۴) |corr روزانه با Overnight (S139)| < 0.35.
      (۵) |corr روزانه با Monday (S140)| < 0.35.
      (۶) |corr روزانه با Turn-of-Month (S141)| < 0.35.
      (۷) |corr روزانه با Mid-Month (S142)| < 0.35.
      (۸) |corr روزانه با End-of-Month long (S144)| < 0.35.
      (۹) |corr روزانه با SHORT-MA-Confluence (لایهٔ SHORTِ موجود)| < 0.35.
  • انتخابِ محافظه‌کارانهٔ سودِ لایه = میانگینِ ترکیب‌هایی که both✓ و allWF✅ (کف، نه سقف).
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
RECORD_TOTAL = 196481.0          # رکوردِ فعلی (S144 End-of-Month long)
CORR_MAX = 0.35

# ماشهٔ SHORT از پیش تعیین‌شده (از اکتشاف: پایدارترین both-halves منفی).
PRE_EOM_SHORT_DAYS = [-9, -10]
PRE_EOM_SHORT_HOURS = [16, 17, 18, 19, 20, 21]


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day; df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rk'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rk'] - days['cnt'] - 1
    df['from_end'] = df['date'].map(dict(zip(days['date'], days['from_end']))).astype(int)
    df['rank_in_month'] = df['date'].map(dict(zip(days['date'], days['rk']))).astype(int)
    return df


def assign_tom_rel(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rk'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rk'] - days['cnt'] - 1
    def rel(r):
        return int(r['from_end']) if r['from_end'] >= -2 else int(r['rk'])
    days['tom_rel'] = days.apply(rel, axis=1)
    df['tom_rel'] = df['date'].map(dict(zip(days['date'], days['tom_rel']))).astype(int)
    return df


# ---------- ماشهٔ لایهٔ نو (SHORT) ----------
def build_short_eom_signals(df, days, hours):
    n = len(df)
    short_sig = np.isin(df['from_end'].values, days) & np.isin(df['hour'].values, hours)
    return np.zeros(n, bool), short_sig


# ---------- ماشه‌های لایه‌های رکورد (برای corr) ----------
def build_overnight(df, hours=(22, 23)):
    n = len(df); return np.isin(df['hour'].values, list(hours)), np.zeros(n, bool)

def build_monday(df, hours=(18, 19, 20, 21)):
    n = len(df); return ((df['dow'].values == 0) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)

def build_tom(df, hours=(7, 8, 9, 10, 11, 12)):
    d = assign_tom_rel(df); n = len(df)
    return ((d['tom_rel'].values == 1) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)

def build_midmonth(df, days=(10, 13, 20), hours=tuple(range(1, 13))):
    n = len(df); return (np.isin(df['dom'].values, list(days)) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)

def build_eom_long(df, days=(-6, -7, -8), hours=(19, 20, 21, 22, 23)):
    n = len(df); return (np.isin(df['from_end'].values, list(days)) & np.isin(df['hour'].values, list(hours))), np.zeros(n, bool)

def build_s67_proxy(df):
    c = df['close']
    ema20 = c.ewm(span=20, adjust=False).mean().values
    ema100 = c.ewm(span=100, adjust=False).mean().values
    ls = (ema20 > ema100); edge = np.zeros(len(df), bool); edge[1:] = ls[1:] & ~ls[:-1]
    return edge, np.zeros(len(df), bool)

def build_short_ma_confluence(df):
    """لایهٔ SHORTِ موجود: قطعِ رو به پایینِ میانهٔ [EMA50,EMA100,SMA200]."""
    c = df['close']
    ema50 = c.ewm(span=50, adjust=False).mean().values
    ema100 = c.ewm(span=100, adjust=False).mean().values
    sma200 = c.rolling(200).mean().values
    mid = np.nanmean(np.vstack([ema50, ema100, sma200]), axis=0)
    px = c.values; n = len(df)
    below = px < mid
    short_edge = np.zeros(n, bool)
    short_edge[1:] = below[1:] & ~below[:-1]
    return np.zeros(n, bool), short_edge


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


def walk_forward(df, sl, tp, mh, nwin=4):
    n = len(df); edges = np.linspace(0, n, nwin + 1, dtype=int); outs = []
    for k in range(nwin):
        sub = df.iloc[edges[k]:edges[k+1]].reset_index(drop=True)
        sub = assign_from_end(sub)
        ls, ss = build_short_eom_signals(sub, PRE_EOM_SHORT_DAYS, PRE_EOM_SHORT_HOURS)
        st, _ = run_layer(sub, ls, ss, sl, tp, mh)
        outs.append(round(net_of(st), 0))
    return outs


def main():
    df = assign_from_end(load())
    n = len(df); half = n // 2
    print(f"داده: {n} کندلِ M15 XAUUSD | رکوردِ فعلی = ${RECORD_TOTAL:,.0f}")
    print(f"ماشهٔ SHORT: روزهای {PRE_EOM_SHORT_DAYS} مانده به پایانِ ماه، ساعاتِ {PRE_EOM_SHORT_HOURS} UTC\n")

    # --- جاروبِ سبکِ خروجِ SHORT ---
    print("="*84)
    print("۱) جاروبِ سبکِ خروجِ SHORT (SL/TP/max_hold) — گیتِ both + WF داخلِ حلقه")
    print("="*84)
    print(f"{'SL':>5}{'TP':>6}{'mh':>5}{'net$':>12}{'PF':>7}{'WR%':>7}{'N':>7}  both  allWF")
    passing = []
    for sl in [100, 150, 200, 250]:
        for tp in [200, 300, 400, 500, 700]:
            for mh in [48, 96]:
                ls, ss = build_short_eom_signals(df, PRE_EOM_SHORT_DAYS, PRE_EOM_SHORT_HOURS)
                st, tr = run_layer(df, ls, ss, sl, tp, mh)
                if st is None:
                    continue
                trh1 = tr[tr['exit_bar'] < half]; trh2 = tr[tr['exit_bar'] >= half]
                s1 = se.run_capital(trh1, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0] if len(trh1) else None
                s2 = se.run_capital(trh2, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0] if len(trh2) else None
                both = (net_of(s1) > 0 and net_of(s2) > 0)
                wf = walk_forward(df, sl, tp, mh)
                allwf = all(x > 0 for x in wf)
                net = net_of(st)
                pf = st.get('profit_factor', 0.0); wr = st.get('win_rate', 0.0)
                mark = ('✓' if both else '✗') + '   ' + ('✅' if allwf else '❌')
                print(f"{sl:>5}{tp:>6}{mh:>5}{net:>12,.0f}{pf:>7.2f}{wr:>7.1f}{len(tr):>7}  {mark}")
                if both and allwf and net > 0:
                    passing.append(dict(sl=sl, tp=tp, mh=mh, net=net, wf=wf, n=len(tr)))

    if not passing:
        print("\n⚠️ هیچ ترکیبی هر دو گیتِ both+allWF را پاس نکرد ⇒ رکورد دست‌نخورده می‌ماند.")
        return

    layer_net = float(np.mean([p['net'] for p in passing]))
    best = max(passing, key=lambda p: p['net'])
    print(f"\nترکیب‌های پذیرفته‌شده (both✓ و allWF✅): {len(passing)}")
    print(f"سودِ محافظه‌کارانهٔ لایه (میانگینِ پذیرفته‌شده‌ها) = ${layer_net:,.0f}")
    print(f"بهترین ترکیب: SL={best['sl']} TP={best['tp']} mh={best['mh']} net=${best['net']:,.0f} WF={best['wf']}")

    # --- گیتِ corr با همهٔ لایه‌ها ---
    print("\n" + "="*84)
    print("۲) گیتِ همبستگیِ روزانه (باید |corr|<0.35 با همه)")
    print("="*84)
    ls_new, ss_new = build_short_eom_signals(df, PRE_EOM_SHORT_DAYS, PRE_EOM_SHORT_HOURS)
    _, tr_new = run_layer(df, ls_new, ss_new, best['sl'], best['tp'], best['mh'])

    layers = {
        'S67-long': build_s67_proxy(df),
        'Overnight(S139)': build_overnight(df),
        'Monday(S140)': build_monday(df),
        'TurnOfMonth(S141)': build_tom(df),
        'MidMonth(S142)': build_midmonth(df),
        'EOM-long(S144)': build_eom_long(df),
        'SHORT-MA-Confl': build_short_ma_confluence(df),
    }
    all_ok = True
    for name, (ll, sl_sig) in layers.items():
        # از خروجِ رکوردیِ نمایندهٔ هر لایه استفاده می‌کنیم (SL/TP نمایندهٔ سبکِ آن)
        st_o, tr_o = run_layer(df, ll, sl_sig, 150, 500, 96)
        c = corr_daily(df, tr_new, tr_o)
        ok = abs(c) < CORR_MAX
        all_ok = all_ok and ok
        print(f"  corr با {name:>20}: {c:+.3f}  {'✅' if ok else '❌ FAIL'}")

    print("\n" + "="*84)
    if all_ok:
        new_total = RECORD_TOTAL + layer_net
        print(f"✅ همهٔ گیت‌ها سبز. سودِ افزایشیِ لایه = ${layer_net:,.0f}")
        print(f"🥇 رکوردِ جدیدِ کل = ${new_total:,.0f}  (قبلی ${RECORD_TOTAL:,.0f}, Δ +${layer_net:,.0f})")
    else:
        print("❌ گیتِ corr شکست خورد ⇒ لایه افزایشی نیست، رکورد دست‌نخورده می‌ماند.")
    print("="*84)

    out = dict(days=PRE_EOM_SHORT_DAYS, hours=PRE_EOM_SHORT_HOURS,
               passing=passing, layer_net=layer_net, best=best,
               record_prev=RECORD_TOTAL, all_corr_ok=all_ok)
    with open(os.path.join(RESULTS, '_s145_short_preeom.json'), 'w') as f:
        json.dump(out, f, indent=2, default=float)
    print("\nنتایج در results/_s145_short_preeom.json ذخیره شد.")


if __name__ == '__main__':
    main()
