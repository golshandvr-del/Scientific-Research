# ============================================================================
# استراتژی ۸۳ — «تشریحِ مغزِ نزولیِ زندهٔ سایت به تفکیکِ روزِ هفته و سشن»
# ----------------------------------------------------------------------------
# پاسخِ مستقیم به User Note 2:
#   «سایت دو معاملهٔ SHORT داد و هر دو SL خوردند (−۱۲$ و −۱۶$). آیا استراتژی
#    واقعاً کار می‌کند؟ آیا چون روزِ جمعه یا سشنِ نیویورک است رفتار
#    غیرقابل‌پیش‌بینی شده؟ آیا در دادهٔ تاریخی این اثبات می‌شود؟»
#
# نکتهٔ کلیدیِ کشف‌شده پیش از این تحلیل:
#   موتورِ زندهٔ سایت (web_tool/src/signal.ts) SHORT را با یک نسخهٔ **دستیِ**
#   `bearScore` تولید می‌کند (وزن‌های hand-tuned)، نه با مدلِ ML که در S31
#   بک‌تست شد (PF=۱.۴۹). یعنی «آنچه سایت اجرا می‌کند» هرگز مستقلاً بک‌تست نشده.
#   این اسکریپت دقیقاً همان bearScore سایت را بازتولید و روی ۱۵۰k کندل تست می‌کند،
#   سپس نتیجه را به تفکیکِ روزِ هفته (به‌ویژه جمعه) و سشنِ UTC می‌شکند.
#
# هدف (طبقِ قانونِ پروژه): سنجشِ «سودِ خالص» این جریانِ SHORT، نه صرفاً WR.
# ============================================================================
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, rsi, atr, macd

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'XAUUSD_M15.csv')
SPREAD = 0.20          # اسپردِ واقعیِ طلا (دلار)
LOT_USD_PER_DOLLAR = 1 # هر $ حرکت × ۰.۰۱ لات ≈ ۱$؛ برای مقایسهٔ نسبی exp کافی است

# ---- پارامترهای دقیقِ مغزِ نزولیِ سایت (کپیِ مو‌به‌مو از signal.ts) ----
ENTRY_THRESHOLD = 60   # آستانهٔ احتمال
TP_M = 1.4             # مغز نزولی: TP = 1.4×ATR
SL_M = 1.7             # مغز نزولی: SL = 1.7×ATR
HORIZON = 96           # حداکثر کندل نگه‌داری (۹۶×۱۵m = ۲۴ ساعت)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def build():
    df = pd.read_csv(DATA)
    df.columns = [c.strip().lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['dow'] = df['dt'].dt.dayofweek          # 0=دوشنبه ... 4=جمعه ... 6=یکشنبه
    df['hour'] = df['dt'].dt.hour              # ساعتِ UTC

    # اندیکاتورها — دقیقاً مانند signal.ts
    df['ema20'] = ema(df['close'], 20)
    df['ema50'] = ema(df['close'], 50)
    df['ema100'] = ema(df['close'], 100)
    df['ema200'] = ema(df['close'], 200)
    df['rsi14'] = rsi(df['close'], 14)
    df['atr'] = atr(df, 14)
    macd_line, macd_sig, macd_hist = macd(df['close'])
    df['macd_hist'] = macd_hist

    # VWAP روزانهٔ لنگرشده (session-anchored روی روزِ UTC) — مانند features.py
    df['day'] = df['dt'].dt.floor('D')
    tp = (df['high'] + df['low'] + df['close']) / 3.0
    pv = tp * df['volume']
    df['cum_pv'] = pv.groupby(df['day']).cumsum()
    df['cum_v'] = df['volume'].groupby(df['day']).cumsum()
    df['vwap'] = df['cum_pv'] / df['cum_v'].replace(0, np.nan)

    # ADX ساده (۱۴) — برای بازتولیدِ adxContrib
    df['adx'] = compute_adx(df, 14)
    # DI diff
    df['pdi'], df['mdi'] = compute_di(df, 14)
    # vol z-score (۲۰)
    vm = df['volume'].rolling(20).mean()
    vs = df['volume'].rolling(20).std()
    df['vol_z'] = (df['volume'] - vm) / vs.replace(0, np.nan)

    return df.dropna().reset_index(drop=True)


def compute_adx(df, period=14):
    up = df['high'].diff()
    dn = -df['low'].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1/period, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr_.replace(0, np.nan)
    mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr_.replace(0, np.nan)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/period, adjust=False).mean()


def compute_di(df, period=14):
    up = df['high'].diff()
    dn = -df['low'].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1/period, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr_.replace(0, np.nan)
    mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / atr_.replace(0, np.nan)
    return pdi, mdi


