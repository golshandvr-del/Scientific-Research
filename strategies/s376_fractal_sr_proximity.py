# -*- coding: utf-8 -*-
"""
S376 — «فیلترِ نزدیکیِ ساختاری (Fractal-SR Proximity)» روی لایهٔ S333
================================================================================
پیش‌ثبت: results/S376_PREREG_fractal_sr_proximity_filter.md  (commit شده پیش از این فایل)

منبع
----
ششمین موردِ `Telegram-Resource` — `000_3_Level_ZZ_Semafor_TRO_MODIFIED_VERSION.ex4`
اندیکاتورِ `3-Level ZZ Semafor` (اثرِ TRO): سه ZigZag با عمق‌های `Period1/2/3`
هم‌زمان؛ سطحِ عمیق‌تر = سقف/کفِ **ساختاریِ ماژور**.

چرا این فیلتر از جنسِ متفاوت است
--------------------------------
مسیرِ نجاتِ `S323` (`strategies/s358_s323_h5_rescue.py:123-135`) **۸۸ آزمون** با
۱۱ سنجه خرج کرد:
    chop · r2 · corr_t · hurst · entropy · fisher · cmo · trix · natr · kurt · ulcer
هر ۱۱ تا **آمارهٔ حالتِ بازار**اند. **صفر** سنجهٔ **موقعیتی/ساختاری**.
همه می‌پرسند «حالتِ بازار چیست؟»؛ هیچ‌کدام نمی‌پرسد «قیمت **کجای ساختار** است؟»

و گزارشِ `S323` قانونِ شکست را استخراج کرده بود:
    «هیچ‌کدام از ۱۱ سنجه **باختِ فاجعه‌بار** را تشخیص نداد؛ فقط کیفیت را رتبه‌بندی
     کرد… مسیرِ فیلتر باید با تشخیصِ باختِ فاجعه‌بار شروع شود.»

فرضیهٔ علّی: در یک لایهٔ **پولبک**، باختِ فاجعه‌بار یک رویدادِ **مکانی** است —
پولبکی که به حمایتِ ساختاریِ واقعی نرسیده و در «هوا» خریداری شده. آمارهٔ حالت
این را نمی‌بیند چون در همان رژیم هم ورودِ خوب هست و هم بد.

⚠️ قفلِ علّیت (بندِ ۱ پیش‌ثبت) — درسِ گران‌قیمتِ S375
------------------------------------------------------
ZigZag/Semafor ذاتاً **repaint** دارد. در S375 همین نشست، فیلتری که «بعداً تأیید
می‌شود» را نگه می‌داشت `meanR=+0.4408` نشان داد ولی نسخهٔ علّی‌اش `−0.2860` بود.
پس اینجا پیوت **فقط** وقتی موجود است که `K` کندلِ کاملْ‌شده بعد از آن، آن را
نشکسته باشند:

    pivot_low در بارِ t  ⟺  low[t] = min(low[t-K … t+K])
    زودترین زمانِ دسترسی = t + K   (چون کندلِ t+K باید بسته شده باشد)
    تصمیمِ بارِ i فقط پیوت‌هایی را می‌بیند که  t + K ≤ i

این **دقیقاً** همان چیزی است که `.ex4.md` منبع خواست: «نسخهٔ non-repaint».
"""
import sys, os, json, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np                                                       # noqa: E402
import pandas as pd                                                      # noqa: E402
from engine import scalp_engine as SE                                     # noqa: E402
from engine import indicator_bank as ib                                   # noqa: E402
from engine.rqs2 import compute_rqs2, expected_max_z                      # noqa: E402
from strategies.s333_s79_pullback_revival import (                        # noqa: E402
    core_signal_confirmed, BEST_CFG, _reg_asset,
)

OUT = "results/_scan_S376"

# ⛔ دفترِ چندگانگی — پیش‌ثبت §۵، تثبیت‌شده پیش از وجودِ هر نتیجه.
#    ۱۱۷ (پایانِ S375) + ۳۶ درجهٔ آزادی (۳ K × ۳ عمق × ۴ چندک) = ۱۵۳
N_TRIALS = 153
BOUND = expected_max_z(N_TRIALS)          # = 2.6768 — محاسبه‌شده پیش از هر اجرا

N_PERM = 500       # ⚠️ ۵۰۰ و نه کمتر: موتور زیرِ ۵۰۰ حکمِ H3 را UNKNOWN می‌کند
                   #    (sd جای‌گشت همگرا نشده ⇒ z وابسته به بذر). درسِ S375.

