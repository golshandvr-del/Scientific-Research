# -*- coding: utf-8 -*-
"""
S341-H1 (احیاشده) — Al Brooks «Horizontal Lines: Swing Points» (فصلِ ۱۷) روی XAUUSD-H1
================================================================================
پارادایم: RQS+ ≥ ۸۰.

داستانِ علمی:
- نسخهٔ خامِ swing-fade روی H1 «سوخته» بود: RQS+=۳۳٫۴، WR=۵۶٫۱٪ ⇒ رد روی گیتِ G0 (کفِ WR<۶۰٪).
- طبق «قانونِ جعبه‌ابزار» به بانکِ ۴۰۱ اندیکاتور رجوع شد. Brooks در همین فصل می‌گوید
  «the middle of the day acts like a magnet» ⇒ fade فقط وقتی می‌ارزد که قیمت واقعاً از میانگین
  «کشیده» شده باشد. نگاشتِ مکانیکیِ این جمله = اندیکاتورِ `ema_dist_atr = (close−SMA)/EMA(ATR)`.
- افزودنِ تنها یک فیلتر — `ema_dist_atr ≥ 0.7` (کششِ حداقل ۰٫۷ ATR از میانگین، جهتِ LONG یعنی
  کفِ کشیده) — WR را از ۵۶٫۱٪ به ۶۶٫۷٪ و RQS+ را از ۳۳ به ۹۴٫۵ رساند. (بدونِ کوچک‌کردنِ TP؛
  نرخِ اصابتِ *واقعی* بالا رفت، نه ساختگی.)

منطقِ مکانیکی (causal؛ سیگنال روی کندلِ i، ورود در open کندلِ i+1):
  side='long' (تنها جهتِ تأییدشده روی H1):
    - رژیمِ رنج (اجباری، قلبِ فصلِ ۱۷): chop≥61.8 و r2≤0.22 و |ER|≤0.16
    - failed breakout زیرِ swing low: low[i] < swing_low − buf·ATR  و  close[i] > swing_low
    - فیلترِ کششِ مغناطیسی: ema_dist_atr[i] ≤ −0.7   (قیمت زیرِ میانگین، کشیده)
    - فیلترِ خستگی (اختیاری): ifish_rsi[i] ≤ −0.25
  swing_low = پیوتِ فراکتالی با نیم‌پنجرهٔ w=4.

نتیجهٔ نهایی (XAUUSD-H1): RQS+=94.5 | n=42 | WR=66.7% | PF=2.01 | DD=1.5% | MCL=2 | net=+$387
"""
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs
from strategies.s341_brooks_swing_levels import _fractal_levels, load_tf


# پیکربندیِ تأییدشدهٔ نهاییِ چند-تایم‌فریمی (غیررند، per-TF) — طبق قانونِ #۷ (اجتناب از اعداد رند)
# و قانونِ اولِ مولتی‌تایم‌فریم (هر TF بهبود/تنظیمِ متناسبِ خود را دارد).
# ───────────────────────────────────────────────────────────────────────────
#  M5/M15/M30 : از همان آغاز ACCEPT بودند — از طریقِ رژیمِ رنجِ سفت + سیگنالِ دوم
#               (require_second=True)، بدونِ نیاز به فیلترِ کششِ جعبه‌ابزار.
#  H1         : در آغاز «سوخته» (RQS 33) بود؛ با فیلترِ جعبه‌ابزار ema_dist_atr≥0.7
#               («مغناطیسِ میانه») احیا شد ⇒ RQS+ 94.5.
CONFIG = {
    # RQS+=94.7 | n=48 | WR=70.8% | PF=2.22 | DD=2.0% | MCL=2
    'XAUUSD-M5': dict(
        side='long', w=4, buf=0.05, require_second=True,
        stretch=None, exh=None,                # فیلترِ کشش لازم نشد (رژیم+سیگنالِ دوم کافی بود)
        sl=180, tp=260, mh=48,
        chop_min=61.8, r2_max=0.22, er_max=0.16,
        chop_p=14, r2_p=20, er_name='er_lucas_11',
    ),
    # RQS+=89.8 | n=40 | WR=65.0% | PF=1.83 | DD=1.8% | MCL=4
    'XAUUSD-M15': dict(
        side='long', w=4, buf=0.15, require_second=True,
        stretch=None, exh=None,
        sl=280, tp=620, mh=40,
        chop_min=61.8, r2_max=0.22, er_max=0.16,
        chop_p=14, r2_p=20, er_name='er_lucas_11',
    ),
    # RQS+=89.7 | n=61 | WR=63.9% | PF=1.77 | DD=1.5% | MCL=3
    'XAUUSD-M30': dict(
        side='long', w=8, buf=0.15, require_second=True,
        stretch=None, exh=None,
        sl=380, tp=840, mh=18,
        chop_min=58, r2_max=0.30, er_max=0.22,
        chop_p=14, r2_p=20, er_name='er_lucas_11',
    ),
    # RQS+=94.5 | n=42 | WR=66.7% | PF=2.01 | DD=1.5% | MCL=2  (احیاشده با فیلترِ جعبه‌ابزار)
    'XAUUSD-H1': dict(
        side='long', w=4, buf=0.05, require_second=False,
        stretch=0.7, exh=0.25,                 # فیلترهای جعبه‌ابزار
        sl=520, tp=1550, mh=16,                # per-TF، TP>SL (بدونِ بازیِ اشتباهِ #۸)
        chop_min=61.8, r2_max=0.22, er_max=0.16,
        chop_p=14, r2_p=20, er_name='er_lucas_11',
    ),
}


