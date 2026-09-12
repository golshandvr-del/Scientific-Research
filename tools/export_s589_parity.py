# -*- coding: utf-8 -*-
"""S589 — صادرکنندهٔ مرجعِ پریتی (پایتون ⇒ JSON) برای پورتِ TypeScript.

چرا این فایل **قبل** از هر خطِ TypeScript نوشته می‌شود
=====================================================
نشستِ S607 اثبات کرد شش دامِ پورت وجود دارد که با چشم دیده نمی‌شوند و فقط یک
مرجعِ بیت‌به‌بیت می‌گیردشان. پس اول مرجع، بعد پورت.

این فایل از **همان ماشینِ منجمدی** می‌خواند که حکمِ ACCEPT 88.3/86.3 را ساخت:
  · قاعدهٔ رویداد + گیت  ⇐ tools/s589_volume_fresh_high_runner.py
  · ATR و هندسه و شبیه‌ساز ⇐ strategies/s382_williamsr_momentum.py (هارنسِ ارثی)
هیچ‌کدام بازنویسی نمی‌شوند؛ import/بازتولیدِ عینی می‌شوند.

دام‌های پورتِ ثبت‌شده (هر کدام اگر رعایت نشود حکم را باطل می‌کند)
================================================================
① **گیت روی حجمِ هم‌اسلات است، نه حجمِ خام.** مرجع =
   `median(volume of the previous 30 bars sharing the same hour-of-day)`
   با `shift(1)` **درونِ گروهِ ساعت** و `min_periods=20`. اگر کسی آن را با
   میانهٔ ۳۰ کندلِ **متوالیِ** قبلی پورت کند، عملاً «گیتِ ساعتِ روز» ساخته
   (کندلِ لندن همیشه پرحجم، کندلِ آسیا همیشه کم‌حجم) — دقیقاً همان اشتباهی که
   §۱ پیش‌ثبت صریحاً رد کرد. جمعیتِ داوری‌شده عوض می‌شود.
② **ورود در `close` کندلِ سیگنال است، نه `open` کندلِ بعد.** شبیه‌سازِ ارثیِ
   S382 صریحاً `entry = close[e]` می‌گیرد و از کندلِ `e+1` به‌دنبالِ برخورد
   می‌گردد. (سندِ S589 §۲ عبارتِ «open کندل بعد» را دارد که توصیفِ اقتصادیِ
   همان لحظه است؛ **کدِ حاکم** close است.) پورتِ open ⇒ هندسهٔ دیگر.
③ **رویداد است نه حالت.** `nh & ~nh.shift(1)` — یک گردشِ چندکندلی بالای سقفِ
   ۹۰ **یک** فرصت است نه چند. حالت‌محور پورت‌کردن n را چند برابر می‌کند.
④ **هندسه از میانهٔ ATR100 روی کلِ ۱۵.۶ سال منجمد است** (H8 = 179.67 pip،
   H4 = 122.85 pip)، نه از پنجرهٔ زندهٔ سایت. ATR وایلدر است
   (`ewm(alpha=1/100, adjust=False)`) نه میانگینِ ساده. سایت نمی‌تواند این
   میانه را از پنجرهٔ کوتاهش بازتولید کند ⇒ عدد از همین مرجع import می‌شود،
   و در نتیجه **ATR در زمانِ اجرا لازم نیست**.
⑤ **بدونِ max_hold.** شبیه‌سازِ ارثی هیچ خروجِ زمانی ندارد؛ معامله تا برخوردِ
   SL/TP باز می‌ماند. کپی‌کردنِ maxHold=16 از S965 لایهٔ دیگری می‌سازد.
⑥ **SL در کندلِ مبهم برنده است** (بدبینانه‌ترین فرض) و معاملهٔ بازِ پایانِ داده
   حذف می‌شود.

خروجی: results/_s589_parity/{XAUUSD_H8,XAUUSD_H4}.json
  · سری‌های علّی (priorMax90, freshEdge, rvolSlot, gated)
  · شاخصِ همهٔ سیگنال‌ها + هندسهٔ منجمد
  · کارتِ H12 هم صادر می‌شود به‌عنوان **شاهدِ منفیِ اجراشدنی** (REJECT 25.1)
    تا اثبات شود وصل‌نشدنش تصمیمِ حکمی است نه سکوتِ پورت.

گیتِ سلامت: باید n_signals/n_trades/WR/SL/TP را عیناً از
results/_s589/XAUUSD_{H8,H4}_gated.json بازتولید کند، وگرنه SystemExit.

اجرا: python3 tools/export_s589_parity.py
"""
from __future__ import annotations