# ── شبکهٔ پیش‌ثبت‌شده (۳۶ سلول). هیچ سلولی بعداً افزوده نمی‌شود. ──────────────
#  K = تعدادِ کندلِ تأییدِ پیوت در هر سمت. اعدادِ غیررند از دنبالهٔ لوکاس/فیبوناچی
#      گرفته شده‌اند (پرهیز از اشتباه #۷: نه ۵/۱۰/۲۰).
K_GRID = (3, 4, 7)
#  DEPTH = عمقِ Semafor — چند پیوتِ اخیر برای ساختِ «سطحِ ساختاری» استفاده شود.
#      متناظرِ Period1/2/3 منبع.
DEPTH_GRID = (1, 2, 3)
#  چندک‌های آستانهٔ نزدیکی — از توزیعِ **خودِ فاصله‌ها روی کندل‌های سیگنال**
#      ساخته می‌شوند، نه اعدادِ رند (بندِ ۴ قفل).
Q_GRID = (0.30, 0.45, 0.60, 0.75)

MIN_TRADES = 20          # کفِ گزارش‌پذیری؛ زیرِ آن سلول بی‌معناست

TF_ALL = ('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1')


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) پیوتِ فراکتالیِ **علّی** — هستهٔ non-repaint از Semafor
# ═══════════════════════════════════════════════════════════════════════════
def causal_pivot_lows(low, K):
    """آرایهٔ `avail_at[i] = قیمتِ آخرین پیوت-کفِ **قابلِ دانستن** در بارِ i`.

    پیوت-کف در بارِ t: `low[t]` کمینهٔ پنجرهٔ `[t-K, t+K]` باشد.
    زودترین زمانِ دانستنِ آن `t+K` است (کندلِ `t+K` باید بسته باشد).
    پس در بارِ i فقط پیوت‌هایی دیده می‌شوند که `t+K <= i`.

    خروجی: (last_pivot_price, last_pivot_bar) — هر دو با NaN/-1 پیش از وجود.
    """
    n = len(low)
    is_piv = np.zeros(n, bool)
    # پنجرهٔ متقارنِ 2K+1 — پیوتِ سختِ فراکتالی (Williams-style اما با K دلخواه)
    for t in range(K, n - K):
        w = low[t - K:t + K + 1]
        if low[t] == w.min():
            is_piv[t] = True

    price = np.full(n, np.nan)
    bar = np.full(n, -1, dtype=np.int64)
    cur_p, cur_b = np.nan, -1
    for i in range(n):
        # پیوتی که در بارِ `i - K` رخ داده، حالا (بارِ i) تازه قابلِ دانستن است
        t = i - K
        if t >= 0 and is_piv[t]:
            cur_p, cur_b = low[t], t
        price[i] = cur_p
        bar[i] = cur_b
    return price, bar, is_piv


def causal_pivot_stack(low, K, depth):
    """سطحِ ساختاری با **عمقِ** `depth`: قیمتِ `depth`-اُمین پیوتِ اخیرِ قابلِ دانستن.

    `depth=1` ⇒ آخرین پیوت (Semafor سطحِ ۱، نوسانِ کوچک)
    `depth=3` ⇒ سه پیوت عقب‌تر (ساختارِ ماژور، Semafor سطحِ ۳)
    این ترجمهٔ **بدونِ repaint** از سه‌سطحیِ منبع است: به‌جای سه ZigZagِ متفاوت،
    یک پیوتِ تأییدشده با فاصلهٔ ساختاریِ متفاوت.
    """
    n = len(low)
    is_piv = np.zeros(n, bool)
    for t in range(K, n - K):
        if low[t] == low[t - K:t + K + 1].min():
            is_piv[t] = True

    price = np.full(n, np.nan)
    hist = []            # پیوت‌های قابلِ دانستن، به‌ترتیبِ زمان
    for i in range(n):
        t = i - K
        if t >= 0 and is_piv[t]:
            hist.append(low[t])
        if len(hist) >= depth:
            price[i] = hist[-depth]
        # else: NaN — ساختارِ کافی هنوز شکل نگرفته
    return price


