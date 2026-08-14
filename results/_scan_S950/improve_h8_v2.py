# S950-H8 بهبود v2 — خواهرهای خانواده + فیلتر هم‌راستایی درفت
# n_trials صادقانه: 24 (خانواده) + 5 (BE/trail شکست‌خورده) + 4 (اینجا) = 33
import sys, os, json
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
from strategies.s950_jump_aftermath import (features, member_signals,
                                            build_null_perm, SPLIT_FRAC,
                                            MAX_HOLD, BV_WIN)
from tools import s434_fast_data as fd
from engine import scalp_engine as se, rqs2

N_TRIALS_TOTAL = 33
d = fd.load_fast('XAUUSD', 'H8'); df = fd.as_dataframe(d)
pip = se.ASSETS['XAUUSD']['pip']
c = df['close'].values.astype(np.float64)
r, sbv, atr_px = features(df)
ls0, ss0 = member_signals(r, sbv, 2.6, 'continuation', warm=BV_WIN + 2)
split = int(len(df) * SPLIT_FRAC)

# درفتِ رژیم: علامتِ بازدهِ 89 کندلِ گذشته (فیبوناچی، causal با شیفت 1)
drift = np.zeros(len(c))
drift[BV_WIN + 1:] = c[BV_WIN:-1] - c[:-(BV_WIN + 1)]

def judge(name, ls, ss, a, rr):
    sl_arr = np.maximum(a * atr_px / pip, 1e-9)
    tp_arr = sl_arr * rr
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=False)
    if tr is None or len(tr) < 30:
        print(f'[{name}] too few trades'); return dict(verdict='TOO-FEW')
    null = build_null_perm(df, ls, ss, MAX_HOLD)
    sl_med = float(np.median(tr['sl_pip'].values))
    res = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=sl_med * rr,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS_TOTAL, split_bar=split,
                            close=df['close'].values)
    m = res['metrics']
    failed = [g for g, v in res['gates'].items() if v is False]
    rec = dict(verdict=res['verdict'], score=res['rqs2_score'],
               failed_gates=failed, n=m['n_trades'], wr=m['win_rate'],
               pf=m['profit_factor'], net=m['net_profit'], dd=m['max_dd_pct'],
               mcl=m['max_consec_losses'], lift=m['skill_lift_pp'],
               z=m['skill_z'], p=m['skill_p_perm'],
               recovery=m['recovery_factor'], cd=m.get('counter_drift'))
    print(f"[{name}] {res['verdict']} score={res['rqs2_score']} dd={m['max_dd_pct']}% "
          f"z={m['skill_z']} lift={m['skill_lift_pp']} n={m['n_trades']} "
          f"net=${m['net_profit']} failed={failed}", flush=True)
    return rec

out = {}
# ۱) خواهر a=1.272 rr=1.0
out['sib_a1272'] = judge('sib_a1272', ls0, ss0, 1.272, 1.0)
# ۲) خواهر a=2.058 rr=1.618
out['sib_rr1618'] = judge('sib_rr1618', ls0, ss0, 2.058, 1.618)
# ۳) فیلتر هم‌راستایی: long فقط اگر درفت>0، short فقط اگر درفت<0
ls_al = ls0 & (drift > 0); ss_al = ss0 & (drift < 0)
out['drift_aligned'] = judge('drift_aligned', ls_al, ss_al, 2.058, 1.0)
# ۴) فیلتر خلاف‌راستایی (کنترل — اگر این هم خوب بود، فیلتر بی‌معناست)
ls_ct = ls0 & (drift < 0); ss_ct = ss0 & (drift > 0)
out['drift_counter'] = judge('drift_counter', ls_ct, ss_ct, 2.058, 1.0)

json.dump(out, open('results/_scan_S950/H8_improve_v2.json', 'w'),
          ensure_ascii=False, indent=1, default=str)
