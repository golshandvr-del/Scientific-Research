// ---------------------------------------------------------------------------
// S759 — «شکستِ ساختاریِ داو × کندلِ مطلع» (Informed Structure Break) · XAUUSD-**H4**
//
// حکمِ نهایی (سند: results/S759_InformedStructureBreak_Xauusd_H4_rqs2_85_ACCEPT.md):
//   · XAUUSD-H4 (L=5) ⇒ RQS2 = **85.2** (تنشِ n_trials=100 ⇒ 83.5) · هر ۱۱ دروازه سبز
//     n=175 · WR=52.00٪ · BE=39.26٪ · lift=+12.58pp · z=3.40 · PF=1.78
//     H7 (نیمهٔ دومِ دست‌نخورده) n=90 · WR 58.89٪ · PF 2.38
//   · ⚠️ **قانونِ MTF:** تنها کارتِ ACCEPT همین H4 است. H3 با ۱۰/۱۱ (فقط DD 8.9٪)
//     **REJECT 30.3** است؛ H6/H8 و بقیه REJECT؛ H12/D1/W1 UNPROVEN ⇒ فقط H4 وصل می‌شود.
//
// قاعدهٔ منجمد (عینِ strategies/s758_swing_structure.py::structure_signals + s759 ρ-gate):
//   ① پیوتِ فراکتال با نیم‌پهنای L=5: high[p] ≥ max(high[p−5..p+5]) (و آینه برای low)؛
//      پیوت **فقط در p+5 تأیید** می‌شود ⇒ کاملاً علّی.
//   ② ساختارِ HL: دو پیوت‌کفِ آخرِ تأییدشده l₁, l₂ با low[l₂] > low[l₁]، و سقفِ میانی
//      hh = بالاترین پیوت‌سقفِ تأییدشده با l₁ < p < l₂.
//   ③ کیفیتِ پا: hh − low[l₁] ≥ 1.0 × ATR89[t−1]   (ATR وایلدر، از t−1 نه t).
//   ④ رویداد (لبهٔ اول): close[t] > hh ∧ close[t−1] ≤ hh ∧ close[t] > low[l₂].
//   ⑤ گیتِ مطلع: ρ = (close−open)/(high−low) ≥ 0.618 روی همان کندلِ شکست.
//   ⑥ LONG-only.
//
// 🔴 دام‌های پورت (با هارنسِ پریتی سنجیده می‌شوند، نه با چشم):
//   A) **ورود = openِ کندلِ بعد** (engine/scalp_engine.simulate_trades: entry_bar=si+1،
//      fill=o[entry_bar]). برخلافِ S1516 (هارنسِ S382 که close می‌گیرد)، اینجا هارنسِ
//      حکم موتورِ استاندارد است ⇒ سیگنال روی آخرین کندلِ **بسته** ⇒ ورود در قیمتِ جاری.
//   B) **هندسه شناور است، نه منجمد:** SL = 1.45 × ATR89 **روی کندلِ سیگنال** (sl_pip[si])،
//      TP = 1.618 × SL. میانهٔ ۱۵.۶ ساله 118.9/192.3 pip فقط برای گزارش است. پس برخلافِ
//      S1516 عددِ artifact کپی نمی‌شود؛ فرمول روی فیدِ زنده اجرا می‌شود.
//   C) **max_hold = 55 پارامترِ حکم است** (موتور با max_hold=55 داوری کرد) ⇒ عیناً ۵۵.
//   D) پیوت با `>=` (تساوی هم پیوت است) — عینِ `h >= rmax` پانداس.
//   E) ترتیبِ به‌روزرسانی در هر t: اول پیوت‌سقف، بعد پیوت‌کف، بعد بازسازیِ hh، بعد
//      بررسیِ سیگنال — عینِ حلقهٔ پایتون؛ ترتیبِ دیگر hh متفاوتی می‌سازد.
//   F) واحدِ pip موتور برای XAUUSD = 0.10$ (نه 0.01) — شرطِ ③ در واحدِ قیمت بیان شد
//      تا مستقل از pip باشد؛ SL/TP هم مستقیم در دلار ساخته می‌شوند.
//
// ممیزیِ شاهدِ کاذب (پیش از سیم‌کشی): tools/s759_false_witness_audit.py ⇒
//   results/_s759/false_witness_h4.json — حکم **CLEAR** (کنترل‌ها: ۱۷۵/۵۲.۰۰ و ۵۰۸ S1516).
//   jaccard در برابرِ ساکنانِ زندهٔ H4: S382 0.069 · S589 0.083 · S547 0.0 · S1516 0.017
//   (سطحِ روز همه < 0.14). ⚠️ قیدِ سایز (نه قیدِ ورود): ۵۴.۸٪ کندل‌های S759 با گذرِ
//   S382 هم‌کندل است (۷۸.۴٪ در ±۲ کندل) ولی S382 ۷.۵× بزرگ‌تر است ⇒ شکلِ «فیلترِ کیفیت»
//   (پروندهٔ S966/S1911)، نه یک رویداد با دو نام. سندِ S759 §۶: nonOV lift +10.6pp ⇒
//   ارزشِ مستقل. اگر هر دو هم‌زمان روشن بودند: **یک** پوزیشن، نه دو.
// ---------------------------------------------------------------------------

