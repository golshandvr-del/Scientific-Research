"""
scalp_engine.py — موتورِ محاسباتیِ نو از صفر برای اسکالپینگ و نوسان‌گیری (پاسخِ User Note 2)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است. تعدادِ معامله در روز و Profit Factor هم هدف نیستند. **ما دنبالِ پول
> هستیم، نه آمارِ زیبا.** تنها تابعِ هدفِ کلِ پروژه: **سودِ خالصِ تجمعیِ پس از
> اسپرد/کمیسیون/اسلیپیج.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ چهار ارز (XAUUSD + EURUSD + AUDUSD + DXY/…)،
> نه فقط XAUUSD.**

================================================================================
انگیزهٔ ساخت (پاسخِ مستقیم به User Note 2):
  «موتور محاسباتی جدید از صفر برای اسکالپینگ و نوسان‌گیری بسازیم؟» — بله.
  موتورِ قدیمی (`backtest.py` + `capital_engine.py`) سه نقصِ کُشنده برای اسکالپینگِ
  فارکس داشت که مستقیماً باعثِ ruinِ S71/S72/S77 شد:

  ۱) **طلا-محور بودنِ لات:** capital_engine پیش‌فرض `CONTRACT_SIZE=100` (طلا) دارد؛
     اگر برای فارکس صریحاً contract=100_000 پاس داده نشود، لاتِ نجومی → ruin.
  ۲) **SL مبتنی بر ATRِ خام:** در اسکالپینگ ATR بسیار کوچک است؛ ریسکِ درصدی ثابت
     ⇒ لاتِ عظیم ⇒ چند ضررِ پیاپی ⇒ نابودی. S73 این را با SL ثابتِ pip حل کرد.
  ۳) **مدلِ هزینهٔ ناقص:** فقط اسپردِ ثابت مدل می‌شد؛ کمیسیون در capital_engine و
     **اسلیپیج اصلاً نبود**. در اسکالپینگ که سودِ هدف ۲–۵ pip است، این‌ها تعیین‌کنندهٔ
     مرگ‌وزندگی‌اند.

  این موتور از صفر و با فلسفهٔ «pip-native, cost-first, multi-asset» ساخته شده:
    • همه چیز بر حسبِ **pip** است (نه دلارِ خام قیمت) → مقیاسِ همهٔ دارایی‌ها یکسان.
    • هر دارایی مشخصاتِ واقعیِ خودش را دارد: pip_size, contract, pip_value, spread,
      commission, slippage. (جدولِ ASSETS پایین.)
    • **SL/TP اجباراً بر حسبِ pip** (نه ATRِ خام) → floorِ امنیتیِ لات همیشه فعال.
    • مدلِ هزینهٔ کامل: اسپرد (نصف‌اسپرد در ورود + نصف در خروج) + کمیسیون/لات +
      اسلیپیجِ ورود و خروج.
    • ریسکِ درصدی + کامپاند، با سقفِ ایمنیِ لات (max_lot_per_equity) → غیرِممکن
      شدنِ لاتِ نجومی حتی اگر SL خیلی کوچک باشد.
    • کاملاً forward-safe: ورود در open کندلِ بعد از سیگنال؛ SL/TP intrabar با
      قاعدهٔ بدترین‌حالت (SL مقدم بر TP هنگام ابهام).

  خروجی: یک DataFrameِ معاملات + آمارِ سرمایه‌محورِ کامل (net_profit, equity curve,
  maxDD, PF, Sharpe, avg_lot, هزینهٔ کل). این موتور تصمیمِ ورود نمی‌گیرد؛ فقط
  حسابداری می‌کند ⇒ هیچ look-ahead جدیدی وارد نمی‌کند.
================================================================================
"""
import numpy as np
import pandas as pd


