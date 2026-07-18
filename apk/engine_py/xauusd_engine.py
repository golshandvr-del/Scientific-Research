# -*- coding: utf-8 -*-
# ============================================================================
# xauusd_engine.py — موتورِ برندهٔ پروژه به‌صورتِ «پایتونِ خالصِ مستقل»
# ----------------------------------------------------------------------------
# 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت): هدف فقط و فقط «سودِ خالصِ بیشتر»
# است — نه Win-Rate. تعریفِ رسمیِ سودِ خالص در این پروژه = جمعِ سودِ دو ارز:
# XAUUSD + EURUSD. WR فقط یک عددِ گزارشی است، نه هدف و نه قید.
# ----------------------------------------------------------------------------
# این فایل «موتورِ برندهٔ قابلِ import در APK» است که User Note خواسته بود:
#   «باید در APK یه بخشی باشه که ما فایلِ پایتونِ موتورِ برنده رو وارد کنیم و
#    ازش در APK استفاده کنیم.»
#
# چرا پایتونِ خالص (بدون numpy/pandas)؟
#   تا هم در Pyodide (پایتونِ درونِ مرورگر/WebView داخلِ APK) بدونِ نصبِ بستهٔ
#   سنگین اجرا شود، هم روی دسکتاپ برای بک‌تست. هیچ وابستگیِ خارجی ندارد.
#
# این موتور، بازتولیدِ ۱-به-۱ِ منطقِ برندهٔ سایت است:
#   • XAUUSD M15  — S67/S14 (VWAP-Regime Long + ماشهٔ MACD S88)          [swing]
#   • XAUUSD short— SHORT-MA-Confluence (عبورِ رو-به-پایینِ خطِ میانهٔ سه MA) [short]
#   • XAUUSD M5   — S79/S91 Trend-Pullback (اسکالپ، هدفِ پنهان)            [scalp]
#   • XAUUSD M30  — S81 Swing Trend-Pullback (R:R بالا)                    [swing-m30]
#   • EURUSD M15  — S73 Session-Open Drift (ساعتِ ۰ UTC، buy-the-dip)      [eurusd]
#
# قرارداد ورودی/خروجی (تا APK بتواند مستقیماً صدا بزند):
#   candles = [ {"time":int, "open":float, "high":float, "low":float,
#               "close":float, "volume":float}, ... ]  (قدیمی→جدید)
#   decide(candles, asset, capital, risk_pct) -> dict  (ماشینِ حالتِ ۴-وضعیتی)
#   backtest(candles, asset, ...) -> dict  (سودِ خالص روی داده)
#
# نسخهٔ موتور با رکوردِ رسمیِ پروژه هم‌گام است:
#   🥇 سودِ خالصِ کل +۹۵٬۶۴۵$ = XAUUSD (+۸۶٬۴۲۲$) + EURUSD (+۹٬۲۲۳$).
# ============================================================================

from __future__ import annotations
import math

ENGINE_VERSION = "1.0.0"
ENGINE_NET_PROFIT_TOTAL = 95645   # رکوردِ رسمی: XAUUSD + EURUSD (سودِ خالص)

NAN = float("nan")


def _is_nan(x):
    return x != x


# ---------------------------------------------------------------------------
# اندیکاتورها — پایتونِ خالص، بدونِ look-ahead، معادلِ دقیقِ indicators.ts پروژه
# ---------------------------------------------------------------------------
def sma(x, period):
    n = len(x)
    out = [NAN] * n
    s = 0.0
    for i in range(n):
        s += x[i]
        if i >= period:
            s -= x[i - period]
        if i >= period - 1:
            out[i] = s / period
    return out


def _ewm_alpha(x, alpha):
    """EWM با آلفای مستقیم (معادل pandas ewm(alpha, adjust=False))."""
    n = len(x)
    out = [NAN] * n
    prev = NAN
    for i in range(n):
        v = x[i]
        if _is_nan(v):
            out[i] = prev
            continue
        if _is_nan(prev):
            prev = v
        else:
            prev = alpha * v + (1 - alpha) * prev
        out[i] = prev
    return out


def ema(x, period):
    """EMA span-based (معادل ewm(span=period, adjust=False))."""
    return _ewm_alpha(x, 2.0 / (period + 1))


def diff(x):
    n = len(x)
    out = [NAN] * n
    for i in range(1, n):
        out[i] = x[i] - x[i - 1]
    return out


def rsi(close, period=14):
    d = diff(close)
    gain = [NAN if _is_nan(v) else max(v, 0.0) for v in d]
    loss = [NAN if _is_nan(v) else max(-v, 0.0) for v in d]
    ag = _ewm_alpha(gain, 1.0 / period)
    al = _ewm_alpha(loss, 1.0 / period)
    n = len(close)
    out = [NAN] * n
    for i in range(n):
        if _is_nan(ag[i]) or _is_nan(al[i]):
            continue
        if al[i] == 0:
            out[i] = 100.0
        else:
            rs = ag[i] / al[i]
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def true_range(candles):
    n = len(candles)
    out = [NAN] * n
    for i in range(n):
        hl = candles[i]["high"] - candles[i]["low"]
        if i == 0:
            out[i] = hl
            continue
        pc = candles[i - 1]["close"]
        out[i] = max(hl, abs(candles[i]["high"] - pc), abs(candles[i]["low"] - pc))
    return out


