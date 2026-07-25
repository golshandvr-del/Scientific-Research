# -*- coding: utf-8 -*-
"""
S310 — احیای S144 (End-of-Month Drift LONG، طلا) — حملهٔ نو به تنشِ G0↔G2
================================================================================
هدف: لایهٔ سوختهٔ S144/S308 که فقط G2 (PF≥1.3) را با اختلافِ ۰.۰۱ رد کرد، اکنون با:
  (۱) قانونِ مولتی‌تایم‌فریم: تستِ مجزا روی M5/M15/M30/H1 (S308 فقط M15 بود — اشتباهِ رایج #۵)
  (۲) فیلترهای «کیفیتِ ورود» (نه دستکاریِ TP/SL): بردنِ PF بالا بدونِ قربانی‌کردنِ WR
      - کیفیتِ کندلِ ورود (body_ratio, close_pos)  ← درسِ S186
      - رژیمِ نوسان (ATR نه‌خیلی‌بالا)  ← بازنده‌های بزرگ در climax اتفاق می‌افتند
      - جهتِ روندِ کلان (close>EMA200 یا شیبِ EMA)
  (۳) TP/SL مخصوصِ هر TF (اشتباهِ رایج #۶: TP/SL یکسان برای همه)

تز: تنشِ G0↔G2 «کاذب» است. PF پایین از «بازنده‌های بزرگ» می‌آید، نه از TP دور.
    اگر ورودهایی را که به بازنده‌های بزرگ تبدیل می‌شوند (climax/low-quality) حذف کنیم،
    هم WR بالا می‌ماند (G0) هم زیانِ کل کم می‌شود ⇒ PF↑ (G2). تنش شکسته می‌شود.

بازتولید:
  python3 strategies/s310_eom_drift_revival.py
"""
import os
import sys
import itertools
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS   # noqa: E402
from engine import rqs as RQS              # noqa: E402
from engine import indicators as ind       # noqa: E402


