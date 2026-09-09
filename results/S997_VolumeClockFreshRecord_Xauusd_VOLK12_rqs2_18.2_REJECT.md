# S997 — VolumeClockFreshRecord — XAUUSD volume bars K=12 (from M5) — REJECT (RQS2 v2.6 = 18.2)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S997_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم) · **runner:** `strategies/s997_volume_clock_runner.py`
**رکوردها:** `results/_s997/` · **داده:** `data/mt5_full/XAUUSD_M5.csv` ۱۵.۶ سال؛ نیمهٔ دوم (544787 کندل M5 → 23798 کندل حجمی)

## حکم موتور — عیناً
```
S997_VolumeClockFreshRecord_VOLK12 | REJECT RQS2=18.2 | n=790 WR=45.06% PF=1.146 lift=3.83 z=1.98 p_perm=0.023987 | H0:✓ H1:✗ H2:✓ H3:✗ H4:✗ H5:✗ H6:✓ H7:✗ H8:✗ H9:✓ H10:✓
```
- قاعده: کندل حجمی (آستانه = median(حجم روزانهٔ ۲۰ روز قبل)/12)؛ W=90 رکورد تازهٔ close (لانگ) / کف تازه (شورت)؛ SL=111.4 TP=167.0 پیپ؛ max_hold=40؛ allow_overlap=False
- نول: {"long": {"uncond_wr": 41.674733785091966, "perm_mean": 43.30419034309237, "perm_sd": 1.72709426807917, "perm_max": 48.17629179331307, "perm_k": 500}, "short": {"uncond_wr": 37.67409470752089, "perm_mean": 36.93194709944513, "perm_sd": 2.2923473212206797, "perm_max": 44.16243654822335, "perm_k": 500}} · seed=997997 · n_trials=50
- P1 (ساعت حجم > ساعت زمانی) در اکتشاف نیمهٔ اول در K=6 رد شد، در K=12 حاشیه‌ای.

## گیت‌ها
H0:✓ H1:✗ H2:✓ H3:✗ H4:✗ H5:✗ H6:✓ H7:✗ H8:✗ H9:✓ H10:✓

## متریک‌ها (از موتور)
```
{
 "n_trades": 790,
 "win_rate": 45.06,
 "net_profit": 8979.1,
 "profit_factor": 1.146,
 "max_dd_pct": 19.48,
 "max_consec_losses": 9,
 "mcl_allowed": 17,
 "n_wins": 356,
 "top_win_share": 0.0029,
 "recovery_factor": 2.13,
 "expectancy_pip": 10.1309,
 "expectancy_at_2x_cost": 6.8309,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 111.359,
 "tp_pip": 167.039,
 "rr": 1.5,
 "breakeven_wr_cost": 41.19,
 "wr_excess_cost": 3.88,
 "null_ref_wr": 41.24,
 "skill_lift_pp": 3.83,
 "skill_z": 1.98,
 "skill_p_perm": 0.023987,
 "perm_max": 46.7,
 "perm_k": 500,
 "p_emp": 0.015844,
 "p_adj_bonferroni": 0.792198,
 "z_obs": 2.184,
 "z_luck_bound": 2.276,
 "z_margin": -0.092,
 "n_trials": 50,
 "cal_positive": 3,
 "cal_occupied": 4,
 "max_concurrency": 1,
 "n_required_h3": 1580.7
}
```
— لاگرانژ، دههٔ S990–S999
