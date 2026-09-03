// ---------------------------------------------------------------------------
// S770 — «انبساطِ دامنه نسبت به ADR با تداوم» (ADR Range-Expansion Continuation)
//        XAUUSD · استخرِ دوعضویِ {D1, H8} · دوسویه (LONG + SHORT)
//
// حکمِ نهایی (سند: results/S770_AdrExpansionPool_Xauusd_D1H8_rqs2_82_ACCEPT.md):
//   RQS2 = **82.4** · هر ۱۱ دروازهٔ H0..H10 پاس (خطِ حکم عیناً از engine/rqs2.py v2.6)
//   n=689 (D1=266 + H8=423 پس از ادغامِ FIFO) · WR=44.70٪ · PF=1.398 · maxDD=5.83٪
//   lift=+7.23pp · z=3.91 (سد 2.897) · p_perm=4.5e−05 · K=800 · n_trials=**301** صادقانه
//   net=+$29,077 · expectancy=66.2 pip (در ۲×هزینه: 62.9) · recovery=12.17 · MCL=11/17
//   هر دو سو لبه دارند: long +9.06pp (WR 49.44٪ · n=358) · short +5.25pp (WR 39.58٪ · n=331)
//   holdout الزامی (H7): OOS n=276 · WR=45.29٪ · PF=**1.502** ⇒ نیمهٔ پنهان **بهتر** از کشف
//
// فیزیکِ لایه (Moskowitz-Ooi-Pedersen 2012 · Gao-Han-Li-Zhou 2018):
//   وقتی حرکتِ روزِ جاری از **مقیاسِ عادیِ روزانه** (ADR₂₁) فراتر می‌رود، بازار در
//   حالِ «انبساطِ دامنه» است — رخدادی که با ورودِ جریانِ سفارشِ اطلاعاتی پیوند دارد و
//   تا هدفِ ۲.۰۵۸برابری پیش از بازگشتِ میانگین تداوم می‌یابد.
//   متغیرِ حالت: frac(t) = (close(t) − dayOpen(t)) ÷ ADR₂₁(t−1) — **بی‌بعد و
//   خودمقیاس‌شونده**؛ هیچ سطحِ قیمتیِ مطلقی در قاعده نیست (تمایزِ صریح از خانوادهٔ
//   سوختهٔ breakoutِ سطح-محور: S346/S371/S373/S543).
//   رخداد = **عبورِ حالت** (state-cross) از ±θ، نه بودن در آن ⇒ اطلاعات در لبهٔ
//   تغییر است، نه در حالتِ انباشته (قانونِ S963).
//
// ⚠️ قانونِ MTF — چرا **دو** کارت وصل می‌شود و نه یکی و نه سه:
//   هر ۲۰ تایم‌فریم از M1 داوری و در §۷ سند گزارش شد. هر کارتِ **تکی** REJECT بود
//   (بهترین: D1=21.0 · H8=19.3) چون n کوچک بود؛ ولی استخرِ {D1,H8} با پروتکلِ
//   `engine/rqs2_pool.py` (FIFO تقویمی، concurrency=1) هر ۱۱ دروازه را پاس کرد.
//   ⇒ حکمِ ACCEPT **متعلق به هر دو کارت با هم** است ⇒ طبقِ قانونِ MTF هر دو باید
//     وصل شوند؛ حذفِ یکی، جمعیتی که حکم بر آن صادر شده را نابود می‌کند.
//   M1..M30 هزینه-مرده (REJECT_BY_RULE) · H1=9.8 · H2/H3 مرده · H4=13.7 · H6=10.1
//   · H12=18.6 · W1=8.8 · MN1 مرده ⇒ **صفر تعمیم** به هیچ تایم‌فریمِ دیگری.
//   ساختارِ یکنواختِ lift با مقیاس (منفیِ زیرساعتی → +2.67 در H4 → +4.23 در H8 →
//   +5.70 در D1) خودش شاهدِ مستقلِ فیزیکی‌بودنِ پدیده است، نه گلچینِ تایم‌فریم.
//
// ⚠️ پورتِ **مو-به-موی** strategies/s770_adr_expansion.py — چهار دامِ پورت:
//   ① ADR₂₁ روی **روزهای تقویمیِ UTC** حساب می‌شود، نه روی کندل‌ها:
//      groupby(day) → rng=max(high)−min(low) → rolling(21).mean().**shift(1)**
//      سپس روی هر کندلِ همان روز reindex می‌شود. برای کارتِ D1 هر روز یک کندل
//      دارد ⇒ dayOpen = openِ خودِ کندل؛ برای H8 سه کندل ⇒ dayOpen = openِ
//      نخستین کندلِ آن روزِ UTC. مرزهای تجمیعِ سایت (H1×8 روی 0/8/16 و H1×24
//      روی 00:00) دقیقاً با همین روزهای UTC هم‌ترازند.
//   ② ATR₁₀۰ = **میانگینِ سادهٔ** ۱۰۰تاییِ TR (pandas rolling.mean) و **بدونِ
//      شیفت** — چون خودِ کندلِ سیگنال بسته است، `sl_pip[si]` علّی می‌ماند.
//      atrWilder (ewm) اینجا غلط است؛ و برخلافِ S950 اینجا شیفتِ ۱ وجود ندارد.
//      TR با pc = روی‌غلتِ close و pc[0]=close[0] (عینِ np.roll در پایتون).
//   ③ آستانه دوسویه و **متقارن** است: عبورِ رو-به-بالا از +θ ⇒ LONG و عبورِ
//      رو-به-پایین از −θ ⇒ SHORT. هیچ فیلترِ رژیم/جهت‌مندی وجود ندارد.
//   ④ هندسه **برداری** است (عینِ بک‌تست): SL و TP از ATR₁۰۰ **همان کندلِ سیگنال**
//      خوانده می‌شوند، نه از یک عددِ ثابت. میانهٔ تاریخی: SL=220.3 / TP=453.4 pip.
//
// پارامترها همه **نارُند** و از کاوشِ ۶۰٪ نخست منجمد شده‌اند (ضدِ اشتباهِ رایجِ ۷):
//   θ=0.65 (=13/20) · SL_K=1.272 (=√φ) · RR=2.058 · ADR=21 · ATR=100 · hold=16.
//   هر دو عضوِ نهایی **مستقلاً** به همین θ=0.65 و hold=16 رسیدند.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1
const SEC_PER_DAY = 86400