def bear_probability(row):
    """بازتولیدِ مو‌به‌مویِ bearScore در signal.ts."""
    price = row['close']; e50 = row['ema50']; e200 = row['ema200']
    atr_v = row['atr']; vwap = row['vwap']; r = row['rsi14']
    a = row['adx']; mh = row['macd_hist']
    diDiff = row['pdi'] - row['mdi']

    bearRegimeOk = (price < e50) and (e50 < e200)
    vwapDistAtr = (price - vwap) / atr_v if atr_v else 0
    ema50DistAtr = (price - e50) / atr_v if atr_v else 0

    s = 0.12
    s += 0.55 if bearRegimeOk else -1.2
    if -1.0 <= vwapDistAtr <= 0.5: s += 0.35
    elif vwapDistAtr < -2.0: s -= 0.30
    if -2.0 <= ema50DistAtr <= 0: s += 0.22
    elif ema50DistAtr < -3.5: s -= 0.25
    if 35 <= r <= 55: s += 0.25
    elif r < 25: s -= 0.30
    elif r > 65: s -= 0.10
    if 20 <= a <= 45: s += 0.20
    elif a < 15: s -= 0.12
    s += 0.15 if mh < 0 else -0.10
    s += 0.10 if diDiff < 0 else -0.10

    rawP = sigmoid(s * 1.15)
    prob = max(30, min(78, 42 + rawP * 34))
    return prob, bearRegimeOk


def backtest(df):
    """شبیه‌سازیِ SHORTهای مغزِ نزولیِ سایت روی کل تاریخ."""
    trades = []
    n = len(df)
    high = df['high'].values; low = df['low'].values
    i = 0
    while i < n - 1:
        row = df.iloc[i]
        prob, bearOk = bear_probability(row)
        if bearOk and prob >= ENTRY_THRESHOLD and row['atr'] > 0:
            entry = df.iloc[i + 1]['open'] + SPREAD  # ورود در open بعدی + اسپرد (بدترین حالتِ short)
            atr_v = row['atr']
            tp = entry - TP_M * atr_v
            sl = entry + SL_M * atr_v
            outcome = None; exit_price = None; bars = 0
            for j in range(i + 1, min(i + 1 + HORIZON, n)):
                bars = j - i
                if high[j] >= sl:      # SL نزولی بالاست
                    outcome = 'loss'; exit_price = sl; break
                if low[j] <= tp:       # TP نزولی پایین است
                    outcome = 'win'; exit_price = tp; break
            if outcome is None:
                exit_price = df.iloc[min(i + HORIZON, n - 1)]['close']
                outcome = 'win' if exit_price < entry else 'loss'
            pnl = (entry - exit_price)  # SHORT: سود وقتی exit < entry
            trades.append({
                'idx': i, 'dow': int(row['dow']), 'hour': int(row['hour']),
                'entry': entry, 'exit': exit_price, 'pnl': pnl,
                'win': outcome == 'win', 'bars': bars, 'prob': prob,
            })
            i = j  # پرش به بعد از خروج (بدون هم‌پوشانی)
        else:
            i += 1
    return pd.DataFrame(trades)


DOW_FA = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه']


def sess_name(h):
    # سشن‌های تقریبی UTC
    if 0 <= h < 7:   return '1-آسیا'
    if 7 <= h < 12:  return '2-لندن'
    if 12 <= h < 17: return '3-هم‌پوشانیِ لندن/نیویورک'
    if 17 <= h < 21: return '4-نیویورک'
    return '5-پایانِ‌روز/کم‌عمق'


