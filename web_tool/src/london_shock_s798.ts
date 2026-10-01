// ---------------------------------------------------------------------------
// S798 — «ادامهٔ شوکِ نشستِ لندن» (London-Session Shock Continuation) · XAUUSD-**H8**
//
// حکمِ نهایی (سند: results/S798_LondonSessionShockContinuation_Xauusd_H8_rqs2_86.9_ACCEPT.md):
//   RQS2 = **86.9** · ACCEPT · n=79 · WR=74.68٪ · PF=3.10 · n_trials=149 · نول K=500 (seed 798)
//   پیش‌ثبت: strategies/S798_PREREG.md (کامیت 8c5a19d8) — صفر تیونِ پس از داوری.
//
// فیزیکِ لایه: کندلِ H8ِ ساعتِ ۰۸ UTC (۰۸:۰۰–۱۶:۰۰ = نشستِ لندن + همپوشانیِ نیویورک)
// اگر یک **شوکِ دامنه** باشد (high−low ≥ 2.618×ATR21[i−1])، جریانِ نهادیِ لندن
// جهتِ بدنه را ادامه می‌دهد ⇒ follow. هیچ شرطِ ρ (ماندگاری) ندارد — این همان
// چیزی است که آن را از S965 جدا می‌کند (S965 = شوکِ هر ساعت × ρ ≥ 0.618).
//
// ⚠️ قانونِ MTF: فقط کارتِ H8 پیش‌ثبت و داوری شد ⇒ **فقط XAUUSD-H8**. تعمیم ممنوع.
//
// ⚠️ پورتِ مو-به-موی strategies/s798_final.py — دامِ پورت:
//   ① ATR21 اینجا **EMA** است (α = 2/22، a[0] = tr[0] = H0−L0) سپس **شیفتِ ۱**
//      (atr[0] = NaN) — نه میانگینِ سادهٔ `_rollsum`ِ لایه‌های کایل (S965/S966/S1911)
//      و نه Wilder. استفاده از s965Features این‌جا غلط است.
//   ② هندسه متقارن: SL = TP = 1.618×ATR21[i−1] (RR=1.0) · max_hold = 12 کندلِ H8.
//   ③ ساعت = ساعتِ UTCِ **شروعِ** کندلِ H8 (سرورِ MT5 = UTC، مرزهای 0/8/16)؛
//      aggregateCandles(H1, 8) همان مرزها را می‌سازد (floor(time/28800)).
//
// 🔎 ممیزیِ شاهدِ کاذب (tools/s798_false_witness_audit.py → results/_s798/false_witness_h8.json):
//   حکم **CLEAR** در برابرِ هر ۸ ساکنِ H8 (آستانهٔ شاهدِ کاذب: jaccard ≥ 0.6 یا share ≥ 0.9):
//   S955 0.113 · S965 **0.286** · S770 0.055 · S966 0.143 · S1911 0.229 · S607 0.094 ·
//   S1520 0.010 · S589 0.006 · جهتِ مخالف = صفر در همه.
//   قیدِ اندازه (نه شاهدِ کاذب): ۶۳٪ رویدادهای S798 هم‌کندل با S965 هستند (هم‌جهت)
//   و ۸۸.۶٪ درونِ مجموعهٔ بسیار بزرگ‌ترِ S770 (۱۲۷۲ رویداد) می‌نشینند ⇒ وقتی هم‌زمان
//   روشن شدند، **یک پوزیشن** است نه دو شاهدِ مستقل؛ حجم را دوبرابر نکنید.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'

const GOLD_PIP = 0.1

export interface S798Config {
  id: string          // شناسهٔ کارت (XAUUSD-H8)
  tfFa: string        // برچسبِ فارسی
  hourUtc: number     // ساعتِ شروعِ کندلِ نشست (قفل: 8)
  theta: number       // آستانهٔ شوک: high−low ≥ theta×ATR21[i−1] (قفل: 2.618)
  atrWin: number      // پنجرهٔ EMA-ATR (قفل: 21)
  kSl: number         // SL = kSl×ATR21[i−1] (قفل: 1.618)
  rr: number          // TP = rr×SL (قفل: 1.0)
  maxHold: number     // بیشینهٔ نگه‌داری بر حسبِ کندلِ H8 (قفل: 12)
  approachFrac: number // فقط UI: «نزدیک‌شدن» = رنج ≥ approachFrac×آستانه
}

