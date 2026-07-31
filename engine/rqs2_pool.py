# -*- coding: utf-8 -*-
"""
RQS2-POOL — تجمیعِ چند-کارتیِ لبه‌های POWER-LIMITED برای بزرگ‌کردنِ نمونه
================================================================================
مسئله‌ای که این ماژول حل می‌کند (تصمیمِ حاکمیتیِ کاربر، هم‌راه با حکمِ
POWER-LIMITED در `engine/rqs2.py`):

یک لبهٔ اقتصاداً-سالم می‌تواند فقط به‌خاطرِ کمبودِ نمونه، دروازهٔ توان‌محورِ
H3 (که z≥3σ می‌خواهد و z∝√n) را رد کند. نمونهٔ زنده: S351/LPSB روی
XAUUSD-D1 با lift=+۱۴pp ولی تنها ۷۴ معامله ⇒ z=2.6<3.0. راهِ نجات **شل
کردنِ آستانه نیست** (که سپرِ ضدِ تقلب را می‌شکند)، بلکه **بزرگ‌کردنِ نمونه**
است: همان قانونِ ساختاری روی چند تایم‌فریمِ هم‌جهت اجرا و trades ادغام شود.

--------------------------------------------------------------------------------
چهار شرطِ اعتبارِ علمیِ تجمیع (بدونِ این‌ها تجمیع = تقلبِ آماری):
  ۱) هندسهٔ **یکسان**: همان قانون و همان براکتِ نسبی (ATR-محور) روی همهٔ کارت‌ها.
  ۲) هم‌جهتی: lift هر کارتِ عضو باید **مثبت** باشد؛ اگر کارتی lift<0 دارد،
     ادغامش «میانگین‌گیری با نویز» است و ممنوع.
  ۳) بی‌همپوشانی در سطحِ زمانِ واقعی: چون کارت‌ها تایم‌فریم‌های متفاوت‌اند،
     ورودهایشان روی محورِ زمانِ تقویمی نگاشت و صفِ FIFO می‌شود تا concurrency
     واقعی بماند (نه تورمِ مصنوعیِ H0/H8).
  ۴) **همگنیِ قدرتِ لبه** (درسِ کلیدیِ آزمونِ S351): هم‌جهت بودن کافی نیست.
     lift استخر تقریباً میانگینِ **وزنی** با وزنِ تعدادِ معامله است:
         lift_pool ≈ Σ(nᵢ·liftᵢ) / Σnᵢ
     پس اگر یک کارتِ قویِ کوچک (D1: n=۷۴ lift=+۱۴) را با کارتِ ضعیفِ بزرگ
     (H1: n=۱۹۳۷ lift=+۲.۳) ادغام کنیم، لبهٔ قوی در دریای معاملاتِ ضعیف
     **رقیق** می‌شود: lift_pool≈۲.۷ (که با نتیجهٔ تجربیِ +۲.۵ می‌خواند) و z
     هرگز از ۳ رد نمی‌شود. تجمیعِ خام فقط وقتی *تقویت‌کننده* است که lift اعضا
     در یک بازهٔ همگن باشند. این ماژول قبل از ادغام یک پیش‌بینیِ z می‌سازد و
     اگر تجمیعِ کاملْ z را کاهش دهد، به‌جای آن **بزرگ‌ترین زیرمجموعهٔ همگنی**
     را که بیشترین z را می‌دهد پیشنهاد می‌کند (حریصانه، از قوی‌ترین کارت).

خروجی: یک شیءِ trades ادغام‌شده + zمانِ تقویمی، آمادهٔ دادن به `compute_rqs2`.
این ماژول **حکم نمی‌دهد**؛ فقط استخر را می‌سازد. داوری با همان
`compute_rqs2` روی استخر انجام می‌شود تا هیچ آستانه‌ای دور زده نشود.
"""
import numpy as np
import pandas as pd


def _to_calendar(tr, dt_values):
    """
    ورود/خروجِ هر معامله را از اندیسِ کندلِ کارتِ خودش به **زمانِ تقویمیِ
    مطلق** (نانوثانیه) نگاشت می‌کند تا معاملاتِ تایم‌فریم‌های مختلف روی یک
    محورِ مشترک مقایسه‌شدنی شوند.
    """
    eb = tr['entry_bar'].values.astype(np.int64)
    xb = tr['exit_bar'].values.astype(np.int64)
    n = len(dt_values)
    eb = np.clip(eb, 0, n - 1)
    xb = np.clip(xb, 0, n - 1)
    t_entry = dt_values[eb].astype('datetime64[ns]').astype(np.int64)
    t_exit = dt_values[xb].astype('datetime64[ns]').astype(np.int64)
    out = tr.copy()
    out['t_entry'] = t_entry
    out['t_exit'] = t_exit
    return out