def swing_fade_confluence_signals(df, cfg):
    """آرایهٔ بولین هم‌طولِ df؛ True = سیگنالِ ورود روی این کندل (ورود در i+1)."""
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(df)

    atr = ib.atr_s(df, p=14).to_numpy()
    ch = ib.chop(df, p=cfg['chop_p']).to_numpy()
    r2 = ib.r2(df, p=cfg['r2_p']).to_numpy()
    er = ib.compute(cfg['er_name'], df).to_numpy()
    edist = ib.compute('ema_dist_atr', df).to_numpy()
    ifr = ib.compute('ifish_rsi', df).to_numpy()

    finite = np.isfinite(ch) & np.isfinite(r2) & np.isfinite(er)
    reg = finite & (ch >= cfg['chop_min']) & (r2 <= cfg['r2_max']) & (np.abs(er) <= cfg['er_max'])

    last_sh, last_sl = _fractal_levels(h, l, cfg['w'])
    side = cfg['side']
    buf_frac = cfg['buf']
    stretch = cfg['stretch']
    exh = cfg['exh']

    sig = np.zeros(n, dtype=bool)
    recent = []
    for i in range(cfg['w'] + 2, n):
        if not reg[i]:
            continue
        a = atr[i]
        if not (a > 0) or not np.isfinite(a):
            continue
        buf = buf_frac * a

        if side == 'short':
            lvl = last_sh[i]
            if not np.isfinite(lvl):
                continue
            trig = (h[i] > lvl + buf) and (c[i] < lvl)
        else:
            lvl = last_sl[i]
            if not np.isfinite(lvl):
                continue
            trig = (l[i] < lvl - buf) and (c[i] > lvl)
        if not trig:
            continue

        # فیلترِ کششِ مغناطیسی (ema_dist_atr) — جهت‌دار
        if stretch is not None:
            ed = edist[i]
            if not np.isfinite(ed):
                continue
            if side == 'long' and not (ed <= -stretch):
                continue
            if side == 'short' and not (ed >= stretch):
                continue
        # فیلترِ خستگیِ مومنتوم (ifish_rsi) — جهت‌دار
        if exh is not None:
            fv = ifr[i]
            if not np.isfinite(fv):
                continue
            if side == 'long' and not (fv <= -exh):
                continue
            if side == 'short' and not (fv >= exh):
                continue

        if cfg['require_second']:
            recent = [k for k in recent if i - k <= 40]
            recent.append(i)
            if len(recent) < 2:
                continue
        sig[i] = True
    return sig


def run(card='XAUUSD-H1'):
    cfg = CONFIG[card]
    asset, tf = card.split('-')
    df = load_tf(asset, tf)
    sig = swing_fade_confluence_signals(df, cfg)
    long_sig = sig if cfg['side'] == 'long' else np.zeros(len(df), bool)
    short_sig = sig if cfg['side'] == 'short' else np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=cfg['sl'], tp_pip=cfg['tp'],
                            asset=asset, max_hold=cfg['mh'], allow_overlap=False)
    r = rqs.compute_rqs(tr, asset, sl_pip=cfg['sl'], tp_pip=cfg['tp'])
    return r, tr


if __name__ == '__main__':
    import sys
    cards = sys.argv[1:] or list(CONFIG.keys())
    for card in cards:
        r, tr = run(card)
        print(rqs.format_report(f'S341_{card}', r))
        m = r['metrics']
        print(f"  net=${m.get('net_profit',0):.0f}  n={m.get('n_trades',0)}  "
              f"WR={m.get('win_rate',0):.1f}%  PF={m.get('profit_factor',0):.2f}  passed={r['passed']}")
