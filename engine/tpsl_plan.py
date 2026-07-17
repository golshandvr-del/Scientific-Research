"""
tpsl_plan.py — ماژولِ مستقلِ TP-Plan + SL-Plan (رژیم-آگاه، forward-safe)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدفِ پروژه **فقط و فقط «سودِ خالصِ بیشتر»**
است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**

------------------------------------------------------------------------------
انگیزه (پاسخ به User Note نکتهٔ ۲):
  کاربر به یاد داشت که قبلاً با «tpplan/slplan» به سودِ خالصِ ۷۰۰۰$+ رسیده بودیم.
  بررسی نشان داد این منطق (SL و TP رژیم-آگاهِ یادگرفته‌شده از گذشته) در کدِ
  `s66_adaptive_sl_router.py` (نتیجهٔ ۷۳۵۰$) وجود داشت اما **هیچ‌گاه به‌عنوانِ یک
  ماژولِ مستقل و شفاف بیرون کشیده نشده بود** و در README/سایت هم منعکس نشده بود.

  این ماژول همان منطق را به‌صورتِ یک واحدِ تمیز و قابلِ استفادهٔ مجدد استخراج می‌کند:

  • **SL-Plan:** برای هر سطلِ رژیم (`trend_hi/lo`, `chop_hi/lo`)، ضریبِ SLِ بهینه
    (بر حسبِ ATR) که در پنجرهٔ اخیرِ گذشته بیشترین سودِ خالص را داده.
  • **TP-Plan:** به همان روش، ضریبِ TPِ بهینه برای هر سطل.
  • **جست‌وجوی مشترکِ (SL, TP)** روی گرید تا کلِ R:R رژیم-آگاه شود (نه بهینه‌سازیِ
    جدا-جدا که به نقطهٔ زین می‌افتد).

  هر دو Plan **فقط از داده‌های قبل از بلوکِ جاری** یاد گرفته می‌شوند → کاملاً بدونِ
  نشتِ آینده (forward-safe). این دقیقاً نگاشتِ حالتِ چهارمِ سایت («مدیریتِ معامله»)
  است: سایت به کاربر می‌گوید SL/TP را کجا بگذارد و کِی جابه‌جا کند.

------------------------------------------------------------------------------
خروجی: یک شیءِ `Plan` که برای هر کندل ضریبِ SL و TP و وزنِ Kelly را نگه می‌دارد،
        به‌همراهِ سری‌های دلاریِ SL و TP (ضریب × ATR) آمادهٔ تزریق به موتور.
"""
import numpy as np


# --- کاندیدهای پیش‌فرضِ ضریب (بر حسبِ ATR) — منطبق بر برندهٔ S66 ---
DEFAULT_SL_CANDS_L = [1.0, 1.25, 1.5, 1.75, 2.0]     # Bull
DEFAULT_SL_CANDS_S = [1.2, 1.45, 1.7, 1.95, 2.2]     # Bear
DEFAULT_TP_CANDS_L = [0.8, 1.0, 1.3, 1.6, 2.0]       # Bull
DEFAULT_TP_CANDS_S = [1.0, 1.4, 1.8, 2.2, 2.6]       # Bear
SL_BASE_L, SL_BASE_S = 1.5, 1.7
BUCKETS = ['trend_hi', 'trend_lo', 'chop_hi', 'chop_lo']

# پارامترهای یادگیریِ رولینگ (منطبق بر برندهٔ S63–S66)
STEP = 6000
LOOKBACK = 24000
EXP_MIN = 0.10
MIN_N = 15
# وزنِ Kelly
W_MIN, W_MAX, W_BASE, W_SLOPE = 0.5, 2.0, 1.0, 1.2


def kelly_weight(exp, exp_min=None, atr_scale=None):
    """
    وزنِ حجمِ Kelly-کسری بر اساسِ اکسپکتنسیِ اخیرِ سطل.
    exp_min   : مبنای صفرِ وزن (پیش‌فرض EXP_MIN سراسری — رفتارِ تاریخیِ XAUUSD).
    atr_scale : اگر داده شود، (exp - exp_min) بر حسبِ ATR نرمال می‌شود تا وزن‌دهی
                برای دارایی‌های با مقیاسِ قیمتِ متفاوت هم درست باشد (S69).
    """
    if exp_min is None:
        exp_min = EXP_MIN
    if atr_scale and atr_scale > 0:
        return float(np.clip(W_BASE + W_SLOPE * ((exp - exp_min) / atr_scale), W_MIN, W_MAX))
    return float(np.clip(W_BASE + W_SLOPE * (exp - exp_min), W_MIN, W_MAX))


class TPSLPlan:
    """
    نگه‌دارندهٔ خروجیِ برنامه‌ریزی: برای هر کندل ضریبِ SL/TP و وزنِ Kelly.
    از `build_plan` تولید می‌شود. سری‌های دلاری را با `sl_series`/`tp_series` بگیرید.
    """
    def __init__(self, n, atrv, direction):
        self.n = n
        self.atrv = atrv
        self.direction = direction
        self.entries = np.zeros(n, dtype=bool)
        self.weights = np.ones(n)
        self.sl_mult = np.zeros(n)
        self.tp_mult = np.zeros(n)
        self.log = []   # [(block_start, [(bucket, sl, tp, w), ...]), ...]

    def sl_series(self, default_mult=None):
        base = default_mult if default_mult is not None else (
            SL_BASE_L if self.direction == 'long' else SL_BASE_S)
        return np.where(self.sl_mult > 0, self.sl_mult * self.atrv, base * self.atrv)

    def tp_series(self, default_mult=1.0):
        return np.where(self.tp_mult > 0, self.tp_mult * self.atrv, default_mult * self.atrv)

    def sl_dist_for_trades(self, trades):
        """فاصلهٔ SL به دلار برای هر معامله (به ترتیبِ trades) — برای موتورِ سرمایه."""
        sl_ser = self.sl_series()
        idx = trades['signal_bar'].values
        return sl_ser[idx]


