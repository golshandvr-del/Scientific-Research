# S996 — OlsChannelBreakPool — XAUUSD {H4,H6,H8} — REJECT (RQS2 v2.6 = 11.6)

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S996_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم) · **runner:** `strategies/s996_ols_channel_pool.py`
**رکوردها:** `results/_s996/` · **داده:** `data/mt5_full/` ۱۵.۶ سال، نیمهٔ دوم هر کارت · ماشین استخر: `engine/rqs2_pool` (دست‌نخورده)

## حکم موتور — عیناً
```
S996_OlsChannelBreakPool (n_trials=215) | REJECT RQS2=11.6 | n=180 WR=53.89 PF=1.112 lift=3.51 z=0.71 p_perm=0.237364 | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✓ H7:✗ H8:✗ H9:✓ H10:✗
S996 STRESS (n_trials=1000) | REJECT RQS2=11.6 | n=180 WR=53.89 PF=1.112 lift=3.51 z=0.71 p_perm=0.237364 | H0:✓ H1:✗ H2:✗ H3:✗ H4:✗ H5:✗ H6:✓ H7:✗ H8:✗ H9:✓ H10:✗
```
## قاعده (منجمد)
OLS روی close در پنجرهٔ W=55؛ zres=(close−fit)/σ_e؛ رویداد = عبورِ تازهٔ zres از ±2.0 هم‌جهت با شیب؛ SL=1.5×ATR100 (میانهٔ کارت)، TP=SL؛ max_hold H4:30/H6:24/H8:21؛ FIFO تقویمی.

## کارت‌ها (نیمهٔ دوم)
| card | n | WR | uncond | holdout lift | first-half lift | SL pip | share |
|---|---|---|---|---|---|---|---|
| H4-long | 129 | 58.91 | 51.24 | +7.68 | +13.90 | 149.1 | 0.72 |
| H4-short | 69 | 46.38 | 45.43 | +0.94 | +7.41 | 149.1 | 0.00 |
| H6-long | 97 | 60.82 | 54.71 | +6.11 | +5.30 | 187.1 | 0.00 |
| H6-short | 38 | 31.58 | 45.94 | -14.36 | +16.98 | 187.1 | 0.19 |
| H8-short | 24 | 50.00 | 43.66 | +6.34 | +17.21 | 221.0 | 0.09 |
- استخر: n_before=191 n_after=180 · used=[{'card': 'H8-short', 'lift': 17.21, 'n': 24}, {'card': 'H6-short', 'lift': 16.98, 'n': 38}, {'card': 'H4-long', 'lift': 13.9, 'n': 129}] · dropped=[{'card': 'H4-short', 'lift': 7.41, 'reason': 'dilutes pool (lowers z_proxy)'}, {'card': 'H6-long', 'lift': 5.3, 'reason': 'dilutes pool (lowers z_proxy)'}]
- نول آمیخته: {"long": {"uncond_wr": 51.23900879296562, "perm_mean": 52.43355466232932, "perm_sd": 4.370934589395679, "perm_max": 65.57377049180327, "perm_k": 500}, "short": {"uncond_wr": 45.17710936826682, "perm_mean": 42.89038152215564, "perm_sd": 6.281506403560347, "perm_max": 70.83333333333334, "perm_k": 500}}
- SL/TP وزنی: 163.1/163.1 · seed=996996 · n_trials=215 (۲۱۰ سلول + ۵ تصمیم انجماد)

## متریک‌ها (رسمی)
```
{
 "n_trades": 180,
 "win_rate": 53.89,
 "net_profit": 1031.6,
 "profit_factor": 1.112,
 "max_dd_pct": 5.67,
 "max_consec_losses": 5,
 "mcl_allowed": 12,
 "n_wins": 97,
 "top_win_share": 0.0142,
 "recovery_factor": 1.57,
 "expectancy_pip": 8.9222,
 "expectancy_at_2x_cost": 5.6222,
 "cost_pip": 3.3,
 "spread_pip": 3.3,
 "sl_pip": 163.082,
 "tp_pip": 163.082,
 "rr": 1.0,
 "breakeven_wr_cost": 51.01,
 "wr_excess_cost": 2.88,
 "null_ref_wr": 50.38,
 "skill_lift_pp": 3.51,
 "skill_z": 0.71,
 "skill_p_perm": 0.237364,
 "perm_max": 67.06,
 "perm_k": 500,
 "p_emp": 0.192826,
 "p_adj_bonferroni": 1.0,
 "z_obs": 0.942,
 "z_luck_bound": 2.789,
 "z_margin": -1.847,
 "n_trials": 215,
 "cal_positive": 4,
 "cal_occupied": 4,
 "max_concurrency": 1,
 "n_required_h3": 1935.9
}
```
notes: ['PF=1.112<1.3']

— لاگرانژ، دههٔ S990–S999
