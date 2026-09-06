# -*- coding: utf-8 -*-
"""
قواعد منجمد لایه‌های دههٔ S1780–S1789 (ابن هیثم). هر قاعده عیناً از پیش‌ثبت همان لایه.
build(layer, arm, df, split) -> dict(long, short, sl, tp, max_hold, n_trials, warm)
"""
import numpy as np
import pandas as pd

PIP = 0.10


def causal_atr_pips(df, period=89):
    h = df['high'].values.astype(float); l = df['low'].values.astype(float)
    c = df['close'].values.astype(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(period).mean().shift(1).values / PIP


def entry_edge(state):
    prev = np.roll(state, 1); prev[0] = False
    return state & ~prev


# ---------------------------------------------------------------- S1780
def s1780(arm, df, split):
    """Frog-in-the-Pan: R_21 >= 1.618*sigma_21 (+ up-bar share >= 0.618 for FIP arm), LONG-only."""
    c = df['close'].values.astype(float)
    W = 21
    r1 = pd.Series(c).pct_change()
    sig1 = r1.rolling(89).std().shift(1).values * np.sqrt(W)
    RW = c / np.roll(c, W) - 1.0; RW[:W] = np.nan
    up = (r1 > 0).astype(float)
    share_up = up.rolling(W).sum().values / W          # includes bar i (closed bar) — causal at close
    base = np.isfinite(sig1) & (RW >= 1.618 * sig1)
    if arm == 'control':
        state = base
    elif arm == 'fip':
        state = base & (share_up >= 0.618)
    else:
        raise ValueError(arm)
    long_sig = entry_edge(state)
    atr = causal_atr_pips(df, 89)
    sl = 2.058 * atr; tp = 1.0 * sl
    return dict(long=long_sig, short=np.zeros(len(df), bool), sl=sl, tp=tp,
                max_hold=21, n_trials=6, warm=120)


REGISTRY = {1780: s1780}


def build(layer, arm, df, split):
    return REGISTRY[layer](arm, df, split)
