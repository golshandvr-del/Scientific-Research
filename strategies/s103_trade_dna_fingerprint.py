"""
s103_trade_dna_fingerprint.py — پاسخِ علمی به User Note فلسفی
================================================================================
سوالِ فلسفیِ User Note:
  «چرا هر استراتژی فقط روندهای خاصی را کشف می‌کند؟ چه چیزِ مشترکی بین روندهایی که
   یک استراتژی درست تشخیص می‌دهد وجود دارد؟ و چرا استراتژی دیگر روندهای دیگری را؟»

فرضیهٔ محوریِ این فایل (Trade-DNA):
  هر استراتژی یک «آشکارساز» است که به یک «امضای رژیمی» (regime fingerprint) خاص
  کوک شده. معاملاتِ برندهٔ آن استراتژی یک DNA مشترک دارند (بردارِ ویژگی‌های بازار
  در لحظهٔ ورود). معاملاتِ بازنده در ناحیهٔ دیگری از فضای ویژگی می‌افتند.
  → اگر امضای رژیمیِ برنده را کشف کنیم و استراتژی را *فقط* در آن ناحیه فعال کنیم،
    سودِ خالص بالا می‌رود (هرس کردنِ بازنده‌های سیستماتیک).

این اسکریپت:
  1. معاملاتِ لایهٔ SHORT (تنها لایهٔ SHORTِ رکورد) را بازتولید می‌کند.
  2. برای هر معامله، بردارِ امضای رژیمی در لحظهٔ ورود را استخراج می‌کند.
  3. تفاوتِ آماریِ برنده‌ها و بازنده‌ها را در فضای ویژگی نشان می‌دهد (پاسخِ سوال).
  4. یک گیتِ DNA می‌سازد و اثرِ آن بر سودِ خالص را می‌سنجد (بدون look-ahead:
     آستانه‌ها فقط روی نیمهٔ اول برازش، روی نیمهٔ دوم OOS تست می‌شوند).

قانونِ شمارهٔ ۱ پروژه: فقط و فقط «سودِ خالصِ بیشتر». WR فقط گزارشی است.
تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def short_signal(df):
    """ماشهٔ SHORTِ رکورد: قیمت میانگینِ [EMA50,EMA100,SMA200] را از بالا به پایین قطع کند."""
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values
    e100 = ind.ema(c, 100).values
    s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def build_fingerprint(df):
    """
    بردارِ امضای رژیمی برای هر کندل — «DNA بازار در آن لحظه».
    این ویژگی‌ها همان چیزی هستند که سوالِ فلسفی می‌پرسد: چه چیزی محیطِ ورود را
    از هم متمایز می‌کند؟
    """
    c = df['close']; h = df['high']; l = df['low']
    atr14 = ind.atr(df, 14)
    fp = pd.DataFrame(index=df.index)
    # 1) قدرت/جهتِ روند (ADX + شیب)
    adx_, _pdi, _mdi = ind.adx(df, 14)
    fp['adx'] = adx_.values
    fp['slope50'] = ind.rolling_slope(c, 50) / atr14           # شیبِ نرمال‌شده با نوسان
    # 2) رژیمِ نوسان (ATR نسبی + z-نوسان)
    fp['atr_pct'] = (atr14 / c) * 100.0
    fp['vol_z'] = ind.zscore(atr14, 100)
    # 3) موقعیتِ قیمت نسبت به میانگین‌ها (کشش)
    e50 = ind.ema(c, 50); s200 = ind.sma(c, 200)
    fp['dist_ema50'] = (c - e50) / atr14                       # چقدر از EMA50 دور است
    fp['dist_sma200'] = (c - s200) / atr14
    # 4) مومنتوم
    fp['rsi'] = ind.rsi(c, 14)
    fp['ret20'] = c.pct_change(20) * 100.0                     # بازدهِ ۲۰ کندلِ اخیر
    # 5) ساعتِ روز (ساختارِ سشن)
    fp['hour'] = df['dt'].dt.hour
    return fp


def extract_trade_dna(df, trades, fp):
    """برای هر معامله، امضای رژیمی در کندلِ سیگنال (entry_bar - 1) را می‌چسباند."""
    rows = []
    for _, t in trades.iterrows():
        sig_bar = int(t['entry_bar']) - 1
        if sig_bar < 0 or sig_bar >= len(fp):
            continue
        row = fp.iloc[sig_bar].to_dict()
        row['pnl_pip'] = t['pnl_pip']
        row['win'] = 1 if t['outcome'] == 'win' else 0
        row['exit_bar'] = t['exit_bar']
        row['sl_pip'] = t['sl_pip']
        row['outcome'] = t['outcome']
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    print("=" * 78)
    print("s103 — Trade-DNA: چرا هر استراتژی روندهای خاصی را کشف می‌کند؟")
    print("=" * 78)
    df = load()
    print(f"داده: {len(df):,} کندل XAUUSD M15")

    # --- بازتولیدِ لایهٔ SHORTِ رکورد (SL40/BE8/trail8/max12) ---
    ssig = short_signal(df)
    nosig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, nosig, ssig, sl_pip=40, tp_pip=200,
                                asset='XAUUSD', max_hold=12, allow_overlap=False,
                                be_trigger_pip=8, trail_pip=8)
    print(f"تعداد معاملاتِ SHORT: {len(trades)}")

    stats, _ = se.run_capital(trades, 'XAUUSD', initial_capital=10_000, risk_pct=1.0,
                              compounding=False)
    print(f"سودِ خالصِ پایه (کلِ داده): ${stats['net_profit']:,.0f}  "
          f"PF={stats['profit_factor']:.2f}  WR={stats['win_rate']:.1f}%")

    # --- استخراجِ DNA ---
    fp = build_fingerprint(df)
    dna = extract_trade_dna(df, trades, fp)
    dna = dna.dropna()
    print(f"\nمعاملاتِ با DNA کامل: {len(dna)}  (برنده: {dna['win'].sum()}, بازنده: {(1-dna['win']).sum()})")

    # --- پاسخِ سوالِ فلسفی: تفاوتِ آماریِ برنده‌ها و بازنده‌ها ---
    print("\n" + "=" * 78)
    print("پاسخِ سوالِ فلسفی: امضای رژیمیِ برنده‌ها در برابر بازنده‌ها")
    print("=" * 78)
    feats = ['adx', 'slope50', 'atr_pct', 'vol_z', 'dist_ema50', 'dist_sma200',
             'rsi', 'ret20', 'hour']
    win = dna[dna['win'] == 1]
    los = dna[dna['win'] == 0]
    print(f"{'ویژگی':<14}{'میانگین(برنده)':>16}{'میانگین(بازنده)':>16}{'تفاوت':>12}")
    sep = {}
    for f in feats:
        mw, ml = win[f].mean(), los[f].mean()
        sd = dna[f].std()
        d = (mw - ml) / sd if sd > 0 else 0.0   # اثرِ کوهن
        sep[f] = d
        print(f"{f:<14}{mw:>16.3f}{ml:>16.3f}{d:>12.3f}")
    # قوی‌ترین متمایزکننده‌ها
    ranked = sorted(sep.items(), key=lambda x: -abs(x[1]))
    print("\nقوی‌ترین متمایزکننده‌ها (اثرِ کوهن):")
    for f, d in ranked[:4]:
        direction = "برنده‌ها بالاتر" if d > 0 else "برنده‌ها پایین‌تر"
        print(f"  • {f}: |d|={abs(d):.3f}  ({direction})")

    # --- گیتِ DNA بدون look-ahead: برازش روی نیمهٔ اول، تست روی نیمهٔ دوم ---
    print("\n" + "=" * 78)
    print("گیتِ DNA (بدون look-ahead): آستانه روی نیمهٔ اول، تست OOS روی نیمهٔ دوم")
    print("=" * 78)
    dna = dna.sort_values('exit_bar').reset_index(drop=True)
    mid = len(dna) // 2
    train = dna.iloc[:mid]
    test = dna.iloc[mid:]

    # روی نیمهٔ اول، ۲ ویژگیِ برترِ متمایزکننده را با آستانهٔ سودده انتخاب کن
    top2 = [f for f, _ in ranked[:2]]
    print(f"دو ویژگیِ منتخبِ گیت: {top2}")

    def apply_gate(sub, gates):
        m = np.ones(len(sub), dtype=bool)
        for f, lo, hi in gates:
            m &= (sub[f] >= lo) & (sub[f] <= hi)
        return m

    # آستانه: چارکِ سودده روی train (بیشینه‌سازیِ سودِ خالصِ pip)
    best_gate = None; best_net_tr = -1e9
    for f in top2:
        qs = train[f].quantile([0, .1, .25, .4, .6, .75, .9, 1]).values
        for i in range(len(qs)):
            for j in range(i+1, len(qs)):
                lo, hi = qs[i], qs[j]
                m = (train[f] >= lo) & (train[f] <= hi)
                if m.sum() < 30:
                    continue
                net = train.loc[m, 'pnl_pip'].sum()
                if net > best_net_tr:
                    best_net_tr = net; best_gate = [(f, lo, hi)]
    print(f"بهترین گیتِ تک-ویژگی روی train: {best_gate}  net_pip={best_net_tr:.0f}")

    # اعمالِ همان گیتِ ثابت روی نیمهٔ دوم (OOS) — قضاوتِ نهایی
    m_test = apply_gate(test, best_gate)
    kept = test[m_test]
    base_net_test = test['pnl_pip'].sum()
    gate_net_test = kept['pnl_pip'].sum()
    print(f"\nOOS (نیمهٔ دوم):")
    print(f"  بدونِ گیت:  net_pip={base_net_test:8.0f}  n={len(test)}  WR={test['win'].mean()*100:.1f}%")
    print(f"  با گیتِ DNA: net_pip={gate_net_test:8.0f}  n={len(kept)}  WR={kept['win'].mean()*100:.1f}%")

    verdict = "✅ گیتِ DNA سودِ OOS را بهبود داد" if gate_net_test > base_net_test \
        else "❌ گیتِ DNA سودِ OOS را بهبود نداد"
    print(f"  {verdict}")

    out = {
        'base_net_full_usd': stats['net_profit'],
        'top_discriminators': ranked[:4],
        'best_gate': best_gate,
        'oos_base_net_pip': float(base_net_test),
        'oos_gate_net_pip': float(gate_net_test),
        'oos_base_n': int(len(test)),
        'oos_gate_n': int(len(kept)),
    }
    with open(os.path.join(RESULTS, '_s103_dna.json'), 'w') as fjson:
        json.dump(out, fjson, ensure_ascii=False, indent=2, default=float)
    print("\nذخیره شد: results/_s103_dna.json")


if __name__ == '__main__':
    main()
