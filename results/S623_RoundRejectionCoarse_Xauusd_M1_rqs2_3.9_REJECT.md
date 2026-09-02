# S623 — RoundRejectionCoarse · XAUUSD-M1 · حکم رسمی موتور: REJECT (RQS2=3.9)

**دانشمند:** اقلیدس (بلوک S620–S629) · **تاریخ:** 2026-09-02
**پیش‌ثبت:** `results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md` (commit 31bc0c61 + ADDENDUM-1 9ba370d7، قبل از اجرا) · n_trials=48 · seed=623623
**پیش‌ثبت اصلی جست‌وجو:** `results/S623_PREREG_*.md`

> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**
```
S623_RoundRejectionCoarse_M1 | REJECT RQS2=3.9 | n=5772 WR=46.07% exp=-0.59pip PF=0.922 lift=1.38pp z=1.31 p_emp=0.018214 oos={'n': 3443, 'wr': 46.85, 'pf': 0.995, 'net': -575.3, 'wr_req': 41.37} | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗
```

## قاعدهٔ منجمد
سمت: long · SL=16.0×ATR100 (میانهٔ محقق‌شده 96.7 pip) · TP=1.5×SL · max_hold=960 · allow_overlap=False · ورود open کندل بعد (شبیه‌ساز محافظه‌کار)
دادهٔ کامل (5000000 کندل) · split_bar=2500000 (نیمهٔ اول اکتشاف، نیمهٔ دوم خارج‌ازنمونه)

## null اندازه‌گیری‌شده (هندسه‌پوش S612، گیت‌شرطی S346)
{
 "long": {
  "uncond_wr": 44.68948299178196,
  "perm_mean": 43.839536089003055,
  "perm_sd": 1.0516494750845575,
  "perm_max": 47.15840386940749,
  "perm_k": 500
 }
}
سقف ورود هر قرعهٔ null=2000 (محافظه‌کارانه) · K=500

## دروازه‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗

## یادداشت‌های موتور
- PF=0.922<1.3

## آرتیفکت‌ها
`results/_official_S623/{M1_rqs2.json, M1_trades.csv, null_model.json}`

— اقلیدس، بلوک S620–S629 📐
