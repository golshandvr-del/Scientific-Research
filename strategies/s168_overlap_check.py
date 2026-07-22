# -*- coding: utf-8 -*-
"""
S168 — آزمونِ همپوشانیِ زمانی با لایه‌های زمان-محورِ موجودِ XAUUSD.

هدف: اطمینان از اینکه سودِ لایهٔ جدید (High-2) صرفاً بازتولیدِ لایه‌های موجود نیست.
لایه‌های زمان-محورِ فعالِ XAUUSD long:
  S139 Overnight (22–23 UTC)، S141 Turn-of-Month (روزهای ۱–۳ ماه)،
  S142 Mid-Month، S144 End-of-Month (۶–۸ روز پیش از پایان)، S140 Monday.
اگر بخشِ کوچکی از سیگنال‌های High-2 در این پنجره‌ها بیفتد ⇒ همپوشانیِ پایین ⇒ لبهٔ مستقل.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from s168_brooks_high2_low2 import count_high2_low2

DATA = os.path.join(ROOT, "data", "XAUUSD_M15.csv")


def main():
    df = pd.read_csv(DATA)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["hour"] = df["dt"].dt.hour
    df["dow"] = df["dt"].dt.dayofweek  # دوشنبه=0
    df["dom"] = df["dt"].dt.day
    # روزِ معاملاتی از پایانِ ماه
    df["ym"] = df["dt"].dt.year * 100 + df["dt"].dt.month
    tdays = df[["dt", "ym"]].copy()
    tdays["date"] = df["dt"].dt.normalize()
    days = tdays.drop_duplicates("date").reset_index(drop=True)
    days["rank"] = days.groupby("ym").cumcount() + 1
    days["cnt"] = days.groupby("ym")["date"].transform("count")
    days["from_end"] = days["rank"] - days["cnt"] - 1
    m = dict(zip(days["date"], days["from_end"]))
    df["from_end"] = df["dt"].dt.normalize().map(m)

    long_evt, _ = count_high2_low2(df, 20, 50)
    idx = np.where(long_evt)[0]
    total = len(idx)
    sub = df.iloc[idx]

    overnight = (sub["hour"].isin([22, 23])).sum()
    turn_month = (sub["dom"] <= 3).sum()
    mid_month = (sub["dom"].between(13, 17)).sum()
    end_month = (sub["from_end"].between(-8, -6)).sum()
    monday = (sub["dow"] == 0).sum()

    covered = ((sub["hour"].isin([22, 23])) |
               (sub["dom"] <= 3) |
               (sub["dom"].between(13, 17)) |
               (sub["from_end"].between(-8, -6)) |
               (sub["dow"] == 0)).sum()

    print(f"کلِ سیگنال‌های High-2 long: {total}")
    print(f"  در پنجرهٔ Overnight (22–23 UTC): {overnight} ({overnight/total*100:.1f}%)")
    print(f"  در Turn-of-Month (روزِ ۱–۳):     {turn_month} ({turn_month/total*100:.1f}%)")
    print(f"  در Mid-Month (روزِ ۱۳–۱۷):       {mid_month} ({mid_month/total*100:.1f}%)")
    print(f"  در End-of-Month (۶–۸ پیش پایان): {end_month} ({end_month/total*100:.1f}%)")
    print(f"  در Monday:                        {monday} ({monday/total*100:.1f}%)")
    print(f"\nپوششِ کلِ همهٔ پنجره‌های زمان-محور: {covered} ({covered/total*100:.1f}%)")
    print(f"سیگنال‌های خارج از همهٔ پنجره‌ها (مستقل): {total-covered} ({(total-covered)/total*100:.1f}%)")
    if (total - covered) / total > 0.5:
        print("\n✅ اکثریتِ سیگنال‌ها خارج از پنجره‌های موجود ⇒ لبهٔ ساختاریِ مستقل.")
    else:
        print("\n⚠️ همپوشانیِ بالا با لایه‌های زمان-محورِ موجود ⇒ نیاز به بررسیِ بیشتر.")


if __name__ == "__main__":
    main()
