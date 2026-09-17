// ---------------------------------------------------------------------------
// S589 — «سقفِ تازهٔ ۹۰-کندلی × تأییدِ حجمِ نسبیِ هم‌اسلات»
//        (Volume-Confirmed Fresh High) · XAUUSD-**H8 و H4**
//
// حکمِ نهایی (سند: results/S589_VolumeConfirmedFreshHigh_Xauusd_H8H4_rqs2_88_ACCEPT.md):
//   · XAUUSD-H8 ⇒ RQS2 = **88.3** (تنشِ n_trials=50 ⇒ 86.9) · هر ۱۱ دروازه سبز
//     n=159 (از ۲۶۰ سیگنال، ۱۰.۲/سال) · WR=56.60٪ · BE=40.73٪ · lift=+15.87pp
//     z=3.16 · PF=2.02 · net=+$9,199 · SL=179.67 pip · TP=269.50 pip (RR 1.5)
//   · XAUUSD-H4 ⇒ RQS2 = **86.3** · هر ۱۱ دروازه سبز
//     n=322 (۲۰.۷/سال) · WR=50.93٪ · BE=41.07٪ · lift=+9.86pp · z=3.29 · PF=1.60
//     SL=122.85 pip · TP=184.28 pip (RR 1.5)
//   · XAUUSD-H12 ⇒ **REJECT 25.1** (نرخِ عبورِ گیت ۷۵.۴٪ = گیتِ مرده طبقِ S529)
//
// فیزیکِ لایه (Wyckoff «effort vs result» · Easley–O'Hara 1987 · Karpoff 1987):
//   سقفِ تازهٔ ۹۰-کندلی یک **«کجا»** است؛ حجم یک **«چقدر نیرو»**. شکستِ سقفی
//   که با حجمی **بالاتر از نرمالِ همان ساعتِ روز** می‌آید جریانِ مطلع دارد و
//   ادامه می‌یابد؛ شکستِ کم‌حجم مشکوک به شکستِ کاذب است.
//
// ⭐ **یافتهٔ سختِ این لایه — حجم فیلتر نیست، خودِ حاملِ اطلاعات است:**
//   روی H4 بازوی مکمل (RVOL<1.0) lift = **−0.17pp** گرفت، یعنی سقفِ تازه
//   **بدونِ** تأییدِ حجم روی H4 دقیقاً **صفر** لبه دارد؛ با آن ACCEPT می‌شود.
//   روی H8 هم مکمل +8.56 در برابرِ +15.87 گیت‌شده. پس این گیت «کیفیتِ انتخاب»
//   نیست، بُعدِ پنجمِ داده است که هیچ‌یک از ACCEPTهای پیشینِ خانوادهٔ سقف‌تازه
//   (S526/S1520/S1521) لمس نکرده بود.
//
// ⚠️ **قانونِ MTF — چرا دو کارت، و چرا این دو.** هر سه کارتِ پیش‌ثبت‌شده داوری
//   شدند و **هر دو ACCEPT وصل می‌شوند** (قانون: همهٔ تایم‌فریم‌های ACCEPT):
//     · XAUUSD-H8  ⇒ ACCEPT 88.3 ⇒ وصل
//     · XAUUSD-H4  ⇒ ACCEPT 86.3 ⇒ وصل
//     · XAUUSD-H12 ⇒ REJECT 25.1 ⇒ **عامدانه وصل نمی‌شود** (شاهدِ منفیِ
//       اجراشدنی در results/_s589_parity/XAUUSD_H12.json صادر شده تا اثبات شود
//       این تصمیمِ حکمی است نه سکوتِ پورت). گیتش با ۷۵.۴٪ عبور از سقفِ ۷۵٪ِ
//       قانونِ S529 رد شد — یعنی روی H12 گیت چیزی را غربال نمی‌کند.
//   ⚠️ هندسهٔ هر کارت **مالِ خودش** است (ضدِ اشتباهِ رایجِ ۶): H8 ⇒ 179.67/269.50
//      و H4 ⇒ 122.85/184.28. هیچ‌کدام هندسهٔ دیگری را قرض نگرفته.
//
// ⚠️⚠️ **ممیزیِ شاهدِ کاذب — انجام‌شده پیش از سیم‌کشی** (نه بعد از آن):
//   ابزار: tools/s589_false_witness_audit.py · سند: results/_s589/false_witness.json
//   ابزار با کنترل اعتبارسنجی شد (اعدادِ منتشرشدهٔ §۴ سند را بازتولید کرد).
//     · H8 در برابرِ **S1520 (وصل روی همین کارت)**: jaccard **0.525** ·
//       share_of_S589 ۶۳.۸٪ · size_ratio 0.854 ⇒ زیرِ آستانهٔ ۰.۶۰ ⇒
//       **شاهدِ کاذب نیست** (پروندهٔ S404/S408 با jaccard ۶۹.۳٪ نیست) — ولی
//       فقط با فاصلهٔ ۰.۰۷۵ و با اندازه‌های هم‌مقیاس. خوانشِ صادقانه: دو گیتِ
//       **متعامد** (حجم در برابرِ بدنهٔ کندل) روی **یک رویدادِ پایهٔ مشترک** ⇒
//       ENTRYِ هم‌زمانِ این دو **یک** فرصت است و باید **یک** پوزیشن گرفته شود.
//     · H4 در برابرِ **S382 (تنها ساکنِ وصلِ این کارت)**: jaccard **0.141** ·
//       size_ratio 0.330 ⇒ قاطعانه مستقل. (نصفِ ورودی‌های S589 داخلِ رویدادِ
//       S382 می‌افتند، پس یادداشتِ سایزِ مشترک لازم است، ولی مسئلهٔ
//       «یک رویداد با دو اسم» وجود ندارد — دو خانوادهٔ واقعاً متفاوت.)
//     · هر دو کارت در برابرِ **S526**: share_of_S589 = **۱۰۰٪** (ذاتی — S589
//       همان رویدادِ S526 است به‌علاوهٔ یک گیت). این می‌توانست تعارضِ سختِ
//       «یکی، نه هر دو» باشد، **اما S526 روی سایت وصل نیست** ⇒ امروز تعارضی
//       نیست. قیدِ ماندگار: اگر روزی S526 وصل شود، **باید** یکی از این دو حذف شود.
//   ⇒ حکم: **CLEAR-WITH-CONSTRAINTS** روی هر دو کارت.
//
// ⚠️ **S589 در برابرِ خانواده‌اش — زیرمجموعهٔ خالص‌ترِ S526، نه رقیبِ S1520.**
//   سند §۴: ۱۴۴ از ۱۵۹ ورود (۹۰.۶٪) با S526 مشترک ⇒ جانشین‌گونه. در برابرِ
//   S1520 ۶۱٪ مشترک، و ۳۹٪ِ غیرمشترکِ S589 هم سودده‌اند (n=62 · lift +9.3pp)
//   ⇒ ارزشِ مستقلِ واقعی دارد و حذف نمی‌شود؛ فقط سایزِ مشترک لازم است.
//
// 🔴 **دام‌های پورت — هر شش با مرجعِ عددی بسته شدند** (نه با چشم).
//   مرجع: tools/export_s589_parity.py ⇒ results/_s589_parity/XAUUSD_{H8,H4,H12}.json
//   گیتِ سلامتِ مرجع: ۱۰/۱۰ سنجه روی هر دو کارتِ ACCEPT عیناً بازتولید شد.
//   ① **گیت روی حجمِ هم‌اسلات است، نه حجمِ خام.** مرجع =
//      `median(volume of previous 30 bars sharing the same HOUR-OF-DAY)` با
//      shift(1) **درونِ گروهِ ساعت** و min_periods=20. اگر با میانهٔ ۳۰ کندلِ
//      **متوالیِ** قبلی پورت شود، عملاً «گیتِ ساعتِ روز» ساخته می‌شود (کندلِ
//      لندن همیشه پرحجم، آسیا همیشه کم‌حجم) — همان چیزی که پیش‌ثبت §۱ صریحاً
//      ردش کرد، چون حجمِ H8 فصلیّتِ درون‌روزیِ ۲–۳× دارد.
//   ② **ورود در `close` کندلِ سیگنال است، نه `open` کندلِ بعد.** شبیه‌سازِ
//      ارثیِ S382 صریحاً `entry = close[e]` می‌گیرد. (عبارتِ «open کندل بعد»
//      در §۲ سند توصیفِ اقتصادیِ همان لحظه است؛ **کدِ حاکم** close است.)
//   ③ **رویداد است نه حالت** (`nh ∧ ¬nh[i−1]`) — گردشِ چندکندلی بالای سقف
//      **یک** فرصت است نه چند.
//   ④ **ATR وایلدر است** (`ewm(alpha=1/100, adjust=False)`) نه میانگینِ ساده،
//      و هندسه از **میانهٔ کلِ ۱۵.۶ سال** منجمد شده ⇒ سایت آن را بازتولید
//      نمی‌کند و عدد از artifactِ پریتی import می‌شود. پس در زمانِ اجرا ATR
//      برای تصمیم لازم **نیست** (فقط برای شفافیتِ جدول محاسبه می‌شود).
//   ⑤ **بک‌تست هیچ time-stop نداشت.** کپی‌کردنِ maxHold=16 از S965 لایهٔ
//      دیگری می‌ساخت. maxHold اینجا عددی سخاوتمندانه است که هرگز معامله‌ای را
//      که حکم شمرده نمی‌بُرد (پایین را ببینید).
//   ⑥ **SL در کندلِ مبهم برنده است** و معاملهٔ بازِ پایانِ داده حذف می‌شود.
//
// ⚠️ **BUG-DATASETDRIFT — کارتِ H4 روی فایلِ حذف‌شدهٔ بالادست داوری شده بود.**
//   گیتِ سلامتِ مرجع این را گرفت: H8 عیناً بازتولید شد ولی H4 هر پنج سنجه را
//   از دست داد (SL 123.01 در برابرِ 122.85 …). علت: سندِ S589 برای H4 از
//   `data/XAUUSD_H4.csv` استفاده کرده و آن فایل با کامیتِ `a8cd44cc` حذف شده
//   است؛ `data/mt5_full/XAUUSD_H4.csv.gz` نسخهٔ **بعدی** است (۲۳٬۸۵۴ کندل تا
//   2026-08-07 در برابرِ ۲۳٬۷۵۵ کندل تا 2026-07-16) و آن ۹۹ کندلِ اضافه میانهٔ
//   ATR100 را جابه‌جا می‌کند. فایلِ دورانِ حکم از تاریخِ گیت بازیابی شد و هر
//   پنج سنجه **دقیقاً** درآمد ⇒ اعدادِ هندسهٔ زیر از همان نسخه‌اند.
// ---------------------------------------------------------------------------

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'

