# -*- coding: utf-8 -*-
"""
ea_tracer.py — «شبیه‌سازِ ردیابِ رباتِ MT4/MT5» (EA Behavior Tracer)
=====================================================================
پاسخِ مستقیم به User Note:
    «یه فایل ex4-ex5 رو انتخاب کنی، بعد یه ابزار شبیه‌ساز ردیاب براش بسازی؛ یعنی
     این ابزار ربات رو اجرا میکنه (داده‌های غنی داریم) بعد اطلاعاتِ کاملِ همهٔ
     معاملاتِ انجام‌شده توسط اون رو به ما میده: محلِ ورود و خروج و tp/sl و حجم.
     بعد ما طبقِ اون می‌تونیم به منطقِ پشتِ ربات دست پیدا کنیم!»

--------------------------------------------------------------------------------
چرا «بازپیاده‌سازیِ منطق» و نه «اجرای مستقیمِ باینری»؟
    فایل‌های .ex4/.ex5 باینریِ کامپایل‌شده و رمزنگاری‌شده‌اند (strings آن‌ها هیچ
    رشتهٔ منطقیِ قابلِ خواندنی ندارد) و اجرای واقعی‌شان فقط درونِ ترمینالِ
    MetaTrader روی ویندوز ممکن است — که در این سندباکسِ لینوکسی/Cloudflare وجود
    ندارد و decompiler هم نداریم. راهِ علمیِ معادل که *دقیقاً همان هدف* (کشفِ
    منطقِ پشتِ ربات + استخراجِ همهٔ معاملات) را محقق می‌کند:
      1) منطقِ رباتِ باینری را از سورسِ قابلِ خواندنِ همراهش استخراج می‌کنیم،
      2) همان منطق را «tick-by-bar» روی دادهٔ غنیِ خودمان اجرا (شبیه‌سازی) می‌کنیم،
      3) هر معامله را از ورود تا خروج ردیابی و لاگِ کامل تولید می‌کنیم.

فایلِ هدفِ این نسخه:
    «123PatternsV6.ex4»  (منبع: Telegram-Resource/telegram_source_1/
     1-2-3-pattern-day-trader/ — نویسنده: Robert Dee, 2010, ForexFactory)
    نوع: اندیکاتورِ سیگنال‌دهندهٔ الگوی 1-2-3 (ZigZag-based) + خطوطِ Target.
    سورسِ .mq4 در همان بسته موجود است ⇒ منطق ۱۰۰٪ شفاف و قابلِ بازتولید.

منطقِ استخراج‌شده از سورس (123PatternsV6.mq4):
    * یک ZigZag(depth, dev=5, backstep=3) نقاطِ چرخشِ سقف/کف را می‌سازد.
    * سه نقطهٔ متوالیِ چرخش = «1، 2، 3» الگو:
        - صعودی: 1=prevlow, 2=lasthigh, 3=lastlow  → retrace = (3-2)/(1-2)
        - نزولی: 1=prevhigh, 2=lastlow, 3=lasthigh → retrace = (3-2)/(1-2)
      باید RetraceDepthMin < retrace < RetraceDepthMax باشد (پیش‌فرض 0.4..1.0).
    * سیگنالِ خرید وقتی صادر می‌شود که کندل خطِ سقف (نقطهٔ 2) را بشکند:
        Low[t] < line  AND  Close[t] > line  (و آن خط قبلاً شکسته نشده باشد)
      و متقارن برای فروش با خطِ کف.
    * اهداف: range = |two - three| ؛ Target1 = two + range*1.5 ؛ Target2 = two + range*3.0
      (برای فروش با علامتِ منفی).

مدیریتِ معامله در ردیاب (چون اندیکاتور خودش سفارش نمی‌گذارد، منطقِ استانداردِ
معامله‌گر روی همین سیگنال‌ها اعمال می‌شود — دقیقاً همان چیزی که کاربر ترسیم
می‌کند: «TP/SL/حجم»):
    * ورود: در close همان کندلِ شکست (سیگنال).
    * TP: Target1 (پیش‌فرض) — قابلِ تغییر به Target2.
    * SL: نقطهٔ 3 الگو (ساختاریِ منطقی: زیرِ کفِ اخیر برای خرید، بالای سقف برای فروش).
    * حجم: از مدلِ ریسکِ ثابتِ درصدی محاسبه می‌شود (پیش‌فرض ۱٪ ریسک روی SL).
    * خروج: هرکدام از TP/SL که زودتر لمس شود (با فرضِ محافظه‌کارانهٔ «SL اول» وقتی
      یک کندل هر دو را در بر می‌گیرد ⇒ ضدِ خوش‌بینی).

خروجی: یک جدولِ کاملِ معاملات + خلاصهٔ آماری، و اختیاراً ذخیرهٔ CSV/JSON.

استفاده:
    python tools/ea_tracer.py --symbol XAUUSD --tf M15
    python tools/ea_tracer.py --symbol XAUUSD --tf M15 --target 2 --limit 40000 --save
"""

