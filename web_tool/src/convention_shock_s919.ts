// ---------------------------------------------------------------------------
// S919 — «شوکِ مطلعِ هم‌راستا با قراردادِ بازار» (Convention-Aligned Informed Shock)
// XAUUSD-H6 — تنها کارتِ ACCEPT · دانشمند: جان مینارد کینز (بلوکِ S910–S919)
//
// حکمِ نهایی (سند: results/S919_ConventionAlignedInformedShock_Xauusd_H6_rqs2_88.9_ACCEPT.md):
//   RQS2 = **88.9** · هر ۱۱ دروازهٔ H0..H10 سبز · notes خالی
//   n=106 · WR=55.66٪ · null_ref=40.04٪ · BE_cost=39.29٪ · lift=+15.62pp
//   z_obs=3.282 · z_margin=2.762 · p_perm=8.42e−04 · PF=1.85 · maxDD=2.89٪
//   نول: K=500 جایگشتِ هم‌هندسه (perm_mean=39.96 sd=4.97 perm_max=55.24) · uncond 50k
//   n_trials=2 (یک لمس روی کلِ ۱۵.۶ سال — هیچ فازِ کشفی وجود نداشت)
//
// فیزیکِ لایه — **قراردادِ کینزی روی شوکِ مطلعِ کایل**:
//   بازار بر «قرارداد» ایستاده است (کینز، نظریهٔ عمومی، فصل ۱۲): «وضعِ موجود
//   ادامه می‌یابد مگر دلیلی برای تغییر». شوکِ مطلع (ρ بالا = اثرِ قیمتیِ دائمی
//   به معنای Kyle 1985) دو سرنوشت دارد:
//     ① هم‌جهت با قراردادِ ۶۰-روزه → قرارداد تقویت می‌شود، جمعیت می‌پیوندد ⇒ ادامه.
//     ② خلافِ قرارداد → بازار آن را «اختلالِ موقت» می‌خواند و جذب می‌کند ⇒ ادامهٔ ضعیف‌تر.
//   ابطال‌گرِ P3 همین را اندازه گرفت: بازوی خلافِ قرارداد روی H6 فقط WR=42.1٪
//   (n=133) داد و روی H3 حتی زیرِ BE رفت (e=−5.1 pip) ⇒ روایت تأیید شد.
//
// ⚠️ **قانونِ MTF — تعمیم ممنوع.** پیش‌ثبت قلمرو را به دو کارت قفل کرده بود:
//     · H6 = ✅ ACCEPT 88.9 (n=106 · z=3.28)
//     · H3 = ❌ REJECT 16.0 (n=317 · WR=44.79٪ · z=1.87 · ردِ H1 H3 H7 H8 H10)
//   ⇒ **فقط یک کارت وصل می‌شود: XAUUSD-H6.** (H8 عامدانه از پیش‌ثبت حذف شده بود
//     چون S965/S966 آن‌جا ACCEPT دارند و دوباره‌آزمونی چندگانگیِ نو می‌ساخت.)
//
// ⚠️⚠️ دامِ پورت — **پنج‌تا**؛ چهارمی مرگبار است:
//   ① ATR = میانگینِ سادهٔ ۲۱تاییِ TR با `rolling(21).mean()` سپس **شیفتِ ۱**
//      (atr_prev) — نه Wilder/ewm.
//   ② پایتون `pd.Series.rolling(21).mean()` در ۲۰ عضوِ اول **NaN** می‌دهد و
//      `nan_to_num(atr_prev, nan=inf)` آن‌ها را در شرطِ شوک به inf می‌برد ⇒ شوک
//      خاموش؛ ولی در هندسه `nan_to_num(·, nan=0.0)` می‌شود. توجه: این با
//      `_rollsum`ِ S966 (جمعِ جزئی ÷ w) **متفاوت** است.
//   ③ هندسه از **atr_prev کندلِ سیگنال** ساخته می‌شود = ATR21 تا خودِ کندلِ
//      رویداد. یعنی برای رویدادِ t، هندسه از atr_prev[t+1] می‌آید.
//   ④ 🔴 **ماسک از پیش شیفت‌شده است:** `lm[1:] = up[:-1]` و سپس موتور ورود را در
//      openِ کندلِ **بعد از ماسک** می‌گذارد ⇒ ورودِ واقعی در **رویداد + ۲** است،
//      نه رویداد + ۱. (در S966 ماسک روی خودِ رویداد بود ⇒ ورود رویداد+۱.)
//      اندازه‌گیریِ اثرِ این دام روی همان داده و همان هندسه:
//        · ورودِ رویداد+۲ (کدِ داوری‌شده): n=106 · WR=**55.66٪** · e=+51.93 pip ✓
//        · ورودِ رویداد+۱ (پورتِ ساده‌لوح): n=106 · WR=**48.11٪** · e=+24.56 pip ✗
//      ⇒ پورتِ ساده‌لوحانه لبه را **کاملاً نابود می‌کند** (زیرِ نقطهٔ سربه‌سر).
//      بنابراین در سایت، رویداد روی کندلِ **i = n−2** سنجیده می‌شود و سیگنال روی
//      کندلِ بستهٔ i = n−1 صادر می‌گردد (ورود در openِ کندلِ بعد).
//   ⑤ گیتِ قرارداد **دو کندل** علّی است: `close[t−1] − close[t−1−K]` با K=240 —
//      کندلِ t (خودِ شوک) اصلاً لمس نمی‌شود. اگر اشتباهاً `close[t]` بگذاریم،
//      شوک خودش قرارداد را می‌سازد و لایه به نویز تبدیل می‌شود.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

