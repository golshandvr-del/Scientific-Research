# -*- coding: utf-8 -*-
"""
S329f — نسخهٔ بهینهٔ (vectorized/precomputed) تستِ رژیمِ H1 روی EURUSD M15
================================================================================
هدف: همان فرضیهٔ S329e (گیتِ روندِ نزولیِ H1 برای پاس‌کردنِ G4)، اما با پیش‌محاسبهٔ
  اجزای گران (ADX/EMA/prev_hh/HTF) فقط **یک‌بار** و ساختنِ سیگنالِ خام به‌صورتِ برداری؛
  سپس برای هر ترکیبِ فیلتر یک استراتژیِ سبک که آرایهٔ سیگنالِ ازپیش‌ساخته را می‌خواند.
  این ده‌ها برابر سریع‌تر از _precompute در هر ترکیب است.

اگر هیچ ترکیبی G4 را پاس نکند ⇒ EURUSD M15 طبقِ «قانونِ مرگِ ابدی» برای این لایه DEAD.
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


def build_htf_down(df_m15, htf_ema, htf_lb):
    """آرایهٔ بولیِ هم‌طولِ M15: روندِ H1 نزولی؟ (بدون look-ahead، merge_asof backward)."""
    df_h1 = TS.load_data('EURUSD_H1')
    ema_h1 = ind.ema(df_h1['close'], htf_ema).to_numpy()
    ema_prev = pd.Series(ema_h1).shift(htf_lb).to_numpy()
    down = ema_h1 < ema_prev
    h1 = pd.DataFrame({'dt': pd.to_datetime(df_h1['dt'].values), 'down': down})
    h1['down'] = h1['down'].shift(1).fillna(False)      # فقط کندلِ H1ِ قطعاً‌بسته
    h1 = h1.sort_values('dt')
    m = pd.DataFrame({'dt': pd.to_datetime(df_m15['dt'].values)}).sort_values('dt')
    merged = pd.merge_asof(m, h1, on='dt', direction='backward')
    merged['down'] = merged['down'].fillna(False)
    return merged.set_index(m.index).sort_index()['down'].to_numpy().astype(bool)


class PrebuiltSignalShort:
    """استراتژیِ سبک: سیگنالِ ورودِ ازپیش‌محاسبه (آرایهٔ بول) + SL/TP بر حسبِ پیپ."""
    def __init__(self, sig, sl_pip, tp_pip, max_hold=48):
        self._sig = sig; self.sl_pip = sl_pip; self.tp_pip = tp_pip; self.max_hold = max_hold

    def advise(self, ctx):
        i = ctx.i
        if ctx.in_position():
            if (i + 1) - ctx.position['entry_bar'] >= self.max_hold:
                return {'action': 'CLOSE'}
            return None
        if self._sig[i]:
            price = ctx.price(); pip = ctx.spec['pip']
            return {'action': 'SHORT', 'sl': price + self.sl_pip * pip,
                    'tp': price - self.tp_pip * pip}
        return None


def main():
    asset = 'EURUSD'; tf = 'M15'
    df = TS.load_data(f'{asset}_{tf}')
    c = df['close']; h = df['high'].to_numpy(); cl = c.to_numpy()
    dt = pd.to_datetime(df['dt'].values)
    hour = pd.DatetimeIndex(dt).hour.to_numpy()
    dow = pd.DatetimeIndex(dt).dayofweek.to_numpy()

    # --- اجزای پایه (یک‌بار) ---
    ef, es, lb = 13, 34, 40
    emaF = ind.ema(c, ef).to_numpy()
    emaS = ind.ema(c, es).to_numpy()
    adx = ind.adx(df, 14)
    adx = adx[0] if isinstance(adx, tuple) else adx
    adx = pd.Series(np.asarray(adx)).fillna(0).to_numpy()
    prev_hh = pd.Series(h).rolling(lb).max().shift(1).to_numpy()
    rev_attempt = cl > prev_hh
    ema_stack = emaF < emaS

    # فیلترهای session/day (بهینهٔ S329c/d): ساعتِ ورود = i+1
    bad_hours = {8, 9, 12, 17}; bad_dow = {0, 1}
    nb_hour = np.roll(hour, -1); nb_dow = np.roll(dow, -1)
    time_ok = ~(np.isin(nb_hour, list(bad_hours)) | np.isin(nb_dow, list(bad_dow)))

    print('===== S329f — EURUSD M15 + رژیمِ H1 (نسخهٔ سریع) =====', flush=True)
    adx_hi = 22
    trend = adx > adx_hi
    base_raw = trend & ema_stack & rev_attempt & time_ok

    best = None; best_kw = None; any_pass = False
    for htf_ema in (30, 50, 80):
        for htf_lb in (12, 24, 48):
            htf_down = build_htf_down(df, htf_ema, htf_lb)
            raw = base_raw & htf_down
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
                tag = f"he{htf_ema} hlb{htf_lb} rr={rr}"
                print(f"  {tag:22s} | {r['verdict']:6s} RQS={r['rqs_score']:5.1f} "
                      f"n={m.get('n_trades',0):3d} WR={m.get('win_rate',0):4.1f}% "
                      f"PF={m.get('profit_factor',0):.2f} DD={m.get('max_dd_pct',0):.1f}% "
                      f"MCL={m.get('max_consec_losses',0)} p={m.get('p_value',1):.3f} "
                      f"WF={m.get('wf_nets')} {g}{mark}", flush=True)
                if best is None or r['rqs_score'] > best['rqs_score']:
                    best = r; best_kw = (htf_ema, htf_lb, rr)

    print('\n' + '=' * 70, flush=True)
    print('ANY_PASS =', any_pass, flush=True)
    if best is not None:
        print('BEST:', RQS.format_report(f'htf{best_kw}', best), flush=True)
        print('WF   :', best['metrics'].get('wf_nets'), flush=True)


if __name__ == '__main__':
    main()
