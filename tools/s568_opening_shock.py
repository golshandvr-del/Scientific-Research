# -*- coding: utf-8 -*-
"""
s568_opening_shock.py — شوکِ کندلِ نخستِ روز → دنبال‌کردن (M15/H1) — مسیر C

پیش‌ثبت: results/S568_PREREG_OPENING_SHOCK_FOLLOW_XAUUSD.md (کامیت 09787940 — قبل از هر تست).

رویداد: کندل نخستِ روز با rng = high−low > q90 علّیِ تاریخچهٔ rng کندل‌های
نخستِ روزهای قبلی (غلتان ۲۵۰ روز، حداقل ۶۰ نمونه). جهت = علامت بدنه.
بازوها: {FOLLOW-BOTH, LONG-ONLY} × {BARE, RHO≥0.618}. hold منجمد: M15→16، H1→4.
هندسه: V-TIME q98 نیمهٔ اول. سدها: n_fh<30 ⇒ NO-VERDICT · lift_fh<+4pp ⇒ STOPPED_DEAD.
null: هر سمت جدا (null_for/null_short)؛ موتور با وزنِ سمت ترکیب می‌کند. n_trials=56.

اجرا:
  python3 tools/s568_opening_shock.py lock  M15
  python3 tools/s568_opening_shock.py stop  M15
  python3 tools/s568_opening_shock.py judge M15
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
from tools.s560_gapopen_explore import day_breaks, SPLIT_UTC  # noqa: E402
from tools.s560_adjudicate import _pip                     # noqa: E402
from tools.s561_h8revival import null_for                  # noqa: E402
from tools.s564_highvol_short import null_short            # noqa: E402
from tools.s434_fast_data import load_fast, as_dataframe   # noqa: E402

N_TRIALS = 56
N_PERM = 500
SEED = 20260902
ALLOWED_TFS = ('M15', 'H1')
HOLD = {'M15': 16, 'H1': 4}          # ۴ ساعت، منجمد
Q_EVENT = 90                          # منجمد
RHO_MIN = 0.618                       # از S965، منجمد
ROLL_D, MIN_S = 250, 60               # ثابت‌های S562
OUT = os.path.join(ROOT, 'results', '_s568_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')
LIFT_STOP = 4.0
SIDES = ('BOTH', 'LONG')
FILTS = ('BARE', 'RHO')


def _check_tf(tf):
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ پیش‌ثبت S568 (فقط M15/H1)')


def _split_bar(t):
    import calendar
    return int(np.searchsorted(t, calendar.timegm((2018, 10, 20, 0, 0, 0))))


def day_starts(d, tf):
    t = d['time']
    brk = day_breaks(t, tf)
    return np.concatenate([[0], brk + 1])


def shock_masks(d, tf, use_rho):
    """برمی‌گرداند (long_mask, short_mask, stats). فقط کندلِ نخست هر روز."""
    o, h, l, c = d['open'], d['high'], d['low'], d['close']
    n = len(o)
    starts = day_starts(d, tf)
    rng_first = h[starts] - l[starts]
    n_days = len(starts)
    lm = np.zeros(n, bool)
    sm = np.zeros(n, bool)
    n_known = n_event = n_rho_pass = 0
    for k in range(n_days):
        lo = max(0, k - ROLL_D)
        hist = rng_first[lo:k]                 # اکیداً روزهای قبلی
        if len(hist) < MIN_S:
            continue
        n_known += 1
        i = int(starts[k])
        r = rng_first[k]
        if not (r > np.percentile(hist, Q_EVENT)):
            continue
        n_event += 1
        body = c[i] - o[i]
        if body == 0 or r <= 0:
            continue
        rho = abs(body) / r
        if rho >= RHO_MIN:
            n_rho_pass += 1
        if use_rho and rho < RHO_MIN:
            continue
        if i + 1 >= n:
            continue
        if body > 0:
            lm[i] = True
        else:
            sm[i] = True
    stats = dict(days_known=n_known, days_event=n_event,
                 event_rate=round(100.0 * n_event / max(n_known, 1), 2),
                 rho_pass_of_events=round(100.0 * n_rho_pass / max(n_event, 1), 1))
    return lm, sm, stats


def arm_masks(d, tf, side, filt):
    lm, sm, st = shock_masks(d, tf, filt == 'RHO')
    if side == 'LONG':
        sm = np.zeros_like(sm)
    return lm, sm, st


def geometry_vtime(d, lm, sm, mh, split_bar):
    pip = _pip('XAUUSD')
    h, l, o = d['high'], d['low'], d['open']
    n = len(o)
    moves = []
    for mask, is_long in ((lm, True), (sm, False)):
        idx = np.flatnonzero(mask)
        idx = idx[idx + 1 + mh < min(split_bar, n)]
        for i in idx:
            e = i + 1
            j1 = min(e + mh, n)
            entry = o[e]
            up = (h[e:j1].max() - entry) / pip
            dn = (entry - l[e:j1].min()) / pip
            moves.extend([abs(up), abs(dn)])
    if not moves:
        return None
    return round(float(np.percentile(np.array(moves), 98)), 1)


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


def _side_counts_fh(tr, split_bar):
    m = tr[tr['exit_bar'] < split_bar]
    if 'direction' in m.columns:
        nl = int((m['direction'] == 'long').sum())
        ns = int((m['direction'] == 'short').sum())
    else:
        nl, ns = len(m), 0
    return nl, ns


def _coevent_with_gap(d, tf, lm, sm):
    """ابطال‌گر F1 (قانون S527): سهم روزهای رویداد S568 که روز گپ منفی S560 هم هستند."""
    try:
        from tools.s560_adjudicate import build
        _, _, gmask, _, _ = build(tf)
    except Exception as ex:                                  # noqa: BLE001
        return dict(error=str(ex))
    starts = day_starts(d, tf)
    # نقشهٔ اندیس کندل → اندیس روز
    day_id = np.searchsorted(starts, np.arange(len(d['time'])), side='right') - 1
    gap_days = set(day_id[np.flatnonzero(gmask)].tolist())
    # سیگنال S560 روی کندل آخر روز g−1 است ⇒ روز هدف = g = day_id+1
    gap_target_days = {g + 1 for g in gap_days}
    ev_days_long = set(day_id[np.flatnonzero(lm)].tolist())
    ev_days_short = set(day_id[np.flatnonzero(sm)].tolist())
    ev_days = ev_days_long | ev_days_short
    co = len(ev_days & gap_target_days)
    co_long = len(ev_days_long & gap_target_days)
    return dict(n_event_days=len(ev_days), n_gap_target_days=len(gap_target_days),
                co_days=co, co_share_pct=round(100.0 * co / max(len(ev_days), 1), 1),
                co_long=co_long, co_short=co - co_long)


def phase_lock(tf: str):
    _check_tf(tf)
    d = load_fast('XAUUSD', tf)
    df = as_dataframe(d)
    split_bar = _split_bar(d['time'])
    mh = HOLD[tf]
    scored = {}
    dens = {}
    for side in SIDES:
        for filt in FILTS:
            lm, sm, st = arm_masks(d, tf, side, filt)
            dens[filt] = st
            g = geometry_vtime(d, lm, sm, mh, split_bar)
            if g is None:
                continue
            tr = se.simulate_trades(df, lm, sm, g, g, 'XAUUSD',
                                    max_hold=mh, allow_overlap=False)
            t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
            nl_fh, ns_fh = _side_counts_fh(tr, split_bar)
            name = f'{side}-{filt}'
            scored[name] = dict(side=side, filt=filt, mh=mh, sl=g, tp=g,
                                n_long=int(lm.sum()), n_short=int(sm.sum()),
                                n_signals=int(lm.sum() + sm.sum()),
                                t_first_half=t_fh, n_first_half=n_fh,
                                n_long_fh=nl_fh, n_short_fh=ns_fh,
                                wr_first_half=wr_fh, dd_first_half=dd_fh)
            print(f"  {name}: nL={int(lm.sum())} nS={int(sm.sum())} sl=tp={g} → "
                  f"t={t_fh} n_fh={n_fh} (L{nl_fh}/S{ns_fh}) WR={wr_fh} DD={dd_fh}%")
    print(f"densities: {dens}")
    cands = [k for k in scored if scored[k]['t_first_half'] is not None]
    pick = max(cands, key=lambda k: round(scored[k]['t_first_half'], 2),
               default=None)
    # F1 — روی بازوی BOTH-BARE (کل رویداد)
    lm, sm, _ = arm_masks(d, tf, 'BOTH', 'BARE')
    f1 = _coevent_with_gap(d, tf, lm, sm)
    print(f"F1 co-event vs S560 gap: {f1}")
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(arms=scored, picked=pick, densities=dens, f1_coevent=f1,
                    split_bar=int(split_bar), split_utc=SPLIT_UTC, src=d['src'])
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def _rebuild(L, d, tf):
    a = L['arms'][L['picked']]
    lm, sm, _ = arm_masks(d, tf, a['side'], a['filt'])
    assert int(lm.sum()) == a['n_long'] and int(sm.sum()) == a['n_short'], 'BUG-DATASETDRIFT'
    return a, lm, sm


def stop_check(tf: str):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    if not L.get('picked'):
        print(f"{tf}: NO-VERDICT (n_fh<30)")
        L['stop_check'] = dict(no_verdict=True)
        lock[tf] = L
        json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
        return
    d = load_fast('XAUUSD', tf)
    df = as_dataframe(d)
    split_bar = _split_bar(d['time'])
    a, lm, sm = _rebuild(L, d, tf)
    df_fh = df.iloc[:split_bar].reset_index(drop=True)
    tr = se.simulate_trades(df, lm, sm, a['sl'], a['tp'], 'XAUUSD',
                            max_hold=a['mh'], allow_overlap=False)
    m = tr[tr['exit_bar'] < split_bar]
    has_dir = 'direction' in m.columns
    wr_side, n_side, null_side = {}, {}, {}
    for s, mask in (('long', lm), ('short', sm)):
        ms = m[(m['direction'] == s).values] if has_dir else (m if s == 'long' else m.iloc[0:0])
        n_side[s] = len(ms)
        if len(ms) == 0:
            continue
        wr_side[s] = 100.0 * float((ms['pnl_pip'].values > 0).mean())
        fn = null_for if s == 'long' else null_short
        nl = fn(df_fh, mask[:split_bar], a['sl'], a['tp'], a['mh'], n_perm=200, seed=SEED)
        null_side[s] = nl[s]['uncond_wr']
    tot = sum(n_side.values())
    lift = sum((wr_side[s] - (null_side[s] or 50.0)) * n_side[s] / tot for s in wr_side)
    dead = lift < LIFT_STOP
    L['stop_check'] = dict(lift_fh_pp=round(lift, 2),
                           per_side=dict(n=n_side, wr=wr_side, null_uncond_wr=null_side),
                           threshold=LIFT_STOP, stopped_dead=bool(dead))
    lock[tf] = L
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"{tf}: per-side {json.dumps(L['stop_check']['per_side'])}")
    print(f"{tf}: lift_fh={lift:+.2f}pp vs stop {LIFT_STOP}pp → "
          f"{'STOPPED_DEAD' if dead else 'PROCEED to judge'}")


def phase_judge(tf: str):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    sc = L.get('stop_check') or {}
    if sc.get('no_verdict') or sc.get('stopped_dead'):
        raise SystemExit(f'{tf} متوقف — داوری ممنوع (پیش‌ثبت §4-2)')
    if 'stopped_dead' not in sc:
        raise SystemExit(f'{tf}: اول فاز stop')
    d = load_fast('XAUUSD', tf)
    df = as_dataframe(d)
    split_bar = _split_bar(d['time'])
    a, lm, sm = _rebuild(L, d, tf)
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    tr = se.simulate_trades(df, lm, sm, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    n_tr = len(tr)
    print(f"src={d['src']} arm={L['picked']} sl={sl} tp={tp} mh={mh} n={n_tr}")
    if n_tr < 30:
        res_out = dict(tf=tf, error=f'n<30 (n={n_tr})', invalid=True)
    else:
        null = {'long': {}, 'short': {}}
        if lm.any():
            null['long'] = null_for(df, lm, sl, tp, mh, n_perm=N_PERM, seed=SEED)['long']
        if sm.any():
            null['short'] = null_short(df, sm, sl, tp, mh, n_perm=N_PERM, seed=SEED + 1)['short']
        res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                           bar_time=df['time'].values,
                           close=df['close'].values,
                           null=null, n_trials=N_TRIALS, split_bar=split_bar,
                           initial_capital=10000.0, allow_overlap=False)
        gt = res.get('gates') or {}
        m = res.get('metrics') or {}
        lift = m.get('skill_lift_pp')
        ref = m.get('null_ref_wr')
        p0 = (ref if ref else 50.0) / 100.0
        n_need = n_required_for_h3(lift, p0) if lift else float('inf')
        res_out = {
            'tf': tf, 'arm': L['picked'], 'direction': a['side'],
            'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=mh,
                             rr=round(tp / sl, 3), rule='V-TIME q98 first-half'),
            'n_signals': int(lm.sum() + sm.sum()), 'n_long': int(lm.sum()),
            'n_short': int(sm.sum()),
            'verdict': res.get('verdict'),
            'rqs2_score': res.get('rqs2_score'),
            'gates': {k: gt.get(k) for k in sorted(gt)},
            'failed_gates': sorted(k for k, v in gt.items() if v is False),
            'unknown_gates': sorted(k for k, v in gt.items() if v is None),
            'null': null, 'n_trials': N_TRIALS,
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
    mm2 = res_out.get('metrics') or {}
    print(f"WR={mm2.get('win_rate')} lift={mm2.get('skill_lift_pp')} "
          f"z={mm2.get('skill_z')} dd={mm2.get('max_dd_pct')} "
          f"mcl={mm2.get('max_consec_losses')}/{mm2.get('mcl_allowed')} "
          f"rec={mm2.get('recovery_factor')}")
    print(f"saved → {path}")


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    {'lock': phase_lock, 'stop': stop_check, 'judge': phase_judge}[phase](tf)
