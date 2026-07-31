# -*- coding: utf-8 -*-
"""S346 — بازآزمونِ **hold-out تمیز (پروتکل C)** زیرِ معیارِ اصلاح‌شدهٔ RQS2 v2.4.

انگیزه
------
حسابرسی نشان داد لبهٔ S346 روی XAUUSD تنها لبه‌ای است که یک شاهدِ OOS **تمیز**
دارد (انتقالِ بین‌کارتی: H1/H4/M30/W1 = TRANSFER CONFIRMED؛ همهٔ EUR = FAILED).
اما رکوردِ اصلیِ D1 دو مشکل داشت که مانعِ ACCEPTِ صادقانه بود:
  ۱) `h7_contaminated=true` — دو فیلترِ C1 روی همان پنجرهٔ holdout انتخاب شده
     بودند ⇒ holdoutِ آن سری واقعی نبود.
  ۲) `perm_k=300 < 500` — زیرِ کفِ همگراییِ v2.4 ⇒ H3 اکنون UNKNOWN می‌شود.

این اسکریپت یک **پروتکل C واقعی** اجرا می‌کند تا هر دو مشکل رفع شود:

  • **نیمهٔ اول (کشف، ۶۰٪):** آستانهٔ کارآییِ ورود `er_thr` و آستانه‌های دو فیلترِ
    رژیمی **فقط** روی نیمهٔ اول تنظیم می‌شوند. این تنها جایی است که به داده نگاه
    می‌کنیم تا پیکربندی را انتخاب کنیم.
  • **قفل:** پیکربندیِ برنده در JSON ثبت و در یک commitِ جداگانه پیش‌ثبت می‌شود
    (مُهرِ زمانیِ git). این فایل هرگز پس از دیدنِ نیمهٔ دوم تغییر نمی‌کند.
  • **نیمهٔ دوم (تستِ یک‌باره، ۴۰٪):** دقیقاً همان پیکربندیِ قفل‌شده **یک بار**
    روی نیمهٔ دومِ دست‌نخورده اجرا و با `compute_rqs2` (v2.4) داوری می‌شود.
    `n_trials=1` (پروتکل C: روی دادهٔ دیده‌نشده تعدادِ فرضیه واقعاً ۱ است).
    نول با `K=500` ساخته می‌شود تا کفِ همگراییِ v2.4 برآورده شود.

هندسهٔ پایهٔ S346 (verbatim از s346_transfer.REF_GEOM):
    breakout channel، p=13، mult=2.058، RR=1، sl_k=1.0، hold=5، tp_mode=atr
دو فیلترِ رژیمیِ پایه (verbatim از s346_transfer.REF_FILTERS):
    cg_fib_13 ≥ thr1 ,  std_fib_55 ≤ thr2
اما آستانه‌ها اینجا **بازکشف** می‌شوند تا آلودگیِ holdout حذف شود.

اجرا: python3 strategies/s346_holdout_c.py
خروجی: results/_scan_S346/holdout_c_XAUUSD-D1.json (+ لاگ)
"""
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se
from engine import rqs2 as R2
from engine import indicator_bank as ib
from strategies.s346_adaptive_channel import adaptive_channel
from strategies.s346_geom import event_mask

OUT = 'results/_scan_S346'
CARD = 'XAUUSD-D1'
PATH = 'data/XAUUSD_D1.csv'
ASSET = 'XAUUSD'

# هندسهٔ پایه — verbatim، تغییرناپذیر
BASE = dict(mode='breakout', p=13, mult=2.058, sl_k=1.0, rr=1.0, hold=5)
WARMUP = max(5 * BASE['p'], 250)

# شبکهٔ کوچکِ کشف (فقط روی نیمهٔ اول) — پیش‌ثبت‌شده، N=len(grid)
ER_GRID = [0.10, 0.146, 0.20, 0.25]                  # آستانهٔ کارآییِ ورود
CG_Q = [0.20, 0.30, 0.40]                            # چارکِ آستانهٔ cg_fib_13 (ge)
STD_Q = [0.60, 0.70, 0.80]                           # چارکِ آستانهٔ std_fib_55 (le)
# ⇒ فضای کشف = 4×3×3 = 36 ترکیب. این N_effِ صادقانهٔ نیمهٔ اول است.


def build_signal(df, er_thr, cg_thr, std_thr):
    """سیگنالِ breakout + دو فیلترِ رژیمی. خروجی: ls, ss, sl_pip, tp_pip."""
    ch = adaptive_channel(df, p=BASE['p'], mult=BASE['mult'])
    ls, ss = event_mask(df, ch, BASE['mode'], BASE['mult'], er_thr, WARMUP)

    cg = ib.compute('cg_fib_13', df).values
    std = ib.compute('std_fib_55', df).values
    gate = np.isfinite(cg) & np.isfinite(std) & (cg >= cg_thr) & (std <= std_thr)
    ls = ls & gate
    ss = ss & gate

    pip = se.ASSETS[ASSET]['pip']
    sl_price = BASE['sl_k'] * ch['atr_a']
    tp_price = BASE['rr'] * sl_price
    with np.errstate(invalid='ignore'):
        sl_pip = np.nan_to_num(sl_price / pip, nan=0.0)
        tp_pip = np.nan_to_num(tp_price / pip, nan=0.0)
    tp_pip = np.maximum(tp_pip, sl_pip)   # قیدِ ضدِ تقلبِ #۸
    return ls, ss, sl_pip, tp_pip


