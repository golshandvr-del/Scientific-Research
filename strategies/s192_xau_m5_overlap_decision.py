# -*- coding: utf-8 -*-
"""
s192_xau_m5_overlap_decision.py — قانونِ همپوشانی + اثرِ خالصِ واقعیِ لایه‌های M5 طلا
================================================================================
> # 🎯 قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD). WR≥۴۰٪ فقط کفِ پذیرش.

انگیزه: S191 نشان داد سه لایهٔ زمان-محورِ طلا (S139 Overnight، S140 Monday، S142
  Mid-Month) روی M5 با **TP/SL بازتنظیم‌شده (SL100/TP200 mh288)** گیتِ سخت را پاس می‌کنند.
  اکنون طبقِ **قانونِ همپوشانیِ اجباری** باید پیش از هر تصمیم بررسی شود:
    (۱) هر لایهٔ M5 با نسخهٔ M15 خودش چند درصد همپوشانیِ روزانه دارد؟
    (۲) بخشِ ناهمپوشانِ M5 سودده است یا ضررده؟
    (۳) تصمیم: upgrade (جایگزین) / افزودنِ لایهٔ دوم / فیلتر / رد.
  و مثلِ S189، اثرِ خالصِ واقعیِ افزایشی روی رکورد با رویکردِ hybrid محاسبه شود
  (M5 فقط از ۲۰۲۳-۰۹ داده دارد؛ نسخهٔ رکوردِ M15 روی کلِ تاریخ فعال است).

نکتهٔ روش‌شناختیِ مهم (اثرِ افزایشی، نه net خام):
  Δ افزایشیِ هر لایه روی رکورد = (net نسخهٔ M5 در بازهٔ مشترک) − (net نسخهٔ M15 در بازهٔ مشترک).
  چون بخشِ تاریخیِ پیش از ۲۰۲۳ در هر دو سناریو یکسان می‌ماند (M15)، فقط اختلافِ بازهٔ
  مشترک اهمیت دارد. این محافظه‌کارانه و دقیقاً روشِ پذیرفته‌شدهٔ S189 است.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0
for tf in ('M15', 'M5'):
    se.ASSETS[f'XAUUSD_{tf}'] = dict(file=f'data/XAUUSD_{tf}.csv', pip=0.10, contract=100.0,
                                     pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    dt = df['dt']
    df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek; df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize(); df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    df['from_end'] = df['date'].map(dict(zip(days['date'], days['from_end']))).astype(int)
    return df


def sig_S139(df): return np.isin(df['hour'].values, [22, 23])
def sig_S140(df): return (df['dow'].values == 0) & np.isin(df['hour'].values, [18, 19, 20, 21])
def sig_S142(df): return np.isin(df['dom'].values, [10, 13, 20]) & np.isin(df['hour'].values, list(range(1, 13)))


def net_of(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values if len(pt) else np.array([])
    w = int((nu > 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()) if n else 0.0; gl = float(-nu[nu <= 0].sum()) if n else 0.0
    return dict(net=float(st['net_profit']), n=n, wr=(w/n*100.0 if n else 0.0),
                pf=(gp/gl if gl > 0 else float('inf')))


def make_trades(df, sigfn, sl, tp, mh, asset):
    ls = np.nan_to_num(sigfn(df), nan=False).astype(bool)
    tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    tr['entry_time'] = pd.to_datetime(df['time'].values[tr['entry_bar'].values], unit='s')
    return tr


def overlap(tr15, tr5, asset5):
    """همپوشانیِ روزانه: معاملهٔ M5 که ورودش در روزِ معاملاتیِ یک معاملهٔ M15 باشد."""
    if tr15 is None or tr5 is None or len(tr15) == 0 or len(tr5) == 0:
        return None
    days15 = set(pd.to_datetime(tr15['entry_time']).dt.normalize())
    d5 = pd.to_datetime(tr5['entry_time']).dt.normalize()
    m = d5.isin(days15).values
    n5 = len(tr5); no = int(m.sum()); ni = n5 - no
    tr_ov = tr5[m].reset_index(drop=True); tr_in = tr5[~m].reset_index(drop=True)
    return dict(n5=n5, n_overlap=no, n_indep=ni, pct_overlap=no/n5*100.0 if n5 else 0.0,
                net_overlap=net_of(tr_ov, asset5), net_indep=net_of(tr_in, asset5))


# لایه‌های برنده S191 (بهترین کاندیدِ گیت-پاس)
WINNERS = [
    ('S139 Overnight',     sig_S139, 150, 500, 96,  100, 200, 288),  # name,sig,sl15,tp15,mh15, sl5,tp5,mh5
    ('S140 Monday',        sig_S140, 100, 300, 96,  100, 200, 288),
    ('S142 Mid-Month',     sig_S142, 100, 500, 96,  100, 200, 288),
]


def main():
    print("=" * 100)
    print("S192 — قانونِ همپوشانی + اثرِ خالصِ واقعیِ لایه‌های M5 طلا (User Note)")
    print("=" * 100, flush=True)

    df15 = assign_from_end(load('XAUUSD_M15'))
    df5 = assign_from_end(load('XAUUSD_M5'))
    start = max(df15['dt'].iloc[0], df5['dt'].iloc[0])
    end = min(df15['dt'].iloc[-1], df5['dt'].iloc[-1])
    df15c = assign_from_end(df15[(df15['dt'] >= start) & (df15['dt'] <= end)].reset_index(drop=True))
    df5c = assign_from_end(df5[(df5['dt'] >= start) & (df5['dt'] <= end)].reset_index(drop=True))
    print(f"بازهٔ مشترک: {start.date()} → {end.date()}\n")

    decisions = []
    total_incremental = 0.0
    for name, sigfn, sl15, tp15, mh15, sl5, tp5, mh5 in WINNERS:
        tr15 = make_trades(df15c, sigfn, sl15, tp15, mh15, 'XAUUSD_M15')
        tr5 = make_trades(df5c, sigfn, sl5, tp5, mh5, 'XAUUSD_M5')
        n15 = net_of(tr15, 'XAUUSD_M15'); n5 = net_of(tr5, 'XAUUSD_M5')
        ov = overlap(tr15, tr5, 'XAUUSD_M5')
        delta = n5['net'] - n15['net']   # اثرِ افزایشیِ hybrid (روشِ S189)

        print("=" * 100)
        print(f"▶ {name}")
        print(f"  M15 (بازهٔ مشترک، تنظیماتِ رکورد SL{sl15}/TP{tp15}): net={n15['net']:+,.0f} WR={n15['wr']:.1f}% n={n15['n']}")
        print(f"  M5  (بازتنظیم SL{sl5}/TP{tp5} mh{mh5}):            net={n5['net']:+,.0f} WR={n5['wr']:.1f}% n={n5['n']}")
        if ov:
            print(f"  همپوشانیِ روزانه: {ov['pct_overlap']:.1f}% ({ov['n_overlap']}/{ov['n5']})")
            print(f"    بخشِ همپوشانِ M5: net={ov['net_overlap']['net']:+,.0f} WR={ov['net_overlap']['wr']:.1f}% (n={ov['n_overlap']})")
            print(f"    بخشِ مستقلِ M5:   net={ov['net_indep']['net']:+,.0f} WR={ov['net_indep']['wr']:.1f}% (n={ov['n_indep']})")
        # تصمیم بر اساسِ درسِ S188/S189
        indep_net = ov['net_indep']['net'] if ov else 0.0
        indep_wr = ov['net_indep']['wr'] if ov else 0.0
        if delta > 0:
            # M5 در بازهٔ مشترک بهتر است ⇒ upgrade (جایگزین). اثرِ افزایشی = delta.
            action = 'upgrade_to_M5'
            incr = delta
            print(f"  ⇒ تصمیم: M5 در بازهٔ مشترک net بالاتر دارد ⇒ **ارتقا (upgrade جایگزین)**.")
            print(f"     اثرِ افزایشیِ hybrid (Δ = M5 − M15 در بازهٔ مشترک) = {incr:+,.0f}$")
        else:
            # M5 در بازهٔ مشترک بدتر است ⇒ ارتقا سود را کم می‌کند.
            # آیا بخشِ مستقلِ M5 (روزهایی که M15 معامله نکرد) به‌تنهایی سودده و WR≥40 است؟
            if indep_net > 0 and indep_wr >= 40.0 and (ov['n_indep'] >= 50):
                action = 'add_independent_part'
                incr = indep_net
                print(f"  ⇒ تصمیم: M5 کلی بدتر است اما **بخشِ مستقلِ M5 سودده و WR≥40** ⇒ افزودنِ فقط بخشِ مستقل.")
                print(f"     اثرِ افزایشی = net بخشِ مستقل = {incr:+,.0f}$")
            else:
                action = 'keep_M15'
                incr = 0.0
                print(f"  ⇒ تصمیم: M5 کلی بدتر و بخشِ مستقل هم سودده/باکیفیت نیست ⇒ **نگه‌داشتنِ M15** (M5 رد).")
        total_incremental += incr
        decisions.append(dict(layer=name, m15=n15, m5=n5, overlap=ov, delta_common=delta,
                              action=action, incremental=incr))

    print("\n" + "=" * 100)
    print("خلاصهٔ اثرِ خالصِ افزایشیِ کل (محافظه‌کارانه، روشِ hybrid S189)")
    print("=" * 100)
    for d in decisions:
        print(f"  {d['layer']:22s}: {d['action']:22s} Δ={d['incremental']:+,.0f}$")
    print(f"\n  مجموعِ اثرِ افزایشی روی رکورد = {total_incremental:+,.0f}$")

    out = dict(note='S192 XAU M5 overlap + incremental effect',
               window=[str(start.date()), str(end.date())],
               decisions=decisions, total_incremental=total_incremental)
    with open(os.path.join(RESULTS, '_s192_xau_m5_overlap.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s192_xau_m5_overlap.json")
    return out


if __name__ == '__main__':
    main()
