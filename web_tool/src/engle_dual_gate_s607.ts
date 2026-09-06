// ---------------------------------------------------------------------------
// S607 — «شوکِ انگل با دو گیتِ متعامد» (Engle Shock · Dual Orthogonal Gate)
// XAUUSD {D1 خام · H8-DUAL · H6-DUAL} — **سه کارتِ ACCEPT**
//
// حکمِ رسمیِ موتور (سند:
//   results/S607_EngleShockDualGatePool_Xauusd_D1H8H6_rqs2_83.1_ACCEPT.md):
//     S607-DUAL OFFICIAL (n_trials=5177) | ACCEPT RQS2=83.1
//       n=283 · WR=60.07٪ · PF=1.609 · lift=+12.50pp · z=4.21 · p_perm=1.3e−05
//       maxDD=7.47٪ · Expectancy=+43.5 pip · net=+$10,217 · H0..H10 **همه ✓**
//     S607-DUAL STRESS  (n_trials=8000) | ACCEPT RQS2=82.9 · z_margin=+0.405σ
//   ⇒ **بالاترین نمرهٔ دههٔ S600–S609** (S602 76.4 · S604 80.7 · S606 80.1).
//
// فیزیکِ لایه — **دو بُعدِ مستقلِ اطلاعات روی یک شوک**:
//   ① شوکِ استانداردشدهٔ ARCH (Engle 1982): σ²_t = λσ²_{t−1} + (1−λ)r²_{t−1}
//      با λ=0.94 (RiskMetrics/IGARCH بی‌ثابت) و z_t = r_t/σ_t. رویدادِ ورود
//      |z| ≥ 2.618 روی کندلِ **بسته**، جهت = follow (هم‌جهتِ خودِ شوک).
//   ② گیتِ روند (MOP 2012 · Time-Series Momentum): شوک فقط وقتی معتبر است که
//      با رانشِ K-کندلیِ **علّی** هم‌جهت باشد ⇒ ارثی از S604.
//   ③ گیتِ رژیمِ σ (Andersen–Bollerslev): شوک فقط در بازارِ **آرام** معتبر است،
//      یعنی σ_t ≤ median(σ_{t−W..t−1}) ⇒ ارثی از S606/S605.
//   کشفِ کلیدیِ سند: نسبتِ هم‌خطی PR_dual/(PR_drift·PR_calm) ≈ ۱.۰
//   (H8=1.072 · H6=1.011) ⇒ دو گیت **مستقل**‌اند، پس اطلاعاتشان جمع‌پذیر است
//   نه تکراری: لیفتِ H6 خام +5.87pp → با گیتِ روند +12.8 → dual **+15.74pp**.
//
// ⚠️ **صفر پارامترِ آزاد.** هیچ عددِ این لایه در S607 جست‌وجو نشده؛ همه از
//    والدها منجمد آمده‌اند: z_thr/mode/sl_k/rr/hold از برندهٔ S840
//    (results/_scan_S840/<TF>.json::is_winner)، K از S604، W از S605/S606.
//    ⇒ هیچ چندگانگیِ نویی تحمیل نشده (ضدِ اشتباهِ رایجِ #۸).
//
// ⚠️⚠️ **قانونِ MTF — قلمروِ دقیقاً سه کارت.** پیش‌ثبت چهار کارت را نامزد کرد
//    (D1, H8, H12, H6) ولی **انتخاب‌گرِ رسمی H12 را با حاشیهٔ ۰.۱۵ حذف کرد**:
//      · XAUUSD-D1 → ✅ عضوِ استخر (خام، بی‌گیت) · n=87 · WR=64.37٪ · lift=+16.69
//      · XAUUSD-H8 → ✅ عضوِ استخر (DUAL · K=180 · W=233) · n=131 · WR=66.41٪ · lift=+16.61
//      · XAUUSD-H6 → ✅ عضوِ استخر (DUAL · K=240 · W=233) · n=166 · WR=60.84٪ · lift=+15.74
//      · XAUUSD-H12 → ❌ **حذف‌شده** (با آنکه n=167/WR=62.28 داشت) ⇒ **وصل نمی‌شود**
//    مدرکِ ماشینی: results/_s607_dual_gate/verdict.json::members دقیقاً سه کارتِ
//    اول است، و results/_s607_parity/H12.json با `official_member=false` ذخیره
//    شده تا نشستِ آینده نتواند بی‌صدا کارتِ ردشده را وصل کند.
//
// ⚠️ **حکم روی جمعیتِ تجمیعیِ سه کارت است (n=283)، نه هر کارت به‌تنهایی.**
//    این یک **استخرِ اتحادی** است (METHOD_ENSEMBLE_UNION_DEPLOYMENT.md): هر سه
//    کارت باید هم‌زمان روی سایت باشند وگرنه جمعیتِ داوری‌شده بازتولید نمی‌شود.
//    سهمِ FIFO: D1=24٪ · بریدگیِ FIFO ۲۶٪ · وتوی FIFO لازم نشد.
//
// ⚠️ **نسبت با S606 یک تصمیمِ ریسک/بازده است، نه علمی** (بندِ ۳ سند): S606
//    (D1+H8-calm) maxDD=5.66٪ دارد و S607 = 7.47٪، در برابرِ z بالاتر (4.21 در
//    برابرِ 3.82) و سودِ بیشتر با سه کارت. S606 روی سایت وصل نیست ⇒ تعارضی
//    نداریم؛ اگر روزی وصل شد، **زیرمجموعهٔ اکیدِ** این لایه است (D1 و H8 مشترک)
//    ⇒ سایزِ مشترک الزامی.
//
// ⚠️ **پورتِ مو-به-موی** strategies/s607_engle_dual_gate.py + ماشینِ والد
//    (s840_engle_shock.ewma_z/atr_series/signals_for · s605.sigma_series/
//    regime_ratio). **پنج دامِ پورت** که همه در پریتی تست می‌شوند:
//    ① `ewma_z` واریانس را از `k0 = min(50, n−1)` بذر می‌گیرد با
//       `v = var(r[1..k0])` — واریانسِ **جمعیتی** (ddof=0) — و بعد
//       `v_t = λv_{t−1} + (1−λ)r²_{t−1}`. توجه: r²ِ **کندلِ قبل**، نه خودِ کندل.
//    ② ATR = **وایلدر** با بذرِ `mean(tr[0..p−1])` در ایندکسِ `p−1`، سپس
//       `acc += (tr[i]−acc)/p`. و `tr[0]` از `pc = c[0]` ساخته می‌شود (نه NaN).
//    ③ گیتِ روند **دو کندل** علّی است: `cl[i−1] − cl[i−1−K]`. اگر اشتباهاً
//       `cl[i]` بگذاریم، خودِ شوک رانش را می‌سازد و لایه به نویز بدل می‌شود.
//    ④ `regime_ratio` میانه را با **shift(1)** و `min_periods=W` می‌گیرد ⇒
//       پنجرهٔ `σ[i−W..i−1]` (بستهٔ گذشته) و پیش از آن NaN. شرطِ آرامش
//       `reg ≤ 1.0` است (نه `<`).
//    ⑤ `warmup = 250` برای دادهٔ ≥۵۰۰۰ کندل؛ سیگنال‌های پیش از آن نادیده.
//       و ورودِ معامله در openِ کندلِ **بعد** از کندلِ سیگنال.
//
// اثباتِ پورت: web_tool/tools/parity_s607.mjs روی مرجعِ پایتون
//    (results/_s607_parity/{D1,H8,H6,H12}.json) — صفر اختلاف.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

