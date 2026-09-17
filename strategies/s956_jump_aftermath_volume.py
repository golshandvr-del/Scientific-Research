# =============================================================================
# S956 — «جهشِ هم‌راستا با تأییدِ حجم» (S950 × RVOL_slot ≥ 1.0)
# پیش‌ثبت: results/S956_PREREG_jump_aftermath_volume_confirmed.md (قبل از هر آزمون)
# دانشمند: Robert Merton (باند S950–S959) — فقط اکتشاف؛ هیچ تغییری در سایت
#
# پایهٔ منجمد: S950 (features/member_signals import) + drift(89) هم‌راستا
# گیت: RVOL_slot[t] = vol[t] / median(vol of previous 30 bars with same hour-of-day),
#       min_periods=20, shift(1) درون گروه — تعریفِ S589 عیناً (پیاده‌سازی numpy کم‌حافظه)
# سه بازو: base (S950) · vol (لایه) · lowvol (کنترل P2) · n_trials=35
# =============================================================================
import sys, os, json, gc
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
import pandas as pd

from engine import scalp_engine as se, rqs2
from tools import s434_fast_data as fd
from strategies.s950_jump_aftermath import features, member_signals, BV_WIN, MAX_HOLD
from strategies.s951_compression_breakout import build_null_perm   # کانونی (اصلاح‌شده)

K_JUMP = 2.6
SL_K = 2.058
SLOT_WIN = 30
SLOT_MINP = 20
RVOL_THR = 1.0
N_TRIALS = 35
SEED = 20260910
K_PERM = 2000
SPLIT_FRAC = 0.60          # عین S950
OUT_DIR = 'results/_scan_S956'
os.makedirs(OUT_DIR, exist_ok=True)

TFS = ['H8', 'H6', 'H12', 'D1', 'H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15',
       'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M2', 'M1']


def rvol_slot(volume, hour):
    """عینِ S589: v[t] / median(v[previous SLOT_WIN bars with same hour]), shift(1) درون گروه."""
    v = pd.Series(np.asarray(volume, dtype=np.float64))
    h = pd.Series(np.asarray(hour))
    ref = v.groupby(h).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    ref = ref.replace(0, np.nan).values
    with np.errstate(divide='ignore', invalid='ignore'):
        return v.values / ref


def arm_metrics(tr):
    if tr is None or len(tr) == 0:
        return dict(n=0)
    pnl = tr['pnl_pip'].values
    wins = pnl[pnl > 0].sum(); loss = -pnl[pnl <= 0].sum()
    return dict(n=int(len(tr)), wr=round(100 * float((pnl > 0).mean()), 2),
                pf=round(float(wins / loss), 3) if loss > 0 else 999.0,
                net_pip=round(float(pnl.sum()), 1))


def judge(df, ls, ss, sl_arr, sl_med, split, label):
    tr = se.simulate_trades(df, ls, ss, sl_arr, sl_arr, 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=False)
    out = dict(arm=label, **arm_metrics(tr))
    if len(tr) < 30:
        out['verdict'] = 'NO-CANDIDATE'
        return out
    null = build_null_perm(df, ls, ss, MAX_HOLD, K=K_PERM, seed=SEED)
    rq = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=sl_med,
                           bar_time=df['time'].values, null=null,
                           n_trials=N_TRIALS, split_bar=split,
                           close=df['close'].values)
    m = rq['metrics']
    out.update(verdict=rq['verdict'], rqs2_score=rq['rqs2_score'],
               gates={g: (None if v is None else bool(v)) for g, v in rq['gates'].items()},
               lift_pp=m.get('skill_lift_pp'), skill_z=m.get('skill_z'),
               p_perm=m.get('skill_p_perm'), pf_engine=m.get('profit_factor'),
               maxdd=m.get('max_dd_pct'), notes=rq.get('notes'))
    return out