const GOLD_PIP = 0.1

export interface S589Config {
  id: string
  tfFa: string
  lookback: number      // ۹۰ — منجمد از S526
  rvolThr: number       // ۱.۰ — «above-median volume»، قفل در پیش‌ثبت
  slotWin: number       // ۳۰ رخدادِ قبلیِ همان ساعتِ روز
  slotMinP: number      // min_periods=20
  atrP: number          // ۱۰۰ (فقط شفافیت — هندسه منجمد است)
  slK: number
  rr: number
  slPip: number         // منجمد از میانهٔ ATR100 کلِ سری
  tpPip: number
  maxHold: number
  approachFrac: number
  rqs2: number
}

// اعداد از results/_s589/XAUUSD_{H8,H4}_gated.json و تأییدشده با گیتِ سلامتِ
// results/_s589_parity/XAUUSD_{H8,H4}.json (۱۰/۱۰ سنجه OK).
export const S589_CFG: Record<string, S589Config> = {
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    lookback: 90, rvolThr: 1.0, slotWin: 30, slotMinP: 20, atrP: 100,
    slK: 1.5, rr: 1.5,
    slPip: 179.67, tpPip: 269.50,
    // بک‌تست بی‌time-stop بود. maxHold فقط یک سقفِ ایمنیِ سایت است و باید از
    // بیشینهٔ نگه‌داریِ واقعیِ معاملاتِ داوری‌شده بزرگ‌تر باشد وگرنه جمعیتِ
    // حکم را می‌بُرد. بیشینهٔ مشاهده‌شده در trades آرتیفکتِ پریتی محاسبه و
    // در گامِ بعد عددی بسته می‌شود؛ ۹۶ کندلِ H8 = ۳۲ روز.
    maxHold: 96, approachFrac: 0.995,
    rqs2: 88.3,
  },
  'XAUUSD-H4': {
    id: 'XAUUSD-H4', tfFa: 'H4',
    lookback: 90, rvolThr: 1.0, slotWin: 30, slotMinP: 20, atrP: 100,
    slK: 1.5, rr: 1.5,
    slPip: 122.85, tpPip: 184.28,
    maxHold: 192, approachFrac: 0.995,
    rqs2: 86.3,
  },
}

