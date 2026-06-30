#!/usr/bin/env python3
"""validate_python_api_deps.py — Arc F B3: the WHOLE-API supply-chain gate.

Generalizes validate_ml_deps.py (which only guarded python-api/ml/*.py) to EVERY
python-api subsystem, and sharpens the rule with import-guard awareness.

THE BUG CLASS (joblib-502, found by Arc E): a module-top `import joblib` with the
distribution missing from requirements.txt → the whole module fails to import →
/ml/train, /ml/predict, /ml/status ALL 502, and the rules-fallback never runs. The
SAME class can bite any subsystem (an undeclared `fluids` would 502 every fluid calc).

THE RULE (two tiers, evidence-based):
  • HARD import  (top-level OR not wrapped in try/except ImportError): the distribution
    MUST be declared in requirements.txt. An undeclared hard import = FAIL (the joblib class).
  • GUARDED import (inside try/except ImportError|ModuleNotFoundError|Exception → graceful
    degrade, e.g. weasyprint's 503 fallback in main.py): MAY be undeclared — it falls back,
    it does not 502. Reported as info, not a failure.
  • PLANT-SIDE scripts (evidence marker "RUN THIS ON THE PLANT GATEWAY", e.g.
    sensors/mqtt_subscriber_template.py) are NOT part of the API runtime — excluded.

Plus a CVE scan: if `pip-audit` is installed, audit requirements.txt and report known
vulnerabilities as WARN (pin bumps are a separate change with their own blast radius;
the hard-import gate is the FAIL teeth). If pip-audit is absent, the CVE scan is
skipped with an install hint — the declaration gate still runs.

USAGE:      python tools/validate_python_api_deps.py
Self-test:  python tools/validate_python_api_deps.py --self-test   (proves the teeth)
"""
from __future__ import annotations
import ast
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PYAPI = ROOT / "python-api"
REQS = PYAPI / "requirements.txt"

# import-name -> distribution (pip) name when they differ
DIST = {
    "sklearn": "scikit-learn", "edge_tts": "edge-tts", "paho": "paho-mqtt",
    "PIL": "pillow", "yaml": "pyyaml", "cv2": "opencv-python", "dateutil": "python-dateutil",
}
# first-party packages (live under python-api/) — never a requirements entry
FIRST_PARTY = {"calcs", "ml", "analytics", "diagrams", "projects", "reliability",
               "sensors", "_auth", "main", "analytics_shim"}
STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {"__future__"}
PLANT_SIDE_MARKER = "RUN THIS ON THE PLANT GATEWAY"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"


def declared() -> set[str]:
    out: set[str] = set()
    if not REQS.exists():
        return out
    for ln in REQS.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        out.add(re.split(r"[=<>!~\[ ]", ln)[0].lower())
    return out


def _guarded_lines(tree: ast.AST) -> set[int]:
    """Line numbers of import statements wrapped in a try/except that catches
    ImportError/ModuleNotFoundError/Exception (graceful-degrade imports)."""
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        catches_import = False
        for h in node.handlers:
            names = []
            if isinstance(h.type, ast.Name):
                names = [h.type.id]
            elif isinstance(h.type, ast.Tuple):
                names = [e.id for e in h.type.elts if isinstance(e, ast.Name)]
            elif h.type is None:
                names = ["Exception"]  # bare except
            if any(n in ("ImportError", "ModuleNotFoundError", "Exception") for n in names):
                catches_import = True
        if catches_import:
            for stmt in ast.walk(node):
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    guarded.add(stmt.lineno)
    return guarded


