# -*- coding: utf-8 -*-
"""
S347 — **گروههٔ رأی‌گیریِ** خانوادهٔ S346
================================================================================
پیش‌ثبت: `results/S347_PREREGISTRATION_ENSEMBLE.md` (پیش از این فایل کامیت شد)

منطقِ کوتاه
-----------
قانونِ چهارم ثابت کرد فیلتر نمی‌تواند `WR` را از زیرِ ۵۰٪ به بالای سربه‌سرِ
هزینه‌دار برساند. پس چیزی لازم است که **فیلتر نباشد**: توافقِ چند جریانِ
سیگنال. `votes(t)` تعدادِ جریان‌هایی است که در کندلِ `t` هم‌جهت سیگنال
می‌دهند، و ورود تنها وقتی رخ می‌دهد که `votes ≥ K`.

⭐ سه خاصیتِ آماریِ این طرح
---------------------------
۱) **هیچ عضوی گزینش نمی‌شود** ⇒ جریمهٔ چندگانگیِ `H5` فقط از شبکهٔ کوچکِ
   `K` می‌آید (`N=10` ⇒ کران ≈ ۲.۰σ) نه از فضای ۴۰۱-ابزاری (کران ۴.۲۶۵σ).
۲) **صفر پارامترِ نو جز `K`**: براکت هم **تجمیع** می‌شود —
   `SL = میانهٔ ATR تطبیقیِ جریان‌های رأی‌دهنده`. انتخابِ یک `p` مرجع
   خودش یک گزینش بود، پس از آن پرهیز شد.
۳) دو مدلِ صفر، که دومی حیاتی‌تر است:
   * `N1` جای‌گشتِ زمانی → «آیا مهارتی هست؟»
   * `N2` ⭐ **جای‌گشتِ رأی**: همان تعدادِ ورود، اما زمان‌ها از میانِ
     کندل‌هایی با **≥۱ رأی** ⇒ «آیا خودِ *توافق* چیزی افزود، یا فقط
     کم‌شدنِ `n` واریانسِ `WR` را باد کرده بود؟»

نکتهٔ ظریفِ ساختاری که در پیش‌ثبت آمد: `hold` فقط بر **خروج** اثر دارد،
پس ۵۴ عضوِ خانواده تنها **۱۸ جریانِ سیگنالِ متمایز** دارند ⇒ سقفِ رأی ۱۸.
"""
import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                      # noqa: E402
from engine import indicator_bank as ib                    # noqa: E402
from strategies.s346_geom import CARDS, event_mask         # noqa: E402
from strategies.s346_adaptive_channel import adaptive_channel   # noqa: E402
from strategies.s346_fast import barrier_outcomes, select_non_overlap  # noqa: E402

OUT = 'results/_scan_S346'
SEED = 20260730

# ---------------- خانوادهٔ منجمد (عیناً از s346_family) ----------------
P_LIST = (13, 21, 34)
MULT_LIST = (1.272, 1.618, 2.058)
ER_LIST = (0.146, 0.236)
HOLD_LIST = (5, 8, 13)
MODE = 'breakout'
SL_K = 1.0
RR = 1.0                     # ⚠️ قیدِ ضدِ تقلبِ اشتباه #۸: TP = SL
ENS_HOLD = int(np.median(HOLD_LIST))     # = ۸ ، میانهٔ خانواده (نه انتخابِ دلبخواه)

K_GRID = (2, 3, 5, 8, 13)    # فیبوناچی — اشتباهِ رایج #۷
N_TRIALS = len(K_GRID) * 2   # دو گونه A/B

# فیلترهای منجمدِ C1 + فضای بانکِ آن‌ها (درسِ گران‌بهای نشستِ قبل)
C1_FILTERS = [
    dict(col='cg_fib_13',  dir='ge', thr=-0.05637353658676148, kind='raw'),
    dict(col='std_fib_55', dir='le', thr=0.8881055116653442,  kind='z233'),
]
REF_CARD = 'XAUUSD-D1'
ZWIN = 233
REGIME_LOOKBACK = 200        # عیناً `engine.rqs2.REGIME_LOOKBACK`


# ============================== ابزارها ==============================

def _ind(df, name, kind='raw'):
    """اندیکاتور **در همان فضای بانک** (z233 در صورتِ لزوم)."""
    v = ib.compute(name, df).values.astype(np.float64)
    if kind != 'z233':
        return v
    s = pd.Series(v)
    mu = s.rolling(ZWIN, min_periods=55).mean()
    sd = s.rolling(ZWIN, min_periods=55).std()
    return ((s - mu) / sd.where(sd > 0)).values


