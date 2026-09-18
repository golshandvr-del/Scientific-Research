// ---------------------------------------------------------------------------
// S955 — «جهشِ هم‌راستا در رژیمِ آرام» (S950 Jump-Aftermath × گیتِ آرامشِ σ)
//   سند: results/S955_JumpAftermathCalmRegime_Xauusd_H8H12H6_rqs2_88_ACCEPT.md
//   پیش‌ثبت (پیش از هر عدد): results/S955_PREREG_jump_aftermath_calm_regime.md
//   کدِ منجمد: strategies/s955_jump_aftermath_calm.py
//
// حکمِ موتور (RQS2 v2.6 دست‌نخورده، ۱۱ گیتِ وتو) — سه کارت، سه ACCEPT:
//   · XAUUSD-H8  : ACCEPT **87.7** · n=112 · WR 67.86٪ · lift +17.85pp · z=3.78
//                  · PF 2.06 · maxDD 2.86٪ · p_perm 7.9e-05
//   · XAUUSD-H12 : ACCEPT **89.4** · n=76  · WR 69.74٪ · lift +19.86pp · z=3.46
//                  · PF 2.31 · maxDD 2.43٪
//   · XAUUSD-H6  : ACCEPT **84.9** · n=149 · WR 65.10٪ · lift +15.15pp · z=3.67
//                  · PF 1.74 · maxDD 4.74٪
//   H4 = POWER-LIMITED (26.0) · H3…M1 = REJECT · D1/W1/MN1 = NO-CANDIDATE (n<30)
//   ⇒ طبقِ قانونِ MTF فقط همین سه کارت وصل می‌شوند و یک کارتِ چهارم هم اضافه
//     نمی‌شود؛ «تعمیمِ بدونِ شاهد» در این مخزن ممنوع است.
//
// فیزیکِ لایه — و چرا این یک گیتِ اطلاعات‌افزاست نه یک فیلترِ توان‌سوز:
//   رویدادِ پایه (S950) جهشِ قیمتی هم‌راستا با رانش است. S955 می‌گوید همان جهش
//   وقتی در **بستهٔ آرامِ** نوسان رخ دهد به‌مراتب بهتر ادامه می‌یابد. تفکیکِ
//   اندازه‌گیری‌شده روی H8: ۲۳۸ جهشِ هم‌راستا ⇒ ۱۱۸ آرام (WR ۶۷.۹٪) در برابرِ
//   ۱۲۰ طوفانی (WR ۵۴.۵٪) — ۱۳ نقطهٔ درصدی اختلاف، همان رویداد، همان براکت.
//   هر سه ابطال‌گرِ پیش‌ثبت روی هر سه کارت پاس شدند (۳/۳ در هر سه):
//     P1 lift_calm > lift_base ⇒ گیت اطلاع می‌افزاید (درسِ S1912: فیلتری که فقط
//        n را کم کند و lift را بالا نبرد، صرفاً توان را می‌سوزاند)
//     P2 بازوی طوفانی ضعیف‌تر ⇒ جهتِ اثر همان است که فرض شد
//     P3 pass-rate در ۳۰–۸۵٪ (۴۹.۶ / ۴۵.۶ / ۴۹.۸) ⇒ گیت زنده است، نه همیشه-باز
//   این **سومین تکرارِ مستقلِ** قانونِ «شوک × آرامش» در مخزن است (S606 Engle،
//   S1911 Kyle-range، S1740 strong-close) و نخستین بار روی رویدادِ **بازده‌ای**.
//
// ⚠️⚠️ دو قیدِ پرتفوی که از **اندازه‌گیریِ** شاهدِ کاذب آمده‌اند، نه از سلیقه.
//   ابزار: tools/s955_false_witness_audit.py · خروجی: results/_s955_ckpt/false_witness.json
//
//   ① **S1913 دوقلوی S955-H8 است — هرگز جدا وصل نشود.**
//      S1913 (results/S1913_JumpAftermathCalm_Xauusd_H8_rqs2_89.3_ACCEPT.md)
//      همین ترکیب را روی H8 آزموده و **هر چهار عددِ حکم عیناً یکی است**:
//      n=112 · WR=67.86 · PF=2.06 · maxDD=2.86. دو پیاده‌سازیِ مستقل، یک نتیجه.
//      این همان پروندهٔ S404/S408 در `strategy_registry.ts` است (jaccard ۶۹.۳٪ +
//      هم‌اندازگی ⇒ «یکی، نه هر دو») ولی شدیدتر: jaccard ≈ ۱.۰. اگر هر دو وصل
//      شوند سایت **دو کادر** نشان می‌دهد و اپراتور گمان می‌کند دو شاهدِ مستقل
//      دارد، در حالی که یک شاهد دو بار شمرده شده ⇒ ریسکِ دوبرابر، اطلاعِ صفر.
//      هر دو سند خودشان همین را می‌گویند (S955 §۸: «یک لایه، دو نام؛ فقط یکی
//      مستقر شود»). ⇒ S1913 از فهرستِ قابلِ استقرار **حذفِ دائمی** است.
//
//   ② **روی H8 این لایه زیرمجموعهٔ S950 است ⇒ جانشین می‌شود، افزوده نمی‌شود.**
//      اندازه‌گیری: ۱۱۸ از ۲۳۸ رویدادِ S950 ⇒ **۱۰۰٪ زیرمجموعهٔ ساختاری**،
//      همپوشانیِ پنجرهٔ نگهداری ۱۰۰٪، جهتِ مخالف **صفر**. با نصفِ اندازه ⇒
//      طبقِ پروندهٔ S966/S1911 این «فیلترِ کیفیت» است نه شاهدِ نو. اگر کنارِ
//      S950 بنشیند، روی هر سیگنالِ مشترک سایز دو برابر می‌شود بدونِ هیچ
//      اطلاعِ تازه. سندِ S955 خودش راهِ صادقانه را پیشنهاد کرده: **جانشینی**
//      — همان ۱۱۲ معامله از ۲۲۴، اما WR ۶۱.۶→۶۷.۹ · PF ۱.۵۶→۲.۰۶ ·
//      maxDD ۴.۹۲→۲.۸۶. یعنی نصفِ معاملات حذف می‌شود و همان نصفی حذف می‌شود
//      که ضرر می‌داد. ⇒ روی کارتِ H8، `s955Layer` جای `s950Layer` را می‌گیرد.
//
//   ③ روی H6 و H12 مستقل است ⇒ افزودنِ آزاد:
//      · H6  در برابرِ S919 : jaccard ۰.۲۲۰ (۴۷ هم‌کندل از ۱۵۵/۱۰۶) ⇒ مستقل
//      · H12 در برابرِ S800 : jaccard ۰.۰۷۱ (۳۴ از ۷۸/۴۳۶) ⇒ مستقل
//        نکتهٔ H12: همپوشانیِ **پنجرهٔ نگهداری** ۹۲.۳٪ است در حالی که هم‌کندل
//        فقط ۴۳.۶٪ — این نشانهٔ «رویدادِ مشترک» نیست، نشانهٔ آن است که S800 با
//        ۴۳۶ معامله تقریباً همیشه در معامله است. پس قیدِ **سایز** می‌گذارد،
//        نه قیدِ **ورود**؛ و در manageNote به اپراتور گفته می‌شود.
//
// ⚠️ پورتِ مو-به-مو — و عمداً **هیچ فرمولی بازنویسی نشده**:
//    · رویدادِ جهش + رانش + هندسهٔ ATR ⇒ عیناً از `s950Features` (همین سایت،
//      پورت و تأییدشده). سه دامِ پورتِ S950 (ATR = SMA سادهٔ ۸۹ سپس شیفت ۱،
//      رفتارِ np.convolve در warm-up، و ایندکسِ علّیِ Bipower) همان‌جا حل شده‌اند
//      و با ارث‌بری خودبه‌خود درست می‌مانند.
//    · گیتِ آرامش ⇒ عیناً `ewmaZ` + `regimeRatio` از `engle_dual_gate_s607.ts`
//      (همان دو تابعی که S1911 هم از آن‌ها تغذیه می‌شود ⇒ یک منبعِ حقیقت).
//    تنها کارِ این فایل **ترکیبِ** این دو است — دقیقاً مثل خودِ کدِ پایتون که
//    features/member_signals را از s950 و sigma_series/regime_ratio را از s605
//    فقط import می‌کند و هیچ‌چیز را بازنویسی نمی‌کند.
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import { s950Features, type S950Config } from './jump_aftermath_s950'
import { ewmaZ, regimeRatio } from './engle_dual_gate_s607'

