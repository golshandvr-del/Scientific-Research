// ---------------------------------------------------------------------------
// S1520 — «سقفِ تازهٔ ۹۰-کندلی × کندلِ مطلع» (Informed Fresh High) · XAUUSD-H8
//
// حکمِ نهایی (سند: results/S1520_InformedFreshHigh_Xauusd_H8_rqs2_91_ACCEPT.md):
//   RQS2 = **90.6** · هر ۱۱ دروازهٔ H0..H10 سبز · notes خالی · n_trials=17
//   تنش n_trials=50 ⇒ ACCEPT 90.0 (حکم زیرِ بودجهٔ سخت‌تر هم می‌ماند)
//   n=147 (از ۲۲۲ سیگنال) · WR=59.86٪ · BE=40.73٪ · lift=+19.13pp
//   z=3.83 · p_perm≈۰ · PF=2.314 · net=+$10,483 · ۹.۴ معامله در سال
//   SL=179.67pip · TP=269.50pip (RR 1.5 ⇒ TP>SL)
//
// فیزیکِ لایه (Kyle 1985 روی یک لنگرِ ساختاری):
//   سقفِ تازهٔ ۹۰-کندلی یک **«کجا»** است؛ ρ یک **«چگونه»**. سقفِ تازه‌ای که با
//   بدنهٔ پُر بسته می‌شود، جریانِ سفارشِ **مطلع** است و اثرِ قیمتی‌اش می‌ماند
//   ⇒ ادامه. سقفِ تازه‌ای با سایهٔ بالاییِ بلند، شکستِ **رد‌شده** است — بازار
//   سقف را نپذیرفت. S526 (والد، ACCEPT 88.2) هر دو گونه را می‌خرید و
//   +14.77pp گرفت؛ S1520 گونهٔ دوم را کنار می‌گذارد و به +19.13pp می‌رسد.
//
// ⭐ **قانونِ بلوکِ دومِ گاوس (نخستین قانون آن):** روی H8، «رویدادِ ساختاری ×
//   کیفیتِ هم‌کندل» هم‌افزاست، در حالی که «رویدادِ ساختاری × رژیمِ درفت»
//   هم‌خط بود (S529 با همان پایه شکست خورد). یعنی گیتی که از **همان کندل**
//   اطلاعات می‌گیرد (ρ) می‌تواند مستقل از گیتی باشد که از **تاریخ** می‌گیرد
//   (درفت) — چون رویدادِ سقف‌تازه تاریخ را از قبل جذب کرده اما ریزساختارِ
//   کندل را نه.
//
// آزمون‌های ابطال‌گرِ پیش‌ثبت‌شده — هر دو پاس:
//   P1 (ضدِ سوختنِ توان): lift گیت‌شده باید اکیداً از پایهٔ S526 (+14.77pp)
//      بیشتر باشد ⇒ **+19.13 > +14.77 ✓** و z **3.83 > 3.23 ✓**. پس گیت
//      اطلاعات افزود، فقط معامله حذف نکرد. (وارونهٔ مرگِ S529.)
//   P2 (بازوی مکمل): بازوی ρ<0.618 ⇒ REJECT 24.2 · lift +10.27 ≪ +19.13 ✓
//      (Δ = ۸.۹pp) — پس ρ برای این رویداد روی H8 اطلاعاتِ واقعی دارد.
//   نرخِ عبورِ گیت (قانونِ S529: >۷۵٪ = گیتِ مرده): ۲۲۲/۳۶۱ = **۶۱.۵٪** ⇒
//      گیت **زنده** است. این عدد **پیش از** هر PnL سنجیده و پیش‌ثبت شد.
//
// ⚠️ **قانونِ MTF — چرا فقط یک کارت.** هر سه کارتِ پیش‌ثبت‌شده داوری شدند:
//   · XAUUSD-H8  ⇒ **ACCEPT 90.6** (تنها ACCEPT) ⇒ وصل می‌شود
//   · XAUUSD-H4  ⇒ REJECT 16.7 (n=284 · lift=+3.64 · z=0.95)
//   · XAUUSD-H12 ⇒ UNPROVEN 27.1 (n=104 · lift=+16.15 · z=1.80)
//   قاعدهٔ MTF «همهٔ تایم‌فریم‌های ACCEPT باید وصل شوند» اینجا **دقیقاً یک**
//   کارت می‌دهد. H4 حتی **وارونه** شد (بازوی counter +10.93 > gated +3.64):
//   روی H4 کندلِ پُربدنهٔ سقف‌شکن احتمالاً «اورشوتِ درون‌روزی» است نه اطلاعات؛
//   H8 (۳ کندل در روز) کیفیتِ **جلسه‌ای** را می‌گیرد. این تکرارِ قانونِ S525
//   است: خصوصیت‌های ریزساختاری روی تایم‌فریمِ درشت معنی دارند.
//   ⇒ اتصالِ H4/H12 «برای یکدستی» ممنوع است؛ شاهدِ منفیِ اجراشدنی برای هر دو
//     در results/_s1520_parity/ صادر شده تا اثبات شود این تصمیمِ حکمی است،
//     نه یک باگِ سکوتِ پورت.
//
// ⚠️⚠️ **قیدِ پرتفوی — S1520 جانشینِ S526 است، نه رقیبش** (قانونِ S605):
//   ۱۲۱ از ۱۴۷ ورود (۸۲.۳٪) با S526 مشترک است؛ ۲۶ ورودِ باقی همان‌هایی‌اند
//   که در S526 با FIFO مسدود می‌شدند. همان رویداد، خالص‌تر:
//     n ۲۰۰→۱۴۷ (−۲۶٪) · WR ۵۵.۵→۵۹.۹ · PF ۱.۹۴→۲.۳۱ · lift +۱۴.۷۷→+۱۹.۱۳
//     z ۳.۲۳→۳.۸۳ — در **هر** سنجه بهتر.
//   S526 روی سایت وصل **نیست** ⇒ تعارضی وجود ندارد. اگر روزی وصل شود،
//   **باید** یکی از این دو حذف گردد؛ هرگز هم‌زمان معامله نشوند.
//   هم‌پوشانی با S382-H4 زنده: ۵۷.۱٪ · بخشِ غیرِ هم‌پوشان n=۶۳ WR=۵۳.۹۷٪
//   lift=**+۱۳.۲۳pp** ⇒ ارزشِ مستقلِ واقعی بیرون از پوزیشن‌های بازِ H4 دارد
//   (فیلترِ حذف لازم نیست، فقط سایزِ مشترک).
//
// ⚠️ پورتِ **مو-به-موی** tools/s1520_informed_fresh_high_runner.py و ماشینِ
//    ارثی‌اش (strategies/s382_williamsr_momentum.py). چهار دامِ پورت که با
//    پریتی عددی اثبات شدند — هر کدام اگر رعایت نشود جمعیتِ داوری‌شده را
//    عوض می‌کند و حکمِ ۹۰.۶ را بی‌اعتبار:
//
//    ① **ρ علامت‌دار است، نه قدرمطلق.** رانر می‌نویسد
//       `(close − open) / (high − low)`. برادرِ این لایه S965 از
//       `|close − open|` استفاده می‌کند چون دوجهته است، ولی S1520
//       **LONG-only** است و بدنهٔ صعودی **لازمهٔ** سیگنال. اگر کسی abs()
//       بگذارد، کندل‌های **نزولیِ** پُربدنه هم سیگنال می‌گیرند.
//    ② **ATR = Wilder با `ewm(alpha=1/100, adjust=False)`**، نه میانگینِ
//       سادهٔ ۱۰۰تایی. برادرِ S965 عمداً میانگینِ ساده دارد (`_rollsum`)؛
//       جابه‌جا کردنِ این دو، هندسه را جابه‌جا می‌کند.
//    ③ **هندسه از میانهٔ کلِ تاریخ می‌آید، نه ATR کندلِ جاری.** رانرِ
//       s382_mtf: `sl_abs = nanmedian(ATR100(کلِ سری)) × 1.5`. پس SL یک
//       عددِ **ثابتِ منجمد** است (۱۷۹.۶۷ pip روی H8)، برخلافِ S965/S607 که
//       هندسهٔ **شناور** دارند. سایت نمی‌تواند این میانه را از پنجرهٔ کوتاهِ
//       خودش بازتولید کند ⇒ عدد از artifactِ پریتی **منجمد** وارد شده است.
//    ④ **رویداد است، نه حالت.** `nh & ~nh.shift(1)`: یک گردشِ چند-کندلی
//       بالای سقفِ ۹۰ کندلی **یک** فرصت است نه چند فرصت. اگر پورت شرط را
//       به‌صورتِ حالت بخواند، بسامد چند برابر متورم می‌شود.
//
//    ⑤ **بک‌تست هیچ time-stop ندارد.** simulate_trades تا برخوردِ TP یا SL
//       می‌رود (بیشینهٔ مشاهده‌شده ۶۵ کندلِ H8). پس maxHold یک پارامترِ حکم
//       **نیست**؛ برای UI روی ۹۶ گذاشته شد که ۱۰۰٪ معاملاتِ داوری‌شده را
//       می‌پوشاند (میانه ۴ · p90 ۱۹ · p95 ۲۷ · بیشینه ۶۵) ⇒ سقف هرگز
//       معامله‌ای را که حکم شمرده است نمی‌بُرد. اگر کسی ۱۶ بگذارد
//       («مثلِ S965»)، ۱۱.۶٪ معاملات را زودتر می‌بندد = هندسهٔ دیگری.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