import os
import sys
import json
import argparse
import csv
from datetime import datetime, timezone

# مسیرِ ریشهٔ پروژه تا بتوانیم engine/ را ایمپورت کنیم
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.market_spec import get_spec  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data")


# ---------------------------------------------------------------------------
# 1) بارگذاریِ داده
# ---------------------------------------------------------------------------
def load_candles(symbol, tf, limit=None):
    """کندل‌های OHLCV را از data/<SYMBOL>_<TF>.csv می‌خواند."""
    path = os.path.join(DATA_DIR, f"{symbol}_{tf}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"دادهٔ موردنظر یافت نشد: {path}")
    times, o, h, l, c, v = [], [], [], [], [], []
    with open(path, "r", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            times.append(int(float(row["time"])))
            o.append(float(row["open"]))
            h.append(float(row["high"]))
            l.append(float(row["low"]))
            c.append(float(row["close"]))
            v.append(float(row.get("volume", 0) or 0))
    if limit and len(times) > limit:
        times, o, h, l, c, v = (x[-limit:] for x in (times, o, h, l, c, v))
    return {"time": times, "open": o, "high": h, "low": l, "close": c, "volume": v}


# ---------------------------------------------------------------------------
# 2) ZigZag — بازپیاده‌سازیِ دقیقِ الگوریتمِ استانداردِ MetaTrader
#    (ExtDepth, ExtDeviation, ExtBackstep). خروجی: آرایه‌ای هم‌طول با کندل‌ها
#    که در نقاطِ چرخش مقدارِ High/Low و در بقیه 0 دارد.
# ---------------------------------------------------------------------------
def zigzag(high, low, depth=12, deviation=5, backstep=3, point=0.01):
    n = len(high)
    zz = [0.0] * n
    hi_buf = [0.0] * n
    lo_buf = [0.0] * n
    dev_points = deviation * point

    last_low = 0.0
    last_high = 0.0

    for i in range(depth, n):
        # --- کمترین کفِ پنجرهٔ depth ---
        window_low = min(low[i - depth + 1:i + 1])
        if window_low == last_low:
            window_low = 0.0
        else:
            last_low = window_low
            if low[i] - window_low > dev_points:
                window_low = 0.0
            else:
                for b in range(1, backstep + 1):
                    if i - b >= 0 and lo_buf[i - b] != 0.0 and lo_buf[i - b] > window_low:
                        lo_buf[i - b] = 0.0
        if low[i] == window_low:
            lo_buf[i] = low[i]
        else:
            lo_buf[i] = 0.0

        # --- بیشترین سقفِ پنجرهٔ depth ---
        window_high = max(high[i - depth + 1:i + 1])
        if window_high == last_high:
            window_high = 0.0
        else:
            last_high = window_high
            if window_high - high[i] > dev_points:
                window_high = 0.0
            else:
                for b in range(1, backstep + 1):
                    if i - b >= 0 and hi_buf[i - b] != 0.0 and hi_buf[i - b] < window_high:
                        hi_buf[i - b] = 0.0
        if high[i] == window_high:
            hi_buf[i] = high[i]
        else:
            hi_buf[i] = 0.0

    # --- تلفیقِ بافرها به یک خطِ ZigZag متناوب (سقف/کف) ---
    last_type = 0     # 1=high , -1=low
    last_idx = -1
    for i in range(n):
        hv = hi_buf[i]
        lv = lo_buf[i]
        if hv != 0.0 and lv != 0.0:
            # هر دو در یک کندل — سقف را اولویت می‌دهیم (رفتارِ رایجِ MT4)
            zz[i] = hv
            continue
        if hv != 0.0:
            if last_type == 1 and last_idx >= 0:
                # دو سقفِ متوالی: قوی‌ترین را نگه دار
                if zz[last_idx] < hv:
                    zz[last_idx] = 0.0
                    zz[i] = hv
                    last_idx = i
            else:
                zz[i] = hv
                last_type = 1
                last_idx = i
        elif lv != 0.0:
            if last_type == -1 and last_idx >= 0:
                if zz[last_idx] > lv:
                    zz[last_idx] = 0.0
                    zz[i] = lv
                    last_idx = i
            else:
                zz[i] = lv
                last_type = -1
                last_idx = i
    return zz, hi_buf, lo_buf


# ---------------------------------------------------------------------------
# 3) تولیدِ سیگنال‌های 1-2-3 و breakout (منطقِ 123PatternsV6.mq4)
#    خروجی: فهرستِ سیگنال‌ها با فیلدهای shift, dir, price, two, three, t1, t2
# ---------------------------------------------------------------------------
def generate_signals(cd, depth=12, dev=5, backstep=3,
                     retrace_min=0.4, retrace_max=1.0,
                     t1_mult=1.5, t2_mult=3.0, point=0.01,
                     show_all_breaks=False, pattern_only=True):
    high, low, close, times = cd["high"], cd["low"], cd["close"], cd["time"]
    n = len(high)
    zz, hi_buf, lo_buf = zigzag(high, low, depth, dev, backstep, point)

    signals = []
    # حالتِ ماشینِ چرخش‌ها مثلِ سورس
    firsthigh = firstlow = lasthigh = lastlow = prevhigh = prevlow = 0.0
    firsthightime = firstlowtime = lasthightime = lastlowtime = 0
    prevhightime = prevlowtime = 0
    broken_upper = None
    broken_lower = None
    upper_line = 0.0
    lower_line = 0.0

    for shift in range(n):
        # به‌روزرسانیِ خطوط (پله‌ای، مثلِ UpperLine[shift]=UpperLine[shift+1])
        z = zz[shift]
        if z != 0.0 and z == high[shift]:
            upper_line = high[shift]
            firsthigh, firsthightime = prevhigh, prevhightime
            prevhigh, prevhightime = lasthigh, lasthightime
            lasthigh, lasthightime = z, times[shift]
        if z != 0.0 and z == low[shift]:
            lower_line = low[shift]
            firstlow, firstlowtime = prevlow, prevlowtime
            prevlow, prevlowtime = lastlow, lastlowtime
            lastlow, lastlowtime = z, times[shift]

        if shift == 0:
            continue

        # ---------- BULLISH BREAK ABOVE #2 (الگوی 1-2-3 صعودی) ----------
        one = prevlow
        two = lasthigh
        twotime = lasthightime
        if twotime == times[shift]:
            two = prevhigh
        three = lastlow
        retrace = None
        if (one - two) != 0:
            retrace = (three - two) / (one - two)
        if (two > 0 and three > 0 and retrace is not None and
                retrace_min < retrace < retrace_max and
                broken_upper != upper_line and upper_line > 0 and
                low[shift] < upper_line and close[shift] > upper_line):
            rng = abs(two - three)
            t1 = two + rng * t1_mult
            t2 = two + rng * t2_mult
            signals.append({
                "shift": shift, "time": times[shift], "dir": "BUY",
                "kind": "123", "entry": close[shift],
                "two": two, "three": three, "retrace": retrace,
                "t1": t1, "t2": t2,
            })
            broken_upper = upper_line

        # ---------- BULLISH BREAK (بدونِ الگو) ----------
        elif (show_all_breaks and not pattern_only and
              broken_upper != upper_line and upper_line > 0 and
              low[shift] < upper_line and close[shift] > upper_line):
            rng = upper_line - lower_line
            signals.append({
                "shift": shift, "time": times[shift], "dir": "BUY",
                "kind": "break", "entry": close[shift],
                "two": upper_line, "three": lower_line, "retrace": None,
                "t1": upper_line + rng * t1_mult, "t2": upper_line + rng * t2_mult,
            })
            broken_upper = upper_line

        # ---------- BEARISH BREAK BELOW #2 (الگوی 1-2-3 نزولی) ----------
        one = prevhigh
        two = lastlow
        twotime = lastlowtime
        if twotime == times[shift]:
            two = prevlow
        three = lasthigh
        retrace = None
        if (one - two) != 0:
            retrace = (three - two) / (one - two)
        if (two > 0 and three > 0 and retrace is not None and
                retrace_min < retrace < retrace_max and
                broken_lower != lower_line and lower_line > 0 and
                high[shift] > lower_line and close[shift] < lower_line):
            rng = abs(two - three)
            t1 = two - rng * t1_mult
            t2 = two - rng * t2_mult
            signals.append({
                "shift": shift, "time": times[shift], "dir": "SELL",
                "kind": "123", "entry": close[shift],
                "two": two, "three": three, "retrace": retrace,
                "t1": t1, "t2": t2,
            })
            broken_lower = lower_line

        elif (show_all_breaks and not pattern_only and
              broken_lower != lower_line and lower_line > 0 and
              high[shift] > lower_line and close[shift] < lower_line):
            rng = upper_line - lower_line
            signals.append({
                "shift": shift, "time": times[shift], "dir": "SELL",
                "kind": "break", "entry": close[shift],
                "two": lower_line, "three": upper_line, "retrace": None,
                "t1": lower_line - rng * t1_mult, "t2": lower_line - rng * t2_mult,
            })
            broken_lower = lower_line

    return signals, zz


# ---------------------------------------------------------------------------
# 4) موتورِ مدیریتِ معامله (Tracer) — هر سیگنال را از ورود تا خروج دنبال می‌کند
#    و «همهٔ اطلاعاتِ معامله» را (طبقِ درخواستِ کاربر) تولید می‌کند.
# ---------------------------------------------------------------------------
def trace_trades(cd, signals, symbol, target=1,
                 risk_pct=1.0, initial_capital=10000.0,
                 sl_source="three", max_hold_bars=192):
    """
    برای هر سیگنال یک معامله می‌سازد و کندل‌به‌کندل جلو می‌رود تا TP/SL/زمان.
    خروجی: فهرستِ dictهای معامله با فیلدهای کامل (ورود/خروج/TP/SL/حجم/سود).
    """
    spec = get_spec(symbol)
    contract = spec["contract_size"]
    cost_price = spec["cost_price"]       # هزینهٔ رفت‌وبرگشت بر حسبِ قیمت (یکبار)
    min_lot = spec["min_lot"]

    high, low, close, times = cd["high"], cd["low"], cd["close"], cd["time"]
    n = len(high)

    trades = []
    equity = initial_capital
    open_until = -1   # اجازه نمی‌دهیم معاملاتِ هم‌پوشان باز شوند (مثلِ رفتارِ تک‌معامله)

    for sg in signals:
        s = sg["shift"]
        if s <= open_until:
            continue  # هنوز معاملهٔ قبلی باز است
        entry = sg["entry"]
        direction = sg["dir"]
        tp = sg["t1"] if target == 1 else sg["t2"]

        # --- SL ساختاری ---
        if sl_source == "three":
            sl = sg["three"]
        else:  # فاصلهٔ متقارن با TP
            sl = entry - (tp - entry)

        # اطمینان از سمتِ درستِ SL/TP
        if direction == "BUY":
            if not (sl < entry < tp):
                continue
        else:
            if not (tp < entry < sl):
                continue

        sl_dist = abs(entry - sl)   # فاصلهٔ SL بر حسبِ قیمت
        if sl_dist <= 0:
            continue

        # --- حجم (لات) از ریسکِ درصدی ---
        risk_dollar = equity * (risk_pct / 100.0)
        # ضررِ SL بر حسبِ دلار برای ۱ لات = (sl_dist + cost_price) * contract
        loss_per_lot = (sl_dist + cost_price) * contract
        lots = risk_dollar / loss_per_lot if loss_per_lot > 0 else min_lot
        lots = max(min_lot, round(lots, 2))

        # --- شبیه‌سازیِ کندل‌به‌کندل تا خروج ---
        exit_price = None
        exit_time = None
        exit_reason = None
        exit_shift = None
        end = min(n, s + 1 + max_hold_bars)
        for j in range(s + 1, end):
            hj, lj = high[j], low[j]
            if direction == "BUY":
                hit_sl = lj <= sl
                hit_tp = hj >= tp
            else:
                hit_sl = hj >= sl
                hit_tp = lj <= tp
            if hit_sl and hit_tp:
                # هر دو در یک کندل ⇒ محافظه‌کارانه SL اول
                exit_price, exit_reason = sl, "SL(both)"
                exit_time, exit_shift = times[j], j
                break
            if hit_sl:
                exit_price, exit_reason = sl, "SL"
                exit_time, exit_shift = times[j], j
                break
            if hit_tp:
                exit_price, exit_reason = tp, "TP"
                exit_time, exit_shift = times[j], j
                break
        if exit_price is None:
            # پایانِ پنجرهٔ نگهداری ⇒ خروج در close
            jj = end - 1
            exit_price, exit_reason = close[jj], "TIME"
            exit_time, exit_shift = times[jj], jj

        # --- سود/زیانِ دلاری (با کسرِ هزینهٔ رفت‌وبرگشت) ---
        if direction == "BUY":
            move = exit_price - entry
        else:
            move = entry - exit_price
        pnl = (move - cost_price) * contract * lots
        equity += pnl

        trades.append({
            "signal_kind": sg["kind"],
            "dir": direction,
            "entry_time": iso(sg["time"]),
            "entry_shift": s,
            "entry_price": round(entry, 5),
            "tp": round(tp, 5),
            "sl": round(sl, 5),
            "lots": lots,
            "exit_time": iso(exit_time),
            "exit_shift": exit_shift,
            "exit_price": round(exit_price, 5),
            "exit_reason": exit_reason,
            "hold_bars": exit_shift - s,
            "retrace": round(sg["retrace"], 3) if sg.get("retrace") is not None else None,
            "pnl": round(pnl, 2),
            "equity": round(equity, 2),
        })
        open_until = exit_shift

    return trades


def iso(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# 5) خلاصهٔ آماری
# ---------------------------------------------------------------------------
def summarize(trades, initial_capital=10000.0):
    if not trades:
        return {"n": 0, "net": 0.0, "wr": 0.0, "pf": 0.0}
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    net = sum(t["pnl"] for t in trades)
    wr = 100.0 * len(wins) / len(trades)
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    by_reason = {}
    for t in trades:
        by_reason[t["exit_reason"]] = by_reason.get(t["exit_reason"], 0) + 1
    by_dir = {"BUY": 0, "SELL": 0}
    for t in trades:
        by_dir[t["dir"]] += 1
    return {
        "n": len(trades), "wins": len(wins), "losses": len(losses),
        "net": round(net, 2), "wr": round(wr, 2), "pf": round(pf, 3),
        "gross_win": round(gross_win, 2), "gross_loss": round(gross_loss, 2),
        "avg_win": round(gross_win / len(wins), 2) if wins else 0.0,
        "avg_loss": round(gross_loss / len(losses), 2) if losses else 0.0,
        "final_equity": round(initial_capital + net, 2),
        "by_reason": by_reason, "by_dir": by_dir,
    }


# ---------------------------------------------------------------------------
# 6) CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="EA Behavior Tracer — 123PatternsV6")
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--tf", default="M15")
    ap.add_argument("--limit", type=int, default=None, help="فقط N کندلِ آخر")
    ap.add_argument("--depth", type=int, default=12, help="ZigZag depth")
    ap.add_argument("--dev", type=int, default=5, help="ZigZag deviation")
    ap.add_argument("--backstep", type=int, default=3)
    ap.add_argument("--rmin", type=float, default=0.4, help="RetraceDepthMin")
    ap.add_argument("--rmax", type=float, default=1.0, help="RetraceDepthMax")
    ap.add_argument("--t1", type=float, default=1.5)
    ap.add_argument("--t2", type=float, default=3.0)
    ap.add_argument("--target", type=int, default=1, choices=[1, 2])
    ap.add_argument("--risk", type=float, default=1.0, help="risk %% per trade")
    ap.add_argument("--sl", default="three", choices=["three", "symmetric"])
    ap.add_argument("--maxhold", type=int, default=192)
    ap.add_argument("--breaks", action="store_true", help="شاملِ break-only (نه فقط 123)")
    ap.add_argument("--show", type=int, default=15, help="چند معاملهٔ اول چاپ شود")
    ap.add_argument("--save", action="store_true", help="ذخیرهٔ CSV/JSON در results/")
    args = ap.parse_args()

    point = 0.01 if args.symbol.upper() == "XAUUSD" else 0.00001
    cd = load_candles(args.symbol, args.tf, args.limit)
    print(f"دادهٔ بارگذاری‌شده: {args.symbol} {args.tf} — {len(cd['time'])} کندل "
          f"({iso(cd['time'][0])} → {iso(cd['time'][-1])})")

    signals, zz = generate_signals(
        cd, depth=args.depth, dev=args.dev, backstep=args.backstep,
        retrace_min=args.rmin, retrace_max=args.rmax,
        t1_mult=args.t1, t2_mult=args.t2, point=point,
        show_all_breaks=args.breaks, pattern_only=(not args.breaks),
    )
    n_pivots = sum(1 for z in zz if z != 0.0)
    print(f"نقاطِ چرخشِ ZigZag: {n_pivots} | سیگنال‌های تولیدشده: {len(signals)}")

    trades = trace_trades(
        cd, signals, args.symbol, target=args.target,
        risk_pct=args.risk, sl_source=args.sl, max_hold_bars=args.maxhold,
    )
    summ = summarize(trades)

    print("\n" + "=" * 78)
    print(f"🤖 ردیابِ ربات «123PatternsV6» روی {args.symbol} {args.tf} "
          f"(target={args.target}, risk={args.risk}%, SL={args.sl})")
    print("=" * 78)
    print(f"  تعدادِ معاملات : {summ['n']}   (BUY={summ['by_dir']['BUY']} / "
          f"SELL={summ['by_dir']['SELL']})")
    print(f"  سودِ خالص      : {summ['net']:+,.2f}$")
    print(f"  Win-Rate       : {summ['wr']:.2f}%   (کفِ پروژه = ۴۰٪)")
    print(f"  Profit Factor  : {summ['pf']}")
    print(f"  میانگینِ برد/باخت: +{summ['avg_win']} / -{summ['avg_loss']}")
    print(f"  دلایلِ خروج    : {summ['by_reason']}")
    print(f"  اکوییتیِ نهایی : {summ['final_equity']:,.2f}$  (شروع ۱۰٬۰۰۰$)")

    if trades:
        print("\n  --- نمونهٔ معاملات (ورود/خروج/TP/SL/حجم/سود) ---")
        head = ["#", "dir", "entry_time", "entry", "tp", "sl", "lots",
                "exit_time", "exit", "reason", "pnl"]
        print("  " + " | ".join(f"{h:>10}" for h in head))
        for i, t in enumerate(trades[:args.show], 1):
            print("  " + " | ".join(f"{str(x):>10}" for x in [
                i, t["dir"], t["entry_time"], t["entry_price"], t["tp"],
                t["sl"], t["lots"], t["exit_time"], t["exit_price"],
                t["exit_reason"], t["pnl"]]))

    if args.save:
        os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
        tag = f"{args.symbol}_{args.tf}_123patterns_t{args.target}"
        csv_path = os.path.join(ROOT, "results", f"_tracer_{tag}.csv")
        json_path = os.path.join(ROOT, "results", f"_tracer_{tag}.json")
        with open(csv_path, "w", newline="") as f:
            if trades:
                wr = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
                wr.writeheader()
                wr.writerows(trades)
        with open(json_path, "w") as f:
            json.dump({"summary": summ, "trades": trades}, f, indent=2)
        print(f"\n  💾 ذخیره شد: {csv_path}\n  💾 ذخیره شد: {json_path}")

    return summ


if __name__ == "__main__":
    main()
