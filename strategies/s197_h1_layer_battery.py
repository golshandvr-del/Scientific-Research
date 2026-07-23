"""
s197_h1_layer_battery.py — تستِ باتریِ لایه‌ها روی XAUUSD H1 (پاسخِ User Note: TF=H1)
================================================================================
> قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD). WR≥40٪ فقط کفِ پذیرش.

طبقِ User Note، لیستِ لایه‌ها:
  (الف) لایه‌های زمان-محورِ *فعلیِ* رکورد (S139/S140/S141/S142/S144) — بازتنظیم‌شده برای H1.
  (ب) لایهٔ *حدسیِ* جدید که اکتشافِ S196 پیشنهاد داد: «Asian Drift ساعتِ ۰–۳ UTC»
      (روی H1 مرکزِ ثقلِ drift از ۲۲–۲۳ به ۰–۳ جابه‌جا شده؛ ساعتِ ۱ UTC با t=+4.7).

هر لایه به‌صورتِ مجزا روی XAUUSD H1 با گیتِ سختِ ضدِ overfit سنجیده می‌شود:
  گیت = net>0  AND  هر دو نیمه مثبت  AND  هر ۴ پنجرهٔ walk-forward مثبت  AND  WR≥40٪.

تنظیمِ H1 (طبقِ S196): ATR H1 ≈ 1.38× M15 ⇒ TP/SL کمی بزرگ‌تر؛ max_hold بر حسبِ
*تعداد کندل* تقریباً M15/4 (هر H1 = 4×M15). جاروبِ سبک روی چند TP/SL/mh کاندید.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se

# اطمینان از مشخصاتِ واقعیِ حسابِ کاربر (طلا 3.3pip، کمیسیون صفر)
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)

RESULTS = os.path.join(ROOT, 'results')
DATA_H1 = os.path.join(ROOT, 'data', 'XAUUSD_H1.csv')
CAP, RISK = 10000.0, 1.0


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    df['dom'] = df['dt'].dt.day
    df['dim'] = df['dt'].dt.days_in_month
    return df.reset_index(drop=True)


# ---------- سازندگانِ سیگنالِ هر لایه (روی H1) ----------
def sig_hours(df, hours):
    return np.isin(df['hour'].values, list(hours))

def sig_monday(df, hours):
    return (df['dow'].values == 0) & np.isin(df['hour'].values, list(hours))

def sig_turn_of_month(df, hours):
    # dom==1 (اولین روزِ تقویمی) — تقریبِ ساده و forward-safe
    return (df['dom'].values == 1) & np.isin(df['hour'].values, list(hours))

def sig_midmonth(df, days, hours):
    return np.isin(df['dom'].values, list(days)) & np.isin(df['hour'].values, list(hours))

def sig_endofmonth(df, rel_days, hours):
    # rel_days منفی: فاصله از پایانِ ماه. dom == dim + rel + 1
    dom = df['dom'].values; dim = df['dim'].values
    m = np.zeros(len(df), bool)
    for rel in rel_days:
        m |= (dom == (dim + rel + 1))
    return m & np.isin(df['hour'].values, list(hours))


def run_layer(df, long_sig, sl, tp, mh):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short, sl, tp, 'XAUUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def gate(df, sigfn, sl, tp, mh):
    """گیتِ سخت: net کل + هر دو نیمه + walk-forward ۴ پنجره + WR."""
    n = len(df)
    full = df
    st, tr = run_layer(full, sigfn(full), sl, tp, mh)
    if st is None:
        return None
    net = st['net_profit']; wr = st['win_rate']; ntr = st['n_trades']
    half = n // 2
    d1 = df.iloc[:half].reset_index(drop=True)
    d2 = df.iloc[half:].reset_index(drop=True)
    s1, _ = run_layer(d1, sigfn(d1), sl, tp, mh)
    s2, _ = run_layer(d2, sigfn(d2), sl, tp, mh)
    h1 = s1['net_profit'] if s1 else 0.0
    h2 = s2['net_profit'] if s2 else 0.0
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
                wr_ok=bool(wr >= 40.0), ok=bool(ok), sl=sl, tp=tp, mh=mh)


# جاروبِ خروجِ کاندید مخصوصِ H1 (SL/TP/mh بر حسبِ pip و تعدادِ کندلِ H1)
# mh روی H1: 6=۶ساعت، 12=۱۲ساعت، 24=۱روز
EXITS_H1 = [
    (100, 200, 6), (100, 250, 12), (150, 300, 12), (150, 400, 24),
    (200, 400, 24), (200, 500, 24), (120, 350, 8), (250, 500, 12),
]


def sweep_layer(df, name, sigfn):
    print(f"\n{'='*92}\n▶ لایه: {name}")
    print(f"{'SL':>5}{'TP':>5}{'mh':>4}{'n':>7}{'net':>12}{'WR':>7}{'H1':>11}{'H2':>11}{'WFmin':>11} حکم")
    print("-" * 84)
    rows = []
    for (sl, tp, mh) in EXITS_H1:
        g = gate(df, sigfn, sl, tp, mh)
        if g is None:
            continue
        flag = "✅" if g['ok'] else ("wr<40" if not g['wr_ok'] else "—")
        print(f"{sl:>5}{tp:>5}{mh:>4}{g['n']:>7}${g['net']:>+11,.0f}{g['wr']:>6.1f}%"
              f"${g['h1']:>+10,.0f}${g['h2']:>+10,.0f}${g['wf_min']:>+10,.0f} {flag}", flush=True)
        rows.append(dict(name=name, **g))
    passed = [r for r in rows if r['ok']]
    best = max(passed, key=lambda r: r['net']) if passed else None
    if best:
        print(f"  🏆 برندهٔ گیت-پاس: SL{best['sl']}/TP{best['tp']}/mh{best['mh']}  "
              f"net=${best['net']:+,.0f}  WR={best['wr']:.1f}%")
    else:
        print(f"  ⚠️ هیچ پیکربندی‌ای گیتِ سخت را روی H1 پاس نکرد.")
    return rows, best


def main():
    print("=" * 92)
    print("s197 — باتریِ لایه‌ها روی XAUUSD H1 (زمان-محورهای فعلی + Asian Drift حدسی)")
    print("گیتِ سخت: net>0 و هر دو نیمه مثبت و WF ۴/۴ مثبت و WR≥40٪")
    print("=" * 92, flush=True)

    df = load(DATA_H1)
    print(f"داده: {len(df):,} کندلِ H1  ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})")

    layers = {
        # (ب) لایهٔ حدسیِ جدید از اکتشافِ S196 — قوی‌ترین کاندید
        'AsianDrift_h0-3 (حدسی-نو)': lambda d: sig_hours(d, [0, 1, 2, 3]),
        'AsianDrift_h1 (حدسی-نو، فقط ساعتِ قوی)': lambda d: sig_hours(d, [1]),
        'AsianDrift_h0-1-3 (حدسی-نو)': lambda d: sig_hours(d, [0, 1, 3]),
        # (الف) لایه‌های زمان-محورِ فعلیِ رکورد — بازتنظیم‌شده برای H1
        'S139_Overnight_h22-23 (فعلی)': lambda d: sig_hours(d, [22, 23]),
        'S140_Monday_h18-21 (فعلی)': lambda d: sig_monday(d, [18, 19, 20, 21]),
        'S141_TurnOfMonth_h7-12 (فعلی)': lambda d: sig_turn_of_month(d, range(7, 13)),
        'S142_MidMonth_d10-13-20_h1-12 (فعلی)': lambda d: sig_midmonth(d, [10, 13, 20], range(1, 13)),
        'S144_EndOfMonth_rel6-8_h19-23 (فعلی)': lambda d: sig_endofmonth(d, [-6, -7, -8], [19, 20, 21, 22, 23]),
    }

    all_rows = {}
    winners = {}
    for name, fn in layers.items():
        rows, best = sweep_layer(df, name, fn)
        all_rows[name] = rows
        if best:
            winners[name] = best

    print(f"\n{'='*92}\n📊 خلاصهٔ برندگانِ گیت-پاس روی H1:")
    if not winners:
        print("  هیچ لایه‌ای به‌تنهایی گیتِ سخت را روی H1 پاس نکرد.")
    else:
        for name, b in sorted(winners.items(), key=lambda kv: -kv[1]['net']):
            print(f"  ✅ {name}: net=${b['net']:+,.0f}  WR={b['wr']:.1f}%  "
                  f"SL{b['sl']}/TP{b['tp']}/mh{b['mh']}  WF={['%+.0f'%x for x in b['wf']]}")

    out = dict(data='XAUUSD_H1', n_candles=len(df), layers=all_rows,
               winners={k: v for k, v in winners.items()})
    with open(os.path.join(RESULTS, '_s197_h1_battery.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s197_h1_battery.json")


if __name__ == '__main__':
    main()
