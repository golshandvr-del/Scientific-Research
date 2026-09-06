# S994 — SeasonalVolumeShockLong — XAUUSD-M30 — REJECT (RQS2 v2.6 = 6.6)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S994_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py s994` · **رکوردها:** `results/_s994/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (91073 کندل)

## حکم موتور — عیناً
```
S994_SeasonalVolumeShockLong_M30 | REJECT RQS2=6.6 | n=288 WR=44.79% PF=1.063 lift=3.58 z=1.24 p_perm=0.108375 | H0:✓ H1:✗ H2:✗ H3:✗ H4:✓ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✓
```
- side=long · SL=51.9 TP=77.9 پیپ · max_hold=64 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 40.62 · جایشگت K=500 mean=41.21 sd=2.49 max=48.61 · seed=994994
- n_trials=64 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✗ H2:✗ H3:✗ H4:✓ H5:✗ H6:✗ H7:✗ H8:✗ H9:✗ H10:✓

## متریک‌ها (از موتور)
```
{
 "n_trades": 288,
 "win_rate": 44.79,
 "net_profit": 1283.0,
 "profit_factor": 1.063,
 "max_dd_pct": 15.76,
 "max_consec_losses": 9,
 "mcl_allowed": 16,
 "n_wins": 129,
 "top_win_share": 0.0079,
 "recovery_factor": 0.61,
 "expectancy_pip": 2.5459,
 "expectancy_at_2x_cost": -0.7541,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 51.93,
 "tp_pip": 77.895,
 "rr": 1.5,
 "breakeven_wr_cost": 42.54,
 "wr_excess_cost": 2.25,
 "null_ref_wr": 41.21,
 "skill_lift_pp": 3.58,
 "skill_z": 1.24,
 "skill_p_perm": 0.108375,
 "perm_max": 48.61,
 "perm_k": 500,
 "side_n": {
  "long": 288,
  "short": 0
 },
 "side_wr": {
  "long": 44.79
 },
 "side_lift_pp": {
  "long": 3.58
 },
 "prune_sides": [],
 "p_emp": 0.120161,
 "p_adj_bonferroni": 1.0,
 "z_obs": 1.235,
 "z_luck_bound": 2.369,
 "z_margin": -1.134,
 "n_trials": 64,
 "cal_nets": [
  2402.9,
  429.6,
  -666.1,
  -650.3
 ],
 "cal_counts": [
  174,
  59,
  37,
  18
 ],
 "cal_positive": 2,
 "cal_occupied": 4,
 "half_nets": [
  2966.6,
  -1280.2
 ],
 "oos": {
  "n": 23,
  "wr": 30.43,
  "pf": 0.585,
  "net": -687.2,
  "wr_req": 42.54
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 231,
  "n_unjudgeable": 57,
  "n_counter": 32,
  "n_aligned": 199,
  "regime_lookback_days": 280.0,
  "wr_counter": 43.75,
  "exp_counter": 1.568,
  "wr_aligned": 43.22,
  "exp_aligned": 0.597
 },
 "n_required_h3": 1802.3
}
```

— لاگرانژ، دههٔ S990–S999
