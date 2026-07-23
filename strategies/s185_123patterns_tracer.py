# -*- coding: utf-8 -*-
"""
s185_123patterns_tracer.py — اعتبارسنجیِ گیتِ سختِ لبهٔ «123PatternsV6»
========================================================================
منبع: فایلِ باینریِ 123PatternsV6.ex4 (Telegram-Resource) — منطق از سورسِ همراهش
(123PatternsV6.mq4، نویسنده Robert Dee 2010) استخراج و در tools/ea_tracer.py
بازپیاده‌سازی شد. این اسکریپت خروجیِ ردیاب را زیرِ «گیتِ سختِ ضدِ overfit» پروژه
می‌بَرَد:
    net>0  AND  هر دو نیمهٔ داده مثبت  AND  هر ۴ پنجرهٔ walk-forward مثبت
    AND  WR کلِ لایه ≥ ۴۰٪.
همچنین همپوشانیِ زمانی-جهتیِ روزانه با پرتفویِ فعلی را (به‌صورتِ تقریبی) گزارش می‌کند.

هدف طبقِ قانونِ #۱ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)، با کفِ WR≥۴۰٪.
"""
import sys
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.ea_tracer import (load_candles, generate_signals,
                             trace_trades, summarize)


def gate_check(trades, label):
    """گیتِ سخت: net>0 + هر دو نیمه مثبت + هر ۴ پنجرهٔ WF مثبت + WR≥40."""
    s = summarize(trades)
    if s["n"] < 30:
        return False, s, f"n<30 (n={s['n']}) — نمونهٔ ناکافی"
    # نیمه‌ها بر اساسِ ترتیبِ زمانیِ ورود
    tr = sorted(trades, key=lambda t: t["entry_shift"])
    mid = len(tr) // 2
    h1 = sum(t["pnl"] for t in tr[:mid])
    h2 = sum(t["pnl"] for t in tr[mid:])
    # ۴ پنجره
    q = len(tr) // 4
    wins = [sum(t["pnl"] for t in tr[i*q:(i+1)*q]) for i in range(4)]
    reasons = []
    ok = True
    if s["net"] <= 0:
        ok = False; reasons.append(f"net≤0 ({s['net']})")
    if s["wr"] < 40:
        ok = False; reasons.append(f"WR<40 ({s['wr']}%)")
    if not (h1 > 0 and h2 > 0):
        ok = False; reasons.append(f"نیمه‌ها: h1={h1:.0f} h2={h2:.0f}")
    if not all(w > 0 for w in wins):
        ok = False; reasons.append(f"WF: {[round(w) for w in wins]}")
    detail = (f"net={s['net']:+.0f} WR={s['wr']}% PF={s['pf']} n={s['n']} | "
              f"h1={h1:+.0f} h2={h2:+.0f} | WF={[round(w) for w in wins]}")
    return ok, s, (("✅ PASS " if ok else "❌ FAIL ") + " ; ".join(reasons) + " | " + detail)


def run(symbol, tf, point, target=1, risk=1.0, direction=None,
        rmin=0.4, rmax=1.0, depth=12):
    cd = load_candles(symbol, tf)
    sig, zz = generate_signals(cd, point=point, retrace_min=rmin,
                               retrace_max=rmax, depth=depth)
    tr = trace_trades(cd, sig, symbol, target=target, risk_pct=risk)
    if direction:
        tr = [t for t in tr if t["dir"] == direction]
    return tr


def main():
    print("=" * 80)
    print("S185 — گیتِ سختِ لبهٔ «123PatternsV6» (منبعِ ex4/تلگرام)")
    print("=" * 80)

    configs = [
        ("XAUUSD", "M15", 0.01, 1, None),
        ("XAUUSD", "M15", 0.01, 1, "BUY"),
        ("XAUUSD", "M15", 0.01, 1, "SELL"),
        ("EURUSD", "M15", 0.00001, 1, None),
        ("EURUSD", "M15", 0.00001, 1, "BUY"),
        ("EURUSD", "M15", 0.00001, 1, "SELL"),
    ]
    results = {}
    for sym, tf, pt, tgt, d in configs:
        tr = run(sym, tf, pt, target=tgt, direction=d)
        label = f"{sym} {d or 'BOTH'} t{tgt}"
        ok, s, msg = gate_check(tr, label)
        results[label] = (ok, s)
        print(f"\n[{label}]")
        print("  " + msg)

    # جمعِ سودِ خالصِ لایه‌هایی که گیت را پاس کردند (BOTH برای هر ارز)
    print("\n" + "=" * 80)
    net_sum = 0.0
    for sym in ("XAUUSD", "EURUSD"):
        ok, s = results[f"{sym} BOTH t1"]
        status = "✅" if ok else "❌"
        print(f"  {sym} BOTH t1: {status} net={s['net']:+,.2f} WR={s['wr']}%")
        if ok:
            net_sum += s["net"]
    print(f"\n  جمعِ سودِ خالصِ لایه‌های PASS (XAUUSD+EURUSD): {net_sum:+,.2f}$")
    print("=" * 80)


if __name__ == "__main__":
    main()
