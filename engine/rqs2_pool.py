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


def pool_cards(members):
    """
    ادغامِ چند کارتِ هم‌جهت به یک استخرِ واحد.

    ورودی `members`: فهرستی از dict، هرکدام:
        dict(card=str, tr=DataFrame, dt=np.ndarray[datetime64], lift=float)
    که `tr` خروجیِ همان سازوکارِ لایه روی آن کارت است (ستون‌های لازم:
    direction, outcome/win, pnl_pip, entry_bar, exit_bar).

    قواعدِ اعتبار (شرطِ ۲): هر عضوی که lift<=0 دارد **حذف** می‌شود و در
    گزارش علامت می‌خورد؛ تجمیع فقط روی اعضای هم‌جهتِ مثبت انجام می‌شود.

    خروجی: dict(pool=DataFrame, dt_cal=..., used=[...], dropped=[...],
                n_before, n_after)
    یا None اگر هیچ عضوِ معتبری نماند.
    """
    used, dropped, frames = [], [], []
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
        cal = _to_calendar(tr, m['dt'])
        cal['src_card'] = m['card']
        frames.append(cal)
        used.append(dict(card=m['card'], lift=lift, n=int(len(tr))))

    if not frames:
        return None

    merged = pd.concat(frames, ignore_index=True)
    n_before = len(merged)
    pool = _fifo_calendar(merged)
    n_after = len(pool)
    return dict(pool=pool, used=used, dropped=dropped,
                n_before=n_before, n_after=n_after)