# ═══════════════════════════════════════════════════════════════════════════
#  ۲) بازوی پایه = لایهٔ S333 **verbatim**
# ═══════════════════════════════════════════════════════════════════════════
def build_s333_layer(df, cfg):
    """عیناً `build_layer` از مولدِ S333 — بازتولید، نه بازنویسی.

    (کپی نمی‌کنم؛ همان توابعِ import‌شده را صدا می‌زنم تا دو بازو نتوانند واگرا شوند.)
    """
    base = core_signal_confirmed(df, cfg['ef'], cfg['es'], cfg['rp'], cfg['rth'],
                                 confirm=cfg.get('confirm', 'rsi_turn'))
    hu = ib.compute('hurst', df).values
    sig = base & (np.nan_to_num(hu, nan=-1.0) > cfg['hurst'])
    if cfg.get('er') is not None:
        er = ib.compute('er_lucas_29', df).values
        sig = sig & (np.nan_to_num(er, nan=-1.0) > cfg['er'])
    if cfg.get('r2') is not None:
        r2 = ib.compute('r2_fib_89', df).values
        sig = sig & (np.nan_to_num(r2, nan=-1.0) > cfg['r2'])
    return np.nan_to_num(sig).astype(bool)


# ═══════════════════════════════════════════════════════════════════════════
#  ۳) فاصلهٔ ساختاری — سنجهٔ **موقعیتی** (نه حالتی)
# ═══════════════════════════════════════════════════════════════════════════
def structural_distance(df, K, depth, pip):
    """`dist[i]` = فاصلهٔ close تا سطحِ ساختاریِ زیرین، **نرمال‌شده با ATR**.

    نرمال‌سازی با ATR لازم است چون فاصلهٔ خام با نوسان مقیاس می‌شود و بین
    تایم‌فریم‌ها/ابزارها قابلِ مقایسه نیست (پرهیز از اشتباهِ #۶: آستانهٔ یکسان
    برای همهٔ TFها). واحد: «چند ATR بالای حمایتِ ساختاری».

    مقدارِ کوچک ⇒ قیمت **نزدیکِ** حمایتِ ساختاری (ورودِ باکیفیت طبقِ فرضیه)
    مقدارِ بزرگ ⇒ قیمت در «هوا» (باختِ فاجعه‌بارِ فرضی)
    """
    c = df['close'].values.astype(float)
    lo = df['low'].values.astype(float)
    piv = causal_pivot_stack(lo, K, depth)
    # `atr_fib_21` و نه `atr`: بانکِ ۴۰۱-اندیکاتوریِ پروژه عمداً هیچ ATRِ با دورهٔ
    # رند ندارد؛ همه دوره‌های فیبوناچی‌اند (اشتباهِ رایج #۷). ۲۱ نزدیک‌ترین دورهٔ
    # فیبوناچی به ATR کلاسیکِ ۱۴ است و در کلِ پروژه همین خانواده استفاده شده.
    atr = ib.compute('atr_fib_21', df).values.astype(float)
    atr = np.where(np.isfinite(atr) & (atr > 0), atr, np.nan)
    with np.errstate(invalid='ignore', divide='ignore'):
        d = (c - piv) / atr
    return d, piv


