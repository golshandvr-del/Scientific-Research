# INDICATOR BANK EXPANSION — بانک اندیکاتور (هدف: ۴۰۰+ اندیکاتور پیچیده)

> **وضعیت:** در حال تکمیل (نشستِ User Note).
> **هدف:** افزودن ۴۰۰+ اندیکاتورِ پیچیده و کمتر ساده به رجیستریِ پروژه
> (`web_tool/src/indicators/`)، با تمرکز روی **XAUUSD**.
> **قانونِ فعال‌سازی:** همهٔ اندیکاتورهای جدید به‌صورتِ پیش‌فرض **غیرفعال (`active:false`)**
> ثبت می‌شوند و فقط وقتی یک لایهٔ استراتژی آن‌ها را صدا بزند فعال می‌گردند.
> **ضدِ ریست:** این فایل تدریجی و مرحله‌به‌مرحله پر و بلافاصله commit+push می‌شود، تا اگر
> سندباکس ریست شد از همین نقطه ادامه دهیم.

---

## وضعیتِ فعلیِ رجیستری (پیش از این نشست)

اندیکاتورهای موجود در `web_tool/src/indicators/` (پایه + چند پیچیده):
`sma, ema, rsi, zscore, slope, kaufmanER, atr, bollinger, macd, stoch, adx,
vortex, alligator, ichimoku` (به‌همراه توابعِ کمکی: smma, gatorState, ribbon/GMMA,
ichimokuCloudPos). جمعاً ~۱۵ اندیکاتورِ ثبت‌شده در registry.

**کمبود:** طبق User Note باید بانک به ۴۰۰+ اندیکاتور برسد و شکافِ اندیکاتورهای
پیچیده/کمیاب (Ehlers، Hilbert، DeMark، cycle، fractal، statistical…) پر شود.

---

## پیشرفتِ جمع‌آوری (شمارشِ زنده)

| مرحله | منبع/زبان | یافته‌های خام | وضعیت |
|---|---|---|---|
| ۱ | جستجوی انگلیسی (وب عمومی) | ~۷۰ | ✅ در حال ثبت |
| ۲ | جستجوی روسی | — | ⏳ |
| ۳ | جستجوی چینی | — | ⏳ |
| ۴ | Deep-web / بلاگ‌ها / فروشگاه MT4/MT5 | — | ⏳ |

---

## مرحله ۱ — جستجوی انگلیسی (منابع عمومیِ معتبر)

منابع: incrediblecharts.com (A–Z)، quantifiedstrategies.com (Top 100)،
tradingtechnologies TT library، mql5.com blogs، StockCharts ChartSchool.

### دستهٔ Trend / Moving-Average
1. SMA — Simple Moving Average
2. EMA — Exponential Moving Average
3. WMA — Weighted Moving Average
4. HMA — Hull Moving Average
5. WWMA / RMA — Wilder Moving Average
6. DMA — Displaced Moving Average
7. SMMA — Smoothed MA (پایهٔ Alligator)
8. MMA — Multiple Moving Averages (Guppy)
9. Rainbow 3D MA
10. MA Oscillator (Price − MA)
11. Linear Regression Indicator (LSMA)
12. Standard Deviation Channels
13. TRIX (triple-smoothed ROC)
14. MACD
15. MACD Histogram
16. MACD Percentage Price Oscillator (PPO)
17. KST — Know Sure Thing (Pring)
18. Coppock Curve
19. Parabolic SAR (Wilder)
20. Directional Movement Index (DMI / +DI / −DI)
21. ADX — Average Directional Index
22. ADXR — ADX Rating
23. Aroon (Up/Down)
24. Aroon Oscillator
25. Vortex Indicator (VI+/VI−)
26. Ichimoku Cloud (Tenkan/Kijun/Senkou/Chikou)
27. Alligator (Bill Williams)
28. Gator Oscillator
29. Vertical Horizontal Filter (VHF)
30. Detrended Price Oscillator (DPO)

