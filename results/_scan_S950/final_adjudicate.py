# S950-H8 drift-aligned — داوریِ نهایی با ۳ seed مدلِ صفر (رویهٔ S356)
# n_trials=33 صادقانه (24 خانواده + 5 BE/trail + 4 دورِ v2). گزارشِ کامل metrics.
import sys, os, json
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
from strategies.s950_jump_aftermath import (features, member_signals,
                                            build_null_perm, SPLIT_FRAC,
                                            MAX_HOLD, BV_WIN)
from tools import s434_fast_data as fd
from engine import scalp_engine as se, rqs2

N_TRIALS = 33
SEEDS = (20260812, 23, 101, 777)

d = fd.load_fast('XAUUSD', 'H8'); df = fd.as_dataframe(d)
src = d['src']
pip = se.ASSETS['XAUUSD']['pip']
c = df['close'].values.astype(np.float64)
r, sbv, atr_px = features(df)
ls0, ss0 = member_signals(r, sbv, 2.6, 'continuation', warm=BV_WIN + 2)
drift = np.zeros(len(c))
drift[BV_WIN + 1:] = c[BV_WIN:-1] - c[:-(BV_WIN + 1)]
ls = ls0 & (drift > 0); ss = ss0 & (drift < 0)
sl_arr = np.maximum(2.058 * atr_px / pip, 1e-9)
tr = se.simulate_trades(df, ls, ss, sl_arr, sl_arr, 'XAUUSD',
                        max_hold=MAX_HOLD, allow_overlap=False)
sl_med = float(np.median(tr['sl_pip'].values))
split = int(len(df) * SPLIT_FRAC)

out = dict(src=src, n_bars=len(df), n_trades=len(tr),
           sl_pip_med=round(sl_med, 1), tp_pip_med=round(sl_med, 1),
           n_trials=N_TRIALS, seeds={})
verdicts = []
for seed in SEEDS:
    null = build_null_perm(df, ls, ss, MAX_HOLD, seed=seed)
    res = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=sl_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS, split_bar=split,
                            close=df['close'].values)
    m = res['metrics']
    verdicts.append(res['verdict'])
    out['seeds'][seed] = dict(verdict=res['verdict'], score=res['rqs2_score'],
                              gates={g: (None if v is None else bool(v))
                                     for g, v in res['gates'].items()},
                              z=m['skill_z'], lift=m['skill_lift_pp'],
                              p_perm=m['skill_p_perm'])
    if seed == SEEDS[0]:
        out['metrics_full'] = {k: (v if not isinstance(v, (dict, list))
                                   else str(v)[:300]) for k, v in m.items()}
        out['notes'] = res['notes']
    print(f"seed={seed}: {res['verdict']} score={res['rqs2_score']} "
          f"z={m['skill_z']} p={m['skill_p_perm']}", flush=True)

out['seed_stable'] = all(v == 'ACCEPT' for v in verdicts)
print('seed_stable =', out['seed_stable'])
# سالانه‌سازی و علتِ برد/باخت — برای گزارش
pnl = tr['pnl_pip'].values
years = (df['time'].values[-1] - df['time'].values[0]) / (365.25 * 86400) \
    if not np.issubdtype(np.asarray(df['time'].values).dtype, np.datetime64) \
    else (df['time'].values[-1] - df['time'].values[0]) / np.timedelta64(1, 'D') / 365.25
out['trades_per_year'] = round(len(tr) / float(years), 1)
out['long_short'] = dict(n_long=int((tr['direction'] == 'long').sum()),
                         n_short=int((tr['direction'] == 'short').sum()))
for side in ('long', 'short'):
    sub = tr[tr['direction'] == side]
    if len(sub):
        out['long_short'][f'wr_{side}'] = round(
            100.0 * float((sub['pnl_pip'] > 0).mean()), 2)
out['hold'] = dict(mean_bars=round(float(tr['bars_held'].mean()), 1),
                   tp_exits=int((tr['outcome'] == 'win').sum()),
                   sl_exits=int((tr['outcome'] == 'loss').sum()),
                   time_exits=int((~tr['outcome'].isin(['win', 'loss'])).sum()))
json.dump(out, open('results/_scan_S950/H8_final.json', 'w'),
          ensure_ascii=False, indent=1, default=str)
print(json.dumps(out['long_short'], ensure_ascii=False),
      out['trades_per_year'], 'tr/yr')