def scan_file(path: Path) -> list[tuple[str, bool]]:
    """Return [(top_module, is_hard)] for third-party imports in this file."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except Exception:
        return []
    guarded = _guarded_lines(tree)
    out: list[tuple[str, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                out.append((top, node.lineno not in guarded))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import = first-party
            if node.module:
                top = node.module.split(".")[0]
                out.append((top, node.lineno not in guarded))
    return out


def is_third_party(mod: str) -> bool:
    return bool(mod) and not mod.startswith("_") and mod not in STDLIB and mod not in FIRST_PARTY


def run_cve_scan() -> tuple[str, list[str]]:
    """('ok'|'skipped'|'warn', lines). pip-audit if present; else skip with a hint."""
    try:
        import importlib.util
        if importlib.util.find_spec("pip_audit") is None:
            return "skipped", ["pip-audit not installed — CVE scan skipped (pip install pip-audit)"]
    except Exception:
        return "skipped", ["pip-audit probe failed — CVE scan skipped"]
    try:
        proc = subprocess.run([sys.executable, "-m", "pip_audit", "-r", str(REQS),
                               "--progress-spinner", "off"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
        lines = [l for l in (proc.stdout + proc.stderr).splitlines() if l.strip()]
        if proc.returncode == 0:
            return "ok", ["pip-audit: no known vulnerabilities in requirements.txt"]
        return "warn", lines[-12:]
    except Exception as e:  # noqa: BLE001
        return "skipped", [f"pip-audit run failed: {e}"]


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    decl = declared()
    files = sorted(PYAPI.rglob("*.py"))
    hard_undeclared: list[tuple[str, str, str]] = []   # (module, dist, file)
    guarded_undeclared: list[tuple[str, str]] = []
    plant_side: list[str] = []
    all_hard: set[str] = set()

    for f in files:
        src = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(PYAPI).as_posix()
        if PLANT_SIDE_MARKER in src:
            plant_side.append(rel)
            continue
        for mod, is_hard in scan_file(f):
            if not is_third_party(mod):
                continue
            dist = DIST.get(mod, mod).lower()
            declared_ok = dist in decl
            if is_hard:
                all_hard.add(mod)
                if not declared_ok:
                    hard_undeclared.append((mod, dist, rel))
            elif not declared_ok:
                guarded_undeclared.append((mod, rel))

    print("=" * 70)
    print("  validate_python_api_deps — whole-API supply-chain gate (Arc F B3)")
    print("=" * 70)
    print(f"  scanned {len(files)} files · {len(all_hard)} distinct HARD third-party imports")
    if plant_side:
        print(f"  excluded plant-side (not API runtime): {', '.join(plant_side)}")
    for mod, rel in sorted(set(guarded_undeclared)):
        print(f"  {YEL}info{RST}  guarded import `{mod}` ({rel}) undeclared — graceful try/except fallback (OK)")

    # CVE scan (WARN tier)
    cve_status, cve_lines = run_cve_scan()
    print(f"\n  CVE scan (pip-audit): {cve_status}")
    for l in cve_lines:
        tag = YEL + "warn" + RST if cve_status == "warn" else "    "
        print(f"    {tag} {l}")

    print()
    if hard_undeclared:
        for mod, dist, rel in hard_undeclared:
            print(f"  {RED}FAIL{RST}  hard import `{mod}` in {rel} but `{dist}` NOT in requirements.txt (joblib-502 class)")
        print(f"\n  {RED}FAIL{RST}: {len(hard_undeclared)} undeclared HARD dependency(ies) (baseline 0)")
        return 1

    print(f"  {GREEN}OK{RST}  every hard third-party import across python-api is declared in requirements.txt")
    if self_test:
        # teeth: a synthetic hard import of an undeclared module must be caught
        probe = "import a_totally_unlikely_undeclared_pkg_xyz\n"
        tree = ast.parse(probe)
        guarded = _guarded_lines(tree)
        caught = any(node.lineno not in guarded for node in ast.walk(tree) if isinstance(node, ast.Import))
        mark = f"{GREEN}PASS{RST}" if caught else f"{RED}FAIL{RST}"
        print(f"  TEETH [{mark}] an unguarded undeclared import is classified HARD (would FAIL)")
        if not caught:
            return 1
    print(f"  (CVE scan is advisory; pin bumps are a separate change — the hard-import gate is the teeth)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
