# -*- coding: utf-8 -*-
"""
S351-POOL — آزمونِ نجاتِ چند-کارتیِ لبهٔ POWER-LIMITED
================================================================================
هدف: اثباتِ عملیِ مسیرِ نجاتی که با حکمِ POWER-LIMITED و ابزارِ
`engine/rqs2_pool.py` ساختیم.

فرضیه: عضوِ مرکزیِ LPSB (L=8, f=0.33) روی XAUUSD-D1 یک لبهٔ اقتصاداً-سالمِ
هم‌جهت با lift مثبت دارد که فقط به‌خاطرِ کمبودِ نمونه (n≈۷۴) H3 را رد می‌کند.
اگر همان قانون را روی چند تایم‌فریمِ بالای هم‌جهتِ طلا (D1 + H4 + H1) اجرا و
trades را روی محورِ زمانِ تقویمی ادغام کنیم، نمونه بزرگ می‌شود و z ممکن است
از زیرِ ۳ به بالای ۳ برود — **بدونِ شل کردنِ هیچ آستانه‌ای**.

اگر z پس از تجمیع ≥۳ شد و همهٔ گیت‌ها پاس شدند ⇒ ACCEPT (لبهٔ واقعیِ نجات‌یافته).
اگر همچنان z<۳ ⇒ POWER-LIMITED می‌ماند (صادقانه: هنوز نمونه کم است).
اگر پس از تجمیع lift ریخت ⇒ درسِ منفی: لبه روی TFها یکسان نبوده.

هر سه نتیجه علمی و آموزنده است.
"""
import sys
import json
import numpy as np

from engine import scalp_engine as se
from engine import rqs2
from engine.rqs2_pool import pool_cards
from strategies.s351_lpsb import (atr_series, lpsb_signals,
                                  GEO_SL_K, GEO_RR, GEO_HOLD, ATR_P, SEED)
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip
from strategies.s351_verdict import build_null_side, CENTRAL, CARDS

# تایم‌فریم‌های بالای طلا که در اسکنِ خام lift مثبت داشتند (هم‌جهت).
# D1: lift≈+14 · H4: lift≈+0.9 · H1: lift≈+2.3  (همه مثبت ⇒ مجازِ تجمیع)
POOL_MEMBERS = ['XAUUSD-D1', 'XAUUSD-H4', 'XAUUSD-H1']
WARMUP = max(4 * (2 * 13 + 1), 250)
OUT = 'results/_scan_S351'


