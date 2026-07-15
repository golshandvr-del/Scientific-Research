import sys, os, json
HERE=os.path.dirname(__file__); ENGINE=os.path.join(HERE,'..','..','engine'); ROBOT=os.path.join(HERE,'..','..','mt5_robot')
sys.path.insert(0,ENGINE)
import numpy as np, pandas as pd, indicators as ind
from backtest import load_data; from features import build_features
import onnxruntime as ort; import warnings; warnings.filterwarnings('ignore')
DATA=os.path.join(HERE,'..','..','data','XAUUSD_M15.csv')
df=load_data(DATA); feats=build_features(df); fc=list(feats.columns)
ema50=ind.ema(df['close'],50).values; ema200=ind.ema(df['close'],200).values; cv=df['close'].values
valid=feats.dropna(); Xall=valid[fc].values.astype(np.float32)
sess=[ort.InferenceSession(os.path.join(ROBOT,f'xauusd_s14_model_{i}.onnx')) for i in range(3)]
def ens(X):
    ps=[]
    for s in sess:
        o=s.run(None,{s.get_inputs()[0].name:X})
        for a in o:
            a=np.array(a)
            if a.ndim==2 and a.shape[1]==2: ps.append(a[:,1]); break
    return np.mean(np.vstack(ps),axis=0)
pall=ens(Xall)
pos={idx:k for k,idx in enumerate(valid.index.tolist())}
# آخرین 2000 کندل valid
tail=valid.tail(2000).index.tolist()
out=[]
for idx in tail:
    cand=bool((cv[idx]>ema50[idx]) and (ema50[idx]>ema200[idx]))
    p=float(pall[pos[idx]])
    out.append({'idx':int(idx),'cand':cand,'proba':p,'signal':bool(cand and p>=0.68)})
json.dump(out,open(os.path.join(HERE,'full_ref_2000.json'),'w'))
print('صادر شد:',len(out),'| سیگنال‌های long:',sum(r['signal'] for r in out))

# اضافه: صادرات کامل feature برای ۲۰۰۰ کندل جهت دیف دقیق
full={}
for idx in tail:
    full[int(idx)]={fc[j]: float(valid[fc].values[pos[idx]][j]) for j in range(len(fc))}
json.dump(full, open(os.path.join(HERE,'full_feats_2000.json'),'w'))
print('feature کامل صادر شد')
