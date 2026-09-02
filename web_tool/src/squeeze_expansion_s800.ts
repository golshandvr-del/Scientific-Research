// ---------------------------------------------------------------------------
// S800 — «فشردگی → گشایش» (Squeeze-Expansion Breakout) · XAUUSD-D1 + XAUUSD-H12
//
// حکمِ نهایی (سند: results/S800_SqueezeExpansion_Xauusd_M1toMN1_rqs2_91_ACCEPT.md):
//   • XAUUSD-D1  → RQS2 = **91.1** · هر ۱۱ دروازه پاس · n=81  · WR=70.37٪ · PF=1.94
//                  maxDD=2.77٪ · MCL=3 (مجاز ۸) · lift=+21.12pp · z=3.80 · p_perm=7.2e−05
//   • XAUUSD-H12 → RQS2 = **83.6** · هر ۱۱ دروازه پاس · n=183 · WR=54.6٪  · PF=1.55
//                  maxDD=5.64٪ · MCL=7 · lift=+12.93pp · z=3.55 · p_perm=1.95e−04
//
// ⭐ چرا این لایه انتخاب شد و چرا **دو** کارت می‌گیرد: این تنها ACCEPTِ نو است که
//    **دو حکمِ مستقلِ تک-کارتی** دارد — هر کارت جداگانه با n_trials=1 (مسیر C،
//    hold-out فیزیکی) داوری شده و جداگانه هر ۱۱ دروازه را پاس کرده. حکمِ استخری
//    (pooled) نیست که اعضایش اثباتِ مستقل نداشته باشند ⇒ طبقِ **قانونِ MTF**
//    هر دو تایم‌فریم حقِ اتصال دارند و هر دو **باید** وصل شوند.
//
// فیزیکِ لایه: انقباضِ نوسان (ATR در چندکِ پایینِ ۱۰۱ کندلِ اخیر) انرژیِ ذخیره‌شده
//   است؛ شکستِ کانالِ دانچیان از دلِ همان فشردگی، «گشایش» را آزاد می‌کند. مقیاس
//   مهم است: روی D1/H12 گشایش ادامه دارد، ولی H1/H3/H6 با آزمونِ نهایی REJECT
//   شدند (۴.۹ / ۲۰.۵ / ۱۹.۷) و M1..M30 + H2 اصلاً توان نداشتند (lift·√n < 78)
//   ⇒ تعمیم به تایم‌فریمِ بدونِ شاهد **ممنوع**؛ فقط D1 و H12 وصل می‌شوند.
//
// همپوشانی (§۷ سند): با S382-H4 در تقویمِ روزانه D1=81.4٪ و H12=90.6٪ همپوشانی
//   دارد، ولی هر دو زیرمجموعهٔ «همپوشان» و «مستقل» سودده‌اند ⇒ فیلترِ حذفی لازم
//   نیست. ⚠️ روی حسابِ واقعی صفِ FIFO لازم است (قیدِ allow_overlap=false).
//
// ⚠️ پورتِ **مو-به-موی** strategies/s800_squeeze_expansion.py::base_arrays/
//    donch_signals/run_cfg + engine/indicator_bank.py — سه دامِ پورت:
//    ① `atr_pct` روی **RMA وایلدر** ساخته می‌شود (ewm(alpha=1/14, adjust=False))
//       نه SMA و نه EMA با span. هر میانگینِ دیگری منحنیِ متفاوتی می‌دهد.
//    ② `atr_pct` یک **رتبهٔ چندکی** است نه مقدارِ ATR: در پنجرهٔ ۱۰۱ کندلی
//       (lookback+1) برابرِ 100·(#{w ≤ w[-1]})/101 است ⇒ q=20 یعنی «ATR در
//       ۲۰٪ پایینِ ۱۰۱ کندلِ اخیر». اشتباهِ گرفتنش به‌جای درصدِ ATR، لایه را
//       کاملاً بی‌معنا می‌کند.
//    ③ ATRِ هندسه (`atr_fib_21` = RMA(TR,21)) **بدونِ شیفت** روی خودِ کندلِ
//       سیگنال خوانده می‌شود (بردارِ sl_pip_arr در بک‌تست شیفت نداشت). شیفت‌دادنش
//       نقضِ قانونِ آزموده‌شده است — و look-ahead هم نیست، چون ATRِ کندلِ سیگنال
//       در لحظهٔ بسته‌شدنش معلوم است و ورود در openِ کندلِ بعد رخ می‌دهد.
//    ④ فشردگی با تأخیرِ یک کندل خوانده می‌شود: sqz[t] = atr_pct[t−1] (وضعیت در
//       بازشدنِ کندلِ سیگنال معلوم است). دانچیان هم علّی است: hh[t]/ll[t] روی
//       [t−p , t−1] — خودِ کندلِ t در سقف/کف شرکت نمی‌کند.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'