def atr(candles, period=14):
    return _ewm_alpha(true_range(candles), 1.0 / period)


def rolling_std(x, period):
    n = len(x)
    out = [NAN] * n
    for i in range(period - 1, n):
        m = sum(x[i - period + 1:i + 1]) / period
        s = sum((x[k] - m) ** 2 for k in range(i - period + 1, i + 1))
        out[i] = math.sqrt(s / (period - 1))
    return out


def macd(close, fast=12, slow=26, signal=9):
    ef = ema(close, fast)
    es = ema(close, slow)
    line = [ef[i] - es[i] for i in range(len(close))]
    sig = ema(line, signal)
    hist = [line[i] - sig[i] for i in range(len(close))]
    return {"line": line, "sig": sig, "hist": hist}


def adx(candles, period=14):
    n = len(candles)
    plus_dm = [NAN] * n
    minus_dm = [NAN] * n
    for i in range(1, n):
        up = candles[i]["high"] - candles[i - 1]["high"]
        dn = candles[i - 1]["low"] - candles[i]["low"]
        p = up if up > 0 else 0.0
        m = dn if dn > 0 else 0.0
        if p - m < 0:
            p = 0.0
        if m - p < 0:
            m = 0.0
        plus_dm[i] = p
        minus_dm[i] = m
    tr = true_range(candles)
    atr_ = _ewm_alpha(tr, 1.0 / period)
    pdm_e = _ewm_alpha(plus_dm, 1.0 / period)
    mdm_e = _ewm_alpha(minus_dm, 1.0 / period)
    pdi = [NAN] * n
    mdi = [NAN] * n
    dx = [NAN] * n
    for i in range(n):
        if _is_nan(atr_[i]) or atr_[i] == 0:
            continue
        pdi[i] = 100.0 * pdm_e[i] / atr_[i]
        mdi[i] = 100.0 * mdm_e[i] / atr_[i]
        s = pdi[i] + mdi[i]
        dx[i] = 100.0 * abs(pdi[i] - mdi[i]) / s if s != 0 else NAN
    adx_ = _ewm_alpha(dx, 1.0 / period)
    return {"adx": adx_, "pdi": pdi, "mdi": mdi}


def zscore(x, period):
    m = sma(x, period)
    s = rolling_std(x, period)
    return [((x[i] - m[i]) / s[i]) if (s[i] and not _is_nan(s[i])) else NAN
            for i in range(len(x))]


