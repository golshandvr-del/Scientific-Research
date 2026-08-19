# -*- coding: utf-8 -*-
"""
S602 — استخرِ ۲عضویِ {D1,H8} شوکِ انگل — درمانِ تلهٔ رقیق‌سازیِ وارونهٔ S601
================================================================================
پیش‌ثبت: results/S602_PREREG_ENGLE_SHOCK_POOL_D1H8.md (کامیت 8faf7b2c، قبل از اجرا).
سازوکار عیناً s601 (import می‌شود)؛ تنها تفاوتِ پیش‌ثبت‌شده: اعضا={D1,H8}،
SEED=20260818، OUT جدید. صفر پارامترِ جدید.
"""
import sys
sys.path.insert(0, '.')

import strategies.s601_engle_pool as base

base.CANDIDATES = ['D1', 'H8']
base.SEED = 20260818
base.OUT = 'results/_s602_engle_pool_d1h8'

if __name__ == '__main__':
    base.main()
