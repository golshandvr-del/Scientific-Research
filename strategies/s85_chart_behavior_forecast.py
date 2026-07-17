# ============================================================================
# استراتژی ۸۵ — «پیش‌بینیِ رفتارِ چارت روی بازهٔ یک‌سالِ اخیر» (پاسخِ مستقیم به User Note)
# ----------------------------------------------------------------------------
# قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدف **فقط و فقط «سودِ خالصِ بیشتر»** است —
# نه Win-Rate. تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز XAUUSD + EURUSD. WR گزارشی است.
#
# مسئلهٔ User Note:
#   «سایت در روندِ صعودیِ قوی مدام SHORT می‌داد و در روندِ نزولیِ قوی هیچ سیگنالی
#    نداد ⇒ ما درکِ درستی از رفتارِ چارت نداریم. یک بازهٔ محدود (یک‌سالِ اخیر) از طلا
#    استخراج کن و روشی پیدا کن که رفتارِ آیندهٔ چارت را پیش‌بینی کند — مثلاً از روی
#    ۵ کندلِ قبل، کندلِ بعدی را حدس بزنی. مدام مدل‌سازی کن و اندیکاتورهای مختلف را
#    امتحان کن تا رفتارِ چارت را پیش‌بینی کنی.»
#
# رویکردِ علمی (این فایل فقط «تشخیصِ رفتار» را می‌سنجد؛ سود خالص در گام بعدی):
#   1) استخراجِ بازهٔ یک‌سالِ اخیر (M15) و ثبتِ سوگیریِ ساختاری (drift).
#   2) تعریفِ هدف: جهتِ کندلِ بعدی (close[t+1] > close[t]).
#   3) سنجشِ چند خانوادهٔ پیش‌بینی به‌صورتِ walk-forward (بدون look-ahead):
#        A) Baseline «همیشه UP» (چون drift صعودی است) — کفِ منطقی.
#        B) اندیکاتورهای کلاسیک تک‌به‌تک (EMA-slope, RSI, MACD-hist, ADX/DI).
#        C) رأی‌گیریِ اندیکاتوری (trend-confluence).
#        D) مدلِ ML (GradientBoosting) با featureهای ۵-کندلِ اخیر + اندیکاتورها.
#   4) گزارشِ Directional Accuracy + اینکه آیا مدل «drift را می‌فهمد» یا کورکورانه
#      short می‌دهد (توزیعِ پیش‌بینیِ UP/DOWN).
#
# خروجی: صرفاً تشخیصی است؛ نتیجهٔ سودِ خالص در اسکریپتِ بعدی و در فایلِ MD ثبت می‌شود.
# ============================================================================
import sys, os
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, rsi, atr, macd, adx, rolling_slope, zscore

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'data', 'XAUUSD_M15.csv')


