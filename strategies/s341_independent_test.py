# -*- coding: utf-8 -*-
"""
تستِ سهمِ مستقل + بررسیِ کاربردِ فیلتر — S341 روی M5/M15/M30 (که ~۳۰٪ همپوشانیِ خام با پراکسیِ S333 داشتند)
================================================================================
قانونِ همپوشانیِ پروژه (بندِ سوم و چهارم): اگر لایهٔ جدید همپوشانیِ جزئی داشت، باید
(الف) امکانِ استفادهٔ بخشِ همپوشان به‌عنوان فیلتر بررسی شود، و
(ب) از طریقِ شبیه‌سازِ رویدادمحور (همان simulate_trades) تست شود.

روش (تصمیمِ علمی):
  ۱) ورودهای S341 را به دو دسته می‌شکنیم: «همپوشان با پراکسیِ S333» و «مستقل».
  ۲) RQS+ را روی زیرمجموعهٔ *مستقل* (بدونِ ورودهای همپوشان) می‌سنجیم.
       - اگر مستقل‌ها هم گیت‌پاس ⇒ S341 «لبهٔ نوِ اصیل» است (نه صرفاً فیلتر).
  ۳) هم‌چنین RQS+ را روی زیرمجموعهٔ *همپوشان* می‌سنجیم (آیا آن بخش هم به‌تنهایی می‌ارزد؟).

نکته: پراکسیِ S333 در ممیزی بسیار «پهن» است (هزاران کندل)، پس این تستْ محافظه‌کارانه
(سخت‌گیرانه) است: حتی اگر بخشِ زیادی «همپوشان» برچسب بخورد، بازهم مستقل‌بودنِ باقی‌مانده معنادار است.
"""
import numpy as np
from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs
from strategies.s341_brooks_swing_levels import load_tf
from strategies.s341_swing_fade_h1_revived import CONFIG, swing_fade_confluence_signals
from strategies.s341_multitf_overlap_audit import s333_like_long, to_idx


def run_subset(df, entry_idx, cfg, asset):
    """RQS+ روی زیرمجموعه‌ای از ورودها (بولینِ هم‌طول)."""
    sig = np.zeros(len(df), bool)
    sig[entry_idx] = True
    long_sig = sig if cfg['side'] == 'long' else np.zeros(len(df), bool)
    short_sig = sig if cfg['side'] == 'short' else np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=cfg['sl'], tp_pip=cfg['tp'],
                            asset=asset, max_hold=cfg['mh'], allow_overlap=False)
    return rqs.compute_rqs(tr, asset, sl_pip=cfg['sl'], tp_pip=cfg['tp'])


def analyze(card, tol=1):
    cfg = CONFIG[card]
    asset, tf = card.split('-')
    df = load_tf(asset, tf)
    s341 = to_idx(swing_fade_confluence_signals(df, cfg))
    s333 = to_idx(s333_like_long(df))

    s333set = np.asarray(s333)
    overlap_mask = np.array([bool(s333set.size and np.any(np.abs(s333set - x) <= tol)) for x in s341])
    indep = s341[~overlap_mask]
    over = s341[overlap_mask]

    print(f"\n=== {card} ===  کل ورودهای S341={len(s341)} | مستقل={len(indep)} | همپوشان={len(over)}")

    r_all = run_subset(df, s341, cfg, asset)
    print("  [کل]      ", rqs.format_report(f'{card}_ALL', r_all))
    if len(indep) >= 1:
        r_ind = run_subset(df, indep, cfg, asset)
        print("  [مستقل]   ", rqs.format_report(f'{card}_INDEP', r_ind))
    if len(over) >= 1:
        r_ov = run_subset(df, over, cfg, asset)
        print("  [همپوشان] ", rqs.format_report(f'{card}_OVER', r_ov))


if __name__ == '__main__':
    import sys
    cards = sys.argv[1:] or ['XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30']
    for card in cards:
        analyze(card)
