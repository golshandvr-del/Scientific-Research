# -*- coding: utf-8 -*-
"""
s435_adjudicate.py — داوریِ کاملِ RQS2 v2.6 برای «SoS-H1 + فیلترِ ATR»

چرا سه بازو، نه یکی
--------------------
قانونِ همپوشانیِ پروژه می‌گوید وقتی لایه‌ای بخشاً همپوشان است، باید **هر دو
بخش** بررسی شوند: بخشِ نو (لبهٔ افزوده) و بخشِ همپوشان (امکانِ استفاده به
عنوانِ **فیلتر**). پس:

  A) `full`     — کلِ لایه (۳۳۳ معامله). مبنای مقایسه.
  B) `novel`    — فقط معاملاتی که روزشان در اجتماعِ زندهٔ فعلی **نیست**.
                  این همان چیزی است که `S205` سنجید و ۵ معامله یافت؛
                  حالا ۲۷۵ روز است.
  C) `overlap`  — فقط معاملاتی که روزشان **هست**. اگر این بازو WR یا PF
                  به‌مراتب بالاتری بدهد، یعنی SoS به‌عنوانِ **فیلترِ تأیید**
                  روی لایه‌های زنده ارزش دارد — که طبقِ قانونِ سومِ
                  همپوشانی باید **همین‌جا** بررسی شود، نه در مرحلهٔ بعد.

⚠️ محافظ‌های ضدِ خطاهای شناخته‌شدهٔ این مأموریت
-------------------------------------------------
* `BUG-NULLUNCOND` (گامِ ۳۷): خطِ مبنای بی‌قید باید با **همان** هندسه و
  همان مدیریتِ معامله اجرا شود. اینجا لایه تریلینگ ندارد، پس هر دو سمت
  بدونِ تریلینگ — ولی صریحاً و با ذکرِ دلیل، نه به‌طورِ ضمنی.
* تلهٔ ۱ (گامِ ۳۳): `perm_k` برای **هر بازو** برابرِ تعدادِ سیگنالِ
  **همان بازو** است، نه بازوی کامل. مدلِ صفرِ قرضی یعنی z بی‌معنا.
* `n_trials` صادقانه: ۲۶۷ (بَتریِ S202) + ~۲۰ (جاروبِ ATR در S204) + ۳
  بازوی من = **۲۹۰**. کم‌گزارش‌کردنش اشتباهِ رایجِ ۸ است.
* تخمینِ `1/√n` **ممنوع** — گامِ ۶۶ نشان داد ۲۶٪ خطا می‌دهد. جای‌گشتِ
  واقعی برای هر بازو.

اجرا:
    cd /home/user/webapp && PYTHONPATH=. python3 tools/s435_adjudicate.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'strategies'))

from engine import scalp_engine as se            # noqa: E402
from engine.rqs2 import compute_rqs2             # noqa: E402
import tools.s435_coverage_union as cov          # noqa: E402

OUT = 'results/_s435_verdicts'

# 🔒 حسابِ صادقانهٔ آزمون‌ها — پیش‌ثبتِ گامِ ۷۶
N_TRIALS = 290
# 🔴 گامِ ۸۶: موتور خودش اعتراض کرد — با ۴۰ جای‌گشت `H3` را **نامعلوم**
#    برمی‌گرداند: «perm_sd همگرا نشده، z هنوز به seed وابسته است؛ حداقل
#    ۵۰۰ جای‌گشت لازم است». قانونِ پروژه «صفر دروازهٔ نامعلوم» می‌خواهد و
#    قانونِ مرگِ ابدی حکم‌دادن با دروازهٔ نامعلوم را ممنوع می‌کند.
#    ⚠️ نکتهٔ مهم: این ایراد **علیهِ** نتیجهٔ فعلیِ من نیست — نتیجه منفی
#    است و همگراییِ بیشتر آن را منفی‌تر یا خنثی می‌کند، نه مثبت. ولی
#    «نتیجه‌ام منفی است پس دقت لازم ندارم» همان تنبلیِ روش‌شناختی است که
#    در گامِ ۶۸ به آن اعتراف کردم (ابزارِ خودممیزی را ساختم و اجرا نکردم).
N_PERM = 500
SEED = 7


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def build_arms():
    """سه بازو را می‌سازد و ماسکِ سیگنالِ هرکدام را برمی‌گرداند."""
    df = cov.load_h1()
    sig = cov.sos_edge(df) & cov.atr_filter(df)

    # اجتماعِ زنده از خروجیِ ذخیره‌شدهٔ گامِ ۸۱ خوانده می‌شود، نه بازسازی.
    # دلیل: باید **همان** اجتماعی باشد که در مخزن قابلِ بازرسی است.
    cp = os.path.join(ROOT, OUT.replace('_verdicts', '_coverage'),
                      'coverage_H1.json')
    if not os.path.exists(cp):
        cp = os.path.join(ROOT, 'results/_s435_coverage/coverage_H1.json')
    with open(cp, encoding='utf-8') as f:
        cd = json.load(f)
    union_days = set(pd.to_datetime(pd.Series(cd['union_days'])).dt.floor('D')) \
        if 'union_days' in cd else None

    # اگر فایل روزهای اجتماع را ذخیره نکرده، بازسازی می‌کنیم (با اعلام).
    if union_days is None:
        print('  [i] union_days در JSON نبود ⇒ بازسازیِ اجتماع')
        union_days = cov.rebuild_union(df) if hasattr(cov, 'rebuild_union') else set()

    t_full = cov.trades_of(df, sig, cov.CAND['sl'], cov.CAND['tp'],
                           cov.CAND['max_hold'])
    if t_full is None or len(t_full) == 0:
        raise SystemExit('no trades')

    eb = t_full['entry_bar'].values
    edays = pd.to_datetime(df['dt'].iloc[eb]).dt.floor('D').to_numpy()
    in_union = np.array([d in union_days for d in pd.to_datetime(edays)])

    # ماسکِ سیگنال برای هر بازو (بر حسبِ کندلِ ورود)
    m_novel = np.zeros(len(df), bool)
    m_novel[eb[~in_union]] = True
    m_over = np.zeros(len(df), bool)
    m_over[eb[in_union]] = True

    return df, {
        'full': sig,
        'novel': m_novel,
        'overlap': m_over,
    }, {'n_full': len(t_full), 'n_novel': int((~in_union).sum()),
        'n_overlap': int(in_union.sum()),
        'union_days': len(union_days)}


def null_for(df, mask, sl, tp, mh, asset='XAUUSD', n_perm=N_PERM, seed=SEED):
    """مدلِ صفرِ **اختصاصیِ همین بازو** — تلهٔ ۱ گامِ ۳۳."""
    n = len(df)
    z = np.zeros(n, bool)
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True

    # خطِ مبنای بی‌قید. allow_overlap=True اجباری است (تعریفِ «بی‌قید»
    # بدونِ آن قابلِ بیان نیست). هندسه و مدیریت عیناً همان سیگنال:
    # لایه تریلینگ/سربه‌سر ندارد ⇒ کنترل هم ندارد. BUG-NULLUNCOND بسته.
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)
    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    um = np.zeros(n, bool)
    um[pick] = True
    tu = se.simulate_trades(df, um, z, sl, tp, asset, max_hold=mh,
                            allow_overlap=True)
    wr_unc = _wr(tu)

    k = int(mask.sum())
    perm = []
    for i in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        tp_ = se.simulate_trades(df, pm, z, sl, tp, asset, max_hold=mh,
                                 allow_overlap=False)
        w = _wr(tp_)
        if w is not None:
            perm.append(w)
    pa = np.array(perm, float) if perm else np.array([])
    return {'long': dict(uncond_wr=wr_unc,
                         perm_mean=float(pa.mean()) if pa.size else None,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else None,
                         perm_k=k),
            'short': {}}


def adjudicate_arm(df, mask, label, oos_frac=0.30):
    sl, tp, mh = cov.CAND['sl'], cov.CAND['tp'], cov.CAND['max_hold']
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return {'arm': label, 'error': 'no trades'}

    null = null_for(df, mask, sl, tp, mh)
    split_bar = int(len(df) * (1.0 - oos_frac))

    d_time = pd.to_numeric(df['time']).to_numpy()
    res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                       bar_time=d_time, close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)

    g = res.get('gates') or {}
    m = res.get('metrics') or {}
    return {
        'arm': label,
        'n_signals': int(mask.sum()),
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: g.get(k) for k in sorted(g)},
        'failed_gates': sorted(k for k, v in g.items() if v is False),
        'unknown_gates': sorted(k for k, v in g.items() if v is None),
        'null': null['long'],
        'n_trials': N_TRIALS,
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'rr', 'top_win_share')},
        'notes': [str(x) for x in (res.get('notes') or [])],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='full,novel,overlap')
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    df, masks, info = build_arms()
    print(f"[S435 داوری] XAUUSD-H1 · n_trials={N_TRIALS} · {N_PERM} جای‌گشت/بازو")
    print(f"  کامل={info['n_full']}  نو={info['n_novel']}  "
          f"همپوشان={info['n_overlap']}  اجتماع={info['union_days']} روز\n")

    for lbl in a.arms.split(','):
        lbl = lbl.strip()
        if lbl not in masks:
            continue
        out = adjudicate_arm(df, masks[lbl], lbl)
        p = os.path.join(OUT, f'arm_{lbl}.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        if 'error' in out:
            print(f"  [{lbl}] {out['error']}")
            continue
        m = out['metrics']
        print(f"  ═══ [{lbl}] {out['verdict']} · RQS2={out['rqs2_score']}")
        print(f"      n={m['n_trades']} WR={m['win_rate']} "
              f"lift={m['skill_lift_pp']} z={m['skill_z']}")
        print(f"      PF={m['profit_factor']} net={m['net_profit']} "
              f"maxDD={m['max_dd_pct']}% rec={m['recovery_factor']}")
        print(f"      افتاده: {out['failed_gates']}  نامعلوم: "
              f"{out['unknown_gates'] or 'هیچ'}")
        sys.stdout.flush()

    print('\n[done]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
