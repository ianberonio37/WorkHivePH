#!/usr/bin/env python3
"""validate_ml_deps.py — G0 gate: the Python-API ML path must declare its hard deps.

THE BUG (caught live 2026-06-20 by backend_live_invoke.py): trigger-ml-retrain ->
/ml/train returned 502 `ModuleNotFoundError: No module named 'joblib'`. ml/trainer.py
has a module-top `import joblib` and in-fn `from sklearn...`, so BOTH must be present
or /ml/train, /ml/predict AND /ml/status all 502 — the rules-fallback never runs
because the module fails to import. requirements.txt had numpy+pandas but neither
scikit-learn nor joblib. Fixed by pinning both (numpy-1.26.4 compatible).

RULE: every top-level third-party module imported by python-api/ml/*.py must be
declared in python-api/requirements.txt. Baseline 0 undeclared.

USAGE: python tools/validate_ml_deps.py
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ML_DIR = ROOT / "python-api" / "ml"
REQS = ROOT / "python-api" / "requirements.txt"

# import-name -> the distribution (pip) name that provides it
DIST = {"sklearn": "scikit-learn", "joblib": "joblib", "numpy": "numpy",
        "pandas": "pandas", "scipy": "scipy"}
# stdlib / first-party modules that need no requirements entry
STDLIB = {"json", "os", "sys", "re", "math", "pathlib", "datetime", "typing",
          "collections", "itertools", "functools", "dataclasses", "enum",
          "warnings", "logging", "traceback", "io", "time"}

# a real import: `from X import ...` (the `import` keyword guards against docstring
# prose that merely starts with "from ...") OR a bare `import X`.
IMPORT_RE = re.compile(r"(?m)^\s*(?:from\s+([.\w]+)\s+import\b|import\s+([.\w]+))")
TRIPLE_STR = re.compile(r"('''|\"\"\").*?\1", re.DOTALL)


def imported_top_modules() -> set[str]:
    mods: set[str] = set()
    for f in sorted(ML_DIR.glob("*.py")):
        code = f.read_text(encoding="utf-8", errors="replace")
        code = TRIPLE_STR.sub("", code)             # strip docstrings / triple-quoted blocks
        code = re.sub(r"^\s*#.*", "", code, flags=re.M)  # strip comment lines
        for m in IMPORT_RE.finditer(code):
            name = (m.group(1) or m.group(2) or "").split(".")[0]
            if name and not name.startswith("_"):
                mods.add(name)
    return mods


def declared() -> set[str]:
    if not REQS.exists():
        return set()
    out = set()
    for ln in REQS.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        out.add(re.split(r"[=<>!~\[ ]", ln)[0].lower())
    return out


def main() -> int:
    if not ML_DIR.exists():
        print("  (no python-api/ml — skipping)")
        return 0
    mods = imported_top_modules()
    decl = declared()
    missing = []
    for mod in sorted(mods):
        if mod in STDLIB or mod == "ml":   # first-party package
            continue
        dist = DIST.get(mod, mod).lower()
        if dist not in decl:
            missing.append((mod, dist))

    print("=" * 60)
    print("  validate_ml_deps — ml/*.py imports must be in requirements.txt")
    print("=" * 60)
    if missing:
        for mod, dist in missing:
            print(f"  X  ml/*.py imports `{mod}` but `{dist}` not in requirements.txt")
        print(f"\n  FAIL: {len(missing)} undeclared ML dependency(ies) (baseline 0)")
        return 1
    third = sorted(m for m in mods if m not in STDLIB and m != "ml")
    print(f"  OK  all {len(third)} third-party ML imports declared: {', '.join(third)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
