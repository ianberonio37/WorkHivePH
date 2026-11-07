#!/usr/bin/env python3
# DEEPWALK-CELL: * QA
"""skipped_gates_for_diff.py - the skip_if_fast gates a change can reach, so a release runs them (2026-11-06, GJ M11).

★THE PUSH BOARD NEVER RUNS A skip_if_fast GATE, AND TWO SAT RED FROM M8 TO M11. The pre-push hook runs
run_platform_checks.py --fast, which leaves out every gate marked skip_if_fast (616 of them). Two such gates were red
for three milestones with no board showing it:
  - validate_public_read_surface: M8 added auth_own_history_names(), and the gate's caller vocabulary did not know it;
  - validate_removal_tells_the_worker: M8's J14 rewrote the removal notice ("records stay yours"), and the gate still
    looked for "records are still".
Both were found by accident, while a later change touched the same files. A step that depends on someone remembering
which slow gates a change reaches does not happen. So this lists them: every skip_if_fast gate whose script names a file
the change touched (its basename appears in the gate's source). The list is the release's `--only` set for the
skipped half of the board.

    python tools/skipped_gates_for_diff.py                  # changed since origin/master, plus the working tree
    python tools/skipped_gates_for_diff.py --base ffca61fd  # changed since a given commit
    python tools/skipped_gates_for_diff.py --ids            # just the comma-separated ids, for --only
    python tools/skipped_gates_for_diff.py --run            # run them through run_platform_checks.py --only
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_EXT = {".html", ".js", ".mjs", ".cjs", ".ts", ".py", ".sql", ".css"}
# generated or bookkeeping files: a gate that names one is reading a report, not the code the change touched
GENERATED = re.compile(r"(_report\.(json|md)|_baseline\.json|\.md$|^substrate/|^\.tmp/|sentinel_|flywheel_|_ledger\.json)")


def validators() -> list[dict]:
    tree = ast.parse((ROOT / "run_platform_checks.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "VALIDATORS" for t in node.targets):
            out = []
            for e in node.value.elts:
                if not isinstance(e, ast.Dict):
                    continue
                d = {}
                for k, v in zip(e.keys, e.values):
                    if not isinstance(k, ast.Constant):
                        continue
                    if isinstance(v, ast.Constant):
                        d[k.value] = v.value
                    elif isinstance(v, ast.Call) and all(isinstance(a, ast.Constant) for a in v.args):
                        d[k.value] = "/".join(str(a.value) for a in v.args)   # os.path.join("tools", "x.py")
                out.append(d)
            return out
    raise SystemExit("run_platform_checks.py has no VALIDATORS list")


def changed(base: str) -> list[str]:
    def git(*a):
        p = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return [l.strip() for l in p.stdout.splitlines() if l.strip()]
    files = set(git("diff", "--name-only", f"{base}..HEAD")) | set(git("diff", "--name-only")) \
        | set(git("diff", "--name-only", "--cached")) | set(git("ls-files", "--others", "--exclude-standard"))
    return sorted(f for f in files if Path(f).suffix in SOURCE_EXT and not GENERATED.search(f.replace("\\", "/")))


def removed_phrases(base: str, files: list[str]) -> set[str]:
    """Words the change DELETED from the product: each removed line's quoted strings and its plain text, split into
    phrases of 4+ words. A gate that pins one of them is reading copy that no longer exists - the exact shape of both
    stale gates (each looked for a sentence an edit had rewritten)."""
    p = subprocess.run(["git", "diff", "-U0", f"{base}", "--", *files], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = set()
    for line in p.stdout.splitlines():
        if not line.startswith("-") or line.startswith("---"):
            continue
        for frag in re.findall(r"[A-Za-z][A-Za-z ,'’-]{18,}[A-Za-z]", line[1:]):
            # words a person reads, not code: no camelCase identifier (readFileSync), and a phrase is 4+ real words
            words = [w for w in frag.split() if not re.search(r"[a-z][A-Z]", w)]
            if len(words) < 4:
                continue
            for i in range(0, len(words) - 3):
                ph = " ".join(words[i:i + 4])
                if len(ph) >= 18:
                    out.add(ph)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/master")
    ap.add_argument("--ids", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--broad", action="store_true", help="every skip_if_fast gate whose script names a changed file "
                    "(wide: shared files such as utils.js are named by hundreds of gates)")
    a = ap.parse_args()

    files = changed(a.base)
    # an index file is named by its directory (every edge function is an index.ts; every article an index.html)
    def key(f):
        p = Path(f)
        return f"{p.parent.name}/{p.name}" if p.name in ("index.ts", "index.html") and p.parent.name else p.name
    keys = {key(f) for f in files}
    gone = set() if a.broad else removed_phrases(a.base, files)
    hits = []
    for v in validators():
        if not v.get("skip_if_fast") or not v.get("id") or not v.get("script"):
            continue
        script = ROOT / v["script"]
        if not script.exists():
            continue
        src = script.read_text(encoding="utf-8", errors="replace")
        if a.broad:
            named = sorted(k for k in keys if k in src and Path(v["script"]).name != k)
        else:
            # precise (default): the gate pins words this change deleted
            named = sorted({ph for ph in gone if ph in src})[:3]
        if named:
            hits.append((v["id"], named))
    if a.ids or a.run:
        ids = ",".join(i for i, _ in hits)
        if a.run:
            if not ids:
                print("no skip_if_fast gate names a changed file")
                return 0
            return subprocess.call([sys.executable, "run_platform_checks.py", "--only", ids], cwd=ROOT)
        print(ids)
        return 0
    print(f"{len(files)} changed source file(s) since {a.base}; {len(hits)} skip_if_fast gate(s) " + ("name one of them:" if a.broad else "pin words this change deleted:"))
    for i, named in hits:
        print(f"  {i:<44} {', '.join(named[:4])}{' …' if len(named) > 4 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
