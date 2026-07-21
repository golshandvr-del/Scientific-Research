"""
s137_short_loss_filter.py — فیلترِ «کاهشِ سیگنالِ غلط» روی لایهٔ SHORT (MA-Confluence)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> از این پس Win-Rate صرفاً یک عددِ گزارشی است، نه هدف و نه قید. تعدادِ معامله در
> روز و Profit Factor هم هدف نیستند. ما دنبالِ پول هستیم، نه آمارِ زیبا.
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**
================================================================================

پاسخ به User Note این نشست:
  «از این مرحله به بعد، هدف افزایشِ سودِ خالص از طریقِ سیگنال‌های جدید نیست، بلکه هدف
   کاهشِ سیگنال‌های غلط برای کاهشِ ضررها و به‌دنبالِ آن افزایشِ سودِ خالص است.»

و مطابقِ «گام‌های بعدیِ پیشنهادی» در فایلِ رکورد (`SqueezeBreakoutFilter_NetProfit_126118.md`):
  «بررسیِ آیا همین گیتِ کیفیت روی لایهٔ SHORT (MA-confluence) هم ضرر را کم می‌کند.»

--------------------------------------------------------------------------------
هدف: لایهٔ SHORT بزرگ‌ترین منبعِ سیگنالِ غلطِ پروژه است (۳۳۱۸ معامله، ۱۴۸۶ باخت،
ضررِ ناخالص ≈۴۵٬۰۱۹ pip روی لاتِ ثابت). با یک **گیتِ کیفیتِ ورودِ قابل‌تفسیر** —
بدونِ افزودنِ لایه/کاشفِ جدید — ورودهای بی‌کیفیت (شکست‌های ضعیفِ MA که سریع
V-recovery می‌شوند) را حذف می‌کنیم تا ضرر کم و سودِ خالص زیاد شود.

روش (علمی، ضدِ overfit — دقیقاً هم‌ترازِ s136):
  ۱) ماشهٔ SHORT و خروجِ رکورد را عیناً بازتولید می‌کنیم (baseline = +$34,542).
  ۲) برای *هر معاملهٔ* SHORT، featureهای «لحظهٔ سیگنال» (اندیس ≤ signal_bar) را ثبت
     می‌کنیم — هیچ نگاهِ به آینده:
       - brk_strength : قدرتِ شکستِ رو به پایین = (mid - close)/ATR14  (قرینهٔ s136)
       - adx14        : قدرتِ روند
       - dist_ema200  : فاصلهٔ درصدیِ close از EMA200 (چقدر «کش‌آمده»)
       - rsi14        : اشباع
       - atr_pct      : ATR/price (رژیمِ نوسان)
       - slope_mid    : شیبِ خطِ میانهٔ سه‌MA در ۵ کندلِ اخیر (رو به پایین بودنِ رژیم)
  ۳) «امضای ضرر» را از مقایسهٔ توزیعِ feature در بردها vs باخت‌ها می‌یابیم.
  ۴) چند فیلترِ تک‌شرطیِ قابل‌تفسیر را جدا می‌سنجیم؛ فقط فیلتری را نگه می‌داریم که
     سودِ خالص را بالا ببرد (یا حفظ کند و ضرر/DD را کم کند) و در *هر دو نیمهٔ داده*
     و *walk-forward* پایدار باشد.
  ۵) خروجی: بهترین فیلتر + Δ سودِ خالص + آمارِ کاهشِ ضرر. ذخیره در JSON.

تنظیماتِ سرمایه دقیقاً مثلِ رکورد: initial=10000, risk=1%, compounding=False.
ورود در open کندلِ signal_bar+1 (منطبق با موتور).
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')
PIP = 0.1

# ── خروجِ رکوردِ SHORT (s118 «بگذار بردها بدوند») — دست‌نخورده ──
EXIT = dict(sl_pip=70, tp_pip=800, max_hold=48, be_trigger_pip=6, trail_pip=6)
CAP = dict(initial_capital=10000, risk_pct=1.0, compounding=False)

# اجزای رکوردِ کل (README): long+scalp+swing+squeeze خطِ XAU، و EUR
RECORD_TOTAL = 126118.0
RECORD_SHORT_BASE = 34542.0          # سهمِ فعلیِ SHORT در رکورد
RECORD_REST = RECORD_TOTAL - RECORD_SHORT_BASE   # بقیهٔ پرتفوی (دست‌نخورده)


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def short_signal(df):
    """ماشهٔ رکورد: قطعِ رو به پایینِ میانهٔ سه‌MA [EMA50, EMA100, SMA200]."""
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    sig = (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)
    return sig, mid


def build_features(df):
    """featureهای لحظهٔ سیگنال (همه با اندیس ≤ i، forward-safe)."""
    c = df['close']
    _, mid = short_signal(df)
    atr14 = ind.atr(df, 14).values
    adx14, _, _ = ind.adx(df, 14)
    adx14 = adx14.values
    ema200 = ind.ema(c, 200).values
    rsi14 = ind.rsi(c, 14).values
    price = c.values
    # قدرتِ شکستِ رو به پایین: چقدر close زیرِ mid بسته شده، مقیاس‌شده با ATR
    brk_strength = (mid - price) / np.where(atr14 > 0, atr14, np.nan)
    dist_ema200 = (price - ema200) / np.where(ema200 != 0, ema200, np.nan) * 100.0
    atr_pct = atr14 / np.where(price != 0, price, np.nan) * 100.0
    # شیبِ mid روی ۵ کندلِ اخیر (نرمالایز با ATR) — رژیمِ نزولی بودن
    slope_mid = np.full(len(df), np.nan)
    for i in range(5, len(df)):
        slope_mid[i] = (mid[i] - mid[i - 5]) / (atr14[i] if atr14[i] > 0 else np.nan)
    return dict(brk_strength=brk_strength, adx14=adx14, dist_ema200=dist_ema200,
                rsi14=rsi14, atr_pct=atr_pct, slope_mid=slope_mid)


def run(df, sig, params):
    long_flat = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_flat, sig, asset='XAUUSD', **params)
    if tr is None or len(tr) == 0:
        return None, None
    st, _ = se.run_capital(tr, 'XAUUSD', CAP['initial_capital'], CAP['risk_pct'], CAP['compounding'])
    return st, tr


def gross_loss_pip(tr):
    return float(-tr.loc[tr['pnl_pip'] <= 0, 'pnl_pip'].sum())


def apply_filter(df, base_sig, feats, key, op, thr):
    """فیلتر روی سیگنال (نه بعد از معامله): فقط کندل‌هایی که شرط را پاس کنند سیگنال می‌مانند."""
    f = feats[key]
    mask = np.zeros(len(df), bool)
    valid = ~np.isnan(f)
    if op == '>=':
        mask[valid] = f[valid] >= thr
    elif op == '<=':
        mask[valid] = f[valid] <= thr
    elif op == '>':
        mask[valid] = f[valid] > thr
    elif op == '<':
        mask[valid] = f[valid] < thr
    return base_sig & mask


def main():
    print("=" * 80)
    print("s137 — فیلترِ کاهشِ سیگنالِ غلط روی لایهٔ SHORT (MA-Confluence)")
    print("=" * 80)
    df = load()
    n = len(df)
    sig, mid = short_signal(df)
    feats = build_features(df)

    # ── baseline (بازتولیدِ رکورد) ──
    st_b, tr_b = run(df, sig, EXIT)
    print(f"\nBaselineِ SHORT (رکورد، خروجِ SL70/TP800/mh48/be6/trail6):")
    print(f"  trades={len(tr_b)}  net=${st_b['net_profit']:,.0f}  WR={st_b['win_rate']:.1f}%"
          f"  PF={st_b['profit_factor']:.2f}  grossLoss={gross_loss_pip(tr_b):,.0f}pip")

    # ── امضای ضرر: میانگینِ feature در بردها vs باخت‌ها (لحظهٔ سیگنال) ──
    sb = tr_b['signal_bar'].values.astype(int)
    win = tr_b['pnl_pip'].values > 0
    print(f"\nامضای ضرر (میانگینِ feature در لحظهٔ سیگنال):")
    print(f"  {'feature':>14} {'برد':>10} {'باخت':>10}  جهتِ حذفِ باخت")
    sig_report = {}
    for k in ['brk_strength', 'adx14', 'dist_ema200', 'rsi14', 'atr_pct', 'slope_mid']:
        fv = feats[k][sb]
        mw = np.nanmean(fv[win]); ml = np.nanmean(fv[~win])
        arrow = "باخت‌ها کمترند⇒حذفِ کم‌ها" if ml < mw else "باخت‌ها بیشترند⇒حذفِ زیادها"
        print(f"  {k:>14} {mw:>10.3f} {ml:>10.3f}  {arrow}")
        sig_report[k] = dict(win=float(mw), loss=float(ml))

    # ── نامزدهای فیلترِ تک‌شرطیِ قابل‌تفسیر ──
    # جهت‌ها بر اساسِ منطق: شکستِ قوی‌تر بهتر، رژیمِ نزولی‌تر (slope منفی‌تر) بهتر،
    # ADX بالاتر (روندِ واقعی) بهتر، کش‌آمدگیِ افراطی زیرِ EMA200 بدتر.
    candidates = [
        ('brk_strength', '>=', 0.10), ('brk_strength', '>=', 0.20), ('brk_strength', '>=', 0.30),
        ('adx14', '>=', 15.0), ('adx14', '>=', 20.0), ('adx14', '>=', 25.0),
        ('slope_mid', '<=', 0.0), ('slope_mid', '<=', -0.2), ('slope_mid', '<=', -0.5),
        ('dist_ema200', '>=', -3.0), ('dist_ema200', '>=', -2.0),
        ('rsi14', '<=', 55.0), ('rsi14', '<=', 50.0), ('rsi14', '>=', 30.0),
        ('atr_pct', '<=', 0.5), ('atr_pct', '<=', 0.4),
    ]

    half = n // 2
    df_h1 = df.iloc[:half].reset_index(drop=True)
    df_h2 = df.iloc[half:].reset_index(drop=True)
    sig_h1, _ = short_signal(df_h1); feats_h1 = build_features(df_h1)
    sig_h2, _ = short_signal(df_h2); feats_h2 = build_features(df_h2)

    base_gl = gross_loss_pip(tr_b)
    print(f"\n{'='*80}\nجاروبِ فیلترهای تک‌شرطی (گیتِ ضدِ overfit: هر دو نیمه مثبت + Δ سود ≥ 0):")
    print(f"  {'filter':>26} {'trades':>7} {'net':>10} {'Δnet':>9} {'grossLoss':>10} {'h1':>9} {'h2':>9}  حکم")
    rows = []
    for key, op, thr in candidates:
        fsig = apply_filter(df, sig, feats, key, op, thr)
        st, tr = run(df, fsig, EXIT)
        if st is None:
            continue
        fsig1 = apply_filter(df_h1, sig_h1, feats_h1, key, op, thr)
        fsig2 = apply_filter(df_h2, sig_h2, feats_h2, key, op, thr)
        st1, _ = run(df_h1, fsig1, EXIT)
        st2, _ = run(df_h2, fsig2, EXIT)
        net = st['net_profit']; dnet = net - st_b['net_profit']
        gl = gross_loss_pip(tr)
        h1 = st1['net_profit'] if st1 else 0.0
        h2 = st2['net_profit'] if st2 else 0.0
        both_pos = h1 > 0 and h2 > 0
        # قانونِ شمارهٔ ۱: سودِ خالص باید ≥ baseline باشد (و ضرر کم شود)
        ok = both_pos and dnet >= 0 and gl < base_gl
        flag = "✅" if ok else "—"
        label = f"{key}{op}{thr}"
        print(f"  {label:>26} {len(tr):>7} ${net:>9,.0f} ${dnet:>+8,.0f} {gl:>10,.0f} "
              f"${h1:>8,.0f} ${h2:>8,.0f}  {flag}")
        rows.append(dict(filter=label, key=key, op=op, thr=thr, trades=int(len(tr)),
                         net=float(net), dnet=float(dnet), gross_loss=float(gl),
                         h1=float(h1), h2=float(h2), both_pos=bool(both_pos), ok=bool(ok)))

    # ── انتخابِ برنده: بیشترین سودِ خالص در میانِ پاس‌شده‌ها ──
    passed = [r for r in rows if r['ok']]
    out = dict(baseline_net=float(st_b['net_profit']), baseline_gross_loss=float(base_gl),
               baseline_trades=int(len(tr_b)), loss_signature=sig_report, sweep=rows)

    if not passed:
        print("\n⚠️ هیچ فیلترِ تک‌شرطی هر سه گیت را پاس نکرد. رکورد بدون تغییر می‌ماند.")
        out['verdict'] = False
    else:
        passed.sort(key=lambda r: -r['net'])
        best = passed[0]
        print(f"\n{'='*80}\n🏆 برندهٔ تک‌شرطی: {best['filter']}")
        print(f"  net=${best['net']:,.0f}  Δ=${best['dnet']:+,.0f}  grossLoss={best['gross_loss']:,.0f}pip"
              f"  (baseline {base_gl:,.0f})")

        # ── walk-forward چهار پنجره روی برنده ──
        key, op, thr = best['key'], best['op'], best['thr']
        print(f"\n  Walk-forward چهار پنجره (برنده):")
        edges = [0, n // 4, n // 2, 3 * n // 4, n]; wf = []; all_pos = True
        for i in range(4):
            seg = df.iloc[edges[i]:edges[i + 1]].reset_index(drop=True)
            s, _ = short_signal(seg); ff = build_features(seg)
            fs = apply_filter(seg, s, ff, key, op, thr)
            stw, _ = run(seg, fs, EXIT)
            net = stw['net_profit'] if stw else 0.0
            wf.append(float(net))
            if net <= 0: all_pos = False
            print(f"    W{i+1}: ${net:>9,.0f}")

        # ── robustness: آیا آستانه‌های همسایه هم بهبود می‌دهند؟ ──
        neigh = [r for r in rows if r['key'] == key]
        n_improve = sum(1 for r in neigh if r['dnet'] >= 0 and r['gross_loss'] < base_gl)
        print(f"\n  Robustness: از {len(neigh)} آستانهٔ همسایهٔ همین feature، "
              f"{n_improve} تا هم‌زمان سود↑ و ضرر↓ (پارامتر-پایدار: {'✅' if n_improve>=2 else '⚠️'}).")

        new_short = best['net']
        new_total = RECORD_REST + new_short
        print(f"\n  رکوردِ جدیدِ کل = بقیه ${RECORD_REST:,.0f} + SHORT ${new_short:,.0f} = ${new_total:,.0f}")
        print(f"  Δ نسبت به رکوردِ ${RECORD_TOTAL:,.0f} = ${new_total-RECORD_TOTAL:+,.0f}")
        verdict = all_pos and new_total > RECORD_TOTAL and n_improve >= 2
        print(f"\n  {'✅✅ رکوردِ جدید تأیید شد!' if verdict else '⚠️ گیتِ نهایی ناموفق'}")
        out.update(best_filter=best, wf=wf, wf_all_pos=bool(all_pos),
                   robust_neighbors=int(n_improve), new_short=float(new_short),
                   new_total=float(new_total), verdict=bool(verdict))

    with open(os.path.join(RESULTS, '_s137_short_loss_filter.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nخروجی ذخیره شد: results/_s137_short_loss_filter.json")


if __name__ == '__main__':
    main()