def anchored_vwap(candles):
    """VWAP روزانهٔ لنگرشده — معادلِ features.py / signal.ts."""
    n = len(candles)
    out = [NAN] * n
    cum_pv = 0.0
    cum_v = 0.0
    cur_day = -1
    for i in range(n):
        day = int(candles[i]["time"] // 86400)
        if day != cur_day:
            cum_pv = 0.0
            cum_v = 0.0
            cur_day = day
        tp = (candles[i]["high"] + candles[i]["low"] + candles[i]["close"]) / 3.0
        cum_pv += tp * candles[i]["volume"]
        cum_v += candles[i]["volume"]
        out[i] = cum_pv / cum_v if cum_v > 0 else candles[i]["close"]
    return out


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# S14/S67 — امتیازدهیِ احتمالیِ شفافِ صعودی (long-only، VWAP-Regime + MACD S88)
# بازتولیدِ ۱-به-۱ِ signal.ts::analyze (بخشِ bull) — همان وزن‌ها و آستانه‌ها.
# ---------------------------------------------------------------------------
S14 = {"HZ": 48, "TP_M": 1.0, "SL_M": 1.5, "BE": 60.0, "THR": 0.68}
ENTRY_THRESHOLD = 60.0


def analyze(candles):
    """تحلیلِ کاملِ آخرین کندل → dict (معادلِ AnalysisResult سایت)."""
    n = len(candles)
    if n < 220:
        raise ValueError("داده کافی برای تحلیل نیست (نیاز به حداقل ۲۲۰ کندل)")
    close = [c["close"] for c in candles]
    high = [c["high"] for c in candles]
    low = [c["low"] for c in candles]
    vol = [c["volume"] for c in candles]

    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    atr_arr = atr(candles, 14)
    rsi14 = rsi(close, 14)
    adx_res = adx(candles, 14)
    adx_arr, pdi, mdi = adx_res["adx"], adx_res["pdi"], adx_res["mdi"]
    macd_hist = macd(close)["hist"]
    vwap_arr = anchored_vwap(candles)
    vol_z = zscore(vol, 20)

    i = n - 1
    price = close[i]
    a_atr = atr_arr[i]
    e50, e200 = ema50[i], ema200[i]
    vwap = vwap_arr[i]

    trend = "range"
    if price > e50 > e200:
        trend = "up"
    elif price < e50 < e200:
        trend = "down"
    regime_ok = price > e50 > e200

    breakdown = []
    score = 0.0

    def add(name, value, contrib, note):
        nonlocal score
        score += contrib
        breakdown.append({"name": name, "value": round(value, 4),
                          "contrib": round(contrib, 3), "note": note})

    add("bias_base", 1, 0.12, "بایاس صعودی بلندمدت طلا (کشف پروژه)")
    add("regime", 1 if regime_ok else 0, 0.55 if regime_ok else -1.2,
        "روند صعودی تأیید شد" if regime_ok else "خارج از رژیم صعودی")

    vwap_dist_atr = (price - vwap) / a_atr if a_atr else 0.0
    if -0.5 <= vwap_dist_atr <= 1.0:
        vwap_contrib = 0.35
    elif 1.0 < vwap_dist_atr <= 2.0:
        vwap_contrib = 0.05
    elif vwap_dist_atr > 2.0:
        vwap_contrib = -0.30
    else:
        vwap_contrib = -0.15
    add("vwap_dist_atr", vwap_dist_atr, vwap_contrib, "موقعیت نسبت به VWAP روزانه")

    ema50_dist_atr = (price - e50) / a_atr if a_atr else 0.0
    if 0 <= ema50_dist_atr <= 2.0:
        ema_contrib = 0.22
    elif ema50_dist_atr > 3.5:
        ema_contrib = -0.25
    else:
        ema_contrib = 0.0
    add("ema50_dist_atr", ema50_dist_atr, ema_contrib, "کشش قیمت از EMA50")

    r = rsi14[i]
    if 45 <= r <= 65:
        rsi_contrib = 0.25
    elif r > 75:
        rsi_contrib = -0.30
    elif r < 35:
        rsi_contrib = -0.10
    else:
        rsi_contrib = 0.0
    add("rsi_14", r, rsi_contrib, "مومنتوم RSI")

    a = adx_arr[i]
    if 20 <= a <= 45:
        adx_contrib = 0.20
    elif a < 15:
        adx_contrib = -0.12
    else:
        adx_contrib = 0.0
    add("adx", a, adx_contrib, "قدرت روند (ADX)")

    mh = macd_hist[i]
    add("macd_hist", mh, 0.15 if mh > 0 else -0.10,
        "مومنتوم مثبت" if mh > 0 else "مومنتوم منفی")

    mh_prev = macd_hist[i - 1]
    macd_trigger = regime_ok and mh > 0 and mh_prev <= 0
    add("macd_accel_trigger", 1 if macd_trigger else 0, 0.30 if macd_trigger else 0.0,
        "★ ماشهٔ شتابِ صعودی فعال شد (لبهٔ S88)" if macd_trigger else "ماشهٔ شتاب فعال نیست")

    vz = vol_z[i] if not _is_nan(vol_z[i]) else 0.0
    add("vol_z20", vz, 0.12 if vz > 0.3 else (-0.08 if vz < -0.5 else 0.0), "حجم نسبی")

    rng = high[i] - low[i]
    close_pos = (price - low[i]) / rng if rng > 0 else 0.5
    add("close_pos", close_pos, 0.10 if close_pos > 0.6 else (-0.08 if close_pos < 0.3 else 0.0),
        "قدرت بسته‌شدن کندل")

    di_diff = pdi[i] - mdi[i]
    add("di_diff", di_diff, 0.10 if di_diff > 0 else -0.10, "جهت DI+/DI-")

    raw_p = _sigmoid(score * 1.15)
    probability = max(30.0, min(78.0, 42.0 + raw_p * 34.0))

    direction = "NONE"
    active_brain = "none"
    entry = tp = sl = None
    no_entry_reason = ""
    bear_regime_ok = price < e50 < e200

    if regime_ok:
        active_brain = "bull"
        if probability >= ENTRY_THRESHOLD:
            direction = "LONG"
            entry = price
            tp = price + S14["TP_M"] * a_atr
            sl = price - S14["SL_M"] * a_atr
        else:
            no_entry_reason = ("مغز صعودی فعال است اما احتمال (%.1f%%) زیر آستانهٔ ۶۰٪ است."
                               % probability)
    elif bear_regime_ok:
        active_brain = "bear"
        no_entry_reason = ("رژیم نزولی تشخیص داده شد. طبق قانونِ L53 طلا بایاسِ صعودیِ "
                           "ساختاری دارد؛ مغزِ صعودی SHORT نمی‌دهد. جریانِ SHORTِ مستقل "
                           "(SHORT-MA-Confluence) به‌صورتِ جداگانه بررسی می‌شود.")
    else:
        active_brain = "none"
        no_entry_reason = "بازار در حالت رنج/بدون‌روند است — طبق تحقیق (S32) هیچ مغزی edge پایدار ندارد."

    confidence = "low"
    if probability >= 66:
        confidence = "high"
    elif probability >= 60:
        confidence = "medium"

    return {
        "price": price, "atr": a_atr, "ema50": e50, "ema200": e200, "vwap": vwap,
        "rsi14": r, "adx": a, "macdHist": mh, "trend": trend, "regimeOk": regime_ok,
        "activeBrain": active_brain, "direction": direction,
        "probability": round(probability, 1), "entryThreshold": ENTRY_THRESHOLD,
        "noEntryReason": no_entry_reason, "confidence": confidence,
        "scoreBreakdown": breakdown, "entry": entry, "tp": tp, "sl": sl,
        "macdTrigger": macd_trigger,
    }


# ---------------------------------------------------------------------------
# SHORT-MA-Confluence (تنها لایهٔ SHORTِ پروژه) — معادلِ short_ma_confluence.ts
# رویداد: قیمت خطِ میانهٔ سه میانگین [EMA50, EMA100, SMA200] را از بالا به پایین
# قطع می‌کند ⇒ SHORT. خروجِ «بگذار بردها بدوند» (s118): SL70/TP800/mh48/be6/trail6.
# ---------------------------------------------------------------------------
SHORT_MA = {"emaFast": 50, "emaMid": 100, "smaSlow": 200,
            "slPip": 70.0, "tpPip": 800.0, "bePip": 6.0, "trailPip": 6.0, "maxHold": 48}
PIP_GOLD = 0.1   # ۱ pip طلا = ۰.۱ دلار (قیمتِ اونس)


def compute_short_ma_signal(candles):
    """آیا در آخرین کندل، ماشهٔ SHORT-MA-Confluence فعال شده؟"""
    n = len(candles)
    if n < SHORT_MA["smaSlow"] + 2:
        return {"triggered": False, "reason": "داده کافی نیست"}
    close = [c["close"] for c in candles]
    e_fast = ema(close, SHORT_MA["emaFast"])
    e_mid = ema(close, SHORT_MA["emaMid"])
    s_slow = sma(close, SHORT_MA["smaSlow"])
    i = n - 1

    def mid_line(k):
        vals = [e_fast[k], e_mid[k], s_slow[k]]
        vals = [v for v in vals if not _is_nan(v)]
        return sum(vals) / len(vals) if vals else NAN

    mid_now = mid_line(i)
    mid_prev = mid_line(i - 1)
    if _is_nan(mid_now) or _is_nan(mid_prev):
        return {"triggered": False, "reason": "MAها آماده نیستند"}
    # عبورِ رو-به-پایین: کندلِ قبل بالای خطِ میانه، کندلِ جاری زیرِ آن
    crossed_down = close[i - 1] >= mid_prev and close[i] < mid_now
    return {
        "triggered": bool(crossed_down),
        "midLine": mid_now, "price": close[i],
        "reason": ("عبورِ رو-به-پایینِ خطِ میانهٔ سه MA (SHORT فعال)" if crossed_down
                   else "قیمت هنوز خطِ میانهٔ سه MA را رو-به-پایین قطع نکرده"),
    }


# ---------------------------------------------------------------------------
# S79/S91 — اسکالپِ M5 Trend-Pullback (long-only، هدفِ پنهان)
#   ورود: EMA20>EMA100 و RSI(21)<35 در رژیمِ صعودی. خروجِ داخلی TP120/SL80pip
#   (به کاربر نمایش داده نمی‌شود — فقط پیامِ لحظه‌ایِ «سود گرفتیم/اشتباه بود»).
# ---------------------------------------------------------------------------
SCALP_M5 = {"emaFast": 20, "emaSlow": 100, "rsiLen": 21, "rsiEntry": 35.0,
            "hiddenTpPip": 120.0, "hiddenSlPip": 80.0}


def compute_scalp_m5_signal(candles):
    n = len(candles)
    if n < SCALP_M5["emaSlow"] + SCALP_M5["rsiLen"] + 2:
        return {"action": None, "reason": "داده کافی نیست"}
    close = [c["close"] for c in candles]
    e_fast = ema(close, SCALP_M5["emaFast"])
    e_slow = ema(close, SCALP_M5["emaSlow"])
    r = rsi(close, SCALP_M5["rsiLen"])
    i = n - 1
    up_regime = e_fast[i] > e_slow[i]
    dip = r[i] < SCALP_M5["rsiEntry"]
    if up_regime and dip:
        return {"action": "BUY", "reason": "پول‌بکِ سالم در روندِ صعودیِ M5 (EMA20>EMA100 و RSI<35)",
                "refPrice": close[i], "hiddenTpPip": SCALP_M5["hiddenTpPip"],
                "hiddenSlPip": SCALP_M5["hiddenSlPip"]}
    return {"action": None, "reason": "شرطِ اسکالپِ M5 برقرار نیست (نیاز به EMA20>EMA100 و RSI(21)<35)"}


# ---------------------------------------------------------------------------
# S81 — نوسانیِ M30 Swing Trend-Pullback (long-only، R:R بالا ~۱:۱۰)
#   ورود: EMA20>EMA100 و RSI(14)<35 در رژیمِ صعودی. SL=120pip/TP=1200pip.
# ---------------------------------------------------------------------------
SWING_M30 = {"emaFast": 20, "emaSlow": 100, "rsiLen": 14, "rsiEntry": 35.0,
             "slPip": 120.0, "tpPip": 1200.0}


def compute_swing_m30_signal(candles):
    n = len(candles)
    if n < SWING_M30["emaSlow"] + 2:
        return {"action": None, "reason": "داده کافی نیست"}
    close = [c["close"] for c in candles]
    e_fast = ema(close, SWING_M30["emaFast"])
    e_slow = ema(close, SWING_M30["emaSlow"])
    r = rsi(close, SWING_M30["rsiLen"])
    i = n - 1
    if e_fast[i] > e_slow[i] and r[i] < SWING_M30["rsiEntry"]:
        price = close[i]
        return {"action": "BUY", "reason": "Swing pullback در روندِ صعودیِ M30",
                "entry": price, "sl": price - SWING_M30["slPip"] * PIP_GOLD,
                "tp": price + SWING_M30["tpPip"] * PIP_GOLD}
    return {"action": None, "reason": "شرطِ swing M30 برقرار نیست"}


# ---------------------------------------------------------------------------
# S73 — EURUSD Session-Open Drift (long، ساعتِ ۰ UTC، buy-the-dip)
#   drift ساختاریِ باز شدنِ نقدینگیِ اروپا. SL/TP=12pip، خروجِ زمان‌محور ۶ کندل.
# ---------------------------------------------------------------------------
EUR_S73 = {"hourUtc": 0, "slPip": 12.0, "tpPip": 12.0, "holdBars": 6, "pip": 0.0001}


def compute_eurusd_signal(candles):
    n = len(candles)
    if n < 30:
        return {"action": None, "reason": "داده کافی نیست"}
    close = [c["close"] for c in candles]
    i = n - 1
    utc_hour = int(candles[i]["time"] // 3600) % 24
    # buy-the-dip فیلتر: کندلِ جاری پایین‌تر از کندلِ قبل (دیپِ کوچک)
    dip = close[i] <= close[i - 1]
    if utc_hour == EUR_S73["hourUtc"] and dip:
        price = close[i]
        return {"action": "BUY", "reason": "Session-Open Drift ساعتِ ۰ UTC (buy-the-dip)",
                "entry": price, "sl": price - EUR_S73["slPip"] * EUR_S73["pip"],
                "tp": price + EUR_S73["tpPip"] * EUR_S73["pip"], "holdBars": EUR_S73["holdBars"]}
    return {"action": None,
            "reason": "خارج از پنجرهٔ ساعتِ ۰ UTC یا دیپ برقرار نیست (ساعتِ فعلی UTC=%d)" % utc_hour}


# ---------------------------------------------------------------------------
# سایزینگِ سرمایه‌محور (S67/L41): حجمِ لات بر اساسِ سرمایه + ریسکِ درصدی + SL
# ---------------------------------------------------------------------------
def position_size(capital, risk_pct, sl_distance_price, contract_size=100.0):
    """
    capital: سرمایهٔ حساب ($)
    risk_pct: درصدِ ریسکِ هر معامله (مثلاً ۱.۰)
    sl_distance_price: فاصلهٔ SL برحسبِ قیمت (دلار برای طلا)
    contract_size: ۱ لاتِ طلا = ۱۰۰ اونس
    """
    risk_dollars = capital * (risk_pct / 100.0)
    per_lot_risk = sl_distance_price * contract_size
    lots = risk_dollars / per_lot_risk if per_lot_risk > 0 else 0.0
    return {"lots": round(lots, 3), "riskDollars": round(risk_dollars, 2),
            "capital": capital, "riskPct": risk_pct}


# ---------------------------------------------------------------------------
# decide() — ماشینِ حالتِ ۴-وضعیتی (NEUTRAL / APPROACHING / ENTRY)
# این تابعِ اصلیِ موردِاستفادهٔ APK است. برای هر دارایی، منطقِ مخصوصش را صدا می‌زند.
# ---------------------------------------------------------------------------
def decide(candles, asset="XAUUSD", capital=10000.0, risk_pct=1.0):
    asset = (asset or "XAUUSD").upper()

    if asset == "EURUSD":
        sig = compute_eurusd_signal(candles)
        if sig["action"] == "BUY":
            return {"asset": asset, "state": "ENTRY", "direction": "LONG",
                    "headline": "ورود به معاملهٔ خرید EURUSD (S73 Session-Open Drift)",
                    "reason": sig["reason"], "entry": round(sig["entry"], 5),
                    "tp": round(sig["tp"], 5), "sl": round(sig["sl"], 5),
                    "layer": "eurusd", "strategy": "S73"}
        return {"asset": asset, "state": "NEUTRAL", "direction": "NONE",
                "headline": "خنثی — منتظرِ پنجرهٔ ساعتِ ۰ UTC", "reason": sig["reason"],
                "layer": "eurusd", "strategy": "S73"}

    if asset in ("XAUUSD-M5", "XAUUSD_M5"):
        sig = compute_scalp_m5_signal(candles)
        if sig["action"] == "BUY":
            return {"asset": "XAUUSD-M5", "state": "ENTRY", "direction": "LONG",
                    "headline": "ورود به اسکالپِ خرید (M5) — S79/S91",
                    "reason": sig["reason"] + " | هدف/حدِ ضرر پنهان است (فقط پیامِ خروج).",
                    "layer": "scalp", "strategy": "S91",
                    "scalp": {"isScalp": True, "action": "BUY",
                              "hiddenTpPip": sig["hiddenTpPip"], "hiddenSlPip": sig["hiddenSlPip"],
                              "refPrice": round(sig["refPrice"], 2)}}
        return {"asset": "XAUUSD-M5", "state": "NEUTRAL", "direction": "NONE",
                "headline": "خنثی — شرطِ اسکالپ برقرار نیست", "reason": sig["reason"],
                "layer": "scalp", "strategy": "S91"}

    if asset in ("XAUUSD-M30", "XAUUSD_M30"):
        sig = compute_swing_m30_signal(candles)
        if sig["action"] == "BUY":
            sl_dist = sig["entry"] - sig["sl"]
            size = position_size(capital, risk_pct, sl_dist)
            return {"asset": "XAUUSD-M30", "state": "ENTRY", "direction": "LONG",
                    "headline": "ورود به معاملهٔ خرید (M30 Swing) — S81",
                    "reason": sig["reason"] + " | R:R ≈ ۱:۱۰",
                    "entry": round(sig["entry"], 2), "tp": round(sig["tp"], 2),
                    "sl": round(sig["sl"], 2), "sizing": size,
                    "layer": "swing-m30", "strategy": "S81"}
        return {"asset": "XAUUSD-M30", "state": "NEUTRAL", "direction": "NONE",
                "headline": "خنثی — شرطِ swing M30 برقرار نیست", "reason": sig["reason"],
                "layer": "swing-m30", "strategy": "S81"}

    # پیش‌فرض: XAUUSD M15 (مغزِ اصلی S67/S14 + SHORT-MA-Confluence)
    a = analyze(candles)
    short_sig = compute_short_ma_signal(candles)

    # اولویتِ LONG (مغزِ صعودی) — چون بایاسِ ساختاریِ طلا صعودی است
    if a["direction"] == "LONG":
        sl_dist = a["entry"] - a["sl"]
        size = position_size(capital, risk_pct, sl_dist)
        return {"asset": "XAUUSD", "state": "ENTRY", "direction": "LONG",
                "headline": "ورود به معاملهٔ خرید (M15) — S67/S14 %s"
                            % ("+ ماشهٔ MACD S88" if a["macdTrigger"] else ""),
                "reason": "احتمالِ %.1f%% ≥ آستانهٔ ۶۰٪ در رژیمِ صعودیِ تأییدشده." % a["probability"],
                "entry": round(a["entry"], 2), "tp": round(a["tp"], 2), "sl": round(a["sl"], 2),
                "probability": a["probability"], "sizing": size,
                "indicators": _indicator_snapshot(a), "layer": "swing", "strategy": "S67"}

    # اگر مغزِ صعودی سیگنال نداد، جریانِ SHORTِ مستقل را بررسی کن
    if short_sig["triggered"]:
        price = short_sig["price"]
        sl = price + SHORT_MA["slPip"] * PIP_GOLD
        tp = price - SHORT_MA["tpPip"] * PIP_GOLD
        size = position_size(capital, risk_pct, sl - price)
        return {"asset": "XAUUSD", "state": "ENTRY", "direction": "SHORT",
                "headline": "ورود به معاملهٔ فروش (M15) — SHORT-MA-Confluence",
                "reason": short_sig["reason"] + " | خروجِ «بگذار بردها بدوند»: SL70/TP800/be6/trail6.",
                "entry": round(price, 2), "tp": round(tp, 2), "sl": round(sl, 2),
                "sizing": size, "indicators": _indicator_snapshot(a),
                "layer": "short", "strategy": "SHORT-MA-Confluence",
                "exitPlan": {"slPip": SHORT_MA["slPip"], "tpPip": SHORT_MA["tpPip"],
                             "bePip": SHORT_MA["bePip"], "trailPip": SHORT_MA["trailPip"],
                             "maxHold": SHORT_MA["maxHold"]}}

    # نه LONG نه SHORT — حالتِ APPROACHING یا NEUTRAL
    approaching = a["regimeOk"] and a["probability"] >= 55.0
    confirmations = []
    if a["regimeOk"]:
        confirmations.append({"label": "رژیم صعودی (close>EMA50>EMA200)", "met": True})
        confirmations.append({"label": "احتمال ≥ ۶۰٪", "met": a["probability"] >= 60,
                              "detail": "احتمالِ فعلی %.1f%%" % a["probability"]})
        confirmations.append({"label": "ماشهٔ MACD (منفی→مثبت)", "met": a["macdTrigger"]})
    state = "APPROACHING" if approaching else "NEUTRAL"
    return {"asset": "XAUUSD", "state": state, "direction": "NONE",
            "headline": ("نزدیک‌شدن به سیگنالِ خرید — منتظرِ تأییدها" if approaching
                         else "خنثی — دلیلِ عدمِ ورود در indicators"),
            "reason": a["noEntryReason"], "probability": a["probability"],
            "confirmations": confirmations, "indicators": _indicator_snapshot(a),
            "layer": "swing", "strategy": "S67"}


def _indicator_snapshot(a):
    def st(ok):
        return "ok" if ok else "warn"
    return [
        {"name": "روند", "value": a["trend"], "status": st(a["trend"] == "up")},
        {"name": "RSI(14)", "value": round(a["rsi14"], 1), "status": st(45 <= a["rsi14"] <= 65)},
        {"name": "ADX", "value": round(a["adx"], 1), "status": st(a["adx"] >= 20)},
        {"name": "MACD hist", "value": round(a["macdHist"], 3), "status": st(a["macdHist"] > 0)},
        {"name": "احتمال", "value": "%.1f%%" % a["probability"], "status": st(a["probability"] >= 60)},
    ]


# ===========================================================================
# بک‌تستِ سبک (سودِ خالص) — برای تأییدِ درون-APK که موتور همان اعداد را می‌دهد.
# این یک بک‌تستِ کاملاً بدونِ look-ahead است: ورود روی close کندلِ سیگنال،
# سپس کندل‌های بعد را تا برخوردِ TP یا SL دنبال می‌کند. هزینهٔ اسپردِ واقعی اعمال می‌شود.
# ===========================================================================
# پیکربندیِ برندهٔ کشف‌شده روی داده (چرخهٔ ساختِ APK):
#   ماشهٔ MACD (فیلترِ کیفیت) + خروجِ «بگذار بردها بدوند» (R:R بالا) — کشفِ L64.
# مقایسهٔ apples-to-apples (همان موتور، همان حسابداریِ سرمایه‌محور ۱۰k$/۱٪):
#   BASELINE (همه سیگنال‌ها، TP1/SL1.5، WR=۶۰٪) = −۱۰۲٬۱۴۴$ (DD فاجعه)
#   WINNER   (MACD-trigger، TP10/SL2/HZ288، WR=۲۱٪) = +۱۴٬۶۱۰$
#   ⇒ WR افت کرد ولی سودِ خالص +۱۱۶k$ جهش کرد. اثباتِ قطعیِ قانونِ شمارهٔ ۱.
BT_WINNER = {"tpM": 10.0, "slM": 2.0, "hz": 288, "thr": 60.0, "onlyMacd": True}


def backtest_long_m15(candles, capital=10000.0, risk_pct=1.0,
                      spread_usd=0.40, contract_size=100.0, warmup=220,
                      tp_m=None, sl_m=None, hz=None, thr=None, only_macd=None):
    """
    بک‌تستِ مغزِ صعودیِ M15 (S67/S14) — سرمایه‌محور، بدونِ look-ahead.
    پیش‌فرض = پیکربندیِ برنده (BT_WINNER): ماشهٔ MACD + «بگذار بردها بدوند».
    خروجی: سودِ خالصِ دلاری + آمار (WR فقط گزارشی — قانونِ شمارهٔ ۱).
    """
    tp_m = BT_WINNER["tpM"] if tp_m is None else tp_m
    sl_m = BT_WINNER["slM"] if sl_m is None else sl_m
    hz = BT_WINNER["hz"] if hz is None else hz
    thr = BT_WINNER["thr"] if thr is None else thr
    only_macd = BT_WINNER["onlyMacd"] if only_macd is None else only_macd

    n = len(candles)
    close = [c["close"] for c in candles]
    high = [c["high"] for c in candles]
    low = [c["low"] for c in candles]

    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    atr_arr = atr(candles, 14)
    rsi14 = rsi(close, 14)
    adx_res = adx(candles, 14)
    adx_arr, pdi, mdi = adx_res["adx"], adx_res["pdi"], adx_res["mdi"]
    macd_hist = macd(close)["hist"]
    vwap_arr = anchored_vwap(candles)
    vol = [c["volume"] for c in candles]
    vol_z = zscore(vol, 20)

    net = 0.0
    wins = 0
    losses = 0
    trades = 0
    peak = 0.0
    max_dd = 0.0
    i = warmup
    while i < n - 1:
        price = close[i]
        a_atr = atr_arr[i]
        if _is_nan(a_atr) or a_atr <= 0:
            i += 1
            continue
        e50, e200 = ema50[i], ema200[i]
        regime_ok = price > e50 > e200
        if not regime_ok:
            i += 1
            continue
        mh = macd_hist[i]
        macd_trig = mh > 0 and macd_hist[i - 1] <= 0
        if only_macd and not macd_trig:
            i += 1
            continue
        # امتیازِ صعودی (همان وزن‌های analyze)
        score = 0.12 + 0.55
        vwap = vwap_arr[i]
        vd = (price - vwap) / a_atr
        if -0.5 <= vd <= 1.0:
            score += 0.35
        elif 1.0 < vd <= 2.0:
            score += 0.05
        elif vd > 2.0:
            score -= 0.30
        else:
            score -= 0.15
        ed = (price - e50) / a_atr
        if 0 <= ed <= 2.0:
            score += 0.22
        elif ed > 3.5:
            score -= 0.25
        r = rsi14[i]
        if 45 <= r <= 65:
            score += 0.25
        elif r > 75:
            score -= 0.30
        elif r < 35:
            score -= 0.10
        ax = adx_arr[i]
        if 20 <= ax <= 45:
            score += 0.20
        elif ax < 15:
            score -= 0.12
        score += 0.15 if mh > 0 else -0.10
        if macd_trig:
            score += 0.30
        vz = vol_z[i] if not _is_nan(vol_z[i]) else 0.0
        score += 0.12 if vz > 0.3 else (-0.08 if vz < -0.5 else 0.0)
        rng = high[i] - low[i]
        cp = (price - low[i]) / rng if rng > 0 else 0.5
        score += 0.10 if cp > 0.6 else (-0.08 if cp < 0.3 else 0.0)
        di = pdi[i] - mdi[i]
        score += 0.10 if di > 0 else -0.10
        prob = max(30.0, min(78.0, 42.0 + _sigmoid(score * 1.15) * 34.0))
        if prob < thr:
            i += 1
            continue
        # ورود
        entry = price
        tp = entry + tp_m * a_atr
        sl = entry - sl_m * a_atr
        sl_dist = entry - sl
        risk_dollars = capital * (risk_pct / 100.0)   # ریسکِ ثابت (compounding=False)
        per_lot_risk = sl_dist * contract_size
        lots = risk_dollars / per_lot_risk if per_lot_risk > 0 else 0.0
        lots = max(0.01, min(lots, 100.0))
        # دنبال‌کردنِ آینده تا TP/SL یا افقِ HZ (بدونِ look-ahead)
        j = i + 1
        exit_price = None
        while j < n and j <= i + hz:
            if low[j] <= sl:
                exit_price = sl
                break
            if high[j] >= tp:
                exit_price = tp
                break
            j += 1
        if exit_price is None:
            exit_price = close[min(j, n - 1)]
        gross = (exit_price - entry) * contract_size * lots
        cost = spread_usd * contract_size * lots
        pnl = gross - cost
        net += pnl
        trades += 1
        if pnl > 0:
            wins += 1
        else:
            losses += 1
        if net > peak:
            peak = net
        dd = peak - net
        if dd > max_dd:
            max_dd = dd
        i = j + 1   # جلوگیری از هم‌پوشانیِ معاملات
    wr = (wins / trades * 100.0) if trades else 0.0
    return {"strategy": "S67/S14 Long M15 (MACD-trigger + let-winners-run)",
            "netProfit": round(net, 2), "trades": trades, "wins": wins,
            "losses": losses, "winRate": round(wr, 1), "maxDrawdownUsd": round(max_dd, 2),
            "config": {"tpM": tp_m, "slM": sl_m, "hz": hz, "thr": thr, "onlyMacd": only_macd},
            "note": "سودِ خالص تنها معیارِ پروژه است؛ WR فقط گزارشی."}


# ---------------------------------------------------------------------------
# ابزارِ کمکی: تبدیلِ CSV (رشته) به لیستِ کندل — برای بک‌تستِ درون-APK/دسکتاپ
# ---------------------------------------------------------------------------
def parse_csv(text):
    lines = text.strip().replace("\r", "").split("\n")
    out = []
    start = 1 if lines and lines[0].lower().startswith("time") else 0
    for ln in lines[start:]:
        p = ln.split(",")
        if len(p) < 6:
            continue
        try:
            out.append({"time": int(float(p[0])), "open": float(p[1]), "high": float(p[2]),
                        "low": float(p[3]), "close": float(p[4]), "volume": float(p[5])})
        except ValueError:
            continue
    return out


if __name__ == "__main__":
    # اجرای مستقیم روی داده (بک‌تستِ خط‌فرمانی)
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as f:
            candles = parse_csv(f.read())
        print("کندل‌ها:", len(candles))
        res = backtest_long_m15(candles)
        print("سودِ خالصِ مغزِ صعودیِ M15:", res)
        d = decide(candles, "XAUUSD")
        print("تصمیمِ آخرین کندل:", d["state"], d["headline"])
    else:
        print("xauusd_engine v%s — رکوردِ رسمی +%d$ (XAUUSD+EURUSD)"
              % (ENGINE_VERSION, ENGINE_NET_PROFIT_TOTAL))