export interface S607Config {
  id: string          // شناسهٔ کارت (XAUUSD-D1 | XAUUSD-H8 | XAUUSD-H6)
  tfFa: string        // برچسبِ فارسیِ تایم‌فریم
  zThr: number        // آستانهٔ شوک |z| (منجمد از S840: 2.618 هر سه کارت)
  lam: number         // λِ IGARCH (منجمد: 0.94 — RiskMetrics)
  atrP: number        // پنجرهٔ ATR وایلدر (منجمد: 34)
  slK: number         // SL = slK × ATR34[i]  (D1: 1.272 · H8/H6: 1.618)
  rr: number          // TP = max(rr×SL, SL)  (D1/H8: 1.0 · H6: 1.272)
  maxHold: number     // بیشینهٔ نگه‌داری بر حسبِ کندلِ همان TF (D1: 21 · H8/H6: 34)
  // گرم‌شدنِ بک‌تست — ⚠️ دامِ ⑥ (که آزمونِ پریتی کشفش کرد): در پایتون این عدد
  // **ثابت نیست**، بلکه از طولِ داده مشتق می‌شود:
  //   s604.load_raw → `warmup = 250 if len(df) >= 5000 else max(60, len(df)//10)`
  // روی دادهٔ کاملِ MT5: H8 (۱۱۹۷۸ کندل) و H6 (۱۵۹۶۶) ⇒ ۲۵۰، ولی
  // **D1 فقط ۴۰۰۵ کندل دارد** (۱۵.۶ سال × ~۲۵۶ روزِ معاملاتی) ⇒ ۴۰۰۵//۱۰ = **۴۰۰**.
  // اگر ۲۵۰ بگذاریم، ۱۵۰ کندلِ ابتداییِ D1 که پایتون آن‌ها را نامعتبر می‌داند
  // سیگنال می‌دهند ⇒ جمعیتِ داوری‌شده عوض می‌شود. پس عددِ **بازتولیدشده** ذخیره
  // می‌شود تا آزمونِ پریتی (`tools/_parity_s607.mts`) بتواند همان جمعیتِ
  // داوری‌شده را بازبسازد.
  //
  // 🔴 دامنهٔ استفاده — این عدد **در مسیرِ تصمیمِ زنده به‌کار نمی‌رود** و
  // این عمدی است، نه فراموشی:
  //   • `warm` معنایش «از کندلِ چندم به بعد، معامله را در آمارِ بک‌تست
  //     بشمار» است — یک قاعدهٔ **شمارشِ جمعیت** روی تاریخِ کامل.
  //   • ولی سایت هیچ جمعیتی نمی‌شمارد؛ فقط **آخرین کندلِ بسته** را می‌خواند.
  //     چیزی که آنجا اهمیت دارد این است که z/σ/ATR به‌قدرِ کافی همگرا شده
  //     باشند، و آن با `minBars` (خطِ ۲۷۵) کنترل می‌شود که از خودِ
  //     نیازمندی‌های علّی مشتق می‌شود: max(atrP+2, 51, K+2, W+1).
  //   • اگر `warm` را اشتباهاً در مسیرِ زنده به‌کار ببریم، کارتِ D1 با ~۷۲۰
  //     کندلِ زندهٔ Yahoo هرگز روشن نمی‌شود چون ۴۰۰ کندل از همان تاریخِ
  //     کوتاه را دور می‌ریزد ⇒ لایه‌ای که ACCEPT گرفته، عملاً مرده می‌ماند.
  warm: number
  driftK: number | null   // گیتِ روند بر حسبِ **کندل** (D1: null ⇒ بی‌گیت)
  sigmaW: number | null   // پنجرهٔ میانهٔ رژیمِ σ (D1: null ⇒ بی‌گیت)
  barsPerDay: number      // فقط برای نمایشِ «≈چند روز» (D1:1 · H8:3 · H6:4)
  approachFrac: number    // «نزدیک‌شدن»: |z| ≥ approachFrac×zThr (فقط UI)
  // اعدادِ رسمیِ عضو در استخر — فقط برای متنِ گزارش (هیچ اثری در منطق ندارند)
  memberN: number
  memberWr: number
  memberLift: number
}

