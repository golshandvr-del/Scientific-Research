# S950-H8 بهبود — گرید BE/trail فیبوناچی، شمارش صادقانهٔ چندگانگی
# پایه: k=2.6 continuation a=2.058 rr=1.0 — فقط گیت H8 (maxDD=8.59% > 8.0%) شکست.
# headroom سنجیده‌شده: H6 حتی در n_trials=200 پاس است ⇒ 5 آزمایش اضافه امن است.
import sys, os, json
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
from strategies.s950_jump_aftermath import (features, member_signals,
                                            build_null_perm, SPLIT_FRAC,
                                            MAX_HOLD, BV_WIN)
from tools import s434_fast_data as fd
from engine import scalp_engine as se, rqs2

d = fd.load_fast('XAUUSD', 'H8'); df = fd.as_dataframe(d)
pip = se.ASSETS['XAUUSD']['pip']
r, sbv, atr_px = features(df)
ls, ss = member_signals(r, sbv, 2.6, 'continuation', warm=BV_WIN + 2)
sl_arr = np.maximum(2.058 * atr_px / pip, 1e-9)
tp_arr = sl_arr * 1.0
null = build_null_perm(df, ls, ss, MAX_HOLD)
split = int(len(df) * SPLIT_FRAC)

# ۲۴ عضو اصلی + ۵ واریانت بهبود = ۲۹ آزمایش
N_TRIALS_TOTAL = 24 + 5
VARIANTS = [
    ('base',        dict()),
    ('be382',       dict(be_frac=0.382)),
    ('be618',       dict(be_frac=0.618)),
    ('trail786',    dict(trail_frac=0.786)),
    ('be618_tr786', dict(be_frac=0.618, trail_frac=0.786)),
]

out = {}
for name, kw in VARIANTS:
    be = kw.get('be_frac')
    trl = kw.get('trail_frac')
    # موتور اسکالر می‌خواهد برای be/trail — از میانهٔ SL استفاده می‌کنیم
    sl_med0 = float(np.median(sl_arr[np.where(ls | ss)[0]]))
    be_pip = sl_med0 * be if be else None
    trail_pip = sl_med0 * trl if trl else None
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=False,
                            be_trigger_pip=be_pip, trail_pip=trail_pip)
    if tr is None or len(tr) == 0:
        out[name] = dict(verdict='NO-TRADES'); continue
    sl_med = float(np.median(tr['sl_pip'].values))
    res = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=sl_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS_TOTAL, split_bar=split,
                            close=df['close'].values)
    m = res['metrics']
    failed = [g for g, v in res['gates'].items() if v is False]
    out[name] = dict(verdict=res['verdict'], score=res['rqs2_score'],
                     failed_gates=failed, n=m['n_trades'], wr=m['win_rate'],
                     pf=m['profit_factor'], net=m['net_profit'],
                     dd=m['max_dd_pct'], lift=m['skill_lift_pp'],
                     z=m['skill_z'], p=m['skill_p_perm'],
                     recovery=m['recovery_factor'])
    print(f"[{name}] {res['verdict']} score={res['rqs2_score']} "
          f"dd={m['max_dd_pct']}% z={m['skill_z']} lift={m['skill_lift_pp']} "
          f"n={m['n_trades']} net=${m['net_profit']} failed={failed}", flush=True)

json.dump(out, open('results/_scan_S950/H8_improve.json', 'w'),
          ensure_ascii=False, indent=1, default=str)