### دستهٔ Momentum / Oscillator
31. RSI — Relative Strength Index (Wilder)
32. Stochastic Oscillator (%K/%D)
33. Slow Stochastic
34. Stochastic RSI (Chande & Kroll)
35. Williams %R
36. CCI — Commodity Channel Index
37. Momentum Indicator
38. Rate of Change (ROC, price)
39. Smoothed Rate of Change (SROC)
40. Chande Momentum Oscillator (CMO)
41. Ultimate Oscillator (Williams)
42. Awesome Oscillator (Bill Williams)
43. Accelerator/Decelerator Oscillator (AC)
44. DeMarker (DeM)
45. Relative Vigor Index (RVI)
46. TSI — True Strength Index
47. Fisher Transform (Ehlers)
48. Elder Ray Index (Bull/Bear Power)
49. Percentage Price Oscillator (PPO)
50. Kaufman Efficiency Ratio (ER)

### دستهٔ Volatility
51. ATR — Average True Range
52. ATR Bands
53. ATR Trailing Stops
54. Bollinger Bands
55. Bollinger Bandwidth
56. Bollinger %B
57. Keltner Channels
58. Donchian Channels
59. Chaikin Volatility
60. Choppiness Index (Dreiss)
61. Mass Index
62. Standard Deviation (rolling)
63. Volatility (coefficient of variation)
64. Volatility Ratio (Schwager)
65. Volatility Stops (Wilder)
66. Chandelier Exits
67. Price Envelope / Percentage Bands
68. Historical Volatility

### دستهٔ Volume / Money-Flow (نکته: XAUUSD اسپات معمولاً tick-volume دارد)
69. On Balance Volume (OBV)
70. Accumulation/Distribution (A/D)
71. Chaikin Money Flow (CMF)
72. Chaikin Oscillator
73. Money Flow Index (MFI)
74. Ease of Movement (EOM)
75. Force Index (Elder)
76. Price Volume Trend (PVT)
77. Negative Volume Index (NVI)
78. Positive Volume Index (PVI)
79. Volume Oscillator
80. Klinger Volume Oscillator (KVO)

### دستهٔ Price-Transform / Support-Resistance
81. Typical Price (HLC/3)
82. Median Price (HL/2)
83. Weighted Close (HLCC/4)
84. Heikin Ashi
85. Pivot Points (classic/Fibonacci/Camarilla/Woodie)
86. Fibonacci Retracement/Extension
87. Coppock (bull-market bottom finder)

### دستهٔ Cycle / DSP / Ehlers (پیشرفته و کمیاب — قلبِ اشتباهِ رایج #۳)
منابع: mesasoftware.com (John Ehlers technical papers)، davenewberg EhlersCodes،
thinkorswim studies library، Ehlers کتاب‌های "Cybernetic Analysis"، "Rocket Science
for Traders"، "Cycle Analytics for Traders".
88. Super Smoother Filter (Ehlers 2-pole Butterworth)
89. Roofing Filter (HP + Super Smoother)
90. MAMA — MESA Adaptive Moving Average
91. FAMA — Following Adaptive MA
92. Cyber Cycle (Ehlers)
93. Center of Gravity Oscillator (Ehlers CG)
94. Ehlers Fisher Transform
95. Inverse Fisher Transform (of RSI/CCI)
96. Sine Wave Indicator (Ehlers)
97. Even Better Sine Wave (Cycle Analytics)
98. Instantaneous Trendline (Ehlers)
99. Hilbert Transform — Dominant Cycle Period
100. Homodyne Discriminator (dominant cycle)
101. Dual Differentiator (cycle period)
102. Phase Accumulation (cycle period)
103. Adaptive RSI (Ehlers, cycle-tuned)
104. Adaptive Stochastic (Ehlers)
105. Adaptive CCI (Ehlers)
106. Laguerre Filter (Ehlers)
107. Laguerre RSI (Ehlers)
108. Decycler (Ehlers high-pass removal)
109. Decycler Oscillator
110. Correlation Trend Indicator (CTI, Ehlers)
111. Reverse EMA (Ehlers)
112. Predictive Moving Average (Ehlers 7-bar WMA pair)
113. Stochastic MAMA
114. Empirical Mode Decomposition (Ehlers EMD)
115. Bandpass Filter (Ehlers)
116. High-Pass Filter (Ehlers 1-pole/2-pole)
117. Two-Pole / Three-Pole Super Smoother
118. Ehlers Distance Coefficient Filter (median/nonlinear)
119. Autocorrelation Periodogram (Ehlers)
120. MESA Momentum / MESA Cycle

