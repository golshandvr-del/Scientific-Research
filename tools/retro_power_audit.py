# -*- coding: utf-8 -*-
"""حسابرسیِ retro با منحنیِ توانِ کالیبره‌شده — **کدام ردها بی‌اطلاع بودند؟**

## پرسشِ این ابزار

کالیبراسیونِ `Q10` روی هر ۴ کارتِ طلا نشان داد:

```
توان(WR=65٪) ≈ ۰٪   برای n < ~۳۰۰
توان(WR=65٪) ≈ ۹۶٪   برای n ≥ ۳۲۰
```

پیامدِ فوری و اجتناب‌ناپذیر: **هر لایه‌ای که با `n` کوچک رد شد، «سوخته»
نیست — «ردِ بی‌اطلاع» است.** چون اگر لبهٔ واقعیِ ۶۵٪ هم داشت، معیار
تقریباً همیشه ردش می‌کرد.

این ابزار روی **۷۳۶ فایلِ JSONِ اجراهای واقعیِ خودِ پروژه** می‌گردد، `n` هر
آزمون را استخراج می‌کند و با **منحنیِ توانِ کالیبره‌شدهٔ همان کارت** (نه یک
عددِ حدسیِ ۳۰۰) تلاقی می‌دهد.

## چرا این کار درجهٔ آزادی خرج نمی‌کند

هیچ فرضیهٔ بازاری آزموده نمی‌شود. هیچ پارامتری جست‌وجو نمی‌شود. هیچ لایه‌ای
پاس/رد نمی‌شود. این ابزار فقط **بازخوانیِ اعدادِ قبلاً ثبت‌شده** است و آنها را
با یک منحنیِ اندازه‌گیری‌شده مقایسه می‌کند ⇒ صفر خرج از دفترِ چندگانگی.

## فنسِ صداقت — این ابزار چه چیزی را **اثبات نمی‌کند**

۱. **هیچ لایهٔ سوخته‌ای «نجات» پیدا نمی‌کند.** «ردِ بی‌اطلاع» یعنی
   *نمی‌دانیم*، نه یعنی *لبه داشت*. تفکیکِ این دو حیاتی است و هر خوانشِ
   دیگری تقلب است.
۲. **مجوزِ شل کردنِ هیچ دروازه‌ای صادر نمی‌شود.** شرطِ مشاور برای ادغامِ
   دروازه‌ها (توان<۵۰٪ با nِ کافی) روی هر ۴ کارت **برقرار نشد**.
۳. **مجوزِ بازآزماییِ خودسرانه صادر نمی‌شود.** هر بازآزمایی یک آزمونِ نو
   است و باید هزینهٔ خودش را به دفترِ چندگانگی بپردازد.
۴. آنچه **می‌دهد** فقط یک چیز است: صفِ اولویت. اگر بازآزمایی‌ای انجام شود،
   کدام لایه‌ها بیشترین احتمالِ داشتنِ لبهٔ کشف‌نشده را دارند.

## معیارِ اولویت — چرا `n` تنها ملاک نیست

یک لایه با `n=۱۰` و `WR=۵۲٪` هیچ نشانه‌ای از لبه ندارد؛ بی‌اطلاع بودنش
بی‌اهمیت است. اما لایه‌ای با `n=۸۰` و `WR=۶۸٪` هم بی‌اطلاع است و هم
**نشانهٔ لبه** دارد. پس اولویت با هر دو تعریف می‌شود:

```
اولویت  =  (۱ − توانِ کالیبره‌شده)  ×  نشانهٔ لبه
```

که در آن «نشانهٔ لبه» = لیفتِ مشاهده‌شده روی مبنای پوچِ همان کارت.
عاملِ اول یعنی «چقدر کور بودیم»، عاملِ دوم یعنی «چقدر چیزی برای دیدن بود».
"""

import json
import glob
import os
import re

OUT = 'results/_audit_retro_power'
CALIB_DIR = 'results/_calib_power'
LM_DIR = 'local-mobile'
os.makedirs(OUT, exist_ok=True)