# ------------------------------------------------------------------------------
# جدولِ مشخصاتِ واقعیِ دارایی‌ها (بروکرِ استانداردِ خرده‌فروشی)
#   pip        : اندازهٔ یک pip بر حسبِ قیمت (طلا: 0.10$؛ اکثرِ فارکس: 0.0001)
#   contract   : اندازهٔ ۱ لاتِ استاندارد (طلا: 100 اونس؛ فارکس: 100000 واحدِ پایه)
#   pip_value  : ارزشِ دلاریِ ۱ pip برای ۱ لاتِ استاندارد (= contract × pip)
#   spread_pip : اسپردِ نوعیِ رفت‌وبرگشت بر حسبِ pip
#   comm       : کمیسیونِ رفت‌وبرگشت به‌ازای هر لاتِ استاندارد (دلار)
#   slip_pip   : اسلیپیجِ نوعی (هر طرف) بر حسبِ pip
#
# ⚠️ مشخصاتِ طلا از «حسابِ واقعیِ کاربر» گرفته شده (User Note 2 — ۲۰۲۶/۰۷/۱۷):
#   • حجمِ ۰.۰۱ لات → مارجینِ ۰.۴۰$ (leverage بسیار بالا؛ در بک‌تستِ ۱۰k$ محدودیتِ
#     مارجین اصلاً فعال نمی‌شود، پس نادیده گرفته می‌شود).
#   • اسپردِ کلِ طلا = ۴۰ pip بر تعریفِ بروکر (۱pip=۰.۰۱$ حرکت) = ۰.۴۰$ حرکتِ قیمت.
#     چون در موتور pip=0.10 است، این معادلِ ۴.۰ pipِ موتور است (۴×۱۰$=۴۰$ برای ۱ لات).
#   • کمیسیونِ طلا = صفر.
#   این جایگزینِ فرضِ قدیمیِ (spread=2, comm=7) شد؛ اکنون بدبینانه‌تر و واقعی‌تر است.
# ------------------------------------------------------------------------------
ASSETS = {
    # ⭐ کالیبراسیونِ واقعیِ حسابِ کاربر (User Note): اسپردِ طلا = 0.33$/oz = 3.3 pip،
    #    کمیسیون صفر، slippage صفر (اسپردِ گزارش‌شده رفت‌وبرگشتِ کامل است).
    #    مدلِ قدیم spread_pip=4.0/slip=0.5 (=5.0pip) بود که ~۱.۵× بدبینانه‌تر از واقعیت بود.
    'XAUUSD': dict(file='data/XAUUSD_M15.csv', pip=0.10,   contract=100.0,     pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0),
    'EURUSD': dict(file='data/EURUSD_M15.csv', pip=0.0001, contract=100_000.0, pip_value=10.0, spread_pip=1.0, comm=7.0, slip_pip=0.3),
    'AUDUSD': dict(file='data/AUDUSD_M15.csv', pip=0.0001, contract=100_000.0, pip_value=10.0, spread_pip=1.2, comm=7.0, slip_pip=0.3),
    'USDCHF': dict(file='data/USDCHF_M15.csv', pip=0.0001, contract=100_000.0, pip_value=10.0, spread_pip=1.4, comm=7.0, slip_pip=0.3),
    # DXY داراییِ قابلِ‌معاملهٔ مستقیم نیست؛ به‌عنوانِ دارایی چهارم از AUDUSD استفاده می‌کنیم
    # مگر کاربر خلافش را بخواهد. (طبقِ DATA، چهار داراییِ اصلی: XAU/EUR/AUD + یکی از این‌ها.)
}

DEFAULT_CAPITAL = 10_000.0
DEFAULT_RISK_PCT = 1.0
MIN_LOT = 0.01
MAX_LOT = 100.0
# سقفِ ایمنی: حداکثر ارزشِ اسمیِ پوزیشن نسبت به equity (اهرمِ مؤثر). مانعِ لاتِ نجومی.
MAX_LOTS_PER_10K = 5.0    # حداکثر ۵ لاتِ استاندارد به‌ازای هر ۱۰٬۰۰۰$ equity


