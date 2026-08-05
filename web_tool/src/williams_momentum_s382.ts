// ============================================================================
// williams_momentum_s382.ts — لایهٔ S382 «مومنتومِ Williams %R» — ✅ ACCEPTED
// ----------------------------------------------------------------------------
// ⭐ نخستین لایهٔ تاریخِ پروژه که **پیش از آزمون** توانِ آماریِ کافی داشت،
//    و تنها لایه‌ای که با **صفر فیلتر** هر ۱۱ دروازهٔ RQS2 را پاس کرد.
//
// منطق (ضدِ شهود — اندازه‌گیری‌شده، نه استنباط‌شده):
//   `Williams %R(14)` گذر به **بالای −۱۳` ⇒ قیمت در ۱۳٪ بالاییِ دامنهٔ ۱۴-کندلی
//   است، یعنی ناحیهٔ **اشباعِ خرید** — و ما همان‌جا **خرید** می‌کنیم.
//   این خلافِ خواندنِ کلاسیک است (اشباعِ خرید ⇒ فروش)، پس لایه **مومنتومی**
//   است نه بازگشتی: «خریدنِ قدرت». کشفش فقط چون جاروب هر دو جهت را آزمود
//   ممکن شد؛ با پیش‌داوریِ سبکِ کلاسیک هرگز دیده نمی‌شد.
//
// ⚠️ «گذر» است نه «حالت»: شرطِ ورود `w[i-1] <= −13 && w[i] > −13`.
//    شمردنِ کندل‌هایی که شرط در آن‌ها برقرار است، کندل می‌شمارد نه فرصت؛
//    یک گردشِ ۲۰-کندلی بالای آستانه **یک** فرصت است نه بیست. این تمایز
//    اندازه‌گیری شد و نرخ را ۵ تا ۲۰ برابر متورم می‌کرد.
//
// هندسه (خودکالیبره از ATR همان کارت — ضدِ اشتباهِ #۶ و #۷):
//   SL = ۱.۵ × ATR(100) → روی XAUUSD-H4 = **۱۲۲.۸۵۴ pip**
//   TP = ۱.۵ × SL       → **۱۸۴.۲۸۱ pip**  (TP > SL ⇒ ضدِ اشتباهِ #۸)
//   آستانهٔ Williams = **−۱۳** (غیررند؛ نه −۲۰ کلاسیک) — ضدِ اشتباهِ #۷
//
// اعدادِ اندازه‌گیری‌شده (XAUUSD-H4، بازهٔ ۱۵.۵۳ سال، اسپرد ۳.۳ pip):
//   RQS2 = **۸۳.۵** · هر ۱۱ دروازه ✅ · rank_tier = A
//   n = ۸۶۹ معامله (۵۵.۹ در سال) · WR = ۴۸.۹۱٪ · سربه‌سرِ هزینه‌دار = ۴۱.۰۷٪
//   lift = **+۷.۸۳** · PF = **۱.۴۶۷** · سودِ خالص = **$۵۴٬۰۹۸.۸**
//   maxDD = ۵.۶٪ · بیشینه رشتهٔ باخت = ۱۲ (مجاز ۱۶) · ضریبِ بازیافت = ۱۴.۸۳
//   انتظار = ۲۷.۳۶ pip (در ۲× هزینه: ۲۴.۰۶ pip ⇒ حاشیهٔ ایمنیِ هزینه)
//   میانگینِ مدتِ اشغال = ۸.۵ کندل · بیشینه همزمانی = ۱ (قیدِ تک‌معامله)
//
// مدلِ صفر — خطرناک‌ترین آزمون (سه مرجعِ مستقل و کورِ نسبت‌به‌هم):
//   سربه‌سرِ هندسی ۴۱.۰۷ · خریدارِ کور ۴۰.۵۴ · میانگینِ ۲۰۰۰ جایگشت ۴۰.۹۸
//   ⇒ هر سه روی ~۴۱٪ همگرا شدند. لایه ۴۸.۹۱٪.
//   شانسِ محض در ۲۰۰۰ قرعه **هرگز** به ۴۸.۹۱ نرسید (بهترینش ۴۴.۵۹).
//   z = ۴.۷۵۴ در برابرِ کرانِ شانسِ ۴.۰۶۷ ⇒ حاشیهٔ +۰.۶۸۷ · p_perm = 1e−6
//
// ⚠️ بازداوریِ S395 زیرِ کرانِ سخت‌گیرانهٔ نو (M_eff = ۲۷۸٬۴۴۷ ⇒ سد = ۴.۶۰۸۶):
//    z = ۵.۰۲۳۶ > ۴.۶۰۸۶ ⇒ **هنوز پاس، با حاشیهٔ +۰.۴۱۵۰**. اتصال معتبر است.
//    سند: results/S395_AUDIT_S382_UNDER_NEW_BOUND.md
//
// خارج‌نمونه (۳۰٪ پایانیِ دست‌نخورده): n=۳۶۴ · WR=۴۹.۷۳٪ · PF=۱.۴۸۱
//   ⇒ بهتر از درون‌نمونه ⇒ بی‌نشانهٔ بیش‌برازش.
// چهار ربعِ تقویمی: هر ۴ ربع سودِ مثبت و اشغال‌شده (cal_positive=4/4).
//
// یافتهٔ رانشِ ضدِّ رژیم (ثبت‌شده): ۲۴۰ معاملهٔ ضدِ روند WR=۵۰.۰۰٪ و انتظارِ
//   ۳۰.۷۱ pip — **بهتر** از ۵۵۸ معاملهٔ هم‌جهت (۴۸.۲۱٪ / ۲۵.۲۱ pip)
//   ⇒ ایرادِ «این فقط بتای طلاست» عدداً ابطال شد.
//
// همپوشانی: با S389 (نامزدِ سوخته) ژاکاردِ زمانی ۰.۰۳۰۱ ⇒ عملاً مستقل.
//   با لایه‌های هم‌کارت (S374/S340/S332) قاعده‌ای مشترک ندارد (اندیکاتورِ پایه
//   متفاوت و «گذر»محور است، نه ساختار/کانال).
//
// منبعِ حقیقت (پورتِ verbatim): strategies/s382_williamsr_momentum.py
// سند کامل: results/S382_WilliamsR_Xauusd_H4_rqs2-83.md
//
// ماژولار/ROS2-مانند: فایلِ کاملاً مستقل. افزودنش فقط یک ورودی در
//   CARD_LAYERS['XAUUSD-H4'] می‌خواهد و هیچ لایهٔ دیگری را دست نمی‌زند.
// ============================================================================

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

