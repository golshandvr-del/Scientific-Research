# S995 — SeasonalRangeShockLong — XAUUSD-H2 — REJECT (RQS2 v2.6 = 13.7)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S995_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py s995` · **رکوردها:** `results/_s995/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (23812 کندل)

## حکم موتور — عیناً
```
S995_SeasonalRangeShockLong_H2 | REJECT RQS2=13.7 | n=97 WR=44.33% PF=1.128 lift=1.12 z=0.22 p_perm=0.411879 | H0:✓ H1:✗ H2:✓ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✓
```
- side=long · SL=104.3 TP=156.5 پیپ · max_hold=40 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 42.28 · جایشگت K=500 mean=43.21 sd=4.97 max=59.00 · seed=995995
- n_trials=160 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✗ H2:✓ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✓

## متریک‌ها (از موتور)
```
{
 "n_trades": 97,
 "win_rate": 44.33,
 "net_profit": 769.1,
 "profit_factor": 1.128,
 "max_dd_pct": 9.49,
 "max_consec_losses": 8,
 "mcl_allowed": 14,
 "n_wins": 43,
 "top_win_share": 0.0233,
 "recovery_factor": 0.68,
 "expectancy_pip": 8.6331,
 "expectancy_at_2x_cost": 5.3331,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 104.314,
 "tp_pip": 156.471,
 "rr": 1.5,
 "breakeven_wr_cost": 41.27,
 "wr_excess_cost": 3.06,
 "null_ref_wr": 43.21,
 "skill_lift_pp": 1.12,
 "skill_z": 0.22,
 "skill_p_perm": 0.411879,
 "perm_max": 59.0,
 "perm_k": 500,
 "side_n": {
  "long": 97,
  "short": 0
 },
 "side_wr": {
  "long": 44.33
 },
 "side_lift_pp": {
  "long": 1.12
 },
 "prune_sides": [
  "long"
 ],
 "p_emp": 0.450374,
 "p_adj_bonferroni": 1.0,
 "z_obs": 0.223,
 "z_luck_bound": 2.692,
 "z_margin": -2.469,
 "n_trials": 160,
 "cal_nets": [
  116.4,
  191.4,
  1320.0,
  -750.2
 ],
 "cal_counts": [
  31,
  15,
  29,
  22
 ],
 "cal_positive": 3,
 "cal_occupied": 4,
 "half_nets": [
  312.4,
  477.1
 ],
 "oos": {
  "n": 24,
  "wr": 25.0,
  "pf": 0.469,
  "net": -937.7,
  "wr_req": 41.27
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 86,
  "n_unjudgeable": 11,
  "n_counter": 12,
  "n_aligned": 74,
  "regime_lookback_days": 280.0,
  "wr_counter": 50.0,
  "exp_counter": 22.778,
  "wr_aligned": 41.89,
  "exp_aligned": 1.634,
  "h10_substitute": "small-counter-sample-nonnegative"
 },
 "n_required_h3": 18672.3
}
```

— لاگرانژ، دههٔ S990–S999
