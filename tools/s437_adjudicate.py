# -*- coding: utf-8 -*-
"""
s437_adjudicate.py — داورِ `S437`: احیای `SoS` روی کارتِ **بکرِ** `EURUSD-M30`

پیش‌ثبت: `results/S437_PREREG_SOS_EURUSD_M30_VIRGIN_CARD.md` (گام ۱۳۰)

╭──────────────────────────────────────────────────────────────────────────╮
│ چهار بازوی پیش‌ثبت‌شده — نه بیشتر:                                        │
│   V0  لبهٔ خامِ SoS، هندسهٔ SL=15/TP=30 pip                               │
│   V1  V0 + فیلترِ ارثیِ ATR14>ATR100  (پیش‌بینی‌ام: مضر)                   │
│   V2  V0 با thr یک پله بالاتر                                            │
│   V3  V0 با هندسهٔ مشتق از MFE خودِ داده                                  │
╰──────────────────────────────────────────────────────────────────────────╯

گاردهایی که از پنجاه‌وچند گامِ قبل به ارث رسیده‌اند — هر یک با نامِ باگی که
تولیدش کرد، تا خوانندهٔ بعدی بداند *چرا* آنجاست نه فقط *که* آنجاست:

  ① `BUG-PERMK`     — `perm_k = pa.size` (تعدادِ جای‌گشت‌ها) نه اندازهٔ نمونه.
                       در `S435` مقدارِ غلط در یک بازو داد زد و در بازوی دیگر
                       **بی‌صدا** حکم داد که «H3 معلوم است» با ۴۰ جای‌گشت.

  ② `BUG-NULLUNCOND`— نالِ هر بازو با هندسهٔ **خودِ همان بازو** ساخته می‌شود.
                       سه بار در `S435` در سه لباس ظاهر شد. اگر `V3` با نالِ
                       `V0` سنجیده شود، لیفت به‌جای مهارتِ سیگنال **تغییرِ
                       هندسه** را اندازه می‌گیرد.

  ③ `BUG-SCOREKEY`  — نگاشتِ خروجیِ موتور **عیناً** از `s436_adjudicate.py`
                       کپی شده. کلیدِ درست `rqs2_score` است؛ `score` بی‌صدا
                       `None` می‌دهد و `None > None` همیشه `False` است.
                       `failed`/`unknown` کلیدِ موتور **نیستند** و از `gates`
                       مشتق می‌شوند.

  ④ `BUG-ZBARAPPROX`— سدِ چاپ‌شده از `z_luck_bound` خودِ موتور خوانده می‌شود،
                       **نه** بازمحاسبه با `sqrt(2·lnN)`. آن تقریب در تمامِ
                       `S436` چاپ می‌شد و ۱۳.۲٪ سخت‌گیرانه‌تر از سدِ واقعی بود.
                       چون فقط **چاپ** می‌شد و با چیزی سنجیده نمی‌شد، تا
                       گام ۱۲۶ زنده ماند.

  ⑤ `BUG-PIPGUESS`  — اندازهٔ `pip` در زمانِ اجرا از موتور **خوانده** می‌شود.
                       یورو `0.0001` است و طلا `0.10`. حدس زدنش در `S435`
                       عددی داد که فقط چون **فیزیکاً محال** بود گیر افتاد.

  ⑥ قیدِ ۲          — زیرِ ۳۰ معامله **حکم داده نمی‌شود** ⇒
                       `MEASUREMENT-LIMITED`. «نمونهٔ ناکافی» و «لایه شکست
                       خورد» دو یافتهٔ متفاوت‌اند.

⚠️ `n_trials = 412` — محافظه‌کارانه‌ترین شمارش (گام ۱۳۰، بخش ۲). چون
   `expected_max_z(N)=3.09` در `N=567` حل می‌شود، هر شمارشی زیرِ ۵۶۶ سدِ
   یکسان می‌دهد ⇒ صداقت اینجا **رایگان** است.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'strategies'), os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import scalp_engine as se                      # noqa: E402
from engine.rqs2 import compute_rqs2                       # noqa: E402
import tools.s435_coverage_union as cov                    # noqa: E402

OUT = 'results/_s437_arms'
N_TRIALS = 412        # گام ۱۳۰ بخش ۲ — محافظه‌کارانه‌ترین سناریو
N_PERM = 500          # درسِ `S435` گام ۸۷: زیرِ ۵۰۰ حکمِ `H3` نوسانی است
SEED = 20260811

CARDS = {
    'EURUSD-M30': ('data/EURUSD_M30.csv', 'EURUSD'),
    'EURUSD-M15': ('data/EURUSD_M15.csv', 'EURUSD'),
    'EURUSD-M5':  ('data/EURUSD_M5.csv',  'EURUSD'),
    'EURUSD-H1':  ('data/EURUSD_H1.csv',  'EURUSD'),
    'XAUUSD-M5':  ('data/mt5_full/XAUUSD_M5.csv.gz',  'XAUUSD'),
    'XAUUSD-M30': ('data/mt5_full/XAUUSD_M30.csv.gz', 'XAUUSD'),
}

# 🔴 گامِ ۱۳۲ — `BUG-GEOMDRIFT`: اینجا `SL=15/TP=30` نوشته بودم، ولی
#    `tools/s437_virgin_card_scout.py` با `SL=50/TP=100` شمرده بود.
#    ⇒ **همان کارت، دو هندسهٔ متفاوت، بی‌هیچ خطا.**
#    پیامد: عددِ `n=1229` که کلِ محاسبهٔ توانِ گام ۱۲۹ و نقطهٔ شکستِ
#    `4.40pp` در پیش‌ثبتِ گام ۱۳۰ بر آن بنا شد، به هندسه‌ای تعلق داشت که
#    **هرگز داوری نشد**. داور با ۱۵/۳۰ رفت و `n=1953` گرفت (‎+۵۹٪‏) و
#    `WR` از ۳۸.۸۹٪ به ۳۱.۵۹٪ افتاد — چون `SL` تنگ‌تر زودتر می‌خورد.
#    ⇒ هندسه از **همان ثابتِ کاوش** خوانده می‌شود تا واگرایی محال شود.
#    (همان درسِ `BUG-LPSBIMPORT`: دو ابزاری که یک چیز می‌سازند باید از یک
#     منبع بخوانند، نه اینکه هر کدام مقدارِ خودش را بنویسد.)
import tools.s437_virgin_card_scout as _scout                # noqa: E402

GEOM = {k: dict(sl=float(v['sl']), tp=float(v['tp']), mh=int(v['mh']))
        for k, v in _scout.GEOM.items()}


def load_card(key: str) -> tuple[pd.DataFrame, str]:
    rel, asset = CARDS[key]
    df = se.load_data(os.path.join(ROOT, rel))
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df, asset


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def sos_edge_thr(df: pd.DataFrame, thr: int | None = None) -> np.ndarray:
    """لبهٔ صعودیِ نمرهٔ `SoS`.

    `thr=None` ⇒ عیناً `cov.sos_edge` (آستانهٔ `CAND['thr']`، بی‌هیچ تغییر).
    ⚠️ برای `V2` آستانه یک پله بالا می‌رود؛ آن **یک** بازوی پیش‌ثبت‌شده است،
       نه جاروبِ آستانه. جاروب کردن `n_trials` را متورم می‌کند و آستانه را
       «به‌خاطرِ نتیجه‌اش» انتخاب می‌کند.
    """
    if thr is None:
        return cov.sos_edge(df)
    from s171_brooks_signs_of_strength_filter import signs_of_strength_bull
    sos = signs_of_strength_bull(df, ema_period=cov.CAND['ema_period'],
                                 win=cov.CAND['win'])
    strong = np.asarray(sos['score']) >= thr
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    # `shift(1)` دومِ عمدی: ورود در کندلِ بعد ⇒ بی‌نگاه به آینده
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


def null_for(df, mask, sl, tp, mh, asset, n_perm=N_PERM, seed=SEED):
    """مدلِ صفرِ **اختصاصیِ همین بازو با همین هندسه** — گاردِ ②.

    عیناً از `tools/s436_adjudicate.py` کپی شده، با `asset` به‌عنوان
    پارامتر تا برای یورو و طلا هر دو درست کار کند.
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
    tu = se.simulate_trades(df, um, z, sl, tp, asset, max_hold=mh,
                            allow_overlap=True)
    wr_unc = _wr(tu)

    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, pm, z, sl, tp, asset, max_hold=mh,
                               allow_overlap=False)
        w = _wr(t)
        if w is not None:
            perm.append(w)
    pa = np.array(perm, float) if perm else np.array([])
    return {'long': dict(uncond_wr=wr_unc,
                         perm_mean=float(pa.mean()) if pa.size else None,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else None,
                         perm_k=int(pa.size)),      # 🔴 گاردِ ① BUG-PERMK
            'short': {}}


