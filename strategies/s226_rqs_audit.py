# -*- coding: utf-8 -*-
"""
s226_rqs_audit.py — ممیزیِ همهٔ لایه‌های احیاشدهٔ این نشست با معیارِ جدیدِ RQS.

هدف (پاسخ به نگرانیِ کاربر): جدا کردنِ لایه‌های «واقعی» از «توهمی» (WRِ مصنوعِ TP/SL،
مثلِ سیگنالِ رندوم). برای هر لایه:
  1) سیگنالِ واقعی را بک‌تست می‌کند،
  2) سیگنالِ رندومِ هم‌ساختار (همان n، همان TP/SL، در همان پنجرهٔ زمانی اگر زمان‌محور) می‌سازد،
  3) RQS را حساب و pass/fail هر ۵ دروازه را گزارش می‌کند.
خروجی: results/_s226_rqs_audit.json (افزایشی/مقاوم در برابر ریست).
"""
from __future__ import annotations
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import strategies.s220_wr60_booster as B
from strategies.rqs_metric import compute_rqs, format_rqs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RNG = np.random.default_rng(2024)
N_RAND = 8  # تعداد تکرارِ سیگنالِ رندوم برای میانگین


def asnp(x):
    return x.to_numpy() if hasattr(x, 'to_numpy') else np.asarray(x)


def load_gold(tf):
    df = B.add_indicators(B.add_calendar(B.load(f'XAUUSD_{tf}')))
    df = B.last_n_years(df, 4)
    df = B.add_indicators(B.add_calendar(df.copy().reset_index(drop=True)))
    return df


def random_control(df, base_window, nsig, sl, tp, mh, asset):
    """میانگینِ WR/net روی N_RAND سیگنالِ رندوم که فقط در base_window مجازند."""
    n = len(df)
    winidx = np.where(base_window)[0] if base_window is not None else np.arange(n)
    if len(winidx) < nsig or nsig == 0:
        return None, None
    wrs, nets = [], []
    for _ in range(N_RAND):
        pick = RNG.choice(winidx, size=nsig, replace=False)
        rd = np.zeros(n, bool); rd[pick] = True
        rr = B.eval_signal(df, rd, np.zeros(n, bool), sl, tp, mh, asset)
        if rr:
            wrs.append(rr['wr']); nets.append(rr['net'])
    if not wrs:
        return None, None
    return float(np.mean(wrs)), float(np.mean(nets))


def time_window_gold(df, hours, dow=None, first_day_of_month=False):
    """ساختِ ماسکِ پنجرهٔ زمانیِ طلا (long-only، shift(1) برای اجتناب از look-ahead)."""
    tcol = df['time'] if 'time' in df.columns else df.iloc[:, 0]
    dt = pd.to_datetime(tcol, unit='s', utc=True)
    hh = dt.dt.hour.to_numpy()
    base = np.isin(hh, hours)
    if dow is not None:
        base = base & (dt.dt.dayofweek.to_numpy() == dow)
    if first_day_of_month:
        ym = (dt.dt.year * 100 + dt.dt.month).to_numpy()
        dom = dt.dt.day.to_numpy()
        s = pd.Series(dom).groupby(ym).transform('min').to_numpy()
        base = base & (dom == s)
    return pd.Series(base).shift(1).fillna(False).to_numpy()


def eval_layer(name, tf, base_mask, base_window, filters, sl, tp, mh, side='long'):
    """یک لایه را کامل ارزیابی و RQS می‌دهد."""
    df = load_gold(tf)
    n = len(df); asset = 'XAUUSD'
    F = B.build_filters(df)
    mask = base_mask.copy()
    for f in filters:
        mask = mask & asnp(F[f])
    long_sig = mask if side == 'long' else np.zeros(n, bool)
    short_sig = mask if side == 'short' else np.zeros(n, bool)
    r = B.eval_signal(df, long_sig, short_sig, sl, tp, mh, asset)
    if r is None:
        return {'name': name, 'error': 'no trades'}
    nsig = int(mask.sum())
    rand_wr, rand_net = random_control(df, base_window, nsig, sl, tp, mh, asset)
    if rand_wr is None:
        rand_wr, rand_net = r['wr'], 0.0  # fallback محافظه‌کارانه
    rqs = compute_rqs(r, rand_wr, rand_net)
    return {'name': name, 'tf': tf, 'sl': sl, 'tp': tp, 'filters': filters,
            'random_wr': round(rand_wr, 1), 'random_net': round(rand_net, 0),
            'rqs': rqs}


