// ============================================================================
// reversal_day_s345.ts — لایهٔ نوِ S345 (Al Brooks «Reversal Day» — فصلِ ۲۴ کتابِ
//   Trading Price Action: TRENDS)
// ----------------------------------------------------------------------------
// تزِ مرکزی (نقلِ Brooks، فصلِ ۲۴): «The day trends in one direction and then it
//   trends in the opposite direction into the close.» ⇒ چرخشِ روندِ درون‌روزی.
//   ماشهٔ مکانیکی طبقِ سه قاعدهٔ صریحِ فصل:
//     ۱) countertrend spike قوی (بدنه ≥ k×ATR) در جهتِ مخالفِ روندِ اولیهٔ روز
//        («There is almost always at least one countertrend spike before the
//          channel begins…»)
//     ۲) شکستِ خطِ روندِ اولیهٔ روز (رگرسیونِ تجمعیِ close از بازِ روز)
//        («The pullback to bar 5 broke the bull trend line…»)
//     ۳) lower-high (چرخشِ نزولی) یا higher-low (چرخشِ صعودی) نسبت به اکسترممِ
//        running روز («…and the bar 6 lower high set the stage for a bear trend
//        day into the close.»)
//     ۴) فیلترِ زمان: ورود فقط در پنجرهٔ میانه/اواخرِ روز — نه در opening range
//        («If the reversal starts in the last couple of hours and is strong…»)
//
// دو کارتِ پذیرفته‌شده (RQS+ ≥ ۸۰، منبع: results/S345_BrooksReversalDay_XauEur_M15M30_rqs90.md):
//   • XAUUSD-M15 LONG  → nOpen=4 · k=1.1 · slopeMin=0.05 · win=(0.40,0.95)
//       رژیمِ بانک r2_lo: r2(34) ≤ 0.55   +   فیلترِ بهبود: حذفِ Turn-of-Month (روزِ ماه > ۳)
//       SL=240 / TP=400 pip · maxHold=40 → RQS+ = 90.7 (WR 62.4٪ · PF 2.30 · +$2,422.8)
//   • EURUSD-M30 SHORT → nOpen=6 · k=0.8 · slopeMin=0.18 · win=(0.40,0.95)
//       رژیمِ بانک r2_lo: r2(34) ≤ 0.55
//       SL=20 / TP=33 pip · maxHold=28 → RQS+ = 91.7 (WR 62.5٪ · PF 2.38 · +$2,281.6)
//
// همپوشانی (ثبت‌شده، قانونِ اجباری): XAU-M15 با زمان-محورِ S139..S144 = ۴۸.۵٪ اما
//   بخشِ مستقل کیفیتِ *بالاتر* دارد (WR 65.0 / PF 2.56 در برابر WR 56.6 / PF 1.73 بخشِ
//   همپوشان) ⇒ بازتولیدِ لایهٔ زمان-محور نیست. EUR-M30 همپوشانی = ۳۰.۶٪ (خوش‌خیم).
//   نقشِ فیلتری هم آزموده شد: حذفِ *فقط* Turn-of-Month لایه را از ۸۹.۸ به ۹۰.۷ برد
//   (اعمال شد)، اما حذفِ دوشنبه‌ها بدتر کرد (اعمال نشد).
//
// نکتهٔ TP>SL (ضدِ اشتباهِ رایج #۸): هر دو کارت TP/SL > 1 دارند (1.67 و 1.65) ⇒ WR بالا
//   از دقتِ نقطهٔ چرخش می‌آید، نه از کوچک‌کردنِ TP.
//
// کدِ منبعِ حقیقتِ Python: strategies/s345_brooks_reversal_day.py (پورتِ verbatim)
// ماژولار/توسعه‌پذیر: فایلِ کاملاً مستقل؛ افزودنش فقط دو ورودی در CARD_LAYERS.
// ============================================================================

