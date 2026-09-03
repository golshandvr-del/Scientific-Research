# -*- coding: utf-8 -*-
"""ساختِ fixture پریتیِ S770 — پایتونِ مرجع ↔ TSِ سایت. دو کارت: D1 و H8.

خروجی: results/_scan_S770/parity_{D1,H8}_fixture.json
  candles       : دمِ کندل‌ها (همان چیزی که سایت می‌بیند)
  py.idx_long   : ایندکسِ سیگنال‌های LONG پایتون **در فضای همین دم**
  py.idx_short  : همان برای SHORT
  py.frac       : متغیرِ حالت (close−dayOpen)/ADR21 روی همین دم
  py.adr        : ADR₂۱ روزِ متناظرِ هر کندل (علّی)
  py.atr        : ATR₁۰۰ (میانگینِ سادهٔ TR، بدونِ شیفت)
  py.sl_pip / tp_pip : هندسهٔ برداریِ هر کندل

⚠️ نکتهٔ کلیدیِ روشِ آزمون: مرجعِ پایتون **روی کلِ تاریخ** محاسبه می‌شود و بعد
برش می‌خورد. اگر پورتِ TS به warm-up وابسته باشد (مثلاً ADR را از ابتدای پنجره
شروع کند نه از ۲۱ روزِ واقعی) اختلاف همان‌جا لو می‌رود.

پیکربندی عیناً از strategies/s770_adr_expansion.py خوانده می‌شود (θ/hold از
فایل‌های _explore.json که **قبل** از داوری قفل شده‌اند) — هیچ عددی اینجا
دستی وارد نمی‌شود.

اجرا: python3 web_tool/tools/make_s770_fixture.py
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from strategies import s770_adr_expansion as S     # noqa: E402
from engine import scalp_engine as se              # noqa: E402

CARDS = ['D1', 'H8']
TAIL = {'D1': 1500, 'H8': 3000}
OUTDIR = os.path.join(ROOT, 'results', '_scan_S770')


def locked_cfg(tf):
    """θ و hold را از خروجیِ اکتشافِ قفل‌شده می‌خوانیم (نه دستی)."""
    fp = os.path.join(OUTDIR, f'{tf}_explore.json')
    with open(fp) as f:
        ex = json.load(f)
    best = ex['best']
    return float(best['theta']), int(best['hold'])


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    pip = se.ASSETS['XAUUSD']['pip']

    for tf in CARDS:
        theta, hold = locked_cfg(tf)
        df, src = S.load_card(tf)
        n = len(df)

        frac = S.build_features(df)
        sl_pip, tp_pip, atr = S.geometry(df)
        valid = np.isfinite(frac) & np.isfinite(sl_pip) & (sl_pip > 0)
        lsig, ssig = S.signals_for(frac, theta)
        lsig &= valid
        ssig &= valid

        # ADR روزانهٔ بازتاب‌شده روی هر کندل (برای مقایسهٔ عددیِ TS)
        t = __import__('pandas').to_datetime(df['time'], unit='s')
        day = t.dt.normalize().values
        daily = df.groupby(day).agg(hi=('high', 'max'), lo=('low', 'min'),
                                    op=('open', 'first'))
        daily['rng'] = daily['hi'] - daily['lo']
        daily['adr'] = daily['rng'].rolling(S.ADR_P).mean().shift(1)
        adr = daily['adr'].reindex(day).values
        dopen = daily['op'].reindex(day).values

        tail = min(TAIL[tf], n)
        off = n - tail
        idx_long = [int(i) - off for i in np.flatnonzero(lsig) if i >= off]
        idx_short = [int(i) - off for i in np.flatnonzero(ssig) if i >= off]

        def cut(a):
            return [None if not np.isfinite(x) else float(x) for x in a[off:]]

        candles = [dict(time=int(df['time'].values[i]),
                        open=float(df['open'].values[i]),
                        high=float(df['high'].values[i]),
                        low=float(df['low'].values[i]),
                        close=float(df['close'].values[i]),
                        volume=float(df['volume'].values[i]))
                   for i in range(off, n)]

        fx = dict(
            tf=tf, src=src, n_bars_full=int(n), tail=int(tail), offset=int(off),
            cfg=dict(theta=theta, hold=hold, adr_p=S.ADR_P, atr_p=S.ATR_P,
                     sl_k=S.SL_K, rr=S.RR),
            candles=candles,
            py=dict(idx_long=idx_long, idx_short=idx_short,
                    frac=cut(frac), adr=cut(adr), day_open=cut(dopen),
                    atr=cut(atr), sl_pip=cut(sl_pip), tp_pip=cut(tp_pip)),
        )
        fp = os.path.join(OUTDIR, f'parity_{tf}_fixture.json')
        with open(fp, 'w') as f:
            json.dump(fx, f)
        print(f'{tf}: bars_full={n:,} tail={tail} off={off} '
              f'theta={theta} hold={hold} '
              f'sig_in_tail long={len(idx_long)} short={len(idx_short)} '
              f'med_sl={np.nanmedian(sl_pip):.1f}pip -> {fp}', flush=True)


if __name__ == '__main__':
    main()
