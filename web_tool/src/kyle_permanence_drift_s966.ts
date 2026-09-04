// ---------------------------------------------------------------------------
// S966 — «ماندگاریِ کایل × هم‌راستاییِ درفت» (Kyle Permanence, Drift-Aligned)
// XAUUSD-H8 — تنها کارتِ ACCEPT
//
// حکمِ نهایی (سند: results/S966_KylePermanenceDriftAligned_Xauusd_H8_rqs2_86_ACCEPT.md):
//   RQS2 = **85.8** · هر ۱۱ دروازهٔ H0..H10 سبز · notes خالی
//   n=73 · WR=61.64٪ · lift=+19.32pp · z=3.21 · p_perm=6.61e−04 · PF=2.466 · net=+$5,054
//   نول: K=500 جایگشت · draw=73 · uncond_n=11,711 · n_trials=620 (تجمعیِ صادقانه)
//
// فیزیکِ لایه — **تأییدِ جریانِ مطلع در دو مقیاسِ زمانیِ مستقل**:
//   ① مقیاسِ کندل (Kyle 1985): شوکِ با retention بالا اثرِ قیمتیِ **دائمی**
//      می‌گذارد ⇒ همان پایهٔ منجمدِ S965 (رنج ≥ 2.618×ATR21[i−1] و ρ ≥ 0.618).
//   ② مقیاسِ ماه (TSM؛ Moskowitz-Ooi-Pedersen 2012): جریانِ مطلعِ بلندمدت خودش
//      را در درفتِ K-کندلی نشان می‌دهد ⇒ گیتِ علّیِ K=180 کندلِ H8 (≈۶۰ روز).
//   وقتی هر دو مقیاس هم‌جهت‌اند، ادامه **قوی‌تر** است.
//
// ⚠️ **S966 زیرمجموعهٔ اکیدِ S965 است** (پایهٔ یکسان + یک گیتِ اضافه). پس هر
//    سیگنالِ S966 لزوماً سیگنالِ S965 هم هست — دو **لایهٔ خواهر** روی یک کارت،
//    نه دو لبهٔ مستقل. روی حسابِ واقعی **سایزِ مشترک** الزامی است؛ جزئیات در
//    manageNote و در کامنتِ CARD_LAYERS ثبت شده است.
//
// آزمونِ تفکیک‌گرِ P1 (قانونِ S603/S964 — گیت باید اطلاعات بیفزاید نه توان بسوزاند):
//   پایهٔ بی‌گیت روی نیمهٔ کشف:  n=82 · WR=58.54٪ · lift=+18.155pp
//   بازوی aligned K=180:        n=46 · WR=63.04٪ · lift=**+22.75pp** ✓ گذشت
//   ⇒ نیمی از معاملات حذف شد ولی lift +۴.۶pp بالا رفت = گیتِ اطلاعات‌افزا.
//
// ⚠️ **قانونِ MTF — تعمیم ممنوع.** پیش‌ثبت قلمرو را به دو کارت قفل کرده بود
//   (H8 و H6 — تنها کارت‌هایی که پایهٔ S965 در آن‌ها زنده بود):
//     · H8 = ✅ ACCEPT 85.8 (بازوی aligned · K=180)
//     · H6 = ❌ REJECT 7.8  (z=0.59 · برندهٔ کشف بازوی counter بود ⇒ گیت روی
//                            پایهٔ مرده معجزه نکرد — عیناً منتشر شد)
//   ⇒ **فقط یک کارت وصل می‌شود: XAUUSD-H8.**
//
// ⚠️ پورتِ **مو-به-موی** strategies/s966_kyle_permanence_drift.py
//    (features / drift_up / member_signals / _run). دامِ پورت — چهارتا:
//    ① ATR = میانگینِ سادهٔ ۲۱تاییِ TR با `_rollsum` سپس **شیفتِ ۱** (atr_prev)
//       — نه Wilder/ewm.
//    ② `_rollsum` در ۲۰ عضوِ اول «جمعِ جزئی ÷ ۲۱» می‌دهد؛ عیناً بازتولید شود.
//    ③ هندسه از **atr_prev** ساخته می‌شود، نه ATR کندلِ شوک (وگرنه look-ahead).
//    ④ 🆕 گیتِ درفت **دو کندل** علّی است: `close[i−1] > close[i−1−K]` —
//       کندلِ i (خودِ شوک) اصلاً لمس نمی‌شود. اگر اشتباهاً `close[i]` بگذاریم،
//       شوک خودش درفت را می‌سازد و لایه به نویز تبدیل می‌شود.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

