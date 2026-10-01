# -*- coding: utf-8 -*-
"""S759 — ممیزیِ «شاهدِ کاذب» پیش از سیم‌کشی · XAUUSD-H4 (تنها کارتِ ACCEPT)

چرا
===
مکانیزمِ نمایشِ سایت همپوشانیِ معمولی را حل می‌کند، ولی نه وقتی دو لایه در
واقع **یک رویداد با دو اسم** باشند (سابقه: strategy_registry.ts — S404/S408،
jaccard ۶۹.۳٪ ⇒ «یکی، نه هر دو»). S759 روی H4 به کارتی می‌رود که چهار ساکنِ
زنده دارد: S382 · S589 · S547 · S1516. دو مورد حساس‌اند:
  · S382 (مومنتومِ %R) — سندِ S759 §۶ همپوشانیِ **پنجرهٔ** ۶۰٪ گزارش کرد
    (ولی هم‌کندلیِ ورود فقط ۵.۷٪). باید در سطحِ **رویداد** اندازه گرفته شود.
  · S589 (سقفِ تازه) — S759 هم یک «شکستِ رو به بالا» است؛ هم‌خانوادهٔ مفهومی.

معیار (ارثی، بدونِ تغییر — همان آستانه‌های tools/s1516_false_witness_audit.py):
  jaccard ≥ 0.60 و size_ratio ≥ 0.75 ⇒ FALSE-WITNESS.
  برای تحملِ ناهم‌ترازیِ یک‌کندلی، علاوه بر هم‌کندلی، اشتراکِ همسایگیِ ±۲ کندل
  و همپوشانیِ روزانه هم گزارش می‌شود (S547 رویدادِ روزانه است).

داده: همان سری‌ای که حکمِ S759 روی آن صادر شد (H1 رسمیِ mt5_full → H4) —
سایت هم کارتِ H4 را از تجمیعِ H1×4 می‌سازد.

کنترل‌های اعتبارِ ابزار (هر دو باید بازتولید شوند، وگرنه ممیزی باطل است):
  ① S759: ۱۷۵ معامله با WR=52.00٪ (سند §۳).
  ② S1516-H4 (L=180) روی همین سری: ۵۰۸ رویداد — عددِ منتشرشدهٔ اسکنِ S1516
     روی snapshotِ زمانِ حکم (همان H4ِ مشتق‌از-H1).

اجرا:  python3 tools/s759_false_witness_audit.py
خروجی: results/_s759/false_witness_h4.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from engine import scalp_engine as se                       # noqa: E402
from strategies import s759_informed_structure as S9         # noqa: E402
import s1516_false_witness_audit as FW                       # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s759', 'false_witness_h4.json')
NEIGH = 2


def neigh_share(a: np.ndarray, b: np.ndarray, k: int) -> float:
    ia = np.where(a)[0]
    if not len(ia):
        return 0.0
    ib = np.where(b)[0]
    if not len(ib):
        return 0.0
    pos = np.searchsorted(ib, ia)
    hit = 0
    for i, p in zip(ia, pos):
        for q in (p - 1, p):
            if 0 <= q < len(ib) and abs(ib[q] - i) <= k:
                hit += 1
                break
    return round(100.0 * hit / len(ia), 1)


def day_cmp(a: np.ndarray, b: np.ndarray, days: pd.Series) -> dict:
    da, db = set(days[a]), set(days[b])
    u = da | db
    jac = len(da & db) / len(u) if u else 0.0
    sr = min(len(da), len(db)) / max(len(da), len(db)) if max(len(da), len(db)) else 0.0
    return dict(days_a=len(da), days_b=len(db), shared_days=len(da & db),
                jaccard_day=round(jac, 4), size_ratio_day=round(sr, 4),
                false_witness_day=bool(jac >= FW.JACCARD_FALSE_WITNESS
                                       and sr >= FW.SIZE_RATIO_COMPARABLE))


def main() -> None:
    df, src = S9.load_tf('H4')
    assert 'mt5_full' in src
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    n = len(df)
    atr = S9.atr_pips(df)
    g, _ = S9.informed_long(df, 5, atr)
    g[:max(S9.ATR_P * 4, 400)] = False
    sl = S9.SL_K * atr
    tr = se.simulate_trades(df, g, np.zeros(n, bool), sl, S9.RR * sl, 'XAUUSD',
                            max_hold=S9.MAX_HOLD, allow_overlap=False)
    wr = round(float((tr['pnl_pip'] > 0).mean() * 100), 2)

    live = {
        'S382': FW.sig_s382(df),
        'S589': FW.sig_s589(df),
        'S547': FW.sig_s547(df),
        'S1516': FW.sig_s1516(df, 180),
    }
    days = df['dt'].dt.floor('D')
    rep = dict(card='XAUUSD-H4', src=src, bars=n,
               thresholds=dict(jaccard=FW.JACCARD_FALSE_WITNESS,
                               size_ratio=FW.SIZE_RATIO_COMPARABLE,
                               precedent='S404/S408 jaccard 69.3% => one, not both'),
               n_events={'S759': int(g.sum()), **{k: int(v.sum()) for k, v in live.items()}},
               vs_live={})
    print(f'{src} bars={n} S759 signals={int(g.sum())} trades={len(tr)} WR={wr}')
    for k, v in live.items():
        rec = FW.compare(g, v, 'S759', k)
        rec[f'share_of_S759_within_{NEIGH}bars'] = neigh_share(g, v, NEIGH)
        rec.update(day_cmp(g, v, days))
        rep['vs_live'][k] = rec
        print(k, json.dumps(rec, ensure_ascii=False))

    ctrl = dict(s759_trades=len(tr), s759_trades_published=175,
                s759_wr=wr, s759_wr_published=52.0,
                s1516_h4_events=int(live['S1516'].sum()), s1516_h4_published=508)
    ctrl['tool_valid'] = bool(len(tr) == 175 and wr == 52.0
                              and int(live['S1516'].sum()) == 508)
    rep['control'] = ctrl
    any_fw = any(r['false_witness'] or r['false_witness_day'] for r in rep['vs_live'].values())
    rep['verdict'] = ('FALSE-WITNESS' if any_fw else 'CLEAR') if ctrl['tool_valid'] else 'TOOL-INVALID'
    print('control', ctrl, '=>', rep['verdict'])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    if not ctrl['tool_valid']:
        raise SystemExit('TOOL-INVALID')


if __name__ == '__main__':
    main()