def deployed_layers():
    """لایه‌هایی که **همین حالا در `local-mobile` مستقرند**.

    چرا لازم است: صفِ اولویت باید «سرنخِ کشف‌نشده» بدهد. اگر مشاهده‌ای به
    لایه‌ای تعلق دارد که هم‌اکنون فعال است، آن مشاهده کشفِ نو نیست —
    بازتابِ چیزی است که پروژه قبلاً پذیرفته و به کار گرفته. بی‌برچسب
    گذاشتنش باعث می‌شود پرتفویِ موجود به‌شکلِ فرصتِ جدید دیده شود.
    """
    ids = set()
    if not os.path.isdir(LM_DIR):
        return ids
    for fn in os.listdir(LM_DIR):
        p = os.path.join(LM_DIR, fn)
        if not os.path.isfile(p):
            continue
        try:
            txt = open(p, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        ids.update(m.upper() for m in re.findall(r'\bS(\d{2,3})\b', txt))
    return {f'S{i}' for i in ids}


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) بارگذاریِ منحنی‌های توانِ کالیبره‌شده — اندازه‌گیری‌شده، نه حدسی
# ═══════════════════════════════════════════════════════════════════════════

def load_power_curves():
    """منحنیِ توان از فایل‌های `results/_calib_power/*.json`.

    ساختارِ خروجی:  `{card: {wr_target: {n: power}}}` + مبنای پوچِ هر کارت.
    """
    curves, baselines = {}, {}
    for f in sorted(glob.glob(os.path.join(CALIB_DIR, 'power_*.json'))):
        d = json.load(open(f))
        card = d['card']
        baselines[card] = d['base_wr']
        cur = {}
        for v in d['cells'].values():
            cur.setdefault(v['wr_target'], {})[v['n']] = v['power']
        curves[card] = cur
    return curves, baselines


def interp_power(curve, wr, n):
    """توانِ **کران‌دارِ محافظه‌کارانه** در `(wr, n)` — نه درون‌یابیِ خطی.

    ## 🐞 چرا نسخهٔ خطیِ اول غلط بود

    نسخهٔ اول درون‌یابیِ دوخطی می‌کرد. یک ردیف مشکوک شد و بازرسی نشان داد
    باگ **ریاضی** است نه داده‌ای:

    ```
    شبکهٔ XAUUSD_M30، ردیفِ WR=72:    n=40 → ۰.۰٪      n=80 → ۹۴.۴٪
    درون‌یابیِ خطی در n=65:            ۰ + ۰.۶۲۵×۹۴.۴ = ۵۹.۰٪
    سپس بین WR=68 (صفر) و WR=72:                        → ۴۰.۹٪
    ```

    اما سطحِ توان یک **گذارِ فازِ تقریباً پله‌ای** است، نه سطحی صاف. عددِ
    ۴۰.۹٪ در **هیچ سلولِ واقعیِ کالیبراسیون وجود ندارد** — مصنوعِ خطِ راستی
    است که از یک پله عبور داده شده.

    و جهتِ خطا بدترین جهتِ ممکن است: توان را **بالاتر** از واقع نشان می‌دهد،
    پس «کوری» را **کمتر** از واقع ⇒ خطا به نفعِ راحتیِ ما بود.

    ## راهِ درست: کرانِ پایینِ محافظه‌کارانه

    به‌جای حدس زدنِ مقدارِ میانِ دو نقطهٔ شبکه، **بدترین گوشهٔ محاصره‌کننده**
    برداشته می‌شود:

    ```
    توان(wr, n)  ≡  min  توان(w, m)   به‌شرطِ  w ≤ wr  و  m ≤ n
    ```

    یعنی: «توان **حداکثر** آن‌قدری است که نزدیک‌ترین سلولِ شبکه‌ای که هم
    لبهٔ کوچک‌تر و هم نمونهٔ کوچک‌ترِ آن را داریم، نشان می‌دهد.» چون توان در
    هر دو متغیر **یکنوا صعودی** است، این یک کرانِ پایینِ معتبر است و
    هیچ‌گاه عددِ ساختگیِ میانی تولید نمی‌کند.

    خطای باقی‌مانده در جهتِ **محافظه‌کارانه** است: ممکن است کوری را بیش از
    واقع تخمین بزند، که برای این حسابرسی جهتِ درست است — چون فهرستِ اولویت
    را به‌سمتِ احتیاط می‌برد، نه به‌سمتِ خوش‌بینی.
    """
    wrs = sorted(curve.keys())
    ns = sorted(next(iter(curve.values())).keys())

    # ── سلول‌های شبکه‌ای که هم `w ≤ wr` و هم `m ≤ n` باشند
    w_ok = [w for w in wrs if w <= wr]
    n_ok = [m for m in ns if m <= n]

    # اگر زیرِ کفِ شبکه باشد، محافظه‌کارانه‌ترین حالت: کفِ شبکه
    if not w_ok:
        w_ok = [wrs[0]]
    if not n_ok:
        n_ok = [ns[0]]

    # بدترین (کم‌ترین) توان در میانِ گوشه‌های محاصره‌کنندهٔ پایین‌دست
    return min(curve[w][m] for w in [max(w_ok)] for m in [max(n_ok)])


