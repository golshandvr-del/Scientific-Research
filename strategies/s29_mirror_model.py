"""
استراتژی ۲۹ (طرح P30 از strategy_plans.md، گروه F): «مدل آینه» (Mirror Model)

ایده (سند P30):
  یک مدل دوم مستقیماً آموزش می‌بیند تا «باخت‌های مدل اصلی S25» را پیش‌بینی کند.
  برچسب مدل آینه = 1 اگر (مدل اصلی سیگنال داد proba>=THRESH) و آن معامله باخت.
  اگر AUC مدل آینه روی OOS > 0.55 باشد، به‌عنوان وتو روی سیگنال‌های اصلی اعمال می‌شود:
  سیگنال‌هایی که مدل آینه با اطمینان بالا «باخت» پیش‌بینی می‌کند حذف می‌شوند.

  تفاوت ظریف با meta-labeling شکست‌خوردهٔ S15 (سند): آنجا متا روی سیگنال خام ضعیف
  سوار بود؛ اینجا وتو روی سیگنال قوی و از قبل سودآور (S25 در thr0.68) سوار می‌شود و
  فقط باید دم چپ توزیع (باخت‌های قابل‌پیش‌بینی) را بتراشد → بار اثبات سبک‌تر.

منطق PF: حذف باخت‌های قابل‌پیش‌بینی مستقیماً مخرج PF را کوچک و WR را بالا می‌برد.

روش (Recipe-S25):
  ۱. proba پایهٔ S25 را می‌گیریم (ensemble OOS) و ماسک سیگنال ent0 = cand & proba>=thr.
  ۲. برای هر fold آینه: روی سیگنال‌های TRAIN مدل آینه (LightGBM) با برچسب «باخت؟»
     آموزش می‌دهیم؛ روی سیگنال‌های OOS همان fold، p_loss پیش‌بینی می‌کنیم.
     ⚠️ کل جریان purged walk-forward است — هیچ نشتی از آینده.
  ۳. AUC مدل آینه روی OOS گزارش می‌شود.
  ۴. وتو: سیگنال‌هایی با p_loss >= veto_thr حذف می‌شوند. جاروب veto_thr.
  ۵. مقایسهٔ baseline (بدون وتو) با نسخهٔ وتو شده: WR, PF, exp, tpd, p-value.

معیار پذیرش: بهبود هم‌زمان PF و حفظ/بهبود WR>60 بدون سقوط شدید فرکانس.
"""
import sys; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score
import _base_s25 as B
import warnings; warnings.filterwarnings('ignore')

print("="*70)
print("P30 — Mirror Model (یادگیری وتوی باخت‌های S25)")
print("="*70)

base = B.load_base()
df, atr, cand = base['df'], base['atr'], base['cand']
feats, cols, n = base['feats'], base['cols'], base['n']
proba_ens = base['proba_ens']
y = base['y']  # برچسب برد/باخت واقعی در نقطهٔ کار پایه

# --- baseline S25 ---
ent0 = cand & ~np.isnan(proba_ens) & (proba_ens >= B.THRESH)
print(f"\nسیگنال‌های پایه S25 (thr={B.THRESH}): {int(ent0.sum())}")
r_base = B.eval_entries(df, atr, ent0, label='BASELINE S25 (بدون وتو)')

# =====================================================================
# مدل آینه: purged walk-forward روی سیگنال‌های S25
# برچسب آینه = 1 اگر معامله باخت (y==0)، فقط روی ردیف‌های سیگنال‌دار
# =====================================================================
# ردیف‌های سیگنال‌دار با برچسب معتبر
sig_mask = ent0 & ~np.isnan(y)
sig_idx = np.where(sig_mask)[0]
print(f"سیگنال‌های دارای برچسب معتبر برای آموزش آینه: {len(sig_idx)}")

