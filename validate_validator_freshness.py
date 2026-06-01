r"""
Validator Freshness / Decay Meta-Gate -- P3 of SELF_IMPROVING_GATE_ROADMAP.md
=============================================================================
The #1 real rot vector on this platform is a *validator asserting a literal
or shape the code already moved past* -- the kind of break that stays
invisible until a 13-minute full-gate run trips it (the 2026-05-31 session
hit three at once: model_router `for (const entry of reorderChain(`,
schema_coverage `RE_CREATE_VIEW` not spanning `WITH (...) AS`,
agent_memory_store grepping only `index.ts`). This meta-validator gives the
gate a cheap *freshness sense* at G-1: it runs in well under 5 seconds and
flags decay BEFORE the expensive layers do.

Two layers, two confidence tiers:

  Layer 1 -- Declared anchors must still match their target            [FAIL]
    A validator opts in by declaring a module-level constant:

        FRESHNESS_ANCHORS = [
            # (target_file, regex_pattern, note)
            ("supabase/functions/_shared/ai-chain.ts",
             r"export\s+function\s+reorderChain\s*\(", "M04 core symbol"),
        ]

    For each anchor: the target file must exist AND the pattern must still
    match in it. A miss means the validator is asserting a shape the code
    moved past -- "refresh (broaden/rename) or retire." This is the
    author's curated, load-bearing-literal contract: zero false positives,
    so it is FAIL-level. (Read via ast.literal_eval -- the validator is
    never imported/executed, keeping this meta-gate fast and side-effect
    free.) Patterns are treated as regex, with a plain-substring fallback
    if a pattern is not valid regex.

  Layer 2 -- Decay-suspect census (ledger-cross-referenced)            [INFO]
    The roadmap's discovery half: a *never-fired* validator (per
    gate_efficacy_ledger.json) whose code-under-test changed MORE recently
    than the validator file itself is a prime decay suspect -- it may be
    silently asserting a stale shape and just hasn't been run against the
    new code yet. Advisory only (never FAIL): false positives here would
    erode trust and get the gate `--no-verify`'d, the exact rot P4 guards
    against. The engine drafts the suspect list; a human judges whether to
    refresh, add an anchor, or retire (Rule D).

Exit code is 1 only when a DECLARED anchor is stale/missing. The census
never affects the verdict.

Skills consulted: qa-tester (the suite must audit itself; static assertion
vs. live shape), devops (gate runtime as an SLO; never emit false FAILs),
architect ("engine drafts, human judges" -- anchors are FAIL, discovery is
advisory), data-engineer (cross-source id join: ledger is keyed by gate id,
mapped from the registry script field).
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


ROOT         = Path(__file__).resolve().parent
LEDGER_PATH  = ROOT / "gate_efficacy_ledger.json"
ORCHESTRATOR = ROOT / "run_platform_checks.py"
REPORT_NAME  = "validator_freshness_report.json"

# Extensions that count as "code under test" for the decay-suspect census.
# (We compare these files' mtime to the validator's own mtime; .py/.json are
# excluded so a validator's own report/baseline writes don't look like drift.)
TARGET_EXTS = {".ts", ".js", ".mjs", ".html", ".sql", ".toml", ".css"}

SUSPECT_CAP = 25   # cap census rows surfaced per run
# "Never fired" only means something once a validator has actually been run a
# few times. Below this, the efficacy ledger is too immature to distinguish
# "dead weight" from "just hasn't run yet" -- so the decay census stays empty
# (honest) rather than flagging every validator after a single gate run.
MIN_RUNS_FOR_DECAY = 3


def _list_validators() -> list[Path]:
    return sorted(p for p in ROOT.glob("validate_*.py") if p.is_file())


# -- Layer 1: declared anchors -------------------------------------------------

def _extract_anchors(tree: ast.Module) -> list[tuple[str, str, str]]:
    """Pull (target, pattern, note) tuples from a module-level
    `FRESHNESS_ANCHORS = [...]` via ast.literal_eval. Returns [] when the
    constant is absent or not a pure literal (never executes the file)."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "FRESHNESS_ANCHORS"
                   for t in node.targets):
            continue
        try:
            val = ast.literal_eval(node.value)
        except Exception:
            return []
        out: list[tuple[str, str, str]] = []
        for item in val or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                target, pattern = str(item[0]), str(item[1])
                note = str(item[2]) if len(item) >= 3 else ""
                out.append((target, pattern, note))
        return out
    return []


def _matches(pattern: str, content: str) -> bool:
    """Regex search, falling back to plain substring if the pattern is not
    valid regex (so authors can write `reorderChain(` without escaping)."""
    try:
        return re.search(pattern, content) is not None
    except re.error:
        return pattern in content


