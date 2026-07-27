// ============================================================================
// indicators/bank/pattern.ts — دستهٔ الگوهای کندلی (Candlestick Pattern Detectors)
// ----------------------------------------------------------------------------
// منابع: deep-web/TA-Lib. خروجی هر تشخیص‌دهنده: +100 (صعودی)، −100 (نزولی)،
// 0 (بدونِ الگو). بدونِ look-ahead (هر i فقط از c[i], c[i-1], c[i-2] استفاده می‌کند؛
// pat در kit فقط از i>=3 مقدار می‌دهد). منطق کاملاً verbatim از bank.ts؛ active:false.
// ============================================================================

import { makeKit, body, range, upSh, dnSh, isBull, isBear } from './kit'

const K = makeKit()
const { pat } = K

pat('cdl_doji', 'دوجی (بدنهٔ بسیار کوچک)', (c, i) => (range(c[i]) && body(c[i]) <= 0.1 * range(c[i]) ? 100 : 0))
pat('cdl_dragonfly', 'دوجیِ سنجاقک (سایهٔ پایینِ بلند)', (c, i) => (range(c[i]) && body(c[i]) <= 0.1 * range(c[i]) && dnSh(c[i]) >= 0.6 * range(c[i]) ? 100 : 0))
pat('cdl_gravestone', 'دوجیِ سنگِ‌قبر (سایهٔ بالای بلند)', (c, i) => (range(c[i]) && body(c[i]) <= 0.1 * range(c[i]) && upSh(c[i]) >= 0.6 * range(c[i]) ? -100 : 0))
pat('cdl_hammer', 'چکش (سایهٔ پایینِ بلند، بدنهٔ کوچکِ بالا)', (c, i) => (range(c[i]) && dnSh(c[i]) >= 2 * body(c[i]) && upSh(c[i]) <= 0.15 * range(c[i]) && c[i - 1].close < c[i - 2].close ? 100 : 0))
pat('cdl_invhammer', 'چکشِ معکوس', (c, i) => (range(c[i]) && upSh(c[i]) >= 2 * body(c[i]) && dnSh(c[i]) <= 0.15 * range(c[i]) && c[i - 1].close < c[i - 2].close ? 100 : 0))
pat('cdl_hangingman', 'مردِ آویزان', (c, i) => (range(c[i]) && dnSh(c[i]) >= 2 * body(c[i]) && upSh(c[i]) <= 0.15 * range(c[i]) && c[i - 1].close > c[i - 2].close ? -100 : 0))
pat('cdl_shootingstar', 'ستارهٔ ثاقب', (c, i) => (range(c[i]) && upSh(c[i]) >= 2 * body(c[i]) && dnSh(c[i]) <= 0.15 * range(c[i]) && c[i - 1].close > c[i - 2].close ? -100 : 0))
pat('cdl_marubozu', 'ماروبوزو (بدونِ سایه)', (c, i) => (range(c[i]) && body(c[i]) >= 0.95 * range(c[i]) ? (isBull(c[i]) ? 100 : -100) : 0))
pat('cdl_spinningtop', 'فرفره (بدنهٔ کوچک، دو سایه)', (c, i) => (range(c[i]) && body(c[i]) <= 0.3 * range(c[i]) && upSh(c[i]) >= 0.3 * range(c[i]) && dnSh(c[i]) >= 0.3 * range(c[i]) ? 100 : 0))
pat('cdl_engulf_bull', 'پوششِ صعودی', (c, i) => (isBear(c[i - 1]) && isBull(c[i]) && c[i].close >= c[i - 1].open && c[i].open <= c[i - 1].close ? 100 : 0))
pat('cdl_engulf_bear', 'پوششِ نزولی', (c, i) => (isBull(c[i - 1]) && isBear(c[i]) && c[i].open >= c[i - 1].close && c[i].close <= c[i - 1].open ? -100 : 0))
pat('cdl_harami_bull', 'هارامیِ صعودی', (c, i) => (isBear(c[i - 1]) && body(c[i - 1]) > 0 && Math.max(c[i].open, c[i].close) < c[i - 1].open && Math.min(c[i].open, c[i].close) > c[i - 1].close ? 100 : 0))
pat('cdl_harami_bear', 'هارامیِ نزولی', (c, i) => (isBull(c[i - 1]) && body(c[i - 1]) > 0 && Math.max(c[i].open, c[i].close) < c[i - 1].close && Math.min(c[i].open, c[i].close) > c[i - 1].open ? -100 : 0))
pat('cdl_piercing', 'خطِ نفوذی (صعودی)', (c, i) => (isBear(c[i - 1]) && isBull(c[i]) && c[i].open < c[i - 1].low && c[i].close > (c[i - 1].open + c[i - 1].close) / 2 && c[i].close < c[i - 1].open ? 100 : 0))
pat('cdl_darkcloud', 'پوششِ ابرِ سیاه (نزولی)', (c, i) => (isBull(c[i - 1]) && isBear(c[i]) && c[i].open > c[i - 1].high && c[i].close < (c[i - 1].open + c[i - 1].close) / 2 && c[i].close > c[i - 1].open ? -100 : 0))
pat('cdl_morningstar', 'ستارهٔ صبحگاهی', (c, i) => (isBear(c[i - 2]) && body(c[i - 1]) <= 0.3 * range(c[i - 1] || c[i - 2]) && isBull(c[i]) && c[i].close > (c[i - 2].open + c[i - 2].close) / 2 ? 100 : 0))
pat('cdl_eveningstar', 'ستارهٔ شامگاهی', (c, i) => (isBull(c[i - 2]) && body(c[i - 1]) <= 0.3 * range(c[i - 1] || c[i - 2]) && isBear(c[i]) && c[i].close < (c[i - 2].open + c[i - 2].close) / 2 ? -100 : 0))
pat('cdl_3whitesoldiers', 'سه سربازِ سفید', (c, i) => (isBull(c[i]) && isBull(c[i - 1]) && isBull(c[i - 2]) && c[i].close > c[i - 1].close && c[i - 1].close > c[i - 2].close && c[i].open > c[i - 1].open && c[i - 1].open > c[i - 2].open ? 100 : 0))
pat('cdl_3blackcrows', 'سه کلاغِ سیاه', (c, i) => (isBear(c[i]) && isBear(c[i - 1]) && isBear(c[i - 2]) && c[i].close < c[i - 1].close && c[i - 1].close < c[i - 2].close && c[i].open < c[i - 1].open && c[i - 1].open < c[i - 2].open ? -100 : 0))
pat('cdl_beltuphold_bull', 'کمربندِ صعودی', (c, i) => (isBull(c[i]) && c[i].open === c[i].low && body(c[i]) >= 0.7 * range(c[i]) ? 100 : 0))
pat('cdl_beltuphold_bear', 'کمربندِ نزولی', (c, i) => (isBear(c[i]) && c[i].open === c[i].high && body(c[i]) >= 0.7 * range(c[i]) ? -100 : 0))
pat('cdl_longleg_doji', 'دوجیِ پابلند', (c, i) => (range(c[i]) && body(c[i]) <= 0.1 * range(c[i]) && upSh(c[i]) >= 0.35 * range(c[i]) && dnSh(c[i]) >= 0.35 * range(c[i]) ? 100 : 0))
pat('cdl_highwave', 'موجِ بلند', (c, i) => (range(c[i]) && body(c[i]) <= 0.2 * range(c[i]) && (upSh(c[i]) >= 0.4 * range(c[i]) || dnSh(c[i]) >= 0.4 * range(c[i])) ? 100 : 0))
pat('cdl_3inside_up', 'سه داخلیِ صعودی', (c, i) => (isBear(c[i - 2]) && Math.max(c[i - 1].open, c[i - 1].close) < c[i - 2].open && Math.min(c[i - 1].open, c[i - 1].close) > c[i - 2].close && isBull(c[i]) && c[i].close > c[i - 2].open ? 100 : 0))
pat('cdl_3inside_dn', 'سه داخلیِ نزولی', (c, i) => (isBull(c[i - 2]) && Math.max(c[i - 1].open, c[i - 1].close) < c[i - 2].close && Math.min(c[i - 1].open, c[i - 1].close) > c[i - 2].open && isBear(c[i]) && c[i].close < c[i - 2].open ? -100 : 0))
pat('cdl_tweezerbottom', 'انبرکِ کف', (c, i) => (Math.abs(c[i].low - c[i - 1].low) <= 0.05 * (range(c[i]) || 1) && isBear(c[i - 1]) && isBull(c[i]) ? 100 : 0))
pat('cdl_tweezertop', 'انبرکِ سقف', (c, i) => (Math.abs(c[i].high - c[i - 1].high) <= 0.05 * (range(c[i]) || 1) && isBull(c[i - 1]) && isBear(c[i]) ? -100 : 0))
pat('cdl_kicking_bull', 'ضربهٔ صعودی', (c, i) => (isBear(c[i - 1]) && body(c[i - 1]) >= 0.9 * range(c[i - 1]) && isBull(c[i]) && body(c[i]) >= 0.9 * range(c[i]) && c[i].open > c[i - 1].open ? 100 : 0))
pat('cdl_kicking_bear', 'ضربهٔ نزولی', (c, i) => (isBull(c[i - 1]) && body(c[i - 1]) >= 0.9 * range(c[i - 1]) && isBear(c[i]) && body(c[i]) >= 0.9 * range(c[i]) && c[i].open < c[i - 1].open ? -100 : 0))
pat('cdl_gap_up', 'گَپِ صعودی', (c, i) => (c[i].low > c[i - 1].high ? 100 : 0))
pat('cdl_gap_dn', 'گَپِ نزولی', (c, i) => (c[i].high < c[i - 1].low ? -100 : 0))

export const PATTERN_ITEMS = K.items