import { atr, type Candle } from './indicators'
import type { AnalysisResult } from './signal'
import type { RouterDecision, RegimeInfo } from './router'
import { type RawSignal, type DecideMeta, rawToDecision } from './revived_strategies'

export interface S759Config {
  id: string
  tfFa: string
  L: number            // نیم‌پهنای فراکتال (برندهٔ کشفِ نیمهٔ اول از {3,5,8})
  legK: number         // کیفیتِ پا × ATR
  rhoMin: number       // گیتِ مطلع
  atrP: number
  slK: number
  rr: number
  maxHold: number      // پارامترِ حکم (نه سقفِ ایمنی)
  warmup: number       // max(ATR_P*4, 400) — همگراییِ ATRِ وایلدر
  approachAtr: number  // فقط UI: فاصلهٔ close تا hh (×ATR) برای «نزدیک‌شدن»
  // اعدادِ حکم برای شفافیتِ UI
  rqs2: number; nTrades: number; wr: number; lift: number; z: number; pf: number
  medSlPip: number; medTpPip: number
}

export const S759_CFG: Record<string, S759Config> = {
  'XAUUSD-H4': {
    id: 'XAUUSD-H4', tfFa: 'H4',
    L: 5, legK: 1.0, rhoMin: 0.618,
    atrP: 89, slK: 1.45, rr: 1.618, maxHold: 55,
    warmup: 400, approachAtr: 0.25,
    rqs2: 85.2, nTrades: 175, wr: 52.0, lift: 12.58, z: 3.40, pf: 1.78,
    medSlPip: 118.9, medTpPip: 192.3,
  },
}

export interface S759Features {
  atr: number[]
  rho: number[]
  structural: boolean[]   // سیگنالِ S758 (بی‌گیت)
  sig: boolean[]          // S758 ∧ ρ ≥ rhoMin
  hh: number[]            // سقفِ میانیِ فعال در هر t (NaN اگر ساختارِ HL نیست)
  l1Low: number[]
  l2Low: number[]
  legOk: boolean[]
}

/** پورتِ عینِ structure_signals (فقط سمتِ لانگ) + گیتِ ρ. */
export function s759Features(c: Candle[], cfg: S759Config): S759Features {
  const n = c.length
  const L = cfg.L
  const h = c.map(x => x.high), l = c.map(x => x.low), cl = c.map(x => x.close)
  const a = atr(c, cfg.atrP)

  // ① پیوتِ فراکتال (پنجرهٔ مرکزیِ 2L+1؛ لبه‌ها NaN ⇒ پیوت نیست)
  const ph = new Array<boolean>(n).fill(false)
  const pl = new Array<boolean>(n).fill(false)
  for (let i = L; i + L < n; i++) {
    let mx = -Infinity, mn = Infinity
    for (let j = i - L; j <= i + L; j++) { if (h[j] > mx) mx = h[j]; if (l[j] < mn) mn = l[j] }
    ph[i] = h[i] >= mx
    pl[i] = l[i] <= mn
  }

  const structural = new Array<boolean>(n).fill(false)
  const hhArr = new Array<number>(n).fill(NaN)
  const l1Arr = new Array<number>(n).fill(NaN)
  const l2Arr = new Array<number>(n).fill(NaN)
  const legOk = new Array<boolean>(n).fill(false)
  const hsConf: number[] = []
  let l1 = -1, l2 = -1
  let midHH = NaN
  let hlValid = false

  const midHigh = (lo: number, hi: number): number => {
    let best = NaN
    for (let k = hsConf.length - 1; k >= 0; k--) {
      const p = hsConf[k]
      if (p <= lo) break
      if (p < hi) { const v = h[p]; if (!isFinite(best) || v > best) best = v }
    }
    return best
  }

  for (let t = 1; t < n; t++) {
    let changed = false
    const p = t - L
    if (p >= 0 && ph[p]) { hsConf.push(p); changed = true }        // دامِ E: اول سقف
    if (p >= 0 && pl[p]) { l1 = l2; l2 = p; changed = true }        //          بعد کف
    if (changed) {
      hlValid = l1 >= 0 && l2 >= 0 && l[l2] > l[l1]
      midHH = hlValid ? midHigh(l1, l2) : NaN
      hlValid = hlValid && isFinite(midHH)
    }
    if (hlValid) { hhArr[t] = midHH; l1Arr[t] = l[l1]; l2Arr[t] = l[l2] }
    const atrPrev = a[t - 1]
    if (!isFinite(atrPrev) || atrPrev <= 0) continue
    if (hlValid && (midHH - l[l1]) >= cfg.legK * atrPrev) {
      legOk[t] = true
      if (cl[t] > midHH && cl[t - 1] <= midHH && cl[t] > l[l2]) structural[t] = true
    }
  }

  const rho = c.map(x => { const r = x.high - x.low; return r > 0 ? (x.close - x.open) / r : 0 })
  const sig = structural.map((s, i) => s && rho[i] >= cfg.rhoMin)
  return { atr: a, rho, structural, sig, hh: hhArr, l1Low: l1Arr, l2Low: l2Arr, legOk }
}

