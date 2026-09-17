# -*- coding: utf-8 -*-
"""
S798 — داوری رسمی (یک بار) — London-Session Shock Continuation — XAUUSD H8
طبق strategies/S798_PREREG.md (کامیت 8c5a19d8). هیچ پارامتری اینجا جست‌وجو نمی‌شود.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

LAYER = 798; TF = 'H8'; PIP = 0.10
HOUR, THETA, KSL, RR, MH = 8, 2.618, 1.618, 1.0, 12
N_TRIALS = 149; K_PERM = 500
HERE = os.path.dirname(os.path.abspath(__file__))


def atr21(h, l, c, p=21):
    n = len(c)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    tr = np.r_[h[0] - l[0], tr]
    a = np.empty(n); a[0] = tr[0]; al = 2 / (p + 1)
    for i in range(1, n):
        a[i] = a[i - 1] + (tr[i] - a[i - 1]) * al
    return np.r_[np.nan, a[:-1]]


def main():
    d = fd.load_fast('XAUUSD', TF); df = fd.as_dataframe(d)
    assert 'mt5_full' in d['src'], 'E-16 guard'
    t = df['time'].values.astype(np.int64)
    o, h, l, c = [df[k].values for k in ('open', 'high', 'low', 'close')]; n = len(c)
    hr = pd.to_datetime(df['time'], unit='s').dt.hour.values
    print(f'LAYER=S{LAYER} | src={d["src"]} | TF={TF} | bars={n} | {pd.to_datetime(t[0],unit="s")} → {pd.to_datetime(t[-1],unit="s")} | split_bar={n//2}', flush=True)
    atr = atr21(h, l, c); rng_ = h - l
    valid = ~np.isnan(atr)
    sig = valid & (hr == HOUR) & (rng_ >= THETA * atr) & (c != o)
    dirn = np.sign(c - o)
    ls = sig & (dirn > 0); ss = sig & (dirn < 0)
    sl = np.where(valid, KSL * atr / PIP, 0.0); tp = sl * RR
    tr = se.simulate_trades(df, ls, ss, sl, tp, 'XAUUSD', max_hold=MH, allow_overlap=False)
    nL = int((tr['direction'] == 'long').sum()); nS = len(tr) - nL
    print(f'signals long={int(ls.sum())} short={int(ss.sum())} | trades n={len(tr)} (L={nL},S={nS}) WR={100*(tr["pnl_pip"]>0).mean():.2f}', flush=True)

    # نول متعارف: uncond + K=500 جایگشت با حفظ nL/nS، از همهٔ کندل‌های معتبر (نه فقط ساعت 08 — نول بی‌قید نشست)
    rng = np.random.default_rng(LAYER)
    vi = np.where(valid)[0]; zero = np.zeros(n, bool); null = {}
    for side, ns in (('long', nL), ('short', nS)):
        dd = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)
        if ns >= 1:
            s_all = np.zeros(n, bool); s_all[vi] = True
            ta = se.simulate_trades(df, s_all if side == 'long' else zero, zero if side == 'long' else s_all,
                                    sl, tp, 'XAUUSD', max_hold=MH, allow_overlap=True)
            dd['uncond_wr'] = float(100 * (ta['pnl_pip'] > 0).mean())
            wrs = []
            for _ in range(K_PERM):
                pick = vi[np.sort(rng.choice(len(vi), ns, replace=False))]
                s2 = np.zeros(n, bool); s2[pick] = True
                tp_ = se.simulate_trades(df, s2 if side == 'long' else zero, zero if side == 'long' else s2,
                                         sl, tp, 'XAUUSD', max_hold=MH, allow_overlap=True)
                if len(tp_):
                    wrs.append(float(100 * (tp_['pnl_pip'] > 0).mean()))
            a = np.asarray(wrs)
            dd.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = dd
        print(f'  null {side}: {json.dumps(dd)}', flush=True)

    med_sl = float(np.median(tr['sl_pip'])) if 'sl_pip' in tr else float(np.nanmedian(sl[sl > 0]))
    r = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=med_sl, tp_pip=med_sl * RR, bar_time=t, null=null,
                          n_trials=N_TRIALS, split_bar=n // 2, close=c)
    print('\n' + rqs2.format_rqs2(f'S{LAYER}-{TF}', r), flush=True)
    safe = lambda m: {k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v)) for k, v in m.items()}
    out = dict(layer=LAYER, tf=TF, src=d['src'], prereg='strategies/S798_PREREG.md@8c5a19d8',
               rule=dict(hour_utc=HOUR, theta=THETA, ksl=KSL, rr=RR, mh=MH), n_trials=N_TRIALS, split_bar=n // 2,
               null=null, verdict=r['verdict'], rqs2_score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics=safe(r.get('metrics', {})), notes=r.get('notes'))
    with open(os.path.join(HERE, f's{LAYER}_final_result_{TF}.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    tr.to_json(os.path.join(HERE, f's{LAYER}_trades_{TF}.json'), orient='records')
    print(f"\n[S{LAYER} OFFICIAL] {r['verdict']} score={r.get('rqs2_score')}", flush=True)


if __name__ == '__main__':
    main()
