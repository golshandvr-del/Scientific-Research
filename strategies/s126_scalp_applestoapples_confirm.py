"""
s126_scalp_applestoapples_confirm.py — تأییدِ سیب‌به‌سیب: آیا پوششِ بالا سود می‌دهد؟
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» — نه WR.
> تعریفِ سودِ خالص = XAUUSD + EURUSD. این فایل تشخیصی است ⇒ رکورد +$95,645 ثابت.
================================================================================

انگیزه:
  s125 با موتورِ simulate_trades نشان داد ماشه‌های «پوششِ بالا» سودِ منفی می‌دهند و
  فقط ماشهٔ «صیّادِ نادرِ» baseline (S91) سودِ مثبت. اما رکوردِ ثبت‌شدهٔ S91 (+۱۰٬۰۴۴$)
  با موتورِ **paper_broker** (خروجِ سیگنال-محور با catastrophic SL) ساخته شده، نه
  simulate_trades. برای انصافِ کامل، اینجا **دقیقاً همان موتورِ paper_broker + همان
  حسابداریِ run_capital** رکورد را روی هر دو نوع ماشه اجرا می‌کنیم:
    • baseline: ورودِ نادرِ S91 (EMA20>EMA100 & RSI21<35)
    • high-coverage: ورودِ pullbackِ سبک (پوششِ بالا)
  اگر باز هم پوششِ بالا بازنده بود ⇒ پاسخِ فلسفیِ User Note قطعی می‌شود:
    «ذاتِ سوددهیِ اسکالپِ طلا M5 = نادر-یابی است؛ پوششِ بالا سود را نابود می‌کند.»
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import scalp_engine as se
from strategies.s91_scalp_signal_exit import paper_broker, DATA
from strategies.s94_scalp_hidden_target import make_hidden_exit

ROOT = os.path.join(os.path.dirname(__file__), '..')
RESULTS = os.path.join(ROOT, 'results')


def ema(x, p):
    x = np.asarray(x, float); out = np.full_like(x, np.nan); k = 2.0/(p+1.0); acc = x[0]; out[0] = acc
    for i in range(1, len(x)):
        acc = x[i]*k + acc*(1-k); out[i] = acc
    return out
def rsi(x, p=21):
    x = np.asarray(x, float); n = len(x); out = np.full(n, np.nan)
    if n < p+1: return out
    d = np.diff(x); g = np.where(d > 0, d, 0.0); l = np.where(d < 0, -d, 0.0)
    ag = g[:p].mean(); al = l[:p].mean()
    out[p] = 100-100/(1+(ag/al if al > 0 else np.inf))
    for i in range(p+1, n):
        ag = (ag*(p-1)+g[i-1])/p; al = (al*(p-1)+l[i-1])/p
        out[i] = 100-100/(1+(ag/al if al > 0 else np.inf))
    return out


def entries_baseline(df):
    """صیّادِ نادرِ S91: EMA20>EMA100 & RSI21<35."""
    c = df['close'].values.astype(float)
    eF = ema(c, 20); eS = ema(c, 100); r = rsi(c, 21)
    return [(i, 'long') for i in range(102, len(df)-1) if eF[i] > eS[i] and r[i] < 35]


def entries_high_coverage(df):
    """پوششِ بالا: روندِ صعودی + pullbackِ سبک (RSI بینِ ۳۵ و ۵۰، قیمت نزدیکِ EMA20)."""
    c = df['close'].values.astype(float)
    e20 = ema(c, 20); e50 = ema(c, 50); e100 = ema(c, 100); r = rsi(c, 21)
    out = []
    for i in range(102, len(df)-1):
        if e50[i] > e100[i] and c[i] <= e20[i]*1.001 and c[i] > e50[i] and 35 <= r[i] < 50:
            out.append((i, 'long'))
    return out


def add_sl(tr, sl_pip):
    tr = tr.copy(); tr['sl_pip'] = float(sl_pip); return tr


def report(df, entries, label, sl_for_sizing=80.0):
    exit_fn = make_hidden_exit(120, 80, use_trend_break=False)
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=500.0, max_hold=288)
    tr = add_sl(tr, sl_for_sizing)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=10000.0, risk_pct=1.0, compounding=True)
    n = len(df); half = n//2
    tr1 = tr[tr['exit_bar'] < half]; tr2 = tr[tr['exit_bar'] >= half]
    s1, _ = se.run_capital(tr1, 'XAUUSD', compounding=True)
    s2, _ = se.run_capital(tr2, 'XAUUSD', compounding=True)
    print(f"\n── {label} ──")
    print(f"   ورودها={len(entries):>5} | n_trades={st['n_trades']:>4} | net=${st['net_profit']:+,.2f} "
          f"| PF={st['profit_factor']:.2f} | WR={st['win_rate']:.1f}%")
    print(f"   نیمهٔ۱=${s1['net_profit']:+,.0f} | نیمهٔ۲=${s2['net_profit']:+,.0f} "
          f"| هر دو مثبت: {'✅' if s1['net_profit']>0 and s2['net_profit']>0 else '❌'}")
    return dict(label=label, entries=len(entries), n=int(st['n_trades']),
                net=float(st['net_profit']), pf=float(st['profit_factor']),
                wr=float(st['win_rate']), h1=float(s1['net_profit']), h2=float(s2['net_profit']))


def main():
    df = pd.read_csv(DATA); df['dt'] = pd.to_datetime(df['time'], unit='s')
    print("="*74)
    print("s126 — تأییدِ سیب‌به‌سیب با موتورِ رکورد (paper_broker + hidden TP120/SL80)")
    print("="*74)
    print(f"داده: {len(df)} کندلِ M5 طلا")

    a = report(df, entries_baseline(df), "A) صیّادِ نادر (baselineِ S91)")
    b = report(df, entries_high_coverage(df), "B) پوششِ بالا (pullbackِ سبک)")

    print("\n" + "="*74)
    print("نتیجه:")
    print(f"  A نادر : net=${a['net']:+,.0f} (ورود {a['entries']})")
    print(f"  B پوشش : net=${b['net']:+,.0f} (ورود {b['entries']})")
    verdict = ("پوششِ بالا بازنده ⇒ ذاتِ سوددهیِ اسکالپِ طلا = نادر-یابی. "
               "baseline دست‌نخورده؛ رکورد +$95,645 ثابت."
               if b['net'] < a['net'] else
               "پوششِ بالا برنده شد ⇒ باید baseline را جایگزین کرد!")
    print(f"  ⇒ {verdict}")
    out = dict(A_rare=a, B_high_coverage=b, verdict=verdict,
               record_net=95645, record_unchanged=(b['net'] < a['net']))
    with open(os.path.join(RESULTS, '_s126_apples.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n✅ ذخیره شد: results/_s126_apples.json")


if __name__ == '__main__':
    main()