def derive_mfe_target(df, mask, mh, asset) -> dict:
    """هندسهٔ `V3` را از **خودِ داده** می‌گیرد: `TP=q60(MFE)` و `SL=q30(MAE)`.

    ⚠️ گاردِ ⑤ — اندازهٔ `pip` از موتور **خوانده** می‌شود، نه حدس زده.
    چرا **یک** چندک و نه جاروبِ ده‌تایی: عددی که داده تعیین می‌کند عمداً رند
    نیست، و جاروب هم `n_trials` را متورم می‌کند هم عدد را به‌خاطرِ نتیجه‌اش
    انتخاب می‌کند (اشتباهِ رایجِ ۷ و جست‌وجوی پنهان، هر دو).

    🔴 گامِ ۱۳۸ — تصحیحِ دامنه. نسخهٔ نخست فقط `TP` را از `q75(MFE)`
    می‌گرفت و `SL` را دست‌نخورده رها می‌کرد. سرشماریِ خروجِ گام ۱۳۷ نشان
    داد **مشکلِ اصلی سمتِ `SL` است**: `SL` کامل در ۵۱.۱٪ می‌خورد در برابرِ
    `TP` کامل در ۱۸.۱٪ (نسبتِ ۲.۸:۱)، و همین `RR` محقق‌شده را از ۲.۰۰ به
    ۱.۴۱ می‌بَرد و سربه‌سرِ واقعی را به ۴۱.۴۵٪ می‌رساند.
    ⇒ اصلاحِ یک‌طرفهٔ `TP`، نامتقارنی را **حل نمی‌کند**؛ فقط جای آن را
      عوض می‌کند. هر دو سمت باید از داده بیایند.
    ⚠️ این **گسترشِ دامنه** است نه بازویِ نو: هدفِ پیش‌ثبت‌شدهٔ `V3`
      «هندسهٔ مشتق از دادهٔ خودِ کارت» بود و `SL` بخشی از هندسه است.
      چندک‌ها (`q60`/`q30`) در گام ۱۳۶ **پیش از دیدنِ مقادیرشان** ثبت شدند.
    """
    pip = se.pip_size(asset) if hasattr(se, 'pip_size') else None
    if pip is None:
        spec = getattr(se, 'ASSETS', {}).get(asset, {})
        pip = spec.get('pip') or spec.get('pip_size')
    if pip is None:
        raise RuntimeError(f'pip size for {asset} not readable from engine')

    h = df['high'].to_numpy()
    l = df['low'].to_numpy()
    c = df['close'].to_numpy()
    idx = np.flatnonzero(np.asarray(mask, bool))
    mfes, maes = [], []
    n = len(df)
    for i in idx:
        j0, j1 = i + 1, min(i + 1 + mh, n)
        if j1 <= j0:
            continue
        mfes.append((h[j0:j1].max() - c[i]) / pip)
        maes.append((c[i] - l[j0:j1].min()) / pip)
    if not mfes:
        return {'pip': pip, 'p75': None, 'tp': None, 'sl': None, 'n': 0}
    # قاعده‌ای که در گامِ ۱۳۶ **پیش از دیدنِ مقادیر** ثبت شد:
    #   TP = q60(MFE) ⇒ ~۶۰٪ سیگنال‌ها *امکانِ فیزیکیِ* رسیدن دارند
    #   SL = q30(MAE) ⇒ ~۷۰٪ سیگنال‌ها هرگز به آن نمی‌رسند
    tp_q = float(np.percentile(mfes, 60))
    sl_q = float(np.percentile(maes, 30))
    return {'pip': float(pip), 'n': len(mfes),
            'p75': float(np.percentile(mfes, 75)),   # حفظ برای سازگاری
            'tp': round(tp_q, 1), 'sl': round(sl_q, 1),
            'rule': 'TP=q60(MFE) · SL=q30(MAE)',
            'rr': round(tp_q / sl_q, 3) if sl_q else None}


