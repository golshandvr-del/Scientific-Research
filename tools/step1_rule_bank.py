# -*- coding: utf-8 -*-
"""گامِ ۱ — بخشِ ۲: بانکِ **قواعدِ تک‌شرطی** و شمارشِ نرخِ سیگنال.

اصلِ طراحی (و دلیلِ وجودِ این ابزار):
    هر قاعده **تنها یک شرط** دارد. هیچ فیلتری. هیچ ترکیبی.

چرا: کلِ یک ماهِ گذشته صرفِ **افزودن** شد — فیلتر روی فیلتر. ریاضیِ آن این
است که اگر هر فیلتر ۵۰٪ نگه دارد، ۱۰ فیلتر ۰.۱٪ باقی می‌گذارد. پس پیش از
هر چیز باید **بودجهٔ خامِ معامله** اندازه‌گیری شود: یک شرطِ تنها، در سال چند
سیگنال می‌دهد؟ آن عدد سقفِ بودجه است و هر فیلتر از آن خرج می‌کند.

دو دروازهٔ صفر-درجه-آزادی:
    ① `rqs2_floor`  : ≥ ۵۰ سیگنال/سال  → برای رسیدن به n=784 در بازهٔ کارت
    ② `site_target` : ≥ ۲۵۲ سیگنال/سال → هدفِ سایت (روزی ۱ سیگنال)

هیچ TP/SL، هیچ سود، هیچ برد-باخت. صفر پارامترِ قابلِ تنظیم برای بهتر کردنِ
نتیجه ⇒ **غیرقابلِ تقلب**.

نکتهٔ ضدِ اشتباهِ رایجِ #۷ (اعدادِ رند): آستانه‌های اندیکاتوری از اعدادِ رندِ
مرسوم (۳۰/۷۰، ۵۰/۲۰۰) **و هم** از اعدادِ نارند (۳۵/۶۳، ۱۳۵/۱۷۰) گرفته
می‌شوند تا برشِ رند به‌تنهایی سرنوشتِ قاعده را تعیین نکند.
"""

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import indicator_bank as IB  # noqa: E402

DATA = 'data'
OUT = 'results/_step1_census'
os.makedirs(OUT, exist_ok=True)

TRADING_DAYS = 252
RQS2_FLOOR_PER_YEAR = 50      # n=784 روی کارت‌های ۱۵.۵ سالهٔ M30/H1
SITE_TARGET_PER_YEAR = 252    # روزی ۱ سیگنال