// ---------------------------------------------------------------------------
// پیکربندیِ سه کارتِ رسمی. منابعِ حقیقت:
//   · z_thr/mode/sl_k/rr  ← results/_scan_S840/<TF>.json::is_winner
//   · hold                ← strategies/s840_engle_shock.py::TF_HOLD
//   · K = K_days × BARS_PER_DAY[tf] (s604: D1=1, H12=2, H8=3, H6=4)
//   · W                   ← strategies/s607_engle_dual_gate.py::FROZEN
//   · n/wr/lift           ← results/_s607_dual_gate/{verdict,census}.json
// ---------------------------------------------------------------------------
export const S607_CFG: Record<string, S607Config> = {
  // 🟨 D1 — عضوِ **خام** استخر: هیچ گیتی ندارد (سند §۱ «D1 خام»).
  //    چرا بی‌گیت: خودِ کارتِ D1 در S840 برندهٔ ACCEPT بود و S602/S604/S606/S607
  //    همه آن را دست‌نخورده به استخر می‌برند ⇒ افزودنِ گیت = پارامترِ نو = ممنوع.
  'XAUUSD-D1': {
    id: 'XAUUSD-D1', tfFa: 'D1',
    zThr: 2.618, lam: 0.94, atrP: 34,
    // warm=400 (نه ۲۵۰) — بازتولیدِ `max(60, 4005//10)` روی دادهٔ کاملِ D1؛
    // تنها کارتی از سه‌گانه که زیرِ ۵۰۰۰ کندل است (دامِ ⑥).
    slK: 1.272, rr: 1.0, maxHold: 21, warm: 400,
    driftK: null, sigmaW: null, barsPerDay: 1,
    approachFrac: 0.85,
    memberN: 87, memberWr: 64.37, memberLift: 16.6906,
  },
  // 🟦 H8-DUAL — K=60 روز × ۳ کندل/روز = **۱۸۰ کندل** · W=233
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    zThr: 2.618, lam: 0.94, atrP: 34,
    slK: 1.618, rr: 1.0, maxHold: 34, warm: 250,
    driftK: 180, sigmaW: 233, barsPerDay: 3,
    approachFrac: 0.85,
    memberN: 131, memberWr: 66.41, memberLift: 16.6104,
  },
  // 🟩 H6-DUAL — K=60 روز × ۴ کندل/روز = **۲۴۰ کندل** · W=233
  //    تنها کارتی که rr>1 دارد (TP = 1.272×SL) ⇒ هندسهٔ نامتقارن.
  'XAUUSD-H6': {
    id: 'XAUUSD-H6', tfFa: 'H6',
    zThr: 2.618, lam: 0.94, atrP: 34,
    slK: 1.618, rr: 1.272, maxHold: 34, warm: 250,
    driftK: 240, sigmaW: 233, barsPerDay: 4,
    approachFrac: 0.85,
    memberN: 166, memberWr: 60.84, memberLift: 15.7416,
  },
  // ⛔ XAUUSD-H12 عمداً **غایب** است. انتخاب‌گرِ رسمیِ S607 آن را با حاشیهٔ
  //    ۰.۱۵ از استخر حذف کرد (سند §۲ و verdict.json::members). افزودنش =
  //    تعمیمِ ممنوعِ MTF و باطل‌کردنِ جمعیتِ n=283 که داوری شده.
}