### دستهٔ Statistical / Regression / Fractal (کمیاب و ریاضی‌محور)
121. Rolling Z-Score (موجود — پایه)
122. Rolling Linear-Regression Slope (موجود — پایه)
123. Rolling Pearson Correlation (price vs time)
124. R² of Linear Regression (goodness-of-fit)
125. Rolling Skewness
126. Rolling Kurtosis
127. Rolling Variance / Std
128. Rolling Median (robust)
129. Rolling MAD (Median Absolute Deviation)
130. Hurst Exponent (rescaled range R/S)
131. Fractal Dimension Index (FDI)
132. Fractal Adaptive MA (FRAMA, Ehlers)
133. Kaufman Adaptive MA (KAMA)
134. Variable Index Dynamic Average (VIDYA, Chande)
135. Jurik Moving Average (JMA — نزدیک‌سازی)
136. T3 Moving Average (Tillson)
137. Zero-Lag EMA (ZLEMA)
138. Zero-Lag MACD
139. Double EMA (DEMA)
140. Triple EMA (TEMA)
141. Arnaud Legoux MA (ALMA)
142. McGinley Dynamic
143. Ehlers Modified RSI (smoothed)
144. Regression Channel Slope Normalized
145. Entropy (Shannon, rolling of returns)

### دستهٔ Structure / Price-Action / Williams (نادرِ ساختاری)
146. Williams Fractals (up/down fractal points)
147. Fractal Chaos Bands
148. Bill Williams Market Facilitation Index (MFI-BW)
149. Zig Zag (swing structure)
150. Swing High/Low detector
151. Donchian Midline (channel center)
152. Supertrend (ATR-based)
153. Half-Trend
154. QQE — Quantitative Qualitative Estimation
155. Waddah Attar Explosion (MACD+BB volatility)
156. Range Filter
157. Chandelier Exit (long/short)
158. Camarilla Pivots
159. Woodie Pivots
160. Fibonacci Pivots
161. Central Pivot Range (CPR)
162. VWAP (session, tick-volume proxy for XAU)
163. Anchored VWAP
164. Rolling VWAP
165. Elder Impulse System (EMA slope + MACD-hist)
166. Schaff Trend Cycle (STC)
167. Connors RSI (RSI + streak + PctRank)
168. Balance of Power (BOP)
169. Gopalakrishnan Range Index (GAPO)
170. Ergodic Oscillator (TSI-based)

*(مرحله ۱ کامل شد — ~۱۷۰ اندیکاتورِ خام. مراحلِ ۲–۴ و variants در ادامه.)*

---

## مرحله ۲ — جستجوی روسی (Русскоязычные источники)

منابع: mql5.com/ru/code، litefinance.org/ru/blog، clusterdelta.com/ru/indicators،
fxssi.net (sentiment)، smart-lab.ru، admiralmarkets.com/ru، forexxx4all.ru.
تمرکزِ جامعهٔ روسی: کلاستر/دلتا/حجمِ افقی، Gann، VSA، سطوح.
(فقط مواردی که در مرحله ۱ نبودند — برای پرهیز از تکرار.)

