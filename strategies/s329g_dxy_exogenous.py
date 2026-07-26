# -*- coding: utf-8 -*-
"""
S329g — فیلترِ اگزوژنِ DXY روی EURUSD M15 — آخرین مسیرِ علمیِ احیای G4
================================================================================
چرا DXY؟ همهٔ فیلترهای قبلی (session/day=S329c, macro-M15=S329d, HTF-M30=S329f)
  از **خودِ قیمتِ یورو** مشتق شده‌اند؛ لذا در پنجرهٔ سومِ صعودی (۲۰۲۲–۲۰۲۴) همگی
  «گول می‌خورند» و W3 منفی می‌ماند. DXY یک متغیرِ **کاملاً برون‌زا (exogenous)** است:
  شاخصِ دلار، که با EURUSD همبستگیِ معکوسِ ~-0.95 دارد. فرضیه:
    «SHORTِ یورو فقط وقتی معتبر است که DXY هم‌زمان در روندِ صعودی باشد (فشارِ دلار).»
  این یک تأییدِ بنیادی/بین‌بازاری است، نه مشتقِ خودِ سری ⇒ ممکن است W3 را نجات دهد.

بدونِ look-ahead: روندِ DXY با EMA-slope روی DXY_M15 ساخته و یک قدم shift می‌شود؛
  با merge_asof(backward) روی زمانِ EURUSD می‌نشیند (هر دو M15، هم‌تراز).

اگر ANY_PASS=False بماند ⇒ همهٔ مسیرهای منطقیِ بهبود (زمان، رژیمِ درون‌زا، رژیمِ
  برون‌زا) آزموده شده‌اند و طبقِ «قانونِ مرگِ ابدی» EURUSD M15 برای این لایه DEAD؛
  XAUUSD M15 (S303) تنها زیستگاهِ زندهٔ لایه باقی می‌ماند.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from engine import indicators as ind
from strategies.s329f_htf_fast import PrebuiltSignalShort


def build_dxy_up(df_eur, dxy_ema, dxy_lb):
    """آرایهٔ بولیِ هم‌طولِ EURUSD-M15: آیا DXY در روندِ صعودی است؟ (بدون look-ahead)."""
    dxy = TS.load_data('DXY_M15')
    ema = ind.ema(dxy['close'], dxy_ema).to_numpy()
    ema_prev = pd.Series(ema).shift(dxy_lb).to_numpy()
    up = ema > ema_prev                      # DXY صعودی ⇒ فشارِ نزولی روی یورو
    d = pd.DataFrame({'dt': pd.to_datetime(dxy['dt'].values), 'up': up})
    d['up'] = d['up'].shift(1).fillna(False)  # فقط کندلِ قطعاً‌بستهٔ DXY
    d = d.sort_values('dt')
    m = pd.DataFrame({'dt': pd.to_datetime(df_eur['dt'].values)}).sort_values('dt')
    merged = pd.merge_asof(m, d, on='dt', direction='backward')
    merged['up'] = merged['up'].fillna(False)
    return merged.set_index(m.index).sort_index()['up'].to_numpy().astype(bool)


def main():
    asset = 'EURUSD'; tf = 'M15'
    df = TS.load_data(f'{asset}_{tf}')
    c = df['close']; h = df['high'].to_numpy(); cl = c.to_numpy()
    dt = pd.to_datetime(df['dt'].values)
    hour = pd.DatetimeIndex(dt).hour.to_numpy()
    dow = pd.DatetimeIndex(dt).dayofweek.to_numpy()

    ef, es, lb, adx_hi = 13, 34, 40, 22
    emaF = ind.ema(c, ef).to_numpy(); emaS = ind.ema(c, es).to_numpy()
    adx = ind.adx(df, 14); adx = adx[0] if isinstance(adx, tuple) else adx
    adx = pd.Series(np.asarray(adx)).fillna(0).to_numpy()
    prev_hh = pd.Series(h).rolling(lb).max().shift(1).to_numpy()
    rev_attempt = cl > prev_hh
    ema_stack = emaF < emaS
    trend = adx > adx_hi

    bad_hours = {8, 9, 12, 17}; bad_dow = {0, 1}
    nb_hour = np.roll(hour, -1); nb_dow = np.roll(dow, -1)
    time_ok = ~(np.isin(nb_hour, list(bad_hours)) | np.isin(nb_dow, list(bad_dow)))
    base_raw = trend & ema_stack & rev_attempt & time_ok

    print('===== S329g — EURUSD M15 + فیلترِ اگزوژنِ DXY =====', flush=True)
    best = None; best_kw = None; any_pass = False
    for dxy_ema in (20, 50, 100):
        for dxy_lb in (12, 24, 48):
            dxy_up = build_dxy_up(df, dxy_ema, dxy_lb)
            raw = base_raw & dxy_up
            sig = pd.Series(raw).shift(1).fillna(False).to_numpy()
            for rr in (1.1, 1.2):
                sl = 56.9; tp = round(sl * rr, 1)
                strat = PrebuiltSignalShort(sig, sl, tp, max_hold=48)
                tr, _ = TS.simulate(df, strat, asset, warmup=2000)
                r = RQS.compute_rqs(tr, asset); m = r['metrics']
                if m.get('n_trades', 0) < 30:
                    continue
                g = ''.join('✓' if v else '✗' for v in r['gates'].values())
                passed = all(r['gates'].values()); any_pass = any_pass or passed
                mark = '  <== ALL PASS' if passed else ''
                tag = f"de{dxy_ema} dlb{dxy_lb} rr={rr}"
                print(f"  {tag:22s} | {r['verdict']:6s} RQS={r['rqs_score']:5.1f} "
                      f"n={m.get('n_trades',0):3d} WR={m.get('win_rate',0):4.1f}% "
                      f"PF={m.get('profit_factor',0):.2f} DD={m.get('max_dd_pct',0):.1f}% "
                      f"MCL={m.get('max_consec_losses',0)} p={m.get('p_value',1):.3f} "
                      f"WF={m.get('wf_nets')} {g}{mark}", flush=True)
                if best is None or r['rqs_score'] > best['rqs_score']:
                    best = r; best_kw = (dxy_ema, dxy_lb, rr)

    print('\n' + '=' * 70, flush=True)
    print('ANY_PASS =', any_pass, flush=True)
    if best is not None:
        print('BEST:', RQS.format_report(f'dxy{best_kw}', best), flush=True)
        print('WF   :', best['metrics'].get('wf_nets'), flush=True)


if __name__ == '__main__':
    main()
