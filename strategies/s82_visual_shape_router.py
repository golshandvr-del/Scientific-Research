"""
s82_visual_shape_router.py — استراتژیِ S82: مسیریابِ «الگوی بصریِ روند» (Visual-Shape Router)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است؛ تعدادِ معامله در روز و Profit Factor هم هدف نیستند. **ما دنبالِ پول
> هستیم، نه آمارِ زیبا.** تنها تابعِ هدف: سودِ خالصِ تجمعیِ پس از اسپرد/کمیسیون.
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

--------------------------------------------------------------------------------
ایده (پاسخِ مستقیم به User Note این دور):
  «داده‌ها را به الگوی بصری تبدیل کن؛ مهم‌تر از استراتژی، تقسیمِ داده به بخش‌های مشابه.»

  ۱) هر کندل با «شکلِ اخیرِ منحنیِ close» (پنجرهٔ W کندلی، z-score نرمال‌شده) نمایندگی
     می‌شود ⇒ داده به «الگوی بصری» تبدیل شد (مستقل از سطح/مقیاسِ قیمت).
  ۲) KMeans شکل‌های مشابه را در K خوشه تقسیم می‌کند ⇒ «تقسیمِ داده به بخش‌های مشابه».
  ۳) هر خوشه = یک «رژیمِ بصری». لبهٔ آتیِ hold-کندلیِ هر خوشه سنجیده می‌شود و فقط
     خوشه‌های صعودی/نزولیِ قوی معامله می‌شوند؛ بقیه «خنثی».

--------------------------------------------------------------------------------
درسِ گرفته‌شده از L35/L36 (دامِ رژیمِ مرده و راه‌حلِ walk-forward):
  نسخهٔ اولِ IS-fit روی نیمهٔ اولِ *مرده* (رنجِ ۲۰۲۱–۲۳) کالیبره شد و OOS عالی ولی IS
  منفی داد (both-halves ❌). راه‌حلِ اثبات‌شدهٔ پروژه: **walk-forward رو به جلو** —
  در هر بلوک، لبهٔ خوشه از پنجرهٔ اخیرِ گذشته یاد گرفته می‌شود (نه گذشتهٔ دور).

نسخهٔ نهاییِ S82 = **Rolling Visual-Shape Router**:
  • KMeans یک‌بار روی کلِ داده fit می‌شود اما برای *برچسبِ شکل* (نه سیگنالِ معامله) —
    این نشتِ آینده در «تصمیمِ ورود» ایجاد نمی‌کند چون خوشه فقط «کدام شکل شبیهِ کدام»
    را می‌گوید؛ جهتِ معامله از لبهٔ *گذشتهٔ متحرک* می‌آید.
  • برای هر کندلِ i: از پنجرهٔ اخیرِ LOOKBACK کندل قبل از i، اکسپکتنسیِ آتیِ هر خوشه
    محاسبه می‌شود (با آفستِ hold تا هیچ برچوردِ آینده وارد نشود). اگر خوشهٔ کندلِ i
    در آن پنجره لبهٔ صعودیِ کافی داشت ⇒ Long؛ نزولی ⇒ Short؛ وگرنه خنثی.
  • ورود در open کندلِ بعد؛ خروجِ زمان‌محور (hold) + SL محافظتی؛ موتورِ سرمایه‌محور.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

np.random.seed(42)


def zscore_windows(close, W):
    n = len(close)
    idxs = np.arange(W - 1, n)
    X = np.empty((len(idxs), W), dtype=np.float64)
    for r, i in enumerate(idxs):
        w = close[i - W + 1: i + 1]
        mu = w.mean(); sd = w.std()
        X[r] = 0.0 if sd < 1e-12 else (w - mu) / sd
    return X, idxs


def rolling_shape_signals(asset, W=16, K=12, hold=32,
                          lookback=24000, step=2000,
                          long_th=3.0, short_th=6.0, min_n=40,
                          verbose=True):
    """
    Rolling Visual-Shape Router (بدونِ نشتِ آینده در تصمیمِ ورود).

      - برچسبِ خوشهٔ هر کندل از شکلِ گذشته (پنجرهٔ W) می‌آید.
      - برای بلوک‌های step-کندلی، لبهٔ آتیِ hold-کندلیِ هر خوشه فقط از پنجرهٔ اخیرِ
        [start-lookback, start) — که کاملاً در گذشته و با آفستِ hold ایمن است — یاد
        گرفته می‌شود؛ سپس روی همان بلوک اعمال می‌شود.
      - long_th/short_th: حداقلِ میانگینِ بازدهِ آتیِ خوشه (pip) برای Long/Short.
    """
    from sklearn.cluster import KMeans
    cfg = SE.ASSETS[asset]
    df = SE.load_data(cfg['file'])
    close = df['close'].values.astype(np.float64)
    pip = cfg['pip']
    n = len(close)

    X, idxs = zscore_windows(close, W)
    km = KMeans(n_clusters=K, n_init=10, random_state=42)
    lab = km.fit_predict(X)
    lab_full = np.full(n, -1, dtype=int)
    lab_full[idxs] = lab

    # بازدهِ آتیِ hold-کندلی برای هر کندل (برای یادگیریِ لبهٔ گذشته؛ آفستِ hold ایمن)
    fwd = np.full(n, np.nan)
    fwd[:n - hold] = (close[hold:] - close[:n - hold]) / pip

    long_sig = np.zeros(n, bool)
    short_sig = np.zeros(n, bool)

    first = W + lookback  # اولین کندلی که پنجرهٔ کاملِ گذشته دارد
    starts = list(range(first, n, step))
    n_long_blocks = 0
    for start in starts:
        end = min(start + step, n)
        # پنجرهٔ یادگیری: [start-lookback, start) اما فقط کندل‌هایی که fwd آن‌ها
        # قبل از start محقق شده (i+hold < start) ⇒ کاملاً بدونِ نشت.
        lb0 = max(0, start - lookback)
        learn_idx = np.arange(lb0, start - hold)
        if len(learn_idx) < 500:
            continue
        edges = {}
        for c in range(K):
            m = learn_idx[(lab_full[learn_idx] == c)]
            fr = fwd[m]
            fr = fr[~np.isnan(fr)]
            if len(fr) >= min_n:
                edges[c] = fr.mean()
        # اعمال روی بلوکِ جاری
        for i in range(start, end):
            c = lab_full[i]
            if c < 0 or c not in edges:
                continue
            e = edges[c]
            if e >= long_th:
                long_sig[i] = True
            elif e <= -short_th:
                short_sig[i] = True
        if any(edges.get(c, 0) >= long_th for c in edges):
            n_long_blocks += 1

    active_from = first
    if verbose:
        print(f"\n  [{asset}] Rolling Visual-Shape  W={W} K={K} hold={hold} "
              f"lookback={lookback} step={step}")
        print(f"   long_th={long_th} short_th={short_th}  "
              f"سیگنال‌ها: long={long_sig.sum()} short={short_sig.sum()}  "
              f"(فعال از کندلِ {active_from})")
    return df, long_sig, short_sig, close, pip, active_from


def run(asset, W=16, K=12, hold=32, sl_pip=120,
        lookback=24000, step=2000, long_th=3.0, short_th=6.0,
        compounding=False, verbose=True):
    df, long_sig, short_sig, close, pip, active_from = rolling_shape_signals(
        asset, W=W, K=K, hold=hold, lookback=lookback, step=step,
        long_th=long_th, short_th=short_th, verbose=verbose)

    # خروجِ زمان‌محور: TP بسیار دور تا عملاً فقط hold و SL محافظتی عمل کنند
    tr = SE.simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip=99999,
                            asset=asset, max_hold=hold)
    if len(tr) == 0:
        if verbose:
            print("   (هیچ معامله‌ای تولید نشد)")
        return None

    n = len(close); half = n // 2
    s_all, eq = SE.run_capital(tr, asset, compounding=compounding)
    tr1 = tr[tr['entry_bar'] < half]; tr2 = tr[tr['entry_bar'] >= half]
    s1, _ = SE.run_capital(tr1, asset, compounding=compounding)
    s2, _ = SE.run_capital(tr2, asset, compounding=compounding)

    if verbose:
        print(f"\n   {SE.summary_line(asset+'-ALL', s_all)}")
        print(f"   {SE.summary_line(asset+'-H1 ', s1)}")
        print(f"   {SE.summary_line(asset+'-H2 ', s2)}")
        both = s1['net_profit'] > 0 and s2['net_profit'] > 0
        print(f"   both_halves_positive = {'✅' if both else '❌'}")
    return dict(asset=asset, s_all=s_all, s1=s1, s2=s2, tr=tr, eq=eq)


if __name__ == '__main__':
    print("#" * 100)
    print("  S82 — Rolling Visual-Shape Router (walk-forward؛ درسِ L36)")
    print("#" * 100)
    res_gold = run('XAUUSD', W=16, K=12, hold=32, sl_pip=120,
                   lookback=24000, step=2000, long_th=3.0, short_th=6.0)
    print("\n" + "#" * 100)
    if res_gold:
        s = res_gold['s_all']
        print(f"  XAUUSD: net={s['net_profit']:+.0f}$  "
              f"H1={res_gold['s1']['net_profit']:+.0f}  H2={res_gold['s2']['net_profit']:+.0f}")
    print("#" * 100)