export interface S770Config {
  id: string           // شناسهٔ کارت (XAUUSD-D1 یا XAUUSD-H8)
  tfFa: string         // برچسبِ فارسیِ تایم‌فریم برای متن‌ها
  theta: number        // آستانهٔ عبورِ حالت بر حسبِ کسری از ADR (قفل‌شده: 0.65)
  adrP: number         // پنجرهٔ ADR بر حسبِ **روزِ تقویمی** (قفل‌شده: 21)
  atrP: number         // پنجرهٔ ATR بر حسبِ کندلِ همان کارت (قفل‌شده: 100)
  slK: number          // SL = slK × ATR(atrP) (قفل‌شده: 1.272 = √φ)
  rr: number           // TP = rr × SL (قفل‌شده: 2.058 ⇒ TP>SL، قانونِ بودجه)
  maxHold: number      // بیشینهٔ نگه‌داری بر حسبِ کندلِ همان کارت (قفل‌شده: 16)
  approachFrac: number // «نزدیک‌شدن»: |frac| ≥ approachFrac×θ (فقط UI، نه ورود)
  medSlPip: number     // میانهٔ تاریخیِ SL — فقط برای پیامِ «دادهٔ ناکافی»
}

// ⚠️ هر دو کارت **از یک حکمِ استخری** می‌آیند (n=689 مشترک). پارامترها یکسان‌اند
//    چون کاوشِ مستقلِ هر کارت به همان θ=0.65 و hold=16 رسید؛ تفاوتِ عملیِ دو کارت
//    در ATR₁۰۰ **خودشان** است (D1 ≈ چند برابرِ H8) که هندسه را per-TF می‌کند
//    (ضدِ اشتباهِ رایجِ ۶: هرگز SL/TP یکسان بر حسبِ pip برای دو تایم‌فریم).
export const S770_CFG: Record<string, S770Config> = {
  'XAUUSD-D1': {
    id: 'XAUUSD-D1', tfFa: 'D1',
    theta: 0.65, adrP: 21, atrP: 100, slK: 1.272, rr: 2.058, maxHold: 16,
    approachFrac: 0.85, medSlPip: 331.0,
  },
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    theta: 0.65, adrP: 21, atrP: 100, slK: 1.272, rr: 2.058, maxHold: 16,
    approachFrac: 0.85, medSlPip: 165.0,
  },
}