export interface S1520Config {
  id: string           // شناسهٔ کارت (XAUUSD-H8)
  tfFa: string         // برچسبِ فارسیِ تایم‌فریم
  lookback: number     // پنجرهٔ سقفِ غلتان (قفل‌شده: 90 — ارثی از S526)
  rhoMin: number       // کفِ کیفیتِ کندل ρ (قفل‌شده: 0.618 — ارثی از S965)
  atrP: number         // پنجرهٔ ATR ویلدر (قفل‌شده: 100 — ارثی از S382)
  slK: number          // ضریبِ SL روی میانهٔ ATR (قفل‌شده: 1.5)
  rr: number           // TP = rr × SL (قفل‌شده: 1.5 ⇒ TP>SL)
  slPip: number        // **منجمد** از پریتی: median(ATR100)×1.5 روی ۱۵.۶ سال
  tpPip: number        // **منجمد** = slPip × rr
  maxHold: number      // سقفِ نمایشیِ نگه‌داری (۹۶ = پوششِ ۱۰۰٪ — دامِ ⑤)
  approachFrac: number // «نزدیک‌شدن»: close ≥ approachFrac×سقفِ ۹۰ (فقط UI)
  rqs2: number         // نمرهٔ حکم (برای شفافیتِ UI)
}

export const S1520_CFG: Record<string, S1520Config> = {
  // تنها کارتِ ACCEPT از سه کارتِ پیش‌ثبت‌شده (H8/H4/H12).
  // اعداد از results/_s1520/XAUUSD_H8_gated.json و results/_s1520_parity/XAUUSD_H8.json
  // (گیتِ سلامت: n_signals 222 · n_trades 147 · WR 59.86 · SL 179.67 · TP 269.50 — همه OK).
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    lookback: 90, rhoMin: 0.618, atrP: 100,
    slK: 1.5, rr: 1.5,
    slPip: 179.67, tpPip: 269.50,
    maxHold: 96, approachFrac: 0.995,
    rqs2: 90.6,
  },
}

