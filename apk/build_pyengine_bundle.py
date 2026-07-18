# -*- coding: utf-8 -*-
# ============================================================================
# build_pyengine_bundle.py — بسته‌بندیِ موتورِ واقعیِ پایتون برای APK/WebView
# ----------------------------------------------------------------------------
# این اسکریپت فایل‌های واقعیِ برندهٔ پروژه را در apk/www/pyengine/ کپی می‌کند تا
# در محیطِ WebView (Pyodide) قابلِ fetch و اجرا باشند — بدونِ تغییرِ حتی یک خط.
#
# خروجی:
#   apk/www/pyengine/
#     ├── numba.py                (shim — قبل از هر چیز لود می‌شود)
#     ├── live_engine.py          (موتورِ استنتاجِ زنده)
#     ├── engine/                 (indicators.py, scalp_engine.py, capital_engine.py, ...)
#     ├── strategies/             (s118, s73, backtest deps)
#     └── manifest.json           (فهرستِ فایل‌ها برای بارگذاری در Pyodide)
#
# اجرا:  python apk/build_pyengine_bundle.py
# ============================================================================
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, "www", "pyengine")

# فایل‌های موتورِ واقعی که در APK لازم‌اند (وابستگی‌های کاملِ live_engine + s118 + s73)
ENGINE_FILES = [
    "engine/indicators.py",
    "engine/scalp_engine.py",
    "engine/capital_engine.py",
    "engine/backtest.py",          # وابستگیِ s73 (load_data, run_backtest)
]
STRATEGY_FILES = [
    "strategies/s118_short_exit_letwinnersrun.py",
    "strategies/s73_eurusd_session_drift.py",
]
PY_FILES = [
    "apk/py/numba.py",
    "apk/py/live_engine.py",
]


def _copy(rel_src, dst_dir):
    src = os.path.join(REPO, rel_src)
    if not os.path.exists(src):
        print(f"  ⚠️ یافت نشد: {rel_src}")
        return None
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(rel_src))
    shutil.copy2(src, dst)
    return dst


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)

    manifest = {"root_files": [], "engine": [], "strategies": [],
                "note": "موتورِ واقعیِ پروژه؛ در Pyodide با numpy+pandas اجرا می‌شود."}

    print("کپیِ فایل‌های ریشه (shim + live_engine):")
    for f in PY_FILES:
        d = _copy(f, OUT)
        if d:
            manifest["root_files"].append(os.path.basename(f))
            print(f"  ✓ {os.path.basename(f)}")

    print("کپیِ موتورِ واقعی (engine/):")
    for f in ENGINE_FILES:
        d = _copy(f, os.path.join(OUT, "engine"))
        if d:
            manifest["engine"].append(os.path.basename(f))
            print(f"  ✓ engine/{os.path.basename(f)}")

    print("کپیِ استراتژی‌های برنده (strategies/):")
    for f in STRATEGY_FILES:
        d = _copy(f, os.path.join(OUT, "strategies"))
        if d:
            manifest["strategies"].append(os.path.basename(f))
            print(f"  ✓ strategies/{os.path.basename(f)}")

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=2)
    print(f"\n✅ bundle ساخته شد: {OUT}")
    print(f"   manifest: {len(manifest['root_files'])} root + "
          f"{len(manifest['engine'])} engine + {len(manifest['strategies'])} strategy")


if __name__ == "__main__":
    main()
