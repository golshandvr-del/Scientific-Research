# -*- coding: utf-8 -*-
"""S919 — ساختِ fixtureِ پریتی برای اثباتِ تطابقِ پورتِ TS با پایتونِ داوری‌شده.

روش (عینِ الگوی S966): مرجعِ پایتون روی **کلِ ۱۵.۶ سال** محاسبه می‌شود، ولی
fixture فقط ۳۰۰۰ کندلِ آخر را حمل می‌کند. عمیق‌ترین نگاهِ به‌عقبِ S919 گیتِ
قرارداد است (K=240 + ۱) ⇒ برای ایندکس‌های ≥ ۲×۲۴۱ خروجیِ «فقط-پنجره» باید
عیناً با «کل-تاریخ» یکی باشد. اگر پورت به warm-up وابسته باشد، همین‌جا لو می‌رود.

خروجی: results/_s919_ckpt/parity_h6_fixture.json
  candles      : ۳۰۰۰ کندلِ آخر (time/open/high/low/close)
  py.idx_event : ایندکسِ **کندلِ رویداد** (بازوی gated) — نه ایندکسِ ماسک
  py.idx_mask_long/short : ایندکسِ ماسکِ pre-shift (رویداد+۱) — دامِ ④
  py.atr_prev, py.rho, py.shock, py.drift_up, py.drift_dn : بردارها
  py.sl_pip, py.tp_pip : هندسهٔ شناورِ هر سیگنال (از atr_prev[mask])
  py.trade_entry_bar   : ورودِ واقعیِ موتور (باید = رویداد+۲)

اجرا: python3 tools/s919_make_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from strategies import s919_convention_aligned_shock as s   # noqa: E402

TF = 'H6'
TAIL = 3000
OUT = os.path.join(ROOT, 'results', '_s919_ckpt', 'parity_h6_fixture.json')


def main() -> None:
    df = s.load_df(TF)
    n = len(df)
    K = s.DRIFT_K[TF]

    # --- بردارهای پایه روی کلِ تاریخ ---
    shock, rho, body_sgn, atr_prev = s.features(df)
    c = df['close'].to_numpy(float)
    warm = s.ATR_WIN + K + 2
    idx = np.arange(n)
    ev = shock & (rho >= s.RHO_MIN) & (body_sgn != 0) & (idx >= warm)
    drift = np.full(n, np.nan)
    drift[K + 1:] = c[K:-1] - c[:-K - 1]
    up = ev & (body_sgn > 0) & (drift > 0)
    dn = ev & (body_sgn < 0) & (drift < 0)

    # --- ماسکِ pre-shift عیناً مثلِ signals() ---
    lm, sm, sl_arr, tp_arr, warm2 = s.signals(df, TF, 'gated')
    assert warm2 == warm

    tr = s.run(df, lm, sm, sl_arr, tp_arr)

    off = n - TAIL          # ایندکسِ جهانیِ نخستین کندلِ fixture
    def loc(g):             # جهانی -> محلی
        return int(g - off)

    ev_idx_up = [loc(t) for t in np.flatnonzero(up) if t >= off]
    ev_idx_dn = [loc(t) for t in np.flatnonzero(dn) if t >= off]
    mask_long = [loc(t) for t in np.flatnonzero(lm) if t >= off]
    mask_short = [loc(t) for t in np.flatnonzero(sm) if t >= off]

    # هندسهٔ هر ماسک (پایتون sl_arr را در ایندکسِ ماسک می‌خواند)
    # ⚠️ **بدونِ گردکردن**: پریتی آستانهٔ ۱e−۹ دارد و round(·,6) روی عددی مثل
    #    ۲۳۰.۸۰۹۶ خطای نسبیِ ~۲e−۹ می‌سازد ⇒ آستانه را از دقتِ fixture سخت‌تر
    #    نمی‌کنیم؛ دقتِ کامل ذخیره می‌شود تا آزمون واقعاً سخت بماند.
    geom = {}
    for t in list(np.flatnonzero(lm)) + list(np.flatnonzero(sm)):
        if t >= off:
            geom[str(loc(t))] = [float(sl_arr[t]), float(tp_arr[t])]

    # ورودِ واقعیِ موتور برای معاملاتِ داخلِ پنجره
    entries = []
    for _, r in tr.iterrows():
        sb = int(r['signal_bar'])
        if sb >= off:
            entries.append({
                'mask_bar': loc(sb),
                'entry_bar': loc(int(r['entry_bar'])),
                'event_bar': loc(sb - 1),
                'direction': str(r['direction']),
                'sl_pip': round(float(r['sl_pip']), 6),
            })

    tail = df.iloc[off:]
    candles = [
        {
            'time': int(t), 'open': float(o), 'high': float(h),
            'low': float(l), 'close': float(cl),
        }
        for t, o, h, l, cl in zip(
            tail['time'].astype('int64').to_numpy() if np.issubdtype(tail['time'].dtype, np.number)
            else (tail['time'].astype('int64').to_numpy() // 10**9),
            tail['open'], tail['high'], tail['low'], tail['close'],
        )
    ]

    def vec(a, rnd=None):
        out = []
        for v in a[off:]:
            if isinstance(v, (bool, np.bool_)):
                out.append(bool(v))
            else:
                fv = float(v)
                out.append(None if not np.isfinite(fv) else (round(fv, rnd) if rnd else fv))
        return out

    payload = {
        'tf': TF,
        'src': df.attrs.get('src', '?'),
        'total_bars': int(n),
        'tail': TAIL,
        'offset': int(off),
        'K': int(K),
        'warm': int(warm),
        'cfg': {
            'theta': s.THETA, 'rho_min': s.RHO_MIN, 'atr_win': s.ATR_WIN,
            'k_sl': s.K_SL, 'k_tp': s.K_TP, 'max_hold': s.MAX_HOLD,
        },
        'candles': candles,
        'py': {
            'idx_event_long': ev_idx_up,
            'idx_event_short': ev_idx_dn,
            'idx_mask_long': mask_long,
            'idx_mask_short': mask_short,
            'atr_prev': vec(atr_prev, 10),
            'rho': vec(rho, 12),
            'shock': vec(shock),
            'body_sgn': vec(body_sgn),
            'drift_up': vec(drift > 0),
            'drift_dn': vec(drift < 0),
            'geom_by_mask': geom,
            'trades': entries,
        },
        'whole_history_totals': {
            'events_long': int(up.sum()), 'events_short': int(dn.sum()),
            'trades': int(len(tr)),
            'wr': round(100 * float((tr['pnl_pip'].to_numpy() > 0).mean()), 2),
        },
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False)
    print(f'wrote {OUT}')
    print('whole history:', payload['whole_history_totals'])
    print(f'fixture window: events L={len(ev_idx_up)} S={len(ev_idx_dn)} · '
          f'masks L={len(mask_long)} S={len(mask_short)} · trades={len(entries)}')


if __name__ == '__main__':
    main()
