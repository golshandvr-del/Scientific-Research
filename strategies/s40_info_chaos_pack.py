"""
استراتژی ۴۰ — بسته feature اطلاعاتی-آشوبی (Information-Theoretic / Chaos Feature Pack)

طرح: گروه D (ریاضیات عمیق) — بسته‌ی رتبه ۸ ماتریس اولویت (P17+P18+P14+P23+P22)
هدف مستقیم: L1 می‌گوید «فقط اطلاعات ورودیِ جدید سقف را جابه‌جا می‌کند». پنج اهرم
قبلی (MTF/پرتفوی/RR/scale-out/رژیم-نوسان) همگی اهرم «ساختار/خروج/فیلتر» بودند و
هیچ‌کدام feature اطلاعاتیِ *جدید* به مدل ندادند. این استراتژی برای اولین بار یک
بُعد اطلاعاتی کاملاً متفاوت از featureهای فعلی (که «سطح و روند» را می‌بینند) به
مدل تزریق می‌کند:

  1. Hurst exponent (نمای هرست، R/S) روی ۲۵۶ کندل — حافظه بلندمدت (P17)
  2. Permutation Entropy (آنتروپی جایگشتی، order=4) روی ۶۴ — پیش‌بینی‌پذیری (P18)
  3. Variance Ratio در افق ۴/۸/۱۶ — روندی/برگشتی پیوسته (P14)
  4. Jump ratio (RV−BV)/RV — سهم پرش از نوسان (P14)
  5. Rolling Skew/Kurt بازده روی ۶۴ — عدم‌تقارن توزیعی لحظه‌ای (P23)
  6. OU half-life و z نرمال‌شده به half-life روی spread از EMA50 (P22)

روش پذیرش (Recipe-S25): A/B دقیق مدل پایه S25 با و بدون بسته‌ی جدید، همان foldها،
همان seedها، Purged WF + embargo، ورود open بعدی، اسپرد ۰.۲$. معیار: بهبود
هم‌زمان WR/PF. همه‌ی featureها فقط از گذشته/جاری (no look-ahead).
"""
import sys; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np
import pandas as pd
from numba import njit
import lightgbm as lgb
from scipy.stats import binomtest
import warnings; warnings.filterwarnings('ignore')

from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from _base_s25 import (N_FOLDS, MIN_TRAIN_FRAC, EMBARGO, HZ, TP_M, SL_M,
                        THRESH, SPREAD, SEEDS, _lgbm, purged_walk_forward,
                        eval_entries)


# ============================================================
#  featureهای اطلاعاتی-آشوبی (پیاده‌سازی numba، بدون look-ahead)
# ============================================================

@njit(cache=True)
def _hurst_rs(logp, window):
    """
    نمای هرست به روش Rescaled-Range (R/S) روی پنجره‌ی غلتان.
    H>0.5 = حافظه‌دار/روندی، H<0.5 = برگشتی، H=0.5 = تصادفی.
    فقط از close گذشته/جاری استفاده می‌کند.
    """
    n = len(logp)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        # بازده‌های داخل پنجره
        seg = logp[i - window + 1:i + 1]
        # سری تفاضلی (بازده)
        rets = np.empty(window - 1)
        for k in range(window - 1):
            rets[k] = seg[k + 1] - seg[k]
        m = rets.mean()
        # سری تجمعی انحراف
        cum = 0.0
        cmin = 0.0
        cmax = 0.0
        first = True
        var = 0.0
        for k in range(window - 1):
            d = rets[k] - m
            cum += d
            if first:
                cmin = cum; cmax = cum; first = False
            else:
                if cum < cmin:
                    cmin = cum
                if cum > cmax:
                    cmax = cum
            var += d * d
        R = cmax - cmin
        S = np.sqrt(var / (window - 1))
        if S > 1e-12 and R > 1e-12:
            out[i] = np.log(R / S) / np.log(window - 1)
    return out