export function computeS759(candles: Candle[], cfg: S759Config): RawSignal {
  const n = candles.length
  const minBars = cfg.warmup + 2
  if (n < minBars) {
    return {
      active: false, approaching: false, direction: 'LONG',
      slDist: 0, tpDist: 0, maxHoldBars: cfg.maxHold,
      reason: `دادهٔ ناکافی: این لایه دستِ‌کم ${minBars} کندلِ ${cfg.tfFa} می‌خواهد ` +
        `(گرم‌شدنِ ATR${cfg.atrP}ِ وایلدر = ${cfg.warmup} کندل، عینِ warmupِ داوری)، ولی فید ${n} کندل دارد.`,
      indicators: [],
    }
  }
  const f = s759Features(candles, cfg)
  const i = n - 1
  const last = candles[i]
  const atrI = f.atr[i]
  const slDist = cfg.slK * atrI           // دامِ B: ATR روی کندلِ سیگنال
  const tpDist = cfg.rr * slDist
  const hh = f.hh[i]
  const ind: RouterDecision['indicators'] = [
    { name: 'ساختارِ HL (کفِ بالاتر)', value: isFinite(hh) ? `${f.l1Low[i].toFixed(2)} → ${f.l2Low[i].toFixed(2)}` : 'ندارد',
      status: isFinite(hh) ? 'ok' : 'bad' },
    { name: 'سقفِ میانی (hh)', value: isFinite(hh) ? hh.toFixed(2) : '—', status: isFinite(hh) ? 'ok' : 'bad' },
    { name: `کیفیتِ پا (hh − l₁ ≥ ${cfg.legK}×ATR${cfg.atrP})`, value: f.legOk[i] ? 'بله' : 'خیر', status: f.legOk[i] ? 'ok' : 'bad' },
    { name: 'شکستِ لبهٔ اول (close > hh)', value: f.structural[i] ? 'بله' : 'خیر', status: f.structural[i] ? 'ok' : 'bad' },
    { name: `ρ کندل (≥ ${cfg.rhoMin})`, value: f.rho[i].toFixed(3), status: f.rho[i] >= cfg.rhoMin ? 'ok' : 'bad' },
  ]

  if (f.sig[i]) {
    return {
      active: true, approaching: false, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: `شکستِ ساختاریِ داو روی ${cfg.tfFa}: پس از کفِ بالاتر (${f.l1Low[i].toFixed(2)} → ` +
        `${f.l2Low[i].toFixed(2)})، کندل بالای سقفِ میانی ${hh.toFixed(2)} بسته شد (لبهٔ اول) و ` +
        `بدنه‌اش ${(f.rho[i] * 100).toFixed(0)}٪ دامنه است (ρ ≥ ${cfg.rhoMin}) ⇒ **کندلِ مطلع**: ` +
        `خریدار تا انتهای کندل پای شکست ایستاد. ورود = openِ کندلِ بعد.`,
      indicators: ind,
    }
  }

  // فقط UI — حالتِ «نزدیک‌شدن» داوری نشده است.
  if (isFinite(hh) && f.legOk[i] && last.close <= hh && last.close >= hh - cfg.approachAtr * atrI
      && last.close > f.l2Low[i]) {
    return {
      active: false, approaching: true, direction: 'LONG',
      slDist, tpDist, maxHoldBars: cfg.maxHold,
      reason: `ساختارِ HL روی ${cfg.tfFa} مسلح است و close (${last.close.toFixed(2)}) فقط ` +
        `${((hh - last.close) / atrI).toFixed(2)}×ATR زیرِ سقفِ میانی ${hh.toFixed(2)} است.`,
      approachReason: `تأییدِ لازم: کندلی که **بالای ${hh.toFixed(2)} بسته شود** و بدنه‌اش ` +
        `≥ ${(cfg.rhoMin * 100).toFixed(1)}٪ دامنه باشد. شکستِ با کندلِ ضعیف (ρ پایین) معامله نمی‌شود.`,
      indicators: ind,
    }
  }

  let why: string
  if (f.structural[i]) why = `شکستِ ساختاری رخ داد ولی ρ=${f.rho[i].toFixed(3)} < ${cfg.rhoMin} ⇒ کندلِ مطلع نیست (بازوی مکملِ ρ پایین WR 42.5٪ و زیرِ سربه‌سر است).`
  else if (!isFinite(hh)) why = 'ساختارِ «کفِ بالاتر + سقفِ میانی» فعلاً شکل نگرفته است.'
  else if (!f.legOk[i]) why = `ساختار هست ولی پا کوتاه است (hh − l₁ < ${cfg.legK}×ATR).`
  else if (last.close > hh) why = 'قیمت بالای سقفِ میانی است ولی این لبهٔ اول نیست (شکست قبلاً رخ داده).'
  else why = `close زیرِ سقفِ میانی ${hh.toFixed(2)} است.`
  return {
    active: false, approaching: false, direction: 'LONG',
    slDist, tpDist, maxHoldBars: cfg.maxHold,
    reason: `بدونِ سیگنال روی ${cfg.tfFa}. ${why}`,
    indicators: ind,
  }
}

