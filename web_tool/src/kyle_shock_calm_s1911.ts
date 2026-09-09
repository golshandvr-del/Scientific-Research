// ---------------------------------------------------------------------------
// S1911 — «شوکِ مطلع در آرامش» (Kyle Shock × Calm-σ Regime) · XAUUSD-H8
//
// حکمِ نهایی (سند: results/S1911_KyleShockCalmRegime_Xauusd_H8_rqs2_93.9_ACCEPT.md):
//   RQS2 = **93.9** · هر ۱۱ دروازهٔ H0..H10 سبز · notes خالی
//   پیش‌ثبت پیش از هر عدد: results/S1911_PREREG_kyle_shock_calm_regime.md
//   چک‌پوینتِ داور: results/_s1911_ckpt/judge_H8.json
//
// فیزیکِ لایه (کینز × کایل × اِنگل):
//   شوکِ کایل (S965) می‌گوید «کندلِ درشتِ ماروبوزو-گونه = جریانِ مطلع». اما یک
//   کندلِ درشت در **طوفان** می‌تواند فقط نوسانِ رژیمی باشد، نه خبر. تفکیک این
//   دو نیازِ یک سنجهٔ **بیرونی** دارد: سطحِ σ خودِ بازار. اگر شوکِ درشت در
//   دوره‌ای رخ دهد که σ زیرِ میانهٔ تاریخیِ خودش است (بازارِ آرام)، آن حرکت
//   نمی‌تواند «نوسانِ معمولِ رژیم» باشد ⇒ احتمالِ خبرِ واقعی بالا می‌رود.
//   «خبرِ واقعی در سکوت شنیده می‌شود.»
//
// ⚠️⚠️ قانونِ MTF — تعمیم ممنوع. **فقط XAUUSD-H8 وصل می‌شود.**
//   H6 نیز داوری و منتشر شد و **REJECT** است (سه دروازهٔ H3/H7/H8 قفل کردند —
//   `results/_s1911_ckpt/judge_H6.json::failed_gates = ["H3","H7","H8"]`).
//   پس این لایه تک‌کارتی است؛ هیچ کارتِ دومی حق ندارد آن را نشان دهد.
//
// ⚠️⚠️⚠️ قیدِ «شاهدِ کاذب» — این مهم‌ترین یادداشتِ این فایل است.
//   S1911 روی H8 **زیرمجموعهٔ کاملِ S965** است که هم‌اکنون روی همین کارت زنده
//   است. اندازه‌گیری شد (نه حدس)، ابزار: `tools/s1911_false_witness_audit.py`،
//   خروجی: `results/_s1911_ckpt/false_witness_h8.json` — روی همان کندل‌های H8،
//   هم‌ترازِ زمانی، با بازتولیدِ هر لایه از **مرجعِ پایتونیِ خودش**:
//     • S1911 vs S965: n=82 در برابر 144 · اشتراک=82 ⇒ share_of_S1911=**۱۰۰٪**
//       · jaccard=0.569 · جهتِ مخالف=**صفر**
//     • S1911 vs S966: jaccard=0.426 ⇒ مستقل
//     • S1911 vs S950: jaccard=0.144 ⇒ مستقل
//   اعتبارِ ابزار با کنترل تأیید شد: عددِ منتشرشدهٔ «S966 ⊂ S965» را عیناً
//   بازتولید کرد (share=۱۰۰٪ · jaccard=0.50).
//
//   چرا با وجودِ ۱۰۰٪ زیرمجموعه بودن، وصل کردن **مجاز** است؟ چون ریپو دو
//   سابقهٔ متفاوت دارد و این‌ها یک چیز نیستند:
//     ① S404/S408 (`strategy_registry.ts:794-797`): jaccard=۶۹.۳٪ **به‌همراهِ**
//        هم‌اندازگی ⇒ «یک رویدادِ واحد با دو اسم» ⇒ حکم: «یکی، نه هر دو» (حذف).
//     ② S966 زیرِ S965: share=۱۰۰٪ ولی jaccard=۰.۵۰ ⇒ زیرمجموعهٔ **کوچکِ** یک
//        لایهٔ بزرگ‌تر ⇒ ریپو **هر دو** را وصل کرد، با قید.
//   S1911 دقیقاً حالتِ ② است (زیرمجموعه، ولی نیمهٔ اندازه). پس «شاهدِ کاذب»
//   نیست؛ یک **فیلترِ کیفیت** روی رویدادهای S965 است. حکمِ ممیزی:
//   `CLEAR-WITH-CONSTRAINTS`. سه قیدِ الزامی، همان‌ها که برای S966 اعمال شد:
//     (الف) در آرایهٔ کارتِ H8 **پایین‌ترِ** S965 قرار می‌گیرد تا در تلاقی،
//           تصمیمِ اصلیِ کارت از S965 بیاید و S1911 در otherLayers بنشیند.
//     (ب) ارزشِ اعلامیِ لایه در UI صریحاً «کیفیت/انتخابِ زیرمجموعه» است، نه
//           «رویدادِ نو» — کاربر نباید آن را شاهدِ مستقل بشمارد. متنِ reason و
//           یک شاخصِ اختصاصی این را می‌گویند.
//     (ج) در تلاقی، سایز مشترک است؛ دو کادر ≠ دو ریسکِ جدا.
//
// ⚠️ پورتِ مو-به-موی strategies/s1911_kyle_shock_calm.py — دام‌های پورت:
//   ① تکهٔ شوک **عیناً** از S965 می‌آید: ATR = میانگینِ سادهٔ ۲۱تاییِ TR با
//      تقسیمِ همیشگی بر ۲۱ (جمعِ جزئی در ۲۰ عضوِ اول) سپس شیفتِ ۱. برای حذفِ
//      هر امکانِ واگرایی، این فایل `s965Features` را **import** می‌کند و
//      دوباره پیاده‌سازی نمی‌کند (یک منبعِ حقیقت).
//   ② گیتِ آرامش عیناً از S605/S606 می‌آید: σ با RiskMetrics λ=0.94 و
//      reg[t] = σ[t] / median(σ[t−233..t−1]). این‌ها قبلاً در
//      `engle_dual_gate_s607.ts` پورت و تأیید شده‌اند (`ewmaZ`, `regimeRatio`)
//      پس همان‌ها import می‌شوند — نه نسخهٔ دوم.
//   ③ گیت روی **σ کندلِ خودِ رویداد** بسته می‌شود (reg[i] ≤ 1)، ولی میانه از
//      پنجرهٔ **بستهٔ** t−233..t−1 می‌آید ⇒ علّی، بدونِ look-ahead.
//   ④ هندسه از atr_prev (ATR کندلِ i−1) ساخته می‌شود: SL=1.272× · TP=2.058×
//      · maxHold=16 — ارثی از S965 و دست‌نخورده.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'
import { s965Features, type S965Config } from './kyle_intrabar_s965'
import { ewmaZ, regimeRatio } from './engle_dual_gate_s607'