# ═══════════════════════════════════════════════════════════════════════════
#  ۲) استخراجِ (n, wr, card) از JSONهای تاریخیِ پروژه
# ═══════════════════════════════════════════════════════════════════════════

N_KEYS = ('n', 'n_trades', 'trades', 'ntrades')
WR_KEYS = ('wr', 'win_rate', 'winrate', 'wr_pct')
# ── مرجعِ خنثای ثبت‌شدهٔ خودِ آزمون. ترتیب اهمیت دارد: `ref` صریح‌ترین است،
#    `perm_mean` میانگینِ توزیعِ جایگشتیِ همان آزمون، `uncond` نرخِ بی‌قیدِ
#    همان هندسه. هر سه از خودِ آزمون می‌آیند و هندسهٔ آن را می‌شناسند.
REF_KEYS = ('ref', 'perm_mean', 'uncond', 'ref_wr', 'baseline_wr')
# ── نشانگرِ سودآوریِ هم‌سطح. یک مشاهده با WR بالا اما سودِ منفی، «سرنخِ لبه»
#    نیست — امضای اشتباهِ رایجِ #۸ است (TP<SL ⇒ بردِ پرتکرارِ کوچک، باختِ
#    نادرِ بزرگ). چنین مشاهده‌ای باید از صفِ اولویت **حذف** شود، نه اینکه
#    به صدرش برود.
PROFIT_KEYS = ('meanr', 'mean_r', 'sumr', 'sum_r', 'net', 'net_pips',
               'pnl', 'expectancy', 'e_pip', 'sharpe', 'profit', 'meanR')
# ── نقطهٔ سربه‌سرِ هندسهٔ براکت. **مرجعِ درستِ لیفت همین است**، نه نرخِ بردِ
#    بی‌قید. با TP<SL یک ورودِ بی‌مهارت هم نرخِ بردِ بالا می‌دهد؛ اگر مرجع را
#    ~۵۲٪ بگیریم، لیفت به‌طورِ سیستماتیک روی همان هندسه‌ها متورم می‌شود که
#    اشتباهِ رایجِ #۸ در آن‌ها زندگی می‌کند. (سندِ S375)
BE_KEYS = ('be_true_pct', 'be_pct', 'breakeven_pct', 'be_true')
SL_KEYS = ('sl_pip_median', 'sl_pip', 'sl_pips', 'med_sl', 'sl')
TP_KEYS = ('tp_pip_median', 'tp_pip', 'tp_pips', 'med_tp', 'tp')
RR_KEYS = ('rr_realised', 'rr', 'rr_ratio', 's')
# اسپردِ واقعیِ حسابِ دمو: 0.33 $/oz = 3.3 pip. کمیسیونِ جداگانه ندارد.
COST_PIP = 3.3
CARD_RE = re.compile(r'(XAUUSD|EURUSD|GBPUSD|USDJPY|AUDUSD)[_\-]?(M1|M5|M15|M30|H1|H4|D1|W1)',
                     re.I)


