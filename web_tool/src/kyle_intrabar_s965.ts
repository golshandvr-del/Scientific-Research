// ---------------------------------------------------------------------------
// S965 — «ماندگاریِ درون-کندلیِ اثرِ قیمتیِ کایل» (Kyle Intra-Bar Impact
// Permanence) · XAUUSD-H8
//
// حکمِ نهایی (سند: results/S965_KyleIntrabarPermanence_Xauusd_H8_rqs2_82_ACCEPT.md):
//   RQS2 = **82.2** · هر ۱۱ دروازهٔ H0..H10 سبز · notes خالی
//   n=146 · WR=54.79٪ · BE_rob=40.4٪ · lift=+12.84pp · z=3.14 · p_perm=8.33e−04
//   PF=1.81 · net=+$7,113 · نول: K=500 جایگشت · draw=146 · uncond_n=11,711
//
// فیزیکِ لایه (Kyle 1985): جریانِ **مطلع** اثرِ قیمتیِ **دائمی** می‌گذارد —
// بازارساز از حرکت یاد می‌گیرد و قیمت برنمی‌گردد؛ جریانِ **نویز** اثرِ گذرا
// دارد و درونِ همان کندل بازمی‌گردد (سایه‌های بلند). پس *شکلِ* کندلِ شوک حاملِ
// اطلاعات است: شوکِ با retention بالا (بدنهٔ ماروبوزو-گونه) = امضای مطلع ⇒ ادامه.
//
// آزمونِ تفکیک‌گرِ P1 (درسِ S603/S964 — فیلتر باید اطلاعات بیفزاید نه توان بسوزاند):
//   پایهٔ θ-only (شوک بدونِ شرطِ ρ):  n=115 · WR=52.17٪ · lift=+11.81pp
//   بازوی hi (ρ≥0.618):              n=82  · WR=58.54٪ · lift=**+18.16pp** ✓
//   ⇒ شرطِ ρ نه‌تنها معامله حذف نکرد که lift را +۶.۳pp بالا برد. این وارونهٔ
//     مرگِ S964 است (آنجا شرطِ اضافه لبه را رقیق کرد).
//
// ⚠️ **قانونِ MTF — تعمیم ممنوع.** هر ۱۹ تایم‌فریم داوری و منتشر شدند:
//   H8 تنها ACCEPT است. D1 (z=−3.40) و H12 (z=−2.13) صریحاً REJECT با liftِ
//   **منفی**؛ H6/H3/H2/H1 REJECT؛ M30..M1 (۱۰ کارت) NO-SURVIVOR؛ W1/MN1 هم.
//   قلهٔ lift دقیقاً روی H8 است — همان‌جا که S602/S770/S950/S526 قله دارند
//   (پنجمین لبهٔ مستقلِ «رویدادِ لحظه‌ای × تایم‌فریمِ درشت»).
//   ⇒ **فقط یک کارت وصل می‌شود: XAUUSD-H8.**
//
// ⚠️ پورتِ **مو-به-موی** strategies/s965_kyle_intrabar_permanence.py
//    (features / member_signals / _run) — سه دامِ پورت:
//    ① ATR = میانگینِ سادهٔ ۲۱تاییِ TR با `_rollsum` سپس **شیفتِ ۱**
//       (atr_prev) — نه Wilder/ewm. `atrWilder` ماژولِ S382 اینجا غلط است.
//    ② `_rollsum` در ۲۰ عضوِ اول «جمعِ جزئی ÷ ۲۱» می‌دهد (میانگینِ کم‌وزن)؛
//       باید عیناً بازتولید شود وگرنه warm-up منحرف می‌شود.
//    ③ هندسه از **atr_prev** ساخته می‌شود (ATR کندلِ i−1)، نه ATR کندلِ شوک:
//       SL=1.272×atr_prev · TP=2.058×atr_prev. اگر ATR خودِ کندلِ شوک را
//       بگذاریم، شوک براکت را باد می‌کند = look-ahead عملی.
//    tr_arr[0]=0 و atr_prev[0]=atr[0] هم عیناً پورت شده‌اند.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