def check_declared_anchors() -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    results: list[dict] = []
    for path in _list_validators():
        src = read_file(str(path)) or ""
        if "FRESHNESS_ANCHORS" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue   # broken-file detection belongs to cp1252/self-coverage
        for target, pattern, note in _extract_anchors(tree):
            rel = target.replace("\\", "/").lstrip("/")
            fp = ROOT / rel
            row = {"validator": path.name, "target": rel,
                   "pattern": pattern, "note": note}
            tail = f" [{note}]" if note else ""
            if not fp.is_file():
                row["status"] = "target_missing"
                results.append(row)
                issues.append({
                    "check": "declared_anchor",
                    "reason": (f"{path.name}: anchor target `{rel}` no longer "
                               f"exists -- the file this validator guards was "
                               f"moved/renamed. Update the validator's path "
                               f"constant + anchor, or retire the rule.{tail}"),
                })
                continue
            content = read_file(str(fp)) or ""
            if _matches(pattern, content):
                row["status"] = "fresh"
                results.append(row)
            else:
                row["status"] = "stale"
                results.append(row)
                issues.append({
                    "check": "declared_anchor",
                    "reason": (f"{path.name}: anchor /{pattern}/ no longer "
                               f"matches in `{rel}` -- this validator asserts a "
                               f"shape the code moved past. Refresh the "
                               f"assertion (broaden/rename) or retire it.{tail}"),
                })
    return issues, results


# -- Layer 2: decay-suspect census --------------------------------------------

def _load_ledger() -> tuple[dict, int]:
    """Returns (validators_by_gate_id, runs_observed). runs_observed gates how
    much we trust 'never fired' as a decay signal."""
    try:
        doc = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}, 0
    if not isinstance(doc, dict):
        return {}, 0
    return doc.get("validators", {}) or {}, int(doc.get("runs_observed", 0) or 0)


def _script_to_gate_id() -> dict[str, str]:
    """Map `validate_*.py` -> gate id from the registry. The efficacy ledger
    is keyed by gate id, the filesystem by script name -- this is the join."""
    src = read_file(str(ORCHESTRATOR)) or ""
    src = re.sub(r"^\s*#[^\n]*$", "", src, flags=re.MULTILINE)   # drop comments
    out: dict[str, str] = {}
    # Registry entries list "id" before "script"; handle both orders defensively.
    for m in re.finditer(r'"id"\s*:\s*"(?P<id>[^"]+)"[^{}]*?'
                         r'"script"\s*:\s*"(?P<script>validate_\w+\.py)"',
                         src, re.DOTALL):
        out.setdefault(m.group("script"), m.group("id"))
    for m in re.finditer(r'"script"\s*:\s*"(?P<script>validate_\w+\.py)"[^{}]*?'
                         r'"id"\s*:\s*"(?P<id>[^"]+)"',
                         src, re.DOTALL):
        out.setdefault(m.group("script"), m.group("id"))
    return out


def _referenced_targets(src: str) -> list[tuple[str, float]]:
    """The real code-under-test files a validator reads. Control-flow-free:
    we only need WHICH existing files it references, to compare mtimes.
    Resolves os.path.join(...) literal sequences and bare path literals."""
    rels: set[str] = set()
    for m in re.finditer(r"os\.path\.join\(([^)]*)\)", src):
        parts = re.findall(r'["\']([^"\']+)["\']', m.group(1))
        if parts:
            rels.add("/".join(parts))
    for m in re.finditer(r'["\']([\w./\\-]+\.(?:ts|js|mjs|html|sql|toml|css))["\']',
                         src):
        rels.add(m.group(1))
    out: list[tuple[str, float]] = []
    for rel in rels:
        rel = rel.replace("\\", "/").lstrip("/")
        if "*" in rel:
            continue
        fp = ROOT / rel
        if fp.is_file() and fp.suffix.lower() in TARGET_EXTS:
            try:
                out.append((rel, fp.stat().st_mtime))
            except OSError:
                pass
    return out


