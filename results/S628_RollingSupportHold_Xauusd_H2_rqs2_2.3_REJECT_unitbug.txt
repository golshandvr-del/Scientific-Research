# S628 — RollingSupportHold · XAUUSD-H2 · حکم رسمی موتور: REJECT (RQS2=2.3)

**دانشمند:** اقلیدس (بلوک S620–S629) · **تاریخ:** 2026-09-02
**پیش‌ثبت:** `results/S620-S629_PREREG2_OFFICIAL_ENGINE_ADJUDICATION.md` (commit 31bc0c61، قبل از اجرا) · n_trials=24 · seed=628628
**پیش‌ثبت اصلی جست‌وجو:** `results/S628_PREREG_*.md`

> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**
```
S628_RollingSupportHold_H2 | REJECT RQS2=2.3 | n=21 WR=33.33% exp=-2.81pip PF=0.353 lift=9.13pp z=0.93 p_emp=0.228837 oos={'n': 10, 'wr': 40.0, 'pf': 0.567, 'net': -346.3, 'wr_req': 59.34} | H0:✗ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗
```

## قاعدهٔ منجمد
سمت: long · SL=1.5×ATR100 (میانهٔ محقق‌شده 6.8 pip) · TP=1.5×SL · max_hold=64 · allow_overlap=False · ورود open کندل بعد (شبیه‌ساز محافظه‌کار)
دادهٔ کامل (47623 کندل) · split_bar=23811 (نیمهٔ اول اکتشاف، نیمهٔ دوم خارج‌ازنمونه)

## null اندازه‌گیری‌شده (هندسه‌پوش S612، گیت‌شرطی S346)
{
 "long": {
  "uncond_wr": 24.204771371769386,
  "perm_mean": 23.14285714285714,
  "perm_sd": 9.824899909081843,
  "perm_max": 52.38095238095239,
  "perm_k": 500
 }
}
سقف ورود هر قرعهٔ null=2000 (محافظه‌کارانه) · K=500

## دروازه‌ها
H0:✗ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗

## یادداشت‌های موتور
- PF=0.353<1.3
- n_wins=7<10 (winning tail unsampled)
- H10 FAIL (substitute): 4 counter-drift trades (<20) and their expectancy is negative (-3.419 pip) — the little adverse-regime evidence there is points against the edge.

## آرتیفکت‌ها
`results/_official_S628/{H2_rqs2.json, H2_trades.csv, null_model.json}`

— اقلیدس، بلوک S620–S629 📐
