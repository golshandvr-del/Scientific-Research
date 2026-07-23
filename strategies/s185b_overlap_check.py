# -*- coding: utf-8 -*-
"""
S185b — آزمونِ همپوشانیِ لبهٔ «123PatternsV6» با پرتفویِ فعلیِ XAUUSD
=====================================================================
طبقِ «قانونِ همپوشانی» پروژه: پیش از افزودنِ هر لایهٔ جدید باید دقیقاً بدانیم با
کدام لایه‌ها و چند درصد همپوشانی دارد؛ و اگر همپوشانیِ معنی‌دار بود، ابتدا امکانِ
استفاده به‌عنوان «فیلترِ بهبود» بررسی شود.

روش (هم‌راستا با s168_overlap_check.py پروژه): سیگنال‌های ورودِ 123Patterns (BOTH,
target1، همان کاندیدِ PASS) را می‌گیریم و بررسی می‌کنیم چه کسری از آن‌ها در:
  * پنجره‌های زمان-محورِ موجود (Overnight 22–23، Turn-of-Month 1–3، Mid-Month 13–17،
    End-of-Month 6–8 پیش از پایان، Monday) می‌افتند؛
  * جهتِ لایه‌های LONGِ ساختاری (اکثریتِ پرتفوی LONG است).
سپس «سهمِ مستقلِ» 123Patterns (خارج از همهٔ این پنجره‌ها) را جدا و net/WR آن را
دوباره می‌سنجیم. اگر سهمِ مستقل هنوز گیت را پاس کند ⇒ لبهٔ نو؛ وگرنه ⇒ فیلتر.
"""
import sys
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.ea_tracer import (load_candles, generate_signals,
                             trace_trades, summarize)


def dt_fields(ts):
    d = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return d


def build_calendar(times):
    """برای هر کندل: hour, dow, dom, from_end (روزِ معاملاتی از پایانِ ماه)."""
    import collections
    days = {}
    order = []
    for ts in times:
        d = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        key = (d.year, d.month, d.day)
        if key not in days:
            days[key] = (d.year, d.month)
            order.append(key)
    # رتبهٔ روز در ماه از انتها
    by_month = collections.defaultdict(list)
    for key in order:
        by_month[(key[0], key[1])].append(key)
    from_end = {}
    for ym, klist in by_month.items():
        klist_sorted = sorted(klist)
        cnt = len(klist_sorted)
        for i, key in enumerate(klist_sorted):
            from_end[key] = (i + 1) - cnt - 1  # آخرین روز = -1
    return from_end


def in_time_windows(ts, from_end_map):
    d = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    key = (d.year, d.month, d.day)
    fe = from_end_map.get(key, 0)
    return {
        "overnight": d.hour in (22, 23),
        "turn_month": d.day <= 3,
        "mid_month": 13 <= d.day <= 17,
        "end_month": -8 <= fe <= -6,
        "monday": d.weekday() == 0,
    }


def main():
    sym, tf, pt = "XAUUSD", "M15", 0.01
    cd = load_candles(sym, tf)
    sig, zz = generate_signals(cd, point=pt)
    trades = trace_trades(cd, sig, sym, target=1)

    from_end_map = build_calendar(cd["time"])

    total = len(trades)
    counts = {"overnight": 0, "turn_month": 0, "mid_month": 0,
              "end_month": 0, "monday": 0}
    covered = 0
    indep_trades = []
    for t in trades:
        # زمانِ ورود به‌صورتِ unix از entry_shift
        ts = cd["time"][t["entry_shift"]]
        w = in_time_windows(ts, from_end_map)
        any_cov = False
        for k in counts:
            if w[k]:
                counts[k] += 1
                any_cov = True
        if any_cov:
            covered += 1
        else:
            indep_trades.append(t)

    print("=" * 78)
    print("S185b — همپوشانیِ 123PatternsV6 (XAUUSD BOTH t1) با پنجره‌های زمان-محورِ موجود")
    print("=" * 78)
    print(f"کلِ معاملاتِ 123Patterns: {total}")
    for k, v in counts.items():
        print(f"  در {k:12s}: {v:4d} ({v/total*100:5.1f}%)")
    print(f"\nپوششِ کلِ پنجره‌های زمان-محور: {covered} ({covered/total*100:.1f}%)")
    print(f"سهمِ مستقل (خارج از همه): {len(indep_trades)} "
          f"({len(indep_trades)/total*100:.1f}%)")

    s_all = summarize(trades)
    s_indep = summarize(indep_trades)
    print("\n--- مقایسهٔ کل vs سهمِ مستقل ---")
    print(f"  کل      : net={s_all['net']:+,.2f} WR={s_all['wr']}% n={s_all['n']}")
    print(f"  مستقل   : net={s_indep['net']:+,.2f} WR={s_indep['wr']}% "
          f"n={s_indep['n']} PF={s_indep['pf']}")

    # گیتِ walk-forward روی سهمِ مستقل
    tr = sorted(indep_trades, key=lambda t: t["entry_shift"])
    mid = len(tr) // 2
    h1 = sum(t["pnl"] for t in tr[:mid])
    h2 = sum(t["pnl"] for t in tr[mid:])
    q = len(tr) // 4
    wf = [round(sum(t["pnl"] for t in tr[i*q:(i+1)*q])) for i in range(4)]
    print(f"  مستقل halves: h1={h1:+.0f} h2={h2:+.0f} | WF={wf}")
    passes = (s_indep["net"] > 0 and s_indep["wr"] >= 40 and h1 > 0 and h2 > 0
              and all(w > 0 for w in wf) and s_indep["n"] >= 30)
    print(f"\n  سهمِ مستقل گیتِ سخت را: {'✅ پاس می‌کند ⇒ لبهٔ نو' if passes else '❌ رد می‌کند ⇒ نامزدِ فیلتر'}")


if __name__ == "__main__":
    main()