const GOLD_PIP = 0.1

export interface S800Config {
  id: string           // شناسهٔ کارت (XAUUSD-D1 | XAUUSD-H12)
  tfFa: string         // برچسبِ تایم‌فریم برای متن‌ها
  donchP: number       // دورهٔ کانالِ دانچیان (قفل‌شده در <TF>_locked.json)
  sqzQ: number         // آستانهٔ رتبهٔ چندکیِ atr_pct (٪) — «فشردگی»
  atrP: number         // دورهٔ ATR پایه برای atr_pct (بانکِ اندیکاتور: ۱۴)
  atrLookback: number  // پنجرهٔ رتبه‌بندیِ چندکی (بانکِ اندیکاتور: ۱۰۰ ⇒ پنجرهٔ ۱۰۱)
  slAtrP: number       // دورهٔ ATRِ هندسه (atr_fib_21 ⇒ ۲۱)
  slK: number          // SL = slK × ATR(slAtrP)
  rr: number           // TP = rr × SL
  maxHold: number      // بیشینهٔ نگه‌داری بر حسبِ کندلِ همین تایم‌فریم
  approachFrac: number // «نزدیک‌شدن» (فقط UI): فاصله تا لبه ≤ approachFrac×ATR
  slMedPip: number     // میانهٔ تاریخیِ SL (برای پیامِ دادهٔ ناکافی و متنِ مدیریت)
  rqs2: number         // امتیازِ RQS2 همین کارت (فقط برای متن)
  nTrades: number      // تعدادِ معاملهٔ حکم (فقط برای متن)
  wr: number           // نرخِ بردِ حکم (فقط برای متن)
}

// پیکربندی‌های **قفل‌شده** — عیناً از results/_scan_S800/<TF>_locked.json
// (فاز explore فقط روی نیمهٔ اول اجرا شد؛ این‌ها پیش از دیدنِ حکم قفل شدند).
export const S800_CFG: Record<string, S800Config> = {
  // D1_locked.json : {"p":55,"q":20.0,"filter":"none","k":1.272,"rr":1.0,"hold":21}
  'XAUUSD-D1': {
    id: 'XAUUSD-D1', tfFa: 'D1',
    donchP: 55, sqzQ: 20.0, atrP: 14, atrLookback: 100,
    slAtrP: 21, slK: 1.272, rr: 1.0, maxHold: 21,
    approachFrac: 0.25, slMedPip: 257.8,
    rqs2: 91.1, nTrades: 81, wr: 70.4,
  },
  // H12_locked.json: {"p":21,"q":30.0,"filter":"none","k":2.058,"rr":1.618,"hold":34}
  'XAUUSD-H12': {
    id: 'XAUUSD-H12', tfFa: 'H12',
    donchP: 21, sqzQ: 30.0, atrP: 14, atrLookback: 100,
    slAtrP: 21, slK: 2.058, rr: 1.618, maxHold: 34,
    approachFrac: 0.25, slMedPip: 273.0,
    rqs2: 83.6, nTrades: 183, wr: 54.6,
  },
}

// ---------------------------------------------------------------------------
// trueRange — بازتولیدِ engine/indicator_bank.py::_tr
//   pc = close.shift(1)  ⇒ در t=0 مقدارش NaN است و np.max با NaN-skipping
//   فقط (h−l) را برمی‌گرداند ⇒ tr[0] = high[0] − low[0].
// ---------------------------------------------------------------------------
function trueRange(c: Candle[]): number[] {
  const n = c.length
  const tr = new Array<number>(n).fill(0)
  if (n === 0) return tr
  tr[0] = c[0].high - c[0].low
  for (let t = 1; t < n; t++) {
    const h = c[t].high, l = c[t].low, pc = c[t - 1].close
    tr[t] = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc))
  }
  return tr
}

