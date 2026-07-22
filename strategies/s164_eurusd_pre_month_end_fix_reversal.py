# -*- coding: utf-8 -*-
"""
S164 — EURUSD Pre-Month-End Fix Reversal

قانون پروژه: تابع هدف، بیشینه‌سازی سود خالص XAUUSD+EURUSD است؛ WR هدف نیست،
اما WR هر لایه باید حداقل ۴۰٪ باشد.

فرضیهٔ ازپیش‌تعریف‌شده:
سه روز معاملاتی مانده به پایان ماه، در ساعت ۱۳ UTC و پیرامون جریان‌های بازمتوازن‌سازی
قبل از London Fix، EURUSD یک drift نزولی کوتاه‌مدت دارد. سیگنال پس از بسته‌شدن کندل
فعال می‌شود و ورود روی open کندل بعدی است.

پیکربندی نهایی بر مبنای ناحیهٔ پایدار پارامترها انتخاب می‌شود، نه بیشینهٔ منفرد:
Short؛ SL=15 pip؛ TP=20 pip؛ max_hold=12 کندل M15.
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

DATA = os.path.join(ROOT, "data", "EURUSD_M15.csv")
OUT = os.path.join(ROOT, "results", "_s164_eurusd_pre_month_end_fix_reversal.json")
ASSET = "EURUSD"
CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0
SL_PIP = 15
TP_PIP = 20
MAX_HOLD = 12

# مشخصات واقعی و محافظه‌کارانهٔ EURUSD در پروژه: کمیسیون صفر، 1 pip spread، 0.3 slippage.
se.ASSETS[ASSET].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load_data():
    df = pd.read_csv(DATA)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["date"] = df["dt"].dt.normalize()
    df["ym"] = df["dt"].dt.year * 100 + df["dt"].dt.month
    df["hour"] = df["dt"].dt.hour

    trading_days = df[["date", "ym"]].drop_duplicates("date").reset_index(drop=True)
    trading_days["rank"] = trading_days.groupby("ym").cumcount() + 1
    trading_days["count"] = trading_days.groupby("ym")["date"].transform("count")
    # آخرین روز=-1، روز قبل=-2، سه روز معاملاتی مانده به پایان=-3.
    trading_days["from_end"] = trading_days["rank"] - trading_days["count"] - 1
    mapping = dict(zip(trading_days["date"], trading_days["from_end"]))
    df["from_end"] = df["date"].map(mapping).astype(int)
    return df.reset_index(drop=True)


def signals(df):
    short_signal = (df["from_end"].values == -3) & (df["hour"].values == 13)
    return np.zeros(len(df), dtype=bool), short_signal


def run(df, sl=SL_PIP, tp=TP_PIP, max_hold=MAX_HOLD):
    long_signal, short_signal = signals(df)
    trades = se.simulate_trades(
        df,
        long_signal,
        short_signal,
        sl,
        tp,
        ASSET,
        max_hold=max_hold,
        allow_overlap=False,
    )
    if trades is None or len(trades) == 0:
        return None, None, None
    trades = trades.copy()
    trades["sl_pip"] = float(sl)
    stats, _, per_trade = se.run_capital_pertrade(
        trades,
        ASSET,
        initial_capital=CAPITAL,
        risk_pct=RISK_PCT,
        compounding=True,
    )
    net = per_trade["net_usd"].to_numpy()
    summary = {
        "net": float(stats["net_profit"]),
        "wr": float((net > 0).mean() * 100.0),
        "n": int(len(net)),
        "wins": int((net > 0).sum()),
        "losses": int((net <= 0).sum()),
        "pf": float(stats["profit_factor"]),
        "max_dd_pct": float(stats["max_dd_pct"]),
        "sharpe": float(stats["sharpe"]),
    }
    return summary, trades, per_trade


def daily_pnl(df, trades):
    if trades is None or len(trades) == 0:
        return pd.Series(dtype=float)
    bars = np.clip(trades["exit_bar"].to_numpy(dtype=int), 0, len(df) - 1)
    days = pd.to_datetime(df["time"].iloc[bars].to_numpy(), unit="s", utc=True).normalize()
    pnl = pd.Series(trades["pnl_pip"].to_numpy(), index=days)
    return pnl.groupby(level=0).sum()


def correlation_with_existing(df, candidate_trades):
    """همبستگی روزانه با دو لایهٔ فعلی EURUSD؛ منطق پایه برای آزمون dedup."""
    z = np.zeros(len(df), dtype=bool)

    # S73: ساعت ۰ + buy-the-dip، SL12/TP12/hold6.
    close = df["close"].to_numpy()
    pullback = np.zeros(len(df), dtype=bool)
    pullback[5:] = close[4:-1] < close[:-5]
    s73_long = (df["hour"].values == 0) & pullback
    s73 = se.simulate_trades(df, s73_long, z, 12, 12, ASSET, max_hold=6, allow_overlap=False)

    # S143: Mid-Month پایه؛ ساعت‌ها و روزهای آن از نامزد S164 جدا هستند.
    s143_long = np.isin(df["dt"].dt.day.values, [3, 9, 20]) & np.isin(
        df["hour"].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]
    )
    s143 = se.simulate_trades(df, s143_long, z, 20, 40, ASSET, max_hold=96, allow_overlap=False)

    candidate = daily_pnl(df, candidate_trades)
    out = {}
    for name, trades in (("S73", s73), ("S143", s143)):
        other = daily_pnl(df, trades)
        joined = pd.concat([candidate, other], axis=1).fillna(0.0)
        corr = 0.0 if len(joined) < 10 or joined.iloc[:, 0].std() == 0 or joined.iloc[:, 1].std() == 0 else joined.iloc[:, 0].corr(joined.iloc[:, 1])
        out[name] = float(corr)
    return out


def parameter_plateau(df):
    """همسایگی کوچک و ازپیش‌تعریف‌شده برای ردِ قلهٔ تک‌پارامتری."""
    rows = []
    for sl in (12, 15, 20):
        for tp in (15, 20, 30):
            for hold in (8, 12):
                s, _, _ = run(df, sl, tp, hold)
                rows.append({"sl": sl, "tp": tp, "hold": hold, **s})
    return rows


def main():
    df = load_data()
    full, trades, _ = run(df)

    windows = []
    for i, index in enumerate(np.array_split(np.arange(len(df)), 4), start=1):
        sub = df.iloc[index].reset_index(drop=True)
        s, _, _ = run(sub)
        windows.append({"window": i, **s})

    half = len(df) // 2
    halves = []
    for i, sub in enumerate((df.iloc[:half], df.iloc[half:]), start=1):
        s, _, _ = run(sub.reset_index(drop=True))
        halves.append({"half": i, **s})

    correlations = correlation_with_existing(df, trades)
    plateau = parameter_plateau(df)
    plateau_pass = [r for r in plateau if r["net"] > 0 and r["wr"] >= WR_FLOOR]

    gates = {
        "full_net_positive": full["net"] > 0,
        "full_wr_at_least_40": full["wr"] >= WR_FLOOR,
        "both_halves_net_positive": all(x["net"] > 0 for x in halves),
        "both_halves_wr_at_least_40": all(x["wr"] >= WR_FLOOR for x in halves),
        "all_walk_forward_net_positive": all(x["net"] > 0 for x in windows),
        "all_walk_forward_wr_at_least_40": all(x["wr"] >= WR_FLOOR for x in windows),
        "low_correlation": all(abs(x) < 0.35 for x in correlations.values()),
        "parameter_plateau": len(plateau_pass) >= int(np.ceil(len(plateau) * 0.75)),
    }

    out = {
        "strategy": "S164 EURUSD Pre-Month-End Fix Reversal",
        "signal": {"direction": "short", "from_end": -3, "hour_utc": 13},
        "exit": {"sl_pip": SL_PIP, "tp_pip": TP_PIP, "max_hold_m15": MAX_HOLD},
        "account": {"capital": CAPITAL, "risk_pct": RISK_PCT, "spread_pip": 1.0, "slippage_pip": 0.3, "commission": 0.0},
        "data": {"rows": len(df), "start": str(df["dt"].iloc[0]), "end": str(df["dt"].iloc[-1])},
        "full": full,
        "halves": halves,
        "walk_forward": windows,
        "correlations": correlations,
        "plateau": plateau,
        "plateau_pass_count": len(plateau_pass),
        "gates": gates,
        "accepted": all(gates.values()),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    main()