def base_s81(df):
    ema20 = df['ema20'].to_numpy() if 'ema20' in df else B.ema(df['close'], 20).to_numpy()
    ema100 = df['ema100'].to_numpy() if 'ema100' in df else B.ema(df['close'], 100).to_numpy()
    rsi = df['rsi14'].to_numpy() if 'rsi14' in df else None
    sig = (ema20 > ema100) & (rsi < 35)
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def main():
    print("=" * 90)
    print("S226 — ممیزیِ RQS روی لایه‌های نشست (جداسازیِ واقعی از توهمی)")
    print("=" * 90)
    out = os.path.join(ROOT, 'results', '_s226_rqs_audit.json')
    results = {}
    if os.path.exists(out):
        try:
            results = json.load(open(out))
        except Exception:
            results = {}

    def save():
        with open(out, 'w') as f:
            json.dump(results, f, ensure_ascii=False, indent=1, default=float)

    # لایه‌های زمان‌محورِ سایت (M15) — همان پارامترهایی که وصل شدند
    def do(key, fn):
        if key in results and results[key].get('rqs'):
            print(f"⏩ رد شد (قبلاً): {key}")
            return
        print(f"\n▶ در حالِ ارزیابی: {key} ...")
        results[key] = fn()
        save()
        r = results[key]
        if 'rqs' in r and 'gates' in r['rqs']:
            print(format_rqs(key, r['rqs']))

    # 1) Overnight/M15
    def f_overnight():
        df = load_gold('M15')
        bw = time_window_gold(df, [22, 23])
        return eval_layer('Overnight/M15', 'M15', bw, bw,
                          ['pdi>mdi', 'bull_bar', 'atr<1.8med'], 150, 40, 96)
    do('Overnight_M15', f_overnight)

    # 2) Monday/M15
    def f_monday():
        df = load_gold('M15')
        bw = time_window_gold(df, [18, 19, 20], dow=0)
        return eval_layer('Monday/M15', 'M15', bw, bw,
                          ['adx>20', 'atr<1.8med', 'atr>0.5med'], 200, 40, 96)
    do('Monday_M15', f_monday)

    # 3) TurnOfMonth/M15
    def f_tom():
        df = load_gold('M15')
        bw = time_window_gold(df, [7, 8, 9, 10, 11, 12], first_day_of_month=True)
        return eval_layer('TurnOfMonth/M15', 'M15', bw, bw,
                          ['rsi>50', 'pdi>mdi'], 300, 80, 96)
    do('TurnOfMonth_M15', f_tom)

    # 4) S81 Swing/M5 (ساختاری — نه زمان‌محور؛ random در کلِ داده)
    def f_s81():
        df = load_gold('M5')
        base = base_s81(df)
        return eval_layer('S81-Swing/M5', 'M5', base, None,
                          ['ema20>50'], 150, 40, 288)
    do('S81_Swing_M5', f_s81)

    print("\n" + "=" * 90)
    print("خلاصهٔ ممیزیِ RQS:")
    print("=" * 90)
    for k, v in results.items():
        if 'rqs' in v:
            print(f"  {k:22s} RQS={v['rqs']['rqs']:5.1f}/100  {v['rqs']['verdict']}")
    save()
    print(f"\n✅ ذخیره شد: {out}")


if __name__ == '__main__':
    main()