@njit(cache=True)
def _perm_entropy(x, window, order):
    """
    آنتروپی جایگشتی نرمال‌شده (Bandt-Pompe) با order=3 یا 4.
    مقدار پایین = بازار قابل‌پیش‌بینی‌تر (الگوی نظم‌مند).
    برای سرعت، order ثابت ۴ فرض می‌شود (۲۴ جایگشت ممکن).
    """
    n = len(x)
    out = np.full(n, np.nan)
    nperm = 1
    for k in range(2, order + 1):
        nperm *= k  # !order
    logn = np.log(nperm)
    for i in range(window - 1, n):
        counts = np.zeros(nperm)
        # تعداد الگوهای مرتبی داخل پنجره
        npat = 0
        for s in range(i - window + 1, i - order + 2):
            # رتبه‌ی order مقدار متوالی -> یک شناسه جایگشت (Lehmer code)
            # order کوچک است؛ محاسبه‌ی رتبه با شمارش
            code = 0
            factor = 1
            for a in range(order):
                r = 0
                for bb in range(order):
                    if x[s + bb] < x[s + a] or (x[s + bb] == x[s + a] and bb < a):
                        r += 1
                code += r * factor
                factor *= (a + 1)
            # code در [0, order!)
            if code < nperm:
                counts[code] += 1
                npat += 1
        if npat > 0:
            H = 0.0
            for c in range(nperm):
                if counts[c] > 0:
                    p = counts[c] / npat
                    H -= p * np.log(p)
            out[i] = H / logn  # نرمال‌شده به [0,1]
    return out


@njit(cache=True)
def _variance_ratio(logp, window, q):
    """
    نسبت واریانس Lo-MacKinlay: VR(q) = Var(q-period ret)/(q*Var(1-period ret)).
    VR>1 = روندی (momentum)، VR<1 = برگشتی (mean-reverting)، ~1 = تصادفی.
    """
    n = len(logp)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        seg = logp[i - window + 1:i + 1]
        m = len(seg)
        # بازده 1-دوره
        r1 = np.empty(m - 1)
        for k in range(m - 1):
            r1[k] = seg[k + 1] - seg[k]
        mu = r1.mean()
        var1 = 0.0
        for k in range(m - 1):
            d = r1[k] - mu
            var1 += d * d
        var1 /= (m - 1)
        if var1 < 1e-16:
            continue
        # بازده q-دوره
        nq = m - q
        if nq <= 1:
            continue
        muq = q * mu
        varq = 0.0
        for k in range(nq):
            rq = seg[k + q] - seg[k]
            d = rq - muq
            varq += d * d
        varq /= nq
        out[i] = varq / (q * var1)
    return out


@njit(cache=True)
def _jump_ratio(rets, window):
    """
    سهم پرش از کل نوسان: (RV−BV)/RV.
    RV = Σ r² (realized variance)، BV = (π/2)·Σ|r_t||r_{t-1}| (bipower variation).
    نزدیک ۰ = نوسان پیوسته/روان، بالا = وجود پرش (اخبار/شوک).
    """
    n = len(rets)
    out = np.full(n, np.nan)
    c_bv = np.pi / 2.0
    for i in range(window, n):
        rv = 0.0
        bv = 0.0
        for k in range(i - window + 1, i + 1):
            rv += rets[k] * rets[k]
            bv += abs(rets[k]) * abs(rets[k - 1])
        bv *= c_bv
        if rv > 1e-16:
            jr = (rv - bv) / rv
            if jr < 0.0:
                jr = 0.0
            out[i] = jr
    return out


@njit(cache=True)
def _rolling_skew_kurt(rets, window):
    """چولگی و کشیدگی غلتان بازده (گشتاورهای ۳ و ۴ نرمال‌شده)."""
    n = len(rets)
    skew = np.full(n, np.nan)
    kurt = np.full(n, np.nan)
    for i in range(window - 1, n):
        s = 0.0
        for k in range(i - window + 1, i + 1):
            s += rets[k]
        mu = s / window
        m2 = 0.0; m3 = 0.0; m4 = 0.0
        for k in range(i - window + 1, i + 1):
            d = rets[k] - mu
            d2 = d * d
            m2 += d2
            m3 += d2 * d
            m4 += d2 * d2
        m2 /= window; m3 /= window; m4 /= window
        sd = np.sqrt(m2)
        if sd > 1e-12:
            skew[i] = m3 / (sd * sd * sd)
            kurt[i] = m4 / (m2 * m2) - 3.0
    return skew, kurt


