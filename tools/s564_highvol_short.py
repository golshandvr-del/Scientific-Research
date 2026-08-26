# -*- coding: utf-8 -*-
"""
s564_highvol_short.py — شورت مکمل روی روزهای گپ-منفی پرنوسان (M15/H1) — مسیر C

پیش‌ثبت: results/S564_PREREG_GAPOPEN_HIGHVOL_SHORT_XAUUSD.md (کامیت 400768b4 —
قبل از هر تست). روز-رویداد = مکمل دقیق S562:
  ماسک پایهٔ S560 (گپ منفی بزرگ) ∧ NOT(فیلتر V با qv قفل‌شدهٔ S562)
  یعنی دقیقاً روزهایی که S562 به‌خاطر رژیم پرنوسان «رد» می‌کرد.

جهت: فقط SHORT از open کندل دوم روز (همان مکانیک ورود S560، جهت معکوس).
هندسه: SL=TP=q80(|move|) روی نیمهٔ اول همین زیرمجموعه (قاعدهٔ ثابت، بدون جاروب).
بازوها: hold ∈ {h_S560, 2×h_S560} per-TF → 4 بازو → n_trials = 421+4 = **425**.

قواعد توقف صادقانه (پیش‌ثبت §3):
  n نیمهٔ اول < 30 در هر دو TF ⇒ NO-VERDICT (قید ۲)
  بهترین بازوی TF: lift نیمهٔ اول < +4pp نسبت به null شورت ⇒ STOPPED_DEAD
  (نیمهٔ دوم باکره می‌ماند — الگوی S613/S533)

null: شورت غیرشرطی صادقانه (درس S522) — 50000 ورود شورت + K=500 جایگشت.
گاردها: BUG-PERMK · BUG-NULLUNCOND · BUG-SCOREKEY · BUG-PIPGUESS ·
BUG-DATASETDRIFT · BUG-GEOMDRIFT · BUG-BRKTHRESH · قید ۲.
M30 ممنوع (قلمرو S404) · M1/M5 ممنوع (ACCEPT قطعی S560) · EURUSD ممنوع (کاربر).

اجرا:
  python3 tools/s564_highvol_short.py lock  M15
  python3 tools/s564_highvol_short.py judge M15
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from engine.rqs2 import compute_rqs2, n_required_for_h3    # noqa: E402
from tools.s560_gapopen_explore import SPLIT_UTC           # noqa: E402
from tools.s560_adjudicate import build                    # noqa: E402
from tools.s562_volfilter import vol_filter_mask           # noqa: E402

N_TRIALS = 425          # پیش‌ثبت S564 §2 — انباشتهٔ صادقانهٔ خانواده
N_PERM = 500
SEED = 20260826
ALLOWED_TFS = ('M15', 'H1')
QV_LOCKED = {'M15': 85, 'H1': 78}     # عیناً قفل S562 — صفر درجهٔ آزادی جدید
OUT = os.path.join(ROOT, 'results', '_s564_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')
S560_LOCK = os.path.join(ROOT, 'results', '_s560_arms', 'locked_config.json')
S562_LOCK = os.path.join(ROOT, 'results', '_s562_arms', 'locked_config.json')
LIFT_STOP = 4.0         # سد توقف پیش‌ثبت‌شده (pp)


def _check_tf(tf: str):
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ پیش‌ثبت S564 (فقط M15/H1)')


def complement_mask(d, tf, mask):
    """روزهای مکمل: سیگنال پایهٔ S560 که فیلتر V قفل‌شدهٔ S562 آن را رد می‌کند."""
    s562 = json.load(open(S562_LOCK))
    qv = int(s562[tf]['arms'][s562[tf]['picked']]['qv'])
    assert qv == QV_LOCKED[tf], 'BUG-GEOMDRIFT: qv ناهمسان با قفل S562'
    passed = vol_filter_mask(d, tf, mask, qv)
    comp = mask & ~passed
    # سازگاری با قفل S562: pass + reject == base (سیگنال‌های بدون تاریخچه هم رد=مکمل نیستند؟
    # خیر — طبق تعریف S562، «بدون تاریخچه → رد محافظه‌کارانه» جزو ردشده‌هاست، اما آن ردها
    # به‌خاطر رژیم نیستند. برای خلوص فرضیه (رژیم پرنوسان)، فقط ردهایی را نگه می‌داریم که
    # تاریخچهٔ کافی داشتند. بازسازی: ردِ باتاریخچه = base ∧ ~passed ∧ has_history.
    return comp, passed, qv


def has_history_mask(d, tf, mask):
    """سیگنال‌هایی که تاریخچهٔ کافی برای فیلتر V داشتند — بازتولید مستقیم منطق
    تاریخچهٔ vol_filter_mask (هشدار: qv=100 کافی نیست چون روزِ فوق‌پرنوسان‌تر از
    کل تاریخچه در آن رد می‌شود — دقیقاً روزهای هدف ما!)."""
    from tools.s560_gapopen_explore import day_breaks
    from tools.s562_volfilter import VOL_N, ROLL_D, MIN_S
    t, h, l = d['time'], d['high'], d['low']
    n = len(t)
    brk = day_breaks(t, tf)
    starts = np.concatenate([[0], brk + 1])
    ends = np.concatenate([brk, [n - 1]])
    n_days = len(starts)
    rng_day = np.array([h[starts[k]:ends[k] + 1].max()
                        - l[starts[k]:ends[k] + 1].min()
                        for k in range(n_days)])
    vol_ref = np.full(n_days, np.nan)
    csum = np.concatenate([[0.0], np.cumsum(rng_day)])
    for k in range(VOL_N - 1, n_days):
        vol_ref[k] = (csum[k + 1] - csum[k + 1 - VOL_N]) / VOL_N
    day_of_end = {int(ends[k]): k for k in range(n_days)}
    out = np.zeros(n, bool)
    for i in np.flatnonzero(mask):
        k = day_of_end.get(int(i))
        if k is None or np.isnan(vol_ref[k]):
            continue
        lo = max(VOL_N - 1, k - ROLL_D)
        hist = vol_ref[lo:k]
        hist = hist[~np.isnan(hist)]
        if len(hist) >= MIN_S:
            out[i] = True
    return out


def geometry_q80(df, mask, mh, split_bar):
    """SL=TP=q80(|MFE|∪|MAE|) فقط روی سیگنال‌های نیمهٔ اول — قاعدهٔ ثابت خانواده."""
    o, h, l = df['open'].values, df['high'].values, df['low'].values
    idx = np.flatnonzero(mask)
    idx = idx[idx + 1 + mh < split_bar]
    moves = []
    for i in idx:
        e = o[i + 1]
        hi = h[i + 1:i + 1 + mh + 1].max()
        lo = l[i + 1:i + 1 + mh + 1].min()
        moves.append(abs(hi - e))
        moves.append(abs(e - lo))
    if not moves:
        return None
    pip = 0.1  # XAUUSD pip از موتور (BUG-PIPGUESS: تأیید در build)
    return round(float(np.percentile(moves, 80)) / pip, 1)


def null_short(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """نال شورت صادقانه — الگوی s437/s561 اما جهت SHORT (درس S522)."""
    n = len(df)
    zl = np.zeros(n, bool)
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)
    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    um = np.zeros(n, bool)
    um[pick] = True
    tu = se.simulate_trades(df, zl, um, sl, tp, 'XAUUSD', max_hold=mh,
                            allow_overlap=True)
    wr_unc = 100.0 * float((tu['pnl_pip'].values > 0).mean()) if len(tu) else None
    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, zl, pm, sl, tp, 'XAUUSD', max_hold=mh,
                               allow_overlap=False)
        if len(t):
            perm.append(100.0 * float((t['pnl_pip'].values > 0).mean()))
    pa = np.array(perm, float)
    stats = dict(uncond_wr=wr_unc,
                 perm_mean=float(pa.mean()) if pa.size else None,
                 perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                 perm_max=float(pa.max()) if pa.size else None,
                 perm_k=int(pa.size))
    return {'long': {}, 'short': stats}


def first_half_stats(tr, split_bar):
    m = tr[tr['exit_bar'] < split_bar]
    p = m['pnl_pip'].values.astype(float)
    if len(p) < 30:
        return None, len(p), None, None
    se_ = p.std(ddof=1) / np.sqrt(len(p))
    t = float(p.mean() / se_) if se_ > 0 else 0.0
    wr = round(float((p > 0).mean() * 100), 2)
    eq = 10000.0 + np.cumsum(p) * 10.0
    peak = np.maximum.accumulate(eq)
    dd = round(float(((peak - eq) / peak).max() * 100), 2)
    return t, len(p), wr, dd


def phase_lock(tf: str):
    _check_tf(tf)
    d, df, mask, split_bar, cfg = build(tf)
    s560 = json.load(open(S560_LOCK))
    assert s560[tf]['cfg'] == cfg, 'BUG-GEOMDRIFT: cfg ناهمسان با قفل S560'
    assert s560[tf]['n_signals'] == int(mask.sum()), 'BUG-DATASETDRIFT'
    hh = has_history_mask(d, tf, mask)
    comp, passed, qv = complement_mask(d, tf, mask)
    comp = comp & hh  # فقط ردهای رژیمی (تاریخچه‌دار)
    # سنجهٔ سلامت: passed باید بیت‌به‌بیت با n_filtered قفل S562 بخواند
    s562 = json.load(open(S562_LOCK))
    assert int(passed.sum()) == s562[tf]['arms'][s562[tf]['picked']]['n_filtered'], \
        'BUG-DATASETDRIFT: بازسازی فیلتر S562 ناهمسان'
    mh_base = int(s560[tf]['variants']['V-TIME']['mh'])
    print(f"src={d['src']} base={int(mask.sum())} passed(S562)={int(passed.sum())} "
          f"complement(high-vol)={int(comp.sum())} qv={qv} mh_base={mh_base}")
    scored = {}
    for mh in (mh_base, 2 * mh_base):
        g = geometry_q80(df, comp, mh, split_bar)
        if g is None:
            continue
        zl = np.zeros(len(df), bool)
        tr = se.simulate_trades(df, zl, comp, g, g, 'XAUUSD',
                                max_hold=mh, allow_overlap=False)
        t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
        scored[f'SHORT-h{mh}'] = dict(mh=mh, sl=g, tp=g,
                                      n_signals=int(comp.sum()),
                                      t_first_half=t_fh, n_first_half=n_fh,
                                      wr_first_half=wr_fh, dd_first_half=dd_fh)
        print(f"  SHORT-h{mh}: sl=tp={g} → t={t_fh} n_fh={n_fh} "
              f"WR={wr_fh} DD={dd_fh}%")
    # کنترل P1 (فقط ثبت اکتشافی، بدون تصمیم): LONG روی همان روزها، hold پایه
    g0 = geometry_q80(df, comp, mh_base, split_bar)
    if g0 is not None:
        zl = np.zeros(len(df), bool)
        trL = se.simulate_trades(df, comp, zl, g0, g0, 'XAUUSD',
                                 max_hold=mh_base, allow_overlap=False)
        tL, nL, wrL, ddL = first_half_stats(trL, split_bar)
        p1 = dict(t_first_half=tL, n_first_half=nL, wr_first_half=wrL)
        print(f"  [P1 control LONG]: t={tL} n_fh={nL} WR={wrL}")
    else:
        p1 = None
    cands = [k for k in scored if scored[k]['t_first_half'] is not None]
    pick = max(cands, key=lambda k: round(scored[k]['t_first_half'], 2),
               default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(cfg=cfg, qv=qv, arms=scored, picked=pick,
                    p1_control_long=p1,
                    split_bar=int(split_bar), split_utc=SPLIT_UTC,
                    src=d['src'], n_base_signals=int(mask.sum()),
                    n_complement=int(comp.sum()))
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def stop_check(tf: str):
    """سد توقف پیش‌ثبت‌شده: lift نیمهٔ اول نسبت به null شورت < +4pp ⇒ STOPPED_DEAD.
    فقط داده‌ی نیمهٔ اول لمس می‌شود."""
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    if not L.get('picked'):
        print(f"{tf}: NO-VERDICT (n<30)")
        return
    a = L['arms'][L['picked']]
    if a['t_first_half'] is None:
        print(f"{tf}: NO-VERDICT (n_fh={a['n_first_half']}<30)")
        return
    d, df, mask, split_bar, cfg = build(tf)
    comp, _, _ = complement_mask(d, tf, mask)
    comp = comp & has_history_mask(d, tf, mask)
    # null شورت فقط روی نیمهٔ اول (نیمهٔ دوم باکره می‌ماند)
    df_fh = df.iloc[:split_bar].reset_index(drop=True)
    comp_fh = comp[:split_bar]
    nl = null_short(df_fh, comp_fh, a['sl'], a['tp'], a['mh'],
                    n_perm=200, seed=SEED)
    lift = (a['wr_first_half'] or 0) - (nl['short']['uncond_wr'] or 50.0)
    dead = lift < LIFT_STOP
    L['stop_check'] = dict(lift_fh_pp=round(lift, 2),
                           null_uncond_wr_fh=nl['short']['uncond_wr'],
                           threshold=LIFT_STOP,
                           stopped_dead=bool(dead))
    lock[tf] = L
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"{tf}: lift_fh={lift:+.2f}pp vs stop {LIFT_STOP}pp → "
          f"{'STOPPED_DEAD' if dead else 'PROCEED to judge'}")


def phase_judge(tf: str):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    if not L.get('picked'):
        raise SystemExit(f'{tf} قفل نشده')
    sc = L.get('stop_check') or {}
    if sc.get('stopped_dead'):
        raise SystemExit(f'{tf} STOPPED_DEAD — داوری ممنوع (پیش‌ثبت §3)')
    a = L['arms'][L['picked']]
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    d, df, mask, split_bar, cfg = build(tf)
    assert L['n_base_signals'] == int(mask.sum()), 'BUG-DATASETDRIFT'
    comp, _, qv = complement_mask(d, tf, mask)
    comp = comp & has_history_mask(d, tf, mask)
    assert int(comp.sum()) == L['n_complement'], 'BUG-DATASETDRIFT: مکمل ناهمسان'
    zl = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, zl, comp, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    n_tr = len(tr)
    print(f"src={d['src']} arm={L['picked']} sl={sl} tp={tp} mh={mh} n={n_tr}")
    if n_tr < 30:
        res_out = dict(tf=tf, error=f'n<30 (n={n_tr})', invalid=True)
    else:
        null = null_short(df, comp, sl, tp, mh, n_perm=N_PERM, seed=SEED)
        res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                           bar_time=df['time'].values,
                           close=df['close'].values,
                           null=null, n_trials=N_TRIALS, split_bar=split_bar,
                           initial_capital=10000.0, allow_overlap=False)
        gt = res.get('gates') or {}
        m = res.get('metrics') or {}
        lift = m.get('skill_lift_pp')
        p0 = (null['short']['uncond_wr'] or 50.0) / 100.0
        n_need = n_required_for_h3(lift, p0) if lift else float('inf')
        res_out = {
            'tf': tf, 'arm': L['picked'], 'qv': qv, 'direction': 'SHORT',
            'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=mh,
                             rr=round(tp / sl, 3), rule='sym q80 first-half'),
            'cfg': cfg, 'n_signals': int(comp.sum()),
            'verdict': res.get('verdict'),
            'rqs2_score': res.get('rqs2_score'),
            'gates': {k: gt.get(k) for k in sorted(gt)},
            'failed_gates': sorted(k for k, v in gt.items() if v is False),
            'unknown_gates': sorted(k for k, v in gt.items() if v is None),
            'null': null['short'], 'n_trials': N_TRIALS,
            'n_required_for_h3': (None if n_need == float('inf')
                                  else round(float(n_need), 1)),
            'split_bar': int(split_bar), 'split_utc': SPLIT_UTC, 'src': d['src'],
            'metrics': {k: m.get(k) for k in (
                'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
                'profit_factor', 'net_profit', 'max_dd_pct',
                'max_consec_losses', 'mcl_allowed', 'recovery_factor',
                'skill_lift_pp', 'skill_z', 'null_ref_wr',
                'breakeven_wr_cost', 'rr', 'top_win_share', 'z_obs',
                'z_luck_bound', 'z_margin', 'skill_p_perm', 'p_emp',
                'p_adj_bonferroni', 'perm_k', 'perm_max')},
            'notes': [str(x) for x in (res.get('notes') or [])],
        }
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'judge_{tf}.json')
    json.dump(res_out, open(path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: res_out.get(k) for k in
                      ('verdict', 'rqs2_score', 'failed_gates',
                       'n_required_for_h3')}, ensure_ascii=False))
    mm = res_out.get('metrics') or {}
    print(f"WR={mm.get('win_rate')} lift={mm.get('skill_lift_pp')} "
          f"z={mm.get('skill_z')} dd={mm.get('max_dd_pct')}")
    print(f"saved → {path}")


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    {'lock': phase_lock, 'stop': stop_check, 'judge': phase_judge}[phase](tf)