export function decideS759(
  cfg: S759Config, a: AnalysisResult, candles: Candle[], capital = 10000, riskPct = 1.0,
): RouterDecision {
  const raw = computeS759(candles, cfg)
  const reg: RegimeInfo = {
    regime: 'trend_up', efficiencyRatio: 0, trendy: true, adx: 0,
    activeStream: 'bull', bucket: `s759_${cfg.tfFa.toLowerCase()}`,
  }
  const meta: DecideMeta = {
    code: 'S759',
    name: `شکستِ ساختاریِ داو × کندلِ مطلع (${cfg.tfFa})`,
    kind: 'structure_break' as any,
    manageStyle: 'fixed-tp-sl',
    manageNote:
      `هندسهٔ حکم: SL = ${cfg.slK}×ATR${cfg.atrP} (روی کندلِ سیگنال) · TP = ${cfg.rr}×SL ` +
      `(میانهٔ ۱۵.۶ ساله ${cfg.medSlPip}/${cfg.medTpPip} pip موتور = ${(cfg.medSlPip / 10).toFixed(1)}$/${(cfg.medTpPip / 10).toFixed(1)}$). ` +
      `اگر تا **${cfg.maxHold} کندلِ H4** به هیچ‌کدام نخورد، با close بسته شود — این پارامترِ خودِ حکم است. ` +
      `قیدِ تک‌معامله (allow_overlap=false): تا بسته‌شدن، شکستِ بعدی معاملهٔ تازه نیست. ` +
      `⚠️ **قیدِ سایز با S382 روی همین کارت:** ۵۴.۸٪ از رویدادهای S759 هم‌کندلِ گذرِ %R ` +
      `S382 است (ممیزیِ شاهدِ کاذب: jaccard 0.069 ⇒ رویدادِ واحد نیست، ولی هم‌زمانی زیاد است) ⇒ ` +
      `اگر هر دو روشن‌اند **یک** پوزیشن بگیر، نه دو. ` +
      `⚠️ سهمِ بزرگی از سود در ۲۰۲۵–۲۰۲۶ (رژیمِ روندِ قوی) است — ۱۱/۱۶ سال مثبت. ` +
      `هیچ مدیریتِ فعالی (BE/trailing) آزموده نشده ⇒ فقط TP/SL/زمان.`,
    filters: [
      `پیوتِ فراکتالِ L=${cfg.L} با تأییدِ علّی در i+${cfg.L} (برندهٔ کشفِ نیمهٔ اول از {3,5,8})`,
      'ساختارِ داو: کفِ بالاتر (l₂ > l₁) و سقفِ میانی = بالاترین پیوت‌سقف بین آن‌دو',
      `کیفیتِ پا: hh − l₁ ≥ ${cfg.legK}×ATR${cfg.atrP}[t−1]`,
      'لبهٔ اول: close[t] > hh و close[t−1] ≤ hh و close[t] > l₂',
      `گیتِ مطلع: ρ = (close−open)/(high−low) ≥ ${cfg.rhoMin} (منجمد از S965/S1520)`,
      'LONG-only · ورود openِ کندلِ بعد · فقط H4 (H3 REJECT 30.3، بقیه REJECT/UNPROVEN)',
    ],
  }
  return rawToDecision(raw, meta, cfg.id, a.price, reg, capital, riskPct)
}