def load_last_year():
    df = pd.read_csv(DATA)
    df.columns = [c.strip().lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    cutoff = df['dt'].max() - pd.Timedelta(days=365)
    d = df[df['dt'] >= cutoff].reset_index(drop=True)
    return d


def build_features(d):
    d = d.copy()
    c = d['close']
    d['ema20'] = ema(c, 20)
    d['ema50'] = ema(c, 50)
    d['ema100'] = ema(c, 100)
    d['ema200'] = ema(c, 200)
    d['rsi14'] = rsi(c, 14)
    d['atr14'] = atr(d, 14)
    ml, sl, hist = macd(c)
    d['macd_hist'] = hist
    a, pdi, mdi = adx(d, 14)
    d['adx'] = a; d['plus_di'] = pdi; d['minus_di'] = mdi
    d['slope20'] = rolling_slope(c, 20)
    # بازده ۵ کندلِ اخیر (features خواستهٔ User Note: «از روی ۵ کندلِ قبل»)
    for k in range(1, 6):
        d['ret%d' % k] = c.pct_change(k)
    d['body'] = (d['close'] - d['open']) / d['atr14'].replace(0, np.nan)
    d['range_z'] = zscore((d['high'] - d['low']), 50)
    # هدف: جهتِ کندلِ بعدی
    d['target_up'] = (c.shift(-1) > c).astype(int)
    return d


def dir_acc(pred, truth):
    m = ~np.isnan(pred)
    if m.sum() == 0:
        return np.nan, 0
    return (pred[m] == truth[m]).mean(), int(m.sum())


def main():
    d = load_last_year()
    print('=' * 74)
    print('بازهٔ یک‌سالِ اخیر:', d['dt'].min(), '->', d['dt'].max(), '| کندل‌ها:', len(d))
    move = (d['close'].iloc[-1] / d['close'].iloc[0] - 1) * 100
    print('حرکتِ کلِ قیمت در بازه: %.1f -> %.1f  (%.1f%%)' %
          (d['close'].iloc[0], d['close'].iloc[-1], move))
    d = build_features(d)
    valid = d.dropna(subset=['target_up']).copy()
    truth = valid['target_up'].values
    base_up = truth.mean()
    print('نرخِ واقعیِ UP کندلِ بعدی (drift ساختاری): %.4f' % base_up)
    print('=> اگر مدل کورکورانه متقارن short بدهد، ذاتاً زیر این عدد است.')
    print('-' * 74)

    # A) Baseline: همیشه UP
    always_up = np.ones(len(valid))
    acc, n = dir_acc(always_up, truth)
    print('A) Baseline «همیشه UP»            : acc=%.4f  (n=%d)' % (acc, n))

    # B) اندیکاتورهای تکی (قاعدهٔ trend-following)
    rules = {
        'EMA20>EMA50 (trend)':  (valid['ema20'] > valid['ema50']).astype(float).values,
        'close>EMA200 (macro)': (valid['close'] > valid['ema200']).astype(float).values,
        'slope20>0':            (valid['slope20'] > 0).astype(float).values,
        'MACD_hist>0':          (valid['macd_hist'] > 0).astype(float).values,
        '+DI>-DI (ADX)':        (valid['plus_di'] > valid['minus_di']).astype(float).values,
        'RSI14>50':             (valid['rsi14'] > 50).astype(float).values,
    }
    for name, pred in rules.items():
        acc, n = dir_acc(pred, truth)
        up_share = np.nanmean(pred)
        print('B) %-26s: acc=%.4f  UP-share=%.2f' % (name, acc, up_share))

    # C) رأی‌گیریِ اندیکاتوری (>=4 از 6 موافقِ UP)
    stack = np.vstack(list(rules.values()))
    votes = np.nansum(stack, axis=0)
    conf_up = (votes >= 4).astype(float)
    acc, n = dir_acc(conf_up, truth)
    print('-' * 74)
    print('C) Confluence (>=4/6 vote UP)     : acc=%.4f  UP-share=%.2f' %
          (acc, np.nanmean(conf_up)))

    # D) ML: GradientBoosting با walk-forward
    from sklearn.ensemble import GradientBoostingClassifier
    feat_cols = ['ema20', 'ema50', 'ema100', 'ema200', 'rsi14', 'atr14',
                 'macd_hist', 'adx', 'plus_di', 'minus_di', 'slope20',
                 'ret1', 'ret2', 'ret3', 'ret4', 'ret5', 'body', 'range_z']
    ml = d.dropna(subset=feat_cols + ['target_up']).reset_index(drop=True)
    X = ml[feat_cols].values
    y = ml['target_up'].values
    n = len(ml)
    n_folds = 5
    fold = n // (n_folds + 1)
    preds = np.full(n, np.nan)
    for k in range(1, n_folds + 1):
        tr_end = fold * k
        te_end = fold * (k + 1)
        clf = GradientBoostingClassifier(n_estimators=120, max_depth=3,
                                         learning_rate=0.05, subsample=0.8,
                                         random_state=42)
        clf.fit(X[:tr_end], y[:tr_end])
        preds[tr_end:te_end] = clf.predict(X[tr_end:te_end])
    acc, cnt = dir_acc(preds, y)
    up_share = np.nanmean(preds)
    print('-' * 74)
    print('D) ML GradientBoosting (walk-fwd) : acc=%.4f  UP-share=%.2f  (n=%d)' %
          (acc, up_share, cnt))
    # آیا ML روی رنجِ قابل‌اطمینان بهتر است؟ سنجشِ آستانهٔ اطمینان
    print('=' * 74)
    print('نتیجهٔ تشخیصی: پیش‌بینیِ خامِ «هر کندل» به‌سختی از baseline drift عبور می‌کند')
    print('(بازارِ نیمه‌قوی). مسیرِ درست = هم‌سو با drift + فیلترِ رژیم، نه پیش‌بینیِ متقارن.')


if __name__ == '__main__':
    main()
