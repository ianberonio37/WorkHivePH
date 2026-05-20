"""
Patch pages flagged by `data_engineer_restore_identity_from_session` to
call `restoreIdentityFromSession(db)` as part of their auth bootstrap.

Surfaced by the AI-derived skill rule on 2026-05-18. The platform's
auth migration (C1-C4) replaced string localStorage identity with
Supabase Auth sessions. Any page still binding WORKER_NAME from
localStorage without also calling restoreIdentityFromSession diverges
from the canonical auth.uid() identity.

This patcher applies a MINIMAL-RISK FIRE-AND-FORGET fix:

  1. Find `(const|let|var)\\s+WORKER_NAME\\s*=\\s*localStorage...`
  2. If `const`, rewrite to `let` so WORKER_NAME is reassignable
  3. Insert immediately after the declaration:

       // Auth C4: refresh WORKER_NAME from Supabase Auth session if
       // localStorage was empty or stale. Fire-and-forget -- the sync
       // auth-check redirect still runs first; the session identity
       // overrides afterwards.
       if (typeof restoreIdentityFromSession === 'function' && typeof db !== 'undefined') {
         restoreIdentityFromSession(db).then(name => { if (name) WORKER_NAME = name; });
       }

Pages WITHOUT a `WORKER_NAME` global (assistant.html, index.html) use
local-scope helpers (`const name = localStorage.getItem(...)`) and need
per-helper review -- this script skips them.

Idempotent: if `restoreIdentityFromSession` is already invoked in the
file, the patch is a no-op.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "skill_rules_mining_report.json"

# Pages to SKIP because they use local-scope identity helpers, not a
# WORKER_NAME global. These need per-helper investigation rather than
# a top-of-bootstrap insertion.
SKIP_FILES = {
    "assistant.html",   # uses `const name = localStorage...` per helper
    "index.html",       # signin/signup page; localStorage reads are by design
    "analytics-report.html",  # uses `var WORKER_NAME` inside a function body
}

# The fire-and-forget restoration block. Carefully written to be
# safe even if utils.js hasn't loaded yet (typeof checks).
RESTORE_BLOCK = """
  // Auth C4: refresh WORKER_NAME from Supabase Auth session if localStorage was
  // empty or stale. Fire-and-forget -- the sync auth-check redirect still runs
  // first; session identity overrides asynchronously.
  if (typeof restoreIdentityFromSession === 'function' && typeof db !== 'undefined') {
    restoreIdentityFromSession(db).then(_n => { if (_n) WORKER_NAME = _n; });
  }
"""

# Capture the entire multi-line `const/let WORKER_NAME = localStorage... || '';`
# declaration. This regex tolerates the multi-line `|| localStorage...` chains
# common in the codebase. Pattern is anchored to start of line + indentation.
WORKER_NAME_DECL_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<kw>const|let|var)\s+WORKER_NAME\s*=\s*localStorage\.getItem\([^;]+;",
    re.MULTILINE,
)

# Already-patched detection.
ALREADY_PATCHED_RE = re.compile(r"\brestoreIdentityFromSession\s*\(", re.IGNORECASE)


def patch_file(path: Path) -> str:
    """Return 'patched' | 'already_patched' | 'no_decl_found' | 'skipped'."""
    if path.name in SKIP_FILES:
        return "skipped"

    text = path.read_text(encoding="utf-8", errors="replace")
    if ALREADY_PATCHED_RE.search(text):
        return "already_patched"

    m = WORKER_NAME_DECL_RE.search(text)
    if not m:
        return "no_decl_found"

    # Rewrite `const` to `let` for reassignability.
    new_decl = m.group(0).replace(f"{m.group('kw')} WORKER_NAME", "let WORKER_NAME", 1)

    insert_at = m.end()
    indent    = m.group("indent")
    block     = "\n".join(indent + line if line else "" for line in RESTORE_BLOCK.splitlines())

    new_text = text[:m.start()] + new_decl + block + text[insert_at:]
    path.write_text(new_text, encoding="utf-8")
    return "patched"


def main() -> int:
    if not REPORT_PATH.exists():
        print(f"ERROR: {REPORT_PATH.name} not found. Run tools/mine_skill_rules.py first.")
        return 1

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    target_rule = next(
        (r for r in report["all_results"]
         if r["rule_id"] == "data_engineer_restore_identity_from_session"),
        None,
    )
    if not target_rule:
        print("Rule not in report; nothing to patch.")
        return 0

    violators = target_rule["violators"]
    print(f"restoreIdentityFromSession patcher")
    print(f"  targets: {len(violators)} page(s)")
    print(f"  skip list: {sorted(SKIP_FILES)}")
    print()

    results = {"patched": [], "already_patched": [], "no_decl_found": [], "skipped": []}
    for name in violators:
        path = ROOT / name
        if not path.exists():
            print(f"  SKIP  {name}  (file not found)")
            continue
        outcome = patch_file(path)
        results[outcome].append(name)
        tag = {"patched": "OK  ", "already_patched": "NOOP",
               "no_decl_found": "WARN", "skipped": "DEFR"}[outcome]
        print(f"  {tag}  {name}")

    print()
    print(f"Summary:")
    print(f"  patched:           {len(results['patched'])}")
    print(f"  already_patched:   {len(results['already_patched'])}")
    print(f"  no_decl_found:     {len(results['no_decl_found'])}  (needs manual review)")
    print(f"  skipped (deferred): {len(results['skipped'])}  (local-scope helpers; need per-helper review)")

    if results["no_decl_found"]:
        print()
        print("Pages where the standard WORKER_NAME declaration wasn't found:")
        for n in results["no_decl_found"]:
            print(f"  - {n}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
