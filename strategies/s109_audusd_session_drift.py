"""
s109_audusd_session_drift.py — کشفِ ساختارِ سشنیِ AUDUSD (جریانِ کاملاً غیرِهم‌بسته)
================================================================================
> قانونِ شمارهٔ ۱ پروژه: معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است، نه Win-Rate.
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD. اما AUDUSD یک داراییِ مستقل در
> ساختارِ سایت است؛ اگر لبهٔ سوددهِ پایدار داشته باشد، جریانِ کاملاً غیرِهم‌بسته‌ای
> می‌سازد (نه طلا، نه یورو) — دقیقاً پاسخِ «گلوگاهِ نبودِ جریانِ غیرِهم‌بسته» (L50).
> WR فقط گزارشی است.

منشأ (پاسخِ روش‌شناختیِ سوالِ فلسفی):
  متدولوژیِ نسبت‌دهیِ s104 می‌گوید «هر آشکارساز به یک رژیمِ خاص کوک است». روی EURUSD،
  آشکارسازِ «ساعتِ روز» بهترین نتیجه را داد (S73: drift ساعتِ ۰ UTC = +۷.۳k$). AUDUSD
  یک ارزِ کامودیتی/ریسک با سشنِ آسیاییِ متفاوت است ⇒ ساختارِ ساعتیِ متفاوتی دارد که
  با هیچ لایهٔ فعلی هم‌بسته نیست. بدونِ تحمیلِ منطقِ طلا/یورو، صرفاً از دلِ داده کشف
  می‌کنیم کدام ساعت‌ها drift پایدار دارند.

روش (کاملاً forward-safe — Time-of-Day):
  ۱) برای هر ساعتِ UTC، بازدهِ آتیِ h کندل (ورود در open کندلِ بعد) را می‌سنجیم:
     میانگین، t-stat، و **پایداری در ۴ چارَکِ زمانی** (out-of-sample).
  ۲) ساعتِ کاندید = t-stat قوی + هم‌علامت در هر ۴ چارَک.
  ۳) روی کاندیدها استراتژی می‌سازیم (Long یا Short طبقِ علامت) با SL/TP ثابتِ pip،
     فیلترِ pullback، و خروجِ زمان‌محور — سپس سودِ خالصِ سرمایه-محور + both-halves.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import scalp_engine as se
import warnings; warnings.filterwarnings('ignore')

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'AUDUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')
PIP = 0.0001


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['dt'].dt.hour
    return df.reset_index(drop=True)


def main():
    print("=" * 80)
    print("s109 — کشفِ ساختارِ سشنیِ AUDUSD (جریانِ کاملاً غیرِهم‌بسته)")
    print("=" * 80)
    df = load()
    n = len(df)
    print(f"داده: {n:,} کندل AUDUSD M15")
    o = df['open'].values; c = df['close'].values

    # --- فاز کشف: drift ساعتی و پایداری در ۴ چارَک ---
    def fwd_ret_pip(h):
        # ورود در open[i+1]، خروج در close[i+h]  (shift-safe)
        entry = np.r_[o[1:], np.nan]
        exit_ = np.r_[c[h:], [np.nan]*h]
        return (exit_ - entry) / PIP

    print("\nساعت | افق | میانگین(pip) | t-stat | پایدار در ۴ چارَک؟")
    print("-" * 60)
    q = n // 4
    candidates = []
    for h in [4, 6, 8]:
        fr = fwd_ret_pip(h)
        for hr in range(24):
            mask = (df['hour'].values == hr) & np.isfinite(fr)
            vals = fr[mask]
            if len(vals) < 200:
                continue
            m = vals.mean(); sd = vals.std()
            t = m / (sd / np.sqrt(len(vals))) if sd > 0 else 0
            if abs(t) < 4:
                continue
            # پایداری در ۴ چارَک
            signs = []
            for k in range(4):
                a, b = k*q, (k+1)*q if k < 3 else n
                mk = mask.copy(); mk[:a] = False; mk[b:] = False
                vv = fr[mk]
                if len(vv) > 30:
                    signs.append(np.sign(vv.mean()))
            stable = len(signs) == 4 and len(set(signs)) == 1
            flag = "✅" if stable else "—"
            if abs(t) >= 5 or stable:
                print(f"{hr:>4} | {h:>3} | {m:>12.3f} | {t:>6.2f} | {flag}")
            if stable and abs(t) >= 4:
                candidates.append((hr, h, m, t))

    # --- فاز استراتژی: روی کاندیدهای پایدار ---
    print("\n" + "=" * 80)
    print("ساختِ استراتژی روی ساعت‌های کاندیدِ پایدار")
    print("=" * 80)
    if not candidates:
        print("هیچ ساعتِ پایداری با t>=4 یافت نشد ⇒ AUDUSD ساختارِ سشنیِ سوددهِ قوی ندارد.")
        with open(os.path.join(RESULTS, '_s109_audusd.json'), 'w') as fj:
            json.dump(dict(candidates=[], best=None), fj, ensure_ascii=False, indent=2, default=float)
        return

    # برای هر کاندید، استراتژی بساز و سودِ خالص را بسنج
    hours_done = set()
    results = []
    for hr, h, m, t in candidates:
        if hr in hours_done:
            continue
        hours_done.add(hr)
        direction = 1 if m > 0 else -1
        # سیگنال: کندلِ قبل از ساعتِ hr (ورود در open کندلِ ساعتِ hr)
        prev_hour = df['hour'].shift(-1).values   # ساعتِ کندلِ بعد
        base_sig = (prev_hour == hr)
        # فیلترِ pullback: اگر جهت صعودی، ۴ کندلِ قبل نزولی بوده باشد (و بالعکس)
        ret4 = np.r_[[np.nan]*4, (c[4:] - c[:-4])]
        if direction > 0:
            pull = ret4 < 0
        else:
            pull = ret4 > 0
        sig = np.nan_to_num(base_sig & pull, nan=0).astype(bool)
        if sig.sum() < 40:
            continue
        long_sig = sig if direction > 0 else np.zeros(n, dtype=bool)
        short_sig = sig if direction < 0 else np.zeros(n, dtype=bool)
        # جاروبِ کوچکِ SL/TP/mh
        best_local = None
        for sl in [10, 12, 15, 20]:
            for tp in [10, 12, 15, 20, 30]:
                for mh in [4, 6, 8]:
                    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                                                asset='AUDUSD', max_hold=mh, allow_overlap=False)
                    if trades is None or len(trades) < 40:
                        continue
                    st, _ = se.run_capital(trades, 'AUDUSD', 10_000, 1.0, compounding=False)
                    mid = n // 2
                    ls1 = long_sig.copy(); ls1[mid:] = False
                    ss1 = short_sig.copy(); ss1[mid:] = False
                    ls2 = long_sig.copy(); ls2[:mid] = False
                    ss2 = short_sig.copy(); ss2[:mid] = False
                    t1 = se.simulate_trades(df, ls1, ss1, sl, tp, 'AUDUSD', mh, False)
                    t2 = se.simulate_trades(df, ls2, ss2, sl, tp, 'AUDUSD', mh, False)
                    st1, _ = se.run_capital(t1, 'AUDUSD', 10_000, 1.0, compounding=False)
                    st2, _ = se.run_capital(t2, 'AUDUSD', 10_000, 1.0, compounding=False)
                    both = st1['net_profit'] > 0 and st2['net_profit'] > 0
                    rec = dict(hr=hr, dir=direction, sl=sl, tp=tp, mh=mh,
                               net=st['net_profit'], pf=st['profit_factor'], wr=st['win_rate'],
                               nn=st['n_trades'], h1=st1['net_profit'], h2=st2['net_profit'], both=both)
                    if best_local is None or (rec['both'], rec['net']) > (best_local['both'], best_local['net']):
                        best_local = rec
        if best_local:
            results.append(best_local)
            print(f"ساعت {hr:>2} ({'LONG' if direction>0 else 'SHORT'}): "
                  f"net=${best_local['net']:>8,.0f} PF={best_local['pf']:.2f} WR={best_local['wr']:.1f}% "
                  f"n={best_local['nn']} both={'✅' if best_local['both'] else '❌'} "
                  f"(SL{best_local['sl']}/TP{best_local['tp']}/mh{best_local['mh']}, h1=${best_local['h1']:,.0f} h2=${best_local['h2']:,.0f})")

    # بهترین ساعتِ both-halves مثبت
    both_ok = [r for r in results if r['both']]
    pool = both_ok if both_ok else results
    best = max(pool, key=lambda r: r['net']) if pool else None
    print("\n" + "=" * 80)
    if best and best['both'] and best['net'] > 0:
        print(f"✅ بهترین لایهٔ AUDUSD: ساعت {best['hr']} {'LONG' if best['dir']>0 else 'SHORT'} "
              f"net=${best['net']:,.0f} (both-halves مثبت)")
    else:
        print("❌ هیچ لایهٔ AUDUSD ی با both-halves مثبت و سودِ معنادار یافت نشد.")
    print("=" * 80)

    with open(os.path.join(RESULTS, '_s109_audusd.json'), 'w') as fj:
        json.dump(dict(candidates=[[int(hr), int(h), float(m), float(t)] for hr, h, m, t in candidates],
                       results=results, best=best), fj, ensure_ascii=False, indent=2, default=float)
    print("\nذخیره شد: results/_s109_audusd.json")


if __name__ == '__main__':
    main()
