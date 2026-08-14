# تشخیص موقت — headroom چندگانگی و ریسک دنباله برای S950-H8
import sys, os
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
from strategies.s950_jump_aftermath import features, run_member, build_null_perm, SPLIT_FRAC, MAX_HOLD
from tools import s434_fast_data as fd
from engine import rqs2

d = fd.load_fast('XAUUSD', 'H8'); df = fd.as_dataframe(d)
r, sbv, atr = features(df)
tr, ls, ss, slp, tpp = run_member(df, r, sbv, atr, 2.6, 'continuation', 2.058, 1.0, 'XAUUSD', 0.1)
sl_med = float(np.median(tr['sl_pip'].values))
null = build_null_perm(df, ls, ss, MAX_HOLD)
split = int(len(df) * SPLIT_FRAC)

res = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=sl_med,
                        bar_time=df['time'].values, null=null, n_trials=24,
                        split_bar=split, close=df['close'].values)
m = res['metrics']
print('z_obs=', m['z_obs'], 'z_luck=', m['z_luck_bound'], 'z_margin=', m['z_margin'])
print('maxDD%=', m['max_dd_pct'], '(cap 8.0)  mcl=', m['max_consec_losses'],
      '/', m['mcl_allowed'], ' recovery=', m['recovery_factor'], '(min 3.0)')
print('top_win_share=', m['top_win_share'], 'max_concurrency=', m['max_concurrency'])

# headroom چندگانگی: با چند trial هنوز H6 پاس می‌ماند؟
for nt in (24, 30, 40, 60, 100, 200):
    r2 = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=sl_med,
                           bar_time=df['time'].values, null=null, n_trials=nt,
                           split_bar=split, close=df['close'].values)
    print(f"n_trials={nt}: H6={r2['gates']['H6']} margin={r2['metrics']['z_margin']}")

# کجای تاریخ DD رخ داد؟
pnl = tr['pnl_pip'].values * 0.1 * 100  # pip→$ (pip=0.1$, contract=100 ⇒ 1pip=10$... check)
print('pnl$ head check: mean=', np.mean(pnl))
eq = np.cumsum(pnl) + 10000
peak = np.maximum.accumulate(eq)
dd = (peak - eq) / peak * 100
i = int(np.argmax(dd))
import pandas as pd
et = pd.to_datetime(tr['entry_time'].values) if 'entry_time' in tr.columns else None
print('maxDD at trade', i, 'of', len(tr), 'dd%=', round(dd[i], 2),
      'time=', et[i] if et is not None else '?')
print('trade columns:', list(tr.columns))
