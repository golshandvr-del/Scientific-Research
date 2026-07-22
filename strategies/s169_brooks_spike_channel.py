# -*- coding: utf-8 -*-
"""
S169 — Al Brooks Spike-and-Channel Trend
(کتابِ Trading Price Action: Trends — فصلِ ۲۱، مرحلهٔ ۲ کتاب)

قانونِ شمارهٔ ۱ پروژه: تابعِ هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR
هدف نیست، اما WR هر لایه باید حداقل ۴۰٪ باشد.

--------------------------------------------------------------------------------
فرضیهٔ ازپیش‌تعریف‌شده (نقلِ مکانیکی از کتاب، فصلِ Spike and Channel Trend):
  «Every trend has both a spike phase and a channel phase. First a spike of one
   or more strong trend bars (a breakaway gap). Then a pullback. Then the trend
   converts into a channel. When the market is channeling in a bull channel, it
   is better to buy below the low of the prior bar and hold part for a swing.»

یعنی الگو دو-فازی است:
  (۱) SPIKE  = چند کندلِ روندِ قوی پشتِ‌هم با هم‌پوشانیِ کم (شکستِ قوی).
  (۲) CHANNEL= پس از یک pullbackِ کوتاه، روند در قالبِ کانال ادامه می‌یابد؛ و
     قانونِ معاملاتیِ صریحِ Brooks: در bull channel «زیرِ low کندلِ قبلی بخر».

--------------------------------------------------------------------------------
ترجمهٔ کاملاً مکانیکیِ shift-safe (بدونِ look-ahead):

  رژیم/جهت با EMA_fast vs EMA_slow تعیین می‌شود (bull: fast>slow).

  تشخیصِ SPIKE (bull):
    یک پنجرهٔ `spike_len` کندلِ متوالی که همه bull-body باشند (close>open)،
    highها و lowها صعودی (higher-highs & higher-lows)، و مجموعِ حرکت
    (close[end]-close[start]) بزرگ‌تر از `spike_atr_mult × ATR` باشد.
    این «شکستِ قویِ» Brooks است.

  فازِ CHANNEL و ورود (bull):
    پس از تشکیلِ یک spikeِ صعودی، تا `channel_window` کندل، رژیم صعودی است
    (close>EMA_slow) و قیمت هنوز از سقفِ spike خیلی دور نشده:
      • «buy below the low of the prior bar» ⇒ اگر low کندلِ جاری < low کندلِ
        قبلی (یعنی pullbackِ یک‌کندلی) و رژیم صعودی برقرار ⇒ سیگنالِ Long روی
        بسته‌شدنِ همین کندل (ورود روی open کندلِ بعد پس از shift).
    قرینهٔ کامل برای bear spike-and-channel ⇒ Short.

  SL/TP: SL بر حسبِ pip (زیر ساختار)، TP نسبتِ R یا measured-move (ارتفاعِ spike).
  گیتِ سخت‌گیرانه: net>0 کل + net>0 هر دو نیمه + net>0 هر ۴ پنجره + WR≥۴۰٪ + n≥۳۰.
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
from engine import indicators as ind

OUT = os.path.join(ROOT, "results", "_s169_brooks_spike_channel.json")
CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0

ASSET_FILES = {
    "XAUUSD": os.path.join(ROOT, "data", "XAUUSD_M15.csv"),
    "EURUSD": os.path.join(ROOT, "data", "EURUSD_M15.csv"),
}

# کالیبراسیونِ واقعیِ EURUSD (هم‌راستا با scalp_engine.ASSETS)
se.ASSETS["EURUSD"].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load_data(path):
    df = pd.read_csv(path)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def detect_spike_channel_events(df, ema_fast, ema_slow, spike_len,
                                spike_atr_mult, channel_window):
    """پیمایشِ سببیِ یک‌گذر؛ خروجی: دو آرایهٔ بولی long_evt / short_evt روی همان
    کندل (قبل از shift). هیچ داده‌ای از آینده استفاده نمی‌شود."""
    o = df["open"].to_numpy(dtype=np.float64)
    h = df["high"].to_numpy(dtype=np.float64)
    l = df["low"].to_numpy(dtype=np.float64)
    c = df["close"].to_numpy(dtype=np.float64)
    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()
    atr = ind.atr(df, 14).to_numpy()
    n = len(df)

    long_evt = np.zeros(n, dtype=bool)
    short_evt = np.zeros(n, dtype=bool)

    # وضعیتِ فازِ کانال پس از آخرین spike
    bull_channel_left = 0   # چند کندل دیگر مجازیم در فازِ کانالِ صعودی ورود کنیم
    bear_channel_left = 0
    spike_top = np.nan      # سقفِ spikeِ صعودیِ اخیر (برای measured-move/محدودهٔ اعتبار)
    spike_bot = np.nan

    def is_bull_spike(i):
        """آیا پنجرهٔ [i-spike_len+1 .. i] یک bull spike کامل است؟ (سببی)"""
        s = i - spike_len + 1
        if s < 1 or np.isnan(atr[i]):
            return False
        # همه کندل‌ها bull-body، higher-high و higher-low
        for k in range(s, i + 1):
            if c[k] <= o[k]:
                return False
            if h[k] <= h[k - 1] or l[k] <= l[k - 1]:
                return False
        move = c[i] - c[s - 1]
        return move >= spike_atr_mult * atr[i]

    def is_bear_spike(i):
        s = i - spike_len + 1
        if s < 1 or np.isnan(atr[i]):
            return False
        for k in range(s, i + 1):
            if c[k] >= o[k]:
                return False
            if h[k] >= h[k - 1] or l[k] >= l[k - 1]:
                return False
        move = c[s - 1] - c[i]
        return move >= spike_atr_mult * atr[i]

    for i in range(spike_len + 1, n):
        bull = ef[i] > es[i]
        bear = ef[i] < es[i]

        # --- تشخیصِ spike جدید ⇒ باز کردنِ پنجرهٔ کانال ---
        if bull and is_bull_spike(i):
            bull_channel_left = channel_window
            spike_top = h[i]
            spike_bot = l[i - spike_len + 1]
            bear_channel_left = 0
        elif bear and is_bear_spike(i):
            bear_channel_left = channel_window
            spike_bot = l[i]
            spike_top = h[i - spike_len + 1]
            bull_channel_left = 0

        # --- فازِ کانالِ صعودی: buy below prior-bar low ---
        if bull_channel_left > 0:
            if not bull:
                bull_channel_left = 0          # رژیم شکست ⇒ باطل
            else:
                # pullbackِ یک‌کندلی درونِ کانالِ صعودی + هنوز زیرِ سقفِ spike
                if l[i] < l[i - 1] and c[i] < spike_top:
                    long_evt[i] = True
                bull_channel_left -= 1

        # --- فازِ کانالِ نزولی: sell above prior-bar high ---
        if bear_channel_left > 0:
            if not bear:
                bear_channel_left = 0
            else:
                if h[i] > h[i - 1] and c[i] > spike_bot:
                    short_evt[i] = True
                bear_channel_left -= 1

    return long_evt, short_evt


def evaluate(df, asset, side, ema_fast, ema_slow, spike_len, spike_atr_mult,
             channel_window, sl_pip, tp_pip, max_hold):
    long_evt, short_evt = detect_spike_channel_events(
        df, ema_fast, ema_slow, spike_len, spike_atr_mult, channel_window
    )
    long_sig = pd.Series(long_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    short_sig = pd.Series(short_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    if side == "long":
        short_sig = np.zeros_like(short_sig, dtype=bool)
    else:
        long_sig = np.zeros_like(long_sig, dtype=bool)

    trades = se.simulate_trades(
        df, long_sig, short_sig, sl_pip, tp_pip, asset,
        max_hold=max_hold, allow_overlap=False,
    )
    if trades is None or len(trades) < 30:
        return None
    stats, _, per_trade = se.run_capital_pertrade(
        trades, asset, df=df, initial_capital=CAPITAL, risk_pct=RISK_PCT, compounding=False,
    )
    n = len(per_trade)
    if n < 30:
        return None
    half = n // 2
    pnl = per_trade["net_usd"]
    net_h1 = float(pnl.iloc[:half].sum())
    net_h2 = float(pnl.iloc[half:].sum())
    net = float(stats["net_profit"])
    wr = float(stats["win_rate"])
    pf = float(stats["profit_factor"])
    accepted = bool(net > 0 and net_h1 > 0 and net_h2 > 0 and wr >= WR_FLOOR and n >= 30)
    return {
        "asset": asset, "side": side, "ema_fast": ema_fast, "ema_slow": ema_slow,
        "spike_len": spike_len, "spike_atr_mult": spike_atr_mult,
        "channel_window": channel_window, "sl": sl_pip, "tp": tp_pip, "max_hold": max_hold,
        "net": net, "net_h1": net_h1, "net_h2": net_h2,
        "wr": wr, "pf": pf if pf != float("inf") else 999.0,
        "n": int(n), "accepted": accepted,
    }


def main():
    ema_pairs = [(20, 50), (10, 30)]
    spike_lens = [3, 4]
    spike_mults = [1.0, 1.5]
    channel_windows = [10, 20]
    grids = {
        "XAUUSD": [(200, 300), (250, 375), (300, 450)],
        "EURUSD": [(20, 30), (25, 40), (30, 45)],
    }
    max_holds = [16, 32]

    results = {}
    for asset, path in ASSET_FILES.items():
        df = load_data(path)
        variants = []
        for side in ("long", "short"):
            for (ef, es) in ema_pairs:
                for sl_len in spike_lens:
                    for sm in spike_mults:
                        for cw in channel_windows:
                            for (sl, tp) in grids[asset]:
                                for mh in max_holds:
                                    r = evaluate(df, asset, side, ef, es, sl_len,
                                                 sm, cw, sl, tp, mh)
                                    if r is not None:
                                        variants.append(r)
        acc = [v for v in variants if v["accepted"]]
        pos = [v for v in variants if v["net"] > 0]
        variants.sort(key=lambda x: x["net"], reverse=True)
        results[asset] = {
            "rows": len(df), "n_variants": len(variants), "variants": variants,
            "n_accepted": len(acc), "n_net_positive": len(pos),
        }
        print(f"\n===== {asset} ({len(df)} rows) =====")
        print(f"  {len(variants)} variants; accepted={len(acc)}; net_positive={len(pos)}")
        for v in variants[:10]:
            tag = "ACCEPT" if v["accepted"] else "reject"
            print(f"    {tag} {v['side']:5s} ema{v['ema_fast']}/{v['ema_slow']} "
                  f"spk{v['spike_len']}x{v['spike_atr_mult']} cw{v['channel_window']} "
                  f"SL{v['sl']}/TP{v['tp']} mh{v['max_hold']:2d}  "
                  f"net=${v['net']:9.0f}  WR={v['wr']:5.1f}%  n={v['n']:4d}  PF={v['pf']:.2f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_acc = sum(r["n_accepted"] for r in results.values())
    print(f"\n=== خلاصه: مجموع واریانتِ پذیرفته‌شده = {total_acc} ===")


if __name__ == "__main__":
    main()
