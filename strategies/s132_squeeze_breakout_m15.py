"""
S132 — «انفجارِ نوسان پس از فشردگیِ بولینگر» (Bollinger Squeeze → Expansion Breakout)
======================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate (WR).**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز XAUUSD + EURUSD. WR فقط عددِ گزارشی است.
> محصولِ نهایی یک سایتِ دستیارِ تصمیمِ ۴-حالته است؛ این فایل یک «لایهٔ سیگنالِ کاندید»
> را می‌سازد و می‌سنجد که آیا به‌عنوانِ جریانِ ناهمبستهٔ جدید به پرتفوی افزوده شود.

--------------------------------------------------------------------------------
انگیزهٔ علمی (چرا این ایده و چرا تا حالا تست نشده؟)
--------------------------------------------------------------------------------
پرتفویِ رکوردِ فعلی (+$101,259) از ۵ لایه ساخته شده که همگی ماشهٔ ورودشان یکی از
این‌هاست: (۱) عبورِ MACD (ScalpV2 M5)، (۲) EMA20>EMA100 ∧ RSI<35 پولبک (S67/S81)،
(۳) عبور از میانهٔ سه MA (SHORT M15)، (۴) drift سشن (EURUSD). **هیچ لایه‌ای از
«فشردگیِ نوسان» (Volatility Compression) به‌عنوانِ ماشه استفاده نمی‌کند.**

مفهومِ ریاضی (کلاسیکِ Bollinger/Keltner Squeeze — John Bollinger, «Bollinger on
Bollinger Bands»؛ و TTM Squeeze از John Carter, «Mastering the Trade»):
  • BandWidth = (BB_upper − BB_lower) / BB_mid  = ۴·σ/میانگین  (σ = انحرافِ معیارِ close).
  • وقتی BandWidth به یک «کفِ تاریخیِ غلتان» می‌رسد، بازار در حالتِ کم‌نوسان/تراکم است.
  • نظریهٔ «فنرِ فشرده»: دوره‌های کم‌نوسان به دوره‌های پرنوسان ختم می‌شوند
    (volatility clustering — Mandelbrot/Engle-ARCH). یعنی فشردگی، «انرژیِ ذخیره‌شده» است.
  • جهتِ انفجار را نمی‌شناسیم؛ ولی طلا یک داراییِ با بایاسِ صعودیِ ساختاری است (L53).
    پس فقط در آپ‌ترند و فقط breakoutِ صعودی (شکستِ سقفِ فشردگی) را long می‌گیریم.

فرضیهٔ آزمون‌پذیر:
  «وقتی BandWidth در پایین‌ترین صدکِ P کندلِ اخیر است (فشردگی) و قیمت سقفِ بازهٔ
   فشردگی را رو به بالا می‌شکند، در آپ‌ترندِ M15، یک حرکتِ صعودیِ ادامه‌دار با
   انتظارِ ریاضیِ مثبت رخ می‌دهد.»

--------------------------------------------------------------------------------
متدولوژی (کنترلِ علمیِ سیب‌به‌سیب — همان زیرساختِ رکورد)
--------------------------------------------------------------------------------
• داده: data/XAUUSD_M15.csv — دقیقاً ۱۵۰٬۰۰۰ کندلِ واقعیِ M15 (که کاربر داد).
• زیرساختِ اجرا: بازاستفادهٔ عینی از `strategies.s91_scalp_signal_exit`:
    - paper_broker  : ورود در open کندلِ بعدِ سیگنال، خروجِ per-bar، همه forward-safe.
    - make_hidden_exit(TP,SL): خروجِ «هدفِ پنهان» روی close (منطبق با سایت).
    - هزینهٔ واقعیِ حساب: طلا اسپرد ۴pip + اسلیپیج ۰.۵pip هر طرف (داخلِ paper_broker).
• برای اینکه فقط اثرِ *ماشهٔ فشردگی* سنجیده شود، خروج با جارویِ کوچکِ (TP,SL) بهترین
  آستانهٔ خودش را می‌گیرد (نه آستانهٔ منجمدِ M5).
• گیت‌های ضدِ overfit (همه باید سبز شوند تا لایه «قابل‌قبول» باشد):
    (۱) سودِ خالصِ کل مثبت و معنادار،
    (۲) هر دو نیمهٔ داده مثبت،
    (۳) هر ۴ پنجرهٔ walk-forward مثبت،
    (۴) [در فایلِ جدا s133] همبستگیِ روزانه با پرتفویِ موجود پایین (جریانِ ناهمبسته).
• معیارِ نهایی: فقط سودِ خالص (قانونِ شمارهٔ ۱).

توجه: فقط BUY/long (بایاسِ صعودیِ طلا، L53). M15 ⇒ max_hold متناسب (۹۶ کندل = ۲۴ ساعت).
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strategies.s91_scalp_signal_exit import paper_broker, ema, rsi, atr
from strategies.s94_scalp_hidden_target import make_hidden_exit

DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(ROOT, 'results')
PIP = 0.1  # برای طلا، ۱pip = ۰.۱۰$ (منطبق با s91)
MAX_HOLD_M15 = 96  # ۹۶ کندلِ M15 = ۲۴ ساعت


# ==============================================================================
# اندیکاتورهای اختصاصیِ ماشهٔ فشردگی
# ==============================================================================
def bollinger_bandwidth(c, period=20, k=2.0):
    """BandWidth = (upper - lower) / mid = 2*k*std/mid. بردارِ هم‌طولِ c."""
    n = len(c)
    bw = np.full(n, np.nan)
    mid = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = c[i - period + 1:i + 1]
        m = window.mean()
        s = window.std(ddof=0)
        mid[i] = m
        upper[i] = m + k * s
        bw[i] = (2.0 * k * s) / m if m != 0 else np.nan
    return bw, mid, upper


def rolling_min_percentile(x, lookback):
    """آیا x[i] در پایین‌ترین بخشِ lookback کندلِ اخیر است؟ برمی‌گرداند صدکِ غلتانِ x[i]."""
    n = len(x)
    pct = np.full(n, np.nan)
    for i in range(lookback, n):
        window = x[i - lookback:i + 1]
        w = window[~np.isnan(window)]
        if len(w) < 5 or np.isnan(x[i]):
            continue
        pct[i] = (w <= x[i]).mean()  # ۰ = کمترین، ۱ = بیشترین
    return pct


# ==============================================================================
# ماشهٔ ورودِ S132: فشردگی → شکستِ صعودی در آپ‌ترند
# ==============================================================================
def build_entries_squeeze(df, bb_period=20, bb_k=2.0, sqz_lookback=100,
                          sqz_pct=0.15, breakout_lookback=10, trend_gate=True):
    """
    شرایطِ ورود (long) در کندلِ i (سیگنال روی close[i]، ورود open[i+1]):
      1. فشردگی: BandWidth[i-1] در پایین‌ترین `sqz_pct` صدکِ `sqz_lookback` کندلِ اخیر
         (یعنی درست پیش از کندلِ فعلی، بازار فشرده بوده — «فنرِ فشرده»).
      2. شکستِ صعودی: close[i] از بالاترین high در `breakout_lookback` کندلِ گذشته
         (i-breakout_lookback .. i-1) عبور کند ⇒ انفجارِ صعودی از تراکم.
      3. گیتِ روند: EMA50[i] > EMA200[i] (بایاسِ صعودی؛ فقط انفجارِ هم‌سو با روند).
    """
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    e50 = ema(c, 50)
    e200 = ema(c, 200)
    bw, mid, upper = bollinger_bandwidth(c, bb_period, bb_k)
    bw_pct = rolling_min_percentile(bw, sqz_lookback)

    out = []
    n = len(df)
    start = max(bb_period + sqz_lookback, 200, breakout_lookback) + 1
    for i in range(start, n - 1):
        # ۱) فشردگی درست پیش از این کندل
        if np.isnan(bw_pct[i - 1]) or bw_pct[i - 1] > sqz_pct:
            continue
        # ۲) شکستِ صعودی از سقفِ اخیر
        prior_high = h[i - breakout_lookback:i].max()
        if not (c[i] > prior_high):
            continue
        # ۳) گیتِ روندِ صعودی
        if trend_gate and not (e50[i] > e200[i]):
            continue
        out.append((i, 'long'))
    return out


# ==============================================================================
# آمار و ابزارِ ارزیابی
# ==============================================================================
def stats(tr):
    if tr is None or len(tr) == 0:
        return dict(n=0, net=0.0, pf=0.0, wr=0.0, avg=0.0)
    pnl = tr['net_usd'].values if 'net_usd' in tr.columns else tr['pnl_pip'].values * PIP
    wins = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    pf = wins / losses if losses > 0 else float('inf')
    return dict(
        n=len(tr),
        net=float(pnl.sum()),
        pf=float(pf),
        wr=float((pnl > 0).mean() * 100),
        avg=float(pnl.mean()),
    )


def eval_config(df, entries, tp, sl, trendbreak=True):
    exit_fn = make_hidden_exit(tp, sl, use_trend_break=trendbreak)
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=400.0, max_hold=MAX_HOLD_M15)
    return stats(tr), tr


def half_split(df, entries, tp, sl, trendbreak=True):
    n = len(df); half = n // 2
    exit_fn = make_hidden_exit(tp, sl, use_trend_break=trendbreak)
    e1 = [(i, s) for (i, s) in entries if i < half - 1]
    df1 = df.iloc[:half].reset_index(drop=True)
    s1 = stats(paper_broker(df1, e1, exit_fn, catastrophic_sl_pip=400.0, max_hold=MAX_HOLD_M15))
    e2 = [(i - half, s) for (i, s) in entries if i >= half]
    df2 = df.iloc[half:].reset_index(drop=True)
    s2 = stats(paper_broker(df2, e2, exit_fn, catastrophic_sl_pip=400.0, max_hold=MAX_HOLD_M15))
    return s1, s2


def walk_forward(df, entries, tp, sl, trendbreak=True, k=4):
    """k پنجرهٔ متوالی؛ سودِ خالصِ هر پنجره."""
    n = len(df)
    bounds = [int(n * j / k) for j in range(k + 1)]
    exit_fn = make_hidden_exit(tp, sl, use_trend_break=trendbreak)
    nets = []
    for w in range(k):
        lo, hi = bounds[w], bounds[w + 1]
        ew = [(i - lo, s) for (i, s) in entries if lo <= i < hi - 1]
        dfw = df.iloc[lo:hi].reset_index(drop=True)
        nets.append(stats(paper_broker(dfw, ew, exit_fn, catastrophic_sl_pip=400.0,
                                       max_hold=MAX_HOLD_M15))['net'])
    return nets


def main():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    print("=" * 90)
    print("S132 — انفجارِ نوسان پس از فشردگیِ بولینگر (Squeeze→Breakout) روی XAUUSD M15")
    print("=" * 90)
    print(f"داده: {len(df):,} کندلِ M15  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
    print("معیار: فقط سودِ خالص (قانونِ #۱). هزینهٔ واقعی: اسپرد ۴pip + اسلیپ ۰.۵pip.\n")

    # مرحلهٔ ۱: کاوشِ حساسیت به آستانهٔ فشردگی (چند sqz_pct) با یک خروجِ پیش‌فرض
    print("── مرحلهٔ ۱: حساسیت به شدتِ فشردگی (sqz_pct) و طولِ شکست (breakout_lookback) ──")
    print(f"{'sqz_pct':>8} {'brkLB':>6} {'n':>5} | (با TP150/SL90 پیش‌فرض) {'net':>10} {'PF':>5} {'WR':>5}")
    print("-" * 78)
    best_trig = None
    for sqz_pct in [0.10, 0.15, 0.20, 0.25]:
        for blb in [6, 10, 15]:
            ent = build_entries_squeeze(df, sqz_pct=sqz_pct, breakout_lookback=blb)
            s, _ = eval_config(df, ent, 150, 90)
            print(f"{sqz_pct:>8.2f} {blb:>6} {s['n']:>5} | "
                  f"{'':>22}{s['net']:>10,.0f} {s['pf']:>5.2f} {s['wr']:>5.1f}")
            if s['n'] >= 30 and (best_trig is None or s['net'] > best_trig[2]):
                best_trig = (sqz_pct, blb, s['net'])

    if best_trig is None:
        print("\n⚠️ هیچ پیکربندی‌ای ≥۳۰ معامله نداد. ماشه بیش‌ازحد نادر است.")
        return
    sqz_pct, blb, _ = best_trig
    print(f"\n→ بهترین ماشه (بیشترین net با n≥۳۰): sqz_pct={sqz_pct}, breakout_lookback={blb}")

    # مرحلهٔ ۲: جارویِ خروجِ «هدفِ پنهان» روی بهترین ماشه
    print("\n── مرحلهٔ ۲: جارویِ خروج (TP,SL) روی بهترین ماشه + گیت‌های ضدِ overfit ──")
    ent = build_entries_squeeze(df, sqz_pct=sqz_pct, breakout_lookback=blb)
    print(f"تعدادِ ورودها: {len(ent)}")
    print(f"{'TP':>4} {'SL':>4} {'tb':>3} | {'net_all':>10} {'PF':>5} {'WR':>5} {'n':>4} | "
          f"{'½1':>9} {'½2':>9} {'WFمثبت':>7} {'both':>5}")
    print("-" * 90)

    tp_grid = [120, 150, 200, 250, 300]
    sl_grid = [60, 90, 120]
    candidates = []
    for tb in [True, False]:
        for tp in tp_grid:
            for sl in sl_grid:
                s_all, _ = eval_config(df, ent, tp, sl, trendbreak=tb)
                if s_all['n'] < 30:
                    continue
                s1, s2 = half_split(df, ent, tp, sl, trendbreak=tb)
                wf = walk_forward(df, ent, tp, sl, trendbreak=tb, k=4)
                wf_pos = sum(1 for x in wf if x > 0)
                both = (s1['net'] > 0 and s2['net'] > 0)
                flag = "✅" if (both and wf_pos == 4 and s_all['net'] > 0) else ""
                print(f"{tp:>4} {sl:>4} {str(tb)[0]:>3} | {s_all['net']:>10,.0f} "
                      f"{s_all['pf']:>5.2f} {s_all['wr']:>5.1f} {s_all['n']:>4} | "
                      f"{s1['net']:>9,.0f} {s2['net']:>9,.0f} {wf_pos:>7} {str(both):>5} {flag}")
                candidates.append(dict(tp=tp, sl=sl, tb=tb, **{f"net": s_all['net']},
                                       pf=s_all['pf'], wr=s_all['wr'], n=s_all['n'],
                                       half1=s1['net'], half2=s2['net'],
                                       wf=wf, wf_pos=wf_pos, both=both))

    # انتخابِ برنده: بیشترین سودِ خالص با همهٔ گیت‌های ضدِ overfit سبز
    clean = [c for c in candidates if c['both'] and c['wf_pos'] == 4 and c['net'] > 0]
    print("\n" + "=" * 90)
    if clean:
        win = max(clean, key=lambda c: c['net'])
        print(f"🏆 برندهٔ ضدِ overfit: TP={win['tp']} SL={win['sl']} trendbreak={win['tb']}")
        print(f"   سودِ خالص = +${win['net']:,.0f} | PF {win['pf']:.2f} | WR {win['wr']:.1f}% "
              f"(فقط گزارشی) | n={win['n']}")
        print(f"   نیمهٔ۱ +${win['half1']:,.0f} | نیمهٔ۲ +${win['half2']:,.0f} | "
              f"WF {win['wf']} (هر ۴ مثبت)")
    else:
        # هیچ پیکربندیِ کاملاً تمیزی نبود — بهترین از نظرِ net را با هشدار گزارش کن
        win = max(candidates, key=lambda c: c['net']) if candidates else None
        if win:
            print(f"⚠️ هیچ پیکربندی همهٔ گیت‌ها را سبز نکرد. بهترین از نظرِ net (مشروط):")
            print(f"   TP={win['tp']} SL={win['sl']} tb={win['tb']} → +${win['net']:,.0f}, "
                  f"both={win['both']}, WFمثبت={win['wf_pos']}/4")
        else:
            print("❌ هیچ کاندیدِ معتبری تولید نشد.")

    out = dict(trigger=dict(sqz_pct=sqz_pct, breakout_lookback=blb),
               n_entries=len(ent),
               candidates=candidates,
               winner=win if (clean or candidates) else None,
               clean_exists=bool(clean))
    with open(os.path.join(RESULTS, '_s132_squeeze.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("\nخلاصه در results/_s132_squeeze.json ذخیره شد.")
    print("قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD (نه WR).")


if __name__ == '__main__':
    main()
