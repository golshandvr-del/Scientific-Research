# S998 — CurvatureReigniteShort — XAUUSD-H4 — REJECT (RQS2 v2.6 = 0.0)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S998_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py s998` · **رکوردها:** `results/_s998/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (11927 کندل)

## حکم موتور — عیناً
```
S998_CurvatureReigniteShort_H4 | REJECT RQS2=0.0 | n=687 WR=36.68% PF=0.8 lift=-0.05 z=-0.03 p_perm=0.51041 | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗
```
- side=short · SL=149.1 TP=223.7 پیپ · max_hold=30 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 36.73 · جایشگت K=500 mean=36.26 sd=1.21 max=39.90 · seed=998998
- n_trials=216 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✗

## متریک‌ها (از موتور)
```
{
 "n_trades": 687,
 "win_rate": 36.68,
 "net_profit": -5770.7,
 "profit_factor": 0.8,
 "max_dd_pct": 57.75,
 "max_consec_losses": 11,
 "mcl_allowed": 22,
 "n_wins": 252,
 "top_win_share": 0.0042,
 "recovery_factor": -1.0,
 "expectancy_pip": -18.2205,
 "expectancy_at_2x_cost": -21.5205,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 149.125,
 "tp_pip": 223.688,
 "rr": 1.5,
 "breakeven_wr_cost": 40.89,
 "wr_excess_cost": -4.2,
 "null_ref_wr": 36.73,
 "skill_lift_pp": -0.05,
 "skill_z": -0.03,
 "skill_p_perm": 0.51041,
 "perm_max": 39.9,
 "perm_k": 500,
 "side_n": {
  "long": 0,
  "short": 687
 },
 "side_wr": {
  "short": 36.68
 },
 "side_lift_pp": {
  "short": -0.05
 },
 "prune_sides": [
  "short"
 ],
 "p_emp": 0.52618,
 "p_adj_bonferroni": 1.0,
 "z_obs": -0.026,
 "z_luck_bound": 2.791,
 "z_margin": -2.817,
 "n_trials": 216,
 "cal_nets": [
  -2577.8,
  -96.0,
  -2187.0,
  -2819.9
 ],
 "cal_counts": [
  122,
  156,
  132,
  277
 ],
 "cal_positive": 0,
 "cal_occupied": 4,
 "half_nets": [
  -2559.2,
  -4276.4
 ],
 "oos": {
  "n": 312,
  "wr": 35.26,
  "pf": 0.789,
  "net": -3622.8,
  "wr_req": 40.89
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 649,
  "n_unjudgeable": 38,
  "n_counter": 548,
  "n_aligned": 101,
  "regime_lookback_days": 280.0,
  "wr_counter": 37.77,
  "exp_counter": -13.454,
  "wr_aligned": 33.66,
  "exp_aligned": -25.887
 },
 "n_required_h3": null
}
```

— لاگرانژ، دههٔ S990–S999