import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, 'results', '_s589_parity')

# ── ثابت‌های منجمد (عیناً از runnerِ کامیت‌شدهٔ S589) ─────────────────────────
LOOKBACK = 90
RVOL_THR = 1.0
SLOT_WIN = 30
SLOT_MINP = 20
# ── ثابت‌های ارثیِ هارنسِ S382 ────────────────────────────────────────────────
ATR_P = 100
SL_K = 1.5
RR = 1.5
PIP = 0.1          # XAU

CARDS = ('XAUUSD_H8', 'XAUUSD_H4', 'XAUUSD_H12')
# کارت‌هایی که گیتِ سلامت روی‌شان اجرا می‌شود (فقط ACCEPTها حکم دارند)
HEALTH_CARDS = ('XAUUSD_H8', 'XAUUSD_H4')


def load(card: str) -> pd.DataFrame:
    path = os.path.join(ROOT, 'data', 'mt5_full', f'{card}.csv.gz')
    assert 'mt5_full' in path, 'BUG-DATASETDRIFT: must be the full 15.6y source'
    with gzip.open(path, 'rt') as f:
        df = pd.read_csv(f)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    assert 'volume' in df.columns, 'BUG-NOVOLUME'
    return df


def atr_wilder(df: pd.DataFrame, p: int = ATR_P) -> pd.Series:
    """دامِ پورت ④: وایلدر (ewm alpha=1/p, adjust=False) — نه میانگینِ ساده."""
    h, l, c = df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def fresh_high(df: pd.DataFrame) -> pd.Series:
    """دامِ پورت ③: رویداد (لبه)، نه حالت."""
    c = df['close']
    nh = (c > c.rolling(LOOKBACK).max().shift(1)).fillna(False)
    return nh & ~nh.shift(1).fillna(False)


def rvol_slot(df: pd.DataFrame) -> pd.Series:
    """دامِ پورت ①: میانهٔ هم‌اسلات (همان ساعتِ روز)، گذشته‌نگر."""
    v = df['volume'].astype(float)
    hour = df['dt'].dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    return v / ref.replace(0, np.nan)


