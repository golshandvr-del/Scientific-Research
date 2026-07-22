# -*- coding: utf-8 -*-
"""
S165 — Liquidity Sweep + Reversal (اقتباس از منبعِ تلگرام: TM EXECUTION SUITE)

قانونِ پروژه: تابعِ هدف = بیشینه‌سازیِ سودِ خالصِ XAUUSD+EURUSD؛ WR هدف نیست اما
هر لایهٔ فعال باید WR≥۴۰٪ داشته باشد.

منبع: `Telegram-Resource/telegram_source_1/#L01f9e8 TM EXECUTION SUITE.txt`
یک اندیکاتورِ ICT (Pine v6) که هستهٔ اجرایش این است:
    ورود وقتی (Liquidity Sweep) + (بازگشت/Reversal با displacement) + (HTF Bias همسو) + (Killzone).

این اسکریپت آن هستهٔ بصری را به یک قانونِ بک‌تست‌پذیرِ بدونِ look-ahead ترجمه می‌کند:

  Liquidity Sweep (کف):  low[t] < swingLow  AND  close[t] > swingLow   (کفِ نقدینگی جارو و پس‌گرفته شد)
  Displacement:          |close[t]-open[t]| > disp_mult · ATR(14)[t]
  HTF Bias همسو (BULL):  close[t] > high[t-1]  (شکستِ سقفِ کندلِ قبل — همان تعریفِ سورس روی همان TF)
  Killzone:              hour∈London(2..5) ∪ NY(7..10)  (UTC)
  ⇒ سیگنالِ Long روی close[t]، ورود روی open[t+1] (forward-safe؛ توسطِ موتور).

متقارن برای Short (sweepِ سقف + بازگشتِ نزولی + HTF BEAR).

swingLow/swingHigh با pivot تأییدشده تعریف می‌شوند (نیازمندِ swingLen کندل در دو طرف)،
پس در لحظهٔ سیگنال کاملاً در گذشته‌اند ⇒ بدونِ look-ahead.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se

OUT = os.path.join(ROOT, "results", "_s165_liquidity_sweep_reversal.json")
CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0


def load(asset):
    cfg = se.ASSETS[asset]
    df = pd.read_csv(os.path.join(ROOT, cfg["file"]))
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["hour"] = df["dt"].dt.hour
    return df.reset_index(drop=True)


def atr(df, n=14):
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    out = pd.Series(tr).rolling(n, min_periods=1).mean().to_numpy()
    return out


def confirmed_pivots(df, swing_len):
    """آخرین pivotHigh/pivotLow تأییدشده تا کندلِ t (بدونِ look-ahead).
    یک pivot در اندیس k وقتی تأیید می‌شود که swing_len کندلِ بعدی هم دیده شده باشند،
    یعنی زودترین کندلی که می‌تواند از آن استفاده کند t = k + swing_len است.
    """
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    n = len(df)
    last_ph = np.full(n, np.nan)
    last_pl = np.full(n, np.nan)
    cur_ph = np.nan
    cur_pl = np.nan
    for t in range(n):
        k = t - swing_len  # کاندیدِ pivot که حالا تأیید می‌شود
        if k - swing_len >= 0:
            win_h = h[k - swing_len:k + swing_len + 1]
            if h[k] == win_h.max() and np.argmax(win_h) == swing_len:
                cur_ph = h[k]
            win_l = l[k - swing_len:k + swing_len + 1]
            if l[k] == win_l.min() and np.argmin(win_l) == swing_len:
                cur_pl = l[k]
        last_ph[t] = cur_ph
        last_pl[t] = cur_pl
    return last_ph, last_pl


def signals(df, asset, swing_len, disp_mult, use_htf, use_kill):
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)

    a = atr(df, 14)
    ph, pl = confirmed_pivots(df, swing_len)

    disp = np.abs(c - o) > disp_mult * a

    prev_h = np.concatenate([[h[0]], h[:-1]])
    prev_l = np.concatenate([[l[0]], l[:-1]])
    htf_bull = c > prev_h
    htf_bear = c < prev_l

    hour = df["hour"].values
    in_kill = ((hour >= 2) & (hour <= 5)) | ((hour >= 7) & (hour <= 10))

    # Liquidity sweep + reversal
    swept_low = (~np.isnan(pl)) & (l < pl) & (c > pl)   # کفِ نقدینگی جارو و پس‌گرفته شد ⇒ Long
    swept_high = (~np.isnan(ph)) & (h > ph) & (c < ph)  # سقفِ نقدینگی جارو و پس‌گرفته شد ⇒ Short

    long_sig = swept_low & disp
    short_sig = swept_high & disp
    if use_htf:
        long_sig = long_sig & htf_bull
        short_sig = short_sig & htf_bear
    if use_kill:
        long_sig = long_sig & in_kill
        short_sig = short_sig & in_kill
    return long_sig, short_sig


def run(df, asset, side, swing_len=10, disp_mult=0.5, use_htf=True, use_kill=True,
        sl=20, tp=30, max_hold=12):
    long_sig, short_sig = signals(df, asset, swing_len, disp_mult, use_htf, use_kill)
    z = np.zeros(len(df), dtype=bool)
    if side == "long":
        ls, ss = long_sig, z
    elif side == "short":
        ls, ss = z, short_sig
    else:
        ls, ss = long_sig, short_sig

    trades = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=max_hold, allow_overlap=False)
    if trades is None or len(trades) == 0:
        return None, None
    trades = trades.copy()
    trades["sl_pip"] = float(sl)
    stats, _, per_trade = se.run_capital_pertrade(
        trades, asset, initial_capital=CAPITAL, risk_pct=RISK_PCT, compounding=True
    )
    net = per_trade["net_usd"].to_numpy()
    summary = {
        "net": float(stats["net_profit"]),
        "wr": float((net > 0).mean() * 100.0) if len(net) else 0.0,
        "n": int(len(net)),
        "pf": float(stats["profit_factor"]),
        "max_dd_pct": float(stats["max_dd_pct"]),
    }
    return summary, trades


def evaluate(df, asset, side, **kw):
    """گیتِ سختِ ضدِ overfit: net>0 + هر دو نیمه + ۴ پنجرهٔ walk-forward، همه با WR≥40."""
    full, _ = run(df, asset, side, **kw)
    if full is None:
        return {"full": None, "gates": {}, "accepted": False}

    halves = []
    half = len(df) // 2
    for sub in (df.iloc[:half], df.iloc[half:]):
        s, _ = run(sub.reset_index(drop=True), asset, side, **kw)
        halves.append(s)

    windows = []
    for idx in np.array_split(np.arange(len(df)), 4):
        sub = df.iloc[idx].reset_index(drop=True)
        s, _ = run(sub, asset, side, **kw)
        windows.append(s)

    def ok(x):
        return x is not None and x["net"] > 0 and x["wr"] >= WR_FLOOR

    gates = {
        "full_net_positive": full["net"] > 0,
        "full_wr_at_least_40": full["wr"] >= WR_FLOOR,
        "both_halves_ok": all(ok(x) for x in halves),
        "all_walk_forward_ok": all(ok(x) for x in windows),
    }
    return {
        "params": kw, "full": full, "halves": halves, "walk_forward": windows,
        "gates": gates, "accepted": all(gates.values()),
    }


def main():
    results = {}
    for asset in ("XAUUSD", "EURUSD"):
        df = load(asset)
        results[asset] = {
            "rows": len(df),
            "start": str(df["dt"].iloc[0]),
            "end": str(df["dt"].iloc[-1]),
            "variants": [],
        }
        # جستجوی ازپیش‌تعریف‌شدهٔ کوچک روی هستهٔ منبع (بدونِ over-fit تهاجمی)
        for side in ("long", "short"):
            for use_htf in (True, False):
                for use_kill in (True, False):
                    for sl, tp in ((20, 30), (20, 40), (30, 45)):
                        ev = evaluate(
                            df, asset, side,
                            swing_len=10, disp_mult=0.5,
                            use_htf=use_htf, use_kill=use_kill,
                            sl=sl, tp=tp, max_hold=12,
                        )
                        if ev["full"] is not None and ev["full"]["n"] >= 20:
                            results[asset]["variants"].append({
                                "side": side, "use_htf": use_htf, "use_kill": use_kill,
                                "sl": sl, "tp": tp, **ev["full"],
                                "accepted": ev["accepted"], "gates": ev["gates"],
                            })

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # چاپِ خلاصه
    for asset, r in results.items():
        print(f"\n===== {asset} ({r['rows']} rows) =====")
        vs = sorted(r["variants"], key=lambda x: x["net"], reverse=True)
        print(f"  {len(vs)} variants with n>=20")
        for v in vs[:8]:
            flag = "✅ACCEPTED" if v["accepted"] else "  rejected"
            print(f"  {flag} {v['side']:5s} htf={int(v['use_htf'])} kill={int(v['use_kill'])} "
                  f"SL{v['sl']}/TP{v['tp']}  net=${v['net']:>10.0f}  WR={v['wr']:5.1f}%  n={v['n']:4d}  PF={v['pf']:.2f}")
    return results


if __name__ == "__main__":
    main()