def _num(node, keys, lo, hi):
    """اولین کلیدِ عددیِ معتبر از `keys` در همین دیکشنری."""
    for want in keys:
        for k, v in node.items():
            if str(k).lower() == want.lower() and isinstance(v, (int, float)) \
                    and lo < float(v) < hi:
                return float(v)
    return None


def breakeven_of(node):
    """نقطهٔ سربه‌سرِ همین گره (درصد)، یا `None`.

    چهار سطحِ اولویت (سندِ S375):
      ۱) `be_true_pct` ثبت‌شده — معتبرترین، سازندهٔ فایل هندسه‌اش را می‌دانست.
      ۲) از pipِ SL/TP: ``BE = (SL + cost) / (TP + SL)`` — بازتولیدِ دقیقِ #۱.
      ۳) از نسبتِ RR: ``BE ≈ 1/(1+rr)`` — ضعیف‌تر، چون مقیاسِ مطلق را از دست
         می‌دهد و هزینه را نمی‌توان دقیق شارژ کرد.
      ۴) هیچ ⇒ `None` (مرجع نامعلوم؛ نباید مرجعِ غلط جانشین شود).
    """
    be = _num(node, BE_KEYS, 0.0, 100.0)
    if be is not None:
        return be, 'recorded'
    sl = _num(node, SL_KEYS, 0.0, 1e6)
    tp = _num(node, TP_KEYS, 0.0, 1e6)
    if sl and tp:
        return 100.0 * (sl + COST_PIP) / (tp + sl), 'pips'
    rr = _num(node, RR_KEYS, 0.0, 1e3)
    if rr:
        return 100.0 / (1.0 + rr), 'rr'
    return None, None


def harvest(path, node, card_hint, out, depth=0, be_inh=None):
    """پیمایشِ بازگشتی برای یافتنِ جفت‌های `(n, wr)` هم‌سطح.

    شرطِ پذیرش: `n` و `wr` **در همان دیکشنری** باشند — تا `n` یک آزمون با
    `wr` آزمونِ دیگری اشتباه جفت نشود.

    `be_inh` = هندسهٔ **به‌ارث‌رسیده از بالا**. قاعدهٔ هم‌سطحی برای هندسه کار
    نمی‌کند: آرشیو `sl_pip_median`/`tp_pip_median` را در سطحِ بالای فایل ثبت
    می‌کند، ولی `(n, wr)` در گره‌های تودرتو است. پس هندسه باید در پیمایش
    نزول کند — و اگر گرهِ عمیق‌تر هندسهٔ خودش را داشت، آن **خاص‌تر** است و
    ارث را کنار می‌زند (مثلِ گریدی که هر عضو براکتِ خودش را دارد).
    """
    if depth > 5:
        return
    if isinstance(node, dict):
        # هندسهٔ همین گره (اگر باشد) بر ارث اولویت دارد
        be_here = breakeven_of(node)
        be_cur = be_here if be_here[0] is not None else (be_inh or (None, None))
        n_val = wr_val = ref_val = None
        for k, v in node.items():
            kl = str(k).lower()
            if kl in N_KEYS and isinstance(v, (int, float)) and 0 < v < 1e6:
                n_val = int(v)
            if kl in WR_KEYS and isinstance(v, (int, float)) and 0 <= v <= 100:
                wr_val = float(v)
        # ── مرجعِ خنثای خودِ همین آزمون، به ترتیبِ اولویتِ REF_KEYS.
        #    باید هم‌سطحِ (n, wr) باشد تا مرجعِ آزمونِ دیگری قرض گرفته نشود.
        for rk in REF_KEYS:
            for k, v in node.items():
                if str(k).lower() == rk and isinstance(v, (int, float)) \
                        and 0 < v < 100:
                    ref_val = float(v)
                    break
            if ref_val is not None:
                break
        # ── نشانگرِ سودآوریِ هم‌سطح (اگر ثبت شده باشد)
        prof_val = prof_key = None
        for pk in PROFIT_KEYS:
            for k, v in node.items():
                if str(k) == pk or str(k).lower() == pk.lower():
                    # NaN/Inf نه مثبت است نه منفی ⇒ نباید دروازه را دور بزند.
                    if isinstance(v, (int, float)) and -1e12 < v < 1e12:
                        prof_val, prof_key = float(v), str(k)
                        break
            if prof_val is not None:
                break
        # کارت را از خودِ گره یا از نامِ فایل برمی‌داریم
        card = card_hint
        p = node.get('pair')
        t = node.get('tf') or node.get('timeframe')
        if isinstance(p, str) and isinstance(t, str):
            card = f'{p.upper()}_{t.upper()}'
        if n_val is not None and wr_val is not None:
            out.append(dict(file=path, card=card, n=n_val, wr=wr_val,
                            own_ref=ref_val,
                            be=be_cur[0], be_src=be_cur[1],
                            profit=prof_val, profit_key=prof_key))
        for v in node.values():
            harvest(path, v, card, out, depth + 1, be_cur)
    elif isinstance(node, list):
        for v in node[:400]:
            harvest(path, v, card_hint, out, depth + 1, be_inh)