const GOLD_PIP = 0.1

export interface S955Config {
  id: string           // شناسهٔ کارت
  tfFa: string         // برچسبِ فارسیِ تایم‌فریم
  kJump: number        // آستانهٔ جهش بر حسبِ σ_BV (قفل: 2.6)
  bvWin: number        // پنجرهٔ Bipower/رانش/ATR (قفل: 89 — فیبوناچی)
  slK: number          // SL = slK × ATR(bvWin) (قفل: 2.058)
  rr: number           // TP = rr × SL (قفل: 1.0 — متقارن)
  maxHold: number      // بیشینهٔ نگه‌داری بر حسبِ کندلِ کارت (قفل: 34)
  lam: number          // λ در σ²_t = λσ²_{t−1} + (1−λ)r²_{t−1} (قفل: 0.94 RiskMetrics)
  calmW: number        // پنجرهٔ میانهٔ σ (قفل: 233 — عینِ S1911/S605)
  regMax: number       // سقفِ نسبتِ رژیم برای «آرام» (قفل: 1.0)
  approachFrac: number // «نزدیک‌شدن» — فقط UI، هرگز ورود
  // ── اعدادِ حکم، فقط برای نمایشِ صادقانه در UI (هیچ‌کدام در تصمیم دخیل نیست)
  rqs2: number
  nTrades: number
  wr: number
  pf: number
  maxDd: number
  liftPp: number
  passRate: number     // نرخِ عبورِ گیت (P3) — نشان می‌دهد گیت زنده است
  // ── قیدِ پرتفویِ همین کارت (از ممیزیِ شاهدِ کاذب) — متنِ صریح برای اپراتور
  portfolioNote: string
}

