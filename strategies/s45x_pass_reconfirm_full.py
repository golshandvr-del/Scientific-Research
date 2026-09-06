# بازتأییدِ دو PASS مأموریت ۵ روی دادهٔ کامل mt5_full — فقط تأیید، بدونِ جست‌وجو
import sys, os, json, numpy as np
sys.path.insert(0, '/home/user/repo'); os.chdir('/home/user/repo')
from strategies import s459_overnight_norescue as F   # لودرِ full-data
from strategies.s450_paired_replay import metrics, judge
out = {}
# --- S453 / S382_H4 / k=15 (برندهٔ قفل‌شده) ---
F._TF['tf'] = 'H4'; F.patch_loaders()
from strategies import s453_time_stag as S453
df, tr, rf, base = S453.load_patient('S382_H4')
par = np.array([rf(t, None) for t in tr.itertuples(index=False)], float)
mg = np.array([rf(t, 15) for t in tr.itertuples(index=False)], float)
mid = len(df)//2; eb = tr['entry_bar'].to_numpy(int); m1 = eb < mid; m2 = ~m1
out['S453_S382_H4_k15'] = dict(n=len(tr), n_bars=len(df), parity_mism=int((np.abs(par-base)>1e-6).sum()),
    full=judge(metrics(base), metrics(mg)), h1=judge(metrics(base[m1]), metrics(mg[m1])), h2=judge(metrics(base[m2]), metrics(mg[m2])),
    base_full=metrics(base), mgmt_full=metrics(mg), base_h2=metrics(base[m2]), mgmt_h2=metrics(mg[m2]))
# --- S455 / S312_H1 / V_DDFAIL ---
F._TF['tf'] = 'H1'; F.patch_loaders()
from strategies import s455_symbolic_warnings as S455
df, tr, rf, base = S455.load_patient('S312_H1')
par = np.array([rf(t, None) for t in tr.itertuples(index=False)], float)
mg = np.array([rf(t, 'V_DDFAIL') for t in tr.itertuples(index=False)], float)
mid = len(df)//2; eb = tr['entry_bar'].to_numpy(int); m1 = eb < mid; m2 = ~m1
out['S455_S312_H1_VDDFAIL'] = dict(n=len(tr), n_bars=len(df), parity_mism=int((np.abs(par-base)>1e-6).sum()),
    full=judge(metrics(base), metrics(mg)), h1=judge(metrics(base[m1]), metrics(mg[m1])), h2=judge(metrics(base[m2]), metrics(mg[m2])),
    base_full=metrics(base), mgmt_full=metrics(mg), base_h2=metrics(base[m2]), mgmt_h2=metrics(mg[m2]))
json.dump(out, open('research/mgmt/S45x_PASS_RECONFIRM_mt5_full.json','w'), indent=1, default=str)
for k,v in out.items():
    print(k, 'n',v['n'],'bars',v['n_bars'],'parity_mism',v['parity_mism'])
    print('  H2 verdict', v['h2']['verdict'], '| full verdict', v['full']['verdict'])
    print('  H2 base avg %.2f -> mgmt %.2f | maxDD %.1f -> %.1f | sd %.1f -> %.1f'%(v['base_h2']['avg'],v['mgmt_h2']['avg'],v['base_h2']['maxDD'],v['mgmt_h2']['maxDD'],v['base_h2']['sd'],v['mgmt_h2']['sd']))
