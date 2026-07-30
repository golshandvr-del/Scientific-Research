# -*- coding: utf-8 -*-
"""
S346 — داوریِ نهایی با موتورِ اصلیِ پروژه + RQS+ (۶ دروازه)
================================================================================
هرچه در s346_geom/s346_stack2 دیدیم «اکتشاف» بود (موتورِ سریع، allow_overlap=True،
آمارِ pip-محور). داوریِ رسمی **فقط** اینجا انجام می‌شود:

  • `scalp_engine.simulate_trades(..., allow_overlap=False)` — صفِ واقعیِ معاملات
  • `engine.rqs.compute_rqs` — ۶ دروازه با لایهٔ سرمایه (DD٪، MCL، walk-forward)

نکتهٔ مهمِ آماری: با `allow_overlap=False` تعدادِ معاملات کمتر از تعدادِ رویدادها
می‌شود (معاملهٔ باز مانعِ ورودِ جدید است) — این همان چیزی است که کاربرِ واقعی تجربه
می‌کند و MCL/DD را هم واقع‌بینانه‌تر می‌سنجد.

خروجی: خطِ گزارشِ RQS+ + JSON برای مستندسازی.
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from engine import rqs as RQS
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_geom import CARDS, event_mask
from strategies.s346_stack import build_features

OUT = 'results/_scan_S346'


def build_gate(F, filters):
    """ماسکِ بولینِ هم‌طولِ df از فهرستِ فیلترهای آستانه‌ای."""
    g = np.ones(len(F), bool)
    for f in filters:
        v = F[f['col']].values
        m = (v >= f['thr']) if f['dir'] == 'ge' else (v <= f['thr'])
        g &= (m & np.isfinite(v))
    return g


def signals_from_cfg(df, cfg, F=None, card=None):
    """سیگنالِ نهایی (هندسه + گیتِ فیلترها) + آرایه‌های SL/TP بر حسبِ pip."""
    g = cfg['geom']
    asset = CARDS[cfg['card']][0] if 'card' in cfg else cfg['asset']
    pip = se.ASSETS[asset]['pip']
    ch = adaptive_channel(df, p=g['p'], mult=1.0)
    warmup = max(5 * g['p'], 250)
    ls, ss = event_mask(df, ch, g['mode'], g['mult'], g['er_thr'], warmup)

    if F is None:
        F = build_features(df, ch, card or cfg['card'])
    gate = build_gate(F, cfg.get('filters', []))
    ls = ls & gate
    ss = ss & gate
    if g['side'] == 'long':
        ss = np.zeros(len(df), bool)
    elif g['side'] == 'short':
        ls = np.zeros(len(df), bool)

    atr_a = ch['atr_a']
    sl_price = g['sl_k'] * atr_a
    if g.get('tp_mode', 'atr') == 'atr':
        tp_price = g['rr'] * sl_price
    else:
        tp_price = np.maximum(np.abs(ch['val'] - df['close'].values), sl_price)
    with np.errstate(invalid='ignore'):
        sl_pip = np.nan_to_num(sl_price / pip, nan=0.0)
        tp_pip = np.nan_to_num(tp_price / pip, nan=0.0)
    # ⛔ قیدِ ضدِ تقلبِ #۸ حتی در داوری: TP هرگز < SL نیست
    tp_pip = np.maximum(tp_pip, sl_pip)
    return ls, ss, sl_pip, tp_pip, ch, F


def adjudicate(cfg, name=None, verbose=True, F=None):
    card = cfg['card']
    asset, path = CARDS[card]
    df = se.load_data(path)
    ls, ss, sl_pip, tp_pip, ch, F = signals_from_cfg(df, cfg, F=F, card=card)
    g = cfg['geom']
    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset,
                            max_hold=g['hold'], allow_overlap=False)
    r = RQS.compute_rqs(tr, asset)
    nm = name or f"{card}:{g['mode']}/{g['side']}"
    if verbose:
        print("  " + RQS.format_report(nm, r), flush=True)
        m = r['metrics']
        print(f"      net=${m.get('net_profit',0):,.1f} exp={m.get('expectancy_pip',0):.2f}pip "
              f"SL={m.get('sl_pip',0):.1f} TP={m.get('tp_pip',0):.1f} "
              f"rr={m.get('tp_pip',1)/max(m.get('sl_pip',1),1e-9):.2f} "
              f"WRbe={m.get('wr_breakeven',0):.1f}% excess={m.get('wr_excess',0):+.1f}", flush=True)
        print(f"      wf_nets={m.get('wf_nets')} half={m.get('half_nets')}", flush=True)
    return r, tr, F


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-M15'
    src = f"{OUT}/{card}_fade_long_p21_v2.json"
    v2 = json.load(open(src))
    geom = v2['geom']
    print(f"=== S346 adjudication :: {card} ===", flush=True)
    F = None
    for label in ('NO-TIME', 'WITH-TIME'):
        blk = v2[label]
        cfg = dict(card=card, geom=geom, filters=blk['stack'])
        flt = ', '.join(f"{f['col']}{'>=' if f['dir']=='ge' else '<='}{f['thr']:.4g}"
                        for f in blk['stack'])
        print(f"  [{label}] filters: {flt}", flush=True)
        r, tr, F = adjudicate(cfg, name=f"{card} {label}", F=F)
        with open(f"{OUT}/{card}_{label}_rqs.json", 'w') as fh:
            json.dump(dict(cfg=cfg, rqs=r), fh, default=float)
