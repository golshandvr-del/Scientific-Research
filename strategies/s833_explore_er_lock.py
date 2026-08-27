# -*- coding: utf-8 -*-
"""
S833 — کاوشِ ۲: قفلِ جهتیِ نسبتِ کارایی (Kaufman ER Directional Lock) — فقط ۶۰٪ اکتشاف
=========================================================================================
قلمرو بکر: هیچ لایه‌ی RQS2 (سالم/سوخته) از ER استفاده نکرده (فقط اسناد pre-RQS2).
فرضیه‌ی علّی: ER(W) = |c_t − c_{t−W}| / Σ|Δc| ∈ [0,1] — حرکتِ پرکارایی یعنی
سفارش‌های یک‌طرفِ نهادی بدون کشمکش؛ چنین جریانی در افقِ کوتاه ادامه می‌یابد
(time-series momentum؛ ولی متغیرِ حالت = کاراییِ نویز-نرمال، نه اندازه‌ی حرکت —
متمایز از S770/ADR و S842/drift-burst دانشمندانِ موازی).
رخداد: عبورِ تازه‌ی ER از آستانه θ (ER>θ و ER قبلی ≤θ) ⇒ ورود در جهتِ علامتِ
(c_t − c_{t−W}) — درون‌زاد و آینه‌ای. هر دو حالتِ cont/rev سنجیده می‌شود.
سنجه (درس S832): INFO-lift نسبت به نالِ جای‌گشتیِ هم‌هندسه K=120 + PF و E1/E2.
شبکه: TF ∈ {H1, H4} × W ∈ {10, 21} × θ ∈ {0.55, 0.70} × mode ∈ {cont, rev}
هندسه‌ی ساده: SL=2×ATR34، TP=2×SL، hold=34، بدون trail/BE، no-overlap.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

WARMUP = 200
K_NULL = 120
SEED = 833002
SLM, RR, HOLD = 2.0, 2.0, 34

def pf_of(p):
    w = p[p > 0].sum(); lo_ = -p[p < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf

for TF in ('H1', 'H2', 'H3'):
    d = fd.load_fast('XAUUSD', TF)
    assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
    df_full = fd.as_dataframe(d)
    split = int(len(df_full) * 0.6)
    df = df_full.iloc[:split].reset_index(drop=True)
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(df)
    HALF = n // 2
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.empty_like(tr); atr[0] = tr[0]
    a = 1.0 / 34
    for i in range(1, n):
        atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
    atr_pip = atr / se.ASSETS['XAUUSD']['pip']
    slp = np.clip(atr_pip * SLM, 8, 5000)
    tpp = slp * RR

    dc = np.abs(np.diff(c, prepend=c[0]))
    cs_abs = np.cumsum(np.concatenate([[0.0], dc]))
    print(f'\n################ TF={TF}  explore bars={n:,}  src={d["src"]} ################', flush=True)

    for W in (13, 21, 34):
        net = np.full(n, np.nan)
        net[W:] = c[W:] - c[:-W]
        noise = cs_abs[W+1:] - cs_abs[1:-W]     # Σ|Δc| در W کندل منتهی به t
        er = np.full(n, np.nan)
        ok = noise > 0
        er_vals = np.abs(net[W:])
        er[W:][ok] = er_vals[ok] / noise[ok]
        prev_er = np.concatenate([[np.nan], er[:-1]])

        for theta in (0.60, 0.70, 0.80):
            x = (er > theta) & ~(prev_er > theta)
            x[:WARMUP] = False
            up = x & (net > 0)
            dn = x & (net < 0)
            n_ev = int(up.sum() + dn.sum())
            if n_ev < 80:
                print(f'  W={W} th={theta}: events={n_ev} — کم، رد', flush=True)
                continue
            for mode in ('cont', 'rev'):
                ls, ss = (up, dn) if mode == 'cont' else (dn, up)
                tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp,
                                         asset='XAUUSD', max_hold=HOLD,
                                         allow_overlap=False)
                if len(tdf) < 60:
                    continue
                pnl = tdf['pnl_pip'].values
                eb = tdf['entry_bar'].values
                wr = float((pnl > 0).mean() * 100)
                pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
                sig_bars = tdf['signal_bar'].values.astype(int)
                rng = np.random.default_rng(SEED + W * 100 + int(theta * 100))
                wrs = []
                for _ in range(K_NULL):
                    dirs = rng.integers(0, 2, size=len(sig_bars)).astype(bool)
                    lm = np.zeros(n, bool); lm[sig_bars[dirs]] = True
                    sm = np.zeros(n, bool); sm[sig_bars[~dirs]] = True
                    ptr = se.simulate_trades(df, lm, sm, sl_pip=slp, tp_pip=tpp,
                                             asset='XAUUSD', max_hold=HOLD,
                                             allow_overlap=False)
                    if len(ptr):
                        wrs.append(float((ptr['pnl_pip'].values > 0).mean() * 100))
                nm = float(np.mean(wrs)); nsd = float(np.std(wrs))
                lift = wr - nm
                z = lift / nsd if nsd > 0 else 0.0
                flag = ' <<<' if (lift >= 4 and z >= 2.5 and pf >= 1.2) else ''
                print(f'  W={W} th={theta} {mode}: n={len(tdf):5,} WR={wr:5.2f}% '
                      f'null={nm:5.2f}%±{nsd:.2f} INFOlift={lift:+6.2f}pp z={z:+4.1f} '
                      f'exp={float(pnl.mean()):+7.2f} PF={pf:.3f} [E1={pf1:.3f} E2={pf2:.3f}]{flag}',
                      flush=True)

print('\n[S833 explore-2 complete]', flush=True)