@njit(cache=True)
def _ou_halflife(spread, window):
    """
    نیم‌عمر بازگشت به میانگین از رگرسیون AR(1) روی spread (فرایند OU گسسته):
      Δs_t = a + b·s_{t-1} + e  ->  θ = -b،  half-life = ln(2)/(-b) اگر b<0.
    خروجی: نیم‌عمر (کندل) و z نرمال‌شده به همان نیم‌عمر.
    """
    n = len(spread)
    hl = np.full(n, np.nan)
    for i in range(window, n):
        # رگرسیون Δs بر s_{lag}
        sx = 0.0; sy = 0.0; sxx = 0.0; sxy = 0.0
        m = 0
        for k in range(i - window + 1, i + 1):
            x = spread[k - 1]
            y = spread[k] - spread[k - 1]
            sx += x; sy += y; sxx += x * x; sxy += x * y
            m += 1
        denom = m * sxx - sx * sx
        if abs(denom) > 1e-12:
            b = (m * sxy - sx * sy) / denom
            if b < -1e-6:
                hl[i] = np.log(2.0) / (-b)
    return hl


def build_info_chaos_features(df):
    """بسته‌ی feature اطلاعاتی-آشوبی را به‌صورت DataFrame هم‌طول df می‌سازد."""
    close = df['close'].values.astype(np.float64)
    logp = np.log(close)
    rets = np.empty(len(close)); rets[0] = 0.0
    rets[1:] = np.diff(logp)

    g = pd.DataFrame(index=df.index)

    # 1) Hurst (256)
    g['hurst_256'] = _hurst_rs(logp, 256)
    g['hurst_128'] = _hurst_rs(logp, 128)

    # 2) Permutation Entropy (order=4, window=64)
    g['perm_ent_64'] = _perm_entropy(close, 64, 4)
    g['perm_ent_32'] = _perm_entropy(close, 32, 3)

    # 3) Variance Ratio q=4,8,16 (window=96)
    for q in [4, 8, 16]:
        g[f'vr_{q}'] = _variance_ratio(logp, 96, q)

    # 4) Jump ratio (window=32)
    g['jump_ratio'] = _jump_ratio(rets, 32)

    # 5) Skew/Kurt بازده (window=64)
    sk, ku = _rolling_skew_kurt(rets, 64)
    g['ret_skew_64'] = sk
    g['ret_kurt_64'] = ku

    # 6) OU half-life و z نرمال (spread از EMA50)
    ema50 = ind.ema(df['close'], 50).values
    spread = (close - ema50)
    hl = _ou_halflife(spread, 96)
    g['ou_halflife'] = np.clip(hl, 0, 500)
    # z نرمال‌شده: spread فعلی نسبت به std غلتان spread، مقیاس‌شده به سرعت بازگشت
    sp_ser = pd.Series(spread, index=df.index)
    sp_std = sp_ser.rolling(96).std().replace(0, np.nan).values
    z = spread / sp_std
    g['ou_z'] = z
    # کشش برگشتی مورد انتظار = z / sqrt(half-life) (هرچه کوتاه‌تر، برگشت سریع‌تر)
    g['ou_pull'] = z / np.sqrt(np.clip(hl, 1, 500))

    return g


# ============================================================
#  A/B  (baseline S25  vs  augmented با بسته‌ی جدید)
# ============================================================

