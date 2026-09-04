# S993 — ErShockCalmShort — XAUUSD-H1 — REJECT (RQS2 v2.6 = 14.1)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S993_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py s993` · **رکوردها:** `results/_s993/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (45666 کندل)

## حکم موتور — عیناً
```
S993_ErShockCalmShort_H1 | REJECT RQS2=14.1 | n=46 WR=45.65% PF=1.1 lift=6.46 z=0.9 p_perm=0.18485 | H0:✓ H1:✗ H2:✓ H3:✗ H4:✓ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✓
```
- side=short · SL=74.7 TP=112.0 پیپ · max_hold=48 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 38.28 · جایشگت K=500 mean=39.20 sd=6.43 max=64.58 · seed=993993
- n_trials=200 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✗ H2:✓ H3:✗ H4:✓ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✓

## متریک‌ها (از موتور)
```
{
 "n_trades": 46,
 "win_rate": 45.65,
 "net_profit": 260.8,
 "profit_factor": 1.1,
 "max_dd_pct": 6.52,
 "max_consec_losses": 6,
 "mcl_allowed": 12,
 "n_wins": 21,
 "top_win_share": 0.0497,
 "recovery_factor": 0.38,
 "expectancy_pip": 5.171,
 "expectancy_at_2x_cost": 1.871,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 74.693,
 "tp_pip": 112.04,
 "rr": 1.5,
 "breakeven_wr_cost": 41.77,
 "wr_excess_cost": 3.88,
 "null_ref_wr": 39.2,
 "skill_lift_pp": 6.46,
 "skill_z": 0.9,
 "skill_p_perm": 0.18485,
 "perm_max": 64.58,
 "perm_k": 500,
 "side_n": {
  "long": 0,
  "short": 46
 },
 "side_wr": {
  "short": 45.65
 },
 "side_lift_pp": {
  "short": 6.46
 },
 "prune_sides": [],
 "p_emp": 0.226524,
 "p_adj_bonferroni": 1.0,
 "z_obs": 0.897,
 "z_luck_bound": 2.766,
 "z_margin": -1.868,
 "n_trials": 200,
 "cal_nets": [
  -693.0,
  946.9,
  333.7,
  -224.2
 ],
 "cal_counts": [
  8,
  15,
  16,
  7
 ],
 "cal_positive": 2,
 "cal_occupied": 4,
 "half_nets": [
  184.1,
  86.1
 ],
 "oos": {
  "n": 11,
  "wr": 45.45,
  "pf": 1.139,
  "net": 89.0,
  "wr_req": 41.77
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 42,
  "n_unjudgeable": 4,
  "n_counter": 29,
  "n_aligned": 13,
  "regime_lookback_days": 280.0,
  "wr_counter": 51.72,
  "exp_counter": 15.288,
  "wr_aligned": 46.15,
  "exp_aligned": 8.191
 },
 "n_required_h3": 545.8
}
```

— لاگرانژ، دههٔ S990–S999
