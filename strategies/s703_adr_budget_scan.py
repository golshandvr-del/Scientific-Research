#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S703 — اتمامِ بودجهٔ دامنهٔ روزانه (ADR Budget Exhaustion): فازِ جست‌وجو
پیش‌ثبت: results/S703_PREREG_ADR_BUDGET_EXHAUSTION.md (commit 0ebf3b6e)

قفل‌شده‌ها:
  k ∈ {1.0,1.3,1.6} · mode ∈ {fade,cont} · f_sl ∈ {0.25,0.40} · RR=1.5
  ADR20 = میانگینِ high−lowِ ۲۰ روزِ کاملِ قبل (علّی)
  رویداد = نخستین کندلِ روز با cum_range >= k·ADR20؛ جهت از لبهٔ شکسته
  ورود = openِ کندلِ بعد · SEED=703 · K_PERM=200 · n_trials=228
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from tools import s434_fast_data as fd

SEED = 703
K_PERM = 200
KS = [1.0, 1.3, 1.6]
F_SLS = [0.25, 0.40]
RR = 1.5
ADR_N = 20
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s703')
os.makedirs(OUT_DIR, exist_ok=True)

MAX_HOLD = {'M1':240,'M3':240,'M4':240,'M5':240,'M6':240,
            'M10':120,'M12':120,'M15':120,'M20':120,'M30':120,
            'H1':64,'H2':64,'H3':64,'H6':32,'H8':32,'H12':32}
TFS = ['M1','M3','M4','M5','M6','M10','M12','M15','M20','M30',
       'H1','H2','H3','H6','H8','H12']   # D1/W1/MN1: رویدادِ درون‌روزی ندارند


def day_structures(df):
    """
    ساختارهای روزانهٔ علّی:
      day_id, cum_high/cum_low (تا همین کندل)، adr20 (۲۰ روزِ *کاملِ* قبل).
    """
    t = pd.to_datetime(df['time'].values, unit='s', utc=True)
    day = t.floor('D')
    day_id = pd.Series(day).factorize()[0]
    h = df['high'].values; l = df['low'].values
    dfx = pd.DataFrame({'day': day_id, 'h': h, 'l': l})
    cum_high = dfx.groupby('day')['h'].cummax().values
    cum_low = dfx.groupby('day')['l'].cummin().values
    # دامنهٔ کاملِ هر روز ⇒ ADR علّی (شیفتِ ۱ روز، رولینگِ ۲۰)
    day_rng = dfx.groupby('day').agg(hi=('h', 'max'), lo=('l', 'min'))
    day_rng['rng'] = day_rng['hi'] - day_rng['lo']
    adr = day_rng['rng'].shift(1).rolling(ADR_N).mean()   # فقط روزهای قبل
    adr_by_day = adr.values
    adr_bar = adr_by_day[day_id]
    return day_id, cum_high, cum_low, adr_bar


def build_events(df, k):
    """
    رویداد: نخستین کندلِ هر روز که cum_range >= k*ADR20.
    جهتِ لبه: کندلِ رویداد سقفِ نوِ روز ساخته (+1) یا کفِ نو (−1)؛
    اگر هر دو ⇒ جهتِ بدنهٔ همان کندل.
    خروجی: آرایهٔ int8 (0=هیچ، +1=up-edge، −1=down-edge)
    """
    day_id, cum_high, cum_low, adr_bar = day_structures(df)
    h = df['high'].values; l = df['low'].values
    o = df['open'].values; c = df['close'].values
    n = len(df)
    cum_range = cum_high - cum_low
    hit = (cum_range >= k * adr_bar) & np.isfinite(adr_bar)
    # نخستینِ هر روز: hit و (کندلِ قبل هم‌روز نبوده یا hit نبوده)
    prev_same_day = np.zeros(n, dtype=bool)
    prev_same_day[1:] = day_id[1:] == day_id[:-1]
    prev_hit = np.zeros(n, dtype=bool)
    prev_hit[1:] = hit[:-1]
    first = hit & ~(prev_same_day & prev_hit)
    # جهتِ لبه در کندلِ رویداد
    new_high = h >= cum_high - 1e-12       # این کندل سقفِ روز را ساخته
    new_low = l <= cum_low + 1e-12
    edge = np.zeros(n, dtype=np.int8)
    body = np.sign(c - o).astype(np.int8)
    both = new_high & new_low
    edge[new_high & ~new_low] = 1
    edge[new_low & ~new_high] = -1
    edge[both] = body[both]
    ev = np.zeros(n, dtype=np.int8)
    m = first & (edge != 0)
    ev[m] = edge[m]
    return ev


