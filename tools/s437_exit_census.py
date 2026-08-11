# -*- coding: utf-8 -*-
"""
s437_exit_census.py — سرشماریِ **نوعِ خروج** و استخراجِ هندسهٔ در-دسترس

چرا این ابزار وجود دارد (گام ۱۳۶):
    در گام ۱۳۵ شمردم چند معامله به `TP` رسید و «صفر» گرفتم، و بر آن مبنا
    `BUG-GEOMSCALE` را نوشتم. آن شمارش با آستانهٔ `pnl >= +99` انجام شد.
    ولی موتور هزینه را از سود کسر می‌کند: `TP=100` ⇒ `pnl = 98.70`.
    ⇒ آستانهٔ من **یک واحد بالاتر از مقدارِ ممکن** بود و «۰٪» ساخت.
    🔴 `BUG-EXITTHRESH` — تشخیصِ گام ۱۳۵ باید **تصحیح** شود.

    درسِ عمیق‌ترش: من یک آستانه را از **مقدارِ اسمی** ساختم در حالی که داده
    مقدارِ **پس از هزینه** را نگه می‌دارد. همان خانوادهٔ خطای `BUG-GEOMSCALE`:
    یک کمیت را در واحدِ غلط سنجیدن. اینجا واحد، «pip پیش از هزینه» بود.

این ابزار:
    ۱) نوعِ خروج را با آستانه‌های **مشتق‌شده از خودِ داده** می‌شمارد،
       نه با اعدادی که من حدس می‌زنم.
    ۲) توزیعِ `MFE`/`MAE` را در افقِ واقعی اندازه می‌گیرد.
    ۳) هندسهٔ **در-دسترس** را از چندکِ `MFE` استخراج می‌کند — یک عدد،
       نه جاروب (وگرنه `n_trials` متورم می‌شود و عدد «به‌خاطرِ نتیجه‌اش»
       انتخاب می‌شود).

هیچ `compute_rqs2` صدا زده نمی‌شود ⇒ **بودجهٔ چندگانگی مصرف نمی‌شود**.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'strategies'), os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import scalp_engine as se                       # noqa: E402
import tools.s435_coverage_union as cov                     # noqa: E402
import tools.s437_adjudicate as adj                         # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s437_geom')
CARD = 'EURUSD-M30'
MH = 96


def exit_census(t, sl_pip, tp_pip, cost):
    """نوعِ خروج با آستانه‌های **پس از هزینه** — نه اسمی."""
    p = t['pnl_pip'].to_numpy()
    # موتور هزینه را کسر می‌کند ⇒ سقفِ ممکن = tp - cost، کفِ ممکن = -(sl + cost)
    tp_real = tp_pip - cost
    sl_real = -(sl_pip + cost)
    eps = 0.5
    tp_hit = int((p >= tp_real - eps).sum())
    sl_hit = int((p <= sl_real + eps).sum())
    mid = int(len(p) - tp_hit - sl_hit)
    m = (p > sl_real + eps) & (p < tp_real - eps)
    return {
        'n': int(len(p)),
        'tp_real': round(float(tp_real), 2),
        'sl_real': round(float(sl_real), 2),
        'tp_hit': tp_hit, 'tp_pct': round(100.0 * tp_hit / len(p), 2),
        'sl_hit': sl_hit, 'sl_pct': round(100.0 * sl_hit / len(p), 2),
        'timeout': mid, 'timeout_pct': round(100.0 * mid / len(p), 2),
        'timeout_mean': (round(float(p[m].mean()), 2) if m.any() else None),
        'timeout_wins': int(((p > 0) & m).sum()),
        'timeout_losses': int(((p <= 0) & m).sum()),
        'realized_win_mean': round(float(p[p > 0].mean()), 3),
        'realized_loss_mean': round(float(p[p <= 0].mean()), 3),
        'realized_rr': round(float(abs(p[p > 0].mean() / p[p <= 0].mean())), 4),
        'realized_breakeven_pct': round(
            100.0 * abs(p[p <= 0].mean())
            / (p[p > 0].mean() + abs(p[p <= 0].mean())), 2),
        'win_rate': round(100.0 * float((p > 0).mean()), 2),
        'max_bars_held': int(t['bars_held'].max()),
        'pct_at_horizon': round(100.0 * float(
            (t['bars_held'].to_numpy() >= MH - 1).mean()), 2),
    }


def mfe_mae(df, sig, pip):
    idx = np.flatnonzero(sig)
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy()
    mfe = []; mae = []
    for i in idx:
        j = min(i + 1 + MH, len(df))
        if i + 1 >= j:
            continue
        e = c[i]
        mfe.append((h[i + 1:j].max() - e) / pip)
        mae.append((e - l[i + 1:j].min()) / pip)
    return np.asarray(mfe), np.asarray(mae)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    df, asset = adj.load_card(CARD)
    pip = se.ASSETS[asset]['pip']
    cost = se.ASSETS[asset]['spread_pip'] + 2.0 * se.ASSETS[asset]['slip_pip']
    sig = cov.sos_edge(df)
    z = np.zeros(len(df), bool)

    g = adj.GEOM[asset]
    t = se.simulate_trades(df, sig, z, g['sl'], g['tp'], asset,
                           max_hold=MH, allow_overlap=False)
    cen = exit_census(t, g['sl'], g['tp'], cost)

    mfe, mae = mfe_mae(df, sig, pip)
    qs = {f'q{int(q*100):02d}': round(float(np.quantile(mfe, q)), 2)
          for q in (0.25, 0.50, 0.60, 0.70, 0.75, 0.80, 0.90)}
    qa = {f'q{int(q*100):02d}': round(float(np.quantile(mae, q)), 2)
          for q in (0.25, 0.50, 0.75, 0.90)}

    # هندسهٔ در-دسترس: `TP` = چندکِ ۶۰٪ِ `MFE`، `SL` = چندکِ ۳۰٪ِ `MAE`.
    # چرا این دو چندک و نه جاروب: یک عدد که **داده** تعیین می‌کند، تا
    # `n_trials` متورم نشود. q60 برای `TP` یعنی «۶۰٪ سیگنال‌ها امکانِ
    # لمسش را دارند» و q30 برای `SL` یعنی «۷۰٪ سیگنال‌ها آن را لمس نمی‌کنند».
    tp_new = float(np.quantile(mfe, 0.60))
    sl_new = float(np.quantile(mae, 0.30))
    rec = {
        'step': 136, 'card': CARD, 'asset': asset,
        'cost_pip': cost, 'max_hold': MH,
        'current_geometry': dict(sl=g['sl'], tp=g['tp']),
        'exit_census_current': cen,
        'mfe_quantiles_pip': qs, 'mae_quantiles_pip': qa,
        'mfe_n': int(len(mfe)),
        'pct_mfe_reaching_current_tp': round(
            100.0 * float((mfe >= g['tp']).mean()), 2),
        'reachable_geometry': {
            'sl': round(sl_new, 1), 'tp': round(tp_new, 1),
            'rr': round(tp_new / sl_new, 3),
            'rule': 'TP=q60(MFE) · SL=q30(MAE) — یک عدد، بدونِ جاروب',
        },
    }
    with open(os.path.join(OUT, 'exit_census.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)

    print(f'[S437 سرشماریِ خروج] {CARD} · هزینه={cost}pip · افق={MH}')
    print(f"  هندسهٔ فعلی SL={g['sl']} TP={g['tp']}  ⇒ "
          f"سقفِ ممکنِ pnl={cen['tp_real']} کفِ ممکن={cen['sl_real']}")
    print(f"  TP کامل: {cen['tp_hit']} ({cen['tp_pct']}%) · "
          f"SL کامل: {cen['sl_hit']} ({cen['sl_pct']}%) · "
          f"تایم‌اوت: {cen['timeout']} ({cen['timeout_pct']}%)")
    print(f"  RR اسمی={g['tp']/g['sl']:.2f} ⇒ RR محقق‌شده={cen['realized_rr']}")
    print(f"  سربه‌سرِ محقق‌شده={cen['realized_breakeven_pct']}% در برابر "
          f"WR={cen['win_rate']}%")
    print(f"  MFE: {qs}")
    print(f"  ⇒ هندسهٔ در-دسترس: SL={rec['reachable_geometry']['sl']} "
          f"TP={rec['reachable_geometry']['tp']} "
          f"RR={rec['reachable_geometry']['rr']}")
    print(f'  ✅ ذخیره شد ⇒ {OUT}/exit_census.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