// ---------------------------------------------------------------------------
export interface S382Config {
  id: string            // XAUUSD-H4
  tfFa: string
  willrP: number        // ۱۴
  willrThr: number      // −۱۳ (غیررند)
  atrP: number          // ۱۰۰
  slK: number           // ۱.۵ × ATR
  rr: number            // ۱.۵ ⇒ TP > SL
  slPip: number         // ۱۲۲.۸۵۴ (اندازه‌گیری‌شده روی ۱۵.۵۳ سال)
  tpPip: number         // ۱۸۴.۲۸۱
  maxHold: number       // سقفِ نگه‌داری (کندل)
  rqs2: number          // ۸۳.۵
  /** آستانهٔ «نزدیک‌شدن»: %R به آستانه نزدیک شده ولی هنوز عبور نکرده. */
  approachBand: number  // ۸.۰ واحد
}

export const S382_CFG: Record<string, S382Config> = {
  'XAUUSD-H4': {
    id: 'XAUUSD-H4', tfFa: 'H4',
    willrP: 14, willrThr: -13.0, atrP: 100,
    slK: 1.5, rr: 1.5,
    slPip: 122.854, tpPip: 184.281,
    maxHold: 30, rqs2: 83.5,
    approachBand: 8.0,
  },
}

// ---------------------------------------------------------------------------
// اندیکاتورها — پورتِ verbatim از s382_williamsr_momentum.py
// ---------------------------------------------------------------------------

/** Williams %R(p) = −100 × (HH − close) / (HH − LL) روی پنجرهٔ p کندلی. */
export function williamsR(candles: Candle[], p: number): number[] {
  const n = candles.length
  const out = new Array<number>(n).fill(NaN)
  for (let i = p - 1; i < n; i++) {
    let hh = -Infinity
    let ll = Infinity
    for (let j = i - p + 1; j <= i; j++) {
      if (candles[j].high > hh) hh = candles[j].high
      if (candles[j].low < ll) ll = candles[j].low
    }
    const rng = hh - ll
    out[i] = rng === 0 ? NaN : -100.0 * (hh - candles[i].close) / rng
  }
  return out
}