export interface S919Config {
  id: string          // شناسهٔ کارت (XAUUSD-H6)
  tfFa: string        // برچسبِ فارسیِ تایم‌فریم
  tfHours: number     // ساعتِ هر کندل (برای تبدیلِ K به روز در متن)
  theta: number       // آستانهٔ شوک: high−low ≥ theta×ATR21[t−1] (منجمد از S965: 2.618)
  rhoMin: number      // کفِ ماندگاری ρ (منجمد از S965: 0.618)
  atrWin: number      // پنجرهٔ ATR (منجمد: 21)
  driftK: number      // گیتِ قرارداد: close[t−1] در برابرِ close[t−1−K] (H6 ⇒ 240)
  kSl: number         // SL = kSl × ATR21 (منجمد از S965: 1.272)
  kTp: number         // TP = kTp × ATR21 (منجمد از S965: 2.058 ⇒ RR=1.618، TP>SL ✓)
  maxHold: number     // بیشینهٔ نگه‌داری بر حسبِ کندلِ H6 (منجمد: 16)
  approachFrac: number // «نزدیک‌شدن»: رنج ≥ approachFrac×آستانه (فقط UI)
}

export const S919_CFG: Record<string, S919Config> = {
  // تنها کارتِ ACCEPT. همهٔ عددها به ارث از S965 (شوک/ماندگاری/هندسه) و
  // S604 (قاعدهٔ K = ۶۰ روزِ تقویمی ⇒ روی H6: 60×24/6 = 240 کندل).
  // صفر پارامترِ جست‌وجو‌شده ⇒ هیچ چندگانگیِ نو.
  'XAUUSD-H6': {
    id: 'XAUUSD-H6', tfFa: 'H6', tfHours: 6,
    theta: 2.618, rhoMin: 0.618, atrWin: 21, driftK: 240,
    kSl: 1.272, kTp: 2.058, maxHold: 16,
    approachFrac: 0.85,
  },
}

