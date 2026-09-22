# -*- coding: utf-8 -*-
"""S1516 — صدورِ مرجعِ عددیِ پورت (parity ground truth) · XAUUSD-H6 و H4

چرا این فایل، پیش از نوشتنِ ماژولِ TS
=====================================
سیم‌کشیِ یک لایه یعنی ادعا کردنِ اینکه «کادری که در سایت روشن می‌شود همان
چیزی است که RQS2 به آن ACCEPT داد». این ادعا فقط وقتی راست است که پورت با
**عددِ مرجع** سنجیده شود، نه با خواندنِ سند. تجربهٔ S589 در همین ریپو شش دامِ
پورت را فهرست کرده که همگی «با چشم درست به‌نظر می‌رسیدند».

دو دامِ مشخصِ S1516 که این فایل می‌بندد:

  ① **لحظهٔ ورود.** §۲ سندِ ACCEPT می‌گوید «open کندلِ بعد». اما هارنسی که حکم
    را تولید کرد (`strategies/s382_williamsr_momentum.py::simulate_trades`،
    که S1516 عیناً از آن استفاده می‌کند) در خطِ `entry = close[e]` ورود را روی
    **close کندلِ سیگنال** می‌گیرد. حکم محصولِ کد است نه محصولِ متن، پس پورت
    باید `close` را بگیرد. این فایل عدد را از خودِ کد بیرون می‌کشد تا این
    اختلاف مستند و قابل بررسی بماند.

  ② **maxHold.** بک‌تست هیچ time-stop نداشت، پس maxHold پارامترِ حکم نیست؛ فقط
    سقفِ ایمنیِ اجراییِ سایت است. اگر از کارتِ دیگری کپی شود (اشتباهِ رایجِ ۶)
    بی‌صدا هندسهٔ دیگری می‌سازد و معاملاتی را می‌بُرد که موتور شمرده بود. پس
    توزیعِ واقعیِ نگه‌داری صادر می‌شود تا سقف از داده انتخاب شود.

همچنین SL/TP دقیقِ هر کارت (۱.۵×median(ATR100)) و چند سنجهٔ سلامت صادر می‌شود
تا ماژولِ TS بتواند در گامِ بعد در برابرشان تست شود.

⚠️ دادهٔ H4: حکم روی فایلِ **قبل از** کامیت 922b56ac صادر شده (۲۳٬۸۵۴ کندل،
span 15.59)، و فایلِ امروز ۲۴٬۰۰۴ کندل است. این فایل **هر دو** را صادر می‌کند:
`verdict` (بازتولیدِ عددِ سند) و `today` (آنچه سایت واقعاً می‌بیند). پورت باید
با `today` بخواند و با `verdict` اعتبارسنجی شود.

اجرا:  python3 tools/export_s1516_parity.py
خروجی: results/_s1516_parity/XAUUSD_{H6,H4}.json
"""
from __future__ import annotations

import gzip
import importlib.util
import io
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT_DIR = os.path.join(ROOT, 'results', '_s1516_parity')

L_CAL = {'XAUUSD_H6': 120, 'XAUUSD_H4': 180}
PUBLISHED = {
    'XAUUSD_H6': dict(rqs2=87.1, n_trades=244, n_signals=413, wr=54.51,
                      lift=13.64, sl_pip=152.1, tp_pip=228.1),
    'XAUUSD_H4': dict(rqs2=84.1, n_trades=316, n_signals=508, wr=51.58,
                      lift=10.51, sl_pip=123.0, tp_pip=184.5),
}
DATA_SWAP_COMMIT = '922b56ac'


