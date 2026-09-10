# -*- coding: utf-8 -*-
"""
s1450_tp_extension_uu.py — S1450 · تمدیدِ TP با کلمهٔ 𝕌𝕌 در سود
================================================================================
پیش‌ثبت: results/S1450_PREREG_MGMT_DECADE2_PROTOCOL_AND_TP_EXTENSION.md §۲ (کامیت قبل از اجرا).

الفبای علّی عینِ S455 (ترسیل‌های |ln-return| روی پنجرهٔ اکیداً قبلیِ ۵۰۰).
رویداد: در close کندلِ i (بعد از hit-check)، معامله در سود، 𝕌[i-1]&𝕌[i]، TP لمس نشده
⇒ TP ← entry + θ×TP_dist₀ (یک بار). θ ∈ {1.25, 1.5, 2.0}. SL دست نمی‌خورد.
برنده در نیمهٔ اول = بیشترین بهبودِ avg میانِ پاس‌شده‌ها (قاعدهٔ سودمحور).

اجرا: python3 strategies/s1450_tp_extension_uu.py <patient>
"""
import sys
import numpy as np
import pandas as pd
from strategies import s145x_mgmt_cohort2 as C

CODE = 'S1450'
VARIANTS = ('X125', 'X150', 'X200')
THETA = {'X125': 1.25, 'X150': 1.5, 'X200': 2.0}
W = 500


def big_up(df):
    c = df['close'].astype(float)
    r = np.log(c).diff()
    a = r.abs()
    qh = a.rolling(W, min_periods=W).quantile(2 / 3).shift(1)
    return ((a >= qh) & (r > 0)).to_numpy()


class Rule:
    def __init__(self, up, theta):
        self.up = up; self.theta = theta

    def on_bar(self, i, entry, fl, sl_lvl, tp_lvl, state, is_long):
        # state = True اگر تمدید انجام شده
        if state or i < 1 or fl <= 0.0:
            return None, state
        if self.up[i - 1] and self.up[i]:
            tp0 = tp_lvl - entry
            return ('tp', entry + self.theta * tp0), True
        return None, state


def make_rule(df, vn):
    return Rule(big_up(df), THETA[vn])


if __name__ == '__main__':
    for nm in (sys.argv[1:] or list(C.PATIENTS)):
        C.run(CODE, nm, VARIANTS, make_rule, winner_key='avg')