# ═══════════════════════════════════════════════════════════════════════════
#  ۴) مدلِ صفرِ کانونیِ RQS2 — دو استخر، سخت‌ترین برنده
# ═══════════════════════════════════════════════════════════════════════════
def build_null(df, asset, sig, sl, tp, mh, rng, ctx_mask=None):
    """مبنا = «برآمدِ همان براکت اگر روی بارهای تصادفی باز شود».

    دو استخر ساخته می‌شود و **بالاترین WR** به‌عنوان مبنا انتخاب می‌شود:
      الف) بی‌قید — هر بارِ ممکن
      ب) مقیدِ زمینه — فقط بارهایی که ساختار/روند وجود دارد
    انتخابِ بیشینه، آزمون را **سخت‌تر** می‌کند نه آسان‌تر (مبنای پوشالی ممنوع).
    """
    n = len(df)
    warm = 200
    n_sig = int(sig.sum())
    if n_sig < MIN_TRADES:
        return None, {}

    pools = {}
    all_bars = np.arange(warm, n - mh - 1)
    pools['uncond'] = all_bars
    if ctx_mask is not None:
        cb = all_bars[ctx_mask[all_bars]]
        if cb.size > n_sig * 3:
            pools['ctx'] = cb

    best = None
    diag = {}
    for name, pool in pools.items():
        if pool.size <= n_sig:
            continue
        # WRِ مبنا: نمونهٔ بزرگِ تصادفی از استخر
        take = min(pool.size, max(2000, n_sig * 20))
        idx = rng.choice(pool, size=take, replace=False)
        m = np.zeros(n, bool)
        m[idx] = True
        tr = SE.simulate_trades(df, m, np.zeros(n, bool), sl, tp, asset,
                                max_hold=mh, allow_overlap=True)
        if tr is None or len(tr) < 50:
            continue
        wr = float((tr['outcome'].values == 'win').mean() * 100.0)
        diag[name] = dict(wr=round(wr, 2), n=int(len(tr)))
        if best is None or wr > best[1]:
            best = (name, wr, pool)

    if best is None:
        return None, diag
    name, ref_wr, pool = best
    diag['chosen'] = name

    # توزیعِ جای‌گشتی: K قرعهٔ ناهم‌پوشان به اندازهٔ n_sig
    perm = []
    for _ in range(N_PERM):
        idx = rng.choice(pool, size=n_sig, replace=False)
        m = np.zeros(n, bool)
        m[idx] = True
        tr = SE.simulate_trades(df, m, np.zeros(n, bool), sl, tp, asset,
                                max_hold=mh, allow_overlap=False)
        if tr is None or len(tr) == 0:
            continue
        perm.append(float((tr['outcome'].values == 'win').mean() * 100.0))
    perm = np.array(perm, float)
    if perm.size < 100:
        return None, diag

    return dict(ref_wr=ref_wr, perm=perm, pool_name=name), diag


