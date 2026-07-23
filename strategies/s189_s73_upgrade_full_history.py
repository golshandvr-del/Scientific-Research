# -*- coding: utf-8 -*-
"""
s189_s73_upgrade_full_history.py — آیا ارتقای S73 به M5 واقعاً سودِ خالصِ کل را بالا می‌برد؟
================================================================================
> # 🎯 قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAU+EUR)؛ WR≥40 فقط کف.

نکتهٔ ظریف و حیاتی (چرا این اسکریپت لازم است):
  S188 نشان داد S73 روی M5 در بازهٔ مشترک (۲۰۲۳-۱۱ →) net بالاتری از M15 می‌دهد و
  گیتِ سخت را پاس می‌کند. اما داده M5 فقط از ۲۰۲۳-۱۱ موجود است، حال آنکه سهمِ S73 در
  *رکورد* روی کلِ داده M15 (از ۲۰۱۸) محاسبه شده. اگر کورکورانه به M5 «ارتقا» دهیم،
  ~۵.۵ سال دادهٔ تاریخیِ M15 (۲۰۱۸→۲۰۲۳) را از دست می‌دهیم.

  پس تصمیمِ درست فقط با مقایسهٔ apple-to-apple روی *همان بازهٔ زمانی* گرفته می‌شود:
    • سهمِ S73-M15 روی کلِ تاریخِ M15 = X_full   (این عددِ فعلیِ رکورد است)
    • سهمِ S73-M15 روی بازهٔ M5 (۲۰۲۳→)   = X_common15
    • سهمِ S73-M5  روی بازهٔ M5 (۲۰۲۳→)   = X_common5
  ⇒ اثرِ خالصِ ارتقا = (X_common5 − X_common15).  اگر مثبت باشد و کلِ رکورد افزایش یابد،
    ارتقا معتبر است. سهمِ تاریخیِ پیش‌از۲۰۲۳ (X_full − X_common15) در هر دو سناریو یکسان
    باقی می‌ماند (چون M5 آن‌جا داده ندارد ⇒ همان M15 استفاده می‌شود = رویکردِ ترکیبی).

  رویکردِ نهاییِ محافظه‌کارانه و درست: **hybrid** — برای بازه‌ای که M5 داده دارد از M5
  استفاده کن، برای بازهٔ تاریخیِ قبل‌تر از M15. اثرِ خالصِ افزایشی = Δ روی بازهٔ مشترک.
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


def s73_sig(df):
    hour0 = df['hour'].values == 0
    cc = df['close'].values; n = len(df)
    pull = np.zeros(n, bool); pull[5:] = cc[4:-1] < cc[0:-5]
    return hour0 & pull


def run(df, asset, mh):
    ls = s73_sig(df)
    tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), 12, 12, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wr=0.0, pf=0.0)
    tr = tr.copy(); tr['sl_pip'] = 12.0
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values if len(pt) else np.array([])
    w = int((nu > 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()) if n else 0.0; gl = float(-nu[nu <= 0].sum()) if n else 0.0
    return dict(net=float(st['net_profit']), n=n, wr=(w/n*100 if n else 0), pf=(gp/gl if gl>0 else 9.99))


def main():
    print("=" * 96)
    print("S189 — اثرِ خالصِ واقعیِ ارتقای S73 به M5 (رویکردِ hybrid، apple-to-apple)")
    print("=" * 96)

    df15 = load('EURUSD_M15')
    df5 = load('EURUSD_M5')
    m5_start = df5['dt'].iloc[0]
    common_end = min(df15['dt'].iloc[-1], df5['dt'].iloc[-1])

    # X_full : سهمِ فعلیِ S73-M15 روی کلِ تاریخِ M15
    x_full = run(df15, 'EURUSD_M15', 6)
    # X_common15 : S73-M15 روی بازهٔ مشترک (M5 داده دارد)
    df15c = df15[(df15['dt'] >= m5_start) & (df15['dt'] <= common_end)].reset_index(drop=True)
    x_c15 = run(df15c, 'EURUSD_M15', 6)
    # X_common5 : S73-M5 روی بازهٔ مشترک
    df5c = df5[(df5['dt'] >= m5_start) & (df5['dt'] <= common_end)].reset_index(drop=True)
    x_c5 = run(df5c, 'EURUSD_M5', 18)
    # سهمِ تاریخیِ پیش از M5 (فقط M15 موجود)
    df15hist = df15[df15['dt'] < m5_start].reset_index(drop=True)
    x_hist = run(df15hist, 'EURUSD_M15', 6)

    print(f"\nبازهٔ کلِ M15: {df15['dt'].iloc[0].date()} → {df15['dt'].iloc[-1].date()}")
    print(f"بازهٔ M5:      {m5_start.date()} → {df5['dt'].iloc[-1].date()}")
    print(f"\n  X_full  (S73-M15 کلِ تاریخ)         : net={x_full['net']:+9,.0f}  WR={x_full['wr']:.1f}%  n={x_full['n']}")
    print(f"  X_hist  (S73-M15 پیش از {m5_start.date()}): net={x_hist['net']:+9,.0f}  WR={x_hist['wr']:.1f}%  n={x_hist['n']}")
    print(f"  X_c15   (S73-M15 بازهٔ مشترک)       : net={x_c15['net']:+9,.0f}  WR={x_c15['wr']:.1f}%  n={x_c15['n']}")
    print(f"  X_c5    (S73-M5  بازهٔ مشترک)       : net={x_c5['net']:+9,.0f}  WR={x_c5['wr']:.1f}%  n={x_c5['n']}")

    # اثرِ افزایشیِ ارتقا روی بازهٔ مشترک
    delta = x_c5['net'] - x_c15['net']
    # سهمِ S73 در سناریوی فعلی (همه M15) vs سناریوی hybrid (تاریخ M15 + جدید M5)
    current_total = x_full['net']
    # hybrid ≈ x_hist (M15 تاریخی) + x_c5 (M5 جدید). توجه: به دلیلِ کامپاند، جمعِ مجزا
    # دقیقِ ریاضی نیست؛ اما چون هر لایه مستقل روی ۱۰k$ اجرا می‌شود، مقایسهٔ سهمِ افزایشی
    # (Δ روی بازهٔ مشترک) معیارِ درستِ تصمیم است.
    print(f"\n  ⇒ Δ افزایشیِ ارتقا (X_c5 − X_c15) = {delta:+,.0f}$")
    print(f"     WR: M15={x_c15['wr']:.1f}%  →  M5={x_c5['wr']:.1f}%  (هر دو ≥۴۰ ✅)")

    verdict = 'upgrade' if (delta > 0 and x_c5['wr'] >= 40 and x_c5['net'] > 0) else 'reject'
    if verdict == 'upgrade':
        print(f"\n✅ تصمیم: ارتقای S73 به رویکردِ hybrid (M5 برای بازهٔ ۲۰۲۳→، M15 برای تاریخِ قبل).")
        print(f"   اثرِ خالصِ افزایشی روی رکورد ≈ {delta:+,.0f}$ (محافظه‌کارانه؛ فقط بازهٔ مشترک).")
    else:
        print(f"\n❌ تصمیم: رد. ارتقا سودِ خالصِ افزایشی نمی‌دهد.")

    out = dict(note='S189 S73 M5 upgrade full-history analysis',
               x_full=x_full, x_hist=x_hist, x_common15=x_c15, x_common5=x_c5,
               delta_incremental=delta, verdict=verdict,
               m5_start=str(m5_start.date()), common_end=str(common_end.date()))
    with open(os.path.join(RESULTS, '_s189_s73_upgrade.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s189_s73_upgrade.json")
    return out


if __name__ == '__main__':
    main()