def net_of(df, ls, ss, sl_pip, tp_pip):
    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, ASSET,
                            max_hold=BASE['hold'], allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None, 0.0, 0.0
    n = len(tr)
    wins = int((tr['pnl_pip'] > 0).sum())
    wr = wins / n * 100.0
    return tr, wr, n


def build_null_perm(df, ls, ss, sl_pip, tp_pip, K=500, seed=12345):
    """نولِ جای‌گشتِ زمانیِ کانونی برای این لایه: همان تعدادِ ورود، برچسبِ جهت/زمان
    جای‌گشت می‌شود. خروجیِ سازگار با blend_null: dict دو-سمتی با perm_k>=K.
    ما یک نولِ ساده و همگرا می‌سازیم: WRِ جای‌گشت‌ها را جمع می‌کنیم و
    mean/sd/max/k را می‌دهیم. ساختار مطابقِ چیزی که null_from_s346 تولید می‌کند.
    """
    sig_idx = np.where(ls | ss)[0]
    n = len(sig_idx)
    if n < 30:
        return None
    c = df['close'].values.astype(np.float64)
    # بازدهِ رو به جلوی hold کندلی در هر سیگنال (برای برچسبِ جهتِ تصادفی)
    rng = np.random.default_rng(seed)
    # نتیجهٔ واقعیِ هر سیگنال با جهتِ long فرضی: علامتِ تغییرِ قیمت طیِ hold
    fwd = np.full(n, np.nan)
    for j, ei in enumerate(sig_idx):
        k = min(ei + BASE['hold'], len(c) - 1)
        fwd[j] = c[k] - c[ei]
    fwd = fwd[np.isfinite(fwd)]
    m = len(fwd)
    if m < 30:
        return None
    base_wins = fwd > 0     # اگر همه long بودند
    wrs = []
    for _ in range(K):
        signs = rng.integers(0, 2, size=m).astype(bool)   # جهتِ تصادفی
        # win اگر جهت با علامتِ حرکت هم‌سو باشد
        w = np.where(signs, base_wins, ~base_wins)
        wrs.append(w.mean() * 100.0)
    wrs = np.array(wrs)
    ref = float(np.mean(wrs))
    return {
        'long':  dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs)),
                      perm_max=float(np.max(wrs)), perm_k=K),
        'short': dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs)),
                      perm_max=float(np.max(wrs)), perm_k=K),
    }


def main():
    print("=" * 70)
    print("S346 hold-out protocol C  ·  RQS2 v2.4  ·  XAUUSD-D1")
    print("=" * 70)
    df = se.load_data(PATH)
    N = len(df)
    split = int(N * 0.60)
    df1 = df.iloc[:split].reset_index(drop=True)    # نیمهٔ کشف
    df2 = df.iloc[split:].reset_index(drop=True)    # نیمهٔ تستِ دست‌نخورده
    print(f"bars total={N}  discovery(first 60%)={len(df1)}  holdout(last 40%)={len(df2)}")

    # آستانه‌های چارکی را روی نیمهٔ اول به عدد تبدیل می‌کنیم
    cg1 = ib.compute('cg_fib_13', df1).values
    std1 = ib.compute('std_fib_55', df1).values
    cg1v = cg1[np.isfinite(cg1)]
    std1v = std1[np.isfinite(std1)]

    # ---------- مرحلهٔ کشف: فقط نیمهٔ اول ----------
    best = None
    n_eval = 0
    for er in ER_GRID:
        for cq in CG_Q:
            for sq in STD_Q:
                cg_thr = float(np.quantile(cg1v, cq))
                std_thr = float(np.quantile(std1v, sq))
                ls, ss, sl, tp = build_signal(df1, er, cg_thr, std_thr)
                tr, wr, n = net_of(df1, ls, ss, sl, tp)
                n_eval += 1
                if tr is None or n < 40:
                    continue
                net = float(tr['pnl_pip'].sum())
                score = wr + 0.001 * net    # معیارِ کشف: WR با شکنندهٔ net
                if best is None or score > best['score']:
                    best = dict(score=score, er=er, cq=cq, sq=sq,
                                cg_thr=cg_thr, std_thr=std_thr,
                                is_wr=round(wr, 2), is_n=n, is_net=round(net, 1))
    if best is None:
        print("DISCOVERY FAILED: no config produced >=40 trades on first half")
        return
    print(f"\ndiscovery evaluated {n_eval} configs (N_eff grid = {n_eval})")
    print(f"LOCKED config: er_thr={best['er']} cg_q={best['cq']} std_q={best['sq']}")
    print(f"   thresholds: cg_fib_13>={best['cg_thr']:.5f}  std_fib_55<={best['std_thr']:.5f}")
    print(f"   in-sample(first half): WR={best['is_wr']}%  n={best['is_n']}  net={best['is_net']}")

    result = dict(card=CARD, protocol='C_holdout_v2.4', base=BASE,
                  discovery_grid_N=n_eval, locked=best)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/holdout_c_XAUUSD-D1.json', 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nSAVED locked config -> {OUT}/holdout_c_XAUUSD-D1.json")
    print("NEXT: commit this file (pre-registration), THEN run the holdout test.")


if __name__ == '__main__':
    main()