// ---------------------------------------------------------------------------
// rmaWilder — بازتولیدِ pandas `s.ewm(alpha=1/p, adjust=False).mean()`
//   out[0] = x[0] ; out[t] = out[t−1] + (1/p)·(x[t] − out[t−1])
//   (دامِ ① — این «RMA وایلدر» است، نه SMA و نه EMA با span=p)
// ---------------------------------------------------------------------------
function rmaWilder(x: number[], p: number): number[] {
  const n = x.length
  const out = new Array<number>(n).fill(0)
  if (n === 0) return out
  const alpha = 1.0 / p
  out[0] = x[0]
  for (let t = 1; t < n; t++) out[t] = out[t - 1] + alpha * (x[t] - out[t - 1])
  return out
}

export interface S800Features {
  atrPct: number[]   // رتبهٔ چندکیِ ATR در پنجرهٔ ۱۰۱ کندلی (NaN تا گرم‌شدن)
  sqz: number[]      // atrPct با تأخیرِ ۱ کندل (دامِ ④)
  donchHi: number[]  // سقفِ [t−p , t−1] (NaN تا t = p)
  donchLo: number[]  // کفِ  [t−p , t−1]
  atrSl: number[]    // RMA(TR, slAtrP) — بدونِ شیفت (دامِ ③)
}

// پورتِ عینِ base_arrays() + donch_signals() — همه علّی.
export function s800Features(candles: Candle[], cfg: S800Config): S800Features {
  const n = candles.length
  const tr = trueRange(candles)

  // ---- atr_pct : رتبهٔ چندکیِ RMA(TR,14) در پنجرهٔ (lookback+1) کندلی (دامِ ②)
  const atrBase = rmaWilder(tr, cfg.atrP)
  const W = cfg.atrLookback + 1                    // = 101
  const atrPct = new Array<number>(n).fill(NaN)
  for (let t = W - 1; t < n; t++) {
    const cur = atrBase[t]
    let cnt = 0
    for (let j = t - W + 1; j <= t; j++) if (atrBase[j] <= cur) cnt++
    atrPct[t] = (100.0 * cnt) / W
  }

  // ---- فشردگی با تأخیرِ ۱ کندل: sqz[0]=NaN ; sqz[t]=atr_pct[t−1]
  const sqz = new Array<number>(n).fill(NaN)
  for (let t = 1; t < n; t++) sqz[t] = atrPct[t - 1]

  // ---- کانالِ دانچیان علّی: rolling(p).max().shift(1) ⇒ بازهٔ [t−p , t−1]
  const P = cfg.donchP
  const donchHi = new Array<number>(n).fill(NaN)
  const donchLo = new Array<number>(n).fill(NaN)
  for (let t = P; t < n; t++) {
    let hi = -Infinity, lo = Infinity
    for (let j = t - P; j <= t - 1; j++) {
      if (candles[j].high > hi) hi = candles[j].high
      if (candles[j].low < lo) lo = candles[j].low
    }
    donchHi[t] = hi
    donchLo[t] = lo
  }

  // ---- ATRِ هندسه: atr_fib_21 = RMA(TR,21) — **بدونِ شیفت** (دامِ ③)
  const atrSl = rmaWilder(tr, cfg.slAtrP)

  return { atrPct, sqz, donchHi, donchLo, atrSl }
}

