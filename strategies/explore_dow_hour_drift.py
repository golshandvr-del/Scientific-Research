# -*- coding: utf-8 -*-
"""
explore_dow_hour_drift.py — اکتشافِ بُعدِ زمانیِ ترکیبیِ «روزِ هفته × ساعت»

قانونِ پروژه: تابعِ هدف، بیشینه‌سازیِ سودِ خالصِ XAUUSD+EURUSD است؛ WR هدف نیست،
اما WR هر لایه باید حداقل ۴۰٪ باشد.

هدفِ این اسکریپت: صرفاً *اکتشاف* است، نه استراتژیِ نهایی. لایه‌های زمانیِ موجودِ
پروژه همه *تک‌بُعدی*اند (ساعت، یا روزِ هفته، یا روزِ ماه). این‌جا بُعدِ *ترکیبیِ*
(روزِ هفته × ساعتِ روز) را اسکن می‌کنیم تا ببینیم آیا سلولی از این ماتریس یک
drift جهت‌دارِ آماری‌معنادار (t-stat بالا) دارد که هنوز به‌عنوانِ لایه استفاده نشده.

روش (بدونِ look-ahead، پیش‌تعریف‌شده):
  • بازدهِ کندلِ بعدی (open→close یا next-open→exit) را برای هر سلولِ (dow, hour) جمع می‌کنیم.
  • t-stat میانگینِ بازده را محاسبه می‌کنیم؛ سلول‌های با |t|≥4 و n≥150 گزارش می‌شوند.
  • خروجی صرفاً نامزدهای بک‌تستِ کامل است.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(asset):
    df = pd.read_csv(os.path.join(ROOT, "data", f"{asset}_M15.csv"))
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["dow"] = df["dt"].dt.dayofweek       # 0=Mon .. 6=Sun
    df["hour"] = df["dt"].dt.hour
    # بازدهِ آتی: از open کندلِ بعدی تا close همان کندلِ بعدی (یک-کندلی، forward-safe)
    df["fwd_open"] = df["open"].shift(-1)
    df["fwd_close"] = df["close"].shift(-1)
    df["fwd_ret"] = (df["fwd_close"] - df["fwd_open"])  # بر حسبِ قیمت
    # نرمال‌سازی به pip
    pip = 0.10 if asset == "XAUUSD" else 0.0001
    df["fwd_ret_pip"] = df["fwd_ret"] / pip
    return df.dropna(subset=["fwd_ret_pip"]).reset_index(drop=True)


def scan(df, asset):
    print(f"\n===== {asset}: اسکنِ ماتریسِ (روزِ هفته × ساعت) =====")
    rows = []
    for dow in range(5):  # فقط روزهای کاری Mon-Fri
        for hour in range(24):
            m = (df["dow"] == dow) & (df["hour"] == hour)
            r = df.loc[m, "fwd_ret_pip"].values
            n = len(r)
            if n < 150:
                continue
            mean = r.mean()
            std = r.std(ddof=1)
            if std <= 0:
                continue
            t = mean / (std / np.sqrt(n))
            rows.append((dow, hour, n, mean, t))
    res = pd.DataFrame(rows, columns=["dow", "hour", "n", "mean_pip", "t"])
    res = res.reindex(res["t"].abs().sort_values(ascending=False).index)
    dow_names = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
    print("  برترین سلول‌ها بر اساسِ |t| (n≥150):")
    for _, x in res.head(15).iterrows():
        direction = "LONG " if x["mean_pip"] > 0 else "SHORT"
        star = " ***" if abs(x["t"]) >= 4 else (" *" if abs(x["t"]) >= 3 else "")
        print(f"    {dow_names[int(x['dow'])]} @ {int(x['hour']):02d}UTC | "
              f"n={int(x['n']):4d} | mean={x['mean_pip']:+7.3f}pip | t={x['t']:+6.2f} | {direction}{star}")
    return res


if __name__ == "__main__":
    for asset in ["EURUSD", "XAUUSD"]:
        df = load(asset)
        scan(df, asset)
    print("\n(اکتشاف تمام شد — سلول‌های |t|≥4 نامزدِ بک‌تستِ کامل با هزینهٔ واقعی‌اند.)")