export interface S966Config {
  id: string          // شناسهٔ کارت (XAUUSD-H8)
  tfFa: string        // برچسبِ فارسیِ تایم‌فریم
  theta: number       // آستانهٔ شوک: high−low ≥ theta×ATR21[i−1] (منجمد از S965: 2.618)
  rhoMin: number      // کفِ ماندگاری ρ (منجمد از S965: 0.618)
  atrWin: number      // پنجرهٔ ATR (منجمد: 21)
  driftK: number      // 🆕 گیتِ درفتِ علّی: close[i−1] در برابرِ close[i−1−K] (قفل‌شده: 180)
  kSl: number         // SL = kSl × ATR21[i−1] (منجمد: 1.272)
  kTp: number         // TP = kTp × ATR21[i−1] (منجمد: 2.058 ⇒ TP>SL ✓)
  maxHold: number     // بیشینهٔ نگه‌داری بر حسبِ کندلِ H8 (منجمد: 16)
  warm: number        // گرم‌شدنِ بک‌تست (منجمد: 250)
  approachFrac: number // «نزدیک‌شدن»: رنج ≥ approachFrac×آستانه (فقط UI)
}

export const S966_CFG: Record<string, S966Config> = {
  // تنها کارتِ ACCEPT. عددها از results/_scan_S966/H8.json::member
  // (فینالیستِ Path C — gate=aligned, K=180؛ صفر تیونِ پس از کشف).
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    theta: 2.618, rhoMin: 0.618, atrWin: 21, driftK: 180,
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

export interface S966Features {
  atrPrev: number[]    // ATR21 علّی (شیفتِ ۱) بر حسبِ قیمت
  rng: number[]        // high − low
  rho: number[]        // |close−open| / rng  (ماندگاریِ درون-کندلی)
  bodySgn: number[]    // علامتِ بدنه
  driftUp: boolean[]   // 🆕 close[i−1] >  close[i−1−K]
  driftDn: boolean[]   // 🆕 close[i−1] <  close[i−1−K]
}

// پورتِ عینِ features() + drift_up() — همه علّی.
export function s966Features(candles: Candle[], cfg: S966Config): S966Features {
  const n = candles.length
  const W = cfg.atrWin
  const K = cfg.driftK

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

  // 🆕 گیتِ درفتِ علّی — پورتِ عینِ:
  //   du[K+1:]       = c[K:-1] >  c[:-(K+1)]
  //   dn_drift[K+1:] = c[K:-1] <  c[:-(K+1)]
  // یعنی برای ایندکسِ t (≥ K+1): close[t−1] در برابرِ close[t−1−K].
  // پیش از t = K+1 هر دو false می‌مانند (عینِ np.zeros) — دامِ ④.
  const driftUp = new Array<boolean>(n).fill(false)
  const driftDn = new Array<boolean>(n).fill(false)
  for (let t = K + 1; t < n; t++) {
    const a = candles[t - 1].close
    const b = candles[t - 1 - K].close
    driftUp[t] = a > b
    driftDn[t] = a < b
  }

  return { atrPrev, rng, rho, bodySgn, driftUp, driftDn }
}

// ---------------------------------------------------------------------------
// computeS966 — سیگنال روی آخرین کندلِ بستهٔ i = n−1 (ورود در openِ کندلِ بعد)
// ---------------------------------------------------------------------------
export function computeS966(candles: Candle[], cfg: S966Config): RawSignal {
  const n = candles.length
  // کفِ داده: گیتِ درفت به close[i−1−K] نیاز دارد ⇒ دستِ‌کم K+2 کندل.
  // (ATR21+شیفت ۱ فقط ۲۳ کندل می‌خواهد؛ درفت قیدِ سخت‌تر است.)
  const minBars = Math.max(cfg.atrWin + 2, cfg.driftK + 2)

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  if (n < minBars) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 136 * GOLD_PIP, tpDist: 219 * GOLD_PIP, maxHoldBars: cfg.maxHold,
      reason:
        `دادهٔ کافی نیست: این لایه دستِ‌کم ${minBars} کندلِ بستهٔ ${cfg.tfFa} لازم دارد ` +
        `(گیتِ درفتِ ${cfg.driftK}-کندلی + ATR(${cfg.atrWin}) علّی) — موجود: ${n}.`,
      indicators: emptyInd,
    }
  }

  const f = s966Features(candles, cfg)
  const i = n - 1                                  // آخرین کندلِ بسته‌شده

  const atrPrev = f.atrPrev[i]
  const rng = f.rng[i]
  const rho = f.rho[i]
  const sgn = f.bodySgn[i]
  const valid = atrPrev > 1e-12 && rng > 0

  // هندسهٔ شناور = عینِ بک‌تست: از atr_prev (دامِ ③).
  const slPip = Math.max((cfg.kSl * atrPrev) / GOLD_PIP, 1e-9)
  const tpPip = Math.max((cfg.kTp * atrPrev) / GOLD_PIP, 1e-9)
  const slDist = slPip * GOLD_PIP
  const tpDist = tpPip * GOLD_PIP

  const thr = cfg.theta * atrPrev                  // آستانهٔ شوک بر حسبِ قیمت
  const isShock = valid && rng >= thr
  const isPermanent = rho >= cfg.rhoMin
  // پایهٔ S965 (بی‌گیت): شوکِ ماندگار با بدنهٔ غیرصفر
  const baseUp = isShock && isPermanent && sgn > 0
  const baseDn = isShock && isPermanent && sgn < 0
  // 🆕 گیتِ aligned: لانگ فقط با درفتِ مثبت، شورت فقط با درفتِ منفی
  const gateOk = (baseUp && f.driftUp[i]) || (baseDn && f.driftDn[i])
  const active = gateOk
  const direction: 'LONG' | 'SHORT' = baseDn ? 'SHORT' : 'LONG'

  // درفتِ خام برای نمایش (اختلافِ قیمتِ ۱۸۰ کندل، هر دو سر علّی)
  const cPrev = candles[i - 1].close
  const cRef = candles[i - 1 - cfg.driftK].close
  const driftDelta = cPrev - cRef
  const driftAligned = (sgn > 0 && f.driftUp[i]) || (sgn < 0 && f.driftDn[i])

  // «نزدیک‌شدن» (فقط اطلاع‌رسانی؛ هیچ معامله‌ای از این شاخه صادر نمی‌شود):
  // رنج در ۸۵–۱۰۰٪ آستانه · بدنه هم‌اکنون ماندگار · **و درفت هم‌راستاست**.
  // اگر درفت هم‌راستا نباشد، «نزدیک‌شدن» دروغ است چون گیت هرگز باز نمی‌شود.
  const approaching = valid && !active && !isShock &&
    rng >= cfg.approachFrac * thr && isPermanent && sgn !== 0 && driftAligned

  const ratio = thr > 0 ? rng / thr : 0
  const driftDays = Math.round((cfg.driftK * 8) / 24)   // ۱۸۰ کندلِ H8 ≈ ۶۰ روز

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
      // 🆕 شاخصِ یکتای این لایه نسبت به خواهرش S965
      name: `🆕 گیتِ درفتِ علّیِ ${cfg.driftK} کندل (≈${driftDays} روز) — close[i−1] در برابرِ close[i−1−${cfg.driftK}]`,
      value: `${driftDelta >= 0 ? '+' : ''}${(driftDelta / GOLD_PIP).toFixed(0)} pip ` +
        `(${f.driftUp[i] ? 'درفتِ صعودی' : (f.driftDn[i] ? 'درفتِ نزولی' : 'بی‌تغییر')})` +
        `${sgn !== 0 ? (driftAligned ? ' ✓ هم‌راستا با بدنه' : ' ✗ خلافِ بدنه ⇒ گیت بسته') : ''}`,
      status: driftAligned ? 'ok' : 'bad',
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
    const driftDir = direction === 'LONG' ? 'صعودی' : 'نزولی'
    reason =
      `**تأییدِ دو-مقیاسه** روی کندلِ ${cfg.tfFa} بسته‌شده: ` +
      `① مقیاسِ کندل — شوکِ ماندگار: رنج ${(rng / GOLD_PIP).toFixed(1)} pip ` +
      `≥ ${cfg.theta}×ATR(${cfg.atrWin})=${(thr / GOLD_PIP).toFixed(1)} pip (${(ratio * 100).toFixed(0)}٪ آستانه) ` +
      `با ماندگاری ρ=${rho.toFixed(3)} ≥ ${cfg.rhoMin} و بدنهٔ ${bodyDir}. ` +
      `② مقیاسِ ماه — درفتِ علّیِ ${cfg.driftK} کندل (≈${driftDays} روز) هم ${driftDir} است ` +
      `(${driftDelta >= 0 ? '+' : ''}${(driftDelta / GOLD_PIP).toFixed(0)} pip) ⇒ گیت باز ⇒ سیگنالِ ${side}. ` +
      `فیزیکِ اندازه‌گیری‌شده: بدنهٔ ماروبوزو-گونه یعنی اثرِ قیمتی درونِ کندل پس نگرفت ` +
      `(Kyle 1985 — امضای جریانِ مطلع)، و هم‌راستاییِ آن با درفتِ چندماهه یعنی همان جریان ` +
      `در مقیاسِ بزرگ‌تر هم جاری است (TSM؛ Moskowitz-Ooi-Pedersen 2012) ⇒ ادامهٔ قوی‌تر. ` +
      `(۷۳ معامله در ۱۵.۶ سال · WR=۶۱.۶۴٪ · lift=+۱۹.۳۲pp · z=۳.۲۱ · PF=۲.۴۶۶ · هر ۱۱ دروازهٔ RQS2 سبز؛ ` +
      `آزمونِ P1: گیت نیمی از معاملات را حذف کرد ولی lift را از +۱۸.۱۶ به +۲۲.۷۵pp برد ⇒ اطلاعات‌افزا). ` +
      `ورود روی openِ کندلِ بعد؛ SL=${slPip.toFixed(1)} / TP=${tpPip.toFixed(1)} pip. ` +
      `⚠️ اگر لایهٔ خواهر S965 هم‌زمان روشن است، **یک رویداد** است نه دو ⇒ سایزِ مشترک.`
  } else if (approaching) {
    reason =
      `رنجِ کندلِ بسته (${(rng / GOLD_PIP).toFixed(1)} pip) به ${(ratio * 100).toFixed(0)}٪ آستانهٔ ` +
      `شوک (${(thr / GOLD_PIP).toFixed(1)} pip) رسیده، بدنه ماندگار است (ρ=${rho.toFixed(3)}) و ` +
      `گیتِ درفتِ ${cfg.driftK}-کندلی هم **هم‌راستاست**. اگر کندلِ بعد شوکِ کامل بسازد، ورود صادر می‌شود. ` +
      `هنوز معامله‌ای نیست.`
  } else if (!valid) {
    reason = `ATR(${cfg.atrWin}) هنوز معتبر نیست (گرم‌شدن یا رنجِ صفر) — لایه در انتظار.`
  } else if ((baseUp || baseDn) && !gateOk) {
    // مهم‌ترین حالتِ آموزنده: پایهٔ S965 روشن شد ولی گیتِ S966 آن را رد کرد.
    const bodyDir = baseUp ? 'صعودی' : 'نزولی'
    reason =
      `شوکِ ماندگار رخ داد (رنج ${(rng / GOLD_PIP).toFixed(1)} pip ≥ ${(thr / GOLD_PIP).toFixed(1)} pip · ` +
      `ρ=${rho.toFixed(3)} · بدنهٔ ${bodyDir}) — یعنی **پایهٔ S965 روشن است** — ولی گیتِ درفتِ ` +
      `${cfg.driftK}-کندلی (≈${driftDays} روز) خلافِ بدنه است ` +
      `(${driftDelta >= 0 ? '+' : ''}${(driftDelta / GOLD_PIP).toFixed(0)} pip) ⇒ این لایه ورود نمی‌دهد. ` +
      `دقیقاً همین صافیِ سخت‌گیرانه است که WR را از ۵۴.۷۹٪ به ۶۱.۶۴٪ و PF را از ۱.۸۱ به ۲.۴۶۶ برد ` +
      `(به بهایِ نصف‌شدنِ تعدادِ معاملات). خواهرِ بی‌گیتِ همین کارت (S965) ممکن است ورود بدهد — ` +
      `آن یک تصمیمِ جداست، نه تأییدِ این لایه.`
  } else if (isShock && !isPermanent) {
    reason =
      `شوک رخ داد (رنج ${(rng / GOLD_PIP).toFixed(1)} pip ≥ ${(thr / GOLD_PIP).toFixed(1)} pip) ولی ` +
      `ماندگاری کم است: ρ=${rho.toFixed(3)} < ${cfg.rhoMin} — یعنی قیمت **درونِ همان کندل** بخشِ بزرگی ` +
      `از حرکت را پس گرفت (سایهٔ بلند) ⇒ امضای جریانِ **نویز**، نه مطلع ⇒ بدونِ ورود.`
  } else {
    reason =
      `کندلِ بستهٔ اخیر شوک نیست: رنج ${(rng / GOLD_PIP).toFixed(1)} pip یعنی ${(ratio * 100).toFixed(0)}٪ ` +
      `آستانهٔ ${cfg.theta}×ATR(${cfg.atrWin})=${(thr / GOLD_PIP).toFixed(1)} pip. این لایه **کم‌بسامدترینِ** ` +
      `کارت است (۷۳ معامله در ۱۵.۶ سال ≈ ۴.۷ در سال) — خنثی بودنش حالتِ عادی است، نه خرابی.`
  }

  return {
    active, approaching, direction,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ شوکِ کامل (رنج ≥ ${cfg.theta}×ATR(${cfg.atrWin})) با ρ ≥ ${cfg.rhoMin} روی کندلِ بعد — گیتِ درفت هم‌اکنون باز است`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS966(
  cfg: S966Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS966(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s966_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10
  const driftDays = Math.round((cfg.driftK * 8) / 24)

  const meta: DecideMeta = {
    code: 'S966',
    name: `ماندگاریِ کایل × هم‌راستاییِ درفت (${cfg.tfFa})`,
    kind: 'kyle_permanence_drift' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ شناورِ عینِ بک‌تست: SL=${slPipShow} / TP=${tpPipShow} pip ` +
      `(${cfg.kSl}× و ${cfg.kTp}×ATR(${cfg.atrWin}) **کندلِ i−1**؛ میانهٔ تاریخی ≈۱۳۶/۲۱۹ pip). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندلِ ${cfg.tfFa} (≈۵.۳ روز) نگه‌دار. ` +
      `⚠️⚠️ **سایزِ مشترک با S965 الزامی:** S966 زیرمجموعهٔ اکیدِ S965 است (پایهٔ یکسان + ` +
      `گیتِ درفت) ⇒ هر سیگنالِ S966 حتماً سیگنالِ S965 هم هست. اگر هر دو کارت روشن شدند، ` +
      `**یک معامله** بگیرید نه دو — وگرنه ریسک ۲× می‌شود و حکمِ اندازه‌گیری‌شده بی‌اعتبار است. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false در بک‌تست). ` +
      `⚠️ هیچ مدیریتِ فعالی (BE/trailing) آزموده و تأیید نشده ⇒ فقط TP/SL/زمان.`,
    filters: [
      `شوکِ رنج: high−low ≥ ${cfg.theta}×ATR(${cfg.atrWin})[i−1] — پایهٔ منجمدِ S965`,
      `ماندگاری ρ = |close−open|÷(high−low) ≥ ${cfg.rhoMin} — پایهٔ منجمدِ S965`,
      `🆕 گیتِ درفتِ علّیِ ${cfg.driftK} کندل (≈${driftDays} روز): لانگ فقط اگر close[i−1] > close[i−1−${cfg.driftK}]، شورت آینه‌ای`,
      `بازوی counter (قرینه) در کشف باخت ⇒ روایتِ «هم‌راستایی» تأیید شد (ابطال‌گرِ P2)`,
      `هندسهٔ نامتقارنِ TP>SL (${cfg.kSl}/${cfg.kTp}) ⇒ صفر تورشِ WR-سازی · ~۴.۷ معامله در سال`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