// ⚠️ پارامترها در هر سه کارت **یکی** هستند — این تصادفی نیست: قاعده روی H8
//    پیش‌ثبت شد و H12/H6 با **همان قاعدهٔ منجمد و صفر تغییر** ACCEPT گرفتند.
//    اگر روزی کسی خواست یکی از این اعداد را per-card تیون کند، آن دیگر S955
//    نیست و حکمِ موتور شاملش نمی‌شود.
export const S955_CFG: Record<string, S955Config> = {
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    kJump: 2.6, bvWin: 89, slK: 2.058, rr: 1.0, maxHold: 34,
    lam: 0.94, calmW: 233, regMax: 1.0, approachFrac: 0.85,
    rqs2: 87.7, nTrades: 112, wr: 67.86, pf: 2.06, maxDd: 2.86,
    liftPp: 17.85, passRate: 49.6,
    portfolioNote:
      'این لایه **جانشینِ S950 روی همین کارت** است، نه شاهدِ دومِ آن: اندازه‌گیری ' +
      'نشان داد هر ۱۱۸ رویدادِ S955 داخلِ ۲۳۸ رویدادِ S950 است (۱۰۰٪ زیرمجموعه، ' +
      'جهتِ مخالف صفر). همان معاملات، منهای نصفی که در طوفانِ نوسان باز می‌شد و ' +
      'ضرر می‌داد (WR ۶۱.۶→۶۷.۹ · PF ۱.۵۶→۲.۰۶ · maxDD ۴.۹۲→۲.۸۶٪).',
  },
  'XAUUSD-H12': {
    id: 'XAUUSD-H12', tfFa: 'H12',
    kJump: 2.6, bvWin: 89, slK: 2.058, rr: 1.0, maxHold: 34,
    lam: 0.94, calmW: 233, regMax: 1.0, approachFrac: 0.85,
    rqs2: 89.4, nTrades: 76, wr: 69.74, pf: 2.31, maxDd: 2.43,
    liftPp: 19.86, passRate: 45.6,
    portfolioNote:
      'بالاترین نمرهٔ سه کارتِ این لایه (۸۹.۴) و کم‌بسامدترین (۷۶ معامله در ۱۵.۶ سال ' +
      '≈ ۵ در سال). در برابرِ S800 روی همین کارت **مستقل** است (jaccard ۰.۰۷۱). ' +
      '⚠️ اما همپوشانیِ پنجرهٔ نگهداری ۹۲.۳٪ است — نه از رویدادِ مشترک، بلکه چون ' +
      'S800 با ۴۳۶ معامله تقریباً همیشه در بازار است. پس اگر هر دو باز بودند، ' +
      'ریسکِ **هم‌زمان** روی کارت جمع می‌شود: سایزِ مشترک بگیر، نه دو سایزِ کامل.',
  },
  'XAUUSD-H6': {
    id: 'XAUUSD-H6', tfFa: 'H6',
    kJump: 2.6, bvWin: 89, slK: 2.058, rr: 1.0, maxHold: 34,
    lam: 0.94, calmW: 233, regMax: 1.0, approachFrac: 0.85,
    rqs2: 84.9, nTrades: 149, wr: 65.10, pf: 1.74, maxDd: 4.74,
    liftPp: 15.15, passRate: 49.8,
    portfolioNote:
      'پربسامدترین و در عینِ حال کم‌نمره‌ترینِ سه کارت (۸۴.۹ · maxDD ۴.۷۴٪ — ' +
      'تقریباً دو برابرِ H8/H12). در برابرِ S919 روی همین کارت **مستقل** است ' +
      '(jaccard ۰.۲۲۰ · ۴۷ هم‌کندل از ۱۵۵ · جهتِ مخالف صفر) ⇒ هم‌زیستی مجاز.',
  },
}

