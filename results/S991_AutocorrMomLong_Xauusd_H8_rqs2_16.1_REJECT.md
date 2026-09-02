# S991 — AutocorrMomLong — XAUUSD-H8 — REJECT (RQS2 v2.6 = 16.1)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S991_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py s991` · **رکوردها:** `results/_s991/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم (5989 کندل)

## حکم موتور — عیناً
```
S991_AutocorrMomLong_H8 | REJECT RQS2=16.1 | n=98 WR=63.27% PF=1.576 lift=-5.78 z=-1.24 p_perm=0.89218 | H0:✓ H1:✓ H2:✓ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✓
```
- side=long · SL=221.0 TP=221.0 پیپ · max_hold=21 · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = 69.05 · جایشگت K=500 mean=58.75 sd=3.69 max=70.00 · seed=991991
- n_trials=159 (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
H0:✓ H1:✓ H2:✓ H3:✗ H4:✗ H5:✗ H6:✗ H7:✗ H8:✗ H9:✓ H10:✓

## متریک‌ها (از موتور)
```
{
 "n_trades": 98,
 "win_rate": 63.27,
 "net_profit": 2592.6,
 "profit_factor": 1.576,
 "max_dd_pct": 11.42,
 "max_consec_losses": 7,
 "mcl_allowed": 9,
 "n_wins": 62,
 "top_win_share": 0.0169,
 "recovery_factor": 1.6,
 "expectancy_pip": 51.4693,
 "expectancy_at_2x_cost": 48.1693,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 221.043,
 "tp_pip": 221.043,
 "rr": 1.0,
 "breakeven_wr_cost": 50.75,
 "wr_excess_cost": 12.52,
 "null_ref_wr": 69.05,
 "skill_lift_pp": -5.78,
 "skill_z": -1.24,
 "skill_p_perm": 0.89218,
 "perm_max": 70.0,
 "perm_k": 500,
 "side_n": {
  "long": 98,
  "short": 0
 },
 "side_wr": {
  "long": 63.27
 },
 "side_lift_pp": {
  "long": -5.78
 },
 "prune_sides": [
  "long"
 ],
 "p_emp": 0.909526,
 "p_adj_bonferroni": 1.0,
 "z_obs": -1.238,
 "z_luck_bound": 2.69,
 "z_margin": -3.928,
 "n_trials": 159,
 "cal_nets": [
  229.1,
  351.0,
  2879.5,
  -762.1
 ],
 "cal_counts": [
  14,
  16,
  46,
  22
 ],
 "cal_positive": 3,
 "cal_occupied": 4,
 "half_nets": [
  644.8,
  1820.4
 ],
 "oos": {
  "n": 40,
  "wr": 45.0,
  "pf": 0.813,
  "net": -439.5,
  "wr_req": 50.75
 },
 "max_concurrency": 1,
 "counter_drift": {
  "n_judgeable": 91,
  "n_unjudgeable": 7,
  "n_counter": 18,
  "n_aligned": 73,
  "regime_lookback_days": 280.0,
  "wr_counter": 83.33,
  "exp_counter": 144.062,
  "wr_aligned": 57.53,
  "exp_aligned": 27.609,
  "h10_substitute": "small-counter-sample-nonnegative"
 },
 "n_required_h3": null
}
```

— لاگرانژ، دههٔ S990–S999