def load(card):
    df = pd.read_csv(os.path.join(DATA, f'{card}.csv'))
    df.columns = [c.strip().lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════
# بانکِ قواعد — هر تابع یک **آرایهٔ بولیِ سیگنال** برمی‌گرداند.
# قاعده = «لبهٔ رخداد» (crossing)، نه «حالتِ ماندگار». چرا: حالتِ ماندگار
# (مثلِ `RSI<35`) تعدادِ *کندل* را می‌شمارد نه تعدادِ *فرصتِ ورود*؛ یک نزولِ
# ۲۰ کندلیِ RSI یک فرصت است، نه بیست فرصت. شمارشِ کندل نرخ را ۵ تا ۲۰ برابر
# متورم می‌کند و همان تورم است که «بودجه» را توهمی می‌کند.
# ═══════════════════════════════════════════════════════════════════════════

def _cross_up(s, thr):
    """گذرِ رو به بالا از آستانه — یک رخداد در هر گذر."""
    s = pd.Series(s).astype(float)
    return (s.shift(1) <= thr) & (s > thr)


def _cross_dn(s, thr):
    s = pd.Series(s).astype(float)
    return (s.shift(1) >= thr) & (s < thr)


def _cross_series_up(a, b):
    """گذرِ سریِ a از رویِ سریِ b."""
    a, b = pd.Series(a).astype(float), pd.Series(b).astype(float)
    return (a.shift(1) <= b.shift(1)) & (a > b)


def build_rules():
    """فهرستِ (نام, تابعِ سیگنال). هر قاعده **یک شرط**، صفر فیلتر."""
    rules = []

    # ── ① گذرِ آستانه‌ایِ نوسان‌سنج‌ها ───────────────────────────────────
    # آستانه‌ها: رند (مرسوم) + نارند (ضدِ اشتباهِ #۷)
    osc_specs = [
        ('rsi_14', [30, 35, 27, 63, 70, 73]),
        ('cci_20', [-100, -135, -87, 100, 135, 87]),
        ('willr_14', [-80, -73, -87, -20, -27, -13]),
        ('mfi_14', [20, 27, 35, 65, 73, 80]),
        ('cmo_14', [-50, -37, 37, 50]),
    ]
    for ind, thrs in osc_specs:
        for t in thrs:
            for side, fn in (('up', _cross_up), ('dn', _cross_dn)):
                rules.append((f'{ind}_x{side}_{t}',
                              lambda df, i=ind, t=t, f=fn: f(IB.compute(i, df), t)))

    # ── ② گذرِ قیمت از رویِ میانگین‌ها ─────────────────────────────────
    # دوره‌های نارند در کنارِ رند (۵۰/۲۰۰ در برابرِ ۱۳۵/۱۷۰)
    for ma in ('sma', 'ema'):
        for p in (34, 50, 89, 135, 170, 200):
            nm = f'{ma}_{p}'
            if not IB.has_indicator(nm):
                continue
            rules.append((f'close_x_up_{nm}',
                          lambda df, n=nm: _cross_series_up(df['close'], IB.compute(n, df))))
            rules.append((f'close_x_dn_{nm}',
                          lambda df, n=nm: _cross_series_up(IB.compute(n, df), df['close'])))

    # ── ③ شکستِ کانالِ دونچیان (breakout خالص) ────────────────────────
    for p in (20, 34, 55, 89, 135):
        def bo_up(df, p=p):
            hh = df['high'].rolling(p).max().shift(1)
            return (df['close'].shift(1) <= hh) & (df['close'] > hh)

        def bo_dn(df, p=p):
            ll = df['low'].rolling(p).min().shift(1)
            return (df['close'].shift(1) >= ll) & (df['close'] < ll)
        rules.append((f'donchian_break_up_{p}', bo_up))
        rules.append((f'donchian_break_dn_{p}', bo_dn))

    # ── ④ گذرِ باندِ بولینگر ───────────────────────────────────────────
    for p, m in ((20, 2.0), (34, 2.0), (20, 1.618), (55, 2.618)):
        def bb_up(df, p=p, m=m):
            c = df['close'].astype(float)
            mid = c.rolling(p).mean(); sd = c.rolling(p).std()
            up = mid + m * sd
            return (c.shift(1) <= up.shift(1)) & (c > up)

        def bb_dn(df, p=p, m=m):
            c = df['close'].astype(float)
            mid = c.rolling(p).mean(); sd = c.rolling(p).std()
            lo = mid - m * sd
            return (c.shift(1) >= lo.shift(1)) & (c < lo)
        rules.append((f'bb_up_{p}_{m}', bb_up))
        rules.append((f'bb_dn_{p}_{m}', bb_dn))

    # ── ⑤ گذرِ MACD از صفر و از خطِ سیگنال ────────────────────────────
    def macd_zero_up(df):
        c = df['close'].astype(float)
        m = c.ewm(span=12).mean() - c.ewm(span=26).mean()
        return _cross_up(m, 0.0)

    def macd_sig_up(df):
        c = df['close'].astype(float)
        m = c.ewm(span=12).mean() - c.ewm(span=26).mean()
        return _cross_series_up(m, m.ewm(span=9).mean())
    rules.append(('macd_zero_x_up', macd_zero_up))
    rules.append(('macd_signal_x_up', macd_sig_up))

    # ── ⑥ فشردگی/گسترشِ نوسان (رژیمِ ATR) ────────────────────────────
    for p, q in ((14, 0.20), (14, 0.35), (34, 0.20), (34, 0.35)):
        def sq(df, p=p, q=q):
            tr = (df['high'] - df['low']).astype(float)
            a = tr.rolling(p).mean()
            thr = a.rolling(500, min_periods=100).quantile(q)
            return (a.shift(1) >= thr.shift(1)) & (a < thr)
        rules.append((f'atr_squeeze_{p}_{q}', sq))

    return rules


def main():
    census = json.load(open('results/_step1_census/data_census.json'))
    spans = {c['card']: c['span_years'] for c in census['cards']}

    # کارت‌های هدف: فقط دو جفت‌ارزِ پروژه. ترتیب: بلندترین تاریخ اول
    # (یافتهٔ S377: بلندترین تاریخ = بیشترین ظرفیتِ اثبات)
    cards = [c['card'] for c in census['cards']
             if c['pair'] in ('XAUUSD', 'EURUSD')]
    cards.sort(key=lambda c: -spans[c])

    only = sys.argv[1] if len(sys.argv) > 1 else None
    if only:
        cards = [c for c in cards if c == only]

    rules = build_rules()
    print(f'rule bank: {len(rules)} single-condition rules, zero filters')
    print(f'cards     : {len(cards)}')
    print()

    for card in cards:
        yrs = spans[card]
        df = load(card)
        out = []
        for name, fn in rules:
            try:
                sig = fn(df)
                sig = pd.Series(sig).fillna(False).astype(bool)
                n = int(sig.sum())
            except Exception as e:
                out.append(dict(rule=name, error=str(e)[:60]))
                continue
            per_yr = n / yrs if yrs > 0 else 0.0
            out.append(dict(
                rule=name, n_signals=n,
                per_year=round(per_yr, 1),
                per_day=round(per_yr / TRADING_DAYS, 3),
                gate_rqs2=bool(per_yr >= RQS2_FLOOR_PER_YEAR),
                gate_site=bool(per_yr >= SITE_TARGET_PER_YEAR),
            ))
        ok = [r for r in out if 'n_signals' in r]
        n_rqs2 = sum(1 for r in ok if r['gate_rqs2'])
        n_site = sum(1 for r in ok if r['gate_site'])
        payload = dict(card=card, span_years=yrs, n_rules=len(ok),
                       n_pass_rqs2_floor=n_rqs2, n_pass_site_target=n_site,
                       rqs2_floor_per_year=RQS2_FLOOR_PER_YEAR,
                       site_target_per_year=SITE_TARGET_PER_YEAR,
                       rules=sorted(ok, key=lambda r: -r['per_year']))
        with open(os.path.join(OUT, f'rules_{card}.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        print(f'{card:14s} span={yrs:5.2f}y  rules={len(ok):4d}  '
              f'pass_rqs2_floor={n_rqs2:4d}  pass_site={n_site:4d}  '
              f'→ rules_{card}.json')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
