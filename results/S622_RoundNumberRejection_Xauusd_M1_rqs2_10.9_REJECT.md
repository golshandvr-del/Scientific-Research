# S622 — RoundNumberRejection · XAUUSD-M1 · حکم رسمی موتور: REJECT (RQS2=10.9)

**دانشمند:** اقلیدس (بلوک S620–S629) · **تاریخ:** 2026-09-02
**پیش‌ثبت:** `results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md` (commit 31bc0c61 + ADDENDUM-1 9ba370d7، قبل از اجرا) · n_trials=192 · seed=622622
**پیش‌ثبت اصلی جست‌وجو:** `results/S622_PREREG_*.md`

> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**
```
S622_RoundNumberRejection_M1 | REJECT RQS2=10.9 | n=78465 WR=48.06% exp=-3.46pip PF=0.418 lift=5.66pp z=5.14 p_emp=0.0 oos={'n': 57308, 'wr': 49.75, 'pf': 0.35, 'net': -10000.7, 'wr_req': 63.88} | H0:✗ H1:✗ H2:✗ H3:✓ H4:✗ H5:✓ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗
```

## قاعدهٔ منجمد
سمت: both · SL=1.5×ATR100 (میانهٔ محقق‌شده 11.9 pip) · TP=1.0×SL · max_hold=240 · allow_overlap=False · ورود open کندل بعد (شبیه‌ساز محافظه‌کار)
دادهٔ کامل (5000000 کندل) · split_bar=2500000 (نیمهٔ اول اکتشاف، نیمهٔ دوم خارج‌ازنمونه)

## null اندازه‌گیری‌شده (هندسه‌پوش S612، گیت‌شرطی S346)
{
 "long": {
  "uncond_wr": 42.1812746002182,
  "perm_mean": 42.13219929281505,
  "perm_sd": 1.0908437998654854,
  "perm_max": 44.69582704876823,
  "perm_k": 500
 },
 "short": {
  "uncond_wr": 42.44748303127561,
  "perm_mean": 42.60383919950057,
  "perm_sd": 1.1124973385454224,
  "perm_max": 46.0261569416499,
  "perm_k": 500
 }
}
سقف ورود هر قرعهٔ null=2000 (محافظه‌کارانه) · K=500

## دروازه‌ها
H0:✗ H1:✗ H2:✗ H3:✓ H4:✗ H5:✓ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗

## یادداشت‌های موتور
- PF=0.418<1.3

## آرتیفکت‌ها
`results/_official_S622/{M1_rqs2.json, M1_trades.csv, null_model.json}`

— اقلیدس، بلوک S620–S629 📐