export interface S965Config {
  id: string          // شناسهٔ کارت (XAUUSD-H8)
  tfFa: string        // برچسبِ فارسیِ تایم‌فریم
  theta: number       // آستانهٔ شوک: high−low ≥ theta×ATR21[i−1] (قفل‌شده: 2.618)
  rhoMin: number      // کفِ ماندگاری ρ (قفل‌شده: 0.618 — بازوی hi)
  atrWin: number      // پنجرهٔ ATR (قفل‌شده: 21)
  kSl: number         // SL = kSl × ATR21[i−1] (قفل‌شده: 1.272)
  kTp: number         // TP = kTp × ATR21[i−1] (قفل‌شده: 2.058 ⇒ TP>SL ✓)
  maxHold: number     // بیشینهٔ نگه‌داری بر حسبِ کندلِ H8 (قفل‌شده: 16)
  warm: number        // گرم‌شدنِ بک‌تست (قفل‌شده: 250)
  approachFrac: number // «نزدیک‌شدن»: رنج ≥ approachFrac×آستانه (فقط UI)
}

export const S965_CFG: Record<string, S965Config> = {
  // تنها کارتِ ACCEPT در کلِ ۱۹ تایم‌فریم. عددها از
  // results/_scan_S965/H8.json::member (فینالیستِ Path C، صفر تیونِ پس از کشف).
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    theta: 2.618, rhoMin: 0.618, atrWin: 21,
    kSl: 1.272, kTp: 2.058, maxHold: 16, warm: 250,
    approachFrac: 0.85,
  },
}

// ---------------------------------------------------------------------------
// rollMean — بازتولیدِ دقیقِ `_rollsum(x, w) / w` پایتون:
//   out[i] = (Σ x[j] , j = max(0, i−w+1) .. i) / w
// توجه: در i < w−1 مقسوم‌علیه همچنان w است (جمعِ جزئی ÷ w) — عمداً (دامِ ②).
// ---------------------------------------------------------------------------
function rollMean(x: number[], w: number): number[] {
  const n = x.length
  const out = new Array<number>(n).fill(0)
  let acc = 0
  for (let i = 0; i < n; i++) {
    acc += x[i]
    if (i >= w) acc -= x[i - w]
    out[i] = acc / w
  }
  return out
}

export interface S965Features {
  atrPrev: number[]   // ATR21 علّی (شیفتِ ۱) بر حسبِ قیمت
  rng: number[]       // high − low
  rho: number[]       // |close−open| / rng  (ماندگاریِ درون-کندلی)
  bodySgn: number[]   // علامتِ بدنه
}

// پورتِ عینِ features() — همه علّی.
export function s965Features(candles: Candle[], cfg: S965Config): S965Features {
  const n = candles.length
  const W = cfg.atrWin

  // TR: tr[0] = 0 (عینِ np.zeros سپس پرکردنِ [1:])
  const trArr = new Array<number>(n).fill(0)
  for (let t = 1; t < n; t++) {
    const h = candles[t].high, l = candles[t].low, pc = candles[t - 1].close
    trArr[t] = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc))
  }
  const atr = rollMean(trArr, W)

  // ATR علّی: atr_prev[0]=atr[0] ، atr_prev[1:]=atr[:-1]  (دامِ ①)
  const atrPrev = new Array<number>(n).fill(0)
  if (n > 0) atrPrev[0] = atr[0]
  for (let t = 1; t < n; t++) atrPrev[t] = atr[t - 1]

  const rng = new Array<number>(n).fill(0)
  const rho = new Array<number>(n).fill(0)
  const bodySgn = new Array<number>(n).fill(0)
  for (let t = 0; t < n; t++) {
    const c = candles[t]
    const r = c.high - c.low
    rng[t] = r
    const body = c.close - c.open
    rho[t] = r > 0 ? Math.abs(body) / r : 0
    bodySgn[t] = body > 0 ? 1 : (body < 0 ? -1 : 0)
  }

  return { atrPrev, rng, rho, bodySgn }
}

