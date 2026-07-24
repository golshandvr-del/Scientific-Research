"""
s210b_friday_intraday_overlap.py — همپوشانیِ *ساعتیِ واقعی* لایهٔ Friday-H4 (نه روز مشترک)
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪. رکورد = +$262,519.

چرا این گام؟
  S209 همپوشانیِ «روز-تقویمیِ مشترک» را ۹۸.۵٪ گزارش کرد، اما این گمراه‌کننده است:
  S139 هر *شب* (۰۱ UTC) و Friday-Morning-Drift هر *صبحِ جمعه* (۰۰/۰۴/۰۸ UTC) فعال‌اند.
  «یک روزِ مشترک» به معنیِ «یک معاملهٔ مشترک» نیست — ساعت‌ها کاملاً جدا هستند.
  معیارِ درستِ دوباره‌شماری = همپوشانیِ **بازهٔ نگه‌داریِ واقعیِ معاملات** در محورِ زمان.

روش (دقیق، معامله‌محور):
  ۱) معاملات Friday-H4 (پنجرهٔ رکورد ۲۰۲۰+) را با بازهٔ [t_entry, t_exit] بساز.
  ۲) معاملات S139-Overnight-M15 را در همان بازه بساز (h=1، شبانه).
  ۳) یک معاملهٔ Friday «همپوشان» است اگر بازهٔ زمانی‌اش با هر معاملهٔ S139 اشتراکِ زمانی
     داشته باشد (overlap در محورِ زمانِ واقعی، نه فقط روزِ تقویمی).
  ۴) سهمِ مستقلِ ناهمپوشان را جدا گیت کن.
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
CAP, RISK = 10000.0, 1.0
FRI_HOURS = [0, 4, 8]; FSL, FTP, FMH = 200, 800, 6   # Friday-H4 (S210)
S139_HOUR = 1; S_SL, S_TP, S_MH = 100, 200, 288      # S139 overnight M5-ish (تقریب روی M15)


def load(pair, tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', f'{pair}_{tf}.csv'))
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour; df['dow'] = df['dt'].dt.dayofweek
    return df.reset_index(drop=True)


def run(df, sig, sl, tp, mh, asset='XAUUSD'):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, short, sl, tp, asset, max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def trade_intervals(df, tr):
    """[t_entry, t_exit] هر معامله را به ثانیه برمی‌گرداند (بر پایهٔ ایندکسِ ورود/خروج)."""
    t = df['time'].values
    out = []
    for _, r in tr.iterrows():
        ei = int(r['entry_bar']); xi = int(r['exit_bar'])
        ei = max(0, min(ei, len(t) - 1)); xi = max(0, min(xi, len(t) - 1))
        out.append((t[ei], t[xi]))
    return out


def gate_sub(df, mask, sl, tp, mh):
    st, _ = run(df, mask, sl, tp, mh)
    if st is None or st['n_trades'] < 20:
        return None
    n = len(df); half = n // 2
    s1, _ = run(df.iloc[:half].reset_index(drop=True), mask[:half], sl, tp, mh)
    s2, _ = run(df.iloc[half:].reset_index(drop=True), mask[half:], sl, tp, mh)
    both = (s1 and s1['net_profit'] > 0) and (s2 and s2['net_profit'] > 0)
    return dict(net=st['net_profit'], wr=st['win_rate'], n=st['n_trades'], pf=st['profit_factor'],
                h1=(s1['net_profit'] if s1 else 0), h2=(s2['net_profit'] if s2 else 0), both=both)


def main():
    print("=" * 90)
    print("s210b — همپوشانیِ ساعتیِ واقعیِ Friday-H4 (معامله‌محور، نه روزِ تقویمی)")
    print("=" * 90, flush=True)

    dfH4 = load('XAUUSD', 'H4')
    dfM5 = load('XAUUSD', 'M5')
    start = dfM5['dt'].iloc[0]
    dfH4R = dfH4[dfH4['dt'] >= start].reset_index(drop=True)

    # معاملات Friday-H4
    friSig = (dfH4R['dow'].values == 4) & np.isin(dfH4R['hour'].values, FRI_HOURS)
    stF, trF = run(dfH4R, friSig, FSL, FTP, FMH)
    print(f"\nFriday-H4 (۲۰۲۰+): net=${stF['net_profit']:+,.0f} WR={stF['win_rate']:.1f}% n={stF['n_trades']}")
    friIv = trade_intervals(dfH4R, trF)

    # معاملات S139 (overnight h1) روی M5
    s139Sig = (dfM5['hour'].values == S139_HOUR)
    stS, trS = run(dfM5, s139Sig, S_SL, S_TP, S_MH)
    print(f"S139-overnight-M5 (h{S139_HOUR}): net=${stS['net_profit']:+,.0f} WR={stS['win_rate']:.1f}% n={stS['n_trades']}")
    s139Iv = trade_intervals(dfM5, trS)
    s139Iv.sort()
    s139_starts = np.array([a for a, _ in s139Iv])
    s139_ends = np.array([b for _, b in s139Iv])

    # همپوشانیِ زمانیِ واقعی: آیا بازهٔ Friday با هر بازهٔ S139 اشتراک دارد؟
    def overlaps(a, b):
        # جستجوی سریع: هر معاملهٔ S139 که start<=b و end>=a
        lo = np.searchsorted(s139_starts, b, side='right')
        # بررسیِ بازه‌های نزدیک
        for k in range(max(0, lo - 50), min(len(s139Iv), lo + 1)):
            if s139_starts[k] <= b and s139_ends[k] >= a:
                return True
        return False

    ov_flags = [overlaps(a, b) for (a, b) in friIv]
    n_ov = sum(ov_flags); n_all = len(friIv)
    print(f"\nهمپوشانیِ ساعتیِ واقعیِ معاملات Friday با S139: {n_ov}/{n_all} = {100*n_ov/max(1,n_all):.1f}%")

    # سهمِ مستقل: ماسکِ سیگنال‌های Friday که بازه‌شان با S139 همپوشان نیست
    fri_idx = np.where(friSig)[0]
    indep_mask = np.zeros(len(dfH4R), bool)
    for j, i in enumerate(fri_idx[:len(ov_flags)]):
        if not ov_flags[j]:
            indep_mask[i] = True
    g_ind = gate_sub(dfH4R, indep_mask, FSL, FTP, FMH)
    if g_ind:
        print(f"\n[سهمِ مستقلِ ساعتیِ ناهمپوشان] net=${g_ind['net']:+,.0f} WR={g_ind['wr']:.1f}% "
              f"n={g_ind['n']} PF={g_ind['pf']:.2f} h1=${g_ind['h1']:+,.0f} h2=${g_ind['h2']:+,.0f} both={g_ind['both']}")
    else:
        print("\n[سهمِ مستقل] n<20 (معاملاتِ Friday عمدتاً در ساعاتِ صبح‌اند، جدا از S139 شبانه).")

    out = dict(friday=dict(net=stF['net_profit'], wr=stF['win_rate'], n=stF['n_trades']),
               s139=dict(net=stS['net_profit'], wr=stS['win_rate'], n=stS['n_trades']),
               intraday_overlap_pct=float(100*n_ov/max(1, n_all)),
               independent=g_ind)
    with open(os.path.join(RESULTS, '_s210b_friday_intraday_overlap.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s210b_friday_intraday_overlap.json")


if __name__ == '__main__':
    main()