### Volume-Delta / Order-Flow (سبکِ کلاستریِ روسی — بسیار پرطرفدار برای XAU)
171. CVD — Cumulative Volume Delta (дельта кумулятивного объёма)
172. Delta (bid/ask volume delta — پروکسی با up/down tick)
173. Volume Profile (профиль объёма — توزیعِ حجم روی قیمت)
174. VPOC — Volume Point of Control
175. Value Area High / Low (VAH/VAL)
176. Market Profile TPO (Time Price Opportunity)
177. Cluster Imbalance (دیس‌بالانسِ کلاستر)
178. Cumulative Delta Divergence (واگراییِ دلتا با قیمت)
179. Footprint Imbalance ratio
180. Better Volume (کاربردیِ حجمِ روسی)

### Gann / هندسی (مکتبِ گان — پرطرفدارِ روسی)
181. Gann HiLo Activator
182. Gann Fan (زوایای گان: 1x1, 2x1, …)
183. Gann Grid / Square of 9 levels
184. Gann Swing Oscillator
185. Gann Trend Detector

### VSA / Wyckoff (تحلیلِ حجم-اسپرد)
186. VSA No-Demand / No-Supply bar detector
187. VSA Effort vs Result (spread×volume)
188. Wyckoff Wave (accumulation/distribution phase)
189. Weis Wave Volume (موجِ ویس)
190. Effort Index (spread-normalized volume)

### سطوح و کانالِ روسی (نادر)
191. Fractal Levels (سطوحِ فراکتالِ ویلیامز به‌عنوان S/R)
192. Round-Number / Big-Figure levels (سطوحِ رُند — مهم برای XAU: 2000, 2050…)
193. Murray Math Levels (سطوحِ ماری)
194. Fibo Levels auto (اتوفیبو روی سوئینگِ آخر)
195. Session High/Low (Asia/London/NY — مهم برای طلا)
196. Previous Day/Week High-Low (PDH/PDL/PWH/PWL)
197. Opening Range (بازهٔ بازگشاییِ سشن)
198. ZigZag Fibo Projection
199. Support/Resistance by pivots density (خوشه‌بندیِ اکسترمم‌ها)
200. ATR-based Dynamic S/R

### اسیلاتورهای روسیِ کمیاب
201. RSI Divergence detector (تشخیصِ خودکارِ واگرایی)
202. MACD Divergence detector
203. Stochastic Divergence detector
204. TDI — Traders Dynamic Index (RSI + BB + سیگنال)
205. RSX (Jurik-smoothed RSI — بسیار محبوب روسی)
206. WPR smoothed (Williams %R هموارشده)
207. Stochastic of RSI of ROC (ترکیبی)
208. Composite Momentum (میانگینِ چند اسیلاتورِ نرمال‌شده)
209. Sentiment Ratio (نسبتِ خریدار/فروشندهٔ FXSSI — پروکسیِ داخلی)
210. Bulls/Bears Power اصلاح‌شده (Elder روسی)

*(مرحله ۲ کامل — تا اینجا ~۲۱۰ اندیکاتورِ خام.)*

---

## مرحله ۳ — جستجوی چینی (中文技术指标)

منبعِ اصلی: joinquant.com دیکشنریِ کاملِ اندیکاتورهای بومیِ چینی (فرمول‌های
通达信/东方财富/同花顺). بعلاوه zhihu، baidu baike، futunn. جامعهٔ چینی ده‌ها
اندیکاتورِ بومیِ کمیاب دارد که در منابعِ غربی نیستند — دقیقاً هدفِ اشتباهِ رایج #۳.
نکته: XAU حجمِ واقعی ندارد ⇒ حجم‌محورها با **tick-volume proxy** یا صرفِ‌نظر.

