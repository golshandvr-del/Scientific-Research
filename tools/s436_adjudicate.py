# -*- coding: utf-8 -*-
"""
s436_adjudicate.py — داوریِ **پنج بازوی پیش‌ثبتِ گامِ ۱۰۷** برای احیای `S214`
================================================================================

`S214` = Al Brooks، «Late and Missed Entries» (فصلِ ۱۱) روی `XAUUSD-M5` LONG.
نسخهٔ منتشرشده: `pre-EOM {-6,-7,-8}` ∧ `ساعاتِ روز` ∧ فیلترِ مومنتوم،
`SL150/TP300/mh96` ⇒ `REJECT` با `RQS2=14.8`، `n=275`، `lift=2.41`، `z=0.80`.

--------------------------------------------------------------------------------
چرا فایلِ **جدا** و نه ویرایشِ `tools/s435_improve.py`
--------------------------------------------------------------------------------
همان استدلالِ گامِ ۹۲: احکامِ `S435` در `results/_s435_improve/` ذخیره‌اند و
باید با **کدِ همین مخزن** بازتولیدپذیر بمانند. اگر آن ابزار را برای `S214`
دستکاری کنم، سندِ منتشرشده و ابزارِ تولیدش **بی‌صدا** از هم جدا می‌شوند و
خوانندهٔ شش‌ماه بعد نمی‌فهمد کدام درست است.

--------------------------------------------------------------------------------
پنج بازو — همه پیش‌ثبت‌شده در گامِ ۱۰۷، هیچ‌کدام پس از دیدنِ نتیجه
--------------------------------------------------------------------------------
| بازو | تعریف                                                       |
|------|-------------------------------------------------------------|
| `B0` | `pre-EOM` ∧ `ساعاتِ روز` ∧ مومنتوم  ← **لنگرِ بازتولید**       |
| `A1` | `ساعاتِ روز` ∧ مومنتوم (بدونِ تقویم) ← **فرضیهٔ مرکزی**        |
| `A2` | **فقط** مومنتوم (بدونِ تقویم و بدونِ فیلترِ ساعت) ← مرزِ فرضیه |
| `A3` | `A1` + هندسهٔ مشتق‌شده از چندکِ MFE ← تنها اهرمِ غیر-n         |
| `A4` | بهترین بازو روی `M15`/`M30`/`H1` ← قانونِ اجباریِ MTF          |

--------------------------------------------------------------------------------
پنج قیدِ سختِ قفل‌شده — هر کدام یک باگِ **نام‌بُرده** را می‌بندد
--------------------------------------------------------------------------------
۱. `A3`: اگر `TP` مشتق‌شده `< SL` ⇒ **بازو لغو** و لغو گزارش می‌شود
   (اشتباهِ رایجِ ۸: خریدنِ WR با هدفِ کوچک‌تر از حدِ ضرر).
۲. هر بازو با `n < 30` ⇒ **نامعتبر**، حکم صادر نمی‌شود.
۳. مدلِ صفرِ **هر** بازو با **هندسهٔ خودش** ساخته می‌شود ⇒ `BUG-NULLUNCOND`
   (که در `S435` سه بار در سه لباسِ متفاوت دیده شد: خطِ مبنای بی‌قید در
   گامِ ۳۷، هندسهٔ ناهمخوان در گامِ ۹۲، مدیریتِ ناهمخوان در گامِ ۹۷).
۴. `perm_k = pa.size` — یعنی **تعدادِ جای‌گشت‌هایی که واقعاً WR برگرداندند**،
   نه اندازهٔ نمونه ⇒ `BUG-PERMK`. موتور این فیلد را با `PERM_K_MIN=500`
   مقایسه می‌کند تا تصمیم بگیرد `H3` **معلوم** است یا نه.
۵. هر ثابتِ موتور (`pip` و…) در **زمانِ اجرا** از `se.ASSETS` خوانده می‌شود
   ⇒ `BUG-PIPGUESS` (طلا `pip=0.10` است نه `0.01`).

--------------------------------------------------------------------------------
`n_trials = 1928` — شمرده‌شده، نه تخمین‌زده
--------------------------------------------------------------------------------
`۲ side × ۲ EMA × ۳ n_run × ۲ br × ۲ clx × ۵ SL/TP = ۲۴۰` per-TF، ضربدرِ
`۸` ترکیبِ TF×دارایی ⇒ `۱٬۹۲۰`، به‌علاوهٔ `۳` واریانتِ ablation و `۵` بازوی
این پیش‌ثبت ⇒ **`۱٬۹۲۸`** ⇒ سدِ `z ≥ √(2·ln 1928) = ۳.۸۹`.

می‌شد `n_trials=5` اعلام کرد (فقط بازوهای خودم) و سد `۱.۷۹` می‌شد — و آنگاه
حتی `z=۲` هم پاس می‌کرد. `S435` دقیقاً همین وسوسه را داشت، `۲۹۲` اعلام کرد
و **به‌خاطرِ همان صداقت سوخت**. همان انتخاب اینجا هم تکرار می‌شود.
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'strategies'))

from engine import scalp_engine as se                       # noqa: E402
from engine.rqs2 import compute_rqs2                        # noqa: E402
import s214b_late_entry_as_filter as B                      # noqa: E402

OUT = 'results/_s436_arms'
ASSET = 'XAUUSD'

# 🔒 پیش‌ثبتِ گامِ ۱۰۷ — افزایشی و **علیهِ خودم**
N_TRIALS = 1928
N_PERM = 500
SEED = 11

PRE_END = [-6, -7, -8]                  # قابِ تقویمیِ ارثیِ S214
NIGHT = [19, 20, 21, 22, 23]            # ساعاتِ کنارگذاشتهٔ S214

# پیکربندیِ فیلترِ مومنتوم — خوانده‌شده از `s214c_final_independent_layer.py`
FILT = {'ef': 20, 'es': 50, 'n_run': 4, 'br': 0.5, 'clx': 1.5, 'look': 12}
GEO = {'sl': 150.0, 'tp': 300.0, 'mh': 96}

CARDS = {
    'M5':  'data/XAUUSD_M5.csv',
    'M15': 'data/XAUUSD_M15.csv',
    'M30': 'data/XAUUSD_M30.csv',
    'H1':  'data/XAUUSD_H1.csv',
}


# ═══════════════════════════ سازندگانِ سیگنال ═══════════════════════════

def load_card(tf: str) -> pd.DataFrame:
    df = se.load_data(os.path.join(ROOT, CARDS[tf]))
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df


def preeom_mask(df: pd.DataFrame) -> np.ndarray:
    """قابِ تقویمیِ `pre-EOM` — **کپیِ دقیقِ** `s214c.preeom_signal`.

    ⚠️ عمداً بازنویسی نشده بلکه **مو‌به‌مو** از منبع منتقل شده: `from_end`
    برابرِ `rank − count − 1` است، پس روزِ آخرِ ماه `−1` می‌شود و
    `{-6,-7,-8}` یعنی ششمین تا هشتمین روزِ **آخرِ** ماه.
    """
    dt = df['dt']
    d = pd.DataFrame({'date': dt.dt.normalize(),
                      'ym': dt.dt.year * 100 + dt.dt.month})
    days = d.drop_duplicates('date').reset_index(drop=True)
    days['rank'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank'] - days['cnt'] - 1
    mp = dict(zip(days['date'], days['from_end']))
    fe = d['date'].map(mp).to_numpy()
    return np.isin(fe, PRE_END)


def momentum_mask(df: pd.DataFrame) -> np.ndarray:
    """فیلترِ مومنتومِ فصلِ ۱۱ — از ماژولِ اصلیِ `s214b` فراخوانی می‌شود.

    بازنویسی نمی‌شود چون هستهٔ لایه است و هر تفاوتِ ریز در تعریفِ
    `trend-bar` یا قیدِ ضدِ climax، کلِ نامزد را به لایهٔ دیگری بدل می‌کند.
    """
    return B.late_entry_state_mask(df, FILT['ef'], FILT['es'], FILT['n_run'],
                                   FILT['br'], FILT['clx'], FILT['look'])


def day_mask(df: pd.DataFrame) -> np.ndarray:
    return ~np.isin(df['dt'].dt.hour.to_numpy(), NIGHT)


def build_arm_mask(df: pd.DataFrame, arm: str) -> np.ndarray:
    """ماسکِ هر بازو — **تفاوتِ بینِ بازوها فقط در قیدهاست**، نه در هسته."""
    mom = momentum_mask(df)
    if arm == 'B0':
        return preeom_mask(df) & day_mask(df) & mom
    if arm in ('A1', 'A3'):
        return day_mask(df) & mom
    if arm == 'A2':
        return mom
    raise ValueError(f'unknown arm {arm}')


# ═══════════════════════════ مدلِ صفر و داوری ═══════════════════════════

def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """مدلِ صفرِ **اختصاصیِ همین بازو با همین هندسه** (قیدِ ۳).

    هندسه **پارامتر** است نه ثابتِ داخلی، چون `A3` هدفِ متفاوتی دارد و
    مدلِ صفرش باید با **همان** هدف ساخته شود؛ وگرنه لیفت به‌جای مهارتِ
    سیگنال، **تغییرِ هندسه** را اندازه می‌گیرد.
    """
    n = len(df)
    z = np.zeros(n, bool)
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)

    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    um = np.zeros(n, bool)
    um[pick] = True
    tu = se.simulate_trades(df, um, z, sl, tp, ASSET, max_hold=mh,
                            allow_overlap=True)
    wr_unc = _wr(tu)

    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, pm, z, sl, tp, ASSET, max_hold=mh,
                               allow_overlap=False)
        w = _wr(t)
        if w is not None:
            perm.append(w)
    pa = np.array(perm, float) if perm else np.array([])
    return {'long': dict(uncond_wr=wr_unc,
                         perm_mean=float(pa.mean()) if pa.size else None,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else None,
                         perm_k=int(pa.size)),   # 🔴 قیدِ ۴ — BUG-PERMK
            'short': {}}


def derive_mfe_target(df, mask, mh) -> dict:
    """هدفِ `A3` را از **خودِ داده** می‌گیرد: چندکِ ۷۵٪ِ MFE در پنجرهٔ نگه‌داری.

    ⚠️ قیدِ ۵ — `pip` در زمانِ اجرا از موتور خوانده می‌شود، نه بازنویسی
       (`BUG-PIPGUESS`: طلا `0.10` است نه `0.01`؛ آن خطا `p75` را
       ۳٬۹۴۹pip داد یعنی حرکتِ ۳۹ دلاری در ۹۶ کندل — فقط چون **محال**
       بود گیر افتاد، نه چون بررسی‌ای وجود داشت).

    چرا **یک** چندک و نه جاروبِ ده‌تایی: عددی که داده تعیین می‌کند
    (`۳۹۴.۹` در `S435`) عمداً رند نیست، و جاروب هم `n_trials` را علیهِ
    خودم متورم می‌کند هم عدد را «به‌خاطرِ نتیجه‌اش» انتخاب می‌کند.
    """
    pip = se.ASSETS[ASSET]['pip']
    hi = df['high'].to_numpy()
    op = df['open'].to_numpy()
    n = len(df)
    idx = np.flatnonzero(mask)
    mfe = []
    for i in idx:
        if i + 1 + mh >= n:
            continue
        mfe.append((hi[i + 1:i + 1 + mh].max() - op[i + 1]) / pip)
    a = np.array(mfe, float)
    tp = float(np.percentile(a, 75)) if a.size else 0.0
    return {
        'pip_read_from_engine': pip,
        'n_signals': int(a.size),
        'mfe_pct': {f'p{q}': round(float(np.percentile(a, q)), 1)
                    for q in (50, 60, 70, 75, 80, 90)} if a.size else {},
        'tp_pip': round(tp, 1),
        'sl_pip': GEO['sl'],
        'rr': round(tp / GEO['sl'], 3) if GEO['sl'] else None,
        'constraint_tp_ge_sl': bool(tp >= GEO['sl']),
        'reach_old_tp_pct': round(100.0 * float((a >= GEO['tp']).mean()), 1)
        if a.size else None,
        'reach_new_tp_pct': round(100.0 * float((a >= tp).mean()), 1)
        if a.size else None,
    }


def adjudicate(df, mask, label, sl, tp, mh, card, oos_frac=0.30, extra=None):
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 30:            # قیدِ ۲
        return {'arm': label, 'card': card,
                'error': f'n<30 (n={0 if tr is None else len(tr)})',
                'invalid': True}

    null = null_for(df, mask, sl, tp, mh)
    split_bar = int(len(df) * (1.0 - oos_frac))
    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)
    g = res.get('gates') or {}
    m = res.get('metrics') or {}
    return {
        'arm': label,
        'card': card,
        'geometry': {'sl_pip': sl, 'tp_pip': tp, 'max_hold': mh,
                     'rr': round(tp / sl, 3)},
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
        'extra': extra,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='B0,A1')
    ap.add_argument('--card', default='M5')
    a = ap.parse_args()

    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    from math import sqrt, log
    print(f'[S436 داوری] XAUUSD-{a.card} · n_trials={N_TRIALS} · '
          f'{N_PERM} جای‌گشت/بازو · سد z≈{sqrt(2*log(N_TRIALS)):.2f}')

    df = load_card(a.card)
    print(f'  داده: {len(df)} کندل · '
          f'{df["dt"].iloc[0].date()} → {df["dt"].iloc[-1].date()}')

    for lbl in [x.strip() for x in a.arms.split(',') if x.strip()]:
        if lbl == 'A3':
            base = build_arm_mask(df, 'A1')
            d = derive_mfe_target(df, base, GEO['mh'])
            print(f"  [A3] TP مشتق‌شده={d['tp_pip']} pip · RR={d['rr']} · "
                  f"لمسِ TP قدیم={d['reach_old_tp_pct']}% → "
                  f"جدید={d['reach_new_tp_pct']}%")
            if not d['constraint_tp_ge_sl']:
                # قیدِ ۱ — در **کد** اجرا می‌شود نه در قضاوتِ من
                print(f"  ⛔ A3 لغو شد: TP={d['tp_pip']} < SL={d['sl_pip']} "
                      f"⇒ قانونِ حفظِ بودجه (اشتباهِ رایجِ ۸)")
                with open(os.path.join(ROOT, OUT, 'A3_CANCELLED.json'), 'w',
                          encoding='utf-8') as f:
                    json.dump({'cancelled': True, 'reason':
                               'TP<SL violates budget-preservation rule',
                               'derivation': d}, f, ensure_ascii=False, indent=1)
                continue
            out = adjudicate(df, base, 'A3', GEO['sl'], d['tp_pip'],
                             GEO['mh'], a.card, extra=d)
        else:
            mask = build_arm_mask(df, lbl)
            out = adjudicate(df, mask, lbl, GEO['sl'], GEO['tp'],
                             GEO['mh'], a.card)

        name = f'arm_{lbl}_{a.card}.json'
        with open(os.path.join(ROOT, OUT, name), 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)

        if out.get('invalid'):
            print(f"  ⛔ [{lbl}] نامعتبر: {out['error']}")
            continue
        m = out.get('metrics') or {}
        print(f"  ═══ [{lbl}·{a.card}] {out.get('verdict')} · "
              f"RQS2={out.get('rqs2_score')}")
        print(f"      n={m.get('n_trades')} WR={m.get('win_rate')} "
              f"lift={m.get('skill_lift_pp')} z={m.get('skill_z')} "
              f"PF={m.get('profit_factor')} net={m.get('net_profit')}")
        print(f"      افتاده={out.get('failed_gates')} "
              f"نامعلوم={out.get('unknown_gates')}")

    print('\n[done]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
