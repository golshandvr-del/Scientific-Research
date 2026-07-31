# -*- coding: utf-8 -*-
"""
S351 — داورِ رسمیِ RQS2 برای «شکستِ ساختارِ لگ-متناسب» (LPSB)
================================================================================
منبعِ ایده : Market_Structure_Break_and_Order_Block_v3@free_fx_pro.mq4 (GPL)
معیارِ داوری: engine/rqs2.py (پذیرش = هر ۱۱ دروازه؛ بدونِ کفِ نمره‌ای)

--------------------------------------------------------------------------------
پرسشِ علمیِ این ماژول — تنها یک پرسش
--------------------------------------------------------------------------------
    «سیگنالِ شکستِ ساختار که آستانه‌اش به دامنهٔ لگِ ساختاری نرمال شده
      (نه به ATR)، آیا مهارتِ آماریِ معنادار نسبت به مدلِ صفر دارد —
      یا فقط یک بازتولیدِ همان لبهٔ ATR-محورِ خانوادهٔ S346 است؟»

--------------------------------------------------------------------------------
⛔ چرا این «نرم‌کردنِ معیار» نیست — مرزِ دقیق
--------------------------------------------------------------------------------
۱) هندسه **جست‌وجو نمی‌شود**: sl_k=1.618, rr=1.618, hold=12 از قانونِ قفلِ
   سه‌گانه مشتق شده‌اند (docs/FINDING_BARRIER_REACHABILITY_LAW.md) و روی هیچ
   کارتی تنظیم نمی‌شوند. یکسان برای هر ۹ عضو و هر ۱۵ کارت.
۲) خانواده **پیش‌ثبت‌شده** است: L∈{5,8,13}, f∈{0.236,0.33,0.5} ⇒ ۹ عضو.
   هیچ عضوی گزینش نمی‌شود ⇒ آمارهٔ N=1 (میانگینِ خانواده). ولی حکمِ رسمی
   با شمارشِ بدبینانه‌تر صادر می‌شود (زیر).
۳) مبنای اندازه‌گیری‌شده (null) **همان هندسهٔ منجمد** را دارد (rr=1.618).

--------------------------------------------------------------------------------
شمارشِ چندگانگیِ پیش‌ثبت‌شده (قبل از دیدنِ نتیجه)
--------------------------------------------------------------------------------
    N_OFFICIAL = 9 (اعضای خانواده) × 15 (کارت) = 135      ← حکمِ رسمی
    N_FAMILY   = 9                                        ← حساسیت (خانوادهٔ همین کارت)
    N_SINGLE   = 1                                        ← حساسیت (یک فرضیه)
⚠️ اگر لایه فقط در SINGLE پاس کند و در OFFICIAL نه، **رد** است و صریح نوشته
   می‌شود با کدام شمارش پاس شد. جابه‌جاییِ شمارش بعد از دیدنِ نتیجه = تقلب.

--------------------------------------------------------------------------------
داوریِ خانواده (چون هیچ عضوی گزینش نمی‌شود)
--------------------------------------------------------------------------------
معاملاتِ هر ۹ عضو **ادغام** می‌شوند (concat) و یک بار RQS2 روی مجموعهٔ
ادغام‌شده اجرا می‌شود؛ این همان «آمارهٔ N=1» است چون کلِ خانواده یک شیء واحد
تلقی می‌شود، نه ۹ آزمونِ جدا که بهترینش انتخاب شود. برای شفافیت، RQS2ِ
تک‌تکِ اعضا هم گزارش می‌شود ولی حکم روی خانوادهٔ ادغام‌شده است.

--------------------------------------------------------------------------------
قانونِ «اندک اندک»
--------------------------------------------------------------------------------
هر کارت که تمام شود فوراً results/_scan_S351/<card>_rqs2.json نوشته می‌شود.
"""
import sys
import os
import json
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies.s348_rr_sweep import (queue_rr, trades_df,          # noqa: E402
                                      cost_pip, SPLIT_FRAC)
from strategies.s351_lpsb import (atr_series, lpsb_signals,         # noqa: E402
                                  members, CARDS, GEO_SL_K, GEO_RR,
                                  GEO_HOLD, ATR_P, SEED)

OUT = 'results/_scan_S351'

# ==================== شمارشِ چندگانگیِ پیش‌ثبت‌شده ====================
N_OFFICIAL = len(members()) * len(CARDS)     # = 9 × 15 = 135   ← حکم
N_FAMILY = len(members())                    # = 9              ← حساسیت
N_SINGLE = 1                                 #                  ← حساسیت

