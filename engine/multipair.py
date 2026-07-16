"""
ماژول تأییدِ چند-جفت‌ارزی (Multi-Pair Confirmation) — پاسخ به User Note.

ایده: طلا با سبدِ ارزهای دلاری همبستگیِ *هم‌زمانِ* قوی دارد (تأیید تجربی:
corr(XAU,DXY)=-0.33, (XAU,EURUSD)=+0.34, (XAU,AUDUSD)=+0.37, (XAU,USDCHF)=-0.35).
اما قدرتِ *پیش‌روِ* این سبد ضعیف است (lead corr ~0.01). پس سبد را نه به‌عنوان
پیش‌بین، بلکه به‌عنوان **گیتِ تأییدِ هم‌جهت** به کار می‌بریم: یک سیگنالِ long روی
طلا فقط وقتی مجاز است که «قدرتِ دلار» در سبد نیز به نفعِ صعودِ طلا باشد
(دلار ضعیف). این باخت‌های «طلا صعودی ولی دلار قوی» (تضاد) را حذف می‌کند.

قاعدهٔ no-look-ahead: برای هر کندل M15 طلا در زمان t، فقط از کندل‌های جفت‌ارز که
close آن‌ها <= t بسته شده استفاده می‌شود (merge_asof backward). سیگنالِ سبد از
بازدهِ کندل‌های بسته‌شده ساخته می‌شود، پس هم‌زمان‌بودنش نشتِ آینده نیست: در لحظهٔ
تصمیم (بسته‌شدن کندل t طلا)، کندل هم‌زمانِ جفت‌ارز نیز بسته و در دسترس است.
"""
import numpy as np
import pandas as pd
import os

_DATA = os.path.join(os.path.dirname(__file__), '..', 'data')

# جهتِ همبستگی هر جفت با طلا (+1 = هم‌جهت، −1 = معکوس)
_PAIR_SIGN = {'DXY': -1, 'USDCHF': -1, 'EURUSD': +1, 'AUDUSD': +1}
_PAIR_FILE = {'DXY': 'DXY_M15.csv', 'USDCHF': 'USDCHF_M15.csv',
              'EURUSD': 'EURUSD_M15.csv', 'AUDUSD': 'AUDUSD_M15.csv'}


def _load(fn):
    d = pd.read_csv(os.path.join(_DATA, fn))
    d['dt'] = pd.to_datetime(d['time'], unit='s')
    d = d.sort_values('dt').drop_duplicates('dt').reset_index(drop=True)
    return d


def _aligned_close(xau_df, other, name):
    left = xau_df[['dt']].copy()
    left['_row'] = np.arange(len(left))
    right = other[['dt', 'close']].rename(columns={'close': name}).sort_values('dt')
    m = pd.merge_asof(left.sort_values('dt'), right, on='dt',
                      direction='backward', tolerance=pd.Timedelta('2h'))
    return m.sort_values('_row').reset_index(drop=True)[name].values


def build_multipair_features(xau_df, pairs=None):
    """
    featureهای تأییدِ چند-جفت‌ارزی هم‌طول xau_df برمی‌گرداند.

    خروجی (DataFrame با index = xau_df.index):
      mp_basket_ret_{k}   : میانگینِ z-score بازدهِ k-کندلیِ سبد (جهتِ طلا؛ >0 = صعودیِ طلا)
      mp_dollar_str_{k}   : «قدرتِ دلار» (= −basket ⇒ >0 یعنی دلار قوی، طلا نزولی)
      mp_agree_{k}        : چند جفت از ۴ جفت با صعودِ طلا موافق‌اند (0..1) — «رأیِ اکثریت»
      mp_conc_ret         : بازدهِ هم‌زمانِ سبد در همین کندل (تأییدِ لحظه‌ای جهت)
      mp_align_long       : ۱ اگر اکثریتِ سبد (≥۳ از ۴) با صعودِ طلا موافق (گیتِ long)
      mp_align_short      : ۱ اگر اکثریتِ سبد با نزولِ طلا موافق (گیتِ short)
    """
    if pairs is None:
        pairs = list(_PAIR_SIGN.keys())
    n = len(xau_df)
    aligned = {}
    for nm in pairs:
        fn = _PAIR_FILE.get(nm)
        p = os.path.join(_DATA, fn)
        if fn is None or not os.path.exists(p):
            continue
        aligned[nm] = _aligned_close(xau_df, _load(fn), nm)

    f = pd.DataFrame(index=xau_df.index)
    if not aligned:
        return f

    # سیگنالِ سبد در افق‌های مختلف
    for k in [4, 8, 16]:
        comp = np.zeros(n); cnt = np.zeros(n)
        agree = np.zeros(n); agree_cnt = np.zeros(n)
        for nm, c in aligned.items():
            r = (pd.Series(c) / pd.Series(c).shift(k) - 1).values
            z = (r - np.nanmean(r)) / (np.nanstd(r) + 1e-12)
            sgn = _PAIR_SIGN[nm]
            valid = np.isfinite(z)
            comp[valid] += sgn * z[valid]      # جهتِ طلا از منظر این جفت
            cnt[valid] += 1
            # رأیِ جهت: آیا این جفت با صعودِ طلا موافق است؟
            vote_up = (sgn * r) > 0
            agree[valid & vote_up] += 1
            agree_cnt[valid] += 1
        basket = np.where(cnt > 0, comp / np.maximum(cnt, 1), np.nan)
        f[f'mp_basket_ret_{k}'] = basket
        f[f'mp_dollar_str_{k}'] = -basket
        f[f'mp_agree_{k}'] = np.where(agree_cnt > 0, agree / np.maximum(agree_cnt, 1), np.nan)

    # بازدهِ هم‌زمانِ سبد (k=1) — تأییدِ لحظه‌ای
    comp1 = np.zeros(n); cnt1 = np.zeros(n)
    for nm, c in aligned.items():
        r = pd.Series(c).pct_change().values
        z = (r - np.nanmean(r)) / (np.nanstd(r) + 1e-12)
        valid = np.isfinite(z)
        comp1[valid] += _PAIR_SIGN[nm] * z[valid]; cnt1[valid] += 1
    conc = np.where(cnt1 > 0, comp1 / np.maximum(cnt1, 1), np.nan)
    f['mp_conc_ret'] = conc

    # گیتِ هم‌راستایی (اکثریتِ ≥۳ از ۴ جفت با جهت موافق) — بر اساسِ k=8 (باثبات‌تر)
    agree8 = f['mp_agree_8'].values  # کسرِ موافق با صعودِ طلا
    f['mp_align_long'] = (agree8 >= 0.75).astype(float)
    f['mp_align_short'] = (agree8 <= 0.25).astype(float)
    return f


def coverage(xau_df):
    f = build_multipair_features(xau_df)
    if 'mp_basket_ret_8' not in f:
        return dict(coverage_pct=0.0)
    have = f['mp_basket_ret_8'].notna().sum()
    return dict(total=len(f), aligned=int(have),
                coverage_pct=round(100 * have / len(f), 2))