def adjudicate(df, mask, label, sl, tp, mh, card, asset,
               oos_frac=0.30, extra=None):
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 30:                 # گاردِ ⑥ — قیدِ ۲
        return {'arm': label, 'card': card,
                'error': f'n<30 (n={0 if tr is None else len(tr)})',
                'invalid': True, 'n_signals': int(mask.sum())}

    null = null_for(df, mask, sl, tp, mh, asset)
    split_bar = int(len(df) * (1.0 - oos_frac))
    res = compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(),
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)
    g = res.get('gates') or {}
    m = res.get('metrics') or {}
    return {                                        # گاردِ ③ — نگاشتِ کپی‌شده
        'arm': label,
        'card': card,
        'asset': asset,
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
        # 🔴 گامِ ۱۳۳ — `BUG-ZBARNEST`: گاردِ ④ **کار نکرد**. من
        #    `res.get('z_luck_bound')` نوشتم ولی موتور آن را داخلِ
        #    `res['metrics']` می‌گذارد (خطِ ۱۳۷۱ در `engine/rqs2.py`).
        #    ⇒ سطحِ بالا `None` داد و لاگ `bar=None` چاپ کرد.
        #    ⚠️ نکتهٔ ظریف‌تر: `z_luck_bound` در فهرستِ کلیدهایی که از
        #    `metrics` کپی می‌کردم **هم** نبود، پس عدد **دو بار** گم شد.
        #    ⇒ درسِ `BUG-SCOREKEY` را نصفه اجرا کردم: نگاشت را کپی کردم
        #      ولی وقتی کلیدِ **تازه‌ای** افزودم، دوباره حدس زدم کجاست.
        #      کپی‌کردنِ یک نگاشت از کپی‌کردنِ *عادتِ خواندن از منبع* کمتر است.
        'z_luck_bound': m.get('z_luck_bound'),
        'z_margin': m.get('z_margin'),
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'rr', 'top_win_share',
            'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm',
            'p_emp', 'p_adj_bonferroni', 'perm_k', 'perm_max')},
        'notes': [str(x) for x in (res.get('notes') or [])],
        'extra': extra,
    }


