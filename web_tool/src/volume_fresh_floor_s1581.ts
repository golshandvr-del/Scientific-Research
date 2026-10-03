// ---------------------------------------------------------------------------
// S1581 — «کفِ تازهٔ ۹۰ × تأییدِ حجمِ هم‌اسلات» (Volume-Confirmed Fresh Floor)
//         · XAUUSD-**H6**
//
// حکمِ نهایی (سند: results/S1581_VolumeConfirmedFreshFloor_Xauusd_H6_rqs2_88_ACCEPT.md):
//   · XAUUSD-H6 ⇒ RQS2 = **88.0** (تنشِ n_trials=50 ⇒ 86.6) · هر ۱۱ دروازه سبز
//     n=219 (از ۳۲۶ سیگنال، ۱۴.۰/سال) · WR=52.97٪ · BE=40.87٪ · lift=+12.10pp
//     z=3.33 · PF=1.769 · net=+$10,038 · SL=152.10 pip · TP=228.14 pip (RR 1.5)
//   · XAUUSD-H8 ⇒ **POWER-LIMITED 26.2** · XAUUSD-H4 ⇒ **POWER-LIMITED 28.7**
//     ⇒ عامدانه وصل نمی‌شوند (قانونِ MTF در جهتِ عکسش: تعمیم بدونِ شاهد ممنوع).
//
// فیزیکِ لایه (Wyckoff «effort vs result» · Karpoff 1987 · S589/S1580 LAW):
//   «کفِ تازه» = **غیابِ عرضه** (کلِ کندل بالای همهٔ کف‌های ۹۰ کندلِ اخیر) و
//   حجمِ نسبیِ هم‌اسلات = **حاملِ اطلاعات**. روی رویدادهای «سطح/ساختار» حجم
//   بُعدِ مستقل است و توان می‌افزاید؛ روی رویدادهای «دامنه/نوسان» زائد است.
//   اینجا آزمونِ بیرونیِ موفقِ همان قانون است: کفِ تازهٔ **بدونِ** حجم روی H4
//   فقط +1.44pp داشت؛ با حجم +8.47pp (و روی H6 خودِ لایه ACCEPT شد).
//
// ⭐ رابطه با S1516-H6 (کارتِ زندهٔ همین کارت) — اندازه‌گیری‌شده، نه فرض:
//   ابزار: tools/s1581_false_witness_audit.py · سند: results/_s1581/false_witness.json
//   کنترلِ ابزار: n_signals منتشرشدهٔ artifact = ۳۲۶ عیناً بازتولید شد ⇒ معتبر.
//     · S1581 در برابرِ S1516-H6: shared ۲۸۷ · share_of_S1581 **۸۸.۰٪** ·
//       jaccard **۰.۶۳۵** · size_ratio **۰.۷۸۹** ⇒ **FALSE-WITNESS** (بالای هر دو
//       آستانهٔ ۰.۶۰/۰.۷۵). یعنی روی این کارت، S1581 و S1516 عمدتاً **یک رویدادِ
//       کفِ تازه با دو اسم**اند — همان شکلی که پروندهٔ S404/S408 دربارهٔ آن
//       هشدار می‌دهد (jaccard ۶۹.۳٪ ⇒ «یکی، نه هر دو»).
//   ⇒ به‌همین‌دلیل این لایه در `FALSE_WITNESS_PAIRS` ثبت شده است (یک سطر در
//     `strategy_registry.ts`، همان مکانیزمِ اجراشدنی): اگر هر دو هم‌زمان فعال
//     شوند، ضعیف‌تر حذف و در `falseWitness` گزارش می‌شود تا کاربر دو شاهدِ
//     مستقل نبیند. **افزودنِ این لایه کماکان مجاز است** چون:
//       (۱) روی **همهٔ تایم‌فریم‌های ACCEPTش** (فقط H6) وصل می‌شود؛
//       (۲) ابعادِ اطلاعاتیِ متفاوتی دارد: S1581 ستونِ `volume` را می‌خواند و
//           S1516 فقط OHLC ⇒ ۱۲٪ رویدادهای غیرمشترک + گیتِ حجم؛
//       (۳) مکانیزمِ شاهدِ کاذب از دوباره‌شماریِ روی صفحه جلوگیری می‌کند.
//     در برابرِ سه ساکنِ دیگرِ H6 قاطعانه مستقل است:
//       S919 jaccard 0.0047 · S955 0.0191 · S607 0.0081.
//   ⚠️ **در برابرِ والدِ وصل‌نشدهٔ S1511 (L=90):** share ۱۰۰٪ (ذاتی — S1581 همان
//      رویداد است + یک گیت). S1511 روی سایت وصل **نیست** ⇒ تعارضی نیست؛ قیدِ
//      ماندگار: اگر روزی وصل شود، یکی از این دو (و S1516) باید حذف گردد.
//
// 🔴 **دام‌های پورت — با مرجعِ عددی بسته شدند** (نه با چشم).
//   مرجع: results/_s1581/XAUUSD_H6_gated.json + بازتولیدِ عینِ هارنسِ S1511/S382.
//   ① **رویداد روی `low` است، نه `close`** (ارثی از S1511/S1516): `low[i] >
//      max(low[i−90..i−1])`. پورتِ اشتباه روی close رویدادِ دیگری می‌سازد.
//   ② **لبهٔ تازه، نه حالت** (`ff ∧ ¬ff[i−1]`) — وگرنه یک روندِ صعودی ده‌ها
//      سیگنالِ پشت‌سرهم می‌دهد و n متورم می‌شود.
//   ③ **گیتِ درفتِ علّی:** `close[i−1] − close[i−90] > 0` (از i−1 نه i).
//   ④ **گیتِ حجم روی حجمِ هم‌اسلات است، نه حجمِ خام:** میانهٔ ۳۰ رخدادِ قبلیِ
//      **همان ساعتِ روز** (shift(1) درونِ گروه، min_periods=20). حجمِ H6 فصلیّتِ
//      درون‌روزیِ ۲–۳× دارد؛ حجمِ خام عملاً «گیتِ ساعتِ روز» می‌سازد.
//   ⑤ **اگر فید حجم نداشته باشد یا اسلات گرم نشده باشد، لایه سکوت می‌کند** —
//      به‌جای سقوطِ بی‌صدا به رویدادِ بی‌گیت که لبهٔ اندازه‌گیری‌شده‌اش کمتر است.
//   ⑥ **ورود روی `close` کندلِ سیگنال است** (هارنس `entry = close[e]`).
//   ⑦ **pip طلا = ۰.۱$** (نه ۰.۰۱): حسابِ مرجع CONTRACT_SIZE=100 · spread=$0.33
//      = ۳.۳ pip. SL ۱۵۲.۱۰ pip ⇒ **۱۵.۲۱$** فاصله (مثلِ S589/S955/S919 — نه
//      عددِ اشتباهِ ۰.۰۱ که S1516 به‌کار می‌برد).
//   ⑧ **maxHold پارامترِ حکم نیست**؛ بک‌تست هیچ time-stop نداشت. توزیعِ واقعیِ
//      نگه‌داری روی ۲۱۹ معاملهٔ مرجع: کمینه ۱ · میانه ۴ · p95 ۲۹ · **بیشینه ۸۴**
//      ⇒ سقفِ ۱۰۰ هرگز معاملهٔ داوری‌شده‌ای را نمی‌بُرد.
//
// منابع: S1511 (رویدادِ کفِ تازه) · S589 (گیتِ حجمِ هم‌اسلات) · S1580 (قانونِ
//        حجم) · S1523 (قانونِ افقِ تقویمی) · S526/S382 (هندسه و هارنس)
// ---------------------------------------------------------------------------

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'