def _fifo_calendar(pool):
    """
    صفِ FIFO روی زمانِ تقویمی: به ترتیبِ ورود پیش می‌رویم و معامله فقط اگر
    ورودش پس از خروجِ آخرین معاملهٔ پذیرفته‌شده باشد نگه داشته می‌شود.
    concurrency را به ۱ می‌رساند و تورمِ مصنوعیِ همپوشانی را حذف می‌کند.
    """
    pool = pool.sort_values('t_entry', kind='mergesort').reset_index(drop=True)
    keep = []
    last_exit = -(1 << 62)
    te = pool['t_entry'].values
    tx = pool['t_exit'].values
    for i in range(len(pool)):
        if te[i] > last_exit:
            keep.append(i)
            last_exit = tx[i]
    return pool.iloc[keep].reset_index(drop=True)


def _weighted_lift(subset):
    """lift وزنیِ یک زیرمجموعه با وزنِ تعدادِ معامله (شرطِ ۴)."""
    num = sum(m['lift'] * m['n'] for m in subset)
    den = sum(m['n'] for m in subset)
    return (num / den) if den > 0 else 0.0


def _z_proxy(subset):
    """
    نماینده (proxy) از z مهارتِ استخر: z ∝ lift·√n.
    این **جای‌گزینِ** compute_rqs2 نیست — فقط برای *انتخابِ* زیرمجموعه است.
    حکمِ نهایی همیشه با compute_rqs2 روی استخرِ واقعی داده می‌شود.
    z حاصل‌ضربِ «کیفیتِ لبه» (lift) و «توانِ آماری» (√n) است؛ ادغام n را
    بزرگ می‌کند ولی می‌تواند lift را کوچک کند، پس باید حاصل‌ضرب بیشینه شود.
    """
    n = sum(m['n'] for m in subset)
    return _weighted_lift(subset) * (n ** 0.5)


# حاشیهٔ معنادار برای پذیرشِ یک کارتِ اضافه (درسِ دومِ S351):
# z_proxy=lift·√n فرض می‌کند sd جای‌گشت ثابت می‌ماند، ولی وقتی نمونه از ۷۴
# به ۲۰۰۰ می‌رود مدلِ صفر و ساختارِ همبستگیِ معاملات کاملاً عوض می‌شود، پس
# proxy **بیش‌ازحد خوش‌بین** است. در S351، افزودنِ H1 فقط z_proxy را ۱.۷٪
# بالا برد (۱۲۰.۴→۱۲۲.۵) ولی z **واقعی** به ۱.۶ سقوط کرد. درس: یک بهبودِ
# ناچیزِ proxy ارزشِ ریسکِ فروپاشیِ ساختارِ نمونه را ندارد. پس کارتِ اضافه
# فقط وقتی پذیرفته می‌شود که z_proxy را **حداقل ۱۵٪** بالا ببرد.
POOL_ADD_MARGIN = 0.15