// ---------------------------------------------------------------------------
// computeS955 — سیگنال روی آخرین کندلِ بستهٔ i = n−1 (ورود در openِ کندلِ بعد)
//
// ترتیبِ ارزیابی عیناً کدِ پایتون است:
//   ① رویدادِ S950:  jump = |r| > kJump·σ_BV  ∧  رانشِ ۸۹ هم‌جهت
//   ② گیتِ آرامش:    reg = σ_t ÷ میانهٔ σ(۲۳۳ کندلِ بسته)  ≤ 1
//   ورود فقط اگر ① ∧ ②.
// ---------------------------------------------------------------------------
export function computeS955(candles: Candle[], cfg: S955Config): RawSignal {
  const n = candles.length

  // کفِ دادهٔ واقعی را **گیتِ آرامش** تعیین می‌کند نه رویدادِ جهش: میانهٔ σ به
  // پنجرهٔ بستهٔ ۲۳۳تایی نیاز دارد و خودِ σ پس از ۵۰ کندل آغاز می‌شود (ewmaZ)
  // ⇒ دستِ‌کم ۲۸۵ کندل. این عدد از رویدادِ S950 (۹۱ کندل) بزرگ‌تر است، پس
  // همین قید حاکم است. اگر داده کمتر بود لایه **سکوت** می‌کند و هرگز سیگنالِ
  // جعلی نمی‌سازد — همان دو خطِ دفاعی که S1911/S966/S607 پذیرفتند.
  const minBars = cfg.calmW + 52

  if (n < minBars + 2) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 242 * GOLD_PIP, tpDist: 242 * GOLD_PIP, maxHoldBars: cfg.maxHold,
      reason:
        `دادهٔ کافی نیست: گیتِ آرامشِ این لایه به میانهٔ پنجرهٔ بستهٔ ${cfg.calmW} کندلی ` +
        `نیاز دارد و خودِ σ پس از ۵۰ کندل آغاز می‌شود ⇒ دستِ‌کم ${minBars} کندلِ بستهٔ ` +
        `${cfg.tfFa} (موجود: ${n}). تا آن زمان این لایه سکوت می‌کند — نه تخمین، نه حدس.`,
      indicators: [{ name: 'داده', value: 'ناکافی', status: 'neutral' }],
    }
  }

  // ── تکهٔ ①: رویدادِ جهش + رانش + هندسه — عیناً از ماژولِ S950 ──────────────
  const f = s950Features(candles, cfg as unknown as S950Config)
  const i = n - 1
  const warm = cfg.bvWin + 2                      // = 91 (عینِ بک‌تست)

  const rNow = f.r[i]
  const sig = f.sigmaBv[i]
  const dr = f.drift[i]
  const atr = f.atrPx[i]
  const valid = i >= warm && sig > 0

  // ── تکهٔ ②: گیتِ آرامشِ σ — عیناً از پورتِ تأییدشدهٔ S605/S606 ─────────────
  const close = candles.map(c => c.close)
  const { sigma } = ewmaZ(close, cfg.lam)
  const reg = regimeRatio(sigma, cfg.calmW)
  const regI = reg[i]
  const calmOk = Number.isFinite(regI) && regI <= cfg.regMax

  // هندسهٔ برداریِ عینِ بک‌تست: SL = slK × ATR(89) همین کندل، TP = rr × SL.
  const slPip = Math.max((cfg.slK * atr) / GOLD_PIP, 1e-9)
  const tpPip = slPip * cfg.rr
  const slDist = slPip * GOLD_PIP
  const tpDist = tpPip * GOLD_PIP

  const thr = cfg.kJump * sig
  const jumpUp = valid && rNow > thr
  const jumpDn = valid && rNow < -thr
  const longBase = jumpUp && dr > 0
  const shortBase = jumpDn && dr < 0
  const basePart = longBase || shortBase          // رویدادِ S950 (بی‌گیت)
  const active = basePart && calmOk               // لایهٔ S955
  const direction: 'LONG' | 'SHORT' = shortBase ? 'SHORT' : 'LONG'

  // «نزدیک‌شدن» — فقط اطلاع‌رسانی. عمداً **مشروط به آرام‌بودنِ رژیم** است:
  // اگر رژیم طوفانی باشد حتی جهشِ کامل هم ورود نمی‌دهد، پس اعلامِ «نزدیکم»
  // در طوفان یک نشانهٔ گمراه‌کننده است (همان انتخابی که S1911 کرد).
  const nearUp = valid && !active && calmOk && !jumpUp &&
    rNow > cfg.approachFrac * thr && rNow <= thr && dr > 0
  const nearDn = valid && !active && calmOk && !jumpDn &&
    rNow < -cfg.approachFrac * thr && rNow >= -thr && dr < 0
  const approaching = nearUp || nearDn

  const rBp = rNow * 1e4
  const thrBp = thr * 1e4
  const ratio = thr > 0 ? Math.abs(rNow) / thr : 0
  const regTxt = Number.isFinite(regI) ? regI.toFixed(3) : '—'

  const indicators: RouterDecision['indicators'] = [
    {
      name: `بازدهِ کندلِ بسته (r) در برابرِ آستانهٔ جهش ±${cfg.kJump}·σ_BV(${cfg.bvWin})`,
      value: valid
        ? `${rBp.toFixed(1)} / ±${thrBp.toFixed(1)} bp (${(ratio * 100).toFixed(0)}٪ آستانه)`
        : '—',
      status: (jumpUp || jumpDn) ? 'ok' : (approaching ? 'neutral' : 'bad'),
    },
    {
      name: `رانشِ رژیمِ ${cfg.bvWin}-کندلی (close[t−1] − close[t−${cfg.bvWin + 1}])`,
      value: valid ? `${dr >= 0 ? '+' : ''}${dr.toFixed(2)} $` : '—',
      status: basePart ? 'ok' : ((jumpUp && dr <= 0) || (jumpDn && dr >= 0) ? 'bad' : 'neutral'),
    },
    {
      // این شاخص **قلبِ S955** است — تفاوتش با S950 دقیقاً همین یک خط است.
      name: `⭐ گیتِ آرامش: σ ÷ میانهٔ σ(${cfg.calmW} کندلِ بسته) — سقفِ ${cfg.regMax}`,
      value: Number.isFinite(regI)
        ? `${regTxt} ${calmOk ? '⇒ رژیمِ آرام ✓' : '⇒ رژیمِ طوفانی ✗'}`
        : '— (در حالِ گرم‌شدن)',
      status: calmOk ? 'ok' : 'bad',
    },
    {
      name: `σ_BV(${cfg.bvWin}) — نوسانِ پایهٔ Bipower (مقاوم به جهش، علّی)`,
      value: valid ? `${(sig * 1e4).toFixed(2)} bp` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (هندسهٔ برداریِ عینِ بک‌تست)',
      value: `${slPip.toFixed(1)} / ${tpPip.toFixed(1)} pip (نسبت ${cfg.rr} — متقارن)`,
      status: 'ok',
    },
  ]

  const evidence =
    `اندازه‌گیریِ این کارت: RQS2=${cfg.rqs2} · n=${cfg.nTrades} · WR=${cfg.wr}٪ · ` +
    `PF=${cfg.pf} · maxDD=${cfg.maxDd}٪ · lift=+${cfg.liftPp}pp (هر ۱۱ گیتِ RQS2 سبز)`

  let reason: string
  if (active) {
    const side = direction === 'LONG' ? 'خرید' : 'فروش'
    const jdir = direction === 'LONG' ? 'رو به بالا' : 'رو به پایین'
    reason =
      `کندلِ ${cfg.tfFa} بسته‌شده یک **جهشِ** ${jdir} ثبت کرد (r=${rBp.toFixed(1)} bp در برابرِ ` +
      `آستانهٔ ${cfg.kJump}·σ_BV=${thrBp.toFixed(1)} bp) · رانشِ ${cfg.bvWin}-کندلی ` +
      `(${dr >= 0 ? '+' : ''}${dr.toFixed(2)}$) **هم‌جهت** است · و رژیمِ نوسان **آرام** است ` +
      `(σ ÷ میانهٔ σ = ${regTxt} ≤ ${cfg.regMax}) ⇒ سیگنالِ ${side}. ` +
      `فیزیکِ اندازه‌گیری‌شده: جهشِ هم‌راستا در بستهٔ آرام ادامه می‌یابد، در طوفان نه — ` +
      `روی H8 همین تفکیک WR را از ۵۴.۵٪ (۱۲۰ جهشِ طوفانی) به ۶۷.۹٪ (۱۱۸ جهشِ آرام) برد. ` +
      `${evidence}. ورود روی openِ کندلِ بعد؛ SL=TP=${slPip.toFixed(1)} pip.`
  } else if (basePart && !calmOk) {
    // مهم‌ترین شاخهٔ آموزشیِ این لایه: جهشِ کامل رخ داده ولی گیت جلویش را گرفته.
    reason =
      `جهشِ هم‌راستا رخ داد (r=${rBp.toFixed(1)} bp در برابرِ ±${thrBp.toFixed(1)} bp، رانش هم‌جهت) ` +
      `**ولی رژیمِ نوسان طوفانی است** (σ ÷ میانهٔ σ = ${regTxt} > ${cfg.regMax}) ⇒ بدونِ ورود. ` +
      `این همان نیمی از رویدادهاست که لایهٔ پایه (S950) واردشان می‌شد و ضرر می‌داد: ` +
      `WR بازوی طوفانی ۵۴.۵٪ در برابرِ ۶۷.۹٪ آرام. سکوتِ اینجا **خودِ لبه** است، نه از دست دادنِ فرصت.`
  } else if (approaching) {
    reason =
      `بازدهِ کندلِ بسته (${rBp.toFixed(1)} bp) به ${(ratio * 100).toFixed(0)}٪ آستانهٔ جهش ` +
      `(±${thrBp.toFixed(1)} bp) رسیده، رانش هم‌جهت است و رژیم آرام است (${regTxt}) — اگر کندلِ بعد ` +
      `جهشِ کامل بسازد و این دو شرط بمانند، ورود صادر می‌شود. هنوز معامله‌ای نیست.`
  } else if (!valid) {
    reason = `σ_BV هنوز معتبر نیست (گرم‌شدنِ ${warm} کندلی یا نوسانِ صفر) — لایه در انتظار.`
  } else if (jumpUp || jumpDn) {
    reason =
      `جهش رخ داد (r=${rBp.toFixed(1)} bp) ولی رانشِ ${cfg.bvWin}-کندلی ` +
      `(${dr >= 0 ? '+' : ''}${dr.toFixed(2)}$) **مخالف** است ⇒ بدونِ ورود. ` +
      `آزمونِ کنترلِ لایهٔ پایه نشان داد جهشِ خلافِ رانش لبه ندارد (REJECT/z=۱.۶۶).`
  } else {
    reason =
      `کندلِ بستهٔ اخیر جهش نیست: |r|=${Math.abs(rBp).toFixed(1)} bp یعنی ${(ratio * 100).toFixed(0)}٪ ` +
      `آستانهٔ ${cfg.kJump}·σ_BV(${cfg.bvWin})=${thrBp.toFixed(1)} bp. ` +
      `رژیمِ فعلی: ${regTxt} (${calmOk ? 'آرام' : 'طوفانی'}). این لایه کم‌بسامد است ` +
      `(${cfg.nTrades} معامله در ۱۵.۶ سال) — بیشترِ کندل‌ها هیچ‌اند و همین صداقتِ لایه است.`
  }

  return {
    active, approaching, direction,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ جهشِ کامل (|r| > ${cfg.kJump}·σ_BV) هم‌جهت با رانش، در رژیمِ آرام`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS955(
  cfg: S955Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS955(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s955_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10

  const meta: DecideMeta = {
    code: 'S955',
    name: `جهشِ هم‌راستا در رژیمِ آرام (${cfg.tfFa})`,
    kind: 'jump_calm' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ برداریِ عینِ بک‌تست: SL=TP=${slPipShow} pip (${cfg.slK}×ATR(${cfg.bvWin}) ` +
      `کندلِ سیگنال). تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} کندلِ ${cfg.tfFa} نگه‌دار. ` +
      `⚠️ قیدِ تک‌معامله (allow_overlap=false در بک‌تست): تا این معامله بسته نشده، جهشِ ` +
      `بعدی نباید معاملهٔ جدید باز کند — وگرنه حکمِ اندازه‌گیری‌شده معتبر نیست. ` +
      `⚠️ هیچ مدیریتِ فعالی نکن (BE/trailing): در لایهٔ پایه این «بهبود»ها مهارت را ` +
      `نابود کردند، چون پس‌لرزهٔ جهش زمان می‌خواهد. فقط TP/SL/زمان. ` +
      `🔗 قیدِ پرتفویِ این کارت: ${cfg.portfolioNote}`,
    filters: [
      `جهش: |r| > ${cfg.kJump}·σ_BV(${cfg.bvWin}) روی کندلِ بستهٔ ${cfg.tfFa} (σ_BV علّی — Bipower تا t−1)`,
      `هم‌راستایی با رانشِ ${cfg.bvWin}-کندلیِ رژیم (آزمونِ کنترل: مکملش REJECT)`,
      `⭐ گیتِ آرامش: σ_t ÷ میانهٔ σ(${cfg.calmW} کندلِ بسته) ≤ ${cfg.regMax} — نرخِ عبور ${cfg.passRate}٪ ` +
        `(گیتِ زنده، نه همیشه-باز؛ ابطال‌گرِ P3 پیش‌ثبت)`,
      `هندسهٔ متقارن SL=TP=${cfg.slK}×ATR(${cfg.bvWin}) — صفر تورشِ WR-سازی`,
      `قیدِ تک‌معامله (بیشینه همزمانی = ۱) · کم‌بسامد: ${cfg.nTrades} معامله در ۱۵.۶ سال`,
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