def report(tr):
    def stats(g):
        n = len(g)
        if n == 0: return (0, 0, 0, 0)
        wr = 100 * g['win'].mean()
        net = g['pnl'].sum()
        exp = g['pnl'].mean()
        return (n, wr, net, exp)

    print('=' * 74)
    print('  استراتژی ۸۳ — مغزِ نزولیِ زندهٔ سایت روی ۱۵۰k کندل XAUUSD M15')
    print('=' * 74)
    N, WR, NET, EXP = stats(tr)
    print(f'\n  کل: n={N}  WR={WR:.1f}%  سودِ خالص(نسبی $)={NET:+.1f}  exp/trade={EXP:+.3f}$')
    print(f'  دورهٔ داده: {tr.shape[0]} معاملهٔ SHORT در ~۶ سال')

    print('\n  --- به تفکیکِ روزِ هفته ---')
    print(f'  {"روز":<12}{"n":>6}{"WR%":>8}{"سودِخالص$":>14}{"exp$":>10}')
    for d in range(7):
        g = tr[tr['dow'] == d]
        n, wr, net, exp = stats(g)
        if n > 0:
            flag = '  ← جمعه' if d == 4 else ''
            print(f'  {DOW_FA[d]:<12}{n:>6}{wr:>8.1f}{net:>14.1f}{exp:>10.3f}{flag}')

    print('\n  --- به تفکیکِ سشنِ UTC ---')
    tr = tr.copy()
    tr['sess'] = tr['hour'].map(sess_name)
    print(f'  {"سشن":<28}{"n":>6}{"WR%":>8}{"سودِخالص$":>14}{"exp$":>10}')
    for s in sorted(tr['sess'].unique()):
        g = tr[tr['sess'] == s]
        n, wr, net, exp = stats(g)
        print(f'  {s:<28}{n:>6}{wr:>8.1f}{net:>14.1f}{exp:>10.3f}')

    # نکتهٔ ویژه: جمعهٔ سشنِ نیویورک (همان شرایطِ کاربر)
    print('\n  --- تمرکز: جمعه × سشن نیویورک/هم‌پوشانی (شرایطِ گزارشِ کاربر) ---')
    fri_ny = tr[(tr['dow'] == 4) & (tr['hour'] >= 12)]
    n, wr, net, exp = stats(fri_ny)
    print(f'  جمعه بعد از ۱۲UTC: n={n}  WR={wr:.1f}%  سودِخالص={net:+.1f}$  exp={exp:+.3f}$')
    other = tr[~((tr['dow'] == 4) & (tr['hour'] >= 12))]
    n2, wr2, net2, exp2 = stats(other)
    print(f'  بقیهٔ اوقات:        n={n2}  WR={wr2:.1f}%  سودِخالص={net2:+.1f}$  exp={exp2:+.3f}$')
    print('=' * 74)
    return tr


if __name__ == '__main__':
    print('در حالِ ساختِ اندیکاتورها روی ۱۵۰k کندل ...')
    df = build()
    print(f'داده آماده: {len(df)} کندل. در حالِ بک‌تستِ مغزِ نزولیِ سایت ...')
    tr = backtest(df)
    if len(tr) == 0:
        print('هیچ سیگنالِ SHORTی تولید نشد.')
    else:
        report(tr)


# ============================================================================
# بخشِ دوم — آزمونِ دو بهبودِ ساده (طبقِ کشفِ روز/سشن):
#   الف) فیلترِ سشن: حذفِ سشنِ «پایانِ‌روز/کم‌عمق» (۲۱–۲۴ UTC، exp=−0.95$)
#   ب) فیلترِ احتمال: آستانهٔ سخت‌تر (مثل مدلِ ML که در S31 exp را ۱۲× کرد)
# هدف: آیا با فیلترِ ساده «سودِ خالص» جریانِ SHORT سایت معنادار بهتر می‌شود؟
# ============================================================================
def improvement_sweep(df):
    tr = backtest(df)
    print('\n' + '=' * 74)
    print('  بخشِ دوم — اثرِ فیلترهای ساده بر سودِ خالصِ SHORT')
    print('=' * 74)
    base_n = len(tr); base_net = tr['pnl'].sum(); base_exp = tr['pnl'].mean()
    base_wr = 100 * tr['win'].mean()
    print(f'  پایه (سایت فعلی):            n={base_n:>5}  WR={base_wr:.1f}%  خالص={base_net:+.1f}$  exp={base_exp:+.3f}$')

    # الف) حذفِ سشنِ پایانِ‌روز (ساعت ۲۱–۲۴)
    f1 = tr[tr['hour'] < 21]
    print(f'  + حذفِ سشنِ پایانِ‌روز(≥۲۱):    n={len(f1):>5}  WR={100*f1["win"].mean():.1f}%  خالص={f1["pnl"].sum():+.1f}$  exp={f1["pnl"].mean():+.3f}$')

    # ب) آستانهٔ احتمالِ سخت‌تر
    for thr in [62, 65, 68, 70]:
        f = tr[(tr['hour'] < 21) & (tr['prob'] >= thr)]
        if len(f) > 30:
            print(f'  + حذفِ پایانِ‌روز و prob≥{thr}:    n={len(f):>5}  WR={100*f["win"].mean():.1f}%  خالص={f["pnl"].sum():+.1f}$  exp={f["pnl"].mean():+.3f}$')
    print('=' * 74)


if __name__ == '__main__' and '--sweep' in sys.argv:
    df2 = build()
    improvement_sweep(df2)