# عضوِ مرکزیِ پیش‌ثبت‌شده: مرکزِ فراکتالیِ هر دو محورِ خانواده. این فرضیهٔ اصلی
# است چون یک عضوِ تنها ذاتاً بی‌همپوشان است و z صادقانه می‌دهد. از پیش تعیین
# شده — نه پس از دیدنِ نتایج. حکمِ رسمی روی این عضو با N=15 (فقط کارت‌ها) است.
CENTRAL = dict(L=8, f=0.33)
N_CENTRAL = len(CARDS)                        # = 15  ← حکمِ عضوِ مرکزی


def _fifo_non_overlap(entry_bar, exit_bar):
    """
    انتخابِ زیرمجموعهٔ بی‌همپوشانِ معاملات از استخرِ ادغام‌شدهٔ چند عضو.

    قاعدهٔ FIFO: به ترتیبِ زمانِ ورود پیش می‌رویم؛ معامله فقط اگر ورودش پس از
    خروجِ آخرین معاملهٔ پذیرفته‌شده باشد پذیرفته می‌شود. عیناً منطقِ
    select_non_overlap موتور، اما چون معاملات از منابع (اعضای) مختلف آمده‌اند،
    این‌جا روی اندیسِ سراسری اعمال می‌شود. خروجی: آرایهٔ اندیس‌های نگه‌داشته‌شده.
    """
    order = np.argsort(entry_bar, kind='mergesort')
    keep = []
    last_exit = -1
    for idx in order:
        if entry_bar[idx] > last_exit:
            keep.append(idx)
            last_exit = exit_bar[idx]
    return np.array(sorted(keep), dtype=np.int64)


def member_trades(df, atr, asset, L, f, warmup):
    """معاملاتِ یک عضو با هندسهٔ منجمد. برمی‌گرداند st (خروجی queue_rr) یا None."""
    ls, ss, _ = lpsb_signals(df, L, f, warmup=warmup)
    sel = (ls | ss) & np.isfinite(atr) & (atr > 0)
    sig = np.where(sel)[0]
    if len(sig) == 0:
        return None
    is_long = ls[sig]
    sl_dist = GEO_SL_K * atr[sig]
    st = queue_rr(df, sig, is_long, sl_dist, asset, GEO_HOLD, GEO_RR)
    return st