### 超买超卖型 (Overbought/Oversold — بومیِ چینی)
211. ACCER — 幅度涨速 (شتابِ دامنه؛ شیبِ نرمال‌شده)
212. ADTM — 动态买卖气 (Dynamic Buy/Sell Power، بازهٔ −1..+1)
213. BIAS — 乖离率 (نرخِ انحراف از MA؛ N1/N2/N3)
214. BIAS_QL — 乖离率 سنتی
215. BIAS36 — 三六乖离
216. CYF — 市场能量 (Market Energy 0..100)
217. DKX — 多空线 (Bull-Bear Line + سیگنالِ MA)
218. KD — تصادفیِ KD (بدونِ J)
219. KDJ — تصادفیِ KDJ (K/D/J)
220. SKDJ — 慢速KDJ (تصادفیِ آهسته)
221. OSC — 变动速率线 (Oscillator = close − MA)
222. UDL — 引力线 (Gravity Line میانگینِ چند BIAS)
223. WR — 威廉指标 (Williams %R چینی)
224. LWR — LWR威廉 (نسخهٔ هموارشدهٔ WR)
225. TAPI — 加权指数成交值
226. FSL — 分水岭 (Watershed؛ ترکیبِ EXPMA)
227. MARSI — 相对强弱平均线 (RSI هموارشده)

### 趋势型 (Trend — بومیِ چینی)
228. CYE — 市场趋势 (Market Trend، دو خطِ سریع/کند)
229. DBQR — 对比强弱 (قدرتِ نسبیِ مقایسه‌ای)
230. DMA — 平均差 (تفاضلِ دو MA + سیگنال)
231. DPO — 区间震荡线 (Detrended Price Oscillator چینی)
232. GDX — 鬼道线 (Ghost-Path؛ کانالِ تطبیقی)
233. JLHB — 绝路航标 (No-Way-Out؛ سیگنالِ نوسانی)
234. JS — 加速线 (Acceleration Line)
235. QACD — 快速异同平均 (MACD سریع)
236. QR — 强弱指标 (Power/Weakness)
237. VMACD — 量平滑异同 (MACD حجمی، tick-proxy)
238. VPT — 量价曲线 (Volume-Price Trend)
239. WVAD — 威廉变异离散量 (Williams VAD)

### 能量型 (Energy — بومیِ چینی)
240. BRAR — 情绪指标 (BR + AR؛ احساساتِ بازار)
241. CR — 带状能量线 (Band Energy + چند MA)
242. CYR — 市场强弱 (نرخِ رشدِ price×vol)
243. MASS — 梅斯线 (Mass Index)
244. PCNT — 幅度比 ((close−ref)/close×100)
245. PSY — 心理线 (Psychological Line، نسبتِ روزهای up)

### 均线/路径型 (MA & Channel — بومیِ چینی)
246. AMV — 成本价均线 (میانگینِ قیمتِ تمام‌شده، وزنِ حجم)
247. BBI — 多空均线 (میانگینِ MA3/6/12/24)
248. EXPMA — 指数平均线 (جفتِ EMA سریع/کند)
249. BBIBOLL — 多空布林线 (BBI + باندِ std)
250. VMA — 变异平均线 (MA روی (H+L+C+O)/4)
251. ENE — 轨道线 (Envelope بالا/پایین درصدی)
252. MIKE — 麦克支撑压力 (سطوحِ MIKE؛ WeakS/MidS/StrongS/…)
253. PBX — 瀑布线 (Waterfall؛ چند MA/EMA ترکیبی)
254. XS / XS2 — 薛斯通道 (کانالِ Xue تطبیقی)
255. VIDYA — واریانتِ 变异平均 (Chande VIDYA — پیوند با ۱۳۴)

### 特色/复合型 (Special/Composite — بومیِ چینی)
256. AROON — 阿隆 (چینی؛ Up/Down/Osc)
257. TBP — 趋势平衡点 (Trend Balance Point، DeMark-مانند)
258. CDP — 逆势操作 (CDP + AH/NH/NL/AL سطوحِ روزانه)
259. ZLMM — 主力买卖 (Main-Force Buy/Sell، دو خطِ MTM هموار)
260. CYW — 主力控盘 (Main-Force Control؛ سنجشِ فشار)
261. CYS — 市场盈亏 (Market Profit/Loss = close − 13-EMA-قیمتِ میانگین)
262. ZBCD — 准备抄底 (Bottom-Prep؛ اکسترمم-محور)
263. BDZX — 波段之星 (Band-Star؛ CCI-محورِ نوسانی)
264. CJDX — 超级短线 (Super-Short؛ ترکیبِ MACD/EMA)
265. JAX — 济安线 (JAX؛ MA غیرخطیِ تطبیقی)
266. ZX / PUCU — 重心线/逆时钟 (Gravity/Counter-clockwise curve)

