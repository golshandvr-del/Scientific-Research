# S626 — RoundNativeDriftLong · XAUUSD-H1 · حکم رسمی موتور: REJECT (RQS2=6.3)

**دانشمند:** اقلیدس (بلوک S620–S629) · **تاریخ:** 2026-09-02
**پیش‌ثبت:** `results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md` (commit 31bc0c61 + ADDENDUM-1 9ba370d7، قبل از اجرا) · n_trials=49 · seed=626626
**پیش‌ثبت اصلی جست‌وجو:** `results/S626_PREREG_*.md`

> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**
```
S626_RoundNativeDriftLong_H1 | REJECT RQS2=6.3 | n=494 WR=42.51% exp=+15.82pip PF=1.022 lift=1.19pp z=0.54 p_emp=0.311302 oos={'n': 344, 'wr': 44.48, 'pf': 1.134, 'net': 2746.9, 'wr_req': 41.54} | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✗
```

## قاعدهٔ منجمد
سمت: long · SL=1.5×ATR100 (میانهٔ محقق‌شده 85.5 pip) · TP=1.5×SL · max_hold=96 · allow_overlap=False · ورود open کندل بعد (شبیه‌ساز محافظه‌کار)
دادهٔ کامل (91331 کندل) · split_bar=45665 (نیمهٔ اول اکتشاف، نیمهٔ دوم خارج‌ازنمونه)

## null اندازه‌گیری‌شده (هندسه‌پوش S612، گیت‌شرطی S346)
{
 "long": {
  "uncond_wr": 41.31855078202336,
  "perm_mean": 41.124453637764354,
  "perm_sd": 1.6881924238907802,
  "perm_max": 46.391752577319586,
  "perm_k": 500
 }
}
سقف ورود هر قرعهٔ null=2000 (محافظه‌کارانه) · K=500

## دروازه‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✗

## یادداشت‌های موتور
- PF=1.022<1.3

## آرتیفکت‌ها
`results/_official_S626/{H1_rqs2.json, H1_trades.csv, null_model.json}`

— اقلیدس، بلوک S620–S629 📐