/** ATR ویلدر (ewm alpha=1/p) — همان مسیرِ پایتون: `tr.ewm(alpha=1/p)`. */
export function atrWilder(candles: Candle[], p: number): number[] {
  const n = candles.length
  const out = new Array<number>(n).fill(NaN)
  if (n === 0) return out
  const alpha = 1.0 / p
  let acc = NaN
  for (let i = 0; i < n; i++) {
    const h = candles[i].high
    const l = candles[i].low
    let tr = h - l
    if (i > 0) {
      const pc = candles[i - 1].close
      tr = Math.max(tr, Math.abs(h - pc), Math.abs(l - pc))
    }
    acc = i === 0 ? tr : acc + alpha * (tr - acc)
    out[i] = acc
  }
  return out
}

// ---------------------------------------------------------------------------
// computeS382 — سیگنال روی آخرین کندلِ بستهٔ i = n−1 (ورود در کندلِ بعد)
// ---------------------------------------------------------------------------
export function computeS382(candles: Candle[], cfg: S382Config): RawSignal {
  const n = candles.length

  // هندسهٔ پیش‌فرض = اعدادِ قفل‌شدهٔ بک‌تست؛ در ادامه با ATR زندهٔ کارت
  // بازکالیبره می‌شود (قانونِ «شاید همه چیز شناور است»).
  let slDist = cfg.slPip * GOLD_PIP
  let tpDist = cfg.tpPip * GOLD_PIP

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]

  const need = Math.max(cfg.willrP, cfg.atrP) + 2
  if (n < need) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: `دادهٔ کافی برای Williams %R(${cfg.willrP}) و ATR(${cfg.atrP}) موجود نیست.`,
      indicators: emptyInd,
    }
  }

  const w = williamsR(candles, cfg.willrP)
  const a = atrWilder(candles, cfg.atrP)

  const i = n - 1          // آخرین کندلِ بسته‌شده
  const wNow = w[i]
  const wPrev = w[i - 1]

  // --- هندسهٔ شناور: SL = slK × ATR(atrP) زندهٔ همین کارت -------------------
  // بک‌تست از میانهٔ ATR کلِ بازه استفاده کرد (۱۲۲.۸۵۴ pip). در زمانِ واقعی،
  // ATR جاری استفاده می‌شود تا هندسه با نوسانِ فعلی متناسب باشد — ولی با
  // بندِ محافظه‌کارانهٔ [۰.۶۰×, ۱.۶۰×] عددِ بک‌تست تا هرگز از هندسهٔ
  // آزموده‌شده بیش از حد دور نشود (وگرنه نتیجهٔ rqs2 دیگر معتبر نیست).
  if (isFinite(a[i]) && a[i] > 0) {
    const live = (cfg.slK * a[i]) / GOLD_PIP        // pip
    const lo = cfg.slPip * 0.60
    const hi = cfg.slPip * 1.60
    const slPipUsed = Math.min(hi, Math.max(lo, live))
    slDist = slPipUsed * GOLD_PIP
    tpDist = slPipUsed * cfg.rr * GOLD_PIP
  }

  const haveW = isFinite(wNow) && isFinite(wPrev)

  // --- ماشهٔ اصلی: «گذر» به بالای آستانه (رویداد، نه حالت) ------------------
  const crossedUp = haveW && wPrev <= cfg.willrThr && wNow > cfg.willrThr

  // --- نزدیک‌شدن: زیرِ آستانه ولی داخلِ باندِ نزدیکی و در حالِ صعود --------
  const dist = haveW ? cfg.willrThr - wNow : NaN     // >0 یعنی هنوز زیرِ آستانه
  const rising = haveW && wNow > wPrev
  const approaching = !crossedUp && haveW &&
    wNow <= cfg.willrThr && dist <= cfg.approachBand && rising

  const slPipShow = Math.round((slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((tpDist / GOLD_PIP) * 10) / 10

  const indicators: RouterDecision['indicators'] = [
    {
      name: `Williams %R(${cfg.willrP}) — کندلِ فعلی`,
      value: haveW ? wNow.toFixed(2) : '—',
      status: crossedUp ? 'ok' : (approaching ? 'neutral' : 'neutral'),
    },
    {
      name: `Williams %R(${cfg.willrP}) — کندلِ قبل`,
      value: haveW ? wPrev.toFixed(2) : '—',
      status: 'neutral',
    },
    {
      name: `گذر به بالای آستانهٔ ${cfg.willrThr}`,
      value: crossedUp
        ? 'رخ داد ✔'
        : (haveW
          ? (wNow > cfg.willrThr ? 'قبلاً عبور کرده (فرصتِ همین گذر مصرف شد) ✘' : `فاصله ${dist.toFixed(2)} واحد ✘`)
          : '—'),
      status: crossedUp ? 'ok' : 'bad',
    },
    {
      name: `ATR(${cfg.atrP}) — هندسهٔ شناور`,
      value: isFinite(a[i]) ? `${(a[i] / GOLD_PIP).toFixed(1)} pip` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (این کارت)',
      value: `${slPipShow} / ${tpPipShow} pip (نسبت ${cfg.rr})`,
      status: 'ok',
    },
  ]

  let reason: string
  if (crossedUp) {
    reason =
      `Williams %R(${cfg.willrP}) از ${wPrev.toFixed(2)} به ${wNow.toFixed(2)} رفت و ` +
      `آستانهٔ ${cfg.willrThr} را به بالا **قطع کرد** ⇒ قیمت واردِ ۱۳٪ بالاییِ دامنهٔ ` +
      `${cfg.willrP}-کندلی شد. این لایه **مومنتومی** است: قدرت را می‌خریم، نه اینکه ` +
      `اشباعِ خرید را بفروشیم. (اندازه‌گیری‌شده روی ۸۶۹ معامله و ۱۵.۵۳ سال؛ ` +
      `هر ۱۱ دروازهٔ RQS2 پاس، z=۴.۷۵ در برابرِ کرانِ شانسِ ۴.۰۷.)`
  } else if (approaching) {
    reason =
      `Williams %R(${cfg.willrP}) روی ${wNow.toFixed(2)} است و در حالِ صعود ` +
      `(از ${wPrev.toFixed(2)}) — فقط ${dist.toFixed(2)} واحد تا آستانهٔ ${cfg.willrThr}. ` +
      `اگر کندلِ بعد آستانه را **به بالا قطع کند**، ورودِ خرید صادر می‌شود.`
  } else if (!haveW) {
    reason = 'Williams %R قابلِ محاسبه نیست (دامنهٔ پنجره صفر یا دادهٔ ناکافی).'
  } else if (wNow > cfg.willrThr) {
    reason =
      `Williams %R روی ${wNow.toFixed(2)} است، یعنی **پیش از این** از آستانهٔ ` +
      `${cfg.willrThr} عبور کرده. این لایه فقط لحظهٔ **گذر** را می‌گیرد نه ماندن در ناحیه؛ ` +
      `یک گردشِ بالای آستانه **یک** فرصت است نه چند فرصت. منتظرِ بازگشت به زیرِ آستانه ` +
      `و گذرِ تازه می‌مانیم.`
  } else {
    reason =
      `Williams %R روی ${wNow.toFixed(2)} است و ${dist.toFixed(2)} واحد زیرِ آستانهٔ ` +
      `${cfg.willrThr} — قیمت هنوز به ۱۳٪ بالاییِ دامنهٔ ${cfg.willrP}-کندلی نرسیده. ` +
      `شرطِ ورود برقرار نیست.`
  }

  return {
    active: crossedUp, approaching, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ قطعِ آستانهٔ ${cfg.willrThr} به بالا توسطِ Williams %R(${cfg.willrP})`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS382(
  cfg: S382Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS382(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: 'trend_up', efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: 'bull', bucket: `s382_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10

  const meta: DecideMeta = {
    code: 'S382',
    name: `مومنتومِ Williams %R — خریدِ قدرت (${cfg.tfFa})`,
    kind: 'williams_momentum' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ شناورِ ATR-محور: SL=${slPipShow} pip · TP=${tpPipShow} pip (نسبت ${cfg.rr}). ` +
      `تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندل نگه‌دار. ` +
      `⚠️ این لایه با **قیدِ تک‌معامله** آزموده شد (بیشینه همزمانی = ۱): تا این معامله ` +
      `بسته نشده، گذرِ بعدی نباید معاملهٔ جدید باز کند — وگرنه نتیجهٔ اندازه‌گیری‌شده ` +
      `دیگر معتبر نیست. اگر Williams %R به زیرِ ${cfg.willrThr} برگشت و مومنتوم از دست رفت، ` +
      `خروجِ زودهنگام را بسنج. میانگینِ مدتِ اشغالِ اندازه‌گیری‌شده ۸.۵ کندل است.`,
    filters: [
      `Williams %R(${cfg.willrP}) گذر به بالای ${cfg.willrThr} (رویداد، نه حالت)`,
      'صفر فیلترِ اضافه — بودجهٔ معامله دست‌نخورده',
      `هندسهٔ خودکالیبره: SL=${cfg.slK}×ATR(${cfg.atrP}) · TP=${cfg.rr}×SL`,
      'قیدِ تک‌معامله (بیشینه همزمانی = ۱)',
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
