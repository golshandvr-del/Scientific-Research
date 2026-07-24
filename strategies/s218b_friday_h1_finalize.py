"""
s218b_friday_h1_finalize.py — نهایی‌سازیِ Friday-Morning H1 + سهمِ مستقلِ ساعتی
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪. رکورد قبلی = +$262,519.

کاندیدِ برندهٔ S218: XAUUSD-H1 RAW-FriMorning (جمعه × ساعاتِ ۰۰..۱۲ UTC)
  TP600/SL300/mh8، net +$2,018، WR 50.2٪، n=315، هر دو نیمه مثبت، WF min +$69 (گیت‌پاس).

قانونِ همپوشانیِ اجباری (سه بند):
  (۱) همپوشانیِ ساعتیِ واقعی با اجتماعِ لایه‌های LONGِ فعالِ طلا (به‌ویژه S139 شبانه،
      S211 M15، S214 M5، زمان-محورها) — معامله‌محور در محورِ زمان.
  (۲) سهمِ مستقلِ ناهمپوشان جداگانه گیت شود (کشف کلیدی: پایداریِ سهمِ مستقل).
  (۳) اگر همپوشانی بالا بود، امکانِ استفاده به‌عنوان فیلتر بررسی شود.

تصمیم بر پایهٔ *پایداریِ سهمِ مستقل* گرفته می‌شود، نه net خام.
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
FRI_HOURS = list(range(0, 12)); FSL, FTP, FMH = 300, 600, 8   # کاندیدِ H1


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


def intervals(df, tr):
    t = df['time'].values; out = []
    for _, r in tr.iterrows():
        ei = int(r['entry_bar']); xi = int(r['exit_bar'])
        ei = max(0, min(ei, len(t)-1)); xi = max(0, min(xi, len(t)-1))
        out.append((t[ei], t[xi]))
    return out


def gate_sub(df, mask, sl, tp, mh, min_n=25):
    st, _ = run(df, mask, sl, tp, mh)
    if st is None or st['n_trades'] < min_n:
        return None
    n = len(df); half = n//2
    s1, _ = run(df.iloc[:half].reset_index(drop=True), mask[:half], sl, tp, mh)
    s2, _ = run(df.iloc[half:].reset_index(drop=True), mask[half:], sl, tp, mh)
    wf = []
    for k in range(4):
        a = k*(n//4); b = n if k == 3 else (k+1)*(n//4)
        sk, _ = run(df.iloc[a:b].reset_index(drop=True), mask[a:b], sl, tp, mh)
        wf.append(sk['net_profit'] if sk else 0.0)
    both = (s1 and s1['net_profit'] > 0) and (s2 and s2['net_profit'] > 0)
    ok = st['net_profit'] > 0 and both and min(wf) > 0 and st['win_rate'] >= 40
    return dict(net=st['net_profit'], wr=st['win_rate'], n=st['n_trades'], pf=st['profit_factor'],
                h1=(s1['net_profit'] if s1 else 0), h2=(s2['net_profit'] if s2 else 0),
                wf=wf, wf_min=min(wf), both=both, ok=ok)


def main():
    print("=" * 92)
    print("s218b — نهایی‌سازیِ Friday-Morning H1 + قانونِ همپوشانیِ اجباری")
    print(f"کاندید: XAUUSD-H1 جمعه×h{FRI_HOURS[0]}..{FRI_HOURS[-1]} TP{FTP}/SL{FSL}/mh{FMH}")
    print("=" * 92, flush=True)

    dfH1 = load('XAUUSD', 'H1')
    dfM5 = load('XAUUSD', 'M5')
    start = dfM5['dt'].iloc[0]
    dfH1R = dfH1[dfH1['dt'] >= start].reset_index(drop=True)

    friSig = (dfH1R['dow'].values == 4) & np.isin(dfH1R['hour'].values, FRI_HOURS)
    g_raw = gate_sub(dfH1R, friSig, FSL, FTP, FMH, min_n=30)
    print(f"\n[Friday-H1 خام] net=${g_raw['net']:+,.0f} WR={g_raw['wr']:.1f}% n={g_raw['n']} "
          f"h1=${g_raw['h1']:+,.0f} h2=${g_raw['h2']:+,.0f} WFmin=${g_raw['wf_min']:+,.0f} ok={g_raw['ok']}")
    stF, trF = run(dfH1R, friSig, FSL, FTP, FMH)
    friIv = intervals(dfH1R, trF)

    # اجتماعِ لایه‌های LONGِ طلا در محورِ زمان (نمایندهٔ اصلی = S139 شبانه با نگه‌داریِ طولانی)
    # S139: h1، SL100/TP200/mh288 روی M5 (طولانی‌ترین نگه‌داری ⇒ بیشترین احتمالِ تلاقی)
    s139Sig = (dfM5['hour'].values == 1)
    stS, trS = run(dfM5, s139Sig, 100, 200, 288)
    s139Iv = intervals(dfM5, trS); s139Iv.sort()
    s139_s = np.array([a for a, _ in s139Iv]); s139_e = np.array([b for _, b in s139Iv])

    # S211: triple-SMA M15 LONG (day-session) — نمایندهٔ لایه‌های روز
    dfM15 = load('XAUUSD', 'M15')
    dfM15R = dfM15[dfM15['dt'] >= start].reset_index(drop=True)

    def overlaps_s139(a, b):
        lo = np.searchsorted(s139_s, b, side='right')
        for k in range(max(0, lo-60), min(len(s139Iv), lo+1)):
            if s139_s[k] <= b and s139_e[k] >= a:
                return True
        return False

    ov = [overlaps_s139(a, b) for (a, b) in friIv]
    n_ov = sum(ov); n_all = len(friIv)
    print(f"\n[همپوشانیِ ساعتیِ واقعی با S139] {n_ov}/{n_all} = {100*n_ov/max(1,n_all):.1f}%")

    fri_idx = np.where(friSig)[0]
    indep_mask = np.zeros(len(dfH1R), bool)
    for j, i in enumerate(fri_idx[:len(ov)]):
        if not ov[j]:
            indep_mask[i] = True
    g_ind = gate_sub(dfH1R, indep_mask, FSL, FTP, FMH, min_n=20)
    if g_ind:
        print(f"\n[سهمِ مستقلِ ناهمپوشان] net=${g_ind['net']:+,.0f} WR={g_ind['wr']:.1f}% n={g_ind['n']} "
              f"PF={g_ind['pf']:.2f} h1=${g_ind['h1']:+,.0f} h2=${g_ind['h2']:+,.0f} "
              f"WF={['%+.0f'%x for x in g_ind['wf']]} WFmin=${g_ind['wf_min']:+,.0f}")
        print(f"    گیتِ سخت روی سهمِ مستقل: {'✅ پاس' if g_ind['ok'] else '❌ رد'}")
    else:
        print("\n[سهمِ مستقل] n<20 ⇒ لبهٔ مستقلِ کافی ندارد.")

    out = dict(raw=g_raw, overlap_pct=float(100*n_ov/max(1, n_all)),
               independent=g_ind, n_all=n_all, n_overlap=n_ov)
    with open(os.path.join(RESULTS, '_s218b_friday_h1_finalize.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s218b_friday_h1_finalize.json")

    print("\n" + "=" * 92)
    if g_ind and g_ind['ok']:
        print(f"تصمیم: لبهٔ مستقلِ Friday-H1 پایدار است ⇒ پذیرش. Δ محافظه‌کارانه = +${g_ind['net']:,.0f}")
    else:
        print("تصمیم: سهمِ مستقل گیت را پاس نمی‌کند ⇒ به‌عنوانِ لایهٔ رکوردِ سودِ خالص افزوده نمی‌شود.")
        print("       (اما برای User Note: در جمعه صبح باید سیگنال/شفافیتِ صریح به کاربر داده شود.)")


if __name__ == '__main__':
    main()