def choose_homogeneous_subset(candidates, add_margin=POOL_ADD_MARGIN):
    """
    از میانِ کارت‌های هم‌جهتِ مثبت، زیرمجموعه‌ای را برمی‌گزیند که نماینده z
    (lift·√n) را با **حاشیهٔ معنادار** بیشینه کند — شرطِ ۴ (همگنیِ قدرتِ لبه).

    راهبرد (حریصانه محافظه‌کار، از قوی‌ترین کارت): کارت‌ها را نزولی بر حسبِ
    lift مرتب می‌کنیم. کارتِ k فقط وقتی افزوده می‌شود که z_proxy را نسبت به
    بهترین زیرمجموعهٔ تاکنون **بیش از `add_margin`** (پیش‌فرض ۱۵٪) بالا ببرد.
    این محافظه‌کاری از درسِ دومِ S351 می‌آید: proxy فرض می‌کند sd جای‌گشت
    ثابت است، ولی بزرگ‌شدنِ نمونه آن را عوض می‌کند، پس فقط بهبودِ **معنادارِ**
    proxy ارزشِ ریسکِ ادغام را دارد؛ بهبودِ ناچیز (مثل ۱.۷٪ در S351) رد می‌شود.

    ورودی: candidates = [dict(card, lift>0, n, ...), ...]
    خروجی: dict(chosen=[...], rejected_for_dilution=[...], z_full, z_chosen,
                add_margin, trace=[...])  — همان اشیاءِ ورودی، بدونِ تغییر.
    """
    ordered = sorted(candidates, key=lambda m: m['lift'], reverse=True)
    best_k, best_z, trace = 0, -1.0, []
    for k in range(1, len(ordered) + 1):
        sub = ordered[:k]
        zk = _z_proxy(sub)
        # کارتِ اول همیشه پذیرفته می‌شود؛ کارت‌های بعد فقط با حاشیهٔ معنادار.
        threshold = best_z * (1.0 + add_margin) if best_k > 0 else -1.0
        accept = (zk > threshold)
        trace.append(dict(k=k, added=ordered[k - 1]['card'],
                          wlift=round(_weighted_lift(sub), 3),
                          n=sum(m['n'] for m in sub), z_proxy=round(zk, 3),
                          accepted=bool(accept)))
        if accept:
            best_z, best_k = zk, k
    chosen = ordered[:best_k]
    rejected = ordered[best_k:]
    z_full = _z_proxy(ordered) if ordered else 0.0
    return dict(chosen=chosen,
                rejected_for_dilution=rejected,
                z_full=round(z_full, 3),
                z_chosen=round(best_z, 3),
                add_margin=add_margin,
                trace=trace)


def pool_cards(members):
    """
    ادغامِ چند کارتِ هم‌جهت به یک استخرِ واحد.

    ورودی `members`: فهرستی از dict، هرکدام:
        dict(card=str, tr=DataFrame, dt=np.ndarray[datetime64], lift=float)
    که `tr` خروجیِ همان سازوکارِ لایه روی آن کارت است (ستون‌های لازم:
    direction, outcome/win, pnl_pip, entry_bar, exit_bar).

    قواعدِ اعتبار:
      • شرطِ ۲ (هم‌جهتی): هر عضوی که lift<=0 دارد **حذف** می‌شود.
      • شرطِ ۴ (همگنی): از میانِ اعضای هم‌جهت، فقط زیرمجموعه‌ای ادغام می‌شود
        که `choose_homogeneous_subset` بیشینه‌کنندهٔ z_proxy تشخیص دهد؛
        کارتی که lift>0 دارد ولی استخر را رقیق می‌کند در
        `dropped` با دلیلِ 'dilutes pool' علامت می‌خورد.

    خروجی: dict(pool=DataFrame, used=[...], dropped=[...], n_before, n_after,
                selection=<خروجیِ choose_homogeneous_subset>)
    یا None اگر هیچ عضوِ معتبری نماند.
    """
    # --- گامِ ۱: فیلترِ هم‌جهتی (شرطِ ۲) + آماده‌سازیِ نامزدها ---
    dropped, cand = [], []
    tr_by_card = {}
    for m in members:
        lift = m.get('lift')
        if lift is None or lift <= 0:
            dropped.append(dict(card=m['card'], lift=lift,
                                reason='lift<=0 (not co-directional)'))
            continue
        tr = m['tr']
        if tr is None or len(tr) == 0:
            dropped.append(dict(card=m['card'], lift=lift, reason='no trades'))
            continue
        tr_by_card[m['card']] = m
        cand.append(dict(card=m['card'], lift=float(lift), n=int(len(tr))))

    if not cand:
        return None

    # --- گامِ ۲: انتخابِ زیرمجموعهٔ همگن (شرطِ ۴) ---
    sel = choose_homogeneous_subset(cand)
    chosen_cards = {c['card'] for c in sel['chosen']}
    for c in sel['rejected_for_dilution']:
        dropped.append(dict(card=c['card'], lift=c['lift'],
                            reason='dilutes pool (lowers z_proxy)'))

    # --- گامِ ۳: ادغامِ فقط زیرمجموعهٔ برنده روی زمانِ تقویمی (شرطِ ۳) ---
    used, frames = [], []
    for c in sel['chosen']:
        m = tr_by_card[c['card']]
        cal = _to_calendar(m['tr'], m['dt'])
        cal['src_card'] = c['card']
        frames.append(cal)
        used.append(dict(card=c['card'], lift=c['lift'], n=int(len(m['tr']))))

    merged = pd.concat(frames, ignore_index=True)
    n_before = len(merged)
    pool = _fifo_calendar(merged)
    n_after = len(pool)
    return dict(pool=pool, used=used, dropped=dropped,
                n_before=n_before, n_after=n_after, selection=sel)
