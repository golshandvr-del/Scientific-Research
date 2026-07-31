# -*- coding: utf-8 -*-
"""
S351-VOTE — «تأییدِ چند-مقیاسیِ شکستِ ساختار» (Multi-Scale Confirmation)
================================================================================
فرضیهٔ علمیِ پیش‌ثبت‌شده (پیش از دیدنِ هر نتیجه):
--------------------------------------------------------------------------------
    ۹ عضوِ خانوادهٔ LPSB نُه **مقیاسِ متفاوتِ یک قانونِ ساختاریِ یکسان**‌اند:
    سه نیم‌پنجرهٔ پیوت (L∈{5,8,13}) × سه شدتِ تأییدِ شکست (f∈{0.236,0.33,0.5}).

    اگر یک شکستِ ساختاری فقط در یک مقیاس دیده شود، احتمالاً نویزِ همان مقیاس
    است. اگر در چند مقیاس **هم‌زمان** دیده شود، آن شکست **مقیاس-ناوابسته**
    (scale-invariant) است — یعنی امضای واقعیِ فراکتالی، نه آرتیفکتِ پنجره.

    پس شمارِ رأیِ هم‌زمان `k` باید یک **سنجهٔ کیفیتِ ذاتی** باشد و با افزایشِ
    آن، lift باید بالا رود.

⛔ چرا این «برشِ FIFOِ خانواده» نیست (تفاوتِ حیاتی با نسخهٔ پیشین):
--------------------------------------------------------------------------------
    در `s351_verdict.py` معاملاتِ ۹ عضو ادغام و سپس با صفِ FIFO بی‌همپوشان شد.
    آن کار **رأیِ جمعی را دور ریخت**: FIFO اولین سیگنالِ هر خوشه را نگه می‌دارد،
    نه باکیفیت‌ترین را. اندازه‌گیریِ XAUUSD-D1 این را قطعی نشان داد:

        ادغامِ خام (683 معاملهٔ همپوشان)      → WR = 56.4٪   (رأی حاضر است)
        برشِ FIFO   (166 معاملهٔ بی‌همپوشان) → WR = 49.4٪   (رأی دور ریخته شد)
        عضوِ مرکزیِ تنها (74 معامله)          → WR = 59.5٪

    این‌جا رأی **به‌عنوان فیلترِ ورود** به کار می‌رود، نه به‌عنوان مسیرِ تکثیرِ
    معامله: در هر کندل رأی‌ها شمرده می‌شوند و **یک** معامله باز می‌شود.
    پس concurrency ذاتاً ۱ می‌ماند (H0 سالم) و n مصنوعی متورم نمی‌شود.

📐 هدفِ کمّیِ محاسبه‌شده (چرا این مسیر انتخاب شد):
--------------------------------------------------------------------------------
    z ≈ lift·√n / 49.5  ⇒  برای H3 (lift≥4.0pp و z≥3.0σ) لازم است lift·√n ≥ 148.
        XAUUSD-D1: lift خام = +13.9pp عالی است، فقط n=74 کم است ⇒ n ≥ 112 کافی است.
        XAUUSD-H1: n=1937 عالی است، فقط lift=+2.3pp کم است ⇒ lift ≥ 4.5pp کافی است.

    توزیعِ رأیِ اندازه‌گیری‌شده نشان داد هر دو در دسترس‌اند:
        D1: k≥2 → 231 سیگنال  (۳ برابرِ عضوِ مرکزی)
        H1: k≥4 → 1748 سیگنال ، k≥5 → 1060 سیگنال
    یعنی رأی همان «نقطهٔ شیرینِ» lift↔n را می‌سازد که آستانهٔ رژیم نساخت
    (آستانهٔ سخت n را می‌کُشت، آستانهٔ شُل lift را).

⛔ سپرهای ضدِ تقلب:
--------------------------------------------------------------------------------
    ۱) هندسه **همان منجمدِ S351** است؛ هیچ پارامترِ براکتی لمس نمی‌شود.
    ۲) `k` فقط روی ۶۰٪ پنجرهٔ اکتشاف با **t-آمارهٔ امیدِ ریاضی** تنظیم می‌شود؛
       حکم روی کلِ سری با `split_bar` در ۶۰٪ صادر می‌شود (H7 خودش می‌سنجد).
    ۳) شمارشِ چندگانگیِ رسمی از پیش قفل است: |k| × کارت‌ها = ۵ × ۱۵ = ۷۵.
    ۴) مدلِ صفرِ رسمی روی **استخرِ رأی‌دار** ساخته می‌شود (نه کلِ کندل‌ها) —
       سخت‌گیرانه‌ترین خطِ مبنا: lift فقط مهارتِ **جهت‌دهی** را می‌سنجد و
       اثرِ «این کندل‌ها خاص‌اند» را به مدلِ صفر واگذار می‌کند.
    ۵) `rr = 1.618 > 1` ⇒ TP > SL ساختاراً ⇒ سپرِ اشتباهِ #۸.
    ۶) دقیقاً **یک** قاعده نسبت به S351 خام تغییر می‌کند (افزودنِ آستانهٔ رأی)
       تا هر تفاوتِ نتیجه قابلِ انتساب باشد — درسِ آزمونِ کنترل‌شدهٔ S348.
"""
import os
import sys
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies.s348_rr_sweep import (queue_rr, trades_df,          # noqa: E402
                                      cost_pip, SPLIT_FRAC)
