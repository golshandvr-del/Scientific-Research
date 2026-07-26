# -*- coding: utf-8 -*-
"""S327 — تأیید و ذخیرهٔ یک config برندهٔ مشخص روی یک TF (JSON خروجی)."""
import sys, json, argparse
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


def run(asset, tf, cfg):
    df = S.load(asset, tf)
    feat = S.build_features(df, asset)
    atr = feat['atr']; c = feat['c']; pip = se.ASSETS[asset]['pip']
    atr_pip = np.where(atr > 0, atr / pip, np.nan)
    sig = S.make_signals(feat, cfg['k_body'], cfg['br_min'], cfg['streak_n'],
                         cfg['rsi_lo'], cfg['regime'], atr, c)
    valid = sig & np.isfinite(atr_pip) & (atr_pip > 0)
    sl = np.where(np.isfinite(atr_pip), cfg['sl_m'] * atr_pip, 1.0)
    tp = np.where(np.isfinite(atr_pip), cfg['tp_m'] * atr_pip, 1.0)
    short = np.zeros(feat['n'], dtype=bool)
    tr = se.simulate_trades(df, valid, short, sl, tp, asset,
                            max_hold=cfg['hold'], allow_overlap=False)
    r = rqs.compute_rqs(tr, asset)
    print(rqs.format_report(f'S327 {asset} {tf}', r))
    out = _clean({'key': f'{asset}_{tf}', 'cfg': cfg, 'rqs': r['rqs_score'],
                  'passed': r['passed'], 'gates': r['gates'], 'metrics': r['metrics']})
    path = f'results/_s327_sell_climax_{asset}_{tf}.json'
    json.dump(out, open(path, 'w'), ensure_ascii=False, indent=2)
    print('saved', path)
    return r


# configهای برندهٔ هر TF (پر می‌شود همان‌طور که اسکن پیش می‌رود)
CONFIGS = {
    'XAUUSD_M5':  dict(k_body=1.6, br_min=0.6,  streak_n=2, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3, hold=24),
    'XAUUSD_M15': dict(k_body=2.5, br_min=0.45, streak_n=3, rsi_lo=35, regime='trend', sl_m=2.8, tp_m=1.0, hold=16),
}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', required=True)
    args = ap.parse_args()
    asset, tf = args.key.rsplit('_', 1)
    run(asset, tf, CONFIGS[args.key])