const GOLD_PIP = 0.1

export interface S1911Config {
  id: string           // شناسهٔ کارت (فقط XAUUSD-H8)
  tfFa: string         // برچسبِ فارسیِ تایم‌فریم
  theta: number        // آستانهٔ شوک: high−low ≥ theta×ATR21[i−1] (قفل: 2.618)
  rhoMin: number       // کفِ ماندگاری ρ (قفل: 0.618)
  atrWin: number       // پنجرهٔ ATR (قفل: 21)
  lam: number          // λِ RiskMetrics برای σ (قفل: 0.94)
  calmW: number        // پنجرهٔ میانهٔ σ (قفل: 233)
  regMax: number       // سقفِ نسبتِ رژیم برای «آرام» (قفل: 1.0)
  kSl: number          // SL = kSl × ATR21[i−1] (قفل: 1.272)
  kTp: number          // TP = kTp × ATR21[i−1] (قفل: 2.058 ⇒ TP>SL ✓)
  maxHold: number      // بیشینهٔ نگه‌داری بر حسبِ کندلِ H8 (قفل: 16)
  approachFrac: number // «نزدیک‌شدن» (فقط UI)
}

export const S1911_CFG: Record<string, S1911Config> = {
  // تنها کارتِ ACCEPT. هیچ کارتِ دیگری اضافه نشود (H6 = REJECT).
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    theta: 2.618, rhoMin: 0.618, atrWin: 21,
    lam: 0.94, calmW: 233, regMax: 1.0,
    kSl: 1.272, kTp: 2.058, maxHold: 16,
    approachFrac: 0.85,
  },
}