// ---------------------------------------------------------------------------
// computeS800 — سیگنال روی آخرین کندلِ بستهٔ i = n−1 (ورود در openِ کندلِ بعد)
// ---------------------------------------------------------------------------
export function computeS800(candles: Candle[], cfg: S800Config): RawSignal {
  const n = candles.length
  const warm = Math.max(cfg.atrLookback + 2, cfg.donchP + 1)   // D1: 102 · H12: 102

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  if (n < warm + 1) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: cfg.slMedPip * GOLD_PIP, tpDist: cfg.slMedPip * cfg.rr * GOLD_PIP,
      maxHoldBars: cfg.maxHold,
      reason:
        `دادهٔ کافی نیست: این لایه ${warm} کندلِ بستهٔ ${cfg.tfFa} لازم دارد تا رتبهٔ چندکیِ ` +
        `ATR (پنجرهٔ ${cfg.atrLookback + 1} کندلی) و کانالِ دانچیانِ ${cfg.donchP} گرم شوند ` +
        `(موجود: ${n}).`,
      indicators: emptyInd,
    }
  }

  const f = s800Features(candles, cfg)
  const i = n - 1                                  // آخرین کندلِ بسته‌شده

  const close = candles[i].close
  const sq = f.sqz[i]
  const hh = f.donchHi[i]
  const ll = f.donchLo[i]
  const atr = f.atrSl[i]

  const slPip = Math.max((cfg.slK * atr) / GOLD_PIP, 1e-9)
  const tpPip = slPip * cfg.rr
  const slDist = slPip * GOLD_PIP
  const tpDist = tpPip * GOLD_PIP

  const valid = Number.isFinite(sq) && Number.isFinite(hh) && Number.isFinite(ll) && atr > 0
  const sqzOk = valid && sq < cfg.sqzQ
  const breakUp = valid && close > hh
  const breakDn = valid && close < ll

  const longSig = sqzOk && breakUp
  const shortSig = sqzOk && breakDn
  const active = longSig || shortSig
  const direction: 'LONG' | 'SHORT' = shortSig ? 'SHORT' : 'LONG'

  // «نزدیک‌شدن» — فقط اطلاع‌رسانیِ UI؛ هیچ ورودی از این شاخه صادر نمی‌شود.
  // شرط: فشردگی برقرار است و قیمت تا لبهٔ کانال کمتر از approachFrac×ATR فاصله دارد.
  const distUp = valid ? hh - close : Infinity
  const distDn = valid ? close - ll : Infinity
  const nearBand = Math.min(Math.max(distUp, 0), Math.max(distDn, 0))
  const approaching = sqzOk && !active && atr > 0 && nearBand <= cfg.approachFrac * atr
  const approachSide: 'LONG' | 'SHORT' = distUp <= distDn ? 'LONG' : 'SHORT'
  const dirShown: 'LONG' | 'SHORT' = active ? direction : (approaching ? approachSide : direction)

  const indicators: RouterDecision['indicators'] = [
    {
      name: `فشردگیِ نوسان — رتبهٔ چندکیِ ATR(${cfg.atrP}) در ${cfg.atrLookback + 1} کندلِ اخیر (با تأخیرِ ۱)`,
      value: valid ? `${sq.toFixed(1)}٪ / آستانه < ${cfg.sqzQ.toFixed(0)}٪` : '—',
      status: sqzOk ? 'ok' : 'bad',
    },
    {
      name: `کانالِ دانچیانِ ${cfg.donchP} (سقف/کفِ ${cfg.donchP} کندلِ قبل — علّی)`,
      value: valid ? `${ll.toFixed(2)} … ${hh.toFixed(2)} $` : '—',
      status: (breakUp || breakDn) ? 'ok' : 'neutral',
    },
    {
      name: 'قیمتِ بسته در برابرِ لبهٔ کانال',
      value: valid
        ? `${close.toFixed(2)} $ · فاصله تا سقف ${distUp.toFixed(2)}$ / تا کف ${distDn.toFixed(2)}$`
        : '—',
      status: (breakUp || breakDn) ? 'ok' : (approaching ? 'neutral' : 'bad'),
    },
    {
      name: `ATR(${cfg.slAtrP}) — هندسهٔ برداریِ عینِ بک‌تست (بدونِ شیفت)`,
      value: atr > 0 ? `${(atr / GOLD_PIP).toFixed(1)} pip` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (این کارت)',
      value: `${slPip.toFixed(1)} / ${tpPip.toFixed(1)} pip (نسبت ${cfg.rr})`,
      status: 'ok',
    },
  ]

  let reason: string
  if (active) {
    const side = direction === 'LONG' ? 'خرید' : 'فروش'
    const edge = direction === 'LONG'
      ? `سقفِ کانال (${hh.toFixed(2)}$)`
      : `کفِ کانال (${ll.toFixed(2)}$)`
    reason =
      `کندلِ بستهٔ ${cfg.tfFa} از دلِ **فشردگی** ${edge} را شکست: نوسان در رتبهٔ چندکیِ ` +
      `${sq.toFixed(1)}٪ (< ${cfg.sqzQ.toFixed(0)}٪ آستانه) بود و قیمتِ بسته ${close.toFixed(2)}$ ` +
      `از لبه عبور کرد ⇒ سیگنالِ ${side}. فیزیکِ اندازه‌گیری‌شده: انقباضِ نوسان انرژیِ ذخیره‌شده ` +
      `است و گشایشِ پس از آن روی ${cfg.tfFa} ادامه دارد ` +
      `(${cfg.nTrades} معامله در ۱۵.۶ سال · WR=${cfg.wr.toFixed(1)}٪ · RQS2=${cfg.rqs2} · ` +
      `هر ۱۱ دروازه پاس · مسیر C با hold-out فیزیکی و n_trials=1). ` +
      `ورود روی openِ کندلِ بعد؛ SL=${slPip.toFixed(1)} pip (${cfg.slK}×ATR(${cfg.slAtrP}) همین کندل) ` +
      `و TP=${tpPip.toFixed(1)} pip (${cfg.rr}×SL) — عینِ بک‌تست.`
  } else if (approaching) {
    const edge = approachSide === 'LONG' ? 'سقف' : 'کف'
    reason =
      `فشردگی برقرار است (رتبهٔ چندکیِ ATR = ${sq.toFixed(1)}٪ < ${cfg.sqzQ.toFixed(0)}٪) و قیمت تا ` +
      `${edge}ِ کانالِ دانچیانِ ${cfg.donchP} فقط ${nearBand.toFixed(2)}$ فاصله دارد ` +
      `(کمتر از ${cfg.approachFrac}×ATR). اگر کندلِ بعد **بسته‌شده** آن‌سویِ لبه بنشیند و فشردگی ` +
      `هنوز برقرار باشد، ورود صادر می‌شود. هنوز معامله‌ای نیست.`
  } else if (!valid) {
    reason =
      `اندیکاتورها هنوز گرم نشده‌اند (نیازِ ${warm} کندلِ بستهٔ ${cfg.tfFa} برای رتبهٔ چندکیِ ATR ` +
      `و کانالِ ${cfg.donchP}) — لایه در انتظار.`
  } else if (!sqzOk) {
    reason =
      `شرطِ **فشردگی** برقرار نیست: رتبهٔ چندکیِ ATR = ${sq.toFixed(1)}٪ در حالی که آستانه ` +
      `< ${cfg.sqzQ.toFixed(0)}٪ است. این لایه فقط شکستی را می‌خرد که از دلِ آرامش بیرون بیاید؛ ` +
      `شکست در بازارِ از پیش پرنوسان همان چیزی است که در آزمون لبه نداشت.`
  } else {
    reason =
      `فشردگی هست (${sq.toFixed(1)}٪ < ${cfg.sqzQ.toFixed(0)}٪) ولی هنوز شکستی رخ نداده: ` +
      `قیمتِ بسته ${close.toFixed(2)}$ درونِ کانالِ ${ll.toFixed(2)}…${hh.toFixed(2)}$ است. ` +
      `این لایه کم‌بسامد است (~${(cfg.nTrades / 15.6).toFixed(1)} معامله در سال) — بیشترِ کندل‌ها ` +
      `هیچ‌اند و همین صداقتِ لایه است.`
  }

  return {
    active, approaching, direction: dirShown,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ بسته‌شدنِ کندلِ بعد آن‌سویِ کانالِ دانچیانِ ${cfg.donchP} با فشردگیِ برقرار`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS800(
  cfg: S800Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS800(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s800_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10

  const meta: DecideMeta = {
    code: 'S800',
    name: `فشردگی → گشایش (${cfg.tfFa})`,
    kind: 'squeeze_expansion' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ برداریِ عینِ بک‌تست: SL=${slPipShow} pip (${cfg.slK}×ATR(${cfg.slAtrP}) کندلِ سیگنال؛ ` +
      `میانهٔ تاریخی ≈${cfg.slMedPip.toFixed(0)} pip) و TP=${tpPipShow} pip (${cfg.rr}×SL). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندلِ ${cfg.tfFa} نگه‌دار. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false در بک‌تست): تا این معامله بسته نشده، شکستِ بعدی ` +
      `نباید معاملهٔ جدید باز کند. ⚠️ همپوشانیِ تقویمیِ بالا با S382-H4 ` +
      `(D1 ≈۸۱٪ · H12 ≈۹۱٪): روی حسابِ واقعی صفِ FIFO لازم است — هر دو زیرمجموعه سودده‌اند ` +
      `پس حذفِ لایه لازم نیست، ولی ریسکِ همزمان نباید دوبرابر شود.`,
    filters: [
      `فشردگی: رتبهٔ چندکیِ ATR(${cfg.atrP}) در ${cfg.atrLookback + 1} کندلِ اخیر < ${cfg.sqzQ.toFixed(0)}٪ (با تأخیرِ ۱ کندل)`,
      `گشایش: بسته‌شدن بیرونِ کانالِ دانچیانِ ${cfg.donchP} (سقف/کفِ ${cfg.donchP} کندلِ قبل — علّی)`,
      `هندسهٔ ثابت: SL=${cfg.slK}×ATR(${cfg.slAtrP}) · TP=${cfg.rr}×SL · بیشینه نگه‌داری ${cfg.maxHold} کندل`,
      `بدونِ فیلترِ رژیم (filter="none" در پیکربندیِ قفل‌شده) · قیدِ تک‌معامله`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
