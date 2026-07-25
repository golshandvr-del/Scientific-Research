# -*- coding: utf-8 -*-
"""
sim_strategies.py — پیاده‌سازیِ استراتژی‌ها با پروتکلِ advise() شبیه‌سازِ رویداد-محور
================================================================================
هر کلاس متدِ advise(ctx) دارد که طبقِ قراردادِ trade_simulator عمل می‌کند.
این‌ها همان منطقِ اصلیِ استراتژی‌های مستندِ پروژه‌اند، اما به‌جای «سیگنالِ برداری»،
به‌صورتِ «مشاورِ حالت‌دار» بازنویسی شده‌اند تا با کاربرِ واقعیِ حساب یکی باشند.

نکته: sl/tp بر حسبِ *قیمت* برگردانده می‌شوند (نه pip) تا با adviceِ سایت یکی باشند.
"""
import numpy as np
import pandas as pd


# ============================================================
# S164 — EURUSD Pre-Month-End Fix Reversal (SHORT)
#   from_end == -3 (۳ روز کاری مانده به آخرِ ماه) و ساعت ۱۳ UTC
#   SL=15pip, TP=20pip, max_hold=12 کندلِ M15
# ============================================================
class S164_PreEOM_Short:
    def __init__(self, sl_pip=15, tp_pip=20, max_hold=12):
        self.sl_pip = sl_pip
        self.tp_pip = tp_pip
        self.max_hold = max_hold
        self._from_end = None
        self._hour = None

    def _precompute(self, df):
        dt = df['dt']
        hour = dt.dt.hour.values
        date = dt.dt.date
        d = pd.DataFrame({'date': date})
        d['ym'] = pd.to_datetime(dt.dt.strftime('%Y-%m')).values
        days = d.drop_duplicates('date').reset_index(drop=True)
        days['rank'] = days.groupby('ym').cumcount()
        cnt = days.groupby('ym')['date'].transform('count')
        days['from_end'] = days['rank'] - cnt
        mp = dict(zip(days['date'], days['from_end']))
        self._from_end = d['date'].map(mp).astype(int).values
        self._hour = hour

    def advise(self, ctx):
        if self._from_end is None:
            self._precompute(ctx.df)
        i = ctx.i
        # مدیریت: max_hold
        if ctx.in_position():
            pos = ctx.position
            if (i + 1) - pos['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None
        # ورود: from_end == -3 و ساعت ۱۳
        if self._from_end[i] == -3 and self._hour[i] == 13:
            price = ctx.price()
            pip = ctx.spec['pip']
            sl = price + self.sl_pip * pip   # SHORT ⇒ SL بالاتر
            tp = price - self.tp_pip * pip   # SHORT ⇒ TP پایین‌تر
            return {'action': 'SHORT', 'sl': sl, 'tp': tp}
        return None


# ============================================================
# S73 — EURUSD Session-Open Drift (LONG, buy-the-dip ساعتِ ۰ UTC)
#   ساعت ۰ UTC + فیلترِ pullback (close < close چند کندل قبل)
#   SL=12pip, TP=12pip, max_hold=6
# ============================================================
class S73_SessionDrift_Long:
    def __init__(self, sl_pip=12, tp_pip=12, max_hold=6, pullback_lb=4):
        self.sl_pip = sl_pip
        self.tp_pip = tp_pip
        self.max_hold = max_hold
        self.pullback_lb = pullback_lb
        self._hour = None

    def _precompute(self, df):
        self._hour = df['dt'].dt.hour.values

    def advise(self, ctx):
        if self._hour is None:
            self._precompute(ctx.df)
        i = ctx.i
        if ctx.in_position():
            pos = ctx.position
            if (i + 1) - pos['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None
        # ورود در open کندلِ ساعتِ ۰ ⇒ یعنی کندلِ فعلی i ساعتش ۲۳ است و بعدی ۰
        # ما در انتهایِ کندلِ i تصمیم می‌گیریم و روی open کندلِ i+1 اجرا می‌کنیم.
        nb = i + 1
        if nb >= len(self._hour):
            return None
        if self._hour[nb] == 0 and self._hour[i] != 0:
            # فیلترِ pullback: close فعلی < close چند کندل قبل (buy-the-dip)
            closes = ctx.closes()
            if len(closes) > self.pullback_lb:
                if closes[-1] < closes[-1 - self.pullback_lb]:
                    price = ctx.df['open'].values[nb]  # ورود روی open کندلِ بعد
                    pip = ctx.spec['pip']
                    sl = price - self.sl_pip * pip
                    tp = price + self.tp_pip * pip
                    return {'action': 'LONG', 'sl': sl, 'tp': tp}
        return None


# ============================================================
# S302 — S164 احیا‌شده با فیلترِ روزِ هفته (Wed/Thu)
#   کشف: پدیدهٔ month-end-fix در وسطِ هفته (چهارشنبه/پنج‌شنبه) تمیزتر و قوی‌تر است؛
#   دوشنبه/جمعه نویزِ بازکردن/بستنِ هفته دارند. فیلتر WR را 59.5٪→70.0٪ و PF را
#   1.69→2.50 می‌برد و RQS+=93.1 (همه ۶ گیت پاس، هر ۹ سالِ walk-forward مثبت).
# ============================================================
class S302_PreEOM_Short_WedThu(S164_PreEOM_Short):
    """S164 + فیلترِ روزِ هفته: فقط اگر روزِ ورود چهارشنبه(2) یا پنج‌شنبه(3) باشد."""
    ALLOWED_DOW = (2, 3)

    def advise(self, ctx):
        adv = super().advise(ctx)
        if adv and adv.get('action') == 'SHORT':
            nb = ctx.i + 1
            if nb < len(ctx.df):
                dow = ctx.df['dt'].dt.dayofweek.values[nb]
                if dow not in self.ALLOWED_DOW:
                    return None
        return adv


# ============================================================
# S173 — Brooks Market-Inertia (SHORT, XAUUSD, M15)  ← لایهٔ سوختهٔ کاندیدِ احیا
#   منطق (فصلِ ۱ Brooks، «trend-fade reversal-attempt»):
#     روندِ نزولی: emaF(20) < emaS(50)  و  ADX(14) > adx_hi(28)
#     تلاشِ برگشتی: close > بیشینهٔ سقفِ lb(20) کندلِ اخیر  ⇒ SHORT (fade)
#   خام (برداری): WR≈50٪, PF≈1.36. رویداد-محور: WR=52.1٪ ⇒ فقط G0 رد (۵ گیت پاس).
#   SL=250pip, TP=375pip, max_hold=48 کندلِ M15.
#   اندیکاتورها یک‌بار روی کلِ df پیش‌محاسبه می‌شوند؛ در advise فقط تا اندیسِ i خوانده
#   می‌شوند (سببی). shift(1) در سیگنال ⇒ تصمیم روی کندلِ بسته‌شده، اجرا روی open بعدی.
# ============================================================
class S173_MarketInertia_Short:
    def __init__(self, ef=20, es=50, adx_hi=28, lb=20,
                 sl_pip=250, tp_pip=375, max_hold=48):
        self.ef = ef; self.es = es; self.adx_hi = adx_hi; self.lb = lb
        self.sl_pip = sl_pip; self.tp_pip = tp_pip; self.max_hold = max_hold
        self._sig = None

    def _precompute(self, df):
        import sys, os
        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from engine import indicators as ind
        c = df['close']
        h = df['high'].to_numpy(); l = df['low'].to_numpy(); cl = c.to_numpy()
        emaF = ind.ema(c, self.ef).to_numpy()
        emaS = ind.ema(c, self.es).to_numpy()
        adx = ind.adx(df, 14)
        adx = adx[0] if isinstance(adx, tuple) else adx
        adx = pd.Series(np.asarray(adx)).fillna(0).to_numpy()
        trend = adx > self.adx_hi
        prev_hh = pd.Series(h).rolling(self.lb).max().shift(1).to_numpy()
        rev_attempt = cl > prev_hh                    # تلاشِ برگشتی در روندِ نزولی
        raw = trend & (emaF < emaS) & rev_attempt
        # shift(1): سیگنال روی کندلِ بسته‌شده تصمیم گرفته می‌شود
        self._sig = pd.Series(raw).shift(1).fillna(False).to_numpy()

    def advise(self, ctx):
        if self._sig is None:
            self._precompute(ctx.df)
        i = ctx.i
        if ctx.in_position():
            pos = ctx.position
            if (i + 1) - pos['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None
        if self._sig[i]:
            price = ctx.price(); pip = ctx.spec['pip']
            sl = price + self.sl_pip * pip     # SHORT ⇒ SL بالاتر
            tp = price - self.tp_pip * pip     # SHORT ⇒ TP پایین‌تر
            return {'action': 'SHORT', 'sl': sl, 'tp': tp}
        return None


# ============================================================
# S303 — S173 احیا‌شده: Market-Inertia SHORT + فیلترِ سشن/روز + RR متقارن
#   کشف: fade کردنِ «تلاشِ برگشتی» فقط در سشنِ آسیا/لندن (رنج‌تر) کار می‌کند؛
#     در سشنِ پرمومنتومِ آمریکا (h15-18) روند ادامه می‌دهد و شورت ضرر می‌کند.
#   سه بهبودِ همزمان (قانونِ دومِ پروژه: چند فیلتر مجاز):
#     ۱) حذفِ ساعاتِ بد {3,5,12,15,16,17,18} (WR<45٪)
#     ۲) حذفِ سه‌شنبه (dow=1، WR=40٪)
#     ۳) TP از 375→250 (RR متقارن 1:1) ⇒ WR≥60٪ + G1 پاس + maxDD 4.3٪
#   نتیجه: RQS+=87.6، WR=60.9٪، PF=1.88، هر ۴ پنجرهٔ WF مثبت، هر ۷ سال مثبت.
# ============================================================
class S303_MarketInertia_Short_Filtered(S173_MarketInertia_Short):
    BAD_HOURS = frozenset({3, 5, 12, 15, 16, 17, 18})
    BAD_DOW = frozenset({1})   # سه‌شنبه

    def __init__(self, sl_pip=250, tp_pip=250, max_hold=48, **kw):
        super().__init__(sl_pip=sl_pip, tp_pip=tp_pip, max_hold=max_hold, **kw)

    def advise(self, ctx):
        adv = super().advise(ctx)
        if adv and adv.get('action') == 'SHORT':
            nb = ctx.i + 1
            if nb < len(ctx.df):
                ts = pd.Timestamp(ctx.df['dt'].values[nb])
                if ts.hour in self.BAD_HOURS:
                    return None
                if ts.dayofweek in self.BAD_DOW:
                    return None
        return adv


# ============================================================
# S306 — S141 احیا‌شده: XAUUSD Turn-of-Month Drift LONG + RR متقارن
#   منطق (اثرِ turn-of-month): اولین روزِ معاملاتیِ هر ماه، جریانِ ورودیِ
#     صندوق‌های بازنشستگی/شاخصی قیمتِ طلا را در ساعاتِ لندن (8-10 UTC) بالا می‌برد.
#   بهبودِ نسبت به خام: TP از drift-exit به RR متقارن (SL250/TP250) ⇒ WR 49٪→61.3٪.
#   نتیجه: RQS+=85.9، WR=61.3٪، PF=1.93، maxDD=4.2٪، هر ۴ پنجرهٔ WF مثبت، هر ۷ سال مثبت.
#   tom_rel==1 یعنی اولین روزِ تقویمیِ معاملاتیِ ماه (rank_in_month == 1).
# ============================================================
class S306_TurnOfMonth_Long:
    ENTRY_HOURS = frozenset({8, 9, 10})

    def __init__(self, sl_pip=250, tp_pip=250, max_hold=24):
        self.sl_pip = sl_pip; self.tp_pip = tp_pip; self.max_hold = max_hold
        self._tom = None; self._hour = None

    def _precompute(self, df):
        dt = df['dt']
        d = pd.DataFrame({'date': dt.dt.date})
        d['ym'] = pd.to_datetime(dt.dt.strftime('%Y-%m')).values
        days = d.drop_duplicates('date').reset_index(drop=True)
        days['rank'] = days.groupby('ym').cumcount() + 1   # 1 = اولین روزِ ماه
        mp = dict(zip(days['date'], days['rank']))
        self._tom = d['date'].map(mp).astype(int).to_numpy()
        self._hour = dt.dt.hour.to_numpy()

    def advise(self, ctx):
        if self._tom is None:
            self._precompute(ctx.df)
        i = ctx.i
        if ctx.in_position():
            if (i + 1) - ctx.position['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None
        if self._tom[i] == 1 and self._hour[i] in self.ENTRY_HOURS:
            price = ctx.price(); pip = ctx.spec['pip']
            return {'action': 'LONG',
                    'sl': price - self.sl_pip * pip,
                    'tp': price + self.tp_pip * pip}
        return None


STRATEGY_REGISTRY = {
    'S164': dict(cls=S164_PreEOM_Short, asset='EURUSD', tf='EURUSD_M15',
                 label='S164 EURUSD Pre-EOM Short'),
    'S73':  dict(cls=S73_SessionDrift_Long, asset='EURUSD', tf='EURUSD_M5',
                 label='S73 EURUSD Session Drift Long'),
    'S302': dict(cls=S302_PreEOM_Short_WedThu, asset='EURUSD', tf='EURUSD_M15',
                 label='S302 EURUSD Pre-EOM Short + Wed/Thu filter (revived S164)'),
    'S173': dict(cls=S173_MarketInertia_Short, asset='XAUUSD', tf='XAUUSD_M15',
                 label='S173 XAUUSD Market-Inertia Short (revival candidate)'),
    'S303': dict(cls=S303_MarketInertia_Short_Filtered, asset='XAUUSD', tf='XAUUSD_M15',
                 label='S303 XAUUSD Market-Inertia Short + session/dow filter (revived S173)'),
    'S306': dict(cls=S306_TurnOfMonth_Long, asset='XAUUSD', tf='XAUUSD_M15',
                 label='S306 XAUUSD Turn-of-Month Drift Long + symmetric RR (revived S141)'),
}