def _ref_quantiles():
    """چارکِ آستانه‌های C1 روی کارتِ مرجع — یک‌بار، با کش."""
    path = f"{OUT}/oos_ref_quantiles.json"
    if os.path.exists(path):
        return json.load(open(path))
    asset, p = CARDS[REF_CARD]
    df = se.load_data(p)
    q = {}
    for f in C1_FILTERS:
        v = _ind(df, f['col'], f['kind'])
        ok = np.isfinite(v)
        ok[:WARMUP_REF] = False
        q[f['col']] = float((v[ok] <= f['thr']).mean())
    os.makedirs(OUT, exist_ok=True)
    json.dump(q, open(path, 'w'))
    return q


WARMUP_REF = 250


def weighted_median_3(vals, wts):
    """میانهٔ وزنیِ سه ردیف، برداری روی کلِ کندل‌ها.

    `vals` و `wts` هر دو با شکلِ (3, n). وزن = تعدادِ جریان‌های رأی‌دهندهٔ
    آن `p`. برداری نوشته شده چون حلقهٔ پایتونی روی ۲۰۰هزار کندل غیرعملی است.
    """
    order = np.argsort(vals, axis=0)
    v_s = np.take_along_axis(vals, order, axis=0)
    w_s = np.take_along_axis(wts, order, axis=0)
    cum = np.cumsum(w_s, axis=0)
    tot = cum[-1]
    half = tot / 2.0
    idx = np.argmax(cum >= half[None, :], axis=0)
    return np.take_along_axis(v_s, idx[None, :], axis=0)[0]


def _queue(df, sig, is_long, sl_dist, asset, hold):
    """سدِ دوطرفه ← صفِ بی‌همپوشانی ← آمار (عیناً منطقِ داوریِ رسمی)."""
    cfg = se.ASSETS[asset]
    pip = float(cfg['pip'])
    spread = float(cfg['spread_pip'])
    slip = float(cfg.get('slip_pip', 0.0))
    tp_dist = np.maximum(RR * sl_dist, sl_dist)     # ضدِ تقلب: TP ≥ SL
    fo = barrier_outcomes(df, sig, is_long, sl_dist, tp_dist, hold,
                          pip, spread, slip)
    if len(fo['entry_bar']) == 0:
        return None
    keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
    pnl = fo['pnl_pip'][keep]
    if len(pnl) == 0:
        return None
    win = pnl > 0
    gw = float(pnl[win].sum())
    gl = float(-pnl[~win].sum())
    return dict(n=int(len(pnl)), wr=float(win.mean() * 100.0),
                exp=float(pnl.mean()),
                pf=float(gw / gl) if gl > 0 else 999.0,
                pnl=pnl, win=win,
                entry_bar=fo['entry_bar'][keep],
                exit_bar=fo['entry_bar'][keep] + fo['exit_off'][keep],
                is_long=fo['is_long'][keep],
                sl_pip=fo['sl_pip'][keep], tp_pip=fo['tp_pip'][keep])


# ============================== هستهٔ اجرا ==============================

def build_votes(df, warmup):
    """۱۸ جریانِ سیگنال ⇒ شمارِ رأی + ATR تجمیعی."""
    ch = {p: adaptive_channel(df, p=p, mult=1.0) for p in P_LIST}
    n = len(df)
    vl = np.zeros(n, dtype=np.int16)
    vs = np.zeros(n, dtype=np.int16)
    # وزنِ هر p = تعدادِ جریان‌های رأی‌دهندهٔ آن p (برای میانهٔ وزنیِ ATR)
    wl = np.zeros((len(P_LIST), n), dtype=np.int16)
    ws = np.zeros((len(P_LIST), n), dtype=np.int16)
    atr = np.zeros((len(P_LIST), n), dtype=np.float64)
    for i, p in enumerate(P_LIST):
        atr[i] = ch[p]['atr_a']
        for mult in MULT_LIST:
            for er in ER_LIST:
                ls, ss = event_mask(df, ch[p], MODE, mult, er, warmup)
                vl += ls.astype(np.int16)
                vs += ss.astype(np.int16)
                wl[i] += ls.astype(np.int16)
                ws[i] += ss.astype(np.int16)
    return vl, vs, wl, ws, atr


