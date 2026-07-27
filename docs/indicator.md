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

*(ادامهٔ فهرست در مراحلِ ۲–۴ و نیز ژرف‌سازیِ خانوادگی — variants — در بخشِ پیاده‌سازی.)*
