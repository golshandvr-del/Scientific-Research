"""
s209_friday_h4_overlap.py — قانونِ همپوشانیِ اجباری: Friday-H4 در برابر پرتفویِ طلا
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪ کف. رکورد = +$252,471.
> قانونِ همپوشانیِ اجباری (هر سه بند پیش از رفتن به مرحلهٔ بعد):
>   (۱) با کدام لایه و چند درصد همپوشانی دارد؟
>   (۲) حتی ۱٪ ناهمپوشان ارزش دارد؟ (بخشِ مستقل سودده است؟)
>   (۳) امکانِ استفاده از بخشِ همپوشان به‌عنوان فیلتر بررسی شود.

کاندید: **Friday_all H4** (SL200/TP800/mh6، net=+$8,492، WR ۴۸.۶٪، هر دو نیمه + WF ۴/۴).

پرسشِ کلیدی: آیا سودِ «روزِ جمعه» از قبل توسطِ لایه‌های زمان-محورِ رکورد گرفته شده؟
  لایه‌های رکورد عمدتاً روی M15 و بر اساسِ *ساعت/روزِ ماه* فعال‌اند، نه *روزِ هفته*.
  پس ذاتاً Friday یک محورِ ناهمبسته است — اما باید عددی اثبات شود.

روش (مثلِ S199):
  ۱) Friday-H4 و لایه‌های زمان-محورِ M15 را روی *بازهٔ زمانیِ یکسانِ M15* اجرا می‌کنیم.
  ۲) سودِ خالصِ *روزانه* هر کدام + همبستگیِ روزانه.
  ۳) همپوشانیِ *روز-معاملاتی*: چند درصد از روزهای معاملهٔ Friday-H4 با روزهای هر لایهٔ
     دیگر مشترک است.
  ۴) حکم: همبستگیِ پایین (<0.35) و همپوشانیِ کم ⇒ لبهٔ افزایشیِ مستقل.
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


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    df['dom'] = df['dt'].dt.day
    df['dim'] = df['dt'].dt.days_in_month
    return df.reset_index(drop=True)


def run(df, long_sig, sl, tp, mh):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short, sl, tp, 'XAUUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def daily_net(df, tr):
    if tr is None or len(tr) == 0:
        return pd.Series(dtype=float)
    st, eq, pt = se.run_capital_pertrade(tr, 'XAUUSD', df=df, initial_capital=CAP,
                                         risk_pct=RISK, compounding=True)
    if len(pt) == 0:
        return pd.Series(dtype=float)
    pt['day'] = pd.to_datetime(pt['dt']).dt.date
    return pt.groupby('day')['net_usd'].sum()


def trade_days(df, tr):
    if tr is None or len(tr) == 0:
        return set()
    eb = np.clip(tr['entry_bar'].values.astype(int), 0, len(df) - 1)
    dt = pd.to_datetime(df['time'].values[eb], unit='s', utc=True)
    return set(pd.to_datetime(dt).date)


# ---------- سیگنال‌ها ----------
def fri_all(df):
    return (df['dow'].values == 4) & np.isin(df['hour'].values, [0, 4, 8, 12, 16, 20])

# نسخه‌های M15 لایه‌های زمان-محورِ رکورد (تقریب برای همپوشانی روز-معاملاتی)
def m15_overnight(df):   # S139
    return np.isin(df['hour'].values, [21, 22, 23])
def m15_monday(df):      # S140
    return (df['dow'].values == 0) & np.isin(df['hour'].values, [18, 19, 20])
def m15_turnofmonth(df): # S141
    return np.isin(df['dom'].values, [1, 2, 3]) & np.isin(df['hour'].values, range(7, 13))
def m15_midmonth(df):    # S142
    return np.isin(df['dom'].values, [10, 13, 20]) & np.isin(df['hour'].values, range(1, 13))
def m15_endofmonth(df):  # S144
    dom = df['dom'].values; dim = df['dim'].values
    m = np.zeros(len(df), bool)
    for rel in [-6, -7, -8]:
        m |= (dom == (dim + rel + 1))
    return m & np.isin(df['hour'].values, [19, 20, 21, 22, 23])


def main():
    print("=" * 92)
    print("s209 — قانونِ همپوشانیِ اجباری: Friday-H4 در برابر لایه‌های زمان-محورِ M15")
    print("=" * 92, flush=True)

    dfh = load(DATA_H4)
    dfm = load(DATA_M15)
    # بازهٔ مشترک (M15 از ۲۰۲۰؛ H4 را به همان بازه محدود می‌کنیم برای مقایسهٔ منصفانه)
    start = dfm['dt'].iloc[0]
    dfh_aligned = dfh[dfh['dt'] >= start].reset_index(drop=True)
    print(f"بازهٔ مشترکِ مقایسه: {start.date()} → {dfm['dt'].iloc[-1].date()}")
    print(f"  H4 در این بازه: {len(dfh_aligned):,} کندل   M15: {len(dfm):,} کندل\n")

    # Friday-H4 روی بازهٔ کامل (برای گزارشِ اصلی) و روی بازهٔ هم‌تراز (برای همپوشانی)
    st_full, tr_full = run(dfh, fri_all(dfh), 200, 800, 6)
    print(f"Friday-H4 (بازهٔ کامل ۲۰۱۱+): net=${st_full['net_profit']:+,.0f}  "
          f"WR={st_full['win_rate']:.1f}%  n={st_full['n_trades']}")

    st_fri, tr_fri = run(dfh_aligned, fri_all(dfh_aligned), 200, 800, 6)
    print(f"Friday-H4 (بازهٔ هم‌ترازِ ۲۰۲۰+): net=${st_fri['net_profit']:+,.0f}  "
          f"WR={st_fri['win_rate']:.1f}%  n={st_fri['n_trades']}\n")

    dn_fri = daily_net(dfh_aligned, tr_fri)
    td_fri = trade_days(dfh_aligned, tr_fri)

    print("بند ۱ — همپوشانی با هر لایهٔ زمان-محورِ M15 (روز-معاملاتی + همبستگیِ روزانه):")
    print(f"  {'لایه':<22}{'n_days':>8}{'اشتراک':>9}{'٪ازFri':>9}{'corr':>9}")
    layers = {
        'S139_Overnight': m15_overnight,
        'S140_Monday': m15_monday,
        'S141_TurnOfMonth': m15_turnofmonth,
        'S142_MidMonth': m15_midmonth,
        'S144_EndOfMonth': m15_endofmonth,
    }
    results = {}
    union_days = set()
    for name, fn in layers.items():
        stx, trx = run(dfm, fn(dfm), 150, 400, 48)
        tdx = trade_days(dfm, trx)
        union_days |= tdx
        inter = td_fri & tdx
        pct = 100.0 * len(inter) / max(len(td_fri), 1)
        dnx = daily_net(dfm, trx)
        idx = dn_fri.index.intersection(dnx.index)
        if len(idx) >= 5:
            corr = float(np.corrcoef(dn_fri.reindex(idx).fillna(0),
                                     dnx.reindex(idx).fillna(0))[0, 1])
        else:
            corr = 0.0
        print(f"  {name:<22}{len(tdx):>8}{len(inter):>9}{pct:>8.1f}%{corr:>+9.3f}")
        results[name] = dict(n_days=len(tdx), inter=len(inter), pct_of_fri=pct, corr=corr)

    # همپوشانی با اجتماعِ کلِ لایه‌های زمان-محور
    inter_union = td_fri & union_days
    pct_union = 100.0 * len(inter_union) / max(len(td_fri), 1)
    print(f"\n  ⇒ اجتماعِ همهٔ زمان-محورها: {len(union_days)} روز؛ "
          f"اشتراک با Friday = {len(inter_union)} روز = {pct_union:.1f}٪ از روزهای Friday.")

    # بند ۲: سهمِ مستقلِ Friday (روزهایی که هیچ لایهٔ دیگری وارد نشده)
    indep_days = td_fri - union_days
    print(f"\nبند ۲ — سهمِ مستقلِ Friday (روزهای غیرِ همپوشان): {len(indep_days)} روز "
          f"({100.0*len(indep_days)/max(len(td_fri),1):.1f}٪).")
    if len(indep_days) > 0:
        indep_net = dn_fri[dn_fri.index.isin(indep_days)].sum()
        overlap_net = dn_fri[dn_fri.index.isin(inter_union)].sum()
        print(f"  net روی روزهای مستقل  = ${indep_net:+,.0f}")
        print(f"  net روی روزهای همپوشان = ${overlap_net:+,.0f}")
        print(f"  ⇒ کلِ Friday-H4 (هم‌تراز) = ${dn_fri.sum():+,.0f}")

    out = dict(
        friday_full=dict(net=st_full['net_profit'], wr=st_full['win_rate'], n=st_full['n_trades']),
        friday_aligned=dict(net=st_fri['net_profit'], wr=st_fri['win_rate'], n=st_fri['n_trades']),
        per_layer=results, n_fri_days=len(td_fri), union_days=len(union_days),
        inter_union=len(inter_union), pct_union=pct_union,
        indep_days=len(indep_days),
        indep_net=float(dn_fri[dn_fri.index.isin(indep_days)].sum()) if len(indep_days) else 0.0,
        overlap_net=float(dn_fri[dn_fri.index.isin(inter_union)].sum()) if len(inter_union) else 0.0,
    )
    with open(os.path.join(RESULTS, '_s209_friday_overlap.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s209_friday_overlap.json")


if __name__ == '__main__':
    main()
