# -*- coding: utf-8 -*-
"""
S346 — آزمونِ **سطحِ خانواده** (Family-Level Permutation Test)

مسئله‌ای که این آزمون حل می‌کند
--------------------------------
دروازهٔ `H5` (قضیهٔ استراتژیِ کاذب) لایهٔ `C1` را با فاصلهٔ ناچیزِ ۰.۲۶۴σ رد کرد:
`z_obs=4.001` در برابرِ کرانِ `E[max_N]=4.265` برای `N=56,499`.

راهِ **غلط** برای رفعش: پایین آوردنِ آستانه، یا کم‌شمردنِ N. هر دو داده‌کاوی روی
خودِ معیار است.

راهِ **درست**: از بین بردنِ خودِ گزینش. جریمهٔ چندگانگی هزینهٔ *انتخابِ بهترین
عضو* است؛ اگر هیچ عضوی انتخاب نشود، جریمه‌ای هم وجود ندارد.

مشاهدهٔ کلیدی که این را ممکن کرد
----------------------------------
دو کارتِ **مستقل** (D1 و W1) با دو بهینه‌سازیِ **مستقل** روی یک امضای ساختاریِ
یکسان همگرا شدند:

    mode=breakout · side=both · sl_k=1.0 · rr=1.0

و اندازه‌گیریِ توزیعِ این خانواده روی D1 نشان داد:

    بدترینِ ۵۴ عضو = ۵۰.۳۹٪ ·  میانه = ۵۳.۷۲٪ ·  بهترین = ۵۵.۶۳٪
    (مبنای صفرِ D1 ≈ ۵۰.۵٪)

یعنی **کلِ** خانواده بالای مبنا است، نه فقط عضوِ گزینش‌شده. اگر لبه محصولِ
«بهترینِ N» بود، دنبالهٔ پایینیِ توزیع باید زیرِ مبنا می‌افتاد. نمی‌افتد.

طرحِ آزمون
-----------
آمارهٔ آزمون  :  S = میانگینِ WR روی **همهٔ** ۵۴ عضو (هیچ گزینشی نیست)
توزیعِ صفر    :  جای‌گشتِ زمانیِ B بار — برای هر عضو، **همان تعدادِ** ورود با
                 **همان نسبتِ long/short**، در زمان‌های تصادفیِ واجدِ warmup،
                 با همان براکتِ ATR-محورِ محلی، همان hold و همان صفِ
                 بی‌همپوشانی.
p تجربی      :  (۱ + #{S_perm ≥ S_obs}) / (B+1)
چندگانگی     :  **N=1** — خانواده پیش‌ثبت شده و هیچ عضوی برگزیده نشده ⇒
                 کران `E[max_1] = 0.52σ`

چرا جای‌گشت (نه فرمولِ بسته)؟ چون توزیعِ صفرِ «میانگینِ ۵۴ عضوِ به‌شدت همبسته»
فرمِ تحلیلیِ ساده ندارد. جای‌گشت **همهٔ** همبستگی‌های میان‌عضوی را به‌طور خودکار
در توزیعِ صفر می‌آورد.

نکتهٔ ظریفِ طراحی: جای‌گشت **نسبتِ long/short هر عضو را حفظ می‌کند**، چون هدیهٔ
رایگانِ رانش در دو سمت متفاوت است (روی D1: لانگِ تصادفی ۵۲.۷٪، شورتِ تصادفی
۴۵.۵٪). اگر نسبت حفظ نشود، آزمون به‌غلط آسان یا سخت می‌شود.
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from strategies.s346_adaptive_channel import adaptive_channel      # noqa: E402
from strategies.s346_geom import CARDS, event_mask                 # noqa: E402
from strategies.s346_fast import (barrier_outcomes,                # noqa: E402
                                  select_non_overlap, stats)

OUT = 'results/_scan_S346'

# ------------------------------------------------------------------------------
# خانوادهٔ **پیش‌ثبت‌شده** — این تعریف پیش از اجرای آزمون تثبیت شده است.
# منشأ: همگراییِ مستقلِ دو کارتِ D1 و W1 روی همین امضا (ثبت‌شده در
# docs/FINDING_MTF_BASE_QUALITY_LAW.md و results/_scan_S346/XAUUSD-W1_sweep.json).
# ------------------------------------------------------------------------------
FAM_MODE = 'breakout'
FAM_SIDE = 'both'
FAM_SL_K = 1.0            # ⚠️ قیدِ ضدِ تقلبِ #۸: SL و TP مساوی
FAM_RR = 1.0
P_LIST = (13, 21, 34)             # لوکاس/فیبوناچی — نه رند
MULT_LIST = (1.272, 1.618, 2.058)  # نسبت‌های طلایی
ER_LIST = (0.146, 0.236)
HOLD_LIST = (5, 8, 13)


def members():
    """۵۴ عضوِ خانواده. هیچ رتبه‌بندی، هیچ گزینشی."""
    out = []
    for p in P_LIST:
        for mult in MULT_LIST:
            for er in ER_LIST:
                for hold in HOLD_LIST:
                    out.append(dict(mode=FAM_MODE, side=FAM_SIDE, p=p, mult=mult,
                                    er_thr=er, sl_k=FAM_SL_K, rr=FAM_RR,
                                    hold=hold))
    return out


def _queue_stats(df, sig_idx, is_long, atr_at_sig, geom, asset):
    """اجرای یک عضو: سدِ دوطرفه ← صفِ بی‌همپوشانی ← آمار."""
    cfg = se.ASSETS[asset]
    pip = float(cfg['pip'])
    spread = float(cfg['spread_pip'])
    slip = float(cfg.get('slip_pip', 0.0))
    sl_dist = geom['sl_k'] * atr_at_sig
    tp_dist = np.maximum(geom['rr'] * sl_dist, sl_dist)   # ضدِ تقلب: TP ≥ SL
    fo = barrier_outcomes(df, sig_idx, is_long, sl_dist, tp_dist,
                          geom['hold'], pip, spread, slip)
    keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
    st = stats(fo['pnl_pip'][keep], fo['win'][keep], spread + 2 * slip)
    return st


def run(card='XAUUSD-D1', n_perm=300, seed=11, save=True):
    asset, path = CARDS[card]
    df = se.load_data(path)
    n = len(df)
    rng = np.random.default_rng(seed)

    print(f"=== S346 FAMILY-LEVEL TEST :: {card} (bars={n}) ===", flush=True)
    print(f"    pre-registered family: {FAM_MODE}/{FAM_SIDE} "
          f"sl_k={FAM_SL_K} rr={FAM_RR}", flush=True)
    mem = members()
    print(f"    members = {len(mem)}  (NO member is selected)", flush=True)
    print(f"    permutations = {n_perm}", flush=True)

    # کشِ کانال بر حسبِ (p, mult) — عضوها این را به اشتراک می‌گذارند
    ch_cache = {}

    def get_ch(p, mult):
        k = (p, mult)
        if k not in ch_cache:
            ch_cache[k] = adaptive_channel(df, p=p, mult=mult)
        return ch_cache[k]

    # ---------------- گامِ ۱: آمارهٔ مشاهده‌شده روی همهٔ اعضا ----------------
    per_member, prepared = [], []
    for gi, g in enumerate(mem):
        ch = get_ch(g['p'], g['mult'])
        warmup = max(5 * g['p'], 250)
        ls, ss = event_mask(df, ch, g['mode'], g['mult'], g['er_thr'], warmup)
        sig = np.where(ls | ss)[0]
        if len(sig) < 20:
            continue
        is_long = ls[sig]
        atr = ch['atr_a']
        st = _queue_stats(df, sig, is_long, atr[sig], g, asset)
        per_member.append(dict(geom=g, n=st['n'], wr=round(st['wr'], 3),
                               exp=round(st['exp'], 3), pf=round(st['pf'], 3)))
        # آماده‌سازی برای جای‌گشت: تعدادِ ورود، برچسب‌ها، بارهای مجاز
        valid = np.arange(warmup, n - g['hold'] - 2)
        valid = valid[np.isfinite(atr[valid]) & (atr[valid] > 0)]
        prepared.append(dict(geom=g, k=len(sig), labels=is_long.copy(),
                             valid=valid, atr=atr))
        if (gi + 1) % 12 == 0:
            print(f"    ... member {gi+1}/{len(mem)}", flush=True)

    if not per_member:
        print("!!! no viable member", flush=True)
        return None

    wr_obs = float(np.mean([m['wr'] for m in per_member]))
    exp_obs = float(np.mean([m['exp'] for m in per_member]))
    n_tot = int(sum(m['n'] for m in per_member))
    wr_min = min(m['wr'] for m in per_member)
    wr_max = max(m['wr'] for m in per_member)
    print(f"\n  OBSERVED  family mean WR = {wr_obs:.3f}%   "
          f"mean exp = {exp_obs:+.3f}pip   Σn = {n_tot:,}", flush=True)
    print(f"            member WR range = [{wr_min:.2f}, {wr_max:.2f}]",
          flush=True)

    # ---------------- گامِ ۲: توزیعِ صفر با جای‌گشتِ زمانی ----------------
    wr_perm, exp_perm = [], []
    for b in range(n_perm):
        wrs, exps = [], []
        for pr in prepared:
            g = pr['geom']
            v = pr['valid']
            if len(v) <= pr['k']:
                continue
            pick = np.sort(rng.choice(v, size=pr['k'], replace=False))
            lab = rng.permutation(pr['labels'])      # نسبتِ long/short حفظ می‌شود
            st = _queue_stats(df, pick, lab, pr['atr'][pick], g, asset)
            if st['n'] > 0:
                wrs.append(st['wr'])
                exps.append(st['exp'])
        if wrs:
            wr_perm.append(float(np.mean(wrs)))
            exp_perm.append(float(np.mean(exps)))
        if (b + 1) % 25 == 0:
            arr = np.array(wr_perm)
            print(f"    perm {b+1}/{n_perm}  null mean WR = {arr.mean():.3f} "
                  f"sd={arr.std(ddof=1):.3f} max={arr.max():.3f}", flush=True)

    wp = np.array(wr_perm)
    ep = np.array(exp_perm)
    ge_wr = int((wp >= wr_obs).sum())
    ge_exp = int((ep >= exp_obs).sum())
    p_wr = (1.0 + ge_wr) / (len(wp) + 1.0)
    p_exp = (1.0 + ge_exp) / (len(ep) + 1.0)
    z_wr = (wr_obs - wp.mean()) / wp.std(ddof=1) if wp.std(ddof=1) > 0 else 0.0
    z_exp = (exp_obs - ep.mean()) / ep.std(ddof=1) if ep.std(ddof=1) > 0 else 0.0

    print(f"\n  {'='*72}", flush=True)
    print(f"  NULL (time-permuted, {len(wp)} draws):", flush=True)
    print(f"     WR  mean={wp.mean():.3f} sd={wp.std(ddof=1):.3f} "
          f"range=[{wp.min():.3f}, {wp.max():.3f}]", flush=True)
    print(f"     exp mean={ep.mean():+.3f} sd={ep.std(ddof=1):.3f} "
          f"range=[{ep.min():+.3f}, {ep.max():+.3f}]", flush=True)
    print(f"  OBSERVED  WR={wr_obs:.3f}  exp={exp_obs:+.3f}", flush=True)
    print(f"  LIFT      WR={wr_obs - wp.mean():+.3f}pp  ({z_wr:.2f}σ)   "
          f"exp={exp_obs - ep.mean():+.3f}pip  ({z_exp:.2f}σ)", flush=True)
    print(f"  p_emp     WR={p_wr:.5f}  exp={p_exp:.5f}   "
          f"(#draws >= obs: {ge_wr} / {ge_exp})", flush=True)
    # چندگانگی: N=1 چون خانواده پیش‌ثبت شده و عضوی برگزیده نشده
    from engine.rqs2 import expected_max_z
    bound = expected_max_z(1)
    verdict = 'FAMILY EDGE CONFIRMED' if (z_wr > bound and p_wr < 0.05
                                          and z_exp > bound) else 'NOT CONFIRMED'
    print(f"  N=1 (pre-registered family, no member selected) ⇒ "
          f"luck bound = {bound:.3f}σ", flush=True)
    print(f"  ⇒ {verdict}", flush=True)
    print(f"  {'='*72}", flush=True)

    rec = dict(card=card, family=dict(mode=FAM_MODE, side=FAM_SIDE,
                                      sl_k=FAM_SL_K, rr=FAM_RR,
                                      p=list(P_LIST), mult=list(MULT_LIST),
                                      er=list(ER_LIST), hold=list(HOLD_LIST)),
               n_members=len(per_member), n_trades_total=n_tot,
               wr_obs=round(wr_obs, 4), exp_obs=round(exp_obs, 4),
               wr_member_min=wr_min, wr_member_max=wr_max,
               n_perm=len(wp),
               null_wr_mean=round(float(wp.mean()), 4),
               null_wr_sd=round(float(wp.std(ddof=1)), 4),
               null_wr_max=round(float(wp.max()), 4),
               null_exp_mean=round(float(ep.mean()), 4),
               null_exp_sd=round(float(ep.std(ddof=1)), 4),
               lift_wr=round(wr_obs - float(wp.mean()), 4),
               lift_exp=round(exp_obs - float(ep.mean()), 4),
               z_wr=round(float(z_wr), 4), z_exp=round(float(z_exp), 4),
               p_emp_wr=round(p_wr, 6), p_emp_exp=round(p_exp, 6),
               luck_bound_n1=round(float(bound), 4), verdict=verdict,
               members=per_member)
    if save:
        os.makedirs(OUT, exist_ok=True)
        with open(f"{OUT}/{card}_family.json", 'w') as fh:
            json.dump(rec, fh, default=float)
        print(f"  saved -> {OUT}/{card}_family.json", flush=True)
    return rec


if __name__ == '__main__':
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-D1'
    nb = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    run(card, n_perm=nb)