// ---------------------------------------------------------------------------
// atrWilder — پورتِ عینِ `atr()` در s382_williamsr_momentum.py:
//   tr = max(h−l, |h−pc|, |l−pc|) سپس `ewm(alpha=1/p, adjust=False).mean()`
// دقتِ حیاتی (دامِ ②): این **Wilder** است نه میانگینِ سادهٔ ۱۰۰تایی.
// مقدارِ آغازین در pandas با adjust=False برابرِ نخستین مشاهده است ⇒ tr[0].
// ---------------------------------------------------------------------------
export function atrWilderS1520(candles: Candle[], p: number): number[] {
  const n = candles.length
  const out = new Array<number>(n).fill(NaN)
  if (n === 0) return out
  const alpha = 1.0 / p
  // tr[0]: پایتون `h−pc` را با pc=NaN می‌سازد ⇒ max فقط h−l را می‌بیند.
  let prev = candles[0].high - candles[0].low
  out[0] = prev
  for (let i = 1; i < n; i++) {
    const h = candles[i].high, l = candles[i].low, pc = candles[i - 1].close
    const tr = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc))
    prev = alpha * tr + (1 - alpha) * prev
    out[i] = prev
  }
  return out
}

export interface S1520Features {
  priorMax: number[]   // max(close[i−lookback .. i−1]) — علّی (shift 1)
  rho: number[]        // (close−open)/(high−low) — **علامت‌دار** (دامِ ①)
  atr: number[]        // ATR100 ویلدر
  fresh: boolean[]     // لبهٔ تازه: nh ∧ ¬nh[i−1] (دامِ ④)
  gated: boolean[]     // fresh ∧ ρ ≥ rhoMin
}