// ---------------------------------------------------------------------------
// computeS1911 — سیگنال روی آخرین کندلِ بستهٔ i = n−1 (ورود در openِ کندلِ بعد)
// ---------------------------------------------------------------------------
export function computeS1911(candles: Candle[], cfg: S1911Config): RawSignal {
  const n = candles.length

  // کفِ دادهٔ واقعی را گیتِ آرامش تعیین می‌کند، نه ATR: میانهٔ σ به پنجرهٔ
  // بستهٔ ۲۳۳تایی نیاز دارد و خودِ σ پس از ۵۰ کندل شروع می‌شود (ewmaZ).
  // پس دستِ‌کم 233 + 50 + حاشیه لازم است. اگر کمتر باشد، لایه صادقانه
  // «دادهٔ ناکافی» می‌دهد و هرگز سیگنالِ جعلی نمی‌سازد.
  const minBars = cfg.calmW + 52

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  if (n < minBars + 2) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 138 * GOLD_PIP, tpDist: 223 * GOLD_PIP, maxHoldBars: cfg.maxHold,
      reason:
        `دادهٔ کافی نیست: گیتِ رژیمِ σ این لایه به میانهٔ پنجرهٔ بستهٔ ${cfg.calmW} کندلی ` +
        `نیاز دارد و خودِ σ پس از ۵۰ کندل آغاز می‌شود ⇒ دستِ‌کم ${minBars} کندلِ بستهٔ ` +
        `${cfg.tfFa} (موجود: ${n}). تا آن زمان این لایه سکوت می‌کند.`,
      indicators: emptyInd,
    }
  }

  // ── تکهٔ ①: شوکِ کایل — عیناً از ماژولِ S965 (یک منبعِ حقیقت) ──────────────
  const f = s965Features(candles, cfg as unknown as S965Config)
  const i = n - 1

  const atrPrev = f.atrPrev[i]
  const rng = f.rng[i]
  const rho = f.rho[i]
  const sgn = f.bodySgn[i]
  const valid = atrPrev > 1e-12 && rng > 0

  // ── تکهٔ ②: گیتِ آرامشِ σ — عیناً از پورتِ تأییدشدهٔ S605/S606 ─────────────
  const close = candles.map(c => c.close)
  const { sigma } = ewmaZ(close, cfg.lam)
  const reg = regimeRatio(sigma, cfg.calmW)
  const regI = reg[i]
  const regOk = Number.isFinite(regI) && regI <= cfg.regMax

  // هندسهٔ شناور = عینِ بک‌تست: از atr_prev (دامِ ④).
  const slPip = Math.max((cfg.kSl * atrPrev) / GOLD_PIP, 1e-9)
  const tpPip = Math.max((cfg.kTp * atrPrev) / GOLD_PIP, 1e-9)
  const slDist = slPip * GOLD_PIP
  const tpDist = tpPip * GOLD_PIP

  const thr = cfg.theta * atrPrev
  const isShock = valid && rng >= thr
  const isPermanent = rho >= cfg.rhoMin
  const shockPart = isShock && isPermanent && sgn !== 0
  const active = shockPart && regOk
  const direction: 'LONG' | 'SHORT' = active && sgn < 0 ? 'SHORT' : 'LONG'

  // «نزدیک‌شدن»: رنج در ۸۵–۱۰۰٪ آستانه، بدنه ماندگار، **و رژیم آرام**.
  // اگر رژیم طوفانی باشد هیچ approaching اعلام نمی‌شود، چون حتی شوکِ کامل هم
  // در طوفان ورود نمی‌دهد ⇒ نشانهٔ گمراه‌کننده نسازیم.
  const approaching = valid && !active && !isShock && regOk &&
    rng >= cfg.approachFrac * thr && isPermanent && sgn !== 0

  const ratio = thr > 0 ? rng / thr : 0
  const regTxt = Number.isFinite(regI) ? regI.toFixed(3) : '—'

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
      name: `گیتِ آرامش: σ ÷ میانهٔ σ(${cfg.calmW} کندلِ بسته) — سقفِ ${cfg.regMax}`,
      value: Number.isFinite(regI)
        ? `${regTxt} ⇒ ${regOk ? 'بازارِ آرام ✓' : 'بازارِ طوفانی ✗'}`
        : 'σ هنوز گرم نشده',
      status: regOk ? 'ok' : 'bad',
    },
    {
      name: 'جهتِ بدنهٔ کندلِ شوک (اثرِ دائمی ⇒ ادامه)',
      value: sgn > 0 ? 'صعودی (LONG)' : (sgn < 0 ? 'نزولی (SHORT)' : 'بدونِ بدنه (doji)'),
      status: sgn !== 0 ? 'neutral' : 'bad',
    },
    {
      name: 'حد ضرر / هدف (این کارت)',
      value: `${slPip.toFixed(1)} / ${tpPip.toFixed(1)} pip (نسبت ${(cfg.kTp / cfg.kSl).toFixed(3)} ⇒ TP>SL)`,
      status: 'ok',
    },
    // قیدِ (ب) ممیزیِ شاهدِ کاذب — این شاخص هرگز حذف نشود.
    {
      name: '⚠️ نسبت با لایهٔ S965 (اندازه‌گیری‌شده)',
      value: 'زیرمجموعهٔ کامل: ۸۲ از ۸۲ رویداد داخلِ S965 · jaccard ۰.۵۷ — ' +
             'شاهدِ مستقل نیست، فیلترِ کیفیت است',
      status: 'neutral',
    },
  ]

  let reason: string
  if (active) {
    const side = direction === 'LONG' ? 'خرید' : 'فروش'
    const bodyDir = direction === 'LONG' ? 'صعودی' : 'نزولی'
    reason =
      `کندلِ ${cfg.tfFa} بسته‌شده یک **شوکِ مطلع در بازارِ آرام** است: رنج ` +
      `${(rng / GOLD_PIP).toFixed(1)} pip ≥ ${cfg.theta}×ATR(${cfg.atrWin})=${(thr / GOLD_PIP).toFixed(1)} pip ` +
      `(${(ratio * 100).toFixed(0)}٪ آستانه) · ماندگاری ρ=${rho.toFixed(3)} ≥ ${cfg.rhoMin} · بدنهٔ ${bodyDir} ` +
      `**و** گیتِ آرامش باز است (σ÷میانه = ${regTxt} ≤ ${cfg.regMax}) ⇒ سیگنالِ ${side}. ` +
      `فیزیکِ اندازه‌گیری‌شده: شوکِ درشت در **آرامش** نمی‌تواند نوسانِ معمولِ رژیم باشد، ` +
      `پس احتمالِ خبرِ واقعی بالا می‌رود — «خبرِ واقعی در سکوت شنیده می‌شود» (کینز × کایل × اِنگل). ` +
      `RQS2=۹۳.۹ · هر ۱۱ دروازه سبز · پیش‌ثبت پیش از عدد. ` +
      `ورود روی openِ کندلِ بعد؛ SL=${slPip.toFixed(1)} / TP=${tpPip.toFixed(1)} pip ` +
      `(${cfg.kSl}× و ${cfg.kTp}×ATR(${cfg.atrWin}) علّی، عینِ بک‌تست). ` +
      `⚠️ این رویداد **زیرمجموعهٔ S965** است (۱۰۰٪ اندازه‌گیری‌شده): اگر کارت هم‌زمان S965 را ` +
      `نشان می‌دهد، دو شاهدِ مستقل نیست — یک رویداد است با یک فیلترِ کیفیتِ اضافه؛ سایز مشترک بماند.`
  } else if (shockPart && !regOk) {
    reason =
      `شوکِ ماندگار رخ داد (رنج ${(rng / GOLD_PIP).toFixed(1)} pip ≥ ${(thr / GOLD_PIP).toFixed(1)} pip · ` +
      `ρ=${rho.toFixed(3)}) ولی **گیتِ آرامش بسته است**: σ÷میانه = ${regTxt} > ${cfg.regMax} ⇒ بازار در ` +
      `رژیمِ طوفانی است. در طوفان، کندلِ درشت می‌تواند صرفاً نوسانِ رژیمی باشد نه خبر ⇒ بدونِ ورود. ` +
      `همین تفکیک است که RQS2 را از ۸۲.۲ (S965 خام) به ۹۳.۹ برد. ` +
      `(توجه: خودِ S965 ممکن است روی همین کندل ورود بدهد — این لایه فقط سکوت می‌کند.)`
  } else if (!valid) {
    reason = `ATR(${cfg.atrWin}) هنوز معتبر نیست (گرم‌شدن یا رنجِ صفر) — لایه در انتظار.`
  } else if (approaching) {
    reason =
      `رنجِ کندلِ بسته (${(rng / GOLD_PIP).toFixed(1)} pip) به ${(ratio * 100).toFixed(0)}٪ آستانهٔ شوک ` +
      `(${(thr / GOLD_PIP).toFixed(1)} pip) رسیده، بدنه هم‌اکنون ماندگار است (ρ=${rho.toFixed(3)}) و ` +
      `رژیم آرام است (${regTxt} ≤ ${cfg.regMax}). اگر کندلِ بعد شوکِ کامل با همین ماندگاری و همین ` +
      `آرامش بسازد، ورود صادر می‌شود. هنوز معامله‌ای نیست.`
  } else if (isShock && !isPermanent) {
    reason =
      `شوک رخ داد (رنج ${(rng / GOLD_PIP).toFixed(1)} pip ≥ ${(thr / GOLD_PIP).toFixed(1)} pip) ولی ماندگاری ` +
      `کم است: ρ=${rho.toFixed(3)} < ${cfg.rhoMin} — قیمت **درونِ همان کندل** بخشِ بزرگی از حرکت را پس ` +
      `گرفت (سایهٔ بلند) ⇒ امضای جریانِ **نویز**، نه مطلع ⇒ بدونِ ورود.`
  } else {
    reason =
      `کندلِ بستهٔ اخیر شوک نیست: رنج ${(rng / GOLD_PIP).toFixed(1)} pip یعنی ${(ratio * 100).toFixed(0)}٪ ` +
      `آستانهٔ ${cfg.theta}×ATR(${cfg.atrWin})=${(thr / GOLD_PIP).toFixed(1)} pip. ` +
      `این لایه از S965 هم کم‌بسامدتر است (۸۲ رویداد در ۱۵.۶ سال، ~۵ در سال) چون علاوه بر شوک، ` +
      `آرامشِ رژیم را هم می‌خواهد — بیشترِ کندل‌ها هیچ‌اند و همین صداقتِ لایه است. ` +
      `وضعیتِ کنونیِ رژیم: σ÷میانه = ${regTxt} (${regOk ? 'آرام' : 'طوفانی'}).`
  }

  return {
    active, approaching, direction,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ شوکِ کامل (رنج ≥ ${cfg.theta}×ATR(${cfg.atrWin})) با ماندگاری ρ ≥ ${cfg.rhoMin} و رژیمِ آرام روی کندلِ بعد`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS1911(
  cfg: S1911Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS1911(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s1911_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10

  const meta: DecideMeta = {
    code: 'S1911',
    name: `شوکِ مطلع در آرامش (${cfg.tfFa})`,
    kind: 'kyle_shock_calm' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ شناورِ عینِ بک‌تست: SL=${slPipShow} / TP=${tpPipShow} pip ` +
      `(${cfg.kSl}× و ${cfg.kTp}×ATR(${cfg.atrWin}) **کندلِ i−1**؛ میانهٔ تاریخی ≈۱۳۸/۲۲۳ pip). ` +
      `بیشینهٔ نگه‌داری ${cfg.maxHold} کندلِ ${cfg.tfFa}. ` +
      `⚠️ سایز: این لایه زیرمجموعهٔ **۱۰۰٪** S965 است (اندازه‌گیری‌شده، ` +
      `results/_s1911_ckpt/false_witness_h8.json). اگر هر دو کادر روشن‌اند، ` +
      `**یک** رویداد است با فیلترِ کیفیت ⇒ سایزِ مشترک بگیرید، نه دو ریسکِ جدا.`,
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
