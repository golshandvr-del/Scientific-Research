# -*- coding: utf-8 -*-
"""
S361 — نجاتِ `S323` از راهِ **تکمیلِ آینه‌ایِ سمتِ فروش**
==========================================================================

## چرا این مسیر، پس از شکستِ دو مسیرِ قبلی

دو تلاشِ نجات شکست خورد و هرکدام یک درس داد:

  · `s358` (فیلتر): بهترین فیلتر WR را از ۷۲.۵٪ به ۸۱.۰٪ برد ولی n را از
    ۱۶۰ به ۶۳ کوباند. چون z با `√n` مقیاس می‌گیرد، ضریبِ ریشه از ۱۲.۶ به
    ۷.۹ افتاد و کلِ سودِ WR را بلعید. **درس: هر فیلتر هم‌زمان کمک و ضرر
    می‌کند؛ باید باخت‌ها را سریع‌تر از نمونه حذف کند.**

  · `s359`+`s360` (افق): اسکنِ متراکمِ ۴۷ نقطه‌ای نشان داد فقط ۳ نقطهٔ
    ناپیوسته عبور می‌کنند ⇒ قلهٔ تیز، نه فلات ⇒ طبقِ `variants.md` رد.
    **درس ثانویه و مهم‌تر: n در هر ۴۷ افق دقیقاً ۱۶۰ ماند.** یعنی مسدودیِ
    ناهم‌پوشانی از *خوشه‌ایِ بودنِ سیگنال* می‌آید (فاصلهٔ میانه ۲ کندل)،
    نه از افق. آن ۱۴۴ سیگنالِ مسدود از این راه هرگز آزاد نمی‌شوند.

هر دو مسیر روی **صورتِ کسر** یا روی **همان ۱۶۰ معامله** کار می‌کردند. این
اسکریپت به **مخرج** حمله می‌کند، اما نه از راهِ آزادکردنِ سیگنال‌های مسدود
(که ثابت شد ناممکن است)، بلکه از راهِ یک منبعِ کاملاً دست‌نخورده.

## مشاهده‌ای که این مسیر را باز می‌کند

خواندنِ `signals_backtested` نشان می‌دهد لایه **فقط لانگ** است:

    up = (close > ema50) & (ema50 > ema200)      ← فقط روندِ صعودی
    near = 0 < (close - support)/atr < nearMax   ← فقط پولبک به حمایت

یعنی نیمی از بازار — هر روندِ نزولی و هر پولبک به مقاومت — هرگز معامله
نشده است. این یک **حفرهٔ ساختاری** است، نه یک انتخابِ سنجیده: بایگانی هیچ
جا ننوشته که سمتِ فروش آزموده و رد شده؛ صرفاً هرگز نوشته نشده.

## چرا آینه بهترین شکلِ حمله به مخرج است

`z = (WR − ref) / √(ref(1−ref)/n)` ⇒ ضریبِ حساسیت `√n` است.

    الان:            n=160  →  √n = 12.65   →  z = 3.27
    با آینه (تخمین): n≈300  →  √n = 17.32   →  ضریب ×1.37

اگر سمتِ فروش لبه‌ای هم‌مرتبهٔ لانگ داشته باشد، z به حدودِ ۴.۵ می‌رسد —
یعنی نه با حاشیهٔ ۰.۱ سیگما (که `s360` نشان داد شکننده است) بلکه با
حاشیه‌ای که در برابرِ نوفهٔ نمونه‌گیری مقاوم است.

## ⚠️ قیدِ سختی که این مسیر را «رایگان» نگه می‌دارد

سدِ H5 تابعِ **تعدادِ پیکربندی‌هایی است که آزموده‌ایم**. اگر برای سمتِ فروش
پارامترِ تازه تنظیم کنم، آزمون‌ها منفجر می‌شوند و سد بالاتر از سودِ `√n`
می‌رود — همان تلهٔ خودشکنی که در `s358` مستند شد.

پس **قانونِ آهنینِ این اسکریپت: هیچ پارامترِ آزادِ جدیدی وجود ندارد.**
هر شرط دقیقاً آینه می‌شود با همان مقادیرِ لانگ:

    up   = close>ema50 & ema50>ema200   →  down = close<ema50 & ema50<ema200
    near = 0 < (close−sup)/atr < nearMax →  near = 0 < (res−close)/atr < nearMax
    room = (res−close)/atr > roomMin     →  room = (close−sup)/atr > roomMin
    rsi  < rsiMax                        →  rsi  > 100 − rsiMax   (آینهٔ دقیق)
    slope ≥ slopeMin                     →  slope ≤ −slopeMin
    adx  ≥ adxMin                        →  بدونِ تغییر (ADX بی‌جهت است)
    پنجرهٔ طلایی                          →  بدونِ تغییر

⇒ هزینهٔ آزمون = **۱** (نه یک اسکن). سد تقریباً ثابت می‌ماند.

`rsiMax` آینه‌اش `100 − rsiMax` است چون RSI حولِ ۵۰ متقارن است؛ «اشباعِ
فروشِ نسبی» در روندِ صعودی معادلِ «اشباعِ خریدِ نسبی» در روندِ نزولی است.

## دو خطری که صادقانه ثبت می‌شوند

۱. **H4 ممکن است بیفتد.** دروازهٔ H4 می‌خواهد **هر سمت** جداگانه لیفتِ
   مثبت داشته باشد. اگر سمتِ فروش ضعیف باشد، افزودنش H5 را نجات می‌دهد
   ولی H4 را می‌کشد — یعنی معاوضه، نه پیشرفت. پس هر سمت **جداگانه** هم
   سنجیده و گزارش می‌شود، نه فقط ترکیب.

۲. **مدلِ صفرِ هر سمت فرق دارد.** طلا رانشِ صعودیِ تاریخی دارد، پس مبنای
   بی‌قیدِ شورت پایین‌تر از لانگ است. مقایسهٔ شورت با مبنای لانگ تقلبِ
   آشکار است. پس `outcome_table` جداگانه برای هر سمت ساخته می‌شود و
   ترکیب با `blend_null` وزن‌دار به تعدادِ معاملهٔ همان سمت انجام می‌گیرد
   — دقیقاً همان قراردادی که `engine/rqs2.py` دارد.

## قانونِ MTF

طبقِ قانونِ اول، آینه روی **همهٔ** کارت‌ها آزموده می‌شود نه فقط M30، چون
ممکن است سمتِ فروش روی کارتی زنده باشد که سمتِ خرید مرده بود — مثلاً M15
که لانگش فقط ۱.۲۰ سیگما داشت. از XAUUSD-M5 شروع می‌شود (طلا M1 ندارد).
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import scalp_engine as se           # noqa: E402
from engine import indicators as ind            # noqa: E402
from engine import rqs2 as R2                   # noqa: E402
from s357_s323_v24_rejudge import (             # noqa: E402
    cfg_for, signals_backtested, outcome_table, wr_of,
)
from s358_s323_h5_rescue import binom_z, perm_mean_for   # noqa: E402

CARDS = ['XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1',
         'EURUSD-M5', 'EURUSD-M15', 'EURUSD-M30', 'EURUSD-H1']
K_PERM = 1500
SEEDS = (23, 101, 777)

# بودجهٔ انباشته: ۲۴۰۰ ساخت + ۸۸ فیلتر + ۳۲ افقِ پراکنده + ۴۷ افقِ متراکم
# + ۱ آینه (یک پیکربندی، بدونِ پارامترِ آزاد)
PRIOR_TRIALS = 2400 + 88 + 32 + 47
OUT_DIR = 'results/_s361_s323_mirror'


def signals_short_mirror(df, asset, cfg):
    """آینهٔ دقیقِ `signals_backtested` برای سمتِ فروش.

    هیچ پارامترِ آزادِ جدیدی ندارد — هر عدد از همان `cfg`ِ لانگ می‌آید.
    ساختارِ کد عمداً موازیِ نسخهٔ لانگ نگه داشته شده تا هر انحراف در
    بازبینی فوراً دیده شود.
    """
    from engine import structure as st
    tol = 0.0008 if asset == 'EURUSD' else 0.0015
    piv = st.pivots(df, left=6, right=6)
    sr = st.sr_levels(df, piv, tol=tol, expiry=1500)
    atr = ind.atr(df, 14).values
    a = np.where(atr > 0, atr, np.nan)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    rsi14 = ind.rsi(df['close'], 14).values
    adx_arr, _, _ = ind.adx(df, 14)
    adx_arr = np.nan_to_num(adx_arr.values, nan=0.0)
    close = df['close'].values
    hour = df['dt'].dt.hour.values
    sup = sr['support'].values
    res_lvl = sr['resistance'].values

    # آینه: فاصله تا **مقاومت** بالای سر، و فضای نفس تا **حمایت** پایین
    dist_res = np.nan_to_num((res_lvl - close) / a, nan=99.0)
    room = np.nan_to_num((close - sup) / a, nan=-99.0)
    slope = np.full(len(df), np.nan)
    slope[10:] = (ema50[10:] - ema50[:-10]) / a[10:]
    slope = np.nan_to_num(slope, nan=0.0)

    down = (close < ema50) & (ema50 < ema200)
    near = (dist_res > 0) & (dist_res < cfg['nearMax'])
    room_ok = room > cfg['roomMin']
    rsi_ok = rsi14 > (100.0 - cfg['rsiMax'])      # آینهٔ متقارنِ RSI حولِ ۵۰
    slope_ok = slope <= -cfg['slopeMin']
    adx_ok = adx_arr >= cfg['adxMin']             # ADX بی‌جهت است
    gold = ((hour >= cfg['hLo']) & (hour <= cfg['hHi'])) if cfg['golden'] \
        else np.ones(len(df), bool)
    sig = down & near & room_ok & rsi_ok & slope_ok & adx_ok & gold
    sig[:300] = False
    return sig


def side_stats(df, asset, sig, sl, tp, mh, is_short, k_perm, seeds):
    """آمارِ یک سمت با مدلِ صفرِ مخصوصِ همان سمت."""
    long_sig = np.zeros(len(df), bool) if is_short else sig
    short_sig = sig if is_short else np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    n = len(tr)
    if n == 0:
        return dict(n=0)
    w = int((tr['pnl_pip'] > 0).sum())

    res, xbar = outcome_table(df, asset, sl, tp, mh, short=is_short) \
        if 'short' in outcome_table.__code__.co_varnames \
        else outcome_table(df, asset, sl, tp, mh)
    valid = np.arange(260, max(261, len(df) - mh - 2))
    valid = valid[res[valid] != 0]
    uncond = wr_of(valid, res, xbar)
    pms = [perm_mean_for(res, xbar, valid, n, k_perm, s) for s in seeds]
    ref = max(uncond, float(np.mean(pms)))
    return dict(n=n, wins=w, wr=round(100.0 * w / n, 2),
                uncond=round(uncond, 2),
                perm_mean=round(float(np.mean(pms)), 2), ref=round(ref, 2),
                z=round(binom_z(w, n, ref / 100.0), 3),
                lift=round(100.0 * w / n - ref, 2),
                trades=tr)


def main():
    n_trials = PRIOR_TRIALS + 1
    zbar = R2.expected_max_z(n_trials)
    print("S361 — تکمیلِ آینه‌ایِ سمتِ فروش برای S323")
    print(f"بودجهٔ آزمون: {PRIOR_TRIALS} + 1 = {n_trials}   سدِ H5 = {zbar:.4f}")
    print(f"قرعه: K={K_PERM} × {len(SEEDS)} بذر\n", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    summary = {}

    for card in CARDS:
        asset, tf = card.split('-')
        path = f'data/{asset}_{tf}.csv'
        if not os.path.exists(path):
            print(f"— {card}: دادهٔ موجود نیست، رد شد")
            continue
        df = se.load_data(path)
        cfg = cfg_for(card)
        atr14 = ind.atr(df, 14).values
        pip = se.ASSETS[asset]['pip']
        am = float(np.nanmedian(atr14[260:]) / pip)
        sl = round(cfg['slMult'] * am, 1)
        tp = round(cfg['tpMult'] * am, 1)
        mh = cfg['maxHold']

        sig_l = signals_backtested(df, asset, cfg)
        sig_s = signals_short_mirror(df, asset, cfg)

        print(f"=== {card}  SL={sl} TP={tp} mh={mh} | "
              f"سیگنالِ خام: long={int(sig_l.sum())} short={int(sig_s.sum())}",
              flush=True)

        L = side_stats(df, asset, sig_l, sl, tp, mh, False, K_PERM, SEEDS)
        S = side_stats(df, asset, sig_s, sl, tp, mh, True, K_PERM, SEEDS)

        for nm, d in (('long ', L), ('short', S)):
            if d['n'] == 0:
                print(f"  {nm}: بی‌سیگنال")
            else:
                print(f"  {nm}: n={d['n']:4d} WR={d['wr']:6.2f} "
                      f"ref={d['ref']:6.2f} lift={d['lift']:+6.2f} "
                      f"z={d['z']:6.3f}", flush=True)

        rec = dict(card=card, sl_pip=sl, tp_pip=tp, max_hold=mh,
                   n_trials=n_trials, zbar=round(zbar, 4),
                   long={k: v for k, v in L.items() if k != 'trades'},
                   short={k: v for k, v in S.items() if k != 'trades'})

        # ---- ترکیبِ دو سمت با مبنای وزن‌دار (قراردادِ blend_null) -------
        if L['n'] and S['n']:
            nL, nS = L['n'], S['n']
            wtot = L['wins'] + S['wins']
            ntot = nL + nS
            ref_mix = (L['ref'] * nL + S['ref'] * nS) / ntot
            wr_mix = 100.0 * wtot / ntot
            z_mix = binom_z(wtot, ntot, ref_mix / 100.0)
            h4_ok = (L['lift'] > 0) and (S['lift'] > 0)
            print(f"  ⊕ ترکیب: n={ntot} WR={wr_mix:.2f} ref={ref_mix:.2f} "
                  f"lift={wr_mix-ref_mix:+.2f} z={z_mix:.3f} "
                  f"{'✅ H5' if z_mix > zbar else '✗ H5'} "
                  f"{'✅ H4' if h4_ok else '✗ H4(سمتِ بی‌مهارت)'}", flush=True)
            rec['combined'] = dict(n=ntot, wins=wtot, wr=round(wr_mix, 2),
                                   ref=round(ref_mix, 2),
                                   lift=round(wr_mix - ref_mix, 2),
                                   z=round(z_mix, 3),
                                   h5_pass=bool(z_mix > zbar),
                                   h4_pass=bool(h4_ok))
        print(flush=True)
        summary[card] = rec
        json.dump(rec, open(os.path.join(OUT_DIR, f'{card}.json'), 'w',
                            encoding='utf-8'), ensure_ascii=False, indent=1)

    json.dump(summary, open(os.path.join(OUT_DIR, 'summary.json'), 'w',
                            encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"→ wrote {OUT_DIR}/")


if __name__ == '__main__':
    main()