// ---------------------------------------------------------------------------
// rollingMeanSimple — بازتولیدِ دقیقِ pandas Series.rolling(p).mean():
//   out[i] = میانگینِ x[i−p+1..i] برای i ≥ p−1، و NaN برای i < p−1.
// (توجه: این با smaConvolve ماژولِ S950 **متفاوت** است — آنجا جمعِ جزئی ÷ p
//  در warm-up مقدارِ عددی می‌داد؛ اینجا پایتون NaN می‌دهد و باید NaN بماند.)
// ---------------------------------------------------------------------------
function rollingMeanSimple(x: number[], p: number): number[] {
  const n = x.length
  const out = new Array<number>(n).fill(NaN)
  let acc = 0
  for (let i = 0; i < n; i++) {
    acc += x[i]
    if (i >= p) acc -= x[i - p]
    if (i >= p - 1) out[i] = acc / p
  }
  return out
}

export interface S770Features {
  frac: number[]     // (close − dayOpen) ÷ ADR21(t−1) — NaN تا گرم‌شدنِ ADR
  adr: number[]      // ADR₂₁ روزِ متناظرِ هر کندل (علّی: تا روزِ قبل)
  dayOpen: number[]  // openِ نخستین کندلِ روزِ UTC متناظر
  atrPx: number[]    // ATR(atrP) بر حسبِ قیمت (دلار) — همان کندل، بدونِ شیفت
  slPip: number[]    // slK × ATR ÷ pip
  tpPip: number[]    // rr × slPip
}

// پورتِ عینِ build_features() + geometry() از s770_adr_expansion.py
export function s770Features(candles: Candle[], cfg: S770Config): S770Features {
  const n = candles.length
  const frac = new Array<number>(n).fill(NaN)
  const adrOut = new Array<number>(n).fill(NaN)
  const dayOpenOut = new Array<number>(n).fill(NaN)

  // --- دامِ ①: تجمیعِ روزِ تقویمیِ UTC (معادلِ groupby(t.dt.normalize())) ---
  // فرضِ ورودی: کندل‌ها بر حسبِ زمان صعودی مرتب‌اند (سایت همیشه همین را می‌دهد).
  const dayKey = new Array<number>(n).fill(0)
  const dayIndexOf = new Array<number>(n).fill(-1)   // ایندکسِ روز در آرایه‌های روزانه
  const dRng: number[] = []      // high−low روزانه
  const dOpen: number[] = []     // openِ نخستین کندلِ روز
  for (let i = 0; i < n; i++) {
    const k = Math.floor(candles[i].time / SEC_PER_DAY)
    dayKey[i] = k
    if (i === 0 || k !== dayKey[i - 1]) {
      dRng.push(candles[i].high - candles[i].low)
      dOpen.push(candles[i].open)
      // نگه‌داشتِ high/low بیشینه/کمینهٔ روز در همان خانه
      dayIndexOf[i] = dRng.length - 1
    } else {
      const j = dRng.length - 1
      dayIndexOf[i] = j
      // بازسازیِ max(high) و min(low) روز — نیاز به نگه‌داشتِ hi/lo جداگانه
      // (rng را در پایانِ حلقه یک‌بار می‌سازیم؛ اینجا فقط اشاره‌گر است)
    }
  }
  // hi/lo روزانه را در یک گذرِ دوم دقیق می‌سازیم (سازگار با agg('max'/'min'))
  const nDays = dRng.length
  const dHi = new Array<number>(nDays).fill(-Infinity)
  const dLo = new Array<number>(nDays).fill(Infinity)
  for (let i = 0; i < n; i++) {
    const j = dayIndexOf[i]
    if (candles[i].high > dHi[j]) dHi[j] = candles[i].high
    if (candles[i].low < dLo[j]) dLo[j] = candles[i].low
  }
  for (let j = 0; j < nDays; j++) dRng[j] = dHi[j] - dLo[j]

  // ADR₂₁ = rolling(21).mean() روی روزها، سپس **shift(1)** (دامِ ①)
  const adrRoll = rollingMeanSimple(dRng, cfg.adrP)
  const adrDay = new Array<number>(nDays).fill(NaN)
  for (let j = 1; j < nDays; j++) adrDay[j] = adrRoll[j - 1]

  for (let i = 0; i < n; i++) {
    const j = dayIndexOf[i]
    const a = adrDay[j]
    const op = dOpen[j]
    adrOut[i] = a
    dayOpenOut[i] = op
    // پایتون: np.where(adr > 0, (c − dopen)/adr, nan) — NaN>0 نادرست ⇒ NaN
    frac[i] = (isFinite(a) && a > 0) ? (candles[i].close - op) / a : NaN
  }

  // --- دامِ ②: ATR₁۰۰ میانگینِ سادهٔ TR، **بدونِ شیفت** ---
  const tr = new Array<number>(n).fill(0)
  for (let i = 0; i < n; i++) {
    const pc = i === 0 ? candles[0].close : candles[i - 1].close
    const h = candles[i].high, l = candles[i].low
    tr[i] = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc))
  }
  const atrPx = rollingMeanSimple(tr, cfg.atrP)

  // --- دامِ ④: هندسهٔ برداری از ATR همان کندل ---
  const slPip = new Array<number>(n).fill(NaN)
  const tpPip = new Array<number>(n).fill(NaN)
  for (let i = 0; i < n; i++) {
    if (!isFinite(atrPx[i])) continue
    slPip[i] = (cfg.slK * atrPx[i]) / GOLD_PIP
    tpPip[i] = cfg.rr * slPip[i]
  }

  return { frac, adr: adrOut, dayOpen: dayOpenOut, atrPx, slPip, tpPip }
}