def load_data(path):
    """بارگذاریِ CSV با ستون‌های time,open,high,low,close,volume + ستونِ dt."""
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, asset,
                    max_hold=16, allow_overlap=False, be_trigger_pip=None,
                    trail_pip=None):
    """
    شبیه‌سازیِ اجرای معاملات بر حسبِ pip (forward-safe).

    پارامترها:
      df        : دیتافریمِ OHLC.
      long_sig  : آرایهٔ بولینِ هم‌طولِ df؛ True = سیگنالِ خرید روی این کندل.
      short_sig : مشابه برای فروش.
      sl_pip    : فاصلهٔ SL بر حسبِ pip (اسکالر یا آرایهٔ هم‌طولِ df).
      tp_pip    : فاصلهٔ TP بر حسبِ pip (اسکالر یا آرایه).
      asset     : نامِ دارایی (کلیدِ ASSETS) — برای pip_size و اسپرد/اسلیپیج.
      max_hold  : حداکثر کندلِ نگهداری؛ سپس بستن با close.
      allow_overlap : اگر False، تا بسته‌شدنِ معاملهٔ جاری ورودِ جدید نداریم.
      be_trigger_pip : اگر داده شود، وقتی سود به این حد رسید SL را به نقطهٔ ورود ببر (break-even).
      trail_pip : اگر داده شود، تریلینگ‌استاپ به فاصلهٔ این pip از اوجِ سود.

    خروجی: DataFrameِ معاملات با ستونِ کلیدیِ `pnl_pip` (سود/زیانِ خالصِ pip پس از
            اسپرد+اسلیپیج؛ کمیسیون در لایهٔ سرمایه اعمال می‌شود).
    """
    cfg = ASSETS[asset]
    pip = cfg['pip']
    spread = cfg['spread_pip']
    slip = cfg['slip_pip']

    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(df)

    long_sig = np.asarray(long_sig, dtype=bool)
    short_sig = np.asarray(short_sig, dtype=bool)
    if np.isscalar(sl_pip):
        sl_pip = np.full(n, float(sl_pip))
    else:
        sl_pip = np.asarray(sl_pip, dtype=np.float64)
    if np.isscalar(tp_pip):
        tp_pip = np.full(n, float(tp_pip))
    else:
        tp_pip = np.asarray(tp_pip, dtype=np.float64)

    # هزینهٔ رفت‌وبرگشتِ ثابت بر حسبِ pip (اسپردِ کامل + اسلیپیجِ دو طرف)
    cost_pip = spread + 2.0 * slip

    trades = []
    busy_until = -1

    # ترتیبِ سیگنال‌ها بر حسبِ اندیس (long و short با هم؛ اگر هر دو، long مقدم فرضی)
    sig_bars = np.where(long_sig | short_sig)[0]
    for si in sig_bars:
        entry_bar = si + 1
        if entry_bar >= n:
            continue
        if not allow_overlap and entry_bar <= busy_until:
            continue
        direction = 'long' if long_sig[si] else 'short'

        sl_d = sl_pip[si] * pip
        tp_d = tp_pip[si] * pip
        if sl_d <= 0:
            continue

        raw_entry = o[entry_bar]
        # اسلیپیجِ ورود: خرید بدتر (بالاتر)، فروش بدتر (پایین‌تر)
        if direction == 'long':
            fill = raw_entry + slip * pip
            sl_price = fill - sl_d
            tp_price = fill + tp_d
        else:
            fill = raw_entry - slip * pip
            sl_price = fill + sl_d
            tp_price = fill - tp_d

        outcome = None
        exit_bar = None
        exit_price = None
        cur_sl = sl_price
        peak_favor = 0.0  # بیشترین حرکتِ مطلوب بر حسبِ قیمت (برای BE/trail)

        end = min(entry_bar + max_hold, n)
        for j in range(entry_bar, end):
            hi, lo = h[j], l[j]

            # ⚠️ اصلاحِ باگِ look-ahead (نشستِ SHORT-MA):
            # ابتدا exit را با cur_sl/tp که از کندلِ *قبلی* تعیین شده چک می‌کنیم؛
            # سپس در انتهای کندل، peak_favor و trailing/BE را برای کندل‌های *بعدی*
            # به‌روز می‌کنیم. در غیرِ این‌صورت trailing روی extremumِ همان کندل قفل
            # می‌شد و خروجِ سودِ نجومیِ جعلی در همان کندل رخ می‌داد (look-ahead).
            if direction == 'long':
                hit_sl = lo <= cur_sl
                hit_tp = hi >= tp_price
            else:
                hit_sl = hi >= cur_sl
                hit_tp = lo <= tp_price

            if hit_sl and hit_tp:
                outcome = 'loss'; exit_bar = j; exit_price = cur_sl; break  # ابهام → بدترین
            elif hit_tp:
                outcome = 'win'; exit_bar = j; exit_price = tp_price; break
            elif hit_sl:
                outcome = 'loss'; exit_bar = j; exit_price = cur_sl; break

            # به‌روزرسانیِ peak_favor و trailing/BE برای کندلِ بعدی (پس از چکِ exit)
            # ⚠️ اصلاحِ دومِ باگِ look-ahead: در *کندلِ ورود* trailing/BE فعال نمی‌شود.
            # درونِ همان کندلی که وارد شده‌ایم، ترتیبِ برخوردِ high/low نامعلوم است؛
            # اگر peak_favor را با extremumِ همین کندل به‌روز کنیم و trailing را جابجا
            # کنیم، سودِ جعلی (bars_held=0 با pnl نجومی) رخ می‌دهد. پس trailing فقط
            # از کندلِ *بعد* از ورود اثر می‌کند (استانداردِ صحیحِ بک‌تست).
            if j == entry_bar:
                continue
            if direction == 'long':
                favor = hi - fill
                if favor > peak_favor:
                    peak_favor = favor
                if be_trigger_pip is not None and peak_favor >= be_trigger_pip * pip:
                    cur_sl = max(cur_sl, fill)
                if trail_pip is not None and peak_favor > 0:
                    cur_sl = max(cur_sl, fill + peak_favor - trail_pip * pip)
            else:
                favor = fill - lo
                if favor > peak_favor:
                    peak_favor = favor
                if be_trigger_pip is not None and peak_favor >= be_trigger_pip * pip:
                    cur_sl = min(cur_sl, fill)
                if trail_pip is not None and peak_favor > 0:
                    cur_sl = min(cur_sl, fill - peak_favor + trail_pip * pip)

        if outcome is None:
            exit_bar = end - 1
            exit_price = c[exit_bar]

        # اسلیپیجِ خروج
        if direction == 'long':
            exit_fill = exit_price - slip * pip
            gross_price = exit_fill - fill
        else:
            exit_fill = exit_price + slip * pip
            gross_price = fill - exit_fill

        # سود/زیانِ خالص بر حسبِ pip = حرکتِ قیمت/pip − اسپرد (اسلیپیج قبلاً در fill لحاظ شد)
        pnl_pip = gross_price / pip - spread
        # ⚠️ اصلاحِ باگِ گزارشیِ WR (s117/s118): برچسبِ outcome باید بر اساسِ *سود/زیانِ
        # واقعی* باشد، نه صرفِ اینکه کدام سطح (TP/SL) خورد. یک trailing-stop یا max_hold
        # که در ناحیهٔ سود بسته می‌شود یک «برد» است، نه «باخت». پیش از این، هر خروجِ
        # غیرِ TP به‌غلط 'loss' برچسب می‌خورد و با TPِ بزرگ WR گزارشی ≈۰ می‌شد (در حالی
        # که سودِ خالص مثبت بود). این فقط عددِ گزارشیِ WR را تصحیح می‌کند؛ سودِ خالص و
        # منطقِ معامله دست‌نخورده‌اند (net از pnl_pip می‌آید، نه از outcome).
        outcome = 'win' if pnl_pip > 0 else 'loss'

        busy_until = exit_bar
        trades.append({
            'signal_bar': int(si),
            'entry_bar': int(entry_bar),
            'exit_bar': int(exit_bar),
            'direction': direction,
            'entry_price': fill,
            'exit_price': exit_price,
            'outcome': outcome,
            'pnl_pip': float(pnl_pip),
            'sl_pip': float(sl_pip[si]),
            'bars_held': int(exit_bar - entry_bar),
        })

    return pd.DataFrame(trades)