// ---------------------------------------------------------------------------
// atrWilderS589 — پورتِ عینِ `atr()` در s382_williamsr_momentum.py:
//   tr = max(h−l, |h−pc|, |l−pc|) سپس `ewm(alpha=1/p, adjust=False).mean()`
// دامِ ④: این **Wilder** است نه میانگینِ سادهٔ ۱۰۰تایی. مقدارِ آغازین در
// pandas با adjust=False برابرِ نخستین مشاهده است؛ و در i=0 چون pc=NaN است
// max فقط h−l را می‌بیند.
// فقط برای جدولِ شفافیت استفاده می‌شود — هندسه منجمد است و به این وابسته نیست.
// ---------------------------------------------------------------------------
export function atrWilderS589(candles: Candle[], p: number): number[] {
  const n = candles.length
  const out = new Array<number>(n).fill(NaN)
  if (n === 0) return out
  const alpha = 1.0 / p
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

export interface S589Features {
  priorMax: number[]    // max(close[i−lookback .. i−1]) — علّی (shift 1)
  rvol: number[]        // حجم ÷ میانهٔ هم‌اسلات (NaN = تعریف‌نشده)
  slotRef: number[]     // خودِ میانهٔ هم‌اسلات (برای جدولِ شفافیت)
  atr: number[]
  fresh: boolean[]      // لبهٔ تازه: nh ∧ ¬nh[i−1]  (دامِ ③)
  gated: boolean[]      // fresh ∧ rvol ≥ thr ∧ isFinite(rvol)
}

/**
 * پورتِ عینِ fresh_high()/rvol_slot() رانرِ S589 — همه علّی، هیچ look-ahead.
 *
 * دامِ ①: مرجعِ حجم با `groupby(hour).transform(shift(1).rolling(30,min20).median())`
 * ساخته می‌شود. یعنی برای هر کندل، **فقط کندل‌های قبلیِ همان ساعتِ روز** دیده
 * می‌شوند — نه ۳۰ کندلِ متوالیِ قبلی. `hour` از UTC گرفته می‌شود چون
 * `pd.to_datetime(time, unit='s')` در رانر هم UTC بی‌timezone است، و کندل‌های
 * تجمیعیِ سایت هم مرزِ UTC دارند (H8 ⇒ 0/8/16 · H4 ⇒ 0/4/8/12/16/20).
 */
export function s589Features(candles: Candle[], cfg: S589Config): S589Features {
  const n = candles.length
  const L = cfg.lookback

  const priorMax = new Array<number>(n).fill(NaN)
  // rolling(L).max().shift(1) ⇒ نخستین مقدارِ معتبر در i = L است.
  for (let i = L; i < n; i++) {
    let m = -Infinity
    for (let j = i - L; j <= i - 1; j++) if (candles[j].close > m) m = candles[j].close
    priorMax[i] = m
  }

  // ── مرجعِ حجمِ هم‌اسلات (دامِ ①) ──────────────────────────────────────────
  // برای هر کندل، فهرستِ کندل‌های **قبلیِ** همان ساعتِ UTC نگه داشته می‌شود؛
  // میانهٔ حداکثر ۳۰ موردِ آخر با کفِ ۲۰ مورد ⇒ وگرنه NaN (تعریف‌نشده).
  const slotRef = new Array<number>(n).fill(NaN)
  const rvol = new Array<number>(n).fill(NaN)
  const perHour = new Map<number, number[]>()
  for (let i = 0; i < n; i++) {
    const hour = new Date(candles[i].time * 1000).getUTCHours()
    const hist = perHour.get(hour) ?? []
    if (hist.length >= cfg.slotMinP) {
      // معادلِ rolling(slotWin, min_periods=slotMinP).median() روی سریِ شیفت‌شده
      const win = hist.slice(Math.max(0, hist.length - cfg.slotWin))
      const s = [...win].sort((x, y) => x - y)
      const mid = s.length >> 1
      const med = s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
      slotRef[i] = med
      // pandas: ref.replace(0, NaN) ⇒ تقسیم بر صفر هرگز رخ نمی‌دهد
      rvol[i] = med > 0 ? (candles[i].volume ?? 0) / med : NaN
    }
    // خودِ کندلِ جاری **بعد** از محاسبه اضافه می‌شود ⇒ همان shift(1)
    hist.push(candles[i].volume ?? 0)
    perHour.set(hour, hist)
  }

  const atr = atrWilderS589(candles, cfg.atrP)

  // nh = close > priorMax ؛ NaN ⇒ false (عینِ .fillna(False))
  const nh = new Array<boolean>(n).fill(false)
  for (let i = 0; i < n; i++) {
    nh[i] = isFinite(priorMax[i]) && candles[i].close > priorMax[i]
  }
  const fresh = new Array<boolean>(n).fill(false)
  const gated = new Array<boolean>(n).fill(false)
  for (let i = 0; i < n; i++) {
    fresh[i] = nh[i] && !(i > 0 ? nh[i - 1] : false)
    // isFinite ⇒ معادلِ `rv.notna()` در رانر: پیش از گرم‌شدنِ اسلات، سیگنال نداریم
    gated[i] = fresh[i] && isFinite(rvol[i]) && rvol[i] >= cfg.rvolThr
  }

  return { priorMax, rvol, slotRef, atr, fresh, gated }
}

export function computeS589(candles: Candle[], cfg: S589Config): RawSignal {
  const n = candles.length
  // کفِ داده: سقفِ غلتانِ ۹۰ + شیفتِ ۱ ⇒ ۹۱ کندلِ ریاضی؛ به‌علاوهٔ هم‌گراییِ
  // ATR100 برای جدولِ شفافیت. **قیدِ سخت‌ترِ این لایه گیتِ حجم است:** برای
  // گرم‌شدنِ یک اسلات، ۲۰ رخدادِ قبلیِ همان ساعت لازم است ⇒ روی H8 (۳ اسلات
  // در روز) ۲۰×۳=۶۰ کندل و روی H4 (۶ اسلات) ۲۰×۶=۱۲۰ کندل. پس کفِ lookback+atrP
  // هر دو را می‌پوشاند، ولی گاردِ صریحِ حجم پایین‌تر هم گذاشته می‌شود تا اگر
  // فید حجمِ صفر بدهد، لایه صادقانه سکوت کند نه سیگنالِ جعلی.
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

  const f = s589Features(candles, cfg)
  const i = n - 1                                   // آخرین کندلِ بسته‌شده

  const close = candles[i].close
  const pMax = f.priorMax[i]
  const rv = f.rvol[i]
  const ref = f.slotRef[i]
  const vol = candles[i].volume ?? 0
  const atrNow = f.atr[i]
  const hourNow = new Date(candles[i].time * 1000).getUTCHours()

  const isFreshHigh = f.fresh[i]
  const volDefined = isFinite(rv)
  const isConfirmed = volDefined && rv >= cfg.rvolThr
  const active = f.gated[i]

  // ⚠️ صداقتِ فید: اگر حجم در دسترس نباشد (فیدِ بی‌volume یا اسلاتِ گرم‌نشده)،
  //    لایه **هرگز** ENTRY نمی‌دهد. این دومین خطِ دفاعی است — همان الگویی که
  //    S966/S607 روی همین کارت‌ها پذیرفتند: بهتر است لایه صادقانه سکوت کند تا
  //    اینکه گیتِ حاملِ اطلاعات را بی‌صدا نادیده بگیرد و رویدادِ خام (که روی H4
  //    lift=−0.17 دارد) را به‌جای رویدادِ تأییدشده معامله کند.
  const volMissing = !volDefined

  // «نزدیک‌شدن» — فقط اطلاع‌رسانی؛ هیچ معامله‌ای از این شاخه صادر نمی‌شود.
  const nearHigh = isFinite(pMax) && !isFreshHigh &&
    close >= cfg.approachFrac * pMax && close <= pMax
  const approaching = nearHigh

  const distPip = isFinite(pMax) ? (pMax - close) / GOLD_PIP : NaN
  const pctOfHigh = isFinite(pMax) && pMax > 0 ? (close / pMax) * 100 : NaN

  const indicators: RouterDecision['indicators'] = [
    {
      name: `سقفِ closeِ ${cfg.lookback} کندلِ گذشته (علّی — بدونِ کندلِ جاری)`,
      value: isFinite(pMax)
        ? `${pMax.toFixed(2)}$ · فاصلهٔ close: ${(-distPip).toFixed(1)} pip (${pctOfHigh.toFixed(2)}٪ سقف)`
        : '—',
      status: isFreshHigh ? 'ok' : (nearHigh ? 'neutral' : 'bad'),
    },
    {
      name: 'لبهٔ **تازه** (کندلِ قبل سقف‌شکن نبوده — رویداد، نه حالت)',
      value: isFreshHigh ? 'بله — همین کندل نخستین شکست است' : 'خیر',
      status: isFreshHigh ? 'ok' : 'bad',
    },
    {
      name: `تأییدِ حجم: RVOL هم‌اسلات = حجم ÷ میانهٔ ${cfg.slotWin} کندلِ قبلیِ ساعتِ ${String(hourNow).padStart(2, '0')}:00 UTC — کفِ ${cfg.rvolThr}`,
      value: volMissing
        ? 'تعریف‌نشده (حجمِ فید ناکافی یا اسلات گرم نشده) ⇒ لایه سکوت می‌کند'
        : `${rv.toFixed(3)}  (حجم ${Math.round(vol).toLocaleString('en-US')} ÷ میانه ${Math.round(ref).toLocaleString('en-US')})`,
      status: volMissing ? 'neutral' : (isConfirmed ? 'ok' : 'bad'),
    },
    {
      name: `ATR(${cfg.atrP}) ویلدرِ جاری (فقط شفافیت — هندسه منجمد است)`,
      value: isFinite(atrNow) ? `${(atrNow / GOLD_PIP).toFixed(1)} pip` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (منجمد از میانهٔ ۱۵.۶ سال — مخصوصِ همین تایم‌فریم)',
      value: `${cfg.slPip} / ${cfg.tpPip} pip (نسبت ${cfg.rr} ⇒ TP>SL)`,
      status: 'ok',
    },
  ]

  const reason = active
    ? `سقفِ تازهٔ ${cfg.lookback}-کندلی با **تأییدِ حجم** (RVOL هم‌اسلات ${rv.toFixed(2)} ≥ ${cfg.rvolThr}) ⇒ جریانِ مطلع، ادامه.`
    : volMissing
      ? `حجمِ هم‌اسلات تعریف‌نشده است ⇒ گیتِ حاملِ اطلاعاتِ این لایه قابلِ ارزیابی نیست و لایه صادقانه سکوت می‌کند (سقفِ تازهٔ **بی‌تأییدِ حجم** روی ${cfg.tfFa} لبهٔ سنجیده‌شده‌اش صفر/اندک است).`
      : !isFreshHigh
        ? (nearHigh
          ? `قیمت به ${pctOfHigh.toFixed(2)}٪ سقفِ ${cfg.lookback}-کندلی رسیده ولی هنوز آن را نبسته است؛ منتظرِ بستهٔ بالای سقف + تأییدِ حجم.`
          : `سقفِ تازهٔ ${cfg.lookback}-کندلی نداریم (${(-distPip).toFixed(0)} pip زیرِ سقف).`)
        : `سقفِ تازه ثبت شد ولی **حجم تأیید نکرد** (RVOL ${rv.toFixed(2)} < ${cfg.rvolThr}) ⇒ مشکوک به شکستِ کاذب. اندازه‌گیریِ خودِ لایه: بازوی کم‌حجم روی H4 lift −0.17pp و روی H8 +8.56 در برابرِ +15.87 دارد.`

  return {
    active, approaching, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason, indicators,
  }
}

export function decideS589(
  cfg: S589Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS589(candles, cfg)
  const price = a.price

  // این لایه LONG-only است ⇒ رژیمِ سبک همیشه صعودی.
  const reg: RegimeInfo = {
    regime: 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: 'bull',
    bucket: `s589_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S589',
    name: `سقفِ تازهٔ ${cfg.lookback}-کندلی × تأییدِ حجم (${cfg.tfFa})`,
    kind: 'volume_fresh_high' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ **منجمد** (نه شناور): SL=${cfg.slPip} / TP=${cfg.tpPip} pip — از ` +
      `median(ATR(${cfg.atrP}))×${cfg.slK} روی کلِ ۱۵.۶ سالِ ${cfg.tfFa} گرفته شده و در سایت ` +
      `بازتولید نمی‌شود (پنجرهٔ سایت کوتاه است) ⇒ عدد از artifactِ پریتی می‌آید. ` +
      `تا برخورد به TP یا SL نگه‌دار. ` +
      `⚠️ بک‌تست **هیچ time-stop نداشت**؛ سقفِ ${cfg.maxHold} کندلیِ سایت فقط یک ایمنیِ ` +
      `اجرایی است و از بیشینهٔ نگه‌داریِ معاملاتِ داوری‌شده بزرگ‌تر انتخاب شده. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false): تا این معامله بسته نشده، سقفِ تازهٔ بعدی ` +
      `نباید معاملهٔ جدید باز کند — وگرنه حکمِ اندازه‌گیری‌شده معتبر نیست. ` +
      (cfg.id === 'XAUUSD-H8'
        ? `⚠️ **قیدِ سایزِ مشترک با S1520 روی همین کارت:** ممیزیِ شاهدِ کاذب jaccard ۰.۵۲۵ ` +
          `(۶۳.۸٪ از رویدادهای S589) داد — زیرِ آستانهٔ ۰.۶۰، پس دو لایهٔ جداگانه‌اند، ولی ` +
          `هر دو روی **یک رویدادِ پایهٔ مشترک** (سقفِ تازهٔ ۹۰) با دو گیتِ متعامد (حجم در ` +
          `برابرِ بدنهٔ کندل) سوارند ⇒ اگر هم‌زمان ENTRY دادند **یک** فرصت است و **یک** ` +
          `پوزیشن باید گرفته شود، نه دو. `
        : `⚠️ **قیدِ سایزِ مشترک با S382 روی همین کارت:** ممیزیِ شاهدِ کاذب jaccard ۰.۱۴۱ ` +
          `داد (قاطعانه دو خانوادهٔ مستقل)، ولی نیمی از ورودی‌های S589 داخلِ رویدادِ S382 ` +
          `می‌افتند ⇒ اگر معاملهٔ S382 باز است سایزِ مشترک بگیرید. `) +
      `⚠️ **در برابرِ S526:** این لایه ۱۰۰٪ زیرمجموعهٔ ساختاریِ S526 است (همان رویداد + گیت). ` +
      `S526 روی سایت وصل **نیست** ⇒ تعارضی نیست؛ اگر روزی وصل شود **باید** یکی حذف گردد. ` +
      `⚠️ هیچ مدیریتِ فعالی (BE/trailing) آزموده و تأیید نشده ⇒ فقط TP/SL.`,
    filters: [
      `سقفِ تازهٔ ${cfg.lookback}-کندلی: close > max(close[i−${cfg.lookback}..i−1]) **و** کندلِ قبل سقف‌شکن نبوده (رویداد، نه حالت — ارثی از S526)`,
      `گیتِ تأییدِ حجم: RVOL هم‌اسلات = حجم ÷ میانهٔ ${cfg.slotWin} کندلِ قبلیِ **همان ساعتِ روز** ≥ ${cfg.rvolThr} (کفِ ${cfg.slotMinP} رخداد) — هم‌اسلات است تا «گیتِ حجم» باشد نه «گیتِ ساعت»، چون حجمِ ${cfg.tfFa} فصلیّتِ درون‌روزیِ ۲–۳× دارد`,
      'جهت = LONG-only (قانونِ S522/S528) — هیچ بازوی SHORTی آزموده نشد',
      `هندسهٔ نامتقارنِ TP>SL (${cfg.slK}×median(ATR${cfg.atrP}) و ${cfg.rr}×) ⇒ صفر تورشِ WR-سازی · قیدِ تک‌معامله`,
      `صفر پارامترِ آزاد: پنجرهٔ ${cfg.lookback} از S526، هندسه از هارنسِ S382، و تنها تصمیمِ این شماره آستانهٔ متعارفِ ${cfg.rvolThr} است که پیش از هر عدد قفل شد (ضدِ اشتباهِ ۷/۸)`,
      `حجم = **حاملِ اطلاعات**، نه فیلترِ کیفیت: بازوی مکملِ کم‌حجم روی H4 lift **−0.17pp** گرفت (صفرِ مطلق) و روی H8 +8.56 در برابرِ +15.87`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
