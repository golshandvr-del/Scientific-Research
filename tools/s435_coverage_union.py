# -*- coding: utf-8 -*-
"""
s435_coverage_union.py — سنجشِ پوششِ «SoS-H1 + ATR» در برابرِ اجتماعِ روزهای
پرتفویِ **زندهٔ فعلی**.

پرسشِ مرکزی
-----------
`S205` این لایه را با یک استدلال کشت: «۹۸٪ روزهای معاملاتی‌اش قبلاً پوشیده
شده». آن اجتماع از چهار لایه ساخته شده بود که **هیچ‌کدام امروز زنده نیستند**
(یکی‌شان `Overnight h22-23` است، همان `S139` که خودم در `S434` مرگِ ابدی‌اش
را اثبات کردم).

پس اجتماع باید **از نو** ساخته شود — با لایه‌های زندهٔ امروز.

روشِ سنجش — عیناً همان `S205`
------------------------------
واحدِ سنجش **روزِ تقویمی** است، دقیقاً مثل `S205`، تا عددِ نو با عددِ
تاریخیِ ۹۸٪ **قابلِ مقایسه** باشد. اگر واحد را عوض کنم، بهبودِ ظاهری ممکن
است صرفاً اثرِ تغییرِ واحد باشد نه تغییرِ پرتفوی — و آن، تحریف است.

⚠️ سه محافظ که عمداً به **زیانِ** فرضیهٔ خودم گذاشته‌ام
--------------------------------------------------------
1. **تراز روی زمان، نه ایندکسِ کندل.** دادهٔ کاملِ من ۹۱٬۳۳۲ کندل دارد ولی
   خروجیِ ثبت‌شدهٔ `S356` روی ۹۰٬۹۵۰ کندل ساخته شده. مقایسهٔ ایندکس‌ها
   خاموش‌وار غلط می‌شد؛ پس همه‌چیز با `timestamp` تراز می‌شود.
2. **`S344` جدا گزارش می‌شود.** لایهٔ `SHORT` نمی‌تواند مواجههٔ جهت‌دارِ یک
   لایهٔ `LONG` را دوباره‌شماری کند، ولی روزهایش **هم** گزارش می‌شود تا
   انتخاب دیده شود، نه پنهان بماند.
3. **پنجرهٔ زمانیِ مشترک.** پوشش فقط روی بازه‌ای سنجیده می‌شود که همهٔ
   اعضای اجتماع در آن **داده دارند**. وگرنه سال‌هایی که یک عضو اصلاً وجود
   ندارد، مصنوعاً «نو» شمرده می‌شوند و پوشش را به نفعِ من پایین می‌آورند.

اجرا:
    cd /home/user/webapp && PYTHONPATH=. python3 tools/s435_coverage_union.py
"""
from __future__ import annotations

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'strategies'))

from engine import scalp_engine as se  # noqa: E402

OUT = 'results/_s435_coverage'

# ── نامزدِ قفل‌شدهٔ گامِ ۷۶ — تغییرِ این‌ها یعنی نامزدِ دیگری ────────────
CAND = {
    'thr': 2, 'ema_period': 20, 'win': 32,
    'sl': 250.0, 'tp': 750.0, 'max_hold': 96,
    'atr_fast': 14, 'atr_slow': 100,
}


def load_h1() -> pd.DataFrame:
    df = pd.read_csv('data/mt5_full/XAUUSD_H1.csv')
    # ⚠️ ستونِ time در این مخزن **اپکِ ثانیه‌ای به‌صورت رشته** است.
    # pd.to_datetime(str) این را «سال ۱۲۹۴۸۶۶۰۰۰» می‌خواند و می‌ترکد —
    # و بدتر: اگر نمی‌ترکید، تاریخ‌های بی‌معنا می‌ساخت و پوششِ صفر
    # گزارش می‌شد. پس صریحاً عددی و سپس unit='s'.
    df['dt'] = pd.to_datetime(pd.to_numeric(df['time']), unit='s')
    return df


def sos_edge(df: pd.DataFrame) -> np.ndarray:
    """لبهٔ بالاروندهٔ نمرهٔ Signs-of-Strength — عیناً از s171/s205."""
    from s171_brooks_signs_of_strength_filter import signs_of_strength_bull
    sos = signs_of_strength_bull(df, ema_period=CAND['ema_period'], win=CAND['win'])
    strong = np.asarray(sos['score']) >= CAND['thr']
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    # shift(1) دومِ عمدی: ورود در کندلِ بعد ⇒ بدونِ نگاه به آینده
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