// ---------------------------------------------------------------------------
// ewma_z — پورتِ عینِ s840_engle_shock.ewma_z (دامِ ①)
//   r[0] = 0 ; r[t] = ln(c[t]/c[t−1])
//   k0 = min(50, n−1) ; var[k0] = var(r[1..k0])  (جمعیتی، ddof=0)
//   var[t] = λ·var[t−1] + (1−λ)·r[t−1]²      برای t > k0
//   z[t] = r[t] / sqrt(var[t])
// خروجی: z و sigma (=sqrt(var)) — sigma همان چیزی است که s605.sigma_series
//   بازمی‌سازد و سلامتش با max|Δz| < 1e−6 در اکسپورترِ پایتون تأیید شد.
// ---------------------------------------------------------------------------
export function ewmaZ(close: number[], lam: number): { z: number[]; sigma: number[]; r: number[] } {
  const n = close.length
  const r = new Array<number>(n).fill(0)
  for (let t = 1; t < n; t++) {
    const v = Math.log(close[t] / close[t - 1])
    r[t] = Number.isFinite(v) ? v : 0
  }
  const z = new Array<number>(n).fill(NaN)
  const sigma = new Array<number>(n).fill(NaN)
  const k0 = Math.min(50, n - 1)
  if (k0 < 5) return { z, sigma, r }

  // var(r[1..k0]) با ddof=0 — عینِ np.var
  let mean = 0
  for (let t = 1; t <= k0; t++) mean += r[t]
  mean /= k0
  let acc = 0
  for (let t = 1; t <= k0; t++) { const d = r[t] - mean; acc += d * d }
  let v = acc / k0
  if (!(v > 0)) v = 1e-12

  sigma[k0] = Math.sqrt(v)
  z[k0] = sigma[k0] > 0 ? r[k0] / sigma[k0] : NaN
  for (let t = k0 + 1; t < n; t++) {
    v = lam * v + (1.0 - lam) * r[t - 1] * r[t - 1]
    const sd = Math.sqrt(v)
    sigma[t] = sd
    z[t] = sd > 0 ? r[t] / sd : NaN
  }
  return { z, sigma, r }
}

// ---------------------------------------------------------------------------
// atrWilder — پورتِ عینِ s840_engle_shock.atr_series (دامِ ②)
//   pc = [c[0], c[0..n−2]]  ⇒ tr[0] با pc=c[0] ساخته می‌شود (نه NaN)
//   out[p−1] = mean(tr[0..p−1]) ; out[i] = out[i−1] + (tr[i]−out[i−1])/p
//   اگر n ≤ p ⇒ همه NaN
// ---------------------------------------------------------------------------
export function atrWilder(candles: Candle[], p: number): number[] {
  const n = candles.length
  const out = new Array<number>(n).fill(NaN)
  if (n <= p) return out
  const tr = new Array<number>(n).fill(0)
  for (let i = 0; i < n; i++) {
    const h = candles[i].high, l = candles[i].low
    const pc = i === 0 ? candles[0].close : candles[i - 1].close
    tr[i] = Math.max(h - l, Math.max(Math.abs(h - pc), Math.abs(l - pc)))
  }
  let acc = 0
  for (let i = 0; i < p; i++) acc += tr[i]
  acc /= p
  out[p - 1] = acc
  const a = 1.0 / p
  for (let i = p; i < n; i++) {
    acc = acc + a * (tr[i] - acc)
    out[i] = acc
  }
  return out
}

// ---------------------------------------------------------------------------
// regimeRatio — پورتِ عینِ s605.regime_ratio (دامِ ④)
//   med[i] = median(sigma[i−W .. i−1])  (shift(1) + rolling(W, min_periods=W))
//   reg[i] = sigma[i] / med[i] ؛ پیش از دسترسیِ کاملِ پنجره ⇒ NaN
// پیاده‌سازی: پنجرهٔ لغزانِ مرتب‌شده (کافی برای طولِ کندلِ سایت).
// ⚠️ میانهٔ pandas برای Wِ **زوج** میانگینِ دو عضوِ میانی است؛ W=233 فرد است
//    ولی برای درستیِ عمومی هر دو حالت پوشش داده شده.
// ---------------------------------------------------------------------------
export function regimeRatio(sigma: number[], W: number): number[] {
  const n = sigma.length
  const out = new Array<number>(n).fill(NaN)
  for (let i = W; i < n; i++) {
    // پنجرهٔ بستهٔ گذشته: [i−W , i−1]
    const win: number[] = []
    let bad = false
    for (let j = i - W; j <= i - 1; j++) {
      const s = sigma[j]
      if (!Number.isFinite(s)) { bad = true; break }
      win.push(s)
    }
    if (bad || win.length < W) continue
    win.sort((x, y) => x - y)
    const m = win.length
    const med = m % 2 === 1 ? win[(m - 1) / 2] : (win[m / 2 - 1] + win[m / 2]) / 2
    if (!(med > 0) || !Number.isFinite(sigma[i])) continue
    out[i] = sigma[i] / med
  }
  return out
}

export interface S607Features {
  z: number[]
  sigma: number[]
  atr: number[]
  reg: number[] | null       // null برای کارتِ خام (D1)
}

export function s607Features(candles: Candle[], cfg: S607Config): S607Features {
  const close = candles.map((c) => c.close)
  const { z, sigma } = ewmaZ(close, cfg.lam)
  const atr = atrWilder(candles, cfg.atrP)
  const reg = cfg.sigmaW == null ? null : regimeRatio(sigma, cfg.sigmaW)
  return { z, sigma, atr, reg }
}

