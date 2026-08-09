"""
s434_regime_filter_search.py — احیای S139 «رانشِ شبانه» با فیلترِ رژیم (S434)
================================================================================

## چرا این ابزار

کالبدشکافیِ گامِ ۵ نشان داد قاتلِ این لایه **تنها `maxDD`** است (۱۴.۷٪–۲۳.۹٪
در برابرِ سدِ ۸٪)، در حالی که حاشیهٔ لبه در هر چهار کارت **+۱۵ تا +۲۳ pp**
بالای سربه‌سر است. کاوشِ گامِ ۷ ثابت کرد منبعِ آن افت، **رژیمِ نزولیِ کلان**
است (فرضیهٔ A) و نه نویزِ پراکنده (C) و نه یک رویدادِ منفرد (B).

پس بهبودِ درست، **فیلترِ رژیم** است. اما فیلترِ رژیمِ تنها کافی نیست، چون:

    افت را کم می‌کند  ⟹  اما n را هم کم می‌کند  ⟹  به `H3` (توان) صدمه می‌زند

روی M15، قوی‌ترین تعریفِ رژیم (`peak_67d`) از ۱۳۴۰ معامله فقط ۱۰۰ را نگه
می‌دارد. یعنی خطرِ واقعیِ این گام **معاوضهٔ شکستِ H8 با شکستِ H3** است. این
همان تلهٔ «فیلتر معامله را می‌کشد» است که «قانونِ حفظِ بودجه» از آن هشدار
می‌دهد.

بنابراین طبق **«قانونِ همکاریِ بهبودها»** و **«قانونِ بی‌نهایت»**، این ابزار
چند اهرم را **همزمان** جارو می‌کند، نه یکی‌یکی.

--------------------------------------------------------------------------------
## اهرم‌ها — و اینکه چرا هیچ‌یک هندسه را خراب نمی‌کند

| اهرم | چه می‌کند | اثر بر سربه‌سر |
|---|---|---|
| ۱. رژیم (۳ تعریف × ۵ پنجره) | شب‌های رژیمِ نامساعد را حذف می‌کند | **هیچ** |
| ۲. ساعتِ سیگنال {۲۲} / {۲۳} / {۲۲,۲۳} | انتخابِ پنجرهٔ ورود | **هیچ** |
| ۳. `be_trigger` / `trail` | SL را بعد از سودِ محقق جابه‌جا می‌کند | **هیچ** |
| ۴. مضربِ هندسه (`TP/SL` ثابت) | مقیاسِ هر دو با هم | **هیچ** (نسبت ثابت) |

⚠️ **تعهدِ پیش‌ثبت‌شدهٔ S434:** نسبتِ `TP/SL = 3.33` را برای بالا بردنِ WR
**نمی‌شکنم**. اهرمِ ۴ فقط *مقیاس* را عوض می‌کند نه *نسبت* را، پس سربه‌سر
دست‌نخورده می‌ماند — این دقیقاً همان چیزی است که S307 نقض کرد (E-15).
اگر هر ترکیبی نسبت را عوض کند، `be_wr` و `edge_margin_pp` آن در خروجی
گزارش می‌شود تا خطای S307 نتواند خاموش تکرار شود.

--------------------------------------------------------------------------------
## دفاعِ ضدِ خودفریبی (هر بند، پاسخِ یک اشتباهِ رایج)

**الف) look-ahead در برچسبِ رژیم (خطرِ مرگبار).**
هر سه تعریفِ رژیم با `.shift(1)` عقب‌کشیده می‌شوند، پس برچسبِ کندلِ `i` تنها
از اطلاعاتِ تا `i-1` ساخته می‌شود. بدونِ این، هر فیلترِ رژیمی درخشان به نظر
می‌رسد و کلِ نتیجه بی‌ارزش است.

**ب) شبکهٔ محدودِ اعداد (اشتباهِ ۷).**
پنجره‌ها عمداً **غیرِرند** انتخاب شده‌اند: ۷/۱۳/۲۳/۴۱/۶۷ روز — نه
۱۰/۲۰/۵۰/۱۰۰/۲۰۰ و نه فیبوناچی. و سه تعریفِ **ساختاراً مستقل** (میانگینِ
متحرک / شیبِ بازدهِ انباشتهٔ بی‌اندیکاتور / عمقِ ATR-نرمال) کنارِ هم می‌آیند
تا حساسیت به فرمول‌بندی سنجیده شود، نه بهترین عدد.

**ج) tp/sl یکسان برای همهٔ تایم‌فریم‌ها (اشتباهِ ۶).**
`max_hold` بر حسبِ **۲۴ ساعتِ واقعی** به کندل تبدیل می‌شود، نه ۹۶ کندلِ ثابت.
(۹۶ کندل روی H1 یعنی هولدِ چهارروزه ⇒ لایهٔ دیگری با نامِ S139.)

**د) نتیجه‌گیریِ سریع از یک تایم‌فریم (اشتباهِ ۵).**
هر چهار کارتِ ممکن (M5/M15/M30/H1) مستقل جارو می‌شوند و هر کدام فوراً روی
دیسک می‌نشیند (قانونِ سوم: اندک اندک).

**ه) شمارشِ صادقانهٔ آزمون‌ها.**
تعدادِ کلِ ترکیب‌های آزموده‌شده شمرده و در خروجی ذخیره می‌شود تا در داوریِ
نهایی به `n_trials` دادهٔ موتور برود. بدونِ این، دروازهٔ `H5` (بقا در
آزمونِ چندگانه) با عددِ خوش‌بینانه محاسبه می‌شود — یعنی تقلبِ خاموش.

**و) این ابزار حکم صادر نمی‌کند.**
اینجا فقط *غربالِ* ترکیب‌هاست. داوریِ RQS2 v2.6 با `n_trials` واقعی در گامِ
جداگانه انجام می‌شود، تا انتخابِ نامزد و داوری در یک اجرا قاتی نشوند.
"""

