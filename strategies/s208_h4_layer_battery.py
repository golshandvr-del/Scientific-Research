"""
s208_h4_layer_battery.py — تستِ باتریِ لایه‌ها روی XAUUSD H4 (پاسخِ User Note: TF=H4)
================================================================================
> قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD). WR≥40٪ فقط کفِ پذیرش.

طبقِ User Note، لیستِ لایه‌ها (تأییدشده با اکتشافِ S207):
  (الف) لایه‌های زمان-محورِ *فعلیِ* رکورد (S139/S140/S141/S142/S144) — بازتنظیم‌شده H4.
  (ب) لایه‌های *حدسی/رد‌شده* که اکتشافِ S207 پیشنهاد داد:
      - H4-Overnight h0 (قوی‌ترین سیگنال، t=+6.12)
      - Friday-Drift (t=+1.55؛ روی M15/H1 رد شده بود)
      - TurnOfMonth × ساعتِ ۰ (ترکیبِ دو لبهٔ قوی)

هر لایه به‌صورتِ مجزا روی XAUUSD H4 با گیتِ سختِ ضدِ overfit سنجیده می‌شود:
  گیت = net>0  AND  هر دو نیمه مثبت  AND  هر ۴ پنجرهٔ walk-forward مثبت  AND  WR≥40٪.

تنظیمِ H4 (طبقِ S207): ATR H4 ≈ ۲×H1 و ۳×M15 ⇒ TP/SL بزرگ‌تر؛ max_hold بر حسبِ
*تعداد کندل* بسیار کوچک‌تر (هر H4 = 4×H1 = 16×M15).
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
CAP, RISK = 10000.0, 1.0


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    df['dom'] = df['dt'].dt.day
    df['dim'] = df['dt'].dt.days_in_month
    return df.reset_index(drop=True)


# ---------- سازندگانِ سیگنالِ هر لایه (روی H4) ----------
def sig_hours(df, hours):
    return np.isin(df['hour'].values, list(hours))

def sig_monday(df, hours):
    return (df['dow'].values == 0) & np.isin(df['hour'].values, list(hours))

def sig_friday(df, hours):
    return (df['dow'].values == 4) & np.isin(df['hour'].values, list(hours))

def sig_turn_of_month(df, hours):
    return np.isin(df['dom'].values, [1, 2, 3]) & np.isin(df['hour'].values, list(hours))

def sig_midmonth(df, days, hours):
    return np.isin(df['dom'].values, list(days)) & np.isin(df['hour'].values, list(hours))

def sig_endofmonth(df, rel_days, hours):
    dom = df['dom'].values; dim = df['dim'].values
    m = np.zeros(len(df), bool)
    for rel in rel_days:
        m |= (dom == (dim + rel + 1))
    return m & np.isin(df['hour'].values, list(hours))

def sig_tom_hour0(df):
    """Turn-of-Month × کندلِ ساعتِ ۰ (ترکیبِ دو لبهٔ قوی H4)."""
    return np.isin(df['dom'].values, [1, 2, 3]) & (df['hour'].values == 0)


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
    st, tr = run_layer(df, sigfn(df), sl, tp, mh)
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


# جاروبِ خروجِ کاندید مخصوصِ H4 (SL/TP بزرگ‌تر؛ mh بر حسبِ کندلِ H4: 1=4h,3=12h,6=24h)
EXITS_H4 = [
    (200, 400, 3), (200, 600, 6), (300, 600, 6), (300, 800, 6),
    (300, 900, 3), (400, 800, 6), (400, 1000, 6), (400, 1200, 3),
    (250, 500, 2), (350, 700, 4), (200, 800, 6), (300, 1000, 6),
]


def sweep_layer(df, name, sigfn):
    print(f"\n{'='*96}\n▶ لایه: {name}")
    print(f"{'SL':>5}{'TP':>6}{'mh':>4}{'n':>7}{'net':>13}{'WR':>7}{'H1':>12}{'H2':>12}{'WFmin':>12} حکم")
    print("-" * 90)
    rows = []
    for (sl, tp, mh) in EXITS_H4:
        g = gate(df, sigfn, sl, tp, mh)
        if g is None:
            continue
        flag = "✅" if g['ok'] else ("wr<40" if not g['wr_ok'] else ("2half" if not g['both'] else ("WF" if g['wf_min'] <= 0 else "net")))
        print(f"{sl:>5}{tp:>6}{mh:>4}{g['n']:>7}${g['net']:>+12,.0f}{g['wr']:>6.1f}%"
              f"${g['h1']:>+11,.0f}${g['h2']:>+11,.0f}${g['wf_min']:>+11,.0f} {flag}", flush=True)
        rows.append(dict(name=name, **g))
    passed = [r for r in rows if r['ok']]
    best = max(passed, key=lambda r: r['net']) if passed else None
    if best:
        print(f"  🏆 برندهٔ گیت-پاس: SL{best['sl']}/TP{best['tp']}/mh{best['mh']}  "
              f"net=${best['net']:+,.0f}  WR={best['wr']:.1f}%  n={best['n']}")
    else:
        # بهترین از نظر net حتی اگر گیت را پاس نکرد (برای گزارش)
        if rows:
            b2 = max(rows, key=lambda r: r['net'])
            print(f"  ⚠️ هیچ پیکربندی گیتِ سخت را پاس نکرد. بهترین net (رد): "
                  f"SL{b2['sl']}/TP{b2['tp']}/mh{b2['mh']} net=${b2['net']:+,.0f} "
                  f"WR={b2['wr']:.1f}% (both={b2['both']}, wf_min=${b2['wf_min']:+,.0f})")
    return rows, best


def main():
    print("=" * 96)
    print("s208 — باتریِ لایه‌ها روی XAUUSD H4 (زمان-محورهای فعلی + حدسی‌های داده-محورِ S207)")
    print("گیتِ سخت: net>0 و هر دو نیمه مثبت و WF ۴/۴ مثبت و WR≥40٪")
    print("=" * 96, flush=True)

    df = load(DATA_H4)
    print(f"داده: {len(df):,} کندلِ H4  ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})")

    layers = {
        # (ب) حدسی‌های داده-محورِ S207 — قوی‌ترین کاندیدها اول
        'H4_Overnight_h0 (حدسی-نو، t=+6.12)': lambda d: sig_hours(d, [0]),
        'H4_Overnight_h0-20 (حدسی، دو کندلِ مثبت)': lambda d: sig_hours(d, [0, 20]),
        'Friday_all (حدسی-نو، t=+1.55)': lambda d: sig_friday(d, [0, 4, 8, 12, 16, 20]),
        'Friday_h0 (حدسی، جمعه×کندلِ قوی)': lambda d: sig_friday(d, [0]),
        'TurnOfMonth_x_h0 (حدسی، ترکیبِ دو لبه)': sig_tom_hour0,
        # (الف) لایه‌های زمان-محورِ فعلیِ رکورد — بازتنظیم‌شده برای H4
        'S139_Overnight (فعلی، h0 معادلِ شبانه)': lambda d: sig_hours(d, [0]),
        'S140_Monday (فعلی، t=+0.19)': lambda d: sig_monday(d, [16, 20]),
        'S141_TurnOfMonth (فعلی، dom1-3)': lambda d: sig_turn_of_month(d, [0, 4, 8, 12]),
        'S142_MidMonth (فعلی، dom10-14)': lambda d: sig_midmonth(d, [10, 11, 12, 13, 14], [0, 4, 8, 12]),
        'S144_EndOfMonth (فعلی، rel-6..-3)': lambda d: sig_endofmonth(d, [-6, -5, -4, -3], [12, 16, 20]),
    }

    all_rows = {}
    winners = {}
    for name, fn in layers.items():
        rows, best = sweep_layer(df, name, fn)
        all_rows[name] = rows
        if best:
            winners[name] = best

    print(f"\n{'='*96}\n📊 خلاصهٔ برندگانِ گیت-پاس روی H4:")
    if not winners:
        print("  هیچ لایه‌ای به‌تنهایی گیتِ سخت را روی H4 پاس نکرد.")
    else:
        for name, b in sorted(winners.items(), key=lambda kv: -kv[1]['net']):
            print(f"  ✅ {name}: net=${b['net']:+,.0f}  WR={b['wr']:.1f}%  "
                  f"SL{b['sl']}/TP{b['tp']}/mh{b['mh']}  WF={['%+.0f'%x for x in b['wf']]}")

    out = dict(data='XAUUSD_H4', n_candles=len(df), layers=all_rows,
               winners={k: v for k, v in winners.items()})
    with open(os.path.join(RESULTS, '_s208_h4_battery.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s208_h4_battery.json")


if __name__ == '__main__':
    main()
