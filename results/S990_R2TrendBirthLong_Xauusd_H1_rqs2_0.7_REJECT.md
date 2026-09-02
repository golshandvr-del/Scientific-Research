# S990 — R2TrendBirthLong — XAUUSD-H1 — REJECT (RQS2 v2.6 = 0.7)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S990_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py s990` · **رکوردها:** `results/_s990/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (45666 کندل)

## حکم موتور — عیناً
```
S990_R2TrendBirthLong_H1 | REJECT RQS2=0.7 | n=67 WR=40.30% PF=0.617 lift=-12.43pp z=-1.96 p_perm=0.974715 | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗
```
- side=long · SL=74.7 TP=74.7 پیپ · max_hold=48 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 52.73 · جایشگت K=500 mean=51.00 sd=6.36 max=69.23 · seed=990990
- n_trials=27 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗

## متریک‌ها (از موتور)
```
{
 "n_trades": 67,
 "win_rate": 40.3,
 "net_profit": -1519.2,
 "profit_factor": 0.617,
 "max_dd_pct": 19.57,
 "max_consec_losses": 5,
 "mcl_allowed": 15,
 "n_wins": 27,
 "top_win_share": 0.0383,
 "recovery_factor": -0.74,
 "expectancy_pip": -17.9569,
 "expectancy_at_2x_cost": -21.2569,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 74.693,
 "tp_pip": 74.693,
 "rr": 1.0,
 "breakeven_wr_cost": 52.21,
 "wr_excess_cost": -11.91,
 "null_ref_wr": 52.73,
 "skill_lift_pp": -12.43,
 "skill_z": -1.96,
 "skill_p_perm": 0.974715,
 "perm_max": 69.23,
 "perm_k": 500,
 "side_n": {
  "long": 67,
  "short": 0
 },
 "side_wr": {
  "long": 40.3
 },
 "side_lift_pp": {
  "long": -12.43
 },
 "prune_sides": [
  "long"
 ],
 "p_emp": 0.984703,
 "p_adj_bonferroni": 1.0,
 "z_obs": -2.038,
 "z_luck_bound": 2.03,
 "z_margin": -4.068,
 "n_trials": 27,
 "cal_nets": [
  207.9,
  -169.3,
  -777.1,
  -819.8
 ],
 "cal_counts": [
  17,
  15,
  23,
  12
 ],
 "cal_positive": 1,
 "cal_occupied": 4,
 "half_nets": [
  13.9,
  -1533.2
 ],
 "oos": {
  "n": 16,
  "wr": 25.0,
  "pf": 0.303,
  "net": -837.0,
  "wr_req": 52.21
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 57,
  "n_unjudgeable": 10,
  "n_counter": 17,
  "n_aligned": 40,
  "regime_lookback_days": 280.0,
  "wr_counter": 41.18,
  "exp_counter": -16.481,
  "wr_aligned": 32.5,
  "exp_aligned": -29.443,
  "h10_substitute": "small-counter-sample-adverse"
 },
 "n_required_h3": null
}
```

— لاگرانژ، دههٔ S990–S999