def unit_test():
    """آزمونِ واحدِ مصنوعی — پاسخِ معلوم. شکست ⇒ توقف."""
    # ۲۵ روز، هر روز ۴ کندلِ ۶ساعته. ۲۰ روزِ اول دامنهٔ 10.
    rows = []
    t0 = 1_600_041_600  # 2020-09-14 00:00:00 UTC — نیمه‌شبِ دقیق؛ هم‌مرزی با floor('D') الزامی است
    for d in range(25):
        base = 100.0 + d
        if d < 21:
            # دامنهٔ روز = 10، به‌تدریج در ۴ کندل
            candles = [(base, base+3, base-2, base+1),
                       (base+1, base+5, base, base+4),
                       (base+4, base+8, base+3, base+6),
                       (base+6, base+8, base-2, base+7)]
        elif d == 21:
            # روزِ انفجاری: کندلِ ۳ (اندیس ۲) دامنهٔ تجمعی را از ADR=10 رد می‌کند
            candles = [(base, base+4, base-1, base+3),      # cum=5
                       (base+3, base+7, base+1, base+6),    # cum=8
                       (base+6, base+12, base+2, base+11),  # cum=13 ≥ 10 ⇒ رویداد، سقفِ نو ⇒ +1
                       (base+11, base+12, base+9, base+10)]
        else:
            candles = [(base, base+2, base-2, base+1),
                       (base+1, base+3, base, base+2),
                       (base+2, base+4, base+1, base+3),
                       (base+3, base+4, base-1, base+2)]
        for i, (o, h, l, c) in enumerate(candles):
            rows.append(dict(time=t0 + d*86400 + i*21600, open=o, high=h, low=l, close=c))
    df = pd.DataFrame(rows)
    # k=1.2 ⇒ آستانه = 1.2×ADR20 = 12؛
    # روزهای عادی: دامنهٔ تجمعیِ بیشینه = 10 < 12 (اکیداً زیر آستانه — بدونِ ابهامِ مرزی)؛
    # روزِ انفجاری (21): تجمعی در کندلِ اندیس 2 برابرِ 13 ≥ 12 ⇒ تنها رویداد، سقفِ نو ⇒ +1.
    ev = build_events(df, 1.2)
    idx = np.nonzero(ev)[0]
    assert idx.tolist() == [86], f'unit test FAILED: expected exactly [86], got {idx.tolist()}'
    assert ev[86] == 1, f'unit test FAILED: expected up-edge at 86, got {ev[86]}'
    return {'events': idx.tolist(), 'dirs': ev[idx].tolist()}


