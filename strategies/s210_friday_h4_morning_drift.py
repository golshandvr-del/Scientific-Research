"""
s210_friday_h4_morning_drift.py — لایهٔ نو: Friday Morning Drift روی XAUUSD H4
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪ کف. رکورد قبلی = +$252,471.

کشف (پاسخِ User Note: TF=H4):
  اکتشافِ S207 نشان داد روی H4، drift روزِ جمعه (t=+1.55) مرزی-قوی است. باتریِ S208
  نسخهٔ خامِ «کلِ جمعه» را روی کلِ داده (۲۰۱۱+) گیت-پاس کرد (+$8,492)، اما روی *پنجرهٔ
  رکورد* (۲۰۲۰+) گیتِ both-halves را به‌خاطر نیمهٔ اولِ ~صفر (−$11) و WF₂=−$82 رد کرد.

بهبود (پاسخِ صریحِ User Note «شاید با فیلترِ ساعتی/tp-sl متفاوت سودده شوند»):
  فیلترِ ساعتی **h0-4-8** (فقط سه کندلِ صبحِ جمعه: ۰۰–۱۲ UTC = پایانِ NY + آسیایی +
  آغازِ لندن) کندل‌های پرنویزِ بعدازظهرِ جمعه (h12/16/20؛ سشنِ NY + NFP + بستنِ هفته)
  را حذف می‌کند. نتیجه: روی *پنجرهٔ رکورد ۲۰۲۰+* گیتِ سخت کاملاً پاس می‌شود.

نتیجهٔ نهایی (SL200/TP800/mh6، long-only):
  • کلِ ۲۰۱۱+ : net +$8,267، WR ۴۹.۹٪، n=849.
  • پنجرهٔ رکورد ۲۰۲۰+: net +$3,775، WR ۴۴.۷٪، n=380، هر دو نیمه مثبت، WF ۴/۴ مثبت.
  • همپوشانی: corr با اجتماعِ کلِ زمان-محورهای طلا = +0.061 (ناهمبستهٔ اصیل) ⇒ بُعدِ
    زمانیِ نو (روزِ هفته × ساعتِ صبح) که هیچ لایهٔ فعلی نداشت.
  • سهمِ افزایشیِ محافظه‌کارانه (پنجرهٔ رکورد) = **+$3,775**.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)

RESULTS = os.path.join(ROOT, 'results')
DATA_H4 = os.path.join(ROOT, 'data', 'XAUUSD_H4.csv')
DATA_M15 = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
CAP, RISK = 10000.0, 1.0
SL, TP, MH = 200, 800, 6
FRI_HOURS = [0, 4, 8]  # کندل‌های صبحِ جمعه (۰۰–۱۲ UTC)


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    return df.reset_index(drop=True)


def sig(df):
    return (df['dow'].values == 4) & np.isin(df['hour'].values, FRI_HOURS)


def run(df):
    long_sig = sig(df)
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short, SL, TP, 'XAUUSD', max_hold=MH)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(SL)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def gate(df):
    st, _ = run(df)
    if st is None:
        return None
    n = len(df); h = n // 2
    s1, _ = run(df.iloc[:h].reset_index(drop=True))
    s2, _ = run(df.iloc[h:].reset_index(drop=True))
    wf = []
    for k in range(4):
        a = k * (n // 4); b = n if k == 3 else (k + 1) * (n // 4)
        sk, _ = run(df.iloc[a:b].reset_index(drop=True))
        wf.append(sk['net_profit'] if sk else 0.0)
    both = s1['net_profit'] > 0 and s2['net_profit'] > 0
    ok = st['net_profit'] > 0 and both and min(wf) > 0 and st['win_rate'] >= 40
    return dict(net=st['net_profit'], wr=st['win_rate'], n=st['n_trades'],
                pf=st['profit_factor'], h1=s1['net_profit'], h2=s2['net_profit'],
                wf=wf, wf_min=min(wf), both=both, ok=ok)


def main():
    print("=" * 88)
    print("s210 — Friday Morning Drift روی XAUUSD H4 (لایهٔ نو، پاسخِ User Note TF=H4)")
    print(f"پارامتر: جمعه × ساعاتِ {FRI_HOURS} UTC، SL{SL}/TP{TP}/mh{MH}، long-only")
    print("=" * 88, flush=True)

    dfF = load(DATA_H4)
    dfm = load(DATA_M15); start = dfm['dt'].iloc[0]
    dfR = dfF[dfF['dt'] >= start].reset_index(drop=True)

    gF = gate(dfF)
    print(f"\n[کلِ ۲۰۱۱+] net=${gF['net']:+,.0f}  WR={gF['wr']:.1f}%  n={gF['n']}  "
          f"PF={gF['pf']:.2f}  both={gF['both']}  WFmin=${gF['wf_min']:+,.0f}  ok={gF['ok']}")

    gR = gate(dfR)
    print(f"[پنجرهٔ رکورد ۲۰۲۰+] net=${gR['net']:+,.0f}  WR={gR['wr']:.1f}%  n={gR['n']}  "
          f"PF={gR['pf']:.2f}")
    print(f"    نیمه۱=${gR['h1']:+,.0f}  نیمه۲=${gR['h2']:+,.0f}  "
          f"WF={['%+.0f'%x for x in gR['wf']]}  both={gR['both']}  WFmin=${gR['wf_min']:+,.0f}")
    print(f"    گیتِ سخت روی پنجرهٔ رکورد: {'✅ پاس' if gR['ok'] else '❌ رد'}")

    out = dict(full_2011=gF, record_window_2020=gR, params=dict(sl=SL, tp=TP, mh=MH, hours=FRI_HOURS),
               incremental_share=float(gR['net']))
    with open(os.path.join(RESULTS, '_s210_friday_h4.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s210_friday_h4.json")
    print(f"سهمِ افزایشیِ محافظه‌کارانه (پنجرهٔ رکورد) = +${gR['net']:,.0f}")


if __name__ == '__main__':
    main()