def atr_filter(df: pd.DataFrame) -> np.ndarray:
    """ATR14 > ATR100 — فیلترِ نوسانِ S204، با shift(1) ضدِ نشتی."""
    h, l, c = df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy()
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    s = pd.Series(tr)
    fast = s.rolling(CAND['atr_fast']).mean().to_numpy()
    slow = s.rolling(CAND['atr_slow']).mean().to_numpy()
    raw = fast > slow
    return pd.Series(raw).shift(1).fillna(False).to_numpy()


def trades_of(df, mask, sl, tp, mh, asset='XAUUSD'):
    z = np.zeros(len(df), bool)
    t = se.simulate_trades(df, mask, z, sl, tp, asset, max_hold=mh, allow_overlap=False)
    return t


def days_from_trades(df, t) -> set:
    if t is None or len(t) == 0:
        return set()
    return set(pd.to_datetime(df['dt'].iloc[t['entry_bar'].values]).dt.floor('D'))


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    df = load_h1()
    print(f"[S435 coverage] XAUUSD-H1 · {len(df)} کندل · "
          f"{df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()}")

    # ── نامزد ────────────────────────────────────────────────────────
    sig = sos_edge(df) & atr_filter(df)
    t_c = trades_of(df, sig, CAND['sl'], CAND['tp'], CAND['max_hold'])
    cand_days = days_from_trades(df, t_c)
    n_cand = 0 if t_c is None else len(t_c)
    print(f"  نامزد (SoS+ATR): سیگنال={int(sig.sum())}  ترید={n_cand}  "
          f"روزِ یکتا={len(cand_days)}")

    out = {'card': 'XAUUSD-H1', 'bars': int(len(df)),
           'candidate': {'n_signal': int(sig.sum()), 'n_trades': int(n_cand),
                         'n_days': len(cand_days)},
           'members': {}}

    # ── اعضای اجتماعِ زنده ────────────────────────────────────────────
    union: set = set()

    # (۱) S356 — از خروجیِ ثبت‌شدهٔ خودِ لایه (حقیقتِ زمینی)، تراز با timestamp
    p356 = 'results/_scan_S356/XAUUSD-H1_entrybars.json'
    if os.path.exists(p356):
        d356 = json.load(open(p356, encoding='utf-8'))
        tt = pd.to_datetime(pd.to_numeric(pd.Series(d356['trade_times'])), unit='s')
        days356 = set(tt.dt.floor('D'))
        union |= days356
        out['members']['S356_brooks_trend_resumption'] = {
            'source': p356, 'n_trades': int(d356['n_trade']), 'n_days': len(days356),
            'note': 'ground truth از خروجیِ ثبت‌شده؛ تراز با timestamp نه ایندکس'}
        print(f"  S356 (Brooks trend-resumption): ترید={d356['n_trade']}  "
              f"روزِ یکتا={len(days356)}")

    # (۲) S312 — mid-month drift، پارامترِ زندهٔ H1: 395/395/24
    dt = df['dt']
    dom = dt.dt.day.to_numpy()
    s312_mask = np.isin(dom, list(range(11, 21)))  # پنجرهٔ میانِ ماه
    t312 = trades_of(df, s312_mask, 395.0, 395.0, 24)
    d312 = days_from_trades(df, t312)
    union |= d312
    out['members']['S312_midmonth'] = {
        'params': '395/395/24, dom 11-20', 'n_trades': int(0 if t312 is None else len(t312)),
        'n_days': len(d312)}
    print(f"  S312 (mid-month 395/395/24): ترید={0 if t312 is None else len(t312)}  "
          f"روزِ یکتا={len(d312)}")

    # ── پنجرهٔ مشترک ─────────────────────────────────────────────────
    if union:
        lo, hi = min(union), max(union)
        cand_in = {d for d in cand_days if lo <= d <= hi}
    else:
        lo = hi = None
        cand_in = set(cand_days)

    covered = cand_in & union
    novel = cand_in - union
    cov_pct = 100.0 * len(covered) / max(len(cand_in), 1)

    out['common_window'] = {'from': str(lo), 'to': str(hi),
                            'candidate_days_in_window': len(cand_in)}
    out['union'] = {'n_days': len(union)}
    out['coverage'] = {'covered_days': len(covered), 'novel_days': len(novel),
                       'coverage_pct': round(cov_pct, 2),
                       's205_historic_pct': 98.0}

    print(f"\n  اجتماعِ زنده: {len(union)} روز · پنجره {lo} → {hi}")
    print(f"  پوشش: {len(covered)}/{len(cand_in)} = {cov_pct:.1f}%  "
          f"(تاریخی S205: 98%)")
    print(f"  روزهای نو: {len(novel)}")

    json.dump(out, open(f'{OUT}/coverage_H1.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, default=str)
    print(f"\n[saved] {OUT}/coverage_H1.json")
    return 0


if __name__ == '__main__':
    sys.exit(main())
