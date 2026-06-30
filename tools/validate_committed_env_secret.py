#!/usr/bin/env python3
"""
validate_committed_env_secret.py - Arc R (S-lens) gate: no real secret in a tracked .env.* file.
================================================================================================
The platform's existing secret scanner (validate_hardcoded_secrets.py) only opens
*.html / *.js / *.ts / *.py - so a credential committed inside a dotfile like
`.env.roboflow` is INVISIBLE to it. And a `.gitignore` line is a NO-OP for a file that
was already `git add`-ed before the ignore rule existed (git keeps tracking it).

This gate closes that hole: it asks git for every TRACKED file matching `.env*`, excludes
the legitimate placeholder variants (*.example/*.sample/*.template), and FAILs if any of
them contains a line whose value looks like a REAL secret (not a placeholder).

Discriminator (classify by evidence, not by name): a `.env.example` with `KEY=` blank or
`KEY=YOUR_..._HERE` is fine; a tracked `.env.roboflow` with `ROBOFLOW_API_KEY=klWK...20chars`
is a committed credential = FAIL.

Self-test (--self-test): proves the detector has TEETH - it must FLAG a real-looking value
and PASS a placeholder - independent of the current repo state.

Exit 0 = no tracked .env.* secret. Exit 1 = a committed credential (or self-test fail).
"""
from __future__ import annotations
import io, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_committed_env_secret"]

PLACEHOLDER_SUFFIXES = (".example", ".sample", ".template", ".dist")
# A value is a PLACEHOLDER (safe) if it is empty or matches one of these.
PLACEHOLDER_RX = re.compile(
    r"^\s*$|your_|_here|changeme|placeholder|xxx+|\.\.\.|<[^>]+>|example|dummy|sample|todo|replace[_-]?me",
    re.IGNORECASE,
)
# A value LOOKS like a real secret if it is a long, dense token.
SECRET_VALUE_RX = re.compile(r"^[A-Za-z0-9_\-\.=+/]{12,}$")
# Lines we never treat as secrets even if long (public by design).
PUBLIC_KEY_HINTS = ("PUBLISHABLE", "PUBLIC", "ANON_KEY", "PK_", "SUPABASE_URL", "_URL", "PROJECT_REF")


def _is_real_secret(key: str, value: str) -> bool:
    v = value.strip().strip('"').strip("'")
    if PLACEHOLDER_RX.search(v):
        return False
    if not SECRET_VALUE_RX.match(v):
        return False
    ku = key.upper()
    if any(h in ku for h in PUBLIC_KEY_HINTS):
        return False
    return True


def _scan_text(text: str) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, value = s.partition("=")
        if _is_real_secret(key.strip(), value):
            hits.append((i, key.strip()))
    return hits


def _tracked_env_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"{Y}WARN: git unavailable ({e}) - cannot enumerate tracked files.{X}")
        return []
    files = []
    for f in out.stdout.splitlines():
        base = f.split("/")[-1]
        if base.startswith(".env") and not base.lower().endswith(PLACEHOLDER_SUFFIXES):
            files.append(f)
    return files


def self_test() -> bool:
    ok = True
    real = _scan_text("ROBOFLOW_API_KEY=klWKGsoDczmLjxyTbxUU\nFOO=bar")
    if not any(k == "ROBOFLOW_API_KEY" for _, k in real):
        print(f"{R}self-test FAIL: did not flag a real-looking key.{X}"); ok = False
    placeholder = _scan_text("ROBOFLOW_API_KEY=YOUR_KEY_HERE\nGROQ_API_KEY=\nSUPABASE_ANON_KEY=eyJhbGciOiJIUzI1Nireferencelonganonkey")
    if placeholder:
        print(f"{R}self-test FAIL: flagged a placeholder/public value: {placeholder}{X}"); ok = False
    print((G + "self-test PASS - detector has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1

    findings = []
    for rel in _tracked_env_files():
        p = ROOT / rel
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line, key in _scan_text(text):
            findings.append((rel, line, key))

    print(f"{B}Committed .env secret gate (Arc R / S-lens){X}")
    if findings:
        for rel, line, key in findings:
            print(f"  {R}FAIL{X} {rel}:{line}  -> {key} (real secret value in a TRACKED dotfile)")
        print(f"{R}FAIL: {len(findings)} committed credential(s).{X}")
        print(f"{Y}Remediate: git rm --cached <file>; rotate the key; scrub history (BFG/filter-repo).{X}")
        return 1
    print(f"{G}PASS - no real secret in any tracked .env.* file.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
