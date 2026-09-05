# بازداوریِ S951/S952 پس از اصلاحِ ساختارِ null (ERRATUM 2026-09-05)
# فقط TFهایی که به rqs2 رسیده بودند و گیت‌های H3/H4/H5 آن‌ها None مانده بود.
# چک‌پوینت‌های قدیمی به *_prenullfix.json منتقل می‌شوند (حذف نمی‌شوند — رد‌گیری).
import sys, os, json, gc, glob
sys.path.insert(0, '/home/user/webapp'); os.chdir('/home/user/webapp')

which = sys.argv[1]            # S951 | S952
tfs = sys.argv[2:]
mod = __import__('strategies.s951_compression_breakout' if which == 'S951'
                 else 'strategies.s952_jump_flow_imbalance', fromlist=['judge_tf'])
out_dir = mod.OUT_DIR
for tf in tfs:
    p = f'{out_dir}/{tf}.json'
    if os.path.exists(p):
        d = json.load(open(p))
        if d.get('gates', {}).get('H3') is None and 'gates' in d:
            os.replace(p, f'{out_dir}/{tf}_prenullfix.json')
            print(f'[{tf}] archived old checkpoint', flush=True)
        else:
            print(f'[{tf}] already has H3 — skip', flush=True); continue
    mod.judge_tf(tf)
    gc.collect()
print('readjudication done', flush=True)