def card_trades(card):
    """اجرای عضوِ مرکزی روی یک کارت؛ برمی‌گرداند (tr, dt, lift, sl_med, tp_med)."""
    asset, path = CARDS[card]
    df = se.load_data(path)
    atr = atr_series(df)
    dt = df['dt'].values if 'dt' in df.columns else np.arange(len(df))
    ls, ss, _ = lpsb_signals(df, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    sel = (ls | ss) & np.isfinite(atr) & (atr > 0)
    sig = np.where(sel)[0]
    if len(sig) < 5:
        return None
    is_long = ls[sig]
    st = queue_rr(df, sig, is_long, GEO_SL_K * atr[sig], asset, GEO_HOLD, GEO_RR)
    if st is None or st['n'] < 5:
        return None
    tr = trades_df(st)

    # مبنای اندازه‌گیری‌شده برای lift همین کارت
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[valid >= WARMUP]
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    rng = np.random.default_rng(SEED)
    null = build_null_side(df, asset, valid, GEO_SL_K * atr, nL, nS,
                           200, rng, verbose=False)
    nb = rqs2.blend_null(null, {'long': nL, 'short': nS})
    wr = float((tr['outcome'] == 'win').mean() * 100) if 'outcome' in tr else \
        float((tr['pnl_pip'] > 0).mean() * 100)
    lift = (wr - nb['ref_wr']) if nb else None
    return dict(card=card, tr=tr, dt=dt, lift=lift,
                sl_med=float(np.median(st['sl_pip'])),
                tp_med=float(np.median(st['tp_pip'])),
                asset=asset, df=df, atr=atr, valid=valid, nL=nL, nS=nS)


def main():
    print("=" * 90, flush=True)
    print("=== S351-POOL :: multi-card rescue of the POWER-LIMITED daily edge ===",
          flush=True)
    print(f"    frozen geom: sl_k={GEO_SL_K} rr={GEO_RR} hold={GEO_HOLD} "
          f"atr_p={ATR_P} · central L={CENTRAL['L']} f={CENTRAL['f']}", flush=True)

    members = []
    for card in POOL_MEMBERS:
        d = card_trades(card)
        if d is None:
            print(f"    [{card}] no usable trades — skipped", flush=True)
            continue
        print(f"    [{card}] n={len(d['tr']):5d}  lift={d['lift']:+6.2f}pp  "
              f"sl={d['sl_med']:.1f} tp={d['tp_med']:.1f}", flush=True)
        members.append(d)

    if not members:
        print("    no members — abort", flush=True)
        return

    pooled = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                              lift=m['lift']) for m in members])
    if pooled is None:
        print("    pooling produced nothing (all lifts non-positive?)", flush=True)
        return

    print(f"\n    pooled {pooled['n_before']} → {pooled['n_after']} "
          f"non-overlapping calendar trades "
          f"({100*pooled['n_after']/pooled['n_before']:.0f}% kept)", flush=True)
    if pooled['dropped']:
        for d in pooled['dropped']:
            print(f"      dropped {d['card']}: {d['reason']}", flush=True)

    # داوریِ RQS2 روی استخر. مبنای صفر را از پرمصرف‌ترین عضو (بیشترین n) می‌سازیم
    # با همان هندسهٔ نسبی. n_trials محافظه‌کارانه = مجموعِ ۱۵ کارت × ۳ عضوِ پول.
    base = max(members, key=lambda m: len(m['tr']))
    pool = pooled['pool']
    # بازسازیِ ستون‌های لازم برای compute_rqs2 روی محورِ کارتِ مبنا
    tr_pool = pool.copy()
    # entry_bar/exit_bar را از زمانِ تقویمی به اندیسِ کارتِ مبنا نگاشت نمی‌کنیم؛
    # در عوض bar_time را مستقیم از t_entry می‌سازیم (RQS2 فقط ترتیب/زمان می‌خواهد).
    bar_time = tr_pool['t_entry'].values.astype('datetime64[ns]')
    sl_med = float(np.median([m['sl_med'] for m in members]))
    tp_med = float(np.median([m['tp_med'] for m in members]))

    nL = int((tr_pool['direction'] == 'long').sum())
    nS = int(len(tr_pool) - nL)
    rng = np.random.default_rng(SEED)
    null = build_null_side(base['df'], base['asset'], base['valid'],
                           GEO_SL_K * base['atr'], nL, nS, 300, rng, verbose=False)

    n_trials = len(CARDS) * len(POOL_MEMBERS)   # ۱۵×۳ = ۴۵ (محافظه‌کارانه)
    # split برای H7: ۶۰٪ نخستِ زمانِ تقویمی
    order = np.argsort(tr_pool['t_entry'].values)
    split_t = tr_pool['t_entry'].values[order[int(len(order) * 0.60)]]
    hold_mask = (tr_pool['t_entry'].values >= split_t)

    r = rqs2.compute_rqs2(tr_pool, base['asset'], n_trials=n_trials,
                          sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                          null=null, holdout_mask=hold_mask)
    print("\n" + rqs2.format_rqs2('POOL D1+H4+H1', r), flush=True)
    print(f"    verdict = {r['verdict']}  |  power_limited={r.get('power_limited')}",
          flush=True)
    gf = r.get('gate_families', {})
    print(f"    economic_all_pass={gf.get('economic_all_pass')}  "
          f"power_defects={gf.get('power_defects')}", flush=True)

    out = dict(members=[dict(card=m['card'], n=int(len(m['tr'])), lift=m['lift'])
                        for m in members],
               n_before=pooled['n_before'], n_after=pooled['n_after'],
               dropped=pooled['dropped'],
               verdict=r['verdict'], power_limited=r.get('power_limited'),
               rqs2_score=r['rqs2_score'],
               gates=r['gates'], gate_families=gf,
               skill_lift_pp=r['metrics'].get('skill_lift_pp'),
               skill_z=r['metrics'].get('skill_z'),
               n_trades=r['metrics'].get('n_trades'))
    path = f"{OUT}/_pool_rescue.json"
    with open(path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"    [checkpoint] {path}", flush=True)


if __name__ == '__main__':
    main()
