"""
s434_mtf_skill_scan.py — اسکنِ **مهارتِ واقعی** لایهٔ S139 روی همهٔ کارت‌ها
================================================================================

چرا این ابزار وجود دارد
--------------------------------------------------------------------------------
گامِ ۴۱ ثابت کرد سدِ بحرانی `H3` است و فاصله +۱.۹۶pp لیفت است، و اینکه
**فیلترِ بیشتر جواب نمی‌دهد** چون `n` را کم می‌کند، `perm_sd` را بزرگ می‌کند
و سدِ `z` را بالا می‌برد بدون آنکه سدِ لیفت را نرم کند.

پس تنها راهِ باقی‌مانده که قانونِ «مرگِ ابدی» **الزام** می‌کند بیازمایم، این
است: **قانونِ MTF**. مهارتِ یک اثرِ زمان‌محور در تایم‌فریم‌های مختلف یکسان
نیست، چون هرچه کندل ریزتر باشد «ساعتِ ۲۲» به پنجرهٔ زمانیِ دقیق‌تری اشاره
می‌کند. ممکن است کارتی وجود داشته باشد که لیفتش **طبیعتاً** بالای ۴pp است.

و انگیزهٔ دوم: هدیهٔ دادهٔ کاربر **شش کارتِ کاملاً نو** آورد — M3, M4, M6,
M10, M12, M20 — که هیچ‌گاه در تاریخِ پروژه آزموده نشده‌اند.

--------------------------------------------------------------------------------
⭐ چرا **لیفت** می‌سنجم و نه WRِ خام
--------------------------------------------------------------------------------
درسِ گرانِ گام‌های ۳۶–۳۸: WRِ خام بی‌معناست چون هندسهٔ TP/SL و رانشِ ۱۵سالهٔ
طلا خودشان WR تولید می‌کنند. کارتی با WR=۵۰٪ ممکن است لیفتِ **منفی** داشته
باشد اگر خطِ مبنایش ۵۲٪ باشد. پس این اسکنر برای **هر کارت** شاهدِ خودش را
می‌سازد و فقط تفاضل را گزارش می‌کند.

--------------------------------------------------------------------------------
سه انتخابِ طراحی که آگاهانه‌اند
--------------------------------------------------------------------------------
۱. **جای‌گشتِ کم (۱۲ به‌جای ۴۰)**: این ابزار **غربال** است نه داور. هدف
   یافتنِ کارت‌های امیدبخش است، و برای برآوردِ `perm_mean` دوازده تکرار کافی
   است (خطای استاندارد ≈ sd/√12 ≈ ۰.۲۵pp). هر کارتی که رد شود، با مدلِ صفرِ
   کاملِ ۴۰تایی و داورِ RQS2 دوباره سنجیده می‌شود. **هیچ حکمی از این فایل
   صادر نمی‌شود.**

۲. **هندسهٔ نامزدِ قفل‌شده، بدونِ تغییر**: همان SL/TP/تریلینگ/رژیمِ گامِ ۲۴.
   اگر اینجا هندسه را هم بهینه کنم، `n_trials` منفجر می‌شود و سدِ `H5` را
   خودم بالا می‌برم — دقیقاً همان تلهٔ mass-search که RQS2 برایش ساخته شده.

۳. **پایه هم گزارش می‌شود**: برای هر کارت دو ردیف — لایهٔ کامل (با فیلترِ
   رژیم) و پایهٔ برهنه (فقط ساعت). چون گامِ ۴۱ نشان داد فیلتر می‌تواند لیفت
   را بالا ببرد ولی سدِ z را هم بالا ببرد، پس باید ببینم آیا کارتی هست که
   **بی‌فیلتر** هم لیفتِ بالا داشته باشد — آن حالتِ ایده‌آل است.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, 'results', '_s434_mtf')

# ترتیبِ کارت‌ها: از درشت به ریز **نه** — از M1 شروع می‌کنیم چون قانونِ MTF
# پروژه صریحاً می‌گوید «از xauusd و m1 شروع کن». ولی M1 گران‌ترین است، پس
# پس از آن به ترتیبِ صعودیِ هزینه می‌رویم تا اگر سندباکس ریست شد، بیشترین
# تعدادِ کارت ذخیره شده باشد.
TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1']
# W1/MN1 حذف شدند: هیچ کندلی با ساعتِ ۲۲/۲۳ ندارند ⇒ صفر سیگنال. این یک
# مرزِ **ساختاری** است که در گامِ ۱۳ کشف و مستند شد، نه یک شکست.

N_PERM_SCREEN = 12
SEED = 7


def _load_adj():
    """داورِ گامِ ۲۵ را به‌عنوان **تنها منبعِ** هندسه و ماسکِ رژیم بار می‌کند.

    بازنویسی نمی‌کنم: اگر تعریفِ رژیم اینجا ذره‌ای واگرا شود، اسکن به لایهٔ
    **دیگری** تعلق می‌گیرد و مقایسه با حکمِ M30 بی‌معنا می‌شود. همان اصلی که
    در گامِ ۳۴ باعثِ کشفِ BUG-NULLTRAIL شد.
    """
    spec = importlib.util.spec_from_file_location(
        'adj', os.path.join(ROOT, 'tools', 's434_adjudicate.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _wr(tr):
    if tr is None or len(tr) == 0:
        return None
    p = tr['pnl_pip'].values
    return float(100.0 * (p > 0).sum() / len(p))


def scan_card(adj, asset: str, tf: str, n_perm: int = N_PERM_SCREEN,
              seed: int = SEED, verbose: bool = True) -> dict | None:
    """لیفتِ لایه و پایه را روی یک کارت، هر یک نسبت به شاهدِ **خودِ کارت**."""
    import tools.s434_fast_data as fd
    from engine import scalp_engine as se

    t0 = time.time()
    try:
        run = adj.run_candidate(asset, tf)
    except FileNotFoundError:
        if verbose:
            print(f'  [{tf}] فایلِ داده نیست — رد')
        return None
    d, df = run['d'], run['df']
    sl, tp, mh = run['sl'], run['tp'], run['max_hold']
    tl, be = run['trail'], run['be_trigger']
    n = len(df)
    z = np.zeros(n, bool)

    tr_layer = run['trades']
    n_layer = 0 if tr_layer is None else len(tr_layer)
    if n_layer < 30:
        if verbose:
            print(f'  [{tf}] n={n_layer} < 30 — بی‌معنا برای سنجشِ مهارت')
        return {'tf': tf, 'n_bars': d['n_bars'], 'n_layer': n_layer,
                'skipped': 'n<30'}

    # ── پایهٔ برهنه (فقط ساعت، بدونِ فیلترِ رژیم) ─────────────────────────
    base_sig = fd.session_open_signal(d, (22, 23), 'SESSION_OPEN')
    tr_base = se.simulate_trades(df, base_sig, z, sl, tp, asset, max_hold=mh,
                                 allow_overlap=False, be_trigger_pip=be,
                                 trail_pip=tl)
    n_base = 0 if tr_base is None else len(tr_base)

    # ── شاهد: جای‌گشتِ زمانی با **همان** تعدادِ سیگنالِ هر بازو ────────────
    # تلهٔ ۱ (گامِ ۳۳): k باید تعدادِ سیگنالِ **همان بازو** باشد. لایه و پایه
    # k متفاوت دارند، پس هر یک شاهدِ جداگانه لازم دارد — استفاده از یک شاهدِ
    # مشترک، بازوی کم‌سیگنال‌تر را به‌غلط قوی نشان می‌دهد.
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)

    def perm_ref(k_sig: int) -> tuple[float | None, float | None]:
        if k_sig <= 0 or len(vidx) == 0:
            return None, None
        rng = np.random.default_rng(seed)
        k = min(int(k_sig), len(vidx))
        ws = []
        for _ in range(n_perm):
            pick = rng.choice(vidx, size=k, replace=False)
            pm = np.zeros(n, bool)
            pm[pick] = True
            tp_ = se.simulate_trades(df, pm, z, sl, tp, asset, max_hold=mh,
                                     allow_overlap=False, be_trigger_pip=be,
                                     trail_pip=tl)
            w = _wr(tp_)
            if w is not None:
                ws.append(w)
        if not ws:
            return None, None
        a = np.array(ws, float)
        return float(a.mean()), (float(a.std(ddof=1)) if a.size > 1 else None)

    # ── خطِ مبنای بی‌قید: **مشترک** است (به k وابسته نیست) ────────────────
    # (با تریلینگ و BE — درسِ BUG-NULLUNCOND در گامِ ۳۷.)
    tr_unc = se.simulate_trades(df, valid, z, sl, tp, asset, max_hold=mh,
                                allow_overlap=True, be_trigger_pip=be,
                                trail_pip=tl)
    wr_unc = _wr(tr_unc)

    wr_layer, wr_base = _wr(tr_layer), _wr(tr_base)
    pm_layer, sd_layer = perm_ref(int(run['n_signals']))
    pm_base, sd_base = perm_ref(int(base_sig.sum()))

    def lift_of(wr_arm, pm, sd):
        if wr_arm is None:
            return None, None, None
        refs = [x for x in (wr_unc, pm) if x is not None]
        if not refs:
            return None, None, None
        ref = max(refs)                       # محافظه‌کارانه: سخت‌ترین شاهد
        lift = wr_arm - ref
        zz = (lift / sd) if (sd and sd > 0) else None
        return round(ref, 3), round(lift, 3), (round(zz, 3) if zz else None)

    ref_l, lift_l, z_l = lift_of(wr_layer, pm_layer, sd_layer)
    ref_b, lift_b, z_b = lift_of(wr_base, pm_base, sd_base)

    out = {
        'tf': tf, 'n_bars': int(d['n_bars']), 'span_years': d['span_years'],
        'sl_pip': sl, 'tp_pip': tp, 'max_hold': mh,
        'uncond_wr': None if wr_unc is None else round(wr_unc, 3),
        'layer': {'n': int(n_layer),
                  'wr': None if wr_layer is None else round(wr_layer, 3),
                  'perm_mean': None if pm_layer is None else round(pm_layer, 3),
                  'perm_sd': None if sd_layer is None else round(sd_layer, 4),
                  'null_ref': ref_l, 'lift_pp': lift_l, 'z': z_l},
        'base': {'n': int(n_base),
                 'wr': None if wr_base is None else round(wr_base, 3),
                 'perm_mean': None if pm_base is None else round(pm_base, 3),
                 'perm_sd': None if sd_base is None else round(sd_base, 4),
                 'null_ref': ref_b, 'lift_pp': lift_b, 'z': z_b},
        'secs': round(time.time() - t0, 1),
    }
    if verbose:
        L, B = out['layer'], out['base']
        print(f'  [{tf:>3}] {d["n_bars"]:>9,}bar | '
              f'layer n={L["n"]:>5} wr={L["wr"]} lift={L["lift_pp"]} z={L["z"]} | '
              f'base n={B["n"]:>5} lift={B["lift_pp"]} z={B["z"]} '
              f'| unc={out["uncond_wr"]} ({out["secs"]}s)')
        sys.stdout.flush()
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tfs', default=','.join(TF_ORDER))
    ap.add_argument('--nperm', type=int, default=N_PERM_SCREEN)
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    adj = _load_adj()
    tfs = [t.strip() for t in a.tfs.split(',') if t.strip()]
    print(f'[اسکنِ مهارتِ MTF] {a.asset} · {len(tfs)} کارت · '
          f'{a.nperm} جای‌گشت/بازو')
    print(f'  سدِ H3: lift ≥ 4.0pp و z ≥ 3.09 | سدِ H5 (1296 آزمون): z ≥ 3.33')
    sys.stdout.flush()

    for tf in tfs:
        try:
            r = scan_card(adj, a.asset, tf, n_perm=a.nperm)
        except Exception as e:  # noqa: BLE001
            print(f'  !! [{tf}] {type(e).__name__}: {e}')
            sys.stdout.flush()
            continue
        if r is None:
            continue
        # 🔒 قانونِ سوم (اندک اندک): هر کارت **فوراً** ذخیره می‌شود.
        fp = os.path.join(OUT_DIR, f'skill_{a.asset}_{tf}.json')
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
    print('[done]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
