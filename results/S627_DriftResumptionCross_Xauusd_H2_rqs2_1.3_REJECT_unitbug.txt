# S627 — DriftResumptionCross · XAUUSD-H2 · حکم رسمی موتور: REJECT (RQS2=1.3)

**دانشمند:** اقلیدس (بلوک S620–S629) · **تاریخ:** 2026-09-02
**پیش‌ثبت:** `results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md` (commit 31bc0c61، قبل از اجرا) · n_trials=12 · seed=627627
**پیش‌ثبت اصلی جست‌وجو:** `results/S627_PREREG_*.md`

> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**
```
S627_DriftResumptionCross_H2 | REJECT RQS2=1.3 | n=508 WR=32.68% exp=-8.28pip PF=0.23 lift=1.57pp z=0.76 p_emp=0.236698 oos={'n': 284, 'wr': 32.04, 'pf': 0.242, 'net': -8133.8, 'wr_req': 63.87} | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗
```

## قاعدهٔ منجمد
سمت: long · SL=2.0×ATR100 (میانهٔ محقق‌شده 11.9 pip) · TP=1.0×SL · max_hold=64 · allow_overlap=False · ورود open کندل بعد (شبیه‌ساز محافظه‌کار)
دادهٔ کامل (47623 کندل) · split_bar=23811 (نیمهٔ اول اکتشاف، نیمهٔ دوم خارج‌ازنمونه)

## null اندازه‌گیری‌شده (هندسه‌پوش S612، گیت‌شرطی S346)
{
 "long": {
  "uncond_wr": 31.106161841128433,
  "perm_mean": 29.73070100836669,
  "perm_sd": 1.9005632946556572,
  "perm_max": 35.108481262327416,
  "perm_k": 500
 }
}
سقف ورود هر قرعهٔ null=2000 (محافظه‌کارانه) · K=500

## دروازه‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗

## یادداشت‌های موتور
- PF=0.230<1.3

## آرتیفکت‌ها
`results/_official_S627/{H2_rqs2.json, H2_trades.csv, null_model.json}`

— اقلیدس، بلوک S620–S629 📐