// ---------------------------------------------------------------------------
// computeS607 — تصمیم روی آخرین کندلِ بستهٔ i = n−1 (ورود در openِ کندلِ بعد)
// ---------------------------------------------------------------------------
export function computeS607(candles: Candle[], cfg: S607Config): RawSignal {
  const n = candles.length
  // کفِ داده: ATR34 دستِ‌کم ۳۵ کندل؛ گیتِ روند K+2؛ گیتِ رژیم W+1؛
  // و پنجرهٔ بذرِ σ (k0=50) ⇒ ۵۱. سخت‌ترین قید تعیین‌کننده است.
  const needDrift = cfg.driftK == null ? 0 : cfg.driftK + 2
  const needSigma = cfg.sigmaW == null ? 0 : cfg.sigmaW + 1
  const minBars = Math.max(cfg.atrP + 2, 51, needDrift, needSigma)

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  if (n < minBars) {
    const why = [
      `ATR(${cfg.atrP}) وایلدر`,
      'بذرِ ۵۰کندلیِ واریانسِ IGARCH',
      cfg.driftK == null ? null : `گیتِ روندِ ${cfg.driftK}-کندلی`,
      cfg.sigmaW == null ? null : `میانهٔ رژیمِ σ روی ${cfg.sigmaW} کندل`,
    ].filter(Boolean).join(' + ')
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 180 * GOLD_PIP, tpDist: 198 * GOLD_PIP, maxHoldBars: cfg.maxHold,
      reason:
        `دادهٔ کافی نیست: این لایه دستِ‌کم ${minBars} کندلِ بستهٔ ${cfg.tfFa} لازم دارد ` +
        `(${why}) — موجود: ${n}.`,
      indicators: emptyInd,
    }
  }

  const f = s607Features(candles, cfg)
  // 🔴 زمان‌بندیِ ورود — تحلیلِ صریح، چون هم‌کارتیِ H6 (S919) قاعدهٔ **متفاوتی**
  //    دارد و کپیِ کورکورانهٔ آن الگو این لایه را خراب می‌کند:
  //      · S919: ماسکِ بک‌تستش از پیش شیفت‌شده بود (`lm[1:] = up[:-1]`) و موتور
  //        هم ورود را در کندلِ بعد می‌گذاشت ⇒ ورودِ واقعی = **رویداد + ۲**، پس
  //        computeS919 مجبور است رویداد را روی کندلِ i−1 بسنجد.
  //      · S607/S840: `signals_for` **هیچ شیفتی ندارد** (بازگشتِ خامِ
  //        `np.where(sig_m)[0]` روی همان کندلِ شوک) و `barrier_outcomes` ورود را
  //        در `eb = sig_idx + 1` می‌گذارد ⇒ ورودِ واقعی = **رویداد + ۱**.
  //    ⇒ پس این‌جا شوک روی **آخرین کندلِ بسته** سنجیده می‌شود و ورود روی openِ
  //      کندلِ بعد می‌نشیند. اگر (به‌غلط) الگوی S919 را می‌گرفتیم و i−1 را
  //      می‌سنجیدیم، سیگنال یک کندل **دیر** می‌شد و جمعیتِ داوری‌شده عوض می‌شد.
  //    این تفاوت اتفاقی نیست: S919 روی هندسهٔ کندل (range و ρ) ماشه دارد، ولی
  //      S607 روی بازدهِ بسته-به-بسته (r_t) که خودش ذاتاً یک کندل تأخیر دارد.
  const i = n - 1                                   // آخرین کندلِ بسته‌شده

  const zi = f.z[i]
  const atrI = f.atr[i]
  const sigI = f.sigma[i]
  // شرطِ اعتبارِ سیگنال — عینِ `valid` در signals_for:
  //   isfinite(z) ∧ isfinite(atr) ∧ atr > 0
  const valid = Number.isFinite(zi) && Number.isFinite(atrI) && atrI > 0
  const absZ = valid ? Math.abs(zi) : 0

  // هندسهٔ شناور = عینِ بک‌تست: SL = slK×ATR34[i] ، TP = max(rr×SL, SL) (ضدِ #۸)
  const slPrice = Math.max(cfg.slK * (Number.isFinite(atrI) ? atrI : 0), 1e-12)
  const tpPrice = Math.max(cfg.rr * slPrice, slPrice)
  const slPip = slPrice / GOLD_PIP
  const tpPip = tpPrice / GOLD_PIP

  // ① شوکِ انگل روی کندلِ بسته — mode=follow ⇒ جهت هم‌جهتِ خودِ شوک
  const shockUp = valid && zi >= cfg.zThr
  const shockDn = valid && zi <= -cfg.zThr
  const isShock = shockUp || shockDn
  const direction: 'LONG' | 'SHORT' = shockDn ? 'SHORT' : 'LONG'

  // ② گیتِ روندِ علّی (دامِ ③): cl[i−1] − cl[i−1−K]، خودِ کندلِ شوک لمس نمی‌شود
  let driftDelta: number | null = null
  let driftOk = true
  let driftReady = true
  if (cfg.driftK != null) {
    const K = cfg.driftK
    if (i - 1 - K < 0) {
      driftReady = false
      driftOk = false
    } else {
      driftDelta = candles[i - 1].close - candles[i - 1 - K].close
      driftOk = shockDn ? driftDelta < 0 : driftDelta > 0
    }
  }

  // ③ گیتِ رژیمِ σ (دامِ ④): reg = σ[i] / median(σ[i−W..i−1]) و شرط reg ≤ 1.0
  let regVal: number | null = null
  let calmOk = true
  let calmReady = true
  if (cfg.sigmaW != null) {
    const rv = f.reg ? f.reg[i] : NaN
    if (!Number.isFinite(rv)) {
      calmReady = false
      calmOk = false
    } else {
      regVal = rv
      calmOk = rv <= 1.0
    }
  }

  const gatesOk = driftOk && calmOk
  const active = isShock && gatesOk

  // «نزدیک‌شدن» — فقط اطلاع‌رسانی، هیچ معامله‌ای از این شاخه صادر نمی‌شود.
  // شرط: |z| در ۸۵–۱۰۰٪ آستانه **و** هر دو گیت هم‌اکنون باز باشند؛ وگرنه
  // «نزدیک‌شدن» دروغ است چون حتی با شوکِ کامل هم ورودی صادر نمی‌شد.
  // برای جهتِ فرضی از علامتِ z استفاده می‌شود.
  const hypoDn = valid && zi < 0
  let hypoDriftOk = true
  if (cfg.driftK != null) {
    hypoDriftOk = driftReady && driftDelta != null &&
      (hypoDn ? driftDelta < 0 : driftDelta > 0)
  }
  const approaching = valid && !isShock &&
    absZ >= cfg.approachFrac * cfg.zThr && hypoDriftOk && calmOk

  const ratio = cfg.zThr > 0 ? absZ / cfg.zThr : 0
  const driftDays = cfg.driftK == null ? 0 : Math.round(cfg.driftK / cfg.barsPerDay)
  const holdDays = Math.round((cfg.maxHold / cfg.barsPerDay) * 10) / 10

  const indicators: RouterDecision['indicators'] = [
    {
      name: `شوکِ استانداردشدهٔ ARCH: |z| در برابرِ آستانهٔ ${cfg.zThr} (z = r ÷ σ_IGARCH)`,
      value: valid
        ? `${Math.abs(zi).toFixed(3)} / ${cfg.zThr} (${(ratio * 100).toFixed(0)}٪ آستانه)`
        : '—',
      status: isShock ? 'ok' : (approaching ? 'neutral' : 'bad'),
    },
    {
      name: 'جهتِ شوک (mode=follow ⇒ هم‌جهتِ بازدهِ شوک)',
      value: !valid ? '—' : (shockUp ? 'صعودی (LONG)' : (shockDn ? 'نزولی (SHORT)'
        : (zi > 0 ? 'صعودی (زیرِ آستانه)' : 'نزولی (زیرِ آستانه)'))),
      status: isShock ? 'ok' : 'neutral',
    },
  ]

  if (cfg.driftK != null) {
    indicators.push({
      name: `گیتِ ①: روندِ علّیِ ${cfg.driftK} کندل (≈${driftDays} روز) — close[i−1] در برابرِ close[i−1−${cfg.driftK}]`,
      value: !driftReady ? 'پنجرهٔ ناقص (کندلِ کافی نیست)'
        : `${driftDelta! >= 0 ? '+' : ''}${(driftDelta! / GOLD_PIP).toFixed(0)} pip ` +
          `(${driftDelta! > 0 ? 'رانشِ صعودی' : (driftDelta! < 0 ? 'رانشِ نزولی' : 'بی‌تغییر')})` +
          `${isShock ? (driftOk ? ' ✓ هم‌جهتِ شوک' : ' ✗ خلافِ شوک ⇒ گیت بسته') : ''}`,
      status: driftReady && driftOk ? 'ok' : 'bad',
    })
  }
  if (cfg.sigmaW != null) {
    indicators.push({
      name: `گیتِ ②: رژیمِ σ — σ[i] ÷ میانهٔ σ در ${cfg.sigmaW} کندلِ گذشته (کفِ آرامش ≤ ۱.۰)`,
      value: !calmReady ? 'پنجرهٔ ناقص (کندلِ کافی نیست)'
        : `${regVal!.toFixed(3)} (${calmOk ? 'CALM — بازارِ آرام ✓' : 'STORM — بازارِ متلاطم ✗ گیت بسته'})`,
      status: calmReady && calmOk ? 'ok' : 'bad',
    })
  } else {
    indicators.push({
      name: 'گیت‌ها روی این کارت',
      value: 'هیچ — D1 عضوِ **خام** استخر است (سند §۱: «D1 خام»)',
      status: 'neutral',
    })
  }

  indicators.push(
    {
      name: `σ_IGARCH کندلِ جاری (λ=${cfg.lam})`,
      value: Number.isFinite(sigI) ? `${(sigI * 100).toFixed(4)}٪ بازدهِ لگاریتمی` : '—',
      status: 'neutral',
    },
    {
      name: `ATR(${cfg.atrP}) وایلدر — پایهٔ هندسهٔ شناور`,
      value: Number.isFinite(atrI) ? `${(atrI / GOLD_PIP).toFixed(1)} pip` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (این کارت)',
      value: `${slPip.toFixed(1)} / ${tpPip.toFixed(1)} pip ` +
        `(${cfg.slK}×ATR و نسبتِ ${cfg.rr} ⇒ TP${cfg.rr > 1 ? '>' : '='}SL)`,
      status: 'ok',
    },
  )

  // ---------------------------- متنِ گزارش ----------------------------
  const gateWord = cfg.driftK == null ? 'بی‌گیت (کارتِ خام)' : 'دو گیتِ متعامد'
  let reason: string
  if (active) {
    const side = direction === 'LONG' ? 'خرید' : 'فروش'
    const shockDir = direction === 'LONG' ? 'صعودی' : 'نزولی'
    const gateTxt = cfg.driftK == null
      ? `این کارت **خام** است (هیچ گیتی ندارد) — چون خودِ D1 در والدِ S840 برندهٔ ACCEPT بود و ` +
        `افزودنِ گیت به آن یک پارامترِ نو و ممنوع می‌بود.`
      : `گیتِ ① روند: رانشِ ${cfg.driftK}-کندلی (≈${driftDays} روز) ` +
        `${driftDelta! >= 0 ? '+' : ''}${(driftDelta! / GOLD_PIP).toFixed(0)} pip و هم‌جهتِ شوک ✓ ` +
        `(MOP 2012 — جریانِ مطلع در مقیاسِ ماه). ` +
        `گیتِ ② رژیم: σ نسبت به میانهٔ ${cfg.sigmaW} کندل = ${regVal!.toFixed(3)} ≤ ۱.۰ ⇒ بازارِ **آرام** ✓ ` +
        `(Andersen–Bollerslev — شوک در آرامش اطلاع‌بارتر است). ` +
        `نسبتِ هم‌خطیِ اندازه‌گیری‌شدهٔ این دو گیت ≈۱.۰ ⇒ اطلاعاتشان **جمع‌پذیر** است نه تکراری.`
    reason =
      `**شوکِ انگل با ${gateWord}** روی کندلِ ${cfg.tfFa} بسته‌شده: ` +
      `بازدهِ استانداردشده z=${zi.toFixed(3)} یعنی |z|=${absZ.toFixed(3)} ≥ ${cfg.zThr} ` +
      `(${(ratio * 100).toFixed(0)}٪ آستانه) — حرکتی که نسبت به نوسانِ **شرطیِ** خودِ بازار ` +
      `(σ_IGARCH با λ=${cfg.lam}) غیرعادی است، نه نسبت به یک آستانهٔ ثابتِ دلبخواه ` +
      `(Engle 1982: واریانس خوشه‌ای است، پس بزرگیِ خام گمراه‌کننده است). ` +
      `جهت = follow ⇒ ادامهٔ همان شوکِ ${shockDir} ⇒ سیگنالِ ${side}. ${gateTxt} ` +
      `سهمِ این کارت در استخرِ ACCEPT: n=${cfg.memberN} · WR=${cfg.memberWr}٪ · ` +
      `lift=+${cfg.memberLift.toFixed(2)}pp. ` +
      `حکمِ استخرِ سه‌کارتی: RQS2=83.1 · n=283 · WR=60.07٪ · PF=1.609 · z=4.21 · ` +
      `p_perm=1.3e−05 · هر ۱۱ دروازهٔ RQS2 v2.6 سبز (تنش: 82.9). ` +
      `ورود روی openِ کندلِ بعد؛ SL=${slPip.toFixed(1)} / TP=${tpPip.toFixed(1)} pip؛ ` +
      `حداکثر ${cfg.maxHold} کندل (≈${holdDays} روز) نگه‌داری. ` +
      `⚠️ حکم روی **جمعیتِ تجمیعیِ سه کارت (D1+H8+H6)** است ⇒ اگر چند کارت هم‌زمان ` +
      `روشن شدند، سایزِ مشترک بگیرید.`
  } else if (approaching) {
    reason =
      `|z|=${absZ.toFixed(3)} به ${(ratio * 100).toFixed(0)}٪ آستانهٔ شوک (${cfg.zThr}) رسیده و ` +
      `${cfg.driftK == null ? 'این کارت گیتی ندارد' : 'هر دو گیت (روند و رژیمِ σ) هم‌اکنون **باز** هستند'} ` +
      `⇒ اگر کندلِ بعد شوکِ کامل بسازد، ورود صادر می‌شود. هنوز معامله‌ای نیست.`
  } else if (!valid) {
    reason =
      `سری‌های علّی هنوز معتبر نیستند (گرم‌شدنِ ATR(${cfg.atrP}) یا بذرِ ۵۰کندلیِ واریانسِ IGARCH) ` +
      `— لایه در انتظار.`
  } else if (isShock && !driftReady) {
    reason =
      `شوکِ انگل رخ داد (|z|=${absZ.toFixed(3)} ≥ ${cfg.zThr}) ولی پنجرهٔ گیتِ روند ناقص است: ` +
      `این گیت به close[i−1−${cfg.driftK}] نیاز دارد و آن کندل در دادهٔ موجود نیست. ` +
      `طبقِ اصلِ «پنجرهٔ ناقص شاهد نیست» ورودی صادر نمی‌شود.`
  } else if (isShock && !calmReady) {
    reason =
      `شوکِ انگل رخ داد (|z|=${absZ.toFixed(3)} ≥ ${cfg.zThr}) ولی پنجرهٔ گیتِ رژیم ناقص است: ` +
      `میانهٔ σ روی ${cfg.sigmaW} کندلِ گذشته لازم است و دادهٔ موجود کوتاه‌تر است. ` +
      `پنجرهٔ ناقص شاهد نیست ⇒ بدونِ ورود.`
  } else if (isShock && !driftOk) {
    const shockDir = shockDn ? 'نزولی' : 'صعودی'
    reason =
      `شوکِ انگل رخ داد (|z|=${absZ.toFixed(3)} ≥ ${cfg.zThr} · ${shockDir}) — یعنی **پایهٔ S840 روشن است** — ` +
      `ولی گیتِ روندِ ${cfg.driftK}-کندلی (≈${driftDays} روز) خلافِ شوک است ` +
      `(${driftDelta! >= 0 ? '+' : ''}${(driftDelta! / GOLD_PIP).toFixed(0)} pip) ⇒ این لایه ورود نمی‌دهد. ` +
      `دقیقاً همین صافی است که لیفتِ این کارت را از +${cfg.tfFa === 'H8' ? '9.26' : '5.87'}pp خام به ` +
      `+${cfg.memberLift.toFixed(2)}pp رساند: شوکِ خلافِ رانش، بازگشتی است نه ادامه‌دار.`
  } else if (isShock && !calmOk) {
    reason =
      `شوکِ انگل رخ داد (|z|=${absZ.toFixed(3)} ≥ ${cfg.zThr}) ولی گیتِ رژیمِ σ بسته است: ` +
      `نسبتِ σ به میانهٔ ${cfg.sigmaW} کندل = ${regVal!.toFixed(3)} > ۱.۰ ⇒ بازار در رژیمِ **STORM** ` +
      `(متلاطم) است. شوک در بازارِ پرنوسان تازگیِ اطلاعاتی کمی دارد — یکی از چند شوکِ آن خوشه است — ` +
      `پس ادامه‌اش قابلِ اتکا نیست (Andersen–Bollerslev). لایه صادقانه خنثی می‌مانَد.`
  } else {
    reason =
      `کندلِ بستهٔ اخیر شوکِ انگل نیست: |z|=${absZ.toFixed(3)} یعنی ${(ratio * 100).toFixed(0)}٪ آستانهٔ ` +
      `${cfg.zThr}. این لایه **کم‌بسامد** است (سهمِ این کارت ${cfg.memberN} معامله در ۱۵.۶ سال) — ` +
      `خنثی بودنش حالتِ عادی است، نه خرابی.`
  }

  return {
    active, approaching, direction,
    slDist: slPrice, tpDist: tpPrice, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ شوکِ کاملِ |z| ≥ ${cfg.zThr} روی کندلِ بعد — ` +
        `${cfg.driftK == null ? 'کارتِ خام، گیتی ندارد' : 'هر دو گیت هم‌اکنون باز است'}`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS607(
  cfg: S607Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS607(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s607_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10
  const driftDays = cfg.driftK == null ? 0 : Math.round(cfg.driftK / cfg.barsPerDay)
  const holdDays = Math.round((cfg.maxHold / cfg.barsPerDay) * 10) / 10

  const filters = [
    `شوکِ ARCH: |z| ≥ ${cfg.zThr} با z = r ÷ σ و σ²=${cfg.lam}σ²+${(1 - cfg.lam).toFixed(2)}r² (IGARCH بی‌ثابت — منجمد از S840)`,
    `جهت = follow (هم‌جهتِ شوک) — برندهٔ منجمدِ S840 روی این کارت`,
  ]
  if (cfg.driftK != null) {
    filters.push(
      `گیتِ ① روندِ علّی: ${cfg.driftK} کندل (≈${driftDays} روز) — close[i−1] در برابرِ close[i−1−${cfg.driftK}] (ارثی از S604)`,
    )
  }
  if (cfg.sigmaW != null) {
    filters.push(
      `گیتِ ② رژیمِ σ: σ[i] ÷ میانهٔ σ[i−${cfg.sigmaW}..i−1] ≤ ۱.۰ ⇒ فقط بازارِ CALM (ارثی از S605/S606)`,
    )
  } else {
    filters.push('کارتِ **خام** — هیچ گیتی ندارد (سند §۱: «D1 خام»)')
  }
  filters.push(
    `هم‌خطیِ اندازه‌گیری‌شدهٔ دو گیت ≈۱.۰ ⇒ اطلاعاتِ افزایشی، نه تکراری (کشفِ سند §۳)`,
    `صفر پارامترِ آزاد — همه از S840/S604/S605 منجمد شده‌اند`,
  )

  const meta: DecideMeta = {
    code: 'S607',
    name: `شوکِ انگل با دو گیتِ متعامد (${cfg.tfFa})`,
    kind: 'engle_dual_gate' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ شناورِ عینِ بک‌تست: SL=${slPipShow} / TP=${tpPipShow} pip ` +
      `(${cfg.slK}×ATR(${cfg.atrP}) وایلدر و نسبتِ ${cfg.rr}؛ میانهٔ تاریخیِ استخر ≈۱۷۹.۸/۱۹۷.۵ pip). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندلِ ${cfg.tfFa} (≈${holdDays} روز) نگه‌دار. ` +
      `⚠️⚠️ **استخرِ اتحادیِ سه‌کارتی:** حکمِ ACCEPT روی جمعیتِ تجمیعیِ ` +
      `D1+H8+H6 (n=283) است، نه این کارت به‌تنهایی. اگر دو یا سه کارت هم‌زمان ` +
      `سیگنال دادند، **یک رویدادِ نوسانی** است ⇒ سایزِ مشترک بگیرید، نه سه ریسکِ کامل. ` +
      `⚠️ کارتِ H12 با آنکه n=167/WR=62.28٪ داشت توسطِ انتخاب‌گرِ رسمی حذف شد ` +
      `(حاشیهٔ ۰.۱۵) ⇒ اگر روزی کسی آن را وصل کرد، جمعیتِ داوری‌شده باطل می‌شود. ` +
      `⚠️ قیدِ تک‌معامله (FIFO تقویمی بدونِ هم‌زمانی در بک‌تست). ` +
      `⚠️ هیچ مدیریتِ فعالی (BE/trailing) آزموده و تأیید نشده ⇒ فقط TP/SL/زمان. ` +
      `⚠️ maxDD استخر ۷.۴۷٪ است (در برابرِ ۵.۶۶٪ برای S606) — بهایِ z و سودِ بیشتر.`,
    filters,
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