def run_ab():
    print("=" * 70)
    print("S40 — Information/Chaos Feature Pack  |  A/B با base S25")
    print("=" * 70)

    df = load_data()
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values

    print("ساخت featureهای پایه (۵۹) ...")
    base_feats = build_features(df)
    base_cols = list(base_feats.columns)

    print("ساخت featureهای اطلاعاتی-آشوبی (بسته‌ی جدید) ...")
    new_feats = build_info_chaos_features(df)
    new_cols = list(new_feats.columns)
    print(f"  featureهای جدید: {new_cols}")

    # کاندید پایه S25: uptrend long-only
    cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
    y = make_target(df, HZ, TP_M, SL_M, atr, 'long')

    all_feats = pd.concat([base_feats, new_feats], axis=1)
    data = all_feats.copy(); data['y'] = y; data['cand'] = cand
    aug_cols = base_cols + new_cols

    def prep(cols):
        v = data.dropna(subset=cols + ['y'])
        v = v[v['cand']]
        return v[cols].values, v['y'].values.astype(int), v.index.values

    results = {}
    for tag, cols in [('BASE', base_cols), ('AUG', aug_cols)]:
        X, Y, idx = prep(cols)
        print(f"\n[{tag}] cols={len(cols)}  valid rows={len(X)}")
        probas = [purged_walk_forward(X, Y, idx, n, seed=s) for s in SEEDS]
        proba_ens = np.nanmean(np.vstack(probas), axis=0)
        results[tag] = proba_ens
        # importance رتبه‌ی feature (fold آخر، seed اول) فقط برای AUG
        if tag == 'AUG':
            _, models = purged_walk_forward(X, Y, idx, n, seed=42, return_models=True)
            m = models[-1]
            imp = pd.Series(m.feature_importances_, index=cols).sort_values(ascending=False)
            print("\n  رتبه‌ی importance featureهای جدید (از میان کل):")
            ranks = {name: r + 1 for r, name in enumerate(imp.index)}
            for nc in new_cols:
                print(f"    {nc:16s} rank={ranks[nc]:3d}/{len(cols)}  imp={imp[nc]:.0f}")

    # --- ارزیابی در نقطه‌ی کار S25 (thr=0.68) و جاروب thr ---
    print("\n" + "=" * 70)
    print("ارزیابی هم‌سطح در نقطه‌ی کار S25 (TP1.0/SL1.5, HZ48)")
    print("=" * 70)
    summary = {}
    for tag in ['BASE', 'AUG']:
        proba = results[tag]
        ent = (~np.isnan(proba)) & (proba >= THRESH)
        r = eval_entries(df, atr, ent, label=f'{tag} @thr0.68')
        summary[tag] = r

    # جاروب thr برای هر دو
    print("\n--- جاروب thr (AUG) ---")
    aug_curve = []
    for thr in [0.55, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70]:
        proba = results['AUG']
        ent = (~np.isnan(proba)) & (proba >= thr)
        r = eval_entries(df, atr, ent, label=f'AUG thr{thr:.2f}', verbose=True)

    print("\n--- جاروب thr (BASE) برای مقایسه ---")
    for thr in [0.55, 0.60, 0.64, 0.68]:
        proba = results['BASE']
        ent = (~np.isnan(proba)) & (proba >= thr)
        r = eval_entries(df, atr, ent, label=f'BASE thr{thr:.2f}', verbose=True)

    # --- حکم A/B در نقطه‌ی کار مشترک ---
    print("\n" + "=" * 70)
    print("حکم A/B (نقطه‌ی کار مشترک thr0.68):")
    b = summary['BASE']; a = summary['AUG']
    if b and a:
        print(f"  BASE: WR={b['wr']:.2f}% PF={b['pf']:.3f} exp={b['exp']:+.3f}$ n={b['n']}")
        print(f"  AUG : WR={a['wr']:.2f}% PF={a['pf']:.3f} exp={a['exp']:+.3f}$ n={a['n']}")
        print(f"  ΔWR={a['wr']-b['wr']:+.2f}pp  ΔPF={a['pf']-b['pf']:+.3f}  "
              f"Δexp={a['exp']-b['exp']:+.3f}$")
        if a['wr'] > b['wr'] and a['pf'] > b['pf']:
            print("  ✅ بهبود هم‌زمان WR و PF — بسته‌ی جدید ارزش دارد.")
        elif a['pf'] > b['pf'] or a['wr'] > b['wr']:
            print("  ⚠️ بهبود جزئی (فقط یکی از WR/PF).")
        else:
            print("  ❌ بدون بهبود — بسته رد می‌شود (تأیید مجدد L15/L18).")

    return results, summary


if __name__ == '__main__':
    run_ab()
