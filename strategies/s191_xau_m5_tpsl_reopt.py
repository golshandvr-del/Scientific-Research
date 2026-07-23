# -*- coding: utf-8 -*-
"""
s191_xau_m5_tpsl_reopt.py — احیای لایه‌های زمان-محورِ طلا روی M5 با TP/SL مخصوصِ M5
================================================================================
> # 🎯 قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD). WR≥۴۰٪ فقط کفِ پذیرشِ هر لایه.

انگیزه (User Note این نشست — دقیق‌تر از S187):
  S187 لایه‌های زمان-محورِ طلا را روی M5 با **همان SL/TP دقیقِ M15** (فقط mh×3) تست کرد و
  همه با WR کمی زیرِ ۴۰٪ رد شدند (net مثبتِ بزرگ داشتند: S139 +$27.7k/WR39.5٪،
  S142 +$21.5k/WR36.2٪، …). اما User Note صراحتاً می‌گوید:
    «ممکن است هر تایم‌فریم نیاز به TP/SL متفاوت یا فیلترِ مخصوص داشته باشد.»
  دادهٔ S190 این را تأیید کرد: ATR میانهٔ M5 = ۲۱pip در برابرِ M15 = ۳۸pip. یعنی TPهای
  دورِ M15 (۳۰۰–۷۰۰pip) روی کندل‌های ریزترِ M5 دیر پُر می‌شوند ⇒ در این فاصله SL می‌خورد ⇒
  WR سقوط می‌کند. جدولِ WR خام S190: TP300→۲۶.۷٪، TP500→۱۳.۹٪ اما SL50/TP50→۵۰.۷٪.

فرضیهٔ آزمون‌پذیر:
  با **کوچک‌کردن TP و متقارن‌تر کردنِ R:R مخصوصِ M5**، همان درفت‌های زمان-محور روی M5
  می‌توانند WR≥۴۰ را پاس کنند و net مثبت بمانند ⇒ لبهٔ M5.

روش‌شناسیِ ضدِ overfit:
  • گریدِ **کوچک و منطقی** از SL/TP (مقیاسِ M5) — نه جست‌وجوی کور.
  • معیارِ انتخاب = **گیتِ سختِ کامل** (net>0 + دو نیمه مثبت + ۴/۴ walk-forward مثبت +
    WR کل≥۴۰ + n≥۵۰)، نه صرفاً بیشترین net. میان کاندیدهای گیت-پاس، بیشترین net.
  • قانونِ همپوشانی (اجباری، همین‌جا): هر لایهٔ M5 که گیت پاس کرد، همپوشانیِ روزانه‌اش با
    نسخهٔ M15 سنجیده می‌شود ⇒ upgrade/افزودن/فیلتر.
  • بازهٔ زمانی: کلِ داده M5 موجود (۲۰۲۳-۰۹ →). مقایسهٔ عادلانه با M15 روی همان بازه.

خروجی: بهترین پیکربندیِ M5 هر لایه + تصمیم + JSON در results/_s191_xau_m5_reopt.json
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

# مشخصاتِ واقعیِ حساب (single source of truth)
for tf in ('M15', 'M5'):
    se.ASSETS[f'XAUUSD_{tf}'] = dict(file=f'data/XAUUSD_{tf}.csv', pip=0.10, contract=100.0,
                                     pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    dt = df['dt']
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    df['from_end'] = df['date'].map(dict(zip(days['date'], days['from_end']))).astype(int)
    days['tom_rel'] = days.apply(lambda r: int(r['from_end']) if r['from_end'] >= -2
                                 else int(r['rank_in_month']), axis=1)
    df['tom_rel'] = df['date'].map(dict(zip(days['date'], days['tom_rel']))).astype(int)
    return df


# ---- توابعِ سیگنالِ لایه‌های زمان-محورِ طلا (تایم‌فریم-اگنوستیک) ----
def sig_S139(df):  # Overnight: hour∈{22,23}
    return np.isin(df['hour'].values, [22, 23])

def sig_S140(df):  # Monday: dow=0 & hour∈{18..21}
    return (df['dow'].values == 0) & np.isin(df['hour'].values, [18, 19, 20, 21])

def sig_S141(df):  # Turn-of-Month: tom_rel=1 & hour∈{7..12}
    return (df['tom_rel'].values == 1) & np.isin(df['hour'].values, list(range(7, 13)))

def sig_S142(df):  # Mid-Month: dom∈{10,13,20} & hour∈{1..12}
    return np.isin(df['dom'].values, [10, 13, 20]) & np.isin(df['hour'].values, list(range(1, 13)))

def sig_S144(df):  # End-of-Month Pre-End: from_end∈{-6,-7,-8} & hour∈{19..23}
    return np.isin(df['from_end'].values, [-6, -7, -8]) & np.isin(df['hour'].values, [19, 20, 21, 22, 23])


LAYERS = [
    ('S139 Overnight',     sig_S139, 150, 500, 96),   # (name, sig, sl_M15, tp_M15, mh_M15)
    ('S140 Monday',        sig_S140, 100, 300, 96),
    ('S141 Turn-of-Month', sig_S141, 100, 700, 96),
    ('S142 Mid-Month',     sig_S142, 100, 500, 96),
    ('S144 End-of-Month',  sig_S144, 150, 300, 96),
]

# گریدِ M5 مخصوص (مقیاسِ M5 طبقِ S190: ATR~21pip؛ TP نزدیک‌تر و متقارن‌تر)
# نکته: SL/TP بر حسبِ pip؛ mh بر حسبِ کندلِ M5 (سه‌برابرِ معادلِ M15 برای مدتِ ساعتیِ یکسان).
M5_GRID = [
    # (sl, tp, mh_M5)
    (40, 40, 108), (40, 60, 108), (50, 50, 108), (50, 75, 144), (50, 100, 144),
    (60, 60, 144), (60, 90, 144), (75, 75, 144), (75, 100, 216), (80, 120, 216),
    (100, 100, 216), (100, 150, 288), (100, 200, 288),
]


def net_of(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK,
                                        compounding=True)
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


def hard_gate(df, sigfn, sl, tp, mh, asset):
    """گیتِ سخت: کل + دو نیمه + ۴ پنجرهٔ walk-forward + WR≥40 + n≥50."""
    tr = make_trades(df, sigfn, sl, tp, mh, asset)
    full = net_of(tr, asset)
    n = len(df); half = n // 2
    h1 = net_of(make_trades(df.iloc[:half].reset_index(drop=True), sigfn, sl, tp, mh, asset), asset)
    h2 = net_of(make_trades(df.iloc[half:].reset_index(drop=True), sigfn, sl, tp, mh, asset), asset)
    wf = []
    for k in range(4):
        a = n*k//4; b = n*(k+1)//4
        wf.append(net_of(make_trades(df.iloc[a:b].reset_index(drop=True), sigfn, sl, tp, mh, asset), asset))
    both = h1['net'] > 0 and h2['net'] > 0
    allwf = all(w['net'] > 0 for w in wf)
    passed = (full['net'] > 0 and both and allwf and full['wr'] >= 40.0 and full['n'] >= 50)
    return dict(sl=sl, tp=tp, mh=mh, full=full, h1=h1, h2=h2, wf=wf,
                both_halves=both, all_wf=allwf, passed=passed), tr


def main():
    print("=" * 100)
    print("S191 — احیای لایه‌های زمان-محورِ طلا روی M5 با TP/SL مخصوصِ M5 (User Note)")
    print("قانونِ #۱: هدف = سودِ خالص؛ WR≥40 کفِ پذیرش. انتخاب = گیتِ سختِ کامل، نه صرفاً بیشترین net.")
    print("=" * 100, flush=True)

    df15 = assign_from_end(load('XAUUSD_M15'))
    df5 = assign_from_end(load('XAUUSD_M5'))
    start = max(df15['dt'].iloc[0], df5['dt'].iloc[0])
    end = min(df15['dt'].iloc[-1], df5['dt'].iloc[-1])
    df15c = assign_from_end(df15[(df15['dt'] >= start) & (df15['dt'] <= end)].reset_index(drop=True))
    df5c = assign_from_end(df5[(df5['dt'] >= start) & (df5['dt'] <= end)].reset_index(drop=True))
    print(f"بازهٔ مشترک: {start.date()} → {end.date()}  (M15={len(df15c):,}، M5={len(df5c):,})\n")

    results = []
    for name, sigfn, sl15, tp15, mh15 in LAYERS:
        # مبنای M15 (بازهٔ مشترک) با تنظیماتِ اصلیِ لایه
        base15, tr15 = hard_gate(df15c, sigfn, sl15, tp15, mh15*1, 'XAUUSD_M15')
        print(f"{'='*100}\n▶ {name}")
        print(f"  مبنا M15 (بازهٔ مشترک): net={base15['full']['net']:+,.0f} WR={base15['full']['wr']:.1f}% "
              f"n={base15['full']['n']} | SL{sl15}/TP{tp15}")
        # جست‌وجوی گریدِ M5
        cands = []
        for sl, tp, mh in M5_GRID:
            g, tr = hard_gate(df5c, sigfn, sl, tp, mh, 'XAUUSD_M5')
            cands.append((g, tr))
            flag = '✅' if g['passed'] else '  '
            print(f"    {flag} M5 SL{sl:3d}/TP{tp:3d} mh{mh:3d}: net={g['full']['net']:+9,.0f} "
                  f"WR={g['full']['wr']:4.1f}% n={g['full']['n']:4d} PF={g['full']['pf'] if g['full']['pf']!=float('inf') else 99:.2f} "
                  f"| 2half={g['both_halves']} 4wf={g['all_wf']}")
        passed_cands = [(g, tr) for g, tr in cands if g['passed']]
        best = None
        if passed_cands:
            best = max(passed_cands, key=lambda x: x[0]['full']['net'])
            bg = best[0]
            print(f"  ⭐ بهترین کاندیدِ گیت-پاس M5: SL{bg['sl']}/TP{bg['tp']} mh{bg['mh']} "
                  f"⇒ net={bg['full']['net']:+,.0f} WR={bg['full']['wr']:.1f}%")
        else:
            print(f"  ❌ هیچ کاندیدِ M5 گیتِ سخت را پاس نکرد.")
        results.append(dict(layer=name, sl15=sl15, tp15=tp15, base15=base15,
                            best_m5=(best[0] if best else None),
                            n_passed=len(passed_cands)))

    # خلاصهٔ تصمیم
    print("\n" + "=" * 100)
    print("خلاصهٔ تصمیم — کدام لایه‌ها روی M5 با TP/SL بازتنظیم‌شده گیت پاس کردند؟")
    print("=" * 100)
    winners = [r for r in results if r['best_m5'] is not None]
    for r in results:
        if r['best_m5']:
            b = r['best_m5']
            print(f"  ✅ {r['layer']:22s}: M5 SL{b['sl']}/TP{b['tp']} net={b['full']['net']:+,.0f} "
                  f"WR={b['full']['wr']:.1f}% (مبنا M15 net={r['base15']['full']['net']:+,.0f})")
        else:
            print(f"  ❌ {r['layer']:22s}: هیچ پیکربندیِ M5 گیت پاس نکرد")

    out = dict(note='S191 XAU M5 TP/SL re-optimization', window=[str(start.date()), str(end.date())],
               grid=M5_GRID, results=results, n_winners=len(winners))
    with open(os.path.join(RESULTS, '_s191_xau_m5_reopt.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s191_xau_m5_reopt.json")
    return out


if __name__ == '__main__':
    main()
