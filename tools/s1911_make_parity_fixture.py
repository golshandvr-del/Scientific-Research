# -*- coding: utf-8 -*-
"""S1911 — ساختِ fixture برای پریتیِ پایتون ↔ TypeScript · XAUUSD-H8

چرا لازم است: ماژولِ TS (web_tool/src/kyle_shock_calm_s1911.ts) باید **عیناً**
همان رویدادهایی را بدهد که مرجعِ پایتون (strategies/s1911_kyle_shock_calm.py)
داوری‌شان کرده. اگر یک کندل اختلاف باشد، سایت چیزی نشان می‌دهد که هرگز
ACCEPT نگرفته است. پس پیش از وصل کردن، پریتی سنجیده می‌شود.

روش (عینِ الگوی parity_s965_signal.mjs):
  • مرجع روی **کلِ تاریخِ H8** محاسبه می‌شود (همان چیزی که داور دید).
  • fixture شاملِ ۳۰۰۰ کندلِ آخر است تا آزمون بتواند نشان دهد پورت به
    warm-up وابسته نیست — ولی توجه: گیتِ آرامش ۲۳۳+۵۰ کندل حافظه دارد،
    پس آستانهٔ مقایسه باید از ۲×(۲۳۳+۵۰) به بعد باشد، نه ۲×۲۲.
  • برای اینکه پنجرهٔ ۳۰۰۰ کندلی خودش به‌تنهایی σ را گرم کند، سری‌های
    مرجع هم روی همان پنجره‌ی برشی دوباره حساب نمی‌شوند: مقادیرِ «کل-تاریخ»
    ذخیره می‌شوند و TS باید با پنجرهٔ برشی به همان‌ها برسد.

خروجی: results/_s1911_ckpt/parity_h8_fixture.json
اجرا:  python3 tools/s1911_make_parity_fixture.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import strategies.s1911_kyle_shock_calm as S19            # noqa: E402
import strategies.s605_engle_sigma_regime as S5           # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s1911_ckpt')
OUT_FILE = os.path.join(OUT_DIR, 'parity_h8_fixture.json')
TAIL = 3000
TF = 'H8'


def main():
    df = S19.load_df(TF)
    n = len(df)

    # ── سری‌های مرجع، روی کلِ تاریخ (همان چیزی که داور دید) ──────────────
    shock, rho, body_sgn, atr_prev, reg = S19.features(df)
    sigma = S5.sigma_series(df['close'].to_numpy(float))

    # ── رویدادهای بازوی «gated» (بازوی داوری‌شده) ────────────────────────
    warm = max(S19.ATR_WIN, S19.W_CALM + 60) + 2
    idx = np.arange(n)
    ev_base = (shock & (rho >= S19.RHO_MIN) & (body_sgn != 0)
               & (idx >= warm) & ~np.isnan(reg))
    ev = ev_base & (reg <= 1.0)

    idx_long = np.flatnonzero(ev & (body_sgn > 0)).tolist()
    idx_short = np.flatnonzero(ev & (body_sgn < 0)).tolist()

    # بازوی ungated برای ثبتِ اینکه گیت چند رویداد را حذف کرد (شفافیت)
    n_ungated = int(ev_base.sum())

    lo = max(0, n - TAIL)
    candles = [
        {'time': int(t), 'open': float(o), 'high': float(h),
         'low': float(l), 'close': float(c)}
        for t, o, h, l, c in zip(
            df['time'].to_numpy()[lo:], df['open'].to_numpy(float)[lo:],
            df['high'].to_numpy(float)[lo:], df['low'].to_numpy(float)[lo:],
            df['close'].to_numpy(float)[lo:])
    ]

    def nz(a):
        return [None if not np.isfinite(v) else float(v) for v in a]

    fx = {
        'what': 'fixture پریتیِ S1911 (پایتون مرجع ↔ TS) روی XAUUSD-H8',
        'src': df.attrs.get('src', '?'),
        'bars_total': int(n),
        'tail': len(candles),
        'offset': int(lo),          # candles[k] ≡ ایندکسِ کلِ تاریخِ lo+k
        'cfg': {
            'theta': S19.THETA, 'rho_min': S19.RHO_MIN, 'atr_win': S19.ATR_WIN,
            'k_sl': S19.K_SL, 'k_tp': S19.K_TP, 'max_hold': S19.MAX_HOLD,
            'w_calm': S19.W_CALM, 'lam': float(S5.LAMBDA), 'reg_max': 1.0,
            'warm': int(warm),
        },
        'candles': candles,
        'py': {
            'idx_long': idx_long,
            'idx_short': idx_short,
            'n_events_gated': len(idx_long) + len(idx_short),
            'n_events_ungated': n_ungated,
            'atr_prev': nz(atr_prev),
            'rho': nz(rho),
            'reg': nz(reg),
            'sigma': nz(sigma),
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, 'w') as fh:
        json.dump(fx, fh)
    print(f'[fixture] {OUT_FILE}')
    print(f'  bars={n} tail={len(candles)} offset={lo}')
    print(f'  gated events={fx["py"]["n_events_gated"]} '
          f'(ungated={n_ungated}) long={len(idx_long)} short={len(idx_short)}')
    print(f'  lam={S5.LAMBDA} W_calm={S19.W_CALM} warm={warm}')


if __name__ == '__main__':
    main()