def run_capital(trades, asset, initial_capital=DEFAULT_CAPITAL,
                risk_pct=DEFAULT_RISK_PCT, compounding=True, weights=None):
    """
    لایهٔ حسابداریِ سرمایه: تبدیلِ pnl_pip به دلار با ریسکِ درصدیِ ثابت و لاتِ واقعی.

      • برای هر معامله، لات طوری تعیین می‌شود که اگر SL کامل بخورد،
        دقیقاً risk_pct% از equityِ جاری از دست برود (پیش از کمیسیون).
      • لات به [MIN_LOT, MAX_LOT] و همچنین به سقفِ اهرمِ MAX_LOTS_PER_10K کلیپ می‌شود
        → لاتِ نجومی غیرِممکن است (رفعِ ریشه‌ایِ ruinِ S71/S72/S77).
      • کمیسیونِ رفت‌وبرگشت به‌ازای هر لات کسر می‌شود.
    """
    cfg = ASSETS[asset]
    pip_value = cfg['pip_value']
    comm = cfg['comm']

    if trades is None or len(trades) == 0:
        return _empty_stats(initial_capital), np.array([initial_capital])

    tr = trades.sort_values('exit_bar').reset_index(drop=True)
    n = len(tr)
    if weights is None:
        weights = np.ones(n)
    else:
        weights = np.asarray(weights, dtype=np.float64)
        weights = np.where(weights > 0, weights, 1.0)

    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    eq_curve = [initial_capital]
    r_returns = []
    lots_used = []
    wins = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_commission = 0.0
    ruined_at = None

    for i in range(n):
        pnl_pip = tr['pnl_pip'].iloc[i]
        sl_p = tr['sl_pip'].iloc[i]
        w = weights[i]

        risk_base = equity if compounding else initial_capital
        risk_dollars = risk_base * (risk_pct * w) / 100.0

        # زیانِ دلاریِ SL برای ۱ لات = sl_pip × pip_value
        loss_per_lot = sl_p * pip_value
        if loss_per_lot <= 0:
            lots = MIN_LOT
        else:
            lots = risk_dollars / loss_per_lot
        # سقفِ اهرم: مانعِ لاتِ نجومی حتی با SL خیلی کوچک
        lot_cap = MAX_LOTS_PER_10K * (equity / 10_000.0)
        lots = min(lots, max(lot_cap, MIN_LOT))
        lots = float(np.clip(round(lots, 2), MIN_LOT, MAX_LOT))
        lots_used.append(lots)

        pnl_dollars = pnl_pip * pip_value * lots
        commission = comm * lots
        net = pnl_dollars - commission
        total_commission += commission

        if net >= 0:
            gross_profit += net
        else:
            gross_loss += -net

        equity_before = equity
        equity += net
        eq_curve.append(equity)
        if tr['outcome'].iloc[i] == 'win':
            wins += 1
        r_returns.append(net / equity_before if equity_before > 0 else 0.0)

        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
        if equity <= 0 and ruined_at is None:
            ruined_at = i
            break

    eq_curve = np.array(eq_curve)
    net_profit = equity - initial_capital
    r_returns = np.array(r_returns)
    sharpe = (r_returns.mean() / r_returns.std() * np.sqrt(len(r_returns))
              if len(r_returns) > 1 and r_returns.std() > 0 else 0.0)
    max_dd_pct = (max_dd / peak * 100.0) if peak > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    stats = {
        'asset': asset,
        'initial_capital': initial_capital,
        'final_equity': equity,
        'net_profit': net_profit,
        'return_pct': net_profit / initial_capital * 100.0,
        'n_trades': n if ruined_at is None else ruined_at + 1,
        'win_rate': wins / n * 100.0 if n else 0.0,
        'max_dd': max_dd,
        'max_dd_pct': max_dd_pct,
        'profit_factor': profit_factor,
        'sharpe': sharpe,
        'total_commission': total_commission,
        'avg_lot': float(np.mean(lots_used)) if lots_used else 0.0,
        'net_over_dd': net_profit / abs(max_dd) if max_dd < 0 else float('inf'),
        'ruined': ruined_at is not None,
    }
    return stats, eq_curve


