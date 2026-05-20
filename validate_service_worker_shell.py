"""
Service Worker SHELL_FILES Existence Validator (L0, ratcheted).
================================================================
Every path listed in sw.js's SHELL_FILES = [...] array must exist on
disk. Otherwise the SW precache install fails silently and users get
an offline experience that's missing pages they expect to work.

Output: service_worker_shell_report.json. Exit 1 on regression.
Allow with `// sw-shell-allow: <reason>` on the offending line.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "service_worker_shell_report.json"
BASELINE_PATH = ROOT / "service_worker_shell_baseline.json"

SHELL_BLOCK_RE = re.compile(r"const\s+SHELL_FILES\s*=\s*\[(?P<body>[^\]]+)\]")
PATH_RE = re.compile(r"""['"`](?P<p>[^'"`,]+)['"`]""")


def _resolve(target: str) -> Path | None:
    t = target.strip()
    if not t: return None
    if t.startswith(("http://", "https://", "//", "data:")): return None
    if t == "/": return ROOT / "index.html"
    if t.startswith("/workhive/"): return ROOT / t[len("/workhive/"):]
    if t.startswith("/"): return ROOT / t.lstrip("/")
    return ROOT / t


def main() -> int:
    sw = ROOT / "sw.js"
    if not sw.exists():
        print("FAIL: sw.js missing")
        return 2
    body = sw.read_text(encoding="utf-8", errors="replace")
    m = SHELL_BLOCK_RE.search(body)
    if not m:
        print("FAIL: SHELL_FILES = [...] block not found in sw.js")
        return 2

    paths = [p.group("p") for p in PATH_RE.finditer(m.group("body"))]
    broken = []
    for p in paths:
        resolved = _resolve(p)
        if resolved is None: continue
        if not resolved.exists():
            try:
                rel = resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else resolved
            except Exception:
                rel = resolved
            broken.append({"path": p, "resolved": str(rel)})

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("broken", 0)
        except Exception: baseline = 0
    else:
        baseline = len(broken)
        BASELINE_PATH.write_text(json.dumps({"broken": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(broken) < baseline:
        baseline = len(broken)
        BASELINE_PATH.write_text(json.dumps({"broken": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"total_shell_paths": len(paths),
                    "total_broken": len(broken), "baseline": baseline},
        "broken": broken,
    }, indent=2), encoding="utf-8")

    print(f"\nService Worker SHELL_FILES Validator (L0)")
    print("=" * 56)
    print(f"  shell paths:      {len(paths)}")
    print(f"  broken:           {len(broken)}  (baseline: {baseline})")
    if not broken:
        print("\n  PASS — every SHELL_FILES path resolves to a file.")
        return 0
    for b in broken[:20]:
        print(f"    → {b['path']}  (resolves to: {b['resolved']})")
    return 1 if len(broken) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