/** پورتِ عینِ fresh_high()/rho() رانر — همه علّی، هیچ look-ahead. */
export function s1520Features(candles: Candle[], cfg: S1520Config): S1520Features {
  const n = candles.length
  const L = cfg.lookback

  const priorMax = new Array<number>(n).fill(NaN)
  // rolling(L).max().shift(1) ⇒ نخستین مقدارِ معتبر در i = L است.
  for (let i = L; i < n; i++) {
    let m = -Infinity
    for (let j = i - L; j <= i - 1; j++) if (candles[j].close > m) m = candles[j].close
    priorMax[i] = m
  }

  const rho = new Array<number>(n).fill(0)
  for (let i = 0; i < n; i++) {
    const c = candles[i]
    const rng = c.high - c.low
    // .replace(0, NaN) سپس .fillna(0.0) ⇒ رنجِ صفر ⇒ ρ = 0
    rho[i] = rng > 0 ? (c.close - c.open) / rng : 0
  }

  const atr = atrWilderS1520(candles, cfg.atrP)

  // nh = close > priorMax ؛ NaN ⇒ false (عینِ .fillna(False))
  const nh = new Array<boolean>(n).fill(false)
  for (let i = 0; i < n; i++) {
    nh[i] = isFinite(priorMax[i]) && candles[i].close > priorMax[i]
  }
  // لبهٔ تازه: nh ∧ ¬nh[i−1] — با nh[−1] = false (دامِ ④)
  const fresh = new Array<boolean>(n).fill(false)
  const gated = new Array<boolean>(n).fill(false)
  for (let i = 0; i < n; i++) {
    fresh[i] = nh[i] && !(i > 0 ? nh[i - 1] : false)
    gated[i] = fresh[i] && rho[i] >= cfg.rhoMin
  }

  return { priorMax, rho, atr, fresh, gated }
}