// pip طلا = ۰.۱$ (۱ pip = ۱۰ point) — همان قراردادِ revived_strategies.ts و
// حسابِ مرجعِ پروژه (spread $0.33 = ۳.۳ pip). ⚠️ S1516 اشتباهاً ۰.۰۱ گرفته
// بود (باگِ ۱۰× در استاپِ زنده)؛ اینجا عمداً ۰.۱ است.
const GOLD_PIP = 0.1

export interface S1581Config {
  id: string
  tfFa: string
  lookback: number      // ۹۰ — منجمد S1511/S950/S523/S526
  rvolThr: number       // ۱.۰ — «above-median volume»، قفل در پیش‌ثبت
  slotWin: number       // ۳۰ رخدادِ قبلیِ همان ساعتِ روز
  slotMinP: number      // min_periods=20
  atrP: number          // ۱۰۰ (فقط شفافیت — هندسه منجمد است)
  slK: number
  rr: number
  slPip: number         // منجمد از میانهٔ ATR100 کلِ سری (۱۵.۶ سال)
  tpPip: number
  maxHold: number       // سقفِ ایمنیِ اجرایی — از توزیعِ واقعیِ نگه‌داری
  approachFrac: number
  rqs2: number
  nTrades: number
  wr: number
  lift: number
  z: number
}

