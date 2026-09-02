# S626 — RoundNativeDriftLong · XAUUSD-H1 · حکم رسمی موتور: REJECT (RQS2=0.6)

**دانشمند:** اقلیدس (بلوک S620–S629) · **تاریخ:** 2026-09-02
**پیش‌ثبت:** `results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md` (commit 31bc0c61، قبل از اجرا) · n_trials=48 · seed=626626
**پیش‌ثبت اصلی جست‌وجو:** `results/S626_PREREG_*.md`

> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**
```
S626_RoundNativeDriftLong_H1 | REJECT RQS2=0.6 | n=87 WR=25.29% exp=-8.58pip PF=0.255 lift=1.66pp z=0.37 p_emp=0.39743 oos={'n': 64, 'wr': 20.31, 'pf': 0.213, 'net': -4087.4, 'wr_req': 55.46} | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗
```

## قاعدهٔ منجمد
سمت: long · SL=1.5×ATR100 (میانهٔ محقق‌شده 8.5 pip) · TP=1.5×SL · max_hold=96 · allow_overlap=False · ورود open کندل بعد (شبیه‌ساز محافظه‌کار)
دادهٔ کامل (91331 کندل) · split_bar=45665 (نیمهٔ اول اکتشاف، نیمهٔ دوم خارج‌ازنمونه)

## null اندازه‌گیری‌شده (هندسه‌پوش S612، گیت‌شرطی S346)
{
 "long": {
  "uncond_wr": 23.623116818967645,
  "perm_mean": 23.406896551724138,
  "perm_sd": 4.478019853014106,
  "perm_max": 37.93103448275862,
  "perm_k": 500
 }
}
سقف ورود هر قرعهٔ null=2000 (محافظه‌کارانه) · K=500

## دروازه‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗

## یادداشت‌های موتور
- PF=0.255<1.3
- H10 FAIL (substitute): 19 counter-drift trades (<20) and their expectancy is negative (-5.301 pip) — the little adverse-regime evidence there is points against the edge.

## آرتیفکت‌ها
`results/_official_S626/{H1_rqs2.json, H1_trades.csv, null_model.json}`

— اقلیدس، بلوک S620–S629 📐
