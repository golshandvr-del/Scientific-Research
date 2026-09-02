# S628 — RollingSupportHold · XAUUSD-H2 · حکم رسمی موتور: REJECT (RQS2=9.7)

**دانشمند:** اقلیدس (بلوک S620–S629) · **تاریخ:** 2026-09-02
**پیش‌ثبت:** `results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md` (commit 31bc0c61 + ADDENDUM-1 9ba370d7، قبل از اجرا) · n_trials=25 · seed=628628
**پیش‌ثبت اصلی جست‌وجو:** `results/S628_PREREG_*.md`

> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**
```
S628_RollingSupportHold_H2 | REJECT RQS2=9.7 | n=118 WR=41.53% exp=+14.01pip PF=0.99 lift=-0.32pp z=-0.07 p_emp=0.56285 oos={'n': 70, 'wr': 40.0, 'pf': 0.938, 'net': -252.2, 'wr_req': 41.51} | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✓
```

## قاعدهٔ منجمد
سمت: long · SL=1.5×ATR100 (میانهٔ محقق‌شده 87.6 pip) · TP=1.5×SL · max_hold=64 · allow_overlap=False · ورود open کندل بعد (شبیه‌ساز محافظه‌کار)
دادهٔ کامل (47623 کندل) · split_bar=23811 (نیمهٔ اول اکتشاف، نیمهٔ دوم خارج‌ازنمونه)

## null اندازه‌گیری‌شده (هندسه‌پوش S612، گیت‌شرطی S346)
{
 "long": {
  "uncond_wr": 41.715575620767495,
  "perm_mean": 41.84316811292695,
  "perm_sd": 3.6624916665966345,
  "perm_max": 50.955414012738856,
  "perm_k": 500
 }
}
سقف ورود هر قرعهٔ null=2000 (محافظه‌کارانه) · K=500

## دروازه‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✓

## یادداشت‌های موتور
- PF=0.990<1.3

## آرتیفکت‌ها
`results/_official_S628/{H2_rqs2.json, H2_trades.csv, null_model.json}`

— اقلیدس، بلوک S620–S629 📐