# ------------------------------------------------------------------
# استراتژیِ پایه‌دار: End-of-Month Drift LONG با فیلترهای کیفیتِ اختیاری
# ------------------------------------------------------------------
class EOMDriftLong:
    """
    ورود LONG وقتی:
      - from_end ∈ REL  (روزهای کاریِ مانده به پایانِ ماه؛ منفی)
      - hour ∈ HOURS (UTC)
      - [اختیاری] فیلترهای کیفیت پاس شوند
    خروج: TP/SL ثابت یا max_hold.

    همهٔ فیلترها causal اند: روی کندلِ بستهٔ i تصمیم، اجرا روی open کندلِ i+1.
    """
    def __init__(self, rel=(-7,), hours=(20, 21, 22, 23),
                 sl_pip=180, tp_pip=220, max_hold=32,
                 # فیلترهای کیفیت (None = خاموش)
                 min_body_ratio=None,     # بدنهٔ کندلِ ورود / رنج ≥ این مقدار
                 min_close_pos=None,      # موقعیتِ close در رنجِ کندل ≥ این (close قوی)
                 atr_max_mult=None,       # ATR فعلی ≤ atr_max_mult × میانهٔ ATR (ضدِ climax)
                 atr_min_mult=None,       # ATR فعلی ≥ atr_min_mult × میانه (ضدِ رنجِ مرده)
                 ema_trend=None,          # 'above' ⇒ close>EMA(ema_len)
                 ema_len=200,
                 require_up_bar=False,    # کندلِ ورود صعودی (close>open)
                 ):
        self.rel = frozenset(rel)
        self.hours = frozenset(hours)
        self.sl_pip = sl_pip
        self.tp_pip = tp_pip
        self.max_hold = max_hold
        self.min_body_ratio = min_body_ratio
        self.min_close_pos = min_close_pos
        self.atr_max_mult = atr_max_mult
        self.atr_min_mult = atr_min_mult
        self.ema_trend = ema_trend
        self.ema_len = ema_len
        self.require_up_bar = require_up_bar
        self._ready = False

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

        o = df['open'].values; h = df['high'].values
        low = df['low'].values; c = df['close'].values
        rng = np.maximum(h - low, 1e-9)
        self._body_ratio = np.abs(c - o) / rng
        self._close_pos = (c - low) / rng
        self._up_bar = c > o

        atr = ind.atr(df, 14).values
        atr_med = pd.Series(atr).rolling(200, min_periods=50).median().values
        with np.errstate(invalid='ignore', divide='ignore'):
            self._atr_ratio = atr / atr_med
        self._atr_ratio = np.nan_to_num(self._atr_ratio, nan=1.0)

        ema = ind.ema(df['close'], self.ema_len).values
        self._above_ema = c > ema
        self._ready = True

    def _quality_ok(self, i):
        if self.min_body_ratio is not None and self._body_ratio[i] < self.min_body_ratio:
            return False
        if self.min_close_pos is not None and self._close_pos[i] < self.min_close_pos:
            return False
        if self.atr_max_mult is not None and self._atr_ratio[i] > self.atr_max_mult:
            return False
        if self.atr_min_mult is not None and self._atr_ratio[i] < self.atr_min_mult:
            return False
        if self.ema_trend == 'above' and not self._above_ema[i]:
            return False
        if self.require_up_bar and not self._up_bar[i]:
            return False
        return True

    def advise(self, ctx):
        if not self._ready:
            self._precompute(ctx.df)
        i = ctx.i
        if ctx.in_position():
            if (i + 1) - ctx.position['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None
        if self._from_end[i] in self.rel and self._hour[i] in self.hours:
            if not self._quality_ok(i):
                return None
            price = ctx.price(); pip = ctx.spec['pip']
            return {'action': 'LONG',
                    'sl': price - self.sl_pip * pip,
                    'tp': price + self.tp_pip * pip}
        return None


def run(tf_name, asset, strat, warmup=2000):
    df = TS.load_data(tf_name)
    tr, eq = TS.simulate(df, strat, asset, warmup=warmup)
    r = RQS.compute_rqs(tr, asset)
    return r, tr


# ماکسِ نگه‌داری متناسب با TF (تقریباً همان ۸ ساعتِ M15=32) — اشتباهِ رایج #۶
MH_BY_TF = {'M5': 96, 'M15': 32, 'M30': 16, 'H1': 8, 'H4': 3}
# ساعت‌های ورود: چون درایو شبانه است، برای TFهای بزرگ‌تر پنجره را نگه می‌داریم
HOURS_BY_TF = {'M5': (20, 21, 22, 23), 'M15': (20, 21, 22, 23),
               'M30': (20, 21, 22, 23), 'H1': (20, 21, 22, 23), 'H4': (20,)}


def phase_baseline():
    """گامِ ۱: بازتولیدِ baseline S308 روی همهٔ TFها (بدونِ فیلترِ کیفیت)."""
    print("\n" + "=" * 78)
    print("PHASE 1 — BASELINE (S308 replication) multi-timeframe, XAUUSD, NO quality filter")
    print("=" * 78)
    for tf in ['M5', 'M15', 'M30', 'H1']:
        tfn = f'XAUUSD_{tf}'
        strat = EOMDriftLong(rel=(-7,), hours=HOURS_BY_TF[tf],
                             sl_pip=180, tp_pip=220, max_hold=MH_BY_TF[tf])
        r, tr = run(tfn, 'XAUUSD', strat)
        print(RQS.format_report(f'EOM base {tf}', r))


def phase_autopsy(tf='M15'):
    """گامِ ۲: کالبدشکافیِ بازنده‌ها روی TFِ منتخب — کدام بُعد بازنده‌های بزرگ را جدا می‌کند؟"""
    print("\n" + "=" * 78)
    print(f"PHASE 2 — AUTOPSY of winners vs losers ({tf}) — where do big losses hide?")
    print("=" * 78)
    tfn = f'XAUUSD_{tf}'
    strat = EOMDriftLong(rel=(-7,), hours=HOURS_BY_TF[tf],
                         sl_pip=180, tp_pip=220, max_hold=MH_BY_TF[tf])
    strat._precompute(TS.load_data(tfn))
    r, tr = run(tfn, 'XAUUSD', strat)
    # ضمیمهٔ ویژگی‌های کندلِ ورود به هر معامله
    df = TS.load_data(tfn)
    strat2 = EOMDriftLong(rel=(-7,), hours=HOURS_BY_TF[tf],
                          sl_pip=180, tp_pip=220, max_hold=MH_BY_TF[tf])
    strat2._precompute(df)
    rows = []
    for _, t in tr.iterrows():
        eb = int(t['entry_bar']) - 1  # کندلِ تصمیم (بستهٔ i)؛ ورود روی i+1
        if eb < 0 or eb >= len(df):
            continue
        rows.append(dict(
            outcome=t['outcome'], pnl_pip=t['pnl_pip'],
            body=strat2._body_ratio[eb], cpos=strat2._close_pos[eb],
            atr=strat2._atr_ratio[eb], upbar=strat2._up_bar[eb],
            above=strat2._above_ema[eb], hour=strat2._hour[eb],
        ))
    a = pd.DataFrame(rows)
    if len(a) == 0:
        print("no trades"); return
    win = a[a.outcome == 'win']; los = a[a.outcome == 'loss']
    print(f"n={len(a)}  wins={len(win)}  losses={len(los)}")
    print(f"avg WIN  pnl_pip = {win.pnl_pip.mean():+.1f}  |  avg LOSS pnl_pip = {los.pnl_pip.mean():+.1f}")
    print(f"sum WINS = {win.pnl_pip.sum():+.0f}  |  sum LOSSES = {los.pnl_pip.sum():+.0f}  ⇒ PF≈{-win.pnl_pip.sum()/los.pnl_pip.sum():.2f}")
    print("--- means (win vs loss) — a discriminating feature separates them ---")
    for col in ['body', 'cpos', 'atr']:
        print(f"  {col:6s}: win={win[col].mean():.3f}  loss={los[col].mean():.3f}  "
              f"Δ={win[col].mean()-los[col].mean():+.3f}")
    print(f"  upbar%: win={100*win.upbar.mean():.0f}%  loss={100*los.upbar.mean():.0f}%")
    print(f"  above%: win={100*win.above.mean():.0f}%  loss={100*los.above.mean():.0f}%")
    print("--- loss rate by ATR-regime bucket (climax hypothesis) ---")
    for lo, hi in [(0, 0.8), (0.8, 1.1), (1.1, 1.5), (1.5, 99)]:
        sub = a[(a.atr >= lo) & (a.atr < hi)]
        if len(sub):
            print(f"  ATR[{lo},{hi}): n={len(sub):3d}  loss_rate={100*(sub.outcome=='loss').mean():.0f}%  "
                  f"avg_pnl={sub.pnl_pip.mean():+.1f}")


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')
    phase_baseline()
    phase_autopsy('M15')
    phase_autopsy('M5')