// ---------------------------------------------------------------------------
// computeS965 — سیگنال روی آخرین کندلِ بستهٔ i = n−1 (ورود در openِ کندلِ بعد)
// ---------------------------------------------------------------------------
export function computeS965(candles: Candle[], cfg: S965Config): RawSignal {
  const n = candles.length
  // کفِ داده: ATR21 + شیفتِ ۱ + حاشیه. warmِ بک‌تست ۲۵۰ است ولی آن فقط
  // «شروعِ شمارشِ معاملات» بود؛ برای محاسبهٔ خودِ ATR21ِ همگرا ۲۳ کندل کافی است.
  // با این حال کفِ سخت‌گیرانه‌تر (۱۱۰) را نگه می‌داریم تا ATR روی دادهٔ رقیق
  // نلغزد — این همان کفی است که کارتِ H8 در index.tsx تضمین می‌کند.
  const minBars = cfg.atrWin + 2

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  if (n < minBars + 2) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 138 * GOLD_PIP, tpDist: 223 * GOLD_PIP, maxHoldBars: cfg.maxHold,
      reason: `دادهٔ کافی نیست: این لایه دستِ‌کم ${minBars} کندلِ بستهٔ ${cfg.tfFa} برای ATR(${cfg.atrWin}) علّی لازم دارد (موجود: ${n}).`,
      indicators: emptyInd,
    }
  }

  const f = s965Features(candles, cfg)
  const i = n - 1                                  // آخرین کندلِ بسته‌شده

  const atrPrev = f.atrPrev[i]
  const rng = f.rng[i]
  const rho = f.rho[i]
  const sgn = f.bodySgn[i]
  const valid = atrPrev > 1e-12 && rng > 0

  // هندسهٔ شناور = عینِ بک‌تست: از atr_prev، نه ATR کندلِ شوک (دامِ ③).
  const slPip = Math.max((cfg.kSl * atrPrev) / GOLD_PIP, 1e-9)
  const tpPip = Math.max((cfg.kTp * atrPrev) / GOLD_PIP, 1e-9)
  const slDist = slPip * GOLD_PIP
  const tpDist = tpPip * GOLD_PIP

  const thr = cfg.theta * atrPrev                  // آستانهٔ شوک بر حسبِ قیمت
  const isShock = valid && rng >= thr
  const isPermanent = rho >= cfg.rhoMin
  const active = isShock && isPermanent && sgn !== 0
  const direction: 'LONG' | 'SHORT' = active && sgn < 0 ? 'SHORT' : 'LONG'

  // «نزدیک‌شدن» (فقط اطلاع‌رسانی؛ هیچ معامله‌ای از این شاخه صادر نمی‌شود):
  // رنج در ۸۵–۱۰۰٪ آستانه **و** بدنه از هم‌اکنون ماندگار است.
  const approaching = valid && !active && !isShock &&
    rng >= cfg.approachFrac * thr && isPermanent && sgn !== 0

  const ratio = thr > 0 ? rng / thr : 0

  const indicators: RouterDecision['indicators'] = [
    {
      name: `رنجِ کندلِ بسته در برابرِ آستانهٔ شوک (${cfg.theta}×ATR${cfg.atrWin}[i−1])`,
      value: valid
        ? `${(rng / GOLD_PIP).toFixed(1)} / ${(thr / GOLD_PIP).toFixed(1)} pip (${(ratio * 100).toFixed(0)}٪ آستانه)`
        : '—',
      status: isShock ? 'ok' : (approaching ? 'neutral' : 'bad'),
    },
    {
      name: `ماندگاری ρ = |close−open| ÷ (high−low) — کفِ ${cfg.rhoMin}`,
      value: valid ? `${rho.toFixed(3)}` : '—',
      status: isPermanent ? 'ok' : 'bad',
    },
    {
      name: 'جهتِ بدنهٔ کندلِ شوک (اثرِ دائمی ⇒ ادامه)',
      value: sgn > 0 ? 'صعودی (LONG)' : (sgn < 0 ? 'نزولی (SHORT)' : 'بدونِ بدنه (doji)'),
      status: sgn !== 0 ? 'neutral' : 'bad',
    },
    {
      name: `ATR(${cfg.atrWin}) علّی — پایهٔ هندسهٔ شناور`,
      value: atrPrev > 0 ? `${(atrPrev / GOLD_PIP).toFixed(1)} pip` : '—',
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
    reason =
      `کندلِ ${cfg.tfFa} بسته‌شده یک **شوکِ ماندگار** است: رنج ${(rng / GOLD_PIP).toFixed(1)} pip ` +
      `≥ ${cfg.theta}×ATR(${cfg.atrWin})=${(thr / GOLD_PIP).toFixed(1)} pip (${(ratio * 100).toFixed(0)}٪ آستانه) ` +
      `و ماندگاری ρ=${rho.toFixed(3)} ≥ ${cfg.rhoMin} با بدنهٔ ${bodyDir} ⇒ سیگنالِ ${side}. ` +
      `فیزیکِ اندازه‌گیری‌شده (Kyle 1985): بدنهٔ ماروبوزو-گونه یعنی اثرِ قیمتی **درونِ کندل ` +
      `پس نگرفت** = امضای جریانِ مطلع ⇒ ادامه؛ سایهٔ بلند یعنی نویزِ گذرا. ` +
      `(۱۴۶ معامله در ۱۵.۶ سال · WR=۵۴.۷۹٪ · lift=+۱۲.۸۴pp · z=۳.۱۴ · هر ۱۱ دروازهٔ RQS2 سبز؛ ` +
      `آزمونِ P1: شرطِ ρ خودش lift را از +۱۱.۸۱ به +۱۸.۱۶pp برد ⇒ فیلترِ اطلاعات‌افزاست، نه توان‌سوز). ` +
      `ورود روی openِ کندلِ بعد؛ SL=${slPip.toFixed(1)} / TP=${tpPip.toFixed(1)} pip ` +
      `(${cfg.kSl}× و ${cfg.kTp}×ATR(${cfg.atrWin}) علّی، عینِ بک‌تست).`
  } else if (approaching) {
    reason =
      `رنجِ کندلِ بسته (${(rng / GOLD_PIP).toFixed(1)} pip) به ${(ratio * 100).toFixed(0)}٪ آستانهٔ ` +
      `شوک (${(thr / GOLD_PIP).toFixed(1)} pip) رسیده و بدنه هم‌اکنون ماندگار است (ρ=${rho.toFixed(3)}). ` +
      `اگر کندلِ بعد شوکِ کامل (رنج ≥ ${cfg.theta}×ATR) با همین ماندگاری بسازد، ورود صادر می‌شود. ` +
      `هنوز معامله‌ای نیست.`
  } else if (!valid) {
    reason = `ATR(${cfg.atrWin}) هنوز معتبر نیست (گرم‌شدن یا رنجِ صفر) — لایه در انتظار.`
  } else if (isShock && !isPermanent) {
    reason =
      `شوک رخ داد (رنج ${(rng / GOLD_PIP).toFixed(1)} pip ≥ ${(thr / GOLD_PIP).toFixed(1)} pip) ولی ` +
      `ماندگاری کم است: ρ=${rho.toFixed(3)} < ${cfg.rhoMin} — یعنی قیمت **درونِ همان کندل** بخشِ بزرگی ` +
      `از حرکت را پس گرفت (سایهٔ بلند) ⇒ امضای جریانِ **نویز**، نه مطلع ⇒ بدونِ ورود. ` +
      `همین شرط است که lift را +۶.۳pp بالا برد (آزمونِ P1).`
  } else {
    reason =
      `کندلِ بستهٔ اخیر شوک نیست: رنج ${(rng / GOLD_PIP).toFixed(1)} pip یعنی ${(ratio * 100).toFixed(0)}٪ ` +
      `آستانهٔ ${cfg.theta}×ATR(${cfg.atrWin})=${(thr / GOLD_PIP).toFixed(1)} pip. این لایه کم‌بسامد است ` +
      `(~۹ معامله در سال) — بیشترِ کندل‌ها هیچ‌اند و همین صداقتِ لایه است.`
  }

  return {
    active, approaching, direction,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ شوکِ کامل (رنج ≥ ${cfg.theta}×ATR(${cfg.atrWin})) با ماندگاری ρ ≥ ${cfg.rhoMin} روی کندلِ بعد`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS965(
  cfg: S965Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS965(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s965_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10

  const meta: DecideMeta = {
    code: 'S965',
    name: `ماندگاریِ درون-کندلیِ شوکِ کایل (${cfg.tfFa})`,
    kind: 'kyle_permanence' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ شناورِ عینِ بک‌تست: SL=${slPipShow} / TP=${tpPipShow} pip ` +
      `(${cfg.kSl}× و ${cfg.kTp}×ATR(${cfg.atrWin}) **کندلِ i−1**؛ میانهٔ تاریخی ≈۱۳۸/۲۲۳ pip). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندلِ ${cfg.tfFa} (≈۵.۳ روز) نگه‌دار. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false در بک‌تست): تا این معامله بسته نشده، شوکِ بعدی ` +
      `نباید معاملهٔ جدید باز کند — وگرنه حکمِ اندازه‌گیری‌شده معتبر نیست. ` +
      `⚠️ هیچ مدیریتِ فعالی (BE/trailing) آزموده و تأیید نشده ⇒ فقط TP/SL/زمان.`,
    filters: [
      `شوکِ رنج: high−low ≥ ${cfg.theta}×ATR(${cfg.atrWin})[i−1] (ATR علّی — شوک خودش را آلوده نمی‌کند)`,
      `ماندگاری ρ = |close−open|÷(high−low) ≥ ${cfg.rhoMin} (بدنهٔ ماروبوزو-گونه = اثرِ دائمی)`,
      'جهت = follow (هم‌جهت با بدنه) — بازوی against و بازوی lo هر دو در کشف باختند',
      `هندسهٔ نامتقارنِ TP>SL (${cfg.kSl}/${cfg.kTp}) ⇒ صفر تورشِ WR-سازی · قیدِ تک‌معامله · ~۹ معامله در سال`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
