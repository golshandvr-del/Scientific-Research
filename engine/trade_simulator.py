# -*- coding: utf-8 -*-
"""
trade_simulator.py — شبیه‌سازِ رویداد-محورِ کاربرِ حسابِ دمو (Event-Driven Simulator)
================================================================================

فلسفه (پاسخ به کشفِ کاربر «سیگنالِ متناقض در ۳۰ ثانیه»):
--------------------------------------------------------------------------------
بک‌تستِ قدیمیِ پروژه «برداری» (vectorized) بود: هر سیگنال را جدا و مستقل حساب می‌کرد،
با این فرضِ غلط که می‌توان همزمان در ده‌ها معامله بود و سیگنال‌ها هیچ‌وقت با هم تداخل
ندارند. این دقیقاً چیزی است که در حسابِ دموِ واقعی شکست خورد: سایت هم‌زمان ۲۰ لایه را
صدا می‌زد و هرکدام نظرِ متفاوتی می‌دادند ⇒ لانگ/شورت/خنثی در ۳۰ ثانیه.

این ماژول یک بک‌تسترِ *رویداد-محورِ حالت‌دار* (stateful, event-driven) است که دقیقاً مثلِ
یک کاربرِ واقعیِ حسابِ دمو رفتار می‌کند:

  • فقط یک حساب و یک موجودی دارد.
  • در هر لحظه حداکثر یک پوزیشنِ باز دارد (قابلِ تنظیم: allow_pyramiding=False).
  • تا وقتی در یک معامله است، سیگنالِ متناقض را نادیده می‌گیرد ⇒ «تناقضِ سیگنال» حذف.
  • کندل‌به‌کندل و سببی (causal) جلو می‌رود؛ هیچ نگاهی به آینده ندارد.
  • TP/SL را طبقِ adviceِ استراتژی جابه‌جا می‌کند (trailing) یا معامله را زودتر می‌بندد.
  • هزینهٔ واقعیِ حسابِ کاربر را اعمال می‌کند (از market_spec: اسپرد+لغزش، contract، مارجین).

مزیتِ جانبیِ کلیدی:
  چون فقط یک حساب و یک پوزیشن هست، مشکلِ «همپوشانیِ لایه‌ها» خودبه‌خود حل می‌شود —
  دیگر لازم نیست دستی درصدِ همپوشانی حساب کنیم؛ واقعیتِ حساب آن را اعمال می‌کند.

خروجی:
  DataFrameِ معاملاتِ واقعی با ستون‌هایِ سازگار با engine/rqs.py:
    pnl_pip, sl_pip, tp_pip, outcome, exit_bar, entry_bar, side, entry_price,
    exit_price, exit_reason, bars_held, pnl_usd(بر ۱ لات), equity_after
  ⇒ می‌توان مستقیم به compute_rqs(...) داد.

--------------------------------------------------------------------------------
قراردادِ استراتژی (Strategy Protocol):
--------------------------------------------------------------------------------
هر استراتژی یک شیء (یا تابع‌سازِ) است که این متد را دارد:

    advise(ctx) -> dict یا None

که در آن ctx یک StrategyContext است (کندل‌های تا این لحظه + وضعیتِ پوزیشنِ فعلی).
خروجیِ advise یکی از این‌هاست:

  • None  یا {'action': 'FLAT'}         ⇒ کاری نکن / خنثی
  • {'action': 'LONG',  'sl': price, 'tp': price}   ⇒ اگر پوزیشن باز نیست، لانگ باز کن
  • {'action': 'SHORT', 'sl': price, 'tp': price}   ⇒ اگر پوزیشن باز نیست، شورت باز کن
  • {'action': 'MANAGE', 'sl': price, 'tp': price}  ⇒ اگر پوزیشن باز است، SL/TP را به‌روزرسانی کن (trailing)
  • {'action': 'CLOSE'}                 ⇒ اگر پوزیشن باز است، همین حالا (open کندلِ بعد) ببند

نکته: sl/tp بر حسبِ *قیمت* (نه pip) داده می‌شوند تا با adviceِ سایت یکی باشند.
اگر استراتژی بخواهد بر حسبِ pip بدهد، از helperهای price_from_pips استفاده کند.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import market_spec as MS  # noqa: E402


# ============================ مشخصاتِ دارایی ============================
def asset_spec(asset):
    """برمی‌گرداند: dict(pip, contract, spread_price, slip_price, cost_price, margin)."""
    a = asset.upper()
    if a == 'XAUUSD':
        return dict(
            pip=MS.XAU_PIP, contract=MS.XAU_CONTRACT_SIZE,
            spread_price=MS.XAU_SPREAD_PRICE, slip_price=MS.XAU_SLIPPAGE_PRICE,
            cost_price=MS.XAU_COST_PRICE, margin=MS.XAU_MARGIN_PER_LOT,
        )
    # فارکس (EURUSD و ...)
    pip = getattr(MS, 'EUR_PIP', 0.0001)
    contract = getattr(MS, 'EUR_CONTRACT_SIZE', 100_000.0)
    spread_pip = getattr(MS, 'EUR_SPREAD_PIP', 1.0)
    slip_pip = getattr(MS, 'EUR_SLIPPAGE_PIP', 0.3)
    spread_price = spread_pip * pip
    slip_price = slip_pip * pip
    return dict(
        pip=pip, contract=contract,
        spread_price=spread_price, slip_price=slip_price,
        cost_price=spread_price + slip_price,
        margin=getattr(MS, 'EUR_MARGIN_PER_LOT', 40.0),
    )


# ============================ Context ============================
class StrategyContext:
    """آنچه استراتژی در هر کندل می‌بیند — فقط گذشته (causal)."""
    __slots__ = ('df', 'i', 'asset', 'tf', 'position', 'spec')

    def __init__(self, df, i, asset, tf, position, spec):
        self.df = df          # کلِ DataFrame (اما استراتژی فقط باید تا i بخواند)
        self.i = i            # اندیسِ کندلِ *بسته‌شدهٔ* فعلی (تصمیم روی open کندلِ i+1 اجرا می‌شود)
        self.asset = asset
        self.tf = tf
        self.position = position   # None یا dict پوزیشنِ باز
        self.spec = spec

    # ---- helperهای سببی (فقط تا کندلِ i) ----
    def closes(self, n=None):
        c = self.df['close'].values[:self.i + 1]
        return c if n is None else c[-n:]

    def highs(self, n=None):
        h = self.df['high'].values[:self.i + 1]
        return h if n is None else h[-n:]

    def lows(self, n=None):
        low = self.df['low'].values[:self.i + 1]
        return low if n is None else low[-n:]

    def opens(self, n=None):
        o = self.df['open'].values[:self.i + 1]
        return o if n is None else o[-n:]

    def price(self):
        """آخرین قیمتِ بسته‌شده (close کندلِ i)."""
        return float(self.df['close'].values[self.i])

    def dt(self):
        return self.df['dt'].values[self.i] if 'dt' in self.df.columns else None

    def pips(self, n):
        """تبدیلِ n پیپ به فاصلهٔ قیمت."""
        return n * self.spec['pip']

    def in_position(self):
        return self.position is not None


# ============================ Simulator ============================
def simulate(df, strategy, asset, tf='M5',
             initial_capital=10000.0, risk_per_trade=1.0,
             allow_pyramiding=False, max_bars_hold=None,
             warmup=200, verbose=False):
    """
    اجرای شبیه‌سازیِ رویداد-محور.

    df        : DataFrame با ستون‌های time/open/high/low/close (+dt اختیاری)
    strategy  : شیئی با متدِ advise(ctx)->dict|None
    asset     : 'XAUUSD' / 'EURUSD' ...
    risk_per_trade : درصدِ سرمایه که در هر معامله ریسک می‌شود (برای اندازهٔ لات).
    allow_pyramiding : اگر False، تا پوزیشنِ باز هست سیگنالِ جدید نادیده گرفته می‌شود.
    warmup    : تعداد کندلِ ابتدایی که استراتژی برای اندیکاتورها لازم دارد.

    برمی‌گرداند: (trades_df, equity_curve)
    """
    spec = asset_spec(asset)
    pip = spec['pip']
    contract = spec['contract']
    cost_price = spec['cost_price']

    n = len(df)
    o = df['open'].values
    h = df['high'].values
    low = df['low'].values
    c = df['close'].values

    equity = float(initial_capital)
    equity_curve = [equity]
    trades = []
    position = None  # dict: side, entry_bar, entry_price, sl, tp, lots

    def open_position(side, entry_price, sl, tp, entry_bar):
        # اندازهٔ لات بر مبنایِ ریسکِ ثابت: risk% سرمایه ÷ فاصلهٔ SL بر حسبِ دلار
        sl_dist_price = abs(entry_price - sl) if sl is not None else None
        if sl_dist_price and sl_dist_price > 0:
            risk_usd = equity * (risk_per_trade / 100.0)
            lots = risk_usd / (sl_dist_price * contract)
            lots = max(0.01, round(lots, 2))
        else:
            lots = 0.01
        return dict(side=side, entry_bar=entry_bar, entry_price=entry_price,
                    sl=sl, tp=tp, lots=lots)

    def close_position(pos, exit_price, exit_bar, reason):
        nonlocal equity
        side = pos['side']
        raw_move = (exit_price - pos['entry_price']) if side == 'LONG' else (pos['entry_price'] - exit_price)
        # هزینهٔ رفت‌وبرگشت (یکبار، بر حسبِ قیمت) از حرکت کم می‌شود
        net_move = raw_move - cost_price
        pnl_pip = net_move / pip
        pnl_usd_per_lot = net_move * contract
        pnl_usd = pnl_usd_per_lot * pos['lots']
        equity += pnl_usd
        outcome = 'win' if net_move > 0 else 'loss'
        sl_pip = abs(pos['entry_price'] - pos['sl']) / pip if pos['sl'] is not None else 0.0
        tp_pip = abs(pos['tp'] - pos['entry_price']) / pip if pos['tp'] is not None else 0.0
        trades.append(dict(
            entry_bar=pos['entry_bar'], exit_bar=exit_bar,
            side=side, entry_price=pos['entry_price'], exit_price=exit_price,
            sl_pip=sl_pip, tp_pip=tp_pip, pnl_pip=pnl_pip,
            pnl_usd=pnl_usd_per_lot,        # سود بر ۱ لات (سازگار با run_capital)
            pnl_usd_sized=pnl_usd,          # سود با اندازهٔ لاتِ واقعی
            lots=pos['lots'], outcome=outcome,
            exit_reason=reason, bars_held=exit_bar - pos['entry_bar'],
            equity_after=equity,
        ))
        equity_curve.append(equity)

    # ---- حلقهٔ اصلی: کندل i بسته می‌شود، تصمیم روی open کندلِ i+1 اجرا می‌شود ----
    for i in range(warmup, n - 1):
        # ۱) اگر پوزیشن باز است، اول intrabar SL/TP کندلِ i+1 را چک کن (مدیریتِ ریسک اولویت دارد)
        if position is not None:
            nb = i + 1
            hit = _check_sl_tp_hit(position, o[nb], h[nb], low[nb], c[nb])
            if hit is not None:
                exit_price, reason = hit
                close_position(position, exit_price, nb, reason)
                position = None

        # ۲) از استراتژی advice بگیر (بر مبنایِ کندلِ بسته‌شدهٔ i)
        ctx = StrategyContext(df, i, asset, tf, position, spec)
        try:
            adv = strategy.advise(ctx)
        except Exception as e:
            if verbose:
                print(f"[warn] advise() error at bar {i}: {e}")
            adv = None

        if not adv:
            equity_curve.append(equity)
            continue

        action = adv.get('action', 'FLAT')
        exec_price = o[i + 1]  # اجرا روی open کندلِ بعد (بدون look-ahead)

        # ۳) اعمالِ تصمیم با در نظر گرفتنِ حالتِ فعلی (arbitration)
        if action in ('LONG', 'SHORT'):
            if position is None or (allow_pyramiding and position['side'] == action):
                if position is None:  # فقط وقتی آزادیم وارد شو ⇒ تناقضِ سیگنال حذف
                    sl = adv.get('sl'); tp = adv.get('tp')
                    position = open_position(action, exec_price, sl, tp, i + 1)
            # اگر پوزیشنِ مخالف باز است ⇒ سیگنالِ متناقض نادیده گرفته می‌شود (کلیدِ حلِ مشکل)
        elif action == 'CLOSE':
            if position is not None:
                close_position(position, exec_price, i + 1, 'strategy_close')
                position = None
        elif action == 'MANAGE':
            if position is not None:
                if adv.get('sl') is not None:
                    position['sl'] = adv['sl']
                if adv.get('tp') is not None:
                    position['tp'] = adv['tp']
        # FLAT ⇒ کاری نکن

        # ۴) سقفِ نگه‌داری (اختیاری)
        if position is not None and max_bars_hold is not None:
            if (i + 1) - position['entry_bar'] >= max_bars_hold:
                close_position(position, c[i + 1], i + 1, 'max_hold')
                position = None

        equity_curve.append(equity)

    # بستنِ پوزیشنِ بازِ باقی‌مانده در آخرین کندل
    if position is not None:
        close_position(position, c[n - 1], n - 1, 'eod')

    trades_df = pd.DataFrame(trades)
    return trades_df, equity_curve


def _check_sl_tp_hit(pos, o_next, h_next, l_next, c_next):
    """
    بررسیِ برخوردِ SL/TP در کندلِ بعد. فرضِ محافظه‌کارانه: اگر هم SL و هم TP در یک
    کندل لمس شوند، SL اول فرض می‌شود (بدترین حالت برای کاربر — واقع‌گرایانه).
    برمی‌گرداند: (exit_price, reason) یا None.
    """
    side = pos['side']
    sl = pos['sl']; tp = pos['tp']
    if side == 'LONG':
        # گپِ باز روی open
        if sl is not None and o_next <= sl:
            return (o_next, 'sl_gap')
        if tp is not None and o_next >= tp:
            return (o_next, 'tp_gap')
        # درونِ کندل — SL اول (بدبینانه)
        if sl is not None and l_next <= sl:
            return (sl, 'sl')
        if tp is not None and h_next >= tp:
            return (tp, 'tp')
    else:  # SHORT
        if sl is not None and o_next >= sl:
            return (o_next, 'sl_gap')
        if tp is not None and o_next <= tp:
            return (o_next, 'tp_gap')
        if sl is not None and h_next >= sl:
            return (sl, 'sl')
        if tp is not None and l_next <= tp:
            return (tp, 'tp')
    return None


# ============================ Loader ============================
def load_data(tf_or_path, asset=None):
    """بارگذاریِ CSV با ستونِ dt. ورودی: یا مسیرِ کامل یا نامِ فایل مثلِ 'XAUUSD_M5'."""
    if os.path.sep in tf_or_path or tf_or_path.endswith('.csv'):
        path = tf_or_path
    else:
        path = os.path.join(ROOT, 'data', tf_or_path + '.csv')
    df = pd.read_csv(path)
    if 'time' in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    for col in ('open', 'high', 'low', 'close'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)
    return df


if __name__ == '__main__':
    print("trade_simulator.py — Event-Driven Simulator loaded OK")
    print("Assets:", asset_spec('XAUUSD'))
    print("       ", asset_spec('EURUSD'))