def main():
    curves, baselines = load_power_curves()
    dep = deployed_layers()
    print(f'deployed layers in local-mobile: {len(dep)} '
          f'→ {sorted(dep, key=lambda s: int(s[1:]))}')
    if not curves:
        print('no calibrated power curves found — run power_calibration first')
        return
    print('calibrated cards:', sorted(curves.keys()))
    print('baselines       :', {k: round(v, 3) for k, v in baselines.items()})
    print()

    files = sorted(glob.glob('results/**/*.json', recursive=True))
    # فایل‌های خودِ کالیبراسیون و حسابرسی‌ها را کنار می‌گذاریم (خودارجاعی)
    files = [f for f in files
             if '_calib_power' not in f and '_audit_retro_power' not in f]

    rows = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        m = CARD_RE.search(os.path.basename(f))
        hint = f'{m.group(1).upper()}_{m.group(2).upper()}' if m else None
        harvest(f, d, hint, rows)

    print(f'harvested {len(rows):,} (n, wr) observations from {len(files):,} files')

    # ── فقط آزمون‌هایی که کارتشان کالیبره شده قابلِ داوری‌اند
    judged = []
    for r in rows:
        card = r['card']
        if card not in curves:
            continue
        # ── مرجعِ درست = مرجعِ ثبت‌شدهٔ خودِ آزمون (هندسه‌اش را می‌شناسد).
        #    فقط در نبودش به بیس‌لاینِ کالیبراسیون برمی‌گردیم، و آن مشاهده
        #    را علامت می‌زنیم تا در تفسیر با بقیه یکسان شمرده نشود.
        own = r.get('own_ref')
        if own is not None:
            base, ref_src = own, 'own'
        else:
            base, ref_src = baselines[card], 'calib'
        pw = interp_power(curves[card], r['wr'], r['n'])
        lift = r['wr'] - base
        # ── دروازهٔ سودآوری: یک مشاهدهٔ ضررده «سرنخِ لبه» نیست. اگر نشانگرِ
        #    سود هم‌سطح ثبت شده و منفی است، اولویتش صفر می‌شود — از صف حذف،
        #    نه در صدرِ آن. (اگر ثبت نشده باشد، وضعیتش نامعلوم است و همان
        #    lift ملاک می‌ماند، ولی با پرچمِ profit_known=False.)
        prof = r.get('profit')
        prof_known = prof is not None
        losing = bool(prof_known and prof < 0)
        # ── لایهٔ مستقر: کشفِ نو نیست، پرتفویِ فعلیِ خودمان است.
        # هیچ‌کدام از دو مرزِ `\b` اینجا کار نمی‌کند: مرزِ چپ بینِ `_` و `s`
        # برقرار نیست (underscore خودش کاراکترِ کلمه است) و مرزِ راست بینِ
        # رقم و حرفِ نسخه (`_s313e_`) برقرار نیست. پس `\bs(\d+)\b` روی
        # نامِ فایل‌های واقعیِ پروژه **هیچ‌گاه** تطبیق نمی‌کرد.
        # مرزِ چپ = «رقم یا حرف نباشد»، مرزِ راست = «رقم نباشد».
        m = re.search(r'(?:^|[^0-9a-z])s(\d{2,3})(?![0-9])', r['file'], re.I)
        lid = f'S{m.group(1)}' if m else None
        is_dep = lid in dep if lid else False
        prio = 0.0 if (losing or is_dep) \
            else round((1.0 - pw) * max(lift, 0.0), 3)
        judged.append(dict(**r, base_wr=round(base, 3), ref_src=ref_src,
                           lift=round(lift, 3),
                           power=round(pw, 4),
                           blindness=round(1.0 - pw, 4),
                           profit_known=prof_known, losing=losing,
                           layer=lid, deployed=is_dep,
                           priority=prio))

    print(f'judgeable (calibrated card): {len(judged):,}')
    print()

    # ── تجمیعِ آماری
    n_blind = sum(1 for r in judged if r['power'] < 0.10)
    n_seen = sum(1 for r in judged if r['power'] >= 0.80)
    print(f'  power < 10%  (essentially blind) : {n_blind:,}  '
          f'({100*n_blind/max(len(judged),1):.1f}%)')
    print(f'  power >= 80% (adequately seen)   : {n_seen:,}  '
          f'({100*n_seen/max(len(judged),1):.1f}%)')
    print()

    # ── صفِ اولویتِ بازآزمایی
    judged.sort(key=lambda r: -r['priority'])
    n_losing = sum(1 for r in judged if r['losing'])
    n_prof_unk = sum(1 for r in judged if not r['profit_known'])
    n_dep = sum(1 for r in judged if r['deployed'])
    print(f'  losing (profit<0) → priority forced to 0 : {n_losing:,}')
    print(f'  already-deployed layer → priority 0      : {n_dep:,}')
    print(f'  profit not recorded (status unknown)     : {n_prof_unk:,}  '
          f'({100*n_prof_unk/max(len(judged),1):.1f}%)')
    print()
    print('TOP RETEST PRIORITY  (blind AND showing edge signal AND not losing)')
    hdr = (f"{'card':14s} {'n':>6s} {'wr':>7s} {'base':>7s} {'lift':>7s} "
           f"{'power':>7s} {'profit':>10s} {'prio':>7s}  file")
    print(hdr)
    print('-' * len(hdr))
    seen_files = set()
    shown = 0
    for r in judged:
        # یک ردیف در هر فایل ⇒ فهرست خواندنی بماند
        if r['file'] in seen_files:
            continue
        seen_files.add(r['file'])
        pstr = ('n/a' if not r['profit_known']
                else f"{r['profit']:+.4f}")
        print(f"{r['card']:14s} {r['n']:6d} {r['wr']:7.2f} {r['base_wr']:7.2f} "
              f"{r['lift']:+7.2f} {100*r['power']:6.1f}% {pstr:>10s} "
              f"{r['priority']:7.2f}  "
              f"{os.path.basename(r['file'])[:40]}")
        shown += 1
        if shown >= 25:
            break

    payload = dict(
        calibrated_cards=sorted(curves.keys()),
        baselines={k: round(v, 4) for k, v in baselines.items()},
        n_files_scanned=len(files),
        n_observations=len(rows),
        n_judgeable=len(judged),
        n_power_below_10pct=n_blind,
        n_power_above_80pct=n_seen,
        note=('Retro audit. Zero degrees of freedom: no hypothesis tested, no '
              'parameter searched, no layer passed or rejected. An uninformative '
              'rejection means UNKNOWN, not VINDICATED.'),
        observations=judged,
    )
    with open(os.path.join(OUT, 'retro_power_audit.json'), 'w') as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
    print(f'\nsaved → {OUT}/retro_power_audit.json')


if __name__ == '__main__':
    main()
