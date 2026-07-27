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