def scan_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)
    max_hold = MAX_HOLD[tf]
    pip = 0.1

    # ADR بر حسبِ pip از نیمهٔ جست‌وجو (برای هندسه: میانهٔ ADR علّی)
    _, _, _, adr_bar = day_structures(df)
    adr_med_pip = float(np.nanmedian(adr_bar)) / pip

    rng = np.random.default_rng(SEED)
    out = {'tf': tf, 'src': d['src'], 'n_full': int(n_full), 'half_bar': int(half),
           'seed': SEED, 'adr20_med_pip': adr_med_pip, 'rr': RR,
           'k_perm': K_PERM, 'cells': []}

    null_cache = {}
    def uncond_wr(f_sl, side, n_sample=12000):
        key = (f_sl, side)
        if key in null_cache:
            return null_cache[key]
        sl_pip = f_sl * adr_med_pip
        tp_pip = RR * sl_pip
        n_bars = len(df)
        lo = 200; hi = n_bars - max_hold - 2
        if hi <= lo:
            null_cache[key] = (float('nan'), 0)
            return null_cache[key]
        idx = rng.choice(np.arange(lo, hi), size=min(n_sample, n_bars // 4),
                         replace=False)
        sig = np.zeros(n_bars, dtype=bool); sig[idx] = True
        s_ser = pd.Series(sig, index=df.index)
        f_ser = pd.Series(np.zeros(n_bars, dtype=bool), index=df.index)
        tr_ = se.simulate_trades(df, s_ser if side == 'long' else f_ser,
                                 f_ser if side == 'long' else s_ser,
                                 sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                 max_hold=max_hold, allow_overlap=True)
        wr = float((tr_['outcome'] == 'win').mean() * 100) if len(tr_) else float('nan')
        null_cache[key] = (wr, int(len(tr_)))
        return null_cache[key]

    for k in KS:
        ev = build_events(df, k)
        # ورود در کندلِ بعد ⇒ شیفتِ سیگنال
        ev_next = np.zeros_like(ev)
        ev_next[1:] = ev[:-1]
        for mode in ('fade', 'cont'):
            sgn = -1 if mode == 'fade' else 1
            long_sig = pd.Series(ev_next == sgn * 1, index=df.index) if sgn == 1 else \
                       pd.Series(ev_next == -1, index=df.index)
            # fade: up-edge ⇒ شورت، down-edge ⇒ لانگ | cont: هم‌جهت
            if mode == 'cont':
                ls = pd.Series(ev_next == 1, index=df.index)
                ss = pd.Series(ev_next == -1, index=df.index)
            else:
                ls = pd.Series(ev_next == -1, index=df.index)
                ss = pd.Series(ev_next == 1, index=df.index)
            for f_sl in F_SLS:
                sl_pip = f_sl * adr_med_pip
                tp_pip = RR * sl_pip
                tr_ = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                                         asset='XAUUSD', max_hold=max_hold,
                                         allow_overlap=False)
                n = int(len(tr_))
                cell = {'k': k, 'mode': mode, 'f_sl': f_sl,
                        'sl_pip': round(sl_pip, 2), 'tp_pip': round(tp_pip, 2),
                        'n': n}
                if n >= 30:
                    pnl = tr_['pnl_pip'].to_numpy()
                    wr = float((pnl > 0).mean() * 100)
                    gp = float(pnl[pnl > 0].sum()); gl = float(-pnl[pnl < 0].sum())
                    pf = (gp / gl) if gl > 0 else float('inf')
                    n_l = int((tr_['direction'] == 'long').sum())
                    uw_l, _ = uncond_wr(f_sl, 'long')
                    uw_s, _ = uncond_wr(f_sl, 'short')
                    uw = (uw_l * n_l + uw_s * (n - n_l)) / n
                    alpha = wr - uw
                    z = alpha/100*np.sqrt(n)/np.sqrt(uw/100*(1-uw/100)) if 0 < uw < 100 else float('nan')
                    n_req = (3.09*100*np.sqrt(uw/100*(1-uw/100))/alpha)**2 if alpha > 0 else None
                    cell.update({'wr': round(wr, 3), 'uncond_wr': round(uw, 3),
                                 'alpha_pp': round(alpha, 3), 'z': round(float(z), 3),
                                 'pf': round(pf, 3),
                                 'exp_pip': round(float(pnl.mean()), 3),
                                 'n_long': n_l,
                                 'n_req': round(n_req, 0) if n_req else None})
                out['cells'].append(cell)
    out['elapsed_s'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT_DIR, f'scan_{tf}.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else TFS
    utp = os.path.join(OUT_DIR, 'unit_test.json')
    if not os.path.exists(utp):
        rep = unit_test()
        with open(utp, 'w') as f:
            json.dump(rep, f)
        print('UNIT TEST OK', rep, flush=True)
    for tf in tfs:
        p = os.path.join(OUT_DIR, f'scan_{tf}.json')
        if os.path.exists(p):
            print(f'{tf}: already scanned, skip', flush=True)
            continue
        r = scan_tf(tf)
        best = sorted([c for c in r['cells'] if 'z' in c],
                      key=lambda c: -(c.get('z') or -9))[:3]
        print(f"{tf}: done {r['elapsed_s']}s adr={r['adr20_med_pip']:.0f}pip "
              f"top3={[(c['k'],c['mode'],c['f_sl'],c['n'],c.get('alpha_pp'),c.get('pf'),c.get('z')) for c in best]}",
              flush=True)