from strategies.s351_lpsb import (atr_series, lpsb_signals, members,  # noqa: E402
                                  CARDS, GEO_SL_K, GEO_RR, GEO_HOLD,
                                  ATR_P, SEED)
from strategies.s351_verdict import build_null_side                 # noqa: E402

OUT = 'results/_scan_S351'

# ----------------------- فضای پیش‌ثبت‌شدهٔ آستانهٔ رأی -----------------------
# k=1 حذف شد چون عیناً «اجتماعِ اعضا» است و هیچ تأییدی نمی‌خواهد.
# k=7..9 حذف شد چون اندازه‌گیریِ توزیع نشان داد روی D1 تنها ۳..۸ سیگنال
# می‌ماند ⇒ زیرِ کفِ نمونهٔ H0. پس فضا از پیش {2..6} است.
VOTE_K = (2, 3, 4, 5, 6)
N_OFFICIAL = len(VOTE_K) * len(CARDS)          # = 5 × 15 = 75  ← حکمِ رسمی
WARMUP = max(4 * (2 * 13 + 1), 250)


def vote_series(df, warmup=WARMUP):
    """شمارِ رأیِ لانگ/شورت در هر کندل، روی هر ۹ مقیاسِ خانواده."""
    n = len(df)
    vl = np.zeros(n, dtype=np.int16)
    vs = np.zeros(n, dtype=np.int16)
    for m in members():
        ls, ss, _ = lpsb_signals(df, m['L'], m['f'], warmup=warmup)
        vl += ls.astype(np.int16)
        vs += ss.astype(np.int16)
    return vl, vs


def vote_signal(vl, vs, k):
    """
    سیگنالِ تأییدِ چند-مقیاسی.

    کندلی که هم‌زمان رأیِ لانگ و شورت دارد **حذف** می‌شود: ساختار در آن کندل
    متناقض است و انتخابِ یک سمت، تصمیمِ دلبخواهی می‌بود.
    """
    long_ok = (vl >= k) & (vs == 0)
    short_ok = (vs >= k) & (vl == 0)
    return long_ok, short_ok


def _eval(df, atr, asset, is_long_mask, sel_mask, lo, hi):
    sel = sel_mask.copy()
    sel[:max(lo, WARMUP)] = False
    if hi is not None:
        sel[hi:] = False
    sig = np.where(sel)[0]
    if len(sig) < 10:
        return None
    st = queue_rr(df, sig, is_long_mask[sig], GEO_SL_K * atr[sig],
                  asset, GEO_HOLD, GEO_RR)
    if st is None or st['n'] < 10:
        return None
    return st


