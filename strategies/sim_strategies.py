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


STRATEGY_REGISTRY = {
    'S164': dict(cls=S164_PreEOM_Short, asset='EURUSD', tf='EURUSD_M15',
                 label='S164 EURUSD Pre-EOM Short'),
    'S73':  dict(cls=S73_SessionDrift_Long, asset='EURUSD', tf='EURUSD_M5',
                 label='S73 EURUSD Session Drift Long'),
}
