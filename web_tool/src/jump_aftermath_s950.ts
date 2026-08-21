// ---------------------------------------------------------------------------
// S950 — «پس‌لرزهٔ جهش، هم‌راستا با رانش» (Jump-Aftermath Drift-Aligned) · XAUUSD-H8
//
// حکمِ نهایی (سند: results/S950_JumpAftermathDriftAligned_Xauusd_H8_rqs2_80_ACCEPT.md):
//   RQS2 = **80** · هر ۱۱ دروازه پاس · پایدار روی ۴ seed مدلِ صفر (79.9/80.0/80.1/80.0)
//   n=224 (۱۴.۴ معامله در سال) · WR=61.6٪ (LONG 63.6٪ / SHORT 58.3٪) · PF=1.56
//   maxDD=4.92٪ · lift=+11.15pp · z=3.34–3.37 · p_perm≈0.0004 · n_trials=33 صادقانه
//
// فیزیکِ لایه: جهشِ قیمتی (|r| > k·σ_BV با k=2.6) روی H8 «ادامه» دارد، به شرطی
// که با رانشِ ۸۹-کندلیِ رژیم هم‌جهت باشد. σ_BV واریانسِ Bipower است (جهش‌های
// قبلی را از برآوردِ نوسانِ پایه حذف می‌کند) ⇒ آستانهٔ جهش خودش با جهش آلوده
// نمی‌شود. ساختارِ MTF یکنواخت (lift از −11pp در M4 تا +11pp در D1) شاهدِ
// پدیدهٔ فیزیکیِ مقیاس-وابسته است، نه برازشِ تصادفی.
//
// آزمونِ کنترل: فیلترِ مکمل (رانشِ مخالف) REJECT/z=1.66 ⇒ فیلترِ رانش اطلاعات
// دارد، انتخابِ پس‌ازدیدن نیست. همپوشانی با لایه‌های موجود ≤4.8٪ (جاکاردِ روزانه).
//
// ⚠️ پورتِ **مو-به-موی** strategies/s950_jump_aftermath.py::features/member_signals
//    + فیلترِ رانشِ results/_scan_S950/final_adjudicate.py — سه دامِ پورت:
//    ① ATR = میانگینِ سادهٔ ۸۹تاییِ TR سپس شیفتِ ۱ (np.convolve) — **نه** Wilder
//       (ewm). atrWilder ماژولِ S382 اینجا غلط است.
//    ② np.convolve(mode='full')[:len] در ۸۸ عضوِ اول «جمعِ جزئی ÷ ۸۹» می‌دهد
//       (میانگینِ کم‌وزن‌شده) — باید عیناً بازتولید شود وگرنه warm-up منحرف می‌شود.
//    ③ ایندکسِ علّیِ Bipower: prod[j]=|r[j+1]|·|r[j]| و bv[t]=bvFull[t−2] ⇒ آخرین
//       جفتِ دیده‌شده |r[t−1]|·|r[t−2]| است — σ_BV(t) هرگز r[t] را نمی‌بیند
//       (وگرنه آستانه با خودِ جهش آلوده می‌شد = look-ahead).
// ---------------------------------------------------------------------------
import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'

const GOLD_PIP = 0.1

export interface S950Config {
  id: string          // شناسهٔ کارت (XAUUSD-H8)
  tfFa: string        // برچسبِ فارسیِ تایم‌فریم برای متن‌ها
  kJump: number       // آستانهٔ جهش بر حسبِ σ_BV (قفل‌شده: 2.6)
  bvWin: number       // پنجرهٔ Bipower و رانش و ATR (قفل‌شده: 89 — فیبوناچی)
  slK: number         // SL = slK × ATR(bvWin) (قفل‌شده: 2.058 = 1.272×φ)
  rr: number          // TP = rr × SL (قفل‌شده: 1.0 — متقارن، بدونِ تورشِ WR-سازی)
  maxHold: number     // بیشینهٔ نگه‌داری بر حسبِ کندلِ H8 (قفل‌شده: 34 — فیبوناچی)
  approachFrac: number // «نزدیک‌شدن»: |r| ≥ approachFrac×آستانه (فقط UI، نه ورود)
}

export const S950_CFG: Record<string, S950Config> = {
  // تنها کارتِ ACCEPT. D1 حکمِ POWER-LIMITED داشت (نه ACCEPT) ⇒ وصل نمی‌شود؛
  // بقیهٔ ۱۷ تایم‌فریم REJECT صریح — قانونِ MTF: تعمیمِ بدونِ شاهد ممنوع.
  'XAUUSD-H8': {
    id: 'XAUUSD-H8', tfFa: 'H8',
    kJump: 2.6, bvWin: 89, slK: 2.058, rr: 1.0, maxHold: 34,
    approachFrac: 0.85,
  },
}

