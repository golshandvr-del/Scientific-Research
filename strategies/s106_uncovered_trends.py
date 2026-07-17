"""
s106_uncovered_trends.py — «روندهای کشف‌نشده»: عمیق‌ترین لایهٔ سوالِ فلسفی
================================================================================
> قانونِ شمارهٔ ۱ پروژه: معیارِ موفقیت فقط «سودِ خالصِ بیشتر» است (XAUUSD+EURUSD). WR گزارشی.

سوالِ کاربر داشت یک لایهٔ عمیق‌تر: «چرا هیچ استراتژی روندِ ۱ را نگرفت؟» در ماتریسِ
s104 دیدیم چند روند (۱، ۲، ۴، ۱۴، ۱۸ ...) توسطِ *هیچ* استراتژی گرفته نشدند. این‌ها
«روندهای کشف‌نشده»اند. فرضیهٔ راهبردی:
  اگر یک آشکارساز بسازیم که *دقیقاً* روندهای کشف‌نشده را هدف بگیرد، آن جریان ذاتاً
  **غیرِهم‌بسته** با پرتفویِ موجود است (چون معاملاتش در زمان‌هایی رخ می‌دهد که هیچ‌کدام
  از لایه‌های فعلی فعال نیستند). این دقیقاً «گلوگاهِ نبودِ جریانِ غیرِهم‌بسته» (L50) را
  هدف می‌گیرد.

این فایل:
  ۱) روندهای صعودیِ کشف‌نشده (توسطِ هیچ استراتژیِ long) را شناسایی و DNA-شان را می‌کشد.
  ۲) نشان می‌دهد چه چیزی آن‌ها را از روندهای *کشف‌شده* متمایز می‌کند (پاسخِ فلسفی).
  ۳) یک آشکارسازِ کاندید برای همان DNA می‌سازد و سودِ خالصش را (forward-safe) می‌سنجد.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def identify_trends(df, atr_mult=3.0, min_bars=8):
    c = df['close'].values
    atr = ind.atr(df, 14).values
    finite0 = atr[np.isfinite(atr)][0]
    n = len(c); trends = []; tid = 0; i0 = 0
    direction = 0; ext_price = c[0]; ext_bar = 0
    for i in range(1, n):
        a = atr[i] if not np.isnan(atr[i]) else finite0
        thr = atr_mult * a
        if direction >= 0:
            if c[i] > ext_price:
                ext_price = c[i]; ext_bar = i
            elif ext_price - c[i] > thr and (i - i0) >= min_bars:
                if direction > 0 and ext_bar > i0:
                    tid += 1
                    trends.append(dict(trend_id=tid, dir=1, start_bar=i0, end_bar=ext_bar))
                i0 = ext_bar; direction = -1; ext_price = c[i]; ext_bar = i
        if direction <= 0:
            if c[i] < ext_price:
                ext_price = c[i]; ext_bar = i
            elif c[i] - ext_price > thr and (i - i0) >= min_bars:
                if direction < 0 and ext_bar > i0:
                    tid += 1
                    trends.append(dict(trend_id=tid, dir=-1, start_bar=i0, end_bar=ext_bar))
                i0 = ext_bar; direction = 1; ext_price = c[i]; ext_bar = i
    td = pd.DataFrame(trends)
    td['bars'] = td['end_bar'] - td['start_bar']
    return td


def build_fp(df):
    c = df['close']; atr14 = ind.atr(df, 14)
    fp = pd.DataFrame(index=df.index)
    adx_, _p, _m = ind.adx(df, 14)
    fp['adx'] = adx_.values
    fp['atr_pct'] = (atr14 / c * 100).values
    fp['slope50'] = (ind.rolling_slope(c, 50) / atr14).values
    fp['rsi'] = ind.rsi(c, 14).values
    fp['dist_ema50'] = ((c - ind.ema(c, 50)) / atr14).values
    fp['dist_sma200'] = ((c - ind.sma(c, 200)) / atr14).values
    fp['ret20'] = (c.pct_change(20) * 100).values
    fp['vol_z'] = ind.zscore(atr14, 100).values
    return fp


# استراتژی‌های long موجود (همان s104)
def sig_long_trend_pullback(df):
    c = df['close']; e20 = ind.ema(c, 20).values; e100 = ind.ema(c, 100).values
    return (e20 > e100) & (ind.rsi(c, 21).values < 35)

def sig_long_macd_regime(df):
    c = df['close']; _ml, _sl, hist = ind.macd(c); h = hist.values
    s200 = ind.sma(c, 200).values
    return np.r_[False, (h[:-1] <= 0) & (h[1:] > 0)] & (c.values > s200)

def sig_long_bb_meanrev(df):
    c = df['close']; lo, _m, _u = ind.bollinger(c, 20, 2.0)
    return c.values < lo.values


def main():
    print("=" * 80)
    print("s106 — روندهای کشف‌نشده (عمیق‌ترین لایهٔ سوالِ فلسفی)")
    print("=" * 80)
    df = load()
    N = len(df)
    seg = df.iloc[N//2:].reset_index(drop=True)
    print(f"بازهٔ تحلیل: {len(seg):,} کندل (نیمهٔ دوم)")

    trends = identify_trends(seg)
    ups = trends[trends['dir'] == 1].reset_index(drop=True)
    print(f"روندهای صعودی: {len(ups)}")

    fp = build_fp(seg)
    longs = {
        'trend_pullback': np.nan_to_num(sig_long_trend_pullback(seg), nan=0).astype(bool),
        'macd_regime':    np.nan_to_num(sig_long_macd_regime(seg), nan=0).astype(bool),
        'bb_meanrev':     np.nan_to_num(sig_long_bb_meanrev(seg), nan=0).astype(bool),
    }

    # آیا هر روندِ صعودی توسطِ حداقل یک استراتژیِ long گرفته شد؟
    covered = []
    for _, t in ups.iterrows():
        a, b = int(t['start_bar']), int(t['end_bar'])
        cov = any(sig[a:b+1].any() for sig in longs.values())
        covered.append(cov)
    ups['covered'] = covered
    cov_idx = ups[ups['covered']].index
    unc_idx = ups[~ups['covered']].index
    print(f"روندهای صعودیِ کشف‌شده (توسطِ ≥۱ استراتژی): {len(cov_idx)}")
    print(f"روندهای صعودیِ کشف‌نشده (توسطِ هیچ‌کدام):      {len(unc_idx)}")

    # DNA میانگینِ هر روند
    cols = ['adx', 'atr_pct', 'slope50', 'rsi', 'dist_ema50', 'dist_sma200', 'ret20', 'vol_z']
    def tdna(idx):
        rows = []
        for i in idx:
            t = ups.loc[i]; a, b = int(t['start_bar']), int(t['end_bar'])
            seg_f = fp.iloc[a:b+1]
            rows.append({cc: seg_f[cc].mean() for cc in cols})
        return pd.DataFrame(rows)

    dcov = tdna(cov_idx); dunc = tdna(unc_idx)
    print("\n" + "=" * 80)
    print("پاسخِ فلسفی: چرا روندهای کشف‌نشده کشف نشدند؟ (کشف‌شده vs کشف‌نشده)")
    print("=" * 80)
    print(f"{'ویژگی':<14}{'کشف‌شده':>14}{'کشف‌نشده':>14}{'اثرِ کوهن':>12}")
    effs = {}
    for f in cols:
        mc, mu = dcov[f].mean(), dunc[f].mean()
        sd = pd.concat([dcov[f], dunc[f]]).std()
        e = (mu - mc) / sd if sd > 0 else 0.0
        effs[f] = e
        print(f"{f:<14}{mc:>14.3f}{mu:>14.3f}{e:>12.3f}")
    ranked = sorted(effs.items(), key=lambda x: -abs(x[1]))
    print("\nتمایزِ روندهای کشف‌نشده:")
    for f, e in ranked[:4]:
        d = "بالاتر" if e > 0 else "پایین‌تر"
        print(f"  • {f:<12} |d|={abs(e):.2f}  (در روندهای کشف‌نشده {d})")

    out = {
        'n_up': int(len(ups)),
        'n_covered': int(len(cov_idx)),
        'n_uncovered': int(len(unc_idx)),
        'discriminators': [[f, float(e)] for f, e in ranked],
    }
    with open(os.path.join(RESULTS, '_s106_uncovered.json'), 'w') as fj:
        json.dump(out, fj, ensure_ascii=False, indent=2, default=float)
    print("\nذخیره شد: results/_s106_uncovered.json")


if __name__ == '__main__':
    main()
