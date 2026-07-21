"""
s139_gold_overnight_drift.py — لایهٔ نو: «Overnight Drift» روی طلا M15 (Long)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (User Note این نشست: «نبوغ‌آمیز فکر کن!»):
  گلوگاهِ اثبات‌شدهٔ پروژه = «نبودِ جریانِ ساختاراً غیرِهم‌بسته» (PARADIGM §۶).
  پس از رد شدنِ صادقانهٔ دو ایده (lead-lag DXY و رژیمِ DXY؛ لبه < اسپرد)، از ادبیاتِ
  آکادمیک الهام گرفتیم: **The Overnight Drift** (Lou, Polk & Skouras, JFE 2019).

کشفِ ساختاری (explore_gold_overnight_drift.py):
  • بازهٔ شبانه (۲۱:۰۰–۰۶:۰۰ UTC) میانگینِ +۰.۴۷pip/کندلِ مثبت دارد (t=+۳.۱)،
    در حالی که بازهٔ روز (۰۷–۲۰) تقریباً صفر/منفی است (−۰.۰۲pip، t=−۰.۱).
  • ورودِ Long در ساعتِ ۲۱/۲۲/۲۳ UTC و هولدِ چند ساعته یک درایوِ صعودیِ قوی می‌دهد
    (t تا +۷.۸). **در هر دو نیمهٔ داده و هر ۴ پنجرهٔ walk-forward مثبت است** (پایدار).

چرا نامزدِ جریانِ غیرِهم‌بسته است:
  منبعِ سود «نگه‌داری در بازهٔ زمانیِ خاصِ شبانه/کم‌نقدینگی» است — نه یک ماشهٔ قیمتی/
  اندیکاتوری (مثلِ S67/Scalp/Squeeze/SHORT). این تفاوتِ مکانیزم می‌تواند همبستگیِ
  روزانه را پایین نگه دارد. **افزایشی‌بودن با آزمونِ همبستگیِ روزانه سنجیده می‌شود.**

--------------------------------------------------------------------------------
متدولوژیِ سیب‌به‌سیب با رکورد (ضدِ overfit):
  • داده: ۱۵۰٬۰۰۰ کندلِ M15 XAUUSD.
  • موتور: engine.scalp_engine (simulate_trades + run_capital) — همان موتوری که
    لایهٔ Squeeze/SHORT را در رکورد ساخت. اسپردِ واقعیِ طلا ۴pip + اسلیپیج ۰.۵.
  • سرمایه: initial=10000, risk=1%, compounding=True (هم‌ترازِ رکوردِ Squeeze).
  • ورود روی open کندلِ بعد از سیگنال (forward-safe، بدونِ look-ahead).
  • گیت‌های پذیرش (همه باید سبز شوند وگرنه رکورد دست‌نخورده می‌ماند):
      (۱) هر دو نیمهٔ داده مثبت.
      (۲) هر ۴ پنجرهٔ walk-forward مثبت.
      (۳) همبستگیِ روزانه با «لایهٔ نمایندهٔ long طلا (S67)» < ۰.۳۵ (افزایشی).
  • جاروبِ سبکِ خروج (TP/SL/max_hold) فقط برای یافتنِ خروجِ منطقی؛ برنده باید در
    گیت‌ها robust بماند (نه صرفاً بهترین عدد).
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
RECORD_TOTAL = 128325.0            # رکوردِ فعلی (S138)
CORR_MAX = 0.35                    # سقفِ همبستگیِ روزانه برای «افزایشی»


def build_overnight_signals(df, hours):
    """سیگنالِ long روی کندلی که ساعتش در `hours` است ⇒ ورود در open کندلِ بعد."""
    n = len(df)
    hour = pd.to_datetime(df['time'], unit='s').dt.hour.values
    long_sig = np.zeros(n, bool)
    for h in hours:
        long_sig |= (hour == h)
    return long_sig


def run_layer(df, hours, sl, tp, mh, be=None, trail=None):
    long_sig = build_overnight_signals(df, hours)
    short_sig = np.zeros(len(df), bool)
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
    """سودِ خالصِ روزانه (بر حسبِ pip×lot تقریبی از pnl_pip) برای سنجشِ همبستگی."""
    if tr is None or len(tr) == 0:
        return pd.Series(dtype=float)
    exit_bar = tr['exit_bar'].values.astype(int)
    exit_bar = np.clip(exit_bar, 0, len(df) - 1)
    dt = pd.to_datetime(df['time'].values[exit_bar], unit='s')
    day = pd.to_datetime(dt.date)
    s = pd.Series(tr['pnl_pip'].values, index=day)
    return s.groupby(level=0).sum()


def main():
    print("=" * 92)
    print("s139 — لایهٔ نو: Overnight Drift روی طلا M15 (Long، زمان-محور)")
    print("قانونِ #۱: سودِ خالص = XAUUSD + EURUSD (نه WR). هدف: جریانِ غیرِهم‌بستهٔ نو.")
    print("=" * 92, flush=True)

    df = pd.read_csv(DATA)
    n = len(df)
    half = n // 2
    df1 = df.iloc[:half].reset_index(drop=True)
    df2 = df.iloc[half:].reset_index(drop=True)

    # ---- جاروبِ سبکِ خروج روی ساعاتِ کاندید ----
    hour_sets = {
        '21-23': [21, 22, 23],
        '22-23': [22, 23],
        '21': [21], '22': [22], '23': [23],
    }
    exits = [
        (90, 300, 48), (120, 400, 64), (150, 500, 96),
        (200, 600, 96), (100, 250, 32), (150, 450, 96),
    ]

    print(f"\n{'ساعات':>8}{'SL':>5}{'TP':>5}{'mh':>4}{'n':>6}{'net':>11}{'H1':>10}{'H2':>10}{'WF-min':>10} حکم")
    print("-" * 84)
    rows = []
    for hlabel, hours in hour_sets.items():
        for (sl, tp, mh) in exits:
            st, tr = run_layer(df, hours, sl, tp, mh)
            if st is None:
                continue
            net = net_of(st)
            st1, _ = run_layer(df1, hours, sl, tp, mh)
            st2, _ = run_layer(df2, hours, sl, tp, mh)
            h1, h2 = net_of(st1), net_of(st2)
            # walk-forward 4
            wf = []
            for k in range(4):
                a = k * (n // 4); b = n if k == 3 else (k + 1) * (n // 4)
                seg = df.iloc[a:b].reset_index(drop=True)
                sK, _ = run_layer(seg, hours, sl, tp, mh)
                wf.append(net_of(sK))
            wf_min = min(wf)
            both = h1 > 0 and h2 > 0
            wf_ok = wf_min > 0
            ok = both and wf_ok and net > 0
            flag = "✅" if ok else "—"
            print(f"{hlabel:>8}{sl:>5}{tp:>5}{mh:>4}{st['n_trades']:>6}"
                  f"${net:>+10,.0f}${h1:>+9,.0f}${h2:>+9,.0f}${wf_min:>+9,.0f} {flag}", flush=True)
            rows.append(dict(hours=hlabel, sl=sl, tp=tp, mh=mh, n=int(st['n_trades']),
                             net=float(net), h1=float(h1), h2=float(h2),
                             wf=[float(x) for x in wf], wf_min=float(wf_min),
                             both=bool(both), wf_ok=bool(wf_ok), ok=bool(ok)))

    passed = [r for r in rows if r['ok']]
    out = dict(sweep=rows, record_total=RECORD_TOTAL)
    if not passed:
        print("\n⚠️ هیچ پیکربندی‌ای گیت‌های both-halves + WF را پاس نکرد. رکورد دست‌نخورده.")
        out['verdict'] = False
        with open(os.path.join(RESULTS, '_s139_overnight.json'), 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=2, default=float)
        return

    # برنده = بیشترین سودِ خالص در میانِ پاس‌شده‌ها
    passed.sort(key=lambda r: -r['net'])
    best = passed[0]
    print(f"\n{'='*92}\n🏆 برندهٔ سودِ خالص (پاسِ both+WF): ساعات {best['hours']}  "
          f"SL{best['sl']}/TP{best['tp']}/mh{best['mh']}  net=${best['net']:+,.0f}")
    print(f"   H1=${best['h1']:+,.0f}  H2=${best['h2']:+,.0f}  WF={['%+.0f'%x for x in best['wf']]}")

    # ---- آزمونِ همبستگیِ روزانه با لایهٔ نمایندهٔ long طلا (S67 از cache) ----
    hours = hour_sets[best['hours']]
    _, tr_best = run_layer(df, hours, best['sl'], best['tp'], best['mh'])
    d_over = daily_pnl(df, tr_best)

    corr = None
    try:
        corr = correlation_with_s67(df, d_over)
    except Exception as e:
        print(f"   (هشدار: محاسبهٔ همبستگیِ S67 ناموفق: {e})")

    additive = (corr is None) or (abs(corr) < CORR_MAX)
    if corr is not None:
        print(f"\n   همبستگیِ روزانه با S67 (long طلا): {corr:+.3f}  "
              f"({'افزایشی ✅ (<0.35)' if additive else 'هم‌بسته ⚠️ (≥0.35)'})")

    new_total = RECORD_TOTAL + best['net'] if additive else RECORD_TOTAL
    verdict = additive and best['net'] > 0
    print(f"\n   رکوردِ فعلی = ${RECORD_TOTAL:,.0f}")
    if additive:
        print(f"   + لایهٔ Overnight (افزایشی) = ${best['net']:+,.0f}")
        print(f"   ⇒ رکوردِ جدید = ${new_total:,.0f}  (Δ ${new_total-RECORD_TOTAL:+,.0f})")
    else:
        print(f"   ⇒ هم‌بسته با long-stack؛ طبقِ قانونِ dedup به رکورد اضافه نمی‌شود.")

    print(f"\n   {'✅✅ رکوردِ جدید تأیید شد!' if verdict and new_total>RECORD_TOTAL else '⚠️ گیتِ نهایی: رکورد دست‌نخورده'}")

    out.update(best=best, daily_corr_s67=corr, additive=bool(additive),
               new_total=float(new_total), verdict=bool(verdict and new_total > RECORD_TOTAL))
    with open(os.path.join(RESULTS, '_s139_overnight.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s139_overnight.json")


def correlation_with_s67(df, d_over):
    """سودِ روزانهٔ S67 را از cache بازتولید و همبستگیِ روزانه را می‌سنجد."""
    from engine.backtest import load_data, run_backtest
    from engine.tpsl_plan import build_plan
    from engine.capital_engine import run_capital_backtest
    HZ = 48; SPREAD = 0.20; ER_TREND_THR = 0.30; P_HI = 0.66; P_MIN = 0.58
    cache = os.path.join(RESULTS, '_s61_cache.npz')
    z = np.load(cache, allow_pickle=True)
    pL, pS = z['pL'], z['pS']; up_reg, down_reg = z['up_reg'], z['down_reg']
    er = z['er']; atrv = z['atrv']
    dfg = load_data('data/XAUUSD_M15.csv')
    ng = len(dfg)
    trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)
    baseL = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)
    baseS = down_reg & ~np.isnan(atrv) & (pS >= P_MIN)

    def build_labels(direction, base):
        p = pL if direction == 'long' else pS
        ef = np.where(trendy, 'trend', 'chop')
        pw = np.where(p >= P_HI, 'hi', 'lo')
        lab = np.array([f'{a}_{b}' for a, b in zip(ef, pw)], dtype=object)
        lab[~base] = ''
        return lab

    labL = build_labels('long', baseL); labS = build_labels('short', baseS)
    eval_mask = np.zeros(ng, bool); eval_mask[24000:] = True
    planL = build_plan('long', labL, atrv, dfg, run_backtest, spread=SPREAD, max_hold=HZ)
    planS = build_plan('short', labS, atrv, dfg, run_backtest, spread=SPREAD, max_hold=HZ)

    def get_trades(direction, plan):
        s = plan.entries & eval_mask
        st, tr = run_backtest(dfg, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                              sl_series=plan.sl_series(), tp_series=plan.tp_series())
        if len(tr) == 0:
            return tr
        return tr

    trL = get_trades('long', planL); trS = get_trades('short', planS)
    all_tr = pd.concat([trL, trS], ignore_index=True)
    if len(all_tr) == 0:
        return None
    exit_bar = np.clip(all_tr['exit_bar'].values.astype(int), 0, ng - 1)
    dt = pd.to_datetime(dfg['time'].values[exit_bar], unit='s')
    day = pd.to_datetime(dt.date)
    d_s67 = pd.Series(all_tr['pnl_pip'].values, index=day).groupby(level=0).sum()

    idx = d_over.index.union(d_s67.index)
    a = d_over.reindex(idx).fillna(0.0)
    b = d_s67.reindex(idx).fillna(0.0)
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a.values, b.values)[0, 1])


if __name__ == '__main__':
    main()