import argparse
import itertools
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine.rqs2 import (                       # noqa: E402
    breakeven_wr_cost, max_consec_losses, mcl_bound,
)

OUT_DIR = os.path.join(ROOT, 'results', '_s434_search')

# ── هندسهٔ پایهٔ S139 (از strategies/s139_gold_overnight_drift.py) ─────────────
BASE_SL = 150.0
BASE_TP = 500.0
BASE_RATIO = BASE_TP / BASE_SL          # = 3.333… — این نسبت مقدس است
HOLD_HOURS = 24.0

# دقیقهٔ هر تایم‌فریم — برای تبدیلِ ۲۴ ساعت به کندل
TF_MIN = {'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240}

# ── اهرمِ ۱: تعریف‌های رژیم ────────────────────────────────────────────────────
# پنجره‌ها بر حسبِ **روز** تا بین تایم‌فریم‌ها معنایِ یکسان داشته باشند.
REGIME_DAYS = (7, 13, 23, 41, 67)
REGIME_KINDS = ('ma', 'mom', 'peak')

# ── اهرمِ ۲: ساعت‌های سیگنال ──────────────────────────────────────────────────
HOUR_SETS = ((22,), (23,), (22, 23))

# ── اهرمِ ۳: مدیریتِ پس‌از‌ورود (None = خاموش) ─────────────────────────────────
#   اعدادِ غیرِرند و متناسب با SL=150: ۰.۴۷×، ۰.۷۳×، ۱.۱×
BE_TRIGGERS = (None, 70.0, 110.0)
TRAILS = (None, 130.0, 210.0)

# ── اهرمِ ۴: مقیاسِ هندسه با **نسبتِ ثابت** ─────────────────────────────────────
GEO_SCALES = (0.73, 1.0, 1.37)


def bars_per_day(tf):
    """تعدادِ کندلِ یک روزِ معاملاتی (۲۴ ساعت) در این تایم‌فریم."""
    return max(1, int(round(24 * 60 / TF_MIN[tf])))


def load(asset, tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', f'{asset}_{tf}.csv'))
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def build_signals(df, hours):
    """بازتولیدِ **دقیقِ** منطقِ S139: ساعتِ UTC کندل در مجموعهٔ hours.

    ورود در open کندلِ بعدی توسطِ خودِ موتور انجام می‌شود (entry_bar = si+1)،
    پس اینجا نباید دستی شیفت داد — وگرنه ورود دو کندل عقب می‌افتد.
    """
    hour = df['dt'].dt.hour.values
    sig = np.zeros(len(df), bool)
    for h in hours:
        sig |= (hour == h)
    return sig


def regime_mask(df, kind, days, tf):
    """برچسبِ «رژیمِ سالم» — `True` = اجازهٔ ورودِ LONG.

    هر سه تعریف با `.shift(1)` عقب کشیده می‌شوند ⇒ بدونِ look-ahead.
    """
    n = bars_per_day(tf) * days
    c = df['close']

    if kind == 'ma':
        # سالم = قیمت بالای میانگینِ متحرکِ n-کندلی
        ref = c.rolling(n, min_periods=max(5, n // 3)).mean()
        ok = (c > ref)

    elif kind == 'mom':
        # سالم = بازدهِ انباشتهٔ n-کندلی مثبت (بی‌اندیکاتور، خالصِ قیمت)
        ok = (c - c.shift(n)) > 0

    elif kind == 'peak':
        # سالم = عمقِ زیرِ قلهٔ n-کندلی کمتر از ۱.۵ برابرِ ATR روزانه
        peak = c.rolling(n, min_periods=max(5, n // 3)).max()
        tr = (df['high'] - df['low']).rolling(bars_per_day(tf),
                                              min_periods=5).mean()
        depth = (peak - c)
        ok = depth < (1.5 * tr * np.sqrt(days))

    else:
        raise ValueError(kind)

    return ok.shift(1).fillna(False).values.astype(bool)


def eval_combo(df, tf, asset, hours, kind, days, scale, be_trig, trail):
    """یک ترکیب را می‌سنجد و متریک‌های **خامِ غربال** را برمی‌گرداند.

    هیچ حکمی صادر نمی‌شود. تنها اعدادی که برای رتبه‌بندیِ نامزدها لازم است.
    """
    sl = BASE_SL * scale
    tp = BASE_TP * scale
    # نسبت باید دست‌نخورده بماند — این را می‌سنجم نه فرض می‌کنم (تعهدِ S434)
    ratio = tp / sl

    sig = build_signals(df, hours)
    if kind is not None:
        sig = sig & regime_mask(df, kind, days, tf)

    n_sig = int(sig.sum())
    if n_sig < 25:
        return None

    mh = max(1, int(round(HOLD_HOURS * 60 / TF_MIN[tf])))
    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False,
                            be_trigger_pip=be_trig, trail_pip=trail)
    if tr is None or len(tr) < 25:
        return None

    pnl = tr['pnl_pip'].values.astype(np.float64)
    n = len(pnl)
    wins = int((pnl > 0).sum())
    wr = 100.0 * wins / n
    net = float(pnl.sum())
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    pf = (gp / gl) if gl > 0 else 999.0

    cfg = se.ASSETS[asset]

    # ⚠️ BUG-NOTIONALSIZE (S434) — نسخهٔ اول افت را **دستی** حساب می‌کرد با
    #   فرضِ «۱ لاتِ ثابت» روی حسابِ ۱۰٬۰۰۰$:
    #       usd = pnl * pip * 100 ;  eq = 10000 + cumsum(usd)
    #   نتیجه‌اش `max_dd = 182.03٪` بود در ردیفِ کنترل — **افتِ بیش از ۱۰۰٪
    #   ریاضیاً محال است** (یعنی حساب منفی شده). ریشه: با SL=۱۵۰ pip و
    #   pip_value=۱۰۰$، یک لاتِ کامل روی حسابِ ۱۰٬۰۰۰$ یعنی **۱۵۰٪ ریسک در هر
    #   معامله**. موتور اما `run_capital` را می‌راند که لات را طوری می‌چیند که
    #   خوردنِ کاملِ SL دقیقاً `risk_pct%` از equityِ جاری را ببرد، با
    #   بهره‌مرکب و سقفِ اهرمِ MAX_LOTS_PER_10K.
    #   خطرِ واقعی: افتِ کاذبِ ~۱۲ برابر، `h8_dd` را برای **هر ۱۲۹۶ ترکیب**
    #   رد می‌کرد ⇒ من داشتم نتیجه بگیرم «فیلترِ رژیم لایه را نجات نمی‌دهد»
    #   در حالی که کاوشِ گامِ ۷ خلافش را نشان داده بود. تناقضِ بین دو ابزارِ
    #   خودم بود که مرا به این باگ رساند، نه یک استثنا.
    #   اصلاح: حسابداریِ سرمایه به **خودِ موتور** واگذار می‌شود.
    #   نام کلیدها از **متنِ خودِ موتور** (خطوطِ ۳۵۱–۳۶۷) گرفته شد نه از حافظه،
    #   چون همین حدس‌زدن در BUG-METRICKEYS به سه جزءِ `None` منتهی شد.
    #   ⚠️ نکتهٔ ظریف: کلیدِ آمادهٔ `net_over_dd` شرطِ `max_dd < 0` دارد ولی
    #   موتور `max_dd` را **مثبت** ذخیره می‌کند ⇒ آن کلید همیشه `inf` است.
    #   پس `recovery` را خودم از `net_profit / max_dd` می‌سازم، همان‌طور که
    #   `rqs2.compute_rqs2` می‌کند.
    cap, _ = se.run_capital(tr, asset, initial_capital=10000.0)
    dd_pct = abs(float(cap['max_dd_pct']))
    net_usd = float(cap['net_profit'])
    dd_usd = abs(float(cap['max_dd']))
    rec = (net_usd / dd_usd) if dd_usd > 0 else float('inf')
    ruined = bool(cap.get('ruined', False))

    # ⚠️ BUG-OUTCOMETYPE (S434) — در نسخهٔ اول آرایهٔ **عددیِ** pip را به
    #   `max_consec_losses` دادم، اما آن تابع آرایهٔ **برچسبیِ** 'win'/'loss'
    #   می‌خواهد و شرطش `if o == 'win'` است. هیچ عددِ شناوری با رشتهٔ 'win'
    #   مساوی نیست، پس هر معامله «باخت» شمرده شد و خروجی `mcl = n` شد.
    #   نشانهٔ محال در لاگ: `mcl=862/862` با WR=33.99٪ — یعنی ادعا می‌شد هر
    #   ۸۶۲ معامله پشت‌سرهم باخت‌اند، در حالی که ۲۹۳ برد وجود داشت.
    #   خطرِ واقعی: این خطا `h8_mcl` را برای ۸۷۳ ترکیب **کاذباً رد** می‌کرد،
    #   یعنی ممکن بود ترکیبِ نجات‌دهنده را با دستِ خودم دور بریزم.
    outcomes = ['win' if p > 0 else 'loss' for p in pnl]
    mcl = int(max_consec_losses(outcomes))
    mcl_max = int(mcl_bound(n, 1.0 - wr / 100.0))

    cost = cfg['spread_pip'] + 2.0 * cfg['slip_pip']
    be = breakeven_wr_cost(sl, tp, cost)

    # سه شرطِ H8 — دقیقاً همان‌ها که موتور می‌سنجد
    h8_dd = dd_pct <= 8.0
    h8_mcl = mcl <= mcl_max
    h8_rec = (rec >= 3.0) or not np.isfinite(rec)

    return {
        'hours': list(hours), 'regime': kind, 'days': days,
        'scale': scale, 'sl': sl, 'tp': tp, 'ratio': round(ratio, 4),
        'be_trigger': be_trig, 'trail': trail,
        'n_signals': n_sig, 'n': n, 'wr': round(wr, 3),
        'be_wr': round(be, 3) if be is not None else None,
        'edge_margin_pp': round(wr - be, 3) if be is not None else None,
        'pf': round(pf, 4), 'net_pip': round(net, 1),
        'exp_pip': round(net / n, 4),
        'max_dd_pct': round(dd_pct, 3), 'recovery': round(rec, 3),
        'net_usd': round(net_usd, 1), 'dd_usd': round(dd_usd, 1),
        'avg_lot': round(float(cap['avg_lot']), 3),
        'mcl': mcl, 'mcl_allowed': mcl_max,
        # 🔴 `ruined` را صریح ذخیره می‌کنم: حسابِ ورشکسته‌شده هرگز نباید در
        #   جدولِ «نامزدهای پاس‌شده» ظاهر شود، حتی اگر متریک‌هایش زیبا باشند.
        'ruined': ruined,
        'h8_dd': h8_dd, 'h8_mcl': h8_mcl, 'h8_rec': h8_rec,
        'h8_all': bool(h8_dd and h8_mcl and h8_rec and not ruined),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tfs', default='M30')
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    # فضایِ جستجو — با «رژیمِ خاموش» هم آزموده می‌شود تا اثرِ فیلتر منفرد شود
    regime_space = [(None, 0)] + [(k, d) for k in REGIME_KINDS
                                  for d in REGIME_DAYS]

    for tf in [t.strip() for t in args.tfs.split(',') if t.strip()]:
        df = load(args.asset, tf)
        rows, n_trials = [], 0
        space = itertools.product(HOUR_SETS, regime_space, GEO_SCALES,
                                  BE_TRIGGERS, TRAILS)
        for hours, (kind, days), scale, be_t, tl in space:
            n_trials += 1
            try:
                r = eval_combo(df, tf, args.asset, hours, kind, days,
                               scale, be_t, tl)
            except Exception as e:
                print(f'  !! {tf} {hours} {kind}{days} s={scale}: {e}')
                continue
            if r is not None:
                rows.append(r)

        # 🔒 صداقتِ آماری: n_trials شمرده می‌شود، نه تخمین زده.
        #    این عدد به دروازهٔ H5 (بقا در آزمونِ چندگانه) داده خواهد شد.
        passing = [r for r in rows if r['h8_all']]

        # رتبه‌بندی: میانِ آن‌هایی که H8 را پاس می‌کنند، بزرگ‌ترین n
        #   ← عمداً بر اساسِ **توان** مرتب می‌کنم نه بر اساسِ سود، چون خطرِ
        #     شناخته‌شدهٔ این گام شکستِ H3 است نه کمبودِ سود.
        passing.sort(key=lambda r: (-r['n'], -r['exp_pip']))

        out = {
            'note': 'S434 regime-filter search on S139 overnight drift',
            'asset': args.asset, 'tf': tf,
            'base_geometry': {'sl': BASE_SL, 'tp': BASE_TP,
                              'ratio': round(BASE_RATIO, 4),
                              'hold_hours': HOLD_HOURS},
            'n_trials_total': n_trials,
            'n_evaluated': len(rows),
            'n_h8_passing': len(passing),
            'top_h8_passing': passing[:25],
            'all_rows': rows,
        }
        fp = os.path.join(OUT_DIR, f'search_{args.asset}_{tf}.json')
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)

        print(f'[{args.asset}-{tf}] trials={n_trials} evaluated={len(rows)} '
              f'H8-passing={len(passing)}')
        for r in passing[:6]:
            print(f'   n={r["n"]:>5} wr={r["wr"]:>6.2f} pf={r["pf"]:>6.3f} '
                  f'dd={r["max_dd_pct"]:>6.2f}% rec={r["recovery"]:>6.2f} '
                  f'exp={r["exp_pip"]:>8.2f} margin={r["edge_margin_pp"]:>6.2f}pp '
                  f'| h={r["hours"]} {r["regime"]}{r["days"]} '
                  f'sc={r["scale"]} be={r["be_trigger"]} tr={r["trail"]}')
        sys.stdout.flush()

    print('[done]')


if __name__ == '__main__':
    main()