# ماتریس feature روی سیگنال‌ها (همان ۵۹ feature)
Fsig = feats.loc[sig_idx, cols]
valid_f = ~Fsig.isna().any(axis=1)
sig_idx = sig_idx[valid_f.values]
Fsig = Fsig[valid_f.values]
loss_label = (y[sig_idx] == 0).astype(int)   # 1=باخت
X_m = Fsig.values
print(f"سیگنال‌های نهایی آینه: n={len(sig_idx)}, نرخ باخت={loss_label.mean()*100:.1f}%")

# proba آینه OOS با همان طرح purged walk-forward روی *دنبالهٔ سیگنال‌ها*
def mirror_wf(X, Y, seed):
    N = len(X)
    mt = int(N * B.MIN_TRAIN_FRAC)
    fold = (N - mt) // B.N_FOLDS
    ploss = np.full(N, np.nan)
    for k in range(B.N_FOLDS):
        tr_end = mt + k * fold
        te_start = tr_end + 5   # embargo کوچک روی دنبالهٔ سیگنال‌ها (نه کندل خام)
        te_end = tr_end + fold if k < B.N_FOLDS - 1 else N
        if te_start >= te_end:
            continue
        if Y[:tr_end].sum() < 20 or (Y[:tr_end] == 0).sum() < 20:
            continue
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=16,
                               max_depth=4, subsample=0.8, colsample_bytree=0.7,
                               min_child_samples=40, reg_lambda=3.0,
                               random_state=seed, verbose=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        ploss[te_start:te_end] = m.predict_proba(X[te_start:te_end])[:, 1]
    return ploss

print("\nآموزش مدل آینه (ensemble 3-seed) ...")
ploss_seeds = [mirror_wf(X_m, loss_label, s) for s in B.SEEDS]
ploss = np.nanmean(np.vstack(ploss_seeds), axis=0)

# AUC روی بخشی که پیش‌بینی داریم (OOS)
have = ~np.isnan(ploss)
auc = roc_auc_score(loss_label[have], ploss[have])
print(f"\n>>> AUC مدل آینه (پیش‌بینی باخت) روی OOS = {auc:.4f}")
print(f"    (معیار سند: AUC>0.55 لازم است تا وتو ارزش داشته باشد)")

# =====================================================================
# اعمال وتو: سیگنال‌هایی که p_loss بالا دارند حذف می‌شوند
# =====================================================================
# نگاشت p_loss از فضای سیگنال به فضای کندل
ploss_full = np.full(n, np.nan)
ploss_full[sig_idx] = ploss

print("\n=== جاروب آستانهٔ وتو (فقط روی OOSهایی که آینه پیش‌بینی دارد) ===")
# فقط سیگنال‌هایی را نگه می‌داریم که آینه پیش‌بینی دارد (منصفانه: OOS آینه)
scored = ent0 & ~np.isnan(ploss_full)
print(f"سیگنال‌های دارای امتیاز آینه (OOS): {int(scored.sum())}")
r_scored = B.eval_entries(df, atr, scored, label='SCORED subset (بدون وتو، مبنای منصفانه)')

results = []
for vt in [0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40]:
    ent_veto = scored & (ploss_full < vt)
    r = B.eval_entries(df, atr, ent_veto, label=f'VETO p_loss<{vt:.2f}', verbose=True)
    if r:
        results.append((vt, r))

print("\n" + "="*70)
print("خلاصه: اثر وتوی آینه بر جریان پایه")
print("="*70)
if r_scored:
    print(f"مبنا (scored, بدون وتو): WR={r_scored['wr']:.2f}% PF={r_scored['pf']:.3f} "
          f"exp={r_scored['exp']:+.3f} tpd={r_scored['tpd']:.2f} n={r_scored['n']}")
for vt, r in results:
    print(f"veto<{vt:.2f}: WR={r['wr']:.2f}% PF={r['pf']:.3f} exp={r['exp']:+.3f} "
          f"tpd={r['tpd']:.2f} n={r['n']} p={r['pv']:.4f}")

print("\nتمام P30.")