def build_null_side(df, asset, valid, atr_plain, n_long, n_short,
                    n_perm, rng, verbose=True):
    """مبنای اندازه‌گیری‌شده به تفکیکِ سمت، با همان هندسهٔ منجمد (rr=GEO_RR)."""
    null = {}
    for side, is_long_flag, n_side in (('long', True, n_long),
                                       ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) >= 2:
            slv = atr_plain[valid]
            ok = np.isfinite(slv) & (slv > 0)
            vi, slv = valid[ok], slv[ok]
            if len(vi) >= 2:
                s_all = queue_rr(df, vi, np.full(len(vi), is_long_flag),
                                 slv, asset, GEO_HOLD, GEO_RR)
                if s_all:
                    d['uncond_wr'] = s_all['wr']
                if len(vi) > n_side:
                    wrs = []
                    for _ in range(n_perm):
                        pick = np.sort(rng.choice(len(vi), size=n_side,
                                                  replace=False))
                        s_p = queue_rr(df, vi[pick],
                                       np.full(n_side, is_long_flag),
                                       slv[pick], asset, GEO_HOLD, GEO_RR)
                        if s_p:
                            wrs.append(s_p['wr'])
                    if wrs:
                        a = np.asarray(wrs, dtype='float64')
                        d.update(perm_mean=float(a.mean()),
                                 perm_sd=float(a.std(ddof=1)),
                                 perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        if verbose:
            print(f"      null {side:<5} uncond={d['uncond_wr']} "
                  f"perm_mean={d['perm_mean']} sd={d['perm_sd']}", flush=True)
    return null


def run_card(card, n_perm=200, verbose=True):
    asset, path = CARDS[card]
    if not os.path.exists(path):
        out = dict(card=card, verdict='NO_DATA')
        _save(card, out)
        return out
    df = se.load_data(path)
    atr = atr_series(df)
    close = df['close'].values.astype('float64')
    bar_time = df['dt'].values if 'dt' in df.columns else None
    warmup = max(4 * (2 * 13 + 1), 250)
    split = int(len(df) * SPLIT_FRAC)
    c = cost_pip(asset)

    print(f"\n{'='*90}\n=== S351 LPSB :: {card} (bars={len(df):,}) ===", flush=True)
    print(f"    FROZEN geom: sl_k={GEO_SL_K} rr={GEO_RR} hold={GEO_HOLD} "
          f"atr_p={ATR_P} · cost={c:.2f}pip · N_official={N_OFFICIAL}", flush=True)

    if len(df) < warmup + 50:
        out = dict(card=card, asset=asset, bars=len(df), verdict='TOO_SHORT')
        _save(card, out)
        return out

    # ---- ۱) معاملاتِ هر ۹ عضو، سپس ادغام (آمارهٔ N=1 خانواده) ----
    member_res = []
    frames = []
    for m in members():
        st = member_trades(df, atr, asset, m['L'], m['f'], warmup)
        if st is None or st['n'] < 3:
            member_res.append(dict(L=m['L'], f=m['f'], n=0))
            continue
        tr_m = trades_df(st)
        tr_m['member'] = f"L{m['L']}_f{m['f']}"
        frames.append(tr_m)
        member_res.append(dict(L=m['L'], f=m['f'], n=st['n'], wr=st['wr'],
                               exp=st['exp'], pf=st['pf'],
                               sl_pip=float(np.median(st['sl_pip'])),
                               tp_pip=float(np.median(st['tp_pip']))))
    if not frames:
        out = dict(card=card, asset=asset, bars=len(df), verdict='NO_TRADES')
        _save(card, out)
        return out

    # ---- ۱ب) عضوِ مرکزیِ پیش‌ثبت‌شده (فرضیهٔ اصلیِ صادقانه) ----
    # L=8, f=0.33 = مرکزِ فراکتالیِ هر دو محور. یک عضوِ تنها **ذاتاً بی‌همپوشان**
    # است (queue_rr صفِ FIFO دارد) ⇒ concurrency و زنجیرهٔ باخت واقعی، و z
    # بدونِ تورمِ ناشی از ادغام. این حکمِ رسمیِ لایه است؛ خانواده فقط شاهدِ ثبات.
    st_c = member_trades(df, atr, asset, CENTRAL['L'], CENTRAL['f'], warmup)
    central = None
    if st_c is not None and st_c['n'] >= 3:
        tr_c = trades_df(st_c)
        nLc = int((tr_c['direction'] == 'long').sum())
        nSc = int(len(tr_c) - nLc)
        slc = float(np.median(st_c['sl_pip']))
        tpc = float(np.median(st_c['tp_pip']))
        central = dict(tr=tr_c, n_long=nLc, n_short=nSc, sl=slc, tp=tpc)

    # ادغامِ اعضا + **حذفِ همپوشانیِ زمانی بینِ اعضا** (صفِ FIFO بی‌همپوشان).
    # بدونِ این کار، ۹ عضو که هم‌زمان سیگنال می‌دهند concurrency و زنجیرهٔ
    # باختِ مصنوعی می‌سازند و H0/H8 را به‌دلایلِ روش‌شناختی (نه واقعی) رد می‌کنند.
    # این همان قاعدهٔ بی‌همپوشانیِ موتور است که روی کلِ استخرِ ادغام‌شده اعمال
    # می‌شود؛ پس آماره‌ها همان چیزی می‌شوند که یک معامله‌گرِ واقعی تجربه می‌کند.
    fam_all = pd.concat(frames, ignore_index=True).sort_values('entry_bar')
    fam_all = fam_all.reset_index(drop=True)
    eb = fam_all['entry_bar'].values.astype(np.int64)
    xb = fam_all['exit_bar'].values.astype(np.int64)
    keep_no = _fifo_non_overlap(eb, xb)
    fam = fam_all.iloc[keep_no].sort_values('exit_bar').reset_index(drop=True)
    n_before, n_after = len(fam_all), len(fam)
    print(f"    merged {n_before} member-trades → {n_after} non-overlapping "
          f"({100*n_after/n_before:.0f}% kept)", flush=True)
    n_long = int((fam['direction'] == 'long').sum())
    n_short = int(len(fam) - n_long)
    sl_med = float(np.median(fam['sl_pip']))
    tp_med = float(np.median(fam['tp_pip']))
    fam_wr = float((fam['outcome'] == 'win').mean() * 100)
    fam_exp = float(fam['pnl_pip'].mean())
    gw = float(fam.loc[fam['pnl_pip'] > 0, 'pnl_pip'].sum())
    gl = float(-fam.loc[fam['pnl_pip'] <= 0, 'pnl_pip'].sum())
    fam_pf = gw / gl if gl > 0 else 999.0
    rbe = rqs2.breakeven_wr_cost(sl_med, tp_med, 2.0 * c)
    print(f"    FAMILY merged n={len(fam)} (L={n_long} S={n_short}) "
          f"WR={fam_wr:.2f}% exp={fam_exp:+.3f}pip PF={fam_pf:.3f}", flush=True)
    print(f"    bracket SL={sl_med:.1f}pip TP={tp_med:.1f}pip "
          f"rr_eff={tp_med/sl_med:.3f} · robust BE={rbe:.1f}%", flush=True)

    # ---- ۲) مبنای اندازه‌گیری‌شده (null) با همان هندسه ----
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[valid >= warmup]
    rng = np.random.default_rng(SEED)
    print(f"    null pool = {len(valid):,} bars · {n_perm} perms/side", flush=True)
    null = build_null_side(df, asset, valid, GEO_SL_K * atr, n_long, n_short,
                           n_perm, rng, verbose)

    # ---- ۳الف) حکمِ رسمی = عضوِ مرکزیِ پیش‌ثبت‌شده (ذاتاً بی‌همپوشان) ----
    res_central = None
    if central is not None:
        nullc = build_null_side(df, asset, valid, GEO_SL_K * atr,
                                central['n_long'], central['n_short'],
                                n_perm, np.random.default_rng(SEED), verbose=False)
        commonc = dict(sl_pip=central['sl'], tp_pip=central['tp'],
                       bar_time=bar_time, null=nullc, split_bar=split, close=close)
        res_central = rqs2.compute_rqs2(central['tr'], asset,
                                        n_trials=N_CENTRAL, **commonc)
        print(rqs2.format_rqs2(f'{card} CENTRAL ', res_central), flush=True)

    # ---- ۳ب) شاهدِ ثبات = خانوادهٔ بی‌همپوشانِ ادغام‌شده، سه شمارش ----
    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                  null=null, split_bar=split, close=close)
    res = {}
    for tag, nt in (('official', N_OFFICIAL), ('family', N_FAMILY),
                    ('single', N_SINGLE)):
        r = rqs2.compute_rqs2(fam, asset, n_trials=nt, **common)
        res[tag] = r
        print(rqs2.format_rqs2(f'{card} fam-{tag:<5}', r), flush=True)

    # حکمِ لایه: عضوِ مرکزی اگر موجود باشد، وگرنه خانواده
    official_verdict = (res_central['verdict'] if res_central is not None
                        else res['official']['verdict'])

    out = dict(card=card, asset=asset, bars=len(df), cost_pip=c,
               split_bar=split,
               frozen=dict(sl_k=GEO_SL_K, rr=GEO_RR, hold=GEO_HOLD, atr_p=ATR_P),
               central_member=dict(CENTRAL), n_central=N_CENTRAL,
               n_official=N_OFFICIAL, n_family=N_FAMILY,
               family=dict(n=len(fam), wr=fam_wr, exp=fam_exp, pf=fam_pf,
                           sl_pip=sl_med, tp_pip=tp_med, rr_eff=tp_med/sl_med,
                           robust_be=float(rbe), n_long=n_long, n_short=n_short),
               members=member_res,
               verdict=official_verdict)
    if res_central is not None:
        out['rqs2_central'] = {k: res_central[k] for k in
                               ('verdict', 'rqs2_score', 'gates', 'metrics',
                                'notes') if k in res_central}
    for tag in ('official', 'family', 'single'):
        r = res[tag]
        out[f'rqs2_fam_{tag}'] = {k: r[k] for k in
                                  ('verdict', 'rqs2_score', 'gates', 'metrics',
                                   'notes') if k in r}
    _save(card, out)
    return out


def _save(card, out):
    os.makedirs(OUT, exist_ok=True)
    p = f'{OUT}/{card}_rqs2.json'
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(f"    [checkpoint] {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cards', nargs='*', default=None)
    ap.add_argument('--n-perm', type=int, default=200)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    order = a.cards if a.cards else list(CARDS.keys())
    for card in order:
        if card not in CARDS:
            print(f"!! unknown card {card}", flush=True)
            continue
        try:
            run_card(card, n_perm=a.n_perm, verbose=not a.quiet)
        except Exception as e:                                   # noqa: BLE001
            import traceback
            print(f"!! {card} FAILED: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()


if __name__ == '__main__':
    main()