def build_arm(df, arm: str, asset: str):
    """ماسک + هندسهٔ هر بازو. هیچ بازوی خارج از پیش‌ثبت ساخته نمی‌شود."""
    g = GEOM[asset]
    sl, tp, mh = g['sl'], g['tp'], g['mh']

    if arm == 'V0':
        return sos_edge_thr(df), sl, tp, mh, None

    if arm == 'V1':
        return sos_edge_thr(df) & cov.atr_filter(df), sl, tp, mh, None

    if arm == 'V2':
        thr = int(cov.CAND['thr']) + 1
        if thr > 4:
            return None, sl, tp, mh, {'skip': f'thr={thr} > 4 (سقفِ نمره)'}
        return sos_edge_thr(df, thr), sl, tp, mh, {'thr': thr}

    if arm == 'V3':
        m = sos_edge_thr(df)
        d = derive_mfe_target(df, m, mh, asset)
        # 🔴 گامِ ۱۳۸ — هر **دو** سمت از داده. پیش‌تر `sl` ثابتِ کارت پاس
        #    می‌شد و فقط `tp` عوض می‌شد ⇒ نامتقارنی جابه‌جا می‌شد نه حل.
        if not d.get('tp') or not d.get('sl'):
            return None, sl, tp, mh, {'skip': 'چندکِ MFE/MAE نامعلوم'}
        return m, float(d['sl']), float(d['tp']), mh, d

    raise ValueError(f'بازوی ناشناخته: {arm}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='V0')
    ap.add_argument('--card', default='EURUSD-M30')
    a = ap.parse_args()

    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    print(f'[S437 داوری] {a.card} · n_trials={N_TRIALS} · '
          f'{N_PERM} جای‌گشت/بازو')
    print('  ⚠️ سد از `z_luck_bound` خودِ موتور خوانده می‌شود (گاردِ ④)')

    df, asset = load_card(a.card)
    print(f'  داده: {len(df):,} کندل · '
          f'{df["dt"].iloc[0].date()} → {df["dt"].iloc[-1].date()} · {asset}')

    for arm in [x.strip() for x in a.arms.split(',') if x.strip()]:
        mask, sl, tp, mh, extra = build_arm(df, arm, asset)
        if mask is None:
            print(f'  ⛔ [{arm}] رد شد: {extra}')
            continue
        out = adjudicate(df, mask, arm, sl, tp, mh, a.card, asset, extra=extra)
        path = os.path.join(ROOT, OUT, f'arm_{arm}_{a.card}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        if out.get('invalid'):
            print(f'  ⛔ [{arm}] نامعتبر: {out["error"]} '
                  f'(سیگنال={out.get("n_signals")})')
            continue
        m = out['metrics']
        print(f'  [{arm}] SL={sl}/TP={tp} n={m["n_trades"]} '
              f'WR={m["win_rate"]} lift={m["skill_lift_pp"]} '
              f'z={m["skill_z"]} bar={out.get("z_luck_bound")} '
              f'PF={m["profit_factor"]} net=${m["net_profit"]} '
              f'RQS2={out.get("rqs2_score")} {out.get("verdict")}')
        print(f'        شکسته={out.get("failed_gates")} '
              f'نامعلوم={out.get("unknown_gates")}')

    print('[done]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