// ---------------------------------------------------------------------------
// computeS770 — سیگنال روی آخرین کندلِ بسته i = n−1 (ورود در openِ کندلِ بعد)
//   قاعده (§۳ سند، کلمه‌به‌کلمه):
//     LONG  اگر frac[i−1] <  +θ  و  frac[i] ≥ +θ   (عبورِ رو-به-بالا)
//     SHORT اگر frac[i−1] > −θ  و  frac[i] ≤ −θ   (عبورِ رو-به-پایین)
// ---------------------------------------------------------------------------
export function computeS770(candles: Candle[], cfg: S770Config): RawSignal {
  const n = candles.length
  // گرم‌شدن: ATR₁۰۰ به ۱۰۰ کندل نیاز دارد و ADR₂۱ به ۲۲ روزِ تقویمی؛ روی D1
  // این دو یکی‌اند (۱۰۰ کندل = ۱۰۰ روز) و روی H8 ATR سخت‌گیرتر است.
  const warm = cfg.atrP + 2

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  if (n < warm) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: cfg.medSlPip * GOLD_PIP, tpDist: cfg.medSlPip * cfg.rr * GOLD_PIP,
      maxHoldBars: cfg.maxHold,
      reason: `دادهٔ کافی نیست: این لایه ${warm} کندلِ بستهٔ ${cfg.tfFa} برای گرم‌شدنِ ATR(${cfg.atrP}) و ADR(${cfg.adrP} روزِ تقویمی) لازم دارد (موجود: ${n}).`,
      indicators: emptyInd,
    }
  }

  const f = s770Features(candles, cfg)
  const i = n - 1                      // آخرین کندلِ بسته‌شده

  const fracNow = f.frac[i]
  const fracPrev = f.frac[i - 1]
  const adrNow = f.adr[i]
  const atr = f.atrPx[i]
  const sl = f.slPip[i]
  // valid عینِ پایتون: isfinite(frac) & isfinite(sl_pip) & (sl_pip>0)
  const valid = isFinite(fracNow) && isFinite(sl) && sl > 0
  const crossable = valid && isFinite(fracPrev)

  const slPip = valid ? sl : cfg.medSlPip
  const tpPip = slPip * cfg.rr
  const slDist = slPip * GOLD_PIP
  const tpDist = tpPip * GOLD_PIP

  const th = cfg.theta
  const longSig = crossable && fracPrev < th && fracNow >= th
  const shortSig = crossable && fracPrev > -th && fracNow <= -th
  const active = longSig || shortSig
  const direction: 'LONG' | 'SHORT' = shortSig ? 'SHORT' : 'LONG'

  // «نزدیک‌شدن» — فقط اطلاع‌رسانی؛ هیچ معامله‌ای از این شاخه صادر نمی‌شود.
  // حالت در ۸۵–۱۰۰٪ آستانه است و هنوز عبور نکرده.
  const nearUp = valid && !active && fracNow >= cfg.approachFrac * th && fracNow < th
  const nearDn = valid && !active && fracNow <= -cfg.approachFrac * th && fracNow > -th
  const approaching = nearUp || nearDn

  const pctOfTh = valid && th > 0 ? (Math.abs(fracNow) / th) * 100 : 0

  const indicators: RouterDecision['indicators'] = [
    {
      name: `حالتِ انبساط frac = (close − openِ روز) ÷ ADR${cfg.adrP} در برابرِ آستانهٔ ±${cfg.theta}`,
      value: valid ? `${fracNow >= 0 ? '+' : ''}${fracNow.toFixed(3)} / ±${th.toFixed(2)} (${pctOfTh.toFixed(0)}٪ آستانه)` : '—',
      status: active ? 'ok' : (approaching ? 'neutral' : 'bad'),
    },
    {
      name: 'حالتِ کندلِ قبل (لازم برای «عبور» — نه فقط بودن بالای آستانه)',
      value: isFinite(fracPrev) ? `${fracPrev >= 0 ? '+' : ''}${fracPrev.toFixed(3)}` : '—',
      status: active ? 'ok' : 'neutral',
    },
    {
      name: `ADR${cfg.adrP} — مقیاسِ عادیِ دامنهٔ روزانه (علّی: تا روزِ قبل)`,
      value: isFinite(adrNow) ? `${(adrNow / GOLD_PIP).toFixed(0)} pip ($${adrNow.toFixed(2)})` : '—',
      status: 'neutral',
    },
    {
      name: `ATR(${cfg.atrP}) کارتِ ${cfg.tfFa} — هندسهٔ برداریِ عینِ بک‌تست`,
      value: isFinite(atr) ? `${(atr / GOLD_PIP).toFixed(1)} pip` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (این کارت)',
      value: `${slPip.toFixed(1)} / ${tpPip.toFixed(1)} pip (نسبت ${cfg.rr} ⇒ هدف بزرگ‌تر از حدِ ضرر)`,
      status: 'ok',
    },
  ]

  let reason: string
  if (active) {
    const side = direction === 'LONG' ? 'خرید' : 'فروش'
    const dirFa = direction === 'LONG' ? 'رو به بالا' : 'رو به پایین'
    reason =
      `حالتِ انبساطِ دامنه همین الآن آستانه را **قطع کرد** ${dirFa}: ` +
      `frac از ${fracPrev.toFixed(3)} به ${fracNow >= 0 ? '+' : ''}${fracNow.toFixed(3)} رفت و از ` +
      `${direction === 'LONG' ? '+' : '−'}${th.toFixed(2)} گذشت ⇒ سیگنالِ ${side}. ` +
      `یعنی حرکتِ امروز از **مقیاسِ عادیِ روزانه** (ADR${cfg.adrP} = ${isFinite(adrNow) ? (adrNow / GOLD_PIP).toFixed(0) : '—'} pip) ` +
      `فراتر رفته — نشانهٔ ورودِ جریانِ سفارشِ اطلاعاتی که تداوم می‌یابد. ` +
      `فیزیکِ اندازه‌گیری‌شده: ۶۸۹ معامله در ۱۵.۶ سال روی استخرِ D1+H8 · WR=۴۴.۷٪ با نسبتِ ` +
      `${cfg.rr} · هر ۱۱ دروازهٔ RQS2 پاس (z=۳.۹۱ در برابرِ سدِ ۲.۸۹۷ با شمارشِ ۳۰۱ آزمون) · ` +
      `نیمهٔ پنهانِ داده (holdout) حتی **بهتر** بود (PF=۱.۵۰). ` +
      `ورود روی openِ کندلِ بعد؛ SL=${slPip.toFixed(1)} / TP=${tpPip.toFixed(1)} pip ` +
      `(${cfg.slK}×ATR(${cfg.atrP}) همین کندل، عینِ بک‌تست).`
  } else if (approaching) {
    const towards = fracNow >= 0 ? 'سقفِ' : 'کفِ'
    reason =
      `حالتِ انبساط (${fracNow >= 0 ? '+' : ''}${fracNow.toFixed(3)}) به ${pctOfTh.toFixed(0)}٪ ` +
      `${towards} آستانهٔ ±${th.toFixed(2)} رسیده ولی هنوز **عبور نکرده**. اگر کندلِ بعد ` +
      `آستانه را قطع کند، ورود صادر می‌شود. توجه: خودِ «بودن» بالای آستانه سیگنال نیست — ` +
      `فقط لحظهٔ **عبور** اطلاعات دارد (قاعدهٔ state-cross). هنوز معامله‌ای نیست.`
  } else if (!valid) {
    reason =
      `ADR${cfg.adrP} یا ATR(${cfg.atrP}) هنوز معتبر نیست (گرم‌شدنِ ${warm} کندلی / ` +
      `${cfg.adrP + 1} روزِ تقویمی) — لایه در انتظار.`
  } else if (Math.abs(fracNow) >= th) {
    reason =
      `حالتِ انبساط (${fracNow >= 0 ? '+' : ''}${fracNow.toFixed(3)}) بالای آستانهٔ ±${th.toFixed(2)} است، ` +
      `ولی کندلِ قبل هم بالای آستانه بود (${fracPrev.toFixed(3)}) ⇒ **عبورِ تازه‌ای رخ نداده** و ورودی صادر نمی‌شود. ` +
      `این عمدی است: اطلاعات در لبهٔ تغییرِ حالت است نه در حالتِ انباشته — همان قاعده‌ای که ` +
      `اندازه‌گیری شد و پاس گرفت (اگر «بودن» را سیگنال می‌گرفتیم، یک رویداد چند بار شمرده می‌شد).`
  } else {
    reason =
      `حرکتِ روزِ جاری در مقیاسِ عادی است: frac=${fracNow >= 0 ? '+' : ''}${fracNow.toFixed(3)} یعنی ` +
      `${pctOfTh.toFixed(0)}٪ آستانهٔ ±${th.toFixed(2)} (${isFinite(adrNow) ? (adrNow / GOLD_PIP).toFixed(0) : '—'} pip دامنهٔ عادی). ` +
      `این لایه کم‌بسامد است (~۴۴ معاملهٔ استخری در سال روی دو کارت) — بیشترِ کندل‌ها هیچ‌اند ` +
      `و همین صداقتِ لایه است.`
  }

  return {
    active, approaching, direction,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ **عبورِ** frac از ${fracNow >= 0 ? '+' : '−'}${th.toFixed(2)} روی کندلِ بعدِ ${cfg.tfFa}`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS770(
  cfg: S770Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS770(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s770_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10

  const meta: DecideMeta = {
    code: 'S770',
    name: `انبساطِ دامنه نسبت به ADR با تداوم (${cfg.tfFa})`,
    kind: 'range_expansion' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ برداریِ عینِ بک‌تست: SL=${slPipShow} / TP=${tpPipShow} pip ` +
      `(${cfg.slK}×ATR(${cfg.atrP}) کندلِ سیگنال × نسبتِ ${cfg.rr}؛ میانهٔ تاریخیِ استخر ≈۲۲۰/۴۵۳ pip). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندلِ ${cfg.tfFa} نگه‌دار. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false در بک‌تست) و **مهم‌تر**: حکمِ ACCEPT روی ` +
      `**استخرِ D1+H8 با صفِ FIFO و همزمانیِ حداکثر ۱** صادر شده. یعنی اگر کارتِ D1 و ` +
      `کارتِ H8 هم‌زمان سیگنال دادند، **فقط اولی** معامله می‌شود و دومی تا بسته‌شدنِ آن ` +
      `صرفِ‌نظر می‌شود — وگرنه ریسک دو برابر و حکمِ اندازه‌گیری‌شده بی‌اعتبار است. ` +
      `⚠️ همچنین با S382-H4 تلاقیِ زمانیِ ۶۲.۷٪ دارد (هر دو hold بلند) ⇒ سایزِ مشترک؛ ` +
      `ولی بخشِ مستقلش هم سودده است (WR ۳۶.۰٪ بالای سربه‌سرِ ۳۳.۲٪) ⇒ حذف لازم نیست.`,
    filters: [
      `عبورِ حالت (state-cross) از ±${cfg.theta}: frac = (close − openِ روزِ UTC) ÷ ADR${cfg.adrP}`,
      `ADR${cfg.adrP} روی روزهای تقویمی و با شیفتِ ۱ روز (علّی — روزِ جاری در آن نیست)`,
      `هندسهٔ برداری SL=${cfg.slK}×ATR(${cfg.atrP}) و TP=${cfg.rr}×SL ⇒ TP>SL (قانونِ بودجه)`,
      `دوسویه: هر دو سو مستقلاً لبه دارند (long +۹.۰۶pp · short +۵.۲۵pp)`,
      'صفر فیلترِ رژیم/جهت ⇒ بودجهٔ معامله دست‌نخورده · صفِ FIFO استخری با کارتِ دیگر',
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