*(مرحله ۳ کامل — تا اینجا ~۲۶۶ اندیکاتورِ خام.)*

---

## مرحله ۴ — Deep-web / وبلاگ‌ها / کتابخانه‌های اپن‌سورس / فروشگاه MT4-MT5

منابع: github twopirllc/pandas-ta (لیستِ کاملِ ۲۰۲۴)، TA-Lib، mesasoftware، Dave
Newberg Ehlers codes، mql5.com market، forexstore/forex-station (فروشگاه‌های اندیکاتور)،
TradingView community scripts، gist master-lists. تمرکز: پرکردنِ شکاف تا ۴۰۰+ با
اندیکاتورهای کمیاب و variants.

### Momentum/Overlap تازه (pandas-ta که هنوز نداریم)
267. AO — Awesome Oscillator (median 5/34)
268. APO — Absolute Price Oscillator
269. BOP — Balance of Power
270. CFO — Chande Forecast Oscillator
271. CG — Center of Gravity (Ehlers)
272. Coppock Curve (اکنون فرمولی)
273. CTI — Correlation Trend Indicator (Ehlers)
274. DM — Directional Movement (خام +DM/−DM)
275. Inertia (RVI روی RVI + linreg)
276. PGO — Pretty Good Oscillator
277. PSL — Psychological Line (pandas نسخه)
278. PVO — Percentage Volume Oscillator (tick-proxy)
279. QQE — Quantitative Qualitative Estimation
280. RSX — Relative Strength Xtra (Jurik)
281. RVGI — Relative Vigor Index
282. SMI Ergodic (TSI-based)
283. Squeeze (TTM، Carter)
284. Squeeze Pro (سه‌سطحی)
285. TD Sequential (td_seq)
286. UO — Ultimate Oscillator (فرمولی)
287. FWMA — Fibonacci Weighted MA
288. HWMA — Holt-Winter MA
289. HWC — Holt-Winter Channel
290. PWMA — Pascal Weighted MA
291. SINWMA — Sine Weighted MA
292. SWMA — Symmetric Weighted MA
293. Midpoint / Midprice
294. WCP — Weighted Closing Price
295. HL2 / HLC3 / OHLC4 (price transforms)
296. VWMA — Volume Weighted MA (tick-proxy)
297. AMAT — Archer Moving Averages Trend
298. QStick
299. TTM Trend
300. PSAR (Parabolic SAR فرمولی)

### Volatility/Volume تازه
301. Aberration (کانالِ ۴-خطیِ ATR)
302. Acceleration Bands (accbands)
303. NATR — Normalized ATR
304. RVI — Relative Volatility Index
305. Ulcer Index (ui)
306. Elder Thermometer (thermo)
307. Price Distance (pdist)
308. AD — Accumulation/Distribution (ad)
309. ADOSC — A/D Oscillator (Chaikin)
310. AOBV — Archer OBV
311. EFI — Elder Force Index
312. PVR — Price Volume Rank
313. PVOL — Price × Volume
314. Chande Kroll Stop (cksp)

### Statistics/Performance-shape (کمیابِ ریاضی)
315. Entropy (shannon rolling)
316. Kurtosis (rolling)
317. Skew (rolling)
318. MAD — Mean Absolute Deviation (rolling)
319. Median (rolling)
320. Quantile (rolling)
321. Variance (rolling)
322. Stdev (rolling)
323. Drawdown (rolling peak-to-trough)
324. Log Return / Percent Return (rolling)
325. TOS Stdev-All (چند-باندِ std)

