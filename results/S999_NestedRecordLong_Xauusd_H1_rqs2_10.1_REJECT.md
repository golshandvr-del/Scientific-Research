# S999 — NestedRecordLong — XAUUSD-H1 — REJECT (RQS2 v2.6 = 10.1)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S999_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py s999` · **رکوردها:** `results/_s999/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (45666 کندل)

## حکم موتور — عیناً
```
S999_NestedRecordLong_H1 | REJECT RQS2=10.1 | n=303 WR=46.53% PF=1.177 lift=0.62 z=0.22 p_perm=0.414109 | H0:✓ H1:✗ H2:✓ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✗
```
- side=long · SL=74.7 TP=112.0 پیپ · max_hold=48 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 45.91 · جایشگت K=500 mean=45.60 sd=2.09 max=51.66 · seed=999999
- n_trials=48 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✗ H2:✓ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✗

## متریک‌ها (از موتور)
```
{
 "n_trades": 303,
 "win_rate": 46.53,
 "net_profit": 3781.8,
 "profit_factor": 1.177,
 "max_dd_pct": 18.01,
 "max_consec_losses": 7,
 "mcl_allowed": 15,
 "n_wins": 141,
 "top_win_share": 0.0072,
 "recovery_factor": 1.48,
 "expectancy_pip": 8.5066,
 "expectancy_at_2x_cost": 5.2066,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 74.693,
 "tp_pip": 112.04,
 "rr": 1.5,
 "breakeven_wr_cost": 41.77,
 "wr_excess_cost": 4.77,
 "null_ref_wr": 45.91,
 "skill_lift_pp": 0.62,
 "skill_z": 0.22,
 "skill_p_perm": 0.414109,
 "perm_max": 51.66,
 "perm_k": 500,
 "side_n": {
  "long": 303,
  "short": 0
 },
 "side_wr": {
  "long": 46.53
 },
 "side_lift_pp": {
  "long": 0.62
 },
 "prune_sides": [
  "long"
 ],
 "p_emp": 0.436699,
 "p_adj_bonferroni": 1.0,
 "z_obs": 0.217,
 "z_luck_bound": 2.261,
 "z_margin": -2.044,
 "n_trials": 48,
 "cal_nets": [
  3458.7,
  -1309.2,
  918.4,
  802.4
 ],
 "cal_counts": [
  68,
  42,
  65,
  128
 ],
 "cal_positive": 3,
 "cal_occupied": 4,
 "half_nets": [
  1680.7,
  1828.3
 ],
 "oos": {
  "n": 139,
  "wr": 44.6,
  "pf": 1.109,
  "net": 914.6,
  "wr_req": 41.77
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 272,
  "n_unjudgeable": 31,
  "n_counter": 28,
  "n_aligned": 244,
  "regime_lookback_days": 280.0,
  "wr_counter": 35.71,
  "exp_counter": -11.303,
  "wr_aligned": 46.31,
  "exp_aligned": 8.258
 },
 "n_required_h3": 61446.1
}
```

— لاگرانژ، دههٔ S990–S999