# ═══════════════════════════════════════════════════════════════════════════
#  ۵) آزمونِ یک کارت
# ═══════════════════════════════════════════════════════════════════════════
def run_card(pair, tf, save=True, seed=20260803):
    key = f"{pair}_{tf}"
    path = f"data/{pair}_{tf}.csv"
    if not os.path.exists(path):
        print(f"   ⊘ {key}: فایلِ داده نیست", flush=True)
        return None
    _reg_asset(key, path, pair)
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    n = len(df)

    print("=" * 74, flush=True)
    print(f"=== S376 :: {pair}-{tf}  (bars={n:,})  bound(H5)={BOUND:.4f}", flush=True)
    print("=" * 74, flush=True)

    # هندسه: **عیناً** از پیکربندیِ مستقرِ S333 (بندِ ۲ قفل — تغییرِ هندسه ممنوع).
    # برای کارت‌هایی که S333 پیکربندیِ رسمی ندارد، از نزدیک‌ترین TF مقیاس می‌گیریم
    # ولی صریحاً علامت می‌زنیم تا با کارت‌های رسمی اشتباه نشود.
    cfg = BEST_CFG.get(key)
    inherited = cfg is None
    if inherited:
        # مقیاسِ ATR-محور از کارتِ رسمیِ نزدیک — فقط برای گزارشِ MTF (بندِ ۵ قفل)
        ref = BEST_CFG.get(f"{pair}_M30") or BEST_CFG['XAUUSD_M30']
        cfg = dict(ref)
    pip = SE.ASSETS[key]['pip']

    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']
    if inherited:
        # SL/TP را با ATRِ همین کارت مقیاس می‌کنیم (نه عددِ ثابت — اشتباهِ #۶)
        atr_med = float(np.nanmedian(ib.compute('atr_fib_21', df).values))
        ref_atr = 3.8   # ATR تقریبیِ M30 طلا در واحدِ قیمت
        k = max(0.15, min(8.0, atr_med / ref_atr)) if np.isfinite(atr_med) else 1.0
        sl = max(5, int(round(sl * k)))
        tp = max(5, int(round(tp * k)))

    print(f"    geometry: SL={sl} TP={tp} pip mh={mh}  RR={tp/sl:.4f}"
          f"{'  [inherited-scaled]' if inherited else '  [deployed cfg]'}", flush=True)
    if tp < sl:
        print("    ⛔ RR<1 — بندِ ۸ قفل نقض می‌شود؛ کارت رد", flush=True)
        return None

    base_sig = build_s333_layer(df, cfg)
    n_base_sig = int(base_sig.sum())
    print(f"    base signals (raw) = {n_base_sig:,}", flush=True)
    if n_base_sig < MIN_TRADES:
        res = dict(pair=pair, tf=tf, verdict="NO_SAMPLE_BASE", n_sig=n_base_sig)
        if save:
            _save(res, pair, tf)
        print("    >>> NO_SAMPLE_BASE", flush=True)
        return res

    tr_base = SE.simulate_trades(df, base_sig, np.zeros(n, bool), sl, tp, key,
                                 max_hold=mh, allow_overlap=False)
    if tr_base is None or len(tr_base) < MIN_TRADES:
        res = dict(pair=pair, tf=tf, verdict="NO_SAMPLE_BASE_TRADES",
                   n_sig=n_base_sig, n_tr=0 if tr_base is None else len(tr_base))
        if save:
            _save(res, pair, tf)
        print("    >>> NO_SAMPLE_BASE_TRADES", flush=True)
        return res

    wr_base = float((tr_base['outcome'].values == 'win').mean() * 100.0)
    pnl_base = tr_base['pnl_pip'].values.astype(float)
    print(f"    BASE: n={len(tr_base)}  WR={wr_base:.2f}%  net={pnl_base.sum():+.1f}pip",
          flush=True)

    # ── جاروبِ ۳۶ سلولِ پیش‌ثبت‌شده ─────────────────────────────────────────
    sig_bars = np.where(base_sig)[0]
    cells = []
    for K in K_GRID:
        for depth in DEPTH_GRID:
            dist, piv = structural_distance(df, K, depth, pip)
            dv = dist[sig_bars]
            dv = dv[np.isfinite(dv)]
            if dv.size < MIN_TRADES:
                continue
            for q in Q_GRID:
                thr = float(np.quantile(dv, q))     # آستانه از توزیعِ خودِ فاصله‌ها
                keep = base_sig & np.isfinite(dist) & (dist <= thr)
                n_keep = int(keep.sum())
                if n_keep < MIN_TRADES:
                    continue
                tr_f = SE.simulate_trades(df, keep, np.zeros(n, bool), sl, tp, key,
                                          max_hold=mh, allow_overlap=False)
                if tr_f is None or len(tr_f) < MIN_TRADES:
                    continue
                wr_f = float((tr_f['outcome'].values == 'win').mean() * 100.0)
                ret = len(tr_f) / len(tr_base)
                cells.append(dict(K=K, depth=depth, q=q, thr=round(thr, 4),
                                  n=int(len(tr_f)), wr=round(wr_f, 3),
                                  net=round(float(tr_f['pnl_pip'].sum()), 1),
                                  retention=round(ret, 4),
                                  d_wr=round(wr_f - wr_base, 3)))

    if not cells:
        res = dict(pair=pair, tf=tf, verdict="NO_CELL",
                   base=dict(n=int(len(tr_base)), wr=round(wr_base, 3)))
        if save:
            _save(res, pair, tf)
        print("    >>> NO_CELL", flush=True)
        return res

    # مرتب‌سازی بر اساسِ ΔWR — انتخابِ نامزد برای داوریِ گران
    cells.sort(key=lambda c: -c['d_wr'])
    print(f"    cells={len(cells)}  best ΔWR: ", flush=True)
    for c in cells[:5]:
        print(f"      K={c['K']} depth={c['depth']} q={c['q']:.2f} "
              f"n={c['n']:4d} WR={c['wr']:6.2f} ΔWR={c['d_wr']:+6.2f} "
              f"ret={c['retention']:.3f} net={c['net']:+.1f}", flush=True)

    res = dict(pair=pair, tf=tf, verdict="SWEPT", n_trials=N_TRIALS,
               bound=round(BOUND, 4), inherited_cfg=inherited,
               geometry=dict(sl=sl, tp=tp, mh=mh, rr=round(tp / sl, 4)),
               base=dict(n=int(len(tr_base)), wr=round(wr_base, 3),
                         net=round(float(pnl_base.sum()), 1)),
               cells=cells)
    if save:
        _save(res, pair, tf)
    return res


def _save(res, pair, tf):
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/{pair}_{tf}.json"
    with open(p, "w") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=float)
    print(f"    → {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="XAUUSD")
    ap.add_argument("--tfs", default="M1,M5,M15,M30,H1,H4,D1,W1")
    args = ap.parse_args()
    print(f"\nN_TRIALS={N_TRIALS}  BOUND(H5)={BOUND:.4f}  N_PERM={N_PERM}\n", flush=True)
    for tf in args.tfs.split(","):
        tf = tf.strip()
        if not tf:
            continue
        try:
            run_card(args.pair, tf)
        except Exception as e:
            import traceback
            print(f"   ✗ {args.pair}-{tf}: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()


if __name__ == "__main__":
    main()