def judge_tf(tf):
    out_path = f'{OUT_DIR}/{tf}.json'
    if os.path.exists(out_path):
        print(f'[{tf}] checkpoint موجود — رد می‌شوم', flush=True); return
    try:
        d = fd.load_fast('XAUUSD', tf)
    except Exception as ex:
        json.dump(dict(tf=tf, error=str(ex)), open(out_path, 'w'), ensure_ascii=False)
        print(f'[{tf}] ERROR: {ex}', flush=True); return
    hour = d['hour'].astype(np.int8) if 'hour' in d else \
        (pd.to_datetime(d['time'], unit='s').hour.values.astype(np.int8))
    for kx in ('minute', 'dow', 'hour'):
        d.pop(kx, None)
    rv = rvol_slot(d['volume'], hour)
    del hour; gc.collect()
    df = fd.as_dataframe(d)
    pip = se.ASSETS['XAUUSD']['pip']
    c = df['close'].values.astype(np.float64)
    n = len(c)
    r, sbv, atr_px = features(df)
    ls0, ss0 = member_signals(r, sbv, K_JUMP, 'continuation', warm=BV_WIN + 2)
    del r, sbv
    drift = np.zeros(n)
    drift[BV_WIN + 1:] = c[BV_WIN:-1] - c[:-(BV_WIN + 1)]
    ls_base = ls0 & (drift > 0); ss_base = ss0 & (drift < 0)
    del ls0, ss0, drift; gc.collect()
    sl_arr = np.maximum(SL_K * atr_px / pip, 1e-9)
    del atr_px
    ok = np.isfinite(rv)
    hi = ok & (rv >= RVOL_THR); lo = ok & (rv < RVOL_THR)
    del rv; gc.collect()
    # پایه فقط جایی که گیت قابل‌محاسبه است (مقایسهٔ منصفانهٔ P1)
    ls_base &= ok; ss_base &= ok
    n_base = int(ls_base.sum() + ss_base.sum())
    ls_v, ss_v = ls_base & hi, ss_base & hi
    ls_l, ss_l = ls_base & lo, ss_base & lo
    n_vol = int(ls_v.sum() + ss_v.sum())
    pass_rate = round(100 * n_vol / n_base, 1) if n_base else None
    split = int(n * SPLIT_FRAC)
    tr_tmp = se.simulate_trades(df, ls_v, ss_v, sl_arr, sl_arr, 'XAUUSD',
                                max_hold=MAX_HOLD, allow_overlap=False)
    sl_med = float(np.median(tr_tmp['sl_pip'].values)) if len(tr_tmp) else float(np.nanmedian(sl_arr[BV_WIN + 2:]))
    del tr_tmp
    res = dict(tf=tf, src=d['src'], n_bars=n, n_trials=N_TRIALS, rvol_thr=RVOL_THR,
               slot_win=SLOT_WIN, n_sig_base=n_base, n_sig_vol=n_vol,
               pass_rate_pct=pass_rate, sl_med=round(sl_med, 1))
    res['vol'] = judge(df, ls_v, ss_v, sl_arr, sl_med, split, 'vol')
    res['base'] = judge(df, ls_base, ss_base, sl_arr, sl_med, split, 'base_S950')
    res['lowvol'] = judge(df, ls_l, ss_l, sl_arr, sl_med, split, 'lowvol_control')
    res['entry_idx_vol'] = np.where(ls_v | ss_v)[0].tolist()
    lv, lb = res['vol'].get('lift_pp'), res['base'].get('lift_pp')
    res['P1_gate_adds_info'] = (lv is not None and lb is not None and lv > lb)
    wv, wl = res['vol'].get('wr'), res['lowvol'].get('wr')
    res['P2_lowvol_weaker'] = (wv is not None and wl is not None and wl < wv)
    res['P3_pass_rate_alive'] = (pass_rate is not None and 30 <= pass_rate <= 85)
    res['verdict'] = res['vol']['verdict']; res['rqs2_score'] = res['vol'].get('rqs2_score')
    json.dump(res, open(out_path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(f"[{tf}] VOL {res['vol'].get('verdict')} {res['vol'].get('rqs2_score')} "
          f"n={res['vol'].get('n')} wr={wv} lift={lv} z={res['vol'].get('skill_z')} | "
          f"BASE {res['base'].get('verdict')} {res['base'].get('rqs2_score')} lift={lb} | "
          f"LOWVOL wr={wl} lift={res['lowvol'].get('lift_pp')} | pass={pass_rate}% "
          f"P1={res['P1_gate_adds_info']} P2={res['P2_lowvol_weaker']} P3={res['P3_pass_rate_alive']}", flush=True)
    del df, d, ls_base, ss_base, ls_v, ss_v, ls_l, ss_l, hi, lo, ok, sl_arr; gc.collect()


if __name__ == '__main__':
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for tf in (only or TFS):
        judge_tf(tf); gc.collect()
    print('S956 scan تمام شد.', flush=True)