def _mod(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m


def load_today(card: str) -> pd.DataFrame:
    path = os.path.join(ROOT, 'data', 'mt5_full', f'{card}.csv.gz')
    assert 'mt5_full' in path and os.path.exists(path), f'E-16 GUARD: {path}'
    with gzip.open(path, 'rt') as f:
        df = pd.read_csv(f)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def load_verdict(card: str) -> pd.DataFrame:
    """دادهٔ زمانِ صدورِ حکم؛ برای H4 نسخهٔ پیش از جایگزینیِ 922b56ac."""
    ref = f'{DATA_SWAP_COMMIT}~1:data/mt5_full/{card}.csv.gz'
    blob = subprocess.run(['git', 'show', ref], cwd=ROOT, check=True,
                          stdout=subprocess.PIPE).stdout
    with gzip.open(io.BytesIO(blob), 'rt') as f:
        df = pd.read_csv(f)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def summarize(S, df: pd.DataFrame, L: int, tag: str) -> dict:
    """اجرای قاعدهٔ منجمد + هارنسِ اصلی، و استخراجِ هر عددی که پورت لازم دارد."""
    S.LOOKBACK = L
    sig = S.sig_fresh(df)
    H = S._mod('strategies/s382_williamsr_momentum.py', f'_s382_{tag}')
    ps = H.pip_size('XAUUSD')
    atr = H.atr(df).to_numpy()
    sl_abs = float(np.nanmedian(atr)) * H.SL_K
    tr = H.simulate_trades(df, sig, sl_abs, H.RR, True, ps)
    sl_pip = sl_abs / ps
    be = 100.0 * (sl_pip + 3.3) / (sl_pip * H.RR + sl_pip)
    wr = 100.0 * float((tr['outcome'] == 'win').mean()) if len(tr) else None
    hold = (tr['exit_bar'] - tr['entry_bar']).to_numpy() if len(tr) else np.array([])
    out = {
        'tag': tag,
        'bars': int(len(df)),
        'span_years': round((df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 86400), 2),
        'L': L,
        'n_signals': int(sig.sum()),
        'n_trades': int(len(tr)),
        'wr': round(wr, 2) if wr is not None else None,
        'be': round(be, 2),
        'lift': round(wr - be, 2) if wr is not None else None,
        'sl_abs_price': round(sl_abs, 5),
        'sl_pip': round(sl_pip, 2),
        'tp_pip': round(sl_pip * H.RR, 2),
        'sl_k': H.SL_K, 'rr': H.RR, 'atr_period': 100,
        'entry_price_field': 'close[signal_bar]',   # ← دامِ ①، از خودِ کد
        'side': 'long',
    }
    if len(hold):
        out['hold_bars'] = {
            'min': int(hold.min()), 'median': int(np.median(hold)),
            'p95': int(np.percentile(hold, 95)), 'max': int(hold.max()),
        }
    # چند سیگنالِ نمونه برای تستِ نقطه‌ایِ پورت (اولین و آخرین ۵ رویداد)
    ev = np.flatnonzero(sig.to_numpy())
    out['sample_event_times'] = (
        [str(df['dt'].iloc[int(i)]) for i in ev[:5]]
        + [str(df['dt'].iloc[int(i)]) for i in ev[-5:]]
    )
    return out


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    S = _mod('strategies/s1516_cal_floor.py', '_s1516_src')
    S._mod = _mod
    report_all = {}
    ok = True

    for card in ('XAUUSD_H6', 'XAUUSD_H4'):
        L = L_CAL[card]
        today = summarize(S, load_today(card), L, 'today')
        verdict = summarize(S, load_verdict(card), L, 'verdict')
        pub = PUBLISHED[card]

        # کنترل: نسخهٔ verdict باید عددِ منتشرشده را بازتولید کند.
        checks = {
            'n_signals': (verdict['n_signals'], pub['n_signals']),
            'n_trades': (verdict['n_trades'], pub['n_trades']),
            'wr': (verdict['wr'], pub['wr']),
            'lift': (verdict['lift'], pub['lift']),
        }
        detail = {}
        card_ok = True
        for k, (got, exp) in checks.items():
            good = (got == exp) if isinstance(exp, int) else abs(got - exp) < 0.02
            detail[k] = {'measured': got, 'published': exp, 'match': bool(good)}
            card_ok = card_ok and good
        # SL/TP سند تا ۱ رقمِ اعشار گرد شده
        detail['sl_pip'] = {'measured': verdict['sl_pip'], 'published': pub['sl_pip'],
                            'match': bool(abs(verdict['sl_pip'] - pub['sl_pip']) < 0.15)}
        card_ok = card_ok and detail['sl_pip']['match']

        report_all[card] = {
            'published': pub,
            'verdict_time_data': verdict,
            'today_data': today,
            'parity_control': detail,
            'control_passed': bool(card_ok),
            'note_for_port': (
                'Port MUST read today_data geometry (the site trades today\'s feed), '
                'and is validated by verdict_time_data reproducing the published numbers.'),
        }
        ok = ok and card_ok

        print(f'\n{card} (L={L})', flush=True)
        for tag, r in (('verdict', verdict), ('today', today)):
            print(f'  [{tag}] bars={r["bars"]} span={r["span_years"]}y '
                  f'sig={r["n_signals"]} n={r["n_trades"]} wr={r["wr"]} '
                  f'lift={r["lift"]} sl={r["sl_pip"]}pip tp={r["tp_pip"]}pip '
                  f'hold={r.get("hold_bars")}', flush=True)
        print(f'  control: {json.dumps(detail, ensure_ascii=False)}', flush=True)

        with open(os.path.join(OUT_DIR, f'{card}.json'), 'w') as f:
            json.dump(report_all[card], f, ensure_ascii=False, indent=1)

    print(f'\nALL CONTROLS PASSED = {ok}', flush=True)
    if not ok:
        raise SystemExit('PARITY-REFERENCE INVALID: published numbers not reproduced')


if __name__ == '__main__':
    main()
