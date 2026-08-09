"""
s434_adjudicate.py — داوریِ نهاییِ نامزدِ قفل‌شدهٔ S434 با موتورِ RQS2 v2.6
================================================================================

چه می‌کند
--------------------------------------------------------------------------------
ترکیبِ **قفل‌شده‌ای** را که در
`results/S434_PREREG_S139_DUAL_LEVER_SELECTION.md` پیش‌ثبت شد، روی یک کارت
(جفت‌ارز × تایم‌فریم) اجرا می‌کند و به `engine.rqs2.compute_rqs2` می‌سپارد.

⚠️ چرا این فایل از `s434_regime_filter_search.py` **جدا** است
--------------------------------------------------------------------------------
غربالِ نامزد و داوریِ نامزد دو کارِ متفاوت‌اند و باید از هم جدا بمانند:

* غربال ۱۲۹۶ ترکیب را می‌بیند و «بهترین» را برمی‌گزیند ⇒ ذاتاً خوش‌بین است.
* داوری باید **یک** ترکیبِ از-پیش-اعلام‌شده را بسنجد و اجازه ندارد بگردد.

اگر این دو در یک فایل بودند، وسوسهٔ «کمی جابه‌جا کردنِ نامزد بعد از دیدنِ
حکم» ساختاراً باز می‌ماند. اینجا نامزد به‌صورتِ **ثابتِ ماژول** نوشته شده و
هیچ آرگومانِ خط‌فرمانی نمی‌تواند آن را عوض کند — تنها `--tf` و `--asset`
تغییرپذیرند، چون قانونِ MTF ایجاب می‌کند همان ترکیب روی همهٔ کارت‌ها برود.

سه چیزی که به موتور داده می‌شود و اهمیتشان
--------------------------------------------------------------------------------
1. ``n_trials = 1296`` — اندازهٔ **واقعیِ** فضای جاروب‌شده، شمرده نه تخمین.
   دروازهٔ `H5` (بقا در آزمونِ چندگانه) و کنترلِ EFDR روی همین می‌نشینند.
   کوچک نشان دادنِ این عدد، مصداقِ دقیقِ **اشتباهِ رایجِ ۸** است: دور زدنِ
   معیار بدونِ آنکه هیچ عددِ گزارش‌شده‌ای دروغ به نظر برسد.
2. ``split_bar`` — مرزِ زمانیِ اکتشاف/خارج‌ازنمونه برای `H7`. تقسیم بر
   **کندل** انجام می‌شود نه بر معامله، چون تقسیمِ معامله‌محور می‌تواند یک
   رژیمِ تقویمی را در هر دو نیمه پخش کند و آزمونِ خارج‌نمونه را بی‌معنا کند.
3. ``close`` و ``bar_time`` — تا `H10` بتواند رژیمِ خلاف‌جهت را بسنجد.
   ندادنِ این‌ها یعنی `H10` با «نامعلوم» پاس می‌شود ⇒ پاسِ ارزان.

⚠️ تعهدِ ثبت‌شدهٔ گامِ ۲۴ که اینجا اجرایی می‌شود
--------------------------------------------------------------------------------
اگر حکم `ACCEPT` نشد، **ترکیبِ دیگری از فهرستِ ۱۹۸تایی انتخاب نمی‌شود**.
حکمِ واقعی گزارش می‌شود و علتش کالبدشکافی می‌گردد.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tools.s434_fast_data as fd                        # noqa: E402
from engine import scalp_engine as se                    # noqa: E402
from engine.rqs2 import compute_rqs2, format_rqs2        # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s434_verdicts')

# ══════════════════════════════════════════════════════════════════════════
# نامزدِ قفل‌شده — عیناً از پیش‌ثبتِ گامِ ۲۴
# هیچ آرگومانی این‌ها را عوض نمی‌کند. تغییرشان یعنی نامزدِ دیگری، که باید
# پیش‌ثبتِ خودش را داشته باشد.
# ══════════════════════════════════════════════════════════════════════════
CAND = {
    'layer': 'S139 Gold Overnight Drift (LONG, indicator-free)',
    'hours': (22, 23),
    'sig_mode': 'SESSION_OPEN',
    'base_sl': 150.0,
    'base_tp': 500.0,
    'scale': 1.37,
    'trail': 130.0,
    'be_trigger': None,
    'regime_kind': 'mom',
    'regime_days': 13,
    'hold_hours': 24.0,
    'n_trials': 1296,          # 🔒 شمردهٔ واقعیِ فضای جاروب — دست‌کاری ممنوع
}

# نسبتِ مقدس — اگر این عدد عوض شود، «قانونِ حفظِ بودجه» نقض شده و باید
# حاشیهٔ سربه‌سرِ قبل/بعد در همان گام گزارش شود (تعهدِ ۱ از گامِ ۲۴).
SACRED_RATIO = CAND['base_tp'] / CAND['base_sl']         # = 3.3333…


def regime_mask(d: dict, kind: str, days: int, tf: str) -> np.ndarray:
    """ماسکِ رژیم — بازتولیدِ **دقیقِ** همان تعریفی که در جاروب پاس شد.

    ⚠️ چرا بازنویسیِ اینجا خطرناک بود و چگونه مهار شد: اگر تعریفِ رژیم در
      داورِ نهایی حتی جزئی با تعریفِ غربال تفاوت داشت، حکمِ صادرشده متعلق به
      لایهٔ دیگری بود. بنابراین فرمول عیناً از
      `s434_regime_filter_search.regime_mask` کپی شده و در گامِ بعد با یک
      آزمونِ آشتیِ عددی تأیید می‌شود (n و WR باید با ردیفِ #۴ بخوانند).

    ⚠️ `shift(1)` حیاتی است: برچسبِ رژیم روی کندلِ i تنها از اطلاعاتِ تا
      کندلِ i-1 ساخته می‌شود. بدونِ آن، هر فیلترِ رژیمی درخشان به نظر
      می‌رسد و کلِ نتیجه بی‌ارزش است.
    """
    import pandas as pd

    close = pd.Series(d['close'])
    bars = max(2, int(round(days * 24 * 60 / fd.TF_MINUTES[tf])))

    if kind == 'ma':
        ok = close > close.rolling(bars, min_periods=bars).mean()
    elif kind == 'mom':
        # شیبِ بازدهِ تجمعی — بی‌اندیکاتور، مستقل از هر میانگینِ متحرک
        ok = (close / close.shift(bars) - 1.0) > 0.0
    elif kind == 'peak':
        roll_max = close.rolling(bars, min_periods=bars).max()
        atr = (pd.Series(d['high']) - pd.Series(d['low'])).rolling(
            bars, min_periods=bars).mean()
        ok = (roll_max - close) < atr
    else:
        raise ValueError(kind)

    return ok.shift(1).fillna(False).values.astype(bool)


def run_candidate(asset: str, tf: str) -> dict:
    """اجرای نامزدِ قفل‌شده روی یک کارت و برگرداندنِ معاملات + فرادادهٔ منبع."""
    d = fd.load_fast(asset, tf)
    df = fd.as_dataframe(d)

    sig = fd.session_open_signal(d, CAND['hours'], CAND['sig_mode'])
    if CAND['regime_kind'] is not None:
        sig = sig & regime_mask(d, CAND['regime_kind'], CAND['regime_days'], tf)

    sl = CAND['base_sl'] * CAND['scale']
    tp = CAND['base_tp'] * CAND['scale']
    assert abs(tp / sl - SACRED_RATIO) < 1e-9, 'نسبتِ TP/SL نقض شد!'

    mh = fd.hold_bars_for(tf, CAND['hold_hours'])

    tr = se.simulate_trades(
        df, sig, np.zeros(len(df), bool), sl, tp, asset,
        max_hold=mh, allow_overlap=False,
        be_trigger_pip=CAND['be_trigger'], trail_pip=CAND['trail'])

    return {
        'trades': tr, 'df': df, 'd': d,
        'sl': sl, 'tp': tp, 'max_hold': mh,
        'n_signals': int(sig.sum()),
    }


def adjudicate(asset: str, tf: str, oos_frac: float = 0.30) -> dict:
    """داوریِ کاملِ RQS2 v2.6 روی یک کارت."""
    run = run_candidate(asset, tf)
    tr, df, d = run['trades'], run['df'], run['d']

    if tr is None or len(tr) == 0:
        return {'asset': asset, 'tf': tf, 'error': 'no trades'}

    # ── تقسیمِ اکتشاف / خارج‌ازنمونه بر حسبِ **کندل** (نه معامله) ─────────
    #   دلیل در docstringِ بالا: تقسیمِ معامله‌محور می‌تواند یک رژیمِ تقویمی
    #   را در هر دو نیمه پخش کند و آزمونِ H7 را بی‌معنا کند.
    n_bars = len(df)
    split_bar = int(n_bars * (1.0 - oos_frac))

    res = compute_rqs2(
        tr, asset,
        sl_pip=run['sl'], tp_pip=run['tp'],
        bar_time=d['time'],
        close=d['close'],
        n_trials=CAND['n_trials'],
        split_bar=split_bar,
        initial_capital=10000.0,
        allow_overlap=False,
    )

    m = res.get('metrics') or {}
    g = res.get('gates') or {}
    failed = sorted(k for k, v in g.items() if v is False)
    unknown = sorted(k for k, v in g.items() if v is None)

    return {
        'asset': asset, 'tf': tf,
        'candidate': {k: (list(v) if isinstance(v, tuple) else v)
                      for k, v in CAND.items()},
        'geometry': {'sl_pip': run['sl'], 'tp_pip': run['tp'],
                     'ratio': round(run['tp'] / run['sl'], 4),
                     'max_hold_bars': run['max_hold']},
        'data_source': {'path': os.path.relpath(d['src'], ROOT),
                        'n_bars': d['n_bars'],
                        'span_years': d['span_years'],
                        'first_utc': d['first_utc'], 'last_utc': d['last_utc']},
        'split_bar': split_bar, 'oos_frac': oos_frac,
        'n_signals': run['n_signals'],
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: g.get(k) for k in sorted(g)},
        'failed_gates': failed,
        'unknown_gates': unknown,
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'expectancy_at_2x_cost',
            'rr', 'top_win_share', 'max_concurrency', 'wr_excess_cost')},
        'notes': [str(x) for x in (res.get('notes') or [])],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tfs', default='M30')
    ap.add_argument('--oos', type=float, default=0.30)
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            out = adjudicate(a.asset, tf, a.oos)
        except Exception as e:                          # noqa: BLE001
            print(f'!! {a.asset}-{tf}: {type(e).__name__}: {e}')
            sys.stdout.flush()
            continue

        # 🔒 قانونِ سومِ پروژه (اندک اندک): هر کارت **فوراً** ذخیره می‌شود،
        #    منتظرِ اتمامِ همهٔ کارت‌ها نمی‌مانیم چون سندباکس ناپایدار است.
        fp = os.path.join(OUT_DIR, f'verdict_{a.asset}_{tf}.json')
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)

        if 'error' in out:
            print(f'[{a.asset}-{tf}] {out["error"]}')
            sys.stdout.flush()
            continue

        m, ds = out['metrics'], out['data_source']
        print(f'\n═══ {a.asset}-{tf} ═══  ({ds["n_bars"]:,} کندل · '
              f'{ds["span_years"]}س · {os.path.basename(ds["path"])})')
        print(f'  حکم = {out["verdict"]}   RQS2 = {out["rqs2_score"]}')
        print(f'  n={m["n_trades"]} WR={m["win_rate"]}% '
              f'PF={m["profit_factor"]} exp={m["expectancy_pip"]}pip')
        print(f'  maxDD={m["max_dd_pct"]}% MCL={m["max_consec_losses"]}/'
              f'{m["mcl_allowed"]} rec={m["recovery_factor"]}')
        print(f'  z={m["skill_z"]} lift={m["skill_lift_pp"]}pp '
              f'BE_wr={m["breakeven_wr_cost"]}% '
              f'exp@2x={m["expectancy_at_2x_cost"]}')
        print(f'  افتاده: {out["failed_gates"] or "هیچ ✅"}')
        if out['unknown_gates']:
            print(f'  نامعلوم: {out["unknown_gates"]}')
        for nt in out['notes'][:6]:
            print(f'    · {nt[:150]}')
        sys.stdout.flush()

    print('\n[done]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
