# -*- coding: utf-8 -*-
"""
S327b — تلاشِ بهبودِ XAUUSD M30 (که در S327 پایه G2/PF را رد کرد: PF=1.17)
================================================================================
تشخیص: روی M30 لایهٔ climax-reversal WR بالا دارد (81٪) ولی PF زیرِ ۱.۳ است ⇒
  بازنده‌ها (که به SL بزرگ می‌خورند) سنگین‌ترند. راهِ ریاضیِ درست برای بالا بردنِ PF
  بدونِ خراب‌کردنِ WR = **breakeven-stop**: وقتی سود به be_trig×ATR رسید، SL را به
  نقطهٔ ورود ببر ⇒ دُمِ باختِ بزرگ کوتاه می‌شود ⇒ میانگینِ باخت ↓ ⇒ PF ↑.
  (قانونِ بهبود: افزودنِ مکانیزمِ خروجِ شناور؛ قانونِ «همه چیز شناور».)

⚠️ breakeven forward-safe است: در simulate_trades وقتی high/low به تریگر رسید،
   SL به entry منتقل می‌شود؛ هیچ look-ahead جدید.
"""
import sys, time, itertools, json
sys.path.insert(0, '.')
import numpy as np
from engine import scalp_engine as se
from engine import rqs
import strategies.s327_sell_climax_reversal_rqs as S
import warnings; warnings.filterwarnings('ignore')


def _clean(x):
    if isinstance(x, dict):  return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [_clean(v) for v in x]
    if isinstance(x, (np.bool_,)):   return bool(x)
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, (np.floating,)):return float(x)
    return x


def scan_m30(asset='XAUUSD', tf='M30', budget=400):
    df = S.load(asset, tf)
    feat = S.build_features(df, asset)
    atr = feat['atr']; c = feat['c']; pip = se.ASSETS[asset]['pip']
    n = feat['n']
    atr_pip = np.where(atr > 0, atr / pip, np.nan)
    short = np.zeros(n, dtype=bool)

    # فیلترهای کیفیت — با تمرکز روی نسخه‌های قوی‌تر (چون PF مشکل است)
    grid_kbody  = [2.0, 2.5]
    grid_brmin  = [0.45, 0.6]
    grid_streak = [0, 2, 3]
    grid_rsi    = [None, 35, 30]
    grid_regime = ['trend', 'below']
    # SL/TP: TP<SL همچنان، اما دامنه‌ای گسترده‌تر برای یافتنِ نسبتِ بهینه
    grid_sltp   = [(2.0, 0.9), (2.4, 1.0), (2.8, 1.2), (3.1, 1.4)]
    grid_hold   = [16, 24]
    # ⭐ breakeven trigger (× ATR) — قلبِ بهبود
    grid_be     = [None, 0.5, 0.8, 1.1]

    best = None
    t0 = time.time(); evals = 0; rqs_calls = 0
    for k_body, br_min, streak_n, rsi_lo, regime in itertools.product(
            grid_kbody, grid_brmin, grid_streak, grid_rsi, grid_regime):
        sig = S.make_signals(feat, k_body, br_min, streak_n, rsi_lo, regime, atr, c)
        valid = sig & np.isfinite(atr_pip) & (atr_pip > 0)
        if valid.sum() < 30:
            continue
        for (sl_m, tp_m), hold, be in itertools.product(grid_sltp, grid_hold, grid_be):
            if time.time() - t0 > budget:
                print(f"BUDGET HIT after {evals} evals")
                return best, evals
            sl_pip = np.where(np.isfinite(atr_pip), sl_m * atr_pip, 1.0)
            tp_pip = np.where(np.isfinite(atr_pip), tp_m * atr_pip, 1.0)
            be_pip = None
            if be is not None:
                be_pip = float(np.nanmedian(be * atr_pip))
            tr = se.simulate_trades(df, valid, short, sl_pip, tp_pip, asset,
                                    max_hold=hold, allow_overlap=False,
                                    be_trigger_pip=be_pip)
            evals += 1
            pre = S._cheap_prefilter(tr, asset, wr_min=58.0, pf_min=1.28)
            if pre is None:
                continue
            r = rqs.compute_rqs(tr, asset)
            rqs_calls += 1
            cfg = dict(k_body=k_body, br_min=br_min, streak_n=streak_n, rsi_lo=rsi_lo,
                       regime=regime, sl_m=sl_m, tp_m=tp_m, hold=hold, be=be)
            if best is None or r['rqs_score'] > best[0]:
                best = (r['rqs_score'], r, cfg)
                if r['passed']:
                    print(f"  {rqs.format_report('S327b', r)}  cfg={cfg}")
    print(f"evals={evals} rqs_calls={rqs_calls} ({time.time()-t0:.1f}s)")
    return best, evals


if __name__ == '__main__':
    best, evals = scan_m30()
    if best is None:
        print("NO CANDIDATE")
    else:
        score, r, cfg = best
        print("BEST:", rqs.format_report('S327b M30', r), "cfg=", cfg)
        if r['passed'] and score >= 80:
            out = _clean({'key': 'XAUUSD_M30', 'cfg': cfg, 'rqs': score,
                          'passed': r['passed'], 'gates': r['gates'], 'metrics': r['metrics']})
            json.dump(out, open('results/_s327_sell_climax_XAUUSD_M30.json', 'w'),
                      ensure_ascii=False, indent=2)
            print("saved M30 JSON")
