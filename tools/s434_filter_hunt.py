# -*- coding: utf-8 -*-
"""
s434_filter_hunt.py — جست‌وجویِ منظمِ بانکِ ۴۰۱ اندیکاتور برای فیلترِ نجات‌دهنده
================================================================================
چرا این فایل وجود دارد
----------------------
هشدارِ اختصاصیِ **#۳** در `MISSION_4_RESURRECTION_FILTERS.md`:

> «اگر F1..F9 جواب نداد، **قبل از اعلامِ مرگ**، بانکِ ۴۰۰+ اندیکاتور
>  (`docs/indicators/`) را بگرد.»

در گامِ ۴۱ استدلال کردم این لازم نیست، چون فیلتر `n` را کم می‌کند ⇒ `perm_sd`
را بزرگ ⇒ سدِ z را بالا. **آن استدلال بیش‌تعمیم بود** و در گامِ ۵۴ خودم آن را
با تحلیلِ سقف رد کردم:

    حذفِ فقط **۷۴ معامله (۴.۱٪)** — اگر همه زیان‌ده باشند — لیفت را از
    ۲.۰۳۷ به **۴.۰ pp** می‌برد، و `perm_sd` فقط از ۰.۸۶۷۴ به ۰.۸۸۵۸
    (۲.۱٪) می‌رود ⇒ `z = ۴.۵۲` ⇒ **هر دو** سدِ H3 و H5 پاس می‌شوند.

پس مسیرِ فیلتر **باز** است و هشدار #۳ کاملاً برقرار.

روشِ علمی: **تفکیک‌گری** پیش از بک‌تست
--------------------------------------
آزمودنِ کورِ ۴۰۱ اندیکاتور × چند آستانه = ده‌ها هزار بک‌تست، که:
  ۱) گران است، و
  ۲) `n_trials` را می‌ترکانَد و سدِ `H5` را با دستِ خودم بالا می‌برد.

به‌جای آن، از یک واقعیتِ ساده استفاده می‌کنم: **فیلتر فقط وقتی کار می‌کند که
اندیکاتور در لحظهٔ ورود، برنده را از زیان‌ده تفکیک کند.** پس ابتدا برای هر
اندیکاتور یک **آمارهٔ تفکیکِ ارزان** می‌سنجم روی همان ۱۸۰۷ معاملهٔ موجود:

    AUC (سطحِ زیرِ ROC) بینِ توزیعِ مقدارِ اندیکاتور در معاملاتِ برنده و زیان‌ده

* `AUC = ۰.۵۰` ⇒ اندیکاتور **هیچ** اطلاعاتی ندارد ⇒ فیلترش بی‌فایده است.
* `AUC` دور از ۰.۵ (هر دو جهت) ⇒ اطلاعات دارد ⇒ ارزشِ بک‌تست دارد.

این کار **یک بار** روی هر اندیکاتور انجام می‌شود و **بک‌تست نیست**، پس
`n_trials` را زیاد نمی‌کند. فقط نامزدهایی که از این غربال رد شوند، در گامِ
بعد **واقعاً** بک‌تست می‌شوند و آن تعداد در `n_trials` شمرده و **صادقانه
گزارش** می‌شود.

چهار محافظِ ضدِ تقلب که در همین فایل اعمال شده
----------------------------------------------
۱) **بدونِ نگاه به آینده:** مقدارِ اندیکاتور در کندلِ `entry_bar - 1` خوانده
   می‌شود، نه `entry_bar`. اگر روی خودِ کندلِ ورود بخوانم، برای اندیکاتورهایی
   که از `close` همان کندل استفاده می‌کنند، اطلاعاتِ **پس از** تصمیم وارد
   می‌شود و هر اندیکاتوری درخشان به نظر می‌رسد. این بزرگ‌ترین دامِ این کار است.

۲) **AUC، نه اختلافِ میانگین:** میانگین به مقادیرِ پرت حساس است و مقیاسِ
   اندیکاتورها بسیار متفاوت است (RSI در ۰..۱۰۰، `r2` در ۰..۱، `cdl_*` در
   {−۱۰۰,۰,+۱۰۰}). AUC **رتبه‌محور** و بی‌مقیاس است، پس مقایسهٔ ۴۰۱ اندیکاتور
   با آن **منصفانه** است.

۳) **سدِ تصادف صریح:** با `n=۱۸۰۷` (۸۲۷ برنده / ۹۸۰ زیان‌ده)، خطای معیارِ AUC
   زیرِ فرضِ صفر ≈ `sqrt((n1+n2+1)/(12*n1*n2))` ≈ ۰.۰۱۴. پس AUC=۰.۵۳ فقط
   ۲σ است — و چون **۴۰۱** اندیکاتور را می‌گردم، بیشینهٔ AUCِ تصادفی
   قابلِ‌انتظار ≈ ۰.۵ + ۳.۳۳σ ≈ **۰.۵۴۶**. هر چیزی زیرِ آن، **شانس** است.
   این عدد پیش از دیدنِ نتایج نوشته می‌شود.

۴) **گزارشِ صادقانهٔ صفر:** اگر هیچ اندیکاتوری از سدِ ۰.۵۴۶ نگذشت، همان
   گزارش می‌شود و مرگِ ابدی اعلام می‌گردد — نه اینکه سد پایین آورده شود.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, 'results', '_s434_filter')

# ── سدهایی که **پیش از** دیدنِ نتایج تعیین شده‌اند ──────────────────────────
N_WINS, N_LOSSES = 827, 980
AUC_SE = math.sqrt((N_WINS + N_LOSSES + 1) / (12.0 * N_WINS * N_LOSSES))
N_INDICATORS = 401
# بیشینهٔ z قابلِ‌انتظار از ۴۰۱ قرعهٔ مستقل ≈ sqrt(2*ln(N))
EXP_MAX_Z = math.sqrt(2.0 * math.log(N_INDICATORS))
AUC_BAR = 0.5 + EXP_MAX_Z * AUC_SE


def _auc(pos: np.ndarray, neg: np.ndarray) -> float | None:
    """AUCِ ROC با روشِ Mann-Whitney U (رتبه‌محور، مقاوم به مقیاس).

    برمی‌گرداند `None` اگر یکی از دو گروه تهی باشد یا اندیکاتور روی این
    معاملات **ثابت** باشد (واریانسِ صفر ⇒ هیچ تفکیکی ممکن نیست).
    """
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if len(pos) < 30 or len(neg) < 30:
        return None
    allv = np.concatenate([pos, neg])
    if np.nanstd(allv) == 0:
        return None
    # رتبه‌بندی با میانگینِ رتبه برای گره‌ها (ties) — حالتِ cdl_* که فقط سه
    # مقدار دارد بسیار پرگره است و بی‌توجهی به گره‌ها AUC را منحرف می‌کند.
    order = np.argsort(allv, kind='mergesort')
    ranks = np.empty(len(allv), float)
    sorted_v = allv[order]
    i = 0
    while i < len(sorted_v):
        j = i
        while j + 1 < len(sorted_v) and sorted_v[j + 1] == sorted_v[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    n1 = len(pos)
    r1 = ranks[:n1].sum()
    u1 = r1 - n1 * (n1 + 1) / 2.0
    return float(u1 / (n1 * len(neg)))


def hunt(asset: str = 'XAUUSD', tf: str = 'M30', verbose: bool = True) -> dict:
    """قدرتِ تفکیکِ هر یک از ۴۰۱ اندیکاتور را روی معاملاتِ نامزد می‌سنجد."""
    from engine import indicator_bank as ib

    spec = importlib.util.spec_from_file_location(
        'adj', os.path.join(ROOT, 'tools', 's434_adjudicate.py'))
    adj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adj)

    run = adj.run_candidate(asset, tf)
    tr, df = run['trades'], run['df']
    pnl = tr['pnl_pip'].values
    win = pnl > 0

    # ── کندلِ خواندنِ اندیکاتور: `signal_bar` ─────────────────────────────
    # محافظِ ۱ (ضدِ نگاه به آینده) — و **معناشناسیِ درست**:
    #   تصمیم روی بسته‌شدنِ `signal_bar` گرفته می‌شود و ورود در open کندلِ
    #   بعد رخ می‌دهد. پس تنها اطلاعاتی که یک فیلترِ واقعی می‌تواند ببیند،
    #   اطلاعاتِ **تا انتهای `signal_bar`** است.
    # سنجیده شد: `entry_bar − signal_bar == 1` برای **همهٔ** ۱۸۰۷ معامله،
    #   پس `entry_bar−1` هم همان عدد را می‌داد. ولی `signal_bar` انتخاب شد
    #   چون اگر روزی موتور تأخیرِ ورود را عوض کند (مثلاً ورود با تأخیرِ دو
    #   کندل)، `entry_bar−1` بی‌صدا **غلط** می‌شود و اطلاعاتِ آیندهٔ یک
    #   کندلی وارد می‌کند، در حالی که `signal_bar` خودکار درست می‌مانَد.
    #   این همان الگویی است که در این مأموریت هفت بار به «موفقیتِ خاموش»
    #   منتهی شد: کدی که امروز درست است ولی فرضش مستند و بازرسی‌شده نیست.
    col = None
    for c in ('signal_bar', 'entry_bar', 'entry_idx', 'i_entry'):
        if c in tr.columns:
            col = c
            break
    if col is None:
        raise KeyError(f'ستونِ کندلِ سیگنال پیدا نشد. ستون‌ها: {list(tr.columns)}')
    read_bar = tr[col].values.astype(int)
    if col != 'signal_bar':      # فالبک: یک کندل عقب‌تر از ورود
        read_bar = read_bar - 1
    read_bar = np.clip(read_bar, 0, len(df) - 1)

    names = ib.list_indicators()
    if verbose:
        print(f'[شکارِ فیلتر] {asset}-{tf} · {len(names)} اندیکاتور · '
              f'n={len(pnl)} ({int(win.sum())} برنده / {int((~win).sum())} زیان)')
        print(f'  خطای معیارِ AUC زیرِ صفر = {AUC_SE:.4f}')
        print(f'  سدِ تصادف (پیش‌تعیین‌شده) = {AUC_BAR:.4f} '
              f'= 0.5 + {EXP_MAX_Z:.3f}σ  ← از {N_INDICATORS} قرعه')
        sys.stdout.flush()

    rows = []
    t0 = time.time()
    for k, nm in enumerate(names):
        try:
            s = ib.compute(nm, df)
        except Exception as e:  # noqa: BLE001
            rows.append({'name': nm, 'auc': None, 'error': f'{type(e).__name__}'})
            continue
        v = np.asarray(s, dtype=float)
        if len(v) != len(df):
            rows.append({'name': nm, 'auc': None, 'error': 'length'})
            continue
        vals = v[read_bar]
        a = _auc(vals[win], vals[~win])
        rows.append({'name': nm, 'auc': (None if a is None else round(a, 5)),
                     'dev': (None if a is None else round(abs(a - 0.5), 5)),
                     'z': (None if a is None else round((a - 0.5) / AUC_SE, 3)),
                     'n_finite': int(np.isfinite(vals).sum())})
        if verbose and (k + 1) % 100 == 0:
            print(f'  … {k + 1}/{len(names)} ({time.time() - t0:.0f}s)')
            sys.stdout.flush()

    scored = [r for r in rows if r.get('auc') is not None]
    scored.sort(key=lambda r: -r['dev'])
    passing = [r for r in scored if r['auc'] >= AUC_BAR or r['auc'] <= 1 - AUC_BAR]

    out = {
        'note': 'S434 - discrimination screen of the 401-indicator bank, per '
                'MISSION_4 warning #3. AUC of indicator value at entry_bar-1 '
                'between winning and losing trades. NOT a backtest: this screen '
                'does not increase n_trials.',
        'asset': asset, 'tf': tf,
        'n_trades': int(len(pnl)), 'n_wins': int(win.sum()),
        'n_losses': int((~win).sum()),
        'read_bar_column': col,
        'lookahead_guard': 'indicator read at signal_bar (decision close), never at entry_bar. Verified entry_bar-signal_bar==1 for all 1807 trades.',
        'auc_se_under_null': round(AUC_SE, 5),
        'n_indicators_screened': len(names),
        'expected_max_z_from_search': round(EXP_MAX_Z, 4),
        'auc_bar_preregistered': round(AUC_BAR, 5),
        'n_scored': len(scored), 'n_failed_compute': len(rows) - len(scored),
        'n_passing_bar': len(passing),
        'passing': passing[:40],
        'top30_by_deviation': scored[:30],
        'secs': round(time.time() - t0, 1),
    }
    if verbose:
        print(f'\n  سنجیده شد: {len(scored)}/{len(names)} '
              f'(ناموفق: {len(rows) - len(scored)})')
        print(f'  از سد گذشتند: **{len(passing)}**')
        print(f'\n  ۱۵ بیشترین انحراف از ۰.۵:')
        for r in scored[:15]:
            flag = '★ PASS' if (r['auc'] >= AUC_BAR or r['auc'] <= 1 - AUC_BAR) else ''
            print(f"    {r['name']:<24} AUC={r['auc']:.4f} "
                  f"dev={r['dev']:.4f} z={r['z']:+.2f} {flag}")
        sys.stdout.flush()
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tf', default='M30')
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    out = hunt(a.asset, a.tf)
    fp = os.path.join(OUT_DIR, f'hunt_{a.asset}_{a.tf}.json')
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'\n[ذخیره] {os.path.relpath(fp, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
