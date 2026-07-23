"""
s198_h1_aligned_window.py — تستِ عادلانه: H1 روی همان بازهٔ زمانیِ M15 (2020+)
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪ کفِ پذیرش.

انگیزه (نتیجهٔ S197):
  در S197 تقریباً همهٔ لایه‌های زمان-محور روی *کلِ* دادهٔ H1 (۲۰۱۱–۲۰۲۶) net مثبتِ
  بزرگ ساختند اما گیتِ both-halves را رد کردند چون **نیمهٔ اولِ H1 (۲۰۱۱–۲۰۱۸)** منفی
  بود. اما رکوردِ فعلیِ پروژه روی M15 ساخته شده که فقط **از ۲۰۲۰** داده دارد.
  ⇒ مقایسهٔ عادلانه: H1 را هم روی **همان بازهٔ M15 (۲۰۲۰-۰۲-۲۰ به بعد)** بسنجیم.
  آنگاه both-halves و walk-forward روی بازهٔ *یکسان* اجرا می‌شود (سیب‌به‌سیب با رکورد).

این پاسخِ مستقیمِ درسِ داده است: «drift روی H1 در دورهٔ اخیر (مثلِ M15) قوی است؛
گیتِ رد به‌خاطرِ رژیمِ متفاوتِ ۲۰۱۱–۲۰۱۸ بود، نه بی‌اعتباریِ لبه در دورهٔ فعلی.»
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
DATA_H1 = os.path.join(ROOT, 'data', 'XAUUSD_H1.csv')
DATA_M15 = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
CAP, RISK = 10000.0, 1.0


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    df['dom'] = df['dt'].dt.day
    df['dim'] = df['dt'].dt.days_in_month
    return df.reset_index(drop=True)


def sig_hours(df, hours):
    return np.isin(df['hour'].values, list(hours))

def sig_monday(df, hours):
    return (df['dow'].values == 0) & np.isin(df['hour'].values, list(hours))

def sig_midmonth(df, days, hours):
    return np.isin(df['dom'].values, list(days)) & np.isin(df['hour'].values, list(hours))


def run_layer(df, long_sig, sl, tp, mh):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short, sl, tp, 'XAUUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def gate(df, sigfn, sl, tp, mh):
    n = len(df)
    st, _ = run_layer(df, sigfn(df), sl, tp, mh)
    if st is None:
        return None
    net = st['net_profit']; wr = st['win_rate']; ntr = st['n_trades']
    half = n // 2
    d1 = df.iloc[:half].reset_index(drop=True); d2 = df.iloc[half:].reset_index(drop=True)
    s1, _ = run_layer(d1, sigfn(d1), sl, tp, mh); s2, _ = run_layer(d2, sigfn(d2), sl, tp, mh)
    h1 = s1['net_profit'] if s1 else 0.0; h2 = s2['net_profit'] if s2 else 0.0
    wf = []
    for k in range(4):
        a = k * (n // 4); b = n if k == 3 else (k + 1) * (n // 4)
        seg = df.iloc[a:b].reset_index(drop=True)
        sK, _ = run_layer(seg, sigfn(seg), sl, tp, mh)
        wf.append(sK['net_profit'] if sK else 0.0)
    wf_min = min(wf)
    both = h1 > 0 and h2 > 0
    ok = net > 0 and both and wf_min > 0 and wr >= 40.0
    return dict(net=float(net), wr=float(wr), n=int(ntr), h1=float(h1), h2=float(h2),
                wf=[float(x) for x in wf], wf_min=float(wf_min), both=bool(both),
                ok=bool(ok), sl=sl, tp=tp, mh=mh)


EXITS_H1 = [
    (100, 250, 12), (150, 300, 12), (150, 400, 24), (200, 400, 24),
    (200, 500, 24), (120, 350, 8), (250, 500, 12), (150, 350, 18),
]


def sweep(df, name, sigfn):
    print(f"\n{'='*92}\n▶ {name}")
    print(f"{'SL':>5}{'TP':>5}{'mh':>4}{'n':>7}{'net':>12}{'WR':>7}{'H1':>11}{'H2':>11}{'WFmin':>11} حکم")
    print("-" * 84)
    rows = []
    for (sl, tp, mh) in EXITS_H1:
        g = gate(df, sigfn, sl, tp, mh)
        if g is None:
            continue
        flag = "✅" if g['ok'] else "—"
        print(f"{sl:>5}{tp:>5}{mh:>4}{g['n']:>7}${g['net']:>+11,.0f}{g['wr']:>6.1f}%"
              f"${g['h1']:>+10,.0f}${g['h2']:>+10,.0f}${g['wf_min']:>+10,.0f} {flag}", flush=True)
        rows.append(dict(name=name, **g))
    passed = [r for r in rows if r['ok']]
    best = max(passed, key=lambda r: r['net']) if passed else None
    if best:
        print(f"  🏆 گیت-پاس: SL{best['sl']}/TP{best['tp']}/mh{best['mh']} net=${best['net']:+,.0f} WR={best['wr']:.1f}%")
    else:
        print(f"  ⚠️ گیتِ سخت پاس نشد (روی بازهٔ هم‌تراز M15).")
    return rows, best


def main():
    print("=" * 92)
    print("s198 — H1 روی بازهٔ هم‌تراز با M15 (۲۰۲۰+): مقایسهٔ عادلانهٔ سیب‌به‌سیب")
    print("=" * 92, flush=True)

    dfm = load(DATA_M15)
    m15_start = dfm['dt'].iloc[0]
    print(f"شروعِ داده M15: {m15_start}")

    df = load(DATA_H1)
    df = df[df['dt'] >= m15_start].reset_index(drop=True)
    print(f"H1 محدودشده به بازهٔ M15: {len(df):,} کندل  ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})")

    layers = {
        'AsianDrift_h0-3 (حدسی-نو)': lambda d: sig_hours(d, [0, 1, 2, 3]),
        'AsianDrift_h1 (حدسی-نو)': lambda d: sig_hours(d, [1]),
        'AsianDrift_h0-1-3 (حدسی-نو)': lambda d: sig_hours(d, [0, 1, 3]),
        'S139_Overnight_h22-23 (فعلی)': lambda d: sig_hours(d, [22, 23]),
        'S139_Overnight_h21-23 (فعلی-گسترده)': lambda d: sig_hours(d, [21, 22, 23]),
        'S140_Monday_h18-21 (فعلی)': lambda d: sig_monday(d, [18, 19, 20, 21]),
        'S142_MidMonth_d10-13-20_h1-12 (فعلی)': lambda d: sig_midmonth(d, [10, 13, 20], range(1, 13)),
    }

    all_rows = {}; winners = {}
    for name, fn in layers.items():
        rows, best = sweep(df, name, fn)
        all_rows[name] = rows
        if best:
            winners[name] = best

    print(f"\n{'='*92}\n📊 برندگانِ گیت-پاس روی H1 (بازهٔ هم‌تراز M15):")
    if not winners:
        print("  هیچ لایه‌ای پاس نکرد.")
    else:
        for name, b in sorted(winners.items(), key=lambda kv: -kv[1]['net']):
            print(f"  ✅ {name}: net=${b['net']:+,.0f} WR={b['wr']:.1f}% "
                  f"SL{b['sl']}/TP{b['tp']}/mh{b['mh']} WF={['%+.0f'%x for x in b['wf']]}")

    out = dict(data='XAUUSD_H1_alignedM15', n_candles=len(df),
               window_start=str(df['dt'].iloc[0]), layers=all_rows, winners=winners)
    with open(os.path.join(RESULTS, '_s198_h1_aligned.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s198_h1_aligned.json")


if __name__ == '__main__':
    main()
