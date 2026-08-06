# -*- coding: utf-8 -*-
"""
اعتبارسنجیِ هم‌ارزیِ حل‌کنندهٔ برداری با موتورِ رسمی
================================================================================
این آزمون پیش‌شرطِ استفاده از `tools/audit_fast_null.py` در هر داوری است.

منطقِ آزمون از خودِ اشتباهاتِ پروژه بیرون آمده: پروژه یک‌بار از این آسیب دید که
«دانشِ سربه‌سر در یک ابزار بود و در ابزارِ حسابرسی نبود» — یعنی دو پیاده‌سازیِ
یک چیز واگرا شدند و هیچ‌کس نفهمید. پس معیارِ پاس اینجا **آماری نیست، دقیق است**:

    برای هر مجموعهٔ ورودِ یکسان، حل‌کنندهٔ برداری باید **همان تعدادِ معامله** و
    **همان WR** را بدهد که `se.simulate_trades` می‌دهد.

اگر حتی یک معامله اختلاف داشت، آزمون رد می‌شود و علتش چاپ می‌شود — چون یک
معاملهٔ اختلاف در نول یعنی `perm_sd` جابه‌جا شده، و `perm_sd` مخرجِ `z` است.

پوششِ آزمون **عمداً** روی سه محورِ حساس است:
  · دو دارایی با اسلیپیجِ متفاوت (`XAUUSD` slip=0، `EURUSD` slip=0.3)
  · دو سمت (`long`/`short`) — چون علامتِ اسلیپیج و ترتیبِ سدها قرینه است
  · دو رژیمِ افق (کوتاه `max_hold=16` و عملاً بی‌سقف) و دو هندسه (`rr=1` و `rr=1.5`)
"""
from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                    # noqa: E402
from tools.audit_fast_null import (                      # noqa: E402
    resolve_all_entries, wr_of_positions)
from tools.audit_rqs2_rejudge import load_card           # noqa: E402


def official_wr(df, asset, pos, sl_pip, tp_pip, max_hold, side):
    """همان محاسبه با موتورِ رسمی — مرجعِ حقیقت."""
    n = len(df)
    m = np.zeros(n, bool)
    m[pos] = True
    ls = m if side == 'long' else np.zeros(n, bool)
    ss = m if side == 'short' else np.zeros(n, bool)
    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset,
                            max_hold=max_hold, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None, 0
    return 100.0 * float((tr['outcome'] == 'win').mean()), len(tr)


def fast_wr(df, asset, pos, sl_pip, tp_pip, max_hold, side):
    pnl, xb, win, valid = resolve_all_entries(
        df, asset, sl_pip, tp_pip, max_hold, side)
    return wr_of_positions(np.sort(np.asarray(pos)), xb, win, valid, min_n=1)


def main():
    rng = np.random.default_rng(4242)
    cases = []
    for asset, tf in (('XAUUSD', 'M15'), ('EURUSD', 'M15')):
        df = load_card(asset, tf)
        if df is None:
            print(f'[skip] {asset}-{tf} data missing')
            continue
        n = len(df)
        # زیرنمونهٔ داده برای سرعتِ مرجع؛ مکانیک به طولِ داده حساس نیست
        df = df.iloc[:40000].reset_index(drop=True)
        n = len(df)
        sl_base = 40.0 if asset == 'XAUUSD' else 12.0
        for side in ('long', 'short'):
            for rr in (1.0, 1.5):
                for mh in (16, n + 1):
                    pos = np.sort(rng.choice(np.arange(210, n - 2),
                                             size=1200, replace=False))
                    cases.append((df, asset, tf, pos, sl_base,
                                  sl_base * rr, mh, side, rr))

    print(f'{"case":<44} {"official":>18} {"fast":>18}  verdict')
    print('-' * 92)
    all_ok = True
    for df, asset, tf, pos, sl, tp, mh, side, rr in cases:
        w_o, n_o = official_wr(df, asset, pos, sl, tp, mh, side)
        w_f, n_f = fast_wr(df, asset, pos, sl, tp, mh, side)
        same_n = (n_o == n_f)
        same_w = (w_o is None and w_f is None) or (
            w_o is not None and w_f is not None and abs(w_o - w_f) < 1e-9)
        ok = same_n and same_w
        all_ok &= ok
        mh_tag = 'unbounded' if mh > 1000 else f'mh={mh}'
        tag = f'{asset}-{tf} {side:<5} rr={rr} {mh_tag}'
        print(f'{tag:<44} {f"{w_o}" if w_o is None else f"{w_o:.6f}":>10}/{n_o:<7} '
              f'{f"{w_f}" if w_f is None else f"{w_f:.6f}":>10}/{n_f:<7} '
              f'{"EXACT MATCH" if ok else "*** MISMATCH ***"}')

    print('-' * 92)
    print('RESULT:', 'ALL EXACT — fast solver is admissible' if all_ok
          else 'MISMATCH — fast solver MUST NOT be used')
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
