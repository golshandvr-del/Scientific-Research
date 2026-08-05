# -*- coding: utf-8 -*-
"""گامِ ۱ — بخشِ ۳: **هزینهٔ فیلتر** — بخشِ گم‌شدهٔ یک ماهِ گذشته.

پرسش:
    «هر فیلتر چند درصد از بودجهٔ معامله را می‌خورد؟ و ترکیبشان؟»

چرا این ابزار قلبِ گامِ ۱ است: قانونِ فعلیِ پروژه («هیچ محدودیتی در تعدادِ
بهبودهای همزمان نداریم؛ حتی ده فیلتر قابلِ قبول است») در ریاضیاتش قانونِ
«صفر معامله» است — ولی این ادعا تا امروز **اندازه‌گیری نشده بود**. اینجا
اندازه گرفته می‌شود.

سه اندازه‌گیری:
  ① `keep_solo`  — نگه‌داشتِ هر فیلتر به‌تنهایی روی یک قاعدهٔ پایه.
  ② `keep_pair`  — نگه‌داشتِ هر جفتِ فیلتر، و مقایسه با **حاصل‌ضربِ** تک‌ها.
       نسبتِ `keep_pair / (keep_A × keep_B)` = «نسبتِ استقلال».
       اگر ≈۱ ⇒ مستقل. اگر ≪۱ ⇒ **تضادِ ساختاری** (کشفِ نشستِ پیشین: ۰.۱۰۳).
  ③ `n_left`     — تعدادِ معاملهٔ باقی‌مانده، و آیا از آستانه‌ها می‌گذرد.

صفر درجهٔ آزادی: هیچ TP/SL، هیچ سود، هیچ برد-باخت.
"""

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATA = 'data'
OUT = 'results/_step1_census'
os.makedirs(OUT, exist_ok=True)

TRADING_DAYS = 252
RQS2_FLOOR_PER_YEAR = 50
SITE_TARGET_PER_YEAR = 252


def load(card):
    df = pd.read_csv(os.path.join(DATA, f'{card}.csv'))
    df.columns = [c.strip().lower() for c in df.columns]
    return df


# ═══════════════════════════════════════════════════════════════════════════
# فیلترها — هر کدام یک **ماسکِ بولیِ حالت** (نه رخداد).
# فیلتر ذاتاً «حالت» است: «آیا الان در روندِ صعودی هستم؟» — برخلافِ قاعده
# که «رخداد» است. پس اینجا شمارشِ کندل درست است.
# ═══════════════════════════════════════════════════════════════════════════

def _sma(s, p):
    return pd.Series(s).astype(float).rolling(p).mean()


def _rsi(c, p=14):
    c = pd.Series(c).astype(float)
    d = c.diff()
    up = d.clip(lower=0.0).ewm(alpha=1.0 / p, adjust=False).mean()
    dn = (-d.clip(upper=0.0)).ewm(alpha=1.0 / p, adjust=False).mean()
    return 100.0 - 100.0 / (1.0 + up / dn.replace(0.0, np.nan))


def _atr(df, p=14):
    h, l, c = (df[k].astype(float) for k in ('high', 'low', 'close'))
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def _adx(df, p=14):
    h, l = df['high'].astype(float), df['low'].astype(float)
    up, dn = h.diff(), -l.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = _atr(df, p)
    pdi = 100.0 * pd.Series(plus, index=df.index).ewm(alpha=1.0/p, adjust=False).mean() / a
    mdi = 100.0 * pd.Series(minus, index=df.index).ewm(alpha=1.0/p, adjust=False).mean() / a
    dx = 100.0 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / p, adjust=False).mean()


def _er(df, p=20):
    """کاراییِ کافمن — سیگنال به نوفه."""
    c = df['close'].astype(float)
    direction = (c - c.shift(p)).abs()
    volatility = c.diff().abs().rolling(p).sum()
    return direction / volatility.replace(0.0, np.nan)