export const S1581_CFG: Record<string, S1581Config> = {
  'XAUUSD-H6': {
    id: 'XAUUSD-H6', tfFa: 'H6',
    lookback: 90, rvolThr: 1.0, slotWin: 30, slotMinP: 20, atrP: 100,
    slK: 1.5, rr: 1.5,
    // عددِ منجمد از results/_s1581/XAUUSD_H6_gated.json (دادهٔ H6 هرگز عوض نشد).
    slPip: 152.10, tpPip: 228.14,
    // دامِ ⑧ — از توزیعِ واقعی (results/_s1581/XAUUSD_H6_gated.json + هارنس):
    //   کمینه ۱ · میانه ۴ · p95 ۲۹ · **بیشینه ۸۴** کندلِ H6 ⇒ سقفِ ۱۰۰ کافی است.
    maxHold: 100, approachFrac: 0.995,
    rqs2: 88.0, nTrades: 219, wr: 52.97, lift: 12.10, z: 3.33,
  },
}

export interface S1581Features {
  priorMinLow: number[]   // max(low[i−L .. i−1]) — سدِ کف، علّی (shift 1)
  ff: boolean[]           // حالت: low[i] > priorMinLow[i]
  fresh: boolean[]        // لبهٔ تازه: ff ∧ ¬ff[i−1]   (دامِ ②)
  drift: boolean[]        // گیتِ علّی: close[i−1] − close[i−L] > 0  (دامِ ③)
  rvol: number[]          // حجم ÷ میانهٔ هم‌اسلات (NaN = تعریف‌نشده) (دامِ ④)
  slotRef: number[]       // خودِ میانهٔ هم‌اسلات (جدولِ شفافیت)
  base: boolean[]         // fresh ∧ drift
  sig: boolean[]          // base ∧ rvol≥thr ∧ isFinite(rvol)
}

/**
 * پورتِ عینِ `strategies/s1581_fresh_floor_volume.py` (که خودش هارنسِ S1511 را
 * عیناً استفاده می‌کند) — همه علّی، هیچ look-ahead.
 *
 *   ff_state:   low > low.rolling(L).max().shift(1)
 *   sig_fresh:  ff & ~ff.shift(1, fill_value=False) & drift_mask
 *   drift_mask: (close.shift(1) − close.shift(L)) > 0
 *   rvol_slot:  volume / median(volume of prev 30 same-hour bars)   (S589)
 *   gated:      sig_fresh & rvol.notna() & (rvol >= 1.0)
 */