def entries_for_K(vl, vs, wl, ws, atr, K):
    """ورودی‌های گروهه در سطحِ رأیِ K + SL تجمیعی."""
    long_ok = (vl >= K) & (vl > vs)
    short_ok = (vs >= K) & (vs > vl)
    sig = np.where(long_ok | short_ok)[0]
    if len(sig) == 0:
        return sig, sig.astype(bool), np.zeros(0)
    is_long = long_ok[sig]
    w = np.where(is_long[None, :], wl[:, sig], ws[:, sig]).astype(np.float64)
    a = atr[:, sig]
    bad = ~np.isfinite(a) | (a <= 0)
    w = np.where(bad, 0.0, w)
    a = np.where(bad, 0.0, a)
    good = w.sum(axis=0) > 0
    sl = np.zeros(len(sig))
    if good.any():
        sl[good] = weighted_median_3(a[:, good], w[:, good])
    ok = good & np.isfinite(sl) & (sl > 0)
    return sig[ok], is_long[ok], SL_K * sl[ok]


def run(card, n_perm=200, save=True):
    rng = np.random.default_rng(SEED)
    asset, path = CARDS[card]
    df = se.load_data(path)
    n = len(df)
    warmup = max(5 * max(P_LIST), 250)
    print(f"=== S347 ENSEMBLE :: {card} (bars={n:,}) ===", flush=True)
    print(f"    18 signal streams · vote ceiling 18 · K grid {K_GRID}", flush=True)
    print(f"    ensemble hold = {ENS_HOLD} (median of {HOLD_LIST}), "
          f"RR = {RR} frozen", flush=True)

    vl, vs, wl, ws, atr = build_votes(df, warmup)
    print(f"    votes: bars with >=1 vote = "
          f"{int(((vl >= 1) | (vs >= 1)).sum()):,}  "
          f"max_long={int(vl.max())} max_short={int(vs.max())}", flush=True)

    # گونهٔ B: دروازهٔ فیلترِ منجمد با آستانهٔ چارک‌همتا
    qref = _ref_quantiles()
    gate = np.ones(n, dtype=bool)
    thr_used = {}
    for f in C1_FILTERS:
        v = _ind(df, f['col'], f['kind'])
        ok = np.isfinite(v)
        ok[:warmup] = False
        thr = float(np.nanquantile(v[ok], qref[f['col']]))
        thr_used[f['col']] = thr
        g = (v >= thr) if f['dir'] == 'ge' else (v <= thr)
        gate &= np.where(np.isfinite(v), g, False)
    print(f"    filter gate keeps {gate.mean()*100:.2f}% of bars  "
          f"thr={ {k: round(v, 6) for k, v in thr_used.items()} }", flush=True)

    # بارهای مجاز برای مدلِ صفرِ ۱ (هر کندلِ واجدِ warmup)
    valid_all = np.arange(warmup, n - ENS_HOLD - 2)
    # بارهای «≥۱ رأی» برای مدلِ صفرِ ۲
    any_vote = (vl >= 1) | (vs >= 1)

    rows = []
    for variant in ('A', 'B'):
        vmask = gate if variant == 'B' else np.ones(n, dtype=bool)
        for K in K_GRID:
            sig, is_long, sl = entries_for_K(vl, vs, wl, ws, atr, K)
            if len(sig):
                sel = vmask[sig]
                sig, is_long, sl = sig[sel], is_long[sel], sl[sel]
            if len(sig) < 30:
                print(f"  [{variant} K={K:2d}] only {len(sig)} signals — skip",
                      flush=True)
                rows.append(dict(variant=variant, K=K, status='TOO_FEW',
                                 n_sig=int(len(sig))))
                continue
            st = _queue(df, sig, is_long, sl, asset, ENS_HOLD)
            if st is None or st['n'] < 30:
                print(f"  [{variant} K={K:2d}] queue too small — skip", flush=True)
                rows.append(dict(variant=variant, K=K, status='TOO_FEW',
                                 n_sig=int(len(sig))))
                continue

            # ---- مدلِ صفرِ ۱: جای‌گشتِ زمانی (بارهای مجاز) ----
            # ---- مدلِ صفرِ ۲: جای‌گشتِ رأی (بارهای با ≥۱ رأی) ----
            pool2 = np.intersect1d(valid_all, np.where(any_vote & vmask)[0])
            wr1, ex1, wr2, ex2 = [], [], [], []
            k = len(sig)
            for b in range(n_perm):
                for pool, WR, EX in ((valid_all, wr1, ex1), (pool2, wr2, ex2)):
                    if len(pool) <= k:
                        continue
                    pick = np.sort(rng.choice(pool, size=k, replace=False))
                    lab = rng.permutation(is_long)          # نسبتِ جهت حفظ
                    a = atr[:, pick]
                    w = np.ones_like(a)
                    bad = ~np.isfinite(a) | (a <= 0)
                    w[bad] = 0.0
                    a = np.where(bad, 0.0, a)
                    g2 = w.sum(axis=0) > 0
                    if not g2.any():
                        continue
                    s2 = np.zeros(len(pick))
                    s2[g2] = weighted_median_3(a[:, g2], w[:, g2])
                    okk = g2 & (s2 > 0)
                    stn = _queue(df, pick[okk], lab[okk], SL_K * s2[okk],
                                 asset, ENS_HOLD)
                    if stn and stn['n'] > 0:
                        WR.append(stn['wr'])
                        EX.append(stn['exp'])
                if (b + 1) % 50 == 0:
                    print(f"      [{variant} K={K}] perm {b+1}/{n_perm}",
                          flush=True)

            def _z(obs, arr):
                a = np.asarray(arr, dtype=float)
                if len(a) < 5 or a.std(ddof=1) <= 0:
                    return None, None, None
                z = (obs - a.mean()) / a.std(ddof=1)
                p = (1.0 + int((a >= obs).sum())) / (len(a) + 1.0)
                return float(z), float(p), float(a.mean())

            z1w, p1w, m1w = _z(st['wr'], wr1)
            z1e, p1e, m1e = _z(st['exp'], ex1)
            z2w, p2w, m2w = _z(st['wr'], wr2)
            z2e, p2e, m2e = _z(st['exp'], ex2)

            # ---- تشخیصِ H10: زیرمجموعهٔ خلافِ رانش ----
            close = df['close'].values.astype(np.float64)
            eb = st['entry_bar']
            ref = np.maximum(eb - REGIME_LOOKBACK, 0)
            drift = close[np.minimum(eb, n - 1)] - close[ref]
            cdm = np.where(st['is_long'], drift <= 0.0, drift >= 0.0)
            cd = dict(n=int(cdm.sum()))
            if cd['n'] > 0:
                cd['wr'] = float((st['pnl'][cdm] > 0).mean() * 100.0)
                cd['exp'] = float(st['pnl'][cdm].mean())
            al = ~cdm
            if al.sum() > 0:
                cd['n_aligned'] = int(al.sum())
                cd['exp_aligned'] = float(st['pnl'][al].mean())

            cost = se.ASSETS[asset]['spread_pip']
            tp_med = float(np.median(st['tp_pip']))
            wr_break = 50.0 * (1.0 + cost / tp_med) if tp_med > 0 else None

            rec = dict(variant=variant, K=K, status='OK', n_sig=int(len(sig)),
                       n=st['n'], wr=round(st['wr'], 3),
                       exp=round(st['exp'], 4), pf=round(st['pf'], 3),
                       sl_pip_med=round(float(np.median(st['sl_pip'])), 2),
                       tp_pip_med=round(tp_med, 2),
                       wr_break_law4=round(wr_break, 3) if wr_break else None,
                       null1_wr=round(m1w, 3) if m1w else None,
                       null1_exp=round(m1e, 4) if m1e else None,
                       z1_wr=round(z1w, 3) if z1w else None,
                       z1_exp=round(z1e, 3) if z1e else None,
                       p1_wr=round(p1w, 5) if p1w else None,
                       null2_wr=round(m2w, 3) if m2w else None,
                       null2_exp=round(m2e, 4) if m2e else None,
                       z2_wr=round(z2w, 3) if z2w else None,
                       z2_exp=round(z2e, 3) if z2e else None,
                       p2_wr=round(p2w, 5) if p2w else None,
                       counter_drift=cd)
            rows.append(rec)
            print(f"  [{variant} K={K:2d}] n={st['n']:5d} WR={st['wr']:6.2f}% "
                  f"PF={st['pf']:5.3f} exp={st['exp']:+8.2f}pip | "
                  f"need>{rec['wr_break_law4']}% | "
                  f"N1 z={rec['z1_wr']} N2 z={rec['z2_wr']} | "
                  f"CD n={cd['n']} exp={cd.get('exp')}", flush=True)

    from engine.rqs2 import expected_max_z
    bound = float(expected_max_z(N_TRIALS))
    print(f"\n  N={N_TRIALS} (K grid x 2 variants) ⇒ luck bound = "
          f"{bound:.3f}σ", flush=True)

    rec = dict(card=card, asset=asset, bars=int(n), ens_hold=ENS_HOLD,
               rr=RR, sl_k=SL_K, k_grid=list(K_GRID), n_trials=N_TRIALS,
               luck_bound=round(bound, 4), filter_thr=thr_used,
               gate_keep_frac=round(float(gate.mean()), 5),
               n_perm=n_perm, rows=rows)
    if save:
        os.makedirs(OUT, exist_ok=True)
        with open(f"{OUT}/{card}_ens.json", 'w') as fh:
            json.dump(rec, fh, default=float)
        print(f"  saved -> {OUT}/{card}_ens.json", flush=True)
    return rec


if __name__ == '__main__':
    c = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD-D1'
    nb = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    run(c, n_perm=nb)