// ---------------------------------------------------------------------------
// smaConvolve — بازتولیدِ دقیقِ np.convolve(x, ones(p)/p, 'full')[:len(x)]:
//   out[i] = (Σ x[j] , j = max(0, i−p+1) .. i) / p
// توجه: در i < p−1 مقسوم‌علیه همچنان p است (جمعِ جزئی ÷ p) — عمداً، تا با
// بک‌تستِ پایتون بیت‌به‌بیت یکی باشد (دامِ ② بالای فایل).
// ---------------------------------------------------------------------------
function smaConvolve(x: number[], p: number): number[] {
  const n = x.length
  const out = new Array<number>(n).fill(0)
  let acc = 0
  for (let i = 0; i < n; i++) {
    acc += x[i]
    if (i >= p) acc -= x[i - p]
    out[i] = acc / p
  }
  return out
}

export interface S950Features {
  r: number[]         // بازدهِ لگاریتمی؛ r[0]=0
  sigmaBv: number[]   // σ_BV علّی (فقط دادهٔ تا t−1)
  atrPx: number[]     // ATR(bvWin) علّی بر حسبِ قیمت (دلار) — شیفتِ ۱
  drift: number[]     // drift[t] = close[t−1] − close[t−(bvWin+1)]
}

// پورتِ عینِ features() + رانشِ final_adjudicate.py — همه علّی (شیفتِ ۱).
export function s950Features(candles: Candle[], cfg: S950Config): S950Features {
  const n = candles.length
  const W = cfg.bvWin
  const r = new Array<number>(n).fill(0)
  for (let t = 1; t < n; t++) r[t] = Math.log(candles[t].close / candles[t - 1].close)

  // Bipower: prod[j] = |r[j+1]|·|r[j]| (طول n−1) ⇒ bv[t] = bvFull[t−2] (دامِ ③)
  const prod = new Array<number>(Math.max(n - 1, 0)).fill(0)
  for (let j = 0; j < n - 1; j++) prod[j] = Math.abs(r[j + 1]) * Math.abs(r[j])
  const bvFull = smaConvolve(prod, W)
  const sigmaBv = new Array<number>(n).fill(0)
  for (let t = 2; t < n; t++) {
    const bv = bvFull[t - 2] * (Math.PI / 2.0)
    sigmaBv[t] = Math.sqrt(Math.max(bv, 0))
  }

  // ATR(bvWin) علّی: TR ساده، میانگینِ سادهٔ p-تایی، سپس شیفتِ ۱ (دامِ ①)
  const trArr = new Array<number>(n).fill(0)
  for (let t = 1; t < n; t++) {
    const h = candles[t].high, l = candles[t].low, pc = candles[t - 1].close
    trArr[t] = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc))
  }
  const atrConv = smaConvolve(trArr, W)
  const atrPx = new Array<number>(n).fill(0)
  for (let t = 1; t < n; t++) atrPx[t] = atrConv[t - 1]

  // رانشِ رژیم: drift[t] = close[t−1] − close[t−(W+1)] برای t ≥ W+1
  const drift = new Array<number>(n).fill(0)
  for (let t = W + 1; t < n; t++) drift[t] = candles[t - 1].close - candles[t - (W + 1)].close

  return { r, sigmaBv, atrPx, drift }
}