def run_card(card, n_perm=200, verbose=True):
    asset, path = CARDS[card]
    if not os.path.exists(path):
        _save(card, dict(card=card, verdict='NO_DATA'))
        return
    df = se.load_data(path)
    n = len(df)
    atr = atr_series(df)
    close = df['close'].values.astype('float64')
    bar_time = df['dt'].values if 'dt' in df.columns else None
    split = int(n * SPLIT_FRAC)
    c = cost_pip(asset)

    print(f"\n{'='*92}\n=== S351-VOTE :: {card} (bars={n:,}) ===", flush=True)
    print(f"    FROZEN geom sl_k={GEO_SL_K} rr={GEO_RR} hold={GEO_HOLD} "
          f"atr_p={ATR_P} · cost={c:.2f}pip · N_official={N_OFFICIAL}",
          flush=True)

    if n < WARMUP + 100:
        _save(card, dict(card=card, asset=asset, bars=n, verdict='TOO_SHORT'))
        return

    vl, vs = vote_series(df)
    finite = np.isfinite(atr) & (atr > 0)

    # ---------------- مرحلهٔ اکتشاف: تنظیمِ k فقط روی ۶۰٪ نخست ----------------
    grid = []
    best = None
    for k in VOTE_K:
        lo_m, sh_m = vote_signal(vl, vs, k)
        sel = (lo_m | sh_m) & finite
        st = _eval(df, atr, asset, lo_m, sel, WARMUP, split)
        row = dict(k=k, n_sig=int(sel[WARMUP:split].sum()))
        if st is None:
            row.update(n=0, wr=None, exp=None, pf=None, t=None)
            grid.append(row)
            continue
        sd = float(np.std(st['pnl'], ddof=1)) if st['n'] > 1 else 0.0
        t = (st['exp'] * np.sqrt(st['n']) / sd) if sd > 0 else 0.0
        row.update(n=int(st['n']), wr=float(st['wr']), exp=float(st['exp']),
                   pf=float(st['pf']), t=float(t))
        grid.append(row)
        if verbose:
            print(f"    [disc] k={k}: n={st['n']:5d} WR={st['wr']:6.2f}% "
                  f"exp={st['exp']:+8.3f} PF={st['pf']:.3f} t={t:+5.2f}",
                  flush=True)
        if st['exp'] > 0 and sd > 0 and (best is None or t > best['t']):
            best = dict(k=k, t=float(t), n_disc=int(st['n']),
                        wr_disc=float(st['wr']), exp_disc=float(st['exp']))

    if best is None:
        _save(card, dict(card=card, asset=asset, bars=n, grid=grid,
                         verdict='NO_PROFITABLE_K'))
        return
    k = best['k']
    print(f"    LOCKED k={k} (discovery-only t={best['t']:+.2f}, "
          f"n_disc={best['n_disc']}, exp_disc={best['exp_disc']:+.3f})",
          flush=True)

    # ---------------- داوریِ کامل روی کلِ سری با همان k ----------------
    lo_m, sh_m = vote_signal(vl, vs, k)
    sel = (lo_m | sh_m) & finite
    sel[:WARMUP] = False
    sig = np.where(sel)[0]
    st = queue_rr(df, sig, lo_m[sig], GEO_SL_K * atr[sig], asset,
                  GEO_HOLD, GEO_RR)
    if st is None or st['n'] < 5:
        _save(card, dict(card=card, asset=asset, bars=n, grid=grid,
                         verdict='NO_TRADES'))
        return
    tr = trades_df(st)
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    rbe = rqs2.breakeven_wr_cost(sl_med, tp_med, 2.0 * c)
    print(f"    REALISED n={st['n']} (L={nL} S={nS}) WR={st['wr']:.2f}% "
          f"exp={st['exp']:+.3f}pip PF={st['pf']:.3f} · robust BE={rbe:.1f}%",
          flush=True)

    # مدلِ صفرِ رسمی: استخرِ **رأی‌دار** (سخت‌گیرانه‌ترین خطِ مبنا)
    voted = np.where(((vl >= k) | (vs >= k)) & finite)[0]
    voted = voted[voted >= WARMUP]
    print(f"    null pool = {len(voted):,} voted bars · {n_perm} perms/side",
          flush=True)
    null = build_null_side(df, asset, voted, GEO_SL_K * atr, nL, nS,
                           n_perm, np.random.default_rng(SEED), verbose)

    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                  null=null, split_bar=split, close=close)
    res = {}
    for tag, nt in (('official', N_OFFICIAL), ('single', 1)):
        r = rqs2.compute_rqs2(tr, asset, n_trials=nt, **common)
        res[tag] = r
        print(rqs2.format_rqs2(f'{card} {tag:<8}', r), flush=True)

    out = dict(card=card, asset=asset, bars=n, cost_pip=c, split_bar=split,
               rule='multi-scale vote confirmation on LPSB family',
               vote_k=k, vote_space=list(VOTE_K), n_official=N_OFFICIAL,
               frozen=dict(sl_k=GEO_SL_K, rr=GEO_RR, hold=GEO_HOLD,
                           atr_p=ATR_P),
               discovery=best, grid=grid,
               realised=dict(n=int(st['n']), wr=float(st['wr']),
                             exp=float(st['exp']), pf=float(st['pf']),
                             sl_pip=sl_med, tp_pip=tp_med,
                             rr_eff=tp_med / sl_med, robust_be=float(rbe),
                             n_long=nL, n_short=nS),
               verdict=res['official']['verdict'])
    for tag in ('official', 'single'):
        r = res[tag]
        out[f'rqs2_{tag}'] = {kk: r[kk] for kk in
                              ('verdict', 'rqs2_score', 'gates', 'metrics',
                               'notes') if kk in r}
    _save(card, out)
    return out


def _save(card, out):
    os.makedirs(OUT, exist_ok=True)
    p = f'{OUT}/{card}_vote.json'
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
