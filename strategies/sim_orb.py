# -*- coding: utf-8 -*-
"""
sim_orb.py — احیای S21 (Session Opening-Range Breakout + Coiled-Spring) با شبیه‌سازِ
             رویداد-محور و معیارِ RQS+.
================================================================================
منشأ سوخته: `results/Session_ORB_CoiledSpring_47.md` (RQS≈47، عصرِ WR).

تزِ مرکزی (کلاسیک ORB — Toby Crabel / Mark Fisher):
    در آغازِ هر سشنِ بزرگ (لندن ~۷ UTC، نیویورک ~۱۳ UTC) بازار یک «بازهٔ افتتاحیه»
    (Opening Range = high/low چند کندلِ اولِ سشن) می‌سازد. شکستِ این بازه جهتِ غالبِ
    روزانه را نشان می‌دهد و اغلب ادامه می‌یابد.

چرا خام سوخت (تحلیلِ نشستِ احیا):
    ۱) ورودِ *دوطرفه* بود؛ طلا long-biasِ ساختاری دارد ⇒ نیمهٔ SHORT سود را می‌کُشت.
    ۲) سشنِ نیویورک (۱۳ UTC) به‌شدت زیان‌ده بود اما همچنان معامله می‌شد.
    ۳) WRِ بالا فقط از تلهٔ RRِ نامتقارن (TP=0.5×range, SL=1.5×range) می‌آمد ⇒ در RQS+
       گیتِ G1 (لبهٔ واقعی) رد می‌شود (همان کشفِ S303).

بهبودهای احیا (قانونِ دومِ پروژه — چند بهبودِ همزمان مجاز؛ «همه چیز شناور»):
    • side='LONG'  (پیش‌فرض) هم‌راستا با long-biasِ طلا  ← بهبودِ اصلی
    • فیلترِ سشن (فقط لندن یا فقط نیویورک یا هر دو)         ← حذفِ سشنِ زیان‌ده
    • coiled-spring: range/ATR ≤ atr_max                    ← فقط فنرِ فشرده
    • فیلترِ جهتِ روند: close > EMA(trend_ema)               ← فقط در آپ‌ترند
    • TP/SL شناور بر حسبِ range (k_sl, k_tp) — نه عددِ رند   ← رفعِ اشتباهِ #۷
    • RR نزدیک متقارن (k_tp≈k_sl) ⇒ هم G0(WR≥60) هم G1       ← رفعِ تلهٔ RR

قراردادِ استراتژی: advise(ctx) → dict|None (طبقِ engine/trade_simulator.py).
اجرای بدون look-ahead: بازهٔ افتتاحیه فقط از کندل‌های داخلِ پنجره ساخته می‌شود؛ تصمیم
روی کندلِ بسته‌شدهٔ i، اجرا روی open کندلِ i+1.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import indicators as ind  # noqa: E402


class SessionORB:
    """
    Session Opening-Range Breakout (LONG-only پیش‌فرض).

    پارامترها:
      session_start_hour : ساعتِ UTC آغازِ سشن (۷=لندن، ۱۳=نیویورک).
      or_bars            : تعداد کندلِ سازندهٔ بازهٔ افتتاحیه (بسته به TF).
      trade_window_bars  : چند کندل پس از پایانِ بازه، پنجرهٔ فعالِ شکست باز است.
      side               : 'LONG' | 'SHORT' | 'BOTH'.
      atr_max            : coiled-spring — فقط اگر range/ATR ≤ atr_max (۰ = غیرفعال).
      atr_period         : دورهٔ ATR برای coiled-spring و نرمال‌سازی.
      trend_ema          : فیلترِ جهت (LONG فقط اگر close>EMA؛ ۰ = غیرفعال).
      k_sl, k_tp         : ضرایبِ SL/TP بر حسبِ اندازهٔ بازه (range).
      max_hold           : سقفِ نگه‌داری (کندل).
      min_range_atr      : حداقلِ range/ATR (اجتناب از بازهٔ بیش از حد ریز).
    """

    def __init__(self, session_start_hour=7, or_bars=4, trade_window_bars=32,
                 side='LONG', atr_max=0.0, atr_period=14, trend_ema=0,
                 k_sl=1.0, k_tp=1.0, max_hold=48, min_range_atr=0.0,
                 bad_dow=(), regime_atr_ratio_max=0.0, regime_atr_ma=500):
        self.session_start_hour = session_start_hour
        self.or_bars = or_bars
        self.trade_window_bars = trade_window_bars
        self.side = side
        self.atr_max = atr_max
        self.atr_period = atr_period
        self.trend_ema = trend_ema
        self.k_sl = k_sl
        self.k_tp = k_tp
        self.max_hold = max_hold
        self.min_range_atr = min_range_atr
        self.bad_dow = frozenset(bad_dow)
        # فیلترِ رژیمِ نوسان (بهبودِ کلیدیِ S330): فقط اگر ATR جاری ÷ SMAِ بلندِ ATR
        # ≤ آستانه (رژیمِ آرام/رنج). fade فقط در بازارِ آرام معتبر است. (۰=غیرفعال)
        self.regime_atr_ratio_max = regime_atr_ratio_max
        self.regime_atr_ma = regime_atr_ma
        self._prepared = False

    # ---------------- پیش‌محاسبهٔ بازه‌های افتتاحیهٔ روزانه ----------------
    def _precompute(self, df):
        dt = df['dt']
        self._hour = dt.dt.hour.to_numpy()
        self._dow = dt.dt.dayofweek.to_numpy()
        self._date = dt.dt.date.to_numpy()
        n = len(df)
        h = df['high'].to_numpy()
        l = df['low'].to_numpy()
        c = df['close'].to_numpy()

        self._atr = ind.atr(df, self.atr_period).to_numpy()
        if self.trend_ema > 0:
            self._ema = ind.ema(df['close'], self.trend_ema).to_numpy()
        else:
            self._ema = None

        # SMAِ بلندِ ATR برای فیلترِ رژیمِ نوسان (بهبودِ S330)
        if self.regime_atr_ratio_max > 0:
            self._atr_ma = (pd.Series(self._atr)
                            .rolling(self.regime_atr_ma, min_periods=50)
                            .mean().to_numpy())
        else:
            self._atr_ma = None

        # برای هر کندل: آیا در «پنجرهٔ فعالِ شکست» یک سشنِ معتبر است؟ اگر بله،
        # or_high/or_low/or_range همان سشن را ذخیره کن. بازهٔ افتتاحیه از کندل‌هایی
        # ساخته می‌شود که ساعتشان == session_start_hour است و or_bars تای اول آن روز.
        self._or_high = np.full(n, np.nan)
        self._or_low = np.full(n, np.nan)
        self._or_range = np.full(n, np.nan)
        self._or_atr = np.full(n, np.nan)       # ATR در لحظهٔ پایانِ بازه (برای coiled-spring)
        self._active = np.zeros(n, dtype=bool)   # کندلِ i در پنجرهٔ فعالِ شکست است
        self._session_id = np.full(n, -1, dtype=np.int64)  # شناسهٔ یکتای سشن (برای «یک معامله در سشن»)

        # پیمایشِ روز-به-روز
        i = 0
        sid = 0
        start_h = self.session_start_hour
        while i < n:
            # پیدا کردنِ اولین کندلی که ساعتش == start_h (آغازِ سشن)
            if self._hour[i] != start_h:
                i += 1
                continue
            # بازهٔ افتتاحیه = or_bars کندل از i (که همه در همان روز باشند)
            j0 = i
            j1 = min(i + self.or_bars, n)
            # اطمینان از اینکه همهٔ or_bars در همان تاریخ‌اند
            same_day = all(self._date[k] == self._date[j0] for k in range(j0, j1))
            if (j1 - j0) < self.or_bars or not same_day:
                i = j1
                continue
            or_hi = float(np.max(h[j0:j1]))
            or_lo = float(np.min(l[j0:j1]))
            or_rng = or_hi - or_lo
            end_bar = j1 - 1                 # آخرین کندلِ بازه (بسته شده)
            atr_at_end = self._atr[end_bar]
            # پنجرهٔ فعالِ شکست: از end_bar+1 تا end_bar+trade_window_bars (در همان روز)
            w0 = j1
            w1 = min(j1 + self.trade_window_bars, n)
            for k in range(w0, w1):
                if self._date[k] != self._date[j0]:
                    break
                self._active[k] = True
                self._or_high[k] = or_hi
                self._or_low[k] = or_lo
                self._or_range[k] = or_rng
                self._or_atr[k] = atr_at_end
                self._session_id[k] = sid
            sid += 1
            i = w1  # پرش به بعد از پنجره (یک سشن در روز کافی است برای این start_h)

        self._traded_session = set()   # سشن‌هایی که قبلاً واردشان شده‌ایم
        self._prepared = True

    # ---------------- منطقِ تصمیم ----------------
    def advise(self, ctx):
        if not self._prepared:
            self._precompute(ctx.df)
        i = ctx.i

        # مدیریتِ پوزیشنِ باز
        if ctx.in_position():
            pos = ctx.position
            if (i + 1) - pos['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None

        if not self._active[i]:
            return None
        sid = int(self._session_id[i])
        if sid < 0 or sid in self._traded_session:
            return None

        or_hi = self._or_high[i]
        or_lo = self._or_low[i]
        or_rng = self._or_range[i]
        or_atr = self._or_atr[i]
        if not np.isfinite(or_rng) or or_rng <= 0:
            return None

        # فیلترِ روزِ بد
        nb = i + 1
        if nb >= len(self._dow):
            return None
        if self._dow[nb] in self.bad_dow:
            return None

        # فیلترِ رژیمِ نوسان (بهبودِ کلیدیِ S330): fade فقط در بازارِ آرام.
        # ATR جاری ÷ SMAِ بلندِ ATR باید ≤ آستانه باشد (رژیمِ کم‌نوسان/رنج).
        if self._atr_ma is not None:
            am = self._atr_ma[i]
            if not np.isfinite(am) or am <= 0:
                return None
            regime_ratio = self._atr[i] / am
            if regime_ratio > self.regime_atr_ratio_max:
                return None

        # coiled-spring: بازهٔ باریک نسبت به ATR (فنرِ فشرده)
        if or_atr and np.isfinite(or_atr) and or_atr > 0:
            ratio = or_rng / or_atr
            if self.atr_max > 0 and ratio > self.atr_max:
                return None
            if self.min_range_atr > 0 and ratio < self.min_range_atr:
                return None

        cl = ctx.df['close'].values[i]      # close کندلِ بسته‌شدهٔ i (سببی)

        # فیلترِ جهتِ روند
        up_ok = True
        down_ok = True
        if self._ema is not None:
            up_ok = cl > self._ema[i]
            down_ok = cl < self._ema[i]

        pip = ctx.spec['pip']

        # شکستِ سقف ⇒ LONG (breakout روی close کندلِ بسته‌شده تأیید می‌شود)
        if self.side in ('LONG', 'BOTH') and up_ok and cl > or_hi:
            self._traded_session.add(sid)
            entry = ctx.df['open'].values[nb]   # ورود روی open کندلِ بعد
            sl = entry - self.k_sl * or_rng
            tp = entry + self.k_tp * or_rng
            return {'action': 'LONG', 'sl': sl, 'tp': tp}

        # شکستِ کف ⇒ SHORT
        if self.side in ('SHORT', 'BOTH') and down_ok and cl < or_lo:
            self._traded_session.add(sid)
            entry = ctx.df['open'].values[nb]
            sl = entry + self.k_sl * or_rng
            tp = entry - self.k_tp * or_rng
            return {'action': 'SHORT', 'sl': sl, 'tp': tp}

        # ---------------- منطقِ FADE (شکستِ کاذب / liquidity-grab) ----------------
        # فرضیهٔ معکوس: شکستِ بازهٔ افتتاحیه اغلب کاذب است ⇒ در جهتِ مخالف معامله کن.
        if self.side == 'FADE':
            hi_i = ctx.df['high'].values[i]
            lo_i = ctx.df['low'].values[i]
            # سقف را زد ولی close داخلِ بازه بازگشت ⇒ SHORT (fade)
            if hi_i > or_hi and cl < or_hi:
                self._traded_session.add(sid)
                entry = ctx.df['open'].values[nb]
                sl = entry + self.k_sl * or_rng
                tp = entry - self.k_tp * or_rng
                return {'action': 'SHORT', 'sl': sl, 'tp': tp}
            # کف را زد ولی close داخلِ بازه بازگشت ⇒ LONG (fade)
            if lo_i < or_lo and cl > or_lo:
                self._traded_session.add(sid)
                entry = ctx.df['open'].values[nb]
                sl = entry - self.k_sl * or_rng
                tp = entry + self.k_tp * or_rng
                return {'action': 'LONG', 'sl': sl, 'tp': tp}

        return None