// ---------------------------------------------------------------------------
// computeS950 — سیگنال روی آخرین کندلِ بستهٔ i = n−1 (ورود در openِ کندلِ بعد)
// ---------------------------------------------------------------------------
export function computeS950(candles: Candle[], cfg: S950Config): RawSignal {
  const n = candles.length
  const warm = cfg.bvWin + 2                      // = 91 (عینِ بک‌تست)

  const emptyInd: RouterDecision['indicators'] = [
    { name: 'داده', value: 'ناکافی', status: 'neutral' },
  ]
  if (n < warm + 2) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 242 * GOLD_PIP, tpDist: 242 * GOLD_PIP, maxHoldBars: cfg.maxHold,
      reason: `دادهٔ کافی نیست: این لایه ${warm} کندلِ بستهٔ H8 برای گرم‌شدنِ σ_BV(${cfg.bvWin}) و ATR(${cfg.bvWin}) لازم دارد (موجود: ${n}).`,
      indicators: emptyInd,
    }
  }

  const f = s950Features(candles, cfg)
  const i = n - 1                                 // آخرین کندلِ بسته‌شده

  const rNow = f.r[i]
  const sig = f.sigmaBv[i]
  const dr = f.drift[i]
  const atr = f.atrPx[i]
  const valid = i >= warm && sig > 0

  // هندسه = عینِ بک‌تست: SL = slK × ATR(89) «زندهٔ همین کندل» — بک‌تست هم برای
  // هر معامله ATR همان لحظه را استفاده کرد (sl_pip_arr برداری بود) ⇒ هندسهٔ
  // شناور اینجا نه تخفیف است نه بهبود؛ **خودِ قانونِ آزموده‌شده** است.
  const slPip = Math.max((cfg.slK * atr) / GOLD_PIP, 1e-9)
  const tpPip = slPip * cfg.rr
  const slDist = slPip * GOLD_PIP
  const tpDist = tpPip * GOLD_PIP

  const thr = cfg.kJump * sig                     // آستانهٔ جهش بر حسبِ log-return
  const jumpUp = valid && rNow > thr
  const jumpDn = valid && rNow < -thr
  const longSig = jumpUp && dr > 0
  const shortSig = jumpDn && dr < 0
  const active = longSig || shortSig
  const direction: 'LONG' | 'SHORT' = shortSig ? 'SHORT' : 'LONG'

  // «نزدیک‌شدن» (فقط اطلاع‌رسانی؛ ورود همچنان فقط با جهشِ کامل): |r| در
  // ۸۵–۱۰۰٪ آستانه و رانش هم‌جهت. هیچ معامله‌ای از این شاخه صادر نمی‌شود.
  const nearUp = valid && !active && rNow > cfg.approachFrac * thr && rNow <= thr && dr > 0
  const nearDn = valid && !active && rNow < -cfg.approachFrac * thr && rNow >= -thr && dr < 0
  const approaching = nearUp || nearDn

  const rBp = rNow * 1e4                          // برای نمایش: واحدِ ~bp
  const thrBp = thr * 1e4
  const ratio = thr > 0 ? Math.abs(rNow) / thr : 0

  const indicators: RouterDecision['indicators'] = [
    {
      name: `بازدهِ کندلِ بسته (r) در برابرِ آستانهٔ جهش ±${cfg.kJump}·σ_BV(${cfg.bvWin})`,
      value: valid ? `${rBp.toFixed(1)} / ±${thrBp.toFixed(1)} bp (${(ratio * 100).toFixed(0)}٪ آستانه)` : '—',
      status: (jumpUp || jumpDn) ? 'ok' : (approaching ? 'neutral' : 'bad'),
    },
    {
      name: `σ_BV(${cfg.bvWin}) — نوسانِ پایهٔ Bipower (مقاوم به جهش، علّی)`,
      value: valid ? `${(sig * 1e4).toFixed(2)} bp` : '—',
      status: 'neutral',
    },
    {
      name: `رانشِ رژیمِ ${cfg.bvWin}-کندلی (close[t−1] − close[t−${cfg.bvWin + 1}])`,
      value: valid ? `${dr >= 0 ? '+' : ''}${dr.toFixed(2)} $` : '—',
      status: active ? 'ok' : ((jumpUp && dr <= 0) || (jumpDn && dr >= 0) ? 'bad' : 'neutral'),
    },
    {
      name: `ATR(${cfg.bvWin}) — هندسهٔ برداریِ عینِ بک‌تست`,
      value: atr > 0 ? `${(atr / GOLD_PIP).toFixed(1)} pip` : '—',
      status: 'neutral',
    },
    {
      name: 'حد ضرر / هدف (این کارت)',
      value: `${slPip.toFixed(1)} / ${tpPip.toFixed(1)} pip (نسبت ${cfg.rr} — متقارن)`,
      status: 'ok',
    },
  ]

  let reason: string
  if (active) {
    const side = direction === 'LONG' ? 'خرید' : 'فروش'
    const jdir = direction === 'LONG' ? 'رو به بالا' : 'رو به پایین'
    reason =
      `کندلِ H8 بسته‌شده یک **جهشِ** ${jdir} ثبت کرد: r=${rBp.toFixed(1)} bp در برابرِ ` +
      `آستانهٔ ${cfg.kJump}·σ_BV=${thrBp.toFixed(1)} bp (${(ratio * 100).toFixed(0)}٪ آستانه) — و رانشِ ` +
      `${cfg.bvWin}-کندلیِ رژیم (${dr >= 0 ? '+' : ''}${dr.toFixed(2)}$) **هم‌جهت** است ⇒ سیگنالِ ${side}. ` +
      `فیزیکِ اندازه‌گیری‌شده: جهشِ هم‌راستا با رانش روی H8 ادامه می‌یابد ` +
      `(۲۲۴ معامله در ۱۵.۵ سال · WR=۶۱.۶٪ · هر ۱۱ دروازهٔ RQS2 پاس، z=۳.۳۴ پایدار روی ۴ seed؛ ` +
      `آزمونِ کنترل با رانشِ مخالف REJECT شد ⇒ فیلتر واقعاً اطلاعات دارد). ` +
      `ورود روی openِ کندلِ بعد؛ SL=TP=${slPip.toFixed(1)} pip (${cfg.slK}×ATR(${cfg.bvWin}) همین کندل، عینِ بک‌تست).`
  } else if (approaching) {
    reason =
      `بازدهِ کندلِ بسته (${rBp.toFixed(1)} bp) به ${(ratio * 100).toFixed(0)}٪ آستانهٔ جهش ` +
      `(±${thrBp.toFixed(1)} bp) رسیده و رانشِ رژیم هم‌جهت است — اگر کندلِ بعد جهشِ کامل ` +
      `(|r| > ${cfg.kJump}·σ_BV) بسازد و رانش هم‌جهت بماند، ورود صادر می‌شود. هنوز معامله‌ای نیست.`
  } else if (!valid) {
    reason = `σ_BV هنوز معتبر نیست (گرم‌شدنِ ${warm} کندلی یا نوسانِ صفر) — لایه در انتظار.`
  } else if (jumpUp || jumpDn) {
    reason =
      `جهش رخ داد (r=${rBp.toFixed(1)} bp در برابرِ ±${thrBp.toFixed(1)} bp) ولی رانشِ ` +
      `${cfg.bvWin}-کندلی (${dr >= 0 ? '+' : ''}${dr.toFixed(2)}$) **مخالف** است ⇒ بدونِ ورود. ` +
      `این دقیقاً همان فیلتری است که DD را از ۸.۵۹٪ به ۴.۹۲٪ آورد و آزمونِ کنترل نشان داد ` +
      `جهشِ خلافِ رانش لبه ندارد (z=۱.۶۶ REJECT).`
  } else {
    reason =
      `کندلِ بستهٔ اخیر جهش نیست: |r|=${Math.abs(rBp).toFixed(1)} bp یعنی ${(ratio * 100).toFixed(0)}٪ ` +
      `آستانهٔ ${cfg.kJump}·σ_BV(${cfg.bvWin})=${thrBp.toFixed(1)} bp. این لایه کم‌بسامد است ` +
      `(~۱۴ معامله در سال) — بیشترِ کندل‌ها هیچ‌اند و همین صداقتِ لایه است.`
  }

  return {
    active, approaching, direction,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ جهشِ کامل (|r| > ${cfg.kJump}·σ_BV) هم‌جهت با رانشِ ${cfg.bvWin}-کندلی روی کندلِ بعد`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS950(
  cfg: S950Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS950(candles, cfg)
  const price = a.price

  const reg: RegimeInfo = {
    regime: raw.direction === 'SHORT' ? 'trend_down' : 'trend_up',
    efficiencyRatio: 0, trendy: true,
    adx: 0, activeStream: raw.direction === 'SHORT' ? 'bear' : 'bull',
    bucket: `s950_${cfg.tfFa.toLowerCase()}`,
  }

  const slPipShow = Math.round((raw.slDist / GOLD_PIP) * 10) / 10
  const tpPipShow = Math.round((raw.tpDist / GOLD_PIP) * 10) / 10

  const meta: DecideMeta = {
    code: 'S950',
    name: `پس‌لرزهٔ جهش، هم‌راستا با رانش (${cfg.tfFa})`,
    kind: 'jump_aftermath' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ برداریِ عینِ بک‌تست: SL=TP=${slPipShow} pip (${cfg.slK}×ATR(${cfg.bvWin}) ` +
      `کندلِ سیگنال؛ میانهٔ تاریخی ≈۲۴۲ pip). تا برخورد به TP/SL یا پایانِ ${cfg.maxHold} ` +
      `کندلِ H8 (≈۱۱ روز) نگه‌دار. ⚠️ قیدِ تک‌معامله (allow_overlap=false در بک‌تست): تا این ` +
      `معامله بسته نشده، جهشِ بعدی نباید معاملهٔ جدید باز کند — وگرنه حکمِ اندازه‌گیری‌شده ` +
      `معتبر نیست. ⚠️ بهبودهای BE/trailing در آزمون **مهارت را نابود کردند** (پس‌لرزه زمان ` +
      `می‌خواهد) ⇒ هیچ مدیریتِ فعالی نکن؛ فقط TP/SL/زمان.`,
    filters: [
      `جهش: |r| > ${cfg.kJump}·σ_BV(${cfg.bvWin}) روی کندلِ بستهٔ H8 (σ_BV علّی — Bipower تا t−1)`,
      `هم‌راستایی با رانشِ ${cfg.bvWin}-کندلیِ رژیم (فیلترِ کنترل‌شده: مکملش REJECT)`,
      `هندسهٔ متقارن SL=TP=${cfg.slK}×ATR(${cfg.bvWin}) — صفر تورشِ WR-سازی`,
      'قیدِ تک‌معامله (بیشینه همزمانی = ۱) · کم‌بسامد: ~۱۴ معامله در سال',
    ],
  }

  return rawToDecision(raw, meta, cfg.id, price, reg, capital, riskPct)
}
