# -*- coding: utf-8 -*-
"""
s320_bb_rsi_meanrev_revival.py — تلاشِ احیای S01 (BB+RSI Mean-Reversion، طلا)
================================================================================
منشأ: S01 (اولین استراتژیِ پروژه) — `strategies/s01_bb_rsi_meanrev.py`.
وضعیتِ سوخته: WR خام ۴۷.۰٪، expectancy منفی، PnL منفی (کلِ ۱۵۰k کندلِ M15).

فرضیهٔ احیا (تحلیلِ ریشه‌ایِ نشستِ S320):
--------------------------------------------------------------------------------
S01 خام BB+RSI را «بی‌تفاوت به رژیم» می‌زد. اما mean-reversion یک قانونِ ریاضیِ
مشروط است: فقط در رژیمِ **رنج (بدونِ روند)** معنا دارد. در رژیمِ روند، لمسِ باندِ
بولینگر سیگنالِ «walking the band» (ادامه) است نه برگشت. ترکیبِ بی‌تفاوتِ دو رژیم
⇒ edge خطیِ صفر (که S01 در تحلیلِ autocorrelation دید).

چهار اهرمِ بهبود (قانونِ دومِ پروژه: چند بهبودِ همزمان مجاز؛ قانونِ «شاید»: شناور):
  A) فیلترِ رژیمِ رنج: ADX(14) < adx_max  (Wilder: ADX پایین = بی‌روند = زمینِ MR)
  B) عدم‌تقارنِ ساختاریِ طلا (درسِ بنیادیِ پروژه): طلا بایاسِ صعودی دارد ⇒
     LONG-MR (خریدِ کف در رنج) با روندِ بلندمدت هم‌سوست؛ SHORT-MR (fade سقف) شکننده.
     پس هر سمت جداگانه آزموده می‌شود.
  C) RR متقارن (درسِ S303/S306/S312): TP=SL بر حسبِ ATR ⇒ هم WR≥۶۰٪ هم wr_excess>0.
  D) فیلترِ ساعت/سشن (درسِ S303): حذفِ ساعاتِ پرمومنتومِ آمریکا که MR در آن‌ها می‌بازد.

همه‌چیز رویداد-محور (`engine/trade_simulator.py`) + RQS+ (`engine/rqs.py`) سنجیده
می‌شود؛ اندیکاتورها causal (shift-safe) پیش‌محاسبه می‌شوند.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS   # noqa: E402
from engine import rqs as RQS               # noqa: E402
from engine import indicators as ind        # noqa: E402


# ============================================================
# استراتژیِ قابلِ‌تنظیمِ BB+RSI Mean-Reversion (رویداد-محور)
#   sl/tp بر حسبِ ATR در لحظهٔ سیگنال (نه عددِ رند — رفعِ اشتباهِ رایجِ #7).
# ============================================================
class BBRSIMeanRev:
    def __init__(self, side='LONG',
                 bb_period=20, bb_k=2.0, rsi_period=14,
                 rsi_long=30.0, rsi_short=70.0,
                 atr_period=14, sl_atr=1.5, tp_atr=1.5, max_hold=100,
                 # --- فیلترهای احیا (۰/None = غیرفعال) ---
                 adx_max=None,          # A: فقط ADX < adx_max (رژیمِ رنج)
                 adx_period=14,
                 bad_hours=frozenset(), # D: ساعاتِ UTC ممنوع
                 trend_gate_ema=None,   # فقط اگر close نسبت به EMA در سمتِ درست باشد
                 dist_atr_min=0.0):     # حداقلِ فاصلهٔ close تا باند بر حسبِ ATR
        self.side = side
        self.bb_period = bb_period; self.bb_k = bb_k
        self.rsi_period = rsi_period
        self.rsi_long = rsi_long; self.rsi_short = rsi_short
        self.atr_period = atr_period
        self.sl_atr = sl_atr; self.tp_atr = tp_atr; self.max_hold = max_hold
        self.adx_max = adx_max; self.adx_period = adx_period
        self.bad_hours = frozenset(bad_hours)
        self.trend_gate_ema = trend_gate_ema
        self.dist_atr_min = dist_atr_min
        self._sig = None; self._atr = None; self._hour = None

    def _precompute(self, df):
        c = df['close']
        cl = c.to_numpy()
        n = len(cl)
        lower, mid, upper = ind.bollinger(c, self.bb_period, self.bb_k)
        lower = lower.to_numpy(); upper = upper.to_numpy()
        rsi = ind.rsi(c, self.rsi_period).to_numpy()
        self._atr = ind.atr(df, self.atr_period).to_numpy()
        atr_np = self._atr
        # رژیم
        if self.adx_max is not None:
            adx = ind.adx(df, self.adx_period)
            adx = adx[0] if isinstance(adx, tuple) else adx
            adx = pd.Series(np.asarray(adx)).fillna(100).to_numpy()
            range_regime = adx < self.adx_max
        else:
            range_regime = np.ones(n, dtype=bool)
        # گیتِ روندِ بلندمدت (اختیاری)
        if self.trend_gate_ema is not None:
            ema_lt = ind.ema(c, self.trend_gate_ema).to_numpy()
            if self.side == 'LONG':
                trend_ok = cl > ema_lt      # فقط کفِ رنج در روندِ صعودیِ کلان
            else:
                trend_ok = cl < ema_lt
        else:
            trend_ok = np.ones(n, dtype=bool)
        # فاصلهٔ فراتر از باند بر حسبِ ATR (عمقِ افراط)
        with np.errstate(invalid='ignore'):
            if self.side == 'LONG':
                depth_atr = (lower - cl) / np.where(atr_np > 0, atr_np, np.nan)
            else:
                depth_atr = (cl - upper) / np.where(atr_np > 0, atr_np, np.nan)
        depth_ok = (depth_atr >= self.dist_atr_min if self.dist_atr_min > 0
                    else np.ones(n, dtype=bool))
        depth_ok = np.where(np.isnan(depth_ok), False, depth_ok).astype(bool)
        # سیگنالِ خام
        if self.side == 'LONG':
            raw = (cl < lower) & (rsi < self.rsi_long)
        else:
            raw = (cl > upper) & (rsi > self.rsi_short)
        raw = raw & range_regime & trend_ok & depth_ok
        raw = np.where(np.isnan(raw), False, raw).astype(bool)
        # shift(1): تصمیم روی کندلِ بسته‌شده، اجرا روی open بعدی
        self._sig = pd.Series(raw).shift(1).fillna(False).to_numpy()
        self._hour = df['dt'].dt.hour.to_numpy()

    def advise(self, ctx):
        if self._sig is None:
            self._precompute(ctx.df)
        i = ctx.i
        if ctx.in_position():
            if (i + 1) - ctx.position['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None
        if not self._sig[i]:
            return None
        nb = i + 1
        if nb < len(self._hour) and self._hour[nb] in self.bad_hours:
            return None
        a = self._atr[i]
        if not np.isfinite(a) or a <= 0:
            return None
        price = ctx.price()
        if self.side == 'LONG':
            return {'action': 'LONG',
                    'sl': price - self.sl_atr * a,
                    'tp': price + self.tp_atr * a}
        else:
            return {'action': 'SHORT',
                    'sl': price + self.sl_atr * a,
                    'tp': price - self.tp_atr * a}


def run(tag, strat, tf, asset='XAUUSD', warmup=300):
    df = TS.load_data(tf)
    tr, eq = TS.simulate(df, strat, asset, warmup=warmup)
    r = RQS.compute_rqs(tr, asset)
    print(RQS.format_report(tag, r))
    return r


if __name__ == '__main__':
    # baseline خام (side=LONG و side=SHORT) روی XAUUSD M5
    print("=== BASELINE خام (بدونِ هیچ فیلتر) — XAUUSD M5 ===")
    run('S01raw-LONG  M5', BBRSIMeanRev(side='LONG',  sl_atr=1.5, tp_atr=1.5), 'XAUUSD_M5')
    run('S01raw-SHORT M5', BBRSIMeanRev(side='SHORT', sl_atr=1.5, tp_atr=1.5), 'XAUUSD_M5')