def run_capital_pertrade(trades, asset, df=None, initial_capital=DEFAULT_CAPITAL,
                         risk_pct=DEFAULT_RISK_PCT, compounding=False, weights=None):
    """
    مثلِ run_capital اما علاوه بر (stats, equity) یک DataFrameِ per-trade با
    ستون‌های ['exit_bar', 'net_usd', 'dt'] برمی‌گرداند تا تحلیلِ سودِ خالصِ
    روزانه/هفتگی/ماهانه (engine/periodic_pnl.py) ممکن شود.

    اگر df داده شود و ستونِ 'time' (unix) داشته باشد، 'dt' از exit_bar استخراج می‌شود.
    این تابع منطقِ حسابداری را دقیقاً از run_capital کپی می‌کند تا هیچ ناهمگامی
    عددی با run_capital نداشته باشد (پاسخ به User Note: «سایت و تست هم‌گام شوند»).
    """
    cfg = ASSETS[asset]
    pip_value = cfg['pip_value']; comm = cfg['comm']
    if trades is None or len(trades) == 0:
        empty = pd.DataFrame(columns=['exit_bar', 'net_usd', 'dt'])
        return _empty_stats(initial_capital), np.array([initial_capital]), empty

    stats, eq_curve = run_capital(trades, asset, initial_capital=initial_capital,
                                  risk_pct=risk_pct, compounding=compounding, weights=weights)

    tr = trades.sort_values('exit_bar').reset_index(drop=True)
    n = len(tr)
    w = np.ones(n) if weights is None else np.where(np.asarray(weights, float) > 0,
                                                    np.asarray(weights, float), 1.0)
    equity = initial_capital
    rows = []
    for i in range(n):
        pnl_pip = tr['pnl_pip'].iloc[i]; sl_p = tr['sl_pip'].iloc[i]
        risk_base = equity if compounding else initial_capital
        risk_dollars = risk_base * (risk_pct * w[i]) / 100.0
        loss_per_lot = sl_p * pip_value
        lots = MIN_LOT if loss_per_lot <= 0 else risk_dollars / loss_per_lot
        lot_cap = MAX_LOTS_PER_10K * (equity / 10_000.0)
        lots = min(lots, max(lot_cap, MIN_LOT))
        lots = float(np.clip(round(lots, 2), MIN_LOT, MAX_LOT))
        net = pnl_pip * pip_value * lots - comm * lots
        equity += net
        rows.append({'exit_bar': int(tr['exit_bar'].iloc[i]), 'net_usd': float(net)})
        if equity <= 0:
            break
    pt = pd.DataFrame(rows)
    if df is not None and 'time' in df.columns and len(pt):
        idx = np.clip(pt['exit_bar'].values, 0, len(df) - 1)
        pt['dt'] = pd.to_datetime(df['time'].values[idx], unit='s', utc=True)
    return stats, eq_curve, pt


def _empty_stats(initial_capital):
    return {
        'asset': '-', 'initial_capital': initial_capital, 'final_equity': initial_capital,
        'net_profit': 0.0, 'return_pct': 0.0, 'n_trades': 0, 'win_rate': 0.0,
        'max_dd': 0.0, 'max_dd_pct': 0.0, 'profit_factor': 0.0, 'sharpe': 0.0,
        'total_commission': 0.0, 'avg_lot': 0.0, 'net_over_dd': 0.0, 'ruined': False,
    }


def summary_line(name, s):
    return (f"{name:8s}: netP={s['net_profit']:+9.0f}$ ({s['return_pct']:+7.1f}%)  "
            f"n={s['n_trades']:5d}  WR={s['win_rate']:4.1f}%  "
            f"maxDD={s['max_dd_pct']:5.1f}%  PF={s['profit_factor']:.2f}  "
            f"Sh={s['sharpe']:5.2f}  avgLot={s['avg_lot']:.2f}"
            + ("  [RUINED]" if s['ruined'] else ""))
