# S992 — ErShockLong — XAUUSD-H1 — REJECT (RQS2 v2.6 = 17.8)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S992_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py s992` · **رکوردها:** `results/_s992/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (45666 کندل)

## حکم موتور — عیناً
```
S992_ErShockLong_H1 | REJECT RQS2=17.8 | n=111 WR=48.65% PF=1.27 lift=6.07 z=1.29 p_perm=0.097972 | H0:✓ H1:✗ H2:✓ H3:✗ H4:✓ H5:✗ H6:✓ H7:✗ H8:✗ H9:✓ H10:✓
```
- side=long · SL=74.7 TP=112.0 پیپ · max_hold=48 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 42.58 · جایشگت K=500 mean=42.55 sd=4.39 max=55.96 · seed=992992
- n_trials=146 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✗ H2:✓ H3:✗ H4:✓ H5:✗ H6:✓ H7:✗ H8:✗ H9:✓ H10:✓

## متریک‌ها (از موتور)
```
{
 "n_trades": 111,
 "win_rate": 48.65,
 "net_profit": 1810.0,
 "profit_factor": 1.27,
 "max_dd_pct": 7.41,
 "max_consec_losses": 4,
 "mcl_allowed": 13,
 "n_wins": 54,
 "top_win_share": 0.0189,
 "recovery_factor": 1.94,
 "expectancy_pip": 11.7897,
 "expectancy_at_2x_cost": 8.4897,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 74.693,
 "tp_pip": 112.04,
 "rr": 1.5,
 "breakeven_wr_cost": 41.77,
 "wr_excess_cost": 6.88,
 "null_ref_wr": 42.58,
 "skill_lift_pp": 6.07,
 "skill_z": 1.29,
 "skill_p_perm": 0.097972,
 "perm_max": 55.96,
 "perm_k": 500,
 "side_n": {
  "long": 111,
  "short": 0
 },
 "side_wr": {
  "long": 48.65
 },
 "side_lift_pp": {
  "long": 6.07
 },
 "prune_sides": [],
 "p_emp": 0.115927,
 "p_adj_bonferroni": 1.0,
 "z_obs": 1.293,
 "z_luck_bound": 2.661,
 "z_margin": -1.368,
 "n_trials": 146,
 "cal_nets": [
  559.3,
  388.6,
  648.8,
  142.7
 ],
 "cal_counts": [
  22,
  20,
  37,
  32
 ],
 "cal_positive": 4,
 "cal_occupied": 4,
 "half_nets": [
  974.2,
  789.4
 ],
 "oos": {
  "n": 38,
  "wr": 44.74,
  "pf": 1.108,
  "net": 245.4,
  "wr_req": 41.77
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 105,
  "n_unjudgeable": 6,
  "n_counter": 18,
  "n_aligned": 87,
  "regime_lookback_days": 280.0,
  "wr_counter": 44.44,
  "exp_counter": 4.999,
  "wr_aligned": 48.28,
  "exp_aligned": 12.154,
  "h10_substitute": "small-counter-sample-nonnegative"
 },
 "n_required_h3": 633.7
}
```

— لاگرانژ، دههٔ S990–S999