def simulate(df: pd.DataFrame, sig: np.ndarray, sl_abs: float) -> list[dict]:
    """بازتولیدِ عینیِ strategies/s382_williamsr_momentum.py::simulate_trades
    برای LONG: ورود در close[e] (دام ②)، بدون max_hold (دام ⑤)،
    SL برنده در کندلِ مبهم (دام ⑥)، معاملهٔ بازِ پایانِ داده حذف."""
    n = len(df)
    high = df['high'].to_numpy(float)
    low = df['low'].to_numpy(float)
    close = df['close'].to_numpy(float)
    idx = np.flatnonzero(sig)
    tp_abs = sl_abs * RR
    rows: list[dict] = []
    i = 0
    for e in idx:
        e = int(e)
        if e < i or e + 1 >= n:
            continue
        entry = close[e]
        sl_lvl, tp_lvl = entry - sl_abs, entry + tp_abs
        out = None
        j = e + 1
        while j < n:
            if low[j] <= sl_lvl:
                out = ('loss', j, -sl_abs / PIP)
                break
            if high[j] >= tp_lvl:
                out = ('win', j, tp_abs / PIP)
                break
            j += 1
        if out is None:
            break
        rows.append(dict(entry_bar=e, exit_bar=out[1], outcome=out[0],
                         pnl_pip=out[2]))
        i = out[1] + 1
    return rows


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    health_failures: list[str] = []

    for card in CARDS:
        df = load(card)
        edge = fresh_high(df)
        rv = rvol_slot(df)
        gated = (edge & (rv >= RVOL_THR) & rv.notna()).to_numpy()

        atr = atr_wilder(df)
        sl_abs = float(np.nanmedian(atr.to_numpy())) * SL_K
        sl_pip = sl_abs / PIP
        tp_pip = sl_pip * RR

        trades = simulate(df, gated, sl_abs)
        wins = sum(1 for t in trades if t['outcome'] == 'win')
        wr = round(100.0 * wins / len(trades), 2) if trades else 0.0

        ref = {
            'card': card,
            'bars': int(len(df)),
            'span_years': round(
                (df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 86400), 2),
            'frozen': {
                'lookback': LOOKBACK, 'rvol_thr': RVOL_THR,
                'slot_win': SLOT_WIN, 'slot_minp': SLOT_MINP,
                'atr_p': ATR_P, 'sl_k': SL_K, 'rr': RR,
                'sl_pip': round(sl_pip, 2), 'tp_pip': round(tp_pip, 2),
                'entry': 'close_of_signal_bar', 'max_hold': None,
                'side': 'long',
            },
            'counts': {
                'n_edges': int(edge.sum()),
                'n_signals': int(gated.sum()),
                'n_trades': len(trades),
                'wr': wr,
                'gate_pass_rate': round(
                    100.0 * gated.sum() / max(1, int((edge & rv.notna()).sum())), 1),
            },
            'signal_bars': [int(x) for x in np.flatnonzero(gated)],
            'trades': trades,
        }

        # نمونه‌های علّی برای مقایسهٔ سری‌به‌سری در هارنسِ TS (دنبالهٔ آخر = پنجرهٔ زندهٔ سایت)
        tail = 400
        s = slice(max(0, len(df) - tail), len(df))
        ref['tail_series'] = {
            'from_bar': int(s.start),
            'time': [int(x) for x in df['time'].to_numpy()[s]],
            'close': [round(float(x), 4) for x in df['close'].to_numpy()[s]],
            'volume': [float(x) for x in df['volume'].to_numpy()[s]],
            'rvol_slot': [None if not np.isfinite(x) else round(float(x), 6)
                          for x in rv.to_numpy()[s]],
            'fresh_edge': [bool(x) for x in edge.to_numpy()[s]],
            'gated': [bool(x) for x in gated[s]],
        }

        with open(os.path.join(OUT_DIR, f'{card}.json'), 'w') as f:
            json.dump(ref, f, ensure_ascii=False)

        print(f'{card}: bars={len(df)} edges={int(edge.sum())} '
              f'signals={int(gated.sum())} trades={len(trades)} wr={wr} '
              f'sl={sl_pip:.2f}pip tp={tp_pip:.2f}pip '
              f'pass={ref["counts"]["gate_pass_rate"]}%', flush=True)

        # ── گیتِ سلامت: بازتولیدِ عددِ حکم ────────────────────────────────────
        if card in HEALTH_CARDS:
            v = json.load(open(os.path.join(ROOT, 'results', '_s589', f'{card}_gated.json')))
            checks = {
                'n_signals': (int(gated.sum()), int(v['n_signals'])),
                'n_trades': (len(trades), int(v['n_trades'])),
                'wr': (wr, float(v['wr'])),
                'sl_pip': (round(sl_pip, 2), float(v['sl_pip'])),
                'tp_pip': (round(tp_pip, 2), float(v['tp_pip'])),
            }
            for k, (got, want) in checks.items():
                ok = abs(got - want) <= (0.01 if isinstance(want, float) else 0)
                print(f'    health {k}: got={got} verdict={want} '
                      f'{"OK" if ok else "MISMATCH"}', flush=True)
                if not ok:
                    health_failures.append(f'{card}.{k}: got={got} want={want}')

    if health_failures:
        raise SystemExit('HEALTH-GATE FAILED (reference cannot reproduce the '
                         'verdict, so it is worthless): ' + '; '.join(health_failures))
    print('\nhealth gate PASSED on all ACCEPT cards — reference is verdict-faithful',
          flush=True)


if __name__ == '__main__':
    main()
