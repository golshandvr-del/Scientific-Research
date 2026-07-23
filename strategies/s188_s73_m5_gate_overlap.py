# -*- coding: utf-8 -*-
"""
s188_s73_m5_gate_overlap.py — گیتِ سختِ ضدِ overfit + قانونِ همپوشانی برای S73 روی M5
================================================================================
> # 🎯 قانونِ #۱: هدف = سودِ خالص (XAU+EUR)؛ WR≥40 فقط کفِ پذیرش.

انگیزه: S187 نشان داد لایهٔ S73 (EURUSD Session-Open Drift) روی M5 در بازهٔ مشترک
  net=+$8,911/WR=59.6% می‌دهد در مقابل M15 net=+$4,224/WR=55.3% (هر دو Long، ساعتِ ۰ UTC).
  این تنها لایه‌ای بود که طبقِ User Note روی M5 لبهٔ *بهتر* داد. حالا باید:

  (الف) گیتِ سختِ ضدِ overfit: net>0 + هر دو نیمهٔ داده مثبت + هر ۴ پنجرهٔ walk-forward مثبت.
  (ب) قانونِ همپوشانی (اجباری، همین‌جا — نه موکول به بعد):
      - چند درصد از معاملاتِ M5 با معاملاتِ M15 همپوشانِ زمانی هستند؟
      - بخشِ ناهمپوشانِ M5 چه سهمِ مستقلی دارد؟
      - آیا M5 «جایگزینِ بهترِ» همان لایه است (upgrade) یا جریانِ افزایشیِ مکمل؟
  (پ) تصمیم: بهبودِ لایهٔ موجود / لبهٔ نو / فیلتر.

روش‌شناسی: هزینهٔ واقعیِ حساب. بازهٔ مشترکِ M15/M5 برای مقایسهٔ عادلانه؛ اما گیتِ
  walk-forward روی *کلِ داده M5 موجود* هم گزارش می‌شود.
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

se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)
se.ASSETS['EURUSD_M15'] = dict(file='data/EURUSD_M15.csv', pip=0.0001, contract=100_000.0,
                               pip_value=10.0, spread_pip=1.0, comm=0.0, slip_pip=0.3)
se.ASSETS['EURUSD_M5'] = dict(file='data/EURUSD_M5.csv', pip=0.0001, contract=100_000.0,
                              pip_value=10.0, spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['dt'].dt.hour
    return df.reset_index(drop=True)


def s73_signal(df):
    """S73: hour=0 UTC + pullback سادهٔ ۵-کندلی. Long روی EURUSD."""
    hour0 = df['hour'].values == 0
    cc = df['close'].values; n = len(df)
    pull = np.zeros(n, bool); pull[5:] = cc[4:-1] < cc[0:-5]
    return hour0 & pull


def make_trades(df, asset, mh):
    ls = s73_signal(df)
    tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), 12, 12, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = 12.0
    # زمانِ ورود برای تحلیلِ همپوشانی
    tr['entry_time'] = pd.to_datetime(df['time'].values[tr['entry_bar'].values], unit='s')
    return tr


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


def gate(df, asset, mh, label):
    """گیتِ سخت: کل + دو نیمه + ۴ پنجرهٔ walk-forward."""
    tr = make_trades(df, asset, mh)
    full = net_of(tr, asset)
    n = len(df)
    half = n // 2
    trh1 = make_trades(df.iloc[:half].reset_index(drop=True), asset, mh)
    trh2 = make_trades(df.iloc[half:].reset_index(drop=True), asset, mh)
    h1 = net_of(trh1, asset); h2 = net_of(trh2, asset)
    wf = []
    for k in range(4):
        a = n * k // 4; b = n * (k + 1) // 4
        trk = make_trades(df.iloc[a:b].reset_index(drop=True), asset, mh)
        wf.append(net_of(trk, asset))
    both_halves = h1['net'] > 0 and h2['net'] > 0
    all_wf = all(w['net'] > 0 for w in wf)
    passed = full['net'] > 0 and both_halves and all_wf and full['wr'] >= 40.0
    print(f"\n[{label}] mh={mh}")
    print(f"  کل:   net={full['net']:+9,.0f}  WR={full['wr']:4.1f}%  n={full['n']:4d}  PF={full['pf']:.2f}")
    print(f"  نیمه۱: net={h1['net']:+8,.0f} (n={h1['n']})  |  نیمه۲: net={h2['net']:+8,.0f} (n={h2['n']})  → دو نیمه مثبت: {both_halves}")
    print(f"  WF:   " + " ".join(f"[{w['net']:+,.0f}]" for w in wf) + f"  → ۴/۴ مثبت: {all_wf}")
    print(f"  گیتِ سخت (net>0 & دو نیمه & ۴WF & WR≥40): {'✅ پاس' if passed else '❌ رد'}")
    return dict(full=full, h1=h1, h2=h2, wf=wf, both_halves=both_halves,
                all_wf=all_wf, passed=passed), tr


def overlap_analysis(tr15, tr5):
    """
    قانونِ همپوشانی: هر معاملهٔ M5 اگر ورودش در همان *روزِ معاملاتی* یک معاملهٔ M15 باشد
    همپوشان محسوب می‌شود (چون هر دو همان رویدادِ ساعتِ ۰ UTC را هدف می‌گیرند).
    """
    if tr15 is None or tr5 is None:
        return None
    days15 = set(pd.to_datetime(tr15['entry_time']).dt.normalize())
    d5 = pd.to_datetime(tr5['entry_time']).dt.normalize()
    overlap_mask = d5.isin(days15).values
    n5 = len(tr5)
    n_overlap = int(overlap_mask.sum())
    n_indep = n5 - n_overlap
    pct_overlap = n_overlap / n5 * 100.0 if n5 else 0.0
    # سهمِ net بخشِ مستقل (روزهایی که M15 معامله نداشت)
    tr5_indep = tr5[~overlap_mask].reset_index(drop=True)
    tr5_overlap = tr5[overlap_mask].reset_index(drop=True)
    net_indep = net_of(tr5_indep.assign(sl_pip=12.0) if len(tr5_indep) else tr5_indep, 'EURUSD_M5')
    net_overlap = net_of(tr5_overlap.assign(sl_pip=12.0) if len(tr5_overlap) else tr5_overlap, 'EURUSD_M5')
    return dict(n5=n5, n_overlap=n_overlap, n_indep=n_indep, pct_overlap=pct_overlap,
                net_indep=net_indep, net_overlap=net_overlap)


def main():
    print("=" * 96)
    print("S188 — گیتِ سختِ S73 روی M5 + قانونِ همپوشانی با نسخهٔ M15 (پاسخِ User Note)")
    print("=" * 96)

    df15 = load('EURUSD_M15')
    df5 = load('EURUSD_M5')
    start = max(df15['dt'].iloc[0], df5['dt'].iloc[0])
    end = min(df15['dt'].iloc[-1], df5['dt'].iloc[-1])
    df15w = df15[(df15['dt'] >= start) & (df15['dt'] <= end)].reset_index(drop=True)
    df5w = df5[(df5['dt'] >= start) & (df5['dt'] <= end)].reset_index(drop=True)
    print(f"بازهٔ مشترک: {start.date()} → {end.date()}  (M15={len(df15w):,}، M5={len(df5w):,})")

    # --- گیتِ سخت روی بازهٔ مشترک ---
    g15, tr15 = gate(df15w, 'EURUSD_M15', 6, 'S73 M15 (بازهٔ مشترک)')
    g5, tr5 = gate(df5w, 'EURUSD_M5', 18, 'S73 M5 (بازهٔ مشترک، mh=6×3=18)')

    # --- گیتِ سخت روی کلِ داده M5 موجود (سخت‌گیرانه‌تر) ---
    gfull, trfull = gate(df5, 'EURUSD_M5', 18, 'S73 M5 (کلِ داده M5)')

    # --- قانونِ همپوشانی ---
    print("\n" + "=" * 96)
    print("قانونِ همپوشانی — M5 در مقابل M15 (هر دو Long، رویدادِ ساعتِ ۰ UTC)")
    print("=" * 96)
    ov = overlap_analysis(tr15, tr5)
    if ov:
        print(f"  تعدادِ معاملاتِ M5: {ov['n5']}")
        print(f"  همپوشان (روزی که M15 هم معامله داشت): {ov['n_overlap']} ({ov['pct_overlap']:.1f}%)")
        print(f"  مستقل (روزی که M15 معامله نداشت):      {ov['n_indep']} ({100-ov['pct_overlap']:.1f}%)")
        print(f"  net بخشِ همپوشانِ M5: {ov['net_overlap']['net']:+,.0f} (WR {ov['net_overlap']['wr']:.1f}%)")
        print(f"  net بخشِ مستقلِ M5:   {ov['net_indep']['net']:+,.0f} (WR {ov['net_indep']['wr']:.1f}%)")

    # --- تصمیم ---
    print("\n" + "=" * 96)
    print("تصمیم")
    print("=" * 96)
    delta_common = g5['full']['net'] - g15['full']['net']
    decision = {}
    if g5['passed'] and gfull['passed'] and delta_common > 0:
        print(f"✅ M5 گیتِ سخت را در بازهٔ مشترک *و* کلِ داده پاس کرد و net بالاتری از M15 دارد.")
        print(f"   Δ در بازهٔ مشترک = {delta_common:+,.0f}$ (M5 {g5['full']['net']:+,.0f} vs M15 {g15['full']['net']:+,.0f}).")
        print(f"   ⇒ راهِ ۱ (بهبود): S73 به نسخهٔ M5 ارتقا می‌یابد (upgrade جایگزین، نه لایهٔ دوم).")
        decision = dict(action='upgrade_S73_to_M5', delta_common=delta_common,
                        m5_full_net=g5['full']['net'], m15_full_net=g15['full']['net'])
    else:
        print("❌ M5 همهٔ شروط را پاس نکرد؛ جزئیات بالا (نتیجهٔ آموزنده).")
        decision = dict(action='reject', reason='did not pass all gates or not better')

    out = dict(note='S188 S73 M5 gate + overlap', window=[str(start.date()), str(end.date())],
               gate_m15_common=g15, gate_m5_common=g5, gate_m5_full=gfull,
               overlap=ov, decision=decision)
    with open(os.path.join(RESULTS, '_s188_s73_m5.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s188_s73_m5.json")
    return out


if __name__ == '__main__':
    main()
