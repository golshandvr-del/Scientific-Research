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


def phase_search(tf='M15', asset='XAUUSD', rel=(-7,), quiet_top=12):
    """گامِ ۳: جستجوی فیلترهای کیفیت برای شکستنِ تنشِ G0↔G2 روی یک TF.

    محورها (طبقِ کالبدشکافی): atr_min (ضدِ رنجِ مرده)، body/close_pos، atr_max (ضدِ climax)،
    ema_trend، و TP/SL مخصوصِ TF. هدف: RQS+≥80 (هر ۶ گیت).
    """
    print("\n" + "=" * 78)
    print(f"PHASE 3 — FILTER SEARCH to break G0<->G2 tension  ({asset} {tf}, rel={rel})")
    print("=" * 78)
    tfn = f'{asset}_{tf}'
    df = TS.load_data(tfn)
    hours = HOURS_BY_TF[tf]
    mh = MH_BY_TF[tf]

    # گرید بر پایهٔ کالبدشکافی هرس شده تا زمانِ اجرا معقول بماند
    atr_min_grid  = [None, 0.8, 0.9]
    atr_max_grid  = [None, 1.5]
    body_grid     = [None, 0.45]
    cpos_grid     = [None, 0.5]
    ema_grid      = [None, 'above']
    # TP/SL مخصوصِ TF (نه اعدادِ رند — طیفِ ریز)
    tpsl_grid = {
        'M5':  [(170, 210), (200, 200), (180, 250)],
        'M15': [(180, 220), (200, 200), (170, 250)],
        'M30': [(200, 240), (240, 240)],
        'H1':  [(240, 300), (300, 300)],
    }[tf]

    results = []
    combos = itertools.product(atr_min_grid, atr_max_grid, body_grid,
                               cpos_grid, ema_grid, tpsl_grid)
    for amin, amax, body, cpos, ema, (sl, tp) in combos:
        if amin is not None and amax is not None and amin >= amax:
            continue
        strat = EOMDriftLong(rel=rel, hours=hours, sl_pip=sl, tp_pip=tp, max_hold=mh,
                             atr_min_mult=amin, atr_max_mult=amax,
                             min_body_ratio=body, min_close_pos=cpos, ema_trend=ema)
        r, tr = run(tfn, asset, strat)
        m = r['metrics']
        if m['n_trades'] < 30:
            continue
        results.append((r['rqs_score'], r['passed'], m, dict(
            amin=amin, amax=amax, body=body, cpos=cpos, ema=ema, sl=sl, tp=tp)))
    results.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print(f"tested combos with n>=30: {len(results)}")
    for score, passed, m, cfg in results[:quiet_top]:
        tag = 'ACCEPT' if passed else 'reject'
        print(f"  RQS={score:5.1f} {tag} | n={m['n_trades']:3d} WR={m['win_rate']:.1f}% "
              f"PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f}% MCL={m['max_consec_losses']} "
              f"p={m['p_value']:.3f} | amin={cfg['amin']} amax={cfg['amax']} "
              f"body={cfg['body']} cpos={cfg['cpos']} ema={cfg['ema']} SL{cfg['sl']}/TP{cfg['tp']}")
    return results


def phase_rel_stability(tf='M15', asset='XAUUSD'):
    """گامِ ۴: فیلترِ کیفیتِ برنده ثابت، جاروبِ ترکیب‌های rel برای پاس‌کردنِ G4.

    کشفِ فاز ۳: با atr_min+close_pos+ema=above هر ۵ گیت پاس شد جز G4 (پنجرهٔ دومِ WF منفی).
    فرضیه: rel=-7 تنها، نمونه را نازک و یک پنجره را شکننده می‌کند. افزودنِ rel های مجاور
    (نمونهٔ بیشتر، هموارتر) ممکن است پایداری را بازگرداند بدونِ قربانی‌کردنِ کیفیت.
    """
    print("\n" + "=" * 78)
    print(f"PHASE 4 — REL sweep with winning quality filter ({asset} {tf}) to pass G4")
    print("=" * 78)
    tfn = f'{asset}_{tf}'
    hours = HOURS_BY_TF[tf]; mh = MH_BY_TF[tf]
    rel_options = [(-7,), (-6, -7), (-7, -8), (-6, -7, -8),
                   (-5, -6, -7), (-5, -6, -7, -8)]
    # چند نسخهٔ فیلترِ کیفیت (بر پایهٔ فاز ۳)
    filt_options = [
        dict(atr_min_mult=0.9, min_close_pos=0.5, ema_trend='above'),
        dict(atr_min_mult=0.8, min_close_pos=0.5, ema_trend='above'),
        dict(atr_min_mult=0.9, min_close_pos=0.45, ema_trend='above'),
        dict(atr_min_mult=1.0, min_close_pos=0.5, ema_trend='above'),
    ]
    tpsl_options = [(180, 220), (200, 200), (170, 250), (190, 240)]
    best = []
    for rel in rel_options:
        for filt in filt_options:
            for sl, tp in tpsl_options:
                strat = EOMDriftLong(rel=rel, hours=hours, sl_pip=sl, tp_pip=tp,
                                     max_hold=mh, **filt)
                r, tr = run(tfn, asset, strat)
                m = r['metrics']
                if m['n_trades'] < 30:
                    continue
                best.append((r['rqs_score'], r['passed'], m, rel, filt, (sl, tp),
                             r['gates']))
    best.sort(key=lambda x: (x[1], x[0]), reverse=True)
    for score, passed, m, rel, filt, tpsl, gates in best[:15]:
        tag = 'ACCEPT' if passed else 'reject'
        gl = ''.join('1' if v else '0' for v in gates.values())
        print(f"  RQS={score:5.1f} {tag} [{gl}] | n={m['n_trades']:3d} WR={m['win_rate']:.1f}% "
              f"PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f}% MCL={m['max_consec_losses']} | "
              f"rel={rel} amin={filt.get('atr_min_mult')} cpos={filt.get('min_close_pos')} "
              f"SL{tpsl[0]}/TP{tpsl[1]} wf={m['wf_nets']}")
    return best


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what == 'base':
        phase_baseline()
    elif what == 'autopsy':
        phase_autopsy('M15'); phase_autopsy('M5')
    elif what.startswith('search:'):
        # search:M15  یا  search:M5
        phase_search(what.split(':', 1)[1])
    elif what.startswith('rel:'):
        # rel:M15  — همان فیلترِ برنده اما جاروبِ ترکیب‌های rel برای پایداریِ G4
        phase_rel_stability(what.split(':', 1)[1])
    else:
        phase_baseline()
        phase_autopsy('M15'); phase_autopsy('M5')
        phase_search('M15'); phase_search('M5')