// ---------------------------------------------------------------------------
// rollMeanNan — بازتولیدِ دقیقِ `pd.Series(tr).rolling(21).mean()`:
//   out[i] = NaN  برای i < w−1        (دامِ ②؛ برخلافِ _rollsumِ S966)
//   out[i] = میانگینِ w عضوِ آخر  برای i ≥ w−1
// ---------------------------------------------------------------------------
function rollMeanNan(x: number[], w: number): number[] {
  const n = x.length
  const out = new Array<number>(n).fill(NaN)
  let acc = 0
  for (let i = 0; i < n; i++) {
    acc += x[i]
    if (i >= w) acc -= x[i - w]
    if (i >= w - 1) out[i] = acc / w
  }
  return out
}

export interface S919Features {
  atrPrev: number[]    // ATR21 علّی (شیفتِ ۱) بر حسبِ قیمت؛ NaN در گرم‌شدن
  rng: number[]        // high − low
  rho: number[]        // |close−open| ÷ rng  (ماندگاریِ درون-کندلی — Kyle 1985)
  bodySgn: number[]    // علامتِ بدنه
  shock: boolean[]     // rng ≥ theta×atrPrev  و  rng > 0
  driftUp: boolean[]   // close[t−1] >  close[t−1−K]   (قراردادِ صعودی)
  driftDn: boolean[]   // close[t−1] <  close[t−1−K]   (قراردادِ نزولی)
}

// پورتِ عینِ features() + بخشِ driftِ signals() — همه علّی.
export function s919Features(candles: Candle[], cfg: S919Config): S919Features {
  const n = candles.length
  const W = cfg.atrWin
  const K = cfg.driftK

  // TR: tr[0] = 0 (عینِ np.zeros سپس پرکردنِ [1:])
  const trArr = new Array<number>(n).fill(0)
  for (let t = 1; t < n; t++) {
    const h = candles[t].high, l = candles[t].low, pc = candles[t - 1].close
    trArr[t] = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc))
  }
  const atr = rollMeanNan(trArr, W)

  // ATR علّی: atr_prev = np.full(n, nan) سپس atr_prev[1:] = atr[:-1]
  // توجه: برخلافِ S966، اینجا atr_prev[0] هم NaN می‌ماند (دامِ ②).
  const atrPrev = new Array<number>(n).fill(NaN)
  for (let t = 1; t < n; t++) atrPrev[t] = atr[t - 1]

  const rng = new Array<number>(n).fill(0)
  const rho = new Array<number>(n).fill(0)
  const bodySgn = new Array<number>(n).fill(0)
  const shock = new Array<boolean>(n).fill(false)
  for (let t = 0; t < n; t++) {
    const c = candles[t]
    const r = c.high - c.low
    rng[t] = r
    const body = c.close - c.open
    rho[t] = r > 0 ? Math.abs(body) / r : 0
    bodySgn[t] = body > 0 ? 1 : (body < 0 ? -1 : 0)
    // عینِ `rng >= THETA * nan_to_num(atr_prev, nan=inf)` — NaN ⇒ inf ⇒ false
    const ap = atrPrev[t]
    const thr = Number.isFinite(ap) ? cfg.theta * ap : Infinity
    shock[t] = r >= thr && r > 0
  }

  // گیتِ قراردادِ علّی — پورتِ عینِ:
  //   drift[K+1:] = c[K:-1] − c[:-K-1]
  // یعنی برای ایندکسِ t (≥ K+1): close[t−1] − close[t−1−K].
  // پیش از t = K+1 هر دو false می‌مانند (drift = NaN ⇒ هر مقایسه false) — دامِ ⑤.
  const driftUp = new Array<boolean>(n).fill(false)
  const driftDn = new Array<boolean>(n).fill(false)
  for (let t = K + 1; t < n; t++) {
    const d = candles[t - 1].close - candles[t - 1 - K].close
    driftUp[t] = d > 0
    driftDn[t] = d < 0
  }

  return { atrPrev, rng, rho, bodySgn, shock, driftUp, driftDn }
}