export function s1581Features(candles: Candle[], cfg: S1581Config): S1581Features {
  const n = candles.length
  const L = cfg.lookback

  // ── سدِ کف: rolling(L).max().shift(1) روی low ─────────────────────────────
  const priorMinLow = new Array<number>(n).fill(NaN)
  for (let i = L; i < n; i++) {
    let m = -Infinity
    for (let j = i - L; j <= i - 1; j++) if (candles[j].low > m) m = candles[j].low
    priorMinLow[i] = m
  }

  const ff = new Array<boolean>(n).fill(false)
  for (let i = 0; i < n; i++) {
    // NaN ⇒ false (عینِ .fillna(False) در `_b()` رانر)
    ff[i] = isFinite(priorMinLow[i]) && candles[i].low > priorMinLow[i]
  }

  // گیتِ درفتِ علّی — دامِ ③: از close[i−1] و close[i−L]، هرگز close[i].
  const drift = new Array<boolean>(n).fill(false)
  for (let i = L; i < n; i++) {
    drift[i] = candles[i - 1].close - candles[i - L].close > 0
  }

  // ── مرجعِ حجمِ هم‌اسلات (دامِ ④) — همان منطقِ S589 ─────────────────────────
  // برای هر کندل، فهرستِ کندل‌های **قبلیِ** همان ساعتِ UTC نگه داشته می‌شود؛
  // میانهٔ حداکثر ۳۰ موردِ آخر با کفِ ۲۰ ⇒ وگرنه NaN (تعریف‌نشده).
  const slotRef = new Array<number>(n).fill(NaN)
  const rvol = new Array<number>(n).fill(NaN)
  const perHour = new Map<number, number[]>()
  for (let i = 0; i < n; i++) {
    const hour = new Date(candles[i].time * 1000).getUTCHours()
    const hist = perHour.get(hour) ?? []
    if (hist.length >= cfg.slotMinP) {
      const win = hist.slice(Math.max(0, hist.length - cfg.slotWin))
      const s = [...win].sort((x, y) => x - y)
      const mid = s.length >> 1
      const med = s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
      slotRef[i] = med
      rvol[i] = med > 0 ? (candles[i].volume ?? 0) / med : NaN
    }
    // خودِ کندلِ جاری **بعد** از محاسبه اضافه می‌شود ⇒ همان shift(1)
    hist.push(candles[i].volume ?? 0)
    perHour.set(hour, hist)
  }

  const fresh = new Array<boolean>(n).fill(false)
  const base = new Array<boolean>(n).fill(false)
  const sig = new Array<boolean>(n).fill(false)
  for (let i = 0; i < n; i++) {
    fresh[i] = ff[i] && !(i > 0 ? ff[i - 1] : false)
    base[i] = fresh[i] && drift[i]
    // isFinite ⇒ معادلِ `rv.notna()`: پیش از گرم‌شدنِ اسلات، سیگنال نداریم (دامِ ⑤)
    sig[i] = base[i] && isFinite(rvol[i]) && rvol[i] >= cfg.rvolThr
  }

  return { priorMinLow, ff, fresh, drift, rvol, slotRef, base, sig }
}

