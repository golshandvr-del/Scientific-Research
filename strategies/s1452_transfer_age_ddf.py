# -*- coding: utf-8 -*-
"""
s1452_transfer_age_ddf.py — S1452 · انتقالِ S453 (سن k=15) و S455 (شکستِ نجاتِ 𝔻𝔻) و اجتماعشان به cohort 2
================================================================================
پیش‌ثبت: results/S1452_PREREG_ADDENDUM_TRANSFER_S453_S455_COHORT2.md (کامیت قبل از اجرا).
V_AGE: در close کندلِ e+15 اگر fl<=0 ⇒ exit. V_DDF: عینِ S455 V_DDFAIL. V_BOTH: اجتماع.
اجرا: python3 strategies/s1452_transfer_age_ddf.py <patient>
"""
import os
import sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from strategies import s145x_mgmt_cohort2 as C  # noqa: E402

CODE = 'S1452'
VARIANTS = ('V_AGE', 'V_DDF', 'V_BOTH')
K_AGE = 15
W = 500
INFORMATIONAL = ('S382_H4', 'S312_H1')


def big_words(df):
    c = df['close'].astype(float)
    r = np.log(c).diff()
    a = r.abs()
    qh = a.rolling(W, min_periods=W).quantile(2 / 3).shift(1)
    big = (a >= qh).to_numpy()
    up = (r > 0).to_numpy()
    return big & ~up, big & up


class Rule:
    def __init__(self, vn, dn, up):
        self.vn = vn; self.dn = dn; self.up = up
        self.age = vn in ('V_AGE', 'V_BOTH'); self.ddf = vn in ('V_DDF', 'V_BOTH')

    def on_bar(self, i, entry, fl, sl_lvl, tp_lvl, state, is_long):
        # state = (entry_bar, grace_bar)
        if state is None:
            state = (i - 1, None)          # اولین فراخوانی همیشه در e+1 (s382) یا e+1 (ts, i>e)
        e, grace = state
        losing = fl <= 0.0
        if self.age and i == e + K_AGE and losing:
            return ('exit',), state
        if self.ddf:
            if grace is not None and i == grace:
                if losing and not self.up[i]:
                    return ('exit',), (e, None)
                grace = None
            if i >= 1 and self.dn[i - 1] and self.dn[i] and losing:
                grace = i + 1
        return None, (e, grace)


def make_rule(df, vn):
    dn, up = big_words(df)
    return Rule(vn, dn, up)


if __name__ == '__main__':
    C.INFORMATIONAL = INFORMATIONAL
    for nm in (sys.argv[1:] or list(C.PATIENTS)):
        C.run(CODE, nm, VARIANTS, make_rule, winner_key='maxDD')