def build_filters():
    """(نام, تابعِ ماسک). هر فیلتر یک شرطِ حالتِ تنها."""
    F = []
    # روندِ میانگین — دوره‌های آزاد (رند + نارند + دلِ شکافِ فیبوناچی)
    for p in (50, 112, 135, 170, 200):
        F.append((f'trend_up_sma{p}',
                  lambda df, p=p: df['close'].astype(float) > _sma(df['close'], p)))
    # نوسان‌سنج در ناحیه
    for p, t in ((14, 35), (14, 45), (21, 35)):
        F.append((f'rsi{p}_below_{t}',
                  lambda df, p=p, t=t: _rsi(df['close'], p) < t))
    for p, t in ((14, 65), (14, 55)):
        F.append((f'rsi{p}_above_{t}',
                  lambda df, p=p, t=t: _rsi(df['close'], p) > t))
    # قوّتِ روند
    for t in (20, 25, 33):
        F.append((f'adx14_above_{t}', lambda df, t=t: _adx(df, 14) > t))
    # رژیمِ نوسان (کوانتایلِ غلتان ⇒ بی‌واحد و پایدار)
    for q, side in ((0.35, 'lo'), (0.65, 'hi')):
        def volf(df, q=q, side=side):
            a = _atr(df, 14)
            thr = a.rolling(2000, min_periods=250).quantile(q)
            return (a < thr) if side == 'lo' else (a > thr)
        F.append((f'atr_{side}_q{q}', volf))
    # کاراییِ کافمن
    for t in (0.10, 0.20, 0.30):
        F.append((f'er20_above_{t}', lambda df, t=t: _er(df, 20) > t))
    # ساعتِ روز (تنها فیلترِ زمانی — برای مقایسه، نه تمرکز)
    F.append(('hour_london', lambda df: pd.to_datetime(
        df['time'], unit='s', utc=True).dt.hour.between(7, 15)))
    return F


def base_rule(df):
    """قاعدهٔ پایه: گذرِ رو به بالای stoch14 از ۶۵.

    انتخاب شد چون در سرشماریِ S378 روی XAUUSD_M30 نرخِ ۸۳۶.۷/سال داشت —
    یعنی بودجهٔ فراوان ⇒ هزینهٔ فیلتر به‌خوبی دیده می‌شود.
    """
    h, l, c = (df[k].astype(float) for k in ('high', 'low', 'close'))
    hh, ll = h.rolling(14).max(), l.rolling(14).min()
    k = 100.0 * (c - ll) / (hh - ll).replace(0.0, np.nan)
    return (k.shift(1) <= 65) & (k > 65)


def main():
    census = json.load(open('results/_step1_census/data_census.json'))
    spans = {c['card']: c['span_years'] for c in census['cards']}
    cards = sys.argv[1:] or ['XAUUSD_M30', 'XAUUSD_H1', 'EURUSD_M30', 'EURUSD_H1']

    filters = build_filters()
    print(f'filters: {len(filters)}  |  base rule: stoch14_xup_65')
    print()

    for card in cards:
        yrs = spans[card]
        df = load(card)
        sig = pd.Series(base_rule(df)).fillna(False).astype(bool)
        n0 = int(sig.sum())
        r0 = n0 / yrs

        masks, solo = {}, {}
        for name, fn in filters:
            try:
                mk = pd.Series(fn(df)).fillna(False).astype(bool)
            except Exception as e:
                print(f'  ! {name}: {str(e)[:50]}')
                continue
            masks[name] = mk
            n = int((sig & mk).sum())
            solo[name] = dict(name=name, n_left=n,
                              keep=round(n / n0, 4) if n0 else 0.0,
                              per_year=round(n / yrs, 1),
                              gate_rqs2=bool(n / yrs >= RQS2_FLOOR_PER_YEAR),
                              gate_site=bool(n / yrs >= SITE_TARGET_PER_YEAR))

        # ── جفت‌ها: نسبتِ استقلال
        names = list(masks)
        pairs = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                n = int((sig & masks[a] & masks[b]).sum())
                ka, kb = solo[a]['keep'], solo[b]['keep']
                exp = ka * kb
                pairs.append(dict(
                    a=a, b=b, n_left=n,
                    keep=round(n / n0, 5) if n0 else 0.0,
                    keep_expected=round(exp, 5),
                    independence=round((n / n0) / exp, 3) if (n0 and exp > 0) else None,
                    per_year=round(n / yrs, 1),
                    gate_rqs2=bool(n / yrs >= RQS2_FLOOR_PER_YEAR),
                ))

        payload = dict(card=card, span_years=yrs,
                       base_rule='stoch14_xup_65',
                       base_n=n0, base_per_year=round(r0, 1),
                       n_filters=len(masks), n_pairs=len(pairs),
                       solo=sorted(solo.values(), key=lambda r: -r['keep']),
                       pairs=sorted(pairs, key=lambda r: -r['keep']))
        with open(os.path.join(OUT, f'filtercost_{card}.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)

        n_solo_ok = sum(1 for r in solo.values() if r['gate_rqs2'])
        n_pair_ok = sum(1 for r in pairs if r['gate_rqs2'])
        print(f'{card:14s} base={n0:6,d} ({r0:7.1f}/yr)  '
              f'solo_pass={n_solo_ok:3d}/{len(masks):3d}  '
              f'pair_pass={n_pair_ok:4d}/{len(pairs):4d}  '
              f'→ filtercost_{card}.json')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