// ---------------------------------------------------------------------------
// computeS1520 — سیگنال روی آخرین کندلِ **بسته‌شده** i = n−1.
// ورود در openِ کندلِ بعد (عینِ simulate_trades که از e+1 شروع می‌کند).
// ---------------------------------------------------------------------------
export function computeS1520(candles: Candle[], cfg: S1520Config): RawSignal {
  const n = candles.length
  // کفِ داده: سقفِ غلتان ۹۰ کندلی + شیفتِ ۱ ⇒ ۹۱ کندل حداقلِ ریاضی.
  // حاشیه‌ای برای هم‌گراییِ ATR100 هم لازم است تا مقادیرِ warm-up لایه را
  // نلغزاند؛ پس کفِ عملی = lookback + atrP.
  const minBars = cfg.lookback + cfg.atrP

  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP

  if (n < minBars) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason:
        `دادهٔ کافی نیست: این لایه دستِ‌کم ${minBars} کندلِ بستهٔ ${cfg.tfFa} لازم دارد ` +
        `(سقفِ غلتانِ ${cfg.lookback} کندلی + هم‌گراییِ ATR(${cfg.atrP})) — موجود: ${n}.`,
      indicators: [{ name: 'داده', value: 'ناکافی', status: 'neutral' }],
    }
  }

  const f = s1520Features(candles, cfg)
  const i = n - 1                                   // آخرین کندلِ بسته‌شده

  const close = candles[i].close
  const pMax = f.priorMax[i]
  const rho = f.rho[i]
  const atrNow = f.atr[i]

  const isFreshHigh = f.fresh[i]
  const isInformed = rho >= cfg.rhoMin
  const active = f.gated[i]

  // «نزدیک‌شدن» — فقط اطلاع‌رسانی؛ هیچ معامله‌ای از این شاخه صادر نمی‌شود.
  // شرط: قیمت به ۹۹.۵٪ سقفِ ۹۰-کندلی رسیده ولی هنوز از آن نگذشته است.
  const nearHigh = isFinite(pMax) && !isFreshHigh &&
    close >= cfg.approachFrac * pMax && close <= pMax
  const approaching = nearHigh

  const distPip = isFinite(pMax) ? (pMax - close) / GOLD_PIP : NaN
  const pctOfHigh = isFinite(pMax) && pMax > 0 ? (close / pMax) * 100 : NaN

  const indicators: RouterDecision['indicators'] = [
    {
      name: `سقفِ closeِ ${cfg.lookback} کندلِ گذشته (علّی — بدونِ کندلِ جاری)`,
      value: isFinite(pMax)
        ? `${pMax.toFixed(2)}$ · فاصلهٔ close: ${distPip > 0 ? '+' : ''}${(-distPip).toFixed(1)} pip (${pctOfHigh.toFixed(2)}٪ سقف)`
        : '—',
      status: isFreshHigh ? 'ok' : (nearHigh ? 'neutral' : 'bad'),
    },
    {
      name: 'لبهٔ **تازه** (کندلِ قبل سقف‌شکن نبوده — رویداد، نه حالت)',
      value: isFreshHigh ? 'بله — همین کندل نخستین شکست است' : 'خیر',
      status: isFreshHigh ? 'ok' : 'bad',
    },
    {
      name: `کیفیتِ کندلِ مطلع ρ = (close−open) ÷ (high−low) — کفِ ${cfg.rhoMin}`,
      value: `${rho.toFixed(3)}${rho < 0 ? ' (کندلِ نزولی)' : ''}`,
      status: isInformed ? 'ok' : 'bad',
    },
    {
      name: `ATR(${cfg.atrP}) ویلدرِ جاری (فقط شفافیت — هندسه منجمد است)`,
      value: isFinite(atrNow) ? `${(atrNow / GOLD_PIP).toFixed(1)} pip` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (منجمد از میانهٔ ۱۵.۶ سال)',
      value: `${cfg.slPip} / ${cfg.tpPip} pip (نسبت ${cfg.rr} ⇒ TP>SL)`,
      status: 'ok',
    },
  ]

  let reason: string
  if (active) {
    reason =
      `کندلِ ${cfg.tfFa} بسته‌شده یک **سقفِ تازهٔ مطلع** ساخت: close=${close.toFixed(2)}$ از ` +
      `سقفِ closeِ ${cfg.lookback} کندلِ گذشته (${pMax.toFixed(2)}$) گذشت و کندلِ قبل سقف‌شکن ` +
      `**نبود** (لبهٔ تازه، نه ادامهٔ یک گردش)، و کیفیتِ کندل ρ=${rho.toFixed(3)} ≥ ${cfg.rhoMin} ` +
      `است ⇒ سیگنالِ **خرید**. ` +
      `فیزیکِ اندازه‌گیری‌شده (Kyle 1985 روی لنگرِ ساختاری): سقفِ تازه «کجا» را می‌گوید و ρ ` +
      `«چگونه» را — سقفی که با بدنهٔ پُر بسته می‌شود جریانِ سفارشِ **مطلع** است و اثرش می‌ماند؛ ` +
      `سقفی با سایهٔ بالاییِ بلند شکستِ **رد‌شده** است. ` +
      `(۱۴۷ معامله در ۱۵.۶ سال · WR=۵۹.۸۶٪ در برابرِ سربه‌سرِ ۴۰.۷۳٪ · lift=+۱۹.۱۳pp · ` +
      `z=۳.۸۳ · PF=۲.۳۱ · RQS2=${cfg.rqs2} با هر ۱۱ دروازه سبز؛ آزمونِ P1: همین گیتِ ρ ` +
      `liftِ والد S526 را از +۱۴.۷۷ به +۱۹.۱۳pp برد ⇒ اطلاعات‌افزاست نه توان‌سوز، و بازوی ` +
      `مکملِ ρ<${cfg.rhoMin} فقط +۱۰.۲۷ گرفت). ` +
      `ورود روی openِ کندلِ بعد؛ SL=${cfg.slPip} / TP=${cfg.tpPip} pip.`
  } else if (approaching) {
    reason =
      `قیمت به سقفِ closeِ ${cfg.lookback} کندلی نزدیک شده اما از آن نگذشته است: ` +
      `close=${close.toFixed(2)}$ در برابرِ سقفِ ${pMax.toFixed(2)}$ (فاصله ${distPip.toFixed(1)} pip، ` +
      `${pctOfHigh.toFixed(2)}٪ سقف). اگر کندلی **بالای** این سقف ببندد **و** بدنه‌اش ` +
      `دستِ‌کم ${(cfg.rhoMin * 100).toFixed(1)}٪ دامنهٔ همان کندل باشد (ρ ≥ ${cfg.rhoMin})، ` +
      `ورود صادر می‌شود. هنوز معامله‌ای نیست.`
  } else if (isFreshHigh && !isInformed) {
    reason =
      `سقفِ تازه **رخ داد** (close=${close.toFixed(2)}$ > ${pMax.toFixed(2)}$) ولی کندل ` +
      `**مطلع نیست**: ρ=${rho.toFixed(3)} < ${cfg.rhoMin} — یعنی قیمت بخشِ بزرگی از حرکت را ` +
      `درونِ همان کندل پس داد (سایهٔ بالاییِ بلند) یا کندل نزولی بسته شد. این «شکستِ رد‌شده» ` +
      `است: بازار سقفِ نو را نپذیرفت ⇒ بدونِ ورود. ` +
      `همین شرط است که lift را از +۱۴.۷۷ به +۱۹.۱۳pp برد (آزمونِ P1) و بازوی مکملش صریحاً ` +
      `REJECT گرفت (lift +۱۰.۲۷ · z=۱.۳۷).`
  } else {
    reason =
      `کندلِ بستهٔ اخیر سقفِ تازه نساخت: close=${close.toFixed(2)}$ در برابرِ سقفِ closeِ ` +
      `${cfg.lookback} کندلی ${isFinite(pMax) ? pMax.toFixed(2) + '$' : '—'} ` +
      `(${isFinite(pctOfHigh) ? pctOfHigh.toFixed(2) + '٪ سقف' : '—'}). این لایه کم‌بسامد است ` +
      `(~۹.۴ معامله در سال) — بیشترِ کندل‌ها هیچ‌اند و همین صداقتِ لایه است.`
  }

  return {
    active, approaching, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ بسته‌شدنِ یک کندل **بالای** سقفِ ${cfg.lookback} کندلی با بدنهٔ ρ ≥ ${cfg.rhoMin}`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS1520(
  cfg: S1520Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS1520(candles, cfg)
  const price = a.price

  // این لایه LONG-only است ⇒ رژیمِ سبک همیشه صعودی.
  const reg: RegimeInfo = {
    regime: 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: 'bull',
    bucket: `s1520_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S1520',
    name: `سقفِ تازهٔ ${cfg.lookback}-کندلی × کندلِ مطلع (${cfg.tfFa})`,
    kind: 'informed_fresh_high' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ **منجمد** (نه شناور): SL=${cfg.slPip} / TP=${cfg.tpPip} pip — از ` +
      `median(ATR(${cfg.atrP}))×${cfg.slK} روی کلِ ۱۵.۶ سالِ ${cfg.tfFa} گرفته شده و در سایت ` +
      `بازتولید نمی‌شود (پنجرهٔ سایت کوتاه است) ⇒ عدد از artifactِ پریتی می‌آید. ` +
      `تا برخورد به TP یا SL نگه‌دار. ` +
      `⚠️ بک‌تست **هیچ time-stop نداشت**؛ بیشینهٔ نگه‌داریِ مشاهده‌شده ۶۵ کندلِ ${cfg.tfFa} ` +
      `بود (میانه ۴ · p95 ۲۷). سقفِ ${cfg.maxHold} کندلیِ سایت ۱۰۰٪ معاملاتِ داوری‌شده را ` +
      `می‌پوشاند، پس هرگز معامله‌ای را که حکم شمرده است نمی‌بُرد. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false): تا این معامله بسته نشده، سقفِ تازهٔ بعدی ` +
      `نباید معاملهٔ جدید باز کند — وگرنه حکمِ اندازه‌گیری‌شده معتبر نیست. ` +
      `⚠️ **قیدِ سایزِ مشترک با S382-H4:** هم‌پوشانیِ سنجیده‌شده ۵۷.۱٪. بخشِ غیرِ هم‌پوشان ` +
      `مستقلاً سودده است (lift +۱۳.۲۳pp) پس لایه حذف نمی‌شود، ولی اگر معاملهٔ H4 بازست ` +
      `سایزِ مشترک بگیرید. ` +
      `⚠️ **S1520 جانشینِ S526 است، نه رقیبش** (۸۲.۳٪ ورودِ مشترک): اگر روزی S526 هم وصل ` +
      `شود، هرگز هم‌زمان معامله نشوند. ` +
      `⚠️ هیچ مدیریتِ فعالی (BE/trailing) آزموده و تأیید نشده ⇒ فقط TP/SL.`,
    filters: [
      `سقفِ تازهٔ ${cfg.lookback}-کندلی: close > max(close[i−${cfg.lookback}..i−1]) **و** کندلِ قبل سقف‌شکن نبوده (رویداد، نه حالت — ارثی از S526)`,
      `گیتِ کندلِ مطلع: ρ = (close−open) ÷ (high−low) ≥ ${cfg.rhoMin} روی همان کندل — **علامت‌دار**، پس بدنهٔ صعودی لازم است (ارثی از S965)`,
      'جهت = LONG-only (قانونِ S522/S528) — هیچ بازوی SHORTی آزموده نشد',
      `هندسهٔ نامتقارنِ TP>SL (${cfg.slK}×median(ATR${cfg.atrP}) و ${cfg.rr}×) ⇒ صفر تورشِ WR-سازی · قیدِ تک‌معامله · ~۹.۴ معامله در سال`,
      `صفر پارامترِ آزاد: پنجرهٔ ${cfg.lookback} از S526، آستانهٔ ${cfg.rhoMin} از S965، هندسه از S382 — هیچ عددی در این نشست جست‌وجو نشد (ضدِ اشتباهِ ۸)`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
