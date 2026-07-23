"""
s199_h1_overlap_check.py — قانونِ همپوشانیِ اجباری: H1-Overnight در برابر M15-Overnight رکورد
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪ کف.
> قانونِ همپوشانیِ اجباری: پیش از افزودنِ هر لایهٔ نو، باید (۱) بفهمیم با کدام لایه و
>   چند درصد همپوشانی دارد، (۲) حتی ۱٪ ناهمپوشان ارزش دارد، (۳) امکانِ استفاده از بخشِ
>   همپوشان به‌عنوان فیلتر بررسی شود.

پرسشِ این نشست:
  بهترین لایهٔ H1 (S139 Overnight h21-23، net=+$43,089 روی بازهٔ M15) با نسخهٔ M15ِ
  همان لایه (که در رکورد فعال است) چه رابطه‌ای دارد؟
    • آیا لبهٔ افزایشیِ ناهمبسته است (⇒ لایهٔ جدید/ارتقا)؟
    • یا صرفاً همان سیگنالِ M15 با رزولوشنِ درشت‌تر است (⇒ فقط یکی نگه داشته شود)؟

روش:
  ۱) هر دو نسخه (M15 و H1) را روی *بازهٔ زمانیِ یکسان* (۲۰۲۰+) اجرا می‌کنیم.
  ۲) سودِ خالصِ *روزانه* هر کدام را می‌سازیم و **همبستگیِ روزانه** را می‌سنجیم.
  ۳) همپوشانیِ *روز-معاملاتی* (آیا در همان روزها وارد می‌شوند) را درصدگیری می‌کنیم.
  ۴) طبقِ قانون: اگر همبستگی پایین (<0.35) ⇒ افزایشی؛ اگر بالا ⇒ کدام سود بیشتری دارد
     (ارتقا/جایگزینی) + بررسیِ استفاده به‌عنوان فیلتر.
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
    return df.reset_index(drop=True)


def sig_hours(df, hours):
    return np.isin(df['hour'].values, list(hours))


def run(df, hours, sl, tp, mh):
    long_sig = sig_hours(df, hours)
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short, sl, tp, 'XAUUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def daily_net(df, tr):
    """سودِ خالصِ دلاریِ روزانه با per-trade accounting."""
    if tr is None or len(tr) == 0:
        return pd.Series(dtype=float)
    # از run_capital_pertrade برای net_usd روزانه استفاده می‌کنیم
    st, eq, pt = se.run_capital_pertrade(tr, 'XAUUSD', df=df, initial_capital=CAP,
                                         risk_pct=RISK, compounding=True)
    if len(pt) == 0:
        return pd.Series(dtype=float)
    pt['day'] = pd.to_datetime(pt['dt']).dt.date
    return pt.groupby('day')['net_usd'].sum()


def trade_days(df, tr):
    """مجموعهٔ روزهایی که این لایه در آن‌ها *وارد* شده (بر اساسِ entry_bar)."""
    if tr is None or len(tr) == 0:
        return set()
    eb = np.clip(tr['entry_bar'].values.astype(int), 0, len(df) - 1)
    dt = pd.to_datetime(df['time'].values[eb], unit='s', utc=True)
    return set(pd.to_datetime(dt).date)


def main():
    print("=" * 92)
    print("s199 — قانونِ همپوشانیِ اجباری: H1-Overnight در برابر M15-Overnight (بازهٔ ۲۰۲۰+)")
    print("=" * 92, flush=True)

    dfm_full = load(DATA_M15)
    start = dfm_full['dt'].iloc[0]
    dfh = load(DATA_H1)
    dfh = dfh[dfh['dt'] >= start].reset_index(drop=True)
    dfm = dfm_full.reset_index(drop=True)
    print(f"بازهٔ مشترک: {start.date()} → {dfm['dt'].iloc[-1].date()}")
    print(f"M15: {len(dfm):,} کندل | H1: {len(dfh):,} کندل\n")

    # نسخهٔ M15 لایهٔ Overnight (پارامترِ نوعیِ رکورد: ساعاتِ 21-23، خروجِ M15)
    # طبقِ S139: M15 با mhِ بزرگ‌تر (چون کندل ریزتر). چند کاندیدِ M15 را می‌سنجیم و
    # بهترین‌شان را نمایندهٔ «نسخهٔ M15» می‌گیریم.
    print("── نسخهٔ M15 (Overnight h21-23) — جاروبِ سبک برای یافتنِ بهترین M15 ──")
    m15_cands = [(90, 300, 48), (120, 400, 64), (150, 400, 96), (150, 500, 96), (200, 600, 96)]
    best_m15 = None
    for (sl, tp, mh) in m15_cands:
        st, tr = run(dfm, [21, 22, 23], sl, tp, mh)
        if st is None:
            continue
        print(f"   M15 SL{sl}/TP{tp}/mh{mh}: net=${st['net_profit']:+,.0f} WR={st['win_rate']:.1f}% n={st['n_trades']}")
        if best_m15 is None or st['net_profit'] > best_m15[0]['net_profit']:
            best_m15 = (st, tr, (sl, tp, mh))
    stm, trm, pm = best_m15
    print(f"   ⇒ نمایندهٔ M15: SL{pm[0]}/TP{pm[1]}/mh{pm[2]}  net=${stm['net_profit']:+,.0f}  WR={stm['win_rate']:.1f}%")

    # نسخهٔ H1 برندهٔ S198: h21-23, SL150/TP400/mh24
    print("\n── نسخهٔ H1 (Overnight h21-23) — برندهٔ S198 SL150/TP400/mh24 ──")
    sth, trh = run(dfh, [21, 22, 23], 150, 400, 24)
    print(f"   H1 SL150/TP400/mh24: net=${sth['net_profit']:+,.0f}  WR={sth['win_rate']:.1f}%  n={sth['n_trades']}")

    # ── همبستگیِ روزانه ──
    dm = daily_net(dfm, trm)
    dh = daily_net(dfh, trh)
    idx = dm.index.union(dh.index)
    a = dm.reindex(idx).fillna(0.0); b = dh.reindex(idx).fillna(0.0)
    corr = float(np.corrcoef(a.values, b.values)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0

    # ── همپوشانیِ روز-معاملاتی ──
    days_m = trade_days(dfm, trm); days_h = trade_days(dfh, trh)
    inter = days_m & days_h
    ov_m = len(inter) / max(len(days_m), 1) * 100
    ov_h = len(inter) / max(len(days_h), 1) * 100

    print(f"\n{'='*92}\n📊 تحلیلِ همپوشانی:")
    print(f"   روزهای معاملاتیِ M15: {len(days_m)} | H1: {len(days_h)} | مشترک: {len(inter)}")
    print(f"   همپوشانیِ روز-معاملاتی: {ov_m:.1f}% از M15  /  {ov_h:.1f}% از H1")
    print(f"   همبستگیِ سودِ روزانه (M15↔H1): {corr:+.3f}")
    if abs(corr) < 0.35:
        print(f"   ⇒ افزایشیِ ناهمبسته (<0.35): می‌توانند هر دو نگه داشته شوند (لایهٔ نو).")
    else:
        print(f"   ⇒ هم‌بسته (≥0.35): طبقِ قانون فقط پرسودتر نگه داشته می‌شود (ارتقا/جایگزینی).")
        if sth['net_profit'] > stm['net_profit']:
            print(f"      H1 پرسودتر است (${sth['net_profit']:+,.0f} > ${stm['net_profit']:+,.0f}) "
                  f"⇒ کاندیدِ ارتقا: Δ افزایشی ≈ ${sth['net_profit']-stm['net_profit']:+,.0f}")
        else:
            print(f"      M15 پرسودتر است ⇒ ارتقا سودی ندارد.")

    out = dict(
        window_start=str(start),
        m15=dict(params=pm, net=float(stm['net_profit']), wr=float(stm['win_rate']), n=int(stm['n_trades'])),
        h1=dict(params=[150, 400, 24], net=float(sth['net_profit']), wr=float(sth['win_rate']), n=int(sth['n_trades'])),
        overlap_days_pct_of_m15=float(ov_m), overlap_days_pct_of_h1=float(ov_h),
        daily_corr=corr,
        delta_if_upgrade=float(sth['net_profit'] - stm['net_profit']),
    )
    with open(os.path.join(RESULTS, '_s199_h1_overlap.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s199_h1_overlap.json")


if __name__ == '__main__':
    main()
