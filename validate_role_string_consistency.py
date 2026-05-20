"""
Role String Consistency Validator (L0, ratcheted).
====================================================
Permission gates compare `HIVE_ROLE === 'X'` / `role === 'X'` strings.
If two pages use different strings for the same conceptual role (e.g.
'supervisor' vs 'admin', 'worker' vs 'member'), one gate fails closed
or fails open. Class of bug: privilege drift after refactor.

Detection
  Collect every literal `=== 'X'` or `=== "X"` where the LHS contains
  `ROLE`, `role`, `_role`. Build a frequency table of role string values
  across files. Flag values that appear ONCE across the codebase (likely
  typos or stale strings) OR are not in the canonical role set.

Canonical role strings (extend if new roles ship):
  supervisor · worker · admin · platform_admin · founder · viewer

Allow with `// role-allow: <reason>` near the comparison.
Output: role_string_consistency_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "role_string_consistency_report.json"
BASELINE_PATH = ROOT / "role_string_consistency_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

# Canonical role strings used across the platform.
CANONICAL_ROLES = {
    "supervisor", "worker", "admin", "platform_admin", "founder", "viewer",
    "owner",  # marketplace context
}

# Match `<ident-containing-role> === 'X'` / `<ident-containing-role> !== 'X'`
ROLE_CMP_RE = re.compile(
    r"""(?P<ident>\b\w*[Rr]ole\w*)\s*(?:===|!==|==|!=)\s*['"`](?P<val>[^'"`]+)['"`]""",
)

ALLOW_RE = re.compile(r"role-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def main() -> int:
    files: list[tuple[str, Path]] = [(n, ROOT / n) for n in PAGES]
    for js in sorted(ROOT.glob("*.js")):
        if js.name == "sw.js": continue
        files.append((js.name, js))
    edge = ROOT / "supabase" / "functions"
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            files.append((ts.relative_to(ROOT).as_posix(), ts))

    # role_value → {filename}
    value_files: dict[str, set[str]] = defaultdict(set)

    for fname, path in files:
        if not path.exists(): continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        for m in ROLE_CMP_RE.finditer(body):
            val = m.group("val")
            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win): continue
            value_files[val].add(fname)

    # Drift class 1: non-canonical role string (not in CANONICAL_ROLES)
    # Drift class 2: role value used exactly once across the codebase (singleton — typo candidate)
    drift: list[dict] = []
    for val, files_set in sorted(value_files.items()):
        if val in CANONICAL_ROLES: continue
        # Skip values that are obviously NOT roles (empty, '*', booleans, numbers)
        if val.lower() in {"true", "false", "null", "undefined", "*", "all", ""}:
            continue
        # Skip very long values (likely full strings, not role tokens)
        if len(val) > 32: continue
        # Skip values that contain spaces or special chars
        if re.search(r"\s", val): continue
        drift.append({
            "value":      val,
            "files":      sorted(files_set),
            "occurrence": len(files_set),
        })

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = len(drift)
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(drift) < baseline:
        baseline = len(drift)
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_scanned": len(files), "drift": len(drift), "baseline": baseline,
                    "canonical_roles": sorted(CANONICAL_ROLES)},
        "drift": drift,
    }, indent=2), encoding="utf-8")

    print(f"\nRole String Consistency Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {len(files)}")
    print(f"  drift values:     {len(drift)}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every role-string comparison uses a canonical value.")
        return 0
    for d in drift[:20]:
        print(f"  '{d['value']}'  ({d['occurrence']} file{'s' if d['occurrence']!=1 else ''})  → {', '.join(d['files'][:5])}{'...' if len(d['files'])>5 else ''}")
    return 1 if len(drift) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