def build_plan(direction, base_lab, atrv, df, run_backtest,
               spread=0.20, max_hold=48,
               sl_cands=None, tp_cands=None,
               adaptive_sl=True, adaptive_tp=True, use_kelly=True,
               step=STEP, lookback=LOOKBACK, exp_min=None):
    """
    برنامهٔ SL/TP/وزنِ رژیم-آگاه را به‌صورتِ رولینگ و forward-safe می‌سازد.

    برای هر بلوکِ [start, start+step):
      • فقط از پنجرهٔ [start-lookback, start) یاد می‌گیریم.
      • هر سطلِ رژیم که اکسپکتنسیِ اخیرش ≥ exp_min و n ≥ MIN_N باشد «روشن» است.
      • جست‌وجوی مشترکِ (SL, TP) روی گرید، انتخابِ جفتی با بیشترین سودِ خالصِ اخیر.
      • وزنِ Kelly از اکسپکتنسیِ همان جفتِ بهینه.

    exp_min : آستانهٔ اکسپکتنسیِ «روشن‌شدنِ سطل» به «واحدِ قیمتِ همان دارایی».
              اگر None → EXP_MIN سراسری (=۰.۱۰) — رفتارِ تاریخیِ XAUUSD دست‌نخورده
              (سازگاریِ عقب‌رو با S67). ⚠️ برای دارایی‌های با مقیاسِ قیمتِ متفاوت
              (فارکس ~۱.۱ ، DXY ~۱۰۰) این عدد باید ATR-نسبی باشد (~۰.۰۲۶×میانگینِ ATR)،
              وگرنه هیچ سطلی روشن نمی‌شود و صفر معامله تولید می‌گردد (باگِ مقیاسِ کشف‌شده در S69).

    این تابع به backtest.run_backtest وابسته است (تزریق‌شده تا ماژول مستقل بماند).
    """
    if exp_min is None:
        exp_min = EXP_MIN
    n = len(df)
    if sl_cands is None:
        sl_cands = DEFAULT_SL_CANDS_L if direction == 'long' else DEFAULT_SL_CANDS_S
    if tp_cands is None:
        tp_cands = DEFAULT_TP_CANDS_L if direction == 'long' else DEFAULT_TP_CANDS_S
    base_sl = SL_BASE_L if direction == 'long' else SL_BASE_S
    base_tp = tp_cands[1]   # نقطهٔ پایه (۱.۰ Bull / ۱.۴ Bear)

    plan = TPSLPlan(n, atrv, direction)

    def bucket_bt(bucket, lo, hi, sl_mult, tp_mult):
        m = np.zeros(n, dtype=bool)
        seg = (base_lab == bucket)
        m[lo:hi] = seg[lo:hi]
        if m.sum() < 1:
            return None, 0, 0.0
        st, _ = run_backtest(df, m, None, None, direction, spread=spread,
                             max_hold=max_hold,
                             sl_series=sl_mult * atrv, tp_series=tp_mult * atrv)
        return st['expectancy'], st['n_trades'], st['total_pnl']

    for start in range(lookback, n, step):
        end = min(start + step, n)
        lb_lo = max(0, start - lookback)
        chosen = []
        for bk in BUCKETS:
            # آیا سطل روشن است؟ (با SL/TP پایه، مطابق قاعدهٔ روشن/خاموشِ برنده)
            exp0, ntr0, _ = bucket_bt(bk, lb_lo, start, base_sl, base_tp)
            if exp0 is None or ntr0 < MIN_N or exp0 < exp_min:
                continue
            sl_grid = sl_cands if adaptive_sl else [base_sl]
            tp_grid = tp_cands if adaptive_tp else [base_tp]
            best_sl, best_tp, best_pnl, best_exp = base_sl, base_tp, -1e9, exp0
            for slc in sl_grid:
                for tpc in tp_grid:
                    e, nt, pnl = bucket_bt(bk, lb_lo, start, slc, tpc)
                    if e is not None and nt >= MIN_N and pnl > best_pnl:
                        best_pnl, best_sl, best_tp, best_exp = pnl, slc, tpc, e
            # atr_scale: میانگینِ ATR روی پنجرهٔ یادگیری (برای نرمال‌سازیِ ATR-نسبیِ وزن).
            # فقط وقتی exp_min صریح داده شده (S69) اعمال می‌شود؛ برای XAUUSDِ پیش‌فرض None.
            atr_scale = None
            if exp_min != EXP_MIN:
                seg_atr = atrv[lb_lo:start]
                atr_scale = float(np.nanmean(seg_atr)) if len(seg_atr) else None
            w = kelly_weight(best_exp, exp_min=exp_min, atr_scale=atr_scale) if use_kelly else 1.0
            chosen.append((bk, best_sl, best_tp, w))
        for bk, slc, tpc, w in chosen:
            seg = (base_lab == bk)
            sel = np.zeros(n, dtype=bool)
            sel[start:end] = seg[start:end]
            plan.entries |= sel
            plan.weights[sel] = w
            plan.sl_mult[sel] = slc
            plan.tp_mult[sel] = tpc
        plan.log.append((start, [(b, sl, tp, round(w, 2)) for b, sl, tp, w in chosen]))

    return plan
