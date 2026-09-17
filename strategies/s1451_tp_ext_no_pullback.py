# -*- coding: utf-8 -*-
"""
s1451_tp_ext_no_pullback.py — S1451 · تمدیدِ TP + سربه‌سر وقتی پولبک نیامد
================================================================================
پیش‌ثبت: results/S1451_PREREG_ADDENDUM_TP_EXTENSION_NO_PULLBACK.md (کامیت قبل از اجرا).

در close کندلِ i: mfe>=0.75×TP₀ و fl>0 و در k کندلِ اخیر هیچ 𝔻 (نزولِ بزرگ، ترسیلِ
علّیِ ۵۰۰) ⇒ TP←entry+1.5×TP₀، SL←entry (یک بار). k ∈ {2,3,5}.
اجرا: python3 strategies/s1451_tp_ext_no_pullback.py <patient>
"""
import os
import sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from strategies import s145x_mgmt_cohort2 as C  # noqa: E402

CODE = 'S1451'
VARIANTS = ('K2', 'K3', 'K5')
KK = {'K2': 2, 'K3': 3, 'K5': 5}
W = 500
READY = 0.75
EXT = 1.5


def big_down(df):
    c = df['close'].astype(float)
    r = np.log(c).diff()
    a = r.abs()
    qh = a.rolling(W, min_periods=W).quantile(2 / 3).shift(1)
    return ((a >= qh) & (r < 0)).to_numpy()


class Rule:
    def __init__(self, dn, k):
        self.dn = dn; self.k = k

    def on_bar(self, i, entry, fl, sl_lvl, tp_lvl, state, is_long):
        # state = (done, mfe)
        done, mfe = state if state is not None else (False, -np.inf)
        mfe = max(mfe, fl)
        if done:
            return None, (True, mfe)
        tp0 = tp_lvl - entry
        if mfe >= READY * tp0 and fl > 0.0 and i - self.k + 1 >= 0 \
                and not self.dn[i - self.k + 1:i + 1].any():
            return ('tp_sl', entry + EXT * tp0, entry), (True, mfe)
        return None, (False, mfe)


def make_rule(df, vn):
    return Rule(big_down(df), KK[vn])


if __name__ == '__main__':
    for nm in (sys.argv[1:] or list(C.PATIENTS)):
        C.run(CODE, nm, VARIANTS, make_rule, winner_key='avg')
