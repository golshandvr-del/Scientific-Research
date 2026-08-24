# -*- coding: utf-8 -*-
"""
S552 — احیای «شکستِ کانالِ Stairs طلا» (S366) با پیوندِ خروجِ V-TIME
=====================================================================
پیش‌ثبت: results/S552_PREREG_S366_STAIRS_VTIME_TRANSPLANT.md (commit b3025bb2)
که **پیش از اجرای این اسکریپت** به GitHub رفت.

  سیگنال (منجمد، عیناً S366 arm گیت‌دار):
      کانالِ ۵-پیوتی + گیتِ shrink بروکس + فقط نخستین شکستِ هر زمینه
      اجتماعِ k∈{2,3,5} با dedupe (تعارض ⇒ کوچک‌ترین k) — هیچ عضوی انتخاب نمی‌شود
  خروج (تنها تغییر — دستورِ V-TIME از ACCEPTِ S560):
      mh = min(400, 2×میانهٔ مدتِ کانال‌ها)      ← قاعدهٔ خودِ S366
      SL = TP = q98(MFE ∪ MAE در افقِ mh)        ← فقط از پارهٔ اکتشاف (۶۰٪ نخست)
  آمارهٔ حاکم: trade-pooled (قانونِ FAMILY_MEAN_OPTIMISM)
  n_trials=391 · SEED=20260821 · نولِ دوطرفهٔ اندازه‌گیری‌شده با هندسهٔ خودِ لایه

اجرا:  python3 strategies/s552_stairs_vtime.py [CARD ...]
       (پیش‌فرض: M30 M5 M15 H1 H4 — نامزد اول)
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                # noqa: E402
from engine import rqs2                                              # noqa: E402
from tools import s434_fast_data as fd                               # noqa: E402
from strategies.s348_rr_sweep import queue_rr                        # noqa: E402
from strategies.s366_stairs_channel_breakout import (                # noqa: E402
    channel_context, _first_per_seg, FAM_K, HORIZON_MULT, MAX_HOLD_CAP)

ASSET = 'XAUUSD'
SEED = 20260821
N_TRIALS = 391
SPLIT_FRAC = 0.60
UNCOND_CAP = 150_000
OUT = 'results/_scan_S552'

K_PERM = {'M5': 500, 'M15': 500, 'M30': 1000, 'H1': 1000, 'H4': 2000}
ROLE = {'M30': 'DECISIVE', 'M5': 'INFO', 'M15': 'INFO', 'H1': 'INFO', 'H4': 'INFO'}
LADDER = ['M30', 'M5', 'M15', 'H1', 'H4']


def log(msg):
    print(msg, flush=True)


def git_checkpoint(card):
    try:
        subprocess.run(['git', 'add', OUT], check=True)
        subprocess.run(['git', 'commit', '-m',
                        f'S552 checkpoint: {card} judged (frozen prereg b3025bb2)'],
                       check=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'],
                       check=False, timeout=90)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, timeout=90)
        log(f'    [git] checkpoint {card} pushed')
    except Exception as e:                                   # noqa: BLE001
        log(f'    [git] WARN checkpoint failed: {e} (فایل روی دیسک هست)')


def to_dt64(t):
    """درسِ BUG-EPOCH ِ S550: لودر ثانیهٔ epoch (int64) می‌دهد — تبدیلِ صریح."""
    return t.astype('datetime64[s]').astype('datetime64[ns]')


def build_signal(df):
    """اجتماعِ سیگنال‌های اولین-شکستِ سه جریانِ k — منجمد از S366 (گیت‌دار).

    dedupe: اگر چند k روی یک کندل سیگنال بدهند، کوچک‌ترین k حاکم است
    (قاعدهٔ قطعیِ پیش‌ثبت §۲) — جهت و مدتِ کانال از همان k گرفته می‌شود.
    """
    c = df['close'].values.astype(float)
    n = len(df)
    long_u = np.zeros(n, bool)
    short_u = np.zeros(n, bool)
    dur_u = np.zeros(n, np.int64)
    taken = np.zeros(n, bool)
    per_k = {}
    for k in FAM_K:                                  # صعودی: 2, 3, 5
        ctx = channel_context(df, k)
        live = ctx['ok']
        bear = ctx['is_bear']
        shr = ctx['shrink']
        below = live & np.nan_to_num(c < ctx['lower'], nan=False)
        above = live & np.nan_to_num(c > ctx['upper'], nan=False)
        short_raw = (bear & ~shr & below) | (~bear & shr & below)
        long_raw = (~bear & ~shr & above) | (bear & shr & above)
        trig = short_raw | long_raw
        first = _first_per_seg(trig, ctx['seg'])
        lk = first & long_raw
        sk = first & short_raw
        per_k[k] = int((lk | sk).sum())
        fresh = (lk | sk) & ~taken
        long_u |= lk & fresh
        short_u |= sk & fresh
        idx = np.flatnonzero(fresh)
        dur_u[idx] = idx - ctx['t0'][idx]
        taken |= fresh
    return long_u, short_u, dur_u, per_k


def vtime_bracket(df, long_sig, short_sig, mh, disc_mask, pip):
    """براکتِ فاجعهٔ V-TIME: SL=TP=q98(MFE∪MAE) — فقط سیگنال‌های پارهٔ اکتشاف.

    جهت‌آگاه: برای LONG مساعد=high−entry، نامساعد=entry−low؛ برای SHORT برعکس.
    ورود = openِ کندلِ بعد (قراردادِ موتور).
    """
    o = df['open'].values.astype(float)
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    n = len(o)
    mfes, maes = [], []
    for i in np.flatnonzero((long_sig | short_sig) & disc_mask):
        e = i + 1
        j1 = min(e + mh, n)
        if e >= n or e >= j1:
            continue
        entry = o[e]
        up = (h[e:j1].max() - entry) / pip
        dn = (entry - l[e:j1].min()) / pip
        if long_sig[i]:
            mfes.append(up)
            maes.append(dn)
        else:
            mfes.append(dn)
            maes.append(up)
    pool = np.concatenate([np.asarray(mfes), np.asarray(maes)])
    wide = round(float(np.percentile(pool, 98)), 1)
    return max(wide, 1.0), len(mfes)


def build_null(df, valid, sl_price, n_long, n_short, mh, k_perm, rng):
    """نولِ دوطرفهٔ اندازه‌گیری‌شده با هندسهٔ خودِ لایه (rr=1.0، همان mh)."""
    null = {}
    for side, n_side, is_long in (('long', n_long, True),
                                  ('short', n_short, False)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None, uncond_pool=None)
        if n_side >= 1 and len(valid) >= 2:
            vi = valid
            if len(vi) > UNCOND_CAP:
                sub = np.sort(rng.choice(len(vi), size=UNCOND_CAP, replace=False))
                vi_u = vi[sub]
                d['uncond_pool'] = int(UNCOND_CAP)
            else:
                vi_u = vi
                d['uncond_pool'] = int(len(vi))
            s_all = queue_rr(df, vi_u, np.full(len(vi_u), is_long),
                             np.full(len(vi_u), sl_price), ASSET, mh, 1.0)
            if s_all:
                d['uncond_wr'] = s_all['wr']
            if len(vi) > n_side:
                wrs = []
                for _ in range(k_perm):
                    pick = np.sort(rng.choice(len(vi), size=n_side, replace=False))
                    s_p = queue_rr(df, vi[pick], np.full(n_side, is_long),
                                   np.full(n_side, sl_price), ASSET, mh, 1.0)
                    if s_p:
                        wrs.append(s_p['wr'])
                if wrs:
                    a = np.asarray(wrs, dtype='float64')
                    d.update(perm_mean=float(a.mean()),
                             perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        log(f"      null {side}: n={n_side} uncond={d['uncond_wr']} "
            f"perm_mean={d['perm_mean']} sd={d['perm_sd']} k={d['perm_k']}")
    return null


def run_card(card):
    t0 = time.time()
    role = ROLE[card]
    k_perm = K_PERM[card]
    log(f'\n================ S552 · {ASSET} · {card} ({role}) ================')
    d = fd.load_fast(ASSET, card)
    src = d['src']
    if 'mt5_full' not in src:
        raise RuntimeError(f'{card}: دادهٔ full نیست — توقف.')
    df = fd.as_dataframe(d)
    n = len(df)
    t64 = to_dt64(d['time'])
    pip = float(se.ASSETS[ASSET]['pip'])
    cost = float(se.ASSETS[ASSET]['spread_pip']) + \
        2.0 * float(se.ASSETS[ASSET].get('slip_pip', 0.0))
    warm = min(260, max(30, n // 8))                       # عیناً قاعدهٔ S366
    span_y = float((t64[-1] - t64[0]) / np.timedelta64(1, 'D')) / 365.25
    log(f'  src={src}  bars={n:,}  span={span_y:.2f}y  warmup={warm}')

    # ── سیگنالِ منجمد ──
    long_sig, short_sig, dur, per_k = build_signal(df)
    long_sig[:warm] = False
    short_sig[:warm] = False
    sel = long_sig | short_sig
    if not sel.any():
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no signals)')
        _save(card, payload)
        return payload

    # ── mh از هندسهٔ خودِ الگو (قاعدهٔ ثبت‌شدهٔ S366) ──
    med_dur = float(np.median(dur[sel]))
    mh = int(min(MAX_HOLD_CAP, max(5, round(HORIZON_MULT * med_dur))))
    long_sig[n - mh - 2:] = False
    short_sig[n - mh - 2:] = False
    sel = long_sig | short_sig
    nsig = int(sel.sum())
    log(f'  signals={nsig} (per-k={per_k})  median_chan_dur={med_dur:.0f} '
        f'⇒ mh={mh}')

    # ── مرزِ اکتشاف/holdout به‌وقتِ سیگنال (q60) — براکت فقط از اکتشاف ──
    sig_ns = t64[sel].astype(np.int64)
    split_ns = int(np.quantile(sig_ns, SPLIT_FRAC))
    disc_mask = t64.astype(np.int64) < split_ns
    wide, n_disc = vtime_bracket(df, long_sig, short_sig, mh, disc_mask, pip)
    log(f'  split@{np.datetime64(split_ns, "ns")} · disc_signals={n_disc}')
    log(f'  V-TIME bracket: SL=TP={wide} pip (q98 · {wide/cost:.0f}×cost) · '
        f'time exit @ mh={mh}')

    # ── شبیه‌سازی رسمی ──
    tr = se.simulate_trades(df, long_sig, short_sig, wide, wide, ASSET,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        payload = dict(card=card, role=role, verdict='INCOMPLETE (no trades)')
        _save(card, payload)
        return payload
    pnl = tr['pnl_pip'].values.astype(float)
    wr = float(100 * (pnl > 0).mean())
    e_pip = float(pnl.mean()) + cost            # لبهٔ ناخالص = خالص + هزینه
    nL = int((tr['direction'] == 'long').sum())
    nS = int((tr['direction'] == 'short').sum())
    log(f'  trades={len(tr)} (L={nL}/S={nS})  wr={wr:.2f}%  '
        f'net={pnl.mean():+.2f} pip  e_pip={e_pip:+.2f} vs c={cost:.2f}  '
        f'[{time.time()-t0:.0f}s]')

    # ── نولِ دوطرفهٔ هم‌هندسه ──
    rng = np.random.default_rng(SEED)
    valid = np.arange(warm, max(warm + 2, n - mh - 1))
    fin = np.isfinite(df['close'].to_numpy())
    valid = valid[fin[valid]]
    log(f'  building measured null: k={k_perm} …')
    null = build_null(df, valid, wide * pip, nL, nS, mh, k_perm, rng)

    # ── H7: holdout به‌وقتِ ورودِ معامله با همان مرز ──
    te_ns = t64[tr['entry_bar'].to_numpy(int)].astype(np.int64)
    holdout = te_ns >= split_ns
    log(f'  H7: disc={int((~holdout).sum())} · oos={int(holdout.sum())}')

    null_clean = {k: {kk: vv for kk, vv in v.items() if kk != 'uncond_pool'}
                  for k, v in null.items()}
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=float(wide), tp_pip=float(wide),
                            bar_time=t64, close=df['close'].to_numpy(float),
                            null=null_clean, n_trials=N_TRIALS,
                            holdout_mask=holdout, allow_overlap=False)
    log('')
    log(rqs2.format_rqs2(f'S552_{card}', res))
    log(f'  PIP-EDGE LAW: e_pip={e_pip:+.2f} '
        f'{">" if e_pip > cost else "<="} c={cost:.2f} ⇒ '
        f'{"PASS" if e_pip > cost else "FAIL (BELOW_COST)"}')

    entry_times = t64[tr['entry_bar'].to_numpy(int)].astype(str).tolist()
    payload = dict(card=card, role=role, src=src, n_bars=int(n),
                   span_years=span_y, warmup=int(warm),
                   geom=dict(sl=wide, tp=wide, mh=int(mh),
                             rule='V-TIME: SL=TP=q98(MFE∪MAE) disc-only'),
                   med_chan_dur=med_dur, per_k_signals=per_k,
                   n_signals=nsig, n_disc_signals=int(n_disc),
                   n_trades=int(len(tr)), n_long=nL, n_short=nS, wr=wr,
                   net_pip=float(pnl.mean()), e_pip=e_pip, cost_pip=cost,
                   pip_edge_pass=bool(e_pip > cost),
                   null=null, k_perm=k_perm, n_trials=N_TRIALS,
                   split_frac=SPLIT_FRAC, split_ns=split_ns, seed=SEED,
                   verdict=res.get('verdict'),
                   rqs2_score=res.get('rqs2_score'), gates=res.get('gates'),
                   metrics=res.get('metrics'), entry_times=entry_times,
                   elapsed_s=round(time.time() - t0, 1))
    _save(card, payload)
    tr.to_csv(f'{OUT}/{card}_trades.csv', index=False)
    git_checkpoint(card)
    return payload


def _save(card, payload):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/{card}.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, default=str, indent=1)
    log(f'  saved -> {OUT}/{card}.json')


def main():
    cards = sys.argv[1:] or LADDER
    for card in cards:
        try:
            run_card(card)
        except Exception as e:                               # noqa: BLE001
            import traceback
            traceback.print_exc()
            log(f'!! {card} failed: {e} — ادامه با کارتِ بعدی')
    log('\nS552 run complete.')


if __name__ == '__main__':
    main()
