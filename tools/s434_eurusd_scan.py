"""
s434_eurusd_scan.py — انتقالِ لایهٔ S139 به **EURUSD** با ترجمهٔ نوسان‌محور
================================================================================

چرا این فایل وجود دارد
----------------------
قانونِ MTF پروژه می‌گوید هر لایه روی **هر دو جفت‌ارز** آزموده شود، و
«سودِ خالص» رسماً جمعِ سودِ XAUUSD و EURUSD است. تا گامِ ۴۹ تنها طلا
آزموده شده بود: هر ۱۹ تایم‌فریم (۱۲ سنجیده + ۷ ساختاراً ناممکن). یورو
آخرین مسیرِ باقی‌ماندهٔ **قانونِ مرگِ ابدی** است و باید آزموده شود پیش از
آنکه S139 سوخته اعلام شود.

خطای مرگ‌باری که اینجا در کمین است
----------------------------------
انتقالِ ساده یعنی استفاده از **همان اعدادِ pip**: SL=۲۰۵.۵ و TP=۶۸۵.۰.
این برای یورو بی‌معنا است و **اشتباهِ رایجِ ۶** (TP/SL یکسان برای همه) را
در بدترین شکلش مرتکب می‌شود. سنجیده شد نه فرض:

    XAUUSD دامنهٔ روزانهٔ میانه = ۱٬۹۹۳ pip
    EURUSD دامنهٔ روزانهٔ میانه =    ۷۹.۷ pip      ⇒ نسبت ۲۵.۰×

پس SL=۲۰۵.۵ pip روی طلا = **۰.۱۰۳ × دامنهٔ روزانه**، در حالی که همان
۲۰۵.۵ pip روی یورو = **۲.۵۸ × دامنهٔ روزانه** — یعنی استاپی که تقریباً
هرگز فعال نمی‌شود و TP ای که تقریباً هرگز نمی‌رسد. آن آزمون، لایهٔ S139
را نمی‌سنجید؛ چیزِ دیگری را می‌سنجید و نتیجه‌اش (هر چه بود) بی‌ارزش بود.

ترجمهٔ درست: **حفظِ نسبتِ نوسانی**
-----------------------------------
کمیتِ معنادار «چند برابرِ نوسانِ دارایی» است، نه «چند pip». پس:

    SL_eur = SL_xau × (dailyRange_eur / dailyRange_xau)
           = ۲۰۵.۵ × (۷۹.۷ / ۱۹۹۳) ≈ ۸.۲ pip
    TP_eur = SL_eur × ۳.۳۳۳۳          ≈ ۲۷.۴ pip

نسبتِ مقدسِ TP/SL = ۳.۳۳۳۳ **دست‌نخورده** می‌مانَد: تعهدِ گامِ ۲۴ که
برای زیبا کردنِ WR هندسه را عوض نمی‌کنم، به یورو هم تعمیم دارد. اگر
اینجا TP را کوچک می‌کردم، WR بالا می‌رفت و **اشتباهِ رایجِ ۸** بود.

هزینه: تلهٔ پنهانی که یورو دارد و طلا نداشت
--------------------------------------------
اسپردِ یورو ۱.۰ pip است و SL ما ~۸.۲ pip ⇒ هزینه **۱۲.۲٪ فاصلهٔ استاپ**.
روی طلا اسپرد ۳۳ point در برابر SL=۲۰۵۵ point ⇒ فقط **۱.۶٪**. یعنی
لایه روی یورو هفت‌برابر گران‌تر است و این پیش از هر محاسبه‌ای، انتظار را
پایین می‌آورد. این را **پیش‌ثبت** می‌کنم: اگر یورو شکست خورد، بخشی از
علت همین است و نباید آن را به‌حسابِ «نبودِ اثرِ شبانه» بگذارم بی‌آنکه
هزینه را جدا بسنجم.

پیش‌ثبتِ انتظار (پیش از اجرا)
------------------------------
اثرِ «رانشِ شبانه» در ادبیات به **بازگشاییِ نشستِ آسیا** نسبت داده
می‌شود، و آسیا بازارِ اصلیِ طلا است نه یورو (یورو در نشستِ لندن/نیویورک
فعال است). پس پیش‌بینیِ من: لیفتِ یورو **کمتر** از طلا خواهد بود،
احتمالاً زیرِ ۱.۵pp. اگر برعکس شد و یورو **بیشتر** داد، آن یافتهٔ
مهمی است که فرضِ مکانیزمِ من را رد می‌کند و باید گزارش شود.

هیچ حکمی از این فایل صادر نمی‌شود
----------------------------------
این یک **غربال** است با ۱۲ جای‌گشت. هر کارتِ امیدبخش با مدلِ صفرِ کاملِ
۴۰ جای‌گشتی و داورِ RQS2 v2.6 دوباره سنجیده می‌شود.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_DIR = os.path.join(ROOT, 'results', '_s434_eur')

# هندسهٔ مرجعِ طلا (قفل‌شده در گامِ ۲۴)
XAU_SL = 205.5
XAU_TP = 685.0
RATIO = XAU_TP / XAU_SL          # ۳.۳۳۳۳ — دست‌نخورده می‌مانَد
XAU_DAILY_PIP = 1993.0           # میانهٔ سنجیده‌شده روی M30 (۴٬۰۰۵ روز)

N_PERM_SCREEN = 12
SEED = 7


def eur_geometry(tf: str = 'M30') -> tuple[float, float, float]:
    """هندسهٔ یورو را با **حفظِ نسبتِ نوسانی** از هندسهٔ طلا می‌سازد.

    برمی‌گرداند ``(sl_pip, tp_pip, daily_range_pip)``.

    دامنهٔ روزانه **از خودِ دادهٔ یورو** سنجیده می‌شود، نه از یک عددِ
    سخت‌کدشده؛ چون اگر روزی فایلِ داده عوض شود، عددِ سخت‌کدشده بی‌سروصدا
    غلط می‌شود و هیچ خطایی نمی‌دهد — همان خانوادهٔ «موفقیتِ خاموش».
    """
    import tools.s434_fast_data as fd
    src = fd.resolve('EURUSD', tf)
    df = pd.read_csv(src)
    t = pd.to_datetime(df['time'], unit='s')
    g = df.groupby(t.dt.floor('D').values).agg(hi=('high', 'max'),
                                               lo=('low', 'min'))
    daily = float(((g['hi'] - g['lo']) / 0.0001).median())
    sl = round(XAU_SL * (daily / XAU_DAILY_PIP), 2)
    tp = round(sl * RATIO, 2)
    return sl, tp, daily


def _wr(tr):
    if tr is None or len(tr) == 0:
        return None
    p = tr['pnl_pip'].values
    return float(100.0 * (p > 0).sum() / len(p))


def scan_eur_card(adj, tf: str, sl: float, tp: float,
                  n_perm: int = N_PERM_SCREEN, seed: int = SEED) -> dict | None:
    """لایهٔ S139 روی یک کارتِ یورو، با شاهدِ خودِ همان کارت."""
    import tools.s434_fast_data as fd
    from engine import scalp_engine as se

    t0 = time.time()
    try:
        d = fd.load_fast('EURUSD', tf)
    except FileNotFoundError:
        print(f'  [{tf}] فایلِ داده نیست — رد')
        return None
    df = fd.as_dataframe(d)
    n = len(df)
    z = np.zeros(n, bool)
    mh = fd.hold_bars_for(tf, 24.0)
    tl = round(130.0 * (sl / XAU_SL), 2)      # تریلینگ هم نوسان‌محور ترجمه شد
    be = None

    # ── سیگنال: عیناً همان معناشناسیِ SESSION_OPEN و همان ساعت‌ها ─────────
    base_sig = fd.session_open_signal(d, (22, 23), 'SESSION_OPEN')
    reg = adj.regime_mask(d, 'mom', 13, tf)
    sig = base_sig & reg

    tr_layer = se.simulate_trades(df, sig, z, sl, tp, 'EURUSD', max_hold=mh,
                                  allow_overlap=False, be_trigger_pip=be,
                                  trail_pip=tl)
    tr_base = se.simulate_trades(df, base_sig, z, sl, tp, 'EURUSD',
                                 max_hold=mh, allow_overlap=False,
                                 be_trigger_pip=be, trail_pip=tl)
    n_layer = 0 if tr_layer is None else len(tr_layer)
    if n_layer < 30:
        print(f'  [{tf}] n={n_layer} < 30 — بی‌معنا')
        return {'tf': tf, 'n_layer': n_layer, 'skipped': 'n<30'}

    # ── استخرِ واجد + شاهدها (همان سه تلهٔ گامِ ۳۳ رعایت شده) ─────────────
    valid = np.zeros(n, bool)
    valid[250:n - mh - 1] = True
    vidx = np.flatnonzero(valid)

    UNC_CAP = 50_000                          # درسِ گامِ ۴۶
    unc_mask = valid
    if int(valid.sum()) > UNC_CAP:
        rng_u = np.random.default_rng(seed + 101)
        pick = rng_u.choice(vidx, size=UNC_CAP, replace=False)
        unc_mask = np.zeros(n, bool)
        unc_mask[pick] = True
    tr_unc = se.simulate_trades(df, unc_mask, z, sl, tp, 'EURUSD', max_hold=mh,
                                allow_overlap=True, be_trigger_pip=be,
                                trail_pip=tl)          # ← درسِ BUG-NULLUNCOND
    wr_unc = _wr(tr_unc)

    def perm_ref(k_sig: int):
        if k_sig <= 0:
            return None, None
        rng = np.random.default_rng(seed)
        k = min(int(k_sig), len(vidx))
        ws = []
        for _ in range(n_perm):
            pm = np.zeros(n, bool)
            pm[rng.choice(vidx, size=k, replace=False)] = True
            w = _wr(se.simulate_trades(df, pm, z, sl, tp, 'EURUSD',
                                       max_hold=mh, allow_overlap=False,
                                       be_trigger_pip=be, trail_pip=tl))
            if w is not None:
                ws.append(w)
        if not ws:
            return None, None
        a = np.array(ws, float)
        return float(a.mean()), (float(a.std(ddof=1)) if a.size > 1 else None)

    pm_l, sd_l = perm_ref(int(sig.sum()))
    pm_b, sd_b = perm_ref(int(base_sig.sum()))

    def lift_of(wr_arm, pm, sd):
        if wr_arm is None:
            return None, None, None
        refs = [x for x in (wr_unc, pm) if x is not None]
        if not refs:
            return None, None, None
        ref = max(refs)                       # محافظه‌کارانه
        lift = wr_arm - ref
        zz = (lift / sd) if (sd and sd > 0) else None
        return round(ref, 3), round(lift, 3), (round(zz, 3) if zz else None)

    wr_l, wr_b = _wr(tr_layer), _wr(tr_base)
    ref_l, lift_l, z_l = lift_of(wr_l, pm_l, sd_l)
    ref_b, lift_b, z_b = lift_of(wr_b, pm_b, sd_b)

    # ── هزینه: پیش‌ثبتِ گامِ ۵۰ می‌گوید جدا بسنج ──────────────────────────
    exp_pip = None if tr_layer is None else float(tr_layer['pnl_pip'].mean())
    cost_frac = round(1.0 / sl * 100.0, 2)    # اسپردِ ۱pip به‌عنوانِ ٪ SL

    out = {
        'asset': 'EURUSD', 'tf': tf, 'n_bars': int(d['n_bars']),
        'span_years': d['span_years'], 'sl_pip': sl, 'tp_pip': tp,
        'trail_pip': tl, 'max_hold': mh,
        'spread_as_pct_of_sl': cost_frac,
        'uncond_wr': None if wr_unc is None else round(wr_unc, 3),
        'layer': {'n': int(n_layer), 'wr': None if wr_l is None else round(wr_l, 3),
                  'perm_mean': None if pm_l is None else round(pm_l, 3),
                  'perm_sd': None if sd_l is None else round(sd_l, 4),
                  'null_ref': ref_l, 'lift_pp': lift_l, 'z': z_l,
                  'exp_pip': None if exp_pip is None else round(exp_pip, 4)},
        'base': {'n': 0 if tr_base is None else int(len(tr_base)),
                 'wr': None if wr_b is None else round(wr_b, 3),
                 'perm_mean': None if pm_b is None else round(pm_b, 3),
                 'perm_sd': None if sd_b is None else round(sd_b, 4),
                 'null_ref': ref_b, 'lift_pp': lift_b, 'z': z_b},
        'secs': round(time.time() - t0, 1),
    }
    L, B = out['layer'], out['base']
    print(f'  [{tf:>3}] {d["n_bars"]:>9,}bar | layer n={L["n"]:>5} '
          f'wr={L["wr"]} lift={L["lift_pp"]} z={L["z"]} exp={L["exp_pip"]}pip | '
          f'base lift={B["lift_pp"]} | unc={out["uncond_wr"]} ({out["secs"]}s)')
    sys.stdout.flush()
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', default='M30,M15,M5,H1,M1')
    ap.add_argument('--nperm', type=int, default=N_PERM_SCREEN)
    a = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    spec = importlib.util.spec_from_file_location(
        'adj', os.path.join(ROOT, 'tools', 's434_adjudicate.py'))
    adj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adj)

    sl, tp, daily = eur_geometry('M30')
    print(f'[اسکنِ EURUSD] ترجمهٔ نوسان‌محور:')
    print(f'  EURUSD دامنهٔ روزانهٔ میانه = {daily:.1f} pip '
          f'(XAUUSD = {XAU_DAILY_PIP:.0f} pip، نسبت {XAU_DAILY_PIP/daily:.1f}×)')
    print(f'  SL = {sl} pip   TP = {tp} pip   نسبت = {tp/sl:.4f} '
          f'(طلا: {XAU_SL}/{XAU_TP} = {RATIO:.4f})')
    print(f'  اسپردِ ۱pip = {1.0/sl*100:.1f}٪ فاصلهٔ استاپ '
          f'(طلا: {33/2055*100:.1f}٪) ⇒ {(1.0/sl)/(33/2055):.1f}× گران‌تر')
    print(f'  سدِ H3: lift ≥ 4.0pp')
    sys.stdout.flush()

    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            r = scan_eur_card(adj, tf, sl, tp, n_perm=a.nperm)
        except Exception as e:                              # noqa: BLE001
            print(f'  !! [{tf}] {type(e).__name__}: {e}')
            sys.stdout.flush()
            continue
        if r is None:
            continue
        # 🔒 قانونِ سوم: هر کارت فوراً ذخیره می‌شود.
        with open(os.path.join(OUT_DIR, f'eur_{tf}.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
    print('[done]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