export const S798_CFG: Record<string, S798Config> = {
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    hourUtc: 8, theta: 2.618, atrWin: 21, kSl: 1.618, rr: 1.0, maxHold: 12,
    approachFrac: 0.85,
  },
}

// پورتِ عینِ atr21() پایتون: EMA روی TR با tr[0]=H0−L0، سپس شیفتِ ۱ (out[0]=NaN).
export function s798AtrPrev(candles: Candle[], p = 21): number[] {
  const n = candles.length
  const out = new Array<number>(n).fill(NaN)
  if (n === 0) return out
  const al = 2 / (p + 1)
  let a = candles[0].high - candles[0].low
  // out[i] = a[i−1]
  for (let i = 1; i < n; i++) {
    out[i] = a
    const h = candles[i].high, l = candles[i].low, pc = candles[i - 1].close
    const tr = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc))
    a = a + (tr - a) * al
  }
  return out
}

// ماشهٔ خام روی هر اندیسِ i (برای پریتی): 0 = هیچ، +1 = LONG، −1 = SHORT
export function s798SignalAt(candles: Candle[], atrPrev: number[], i: number, cfg: S798Config): number {
  const k = candles[i]
  const ap = atrPrev[i]
  if (!(ap === ap)) return 0                       // NaN
  if (new Date(k.time * 1000).getUTCHours() !== cfg.hourUtc) return 0
  if (k.high - k.low < cfg.theta * ap) return 0
  if (k.close === k.open) return 0
  return k.close > k.open ? 1 : -1
}