export function computeS1581(candles: Candle[], cfg: S1581Config): RawSignal {
  const n = candles.length
  const L = cfg.lookback
  // کفِ داده: سدِ کف به L کندل و گیتِ درفت هم به L کندل نیاز دارد؛ یک کندل
  // اضافه برای تشخیصِ لبهٔ تازه. **قیدِ سخت‌ترِ این لایه گیتِ حجم است:** برای
  // گرم‌شدنِ یک اسلات، ۲۰ رخدادِ قبلیِ همان ساعت لازم است ⇒ روی H6 (۴ اسلات در
  // روز) ۲۰×۴=۸۰ کندل. گاردِ صریحِ حجمِ صفر پایین‌تر هم گذاشته می‌شود.
  const minBars = L + 2

  const slDist = cfg.slPip * GOLD_PIP
  const tpDist = cfg.tpPip * GOLD_PIP

  const baseInd: RouterDecision['indicators'] = []

  if (n < minBars) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason:
        `دادهٔ ناکافی: این لایه دستِ‌کم ${minBars} کندلِ ${cfg.tfFa} می‌خواهد ` +
        `(سدِ کفِ ${L}-کندلی + گیتِ درفتِ ${L}-کندلی + یک کندل برای تشخیصِ لبهٔ تازه)، ` +
        `ولی فیدِ فعلی ${n} کندل دارد ⇒ هیچ حکمی صادر نمی‌شود.`,
      indicators: baseInd,
    }
  }

  const f = s1581Features(candles, cfg)
  const i = n - 1
  const last = candles[i]
  const barrier = f.priorMinLow[i]
  const gapPct = isFinite(barrier) ? ((last.low - barrier) / barrier) * 100 : NaN
  const rv = f.rvol[i]
  const ref = f.slotRef[i]
  const vol = last.volume ?? 0
  const hourNow = new Date(last.time * 1000).getUTCHours()

  const volDefined = isFinite(rv)
  const isConfirmed = volDefined && rv >= cfg.rvolThr
  const volMissing = !volDefined
  const active = f.sig[i]

  const ind: RouterDecision['indicators'] = [
    { name: `سدِ کف (بالاترین کفِ ${L} کندلِ اخیر — علّی)`,
      value: isFinite(barrier) ? barrier.toFixed(2) : '—',
      status: isFinite(barrier) ? 'ok' : 'bad' },
    { name: 'کفِ کندلِ جاری',
      value: last.low.toFixed(2),
      status: f.ff[i] ? 'ok' : 'bad' },
    { name: 'لبهٔ **تازه** (کندلِ قبل کف‌رکورد نبوده — رویداد، نه حالت)',
      value: f.fresh[i] ? 'بله — همین کندل نخستین کفِ تازه است' : 'خیر',
      status: f.fresh[i] ? 'ok' : 'bad' },
    { name: `گیتِ درفتِ علّی (close[−1] > close[−${L}])`,
      value: f.drift[i] ? 'مثبت' : 'منفی',
      status: f.drift[i] ? 'ok' : 'bad' },
    { name: `تأییدِ حجم: RVOL هم‌اسلات = حجم ÷ میانهٔ ${cfg.slotWin} کندلِ قبلیِ ساعتِ ${String(hourNow).padStart(2, '0')}:00 UTC — کفِ ${cfg.rvolThr}`,
      value: volMissing
        ? 'تعریف‌نشده (حجمِ فید ناکافی یا اسلات گرم نشده) ⇒ لایه سکوت می‌کند'
        : `${rv.toFixed(3)}  (حجم ${Math.round(vol).toLocaleString('en-US')} ÷ میانه ${Math.round(ref).toLocaleString('en-US')})`,
      status: volMissing ? 'neutral' : (isConfirmed ? 'ok' : 'bad') },
    { name: 'حد ضرر / هدف (منجمد از میانهٔ ۱۵.۶ سال — مخصوصِ همین تایم‌فریم)',
      value: `${cfg.slPip} / ${cfg.tpPip} pip (نسبت ${cfg.rr} ⇒ TP>SL)`,
      status: 'ok' },
  ]

  // ── ENTRY ────────────────────────────────────────────────────────────────
  if (active) {
    return {
      active: true, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason:
        `کفِ تازهٔ ${L}-کندلی با **تأییدِ حجم** روی ${cfg.tfFa}: کفِ این کندل ` +
        `(${last.low.toFixed(2)}) بالاتر از **همهٔ** کف‌های ${L} کندلِ گذشته ` +
        `(سد ${barrier.toFixed(2)}) است، کندلِ قبل چنین نبود (لبهٔ تازه)، گیتِ ` +
        `درفتِ علّی مثبت، و حجمِ هم‌اسلات ${rv.toFixed(2)} ≥ ${cfg.rvolThr} ⇒ ` +
        `**غیابِ عرضه + جریانِ مطلع**.`,
      indicators: ind,
    }
  }

  // ── APPROACHING ──────────────────────────────────────────────────────────
  // نزدیکِ سدِ کف، گیتِ درفت مثبت، و حجم در دسترس — ولی هنوز کفِ تازه نیست.
  const nearBarrier = isFinite(barrier)
    && last.low >= barrier * cfg.approachFrac
    && !f.ff[i]
  if (nearBarrier && f.drift[i] && !volMissing) {
    return {
      active: false, approaching: true, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason:
        `نزدیکِ کفِ تازه روی ${cfg.tfFa}: کفِ کندل (${last.low.toFixed(2)}) تا سدِ ` +
        `${L}-کندلی (${barrier.toFixed(2)}) فقط ${Math.abs(gapPct).toFixed(2)}٪ فاصله ` +
        `دارد و گیتِ درفت مثبت است — ولی هنوز **بالای** سد نیست.`,
      approachReason:
        `تأییدِ لازم: کفِ کندل باید از ${barrier.toFixed(2)} بالاتر برود ` +
        `(کلِ کندل در هوای پاک) **و** RVOL هم‌اسلات ≥ ${cfg.rvolThr} شود.`,
      indicators: ind,
    }
  }

  // ── NEUTRAL ──────────────────────────────────────────────────────────────
  let why: string
  if (volMissing) {
    why = `حجمِ هم‌اسلات تعریف‌نشده است ⇒ گیتِ حاملِ اطلاعاتِ این لایه قابلِ ` +
      `ارزیابی نیست و لایه صادقانه سکوت می‌کند (کفِ تازهٔ بی‌تأییدِ حجم روی H4 ` +
      `لبهٔ سنجیده‌شده‌اش فقط +1.44pp در برابرِ +8.47pp با حجم است).`
  } else if (f.base[i] && !isConfirmed) {
    why = `کفِ تازه + درفت مثبت ثبت شد ولی **حجم تأیید نکرد** ` +
      `(RVOL ${rv.toFixed(2)} < ${cfg.rvolThr}) ⇒ شکستِ کم‌حجم.`
  } else if (f.ff[i] && !f.fresh[i]) {
    why = `کفِ کندل بالای سد هست، ولی کندلِ قبل هم چنین بود ⇒ **لبهٔ تازه نیست** ` +
      `(این لایه رویداد می‌خرد نه حالت).`
  } else if (f.fresh[i] && !f.drift[i]) {
    why = `لبهٔ کفِ تازه هست، ولی **گیتِ درفتِ علّی منفی** است ` +
      `(close[−1] پایین‌تر از close[−${L}]) ⇒ خارج از فضایی که حکم در آن صادر شد.`
  } else if (isFinite(barrier)) {
    why = `کفِ کندل (${last.low.toFixed(2)}) زیرِ سدِ ${L}-کندلی (${barrier.toFixed(2)}) ` +
      `است ⇒ هنوز در محدودهٔ کف‌های اخیریم.`
  } else {
    why = 'سدِ کف هنوز تعریف نشده (گرم‌شدنِ پنجره).'
  }

  return {
    active: false, approaching: false, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason: `بدونِ سیگنال روی ${cfg.tfFa}. ${why}`,
    indicators: ind,
  }
}