// ---------------------------------------------------------------------------
// s919EventAt — آیا روی کندلِ رویدادِ t، بازویِ gated فعال است؟
// خروجی: 0 = خاموش · +1 = LONG · −1 = SHORT
// این تابع «قاعدهٔ منجمد» است و در پریتی مستقیماً با پایتون سنجیده می‌شود.
// ---------------------------------------------------------------------------
export function s919EventAt(f: S919Features, t: number, cfg: S919Config): number {
  if (t < 0) return 0
  const sgn = f.bodySgn[t]
  if (sgn === 0) return 0
  if (!f.shock[t]) return 0
  if (f.rho[t] < cfg.rhoMin) return 0
  if (sgn > 0 && f.driftUp[t]) return 1
  if (sgn < 0 && f.driftDn[t]) return -1
  return 0
}

// ---------------------------------------------------------------------------
// computeS919 — سیگنال روی آخرین کندلِ بستهٔ i = n−1.
// 🔴 طبق دامِ ④، رویداد روی کندلِ **i−1** سنجیده می‌شود (ماسکِ pre-shift):
//    رویداد در i−1 ⇒ ماسک در i ⇒ ورود در openِ کندلِ بعد = رویداد+۲. ✓
// هندسه از atr_prev[i] می‌آید = ATR21 تا خودِ کندلِ رویداد (دامِ ③).
// ---------------------------------------------------------------------------
export function computeS919(candles: Candle[], cfg: S919Config): RawSignal {
  const n = candles.length
  // کفِ داده: گیتِ قرارداد به close[t−1−K] با t = n−2 نیاز دارد ⇒ دستِ‌کم K+3 کندل.
  const minBars = Math.max(cfg.atrWin + 3, cfg.driftK + 3)

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  if (n < minBars) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 116 * GOLD_PIP, tpDist: 187 * GOLD_PIP, maxHoldBars: cfg.maxHold,
      reason:
        `دادهٔ کافی نیست: این لایه دستِ‌کم ${minBars} کندلِ بستهٔ ${cfg.tfFa} لازم دارد ` +
        `(گیتِ قراردادِ ${cfg.driftK}-کندلی + ATR(${cfg.atrWin}) علّی + شیفتِ ماسک) — موجود: ${n}.`,
      indicators: emptyInd,
    }
  }

  const f = s919Features(candles, cfg)
  const i = n - 1                                  // آخرین کندلِ بسته‌شده (= ماسک)
  const e = i - 1                                  // 🔴 کندلِ رویداد (دامِ ④)

  // هندسهٔ شناور = عینِ بک‌تست: از atr_prev[i] (= ATR21 تا کندلِ رویداد) — دامِ ③.
  const atrGeom = f.atrPrev[i]
  const geomOk = Number.isFinite(atrGeom) && atrGeom > 1e-12
  const atrEvent = f.atrPrev[e]                    // ATRِ مبنای آستانهٔ شوکِ رویداد
  const eventAtrOk = Number.isFinite(atrEvent) && atrEvent > 1e-12

  const slPip = Math.max((cfg.kSl * (geomOk ? atrGeom : 0)) / GOLD_PIP, 1e-9)
  const tpPip = Math.max((cfg.kTp * (geomOk ? atrGeom : 0)) / GOLD_PIP, 1e-9)
  const slDist = slPip * GOLD_PIP
  const tpDist = tpPip * GOLD_PIP

  // --- ارزیابیِ رویداد روی کندلِ e = n−2 ---
  const rngE = f.rng[e]
  const rhoE = f.rho[e]
  const sgnE = f.bodySgn[e]
  const thrE = eventAtrOk ? cfg.theta * atrEvent : Infinity
  const isShock = f.shock[e]
  const isPermanent = rhoE >= cfg.rhoMin
  // پایهٔ S965 (بی‌گیت) روی کندلِ رویداد
  const baseUp = isShock && isPermanent && sgnE > 0
  const baseDn = isShock && isPermanent && sgnE < 0
  // گیتِ قرارداد (S604): لانگ فقط با قراردادِ صعودی، شورت فقط با نزولی
  const dir = s919EventAt(f, e, cfg)
  const active = dir !== 0 && geomOk
  const direction: 'LONG' | 'SHORT' = dir < 0 ? 'SHORT' : (dir > 0 ? 'LONG' : (baseDn ? 'SHORT' : 'LONG'))

  // درفتِ خام برای نمایش (هر دو سر علّی نسبت به کندلِ رویداد)
  const hasDrift = e - 1 - cfg.driftK >= 0
  const driftDelta = hasDrift
    ? candles[e - 1].close - candles[e - 1 - cfg.driftK].close
    : NaN
  const driftAligned = (sgnE > 0 && f.driftUp[e]) || (sgnE < 0 && f.driftDn[e])

  // «نزدیک‌شدن» — روی کندلِ بستهٔ i (که رویدادِ بعدی می‌تواند باشد).
  // فقط اطلاع‌رسانی؛ هیچ معامله‌ای از این شاخه صادر نمی‌شود.
  const rngI = f.rng[i]
  const rhoI = f.rho[i]
  const sgnI = f.bodySgn[i]
  const thrI = geomOk ? cfg.theta * atrGeom : Infinity
  const nextAligned = (sgnI > 0 && f.driftUp[i]) || (sgnI < 0 && f.driftDn[i])
  // اگر کندلِ i خودش رویدادِ کامل باشد ⇒ سیگنالِ کندلِ بعد قطعی است.
  const nextIsEvent = s919EventAt(f, i, cfg) !== 0
  const approaching = !active && geomOk && (
    nextIsEvent ||
    (rngI >= cfg.approachFrac * thrI && rhoI >= cfg.rhoMin && sgnI !== 0 && nextAligned)
  )

  const ratioE = Number.isFinite(thrE) && thrE > 0 ? rngE / thrE : 0
  const ratioI = Number.isFinite(thrI) && thrI > 0 ? rngI / thrI : 0
  const driftDays = Math.round((cfg.driftK * cfg.tfHours) / 24)   // ۲۴۰ کندلِ H6 = ۶۰ روز

  const indicators: RouterDecision['indicators'] = [
    {
      name: `🔴 کندلِ رویداد = i−۱ (ماسکِ pre-shift ⇒ ورود در رویداد+۲)`,
      value: `رویداد روی کندلِ ${cfg.tfFa}ِ ماقبلِ آخر سنجیده می‌شود — عینِ بک‌تستِ داوری‌شده`,
      status: 'neutral',
    },
    {
      name: `رنجِ کندلِ رویداد در برابرِ آستانهٔ شوک (${cfg.theta}×ATR${cfg.atrWin}[t−1])`,
      value: eventAtrOk
        ? `${(rngE / GOLD_PIP).toFixed(1)} / ${(thrE / GOLD_PIP).toFixed(1)} pip (${(ratioE * 100).toFixed(0)}٪ آستانه)`
        : '—',
      status: isShock ? 'ok' : 'bad',
    },
    {
      name: `ماندگاری ρ = |close−open| ÷ (high−low) — کفِ ${cfg.rhoMin} (Kyle 1985)`,
      value: eventAtrOk ? `${rhoE.toFixed(3)}` : '—',
      status: isPermanent ? 'ok' : 'bad',
    },
    {
      name: 'جهتِ بدنهٔ کندلِ شوک (اثرِ دائمی ⇒ ادامه)',
      value: sgnE > 0 ? 'صعودی (LONG)' : (sgnE < 0 ? 'نزولی (SHORT)' : 'بدونِ بدنه (doji)'),
      status: sgnE !== 0 ? 'neutral' : 'bad',
    },
    {
      // شاخصِ یکتای این لایه — گیتِ کینزیِ قرارداد
      name: `گیتِ قراردادِ ${cfg.driftK} کندل (≈${driftDays} روز) — close[t−1] در برابرِ close[t−1−${cfg.driftK}]`,
      value: Number.isFinite(driftDelta)
        ? `${driftDelta >= 0 ? '+' : ''}${(driftDelta / GOLD_PIP).toFixed(0)} pip ` +
          `(${f.driftUp[e] ? 'قراردادِ صعودی' : (f.driftDn[e] ? 'قراردادِ نزولی' : 'بی‌تغییر')})` +
          `${sgnE !== 0 ? (driftAligned ? ' ✓ هم‌راستا با شوک' : ' ✗ خلافِ شوک ⇒ گیت بسته') : ''}`
        : '—',
      status: driftAligned ? 'ok' : 'bad',
    },
    {
      name: `ATR(${cfg.atrWin}) علّی — پایهٔ هندسهٔ شناور (تا کندلِ رویداد)`,
      value: geomOk ? `${(atrGeom / GOLD_PIP).toFixed(1)} pip` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (این کارت)',
      value: `${slPip.toFixed(1)} / ${tpPip.toFixed(1)} pip (نسبت ${(cfg.kTp / cfg.kSl).toFixed(3)} ⇒ TP>SL)`,
      status: 'ok',
    },
  ]

  let reason: string
  if (active) {
    const side = direction === 'LONG' ? 'خرید' : 'فروش'
    const bodyDir = direction === 'LONG' ? 'صعودی' : 'نزولی'
    const convDir = direction === 'LONG' ? 'صعودی' : 'نزولی'
    reason =
      `**شوکِ مطلعِ هم‌راستا با قرارداد** روی کندلِ ${cfg.tfFa}ِ ماقبلِ آخر: ` +
      `① شوکِ ماندگار — رنج ${(rngE / GOLD_PIP).toFixed(1)} pip ` +
      `≥ ${cfg.theta}×ATR(${cfg.atrWin})=${(thrE / GOLD_PIP).toFixed(1)} pip (${(ratioE * 100).toFixed(0)}٪ آستانه) ` +
      `با ماندگاری ρ=${rhoE.toFixed(3)} ≥ ${cfg.rhoMin} و بدنهٔ ${bodyDir}. ` +
      `② قراردادِ بازار — درفتِ علّیِ ${cfg.driftK} کندل (≈${driftDays} روز) هم ${convDir} است ` +
      `(${driftDelta >= 0 ? '+' : ''}${(driftDelta / GOLD_PIP).toFixed(0)} pip) ⇒ گیت باز ⇒ سیگنالِ ${side}. ` +
      `فیزیکِ اندازه‌گیری‌شده: بدنهٔ ماروبوزو-گونه یعنی اثرِ قیمتی درونِ کندل پس نگرفت ` +
      `(Kyle 1985 — امضای جریانِ مطلع)، و هم‌راستاییِ آن با قراردادِ ۶۰-روزه یعنی جمعیت ` +
      `به آن می‌پیوندد نه اینکه جذبش کند (کینز، نظریهٔ عمومی، فصل ۱۲) ⇒ ادامه. ` +
      `(۱۰۶ معامله در ۱۵.۶ سال · WR=۵۵.۶۶٪ · lift=+۱۵.۶۲pp · z=۳.۲۸ · p_perm=۸.۴e−۴ · PF=۱.۸۵ · ` +
      `maxDD=۲.۸۹٪ · هر ۱۱ دروازهٔ RQS2 سبز؛ ابطال‌گرِ P1: بازوی بی‌گیت WR=۴۸.۱٪ ⇒ گیت اطلاعات‌افزاست، ` +
      `ابطال‌گرِ P3: بازوی خلافِ قرارداد WR=۴۲.۱٪ ⇒ روایتِ کینزی تأیید شد). ` +
      `🔴 ورود روی openِ کندلِ بعد — که نسبت به کندلِ رویداد **دو کندل** فاصله دارد (عینِ بک‌تست). ` +
      `SL=${slPip.toFixed(1)} / TP=${tpPip.toFixed(1)} pip.`
  } else if (approaching) {
    reason = nextIsEvent
      ? `کندلِ بستهٔ اخیر **خودش رویدادِ کاملِ S919 است** (شوکِ ماندگار + قراردادِ هم‌راستا). ` +
        `طبق ماسکِ pre-shiftِ بک‌تست، ورود دو کندل بعد از رویداد است ⇒ ` +
        `سیگنالِ ورود روی **کندلِ بعد** صادر می‌شود. هنوز معامله‌ای نیست.`
      : `رنجِ کندلِ بسته (${(rngI / GOLD_PIP).toFixed(1)} pip) به ${(ratioI * 100).toFixed(0)}٪ آستانهٔ ` +
        `شوک (${(thrI / GOLD_PIP).toFixed(1)} pip) رسیده، بدنه ماندگار است (ρ=${rhoI.toFixed(3)}) و ` +
        `گیتِ قرارداد هم **هم‌راستاست**. اگر شوکِ کامل بسازد، دو کندل بعد ورود صادر می‌شود. ` +
        `هنوز معامله‌ای نیست.`
  } else if (!geomOk || !eventAtrOk) {
    reason = `ATR(${cfg.atrWin}) هنوز معتبر نیست (گرم‌شدن یا رنجِ صفر) — لایه در انتظار.`
  } else if ((baseUp || baseDn) && dir === 0) {
    // مهم‌ترین حالتِ آموزنده: پایهٔ S965 روشن شد ولی گیتِ قراردادِ S919 آن را رد کرد.
    const bodyDir = baseUp ? 'صعودی' : 'نزولی'
    reason =
      `شوکِ ماندگار رخ داد (رنج ${(rngE / GOLD_PIP).toFixed(1)} pip ≥ ${(thrE / GOLD_PIP).toFixed(1)} pip · ` +
      `ρ=${rhoE.toFixed(3)} · بدنهٔ ${bodyDir}) — یعنی **پایهٔ S965 روشن است** — ولی گیتِ قراردادِ ` +
      `${cfg.driftK}-کندلی (≈${driftDays} روز) خلافِ بدنه است ` +
      `(${Number.isFinite(driftDelta) ? (driftDelta >= 0 ? '+' : '') + (driftDelta / GOLD_PIP).toFixed(0) : '—'} pip) ` +
      `⇒ این لایه ورود نمی‌دهد. بازارِ کینزی چنین شوکی را «اختلالِ موقت» می‌خواند و جذب می‌کند: ` +
      `بازوی خلافِ قرارداد در اندازه‌گیری فقط WR=۴۲.۱٪ (n=۱۳۳) داد در برابرِ ۵۵.۶۶٪ بازوی هم‌راستا. ` +
      `⚠️ توجه: این کارت H6 است و S965 روی H8 وصل است ⇒ کارت‌های متفاوت، تصمیم‌های جدا.`
  } else if (isShock && !isPermanent) {
    reason =
      `شوک رخ داد (رنج ${(rngE / GOLD_PIP).toFixed(1)} pip ≥ ${(thrE / GOLD_PIP).toFixed(1)} pip) ولی ` +
      `ماندگاری کم است: ρ=${rhoE.toFixed(3)} < ${cfg.rhoMin} — یعنی قیمت **درونِ همان کندل** بخشِ بزرگی ` +
      `از حرکت را پس گرفت (سایهٔ بلند) ⇒ امضای جریانِ **نویز**، نه مطلع ⇒ بدونِ ورود.`
  } else {
    reason =
      `کندلِ رویداد (ماقبلِ آخر) شوک نیست: رنج ${(rngE / GOLD_PIP).toFixed(1)} pip یعنی ` +
      `${(ratioE * 100).toFixed(0)}٪ آستانهٔ ${cfg.theta}×ATR(${cfg.atrWin})=${(thrE / GOLD_PIP).toFixed(1)} pip. ` +
      `این لایه کم‌بسامد است (۱۰۶ معامله در ۱۵.۶ سال ≈ ۶.۸ در سال) — خنثی بودنش حالتِ عادی است، نه خرابی.`
  }

  return {
    active, approaching, direction,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? (nextIsEvent
        ? `رویدادِ کامل ثبت شد — ورود روی کندلِ بعد (ماسکِ pre-shift ⇒ رویداد+۲)`
        : `منتظرِ شوکِ کامل (رنج ≥ ${cfg.theta}×ATR(${cfg.atrWin})) با ρ ≥ ${cfg.rhoMin} — گیتِ قرارداد هم‌اکنون باز است`)
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS919(
  cfg: S919Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS919(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s919_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10
  const driftDays = Math.round((cfg.driftK * cfg.tfHours) / 24)
  const holdDays = Math.round((cfg.maxHold * cfg.tfHours) / 24)

  const meta: DecideMeta = {
    code: 'S919',
    name: `شوکِ مطلعِ هم‌راستا با قرارداد (${cfg.tfFa})`,
    kind: 'convention_informed_shock' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ شناورِ عینِ بک‌تست: SL=${slPipShow} / TP=${tpPipShow} pip ` +
      `(${cfg.kSl}× و ${cfg.kTp}×ATR(${cfg.atrWin}) تا کندلِ رویداد؛ میانهٔ تاریخی ≈۱۱۵.۸/۱۸۷.۳ pip، RR=۱.۶۱۸). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندلِ ${cfg.tfFa} (≈${holdDays} روز) نگه‌دار. ` +
      `🔴 **زمان‌بندیِ ورود:** بک‌تست ماسکِ از پیش شیفت‌شده دارد ⇒ ورود در openِ کندلِ ` +
      `**دومِ** پس از کندلِ شوک است، نه کندلِ بعدیِ آن. سایت همین را رعایت می‌کند ` +
      `(رویداد روی کندلِ ماقبلِ آخر سنجیده می‌شود). اگر یک کندل زودتر وارد شوید، ` +
      `WRِ اندازه‌گیری‌شده از ۵۵.۶۶٪ به ۴۸.۱۱٪ سقوط می‌کند (زیرِ سربه‌سر) — این عدد سنجیده شده است. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false در بک‌تست). ` +
      `⚠️ هیچ مدیریتِ فعالی (BE/trailing) آزموده و تأیید نشده ⇒ فقط TP/SL/زمان. ` +
      `ℹ️ هم‌پوشانی: S965/S966 روی H8 وصل‌اند و رویدادها ذاتاً هم‌پوشان‌اند (یک شوکِ ۸ساعته ` +
      `اغلب شوکِ ۶ساعته هم هست) ⇒ اگر کارتِ H6 و H8 هم‌زمان روشن شدند، صفِ FIFO/سایزِ محتاط.`,
    filters: [
      `شوکِ رنج: high−low ≥ ${cfg.theta}×ATR(${cfg.atrWin})[t−1] — پایهٔ منجمدِ S965`,
      `ماندگاری ρ = |close−open|÷(high−low) ≥ ${cfg.rhoMin} — پایهٔ منجمدِ S965 (Kyle 1985)`,
      `گیتِ قراردادِ کینزی (${cfg.driftK} کندل ≈ ${driftDays} روز، قاعدهٔ S604): لانگ فقط اگر close[t−1] > close[t−1−${cfg.driftK}]، شورت آینه‌ای`,
      `بازوی خلافِ قرارداد در اندازه‌گیری WR=۴۲.۱٪ داد (ابطال‌گرِ P3 گذشت) و بازوی بی‌گیت ۴۸.۱٪ (P1 گذشت)`,
      `هندسهٔ نامتقارنِ TP>SL (${cfg.kSl}/${cfg.kTp} ⇒ RR=۱.۶۱۸) · صفر پارامترِ جست‌وجو‌شده · ~۶.۸ معامله در سال`,
      `🔴 قلمرو: فقط ${cfg.tfFa} — کارتِ H3 با RQS2=۱۶.۰ رد شد (تعمیم ممنوع)`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
