# S1990 — AsianFreshLowFadeLong — XAUUSD-H1 — REJECT (RQS2 v2.6 = 6.1)

**دانشمند:** لاگرانژ (S1990–S1999) · **پیش‌ثبت:** `research/S1990_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s199x_official_runner.py s1990` · **رکوردها:** `results/_s1990/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (45666 کندل)

## حکم موتور — عیناً
```
S1990_AsianFreshLowFadeLong_H1 | REJECT RQS2=6.1 | n=180 WR=41.67% PF=0.965 lift=-0.7 z=-0.19 p_perm=0.575599 | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✓
```
- side=long · SL=74.7 TP=112.0 پیپ · max_hold=48 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 42.37 · جایشگت K=500 mean=42.34 sd=3.30 max=52.94 · seed=19901990
- n_trials=220 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✓

## متریک‌ها (از موتور)
```
{
 "n_trades": 180,
 "win_rate": 41.67,
 "net_profit": -375.6,
 "profit_factor": 0.965,
 "max_dd_pct": 16.63,
 "max_consec_losses": 9,
 "mcl_allowed": 16,
 "n_wins": 75,
 "top_win_share": 0.0137,
 "recovery_factor": -0.21,
 "expectancy_pip": -1.1218,
 "expectancy_at_2x_cost": -4.4218,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 74.693,
 "tp_pip": 112.04,
 "rr": 1.5,
 "breakeven_wr_cost": 41.77,
 "wr_excess_cost": -0.1,
 "null_ref_wr": 42.37,
 "skill_lift_pp": -0.7,
 "skill_z": -0.19,
 "skill_p_perm": 0.575599,
 "perm_max": 52.94,
 "perm_k": 500,
 "side_n": {
  "long": 180,
  "short": 0
 },
 "side_wr": {
  "long": 41.67
 },
 "side_lift_pp": {
  "long": -0.7
 },
 "prune_sides": [
  "long"
 ],
 "p_emp": 0.603482,
 "p_adj_bonferroni": 1.0,
 "z_obs": -0.191,
 "z_luck_bound": 2.797,
 "z_margin": -2.987,
 "n_trials": 220,
 "cal_nets": [
  -401.8,
  -10.0,
  -258.3,
  293.9
 ],
 "cal_counts": [
  28,
  50,
  43,
  59
 ],
 "cal_positive": 1,
 "cal_occupied": 4,
 "half_nets": [
  -391.0,
  25.2
 ],
 "oos": {
  "n": 65,
  "wr": 44.62,
  "pf": 1.105,
  "net": 427.5,
  "wr_req": 41.77
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 165,
  "n_unjudgeable": 15,
  "n_counter": 35,
  "n_aligned": 130,
  "regime_lookback_days": 280.0,
  "wr_counter": 60.0,
  "exp_counter": 34.047,
  "wr_aligned": 38.46,
  "exp_aligned": -6.725
 },
 "n_required_h3": null
}
```

— لاگرانژ، دههٔ S1990–S1999
