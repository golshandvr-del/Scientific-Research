"""
s434_null_model.py — ساختِ مدلِ صفرِ **سنجیده‌شده** برای نامزدِ قفل‌شدهٔ S434
================================================================================

مسئله‌ای که این فایل حل می‌کند
--------------------------------
داوریِ گامِ ۲۷ سه دروازه را **نامعلوم** برگرداند (`H3` توان، `H4` ضدِبرازش،
`H5` آزمونِ چندگانه) و خودِ موتور علت را نام برد:

    H3 UNKNOWN: no measured null model supplied
                — absence of a control is not evidence of skill

`compute_rqs2` آرگومانِ `null` می‌پذیرد و من ندادم. تلخ‌ترین پیامدش این بود که
`n_trials = 1296` را با دقت شمردم و تعهد دادم دست‌کاری نکنم، ولی آن صداقت
**هیچ اثری نداشت** چون بدونِ مدلِ صفر دروازه‌ای وجود نداشت که آن عدد را مصرف
کند. (پنجمین عضوِ خانوادهٔ «موفقیتِ خاموش» در این مأموریت.)

ساختارِ کانونیِ خواسته‌شده (از `engine/rqs2.py::null_from_s346`)
----------------------------------------------------------------
    {'long':  {'uncond_wr','perm_mean','perm_sd','perm_max','perm_k'},
     'short': {...}}

و `_side_null_ref` از آن‌ها **بیشینه** را برمی‌دارد نه میانگین، چون آزمون باید
محافظه‌کارانه باشد: مهارت فقط وقتی اثبات می‌شود که سیگنال از **سخت‌ترین**
رقیبِ بی‌مهارت هم بهتر باشد.

دو خطِ مبنا و تفاوتِ معناییِ آن‌ها
-----------------------------------
۱) **بی‌قید (`uncond_wr`)**: «اگر بی‌هیچ قانونی، در *هر* کندلِ واجد وارد شوم
   با همان SL/TP/hold، چند درصد برنده می‌شوم؟» — این خطِ مبنا **بایاسِ
   هندسه** را می‌گیرد. برای این لایه حیاتی است: نسبتِ TP/SL = ۳.۳۳ به‌تنهایی
   WR را پایین می‌آورد، و بدونِ این خطِ مبنا ممکن است WR = ۴۵.۷۷٪ «بد» به
   نظر برسد در حالی که برای این هندسه عالی است — یا برعکس.

۲) **جای‌گشتِ زمانی (`perm_*`)**: «اگر *همان تعداد* معامله را در زمان‌هایی
   *تصادفی* بزنم، چه توزیعی از WR می‌گیرم؟» — این خطِ مبنا **بایاسِ رانشِ
   بازار** را می‌گیرد. برای طلا که در ۱۵ سال صعودیِ قوی داشته، یک لایهٔ
   فقط-لانگ به‌طورِ خودکار سود می‌دهد؛ جای‌گشت همان رانش را به کنترل هم
   می‌دهد، پس هر برتری‌ای که بماند **متعلق به زمان‌بندی** است نه به روند.

سه تلهٔ طراحیِ کنترل که آگاهانه از آن‌ها پرهیز شده
---------------------------------------------------
۱) **تعدادِ جای‌گشت = تعدادِ لایهٔ نهایی (پس از فیلتر)، نه پایه.**
   لایهٔ من فیلترِ رژیم دارد و n را از ۳۲۴۵ به ۱۸۰۷ می‌رساند. اگر جای‌گشت را
   با ۳۲۴۵ بسازم، پراکندگیِ خطِ مبنا مصنوعاً **باریک** می‌شود (خطای استاندارد
   با √n کوچک می‌شود) و z من به‌غلط بزرگ می‌شود ⇒ یک پاسِ ارزان. این دقیقاً
   همان تله‌ای است که docstringِ `s346_null` هشدار می‌دهد و مسیرِ من از آن
   عبور می‌کند.

۲) **کنترل همان هندسه و همان `max_hold` و همان `allow_overlap` را دارد.**
   اگر کنترل بدونِ تریلینگ اجرا شود ولی سیگنال با تریلینگ، آن‌گاه z تفاوتِ
   *مدیریتِ معامله* را می‌سنجد نه تفاوتِ *انتخابِ زمان*. برای اینکه ادعای
   «S139 در انتخابِ زمان مهارت دارد» آزمون‌پذیر باشد، کنترل باید **از هر
   جهت جز زمانِ ورود** یکسان باشد.

۳) **جای‌گشت از میانِ کندل‌های «واجد» انتخاب می‌شود، نه هر کندل.**
   کندل‌های ابتداییِ warmup و هر کندلی که نمی‌تواند معاملهٔ کامل تولید کند
   باید از استخرِ تصادفی حذف شوند، وگرنه کنترل مصنوعاً ضعیف می‌شود و
   برتریِ من متعلق به «حذفِ کندل‌های بی‌ربط» خواهد بود نه به لایه.

نکتهٔ صداقتی
-------------
این فایل **می‌تواند** حکم را به REJECT ببرد: اگر `uncond_wr` نزدیکِ ۴۵.۷۷٪
باشد، یعنی ساعتِ ۲۲/۲۳ هیچ مهارتی ندارد و کلِ نتیجه محصولِ هندسهٔ TP/SL است.
این را پیش از اجرا می‌نویسم تا اگر چنین شد، بازتفسیر نکنم.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, 'results', '_s434_null')

# تعدادِ جای‌گشت. ۲۰ همان مقداری است که `s346_null` استفاده می‌کند و برای
# برآوردِ میانگین کافی است؛ برای `perm_max` سخاوتمندانه‌تر (=محافظه‌کارانه‌تر)
# می‌شود اگر بیشتر باشد، پس ۴۰ می‌گیریم: خطِ مبنا **سخت‌تر** می‌شود نه آسان‌تر.
N_PERM = 40
SEED = 7


def _wr_of(trades) -> float | None:
    """نرخِ بردِ یک مجموعهٔ معامله بر حسبِ درصد."""
    if trades is None or len(trades) == 0:
        return None
    pnl = trades['pnl_pip'].values
    return float(100.0 * (pnl > 0).sum() / len(pnl))


def build_null(asset: str, tf: str, n_perm: int = N_PERM, seed: int = SEED,
               verbose: bool = True) -> dict:
    """مدلِ صفرِ کانونی برای نامزدِ قفل‌شده روی یک کارت.

    خروجی: dict با کلیدهای `long` و `short` مطابقِ ساختارِ کانونیِ RQS2.
    """
    import importlib.util
    import tools.s434_fast_data as fd
    from engine import scalp_engine as se

    spec = importlib.util.spec_from_file_location(
        'adj', os.path.join(ROOT, 'tools', 's434_adjudicate.py'))
    adj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adj)

    # ── هندسه و ماسکِ لایه: عیناً از خودِ داور گرفته می‌شود ──────────────
    # نه بازنویسی. اگر اینجا هندسه را دوباره حساب کنم و ذره‌ای واگرا شود،
    # کنترل به لایهٔ **دیگری** تعلق می‌گیرد و z بی‌معنا می‌شود.
    run = adj.run_candidate(asset, tf)
    d, df = run['d'], run['df']
    sl, tp, mh = run['sl'], run['tp'], run['max_hold']
    sig_n = int(run['n_signals'])
    n_final = int(len(run['trades']))
    n = len(df)
    z = np.zeros(n, bool)

    if verbose:
        print(f'[{asset}-{tf}] هندسه: SL={sl:.1f} TP={tp:.1f} hold={mh} '
              f'| سیگنال={sig_n} معاملهٔ نهایی={n_final}')

    # ── استخرِ کندل‌های «واجد» ───────────────────────────────────────────
    # تلهٔ ۳: جای‌گشت باید فقط از کندل‌هایی انتخاب شود که **می‌توانند** یک
    # معاملهٔ کامل بسازند. کندل‌های انتهایی جا برای max_hold ندارند و
    # کندل‌های ابتدایی برای گرم‌شدنِ رژیم لازم‌اند. اگر آن‌ها را در استخر
    # بگذارم، کنترل مصنوعاً ضعیف می‌شود و برتریِ من متعلق به «حذفِ کندلِ
    # بی‌ربط» خواهد بود نه به انتخابِ زمانِ S139.
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True

    # ── خطِ مبنای ۱: بی‌قید (هر کندلِ واجد) ──────────────────────────────
    # ⚠️ allow_overlap=True اینجا **اجباری** است: با False موتور پس از هر
    # ورود تا خروج قفل می‌شود، پس «ورود در هر کندل» عملاً به «ورود در هر
    # mh کندل» تبدیل می‌شود و آنچه می‌سنجیم دیگر بی‌قید نیست. این تنها
    # جایی است که کنترل آگاهانه از سیگنال متفاوت است، و دلیلش معناییست:
    # تعریفِ «بی‌قید» بدونِ همپوشانی قابلِ بیان نیست.
    tr_unc = se.simulate_trades(df, valid, z, sl, tp, asset,
                                max_hold=mh, allow_overlap=True, trail_pip=None)
    wr_unc = _wr_of(tr_unc)
    if verbose:
        print(f'  خطِ مبنا ۱ (بی‌قید): n={0 if tr_unc is None else len(tr_unc):,} '
              f'WR={wr_unc:.3f}%' if wr_unc is not None else '  بی‌قید: تهی')

    # ── خطِ مبنای ۲: جای‌گشتِ زمانی ──────────────────────────────────────
    # تلهٔ ۱: k = تعدادِ **سیگنالِ نهایی** (پس از فیلترِ رژیم)، نه پایه.
    # تلهٔ ۲: همان sl/tp/mh/overlap/trail سیگنال — تنها تفاوت، *زمان*.
    rng = np.random.default_rng(seed)
    vidx = np.flatnonzero(valid)
    k = min(sig_n, len(vidx))
    perm_wrs: list[float] = []
    for i in range(n_perm):
        pick = rng.choice(vidx, size=k, replace=False)
        pm = np.zeros(n, bool)
        pm[pick] = True
        # تلهٔ ۲ کاملاً بسته: `trail` **و** `be_trigger` هر دو از سیگنال
        # می‌آیند. (BUG-NULLTRAIL: تا گامِ ۳۴ این کلیدها در خروجیِ داور
        # نبودند و None می‌گرفتند ⇒ کنترل بی‌تریلینگ ⇒ z متورم.)
        tr_p = se.simulate_trades(df, pm, z, sl, tp, asset, max_hold=mh,
                                  allow_overlap=False,
                                  be_trigger_pip=run['be_trigger'],
                                  trail_pip=run['trail'])
        w = _wr_of(tr_p)
        if w is not None:
            perm_wrs.append(w)
        if verbose and (i + 1) % 10 == 0:
            print(f'  جای‌گشت {i + 1}/{n_perm} …')
            sys.stdout.flush()

    pa = np.array(perm_wrs, float) if perm_wrs else np.array([])
    long_null = dict(
        uncond_wr=wr_unc,
        perm_mean=float(pa.mean()) if pa.size else None,
        perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
        perm_max=float(pa.max()) if pa.size else None,
        perm_k=int(k),
    )
    # سمتِ شورت تهی است چون لایه فقط-لانگ است. `blend_null` با وزنِ تعدادِ
    # معاملهٔ هر سمت ترکیب می‌کند، پس سمتِ بی‌معامله وزنِ صفر می‌گیرد.
    return {'long': long_null, 'short': {},
            '_meta': {'asset': asset, 'tf': tf, 'n_perm': int(pa.size),
                      'n_signals': sig_n, 'n_final_trades': n_final,
                      'perm_k': int(k), 'n_valid_pool': int(valid.sum()),
                      'sl_pip': sl, 'tp_pip': tp, 'max_hold': mh,
                      'perm_wrs': [round(x, 4) for x in perm_wrs]}}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tfs', default='M30')
    ap.add_argument('--nperm', type=int, default=N_PERM)
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            nd = build_null(a.asset, tf, n_perm=a.nperm)
        except Exception as e:  # noqa: BLE001
            print(f'!! {a.asset}-{tf}: {type(e).__name__}: {e}')
            sys.stdout.flush()
            continue
        # 🔒 قانونِ سوم: هر کارت فوراً ذخیره می‌شود.
        fp = os.path.join(OUT_DIR, f'null_{a.asset}_{tf}.json')
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(nd, f, ensure_ascii=False, indent=1)
        L, M = nd['long'], nd['_meta']
        print(f'\n═══ مدلِ صفر {a.asset}-{tf} ═══')
        print(f'  بی‌قید WR      = {L["uncond_wr"]}')
        print(f'  جای‌گشت میانگین = {L["perm_mean"]}  sd={L["perm_sd"]}')
        print(f'  جای‌گشت بیشینه  = {L["perm_max"]}  (k={L["perm_k"]}, '
              f'{M["n_perm"]} تکرار)')
        ref = max(x for x in (L['uncond_wr'], L['perm_mean']) if x is not None)
        print(f'  ⇒ خطِ مبنای مؤثر (بیشینه) = {ref:.3f}%')
        sys.stdout.flush()
    print('\n[done]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
