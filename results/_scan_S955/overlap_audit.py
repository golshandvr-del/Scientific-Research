# S955 — آزمونِ همپوشانی با لایه‌های ACCEPTِ هم‌کارت (فقط خواندن؛ منطقِ هر لایه از ماژولِ منتشرشدهٔ خودش)
# H8: S950 (والد)، S965، S966، S1911 · H6: S919 · H12: S800 (cfg قفل‌شده از _scan_S800/H12_locked.json)
import sys, os, json
sys.path.insert(0, '/home/user/webapp'); os.chdir('/home/user/webapp')
import numpy as np
from tools import s434_fast_data as fd
import strategies.s955_jump_aftermath_calm as M

def s955_entries(tf):
    d = fd.load_fast('XAUUSD', tf); df = fd.as_dataframe(d)
    c = df['close'].values.astype(float); n = len(c)
    r, sbv, atr = M.features(df)
    ls0, ss0 = M.member_signals(r, sbv, 2.6, 'continuation', warm=M.BV_WIN + 2)
    drift = np.zeros(n); drift[M.BV_WIN + 1:] = c[M.BV_WIN:-1] - c[:-(M.BV_WIN + 1)]
    reg = M.regime_ratio(M.sigma_series(c), 233); calm = np.isfinite(reg) & (reg <= 1)
    ls = ls0 & (drift > 0) & calm; ss = ss0 & (drift < 0) & calm
    base_l = ls0 & (drift > 0); base_s = ss0 & (drift < 0)
    # موتور در کندلِ بعد وارد می‌شود ⇒ ایندکسِ ورود = سیگنال+1
    return df, dict(long=set(np.where(ls)[0] + 1), short=set(np.where(ss)[0] + 1)), \
        dict(long=set(np.where(base_l)[0] + 1), short=set(np.where(base_s)[0] + 1))

def pairs(a, b, hold_a, hold_b, name_b):
    """اشتراکِ همان‌کندل و همپوشانیِ پنجرهٔ نگهداری (هر ورودِ a که در بازهٔ فعالِ یک معاملهٔ b باشد)."""
    A = a['long'] | a['short']; B = b['long'] | b['short']
    same = A & B
    opp = (a['long'] & b['short']) | (a['short'] & b['long'])
    Bl = sorted(B)
    win = 0
    for i in A:
        for j in Bl:
            if j <= i <= j + hold_b or i <= j <= i + hold_a:
                win += 1; break
    return dict(vs=name_b, n_a=len(A), n_b=len(B), same_bar=len(same),
                same_bar_pct_of_a=round(100 * len(same) / max(len(A), 1), 1),
                opposite_dir_same_bar=len(opp),
                window_overlap_n=win, window_overlap_pct_of_a=round(100 * win / max(len(A), 1), 1))

out = {}
# ---------- H8 ----------
df, s955, s950 = s955_entries('H8')
res = [pairs(s955, s950, 34, 34, 'S950 (parent, ACCEPT 80)')]
import strategies.s1911_kyle_shock_calm as K11
lm, sm, *_ = K11.signals(df, 'gated')
res.append(pairs(s955, dict(long=set(np.where(lm)[0]), short=set(np.where(sm)[0])), 34, 16, 'S1911 (ACCEPT 93.9)'))
import strategies.s966_kyle_permanence_drift as K66
ev_up, ev_dn, atr_prev, c8 = K66.features(df)
l66, s66 = K66.member_signals(ev_up, ev_dn, c8, 180, 'aligned')
res.append(pairs(s955, dict(long=set(np.where(l66)[0] + 1), short=set(np.where(s66)[0] + 1)), 34, 16, 'S966 (ACCEPT 86)'))
res.append(pairs(s955, dict(long=set(np.where(ev_up)[0] + 1), short=set(np.where(ev_dn)[0] + 1)), 34, 16, 'S965 event (ACCEPT 82)'))
out['H8'] = res
# ---------- H6 ----------
df6, s955_6, _ = s955_entries('H6')
import strategies.s919_convention_aligned_shock as K19
lm, sm, *_ = K19.signals(df6, 'H6', 'gated')
out['H6'] = [pairs(s955_6, dict(long=set(np.where(lm)[0]), short=set(np.where(sm)[0])), 34, 16, 'S919 (ACCEPT 88.9)')]
# ---------- H12 ----------
df12, s955_12, _ = s955_entries('H12')
import strategies.s800_squeeze_expansion as S8
cfg = json.load(open('results/_scan_S800/H12_locked.json'))['cfg']
meta, df12b = S8.load('H12')
base = S8.base_arrays(df12b, need_filters=False, tf='H12')
tr, ls, ss, sl, tp = S8.run_cfg(df12b, base, cfg)
assert len(df12b) == len(df12), 'S800 df length mismatch'
out['H12'] = [pairs(s955_12, dict(long=set(np.where(ls)[0] + 1), short=set(np.where(ss)[0] + 1)), 34, cfg['hold'], 'S800-H12 (ACCEPT 83.6)')]
for k, v in out.items():
    for r in v: print(k, r)
json.dump(out, open('results/_scan_S955/overlap_audit.json', 'w'), ensure_ascii=False, indent=1)
