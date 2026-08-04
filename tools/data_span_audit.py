"""حسابرسیِ دهانهٔ تقویمیِ دادهٔ پروژه — پاسخ به «اقدامِ شمارهٔ ۱» مشاور.

پرسش: آیا بحرانِ کفایتِ نمونه از **کوتاهیِ داده** می‌آید یا از **گزینش‌گریِ سیگنال**؟
اگر داده کوتاه باشد، درمان «تاریخچهٔ بلندتر» است (توصیهٔ مشاور).
اگر داده بلند باشد و نمونه کم، درمان «قاعدهٔ کم‌گزینش‌تر» است — و توصیهٔ مشاور
روی آن کارت‌ها **بی‌اثر** خواهد بود.

این اسکریپت هیچ فرضیه‌ای نمی‌آزماید ⇒ هیچ درجهٔ آزادی‌ای خرج نمی‌کند.
"""
import os, json, datetime as dt
import pandas as pd

DATA = 'data'
OUT = 'results/_audit_data_span'
os.makedirs(OUT, exist_ok=True)

# n معاملهٔ واقعیِ کارت‌های سایت (از results/_scan_S376/*.json — بازخوانی‌شده، نه حافظه)
OBSERVED_N = {
    'XAUUSD_M5': 64, 'XAUUSD_M15': 51, 'XAUUSD_M30': 42, 'XAUUSD_H1': 74,
    'EURUSD_M5': 39, 'EURUSD_M15': 52, 'EURUSD_M30': 43, 'EURUSD_H1': 22,
    'EURUSD_M1': 41,
}

rows = []
for f in sorted(os.listdir(DATA)):
    if not f.endswith('.csv'):
        continue
    key = f[:-4]
    df = pd.read_csv(os.path.join(DATA, f), usecols=['time'])
    n = len(df)
    t0, t1 = int(df['time'].iloc[0]), int(df['time'].iloc[-1])
    span_days = (t1 - t0) / 86400.0
    span_years = span_days / 365.25
    rows.append(dict(
        card=key, bars=n,
        start=dt.datetime.utcfromtimestamp(t0).strftime('%Y-%m-%d'),
        end=dt.datetime.utcfromtimestamp(t1).strftime('%Y-%m-%d'),
        span_years=round(span_years, 2),
        trades=OBSERVED_N.get(key),
    ))

for r in rows:
    if r['trades']:
        # هر چند کندل، یک معامله؟
        r['bars_per_trade'] = round(r['bars'] / r['trades'], 1)
        # هر چند روزِ تقویمی، یک معامله؟
        r['days_per_trade'] = round(r['span_years'] * 365.25 / r['trades'], 1)
        # ضریبِ لازم برای رسیدن به سدِ ۳۵۶ معامله
        r['need_x_for_356'] = round(356.0 / r['trades'], 2)
        # سال‌های لازم اگر نرخِ سیگنال ثابت بماند
        r['years_needed_at_same_rate'] = round(r['span_years'] * 356.0 / r['trades'], 1)

with open(os.path.join(OUT, 'span_audit.json'), 'w') as fh:
    json.dump(rows, fh, indent=1, ensure_ascii=False)

hdr = f"{'card':16s} {'bars':>8s} {'start':>10s} {'end':>10s} {'yrs':>5s} {'n':>4s} {'bars/tr':>8s} {'days/tr':>8s} {'x→356':>6s} {'yrs→356':>8s}"
print(hdr); print('-' * len(hdr))
for r in rows:
    print(f"{r['card']:16s} {r['bars']:8d} {r['start']:>10s} {r['end']:>10s} "
          f"{r['span_years']:5.1f} {str(r['trades'] or '-'):>4s} "
          f"{str(r.get('bars_per_trade','-')):>8s} {str(r.get('days_per_trade','-')):>8s} "
          f"{str(r.get('need_x_for_356','-')):>6s} {str(r.get('years_needed_at_same_rate','-')):>8s}")
print(f"\nsaved → {OUT}/span_audit.json")
