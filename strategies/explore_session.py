"""
تحلیل عمیق edge ساعتی: پنجره طلایی شبانه (19-23 UTC).
بررسی احتمال TP-before-SL برای LONG با RR های مختلف در این پنجره،
با و بدون فیلتر روند، تا بهترین ترکیب را برای WR>70% و expectancy>0 پیدا کنیم.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from backtest import load_data, run_backtest, summary_line
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data()
df['hour'] = df['dt'].dt.hour
df['dow'] = df['dt'].dt.dayofweek
atr = ind.atr(df, 14); atr_arr = atr.values
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values
c = df['close'].values

# پنجره طلایی: ساعت شروع در 19..23
hours = df['hour'].values
golden = np.isin(hours, [19, 20, 21, 22, 23])
uptrend = c > ema200  # فیلتر روند صعودی بلندمدت
ema_align = ema50 > ema200

print("جاروب RR برای LONG در پنجره طلایی (19-23 UTC)، spread=0.20$")
print(f"{'filter':<22}{'TP':>4}{'SL':>5}{'trades':>8}{'WR%':>8}{'exp$':>9}{'pnl$':>10}")
print("-"*70)

filters = {
    'golden فقط': golden,
    'golden+uptrend': golden & uptrend,
    'golden+ema_align': golden & ema_align,
}
configs = [
    (1.0, 1.0), (1.5, 1.0), (2.0, 1.0),
    (1.0, 1.5), (1.5, 1.5), (2.0, 2.0),
    (0.75, 1.0), (1.0, 2.0),
]
for fname, fmask in filters.items():
    for tp_m, sl_m in configs:
        entries = fmask.copy()
        # جلوگیری از overlap توسط موتور
        s, t = run_backtest(df, entries, None, None, 'long', spread=0.20,
                            max_hold=32,
                            sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr,
                            allow_overlap=False)
        be = sl_m/(tp_m+sl_m)*100
        flag = " <==" if (s['win_rate']>65 and s['expectancy']>0) else ""
        print(f"{fname:<22}{tp_m:>4.2f}{sl_m:>5.2f}{s['n_trades']:>8}"
              f"{s['win_rate']:>8.2f}{s['expectancy']:>9.3f}{s['total_pnl']:>10.1f}{flag}")
    print()
