# S789 — DormancyGatedFreshExtreme (XAUUSD, H12) — REJECT 14.0

**پژوهشگر:** ابن هیثم · **مسیر چندگانگی:** C (اکتشاف روی ۶۰٪ نخست، داوری منجمد طبق پیش‌ثبت دسته‌ای a14c73b9)

**حکم رسمی موتور (`rqs2.compute_rqs2`, RQS2 v2.6) — دست‌نخورده:**

```
S789 verdict: REJECT  score: 14.0
H0 ✓ H1 ✓ H2 ✓ H3 ✗ H4 ✗ H5 ✗ H6 ✓ H7 ✗ H8 ✗ H9 ✓ H10 ✗
```

| مقدار | |
|---|---|
| فرضیه | پس از خمودگی (≥21 کندل بدون اکسترمم هم‌سو در پنجرهٔ W=144)، نخستین سقف/کف تازه یک «رویداد ساختاری نادر» است که تداوم می‌یابد (الگوی برندگان S950/S770: رویداد گسسته + درفت) |
| قاعدهٔ منجمد | سقف تازهٔ W=144 پس از ≥21 کندل خمودگی → long؛ کف تازه → short · SL=1.618·ATR89(t) پویا · TP=1.272·SL · max_hold 21 |
| داده | mt5_full کامل ۱۵.۶ سال · split_bar=4798 (مرز ۶۰٪ اکتشاف) |
| n_trades | 82 · side_n={'long': 48, 'short': 34} |
| WR / lift | 56.1% / +10.1pp نسبت به نول 46.04% |
| H3 | skill_z=1.31, p_perm=0.0947 (K=500, seed=789) |
| چندگانگی | n_trials=145 · p_emp=0.043217 · z_obs=1.828 vs z_luck=2.659 |
| اقتصاد | PF 1.451 · net $+1929 · maxDD 5.88% · expectancy 15.7 pip · MCL 6/10 |
| OOS | n=31 · WR 48.39% (نیاز 44.61) · PF 1.054 · net $94.6 |
| تقویم | 3.0/4.0 دوره مثبت · nets=[905.8, 97.4, 888.5, -147.5] |
| پای‌ها | side_wr={'long': 54.17, 'short': 58.82} · lift={'long': 5.14, 'short': 17.01} |

## پیشینهٔ اکتشاف (۱۴۵ عضو، فقط ۶۰٪ نخست)
- دور ۱ (۱۲۸ عضو): TF∈{H6,H8,H12,D1} × W∈{89,144} × D∈{21,34} × mode∈{cont,rev} × k∈{1.618,2.058} × RR∈{1.0,1.272}.
  همهٔ ۱۲ ردیف صدر «cont» بودند؛ بهترین: H12 W144 D21 cont z=2.28.
- دور ۲/۳ (یادداشت‌های خام):
```
S789 rounds 2-3 notes (discovery region = first 60% of full 15.6y mt5_full data)

Round 2 (1 member): FIFO pool cont k=1.618 rr=1.272 over H6(W89,D34)+H8(W89,D34)+H12(W144,D21):
n=131 wr=51.91 p0~44.80 alpha=+7.11 z=+1.64 net=+3191
T1 wr=50.0 a+5.2 | T2 wr=47.7 a+3.1 | T3 wr=58.1 a+13.1 (edge grows late — opposite of S787)
long n=68 wr=57.4 net+2492 | short n=63 wr=46.0 net+699 (short leg weak)

Round 3 (16 members): long-only leg, k=1.618:
best H6 W=89 D=34 rr=1.272: n=52 wr=53.8 a=+8.92 z=1.29
H8/H12 long-only ~noise; D1 n<30 skip.

Family accounting: 128 + 1 + 16 = 145 discovery trials. Best z anywhere = 2.28 (H12 W144 D21 cont).
No config reached z>=3.09. S789 closed INCOMPLETE; hold-out untouched.
```

**تفسیر ابن هیثم:** جهت اثر (تداوم پس از اکسترمم تازه) در همهٔ TFها منسجم بود اما
مقدار آن کوچک و رویداد بسیار نادر (n=82 در ۱۵.۶ سال H12). موتور آن را REJECT کرد:
دروازه‌های اقتصادی پایه (H0–H2) سبز اما H3/H4/H5/H7/H8/H10 قرمز — توان و پایداری
ناکافی. لایه بسته و hold-out سوخته است. درس: «کمیابی رویداد» به‌تنهایی ارزش ندارد؛
برندگان رویداد کمیاب **با اثر بزرگ** دارند (S950 lift دو‌رقمی)، نه کمیاب با اثر ۵pp.

فایل‌ها: `results/_s789/s789_final_result_H12.json` · `s789_trades_H12.csv` · `explore_discovery.csv` · `round23_notes.txt` · `strategies/s789_explore.py` · `strategies/s78x_final_adjudicator.py`