def check_decay_suspects() -> tuple[list[dict], int, bool]:
    """Returns (capped_suspects, total, ledger_mature). When the ledger is
    immature (no validator has >= MIN_RUNS_FOR_DECAY runs yet), 'never fired'
    is meaningless, so we surface nothing and say so."""
    led, _runs = _load_ledger()
    s2id = _script_to_gate_id()
    ledger_mature = any(int(v.get("times_run", 0) or 0) >= MIN_RUNS_FOR_DECAY
                        for v in led.values())
    if not ledger_mature:
        return [], 0, False

    suspects: list[dict] = []
    for path in _list_validators():
        name = path.name
        src = read_file(str(path)) or ""
        targets = _referenced_targets(src)
        if not targets:
            continue
        try:
            v_mtime = path.stat().st_mtime
        except OSError:
            continue
        newest_rel, newest_mtime = max(targets, key=lambda t: t[1])
        if newest_mtime <= v_mtime:
            continue   # validator is at least as fresh as the code it guards

        gid = s2id.get(name)
        rec = led.get(gid, {}) if gid else {}
        times_run    = int(rec.get("times_run", 0) or 0)
        true_catches = int(rec.get("true_catches", 0) or 0)
        times_fail   = int(rec.get("times_fail", 0) or 0)
        last_fired   = rec.get("last_fired_run")
        never_fired  = (true_catches == 0 and times_fail == 0 and not last_fired)

        # Only flag a validator the ledger has run enough to trust AND that has
        # never fired (load-bearing validators self-announce by firing). A
        # validator not yet in the ledger is "new", not "decayed" -- skip it
        # (that gap is validator-self-coverage's job).
        if times_run < MIN_RUNS_FOR_DECAY or not never_fired:
            continue

        suspects.append({
            "validator":     name,
            "gate_id":       gid,
            "ledger_status": "never_fired",
            "times_run":     times_run,
            "newest_target": newest_rel,
            "target_newer_by_days": round((newest_mtime - v_mtime) / 86400.0, 1),
            "has_declared_anchors": "FRESHNESS_ANCHORS" in src,
        })

    total = len(suspects)
    # Rank: anchorless first (no curated freshness contract), then biggest
    # staleness gap.
    suspects.sort(key=lambda s: (s["has_declared_anchors"],
                                 -s["target_newer_by_days"]))
    return suspects[:SUSPECT_CAP], total, True


# -- Runner -------------------------------------------------------------------

CHECK_NAMES  = ["declared_anchor", "decay_suspect_census"]
CHECK_LABELS = {
    "declared_anchor":      "L1  Declared FRESHNESS_ANCHORS still match their target file   [FAIL]",
    "decay_suspect_census": "L2  Never-fired validators whose code-under-test out-paces them [INFO]",
}


def main() -> int:
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nValidator Freshness / Decay Meta-Gate (P3)"))
    print("=" * 62)

    validators = _list_validators()
    anchor_issues, anchor_results = check_declared_anchors()
    suspects, suspect_total, ledger_mature = check_decay_suspects()
    # Count validators that actually DECLARE anchors (extracted), not ones that
    # merely mention the constant name (this meta-validator references it too).
    anchored = sorted({r["validator"] for r in anchor_results})

    issues = list(anchor_issues)
    if suspect_total:
        # One SKIP marker so the census line renders yellow (advisory), without
        # spamming the issue list with one row per suspect.
        issues.append({
            "check": "decay_suspect_census", "skip": True,
            "reason": (f"{suspect_total} never-fired validator(s) whose "
                       f"code-under-test changed more recently than the "
                       f"validator -- advisory decay suspects (see census)."),
        })

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    stale = [r for r in anchor_results if r["status"] != "fresh"]
    print(f"\nAnchors:  {len(anchor_results)} declared across "
          f"{len(anchored)} validator(s)  ·  {len(stale)} stale/missing")
    if not ledger_mature:
        print(f"  Decay census: efficacy ledger still immature "
              f"(no validator has >= {MIN_RUNS_FOR_DECAY} runs yet) -- "
              f"census deferred until it accrues history.")
    if suspects:
        print(f"\n{bold('DECAY SUSPECTS (advisory -- never-fired + target out-paces validator)')}")
        print("  " + "-" * 58)
        for s in suspects:
            anchor_tag = "" if s["has_declared_anchors"] else "  [no anchors]"
            print(f"  {s['validator']:<42} +{s['target_newer_by_days']:>5}d  "
                  f"{s['ledger_status']}{anchor_tag}")
        if suspect_total > len(suspects):
            print(f"  ... and {suspect_total - len(suspects)} more "
                  f"(capped at {SUSPECT_CAP}).")

    report = {
        "validator":            "validator_freshness",
        "total_validators":     len(validators),
        "anchored_validators":  len(anchored),
        "declared_anchors":     len(anchor_results),
        "stale_anchors":        len(stale),
        "ledger_mature":        ledger_mature,
        "decay_suspect_total":  suspect_total,
        "anchor_results":       anchor_results,
        "decay_suspects":       suspects,
        "failed":               n_fail,
    }
    with open(REPORT_NAME, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    if n_fail == 0:
        tail = f" ({suspect_total} advisory decay suspect(s))" if suspect_total else ""
        print(f"\n\033[92m  PASS  -- 0 stale declared anchors{tail}\033[0m")
        return 0
    print(f"\n\033[91m  FAIL  -- {n_fail} stale/missing declared anchor(s) "
          f"(validators asserting a shape the code moved past)\033[0m")
    return 1


if __name__ == "__main__":
    sys.exit(main())
