# =============================================================================
# S955 — «جهشِ هم‌راستا در رژیمِ آرام» (S950 × Calm-σ Gate)
# پیش‌ثبت: results/S955_PREREG_jump_aftermath_calm_regime.md (قبل از هر آزمون)
# دانشمند: Robert Merton (باند S950–S959)
#
# پایهٔ منجمد: S950 (features/member_signals عیناً import) + drift(89) هم‌راستا
# گیت: S605 sigma_series/regime_ratio عیناً import، W=233، calm = reg_t ≤ 1
# یک آزمونِ منجمد در هر کارت؛ n_trials=34 (33 تجمعیِ S950 + 1)
# سه بازو گزارش می‌شود: base (بی‌گیت = S950)، calm (لایهٔ S955)، storm (کنترل P2)
# null کانونی (جای‌گشت علامت) · دو-گذری نیست چون هیچ جست‌وجویی وجود ندارد
# =============================================================================
import sys, os, json, gc
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np

from engine import scalp_engine as se, rqs2
from tools import s434_fast_data as fd
from strategies.s950_jump_aftermath import features, member_signals, BV_WIN, MAX_HOLD
from strategies.s605_engle_sigma_regime import sigma_series, regime_ratio
from strategies.s951_compression_breakout import build_null_perm   # کانونی (اصلاح‌شده)

K_JUMP = 2.6
SL_K = 2.058
W_REG = 233
N_TRIALS = 34
SEED = 20260909
K_PERM = 2000
SPLIT_FRAC = 0.60          # عین S950
OUT_DIR = 'results/_scan_S955'
os.makedirs(OUT_DIR, exist_ok=True)

TFS = ['H8', 'H6', 'H12', 'D1', 'H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15',
       'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M2', 'M1']


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
    for kx in ('hour', 'minute', 'dow'):
        d.pop(kx, None)
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
    # گیت آرامش — عیناً S605
    sig = sigma_series(c)
    reg = regime_ratio(sig, W_REG)
    del sig; gc.collect()
    calm = np.isfinite(reg) & (reg <= 1.0)
    storm = np.isfinite(reg) & (reg > 1.0)
    del reg; gc.collect()
    n_base = int(ls_base.sum() + ss_base.sum())
    ls_c, ss_c = ls_base & calm, ss_base & calm
    ls_s, ss_s = ls_base & storm, ss_base & storm
    n_calm = int(ls_c.sum() + ss_c.sum())
    pass_rate = round(100 * n_calm / n_base, 1) if n_base else None
    split = int(n * SPLIT_FRAC)
    # sl_med از بازوی calm (لایهٔ اصلی)
    tr_tmp = se.simulate_trades(df, ls_c, ss_c, sl_arr, sl_arr, 'XAUUSD',
                                max_hold=MAX_HOLD, allow_overlap=False)
    sl_med = float(np.median(tr_tmp['sl_pip'].values)) if len(tr_tmp) else float(np.nanmedian(sl_arr[BV_WIN+2:]))
    del tr_tmp
    res = dict(tf=tf, src=d['src'], n_bars=n, n_trials=N_TRIALS, w_reg=W_REG,
               n_sig_base=n_base, n_sig_calm=n_calm, pass_rate_pct=pass_rate,
               sl_med=round(sl_med, 1))
    res['calm'] = judge(df, ls_c, ss_c, sl_arr, sl_med, split, 'calm')
    res['base'] = judge(df, ls_base, ss_base, sl_arr, sl_med, split, 'base_S950')
    res['storm'] = judge(df, ls_s, ss_s, sl_arr, sl_med, split, 'storm_control')
    res['entry_idx_calm'] = np.where(ls_c | ss_c)[0].tolist()
    # ابطال‌گرها
    lc, lb = res['calm'].get('lift_pp'), res['base'].get('lift_pp')
    res['P1_gate_adds_info'] = (lc is not None and lb is not None and lc > lb)
    wc, ws = res['calm'].get('wr'), res['storm'].get('wr')
    res['P2_storm_weaker'] = (wc is not None and ws is not None and ws < wc)
    res['P3_pass_rate_alive'] = (pass_rate is not None and 30 <= pass_rate <= 85)
    res['verdict'] = res['calm']['verdict']; res['rqs2_score'] = res['calm'].get('rqs2_score')
    json.dump(res, open(out_path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(f"[{tf}] CALM {res['calm'].get('verdict')} {res['calm'].get('rqs2_score')} "
          f"n={res['calm'].get('n')} wr={res['calm'].get('wr')} lift={lc} z={res['calm'].get('skill_z')} | "
          f"BASE {res['base'].get('verdict')} {res['base'].get('rqs2_score')} lift={lb} | "
          f"STORM wr={ws} lift={res['storm'].get('lift_pp')} | pass={pass_rate}% "
          f"P1={res['P1_gate_adds_info']} P2={res['P2_storm_weaker']} P3={res['P3_pass_rate_alive']}", flush=True)
    del df, d, ls_base, ss_base, ls_c, ss_c, ls_s, ss_s, calm, storm, sl_arr; gc.collect()


if __name__ == '__main__':
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for tf in (only or TFS):
        judge_tf(tf); gc.collect()
    print('S955 scan تمام شد.', flush=True)