### Ehlers/DSP کاملِ Dave-Newberg codes (پیشرفتهٔ کمیاب)
326. EBSW — Even Better Sine Wave (ebsw)
327. SSF — Super Smoother Filter (ssf 2/3-pole)
328. Reflex (Ehlers 2020)
329. TrendFlex (Ehlers 2020)
330. Ehlers Stochastic (adaptive)
331. Ehlers CCI (adaptive)
332. Ehlers RSI (adaptive/Laguerre)
333. Adaptive Laguerre Filter
334. MESA Sine/Lead
335. Sinewave + LeadSine pair
336. Dominant Cycle (Autocorrelation Periodogram)
337. Ehlers Roofing RSI
338. Ehlers Deviation-Scaled MA (DSMA)
339. Hann Window FIR (Ehlers)
340. Ehlers Elegant Oscillator

### Candlestick Patterns (TA-Lib/pandas-ta — ۶۰ الگو؛ اندیکاتورِ ساختاری)
از این پس هرکدام یک «تشخیص‌دهندهٔ الگو» (خروجی ۱−/۰/۱+) است — بسیار پرکاربرد برای فیلترِ ورود:
341. Doji  342. Doji Star  343. Dragonfly Doji  344. Gravestone Doji
345. Hammer  346. Inverted Hammer  347. Hanging Man  348. Shooting Star
349. Engulfing (bull/bear)  350. Harami  351. Harami Cross
352. Piercing  353. Dark Cloud Cover  354. Morning Star  355. Evening Star
356. Morning Doji Star  357. Evening Doji Star  358. 3 White Soldiers
359. 3 Black Crows  360. 3 Inside  361. 3 Outside  362. 3 Line Strike
363. Marubozu  364. Closing Marubozu  365. Spinning Top  366. High Wave
367. Belt Hold  368. Counterattack  369. Kicking  370. Tasuki Gap
371. Rising/Falling 3 Methods  372. Separating Lines  373. Matching Low
374. Tristar  375. Abandoned Baby  376. Advance Block  377. Stalled Pattern
378. Long-Legged Doji  379. Rickshaw Man  380. Takuri
381. Hikkake  382. Hikkake Modified  383. Homing Pigeon  384. Ladder Bottom
385. In-Neck  386. On-Neck  387. Thrusting  388. Unique 3 River
389. Upside Gap 2 Crows  390. X-Side Gap 3 Methods  391. 2 Crows
392. 3 Stars in South  393. Concealing Baby Swallow  394. Stick Sandwich
395. Breakaway  396. Gap Side-by-Side White  397. Identical 3 Crows
398. Kicking-by-Length  399. Long Line  400. Short Line  401. Mat Hold

### Composite / پروژه‌ای (ترکیب‌های نجات‌دهنده — قانونِ «همه‌چیز شناور»)
402. Elder Impulse System (EMA-slope × MACD-hist)
403. Connors RSI (RSI3 + streakRSI + PctRank)
404. Waddah Attar Explosion (MACD-diff × BB-width)
405. Vortex-ADX composite (فیلترِ روند)
406. KAMA-slope regime filter
407. Choppiness-gated trend (chop<38.2 ⇒ trend)
408. ATR-percentile volatility regime
409. RSI-of-Kaufman-ER (کارایی-محور)
410. Session-VWAP deviation z-score (XAU London/NY)

*(مرحله ۴ کامل — مجموعِ خامِ کاتالوگ‌شده: ~۴۱۰ اندیکاتور > هدفِ ۴۰۰. ✅)*

---

## جمع‌بندیِ جستجو (پیش از پیاده‌سازی)

- ۴ مرحلهٔ جستجو (EN/RU/CN/Deep-web) کامل شد.
- مجموعِ خام کاتالوگ‌شده: **~۴۱۰ اندیکاتور** (فراتر از هدفِ ۴۰۰).
- گامِ بعد: **پیاده‌سازیِ TypeScript در `web_tool/src/indicators/`** بدونِ look-ahead،
  ثبت در registry با پرچمِ **`active:false`** (پیش‌فرض غیرفعال؛ فقط با صداکردنِ یک لایه فعال).
- پیاده‌سازی مرحله‌به‌مرحله + build + commit/push هر فایل (طبقِ HARD-RULE).