export function decideS1581(
  cfg: S1581Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS1581(candles, cfg)
  const price = a.price

  // این لایه LONG-only است ⇒ رژیمِ سبک همیشه صعودی.
  const reg: RegimeInfo = {
    regime: 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: 'bull',
    bucket: `s1581_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S1581',
    name: `کفِ تازهٔ ${cfg.lookback}-کندلی × تأییدِ حجم (${cfg.tfFa})`,
    kind: 'volume_fresh_floor' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ **منجمد** (نه شناور): SL=${cfg.slPip} / TP=${cfg.tpPip} pip — از ` +
      `median(ATR(${cfg.atrP}))×${cfg.slK} روی کلِ ۱۵.۶ سالِ ${cfg.tfFa} گرفته شده و در سایت ` +
      `بازتولید نمی‌شود (پنجرهٔ سایت کوتاه است) ⇒ عدد از artifactِ حکم می‌آید. ` +
      `تا برخورد به TP یا SL نگه‌دار. ` +
      `⚠️ بک‌تست **هیچ time-stop نداشت**؛ سقفِ ${cfg.maxHold} کندلیِ سایت فقط یک ایمنیِ ` +
      `اجرایی است و از بیشینهٔ نگه‌داریِ معاملاتِ داوری‌شده (۸۴ کندل) بزرگ‌تر انتخاب شده. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false): تا این معامله بسته نشده، کفِ تازهٔ بعدی ` +
      `نباید معاملهٔ جدید باز کند. ` +
      `⚠️ **ورود روی close کندلِ سیگنال** است، نه openِ کندلِ بعد (هارنس entry=close[e]). ` +
      `⚠️ **قیدِ شاهدِ کاذب — S1581 در برابرِ S1516 روی همین کارت:** ممیزیِ ` +
      `اندازه‌گیری‌شده (tools/s1581_false_witness_audit.py · control بازتولیدِ ۳۲۶ ` +
      `سیگنال) jaccard **۰.۶۳۵** و size_ratio **۰.۷۸۹** داد ⇒ بالای هر دو آستانهٔ ` +
      `۰.۶۰/۰.۷۵ ⇒ **یک رویدادِ کفِ تازه با دو اسم** (۸۸٪ زیرمجموعه). این زوج در ` +
      `FALSE_WITNESS_PAIRS ثبت شده تا سایت هرگز دو شاهدِ مستقل نشان ندهد. ` +
      `S1581 ارزشِ افزوده دارد چون ستونِ volume را می‌خواند (S1516 فقط OHLC) و ۱۲٪ ` +
      `رویدادِ غیرمشترک دارد. ` +
      `⚠️ **در برابرِ والدِ وصل‌نشدهٔ S1511 (L=90):** ۱۰۰٪ زیرمجموعهٔ ساختاریِ S1511 ` +
      `است (همان رویداد + گیت). S1511 وصل **نیست** ⇒ تعارضی نیست؛ اگر روزی وصل شود ` +
      `باید یکی از {S1511, S1516, S1581} حذف گردد. ` +
      `⚠️ هیچ مدیریتِ فعالی (BE/trailing) آزموده و تأیید نشده ⇒ فقط TP/SL.`,
    filters: [
      `کفِ تازهٔ ${cfg.lookback}-کندلی: low[i] > max(low[i−${cfg.lookback}..i−1]) — **کلِ کندل** ` +
        `در هوای پاک بالای همهٔ کف‌های اخیر (روی low است نه close؛ ارثی از S1511)`,
      `لبهٔ تازه: کندلِ قبل نباید خودش کف‌رکورد بوده باشد (رویداد، نه حالت)`,
      `گیتِ درفتِ علّی: close[i−1] − close[i−${cfg.lookback}] > 0 — از i−1 نه i ` +
        `(هم ضدِ look-ahead، هم تعریف‌کنندهٔ فضای نولِ مشروط؛ ارثی از S523)`,
      `گیتِ تأییدِ حجم: RVOL هم‌اسلات = حجم ÷ میانهٔ ${cfg.slotWin} کندلِ قبلیِ **همان ساعتِ روز** ≥ ${cfg.rvolThr} ` +
        `(کفِ ${cfg.slotMinP} رخداد) — هم‌اسلات است تا «گیتِ حجم» باشد نه «گیتِ ساعت» (ارثی از S589)`,
      'جهت = LONG-only (قانونِ S522/S528) — هیچ بازوی SHORTی آزموده نشد',
      `هندسهٔ نامتقارنِ TP>SL (${cfg.slK}×median(ATR${cfg.atrP}) و ${cfg.rr}×) ⇒ صفر تورشِ WR-سازی · قیدِ تک‌معامله`,
      `صفر پارامترِ آزاد: رویداد از S1511، گیتِ حجم از S589، هندسه از هارنسِ S382 ⇒ n_trials=3 صادقانه شمرده شد`,
      `حجم = **حاملِ اطلاعات**، نه فیلترِ کیفیت (قانونِ S1580): روی رویدادِ سطحیِ H4، ` +
        `کفِ تازهٔ بدونِ حجم +1.44pp و با حجم +8.47pp — همان آزمونِ بیرونیِ موفقِ قانون`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