import type { Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'
import type { RegimeInfo } from './router'
import { r2Series } from './squeeze_s332'

// ---------------------------------------------------------------------------
export interface S345Config {
  id: string              // XAUUSD-M15 | EURUSD-M30
  tfFa: string
  side: 'LONG' | 'SHORT'
  pip: number             // 0.1 (XAU) | 0.0001 (EUR)
  barsPerDay: number      // M15=96 · M30=48
  nOpen: number           // کندل‌های تعیینِ جهتِ روندِ اولیهٔ روز
  kSpike: number          // ضریبِ ATR برای countertrend spike
  slopeMin: number        // حداقلِ |شیب| روندِ اولیه بر حسبِ کسری از ATR در کندل
  winFrom: number         // کسری از bars_per_day — شروعِ پنجرهٔ ورود
  winTo: number           // کسری از bars_per_day — پایانِ پنجرهٔ ورود
  atrPeriod: number       // 14
  r2Period: number        // 34
  r2Max: number           // 0.55 (رژیمِ r2_lo — بازارِ غیرخطی/چرخش‌پذیر)
  dropTurnOfMonth: boolean // فیلترِ بهبود: حذفِ روزهای ۱..۳ ماه
  slPip: number
  tpPip: number
  maxHold: number
  rqs: number
}

export const S345_CFG: Record<string, S345Config> = {
  // منبعِ اعداد: results/_scan_S345/XAUUSD_M15.json + _adjudicate_M15.json (V2_dropTOM)
  'XAUUSD-M15': {
    id: 'XAUUSD-M15', tfFa: 'M15', side: 'LONG', pip: 0.1, barsPerDay: 96,
    nOpen: 4, kSpike: 1.1, slopeMin: 0.05, winFrom: 0.40, winTo: 0.95,
    atrPeriod: 14, r2Period: 34, r2Max: 0.55, dropTurnOfMonth: true,
    slPip: 240, tpPip: 400, maxHold: 40, rqs: 90.7,
  },
  // منبعِ اعداد: results/_scan_S345/EURUSD_M30.json + _verify_h1_eur.json (EURM30)
  'EURUSD-M30': {
    id: 'EURUSD-M30', tfFa: 'M30', side: 'SHORT', pip: 0.0001, barsPerDay: 48,
    nOpen: 6, kSpike: 0.8, slopeMin: 0.18, winFrom: 0.40, winTo: 0.95,
    atrPeriod: 14, r2Period: 34, r2Max: 0.55, dropTurnOfMonth: false,
    slPip: 20, tpPip: 33, maxHold: 28, rqs: 91.7,
  },
}

// ---------------------------------------------------------------------------
// ATR (Wilder-approx، causal) — پورتِ verbatim از `_atr` پایتون.
// ---------------------------------------------------------------------------
export function atrSeriesS345(
  high: number[], low: number[], close: number[], p = 14,
): number[] {
  const n = close.length
  const tr = new Array<number>(n).fill(0)
  if (n === 0) return []
  tr[0] = high[0] - low[0]
  for (let i = 1; i < n; i++) {
    tr[i] = Math.max(
      high[i] - low[i],
      Math.abs(high[i] - close[i - 1]),
      Math.abs(low[i] - close[i - 1]),
    )
  }
  const atr = new Array<number>(n).fill(NaN)
  if (n >= p) {
    let s = 0
    for (let k = 0; k < p; k++) s += tr[k]
    atr[p - 1] = s / p
    for (let i = p; i < n; i++) atr[i] = (atr[i - 1] * (p - 1) + tr[i]) / p
  }
  return atr
}

// شناسهٔ روزِ UTC (منطبق با `dt.dt.floor('D')` پایتون)
function dayIdOf(tsSec: number): number {
  return Math.floor(tsSec / 86400)
}

// روزِ ماهِ UTC (برای فیلترِ Turn-of-Month، منطبق با `dt.day` پایتون)
function utcDayOfMonth(tsSec: number): number {
  return new Date(tsSec * 1000).getUTCDate()
}

// ---------------------------------------------------------------------------
// computeS345 — ارزیابیِ ماشهٔ چرخش روی «کندلِ آخرِ بسته‌شده» (i = n-1).
//   پورتِ verbatim از reversal_day_signals: همان رگرسیونِ تجمعیِ روز، همان
//   اکسترممِ running، همان سه شرطِ ماشه و همان پنجرهٔ زمانی.
// ---------------------------------------------------------------------------
export function computeS345(candles: Candle[], cfg: S345Config): RawSignal {
  const n = candles.length
  const o = candles.map(c => c.open)
  const h = candles.map(c => c.high)
  const l = candles.map(c => c.low)
  const c = candles.map(x => x.close)
  const t = candles.map(x => x.time)

  const side = cfg.side === 'LONG' ? 'long' : 'short'
  const slDist = cfg.slPip * cfg.pip
  const tpDist = cfg.tpPip * cfg.pip

  const need = cfg.r2Period + cfg.atrPeriod + cfg.nOpen + 10
  if (n < need) {
    return {
      active: false, approaching: false, direction: cfg.side,
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: 'دادهٔ کافی برای تشخیصِ چرخشِ روندِ روز (reversal day) موجود نیست.',
      indicators: [{ name: 'داده', value: 'ناکافی', status: 'neutral' }],
    }
  }

  const atr = atrSeriesS345(h, l, c, cfg.atrPeriod)
  const r2 = r2Series(c, cfg.r2Period)

  const i = n - 1
  const dToday = dayIdOf(t[i])

  // مرزِ روزِ جاری
  let j0 = i
  while (j0 > 0 && dayIdOf(t[j0 - 1]) === dToday) j0 -= 1
  const pos = i - j0                                   // اندیسِ درون‌روزیِ کندلِ آخر

  // پنجرهٔ ورود (verbatim: t_from = max(nOpen, int(winFrom*bpd)) ، t_to = int(winTo*bpd))
  const tFrom = Math.max(cfg.nOpen, Math.floor(cfg.winFrom * cfg.barsPerDay))
  const tTo = Math.floor(cfg.winTo * cfg.barsPerDay)
  const posLo = Math.max(tFrom, cfg.nOpen + 1)
  const inWindow = pos >= posLo && pos <= tTo
  // گاردِ روزِ پایتون (day_len > nOpen+2) — برای هر دو کارت با posLo تضمین می‌شود،
  // اما صریح نگه داشته می‌شود تا معناشناسی دقیقاً یکی باشد.
  const dayLongEnough = pos + 1 > cfg.nOpen + 2

  // --- جهتِ روندِ اولیهٔ روز ---
  const atrRef = atr[j0 + cfg.nOpen - 1]
  const atrRefOk = pos >= cfg.nOpen - 1 && isFinite(atrRef) && atrRef > 0
  let initDir = 0
  if (atrRefOk) initDir = Math.sign(c[j0 + cfg.nOpen - 1] - o[j0])
  const needInit = side === 'short' ? 1 : -1
  const initDirOk = atrRefOk && initDir === needInit

  // --- رگرسیونِ تجمعیِ روز تا کندلِ i (فرمولِ بستهٔ OLS، منطبق با نسخهٔ numpy) ---
  let slope = NaN, lineT = NaN, slopeNorm = NaN
  if (initDirOk && inWindow && dayLongEnough) {
    const m = pos + 1
    let Sy = 0, Sxy = 0
    for (let k = 0; k < m; k++) { Sy += c[j0 + k]; Sxy += k * c[j0 + k] }
    const P = pos
    const Sx = P * (P + 1) / 2
    const Sxx = P * (P + 1) * (2 * P + 1) / 6
    const denom = m * Sxx - Sx * Sx
    if (denom > 0) {
      slope = (m * Sxy - Sx * Sy) / denom
      const intercept = (Sy - slope * Sx) / m
      lineT = intercept + slope * P
      slopeNorm = slope / atrRef
    }
  }
  const trendOk = isFinite(slopeNorm) &&
    (initDir > 0 ? slopeNorm >= cfg.slopeMin : slopeNorm <= -cfg.slopeMin)

  // --- اکسترممِ running روز (شاملِ کندلِ جاری) ---
  let runHigh = -Infinity, runLow = Infinity
  for (let k = j0; k <= i; k++) { if (h[k] > runHigh) runHigh = h[k]; if (l[k] < runLow) runLow = l[k] }

  // --- ماشهٔ چرخش ---
  const body = Math.abs(c[i] - o[i])
  const atrT = (isFinite(atr[i]) && atr[i] > 0) ? atr[i] : atrRef
  const bigBody = isFinite(atrT) && body >= cfg.kSpike * atrT
  const spikeDirOk = side === 'short' ? c[i] < o[i] : c[i] > o[i]
  const brokeLine = isFinite(lineT) && (side === 'short' ? c[i] < lineT : c[i] > lineT)
  const structOk = side === 'short' ? h[i] < runHigh : l[i] > runLow

  // --- رژیمِ بانک r2_lo ---
  const r2v = r2[i]
  const regimeOk = isFinite(r2v) && r2v <= cfg.r2Max

  // --- فیلترِ بهبود: حذفِ Turn-of-Month (روزهای ۱..۳ ماه) ---
  const dom = utcDayOfMonth(t[i])
  const tomOk = !cfg.dropTurnOfMonth || dom > 3

  const active = initDirOk && inWindow && dayLongEnough && trendOk &&
    spikeDirOk && bigBody && brokeLine && structOk && regimeOk && tomOk

  // approaching: روزِ چرخش‌پذیر آماده است (جهتِ اولیه + شیبِ روند + رژیم + پنجره + TOM)
  //   اما هنوز countertrend spike ساختاری نیامده.
  const approaching = !active && initDirOk && inWindow && dayLongEnough &&
    trendOk && regimeOk && tomOk

  const initFa = initDir > 0 ? 'صعودی' : 'نزولی'
  const flipFa = side === 'short' ? 'نزولی' : 'صعودی'
  const structFa = side === 'short' ? 'سقفِ پایین‌تر (lower-high)' : 'کفِ بالاتر (higher-low)'

  const indicators: RouterDecision['indicators'] = [
    { name: `روندِ اولیهٔ روز (${cfg.nOpen} کندلِ نخست) باید ${side === 'short' ? 'صعودی' : 'نزولی'} باشد`,
      value: atrRefOk ? initFa + (initDirOk ? ' ✔' : ' ✘') : '—',
      status: initDirOk ? 'ok' : 'neutral' },
    { name: `قدرتِ روندِ اولیه (|شیب| ≥ ${cfg.slopeMin}×ATR در کندل)`,
      value: isFinite(slopeNorm) ? slopeNorm.toFixed(3) + (trendOk ? ' ✔' : ' ✘') : '—',
      status: trendOk ? 'ok' : 'neutral' },
    { name: `اسپایکِ ضدِ روند (بدنه ≥ ${cfg.kSpike}×ATR، جهتِ ${flipFa})`,
      value: (isFinite(atrT) && atrT > 0 ? (body / atrT).toFixed(2) + '×ATR' : '—')
        + (spikeDirOk && bigBody ? ' ✔' : ' ✘'),
      status: (spikeDirOk && bigBody) ? 'ok' : 'neutral' },
    { name: 'شکستِ خطِ روندِ روز (رگرسیونِ تجمعیِ close)',
      value: brokeLine ? 'شکسته ✔' : (isFinite(lineT) ? 'نشکسته ✘' : '—'),
      status: brokeLine ? 'ok' : 'neutral' },
    { name: `تأییدِ ساختاری: ${structFa}`,
      value: structOk ? 'تأیید ✔' : 'اکسترممِ تازه ✘', status: structOk ? 'ok' : 'neutral' },
    { name: `رژیمِ چرخش‌پذیر (R²(${cfg.r2Period}) ≤ ${cfg.r2Max})`,
      value: (isFinite(r2v) ? r2v.toFixed(2) : '—') + (regimeOk ? ' ✔' : ' ✘'),
      status: regimeOk ? 'ok' : 'bad' },
    { name: `پنجرهٔ زمانیِ چرخش (کندلِ ${posLo}..${tTo} روز)`,
      value: `${pos}` + (inWindow ? ' ✔' : ' ✘'), status: inWindow ? 'ok' : 'neutral' },
    ...(cfg.dropTurnOfMonth
      ? [{ name: 'فیلترِ بهبود: بیرون از ابتدای ماه (روزِ ماه > ۳)',
           value: `${dom}` + (tomOk ? ' ✔' : ' ✘'),
           status: (tomOk ? 'ok' : 'bad') as 'ok' | 'bad' }]
      : []),
  ]

  let reason: string
  if (active) {
    reason = `روزِ چرخش (Reversal Day): روندِ اولیهٔ ${initFa} روز با یک اسپایکِ ضدِ روندِ قوی ` +
      `(${(body / atrT).toFixed(2)}×ATR) شکست، خطِ روندِ روز شکسته شد و ${structFa} تأیید شد ` +
      `⇒ ورودِ ${side === 'short' ? 'فروش' : 'خرید'} در جهتِ چرخش تا پایانِ روز.`
  } else if (approaching) {
    reason = `روندِ اولیهٔ ${initFa} روز در رژیمِ چرخش‌پذیر شکل گرفته و در پنجرهٔ زمانیِ چرخش هستیم؛ ` +
      `منتظرِ اسپایکِ ضدِ روندِ قوی (≥ ${cfg.kSpike}×ATR) + شکستِ خطِ روند + ${structFa}.`
  } else if (!atrRefOk) {
    reason = 'روزِ جاری هنوز کندلِ کافی برای تعیینِ جهتِ روندِ اولیه ندارد.'
  } else if (!initDirOk) {
    reason = `روندِ اولیهٔ روز ${initFa} است؛ برای چرخشِ ${flipFa} باید ` +
      `${side === 'short' ? 'صعودی' : 'نزولی'} باشد — ورود نمی‌کنیم.`
  } else if (!inWindow) {
    reason = 'بیرون از پنجرهٔ زمانیِ چرخش هستیم (چرخش در میانه/اواخرِ روز معتبر است، نه در بازِ روز).'
  } else if (!regimeOk) {
    reason = `رژیمِ بازار چرخش‌پذیر نیست (R²(${cfg.r2Period}) > ${cfg.r2Max}) — از ورود پرهیز می‌کنیم.`
  } else if (!tomOk) {
    reason = 'ابتدای ماه (روزهای ۱..۳) — فیلترِ بهبودِ لایه ورود را مسدود می‌کند.'
  } else if (!trendOk) {
    reason = 'روندِ اولیهٔ روز به‌قدرِ کافی قوی نیست (شیب کم) — چرخشِ معناداری در کار نیست.'
  } else {
    reason = 'اسپایکِ ضدِ روندِ قوی / شکستِ خطِ روند / تأییدِ ساختاری هنوز کامل نشده است.'
  }

  return {
    active, approaching, direction: cfg.side,
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason,
    approachReason: approaching
      ? `منتظرِ ماشهٔ چرخش: اسپایکِ ضدِ روند ≥ ${cfg.kSpike}×ATR + شکستِ خطِ روندِ روز + ${structFa}`
      : undefined,
    indicators,
  }
}

// ---------------------------------------------------------------------------
export function decideS345(
  cfg: S345Config, a: AnalysisResult, candles: Candle[],
  capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS345(candles, cfg)

  const reg: RegimeInfo = {
    regime: cfg.side === 'SHORT' ? 'trend_down' : 'trend_up', efficiencyRatio: 0,
    trendy: false, adx: 0, activeStream: cfg.side === 'SHORT' ? 'bear' : 'bull',
    bucket: `s345_${cfg.tfFa.toLowerCase()}`,
  }

  const meta: DecideMeta = {
    code: 'S345',
    name: `چرخشِ روندِ روز (Brooks Reversal Day · ${cfg.tfFa})`,
    kind: 'reversal_day' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote: `هدف/حدِ ثابتِ مخصوصِ ${cfg.tfFa} (${cfg.tpPip}/${cfg.slPip} pip · نسبت ` +
      `${(cfg.tpPip / cfg.slPip).toFixed(2)}). طبقِ فصلِ ۲۴ Brooks «swinging بهتر از scalping است» ` +
      `⇒ معامله را تا TP/SL یا پایانِ ${cfg.maxHold} کندل نگه‌دار و زود نبند. ` +
      `هشدارِ خروجِ زودهنگام: اگر روندِ اولیهٔ روز از سر گرفته شد (اکسترممِ ` +
      `${cfg.side === 'SHORT' ? 'سقفِ' : 'کفِ'} روز شکست) چرخش شکست خورده است. ` +
      `⚠️ تریلِ زودهنگام روی این لایه آزموده شد و RQS+ را کاهش داد ⇒ حدِ ضرر را جابه‌جا نکن.`,
    filters: [
      `روندِ اولیهٔ روز (${cfg.nOpen} کندل) با |شیب| ≥ ${cfg.slopeMin}×ATR`,
      `اسپایکِ ضدِ روند ≥ ${cfg.kSpike}×ATR`,
      'شکستِ خطِ روندِ تجمعیِ روز',
      cfg.side === 'SHORT' ? 'تأییدِ lower-high' : 'تأییدِ higher-low',
      `رژیمِ چرخش‌پذیر R²(${cfg.r2Period}) ≤ ${cfg.r2Max}`,
      `پنجرهٔ زمانیِ چرخش (${cfg.winFrom}..${cfg.winTo} روز)`,
      ...(cfg.dropTurnOfMonth ? ['حذفِ ابتدای ماه (روزِ ماه > ۳)'] : []),
    ],
  }

  return rawToDecision(raw, meta, cfg.id, a.price, reg, capital, riskPct)
}