export function computeS798(candles: Candle[], cfg: S798Config): RawSignal {
  const n = candles.length
  const minBars = cfg.atrWin + 3
  if (n < minBars) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 0, tpDist: 0, maxHoldBars: cfg.maxHold,
      reason: `دادهٔ کافی نیست: این لایه دستِ‌کم ${minBars} کندلِ بستهٔ ${cfg.tfFa} برای ATR(${cfg.atrWin}) علّی لازم دارد (موجود: ${n}).`,
      indicators: [{ name: 'داده', value: 'ناکافی', status: 'neutral' }],
    }
  }
  const atrPrev = s798AtrPrev(candles, cfg.atrWin)
  const i = n - 1
  const k = candles[i]
  const ap = atrPrev[i]
  const valid = ap === ap && ap > 1e-12
  const hr = new Date(k.time * 1000).getUTCHours()
  const isSession = hr === cfg.hourUtc
  const rng = k.high - k.low
  const thr = valid ? cfg.theta * ap : 0
  const isShock = valid && rng >= thr
  const sgn = k.close > k.open ? 1 : (k.close < k.open ? -1 : 0)
  const sig = s798SignalAt(candles, atrPrev, i, cfg)
  const active = sig !== 0
  const direction: 'LONG' | 'SHORT' = sig < 0 ? 'SHORT' : 'LONG'

  const slDist = valid ? cfg.kSl * ap : 0
  const tpDist = slDist * cfg.rr
  const slPip = slDist / GOLD_PIP
  const ratio = thr > 0 ? rng / thr : 0
  // نزدیک‌شدن: فقط اطلاع‌رسانی — کندلِ بستهٔ نشستِ لندن تا ۸۵–۱۰۰٪ آستانه رسید.
  const approaching = valid && !active && isSession && !isShock && sgn !== 0 && rng >= cfg.approachFrac * thr

  const indicators: RouterDecision['indicators'] = [
    {
      name: `کندلِ نشستِ لندن (H8ِ ساعتِ ${String(cfg.hourUtc).padStart(2, '0')}:00 UTC)`,
      value: `آخرین کندلِ بسته: ${String(hr).padStart(2, '0')}:00 UTC`,
      status: isSession ? 'ok' : 'neutral',
    },
    {
      name: `رنجِ کندل در برابرِ آستانهٔ شوک (${cfg.theta}×ATR${cfg.atrWin}[i−1])`,
      value: valid ? `${(rng / GOLD_PIP).toFixed(1)} / ${(thr / GOLD_PIP).toFixed(1)} pip (${(ratio * 100).toFixed(0)}٪)` : '—',
      status: isShock ? 'ok' : (approaching ? 'neutral' : 'bad'),
    },
    {
      name: 'جهتِ بدنه (follow)',
      value: sgn > 0 ? 'صعودی (LONG)' : (sgn < 0 ? 'نزولی (SHORT)' : 'doji'),
      status: sgn !== 0 ? 'neutral' : 'bad',
    },
    {
      name: 'حد ضرر / هدف (متقارن)',
      value: valid ? `${slPip.toFixed(1)} / ${(slPip * cfg.rr).toFixed(1)} pip (${cfg.kSl}×ATR · RR ${cfg.rr})` : '—',
      status: 'ok',
    },
  ]

  let reason: string
  if (active) {
    const side = direction === 'LONG' ? 'خرید' : 'فروش'
    reason =
      `کندلِ H8ِ نشستِ لندن (۰۸:۰۰ UTC) یک **شوکِ دامنه** بود: رنج ${(rng / GOLD_PIP).toFixed(1)} pip ` +
      `≥ ${cfg.theta}×ATR(${cfg.atrWin})=${(thr / GOLD_PIP).toFixed(1)} pip ⇒ ادامهٔ جهتِ بدنه ⇒ سیگنالِ ${side}. ` +
      `(۷۹ معامله در ۱۵.۶ سال · WR=۷۴.۶۸٪ · PF=۳.۱۰ · RQS2=۸۶.۹). ورود روی openِ کندلِ بعد؛ ` +
      `SL=TP=${slPip.toFixed(1)} pip (${cfg.kSl}×ATR علّی)، حداکثر ${cfg.maxHold} کندلِ H8. ` +
      `⚠️ ۶۳٪ این رویدادها با S965 هم‌کندل‌اند: اگر S965 هم روشن است، یک پوزیشن است نه دو شاهد.`
  } else if (!valid) {
    reason = `ATR(${cfg.atrWin}) هنوز معتبر نیست — لایه در انتظار.`
  } else if (!isSession) {
    reason =
      `آخرین کندلِ بسته (${String(hr).padStart(2, '0')}:00 UTC) کندلِ نشستِ لندن نیست. این لایه فقط ` +
      `روی کندلِ H8ِ ۰۸:۰۰ UTC قضاوت می‌کند (~۵ معامله در سال) — بیشترِ کندل‌ها هیچ‌اند.`
  } else if (approaching) {
    reason =
      `کندلِ نشستِ لندن به ${(ratio * 100).toFixed(0)}٪ آستانهٔ شوک رسید ولی شوکِ کامل نشد ⇒ بدونِ ورود.`
  } else {
    reason =
      `کندلِ نشستِ لندن شوک نیست: رنج ${(rng / GOLD_PIP).toFixed(1)} pip = ${(ratio * 100).toFixed(0)}٪ ` +
      `آستانهٔ ${cfg.theta}×ATR(${cfg.atrWin}) ⇒ بدونِ ورود.`
  }

  return {
    active, approaching, direction,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching ? 'کندلِ لندن نزدیکِ آستانهٔ شوک بود اما کامل نشد' : undefined,
    indicators,
  }
}

export function decideS798(
  cfg: S798Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS798(candles, cfg)
  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s798_${cfg.tfFa.toLowerCase()}`,
  }
  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const meta: DecideMeta = {
    code: 'S798',
    name: `ادامهٔ شوکِ نشستِ لندن (${cfg.tfFa})`,
    kind: 'session' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ متقارنِ عینِ بک‌تست: SL=TP=${slPipShow} pip (${cfg.kSl}×ATR(${cfg.atrWin}) کندلِ i−1، EMA). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندلِ H8 (۴ روز) نگه‌دار. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false). ⚠️ هیچ BE/trailing آزموده نشده. ` +
      `⚠️ هم‌کندل با S965 (۶۳٪ رویدادها، هم‌جهت) ⇒ یک پوزیشن، حجم را دوبرابر نکنید.`,
    filters: [
      `فقط کندلِ H8ِ شروع‌شده در ${String(cfg.hourUtc).padStart(2, '0')}:00 UTC (نشستِ لندن)`,
      `شوکِ دامنه: high−low ≥ ${cfg.theta}×ATR(${cfg.atrWin})[i−1] (EMA علّی)`,
      'جهت = follow بدنه · بدونِ شرطِ ρ',
      `SL=TP=${cfg.kSl}×ATR · max_hold ${cfg.maxHold} · ~۵ معامله در سال`,
    ],
  }
  return rawToDecision(raw, meta, cfg.id, a.price, reg, capital, riskPct)
}
